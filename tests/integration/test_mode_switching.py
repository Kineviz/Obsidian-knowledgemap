#!/usr/bin/env python3
"""
Test script to verify both cloud and ollama modes work correctly
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


from llm_client import get_llm_client, close_llm_client
from prompt_loader import get_prompt_loader

console = Console()

async def test_llm_mode(provider_name: str, test_text: str):
    """Test LLM with a specific provider"""
    console.print(f"\n[bold blue]Testing {provider_name} Mode[/bold blue]")
    
    try:
        # Get LLM client
        client = await get_llm_client()
        
        # Load prompts
        prompt_loader = get_prompt_loader()
        messages = prompt_loader.get_prompt_pair("relationship_extraction", text=test_text)
        
        # Test generation
        start_time = asyncio.get_event_loop().time()
        response = await client.generate(messages)
        end_time = asyncio.get_event_loop().time()
        
        if response.success:
            console.print(f"✅ {provider_name}: Success")
            console.print(f"   Model: {response.model}")
            console.print(f"   Provider: {response.provider}")
            console.print(f"   Server: {response.server_url or 'N/A'}")
            console.print(f"   Response Time: {response.response_time:.2f}s")
            console.print(f"   Tokens: {response.token_count or 'N/A'}")
            
            # Show first 200 characters of response
            preview = response.content[:200] + "..." if len(response.content) > 200 else response.content
            console.print(f"   Preview: {preview}")
            
            return True
        else:
            console.print(f"❌ {provider_name}: Failed - {response.error}")
            return False
            
    except Exception as e:
        console.print(f"❌ {provider_name}: Error - {e}")
        return False
    finally:
        await close_llm_client()

async def main():
    """Main test function"""
    console.print("[bold green]LLM Configuration Test - Cloud vs Ollama[/bold green]")
    
    # Read test document
    test_file = Path("test_document.md")
    if not test_file.exists():
        console.print("[red]Error: test_document.md not found[/red]")
        return
    
    test_text = test_file.read_text(encoding='utf-8')
    console.print(f"[cyan]Test document loaded: {len(test_text)} characters[/cyan]")
    
    # Test results
    results = []
    
    # Test Cloud Mode
    console.print("\n[bold yellow]Switching to Cloud Mode...[/bold yellow]")
    from llm_config_loader import get_config_loader
    config_loader = get_config_loader()
    config = config_loader.get_config()
    config.provider = "cloud"
    config_loader.save_config(config)
    
    cloud_success = await test_llm_mode("Cloud (OpenAI)", test_text)
    results.append(("Cloud (OpenAI)", cloud_success))
    
    # Test Ollama Mode
    console.print("\n[bold yellow]Switching to Ollama Mode...[/bold yellow]")
    config.provider = "ollama"
    config_loader.save_config(config)
    
    ollama_success = await test_llm_mode("Ollama (Local)", test_text)
    results.append(("Ollama (Local)", ollama_success))
    
    # Summary
    console.print("\n[bold green]Test Summary[/bold green]")
    table = Table(title="Test Results")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="magenta")
    
    for provider, success in results:
        status = "✅ Success" if success else "❌ Failed"
        table.add_row(provider, status)
    
    console.print(table)
    
    # Overall result
    all_success = all(success for _, success in results)
    if all_success:
        console.print("\n[bold green]🎉 All tests passed! Both cloud and ollama modes are working correctly.[/bold green]")
    else:
        console.print("\n[bold red]⚠️  Some tests failed. Check the configuration.[/bold red]")

if __name__ == "__main__":
    asyncio.run(main())
