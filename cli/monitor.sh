#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
print_status() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Default values
DEFAULT_PORT=7001
DEFAULT_MAX_CONCURRENT=5

# Function to show usage
show_usage() {
    echo "Usage: $0 <vault_path> [port] [max_concurrent]"
    echo ""
    echo "Arguments:"
    echo "  vault_path      Path to your Obsidian vault (required)"
    echo "  port            Port for Kuzu server (default: $DEFAULT_PORT)"
    echo "  max_concurrent  Max concurrent file processing tasks (default: $DEFAULT_MAX_CONCURRENT)"
    echo ""
    echo "Examples:"
    echo "  $0 '/Users/username/Documents/Obsidian_root/MyVault'"
    echo "  $0 '/Users/username/Documents/Obsidian_root/MyVault' 7002"
    echo "  $0 '/Users/username/Documents/Obsidian_root/MyVault' 7002 10"
    echo ""
    echo "The monitor will:"
    echo "  - Watch for markdown file changes in your vault"
    echo "  - Automatically process changes using the knowledge graph pipeline"
    echo "  - Run entity resolution and metadata extraction"
    echo "  - Keep the Kuzu database up to date"
    echo "  - Run the Kuzu server for graph queries"
    echo ""
    echo "Press Ctrl+C to stop the monitor"
}

# Check if help is requested
if [[ "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]]; then
    show_usage
    exit 0
fi

# Check if vault path is provided
if [ $# -lt 1 ]; then
    print_error "Vault path is required"
    echo ""
    show_usage
    exit 1
fi

# Get arguments
VAULT_PATH="$1"
SERVER_PORT="${2:-$DEFAULT_PORT}"
MAX_CONCURRENT="${3:-$DEFAULT_MAX_CONCURRENT}"

# Validate vault path
if [ ! -d "$VAULT_PATH" ]; then
    print_error "Vault path does not exist: $VAULT_PATH"
    exit 1
fi

# Check if it looks like an Obsidian vault
if [ ! -d "$VAULT_PATH/.obsidian" ]; then
    print_warning "$VAULT_PATH doesn't appear to be an Obsidian vault (no .obsidian directory)"
    print_warning "Continuing anyway..."
fi

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status "Starting Knowledge Graph Monitor..."
print_status "Vault path: $VAULT_PATH"
print_status "Server port: $SERVER_PORT"
print_status "Max concurrent: $MAX_CONCURRENT"
print_status ""

# Check if required files exist
if [ ! -f "step4_monitor.py" ]; then
    print_error "step4_monitor.py not found in current directory"
    exit 1
fi

if [ ! -f "manual_trigger.py" ]; then
    print_error "manual_trigger.py not found in current directory"
    exit 1
fi

# Check if uv is available
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed or not in PATH"
    print_error "Please install uv: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Start the monitor
print_status "Starting file monitor..."
print_status "The monitor will watch for markdown file changes and automatically update the knowledge graph"
print_status "Press Ctrl+C to stop the monitor"
print_status ""

# Run the monitor
uv run step4_monitor.py \
    --vault-path "$VAULT_PATH" \
    --server-port "$SERVER_PORT" \
    --max-concurrent "$MAX_CONCURRENT"

print_success "Monitor stopped"
