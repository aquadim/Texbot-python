# database.py
# Модуль для работы с БД

import sqlite3 as sql

# https://stackoverflow.com/a/3300514
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

db = sql.connect("db.sqlite3", isolation_level=None, timeout=10, check_same_thread=False)
db.row_factory = dict_factory
db.execute("PRAGMA journal_mode=WAL")
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

	# Таблица users_grades
	# user_id - id пользователя
	# date_create - дата создания
	# photo_id - id фотографии
	cur.execute(
		"CREATE TABLE IF NOT EXISTS users_grades("
		"id INTEGER,"
		"user_id INTEGER,"
		"date_create DATETIME,"
		"photo_id INTEGER,"
		"PRIMARY KEY('id'),"
		"FOREIGN KEY('user_id') REFERENCES 'users'('id') ON DELETE CASCADE)"
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

def stop():
	"""Чисто закрывает соединение с БД"""
	db.close()

# Пользователи
def getUserInfo(uid):
	"""Возвращает информацию о пользователе в словаре из таблицы users"""
	response = cur.execute(
		"SELECT * FROM users WHERE vk_id=?",
		(uid,)
	).fetchone()

	return response

def createUser(vid):
	"""Создаёт пользователя"""
	cur.execute(f"INSERT INTO users (vk_id, state) VALUES (?, 0)", (vid,))
	db.commit()

def saveUserData(user):
	"""Сохраняет все данные пользователя"""
	cur.execute(
		"UPDATE users SET state=?, type=?, question_progress=?, allows_mail=?, gid=?, journal_login=?, journal_password=?, teacher_id=?",
		(user['state'], user['type'], user['question_progress'], user['allows_mail'], user['gid'], user['journal_login'], user['journal_password'], user['teacher_id']))
	db.commit()

# Группы
def getGroupsByCourse(num):
	"""Выбирает все группы по заданному курсу"""
	response = cur.execute(f"SELECT id, spec FROM groups WHERE course=?", (num,)).fetchall()
	return response

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

def getGroupName(gid):
	"""Возвращает название группы по gid"""
	response = cur.execute("SELECT course, spec FROM groups WHERE id=?", (gid,)).fetchone()
	return str(response['course']) + ' ' + response['spec']

# Преподаватели
def getTeacherId(name):
	"""Возвращает id преподавателя"""
	response = cur.execute("SELECT id FROM teachers WHERE surname = ?", (name,)).fetchone()
	if not response:
		return False
	else:
		return response['id']

# Функция: Расписание (для студента)
def getScheduleDatesByGid(gid):
	"""Возвращает актуальные даты расписаний для данной группы"""
	response = cur.execute(
		"SELECT id, day FROM schedules WHERE day < date('now', '+3 days') AND gid=?",
		(gid,)
	).fetchall()
	if not response:
		return False
	else:
		return response

def getScheduleDataForGroup(schedule_id):
	"""Возвращает кэшированное photo_id, дату расписания и группу"""
	response = cur.execute("SELECT photo_id, day, gid FROM schedules WHERE id=?", (schedule_id,)).fetchone()
	if not response:
		return False
	else:
		return response

def getPairsForGroup(schedule_id):
	"""Возвращает пары для группы на заданную дату"""
	response = cur.execute(
		"SELECT pairs.time as pair_time, pairs.name as pair_name, group_concat(teachers.surname || ' ' || pairs_places.place, '/') as pair_place FROM pairs "
		"LEFT JOIN schedules ON pairs.schedule_id = schedules.id "
		"LEFT JOIN pairs_places ON pairs.id = pairs_places.pair_id "
		"LEFT JOIN teachers ON teachers.id = pairs_places.teacher_id "
		"WHERE schedules.id=? "
		"GROUP BY pairs.id "
		"ORDER BY pairs.sort ",
		(schedule_id,)
	).fetchall()
	pairs = []
	for row in response:
		pairs.append((row['pair_time'], row['pair_name'], row['pair_place']))
	return pairs

# Функция: Оценки
def getMostRecentGradesImage(user_id):
	"""Возвращает самое недавнее photo_id для оценок пользователя"""
	# -10 minute - оценки за последние 10 минут
	response = cur.execute("SELECT photo_id FROM users_grades WHERE date_create > datetime('now', 'localtime', '-10 minute') ORDER BY date_create DESC LIMIT 1").fetchone()
	if not response:
		return False
	else:
		return response['photo_id']

def addGradesRecord(user_id, photo_id):
	"""Добавляет кэшированное фото оценок"""
	cur.execute("INSERT INTO users_grades (user_id, date_create, photo_id) VALUES(?, DATETIME('now', 'localtime'), ?)", (user_id, photo_id))
	db.commit()

# Функция: Что дальше?
def getNextPairForGroup(gid):
	"""Возвращает следующую пару для группы и оставшееся до неё время в днях"""
	response = cur.execute(
		"SELECT "
			"pairs.time AS pair_time, "
			"pairs.name AS pair_name, "
			"group_concat(teachers.surname || ' ' || pairs_places.place, '/') AS pair_place, "
			"julianday(schedules.day, pairs.time) - julianday('now', 'localtime') AS dt "
		"FROM schedules "
			"LEFT JOIN pairs ON pairs.schedule_id = schedules.id "
			"LEFT JOIN pairs_places ON pairs.id = pairs_places.pair_id "
			"LEFT JOIN teachers ON teachers.id = pairs_places.teacher_id "
		"WHERE gid=? AND datetime(schedules.day, pairs.time) > datetime('now', 'localtime') "
		"GROUP BY pairs.id "
		"ORDER BY schedules.day ASC, pairs.time ASC "
		"LIMIT 1 ",
		(gid,)
	).fetchone()

	if not response:
		return False
	else:
		return response

# Парсинг расписания
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
	return cur.lastrowid

def getIfCanCleanSchedule(schedule_id):
	"""Возвращает true если расписание можно очисить"""
	response = cur.execute("SELECT can_clean FROM schedules WHERE id=?", (schedule_id,)).fetchone()
	return response['can_clean']

def cleanSchedule(schedule_id):
	"""Очищает расписание, затем запрещает его очищать до тех пор пока can_clean не станет 1"""
	cur.execute("DELETE FROM pairs WHERE schedule_id=?", (schedule_id,))
	cur.execute("UPDATE schedules SET can_clean=0, photo_id=NULL WHERE id=?", (schedule_id, ))

def addPair(schedule_id, time, sort, name):
	"""Добавляет запись пары"""
	cur.execute("INSERT INTO pairs (schedule_id, time, sort, name) VALUES(?, ?, ?, ?)", (schedule_id, time, sort, name))
	return cur.lastrowid

def addPairPlace(pair_id, teacher_id, place):
	"""Добавляем место паре"""
	cur.execute("INSERT INTO pairs_places (pair_id, teacher_id, place) VALUES(?, ?, ?)", (pair_id, teacher_id, place))

def makeSchedulesCleanable():
	"""Позволяет всем расписаниям очиститься"""
	cur.execute("UPDATE schedules SET can_clean=1")
	db.commit()

def addCacheToSchedule(schedule_id, photo_id):
	"""Добавляет photo_id к расписанию"""
	cur.execute("UPDATE schedules SET photo_id=? WHERE id=?", (photo_id, schedule_id))
	db.commit()


def getPairInfo(pair_id, get_teachers_by_id):
	"""Возвращает информацию о паре в формате: (time, name, ((teacher_id, place), (teacher_id, place), (...)))"""
	response_main = cur.execute("SELECT time, name FROM pairs WHERE id=?", (pair_id,)).fetchone()

	# Получаем данные проведении
	# ~ if get_teachers_by_id:
		# ~ places_query = "SELECT teacher_id as t, place as p FROM pairs_places WHERE pair_id=?"
	# ~ else:
		# ~ places_query =
			# ~ "SELECT teachers_surname as t, pairs_places.place "
			# ~ "FROM pairs_places LEFT JOIN teachers ON pairs_places.teacher_id=teachers.id"
			# ~ "WHERE pairs_places.pair_id=?"
	# ~ response_places = cur.execute(places_query, (pair_id,)).fetchall()

	# Собираем вывод
	output_places = []
	for row in response_places:
		output_places.append((row['t'], row['p']))
	return (response_main['time'], response_main['name'], tuple(output_places))

if __name__ == "__main__":
	start()
