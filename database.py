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
	# class_teacher_vid - id вконтакте классрука
	cur.execute(
		"CREATE TABLE IF NOT EXISTS groups("
		"id INTEGER,"
		"course INTEGER,"
		"spec TEXT,"
		"join_year INTEGER,"
		"class_teacher_vid INTEGER,"
		"PRIMARY KEY('id'))"
	)

	# Таблица schedules - расписания занятий
	# gid - id группы расписания
	# day - день расписания
	# photo_id - id фото вконтакте для этого расписания
	# human_date - удобная дата
	cur.execute(
		"CREATE TABLE IF NOT EXISTS schedules("
		"id INTEGER,"
		"gid INTEGER,"
		"day DATE,"
		"photo_id INTEGER DEFAULT NULL,"
		"human_date TEXT,"
		"PRIMARY KEY('id'))"
	)

	# Таблица pairs
	# schedule_id - id расписания для пары
	# time - время пары
	# sort - переменная для сортировки
	# places - удобные места пары
	# name - название пары
	cur.execute(
		"CREATE TABLE IF NOT EXISTS pairs("
		"id INTEGER,"
		"schedule_id INTEGER,"
		"time DATETIME,"
		"sort INTEGER,"
		"places TEXT,"
		"name TEXT,"
		"PRIMARY KEY('id'),"
		"FOREIGN KEY('schedule_id') REFERENCES 'schedules'('id') ON DELETE CASCADE)"
	)

	# Таблица pair_places
	# pair_id - id пары
	# teacher_id - id преподавателя, ведущего пару
	# place - место пары
	cur.execute(
		"CREATE TABLE IF NOT EXISTS pair_places("
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

def getPairs(gid, date):
	"""Возвращает пары группы на заданную дату"""
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

def addSchedule(gid, date, short_date):
	"""Добавляет запись расписания. Возвращает id добавленной записи"""
	cur.execute("INSERT INTO schedules (gid, day, human_date) VALUES(?, ?, ?)", (gid, date, short_date))
	db.commit()
	return cur.lastrowid

def addPair(schedule_id, time, sort, name):
	"""Добавляет запись пары"""
	cur.execute("INSERT INTO pairs (schedule_id, time, sort, name) VALUES(?, ?, ?, ?)", (schedule_id, time, sort, name))
	db.commit()
	return cur.lastrowid

def addPairPlace(pair_id, teacher_id, place):
	"""Добавляем место паре"""
	cur.execute("INSERT INTO pair_places (pair_id, teacher_id, place) VALUES(?, ?, ?)", (pair_id, teacher_id, place))
	db.commit()

def updatePairPlacesText(pair_id, places):
	"""Обновляет places у пары"""
	cur.execute("UPDATE pairs SET places=? WHERE id=?", (places, pair_id))
	db.commit()

if __name__ == "__main__":
	start()
