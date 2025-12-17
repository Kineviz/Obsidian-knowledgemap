#!/usr/bin/env python3
"""
Debug script to check why skip logic isn't working
"""

import sys
from pathlib import Path

cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDatabase, Classifier
from config_loader import get_config_loader
from metadata_manager import get_metadata

def get_vault_path() -> Path:
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def debug_skip_logic():
    """Debug why skip logic isn't working"""
    vault_path = get_vault_path()
    
    # Get task
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    task = db.get_task("_vc_analysis")
    
    if not task or not task.tag_schema:
        print("Error: Task not found or has no tag_schema")
        sys.exit(1)
    
    expected_tags = [ts.tag for ts in task.tag_schema]
    print(f"Expected tags: {expected_tags}\n")
    
    # Test with one fully classified note
    test_note = vault_path / "Companies" / "VC" / "AIX Ventures.md"
    if not test_note.exists():
        print(f"Test note not found: {test_note}")
        sys.exit(1)
    
    print(f"Testing with: {test_note.relative_to(vault_path)}\n")
    
    # Check metadata directly
    metadata = get_metadata(test_note)
    print(f"Metadata keys: {list(metadata.keys()) if metadata else 'None'}\n")
    
    # Check each expected tag
    print("Tag presence check:")
    for tag in expected_tags:
        present = tag in metadata if metadata else False
        value = metadata.get(tag) if metadata else None
        status = "✓" if present else "✗"
        print(f"  {status} {tag}: {value}")
    
    # Test with Classifier
    print("\n" + "="*80)
    print("Testing Classifier.is_classified() method:")
    print("="*80)
    classifier = Classifier(vault_path)
    
    # Check single tag (old method)
    for tag in expected_tags:
        is_classified = classifier.is_classified(test_note, tag)
        print(f"  is_classified('{tag}'): {is_classified}")
    
    # Check multi-tag logic (what _classify_note_multi does)
    print("\n" + "="*80)
    print("Testing multi-tag skip logic (what _classify_note_multi does):")
    print("="*80)
    
    metadata = classifier._get_metadata(test_note)
    print(f"  metadata is not None: {metadata is not None}")
    if metadata is not None:
        missing_tags = [tag for tag in expected_tags if tag not in metadata]
        present_tags = [tag for tag in expected_tags if tag in metadata]
        print(f"  Present tags: {present_tags}")
        print(f"  Missing tags: {missing_tags}")
        print(f"  Should skip: {len(missing_tags) == 0}")

if __name__ == "__main__":
    debug_skip_logic()

