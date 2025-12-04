#!/usr/bin/env python3
"""
Debug script to test content-only hash calculation
"""

import hashlib
from pathlib import Path

def parse_frontmatter(content: str) -> str:
    """Extract content only, excluding YAML frontmatter."""
    if not content.startswith('---'):
        return content
    
    lines = content.split('\n')
    if len(lines) < 2:
        return content
    
    # Find the end of frontmatter (second ---)
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end_idx = i
            break
    
    if end_idx is None:
        return content
    
    # Return content after frontmatter
    return '\n'.join(lines[end_idx + 1:]).strip()

def calculate_content_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content (excluding frontmatter)."""
    try:
        content = file_path.read_text(encoding='utf-8')
        content_only = parse_frontmatter(content)
        return hashlib.sha256(content_only.encode('utf-8')).hexdigest()
    except Exception:
        return ""

# Test the file
file_path = Path('/Users/weidongyang/Obsidian/ExampleVault/Events/D Day tour.md')

if file_path.exists():
    content = file_path.read_text(encoding='utf-8')
    print('=== FULL CONTENT ===')
    print(repr(content[:500]) + '...' if len(content) > 500 else repr(content))
    print()
    
    content_only = parse_frontmatter(content)
    print('=== CONTENT ONLY (no frontmatter) ===')
    print(repr(content_only[:500]) + '...' if len(content_only) > 500 else repr(content_only))
    print()
    
    hash_full = calculate_content_hash(file_path)
    print('Content-only hash:', hash_full)
else:
    print('File does not exist:', file_path)
