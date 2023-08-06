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

class TermColors:
	RED   = "\033[91m"
	GREEN = "\033[92m"
	END  = "\033[0m"

class States:
	reg_1 = 0
	select_course = 1
	void = 2

class PayloadTypes:
	select_group = 0	# Выбрать группу
	show_terms = 1		# Показать условия использования

class Purposes:
	registration = 0 # Для регистрации

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

		# ВКонтакте
		self.api = session.get_api()
		self.longpoll = VkLongPoll(session)

	def send(self, vid, msg, kb = None, attach = None):
		"""Отправляет сообщение пользователю"""
		self.api.messages.send(
			user_id = vid,
			message = msg,
			keyboard = kb,
			attachments = attach,
			random_id = random.randint(111111,999999)
		)

	# ГЕНЕРАТОРЫ КЛАВИАТУР
	def makeKeyboardSelectGroup(self, data, purpose):
		"""Генерирует разметку клавиатуры для выбор группы"""
		added = 0
		kb = VkKeyboard(inline=True)
		button_payload = {'ptype': 0, 'purpose': purpose}

		for index, item in enumerate(data):
			button_payload['gid'] = item['id']
			kb.add_button(item['spec'], payload=button_payload)

			added += 1
			if added % 3 == 0 and index != len(data) - 1:
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

	def answerWrongInput(self, vid):
		"""Неверный ввод"""
		self.send(vid, self.answers['wrong_input'])
	# КОНЕЦ ОТВЕТОВ БОТА

	def handleMessage(self, text, user):
		"""Принимает сообщение, обрабатывает, отвечает и сохраняет результат. Возвращает true, если данные пользователя
		нужно обновить"""
		vid = user['vk_id']

		if user['state'] == States.void:
			return False

		if user['state'] == States.reg_1:
			# После "Ты студент?"
			if text == 'Да':
				# Пользователь - студент
				user['type'] = 1
				user['question_progress'] += 1
				user['state'] = States.select_course
				answerAskCourseNumber(vid, user['question_progress'])
				return True
			elif text == 'Нет':
				# Пользователь - преподаватель
				user['type'] = 2
				return True
			else:
				# Неверный ввод
				answerWrongInput(vid)
				return False

		if user['state'] == States.select_course:
			# После "На каком ты курсе?" при регистрации
			if not (text.isdigit() and 1 <= int(text) <= 4):
				answerWrongInput(vid)
				return False

			user['state'] = States.void
			user['question_progress'] += 1

			available_names = database.cmdGetGroupsByCourse(text)
			answerAskStudentGroup(vid, user['question_progress'], available_names)

			return True

	def handleMessageWithPayload(self, data, user):
		"""handleMessage для сообщений с доп. данными"""
		vid = user['vk_id']

		if data['type'] == PayloadTypes.show_terms:
			self.answerShowTerms(vid)
			return False

	def run(self):
		"""Принимает и обрабатывает входящие события"""
		print2("Бот онлайн", TermColors.GREEN)

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
						need_update = self.handleMessageWithPayload(message_data, user)
					else:
						need_update = self.handleMessage(text, user)

					if need_update:
						# Необходимо сохранение данных
						database.cmdSaveUser(user)


def print2(text, color):
	"""Выводит цветной текст в консоль"""
	print(color + text + TermColors.END)

def vkAuth(args):
	"""Возвращает объект vk_api.vk (для работы с api)"""
	tflag_index = args.index("-t")
	try:
		bot_token = args[tflag_index + 1]
	except IndexError:
		# Не указан токен после -t
		print2("Не указан токен после параметра -t", TermColors.RED)
		sys.exit(1)
	return vk_api.VkApi(token=bot_token)

def main(args):
	"""Входная точка программы"""
	# Проверяем аргументы
	if not "-t" in args:
		print2("Отсутствует параметр -t. Использование -t <vk token>", TermColors.RED)
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
