import Adafruit_BBIO.ADC as ADC
from time import sleep
from twisted.python import log

class Pack:

	# define the number of samples to collect = 0.066s worth @ 240Hz
	NUM_SAMPLES = 16

	# define the sample rate
	SAMPLE_RATE = 480.0

	# precalculate the collection delay
	COLLECTION_DELAY = 1.0 / SAMPLE_RATE

	@classmethod 
	def setup(cls):
		# initialize the ADC
		log.msg("Initializing ADC")
		ADC.setup()

	def __init__(self, index, adc_pin):
		# store the provided data
		self.index = index;
		self.adc_pin = adc_pin
		
		# TBD: query pack parameters from the pack's EEPROM via I2C
		# for now hard code
		self.num_circuits = 1;
		self.max_current = 20.0;


	def get_index(self):
		return self.index;

	def get_num_circuits(self):
		return self.num_circuits;

	def get_max_current(self):
		return self.max_current;

	def collect_samples(self, circuit):
		# TBD: switch MUX to selected circuit via I2C
		
		# setup the list of samples
		samples = []
		# iterate to collect the samples
		for x in range(self.NUM_SAMPLES):
			# read the sample
			sample = ADC.read(self.adc_pin)
			# add it to the list
			samples.append(sample)
			# wait the collection delay
			sleep(self.COLLECTION_DELAY)
		# done
		return samples
