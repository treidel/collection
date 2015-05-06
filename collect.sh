ROOT_DIR=/home/ubuntu/src/collection
CERT_DIR=/home/ubuntu
COLLECT_URL=https://54.86.219.87:8443/device/records
DATABASE=/var/local/samples.db

python $ROOT_DIR/application.py --url $COLLECT_URL --ca-cert $CERT_DIR/root.crt --device-cert $CERT_DIR/device.crt --device-key $CERT_DIR/device.key --database $DATABASE
