#!/usr/bin/env python3
"""
Standalone script to build Kuzu database.
This is used as a subprocess to avoid Kuzu cleanup issues.
"""

import sys
import argparse
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from step3_build import Step3Builder

def main():
    parser = argparse.ArgumentParser(description='Build Kuzu database')
    parser.add_argument('--vault-path', required=True, help='Path to the vault')
    parser.add_argument('--db-path', required=True, help='Path to the database file')
    
    args = parser.parse_args()
    
    vault_path = Path(args.vault_path)
    db_path = args.db_path
    
    try:
        builder = Step3Builder(vault_path, db_path)
        builder.build_database()
        print("Database build completed successfully")
        return 0
    except Exception as e:
        print(f"Database build failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
