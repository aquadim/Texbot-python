# main.py
# Вадябот

import api
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import database
import sys
import random
import os
import json
import graphics
import hashlib
import math
from utils import *

class States:
	reg_1			= 0
	select_course	= 1
	void			= 2
	reg_can_send	= 3
	hub				= 4
	enter_login		= 5
	enter_password	= 6

class PayloadTypes:
	select_group		= 0	# Выбор группы
	show_terms			= 1	# Показать условия использования
	select_date 		= 2	# Выбор даты
	enter_credentials	= 3	# Ввод данных журнала
	select_teacher		= 4 # Выбор преподавателя

class Purposes:
	registration		= 0 # Для регистрации
	stud_rasp_view		= 1 # Просмотр расписания группы
	teacher_rasp_view	= 2 # Просмотр расписания преподавателя

class Bot:
	def __init__(self, session):
		"""Инициализация"""
		self.dir = os.path.dirname(__file__)
		self.tasks = []

		# Загрузка ответов
		with open(self.dir + "/config/answers.json", 'r', encoding='utf-8') as f:
			self.answers = json.load(f)

		# Загрузка клавиатур
		with open(self.dir + "/config/keyboards.json", 'r', encoding='utf-8') as f:
			self.keyboards = json.load(f)
		for key in self.keyboards:
			self.keyboards[key] = json.dumps(self.keyboards[key])

		# Загрузка настроек
		with open(self.dir + "/config/config.json", 'r', encoding='utf-8') as f:
			self.config = json.load(f)

		# Загрузка тем
		with open(self.dir + '/config/themes.json', 'r', encoding='utf-8') as f:
			self.themes = json.load(f)

		# ВКонтакте
		self.longpoll = VkBotLongPoll(session, group_id=str(-1 * self.config['public_id']))

	def getRandomWaitText(self):
		return self.answers['wait'+str(random.randint(0,7))]

	def completeTask(self, thread):
		"""Очищает завершившиеся асинхронные процессы"""
		if type(thread) == graphics.ScheduleGenerator:
			# Сохраняем photo_id для сгенерированного расписания
			if thread.successful:
				database.addCacheToSchedule(thread.schedule_id, thread.photo_id)

		elif type(thread) == graphics.GradesGenerator:
			if thread.successful:
				database.addGradesRecord(thread.user_id, thread.photo_id)

		self.tasks.remove(thread)

	def checkIfCancelled(self, text, user):
		"""Проверяет если пользователь запросил отмену. Если да - то возвращаем его в хаб"""
		if text == 'Отмена':
			user['state'] = States.hub
			self.answerToHub(user['vk_id'], user['type'])
			return True
		else:
			return False

	# ГЕНЕРАТОРЫ КЛАВИАТУР
	def makeKeyboardSelectGroup(self, data, purpose):
		"""Генерирует разметку клавиатуры для выбор группы"""
		added = 0
		kb = VkKeyboard(inline=True)
		button_payload = {'type': PayloadTypes.select_group, 'purpose': purpose}

		for index, item in enumerate(data):
			button_payload['gid'] = item['id']
			kb.add_button(item['spec'], payload=button_payload)

			added += 1
			if added % 3 == 0 and index != len(data) - 1:
				kb.add_line()

		return kb.get_keyboard()

	def makeKeyboardSelectDateForGroup(self, purpose, msg_id, gid):
		"""Возвращает разметку клавиатуры для выбора даты расписания у группы"""
		dates = database.getScheduleDatesByGid(gid)
		if not dates:
			return False

		kb = VkKeyboard(inline=True)
		button_payload = {
			'type': PayloadTypes.select_date,
			'purpose': purpose,
			'msg_id': msg_id
		}

		for index, item in enumerate(dates):
			button_payload['schedule_id'] = item['id']
			kb.add_callback_button(getDateName(item['day']), payload=button_payload)
			if index != len(dates) - 1:
				kb.add_line()
		return kb.get_keyboard()

	def makeKeyboardSelectDateForTeacher(self, purpose, msg_id, teacher_id):
		"""Возвращает клавиатуру выбора даты в которой хранится информация о выбранном преподавателе"""
		dates = database.getRelevantScheduleDates()
		if not dates:
			return False

		kb = VkKeyboard(inline=True)
		button_payload = {
			'type': PayloadTypes.select_date,
			'purpose': purpose,
			'msg_id': msg_id,
			'teacher_id': teacher_id
		}

		for index, item in enumerate(dates):
			button_payload['date'] = item['day']
			kb.add_callback_button(getDateName(item['day']), payload=button_payload)
			if index != len(dates) - 1:
				kb.add_line()
		return kb.get_keyboard()

	def makeTeacherSelectKeyboards(self, teachers, purpose, msg_id):
		"""Возвращает клавиатуры для выбора преподавателя"""
		output = []

		button_payload = {
			'type': PayloadTypes.select_teacher,
			'purpose': purpose,
			'msg_id': msg_id,
			'amount': math.ceil(len(teachers) / 9)
		}

		for i in range(0, len(teachers), 9):
			kb = VkKeyboard(inline=True)
			for y in range(i, i + 9, 3):
				for x in range(3):
					button_payload['teacher_id'] = teachers[y + x]['id']
					kb.add_callback_button(teachers[y + x]['surname'], payload=button_payload)
					if x + y >= len(teachers) - 1:
						# Преподаватели закончились
						output.append(kb.get_keyboard())
						return output
				if y != i + 6:
					kb.add_line()
			output.append(kb.get_keyboard())

		return output
	# КОНЕЦ ГЕНЕРАТОРОВ КЛАВИАТУР

	# ОТВЕТЫ БОТА
	def answerShowTerms(self, vid):
		"""Показывает условия использования"""
		api.send(vid, self.answers['tos'])

	def answerOnMeet(self, vid):
		"""Первое взаимодействие с ботом"""
		api.send(vid, self.answers['hi1'])
		api.send(vid, self.answers['hi2'], self.keyboards['tos'])
		self.answerAskIfStudent(vid, 1)

	def answerAskIfStudent(self, vid, progress):
		"""Вопрос: Ты студент?"""
		api.send(vid, self.answers['question_are_you_student'].format(progress), self.keyboards['yn_text'])

	def answerAskCourseNumber(self, vid, progress):
		"""Вопрос: На каком ты курсе?"""
		api.send(vid, self.answers['question_what_is_your_course'].format(progress), self.keyboards['course_nums'])

	def answerAskStudentGroup(self, vid, progress, course):
		"""Вопрос: Какая из этих групп твоя?"""
		group_names = database.getGroupsByCourse(course)
		api.send(
			vid,
			self.answers['question_what_is_your_group'].format(progress),
			self.makeKeyboardSelectGroup(group_names, Purposes.registration)
		)

	def answerAskIfCanSend(self, vid, progress):
		"""Вопрос: можно ли присылать рассылки"""
		api.send(vid, self.answers['question_can_send_messages'].format(progress), self.keyboards['yn_text'])

	def answerWrongInput(self, vid):
		"""Неверный ввод"""
		api.send(vid, self.answers['wrong_input'])

	def answerPostRegistration(self, vid, keyboard_name):
		"""Добро пожаловать"""
		api.send(vid, self.answers['welcome_post_reg'], self.keyboards[keyboard_name])

	def answerSelectDate(self, vid, msg_id, target, for_teacher):
		"""Отсылает сообщение с выбором даты"""
		if for_teacher:
			keyboard = self.makeKeyboardSelectDateForTeacher(Purposes.teacher_rasp_view, msg_id, target)
		else:
			keyboard = self.makeKeyboardSelectDateForGroup(Purposes.stud_rasp_view, msg_id, target)

		if not keyboard:
			api.send(vid, self.answers['no_relevant_data'])
		else:
			api.send(vid, self.answers['pick_day'], kb=keyboard)

	def answerShowScheduleForGroup(self, vid, schedule_id):
		"""Показ расписания для группы"""
		response = database.getScheduleDataForGroup(schedule_id)

		# Расписание кэшировано?
		if response['photo_id']:
			api.send(vid, None, None, 'photo'+str(self.config['public_id'])+'_'+str(response['photo_id']))
		else:
			# Прикол для Виталия :P
			if vid == 240088163:
				api.send(vid, self.getRandomWaitText())

			# Нет кэшированного изображения, делаем
			msg_id = api.send(vid, self.getRandomWaitText())

			# Получаем пары расписания
			pairs = database.getPairsForGroup(schedule_id)

			# Получаем название группы расписания
			group_name = database.getGroupName(response['gid'])

			# Получаем читаемую дату расписания
			schedule_date = getDateName(response['day'])

			# Запускаем процесс генерации
			self.tasks.append(graphics.ScheduleGenerator(
				self.themes['rasp'],
				vid,
				msg_id,
				self.config['public_id'],
				pairs,
				schedule_id,
				group_name,
				schedule_date,
				self,
				False
			))
			self.tasks[-1].start()

	def answerShowScheduleForTeacher(self, vid, msg_id, date, teacher_id):
		"""Показ расписания для преподавателя"""
		response = database.getScheduleDataForTeacher(date, teacher_id)

	def answerShowGrades(self, vid, user_id, msg_id, login, password):
		"""Показ оценок"""
		# Проверяем если пользователь уже получал оценки
		photo_id = database.getMostRecentGradesImage(user_id)
		if photo_id:
			api.send(vid, None, None, 'photo'+str(self.config['public_id'])+'_'+str(photo_id))
		else:
			api.send(vid, self.getRandomWaitText())
			# Запускаем процесс сбора оценок
			self.tasks.append(graphics.GradesGenerator(
				self.themes['grades'],
				vid,
				msg_id,
				self.config['public_id'],
				self,
				login,
				password,
				user_id,
				self.keyboards['enter_journal_credentials']
			))
			self.tasks[-1].start()

	def answerAskJournalLogin(self, vid):
		"""Спрашиваем логин журнала"""
		api.send(vid, self.answers['enter_login'], self.keyboards['cancel'])

	def answerAskJournalPassword(self, vid):
		"""Спрашиваем пароль журнала"""
		api.send(vid, self.answers['enter_password'], self.keyboards['cancel'])

	def answerDone(self, vid):
		"""Ответ: Готово!"""
		api.send(vid, self.answers['done'])

	def answerToHub(self, vid, user_type):
		"""Возвращает пользователя в хаб"""
		if user_type == 1:
			api.send(vid, self.answers['returning'], self.keyboards['stud_hub'])

	def answerWhatsNext(self, vid, gid):
		"""Отвечает какая пара следующая"""
		response = database.getNextPairForGroup(gid)

		if not response:
			api.send(vid, self.answers['get-next-fail'])
			return

		# Оставшееся время
		hours_left = response['dt'] * 24
		minutes_left = (hours_left - int(hours_left)) * 60

		api.send(vid, self.answers['get-next-student'].format(
			str(round(hours_left)) + ' ' + formatHoursGen(round(hours_left)),
			str(round(minutes_left)) + ' ' + formatMinutesGen(round(minutes_left)),
			response['pair_name'],
			response['pair_place'],
			response['pair_time']
		))

	def answerSelectTeacher(self, vid, message_id):
		"""Отправляет сообщения с клавиатурами выбора преподавателя"""

		# Узнаём какие вообще есть преподаватели
		teachers = database.getAllTeachers()
		keyboards = self.makeTeacherSelectKeyboards(teachers, Purposes.teacher_rasp_view, message_id)
		amount = len(keyboards)

		for index, k in enumerate(keyboards):
			api.send(vid, self.answers['select-teacher'].format(index + 1, amount), k)
	# КОНЕЦ ОТВЕТОВ БОТА

	def handleMessage(self, text, user, message_id):
		"""Принимает сообщение, обрабатывает, отвечает и сохраняет результат. Возвращает true, если данные пользователя
		нужно обновить"""
		vid = user['vk_id']

		if user['state'] == States.hub:
			# Выбор функции бота
			if text == 'Расписание':
				self.answerSelectDate(vid, message_id + 1, user['gid'], False)
				return False
			if text == 'Оценки':
				self.answerShowGrades(vid, user['id'], message_id + 1, user['journal_login'], user['journal_password'])
				return False
			if text == 'Что дальше?':
				self.answerWhatsNext(vid, user['gid'])
				return False
			if text == 'Где преподаватель?':
				self.answerSelectTeacher(vid, message_id + 1)

		if user['state'] == States.void:
			# Заглушка
			return False

		if user['state'] == States.reg_1:
			# После "Ты студент?"
			if text == 'Да':
				# Пользователь - студент
				user['type'] = 1
				user['question_progress'] += 1
				user['state'] = States.select_course
				self.answerAskCourseNumber(vid, user['question_progress'])
				return True
			elif text == 'Нет':
				# Пользователь - преподаватель
				user['type'] = 2
				return True
			else:
				# Неверный ввод
				self.answerWrongInput(vid)
				return False

		if user['state'] == States.select_course:
			# После "На каком ты курсе?" при регистрации
			if not (text.isdigit() and 1 <= int(text) <= 4):
				self.answerWrongInput(vid)
				return False

			user['state'] = States.void
			user['question_progress'] += 1

			self.answerAskStudentGroup(vid, user['question_progress'], text)

			return True

		if user['state'] == States.reg_can_send:
			# После "Можно ли отправлять сообщения?" при регистрации
			if text == 'Да':
				user['allows_mail'] = 1
			elif text == 'Нет':
				user['allows_mail'] = 0
			else:
				self.answerWrongInput(vid)
				return False

			user['state'] = States.hub
			self.answerPostRegistration(vid, 'stud_hub')
			return True

		if user['state'] == States.enter_login:
			# Ввод логина
			if self.checkIfCancelled(text, user):
				return True
			user['journal_login'] = text
			user['state'] = States.enter_password
			self.answerAskJournalPassword(vid)
			return True

		if user['state'] == States.enter_password:
			# Ввод пароля
			if self.checkIfCancelled(text, user):
				return True
			user['journal_password'] = hashlib.sha1(bytes(text, "utf-8")).hexdigest()
			user['state'] = States.hub
			self.answerDone(vid)
			self.answerToHub(vid, user['type'])
			return True

	def handleMessageWithPayload(self, data, user, message_id):
		"""handleMessage для сообщений с доп. данными"""
		vid = user['vk_id']

		if data['type'] == PayloadTypes.show_terms:
			# Показ условий использования
			self.answerShowTerms(vid)
			return False

		if data['type'] == PayloadTypes.select_group:
			# Выбрана группа.. но для чего?
			if data['purpose'] == Purposes.registration:
				user['gid'] = data['gid']
				user['question_progress'] += 1
				user['state'] = States.reg_can_send
				self.answerAskIfCanSend(vid, user['question_progress'])
				return True

		if data['type'] == PayloadTypes.select_date:
			# Выбрана дата.. но для чего?
			if data['purpose'] == Purposes.stud_rasp_view:
				# Просмотр расписания группы
				self.answerShowScheduleForGroup(vid, data['schedule_id'])
				return False
			if data['purpose'] == Purposes.teacher_rasp_view:
				# Просмотр расписания преподавателя
				self.answerShowScheduleForTeacher(vid, data['msg_id'], data['date'], data['teacher_id'])

		if data['type'] == PayloadTypes.enter_credentials:
			# Переводим пользователя на ввод логина и пароля дневника
			user['state'] = States.enter_login
			self.answerAskJournalLogin(vid)
			return True

		if data['type'] == PayloadTypes.select_teacher:
			# Выбран преподаватель... но для чего?
			if data['purpose'] == Purposes.teacher_rasp_view:
				# Просмотр расписания преподавателя

				# Удаляем прошлые сообщения
				to_delete = ''
				for i in range(data['msg_id'], data['msg_id'] + data['amount']):
					to_delete += str(i) + ','
				api.delete(to_delete)

				# Отправляем сообщение с выбором даты
				self.answerSelectDate(vid, message_id + 1, data['teacher_id'], True)

	def run(self):
		"""Принимает и обрабатывает входящие события"""
		print2("Бот онлайн", 'green')

		for event in self.longpoll.listen():
			if event.type == VkBotEventType.MESSAGE_NEW:
				# Новое текстовое сообщение
				text = event.obj.message['text']		# Текст сообщения
				vid = event.obj.message['peer_id']		# ID отправившего
				message_id = event.obj.message['id']	# ID сообщения
				from_group = message_id == 0			# Из группы ли?

				if len(text) == 0:
					continue

				if from_group:
					# Пока что мы не будем обрабатывать сообщения из бесед
					continue

				user = database.getUserInfo(vid)
				print('user: ', user)

				if not user:
					# Первый запуск
					self.answerOnMeet(vid)
					database.createUser(vid)
				else:
					# Не первый запуск
					if 'payload' in event.obj.message:
						message_data = json.loads(event.obj.message['payload'])
						need_update = self.handleMessageWithPayload(message_data, user, message_id)
					else:
						need_update = self.handleMessage(text, user, message_id)

					if need_update:
						# Необходимо сохранение данных
						database.saveUserData(user)

			if event.type == VkBotEventType.MESSAGE_EVENT:
				# Новое событие
				vid = event.obj.peer_id
				message_data = event.obj.payload
				event_id = event.obj.event_id
				message_id = None

				user = database.getUserInfo(vid)
				need_update = self.handleMessageWithPayload(message_data, user, message_id)

				if need_update:
					database.saveUserData(user)

				api.answerCallback(event_id, vid, event.obj.peer_id)

def main(args):
	"""Входная точка программы"""
	# Проверяем аргументы
	if not "-t" in args:
		print2("Отсутствует параметр -t. Использование -t <vk token>", 'red')
		sys.exit(1)

	# Инициализируем БД
	database.start()

	# Авторизация ВКонтакте
	session = api.start(args)

	# Инициализация бота
	bot = Bot(session)

	# Цикл работы бота
	while(True):
		try:
			bot.run()
		except KeyboardInterrupt:
			print2('\nПока!', 'green')
			database.stop()
			sys.exit(0)

if __name__ == "__main__":
	main(sys.argv)
