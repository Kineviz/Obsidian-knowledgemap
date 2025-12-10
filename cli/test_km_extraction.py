#!/usr/bin/env python3
"""
Test Knowledge Map extraction for different models
Focus on debugging JSON parsing issues
"""

import sys
import asyncio
import json
from pathlib import Path

# Add cli to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from llm_client import LLMClient
from config_loader import get_config_loader
from prompt_loader import PromptLoader
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

async def test_km_extraction(model_name: str, provider: str, test_content: str):
    """Test knowledge map extraction for a specific model"""
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold cyan]Testing: {model_name} ({provider})[/bold cyan]")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")
    
    # Temporarily modify config
    config = get_config_loader()
    original_provider = config.config_data.get('llm', {}).get('provider', 'cloud')
    
    try:
        # Set provider and model
        if 'llm' not in config.config_data:
            config.config_data['llm'] = {}
        # LLMProvider enum uses 'cloud' for OpenAI, not 'openai'
        config.config_data['llm']['provider'] = 'cloud' if provider == 'openai' else provider
        
        if provider == 'ollama':
            if 'ollama' not in config.config_data['llm']:
                config.config_data['llm']['ollama'] = {}
            config.config_data['llm']['ollama']['model'] = model_name
        else:
            if 'cloud' not in config.config_data['llm']:
                config.config_data['llm']['cloud'] = {}
            if 'openai' not in config.config_data['llm']['cloud']:
                config.config_data['llm']['cloud']['openai'] = {}
            config.config_data['llm']['cloud']['openai']['model'] = model_name
        
        # Create LLM client
        llm_client = LLMClient()
        
        # Build prompt
        prompt_loader = PromptLoader()
        system_prompt = prompt_loader.get_system_prompt("relationship_extraction").content
        user_prompt = prompt_loader.get_user_prompt("relationship_extraction", text=test_content).content
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        console.print("[yellow]Sending request...[/yellow]")
        import time
        start_time = time.time()
        
        # Generate response
        response = await llm_client.generate(messages)
        
        response_time = time.time() - start_time
        
        console.print(f"[green]Response received in {response_time:.2f}s[/green]")
        console.print(f"[dim]Success: {response.success}[/dim]")
        console.print(f"[dim]Model: {response.model}[/dim]")
        console.print(f"[dim]Provider: {response.provider}[/dim]")
        
        if not response.success:
            console.print(f"[red]Error: {response.error}[/red]")
            return
        
        # Show raw response
        console.print(f"\n[bold]Raw Response (first 500 chars):[/bold]")
        console.print(Panel(response.content[:500], border_style="dim"))
        
        # Try to parse JSON
        console.print(f"\n[bold]Attempting JSON parse...[/bold]")
        try:
            # Try to find JSON in the response
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Try to find JSON object
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = content[json_start:json_end]
                console.print(f"[green]Found JSON object at position {json_start}-{json_end}[/green]")
                console.print(f"[dim]JSON content length: {len(json_content)} chars[/dim]")
                
                result = json.loads(json_content)
                relationships = result.get('relationships', [])
                
                console.print(f"\n[bold green]✓ Successfully parsed JSON![/bold green]")
                console.print(f"[green]Found {len(relationships)} relationships[/green]")
                
                # Show first few relationships
                if relationships:
                    console.print(f"\n[bold]First 3 relationships:[/bold]")
                    for i, rel in enumerate(relationships[:3], 1):
                        console.print(f"  {i}. {rel.get('source_label')} - {rel.get('relationship')} - {rel.get('target_label')}")
                
                return True
            else:
                console.print(f"[red]✗ No JSON object found in response[/red]")
                console.print(f"[yellow]Response starts with: {content[:100]}...[/yellow]")
                return False
                
        except json.JSONDecodeError as e:
            console.print(f"[red]✗ JSON parse error: {e}[/red]")
            console.print(f"[yellow]Error at position: {e.pos if hasattr(e, 'pos') else 'unknown'}[/yellow]")
            
            # Show the problematic area
            if hasattr(e, 'pos') and e.pos:
                start = max(0, e.pos - 50)
                end = min(len(content), e.pos + 50)
                console.print(f"\n[bold]Context around error:[/bold]")
                console.print(Syntax(content[start:end], "json", theme="monokai", line_numbers=True))
            
            return False
    
    except Exception as e:
        console.print(f"[red]Exception: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False
    
    finally:
        # Restore original config
        if 'llm' in config.config_data:
            config.config_data['llm']['provider'] = original_provider

async def main():
    """Test all models for Knowledge Map extraction"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Knowledge Map extraction for different models")
    parser.add_argument("test_file", type=str, help="Path to test markdown file")
    parser.add_argument("--model", type=str, default=None, help="Test specific model only")
    
    args = parser.parse_args()
    
    # Load test file
    config = get_config_loader()
    vault_path = Path(config.get('vault.path'))
    test_file = Path(args.test_file)
    
    if not test_file.is_absolute():
        test_file = vault_path / test_file
    
    if not test_file.exists():
        console.print(f"[red]Error: Test file not found: {test_file}[/red]")
        sys.exit(1)
    
    test_content = test_file.read_text(encoding='utf-8')
    console.print(f"[green]Loaded test file: {test_file}[/green]")
    console.print(f"[dim]File size: {len(test_content)} characters[/dim]\n")
    
    # Models to test
    models = [
        {"name": "qwen3:8b", "provider": "ollama"},
        {"name": "qwen3:14b", "provider": "ollama"},
        {"name": "llama3.1:8b", "provider": "ollama"},
        {"name": "gpt-4o-mini", "provider": "openai"},
    ]
    
    if args.model:
        models = [m for m in models if m['name'] == args.model]
        if not models:
            console.print(f"[red]Error: Model {args.model} not found[/red]")
            sys.exit(1)
    
    console.print(Panel.fit("[bold]Knowledge Map Extraction Test[/bold]\nDebugging JSON parsing issues", border_style="cyan"))
    
    for model_config in models:
        await test_km_extraction(model_config['name'], model_config['provider'], test_content)
        await asyncio.sleep(1)  # Small delay between tests

if __name__ == "__main__":
    asyncio.run(main())

