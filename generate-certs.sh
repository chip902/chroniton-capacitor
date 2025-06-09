#!/bin/bash

# Generate self-signed SSL certificates for local development
mkdir -p certs

# Generate private key
openssl genpkey -algorithm RSA -out certs/server.key -pkcs8 -v -aes256

# Generate certificate signing request
openssl req -new -key certs/server.key -out certs/server.csr -subj "/C=US/ST=Dev/L=Dev/O=Dev/CN=localhost"

# Generate self-signed certificate valid for 365 days
openssl x509 -req -in certs/server.csr -signkey certs/server.key -out certs/server.crt -days 365

# Remove CSR file
rm certs/server.csr

echo "SSL certificates generated in ./certs/"
echo "server.crt - Certificate file"
echo "server.key - Private key file"
echo ""
echo "To use HTTPS:"
echo "1. Run: docker-compose -f docker-compose.https.yml up"
echo "2. Access your app at: https://localhost:8443"
echo "3. Accept the self-signed certificate warning in your browser"