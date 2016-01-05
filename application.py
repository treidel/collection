#!/usr/bin/python

import argparse

from twisted.internet import reactor

from application.log import Log
from application.collector import Collector
from application.uploader import Uploader
from application.database import Database
from application.pack import Pack

# parse arguments
parser = argparse.ArgumentParser(description="Main Application")
parser.add_argument('--host', help="MQTT host name", required=True)
parser.add_argument('--port', help="MQTT port", type=int, required=True)
parser.add_argument('--database', help="sqlite database for the application", required=True)
parser.add_argument('--ca-cert', help="root CA certificate", required=True)
parser.add_argument('--device-cert', help="device certificate", required=True)
parser.add_argument('--device-key', help="device private key file", required=True)
parser.add_argument('--debug', help="enable debug logging", action="store_true")
args = parser.parse_args()

# configure logging
Log.setup()
if args.debug:
	Log.enable_debug()

# initialize the pack module
Pack.setup()

# initialize the database layer
Database.setup(args.database)

# create the uploader
uploader = Uploader(args.host, args.port, args.ca_cert, args.device_key, args.device_cert)

# create the collector
collector = Collector(uploader)

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

Log.info("Starting")

# wait until the database has started before starting the upload + collection
d = Database.start()
def processing_start(result):
	uploader.start()
	collector.start()
d.addCallback(processing_start)

Log.info("Running")

# run the reactor
reactor.run()
