#!/bin/bash

# Knowledge Graph Update Script
# This script runs the manual trigger (which handles everything) and starts the server
# 1. Run manual trigger (detects changes, processes files, builds database)
# 2. Start Kuzu server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if vault path is provided
if [ $# -eq 0 ]; then
    print_error "Usage: $0 <vault_path> [server_port]"
    print_error "Example: $0 '/Users/username/Documents/Obsidian_root/test' 7001"
    exit 1
fi

VAULT_PATH="$1"
SERVER_PORT="${2:-7001}"

# Validate vault path
if [ ! -d "$VAULT_PATH" ]; then
    print_error "Vault path does not exist: $VAULT_PATH"
    exit 1
fi

print_status "Starting knowledge graph update process..."
print_status "Vault path: $VAULT_PATH"
print_status "Server port: $SERVER_PORT"

# Change to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Run manual trigger (handles everything)
print_status "Step 1: Running manual trigger to detect changes, process files, and build database..."
if uv run manual_trigger.py --vault-path "$VAULT_PATH"; then
    print_success "Manual trigger completed successfully"
else
    print_error "Manual trigger failed"
    exit 1
fi

# Step 2: Start Kuzu server in foreground
print_status "Step 2: Starting Kuzu server on port $SERVER_PORT..."
# Kill any existing server first
pkill -f "kuzu.*$SERVER_PORT" 2>/dev/null || true
pkill -f "kuzu_neo4j_server" 2>/dev/null || true
sleep 2

print_success "Knowledge graph update completed successfully!"
print_status "Starting Kuzu server in foreground..."
print_status "Server URL: http://0.0.0.0:$SERVER_PORT"
print_status "Health check: http://0.0.0.0:$SERVER_PORT/health"
print_status "Press Ctrl+C to stop the server"
print_status ""

# Start the server in the foreground
uv run kuzu_neo4j_server.py "$VAULT_PATH/.kineviz_graph/database/knowledge_graph.kz" --port "$SERVER_PORT"
