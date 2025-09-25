# Docker Setup for Knowledge Map Tool

This document explains how to run the knowledge map tool using Docker containers.

## Quick Start

### Using Docker Management Script (Recommended)

1. **Set up environment variables**:
   ```bash
   # Create a .env file from the example
   cp docker.env.example .env
   # Edit .env with your actual values:
   # - OPENAI_API_KEY=your_api_key_here
   # - VAULT_PATH=/path/to/your/obsidian/vault
   # - SERVER_PORT=7001
   # - MAX_CONCURRENT=5
   ```

2. **Use the management script**:
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

2. **Run the container**:
   ```bash
   docker-compose up -d
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

5. **Stop the container**:
   ```bash
   docker-compose down
   ```

### Using Docker directly

1. **Build the image**:
   ```bash
   docker build -t knowledge-map-tool .
   ```

2. **Run the container**:
   ```bash
   docker run -d \
     --name knowledge-map-monitor \
     -p 7001:7001 \
     -v /path/to/your/obsidian/vault:/vault:ro \
     -v knowledge-map-cache:/app/cache \
     -e VAULT_PATH=/vault \
     -e SERVER_PORT=7001 \
     -e OPENAI_API_KEY=your_api_key_here \
     knowledge-map-tool
   ```

## Configuration

### Environment Variables

- `VAULT_PATH`: Path to your Obsidian vault (default: `/vault`)
- `SERVER_PORT`: Port for the Kuzu Neo4j server (default: `7001`)
- `MAX_CONCURRENT`: Maximum concurrent file processing tasks (default: `5`)
- `OPENAI_API_KEY`: OpenAI API key for entity extraction (required)

### Volume Mounts

- **Vault Directory**: Mount your Obsidian vault as read-only (`/vault:ro`)
- **Cache Directory**: Persistent storage for processed data (`/app/cache`)
- **Logs Directory**: Application logs (`/app/logs`)

## Setting up OpenAI API Key

The knowledge map tool requires an OpenAI API key for entity extraction. Here are the different ways to provide it:

### Method 1: Environment Variable (Recommended)
```bash
export OPENAI_API_KEY=your_api_key_here
docker-compose up -d
```

### Method 2: .env File
```bash
# Create .env file
echo "OPENAI_API_KEY=your_api_key_here" > .env
docker-compose up -d
```

### Method 3: Docker Run with -e flag
```bash
docker run -d \
  --name knowledge-map-monitor \
  -p 7001:7001 \
  -v /path/to/vault:/vault:ro \
  -e OPENAI_API_KEY=your_api_key_here \
  knowledge-map-tool
```

### Method 4: .env file in cli/ directory
If you have a `.env` file in the `cli/` directory, it will be automatically copied into the container.

## Examples

### Custom Port

```bash
docker run -d \
  --name knowledge-map-monitor \
  -p 8080:8080 \
  -v /path/to/vault:/vault:ro \
  -e VAULT_PATH=/vault \
  -e SERVER_PORT=8080 \
  knowledge-map-tool
```

### Custom Vault Path

```bash
docker run -d \
  --name knowledge-map-monitor \
  -p 7001:7001 \
  -v /Users/username/Documents/MyVault:/my-vault:ro \
  -e VAULT_PATH=/my-vault \
  -e SERVER_PORT=7001 \
  knowledge-map-tool
```

## Accessing the Service

Once running, the Kuzu Neo4j server will be available at:
- **HTTP**: `http://localhost:7001`
- **Web Interface**: `http://localhost:7001` (if available)

## Troubleshooting

### Check Container Status
```bash
docker ps
```

### View Logs
```bash
docker logs knowledge-map-monitor
```

### Access Container Shell
```bash
docker exec -it knowledge-map-monitor /bin/bash
```

### Common Issues

1. **Permission Denied**: Ensure the vault directory is readable by the container
2. **Port Already in Use**: Change the `SERVER_PORT` environment variable
3. **Vault Not Found**: Verify the vault path is correctly mounted

## Development

### Building for Development
```bash
docker build -t knowledge-map-tool:dev .
```

### Running with Live Reload
```bash
docker run -it \
  --name knowledge-map-dev \
  -p 7001:7001 \
  -v /path/to/vault:/vault:ro \
  -v $(pwd)/cli:/app \
  -e VAULT_PATH=/vault \
  knowledge-map-tool:dev
```

## Production Considerations

1. **Resource Limits**: Add memory and CPU limits in production
2. **Health Checks**: The container includes health checks for monitoring
3. **Logging**: Configure log rotation and centralized logging
4. **Backup**: Regularly backup the cache volume
5. **Security**: Run as non-root user in production environments
