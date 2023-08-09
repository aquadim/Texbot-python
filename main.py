# main.py
# Вадябот

import api
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

		# Загрузка настроек
		with open(self.dir + "/config/config.json", 'r', encoding='utf-8') as f:
			self.config = json.load(f)

		# Кэширование
		self.cached_images = {}

		# ВКонтакте
		self.longpoll = VkLongPoll(session)

	def getRandomWaitText(self):
		return self.texts['wait'+str(random.randint(0,6))]

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

	def answerAskStudentGroup(self, vid, progress, group_names):
		"""Вопрос: Какая из этих групп твоя?"""
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

	def answerSelectDate(self, vid, msg_id):
		"""Выбор даты"""
		keyboard = self.makeKeyboardSelectDate(Purposes.stud_rasp_view, msg_id + 1)
		if not keyboard:
			api.send(vid, self.answers['no_relevant_data'])
		else:
			api.send(vid, self.answers['pick_day'], kb=keyboard)

	def answerShowSchedule(self, vid, msg_id, gid, date):
		"""Показ расписания"""
		# Ищем расписание в кэше
		photo_id = database.cmdGetCachedSchedule(gid, date)
		if not photo_id:
			# Кэша нет, создаём
			api.edit(vid, msg_id, self.getRandomWaitText())
			pairs = database.cmdGetPairsForGroup(gid, date)
			self.asyncs.append()
			self.asyncs[-1].start()
		else:
			api.edit(vid, msg_id, None, None, 'photo'+self.config['public_id']+'_'+photo_id)
		pass
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
				self.answerShowSchedule(vid, data['msg_id'], user['gid'], data['date'])
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
		bot.run()

if __name__ == "__main__":
	main(sys.argv)
