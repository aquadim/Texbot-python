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

	# Таблица users_grades - оценки пользователей
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

	# Таблица groups - группы техникума
	# course - номер курса
	# spec - специальность
	# join_year - год поступления
	cur.execute(
		"CREATE TABLE IF NOT EXISTS groups("
		"id INTEGER,"
		"course INTEGER,"
		"spec TEXT,"
		"join_year INTEGER,"
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
	# ptime - время пары
	# sort - переменная для сортировки
	# name - название пары
	cur.execute(
		"CREATE TABLE IF NOT EXISTS pairs("
		"id INTEGER,"
		"schedule_id INTEGER,"
		"ptime DATETIME,"
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

	# Таблица teachers_schedule_cache - хранение photo_id для расписаний преподавателя
	cur.execute(
		"CREATE TABLE IF NOT EXISTS teachers_schedule_cache("
		"id INTEGER,"
		"day DATE,"
		"teacher_id INTEGER,"
		"photo_id INTEGER,"
		"PRIMARY KEY('id'),"
		"FOREIGN KEY('teacher_id') REFERENCES 'teachers'('id') ON DELETE CASCADE ON UPDATE CASCADE)"
	)

	# Таблица stats
	cur.execute(
		"CREATE TABLE IF NOT EXISTS stats("
		"id INTEGER,"
		"caller_gid INTEGER,"
		"caller_teacher INTEGER,"
		"func_id INTEGER,"
		"date_create DATETIME,"
		"PRIMARY KEY('id'))"
	)

	# Таблица function_names
	cur.execute(
		"CREATE TABLE IF NOT EXISTS function_names("
		"id INTEGER,"
		"name TEXT,"
		"PRIMARY KEY('id'))"
	)

	# Таблица occupancy_cache - кэширование занятости кабинетов
	# day - дата
	# place - место
	# photo_id - id фото
	cur.execute(
		"CREATE TABLE IF NOT EXISTS occupancy_cache("
		"id INTEGER,"
		"day DATE,"
		"place TEXT,"
		"photo_id INTEGER,"
		"PRIMARY KEY('id'))"
	)

	cur.execute(
		"CREATE TABLE IF NOT EXISTS mails ("
		"id INTEGER,"
		"target TEXT,"
		"message TEXT,"
		"author INTEGER,"
		"date_create DATETIME,"
		"PRIMARY KEY('id'))"
	)

	# https://ru.stackoverflow.com/a/1537321/418543
	# Триггер очистки записей кэширования
	cur.execute(
		"CREATE TRIGGER IF NOT EXISTS schedule_cleaner AFTER DELETE ON schedules "
		"BEGIN "
			"DELETE FROM teachers_schedule_cache WHERE teachers_schedule_cache.day = OLD.day;"
			"DELETE FROM occupancy_cache WHERE occupancy_cache.day = OLD.day;"
		"END"
	)

	# Триггер очистки мест пар (потому что почему то связь трёх таблиц не работает)
	cur.execute(
		"CREATE TRIGGER IF NOT EXISTS pairs_cleaner AFTER DELETE ON pairs "
		"BEGIN "
			"DELETE FROM pairs_places WHERE pairs_places.pair_id = OLD.id;"
		"END"
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
		"UPDATE users SET state=?, type=?, question_progress=?, allows_mail=?, gid=?, journal_login=?, journal_password=?, teacher_id=? WHERE vk_id=?",
		(user['state'], user['type'], user['question_progress'], user['allows_mail'], user['gid'], user['journal_login'], user['journal_password'], user['teacher_id'], user['vk_id']))
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

def getTeacherSurname(teacher_id):
	"""Возвращает фамилию преподавателя"""
	return cur.execute("SELECT surname FROM teachers WHERE id=?", (teacher_id,)).fetchone()['surname']

# Функция: Расписание (для группы)
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

def getScheduleDataForGroup(date, gid):
	"""Возвращает кэшированное photo_id расписания"""
	response = cur.execute("SELECT photo_id FROM schedules WHERE day=? AND gid=?", (date,gid)).fetchone()
	if not response:
		return False
	else:
		return response

def getPairsForGroup(schedule_id):
	"""Возвращает пары для группы на заданную дату"""
	response = cur.execute(
		"SELECT pairs.ptime as pair_time, pairs.name as pair_name, group_concat(teachers.surname || ' ' || ifnull(pairs_places.place,'н/д'), '/') as pair_place FROM pairs "
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

# Функция: Где преподаватель
def getAllTeachers():
	"""Возвращает всех преподаватей"""
	response = cur.execute("SELECT * FROM teachers ORDER BY surname ASC").fetchall()
	return response

def getRelevantScheduleDates():
	"""Возвращает актуальные даты расписания"""
	response = cur.execute("SELECT DISTINCT day FROM schedules WHERE day BETWEEN date('now') and date('now', '+3 days')").fetchall()
	if not response:
		return False
	else:
		return response

def getScheduleDataForTeacher(date, teacher_id):
	"""Возвращает данные пар для преподавателя"""
	response = cur.execute(
		"SELECT pairs.ptime as pair_time, pairs.name as pair_name, ifnull(pairs_places.place,'н/д') as pair_place, groups.course || groups.spec as group_name "
		"FROM pairs_places "
			"LEFT JOIN pairs ON pairs.id = pairs_places.pair_id "
			"LEFT JOIN schedules ON schedules.id = pairs.schedule_id "
			"LEFT JOIN groups ON groups.id = schedules.gid "
		"WHERE pairs_places.teacher_id = ? AND schedules.day=?"
		"ORDER BY pairs.ptime ASC",
		(teacher_id, date)
	).fetchall()
	if not response:
		return False
	pairs = []
	for row in response:
		pairs.append((row['pair_time'], row['pair_name'], row['pair_place'], row['group_name']))
	return pairs

def getCachedScheduleOfTeacher(date, teacher_id):
	"""Возвращает кэшированное расписание преподавателя"""
	return cur.execute(
		"SELECT photo_id FROM teachers_schedule_cache WHERE day=? AND teacher_id=?", (date, teacher_id)
	).fetchone()

def addCachedScheduleOfTeacher(date, teacher_id, photo_id):
	"""Добавляет кэшированное расписание преподавателя"""
	cur.execute("INSERT INTO teachers_schedule_cache (day,teacher_id,photo_id) VALUES(?,?,?)", (date, teacher_id, photo_id))
	db.commit()

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
			"pairs.ptime AS pair_time, "
			"pairs.name AS pair_name, "
			"group_concat(teachers.surname || ' ' || ifnull(pairs_places.place,'н/д'), '/') AS pair_place, "
			"julianday(schedules.day, pairs.ptime) - julianday('now', 'localtime') AS dt "
		"FROM schedules "
			"LEFT JOIN pairs ON pairs.schedule_id = schedules.id "
			"LEFT JOIN pairs_places ON pairs.id = pairs_places.pair_id "
			"LEFT JOIN teachers ON teachers.id = pairs_places.teacher_id "
		"WHERE gid=? AND datetime(schedules.day, pairs.ptime) > datetime('now', 'localtime') "
		"GROUP BY pairs.id "
		"ORDER BY schedules.day ASC, pairs.ptime ASC "
		"LIMIT 1 ",
		(gid,)
	).fetchone()

	if not response:
		return False
	else:
		return response

def getNextPairForTeacher(teacher_id):
	"""Возвращает следующую пару для группы и оставшееся до неё время в днях"""
	response = cur.execute(
		"SELECT "
			"pairs.ptime AS pair_time,"
			"pairs.name AS pair_name,"
			"ifnull(pairs_places.place,'н/д') AS pair_place,"
			"groups.course || groups.spec AS pair_group,"
			"julianday(schedules.day, pairs.ptime) - julianday('now', 'localtime') AS dt "
		"FROM schedules "
			"LEFT JOIN pairs ON pairs.schedule_id = schedules.id "
			"LEFT JOIN pairs_places ON pairs.id = pairs_places.pair_id "
			"LEFT JOIN groups ON groups.id = schedules.gid "
		"WHERE pairs_places.teacher_id=? AND datetime(schedules.day, pairs.ptime) > datetime('now', 'localtime') "
		"GROUP BY pairs.id "
		"ORDER BY schedules.day ASC, pairs.ptime ASC "
		"LIMIT 1",
		(teacher_id,)
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
	db.commit()

def addPair(schedule_id, time, sort, name):
	"""Добавляет запись пары"""
	cur.execute("INSERT INTO pairs (schedule_id, ptime, sort, name) VALUES(?, ?, ?, ?)", (schedule_id, time, sort, name))
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

# Функция:Кабинеты
def getCabinets(date, place):
	"""Возвращает занятость кабинетов"""
	response = cur.execute(
		"SELECT pairs.ptime AS pair_time, IFNULL(teachers.surname, 'свободен') AS occupant "
		"FROM schedules "
		"LEFT JOIN pairs ON pairs.schedule_id = schedules.id "
		"LEFT JOIN pairs_places ON pairs_places.pair_id = pairs.id "
		"LEFT JOIN teachers ON teachers.id = pairs_places.teacher_id "
		"WHERE schedules.day=? AND pairs_places.place=? "
		"ORDER BY pairs.ptime",
		(date, place)
	).fetchall()

	if not response:
		return None

	output = []
	for row in response:
		output.append((row['pair_time'], row['occupant']))
	return output

def getCachedPlaceOccupancy(date, place):
	"""Возвращает кэшированное photo_id"""
	return cur.execute("SELECT photo_id FROM occupancy_cache WHERE day=? AND place=?", (date, place)).fetchone()

def addOccupancyRecord(date, place, photo_id):
	"""Кэширует занятость кабинетов"""
	cur.execute("INSERT INTO occupancy_cache (day,place,photo_id) VALUES (?, ?, ?)", (date, place, photo_id))
	db.commit()

def addMailRecord(user_id):
	"""Добавляет запись о рассылке"""
	cur.execute("INSERT INTO mails (author, date_create) VALUES(?,DATETIME('now', 'localtime'))", (user_id,))
	db.commit()

def getMostRecentMailRecord(user_id):
	"""Возвращает id самой последней рассылки над которой работал пользователь"""
	return cur.execute("SELECT id FROM mails WHERE author=? ORDER BY date_create DESC LIMIT 1", (user_id,)).fetchone()['id']

def updateMail(mail_id, field, value):
	"""Обновляет поле рассылки"""
	cur.execute("UPDATE mails SET "+field+"=? WHERE id=?", (value, mail_id))
	db.commit()

def deleteMail(mail_id):
	"""Удаляет запись рассылки"""
	cur.execute("DELETE FROM mails WHERE id=?", (mail_id,))
	db.commit()

def getMailInfo(mail_id):
	"""Возвращает данные рассылки, необходимые для... рассылки"""
	return cur.execute("SELECT target, message FROM mails WHERE id=?", (mail_id,)).fetchone()

def getUsersByMask(mask):
	"""Возвращает пользователей, которым можно отправить сообщение"""
	return cur.execute(
		'SELECT vk_id FROM users '
		'WHERE gid IN (SELECT id FROM groups WHERE (course||spec) LIKE ?) AND allows_mail=1',
		(mask.replace("*", "%"),)
	).fetchall()

# Статистика
def getStatsFunctionUsageAllTime():
	"""Количество использований функций за всё время"""
	return cur.execute(
		"SELECT name, function_names.id AS fn_id, COUNT(stats.id) AS cnt FROM function_names "
		"LEFT JOIN stats ON stats.func_id=function_names.id "
		"GROUP BY function_names.id"
	).fetchall()

def getStatsFunctionUsageLastMonth():
	"""Количество использований функций за всё время"""
	return cur.execute(
		"SELECT "
			"name,"
			"CASE "
				"WHEN julianday('now', 'localtime') - julianday(stats.date_create) < 30 THEN "
					"COUNT(*) "
				"ELSE "
					"0 "
				"END cnt "
		"FROM function_names "
		"LEFT JOIN stats ON stats.func_id=function_names.id "
		"GROUP BY function_names.id"
	).fetchall()

def getStatsByGroups():
	return cur.execute(
		"SELECT groups.course||groups.spec AS gname, stats.func_id AS stat_id, COUNT(stats.id) AS cnt FROM groups "
		"LEFT JOIN stats ON stats.caller_gid = groups.id "
		"WHERE groups.course < 5 "
		"GROUP BY groups.id, stats.id "
		"ORDER BY groups.course"
	).fetchall()

def addStatRecord(user_gid, user_type, fn_id):
	if user_type != 1:
		user_gid = None
	cur.execute(
		'INSERT INTO stats (caller_gid, func_id, date_create) VALUES(?, ?, DATETIME("now", "localtime"))',
		(user_gid, fn_id)
	)
	db.commit()

if __name__ == "__main__":
	start()
