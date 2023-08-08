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
	# id - id
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
		"PRIMARY KEY('id'))"
	)

	# Таблица groups
	# id - id
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

	# Таблица pairs
	cur.execute(
		"CREATE TABLE IF NOT EXISTS pairs("
		"id INTEGER,"
		"gid INTEGER,"
		"day DATE,"
		"time DATETIME,"
		"sort INTEGER,"
		"name TEXT,"
		"cab INTEGER,"
		"teacher_id INTEGER,"
		"label TEXT,"
		"PRIMARY KEY('id'))"
	)

	# Таблица teachers
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

def cmdAddScheduleRecord(gid, date, time, sort, name, cab, teacher_id, label):
	"""Добавляет запись о паре в таблицу pairs"""
	cur.execute(
		"INSERT INTO pairs (gid, day, time, sort, name, cab, teacher_id, label) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
		(gid, date, time, sort, name, cab, teacher_id, label)
	)
	db.commit()

def cmdGetTeacherId(name):
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

if __name__ == "__main__":
	start()
