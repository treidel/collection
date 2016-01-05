import string

from json import dumps
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.internet import defer
from twisted.internet import task
from twisted.internet import endpoints
from twisted.internet.defer import inlineCallbacks
from mqtt.client.factory import MQTTFactory
from mqtt import v31
from application.log import Log
from application.record import Record

class Uploader:

	def __init__(self, host, port, ca_cert, device_key, device_cert):
		Log.info('configuring uploader with host={} port={} ca_cert={} device_key={} device_cert={}'.format(host, port, ca_cert, device_key, device_cert))
		# load the certificates and key
		with open(ca_cert) as certAuthCertFile:
			certAuthCert = ssl.Certificate.loadPEM(certAuthCertFile.read())
		with open(device_key) as keyFile:
			with open(device_cert) as certFile:
				deviceCert = ssl.PrivateCertificate.loadPEM(keyFile.read() + certFile.read())
		# create the SSL context factory
		options = deviceCert.options(certAuthCert)
		# create the endpoint 
		self.endpoint = endpoints.SSL4ClientEndpoint(reactor, host, port, options)
		# create the factory
		self.factory = MQTTFactory(profile=MQTTFactory.PUBLISHER)
		# initialize the client to None to indicate we're not connected yet
		self.client = None
	
	def start(self):
		Log.info("starting")
		# try to connect
		task.deferLater(reactor, 0.0, self._connect)
		# we're supposed to return a deferred
		return defer.succeed(None)

	def upload(self):	
		Log.info("uploading")
		# trigger an upload in a short while
		task.deferLater(reactor, 0.0, self._upload)

	@inlineCallbacks
	def _connect(self):
		Log.info("connecting")
		# initialize the client variable so we can clean up in error cases
		try:
			# start the connection
			self.client = yield self.endpoint.connect(self.factory)
			Log.info("connected")
			# do the MQTT connect
			yield self.client.connect("device", keepalive=0, version=v31)
			Log.info("registered")
			# trigger an upload
			self.upload()
		except Exception, e:
			Log.info('failed to connect, waiting to retry.  Reason={}'.format(e))
			self.client = None
			task.deferLater(reactor, 10.0, self._connect)

	@inlineCallbacks 
	def _upload(self):
		Log.info("starting upload")

		# if we don't have a connection give up
		if self.client is None:
			Log.info("no connection, not sending")
			return

		# get all pending database entries
		records = yield Record.find()
		# check for cases where no records are found
		if 0 == len(records):
			Log.info("no records found, not sending")
		else:	
			# go through all records to create the REST payload
			Log.info("found " + str(len(records)) + " records")

			try:
				# iterate through all records
				for record in records:
					# setup the list of circuits
					circuits = []
					# query the measurements for this record
					measurements = yield record.measurements.get()
					# go through all of the measurements and add them to the JSON payload
					for measurement in measurements:
						# create the circuit
						circuit = {'circuit' : measurement.circuit, 'amperage-in-a' : measurement.amperage, 'voltage-in-v' : measurement.voltage}
						# add it to the list
					circuits.append(circuit)

					# create the top-level record entry
					entry = {'timestamp' : record.timestamp, 'uuid' : record.uuid, 'duration-in-s' : record.duration, 'measurements' : circuits}		

					# serialize to JSON
					serialized = dumps(entry)

					Log.info('sending record with UUID={}'.format(record.uuid))
					yield self.client.publish(topic="topic/records", qos=1, message=serialized)
					Log.info("successfully sent record, deleting")
					yield record.delete()
				
				Log.info("sent " + str(len(records)) + " records")	
				# trigger another upload in case there are still records to collect
				self.upload()

			except Exception as e:
            			Log.error("error received when sending records: " + str(e))
			
	def _success(records):
		Log.info("success")

	def _failure():
		Log.info("failure")

if __name__ == '__main__':

	import sys
	import logging
	from optparse import OptionParser
	from twisted.python import log
	from twisted.internet import reactor
	from application.database import Database

	Log.setup()

	parser = OptionParser()
	parser.add_option("--database", dest="database", help="database location")
	parser.add_option("--host", dest="host", help="MQTT server")
	parser.add_option("--port", dest="port", help="MQTT port")
	parser.add_option("--ca-cert", dest="cacert", help="CA certificate")
 	parser.add_option("--device-key", dest="devicekey", help="device key")
	parser.add_option("--device-cert", dest="devicecert", help="device cert")
	(options, args) = parser.parse_args()

	if options.database is None or options.host is None or options.port is None or options.cacert is None or options.devicekey is None or options.devicecert is None:
		raise Exception("missing argument")

	Database.setup(options.database)

	uploader = Uploader(options.host, int(options.port), options.cacert, options.devicekey, options.devicecert)
	uploader.start()

	reactor.run()
