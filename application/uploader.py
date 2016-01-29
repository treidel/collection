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

class CustomMQTTFactory(MQTTFactory):
	def __init__(self, uploader):
		MQTTFactory.__init__(self, profile=MQTTFactory.PUBLISHER)
		self.uploader = uploader

	def clientConnectionFailed(self, connector, reason):
		Log.info("connection failed reason={}".format(reason))
		MQTTFactory.clientConnectionFailed(self, connector, reason)	
	
	def clientConnectionLost(self, connector, reason):
		Log.info("connection lost reason={}".format(reason))
		# clear the protocol
		self.uploader.protocol = None
		# let the base class do the rest
		MQTTFactory.clientConnectionLost(self, connector, reason)

	def buildProtocol(self, addr):
		Log.info("connected to addr={}".format(addr))
		# reset the delay next time we re-connect
		self.resetDelay()
		# create the protocol
		protocol = MQTTFactory.buildProtocol(self, addr)
		# do the connection handling real soon
		task.deferLater(reactor, 0.0, self.uploader._connected, protocol)
		# hand back the protocl
		return protocol

class Uploader:

	def __init__(self, device, host, port, ca_cert, device_key, device_cert):
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
		self.factory = CustomMQTTFactory(self)
		# initialize the protocol to none
		self.protocol = None
		# store the device name
		self.device = device
	
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

	def _connect(self):
		Log.info("connecting")
		# start the connection
		self.endpoint.connect(self.factory)

	@inlineCallbacks
	def _connected(self, protocol):
		Log.info("registering")
                # start the MQTT connection sequence
                yield protocol.connect(self.device, keepalive=0, version=v31)
		Log.info("registered")
		# store the protocol
		self.protocol = protocol
		# trigger an upload
		self.upload()

	@inlineCallbacks 
	def _upload(self):
		Log.info("starting upload")

		# if we don't have a connection give up
		if self.protocol is None:
			Log.info("no connection, not sending")
			return

		# get all pending database entries
		records = yield Record.find(orderby='timestamp DESC')
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
					circuits = {}
					# query the measurements for this record
					measurements = yield record.measurements.get()
					# go through all of the measurements and add them to the JSON payload
					for measurement in measurements:
						# create the circuit
						circuit = {'amperage-in-a' : measurement.amperage, 'voltage-in-v' : measurement.voltage}
						circuits[measurement.circuit] = circuit

					# create the top-level record entry
					entry = {'timestamp' : record.timestamp, 'uuid' : record.uuid, 'duration-in-s' : record.duration, 'measurements' : circuits}		

					# HACK HACK - temporarily populate the device name
					entry['device'] = self.device

					# serialize to JSON
					serialized = dumps(entry)

					Log.info('sending record with UUID={} timestamp={}'.format(record.uuid, record.timestamp))
					yield self.protocol.publish(topic="topic/records", qos=1, message=serialized)
					Log.info("successfully sent record, deleting")
					yield record.delete()
				
				Log.info("sent " + str(len(records)) + " records")	
			except Exception as e:
            			Log.error("error received when sending records: {}".format(e))
				# force a disconnect 
				self.protocol.transport.loseConnection()
			
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
