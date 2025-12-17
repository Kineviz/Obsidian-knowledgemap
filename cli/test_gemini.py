#!/usr/bin/env python3
"""Test Gemini API integration"""

import asyncio
import sys
from pathlib import Path

# Add cli directory to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from llm_client import get_llm_client
from config_loader import get_config_loader
from rich.console import Console

console = Console()

async def test_gemini():
    """Test Gemini API connection and generation"""
    console.print("[bold cyan]Testing Gemini API Integration[/bold cyan]\n")
    
    # Check config
    config = get_config_loader()
    provider = config.get('llm.provider', 'cloud')
    model = config.get('llm.gemini.model', 'gemini-2.0-flash-exp')
    
    console.print(f"[dim]Provider: {provider}[/dim]")
    console.print(f"[dim]Model: {model}[/dim]\n")
    
    if provider != 'gemini':
        console.print(f"[yellow]⚠️  Warning: Config shows provider='{provider}', expected 'gemini'[/yellow]")
        console.print("[yellow]   Update config.yaml: llm.provider: 'gemini'[/yellow]\n")
    
    # Test API key
    api_key = config.get_gemini_api_key()
    if not api_key or api_key == 'your-gemini-api-key-here':
        console.print("[red]❌ Gemini API key not found or still placeholder[/red]")
        console.print("[red]   Set GEMINI_API_KEY in .env file[/red]")
        return False
    
    console.print(f"[green]✅ API Key found ({len(api_key)} chars)[/green]\n")
    
    # Test LLM client
    try:
        console.print("[cyan]Initializing LLM client...[/cyan]")
        llm_client = await get_llm_client()
        console.print("[green]✅ LLM client initialized[/green]\n")
        
        # Test generation
        console.print("[cyan]Testing API call with simple prompt...[/cyan]")
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello from Gemini!' and nothing else."}
        ]
        
        response = await llm_client.generate(test_messages, temperature=0.1, max_tokens=50)
        
        if response.success:
            console.print(f"[green]✅ API call successful![/green]")
            console.print(f"[dim]Response time: {response.response_time:.2f}s[/dim]")
            console.print(f"[dim]Provider: {response.provider}[/dim]")
            console.print(f"[dim]Model: {response.model}[/dim]")
            if response.token_count:
                console.print(f"[dim]Tokens: {response.token_count}[/dim]")
            console.print(f"\n[bold]Response:[/bold]")
            console.print(f"[green]{response.content}[/green]\n")
            return True
        else:
            console.print(f"[red]❌ API call failed[/red]")
            console.print(f"[red]Error: {response.error}[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False
    finally:
        from llm_client import close_llm_client
        await close_llm_client()

if __name__ == "__main__":
    success = asyncio.run(test_gemini())
    sys.exit(0 if success else 1)
