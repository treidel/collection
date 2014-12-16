from twisted.enterprise import adbapi
from twisted.internet.defer import inlineCallbacks
from twisted.python import log

from twistar.utils import transaction
from twistar.registry import Registry

from application.record import Record
from application.record import Measurement

class Database:

	@classmethod
	def setup(cls, database):
		log.msg("Initializing database")
		# create the database connection pool 
		# sqlite requires that foreign key support be turned on with every connection
		# to ensure that we have this turned on we use only one connection 
		Registry.DBPOOL = adbapi.ConnectionPool('sqlite3', database=database, check_same_thread=False, cp_max=1)
		# register our classes with the registry
		Registry.register(Record, Measurement)

	@classmethod
	def start(cls):
		return Registry.DBPOOL.runOperation("PRAGMA FOREIGN_KEYS=ON")

  	@classmethod
	def write_record(cls, record): 
		# run the database calls in a transaction to avoid race conditions
		@transaction
		@inlineCallbacks
		def interaction(txn):
			yield record_object.save()
			# go through each measurement 
			for measurement in record.measurements:
				# save it 
				measurement.record_id = record_object.id
				yield measurement.save()
		yield interaction()


