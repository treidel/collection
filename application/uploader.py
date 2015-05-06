import string

from json import dumps
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.internet import defer
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.websocket import connectWS
from autobahn.twisted.websocket import StompWebSocketClientFactory
from autobahn.twisted.websocket import StompWebSocketClientProtocol
from autobahn.twisted.stomp import ClientSession
from autobahn.twisted.stomp import ClientSessionFactory
from urlparse import urlsplit
from application.log import Log
from application.record import Record

class CustomStompWebSocketClientFactory(StompWebSocketClientFactory):

	def startedConnecting(self, connector):
		Log.info("started connecting to STOMP server")
		self.uploader.session = None

	def clientConnectionFailed(self, connector, reason):
		Log.info("failed to connect to STOMP server, reason=" + str(reason))
		# trigger a reconnect later
		task.deferLater(reactor, 10.0, self.uploader._connect)		

	def clientConnectionLost(self, connector, reason):
		Log.info("connection to STOMP server lost, reason=" + str(reason))
		# clear ourselves in the uploader
		self.uploader.session = None
		# trigger a reconnect
		task.deferLater(reactor, 10.0, self.uploader._connect)	

class CustomClientSession(ClientSession):

	def onConnect(self):
		Log.info("connected to STOMP server")
		ClientSession.onConnect(self)

	def onAttach(self):
		Log.info("attached to STOMP server")
		# setup the registration message
		registration = {'model' : 'test', 'software-version' : '1.0', 'hardware-version' : '1.0'}
		payload = dumps(registration)
		self.send('/registration', payload, False)
		# store ourselves in the uploader
		self.factory.uploader.session = self
		# start an upload in case there are stored records
		self._as_future(self.factory.uploader._upload)
		
	def onDetach(self):
		Log.info("detached from STOMP server")
		
class Uploader:

	def __init__(self, url, ca_cert, device_key, device_cert):
		# load the certificates and key
		with open(ca_cert) as certAuthCertFile:
			certAuthCert = ssl.Certificate.loadPEM(certAuthCertFile.read())
		with open(device_key) as keyFile:
			with open(device_cert) as certFile:
				deviceCert = ssl.PrivateCertificate.loadPEM(keyFile.read() + certFile.read())
		# create the SSL context factory
		self.sslContextFactory = deviceCert.options(certAuthCert)
		# parse the url
		r = urlsplit(url)
		# create the session factory
		session_factory = ClientSessionFactory(r.hostname)
		session_factory.session = CustomClientSession
		session_factory.uploader = self
		# create the connection factory
		self.factory = CustomStompWebSocketClientFactory(session_factory, url=url, debug=True)
		# store a reference to ourselves in the factory
		self.factory.uploader = self
	
	def start(self):
		Log.info("starting uploading")
		# try to connect
		task.deferLater(reactor, 0.0, self._connect)
		# we're supposed to return a deferred
		return defer.succeed(None)

	def upload(self):
		# trigger an upload in a short while
		task.deferLater(reactor, 1.0, self._upload)

	def _connect(self):
		Log.info("triggering connection")
		# initialize the session to None to indicate we're not connected yet
		self.session = None
		# start the connection
		connectWS(self.factory, self.sslContextFactory)

	@inlineCallbacks 
	def _upload(self):
		Log.info("starting upload")

		# if we don't have a connection give up
		if self.session is None:
			Log.info("no connection, not sending")
			return

		# get all pending database entries
		records = yield Record.find(limit=16)
		# check for cases where no records are found
		if 0 == len(records):
			Log.info("no records found, not sending")
		else:	
			# go through all records to create the REST payload
			Log.info("found " + str(len(records)) + " records")

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
					circuit = {'circuit' : measurement.circuit, 'amperage-in-a' : measurement.amperage, 'voltage-in-v' : measurement.voltage}
					# add it to the list
					circuits.append(circuit)

				# create the top-level record entry
				entry = {'timestamp' : record.timestamp, 'uuid' : record.uuid, 'measurements' : circuits}		
				# add the entry to the list
				entries.append(entry)

			# serialize to JSON
			serialized = dumps(entries)

			try:
				Log.info("sending records")
				yield self.session.send('/records', serialized, True)
				Log.info("successfully sent " + str(len(records)))

				# delete the records we sent
				for record in records:
					yield record.delete()
				# trigger another upload in case where are still records to collect
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
	parser.add_option("--url", dest="url", help="The WebSocket URL")
	parser.add_option("--ca-cert", dest="cacert", help="CA certificate")
 	parser.add_option("--device-key", dest="devicekey", help="device key")
	parser.add_option("--device-cert", dest="devicecert", help="device cert")
	(options, args) = parser.parse_args()

	if options.database is None or options.url is None or options.cacert is None or options.devicekey is None or options.devicecert is None:
		raise Exception("missing argument")

	Database.setup(options.database)
	
	uploader = Uploader2(options.url, options.cacert, options.devicekey, options.devicecert)

	reactor.run()
