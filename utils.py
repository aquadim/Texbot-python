# utils.py
# Функции, общие для всех модулей

def print2(text, color):
	if color == 'red':
		prefix = '\033[91m'
	elif color == 'green':
		prefix = '\033[92m'
	else:
		prefix = ''

	print(prefix + text + '\033[0m')

def isGroupName(text):
	"""Возвращает true если text - имя группы"""
	components = text.split(' ')
	if len(components) != 2:
		return False
	if not components[0].isdigit():
		return False
	return True

def getDateName(text):
	"""Принимает строку даты, возвращает дату в читаемой форме"""
	year, month, day = text.split('-')
	return day + ' ' + gen_month_num_to_str[int(month)]

gen_month_num_to_str = {9:"сентября",10:"октября",11:"ноября",12:"декабря",1:"января",2:"февраля",3:"марта",4:"апреля",5:"мая",6:"июня",7:"июля",8:"августа"}
gen_weekdays_num_to_str = {1:"Понедельник",2:"Вторник",3:"Среду",4:"Четверг",5:"Пятницу",6:"Субботу",7:"Воскресенье"}
weekdays_num_to_str = {1:"Понедельник",2:"Вторник",3:"Среда",4:"Четверг",5:"Пятница",6:"Суббота",7:"Воскресенье"}
