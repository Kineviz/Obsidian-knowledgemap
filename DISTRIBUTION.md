# Kineviz Obsidian Base - Distribution Guide

This guide explains how to distribute the Kineviz Obsidian Base tool to other users.

## 📦 **Distribution Methods**

### **Method 1: Docker Hub (Recommended)**

1. **Build and push to Docker Hub:**
   ```bash
   # Build the image
   docker build -t yourusername/kineviz-obsidian-base:latest .
   
   # Push to Docker Hub
   docker push yourusername/kineviz-obsidian-base:latest
   ```

2. **Users can run with:**
   ```bash
   docker run -d \
     --name knowledge-map-monitor \
     -p 7001:7001 \
     -v /path/to/vault:/vault:ro \
     -e OPENAI_API_KEY=your_api_key_here \
     yourusername/kineviz-obsidian-base:latest
   ```

### **Method 2: Docker Compose Package**

1. **Create distribution package:**
   ```bash
   # Create distribution directory
   mkdir kineviz-obsidian-base-distribution
   cp docker-compose.yml kineviz-obsidian-base-distribution/
   cp docker.env.example kineviz-obsidian-base-distribution/
   cp DOCKER.md kineviz-obsidian-base-distribution/
   cp Dockerfile kineviz-obsidian-base-distribution/
   cp -r cli/ kineviz-obsidian-base-distribution/
   
   # Create README for users
   cat > kineviz-obsidian-base-distribution/README.md << 'EOF'
   # Kineviz Obsidian Base
   
   ## Quick Start
   
   1. Set up your OpenAI API key:
      ```bash
      export OPENAI_API_KEY=your_api_key_here
      ```
   
   2. Update the vault path in docker-compose.yml
   
   3. Run the container:
      ```bash
      docker-compose up -d
      ```
   
   4. Access the service at http://localhost:7001
   EOF
   
   # Create archive
   tar -czf kineviz-obsidian-base-distribution.tar.gz kineviz-obsidian-base-distribution/
   ```

2. **Users extract and run:**
   ```bash
   tar -xzf kineviz-obsidian-base-distribution.tar.gz
   cd kineviz-obsidian-base-distribution
   export OPENAI_API_KEY=your_api_key_here
   docker-compose up -d
   ```

### **Method 3: Docker Image Export**

1. **Export the image:**
   ```bash
   docker build -t kineviz-obsidian-base:latest .
   docker save kineviz-obsidian-base:latest | gzip > kineviz-obsidian-base.tar.gz
   ```

2. **Users import and run:**
   ```bash
   docker load < kineviz-obsidian-base.tar.gz
   docker run -d \
     --name knowledge-map-monitor \
     -p 7001:7001 \
     -v /path/to/vault:/vault:ro \
     -e OPENAI_API_KEY=your_api_key_here \
     kineviz-obsidian-base:latest
   ```

### **Method 4: Source Code Distribution**

1. **Create source distribution:**
   ```bash
   # Create source package
   tar -czf kineviz-obsidian-base-source.tar.gz \
     --exclude='.git' \
     --exclude='__pycache__' \
     --exclude='*.pyc' \
     --exclude='.env' \
     --exclude='cache' \
     --exclude='logs' \
     --exclude='database' \
     .
   ```

2. **Users build and run:**
   ```bash
   tar -xzf kineviz-obsidian-base-source.tar.gz
   cd knowledge-map-tool
   docker-compose up -d
   ```

## 🔧 **Pre-built Distribution Scripts**

### **Create Distribution Package**
```bash
#!/bin/bash
# create-distribution.sh

VERSION=${1:-latest}
DIST_DIR="kineviz-obsidian-base-${VERSION}"

echo "Creating distribution package: ${DIST_DIR}"

# Create distribution directory
mkdir -p "${DIST_DIR}"

# Copy necessary files
cp docker-compose.yml "${DIST_DIR}/"
cp docker.env.example "${DIST_DIR}/"
cp DOCKER.md "${DIST_DIR}/"
cp Dockerfile "${DIST_DIR}/"

# Create user README
cat > "${DIST_DIR}/README.md" << 'EOF'
# Kineviz Obsidian Base

A Docker-based tool for creating knowledge graphs from Obsidian vaults.

## Quick Start

1. **Set up your OpenAI API key:**
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

2. **Update the vault path in docker-compose.yml:**
   ```yaml
   volumes:
     - /path/to/your/obsidian/vault:/vault:ro
   ```

3. **Run the container:**
   ```bash
   docker-compose up -d
   ```

4. **Access the service:**
   - Web interface: http://localhost:7001
   - API: http://localhost:7001/kuzudb/kuzu_db

## Configuration

See DOCKER.md for detailed configuration options.

## Troubleshooting

Check logs with:
```bash
docker-compose logs -f
```
EOF

# Create archive
tar -czf "${DIST_DIR}.tar.gz" "${DIST_DIR}/"
echo "Distribution package created: ${DIST_DIR}.tar.gz"
```

### **Build and Push to Docker Hub**
```bash
#!/bin/bash
# build-and-push.sh

DOCKER_USERNAME=${1:-yourusername}
VERSION=${2:-latest}
IMAGE_NAME="kineviz-obsidian-base"

echo "Building and pushing to Docker Hub..."

# Build the image
docker build -t "${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}" .

# Push to Docker Hub
docker push "${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "Image pushed: ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo "Users can run with:"
echo "docker run -d --name knowledge-map-monitor -p 7001:7001 -v /path/to/vault:/vault:ro -e OPENAI_API_KEY=your_api_key_here ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
```

## 📋 **Distribution Checklist**

- [ ] Test the Docker image locally
- [ ] Update version numbers
- [ ] Create user documentation
- [ ] Test on different platforms (Linux, macOS, Windows)
- [ ] Provide clear setup instructions
- [ ] Include troubleshooting guide
- [ ] Test with different vault sizes
- [ ] Verify all dependencies are included

## 🔒 **Security Considerations**

- **Never include API keys in the image** - `.env` files are excluded via `.dockerignore`
- Use environment variables for sensitive data
- Provide clear instructions for secure setup
- Consider using Docker secrets for production
- Regularly update base images for security patches
- Test the build to ensure no sensitive data is included

### **Verifying Security**

Before distributing, verify no sensitive data is included:

```bash
# Build the image
docker build -t kineviz-obsidian-base:test .

# Check if .env file is included
docker run --rm kineviz-obsidian-base:test ls -la /app/.env* 2>/dev/null || echo "No .env files found - Good!"

# Check for any API keys in the image
docker run --rm kineviz-obsidian-base:test grep -r "sk-" /app/ 2>/dev/null || echo "No API keys found - Good!"
```
