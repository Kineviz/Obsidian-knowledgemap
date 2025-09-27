#!/usr/bin/env python3
"""
Test script for LLM Client with Load Balancing and Failover
"""

import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))
from llm_client import get_llm_client, close_llm_client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

async def test_llm_client():
    """Test the LLM client functionality"""
    console.print("[bold blue]Testing LLM Client with Load Balancing and Failover[/bold blue]")
    
    # Get LLM client
    client = await get_llm_client()
    
    # Test server status
    console.print("\n[cyan]Server Status:[/cyan]")
    status = await client.get_server_status()
    console.print(json.dumps(status, indent=2))
    
    # Test message
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that extracts relationships from text."
        },
        {
            "role": "user", 
            "content": "John works at Microsoft. He is married to Sarah."
        }
    ]
    
    console.print("\n[cyan]Testing LLM Generation:[/cyan]")
    console.print(f"Messages: {json.dumps(messages, indent=2)}")
    
    # Test multiple requests to see load balancing
    console.print("\n[cyan]Testing Load Balancing (5 requests):[/cyan]")
    
    results = []
    for i in range(5):
        console.print(f"\n[yellow]Request {i+1}:[/yellow]")
        response = await client.generate(messages)
        
        if response.success:
            console.print(f"✅ Success: {response.content[:100]}...")
            console.print(f"   Model: {response.model}")
            console.print(f"   Provider: {response.provider}")
            console.print(f"   Server: {response.server_url or 'N/A'}")
            console.print(f"   Response Time: {response.response_time:.2f}s")
            console.print(f"   Tokens: {response.token_count or 'N/A'}")
        else:
            console.print(f"❌ Failed: {response.error}")
        
        results.append(response)
    
    # Show load balancing results
    console.print("\n[cyan]Load Balancing Results:[/cyan]")
    server_usage = {}
    for result in results:
        if result.success and result.server_url:
            server_usage[result.server_url] = server_usage.get(result.server_url, 0) + 1
    
    table = Table(title="Server Usage")
    table.add_column("Server", style="cyan")
    table.add_column("Requests", style="magenta")
    
    for server, count in server_usage.items():
        table.add_row(server, str(count))
    
    console.print(table)
    
    # Test failover by simulating server failure
    console.print("\n[cyan]Testing Failover (simulating server failure):[/cyan]")
    
    # Mark some servers as unhealthy (simulation)
    if hasattr(client, 'ollama_servers') and client.ollama_servers:
        # Mark first server as unhealthy
        client.ollama_servers[0].is_healthy = False
        console.print(f"Marked {client.ollama_servers[0].url} as unhealthy")
    
    # Test with remaining healthy servers
    response = await client.generate(messages)
    if response.success:
        console.print(f"✅ Failover Success: {response.content[:100]}...")
        console.print(f"   Used server: {response.server_url}")
    else:
        console.print(f"❌ Failover Failed: {response.error}")
    
    # Restore server health
    if hasattr(client, 'ollama_servers') and client.ollama_servers:
        client.ollama_servers[0].is_healthy = True
        console.print(f"Restored {client.ollama_servers[0].url} to healthy")
    
    # Final status
    console.print("\n[cyan]Final Server Status:[/cyan]")
    final_status = await client.get_server_status()
    console.print(json.dumps(final_status, indent=2))
    
    # Close client
    await close_llm_client()
    console.print("\n[green]✅ LLM Client test completed![/green]")

if __name__ == "__main__":
    asyncio.run(test_llm_client())
