# database.py
# Модуль для работы с БД

import sqlite3 as sql

# https://stackoverflow.com/a/3300514
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

db = sql.connect("db.sqlite3")
db.row_factory = dict_factory
cur = db.cursor()

def start():
	"""Создаёт необходимые таблицы в базе данных"""
	# Таблица users
	# vk_id - id ВКонтакте
	# state - состояние пользователя
	# admin - администратор ли
	# type - тип пользователя (0 - неопределено, 1 - студент, 2 - преподаватель)
	# question_progress - прогресс вопросов
	# allows_mail - разрешена ли рассылка
	# gid - id группы преподавателя/студента
	# journal_login - логин в ЭЖ
	# joirnal_password - пароль в ЭЖ
	# teacher_id - id учителя
	cur.execute(
		"CREATE TABLE IF NOT EXISTS users("
		"id INTEGER,"
		"vk_id INTEGER,"
		"state INTEGER DEFAULT -1,"
		"admin INTEGER DEFAULT 0,"
		"type INTEGER DEFAULT 0,"
		"question_progress INTEGER DEFAULT 1,"
		"allows_mail INTEGER DEFAULT 0,"
		"gid INTEGER,"
		"journal_login TEXT,"
		"journal_password TEXT,"
		"teacher_id INTEGER,"
		"PRIMARY KEY('id'))"
	)

	# Таблица groups
	# course - номер курса
	# spec - специальность
	# join_year - год поступления
	# class_teacher_id - id вконтакте классрука
	cur.execute(
		"CREATE TABLE IF NOT EXISTS groups("
		"id INTEGER,"
		"course INTEGER,"
		"spec TEXT,"
		"join_year INTEGER,"
		"class_teacher_id INTEGER,"
		"PRIMARY KEY('id'))"
	)

	# Таблица schedules - расписания занятий
	# gid - id группы расписания
	# day - день расписания
	# photo_id - id фото вконтакте для этого расписания
	# can_clean - можно ли очисить
	cur.execute(
		"CREATE TABLE IF NOT EXISTS schedules("
		"id INTEGER,"
		"gid INTEGER,"
		"day DATE,"
		"photo_id INTEGER DEFAULT NULL,"
		"can_clean INTEGER DEFAULT 0,"
		"PRIMARY KEY('id'))"
	)

	# Таблица pairs
	# schedule_id - id расписания для пары
	# time - время пары
	# sort - переменная для сортировки
	# name - название пары
	cur.execute(
		"CREATE TABLE IF NOT EXISTS pairs("
		"id INTEGER,"
		"schedule_id INTEGER,"
		"time DATETIME,"
		"sort INTEGER,"
		"name TEXT,"
		"PRIMARY KEY('id'),"
		"FOREIGN KEY('schedule_id') REFERENCES 'schedules'('id') ON DELETE CASCADE)"
	)

	# Таблица pairs_places
	# pair_id - id пары
	# teacher_id - id преподавателя, ведущего пару
	# place - место пары
	cur.execute(
		"CREATE TABLE IF NOT EXISTS pairs_places("
		"id INTEGER,"
		"pair_id INTEGER,"
		"teacher_id INTEGER,"
		"place TEXT,"
		"PRIMARY KEY('id'),"
		"FOREIGN KEY('pair_id') REFERENCES 'pairs'('id') ON DELETE CASCADE)"
	)

	# Таблица teachers
	# surname - фамилия
	cur.execute(
		"CREATE TABLE IF NOT EXISTS teachers("
		"id INTEGER,"
		"surname TEXT,"
		"PRIMARY KEY('id'))"
	)

	db.commit()

def cmdGetUserInfo(uid):
	"""Возвращает информацию о пользователе в словаре из таблицы users"""
	response = cur.execute(
		"SELECT * FROM users WHERE vk_id=?",
		(uid,)
	).fetchone()

	return response

def cmdCreateUser(vid):
	"""Создаёт пользователя"""
	cur.execute(f"INSERT INTO users (vk_id, state) VALUES (?, 0)", (vid,))
	db.commit()

def cmdGetGroupsByCourse(num):
	"""Выбирает все группы по заданному курсу"""
	response = cur.execute(f"SELECT id, spec FROM groups WHERE course=?", (num,)).fetchall()
	return response

def cmdSaveUser(user):
	"""Сохраняет все данные пользователя"""
	cur.execute(
		"UPDATE users SET state=?, type=?, question_progress=?",
		(user['state'], user['type'], user['question_progress']))
	db.commit()

def cmdGetGidFromString(name):
	"""Возвращает id группы с названием name. Формат name: <Номер курса> <специальность>"""
	try:
		course, spec = name.split(' ')
	except ValueError:
		return False
	response = cur.execute("SELECT id FROM groups WHERE course = ? AND spec = ?", (course, spec)).fetchone()
	if not response:
		return False
	else:
		return response['id']

def getTeacherId(name):
	"""Возвращает id преподавателя"""
	response = cur.execute("SELECT id FROM teachers WHERE surname = ?", (name,)).fetchone()
	if not response:
		return False
	else:
		return response['id']

def cmdGetDates():
	"""Возвращает даты которые есть в pairs"""
	response = cur.execute("SELECT DISTINCT day, label FROM pairs").fetchall()
	if not response:
		return False
	else:
		return response

def getPairsForGroup(gid, date):
	"""Возвращает пары для группы на заданную дату"""
	response = cur.execute(
		"SELECT time, name, places FROM pairs"
		"LEFT JOIN schedules ON pairs.schedule_id = schedules.id"
		"WHERE schedules.gid=? AND schedules.day=?"
		"ORDER BY pairs.sort",
		(gid, date)
	).fetchall()
	return response

def getScheduleId(gid, date):
	"""Возвращает id расписания на основании группы и даты"""
	response = cur.execute("SELECT id FROM schedules WHERE gid=? AND day=?", (gid, date)).fetchone()
	if not response:
		return False
	else:
		return response['id']

def addSchedule(gid, date):
	"""Добавляет запись расписания. Возвращает id добавленной записи"""
	cur.execute("INSERT INTO schedules (gid, day) VALUES(?, ?)", (gid, date))
	db.commit()
	return cur.lastrowid

def getIfCanCleanSchedule(schedule_id):
	"""Возвращает true если расписание можно очисить"""
	response = cur.execute("SELECT can_clean FROM schedules WHERE id=?", (schedule_id,)).fetchone()
	return response['can_clean']

def cleanSchedule(schedule_id):
	"""Очищает расписание, затем запрещает его очищать до тех пор пока can_clean не станет 1"""
	cur.execute("DELETE FROM pairs WHERE schedule_id=?", (schedule_id,))
	cur.execute("UPDATE schedules SET can_clean=0 WHERE schedule_id=?", (schedule_id, ))
	db.commit()

def addPair(schedule_id, time, sort, name):
	"""Добавляет запись пары"""
	cur.execute("INSERT INTO pairs (schedule_id, time, sort, name) VALUES(?, ?, ?, ?)", (schedule_id, time, sort, name))
	db.commit()
	return cur.lastrowid

def addPairPlace(pair_id, teacher_id, place):
	"""Добавляем место паре"""
	cur.execute("INSERT INTO pairs_places (pair_id, teacher_id, place) VALUES(?, ?, ?)", (pair_id, teacher_id, place))
	db.commit()

def makeSchedulesCleanable():
	"""Позволяет всем расписаниям очиститься"""
	cur.execute("UPDATE schedules SET can_clean=1")
	db.commit()

if __name__ == "__main__":
	start()
