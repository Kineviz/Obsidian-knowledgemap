#!/usr/bin/env python3
"""
Metadata Manager for Obsidian Notes

Allows adding, removing, and editing key-value pairs in YAML frontmatter.
Automatically creates frontmatter section if it doesn't exist.
"""

import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional
import click
from rich.console import Console

console = Console()


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.
    
    Returns:
        tuple: (frontmatter_dict, content_without_frontmatter)
    """
    if not content.startswith('---'):
        return {}, content
    
    lines = content.split('\n')
    if len(lines) < 2:
        return {}, content
    
    # Find the end of frontmatter (second ---)
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end_idx = i
            break
    
    if end_idx is None:
        return {}, content
    
    # Extract frontmatter and content
    frontmatter_lines = lines[1:end_idx]
    content_text = '\n'.join(lines[end_idx + 1:])
    
    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load('\n'.join(frontmatter_lines)) or {}
    except Exception as e:
        console.print(f"[yellow]Warning: Could not parse frontmatter: {e}[/yellow]")
        frontmatter = {}
    
    return frontmatter, content_text


def add_metadata(note_path: Path, key: str, value: Any) -> bool:
    """Add or update a key-value pair in note's frontmatter.
    
    Args:
        note_path: Path to the markdown file
        key: Metadata key to add/update
        value: Value to set
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        content = note_path.read_text(encoding='utf-8')
        frontmatter, content_body = parse_frontmatter(content)
        
        # Update frontmatter
        frontmatter[key] = value
        
        # Reconstruct file content
        new_content = construct_file_content(frontmatter, content_body)
        
        note_path.write_text(new_content, encoding='utf-8')
        console.print(f"[green]✓ Added {key}: {value} to {note_path.name}[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error adding metadata to {note_path.name}: {e}[/red]")
        return False


def remove_metadata(note_path: Path, key: str) -> bool:
    """Remove a key from note's frontmatter.
    
    Args:
        note_path: Path to the markdown file
        key: Metadata key to remove
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        content = note_path.read_text(encoding='utf-8')
        frontmatter, content_body = parse_frontmatter(content)
        
        if key not in frontmatter:
            console.print(f"[yellow]Key '{key}' not found in {note_path.name}[/yellow]")
            return False
        
        # Remove key
        del frontmatter[key]
        
        # Reconstruct file content
        new_content = construct_file_content(frontmatter, content_body)
        
        note_path.write_text(new_content, encoding='utf-8')
        console.print(f"[green]✓ Removed {key} from {note_path.name}[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error removing metadata from {note_path.name}: {e}[/red]")
        return False


def construct_file_content(frontmatter: Dict[str, Any], content_body: str) -> str:
    """Construct complete file content from frontmatter and body."""
    if not frontmatter:
        return content_body.strip()
    
    # Convert frontmatter to YAML
    yaml_content = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    
    # Ensure content body has proper spacing
    content_body = content_body.strip()
    if content_body:
        content_body = '\n\n' + content_body
    
    return f"---\n{yaml_content}---{content_body}"


def get_metadata(note_path: Path, key: Optional[str] = None) -> Any:
    """Get metadata value(s) from note.
    
    Args:
        note_path: Path to the markdown file
        key: Specific key to get (None for all metadata)
    
    Returns:
        Value for specific key or entire frontmatter dict
    """
    try:
        content = note_path.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if key is None:
            return frontmatter
        return frontmatter.get(key)
        
    except Exception as e:
        console.print(f"[red]Error reading metadata from {note_path.name}: {e}[/red]")
        return None


@click.group()
def cli():
    """Metadata Manager for Obsidian Notes"""
    pass


@cli.command()
@click.argument('note_path', type=click.Path(exists=True, path_type=Path))
@click.argument('key')
@click.argument('value')
def add(note_path: Path, key: str, value: str):
    """Add or update a key-value pair in note's frontmatter"""
    add_metadata(note_path, key, value)


@cli.command()
@click.argument('note_path', type=click.Path(exists=True, path_type=Path))
@click.argument('key')
def remove(note_path: Path, key: str):
    """Remove a key from note's frontmatter"""
    remove_metadata(note_path, key)


@cli.command()
@click.argument('note_path', type=click.Path(exists=True, path_type=Path))
@click.option('--key', '-k', help='Specific key to show (show all if not specified)')
def show(note_path: Path, key: Optional[str] = None):
    """Show metadata from note"""
    result = get_metadata(note_path, key)
    if result is not None:
        if isinstance(result, dict):
            if result:
                console.print("[cyan]Metadata:[/cyan]")
                for k, v in result.items():
                    console.print(f"  {k}: {v}")
            else:
                console.print("[yellow]No metadata found[/yellow]")
        else:
            console.print(f"[cyan]{key}:[/cyan] {result}")


if __name__ == "__main__":
    cli()
