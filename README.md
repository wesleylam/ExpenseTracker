# Expense Tracker for Small Groups 
Simple expense tracker for logging and calculating payments between mulitple parties
- Simply using CSV for DB
- Support multi currency, attachments, etcs

## Requirements
- flask
- flask-bootstrap
- TBD


# Hosting
## How to host (for dev only)?
- `python3 webServer.py`

## How to host (using gunicorn)?
- Require gunicorn installed
- `gunicorn --bind <address>:<port> --certfile=<yourCert> --keyfile=<yourPrivateKey> expenseGunicorn:gapp`

### Commands to generate self-signed cert
Generate a private key without a passphrase
- `openssl genrsa -out private.key 2048`
Create a Certificate Signing Request (CSR)
- `openssl req -new -key private.key -out cert.csr`
Generate the self-signed certificate
- `openssl x509 -req -days 365 -in cert.csr -signkey private.key -out cert.pem`