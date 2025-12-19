#!/bin/bash
# Test if the Kuzu server is returning proper CORS headers

echo "Testing CORS headers from graphxr.kineviz.com..."
echo "================================================"
echo ""

echo "1. Testing OPTIONS preflight (with private network request):"
curl -k -X OPTIONS https://localhost:8443/kuzudb/kuzu_db \
  -H "Origin: https://graphxr.kineviz.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" \
  -H "Access-Control-Request-Private-Network: true" \
  -v 2>&1 | grep -i "access-control"

echo ""
echo "2. Testing actual POST request:"
curl -k -X POST https://localhost:8443/kuzudb/kuzu_db \
  -H "Origin: https://graphxr.kineviz.com" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (n) RETURN count(n) LIMIT 1"}' \
  -v 2>&1 | grep -i "access-control"

echo ""
echo "3. Testing from staging.graphxr.kineviz.com:"
curl -k -X OPTIONS https://localhost:8443/kuzudb/kuzu_db \
  -H "Origin: https://staging.graphxr.kineviz.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Private-Network: true" \
  -v 2>&1 | grep -i "access-control"

echo ""
echo "✓ Test complete"
