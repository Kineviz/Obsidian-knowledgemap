#!/usr/bin/env python3
"""
Debug script to check why a specific note failed
"""

import sys
from pathlib import Path

cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDatabase, Classifier
from config_loader import get_config_loader
from metadata_manager import get_metadata, parse_frontmatter

def get_vault_path() -> Path:
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def debug_failed_note():
    """Debug why Eniac Ventures.md failed"""
    vault_path = get_vault_path()
    note_path = vault_path / "Companies" / "VC" / "Eniac Ventures.md"
    
    if not note_path.exists():
        print(f"Error: Note not found: {note_path}")
        sys.exit(1)
    
    print(f"Checking note: {note_path.relative_to(vault_path)}\n")
    
    # Read note content
    content = note_path.read_text(encoding='utf-8')
    frontmatter, body = parse_frontmatter(content)
    
    print("=" * 80)
    print("Note Content Analysis")
    print("=" * 80)
    print(f"\nFrontmatter keys: {list(frontmatter.keys()) if frontmatter else 'None'}")
    print(f"\nBody length: {len(body)} characters")
    print(f"Body preview (first 500 chars):")
    print("-" * 80)
    print(body[:500])
    print("-" * 80)
    
    # Check if note is empty or has issues
    if not body.strip():
        print("\n⚠️  WARNING: Note body is empty!")
    elif len(body.strip()) < 100:
        print(f"\n⚠️  WARNING: Note body is very short ({len(body.strip())} chars)")
    
    # Get task
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    task = db.get_task("gxr_vc_analysis")
    
    if not task:
        print("Error: Task not found")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("Task Information")
    print("=" * 80)
    print(f"Task: {task.name} ({task.tag})")
    print(f"Task type: {task.task_type}")
    print(f"Tag schema: {len(task.tag_schema) if task.tag_schema else 0} tags")
    
    # Check if already classified
    print("\n" + "=" * 80)
    print("Classification Status")
    print("=" * 80)
    if task.tag_schema:
        expected_tags = [ts.tag for ts in task.tag_schema]
        present_tags = [tag for tag in expected_tags if tag in frontmatter]
        missing_tags = [tag for tag in expected_tags if tag not in frontmatter]
        
        print(f"Expected tags: {expected_tags}")
        print(f"Present tags: {present_tags}")
        print(f"Missing tags: {missing_tags}")
        
        if not missing_tags:
            print("\n✅ Note is already fully classified!")
        elif present_tags:
            print(f"\n⚠️  Note is partially classified ({len(present_tags)}/{len(expected_tags)} tags)")
        else:
            print("\n❌ Note is not classified")

if __name__ == "__main__":
    debug_failed_note()

