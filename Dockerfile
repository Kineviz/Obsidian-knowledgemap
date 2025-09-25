# Use Python 3.13 slim image as base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

# Copy project files
COPY cli/ /app/

# Note: .env files are excluded via .dockerignore for security

# Install Python dependencies using uv
RUN uv sync --frozen

# Create directories for cache and database
RUN mkdir -p /app/cache/content /app/cache/db_input /app/logs

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Default values\n\
VAULT_PATH=${VAULT_PATH:-"/vault"}\n\
SERVER_PORT=${SERVER_PORT:-7001}\n\
MAX_CONCURRENT=${MAX_CONCURRENT:-5}\n\
\n\
# Check if vault path is provided\n\
if [ -z "$VAULT_PATH" ]; then\n\
    echo "Error: VAULT_PATH environment variable is required"\n\
    echo "Usage: docker run -e VAULT_PATH=/path/to/vault -e SERVER_PORT=7001 your-image"\n\
    exit 1\n\
fi\n\
\n\
# Check if vault path exists\n\
if [ ! -d "$VAULT_PATH" ]; then\n\
    echo "Error: Vault path does not exist: $VAULT_PATH"\n\
    echo "Make sure to mount your vault directory as a volume"\n\
    exit 1\n\
fi\n\
\n\
echo "Starting knowledge map monitor..."\n\
echo "Vault path: $VAULT_PATH"\n\
echo "Server port: $SERVER_PORT"\n\
echo "Max concurrent: $MAX_CONCURRENT"\n\
\n\
# Run the monitor\n\
exec uv run step4_monitor.py --vault-path "$VAULT_PATH" --server-port "$SERVER_PORT" --max-concurrent "$MAX_CONCURRENT"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose the server port
EXPOSE 7001

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
