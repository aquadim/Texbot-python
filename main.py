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
import logging
import time
from requests.exceptions import *
from utils import *

class States:
	reg_1						= 0 # Ответ студент или нет
	select_course				= 1 # Выбор курса студента
	void						= 2 # Нет реакции бота
	reg_can_send				= 3 # Ответ можно ли отправлять рассылки
	hub							= 4 # Выбор функции
	enter_login					= 5 # Ввод логина
	enter_password				= 6 # Ввод пароля
	enter_login_after_profile	= 7 # Ввод логина, потом ставим 8
	enter_password_after_profile= 8 # Ввод пароля, потом показываем профиль
	enter_cab					= 9 # Ввод кабинета

class PayloadTypes:
	select_group		= 0	# Выбор группы
	show_terms			= 1	# Показать условия использования
	select_date 		= 2	# Выбор даты
	enter_credentials	= 3	# Ввод данных журнала
	select_teacher		= 4 # Выбор преподавателя
	select_course		= 5 # Выбор курса
	edit_group			= 6 # Смена группы
	toggle_mail			= 7 # Переключение разрешения рассылок

class Purposes:
	registration		= 0 # Для регистрации
	stud_rasp_view		= 1 # Просмотр расписания группы
	teacher_rasp_view	= 2 # Просмотр расписания преподавателя
	edit_student		= 3 # Изменение для студента
	edit_teacher		= 4 # Изменение для преподавателя
	view_cabinets		= 4 # Просмотр занятости кабинетов

class Bot:
	def __init__(self, session, cwd, print_user):
		"""Инициализация"""
		self.dir = cwd
		self.tasks = []
		self.print_user = print_user

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
		if thread.has_exception:
			try:
				api.send(thread.vid, self.answers['exception'].format(str(thread.exception)))
				api.tgErrorReport(str(thread.exception))
			except:
				pass

		if type(thread) == graphics.GroupScheduleGenerator:
			if thread.successful:
				# Сохраняем photo_id для сгенерированного расписания
				database.addCacheToSchedule(thread.schedule_id, thread.photo_id)

		elif type(thread) == graphics.TeacherScheduleGenerator:
			if thread.successful:
				database.addCachedScheduleOfTeacher(thread.date, thread.teacher_id, thread.photo_id)

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
	def makeKeyboardSelectGroup(self, data, msg_id, purpose):
		"""Генерирует разметку клавиатуры для выбора группы"""
		added = 0
		kb = VkKeyboard(inline=True)
		button_payload = {'type': PayloadTypes.select_group, 'msg_id': msg_id, 'purpose': purpose}

		for index, item in enumerate(data):
			button_payload['gid'] = item['id']
			kb.add_callback_button(item['spec'], payload=button_payload)

			added += 1
			if added % 3 == 0 and index != len(data) - 1:
				kb.add_line()

		return kb.get_keyboard()

	def makeKeyboardSelectRelevantDate(self, purpose, msg_id, target):
		"""Возвращает клавиатуру выбора даты"""
		dates = database.getRelevantScheduleDates()
		if not dates:
			return False

		kb = VkKeyboard(inline=True)
		button_payload = {
			'type': PayloadTypes.select_date,
			'purpose': purpose,
			'msg_id': msg_id,
			'target': target
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
					kb.add_button(teachers[y + x]['surname'], payload=button_payload)
					if x + y >= len(teachers) - 1:
						# Преподаватели закончились
						output.append(kb.get_keyboard())
						return output
				if y != i + 6:
					kb.add_line()
			output.append(kb.get_keyboard())

		return output

	def makeKeyboardSelectCourse(self, msg_id, purpose):
		"""Генерирует клавиатуру выбор курса"""
		output = VkKeyboard(inline=True)
		output.add_callback_button('1', payload={'type': PayloadTypes.select_course, 'purpose': purpose, 'num': 1, "msg_id": msg_id})
		output.add_callback_button('2', payload={'type': PayloadTypes.select_course, 'purpose': purpose, 'num': 2, "msg_id": msg_id})
		output.add_line()
		output.add_callback_button('3', payload={'type': PayloadTypes.select_course, 'purpose': purpose, 'num': 3, "msg_id": msg_id})
		output.add_callback_button('4', payload={'type': PayloadTypes.select_course, 'purpose': purpose, 'num': 4, "msg_id": msg_id})
		return output.get_keyboard()

	def makeProfileKeyboard(self, msg_id, user):
		"""Отправляет клавиатуру профиля"""
		output = VkKeyboard(inline=True)

		if user['type'] == 1:
			output.add_callback_button('Сменить группу', payload={'type': PayloadTypes.edit_group, 'purpose': Purposes.edit_student, "msg_id": msg_id})

			if user['journal_login'] == None:
				credentials_text = 'Ввести логин и пароль'
				credentials_color = VkKeyboardColor.POSITIVE
			else:
				credentials_text = 'Изменить логин и пароль'
				credentials_color = VkKeyboardColor.PRIMARY
			output.add_callback_button(
				credentials_text,
				payload={'type': PayloadTypes.enter_credentials, 'after_profile': True},
				color=credentials_color
			)

		output.add_line()
		if user['allows_mail'] == 1:
			mail_text = 'Запретить рассылку'
			mail_color = VkKeyboardColor.NEGATIVE
		else:
			mail_text = 'Разрешить рассылку'
			mail_color = VkKeyboardColor.POSITIVE

		output.add_callback_button(mail_text, payload={'type': PayloadTypes.toggle_mail, 'msg_id': msg_id}, color=mail_color)

		return output.get_keyboard()
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
			self.makeKeyboardSelectGroup(group_names, None, Purposes.registration)
		)

	def answerAskIfCanSend(self, vid, progress):
		"""Вопрос: можно ли присылать рассылки"""
		api.send(vid, self.answers['question_can_send_messages'].format(progress), self.keyboards['yn_text'])

	def answerWrongInput(self, vid):
		"""Неверный ввод"""
		api.send(vid, self.answers['wrong_input'])

	def answerPostRegistration(self, vid, user_type):
		"""Добро пожаловать"""
		if user_type == 1:
			api.send(vid, self.answers['welcome_post_reg'], self.keyboards['stud_hub'])
		else:
			api.send(vid, self.answers['welcome_post_reg'], self.keyboards['teacher_hub'])

	def answerSelectDate(self, vid, msg_id, target, purpose, edit=False):
		"""Отсылает сообщение с выбором даты"""
		keyboard = self.makeKeyboardSelectRelevantDate(purpose, msg_id, target)

		if not keyboard:
			api.send(vid, self.answers['no_relevant_data'])
		else:
			if edit:
				api.edit(vid, msg_id, self.answers['pick_day'], kb=keyboard)
			else:
				api.send(vid, self.answers['pick_day'], kb=keyboard)

	def answerShowScheduleForGroup(self, vid, date, gid):
		"""Показ расписания для группы"""
		response = database.getScheduleDataForGroup(date, gid)

		if not response:
			api.send(vid, self.answers['no-data'])
			return

		# Расписание кэшировано?
		if response['photo_id']:
			api.send(vid, None, None, 'photo'+str(self.config['public_id'])+'_'+str(response['photo_id']))
			return

		# Прикол для Виталия :P
		if vid == 240088163:
			api.send(vid, self.getRandomWaitText())

		# Нет кэшированного изображения, делаем
		msg_id = api.send(vid, self.getRandomWaitText())
		self.tasks.append(graphics.GroupScheduleGenerator(
			vid,
			self.config['public_id'],
			self.themes['rasp'],
			self,
			'group-schedule',
			msg_id,
			date,
			gid
		))
		self.tasks[-1].start()

	def answerShowScheduleForTeacher(self, vid, msg_id, date, teacher_id):
		"""Показ расписания для преподавателя"""
		response = database.getCachedScheduleOfTeacher(date, teacher_id)
		if response:
			# Есть кэшированное
			api.send(vid, None, None, 'photo'+str(self.config['public_id'])+'_'+str(response['photo_id']))
			return
		msg_id = api.send(vid, self.getRandomWaitText())

		self.tasks.append(graphics.TeacherScheduleGenerator(
			vid,
			self.config['public_id'],
			self.themes['rasp'],
			self,
			'teacher-schedule',
			msg_id,
			date,
			teacher_id
		))
		self.tasks[-1].start()

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
				vid,
				self.config['public_id'],
				self.themes['grades'],
				self,
				'grades',
				msg_id,
				login,
				password,
				self.keyboards['enter_journal_credentials'],
				user_id
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
		else:
			api.send(vid, self.answers['returning'], self.keyboards['teacher_hub'])

	def answerWhatsNext(self, vid, target, for_teacher):
		"""Отвечает какая пара следующая"""
		if for_teacher:
			response = database.getNextPairForTeacher(target)
		else:
			response = database.getNextPairForGroup(target)

		if not response:
			api.send(vid, self.answers['get-next-fail'])
			return

		# Оставшееся время
		hours_left = response['dt'] * 24
		minutes_left = (hours_left - int(hours_left)) * 60

		if for_teacher == False:
			api.send(vid, self.answers['get-next-student'].format(
				str(round(hours_left)) + ' ' + formatHoursGen(round(hours_left)),
				str(round(minutes_left)) + ' ' + formatMinutesGen(round(minutes_left)),
				response['pair_name'],
				response['pair_place'],
				response['pair_time']
			))
		else:
			api.send(vid, self.answers['get-next-teacher'].format(
				str(round(hours_left)) + ' ' + formatHoursGen(round(hours_left)),
				str(round(minutes_left)) + ' ' + formatMinutesGen(round(minutes_left)),
				response['pair_name'],
				response['pair_time'],
				response['pair_group'],
				response['pair_place']
			))

	def answerSelectTeacher(self, vid, message_id, purpose):
		"""Отправляет сообщения с клавиатурами выбора преподавателя"""

		# Узнаём какие вообще есть преподаватели
		teachers = database.getAllTeachers()
		keyboards = self.makeTeacherSelectKeyboards(teachers, purpose, message_id)
		amount = len(keyboards)

		for index, k in enumerate(keyboards):
			api.send(vid, self.answers['select-teacher'].format(index + 1, amount), k)

	def answerUpdateHub(self, vid, user_type):
		"""Присылает клавиатуру с меню"""
		if user_type == 1:
			api.send(vid, self.answers['updating-menu'], self.keyboards['stud_hub'])

	def answerSelectGroupCourse(self, vid, msg_id, purpose, edit):
		"""Отправляет сообщение с выбором курса"""
		keyboard = self.makeKeyboardSelectCourse(msg_id, purpose)
		if edit:
			api.edit(vid, msg_id, self.answers['select-course'], keyboard)
		else:
			api.send(vid, self.answers['select-course'], keyboard)

	def answerSelectGroupSpec(self, vid, msg_id, course, purpose):
		"""Отправляет сообщение с выбором группы"""
		group_names = database.getGroupsByCourse(course)
		api.edit(
			vid,
			msg_id,
			self.answers['select-group'],
			self.makeKeyboardSelectGroup(group_names, msg_id, purpose)
		)

	def answerBells(self, vid):
		"""Отправляет сообщение с расписанием звонков"""
		api.send(vid, self.answers['bells-schedule'])

	def answerShowProfile(self, vid, msg_id, user, edit):
		"""Отправляет сообщение профиля"""
		message = ""

		if user['type'] == 1:
			# Студент
			message += self.answers['profile-identifier-student'].format(database.getGroupName(user['gid']))
			if user['journal_login'] == None:
				message += self.answers['profile-journal-not-filled']
			else:
				message += self.answers['profile-journal-filled'].format(user['journal_login'])
		else:
			# Преподаватель
			message += self.answers['profile-identifier-student'].format(database.getTeacherSurname(user['teacher_id']))

		if user['allows_mail'] == 1:
			message += self.answers['profile-mail-allowed']
		else:
			message += self.answers['profile-mail-not-allowed']

		keyboard = self.makeProfileKeyboard(msg_id, user)

		if edit:
			api.edit(vid, msg_id, message, keyboard)
		else:
			api.send(vid, message, keyboard)

	def answerAskTeacherSignature(self, vid, question_progress):
		"""Просит преподавателя выбрать себя из списка"""
		api.send(vid, self.answers['question-who-are-you'].format(question_progress), self.keyboards['empty'])

	def answerAskCabNumber(self, vid):
		"""Просит преподавателя написать кабинет"""
		api.send(vid, self.answers['type-cabinet'], self.keyboards['cancel'])

	def answerShowCabinetOccupancy(self, vid, date, place):
		"""Показ занятости кабинетов"""
		response = database.getCachedPlaceOccupancy(date, place)
		if response:
			# Есть кэшированное
			api.send(vid, None, None, 'photo'+str(self.config['public_id'])+'_'+str(response['photo_id']))
			return

		msg_id = api.send(vid, self.getRandomWaitText())
		self.tasks.append(graphics.CabinetGenerator(
			vid,
			self.config['public_id'],
			self.themes['rasp'],
			self,
			'teacher-schedule',
			msg_id,
			date,
			place
		))
		self.tasks[-1].start()
	# КОНЕЦ ОТВЕТОВ БОТА

	def handleMessage(self, text, user, message_id):
		"""Принимает сообщение, обрабатывает, отвечает и сохраняет результат. Возвращает true, если данные пользователя
		нужно обновить"""
		vid = user['vk_id']

		if user['state'] == States.hub:
			# Выбор функции бота
			if text == 'Расписание':
				if user['type'] == 1:
					self.answerSelectDate(vid, message_id + 1, user['gid'], Purposes.stud_rasp_view)
				else:
					self.answerSelectDate(vid, message_id + 1, user['teacher_id'], Purposes.teacher_rasp_view)
			if text == 'Оценки' and user['type'] == 1:
				self.answerShowGrades(vid, user['id'], message_id + 1, user['journal_login'], user['journal_password'])
			if text == 'Кабинеты' and user['type'] == 2:
				user['state'] = States.enter_cab
				self.answerAskCabNumber(vid)
				return True
			if text == 'Что дальше?':
				if user['type'] == 1:
					self.answerWhatsNext(vid, user['gid'], False)
				else:
					self.answerWhatsNext(vid, user['teacher_id'], True)
			if text == 'Где преподаватель?':
				self.answerSelectTeacher(vid, message_id + 1, Purposes.teacher_rasp_view)
			if text == 'Расписание группы':
				self.answerSelectGroupCourse(vid, message_id + 1, Purposes.stud_rasp_view, False)
			if text == 'Звонки':
				self.answerBells(vid)
			if text == 'Профиль':
				self.answerShowProfile(vid, message_id + 1, user, False)
			if text == '.':
				self.answerUpdateHub(vid, user['type'])
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
				user['question_progress'] += 1
				user['state'] = States.void
				self.answerAskTeacherSignature(vid, user['question_progress'])
				self.answerSelectTeacher(vid, message_id + 2, Purposes.registration)
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
			self.answerPostRegistration(vid, user['type'])
			return True

		if user['state'] == States.enter_login or user['state'] == States.enter_login_after_profile:
			# Ввод логина
			if self.checkIfCancelled(text, user):
				return True
			user['journal_login'] = text
			if user['state'] == States.enter_login:
				user['state'] = States.enter_password
			else:
				user['state'] = States.enter_password_after_profile
			self.answerAskJournalPassword(vid)
			return True

		if user['state'] == States.enter_password or user['state'] == States.enter_password_after_profile:
			# Ввод пароля
			if self.checkIfCancelled(text, user):
				return True
			user['journal_password'] = hashlib.sha1(bytes(text, "utf-8")).hexdigest()

			self.answerDone(vid)
			self.answerToHub(vid, user['type'])
			if user['state'] == States.enter_password_after_profile:
				self.answerShowProfile(vid, message_id + 1, user, False)

			user['state'] = States.hub
			return True

		if user['state'] == States.enter_cab:
			# Ввод кабинета
			if self.checkIfCancelled(text, user):
				return True
			user['state'] = States.hub
			self.answerToHub(vid, user['type'])
			self.answerSelectDate(vid, message_id + 1, text, Purposes.view_cabinets)
			return True

	def handleMessageWithPayload(self, data, user, message_id):
		"""handleMessage для сообщений с доп. данными"""
		vid = user['vk_id']

		if data['type'] == PayloadTypes.select_date:
			# Выбрана дата.. но для чего?
			if data['purpose'] == Purposes.stud_rasp_view:
				# Просмотр расписания группы
				self.answerShowScheduleForGroup(vid, data['date'], data['target'])
				return False
			if data['purpose'] == Purposes.teacher_rasp_view:
				# Просмотр расписания преподавателя
				self.answerShowScheduleForTeacher(vid, data['msg_id'], data['date'], data['target'])
				return False
			if data['purpose'] == Purposes.view_cabinets:
				# Просмотр занятости кабинетов
				self.answerShowCabinetOccupancy(vid, data['date'], data['target'])
				return False

		if data['type'] == PayloadTypes.select_course:
			# Выбран курс. Purpose передаётся дальше
			self.answerSelectGroupSpec(vid, data['msg_id'], data['num'], data['purpose'])

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
			if data['purpose'] == Purposes.stud_rasp_view:
				self.answerSelectDate(vid, data['msg_id'], data['gid'], Purposes.stud_rasp_view, True)
				return False
			if data['purpose'] == Purposes.edit_student:
				user['gid'] = data['gid']
				self.answerShowProfile(vid, data['msg_id'], user, True)
				return True

		if data['type'] == PayloadTypes.enter_credentials:
			# Переводим пользователя на ввод логина и пароля дневника
			if data['after_profile'] == False:
				user['state'] = States.enter_login
			else:
				user['state'] = States.enter_login_after_profile
			self.answerAskJournalLogin(vid)
			return True

		if data['type'] == PayloadTypes.select_teacher:
			# Удаляем прошлые сообщения
			to_delete = ''
			for i in range(data['msg_id'], data['msg_id'] + data['amount']):
				to_delete += str(i) + ','
			api.delete(to_delete)

			# Выбран преподаватель... но для чего?
			if data['purpose'] == Purposes.teacher_rasp_view:
				# Просмотр расписания преподавателя
				self.answerSelectDate(vid, message_id + 1, data['teacher_id'], Purposes.teacher_rasp_view, True)
				return False

			if data['purpose'] == Purposes.registration:
				# Преподаватель регистрируется
				user['teacher_id'] = data['teacher_id']
				user['question_progress'] += 1
				user['state'] = States.reg_can_send
				self.answerAskIfCanSend(vid, user['question_progress'])
				return True

		if data['type'] == PayloadTypes.edit_group:
			# Изменение группы, привязанной к пользователю
			if data['purpose'] == Purposes.edit_student:
				self.answerSelectGroupCourse(vid, data['msg_id'], Purposes.edit_student, True)
				return False

		if data['type'] == PayloadTypes.toggle_mail:
			# Переключение разрешения рассылки
			if user['allows_mail'] == 1:
				user['allows_mail'] = 0
			else:
				user['allows_mail'] = 1
			self.answerShowProfile(vid, data['msg_id'], user, True)
			return True

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

				self.last_vid = vid # Сохраняем кто последний писал. Необходимо для отчёта об ошибке

				if len(text) == 0:
					continue

				if from_group:
					# Пока что мы не будем обрабатывать сообщения из бесед
					continue

				user = database.getUserInfo(vid)

				if self.print_user:
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
		print2("Отсутствует параметр -t. Использование -t <vk token> [--print-user]", 'red')
		sys.exit(1)

	# Инициализируем БД
	database.start()

	# Авторизация ВКонтакте
	session = api.start(args)

	# Инициализация бота
	__dir__ = os.path.dirname(os.path.abspath(__file__))
	bot = Bot(session, __dir__, '--print-user' in args)

	# Настройка логирования
	logging.basicConfig(
		format='\n%(asctime)s %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		filename=__dir__+'/error.log',
		encoding='utf-8',
		filemode='a',
		level=logging.ERROR
	)

	# Цикл работы бота
	while(True):
		try:
			bot.run()
		except KeyboardInterrupt:
			print2('\nПока!', 'green')
			database.stop()
			sys.exit(0)

		except ConnectionError:
			# Такие ошибки довольно часты на сервере техникума и поэтому не уведомляем никого об этом
			print2('Connection error', 'red')
			logging.error('ошибка подключения')
			try:
				time.sleep(30)
			except KeyboardInterrupt:
				print2('\nПока!', 'red')
				database.stop()
				sys.exit(0)

		except Exception as e:
			api.tgErrorReport(str(e))
			try:
				api.send(bot.last_vid, bot.answers['exception'].format(str(e)))
			except:
				pass
			print2(str(e), 'red')
			logging.exception('обработана ошибка')


if __name__ == "__main__":
	main(sys.argv)
