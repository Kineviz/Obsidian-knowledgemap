#!/bin/bash
# create-distribution.sh - Create a distribution package for the Knowledge Map Tool

VERSION=${1:-latest}
DIST_DIR="kineviz-obsidian-base-${VERSION}"

echo "Creating distribution package: ${DIST_DIR}"

# Create distribution directory
mkdir -p "${DIST_DIR}"

# Copy necessary files
cp docker-compose.yml "${DIST_DIR}/"
cp docker.env.example "${DIST_DIR}/"
cp docker-manage.sh "${DIST_DIR}/"
cp DOCKER.md "${DIST_DIR}/"
cp Dockerfile "${DIST_DIR}/"

# Copy the cli directory (source code) maintaining structure, excluding sensitive files
rsync -av --exclude='.venv' --exclude='.env' --exclude='cache' --exclude='logs' --exclude='database' --exclude='*.kz' --exclude='__pycache__' --exclude='*.pyc' cli/ "${DIST_DIR}/cli/"

# Create user README
cat > "${DIST_DIR}/README.md" << 'EOF'
# Kineviz Obsidian Base

A Docker-based tool for creating knowledge graphs from Obsidian vaults.

## Quick Start

### Using Docker Management Script (Recommended)

1. **Set up environment variables:**
   ```bash
   # Create a .env file from the example
   cp docker.env.example .env
   # Edit .env with your actual values:
   # - OPENAI_API_KEY=your_api_key_here
   # - VAULT_PATH=/path/to/your/obsidian/vault
   # - SERVER_PORT=7001
   # - MAX_CONCURRENT=5
   ```

2. **Use the management script:**
   ```bash
   # Start with automatic cleanup and rebuild
   ./docker-manage.sh start
   
   # Or restart if already running
   ./docker-manage.sh restart
   
   # View logs
   ./docker-manage.sh logs
   
   # Check status
   ./docker-manage.sh status
   
   # Clean everything
   ./docker-manage.sh clean
   ```

### Using Docker Compose (Manual)

1. **Set up environment variables** (same as above)

2. **Run the container:**
   ```bash
   docker-compose up -d
   ```

3. **Access the service:**
   - Web interface: http://localhost:7001
   - API: http://localhost:7001/kuzudb/kuzu_db

## Configuration

See DOCKER.md for detailed configuration options.

## Troubleshooting

Check logs with:
```bash
./docker-manage.sh logs
# or
docker-compose logs -f
```
EOF

# Create archive
tar -czf "${DIST_DIR}.tar.gz" "${DIST_DIR}/"
echo "Distribution package created: ${DIST_DIR}.tar.gz"
echo "You can now distribute this file to users."
