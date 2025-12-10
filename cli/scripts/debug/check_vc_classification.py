#!/usr/bin/env python3
"""
Check how many notes in Companies/VC are fully classified by VC Profile Analysis task
"""

import sys
from pathlib import Path

cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDatabase, TaskDefinition
from config_loader import get_config_loader
from metadata_manager import get_metadata

def get_vault_path() -> Path:
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def check_vc_classification():
    """Check classification status of VC notes"""
    vault_path = get_vault_path()
    folder = vault_path / "Companies" / "VC"
    
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)
    
    # Get the task definition
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    task = db.get_task("gxr_vc_analysis")
    
    if not task:
        print("Error: Task 'gxr_vc_analysis' not found")
        sys.exit(1)
    
    if not task.tag_schema:
        print("Error: Task has no tag_schema")
        sys.exit(1)
    
    # Get expected tags
    expected_tags = [ts.tag for ts in task.tag_schema]
    print(f"\n🔍 Checking VC Profile Analysis classification status")
    print(f"   Task: {task.name} ({task.tag})")
    print(f"   Expected tags ({len(expected_tags)}):")
    for tag in expected_tags:
        print(f"     - {tag}")
    print(f"\n   Folder: {folder.relative_to(vault_path)}")
    print()
    
    # Find all markdown files
    md_files = list(folder.rglob("*.md"))
    md_files = [
        f for f in md_files 
        if not any(part.startswith('.') for part in f.relative_to(vault_path).parts)
    ]
    
    print(f"Found {len(md_files)} notes\n")
    
    # Check each note
    fully_classified = []
    partially_classified = []
    not_classified = []
    
    for md_file in md_files:
        relative_path = str(md_file.relative_to(vault_path))
        metadata = get_metadata(md_file)
        
        if metadata is None:
            not_classified.append(relative_path)
            continue
        
        # Check which tags are present
        present_tags = [tag for tag in expected_tags if tag in metadata]
        missing_tags = [tag for tag in expected_tags if tag not in metadata]
        
        if len(present_tags) == len(expected_tags):
            fully_classified.append(relative_path)
        elif len(present_tags) > 0:
            partially_classified.append((relative_path, present_tags, missing_tags))
        else:
            not_classified.append(relative_path)
    
    # Print results
    print("=" * 80)
    print("📊 Classification Status Summary")
    print("=" * 80)
    print(f"\n✅ Fully Classified: {len(fully_classified)}/{len(md_files)}")
    print(f"⚠️  Partially Classified: {len(partially_classified)}/{len(md_files)}")
    print(f"❌ Not Classified: {len(not_classified)}/{len(md_files)}")
    
    if fully_classified:
        print(f"\n✅ Fully Classified Notes ({len(fully_classified)}):")
        for path in sorted(fully_classified):
            print(f"   ✓ {path}")
    
    if partially_classified:
        print(f"\n⚠️  Partially Classified Notes ({len(partially_classified)}):")
        for path, present, missing in sorted(partially_classified):
            print(f"   ⚠ {path}")
            print(f"      Present: {', '.join(present)}")
            print(f"      Missing: {', '.join(missing)}")
    
    if not_classified:
        print(f"\n❌ Not Classified Notes ({len(not_classified)}):")
        for path in sorted(not_classified):
            print(f"   ✗ {path}")
    
    print("\n" + "=" * 80)
    print(f"Summary: {len(fully_classified)}/{len(md_files)} notes are fully classified")
    print("=" * 80)

if __name__ == "__main__":
    check_vc_classification()

