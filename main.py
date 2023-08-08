# main.py
# Вадябот

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import database
import sys
import random
import os
import json
from utils import *

class States:
	reg_1			= 0
	select_course	= 1
	void			= 2
	reg_can_send	= 3
	hub				= 4

class PayloadTypes:
	select_group= 0		# Выбор группы
	show_terms	= 1		# Показать условия использования
	select_date = 2		# Выбор даты

class Purposes:
	registration	= 0 # Для регистрации
	stud_rasp_view	= 1 # Просмотр расписания студентом

class Bot:
	def __init__(self, session):
		"""Инициализация"""
		self.dir = os.path.dirname(__file__)

		# Загрузка ответов
		with open(self.dir + "/config/answers.json", 'r', encoding='utf-8') as f:
			self.answers = json.load(f)

		# Загрузка клавиатур
		with open(self.dir + "/config/keyboards.json", 'r', encoding='utf-8') as f:
			self.keyboards = json.load(f)
		for key in self.keyboards:
			self.keyboards[key] = json.dumps(self.keyboards[key])

		# Кэширование
		self.cached_images = {}

		# ВКонтакте
		self.api = session.get_api()
		self.longpoll = VkLongPoll(session)

	def send(self, vid, msg, kb = None, attach = None):
		"""Отправляет сообщение пользователю"""
		i = self.api.messages.send(
			user_id = vid,
			message = msg,
			keyboard = kb,
			attachments = attach,
			random_id = 0
		)

	def edit(self, vid, msg_id, msg, kb = None, attach = None):
		"""Изменяет сообщение"""
		self.api.messages.edit(
			peer_id = vid,
			message = msg,
			keyboard = kb,
			attachments = attach,
			message_id = msg_id
		)

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

	def makeKeyboardSelectDate(self, purpose, msg_id):
		"""Возвращает разметку клавиатры для выбора даты на основании данных в таблице pairs"""
		dates = database.cmdGetDates()
		if not dates:
			return False

		kb = VkKeyboard(inline=True)
		message_id = random.randint(0, 10000000)
		button_payload = {'type': PayloadTypes.select_date, 'purpose': purpose, 'msg_id': msg_id}

		for index, item in enumerate(dates):
			button_payload['date'] = item['day']
			kb.add_button(item['label'], payload=button_payload)
			if index != len(dates) - 1:
				kb.add_line()
		return kb.get_keyboard()
	# КОНЕЦ ГЕНЕРАТОРОВ КЛАВИАТУР

	# ОТВЕТЫ БОТА
	def answerShowTerms(self, vid):
		"""Показывает условия использования"""
		self.send(vid, self.answers['tos'])

	def answerOnMeet(self, vid):
		"""Первое взаимодействие с ботом"""
		self.send(vid, self.answers['hi1'])
		self.send(vid, self.answers['hi2'], self.keyboards['tos'])
		self.answerAskIfStudent(vid, 1)

	def answerAskIfStudent(self, vid, progress):
		"""Вопрос: Ты студент?"""
		self.send(vid, self.answers['question_are_you_student'].format(progress), self.keyboards['yn_text'])

	def answerAskCourseNumber(self, vid, progress):
		"""Вопрос: На каком ты курсе?"""
		self.send(vid, self.answers['question_what_is_your_course'].format(progress), self.keyboards['course_nums'])

	def answerAskStudentGroup(self, vid, progress, group_names):
		"""Вопрос: Какая из этих групп твоя?"""
		self.send(
			vid,
			self.answers['question_what_is_your_group'].format(progress),
			self.makeKeyboardSelectGroup(group_names, Purposes.registration)
		)

	def answerAskIfCanSend(self, vid, progress):
		"""Вопрос: можно ли присылать рассылки"""
		self.send(vid, self.answers['question_can_send_messages'].format(progress), self.keyboards['yn_text'])

	def answerWrongInput(self, vid):
		"""Неверный ввод"""
		self.send(vid, self.answers['wrong_input'])

	def answerPostRegistration(self, vid, keyboard_name):
		"""Добро пожаловать"""
		self.send(vid, self.answers['welcome_post_reg'], self.keyboards[keyboard_name])

	def answerSelectDate(self, vid, msg_id):
		"""Выбор даты"""
		keyboard = self.makeKeyboardSelectDate(Purposes.stud_rasp_view, msg_id + 1)
		if not keyboard:
			self.send(vid, self.answers['no_relevant_data'])
		else:
			self.send(vid, self.answers['pick_day'], kb=keyboard)
	# КОНЕЦ ОТВЕТОВ БОТА

	def handleMessage(self, text, user, e):
		"""Принимает сообщение, обрабатывает, отвечает и сохраняет результат. Возвращает true, если данные пользователя
		нужно обновить"""
		vid = user['vk_id']

		if user['state'] == States.hub:
			# Выбор функции бота
			if text == 'Расписание':
				self.answerSelectDate(vid, e.message_id)
				return False

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

			available_names = database.cmdGetGroupsByCourse(text)
			self.answerAskStudentGroup(vid, user['question_progress'], available_names)

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

	def handleMessageWithPayload(self, data, user, e):
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
				self.edit(vid, data['msg_id'], "Текст изменён!")
				return False

	def run(self):
		"""Принимает и обрабатывает входящие события"""
		print2("Бот онлайн", 'green')

		for event in self.longpoll.listen():
			if event.type == VkEventType.MESSAGE_NEW and event.to_me:
				# Получено входящее сообщение

				# Определение типа сообщения
				if "payload" in event.__dict__:
					# С доп. данными
					message_data = json.loads(event.payload)
					has_payload = True
				else:
					# Обычное
					has_payload = False

				# Получаем необходимые данные
				vid = event.user_id
				text = event.text
				user = database.cmdGetUserInfo(vid)

				print('user: ', user)

				if not user:
					# Первый запуск
					self.answerOnMeet(vid)
					database.cmdCreateUser(vid)
				else:
					# Не первый запуск
					if has_payload:
						need_update = self.handleMessageWithPayload(message_data, user, event)
					else:
						need_update = self.handleMessage(text, user, event)

					if need_update:
						# Необходимо сохранение данных
						database.cmdSaveUser(user)

def vkAuth(args):
	"""Возвращает объект vk_api.vk (для работы с api)"""
	tflag_index = args.index("-t")
	try:
		bot_token = args[tflag_index + 1]
	except IndexError:
		# Не указан токен после -t
		print2("Не указан токен после параметра -t", 'red')
		sys.exit(1)
	return vk_api.VkApi(token=bot_token)

def main(args):
	"""Входная точка программы"""
	# Проверяем аргументы
	if not "-t" in args:
		print2("Отсутствует параметр -t. Использование -t <vk token>", 'red')
		sys.exit(1)

	# Инициализируем БД
	database.start()

	# Авторизация ВКонтакте
	session = vkAuth(args)

	# Инициализация бота
	bot = Bot(session)

	# Цикл работы бота
	while(True):
		bot.run()

if __name__ == "__main__":
	main(sys.argv)
