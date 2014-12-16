from twisted.python import log
import random
import logging

def setup():
	log.msg("ADC.setup")	

def read(pin): 
	log.msg("ADC.read "  + pin, logLevel=logging.DEBUG)
	raw = read_raw(pin)
	value = raw / 1800.0 
	return value

def read_raw(pin):
	log.msg("ADC.read_raw " + pin, logLevel=logging.DEBUG)
	sample = random.randint(0,4095)      
	value = (float(sample) / 4096.0) * 1800.0
        return value
