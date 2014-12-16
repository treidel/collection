#!/usr/bin/python

import argparse
import logging

from twisted.internet import reactor
from twisted.python import log
from twisted.python import syslog

from application.collector import Collector
from application.uploader import Uploader
from application.database import Database
from application.pack import Pack

# parse arguments
parser = argparse.ArgumentParser(description="Main Application")
parser.add_argument('--url', help="URL of API endpoint", required=True)
parser.add_argument('--database', help="sqlite database for the application", required=True)
parser.add_argument('--ca-cert', help="root CA certificate", required=True)
parser.add_argument('--device-cert', help="device certificate", required=True)
parser.add_argument('--device-key', help="device private key file", required=True)
args = parser.parse_args()

# configure syslog logging
syslog.startLogging(prefix='application')

# initialize the pack module
Pack.setup()

# initialize the database layer
Database.setup(args.database)

# create the collector
collector = Collector()

# create the uploader
uploader = Uploader(args.ca_cert, args.device_key, args.device_cert)

# TBD: probe the GPIO pins to detect the presence of pack modules
pack1 = Pack(0, "AIN0", 800, 15.0, 120.0)
collector.add_pack(pack1)
pack2 = Pack(1, "AIN1", 800, 15.0, 120.0)
collector.add_pack(pack2)
pack3 = Pack(2, "AIN2", 800, 15.0, 120.0)
collector.add_pack(pack3)
pack4 = Pack(3, "AIN3", 3000, 21.0, 240.0)
collector.add_pack(pack4)
pack5 = Pack(4, "AIN4", 3000, 21.0, 240.0)
collector.add_pack(pack5)
pack6 = Pack(5, "AIN5", 3000, 21.0, 240.0)
collector.add_pack(pack6)
pack7 = Pack(6, "AIN6", 3000, 7.5, 240.0)
collector.add_pack(pack7)

log.msg("Starting")

# wait until the database has started before starting the upload + collection
d = Database.start()
def processing_start(result):
	uploader.start()
	collector.start()
d.addCallback(processing_start)

log.msg("Running")

# run the reactor
reactor.run()
