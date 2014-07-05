from OpenSSL import SSL
from twisted.internet import ssl

class WebClientSSLContextFactory(ssl.ClientContextFactory):
	def __init__(self, contextFactory):
		self.contextFactory = contextFactory


	def getContext(self, hostname, port):
		return self.contextFactory.getContext() 
