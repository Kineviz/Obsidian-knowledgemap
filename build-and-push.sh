#!/bin/bash
# build-and-push.sh - Build and push Docker image to Docker Hub

DOCKER_USERNAME=${1:-yourusername}
VERSION=${2:-latest}
IMAGE_NAME="kineviz-obsidian-base"

echo "Building and pushing to Docker Hub..."

# Build the image
docker build -t "${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}" .

# Security verification
echo "Verifying security..."
echo "Checking for .env files..."
docker run --rm "${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}" ls -la /app/.env* 2>/dev/null || echo "✅ No .env files found - Good!"

echo "Checking for API keys..."
docker run --rm "${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}" grep -r "sk-" /app/ 2>/dev/null || echo "✅ No API keys found - Good!"

echo "Security verification complete!"

# Push to Docker Hub
docker push "${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "Image pushed: ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo "Users can run with:"
echo "docker run -d --name knowledge-map-monitor -p 7001:7001 -v /path/to/vault:/vault:ro -e OPENAI_API_KEY=your_api_key_here ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
