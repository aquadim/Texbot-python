# graphics.py
# Модуль для работы с графикой

import api
import threading
import os
import random
from PIL import Image, ImageDraw, ImageFont

# Для оценок
import requests
import datetime
from bs4 import BeautifulSoup

__dir__ = os.path.dirname(__file__)
FONT_CONTENT = ImageFont.truetype(__dir__ + '/fonts/OpenSans-Regular.ttf', 20)
FONT_TITLE = ImageFont.truetype(__dir__ + '/fonts/OpenSans-Regular.ttf', 30)

class TableGenerator(threading.Thread):
	"""Класс для генерации таблиц"""
	def __init__(self, vid, theme, parent, public_id):
		super().__init__()
		self.vid = vid
		self.theme = theme
		self.parent = parent
		self.successful = False
		self.public_id = public_id

	def generateImage(self):
		"""Метод генерации изображения"""
		pass

	def onSuccess(self):
		"""Вызывается в случае успеха"""
		pass

	def onFail(self):
		"""Вызывается в случае провала"""
		pass

	def onFinish(self):
		"""Вызывается в конце"""
		try:
			if self.successful:
				self.onSuccess()
			else:
				self.onFail()
		except:
			pass
		self.parent.completeTask(self)


	def run(self):
		"""Старт процесса"""
		# Генерация изображения
		try:
			image = self.generateImage()
		except:
			self.successful = False
			self.onFinish()
			return

		# Загрузка на сервера ВКонтакте
		filename = self.saveImage(image)
		self.photo_id = api.uploadImage(filename)
		if not self.photo_id:
			self.successful = False
			self.onFinish()
			return

		self.successful = True
		self.onFinish()

class ScheduleGenerator(TableGenerator):
	"""Класс для асинхронной генерации изображений таблиц расписания"""
	def __init__(self, theme, vid, msg_id, public_id, pairs, schedule_id, target, date, parent, for_teacher=False):
		super().__init__(vid, theme, parent, public_id)
		self.msg_id = msg_id
		self.pairs = pairs
		self.schedule_id = schedule_id
		self.target = target
		self.date = date
		self.for_teacher = for_teacher

	def onSuccess(self):
		api.edit(self.vid, self.msg_id, None, None, 'photo'+str(self.public_id)+'_'+str(self.photo_id))

	def onFail(self):
		api.edit(self.vid, self.msg_id, 'Произошла ошибка')

	def saveImage(self, image):
		table_id = random.randint(0,1000000)
		filename = __dir__+'/tmp/table-'+str(table_id)+'.png'
		image.save(filename)
		return filename

	def generateImage(self):
		# Определение подписи таблицы, добавление названий столбцов
		if self.for_teacher:
			table_title = f"Расписание преподавателя {self.target} на {self.date}"
			self.pairs.insert(0, ("Время", "Дисциплина", "Группа", "Кабинет"))
		else:
			table_title = f"Расписание группы {self.target} на {self.date}"
			self.pairs.insert(0, ("Время", "Дисциплина", "Место проведения"))

		# Генерация изображения и текста сообщения
		table = makeTableImage(
			self.pairs,
			[0, 40, 25],
			table_title,
			35,
			False,
			self.theme
		)
		return table

class GradesGenerator(TableGenerator):
	"""Класс для асинхронной генерации изображений таблиц оценок"""
	def __init__(self, theme, vid, msg_id, public_id, parent, login, password):
		super().__init__(vid, theme, parent, public_id)
		self.msg_id = msg_id
		self.login = login
		self.password = password

	def generateImage(self):
		# Авторизация в ЭЖ
		s = requests.Session()
		s.post(
			"http://avers.vpmt.ru:8081/region_pou/region.cgi/login",
			data={'username':self.login, 'userpass': self.password}
		)

		# Смотрим какие есть period_id
		r = s.get('http://avers.vpmt.ru:8081/region_pou/region.cgi/journal_och?page=1&clear=1')
		soup = BeautifulSoup(str(r.content, 'windows-1251'), 'lxml')
		options = soup.find('select', attrs = {'name': 'PERIODLIST'}).findAll('option', recursive=False)

		# Выбираем нужный period_id
		now = datetime.datetime.now()
		if 9 <= now.month <= 12:
			# Начало учебного года, выбираем второй элемент
			period_id = options[1]['value']
		else:
			# Конец учебного года, выбираем третий элемент
			period_id = options[2]['value']

		# Запрашиваем оценки
		r = s.get('http://avers.vpmt.ru:8081/region_pou/region.cgi/journal_och?page=1&marks=1&period_id='+period_id)
		soup = BeautifulSoup(str(r.content, 'windows-1251'), 'lxml')

		# Парсим
		output = [('Дисциплина', 'Оценки', 'Средний балл')]
		rows = soup.find('table').findAll('tr')

		# ~ a = BeautifulSoup('<html><table><tr><td class="header">Дисциплина</td><td class="header">оценки - III семестр</td><td class="header">III семестр</td></tr>, <tr><td class="header">Русский язык и культура речи</td><td>4      5          4                                    5           5 5                               4 5          5            5             5           </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.73)&amp;nbsp<span style="color: blue;">1</span></td></tr>, <tr><td class="header">Физическая культура</td><td>        Н         3                 3                    3     3          4                                      3                         3   4   4    </td><td class="header" style="text-align: right;"><b></b>&amp;nbsp(3.33)&amp;nbsp<span style="color: blue;">12</span></td></tr>, <tr><td class="header">Иностранный язык</td><td>                  5      5           4         5           5            5        5   5          5          5                        5           5      5   </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.92)&amp;nbsp<span style="color: blue;">2</span></td></tr>, <tr><td class="header">Основы алгоритмизации и программирования</td><td>    4 4      Н Н 5  4               5            5      5          5                                                                                    </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.63)&amp;nbsp<span style="color: blue;">3</span></td></tr>, <tr><td class="header">Введение в специальность</td><td>                            5          5                            4    4   5                5  4          5                        5                 </td><td class="header" style="text-align: right;"><b></b>&amp;nbsp(4.67)&amp;nbsp<span style="color: blue;">6</span></td></tr>, <tr><td class="header">Элементы высшей математики</td><td> 5 5       Н Н          5                          4              4              3             4          5                        3       5              </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.25)&amp;nbsp<span style="color: blue;">3</span></td></tr>, <tr><td class="header">Архитектура аппаратных средств</td><td>                      5       5          4      4                       5   5                     4          5 5              5                         </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.70)&amp;nbsp<span style="color: blue;">2</span></td></tr>, <tr><td class="header">МДК 02.01 Технология разработки программного обеспечения</td><td>   3                  5    4               5 5                        4              4                                                               </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.29)&amp;nbsp<span style="color: blue;">4</span></td></tr>, <tr><td class="header">МДК 02.02 Инструментальные средства разработки программного обеспечения</td><td>       Н       5     5             5 5   4 4      4        5     5 5    5               5 5         5                                                        </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.79)&amp;nbsp<span style="color: blue;">1</span></td></tr>, <tr><td class="header">УП.02.01 Ознакомительная</td><td>                                                                                5 5 5 5 5 5                                                         </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(5.00)&amp;nbsp<span style="color: blue;">1</span></td></tr>, <tr><td class="header">Операционные системы и среды</td><td>                          5     5                  4                                            5      5     4           5              5       5    5 5 </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.82)&amp;nbsp<span style="color: blue;">3</span></td></tr>, <tr><td class="header">МДК 06.03 Устройство и функционирование информационной системы</td><td>                       5    4                    5   5   4         4          5                  5    5      5     5     4              5      5    3   5     </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(4.63)&amp;nbsp<span style="color: blue;">3</span></td></tr>, <tr><td class="header">МДК 02.03 Математическое моделирование</td><td>                                                                                                               5 5 5 5  5   5 5   5   5 5               </td><td class="header" style="text-align: right;"><b>5</b>&amp;nbsp(5.00)&amp;nbsp<span style="color: blue;">1</span></td></tr></table></html>', 'lxml')
		# ~ rows = a.find('table').findAll('tr')

		for y in range(1, len(rows)):
			cells = rows[y].findAll('td')

			# Название дисциплины
			name = cells[0].get_text()

			# Оценки (может быть написать через regex?)
			grades = cells[1].get_text().replace(' ','').replace('Н','(Н)').replace('Б','(Б)')

			if len(cells[2].contents) == 3:
				# Семестровая оценка
				semester = cells[2].find('b').get_text()
				if len(semester) == 0:
					# Нет семестровой оценки
					semester = None

				# Средний балл
				average = cells[2].contents[1].replace('&nbsp', '').replace('(', '').replace(')', '')
			else:
				semester = None
				average = None

			output.append((name, grades, (semester, average)))

		# Завершение сессии
		s.get('http://avers.vpmt.ru:8081/region_pou/region.cgi/logout')

		print(output)

# Применяет линейный горизонтальный градиент в области box, стартовым цветом gradient[0] и конечным цветом gradient[1]
def applyGradient(Idraw_interface, box, gradient, steps):
	block_width = (box[2] - box[0]) / steps
	block_color_delta = [(gradient[1][i] - gradient[0][i]) / steps for i in range(3)]
	block_color = list(gradient[0])
	block_x_pos = box[0]

	for step in range(steps):
		Idraw_interface.rectangle(
			(block_x_pos, box[1], block_x_pos + block_width, box[3]),
			fill=tuple(block_color)
		)
		for i in range(3):
			block_color[i] = int(block_color[i] + block_color_delta[i])
		block_x_pos += block_width

def makeTableImage(data, line_size_constraints, table_title, table_title_line_size, is_for_grades, theme):
	"""Создаёт поверхность таблицы из данного двумерного массива данных"""
	width = len(data[0])
	height = len(data)

	line_vertical_padding = 5
	line_horizonal_padding = 5

	rendered_surfaces = [[None for x in range(width)] for y in range(height)] # Поверхности текста
	table_sizes_rows = [0 for y in range(height)] # Для хранения высоты строк таблицы (некоторые яйчейки имеют несколько строк)
	table_sizes_columns = [0 for x in range(width)] # Для хранения ширины столбцов таблицы (для полного вмещения текста)

	# Отрисовка текста таблицы
	for y in range(height):
		for x in range(width):
			# Разбиваем текст на строки
			lines = splitLongString(data[y][x], line_size_constraints[x])

			# Вычисление размеров яйчейки
			text_surface_width = 0
			text_surface_height = 0
			for line in lines:
				size = FONT_CONTENT.getbbox(line)
				text_surface_width = max(text_surface_width, size[2] + 2 * theme['horizontal-padding'])
				text_surface_height += size[3]
			average_line_height = text_surface_height / len(lines)
			text_surface_height = text_surface_height + (theme['line-spacing'] * (len(lines) - 1)) + (2 * theme['vertical-padding'])

			# Рендер текста (прозрачный фон)
			text_surface = Image.new(
				"RGBA",
				size=(text_surface_width, text_surface_height),
				color=(0, 0, 0, 0)
			)
			Itext_draw = ImageDraw.Draw(text_surface)

			y_pos = 0
			for index, line in enumerate(lines):
				Itext_draw.text(
					xy=(theme['horizontal-padding'], y_pos),
					text=line,
					fill=theme["color"],
					font=FONT_CONTENT
				)
				y_pos += average_line_height + theme['line-spacing']
			rendered_surfaces[y][x] = text_surface.copy()

			# Изменение ширины/высоты всей колонки/строки (если необходимо)
			table_sizes_columns[x] = max(table_sizes_columns[x], text_surface_width)
			table_sizes_rows[y] = max(table_sizes_rows[y], text_surface_height)

	# Создание поверхности таблицы
	table_width = sum(table_sizes_columns)
	table_height = sum(table_sizes_rows)
	table_surface = Image.new("RGBA", size=(table_width, table_height), color=(0,0,0,0))
	Itable_draw = ImageDraw.Draw(table_surface)

	# Отрисовка заднего фона
	y_pos = 0
	for y in range(height):
		need_gradient = False

		if is_for_grades:
			# Вычисление левого цвета строки. Слегка желтоватый если семестровая оценка
			# уже выставлена, иначе обычный цвет
			if data[y][2][0] == "(":
				# Если семестровая оценка уже выставлена, строка должна быть жёлтой
				left_color_name = "yellow_highlight"
			else:
				left_color_name = "row_bg"

			# Вычисление правого цвета строки. Красный если предмет в строке имеет двойки
			# Фиолетовый если предмет в строке имеет ТОЛЬКО пятёрки
			if data[y][1].find("2") != -1:
				# Если в оценках за этот семестр существует двойка, подсветить строку красным.
				right_color_name = "red_highlight"
			elif y != 0 and len(data[y][1]) > 0 and data[y][1].find("2") == -1 and data[y][1].find("3") == -1 and data[y][1].find("4") == -1:
				# Если все полученные оценки - это пятёрки, то подсветить строку ~градиентом~
				right_color_name = "perfect_highlight"
			else:
				# Обычный задний фон
				need_gradient = False
		else:
			color1 = theme["background"]

		# Задний фон
		if need_gradient:
			applyGradient(
				Itable_draw,
				(table_sizes_columns[0], y_pos, table_width, y_pos + table_sizes_rows[y]),
				(colorschemes[colorscheme_name][left_color_name][y%2], colorschemes[colorscheme_name][right_color_name][y%2]),
				50
			)
		else:
			Itable_draw.rectangle((0, y_pos, table_width, y_pos + table_sizes_rows[y]), fill=color1[y % 2])

		y_pos += table_sizes_rows[y]

	# Разделительные линии столбцов
	separator_x = 0
	for x in range(width - 1):
		separator_x += table_sizes_columns[x]
		Itable_draw.line(
			(separator_x, 0, separator_x, table_height),
			fill=theme['separator'],
			width=1
		)

	# Разделительные линии таблицы
	Itable_draw.rectangle(
		(0, 0, table_width - 1, table_height - 1),
		outline=theme['separator'],
		width=2
	)

	# Создание слоя текста
	data_overlay = Image.new("RGBA", size=(table_width, table_height), color=(0, 0, 0, 0))

	# Размещение текста таблицы
	cell_pos_y = 0
	for y in range(height):
		cell_pos_x = 0
		for x in range(width):
			data_overlay.paste(rendered_surfaces[y][x], box=(cell_pos_x, cell_pos_y))
			cell_pos_x += table_sizes_columns[x]
		cell_pos_y += table_sizes_rows[y]
	table_surface = Image.alpha_composite(table_surface, data_overlay)

	# Добавляем подпись таблицы
	title_lines = splitLongString(table_title, table_title_line_size)
	title_height = 0
	title_width = 0
	for line in title_lines:
		size = FONT_TITLE.getbbox(line)
		title_width = max(title_width, size[2] + theme['horizontal-padding'])
		title_height += size[3]
	average_title_height = title_height / len(title_lines)
	title_height = title_height + (theme['line-spacing'] * (len(title_lines) - 1)) + (2 * theme['vertical-padding'])
	title_surface = Image.new("RGBA", size=(title_width, title_height), color=theme['container-background'])
	Itext_draw = ImageDraw.Draw(title_surface)
	y_pos = 0
	for line in title_lines:
		Itext_draw.text(xy=(0, y_pos), text=line, fill=theme['title-color'], font=FONT_TITLE)
		y_pos += average_title_height + theme['line-spacing']

	# Рисуем итоговую финальную конечную поверхность
	output_width = max(title_width, table_width) + theme['container-padding'] * 2
	output_height = title_height + table_height + theme['container-padding'] * 2 + theme['container-spacing']
	output = Image.new("RGB", size=(output_width, output_height), color=theme['container-background'])
	output.paste(title_surface, box=(theme['container-padding'], theme['container-padding']))
	output.paste(table_surface, box=(theme['container-padding'], theme['container-padding'] + theme['container-spacing'] + title_height))

	return output

def splitLongString(text, line_size):
	"""Разбивает длинную строку на линии, перенося слова (слова - это участки текста, разделённые пробелами)"""

	# Не разделять слова
	if (line_size == 0):
		return [text]

	output = []
	current_line = ""
	words = text.split(" ")

	for i in range(len(words)):

		# Если строка после прибавления будет больше чем line_size, то её нужно будет перенести на новую строку
		# Если после перенесения строка не вмещается в line_size, то разбить строку вручную на участки по line_size символов
		# А если строка вмещается, просто прибавить её

		if len(current_line) + len(words[i]) + 1 <= line_size:
			current_line += words[i] + " "
		else:
			output.append(current_line)

			if (len(words[i]) + 1 > line_size):
				while (len(words[i]) > line_size):
					output.append(words[i][:line_size])
					words[i] = words[i][line_size:]
				current_line = words[i] + " "
			else:
				current_line = words[i] + " "

	# Добавление оставшихся данных
	output.append(current_line[:-1])

	return output


gg = GradesGenerator(None, None, None, None, None, 'korolevvs', '0096c85fb8f84a92e080be4893900e7c3d15e684')
gg.generateImage()
