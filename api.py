# api.py
# Модуль для работы с API Вконтакте

from utils import *
import vk_api
import requests
import json

def start(bot_token, tg_report_token, tg_report_id):
	"""Авторизуется во ВКонтакте, сохраняет несколько глобальных переменных"""

	# Авторизуемся
	global API
	global PHOTOUPLOAD_URL

	session = vk_api.VkApi(token=bot_token)
	API = session.get_api()
	PHOTOUPLOAD_URL = API.photos.getMessagesUploadServer()["upload_url"]

	# Уведомления в телеграм об ошибках
	global TG_REPORT_TOKEN
	global TG_REPORT_ID
	global TG_REPORT
	TG_REPORT = (tg_report_token != None) or (tg_report_id != None)
	if TG_REPORT:
		if not tg_report_token:
			print2('Указан tg-report-id, но не указан --tg-report-token', 'red')
			exit()
		if not tg_report_id:
			print2('Указан tg-report-token, но не указан --tg-report-id', 'red')
			exit()

		TG_REPORT_TOKEN = tg_report_token
		TG_REPORT_ID = tg_report_id

	return session

def send(vid, msg, kb = None, attach = None):
	"""Отправляет сообщение пользователю"""
	return API.messages.send(
		peer_id = vid,
		message = msg,
		keyboard = kb,
		attachment = attach,
		random_id = 0
	)

def edit(vid, msg_id, msg, kb = None, attach = None):
	"""Изменяет сообщение"""
	API.messages.edit(
		peer_id = vid,
		message = msg,
		keyboard = kb,
		attachment = attach,
		message_id = msg_id
	)

def delete(msg_id):
	try:
		API.messages.delete(message_ids=msg_id, delete_for_all=True)
	except:
		pass

def uploadImage(path):
	"""Загружает изображение с диска и получает id загрузки для параметра attachment"""
	# Чтение данных
	try:
		with open(path, 'rb') as f:
			response = requests.post(PHOTOUPLOAD_URL, files={"file": (path, f.read(), 'image\\png')})
		if not response.ok:
			return
	except FileNotFoundError:
		return None

	photo_info = json.loads(response.content)
	save = API.photos.saveMessagesPhoto(photo=photo_info['photo'], server=photo_info['server'], hash=photo_info['hash'])
	return save[0]['id']

def uploadDocument(peer_id, path):
	"""Загружает файл с диска и получает id для параметра attachment"""
	url = API.docs.getMessagesUploadServer(peer_id=peer_id)['upload_url']
	try:
		with open(path, 'rb') as f:
			response = requests.post(url, files={"file": (path, f.read(), 'text\\plain')})
		if not response.ok:
			return
	except FileNotFoundError:
		return

	uploaded_info = json.loads(response.content)['file']
	return API.docs.save(file=uploaded_info)['doc']['id']

def answerCallback(event_id, vid, peer_id):
	"""Отвечает на callback кнопку"""
	API.messages.sendMessageEventAnswer(
		event_id=event_id,
		user_id=vid,
		peer_id=peer_id
	)

def tgErrorReport(text):
	"""Уведомляет кого то об ошибке"""
	if not TG_REPORT:
		return
	text = '<pre>Ошибка в техботе </pre>' + text
	try:
		r=requests.get('https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}&parse_mode=html'.format(TG_REPORT_TOKEN, TG_REPORT_ID, text))
	except:
		print2('Не удалось отправить уведомление об ошибке', 'red')

def tgAlert(text, prefix):
	"""Уведомляет кого то о чём то"""
	if not TG_REPORT:
		return
	text = '<pre>'+prefix+' </pre>'+text
	try:
		r = requests.get('https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}&parse_mode=html'.format(TG_REPORT_TOKEN, TG_REPORT_ID, text))
	except:
		print2('Не удалось отправить уведомление', 'red')

def massSend(users, message, keyboard):
	"""Отправляет рассылку"""
	current_ids = ''
	messages_sent = 0
	i = 0

	while i < len(users):
		current_ids += str(users[messages_sent]['vk_id']) + ','
		i += 1

		messages_sent += 1
		if messages_sent == 100:
			API.messages.send(user_ids=current_ids, message=message, keyboard=keyboard, random_id=0)
			current_ids = ''
			messages_sent = 0

	if messages_sent > 0:
		API.messages.send(user_ids=current_ids, message=message, keyboard=keyboard, random_id=0)
