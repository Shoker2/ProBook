import configparser
import os
import ast

class Configure:
	DEFAULT_CONFIG: dict
	
	def __init__(self, config_path='./config.ini', default_config: dict = {}, create=True):
		self.DEFAULT_CONFIG = default_config

		self.config_path = config_path
		self.config = configparser.ConfigParser()

		if create and (not os.path.isfile(self.config_path)):
			self.write()
		
		self.config.read(self.config_path, encoding='utf-8')

		for key in self.DEFAULT_CONFIG.keys():
			self.repair_selections(key)
	
	def repair_selections(self, selection: str):
		if selection not in self.config.keys():
			self[selection] = {}

		for key in self.DEFAULT_CONFIG[selection].keys():
			if key not in self[selection].keys():
				self.config[selection][key] = str(self.DEFAULT_CONFIG[selection][key])
		
		self.write()
		
	def read(self, section, key):
		self.config.read(self.config_path, encoding='utf-8')
		return self.config[section][key]
	
	def get(self, selection, key):
		return ast.literal_eval(self.config[selection][key])

	def keys(self):
		return self.config.keys()
	
	def __getitem__(self, key):
		# return 
		return self.config[key]
	
	def __setitem__(self, key, value):
		self.config[key] = value
	
	# def __str__(self) -> str:
	# 	data = {}

	# 	for selection in self.config.keys():
	# 		for key in self.config[selection].keys():
	# 			data[selection][key] = self.config[selection][key]

	# 	return str(data)

	def write(self):
		with open(self.config_path, 'w+', encoding='utf-8') as configfile:
			self.config.write(configfile)

if __name__ == '__main__':
	config = Configure(default_config= {
		"AllowedHosts": {
			'use_allowed_hosts': True,
			'allowed_hosts': ["127.0.0.1"]
		}
	})

	data = config["AllowedHosts"]["allowed_hosts"]
	print(data)
	print(type(data))