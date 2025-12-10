#!/usr/bin/env python3
"""
Check Ollama model information including context window size
"""

import sys
import asyncio
import aiohttp
from pathlib import Path

cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from config_loader import get_config_loader

async def get_model_info(server_url: str, model: str):
    """Get model information from Ollama"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(f"{server_url}/api/show", json={"name": model}) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"Error: HTTP {response.status}")
                    return None
    except Exception as e:
        print(f"Error querying model info: {e}")
        return None

async def main():
    config = get_config_loader()
    model = config.get('llm.ollama.model', 'qwen3:8b')
    
    # Get servers from config
    servers = config.get('llm.ollama.servers', [])
    if not servers:
        print("No Ollama servers configured")
        return
    
    print(f"Checking model: {model}\n")
    
    for server_config in servers:
        if not server_config.get('enabled', True):
            continue
        
        server_url = server_config.get('url')
        server_name = server_config.get('name', server_url)
        
        print(f"Server: {server_name} ({server_url})")
        print("-" * 80)
        
        info = await get_model_info(server_url, model)
        if info:
            # Extract context window info
            modelfile = info.get('modelfile', '')
            details = info.get('details', {})
            
            # Look for context window in modelfile or details
            context_window = None
            if 'num_ctx' in modelfile:
                # Extract num_ctx value
                import re
                match = re.search(r'num_ctx\s+(\d+)', modelfile)
                if match:
                    context_window = int(match.group(1))
            
            # Also check details
            if not context_window and 'parameter_size' in details:
                # Try to infer from parameter size or other details
                pass
            
            print(f"Model: {info.get('modelfile', 'N/A')[:100]}...")
            print(f"\nDetails:")
            for key, value in details.items():
                print(f"  {key}: {value}")
            
            if context_window:
                print(f"\n✅ Context Window: {context_window:,} tokens")
            else:
                print(f"\n⚠️  Could not determine context window from model info")
                print(f"   Default for Qwen3-8B: 32,768 tokens (can be extended to 131,072)")
        else:
            print("❌ Failed to get model info")
        
        print()

if __name__ == "__main__":
    asyncio.run(main())

