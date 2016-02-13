import string

from json import dumps
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.internet import defer
from twisted.internet import task
from twisted.internet import endpoints
from twisted.internet.defer import inlineCallbacks
from mqtt.client.factory import MQTTFactory
from mqtt.client.publisher import MQTTProtocol
from mqtt import v31
from application.log import Log
from application.record import Record

class CustomMQTTProtocol(MQTTProtocol):
	def __init__(self, factory):
		MQTTProtocol.__init__(self, factory)
		self.uploader = factory.uploader

	def connectionMade(self):
		Log.info("registering")
                # start the MQTT connection sequence
                d = self.connect(self.uploader.device, keepalive=0, version=v31)
		d.addCallback(self.uploader._connected, self)
		d.addErrback(self.uploader._failed)

	def connectionLost(self, reason):
		Log.info("lost reason={}".format(reason))
		# clear the uploader
		self.uploader.protocol = None
                # retry in a little while
                Log.info("retrying connection in 10.0 seconds")
                task.deferLater(reactor, 10.0, self.uploader._connect)
		# call the base class
		MQTTProtocol.connectionLost(self, reason)
		
class CustomMQTTFactory(MQTTFactory):
	def __init__(self, uploader):
		MQTTFactory.__init__(self, profile=MQTTFactory.PUBLISHER)
		self.uploader = uploader
	
	def buildProtocol(self, addr):
		Log.info("connected to addr={}".format(addr))
		# create the protocol
		protocol = CustomMQTTProtocol(self)
		# register the disconnection handler
		protocol.setDisconnectCallback(self.uploader._disconnected)
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
		# store if an upload is in progress
		self.uploading = False 
	
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
		d = self.endpoint.connect(self.factory)
		d.addErrback(self._failed)

	def _disconnect(self):
		Log.info("disconnecting")
		# force-close the transport (if it exists)
                if self.protocol is not None:
			# send a disconnect message		
			self.protocol.disconnect()
			# disconnect the transport 
                        self.protocol.transport.loseConnection()
                # protocol no longer valid
                self.protocol = None
                # retry in a little while
                Log.info("retrying connection in 10.0 seconds")
                task.deferLater(reactor, 10.0, self._connect)

	def _disconnected(self, reason):
		Log.info("disconnected reason={}".format(reason))
		# disconnect transport
		self.protocol.transport.loseConnection()
		# protocol no longer valid
		self.protocol = None
		# retry in a little while
		Log.info("retrying connection in 10.0 seconds")
		task.deferLater(reactor, 10.0, self._connect)

	def _connected(self, session, protocol):
		Log.info("registered session={} protocol={}".format(session, protocol))
		# store the protocol
		self.protocol = protocol
		# trigger an upload
		self.upload()

        def _failed(self, reason):
                Log.info("failed reason={}".format(reason))
		# if the protocol is open close the transport
		if self.protocol is not None:
			self.protocol.transport.loseConnection()		
                # retry in a little while
                Log.info("retrying connection in 10.0 seconds")
                task.deferLater(reactor, 10.0, self._connect)


	@inlineCallbacks 
	def _upload(self):
		Log.info("starting upload")
		# if there's already an upload in progress bail
		if self.uploading is True:
			Log.info("already uploading, not sending")
			return

		# if we don't have a connection give up
		if self.protocol is None:
			Log.info("no connection, not sending")
			return

		# mark that we are uploading
		self.uploading = True

		# get the most recent record 
		record = yield Record.find(orderby='timestamp DESC', limit=1)
		# check for cases where no records are found
		if record is None:
			Log.info("no records found, not sending")
			self.uploading = False
			return
		
		# go through all records to create the payload
		try:
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

			Log.info('found record with UUID={} timestamp={}'.format(record.uuid, record.timestamp))

			# make sure we still have a connection
			if self.protocol is not None:
				yield self.protocol.publish(topic="topic/records", qos=1, message=serialized)
				Log.info("successfully sent record, deleting UUID={}".format(record.uuid))
				yield record.delete()
			else:
				Log.info("lost connection, did not upload")
				
			# trigger another upload in case there's still records to be sent
			self.upload()
		except Exception as e:
            		Log.error("error received when sending records: {}".format(e))
			# on any error force a disconnect
			self._disconnect()
		# in all cases we're done uploading 
		self.uploading = False
			
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
