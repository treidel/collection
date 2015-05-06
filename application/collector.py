import uuid

from datetime import datetime

from twisted.internet import defer
from twisted.internet import task
from twisted.internet import threads
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from application.log import Log
from application.database import Database
from application.record import Record
from application.record import Measurement
from application.pack import Pack
from application.power import Power

class Collector:

	def __init__(self, uploader):
		# store the uploader
		self.uploader = uploader
		# setup the list of packs
		self.packs = []
	
	def add_pack(self, pack):
		self.packs.append(pack)

	def start(self): 
		Log.info("starting collection")
		# size the thread pool to the numer of packs
		reactor.suggestThreadPoolSize(len(self.packs))
		# schedule the collection timer
		collectionTimer = task.LoopingCall(self.collection_timer_handler)
		collectionTimer.start(10.0, now=True)		
		# we're supposed to return a deferred...
		return defer.succeed(None)

	@inlineCallbacks
	def collection_timer_handler(self):
		Log.debug("collection_timer_handler enter")
		# setup the list of deferred
		deferreds = []
		# collect for each pack
		for pack in self.packs:
			# schedule the collection in a thread
			deferreds.append(threads.deferToThread(self.pack_collection_handler, pack))
		# wait for all of the collection to finish
		d = defer.DeferredList(deferreds)
		results = yield d

		Log.info("measurements collected") 

		# create list of measurements
		measurements = []

		# go through the results
		for result in results:
			# get the pack
			pack = result[1]['pack']
			for circuit in range(pack.get_num_circuits()):
				# create the measurement 
				circuit_id = str(pack.get_index()) + "-" + str(circuit)
				value = result[1][circuit]
				measurement = Measurement(circuit=circuit_id, amperage=value, voltage=pack.get_voltage())
				# store it in the record
				measurements.append(measurement)
		# create the record to be written to the database
		record = Record(uuid=str(uuid.uuid1()), timestamp=datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
       
		# write the record
		yield Database.write_record(record, measurements)
		# poke the uploader to tell it records are ready
		self.uploader.upload()
		# done 
		Log.debug("collection_timer_handler exit")

	# setup the per-pack collection handler
	def pack_collection_handler(self, pack):
		Log.debug("pack_collection_handler enter pack=" + str(pack.get_index()))
		# setup the dict object with the return data
		result = {'pack' : pack}
		for circuit in range(pack.get_num_circuits()):
			# get the samples
			samples = pack.collect_samples(circuit)
			# calculate the RMS value for the signal
			rms = Power.rms(samples)
			# store the result
			result[circuit] = rms
		Log.debug("pack_collection_handler exit result=" + str(result))
		return result
