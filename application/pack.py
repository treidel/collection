import Adafruit_BBIO.ADC as ADC
from time import sleep
from twisted.python import log

class Pack:

	# define the number of samples to collect = 0.133s worth @ 1920Hz
	NUM_SAMPLES = 256

	# define the sample rate
	SAMPLE_RATE = 1920.0

	# precalculate the collection delay
	COLLECTION_DELAY = 1.0 / SAMPLE_RATE

	@classmethod 
	def setup(cls):
		# initialize the ADC
		log.msg("Initializing ADC")
		ADC.setup()

	def __init__(self, index, adc_pin, turns, resistor):
		# store the provided data
		self.index = index;
		self.adc_pin = adc_pin
		
		# TBD: query pack parameters from the pack's EEPROM via I2C
		# for now hard code
		self.num_circuits = 1;
		# V = IR in general
                # Vsample = 0.9 * normalized sample
		# to get Iactual multiple Isample by the number of turns in the current transformer
                # so the sample is converted to actual current by muliplying the normalized sample
                # by (sample) * (turns) * (0.9) / (resistor)
		self.conversion_factor = (turns * 0.9) / resistor

	def get_index(self):
		return self.index;

	def get_num_circuits(self):
		return self.num_circuits;

	def collect_samples(self, circuit):
		# TBD: switch MUX to selected circuit via I2C
		
		# setup the list of samples
		samples = []
		# iterate to collect the samples
		for x in range(self.NUM_SAMPLES):
			# read the sample
			sample = ADC.read(self.adc_pin)
			# normalize the sample
			normalized_sample = sample - 0.5
			# convert to an amperage
			amperage = normalized_sample * self.conversion_factor
			# add it to the list
			samples.append(amperage)
			# wait the collection delay
			sleep(self.COLLECTION_DELAY)
		# done
		return samples
