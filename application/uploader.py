import json
import logging

from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import task
from twisted.internet import ssl
from twisted.python import log
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from application.web import StringProducer
from application.ssl import WebClientSSLContextFactory
from application.record import Record

class Uploader:

	def __init__(self, ca_cert, device_key, device_cert):
		# load the certificates and key
		with open(ca_cert) as certAuthCertFile:
			certAuthCert = ssl.Certificate.loadPEM(certAuthCertFile.read())
		with open(device_key) as keyFile:
			with open(device_cert) as certFile:
				deviceCert = ssl.PrivateCertificate.loadPEM(keyFile.read() + certFile.read())
		# create the SSL context factory
		sslContextFactory = deviceCert.options(certAuthCert)

		# wrap the SSL context factory in a WebClientSSLContextFactory
		self.webClientContextFactory = WebClientSSLContextFactory(sslContextFactory)

	def start(self): 
		log.msg("starting upload")
		# schedule the collection timer
		uploadTimer = task.LoopingCall(self.upload_timer_handler)
		uploadTimer.start(60.0, now=True)		
		# we're supposed to return a deferred...
		return defer.succeed(None)

	@inlineCallbacks
	def upload_timer_handler(self):
		log.msg("upload_timer_handler enter", logLevel=logging.DEBUG)
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
				entry = {'timestamp' : record.timestamp, 'uuid' : record.uuid, 'measurements' : circuits}		
				# add the entry to the list
				entries.append(entry)

				# serialize to JSON
				serialized = json.dumps(entries)

				# create the HTTP client for the REST API call
				agent = Agent(reactor, webClientContextFactory, connectTimeout=2)
				# wrap the payload
				body = StringProducer(serialized)
				# setup the URL
				recordsURL = args.url + "/records"
				log.msg("sending records to " + recordsURL)
				# execute the request and set the callback handler
				request = agent.request('POST', recordsURL, Headers({'Content-Type' : ['application/json']}), body)
				request.addCallback(self.rest_response_handler, records)
				request.addErrback(self.rest_error_handler)

		log.msg("upload_timer_handler exit", logLevel=logging.DEBUG)

	# setup the HTTP response handler
	@inlineCallbacks
	def rest_response_handler(self, response, records):
		log.msg("rest_response_handler enter response=" + str(response) + " records=" + str(records), logLevel=logging.DEBUG)
		# check for success
		if 201 == response.code:
			log.msg("successfully uploaded " + str(len(records)) + " to " + args.url)
			# the request was successful so remove the records we sent from the database
			for record in records:
				yield record.delete()
		else:
			log.msg("received HTTP " + str(response.code) + " from " + args.url + ", leaving records in place")
		log.msg("rest_response_handler exit", logLevel=logging.DEBUG)	

	def rest_error_handler(error):
		log.msg("rest_error_handler enter error=" + str(error), logLevel=logging.DEBUG)

		log.msg("unable to contact server with URL=" + args.url)

		log.msg("rest_error_handler exit", logLevel=logging.DEBUG)


