#!/bin/bash
# Docker management script for Knowledge Map Tool

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
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

# Function to check if .env file exists
check_env_file() {
    if [ ! -f ".env" ]; then
        print_error ".env file not found!"
        print_status "Creating .env file from docker.env.example..."
        cp docker.env.example .env
        print_warning "Please edit .env file with your actual values before running again"
        exit 1
    fi
    print_success ".env file found"
}

# Function to load environment variables
load_env() {
    print_status "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
    print_success "Environment variables loaded"
    print_status "VAULT_PATH: ${VAULT_PATH}"
    print_status "SERVER_PORT: ${SERVER_PORT}"
    print_status "MAX_CONCURRENT: ${MAX_CONCURRENT}"
}

# Function to stop and remove containers
cleanup_containers() {
    print_status "Stopping and removing existing containers..."
    
    # Stop containers
    if docker-compose ps -q | grep -q .; then
        print_status "Stopping containers..."
        docker-compose down
    else
        print_status "No running containers found"
    fi
    
    # Remove the specific container if it exists
    if docker ps -a --format "table {{.Names}}" | grep -q "knowledge-map-monitor"; then
        print_status "Removing knowledge-map-monitor container..."
        docker rm -f knowledge-map-monitor
    fi
    
    print_success "Container cleanup completed"
}

# Function to build and start
build_and_start() {
    print_status "Building and starting containers..."
    docker-compose up --build -d
    print_success "Containers started successfully"
}

# Function to show logs
show_logs() {
    print_status "Showing container logs..."
    docker-compose logs -f
}

# Function to show status
show_status() {
    print_status "Container status:"
    docker-compose ps
}

# Function to show help
show_help() {
    echo "Docker Management Script for Knowledge Map Tool"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     - Start containers (with cleanup and rebuild)"
    echo "  stop      - Stop containers"
    echo "  restart   - Restart containers (with cleanup and rebuild)"
    echo "  logs      - Show container logs"
    echo "  status    - Show container status"
    echo "  clean     - Clean up containers and volumes"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start    # Start with cleanup and rebuild"
    echo "  $0 restart  # Restart with cleanup and rebuild"
    echo "  $0 logs     # Follow logs"
    echo "  $0 clean    # Clean everything"
}

# Main script logic
case "${1:-start}" in
    start)
        print_status "Starting Knowledge Map Tool..."
        check_env_file
        load_env
        cleanup_containers
        build_and_start
        print_success "Knowledge Map Tool started successfully!"
        print_status "Access the API at: http://localhost:${SERVER_PORT:-7001}"
        print_status "Run '$0 logs' to see logs"
        ;;
    stop)
        print_status "Stopping Knowledge Map Tool..."
        cleanup_containers
        print_success "Knowledge Map Tool stopped"
        ;;
    restart)
        print_status "Restarting Knowledge Map Tool..."
        check_env_file
        load_env
        cleanup_containers
        build_and_start
        print_success "Knowledge Map Tool restarted successfully!"
        print_status "Access the API at: http://localhost:${SERVER_PORT:-7001}"
        print_status "Run '$0 logs' to see logs"
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    clean)
        print_status "Cleaning up containers and volumes..."
        cleanup_containers
        print_status "Removing volumes..."
        docker-compose down -v 2>/dev/null || true
        print_status "Removing images..."
        docker rmi $(docker images "kineviz-obsidian-base*" -q) 2>/dev/null || true
        print_success "Cleanup completed"
        ;;
    help)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
