#!/bin/bash

# Knowledge Graph Rebuild Script
# This script runs the complete knowledge graph rebuild process:
# 1. Run manual trigger to detect changes and process files
# 2. Stop Kuzu server
# 3. Build Kuzu database
# 4. Start Kuzu server

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
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

print_status "Starting knowledge graph rebuild process..."
print_status "Vault path: $VAULT_PATH"
print_status "Server port: $SERVER_PORT"

# Change to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Run manual trigger
print_status "Step 1: Running manual trigger to detect and process changes..."
if uv run manual_trigger.py --vault-path "$VAULT_PATH"; then
    print_success "Manual trigger completed successfully"
else
    print_error "Manual trigger failed"
    exit 1
fi

# Step 2: Stop Kuzu server
print_status "Step 2: Stopping Kuzu server..."
# Kill any existing Kuzu processes
pkill -f "kuzu.*$SERVER_PORT" 2>/dev/null || true
pkill -f "kuzu_neo4j_server" 2>/dev/null || true
sleep 2
print_success "Kuzu server stopped"

# Step 3: Build Kuzu database
print_status "Step 3: Building Kuzu database..."
if uv run build_database_standalone.py --vault-path "$VAULT_PATH" --db-path "$VAULT_PATH/.kineviz_graph/database/knowledge_graph.kz"; then
    print_success "Database built successfully"
else
    print_error "Database build failed"
    exit 1
fi

# Step 4: Start Kuzu server in foreground
print_status "Step 4: Starting Kuzu server on port $SERVER_PORT..."
print_success "Knowledge graph rebuild completed successfully!"
print_status "Starting Kuzu server in foreground..."
print_status "Server URL: http://0.0.0.0:$SERVER_PORT"
print_status "Health check: http://0.0.0.0:$SERVER_PORT/health"
print_status "Press Ctrl+C to stop the server"
print_status ""

# Start the server in the foreground
uv run kuzu_neo4j_server.py "$VAULT_PATH/.kineviz_graph/database/knowledge_graph.kz" --port "$SERVER_PORT"
