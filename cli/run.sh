#!/bin/bash
# Knowledge Map Tool - Simplified runner
# This script provides easy access to all knowledge map tool functions

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

# Function to show usage
show_usage() {
    echo "Knowledge Map Tool - Usage"
    echo ""
    echo "Commands:"
    echo "  monitor <vault_path> [port]     Start file monitoring (recommended)"
    echo "  update <vault_path> [port]      Run one-time update"
    echo "  rebuild <vault_path> [port]     Full rebuild from scratch"
    echo "  server <vault_path> [port]      Start Kuzu server only"
    echo "  help                           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 monitor '/Users/username/Documents/Obsidian_root/MyVault'"
    echo "  $0 update '/Users/username/Documents/Obsidian_root/MyVault' 7002"
    echo "  $0 rebuild '/Users/username/Documents/Obsidian_root/MyVault'"
    echo "  $0 server '/Users/username/Documents/Obsidian_root/MyVault' 7001"
    echo ""
    echo "For more detailed help on any command, run:"
    echo "  ./monitor.sh --help"
    echo "  ./update_knowledge_graph.sh --help"
    echo "  ./rebuild_knowledge_graph.sh --help"
    echo "  ./start_server.sh --help"
}

# Check if command is provided
if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    "monitor")
        if [ $# -eq 0 ]; then
            print_error "Vault path is required for monitor command"
            echo "Usage: $0 monitor <vault_path> [port]"
            exit 1
        fi
        print_status "Starting file monitor..."
        ./monitor.sh "$@"
        ;;
    "update")
        if [ $# -eq 0 ]; then
            print_error "Vault path is required for update command"
            echo "Usage: $0 update <vault_path> [port]"
            exit 1
        fi
        print_status "Running one-time update..."
        ./update_knowledge_graph.sh "$@"
        ;;
    "rebuild")
        if [ $# -eq 0 ]; then
            print_error "Vault path is required for rebuild command"
            echo "Usage: $0 rebuild <vault_path> [port]"
            exit 1
        fi
        print_status "Running full rebuild..."
        ./rebuild_knowledge_graph.sh "$@"
        ;;
    "server")
        if [ $# -eq 0 ]; then
            print_error "Vault path is required for server command"
            echo "Usage: $0 server <vault_path> [port]"
            exit 1
        fi
        print_status "Starting Kuzu server..."
        ./start_server.sh "$@"
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
