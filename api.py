# api.py
# Модуль для работы с API Вконтакте

from utils import *
import vk_api
import requests
import json

def start(args):
	"""Авторизуется во ВКонтакте, сохраняет несколько глобальных переменных"""

	# Получаем токен из аргументов
	token_flag_index = args.index("-t")
	try:
		bot_token = args[token_flag_index + 1]
	except IndexError:
		# Не указан токен после -t
		print2("Не указан токен после параметра -t", 'red')
		sys.exit(1)

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
	TG_REPORT = ('--tg-report-token' in args) or ('--tg-report-id' in args)
	if TG_REPORT:
		if not '--tg-report-token' in args:
			print2('Не указан --tg-report-token', 'red')
			sys.exit(0)
		if not '--tg-report-id' in args:
			print2('Не указан --tg-report-id', 'red')
			sys.exit(0)

		TG_REPORT_TOKEN = args[args.index('--tg-report-token') + 1]
		TG_REPORT_ID = args[args.index('--tg-report-id') + 1]

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

def uploadImage(image_path):
	"""Загружает изображение с диска и получает id загрузки для параметра attachment"""
	# Чтение данных
	try:
		with open(image_path, 'rb') as f:
			payload = {"file": (image_path, f.read(), 'image\\png')}
	except FileNotFoundError:
		return None

	# Загрузка данных изображения
	response = json.loads(requests.post(PHOTOUPLOAD_URL, files=payload).content)

	# Получение id изображения
	return API.photos.saveMessagesPhoto(server=response["server"], photo=response["photo"], hash=response["hash"])[0]["id"]

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
		requests.get('https://api.telegram.org/bot{0}/sendMessage?chat_id={1}&text={2}&parse_mode=html'.format(TG_REPORT_TOKEN, TG_REPORT_ID, text))
	except:
		print2('Не удалось отправить уведомление об ошибке', 'red')
