# graphics.py
# Модуль для работы с графикой

import api
import json
import requests
import threading
import os
import random
from PIL import Image, ImageDraw, ImageFont

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
		image = self.generateImage()
		if not image:
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
			False,
			self.theme
		)
		# ~ output = graphicsTools.addTitle(table, table_title, colorscheme_name)
		return table


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

def makeTableImage(data, line_size_constraints, is_for_grades, theme):
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

	return Image.alpha_composite(table_surface, data_overlay)

# Добавляет подпись таблице
def addTitle(table_surface, title, colorscheme_name):
	padding = 13

	lines = splitLongString(title, 35)

	# Получение размеров подписи
	# Высота одной строки
	title_height = font_title.getbbox(title)[2:][1]
	# Максимальная ширина
	max_title_width = 0
	for l in lines:
		max_title_width = max(max_title_width, font_title.getbbox(l)[2:][0])

	title_lines_padding = 0 # Расстояние между строками

	# Рендер подписи
	text_surface = Image.new(
		"RGBA",
		size=(max_title_width, title_height * len(lines) + title_lines_padding * len(lines) - 1),
		color=colorschemes[colorscheme_name]["container_bg"]
	)
	Itext_draw = ImageDraw.Draw(text_surface)
	line_y = 0
	for l in lines:
		Itext_draw.text(
			xy=(0, line_y),
			text=l,
			fill=colorschemes[colorscheme_name]["title"],
			font=font_title
		)
		line_y += title_height + title_lines_padding

	# Вычисление размеров выходного изображения
	surface_width = max(max_title_width, table_surface.size[0]) + padding * 2
	surface_height = table_surface.size[1] + text_surface.size[1] + padding * 3

	# Отрисовка выходного изображения
	output = Image.new("RGBA", size=(surface_width, surface_height), color=colorschemes[colorscheme_name]["container_bg"])
	output.paste(table_surface, box=(padding, padding * 2 + text_surface.size[1]))
	output.paste(text_surface, box=(padding, padding))

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
