#!/usr/bin/env python3
"""
LLM Configuration Management Tool
Allows easy management of LLM configuration through command line
"""

import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from llm_config_loader import get_config_loader, LLMConfig

console = Console()

@click.group()
def cli():
    """LLM Configuration Management Tool"""
    pass

@cli.command()
def status():
    """Show current configuration status"""
    try:
        config_loader = get_config_loader()
        config = config_loader.get_config()
        
        # Show provider
        console.print(f"[bold blue]Provider:[/bold blue] {config.provider}")
        
        if config.provider == "cloud" and config.cloud:
            console.print(f"[bold green]OpenAI Model:[/bold green] {config.cloud.openai_model}")
            console.print(f"[bold green]API Key:[/bold green] {'*' * 20 if config.cloud.openai_api_key else 'Not set'}")
        
        elif config.provider == "ollama" and config.ollama:
            console.print(f"[bold green]Ollama Model:[/bold green] {config.ollama.model}")
            console.print(f"[bold green]Load Balance Strategy:[/bold green] {config.ollama.load_balance_strategy}")
            
            # Show servers
            table = Table(title="Ollama Servers")
            table.add_column("Name", style="cyan")
            table.add_column("URL", style="magenta")
            table.add_column("Enabled", style="green")
            table.add_column("Priority", style="yellow")
            
            for server in config.ollama.servers:
                table.add_row(
                    server.name,
                    server.url,
                    "✅" if server.enabled else "❌",
                    str(server.priority)
                )
            
            console.print(table)
        
        # Validate configuration
        errors = config_loader.validate_config()
        if errors:
            console.print(f"[bold red]Configuration Errors:[/bold red]")
            for error in errors:
                console.print(f"  • {error}")
        else:
            console.print("[bold green]✅ Configuration is valid[/bold green]")
            
    except Exception as e:
        console.print(f"[bold red]Error loading configuration:[/bold red] {e}")

@cli.command()
@click.option("--provider", type=click.Choice(["cloud", "ollama"]), help="Set LLM provider")
@click.option("--openai-model", help="Set OpenAI model")
@click.option("--ollama-model", help="Set Ollama model")
@click.option("--load-balance", type=click.Choice(["round_robin", "random", "least_connections", "fastest_response"]), help="Set load balance strategy")
def set(provider, openai_model, ollama_model, load_balance):
    """Set configuration values"""
    try:
        config_loader = get_config_loader()
        config = config_loader.get_config()
        
        if provider:
            config.provider = provider
            console.print(f"[green]Set provider to: {provider}[/green]")
        
        if openai_model and config.cloud:
            config.cloud.openai_model = openai_model
            console.print(f"[green]Set OpenAI model to: {openai_model}[/green]")
        
        if ollama_model and config.ollama:
            config.ollama.model = ollama_model
            console.print(f"[green]Set Ollama model to: {ollama_model}[/green]")
        
        if load_balance and config.ollama:
            config.ollama.load_balance_strategy = load_balance
            console.print(f"[green]Set load balance strategy to: {load_balance}[/green]")
        
        # Save configuration
        config_loader.save_config(config)
        console.print("[green]Configuration saved[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error setting configuration:[/bold red] {e}")

@cli.command()
@click.argument("name")
@click.argument("url")
@click.option("--enabled/--disabled", default=True, help="Enable or disable server")
@click.option("--priority", type=int, default=1, help="Server priority (lower = higher priority)")
def add_server(name, url, enabled, priority):
    """Add a new Ollama server"""
    try:
        config_loader = get_config_loader()
        config = config_loader.get_config()
        
        if not config.ollama:
            console.print("[bold red]Ollama configuration not found. Please set provider to 'ollama' first.[/bold red]")
            return
        
        # Check if server already exists
        for server in config.ollama.servers:
            if server.name == name:
                console.print(f"[bold red]Server '{name}' already exists[/bold red]")
                return
        
        # Add new server
        from llm_config_loader import OllamaServerConfig
        new_server = OllamaServerConfig(
            name=name,
            url=url,
            enabled=enabled,
            priority=priority
        )
        config.ollama.servers.append(new_server)
        
        # Save configuration
        config_loader.save_config(config)
        console.print(f"[green]Added server '{name}' at {url}[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error adding server:[/bold red] {e}")

@cli.command()
@click.argument("name")
@click.option("--enabled/--disabled", help="Enable or disable server")
@click.option("--priority", type=int, help="Set server priority")
def edit_server(name, enabled, priority):
    """Edit an existing Ollama server"""
    try:
        config_loader = get_config_loader()
        config = config_loader.get_config()
        
        if not config.ollama:
            console.print("[bold red]Ollama configuration not found[/bold red]")
            return
        
        # Find server
        server = None
        for s in config.ollama.servers:
            if s.name == name:
                server = s
                break
        
        if not server:
            console.print(f"[bold red]Server '{name}' not found[/bold red]")
            return
        
        # Update server
        if enabled is not None:
            server.enabled = enabled
            console.print(f"[green]Set server '{name}' enabled: {enabled}[/green]")
        
        if priority is not None:
            server.priority = priority
            console.print(f"[green]Set server '{name}' priority: {priority}[/green]")
        
        # Save configuration
        config_loader.save_config(config)
        console.print(f"[green]Updated server '{name}'[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error editing server:[/bold red] {e}")

@cli.command()
@click.argument("name")
def remove_server(name):
    """Remove an Ollama server"""
    try:
        config_loader = get_config_loader()
        config = config_loader.get_config()
        
        if not config.ollama:
            console.print("[bold red]Ollama configuration not found[/bold red]")
            return
        
        # Find and remove server
        original_count = len(config.ollama.servers)
        config.ollama.servers = [s for s in config.ollama.servers if s.name != name]
        
        if len(config.ollama.servers) == original_count:
            console.print(f"[bold red]Server '{name}' not found[/bold red]")
            return
        
        # Save configuration
        config_loader.save_config(config)
        console.print(f"[green]Removed server '{name}'[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error removing server:[/bold red] {e}")

@cli.command()
def test():
    """Test LLM configuration"""
    try:
        from llm_client import get_llm_client, close_llm_client
        import asyncio
        
        async def test_llm():
            client = await get_llm_client()
            
            # Test server status
            status = await client.get_server_status()
            console.print(f"[green]Server status:[/green] {status}")
            
            # Test generation
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, how are you?"}
            ]
            
            response = await client.generate(messages)
            if response.success:
                console.print(f"[green]✅ Test successful:[/green] {response.content[:100]}...")
            else:
                console.print(f"[red]❌ Test failed:[/red] {response.error}")
            
            await close_llm_client()
        
        asyncio.run(test_llm())
        
    except Exception as e:
        console.print(f"[bold red]Error testing configuration:[/bold red] {e}")

if __name__ == "__main__":
    cli()
