CERT_DIR=/home/ubuntu
COLLECT_URL=https://54.86.219.87:8443/device/records
DATABASE=/var/local/samples.db
PYTHONPATH=debug
export PYTHONPATH

pdb application.py --url $COLLECT_URL --ca-cert $CERT_DIR/root.crt --device-cert $CERT_DIR/5ANDQKTRPF.crt --device-key $CERT_DIR/5ANDQKTRPF.key --database $DATABASE 
