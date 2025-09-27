#!/usr/bin/env python3
"""Test configuration loading"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))
from llm_config_loader import get_config_loader

def test_config():
    config_loader = get_config_loader()
    config = config_loader.get_config()
    
    print(f"Provider: {config.provider}")
    print(f"Cloud config: {config.cloud}")
    print(f"Ollama config: {config.ollama}")
    
    if config.ollama:
        print(f"Ollama servers: {len(config.ollama.servers)}")
        for server in config.ollama.servers:
            print(f"  - {server.name}: {server.url} (enabled: {server.enabled})")

if __name__ == "__main__":
    test_config()
