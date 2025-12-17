#!/usr/bin/env python3
"""
Migration script to rename VC tags from long to short names

Old tags → New tags:
- gxr_vc_investment_stages → gxr_vc_stages
- gxr_vc_check_size → gxr_vc_size
- gxr_vc_geography → gxr_vc_geo
- gxr_vc_firm_type → gxr_vc_type
- gxr_vc_sectors → gxr_vc_sectors (no change)

Usage:
    cd cli
    uv run scripts/utils/migrate_vc_tags.py [--dry-run] [--folder <folder>]
"""

import sys
import re
from pathlib import Path
from typing import Dict, Tuple

# Add cli directory to path
cli_path = Path(__file__).parent.parent.parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from config_loader import get_config_loader
from metadata_manager import parse_frontmatter, write_frontmatter

# Tag migration mapping
# Migrates from old long names to new short names with _vc_ prefix
TAG_MIGRATIONS: Dict[str, str] = {
    # Old long names → New short names
    "gxr_vc_investment_stages": "_vc_stages",
    "gxr_vc_check_size": "_vc_size",
    "gxr_vc_geography": "_vc_geo",
    "gxr_vc_firm_type": "_vc_type",
    "gxr_vc_sectors": "_vc_sectors",
    # Also migrate from intermediate short names (if they exist)
    "gxr_vc_stages": "_vc_stages",
    "gxr_vc_size": "_vc_size",
    "gxr_vc_geo": "_vc_geo",
    "gxr_vc_type": "_vc_type",
}

def get_vault_path() -> Path:
    """Get vault path from config"""
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def migrate_note(note_path: Path, dry_run: bool = False) -> Tuple[bool, int]:
    """
    Migrate tags in a single note
    
    Returns:
        (success, tags_migrated_count)
    """
    try:
        content = note_path.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        if not frontmatter:
            return True, 0
        
        migrated_count = 0
        new_frontmatter = frontmatter.copy()
        
        # Migrate each tag
        for old_tag, new_tag in TAG_MIGRATIONS.items():
            if old_tag in new_frontmatter:
                value = new_frontmatter.pop(old_tag)
                new_frontmatter[new_tag] = value
                migrated_count += 1
                
                # Also migrate timestamp tags if they exist
                old_timestamp_tag = f"{old_tag}_at"
                new_timestamp_tag = f"{new_tag}_at"
                if old_timestamp_tag in new_frontmatter:
                    timestamp_value = new_frontmatter.pop(old_timestamp_tag)
                    new_frontmatter[new_timestamp_tag] = timestamp_value
        
        if migrated_count > 0 and not dry_run:
            # Write back the updated frontmatter
            new_content = write_frontmatter(new_frontmatter, body)
            note_path.write_text(new_content, encoding='utf-8')
        
        return True, migrated_count
        
    except Exception as e:
        print(f"Error migrating {note_path}: {e}")
        return False, 0

def migrate_folder(folder_path: Path, dry_run: bool = False) -> Dict[str, int]:
    """
    Migrate all markdown files in a folder
    
    Returns:
        {"total": X, "migrated": Y, "tags_migrated": Z, "errors": W}
    """
    stats = {"total": 0, "migrated": 0, "tags_migrated": 0, "errors": 0}
    
    # Find all markdown files
    for md_file in folder_path.rglob("*.md"):
        stats["total"] += 1
        
        success, tags_count = migrate_note(md_file, dry_run)
        
        if success:
            if tags_count > 0:
                stats["migrated"] += 1
                stats["tags_migrated"] += tags_count
        else:
            stats["errors"] += 1
    
    return stats

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate VC tags to shorter names")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without making changes")
    parser.add_argument("--folder", type=str, help="Folder path to migrate (relative to vault). If not specified, migrates entire vault.")
    
    args = parser.parse_args()
    
    vault_path = get_vault_path()
    
    if args.folder:
        folder_path = vault_path / args.folder
        if not folder_path.exists():
            print(f"Error: Folder not found: {folder_path}")
            sys.exit(1)
    else:
        folder_path = vault_path
    
    print(f"Migrating VC tags in: {folder_path.relative_to(vault_path) if args.folder else 'entire vault'}")
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")
    
    print("Tag migrations:")
    for old, new in TAG_MIGRATIONS.items():
        print(f"  {old} → {new}")
    print()
    
    stats = migrate_folder(folder_path, dry_run=args.dry_run)
    
    print(f"\nMigration Summary:")
    print(f"  Total files scanned: {stats['total']}")
    print(f"  Files with tags migrated: {stats['migrated']}")
    print(f"  Total tags migrated: {stats['tags_migrated']}")
    print(f"  Errors: {stats['errors']}")
    
    if args.dry_run:
        print("\nRun without --dry-run to apply changes")

if __name__ == "__main__":
    main()

