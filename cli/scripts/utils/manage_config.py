#!/usr/bin/env python3
"""
Configuration Management Tool
Simple tool to manage the unified config.yaml and .env files
"""

import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from config_loader import get_config_loader

console = Console()

@click.group()
def cli():
    """Configuration Management Tool"""
    pass

@cli.command()
def status():
    """Show current configuration status"""
    try:
        config_loader = get_config_loader()
        
        # Create status table
        table = Table(title="Configuration Status")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Source", style="yellow")
        
        # Vault configuration
        vault_path = config_loader.get_vault_path()
        table.add_row("Vault Path", vault_path or "Not set", "config.yaml or VAULT_PATH")
        
        # LLM configuration
        llm_provider = config_loader.get('llm.provider', 'not set')
        table.add_row("LLM Provider", llm_provider, "config.yaml")
        
        if llm_provider == 'cloud':
            api_key = config_loader.get_openai_api_key()
            table.add_row("OpenAI API Key", "Set" if api_key else "Not set", ".env")
            model = config_loader.get('llm.cloud.openai.model', 'not set')
            table.add_row("OpenAI Model", model, "config.yaml")
        elif llm_provider == 'ollama':
            servers = config_loader.get('llm.ollama.servers', [])
            enabled_servers = [s for s in servers if s.get('enabled', True)]
            table.add_row("Ollama Servers", f"{len(enabled_servers)} enabled", "config.yaml")
            model = config_loader.get('llm.ollama.model', 'not set')
            table.add_row("Ollama Model", model, "config.yaml")
        
        # Database configuration
        db_port = config_loader.get('database.port', 'not set')
        table.add_row("Database Port", str(db_port), "config.yaml")
        
        # Server configuration
        server_port = config_loader.get('server.port', 'not set')
        table.add_row("Server Port", str(server_port), "config.yaml")
        
        console.print(table)
        
        # Show validation errors if any
        errors = config_loader.validate_config()
        if errors:
            console.print("\n[red]Configuration Errors:[/red]")
            for error in errors:
                console.print(f"  - {error}")
        else:
            console.print("\n[green]Configuration is valid![/green]")
            
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")

@cli.command()
def validate():
    """Validate configuration"""
    try:
        config_loader = get_config_loader()
        errors = config_loader.validate_config()
        
        if errors:
            console.print("[red]Configuration validation failed:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            return 1
        else:
            console.print("[green]Configuration is valid![/green]")
            return 0
            
    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")
        return 1

@cli.command()
def show():
    """Show full configuration"""
    try:
        config_loader = get_config_loader()
        
        # Show config.yaml content
        config_path = config_loader.config_path
        if config_path.exists():
            with open(config_path, 'r') as f:
                config_content = f.read()
            
            console.print(Panel(
                config_content,
                title="config.yaml",
                border_style="blue"
            ))
        else:
            console.print("[yellow]config.yaml not found[/yellow]")
        
        # Show .env content (without sensitive data)
        env_path = config_loader.env_path
        if env_path.exists():
            with open(env_path, 'r') as f:
                env_content = f.read()
            
            # Mask API keys
            masked_content = env_content.replace(
                config_loader.get_openai_api_key() or "your-key-here",
                "***MASKED***"
            )
            
            console.print(Panel(
                masked_content,
                title=".env (API keys masked)",
                border_style="green"
            ))
        else:
            console.print("[yellow].env not found[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error showing configuration: {e}[/red]")

if __name__ == "__main__":
    cli()
