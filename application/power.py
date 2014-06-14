from twisted.python import log
from numpy import sqrt, mean, asarray

class Power:

	@classmethod
	def rms(cls, values):
		return sqrt(mean(asarray(values) ** 2))

