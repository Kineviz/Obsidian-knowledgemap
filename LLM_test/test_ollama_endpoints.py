#!/usr/bin/env python3
"""
Test Ollama endpoints availability
"""

import asyncio
import aiohttp
from rich.console import Console
from rich.table import Table

console = Console()

async def test_ollama_endpoint(endpoint: str, model: str = "gemma3:4b") -> dict:
    """Test if an Ollama endpoint is accessible"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            # Test with a simple request
            payload = {
                "model": model,
                "prompt": "Hello, are you working?",
                "stream": False
            }
            
            async with session.post(f"{endpoint}/api/generate", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "status": "✅ Available",
                        "response_time": "N/A",
                        "model_loaded": model in str(result.get("response", "")),
                        "error": None
                    }
                else:
                    return {
                        "status": f"❌ HTTP {response.status}",
                        "response_time": "N/A", 
                        "model_loaded": False,
                        "error": f"HTTP {response.status}"
                    }
    except asyncio.TimeoutError:
        return {
            "status": "❌ Timeout",
            "response_time": "N/A",
            "model_loaded": False,
            "error": "Connection timeout"
        }
    except Exception as e:
        return {
            "status": "❌ Error",
            "response_time": "N/A",
            "model_loaded": False,
            "error": str(e)
        }

async def main():
    """Test all Ollama endpoints"""
    console.print("[bold blue]Testing Ollama Endpoints[/bold blue]\n")
    
    endpoints = [
        ("bsrs-mac-studio", "http://bsrs-mac-studio:11434"),
        ("localhost", "http://localhost:11434"),
        ("wei-m1max", "http://wei-m1max:11434"),
        ("weidongs-mac-studio", "http://weidongs-mac-studio:11434"),
    ]
    
    table = Table(title="Ollama Endpoint Status")
    table.add_column("Endpoint", style="cyan")
    table.add_column("URL", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Model Loaded", style="yellow")
    table.add_column("Error", style="red")
    
    for name, url in endpoints:
        console.print(f"Testing {name}...")
        result = await test_ollama_endpoint(url)
        
        table.add_row(
            name,
            url,
            result["status"],
            "✅ Yes" if result["model_loaded"] else "❌ No",
            result["error"] or ""
        )
    
    console.print(table)
    
    # Check if any endpoints are available
    available = any("✅" in str(row) for row in table.rows)
    if not available:
        console.print("\n[red]No Ollama endpoints are available. Please check:[/red]")
        console.print("1. Ollama is running on the target machines")
        console.print("2. The model 'gemma2:12b' is installed")
        console.print("3. Network connectivity to the endpoints")
    else:
        console.print("\n[green]Some endpoints are available! You can run the benchmark.[/green]")

if __name__ == "__main__":
    asyncio.run(main())
