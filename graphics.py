# graphics.py
# Модуль для работы с графикой

import api
import json
import requests
import threading
from PIL import Image, ImageDraw, ImageFont

class TableGenerator(threading.Thread):
	"""Класс для генерации таблиц"""
	def __init__(self, vid):
		super().__init__()
		self.vid = vid
		self.msg_id = msg_id
		self.photo_id = None
		self.finished = False

	def generateImage(self):
		"""Метод генерации изображения"""
		pass

	def onSuccess(self):
		"""Вызывается когда изображение успешно сгенерировалось и отправилось"""
		self.finished = True

	def onFail(self):
		"""Вызывается при провале"""
		self.finished = True

	def run(self):
		"""Старт процесса"""
		# Генерация изображения
		image = self.generateImage()
		if not image:
			self.onFail()
			return

		# Загрузка на сервера ВКонтакте
		filename = self.saveImage()
		self.photo_id = api.uploadImage(filename)
		if not self.photo_id:
			self.onFail()
			return

		self.onSuccess()

class ScheduleGenerator(TableGenerator):
	"""Класс для асинхронной генерации изображений таблиц расписания"""
	def __init__(self, vid, msg_id, public_id, ):
		super().__init__(vid)
		self.msg_id = msg_id
		self.public_id = public_id

	def onSuccess(self):
		api.edit(self.vid, self.msg_id, None, None, 'photo_'+self.public_id+'-'+self.photo_id)

	def generateImage(self):
		target, date = self.schedule_key.split(":")
		response = getPairs(target, date, self.for_teacher)

		if response == ERROR_NOSCHEDULE:
			self.sendErrorReport(self.texts["schedule_not_found"])
			return
		elif response == ERROR_NOTARGET:
			self.sendErrorReport(self.texts["target_not_found"].format(target))
			return
		elif len(response[0]) == 0:
			self.sendErrorReport(self.texts["no_pairs"])
			return

		# Выбор цветовой схемы
		if response[1] == True:
			colorscheme_name = "schedule_uncertain"
		else:
			colorscheme_name = "schedule"

		# Определение подписи таблицы, добавление названий столбцов
		day, month, week_day = date.split("_")
		if self.for_teacher:
			table_title = f"Расписание преподавателя {target} на {day} {month_names[int(month)]} ({weekday_names[int(week_day)]})"
			response[0].insert(0, ["Время", "Дисциплина", "Группа", "Кабинет"])
		else:
			table_title = f"Расписание группы {target} на {day} {month_names[int(month)]} ({weekday_names[int(week_day)]})"
			response[0].insert(0, ["Время", "Дисциплина", "Преподаватель", "Кабинет"])

		# Генерация изображения и текста сообщения
		table = graphicsTools.makeTableImage(
			response[0],
			{0: 0, 1: 35, 2: 15, 3: 0},
			colorscheme_name,
			False
		)
		output = graphicsTools.addTitle(table, table_title, colorscheme_name)
		return output


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

# Создаёт поверхность таблицы из данного двумерного массива данных
def makeTableImage(data, line_size_constraints, colorscheme_name, is_for_grades):
	width = len(data[0])
	height = len(data)
	line_spacing = 5
	line_horizonal_padding = 5

	# Рендер текста яйчеек
	rendered_surfaces = [[None for x in range(width)] for y in range(height)]
	# Размер яйчеек будущей таблицы
	table_sizes_rows = [0 for y in range(height)] # Для хранения высоты строк таблицы (некоторые яйчейки имеют несколько строк)
	table_sizes_columns = [0 for x in range(width)] # Для хранения ширины столбцов таблицы (для полного вмещения текста)

	# Отрисовка текста таблицы
	for y in range(height):
		for x in range(width):
			lines = splitLongString(data[y][x], line_size_constraints[x])

			# Получение размеров поверхности
			# Ширина
			text_surface_width = 0
			for line in lines:
				text_surface_width = max(text_surface_width, font_content.getbbox(line)[2] + 2 * line_horizonal_padding)
			# Высота
			text_line_heights = [font_content.getbbox(line)[3] + line_spacing for line in lines]
			text_surface_height = sum(text_line_heights) + line_spacing

			# Рендер текста (прозрачный фон)
			text_surface = Image.new(
				"RGBA",
				size=(text_surface_width, text_surface_height),
				color=(0, 0, 0, 0)
			)
			Itext_draw = ImageDraw.Draw(text_surface)

			y_pos = 0
			for index, line in enumerate(lines):
				if index != 0:
					y_pos += text_line_heights[index - 1]

				Itext_draw.text(
					xy=(line_horizonal_padding, y_pos),
					text=line,
					fill=colorschemes[colorscheme_name]["row_fg"],
					font=font_content
				)
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
		need_gradient = True

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
			need_gradient = False
			left_color_name = "row_bg"

		# Задний фон
		Itable_draw.rectangle((0, y_pos, table_width, y_pos + table_sizes_rows[y]), fill=colorschemes[colorscheme_name][left_color_name][y%2])

		# Подсветка (только для оценок)
		if need_gradient:
			applyGradient(
				Itable_draw,
				(table_sizes_columns[0], y_pos, table_width, y_pos + table_sizes_rows[y]),
				(colorschemes[colorscheme_name][left_color_name][y%2], colorschemes[colorscheme_name][right_color_name][y%2]),
				50
			)

		y_pos += table_sizes_rows[y]

	# Отрисовка разделительных линий
	# Для столбцов
	separator_x = 0
	for x in range(width - 1):
		separator_x += table_sizes_columns[x]
		Itable_draw.line(
			(separator_x, 0, separator_x, table_height),
			fill=(colorschemes[colorscheme_name]["separator"]),
			width = 1
		)
	# Для всей таблицы
	Itable_draw.rectangle(
		(0, 0, table_width - 1, table_height - 1),
		outline=colorschemes[colorscheme_name]["separator"],
		width = 2
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

	output = Image.alpha_composite(table_surface, data_overlay)
	return output

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

# Разбивает длинную строку на линии, перенося слова (слова - это участки текста, разделённые пробелами)
# Разбитие осуществляется с помощью символов \n
def splitLongString(text, line_size):
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

# Загружает шрифты
def loadFonts():
	global font_content, font_title

	font_content = ImageFont.truetype(f"{base_dir}/../config/OpenSans-Regular.ttf", 20)
	font_title = ImageFont.truetype(f"{base_dir}/../config/OpenSans-Regular.ttf", 30)

def test():
	a = splitLongString("Хайрутдинова / Логинова", 20)
	print(a)
	# ~ data = [
		# ~ ["Дисциплина", "Оценки", "Средний балл"],
		# ~ ["Русский язык и культура речи", "45455545555", "(5) 4.73"],
		# ~ ["Физическая культура", "(Н)333343344", "3.33"],
		# ~ ["Иностранный язык", "5545555555555", "(5) 4.92"],
		# ~ ["Основы алгоритмизации и программирования", "44НН545555", "(5) 4.63"],
		# ~ ["Введение в специальность", "554455455", "4.67"],
		# ~ ["Элементы высшей математики", "55(Н)(Н)54434535", "(5) 4.25"],
		# ~ ["Архитектура аппаратных средств", "5", "5.00"],
		# ~ ["МДК 02.01 Технология разработки программного обеспечения", "5", "5.00"],
		# ~ ["МДК 02.02 Инструментальные средства разработки программного обеспечения", "3", "5.00"],
		# ~ ["УП.02.01 Ознакомительная", "3", "5.00"],
		# ~ ["Операционные системы и среды", "3", "5.00"],
		# ~ ["МДК 06.03 Устройство и функционирование информационной системы", "5", "5.00"],
		# ~ ["МДК 02.03 Математическое моделирование", "2455", "5.00"],
	# ~ ]

	# ~ line_size_constraints = {
		# ~ 0: (35, 50),
		# ~ 1: (30, 40),
		# ~ 2: (0, 0)
	# ~ }
	# ~ loadFonts()

	# ~ table = makeTableImage(data, line_size_constraints, "grades", True)
	# ~ table.show()
	# ~ output = addTitle(table, "Оценки на 26 февраля, 10:15", "grades")
base_dir = os.path.dirname(__file__)
