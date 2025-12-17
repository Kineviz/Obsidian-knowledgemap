#!/usr/bin/env python3
"""
Debug script to check if task.tag_schema is loaded correctly from database
"""

import sys
from pathlib import Path

cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDatabase, Classifier
from config_loader import get_config_loader

def get_vault_path() -> Path:
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def debug_task_loading():
    """Debug if task.tag_schema is loaded correctly"""
    vault_path = get_vault_path()
    
    # Get task from database
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    task = db.get_task("_vc_analysis")
    
    if not task:
        print("Error: Task not found")
        sys.exit(1)
    
    print(f"Task: {task.name} ({task.tag})")
    print(f"Task type: {task.task_type}")
    print(f"Tag schema: {task.tag_schema}")
    
    if task.tag_schema:
        print(f"\nTag schema tags ({len(task.tag_schema)}):")
        for ts in task.tag_schema:
            print(f"  - {ts.tag} ({ts.output_type.value})")
    else:
        print("\n⚠️  WARNING: tag_schema is None or empty!")
        print("This would cause the skip logic to fail!")
    
    # Test with Classifier (how it's actually used)
    print("\n" + "="*80)
    print("Testing with Classifier (how it's used in classify_folder):")
    print("="*80)
    classifier = Classifier(vault_path)
    
    # Get task again (should be same)
    task_from_classifier = classifier.task_db.get_task("gxr_vc_analysis")
    print(f"Task from classifier.task_db: {task_from_classifier.name}")
    print(f"Tag schema: {task_from_classifier.tag_schema}")
    
    if task_from_classifier.tag_schema:
        expected_tags = [ts.tag for ts in task_from_classifier.tag_schema]
        print(f"Expected tags: {expected_tags}")
    else:
        print("⚠️  WARNING: tag_schema is None!")

if __name__ == "__main__":
    debug_task_loading()

