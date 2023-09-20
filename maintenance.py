# maintenance.py
# Скрипт ответа пользователям, что Техбот временно не работает

import api
import sys
import utils
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

def printUsage(problem_arg, problem_type):
	"""Выводит использование скрипта и все доступные параметры"""
	if problem_type == 1:
		print2("Отсутствует параметр " + problem_arg, 'red')
	elif problem_type == 2:
		print2("Отсутствует значение у параметра " + problem_arg, 'red')

	print("Использование: python maintenance.py --bot-token")
	print("--bot-token: Токен ВК бота")
	exit()

def getArg(argname, args):
	"""Парсит аргументы и возвращает значение по названию"""
	arg_index = args.index(argname)
	if arg_index == -1:
		return None
	try:
		return args[arg_index + 1]
	except IndexError:
		printUsage(argname, 2)

def main(args):
	if "-h" in args or "--help" in args:
		printUsage(None, None)

	required = ("--bot-token",)
	for arg in required:
		if not arg in args:
			printUsage(arg, 1)

	vk_token = getArg('--bot-token', args)
	session = api.start(vk_token, None, None)

	print2("Режим разработки активирован", "green")
	for event in self.longpoll.listen():

		# Получаем vid
		if event.type == VkBotEventType.MESSAGE_NEW:
			vid = event.obj.message['peer_id']
		elif event.type == VkBotEventType.MESSAGE_EVENT:
			vid = event.obj.peer_id

		# Отвечаем
		api.send(vid, "Техбот находится в режиме разработки в данный момент. Повтори запрос позже")

	print2("Режим разработки деактивирован", "red")

if __name__ == "__main__":
	main(sys.argv)