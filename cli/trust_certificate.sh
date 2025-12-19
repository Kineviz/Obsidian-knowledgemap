#!/bin/bash
# Trust the self-signed certificate system-wide on macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_FILE="$SCRIPT_DIR/ssl_certs/cert.pem"

if [ ! -f "$CERT_FILE" ]; then
    echo "❌ Certificate not found at: $CERT_FILE"
    echo "Run ./generate_ssl_cert.sh first"
    exit 1
fi

echo "Adding certificate to macOS Keychain..."
echo "You may be prompted for your password."
echo ""

# Add certificate to keychain and trust it
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CERT_FILE"

echo ""
echo "✅ Certificate has been added to the system keychain and trusted!"
echo ""
echo "Restart your browser for the changes to take effect."
echo ""
echo "To remove the certificate later:"
echo "  1. Open 'Keychain Access' app"
echo "  2. Select 'System' keychain"
echo "  3. Search for 'localhost'"
echo "  4. Delete the certificate"
echo ""
