# schedule.py
# Модуль для работы с расписанием. Не используется в главном модуле

import requests
import os
import subprocess
import datetime
import database
import sys
from docx import Document
from utils import *

def downloadScheduleFile():
	try:
		return requests.get("http://www.vpmt.ru/docs/rasp.doc")
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
				# Если дата актуальна, тогда ещё и добавляем в output
				remains = (guessed_date - now).total_seconds()
				# ~ if remains > 345600:
					# ~ return output

				# ~ if -86400 < remains:
					# ~ output.append([day, month, now.year + i])
				# ~ else:
					# ~ output.append(False)
				output.append(f'{now.year + i}-{month}-{day}')
				break

	return output

def parseDocument(__dir__):
	"""Парсит документ"""
	now	= datetime.datetime.now()
	date_today = str(now.year) + '-' + str(now.month) + '-' + str(now.day)

	tomorrow = now + datetime.timedelta(days=1)
	date_tomorrow = str(tomorrow.year) + '-' + str(tomorrow.month) + '-' + str(tomorrow.day)

	# TODO:
	# Если есть расписание на сегодня и учебный день ещё не закончился, то необходимо сохранить это расписание,
	# потому что иногда расписание на сегодня удаляют уже.. сегодня

	word_doc = Document(__dir__+"/tmp/schedule.docx")
	table_amount = len(word_doc.tables)
	table_dates = getDateList(word_doc, now)

	for table_index in range(table_amount):
		# Проходимся по всем таблицам
		if table_index > len(table_dates) - 1:
			break
		if table_dates[table_index] == False:
			continue

		table = word_doc.tables[table_index]
		table_time_end = 0
		rows = table.rows

		height = len(rows)
		width = len(rows[0].cells)

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
					schedule_id = database.getScheduleId(current_groups_row[x // 2], table_dates[table_index])
					if not schedule_id:
						# Этого расписания ещё не было создано. Создаём!
						schedule_id = database.addSchedule(current_groups_row[x // 2], table_dates[table_index])
					else:
						# Это расписание уже существует. Очищаем все его пары если можно
						if database.getIfCanCleanSchedule(schedule_id):
							database.cleanSchedule(schedule_id)

					# Добавляем пару
					pair_id = database.addPair(schedule_id, data[y][x], y, data[y][x+1])

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
		print2(f'Таблица #{table_index} готова!', 'green')
	database.makeSchedulesCleanable()

def updateSchedule(__dir__, redownload):
	"""Загружает расписание, обновляет его в БД"""

	if redownload:
		# Загрузка файла расписания
		s = downloadScheduleFile()
		if s == False:
			sys.exit(1)
		with open(__dir__ + "/tmp/schedule.doc", "wb") as f:
			f.write(s.content)

		# Конвертирование расписания из doc в docx формат
		subprocess.call(["lowriter", "--convert-to", "docx", __dir__ + "/tmp/schedule.doc", "--outdir", __dir__ + "/tmp/"])

	# Парсинг
	parseDocument(__dir__)

if __name__ == "__main__":
	__dir__ = os.path.dirname(__file__)
	if '-h' in sys.argv:
		print('Использование: python schedule.py [-r]\n\n-r: Загрузить файл расписания')
		sys.exit()

	updateSchedule(__dir__, '-r' in sys.argv)
