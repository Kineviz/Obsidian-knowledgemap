#!/usr/bin/env python3
"""
Standalone script to build Kuzu database.
This is used as a subprocess to avoid Kuzu cleanup issues.
"""

import sys
import argparse
from pathlib import Path

# Add the cli directory (parent of scripts/utils) to the path so we can import our modules
# File is at: cli/scripts/utils/build_database_standalone.py
# Need to import from: cli/step3_build.py, cli/step3b_postprocess.py
cli_dir = Path(__file__).parent.parent.parent
if str(cli_dir) not in sys.path:
    sys.path.insert(0, str(cli_dir))

from step3_build import Step3Builder
from step3b_postprocess import Step3bPostProcessor

def main():
    parser = argparse.ArgumentParser(description='Build Kuzu database')
    parser.add_argument('--vault-path', required=True, help='Path to the vault')
    parser.add_argument('--db-path', required=True, help='Path to the database file')
    parser.add_argument('--skip-postprocess', action='store_true', help='Skip post-processing')
    
    args = parser.parse_args()
    
    vault_path = Path(args.vault_path)
    db_path = args.db_path
    
    builder = None
    processor = None
    try:
        # Step 3: Build database
        builder = Step3Builder(vault_path, db_path)
        builder.build_database()
        print("Database build completed successfully")
        
        # Step 3b: Post-processing (unless skipped)
        if not args.skip_postprocess:
            print("\nRunning post-processing...")
            processor = Step3bPostProcessor(vault_path, db_path)
            processor.run()
            print("Post-processing completed successfully")
        
        return 0
    except Exception as e:
        print(f"Database build failed: {e}", file=sys.stderr)
        return 1
    finally:
        if builder:
            builder.cleanup()
        if processor:
            processor.cleanup()

if __name__ == "__main__":
    sys.exit(main())
