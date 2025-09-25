#!/bin/bash

# Start Knowledge Graph Server Script
# This script just starts the Kuzu server in foreground

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

# Check if database exists
DB_PATH="$VAULT_PATH/.kineviz_graph/database/knowledge_graph.kz"
if [ ! -f "$DB_PATH" ]; then
    print_error "Database not found: $DB_PATH"
    print_error "Run update_knowledge_graph.sh or rebuild_knowledge_graph.sh first"
    exit 1
fi

print_status "Starting Kuzu server..."
print_status "Vault path: $VAULT_PATH"
print_status "Server port: $SERVER_PORT"
print_status "Database: $DB_PATH"

# Change to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Kill any existing server first
print_status "Stopping any existing Kuzu server..."
pkill -f "kuzu.*$SERVER_PORT" 2>/dev/null || true
pkill -f "kuzu_neo4j_server" 2>/dev/null || true
sleep 2

print_success "Starting Kuzu server in foreground..."
print_status "Server URL: http://0.0.0.0:$SERVER_PORT"
print_status "Health check: http://0.0.0.0:$SERVER_PORT/health"
print_status "Press Ctrl+C to stop the server"
print_status ""

# Start the server in the foreground
uv run kuzu_neo4j_server.py "$DB_PATH" --port "$SERVER_PORT"
