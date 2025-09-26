#!/usr/bin/env python3
"""
Obsidian Configuration Reader

This module reads Obsidian configuration files to extract template settings,
including whether templates are enabled and which folder is set as the template folder.

Usage:
    from obsidian_config_reader import ObsidianConfigReader
    
    reader = ObsidianConfigReader(vault_path)
    template_config = reader.get_template_config()
    print(f"Templates enabled: {template_config['enabled']}")
    print(f"Template folder: {template_config['folder']}")
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console

console = Console()


class ObsidianConfigReader:
    """Reads Obsidian configuration files to extract template settings"""
    
    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.obsidian_dir = self.vault_path / ".obsidian"
        self.app_config_file = self.obsidian_dir / "app.json"
        self.templates_config_file = self.obsidian_dir / "templates.json"
        
    def is_obsidian_vault(self) -> bool:
        """Check if the path is a valid Obsidian vault"""
        return self.obsidian_dir.exists() and self.obsidian_dir.is_dir()
    
    def is_templates_enabled(self) -> bool:
        """
        Check if templates are enabled by checking if .obsidian/templates.json exists
        
        Returns:
            bool - True if templates are enabled (templates.json exists)
        """
        return self.templates_config_file.exists()
    
    def get_template_folder(self) -> Optional[str]:
        """
        Get template folder path from templates.json
        
        Returns:
            str - Template folder path (relative to vault) or None if not found
        """
        if not self.is_templates_enabled():
            return None
        
        try:
            with open(self.templates_config_file, 'r', encoding='utf-8') as f:
                templates_config = json.load(f)
                return templates_config.get('folder', None)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read templates.json: {e}[/yellow]")
            return None
    
    def get_template_config(self) -> Dict[str, Any]:
        """
        Get template configuration from Obsidian settings
        
        Returns:
            Dictionary containing template settings:
            - enabled: bool - Whether templates are enabled
            - folder: str - Template folder path (relative to vault)
            - hotkey: str - Template hotkey if set
            - date_format: str - Date format for templates
        """
        if not self.is_obsidian_vault():
            return {
                "enabled": False,
                "folder": None,
                "hotkey": None,
                "date_format": None,
                "error": "Not a valid Obsidian vault"
            }
        
        config = {
            "enabled": self.is_templates_enabled(),
            "folder": self.get_template_folder(),
            "hotkey": None,
            "date_format": None
        }
        
        try:
            # Read app.json for additional template settings
            if self.app_config_file.exists():
                with open(self.app_config_file, 'r', encoding='utf-8') as f:
                    app_config = json.load(f)
                
                # Check if templates are enabled in app.json
                if 'templates' in app_config:
                    templates_config = app_config['templates']
                    config['hotkey'] = templates_config.get('hotkey', None)
                    config['date_format'] = templates_config.get('dateFormat', None)
            
        except Exception as e:
            config['error'] = f"Error reading configuration: {e}"
            console.print(f"[yellow]Warning: Could not read Obsidian config: {e}[/yellow]")
        
        return config
    
    def get_all_plugins(self) -> Dict[str, Any]:
        """
        Get all plugin configurations
        
        Returns:
            Dictionary of plugin configurations
        """
        if not self.is_obsidian_vault():
            return {}
        
        plugins_dir = self.obsidian_dir / "plugins"
        if not plugins_dir.exists():
            return {}
        
        plugins = {}
        
        try:
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    plugin_config_file = plugin_dir / "data.json"
                    if plugin_config_file.exists():
                        with open(plugin_config_file, 'r', encoding='utf-8') as f:
                            plugins[plugin_dir.name] = json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read plugins: {e}[/yellow]")
        
        return plugins
    
    def get_workspace_config(self) -> Dict[str, Any]:
        """
        Get workspace configuration
        
        Returns:
            Dictionary containing workspace settings
        """
        if not self.is_obsidian_vault():
            return {}
        
        workspace_file = self.obsidian_dir / "workspace.json"
        if not workspace_file.exists():
            return {}
        
        try:
            with open(workspace_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read workspace config: {e}[/yellow]")
            return {}
    
    def get_theme_config(self) -> Dict[str, Any]:
        """
        Get theme configuration
        
        Returns:
            Dictionary containing theme settings
        """
        if not self.is_obsidian_vault():
            return {}
        
        theme_file = self.obsidian_dir / "app.json"
        if not theme_file.exists():
            return {}
        
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                app_config = json.load(f)
                return {
                    "theme": app_config.get('theme', 'default'),
                    "css_snippets": app_config.get('cssSnippets', []),
                    "accent_color": app_config.get('accentColor', None)
                }
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read theme config: {e}[/yellow]")
            return {}


def main():
    """CLI interface for reading Obsidian configuration"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python obsidian_config_reader.py <vault_path>")
        sys.exit(1)
    
    vault_path = Path(sys.argv[1])
    reader = ObsidianConfigReader(vault_path)
    
    if not reader.is_obsidian_vault():
        console.print(f"[red]Error: {vault_path} is not a valid Obsidian vault[/red]")
        sys.exit(1)
    
    # Get template configuration
    template_config = reader.get_template_config()
    
    console.print(f"[bold cyan]Obsidian Template Configuration[/bold cyan]")
    console.print(f"Vault: {vault_path}")
    console.print(f"Templates enabled: {template_config['enabled']}")
    console.print(f"Template folder: {template_config['folder']}")
    console.print(f"Template hotkey: {template_config['hotkey']}")
    console.print(f"Date format: {template_config['date_format']}")
    
    if 'error' in template_config:
        console.print(f"[red]Error: {template_config['error']}[/red]")


if __name__ == "__main__":
    main()
