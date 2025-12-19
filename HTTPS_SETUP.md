# HTTPS Setup for Kuzu Server

The Kuzu server can run with HTTPS for secure connections from GraphXR web applications.

## Quick Start

### 1. Generate SSL Certificates

Run the certificate generation script:

```bash
cd cli
./generate_ssl_cert.sh
```

This will create self-signed certificates in `cli/ssl_certs/`:
- `cert.pem` - SSL certificate
- `key.pem` - Private key

### 2. Start the Server

The monitor will automatically detect and use the SSL certificates:

```bash
uv run step4_monitor.py
```

If certificates are found, you'll see:
```
✓ SSL certificates found - enabling HTTPS
Starting Kuzu server on https://0.0.0.0:8443
```

**Note**: The server automatically uses **port 8443** for HTTPS (standard alternative HTTPS port), and port 7001 for HTTP.

### 3. Access from GraphXR

The server is now accessible via HTTPS from:
- https://graphxr.kineviz.com
- https://dev.graphxr.kineviz.com
- https://staging.graphxr.kineviz.com

**Connection URL**: `https://localhost:8443/kuzudb/kuzu_db`

## Manual SSL Configuration

You can also run the Kuzu server directly with custom certificates:

```bash
# Server will automatically use port 8443 for HTTPS
uv run kuzu_server.py /path/to/database \
  --ssl-cert /path/to/cert.pem \
  --ssl-key /path/to/key.pem

# Or specify a custom port
uv run kuzu_server.py /path/to/database \
  --ssl-cert /path/to/cert.pem \
  --ssl-key /path/to/key.pem \
  --port 9443
```

## Self-Signed Certificate Warning

Since these are self-signed certificates, you may see browser warnings when accessing the server locally. This is expected for development.

### Accepting the Certificate in Your Browser

1. Navigate to `https://localhost:8443/health` in your browser
2. Click "Advanced" or "Show Details"
3. Click "Proceed to localhost (unsafe)" or similar option
4. The certificate will be accepted for future visits

## CORS Configuration

The server allows requests from the following origins:
- `https://graphxr.kineviz.com`
- `https://dev.graphxr.kineviz.com`
- `https://staging.graphxr.kineviz.com`
- `http://localhost:3000` (local development)
- `http://localhost:8080` (alternative local port)

The server also includes `Access-Control-Allow-Private-Network: true` header for accessing private network resources from public web applications.

## Production Certificates

For production use, replace the self-signed certificates with proper SSL certificates from a Certificate Authority (CA) like:
- Let's Encrypt (free)
- DigiCert
- Comodo
- etc.

Place your production certificates in `cli/ssl_certs/` with the same names (`cert.pem` and `key.pem`), and the server will automatically use them.

## Troubleshooting

### Port 8443 is in use

If port 8443 is already in use, stop the existing server:
```bash
# Find the process
lsof -i :8443

# Kill it
kill <PID>
```

Or specify a different port when starting the server:
```bash
uv run kuzu_server.py /path/to/database \
  --ssl-cert ssl_certs/cert.pem \
  --ssl-key ssl_certs/key.pem \
  --port 9443
```

### SSL Certificate Errors / ERR_CERT_AUTHORITY_INVALID

If you get `ERR_CERT_AUTHORITY_INVALID` or similar certificate errors:

**Quick Fix - Accept in Browser:**
1. Open a new browser tab: `https://localhost:8443/health`
2. Click "Advanced" or "Show Details"
3. Click "Proceed to localhost (unsafe)"
4. Return to GraphXR and try connecting again

**Better Fix - Trust Certificate System-Wide (macOS):**
```bash
cd cli
./trust_certificate.sh
```
This adds the certificate to your system keychain. You'll need to restart your browser afterward.

**Simple Fix - Use HTTP Instead:**
If you don't need HTTPS for local development:
```bash
cd cli
rm -rf ssl_certs  # Remove certificates
# Restart server - it will use HTTP on port 7001
```

**Regenerate Certificates:**
If certificates are corrupted:
```bash
cd cli
rm -rf ssl_certs
./generate_ssl_cert.sh
```

### Server not starting

Check the logs:
```bash
tail -f cli/logs/kuzu_server.log
```
