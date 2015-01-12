import random

from application.log import Log

def setup():
	Log.info("ADC.setup")

def read(pin): 
	Log.debug("ADC.read "  + pin)
	raw = read_raw(pin)
	value = raw / 1800.0 
	return value

def read_raw(pin):
	Log.debug("ADC.read_raw " + pin)
	sample = random.randint(0,4095)      
	value = (float(sample) / 4096.0) * 1800.0
        return value
