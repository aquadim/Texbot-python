# api.py
# Модуль для работы с API Вконтакте

from utils import *
import vk_api
import requests
import json

def start(args):
	"""Авторизуется во ВКонтакте"""

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

	return session

def send(vid, msg, kb = None, attach = None):
	"""Отправляет сообщение пользователю"""
	API.messages.send(
		user_id = vid,
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

