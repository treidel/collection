ROOT_DIR=/home/ubuntu/src/collection
CERT_DIR=/home/ubuntu
MQTT_HOST=ALZV4L16OIHKX.iot.us-east-1.amazonaws.com
MQTT_PORT=8883
DATABASE=/var/local/samples.db

python $ROOT_DIR/application.py --device ABCD1234 --host $MQTT_HOST --port $MQTT_PORT --ca-cert $CERT_DIR/root.crt --device-cert $CERT_DIR/device.crt --device-key $CERT_DIR/device.key --database $DATABASE
