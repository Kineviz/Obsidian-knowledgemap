#!/bin/bash
# Generate self-signed SSL certificate for local HTTPS server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SCRIPT_DIR/ssl_certs"

# Create ssl_certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

echo "Generating self-signed SSL certificate for localhost..."
echo ""

# Generate private key and certificate
openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1"

echo ""
echo "✅ SSL certificates generated successfully!"
echo ""
echo "Certificate: $CERT_DIR/cert.pem"
echo "Private Key: $CERT_DIR/key.pem"
echo ""
echo "To run the Kuzu server with HTTPS:"
echo "  uv run kuzu_server.py /path/to/database \\"
echo "    --ssl-cert $CERT_DIR/cert.pem \\"
echo "    --ssl-key $CERT_DIR/key.pem"
echo ""
echo "⚠️  Note: This is a self-signed certificate for development only."
echo "    Your browser will show a security warning. You'll need to accept it."
echo ""
