#!/usr/bin/env python3
"""
Reset the classification task database

This script:
1. Backs up the existing database (if it exists)
2. Deletes the database
3. Re-initializes it with sample tasks using new tag names
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add cli directory to path
cli_path = Path(__file__).parent.parent.parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from config_loader import get_config_loader
from scripts.utils.init_sample_tasks import init_sample_tasks

def get_vault_path() -> Path:
    """Get vault path from config"""
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def reset_task_db():
    """Reset the task database"""
    vault_path = get_vault_path()
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    
    print("🔄 Resetting Classification Task Database\n")
    print(f"Database location: {db_path}\n")
    
    # Backup existing database if it exists
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.parent / f"classification.db.backup_{timestamp}"
        print(f"📦 Backing up existing database to: {backup_path.name}")
        shutil.copy2(db_path, backup_path)
        print(f"   ✓ Backup created\n")
        
        # Delete the database
        print(f"🗑️  Deleting existing database...")
        db_path.unlink()
        print(f"   ✓ Database deleted\n")
    else:
        print("ℹ️  No existing database found (this is fine for first-time setup)\n")
    
    # Re-initialize with sample tasks
    print("📋 Re-initializing with sample tasks (using new _vc_ tag names)...\n")
    success = init_sample_tasks()
    
    if success:
        print("\n✅ Task database reset complete!")
        print(f"   Database: {db_path}")
        print(f"   Tasks initialized with new shorter tag names (_vc_*)")
    else:
        print("\n❌ Failed to initialize sample tasks")
        sys.exit(1)

if __name__ == "__main__":
    reset_task_db()

