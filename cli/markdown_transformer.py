#!/usr/bin/env python3
"""
Markdown Transformer Module

This module provides utilities for transforming markdown content,
including updating image links to point to the server's image endpoint.

Usage:
    from markdown_transformer import transform_markdown_images
    
    transformed = transform_markdown_images(markdown_content, server_url="http://localhost:7001")
"""

import re
from typing import Optional
from pathlib import Path
import urllib.parse


def transform_markdown_images(
    markdown_content: str,
    server_url: str = "http://localhost:7001",
    vault_path: Optional[str] = None,
    current_file_path: Optional[str] = None
) -> str:
    """
    Transform markdown image links to point to the server's image endpoint.
    
    Supports various Obsidian image formats:
    - ![[image.png]] -> ![image.png](http://localhost:7001/images/image.png)
    - ![alt](relative/path/image.png) -> ![alt](http://localhost:7001/images/relative/path/image.png)
    - ![alt](./image.png) -> ![alt](http://localhost:7001/images/image.png)
    - ![alt](../other/image.png) -> ![alt](http://localhost:7001/images/other/image.png)
    
    Args:
        markdown_content: The markdown content to transform
        server_url: The base URL of the server (default: http://localhost:7001)
        vault_path: Optional path to the vault root (for resolving relative paths)
        current_file_path: Optional path to the current file (for resolving relative paths)
    
    Returns:
        Transformed markdown content with updated image links
    """
    if not markdown_content:
        return markdown_content
    
    # Remove trailing slash from server URL
    server_url = server_url.rstrip('/')
    
    # Pattern 1: Obsidian wiki-style image links: ![[image.png]]
    # Transform to: ![image.png](http://localhost:7001/images/image.png)
    def replace_wiki_image(match):
        image_path = match.group(1)
        # Remove any size specifications like |100x100
        image_path = image_path.split('|')[0].strip()
        
        # URL encode the path
        encoded_path = urllib.parse.quote(image_path)
        
        # Extract just the filename for alt text
        alt_text = Path(image_path).name
        
        return f'![{alt_text}]({server_url}/images/{encoded_path})'
    
    markdown_content = re.sub(
        r'!\[\[([^\]]+)\]\]',
        replace_wiki_image,
        markdown_content
    )
    
    # Pattern 2: Standard markdown image links: ![alt](path)
    # Only transform if the path is relative (doesn't start with http:// or https://)
    def replace_standard_image(match):
        alt_text = match.group(1)
        image_path = match.group(2)
        
        # Skip if already an absolute URL
        if image_path.startswith(('http://', 'https://', '//')):
            return match.group(0)
        
        # Skip if already pointing to our server
        if server_url in image_path:
            return match.group(0)
        
        # Resolve relative paths if we have context
        resolved_path = image_path
        if current_file_path and vault_path:
            try:
                # Resolve relative to current file
                current_dir = Path(current_file_path).parent
                resolved = (current_dir / image_path).resolve()
                vault_root = Path(vault_path).resolve()
                
                # Get path relative to vault root
                resolved_path = str(resolved.relative_to(vault_root))
            except (ValueError, Exception):
                # If not relative to vault or resolution fails, clean up path manually
                resolved_path = str(Path(image_path).as_posix())
                # Remove leading ./ and ensure no absolute path components
                while resolved_path.startswith('./'):
                    resolved_path = resolved_path[2:]
                if resolved_path.startswith('../'):
                    # Remove leading ../ components if we can't resolve properly
                    parts = resolved_path.split('/')
                    parts = [p for p in parts if p != '..']
                    resolved_path = '/'.join(parts)
        else:
            # Clean up ./ and ../ if we don't have full context
            # This is best-effort - ideally vault_path and current_file_path should be provided
            resolved_path = str(Path(image_path).as_posix())
            while resolved_path.startswith('./'):
                resolved_path = resolved_path[2:]
            # For ../ without context, we'll keep it as the server can handle normalization
            # Or we can try to normalize it
            try:
                resolved_path = str(Path(resolved_path).as_posix())
            except Exception:
                pass
        
        # URL encode the path
        encoded_path = urllib.parse.quote(resolved_path)
        
        return f'![{alt_text}]({server_url}/images/{encoded_path})'
    
    # Match markdown images but not already transformed ones
    markdown_content = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        replace_standard_image,
        markdown_content
    )
    
    return markdown_content


def transform_note_content(
    note_data: dict,
    server_url: str = "http://localhost:7001",
    vault_path: Optional[str] = None
) -> dict:
    """
    Transform note data from database query results, updating image links in content.
    
    Args:
        note_data: Dictionary containing note data (must have 'content' and optionally 'url' keys)
        server_url: The base URL of the server
        vault_path: Optional path to the vault root
    
    Returns:
        Note data with transformed content
    """
    if 'content' not in note_data:
        return note_data
    
    # Get the file path from the note's url field
    current_file_path = note_data.get('url')
    
    # Transform the content
    note_data['content'] = transform_markdown_images(
        note_data['content'],
        server_url=server_url,
        vault_path=vault_path,
        current_file_path=current_file_path
    )
    
    return note_data


def batch_transform_notes(
    notes: list,
    server_url: str = "http://localhost:7001",
    vault_path: Optional[str] = None
) -> list:
    """
    Transform a list of notes, updating image links in all of them.
    
    Args:
        notes: List of note dictionaries
        server_url: The base URL of the server
        vault_path: Optional path to the vault root
    
    Returns:
        List of transformed notes
    """
    return [
        transform_note_content(note, server_url, vault_path)
        for note in notes
    ]


# Example usage
if __name__ == "__main__":
    # Test the transformation
    test_markdown = """
# My Document

Here's an Obsidian image:
![[screenshot.png]]

Here's a standard markdown image:
![My Image](./images/photo.jpg)

Here's another one:
![Alt text](../assets/diagram.png)

This should not be transformed:
![External](https://example.com/image.png)
"""
    
    print("Original:")
    print(test_markdown)
    print("\n" + "="*60 + "\n")
    
    transformed = transform_markdown_images(test_markdown)
    print("Transformed:")
    print(transformed)

