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
