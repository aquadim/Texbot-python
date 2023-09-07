# schedule.py
# Модуль для работы с расписанием. Не используется в главном модуле

import requests
import os
import subprocess
import datetime
import database
import sys
import time
import hashlib
from docx import Document
from utils import *

def downloadScheduleFile(name):
	try:
		return requests.get(name)
	except Exception as e:
		print2(e, 'red')
		return False

def getDateList(word_doc, now):
	"""Возвращает список дат, соответствующий таблицам расписаний.
	Если элемент списка False, то расписание не актуально"""
	output = []

	# Проверка параграфов текста на привязку к таблицам
	for item in word_doc.paragraphs:
		paragraph = item.text.lower()
		words = paragraph.split(" ")

		# Должно быть не менее 4 слов
		if len(words) < 4:
			continue

		# Поиск месяца
		month = -1
		for m in gen_month_num_to_str:
			if paragraph.find(gen_month_num_to_str[m]) != -1:
				month = m
				break
		if month == -1:
			# Не найдено совпадений для месяца
			output.append(False)
			continue

		# Поиск дня
		if words[4].isdigit():
			day = int(words[4])
		else:
			# Не обнаружен день
			output.append(False)
			continue

		# Вычисление года
		# Получаем дату и узнаём день недели этой даты
		# Если у этой даты и даты в документе день недели одинаковый, то мы нашли год!
		max_guess_attempts = 2
		for i in range(max_guess_attempts):
			guessed_date = datetime.datetime(year=now.year + i, month=month, day=day)
			guessed_weekday = guessed_date.isoweekday()

			if words[3] == gen_weekdays_num_to_str[guessed_weekday].lower():
				# Совпадает! Значит высока вероятность того, что год угадан правильно
				output.append(f'{now.year + i}-{dd(month)}-{dd(day)}')
				break
		
		output.append(False)

	return output

def parseTable(table, date):
	"""Парсит таблицу"""
	rows = table.rows
	height = len(rows)
	width = len(rows[0].cells)
	
	# Проверяем точное ли это расписание или нет
	is_uncertain = rows[0].cells[0].paragraphs[0].runs[0].font.color.rgb != None
	if is_uncertain:
		print2(f"Таблица на дату {date} имеет неточные данные!", "red")
		return False

	# Перенос данных таблицы в двоичный массив
	data = []
	for y in range(height):
		data_row = []
		table_row = rows[y].cells
		for x in range(width):
			if x % 2 == 0:
				data_row.append(table_row[x].text.replace("\n", "").replace("\xa0", "").replace(".", ":"))
			else:
				data_row.append(table_row[x].text.replace("\n", "").replace("\xa0", ""))
		data.append(data_row)

	# Парсинг таблицы
	current_groups_row = [] # Какие группы в курсе сейчас присутствуют (в списке id групп)
	y = 0
	while y < len(data):
		if isGroupName(data[y][0]):
			current_groups_row.clear()
			for x in range(0, len(data[y]), 2):
				current_groups_row.append(database.cmdGetGidFromString(data[y][x]))
			y += 1
		else:
			for x in range(0, len(data[y]), 2):
				# Проверка правильности
				if len(data[y][x + 1]) < 2:
					# Названия пар не бывают такими короткими
					continue
				if len(data[y][x]) < 3:
					# Время не бывает настолько коротким
					continue

				# Узнаём id расписания для этой пары
				schedule_id = database.getScheduleId(current_groups_row[x // 2], date)
				if not schedule_id:
					# Этого расписания ещё не было создано. Создаём!
					schedule_id = database.addSchedule(current_groups_row[x // 2], date)
				else:
					# Это расписание уже существует. Очищаем все его пары если можно
					if database.getIfCanCleanSchedule(schedule_id):
						database.cleanSchedule(schedule_id)

				# Время пары
				pair_time = data[y][x].split(':')
				pair_time = dd(int(pair_time[0])) + ':' + dd(int(pair_time[1]))

				# Добавляем пару
				pair_id = database.addPair(schedule_id, pair_time, y, data[y][x+1])

				# К паре добавляем места пары
				# Место пары может быть в двух местах, в таких случаях места разделяются слэшем
				places_data = data[y+1][x+1].split('/')
				for index, place in enumerate(places_data):
					components = place.split(' ')
					if len(components) == 2:
						# Есть и кабинет и преподаватель
						database.addPairPlace(pair_id, database.getTeacherId(components[0]), components[1])
					else:
						# Есть только преподаватель
						database.addPairPlace(pair_id, database.getTeacherId(components[0]), None)
			y += 2
	print2(f'Таблица на дату {date} готова!', 'green')

def parseDocument(word_doc, table_dates, now, today, tomorrow):
	"""Парсит документ"""
	start_time = time.time()
	
	# На сегодня
	try:
		today_index = table_dates.index(today)
	except ValueError:
		today_index = -1
	if today_index != -1:
		parseTable(word_doc.tables[today_index], today)
	
	# На завтра
	try:
		tomorrow_index = table_dates.index(tomorrow)
	except ValueError:
		today_index = -1
	if tomorrow_index != -1:
		parseTable(word_doc.tables[tomorrow_index], tomorrow)
		
	database.makeSchedulesCleanable()
	database.db.commit()
	database.db.close()

	end_time = time.time()
	print(f'Время парсинга таблиц: {end_time - start_time}')

def downloadAndCheck(f, now, today, tomorrow, __dir__):
	"""Скачивает файл расписания и проверяет его на нужные нам даты"""
	# Скачиваем файл
	s = downloadScheduleFile(f)
	if not s:
		print2(f"Не удалось скачать f", "red")
		return False
	with open(__dir__ + "/tmp/schedule.doc", "wb") as f:
		f.write(s.content)
	
	# Конвертируем в docx
	subprocess.call(["lowriter", "--convert-to", "docx", __dir__+"/tmp/schedule.doc", "--outdir", __dir__+"/tmp/"])
	
	# Смотрим какие даты у этого документа есть
	word_doc = Document(__dir__+"/tmp/schedule.docx")
	table_dates = getDateList(word_doc, now)
	
	if not today in table_dates and not tomorrow in table_dates:
		# Нет подходящих нам дат
		print2("Нет подходящих дат", "red")
		return False
	else:
		print2("Подходящие даты найдены", "green")
		return word_doc, table_dates

def updateSchedule(__dir__, redownload):
	"""Загружает расписание, обновляет его в БД"""

	if redownload:
		# Составляем даты которые нам нужны на сегодня
		now = datetime.datetime.now()
		date_today = now.strftime("%Y-%m-%d")
		date_tomorrow = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
		
		# Загрузка файла расписания из файла специально для Техбота
		print("Скачиваем rasp2.doc")
		response = downloadAndCheck("http://www.vpmt.ru/docs/rasp2.doc", now, date_today, date_tomorrow, __dir__)
		if response:
			parseDocument(response[0], response[1], now, date_today, date_tomorrow)
			return
		
		print2("Скачиваем rasp.doc", "red")
		response = downloadAndCheck("http://www.vpmt.ru/docs/rasp.doc", now, date_today, date_tomorrow, __dir__)
		if response:
			parseDocument(response[0], response[1], now, date_today, date_tomorrow)
			return
		
		# Нет подходящих дат, ничего не делаем
		print2("Нет дат", "red")

if __name__ == "__main__":
	__dir__ = os.path.dirname(__file__)
	if '-h' in sys.argv:
		print('Использование: python schedule.py [-r]\n\n-r: Загрузить файл расписания')
		sys.exit()

	updateSchedule(__dir__, '-r' in sys.argv)
