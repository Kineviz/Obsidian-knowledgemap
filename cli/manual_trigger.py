#!/usr/bin/env python3
"""
Manual trigger for knowledge graph processing.
Detects file changes, cleans up CSV cache, and processes files as needed.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Set
import sqlite3
import csv as csv_module
from rich.console import Console

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from file_tracker import FileTracker, ChangeType, FileChange
from step1_extract import Step1Extractor
from step2_organize import Step2Organizer
from step3_build import Step3Builder
from entity_resolution import EntityResolver
from metadata_extractor import MetadataExtractor

console = Console()

class ManualTrigger:
    def __init__(self, vault_path: Path, server_manager=None):
        self.vault_path = Path(vault_path)
        self.file_tracker = FileTracker(self.vault_path)
        self.server_manager = server_manager
        self.entity_resolver = EntityResolver(self.vault_path)
        self.metadata_extractor = MetadataExtractor(self.vault_path)
        self.content_dir = self.vault_path / ".kineviz_graph" / "cache" / "content"
        self.db_input_dir = self.vault_path / ".kineviz_graph" / "cache" / "db_input"
        self.database_dir = self.vault_path / ".kineviz_graph" / "database"
        
        # Ensure directories exist
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.db_input_dir.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
    
    def detect_changes(self) -> tuple[List[FileChange], List[Path]]:
        """Detect file changes and return changes and files to process"""
        console.print("[cyan]Detecting file changes...[/cyan]")
        
        changes, files_to_process = self.file_tracker.scan_vault()
        
        console.print(f"[green]Detected {len(changes)} changes, {len(files_to_process)} files to process[/green]")
        
        # Print summary of changes
        for change in changes:
            if change.change_type == ChangeType.CREATED:
                console.print(f"[green]  + Created: {change.new_path}[/green]")
            elif change.change_type == ChangeType.MODIFIED:
                console.print(f"[yellow]  ~ Modified: {change.new_path}[/yellow]")
            elif change.change_type == ChangeType.DELETED:
                console.print(f"[red]  - Deleted: {change.old_path}[/red]")
            elif change.change_type == ChangeType.MOVED:
                console.print(f"[blue]  → Moved: {change.old_path} → {change.new_path}[/blue]")
        
        return changes, files_to_process
    
    def cleanup_csv_cache(self):
        """Clean up orphaned CSV files that don't correspond to existing markdown files"""
        console.print("[cyan]Cleaning up CSV cache...[/cyan]")
        
        # Get all markdown files in vault
        vault_files = set()
        for md_file in self.vault_path.rglob("*.md"):
            # Skip files in hidden directories (starting with .)
            if any(part.startswith('.') for part in md_file.relative_to(self.vault_path).parts):
                continue
            vault_files.add(str(md_file.relative_to(self.vault_path)))
        
        # Get all CSV files and check which ones are orphaned
        orphaned_csvs = []
        for csv_file in self.content_dir.glob("*.csv"):
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    has_valid_source = False
                    for row in reader:
                        if 'source_file' in row and row['source_file']:
                            source_file = row['source_file'].strip()
                            if source_file:
                                # Convert to relative path if needed
                                if not Path(source_file).is_absolute():
                                    rel_path = source_file
                                else:
                                    rel_path = str(Path(source_file).relative_to(self.vault_path))
                                
                                if rel_path in vault_files:
                                    has_valid_source = True
                                    break
                    
                    # If no valid source file found, mark as orphaned
                    if not has_valid_source:
                        orphaned_csvs.append(csv_file)
            except Exception as e:
                console.print(f"[yellow]Could not read CSV file {csv_file.name}: {e}[/yellow]")
                continue
        
        # Remove orphaned CSV files
        for csv_file in orphaned_csvs:
            console.print(f"[red]Removing orphaned CSV: {csv_file.name}[/red]")
            csv_file.unlink()
        
        if orphaned_csvs:
            console.print(f"[green]Cleaned up {len(orphaned_csvs)} orphaned CSV files[/green]")
        else:
            console.print("[green]No orphaned CSV files found[/green]")
    
    def process_files(self, files_to_process: List[Path]):
        """Process files that need updating"""
        if not files_to_process:
            console.print("[green]No files need processing[/green]")
            return
        
        console.print(f"[cyan]Processing {len(files_to_process)} files...[/cyan]")
        
        # Create extractor instance
        extractor = Step1Extractor(
            vault_path=self.vault_path,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            chunking_backend="recursive-markdown",
            chunk_threshold=0.75,
            chunk_size=1024,
            embedding_model="minishlab/potion-base-8M",
        )
        
        # Process each file
        for file_path in files_to_process:
            try:
                console.print(f"[cyan]Processing: {file_path.relative_to(self.vault_path)}[/cyan]")
                
                # Process the file synchronously
                import threading
                import asyncio
                
                def run_async():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(extractor._process_file(file_path))
                        return result
                    except Exception as e:
                        console.print(f"[red]Error processing {file_path.name}: {e}[/red]")
                        return None
                    finally:
                        try:
                            pending = asyncio.all_tasks(loop)
                            for task in pending:
                                task.cancel()
                            if pending:
                                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception as e:
                            console.print(f"[yellow]Warning during cleanup: {e}[/yellow]")
                        finally:
                            loop.close()
                
                # Run in a separate thread
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                console.print(f"[green]✓ Processed: {file_path.name}[/green]")
                
            except Exception as e:
                console.print(f"[red]Error processing {file_path.name}: {e}[/red]")
    
    def organize_cache(self):
        """Organize cache from content to db_input"""
        console.print("[cyan]Organizing cache...[/cyan]")
        
        organizer = Step2Organizer(self.vault_path)
        organizer.organize_cache()
        
        console.print("[green]✓ Cache organized[/green]")
    
    def extract_metadata(self):
        """Extract metadata from linked markdown files"""
        console.print("[cyan]Extracting metadata from linked files...[/cyan]")
        
        try:
            # Extract metadata for all nodes
            metadata_results = self.metadata_extractor.extract_metadata_for_nodes()
            
            if not metadata_results:
                console.print("[yellow]No metadata found[/yellow]")
                return
            
            # Update database with metadata
            self.metadata_extractor.update_database_with_metadata(metadata_results)
            console.print("[green]✓ Metadata extracted and updated[/green]")
            
        except Exception as e:
            console.print(f"[red]Error during metadata extraction: {e}[/red]")
            # Don't fail the entire process for metadata extraction errors
            console.print("[yellow]Continuing without metadata extraction...[/yellow]")
    
    def apply_entity_resolution(self):
        """Apply entity resolution to CSV files"""
        console.print("[cyan]Applying entity resolution...[/cyan]")
        
        try:
            # Detect entity resolution patterns
            file_mappings = self.entity_resolver.detect_rename_patterns()
            
            if not file_mappings:
                console.print("[yellow]No entity resolution patterns found[/yellow]")
                return
            
            # Apply scoped resolution
            self.entity_resolver.apply_scoped_resolution(file_mappings)
            console.print("[green]✓ Entity resolution applied[/green]")
            
        except Exception as e:
            console.print(f"[red]Error during entity resolution: {e}[/red]")
            # Don't fail the entire process for entity resolution errors
            console.print("[yellow]Continuing without entity resolution...[/yellow]")
    
    def build_database(self):
        """Build Kuzu database from organized cache"""
        import time
        
        console.print("[cyan]Building database in separate process...[/cyan]")
        build_start_time = time.time()
        
        # Stop Kuzu server before building database
        if self.server_manager:
            console.print("[cyan]Stopping Kuzu server for database rebuild...[/cyan]")
            try:
                # Force stop the server
                self.server_manager.stop_server()
                # Wait a moment for the server to fully stop
                import time
                time.sleep(2)
                console.print("[green]Kuzu server stopped[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not stop server gracefully: {e}[/yellow]")
                # Try to kill the process if it exists
                try:
                    if hasattr(self.server_manager, 'process') and self.server_manager.process:
                        self.server_manager.process.terminate()
                        time.sleep(1)
                        if self.server_manager.process.poll() is None:
                            self.server_manager.process.kill()
                except Exception as e2:
                    console.print(f"[yellow]Warning: Could not kill server process: {e2}[/yellow]")
        
        # Clear any existing database and lock files
        db_path = str(self.database_dir / "knowledge_graph.kz")
        if Path(db_path).exists():
            console.print("[cyan]Clearing existing database for clean rebuild...[/cyan]")
            import shutil
            try:
                if Path(db_path).is_dir():
                    shutil.rmtree(db_path)
                else:
                    Path(db_path).unlink()
                console.print("[green]Database cleared successfully[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not clear database: {e}[/yellow]")
        
        # Also clear any lock files and temporary files that might exist
        lock_files = list(self.database_dir.glob("*.lock"))
        for lock_file in lock_files:
            try:
                lock_file.unlink()
                console.print(f"[cyan]Removed lock file: {lock_file.name}[/cyan]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not remove lock file {lock_file.name}: {e}[/yellow]")
        
        # Clear any temporary or cache files that might be holding locks
        temp_files = list(self.database_dir.glob("*"))
        for temp_file in temp_files:
            if temp_file.is_file() and temp_file.suffix in ['.tmp', '.temp', '.pid']:
                try:
                    temp_file.unlink()
                    console.print(f"[cyan]Removed temp file: {temp_file.name}[/cyan]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not remove temp file {temp_file.name}: {e}[/yellow]")
        
        # Wait a moment to ensure all file handles are released
        import time
        time.sleep(1)
        
        # Build database in a separate process to avoid Kuzu cleanup issues
        console.print("[cyan]Building database in separate process...[/cyan]")
        import subprocess
        import sys
        
        try:
            # Use the standalone build script
            script_path = Path(__file__).parent / "build_database_standalone.py"
            
            # Run the script in a separate process
            result = subprocess.run([
                sys.executable, str(script_path),
                "--vault-path", str(self.vault_path),
                "--db-path", db_path
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode == 0:
                console.print("[green]Database built successfully in separate process[/green]")
            else:
                console.print(f"[red]Database build failed: {result.stderr}[/red]")
                # Fallback to in-process build
                console.print("[yellow]Falling back to in-process build...[/yellow]")
                builder = Step3Builder(self.vault_path, db_path)
                builder.build_database()
                
        except subprocess.TimeoutExpired:
            console.print("[red]Database build timed out, falling back to in-process build...[/red]")
            builder = Step3Builder(self.vault_path, db_path)
            builder.build_database()
        except Exception as e:
            console.print(f"[red]Error building database in separate process: {e}[/red]")
            console.print("[yellow]Falling back to in-process build...[/yellow]")
            builder = Step3Builder(self.vault_path, db_path)
            builder.build_database()
        
        # Restart Kuzu server after building database
        if self.server_manager:
            console.print("[cyan]Restarting Kuzu server...[/cyan]")
            try:
                # Wait longer to ensure database is fully written and all handles are released
                import time
                time.sleep(3)
                
                # Try to start the server
                if self.server_manager.start_server(force_restart=True):
                    # Wait longer for server to fully start
                    time.sleep(5)
                    if self.server_manager.is_server_healthy():
                        console.print(f"[green]Kuzu server restarted at {self.server_manager.get_server_url()}[/green]")
                    else:
                        console.print("[yellow]Kuzu server started but not yet healthy[/yellow]")
                else:
                    console.print("[red]Failed to restart Kuzu server[/red]")
            except Exception as e:
                console.print(f"[red]Error restarting Kuzu server: {e}[/red]")
                # Try one more time after a longer delay
                try:
                    console.print("[cyan]Retrying server start after longer delay...[/cyan]")
                    time.sleep(5)
                    if self.server_manager.start_server(force_restart=True):
                        time.sleep(3)
                        if self.server_manager.is_server_healthy():
                            console.print("[green]Kuzu server started on retry[/green]")
                        else:
                            console.print("[yellow]Kuzu server started on retry but not healthy[/yellow]")
                    else:
                        console.print("[red]Failed to restart server on retry[/red]")
                except Exception as e2:
                    console.print(f"[red]Failed to restart server on retry: {e2}[/red]")
                    # Final attempt - clear database and try again
                    try:
                        console.print("[cyan]Final attempt - clearing database and retrying...[/cyan]")
                        if Path(db_path).exists():
                            import shutil
                            if Path(db_path).is_dir():
                                shutil.rmtree(db_path)
                            else:
                                Path(db_path).unlink()
                        time.sleep(2)
                        if self.server_manager.start_server(force_restart=True):
                            console.print("[green]Kuzu server started on final attempt[/green]")
                        else:
                            console.print("[red]Failed to restart server on final attempt[/red]")
                    except Exception as e3:
                        console.print(f"[red]Failed to restart server on final attempt: {e3}[/red]")
        
        build_total_time = time.time() - build_start_time
        console.print(f"[green]✓ Database built in {build_total_time:.2f}s[/green]")
    
    def run_full_cycle(self):
        """Run the complete processing cycle"""
        console.print("[bold blue]Starting manual trigger processing...[/bold blue]")
        
        start_time = time.time()
        
        # Step 1: Detect changes
        changes, files_to_process = self.detect_changes()
        
        # Step 2: Clean up CSV cache
        self.cleanup_csv_cache()
        
        # Step 3: Process files if needed
        if files_to_process:
            self.process_files(files_to_process)
        
        # Step 4: Apply entity resolution
        self.apply_entity_resolution()
        
        # Step 5: Organize cache
        self.organize_cache()
        
        # Step 6: Extract metadata
        self.extract_metadata()
        
        # Step 7: Build database
        self.build_database()
        
        end_time = time.time()
        duration = end_time - start_time
        
        console.print(f"[bold green]✓ Processing completed in {duration:.2f} seconds[/bold green]")
        
        # Summary
        console.print(f"[cyan]Summary:[/cyan]")
        console.print(f"  - Changes detected: {len(changes)}")
        console.print(f"  - Files processed: {len(files_to_process)}")
        console.print(f"  - Processing time: {duration:.2f}s")

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manual trigger for knowledge graph processing")
    parser.add_argument("--vault-path", required=True, help="Path to the Obsidian vault")
    parser.add_argument("--detect-only", action="store_true", help="Only detect changes, don't process")
    parser.add_argument("--cleanup-only", action="store_true", help="Only clean up CSV cache")
    parser.add_argument("--process-only", action="store_true", help="Only process files (skip detection)")
    
    args = parser.parse_args()
    
    vault_path = Path(args.vault_path)
    if not vault_path.exists():
        console.print(f"[red]Vault path does not exist: {vault_path}[/red]")
        sys.exit(1)
    
    trigger = ManualTrigger(vault_path)
    
    if args.cleanup_only:
        trigger.cleanup_csv_cache()
    elif args.process_only:
        # Get all files that need processing
        _, files_to_process = trigger.detect_changes()
        trigger.process_files(files_to_process)
        trigger.organize_cache()
        trigger.build_database()
    elif args.detect_only:
        trigger.detect_changes()
    else:
        trigger.run_full_cycle()

if __name__ == "__main__":
    main()
