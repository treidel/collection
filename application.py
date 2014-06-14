#!/usr/bin/python

from twisted.internet import reactor
from twisted.internet import task
from twisted.internet import defer
from twisted.internet import threads
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent
from twisted.enterprise import adbapi
from twisted.python import log
from twisted.python import syslog
import logging;
from twistar.registry import Registry
from twistar.utils import transaction
from application.pack import Pack
from application.power import Power
from application.record import Record
from application.record import Measurement
from application.web import StringProducer
import uuid;
from datetime import datetime;
import json;
import argparse;

# parse arguments
parser = argparse.ArgumentParser(description="Main Application")
parser.add_argument('--url', help="URL of API endpoint", required=True)
args = parser.parse_args()

# configure syslog logging
syslog.startLogging(prefix='application')

log.msg("Starting")

# create the database connection pool 
# sqlite requires that foreign key support be turned on with every connection
# to ensure that we have this turned on we use only one connection 
Registry.DBPOOL = adbapi.ConnectionPool('sqlite3', database="/var/local/samples.db", check_same_thread=False, cp_max=1)
# register our classes with the registry
Registry.register(Record, Measurement)


# turn on forein key handling
def enableForeignKeysHandler(ignore):
	log.msg("foreign keys enabled", logLevel=logging.DEBUG)

	# now that foreign keys and enabled we can start injecting data
	
	# call the collection timer every 10 seconds
	collectionTimer = task.LoopingCall(collectionTimerHandler)
	collectionTimer.start(10.0, now=True)

	# call the upload timer every minute
	uploadTimer = task.LoopingCall(uploadTimerHandler)
	uploadTimer.start(60.0, now=True)
Registry.DBPOOL.runOperation("PRAGMA FOREIGN_KEYS=ON").addCallback(enableForeignKeysHandler)

# initialize the pack module
Pack.setup()

# setup the list of packs
packs = []

# TBD: probe the GPIO pins to detect the presence of pack modules
pack1 = Pack(0, "AIN0")
packs.append(pack1)
pack2 = Pack(1, "AIN1")
packs.append(pack2)


# TBD: resize the thread pool to have enough threads for all collection to happen 
# concurrently

# setup the collection timer handler
@inlineCallbacks
def collectionTimerHandler():
	log.msg("collectionTimerHandler enter", logLevel=logging.DEBUG)
	# setup the list of deferred
	deferreds = []
	# collect for each pack
	for pack in packs:
		# schedule the collection in a thread
		deferreds.append(threads.deferToThread(packCollectionHandler, pack))
	# wait for all of the collection to finish
	d = defer.DeferredList(deferreds)
	results = yield d

	# run the database calls in a transaction to avoid race conditions
	@transaction
	@inlineCallbacks
	def interaction(txn):
		# create a record
		record = yield Record(uuid=str(uuid.uuid1()), timestamp=datetime.utcnow()).save();
		# go through the results
		for result in results:
			# get the pack
			pack = result[1]['pack']
			for circuit in range(pack.get_num_circuits()):
				# create the measurement 
				circuit_id = str(pack.get_index()) + "-" + str(circuit)
				value = result[1][circuit]
				measurement = yield Measurement(record_id=record.id, circuit=circuit_id, value=value).save()
	yield interaction()
	log.msg("collectionTimerHandler exit", logLevel=logging.DEBUG)

# setup the per-pack collection handler
def packCollectionHandler(pack):
	log.msg("packCollectionHandler enter pack=" + str(pack.get_index()), logLevel=logging.DEBUG)
	# setup the dict object with the return data
	result = {'pack' : pack}
	for circuit in range(pack.get_num_circuits()):
		# get the samples
		samples = pack.collect_samples(circuit)
		# calculate the RMS value for the signal
		rms = Power.rms(samples)
		result[circuit] = rms
	log.msg("packCollectionHandler exit result=" + str(result), logLevel=logging.DEBUG)
	return result

# setup the upload timer handler
@inlineCallbacks
def uploadTimerHandler():
	log.msg("uploadTimerHandler enter", logLevel=logging.DEBUG)
	# get all pending database entries
	records = yield Record.find()
	# check for cases where no records are found
	if 0 == len(records):
		log.msg("no records found, not sending HTTP request")
	else:	
		# go through all records to create the REST payload
		log.msg("sending " + str(len(records)) + " records to server")

		# setup the list of entries
		entries = []
		
		# iterate through all records
		for record in records:
			# setup the list of circuits
			circuits = []
			# query the measurements for this record
			measurements = yield record.measurements.get()
			# go through all of the measurements and add them to the JSON payload
			for measurement in measurements:
				# create the circuit
				circuit = {'circuit' : measurement.circuit, 'value' : measurement.value}
				# add it to the list
				circuits.append(circuit)

			# create the top-level record entry
			entry = {'timestamp' : record.timestamp, 'uuid' : record.uuid, 'circuits' : circuits}		
			# add the entry to the list
			entries.append(entry)

		# serialize to JSON
		serialized = json.dumps(entries)

		# make the REST API call
		agent = Agent(reactor, connectTimeout=2)
		body = StringProducer(serialized)
		request = agent.request('POST', args.url, None, body)
		request.addCallback(restResponseHandler, records)
		request.addErrback(restErrorHandler)

	log.msg("uploadTimerHandler exit", logLevel=logging.DEBUG)

# setup the HTTP response handler
@inlineCallbacks
def restResponseHandler(response, records):
	log.msg("restResponseHandler enter response=" + str(response) + " records=" + str(records), logLevel=logging.DEBUG)
	# check for success
	if 200 == response.code:
		log.msg("successfully uploaded " + str(len(records)) + " to " + args.url)
		# the request was successful so remove the records we sent from the database
		for record in records:
			yield record.delete()
	else:
		log.msg("received HTTP " + str(response.code) + " from " + args.url + ", leaving records in place")
	log.msg("restResponseHandler exit", logLevel=logging.DEBUG)	

def restErrorHandler(error):
	log.msg("restErrorHandler enter error=" + str(error), logLevel=logging.DEBUG)

	log.msg("unable to contact server with URL=" + args.url)

	log.msg("restErrorHandler exit", logLevel=logging.DEBUG)

log.msg("Running")

# run the reactor
reactor.run()
