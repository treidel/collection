import syslog
import logging

from twisted.python import log
from twisted.python import syslog

class Log:

	@classmethod
	def setup(cls):
		# store the default level 
		cls.level = logging.INFO
                # turn on syslog 
		syslog.startLogging(prefix='application')

	@classmethod
	def enable_debug(cls):
		# update the level
		cls.level = logging.DEBUG

  	@classmethod
	def debug(cls, message, **kw): 
		if cls.level <= logging.DEBUG:
			log.msg("DEBUG " + message, kw)

	@classmethod
	def info(cls, message, **kw):
		if cls.level <= logging.INFO: 
			log.msg("INFO " + message, kw)

	@classmethod
	def error(cls, failure):
		log.err(failure, None)

