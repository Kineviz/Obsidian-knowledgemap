#!/bin/bash
# Test script for image serving functionality

set -e

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}=== Testing Image Serving Functionality ===${NC}\n"

# Check if vault path is provided
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage: $0 <vault_path>${NC}"
    echo -e "${YELLOW}Example: $0 /path/to/obsidian/vault${NC}"
    exit 1
fi

VAULT_PATH="$1"
SERVER_PORT="${2:-7001}"
DB_PATH="$VAULT_PATH/.kineviz_graph/database/knowledge_graph.kz"

# Validate paths
if [ ! -d "$VAULT_PATH" ]; then
    echo "Error: Vault path does not exist: $VAULT_PATH"
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    echo "Warning: Database not found: $DB_PATH"
    echo "You may need to build the database first."
fi

echo -e "${CYAN}1. Testing markdown transformer...${NC}"
cd "$(dirname "$0")"
python markdown_transformer.py

echo -e "\n${GREEN}✓ Markdown transformer test passed${NC}\n"

echo -e "${CYAN}2. Server startup command:${NC}"
echo -e "${YELLOW}python kuzu_server.py '$DB_PATH' --port $SERVER_PORT --vault-path '$VAULT_PATH'${NC}\n"

echo -e "${CYAN}3. To test the image endpoint after starting the server:${NC}"
echo -e "${YELLOW}# List images in your vault:${NC}"
echo -e "find '$VAULT_PATH' -type f \\( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' \\) | head -5"
echo ""
echo -e "${YELLOW}# Test accessing an image (replace with actual path):${NC}"
echo -e "curl -I http://localhost:$SERVER_PORT/images/path/to/your/image.png"
echo ""

echo -e "${CYAN}4. To test markdown transformation endpoint:${NC}"
echo -e "${YELLOW}curl -X POST http://localhost:$SERVER_PORT/transform_markdown \\${NC}"
echo -e "${YELLOW}  -H 'Content-Type: application/json' \\${NC}"
echo -e "${YELLOW}  -d '{\"content\": \"# Test\\n![[image.png]]\", \"server_url\": \"http://localhost:$SERVER_PORT\"}'${NC}"
echo ""

echo -e "${GREEN}=== Test Setup Complete ===${NC}"
echo -e "${CYAN}Start the server with the command shown above to enable image serving.${NC}"







