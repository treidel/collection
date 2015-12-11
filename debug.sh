CERT_DIR=/home/ubuntu
MQTT_HOST=ALZV4L16OIHKX.iot.us-east-1.amazonaws.com
MQTT_PORT=8883
DATABASE=/home/ubuntu/src/collection/samples.db
PYTHONPATH=~/src/AutobahnPython/autobahn:debug
export PYTHONPATH

pdb application.py --device ABCD1234 --host $MQTT_HOST --port $MQTT_PORT --ca-cert $CERT_DIR/rootCA.pem.crt --device-cert $CERT_DIR/dd38b4c1a4-certificate.pem.crt --device-key $CERT_DIR/dd38b4c1a4-private.pem.key  --database $DATABASE 
