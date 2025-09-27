#!/usr/bin/env python3
"""
Step 4: Monitor daemon for vault file changes
This step watches the Obsidian vault for markdown file changes and automatically updates the knowledge graph.
"""

import asyncio
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Set

import click
from dotenv import load_dotenv
from rich.console import Console
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from kuzu_server_manager import KuzuServerManager
from file_tracker import FileTracker, ChangeType
from manual_trigger import ManualTrigger
from obsidian_config_reader import ObsidianConfigReader

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()


class VaultFileHandler(FileSystemEventHandler):
    """Handle file system events for markdown files in the vault"""
    
    def __init__(self, vault_path: Path, monitor: 'VaultMonitor'):
        self.vault_path = vault_path
        self.monitor = monitor
        self.pending_changes: Set[Path] = set()
        self.last_processed = 0
        self.debounce_delay = 60.0  # Wait 60 seconds before processing changes
        self.processing_scheduled = False
        self.debounce_timer: Optional[threading.Timer] = None
        
        # Initialize Obsidian config reader for template folder exclusion
        self.obsidian_config = ObsidianConfigReader(vault_path)
        self.template_folder = self._get_template_folder()
    
    def _get_template_folder(self) -> Optional[str]:
        """Get template folder path from Obsidian configuration"""
        if self.obsidian_config.is_templates_enabled():
            template_folder = self.obsidian_config.get_template_folder()
            if template_folder:
                console.print(f"[cyan]Templates enabled, excluding folder: {template_folder}[/cyan]")
            return template_folder
        return None
        
    def should_process_file(self, file_path: Path) -> bool:
        """Check if a file should be processed"""
        # Only process markdown files
        if not file_path.suffix.lower() == '.md':
            return False
            
        # Must be within the vault directory
        try:
            relative_path = file_path.relative_to(self.vault_path)
        except ValueError:
            return False
            
        # Skip hidden directories
        if any(part.startswith('.') for part in relative_path.parts):
            return False
        
        # Skip files in template folder if templates are enabled
        if self.template_folder:
            if str(relative_path).startswith(self.template_folder + "/"):
                console.print(f"[yellow]Skipping template file: {relative_path}[/yellow]")
                return False
            
        return True
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if self.should_process_file(file_path):
            # Use FileTracker to handle the change
            self.handle_file_change(file_path, "modified")
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if self.should_process_file(file_path):
            # Use FileTracker to handle the change
            self.handle_file_change(file_path, "created")
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if self.should_process_file(file_path):
            # Use FileTracker to handle the change
            self.handle_file_change(file_path, "deleted")
    
    def on_moved(self, event):
        """Handle file move/rename events"""
        if event.is_directory:
            return
            
        src_path = Path(event.src_path)
        dest_path = Path(event.dest_path)
        
        # Only process if the destination file should be processed
        if self.should_process_file(dest_path):
            console.print(f"[blue]File moved: {src_path.name} -> {dest_path.name}[/blue]")
            # Use FileTracker to handle the move
            self.handle_file_move(src_path, dest_path)
    
    def handle_file_change(self, file_path: Path, change_type: str):
        """Handle file changes using FileTracker"""
        try:
            # Add the specific file to pending changes for immediate processing
            self.pending_changes.add(file_path)
            console.print(f"[cyan]File {change_type}: {file_path.name}[/cyan]")
            console.print(f"[cyan]Added to pending changes: {len(self.pending_changes)} files pending[/cyan]")
            self.schedule_processing()
        except Exception as e:
            console.print(f"[red]Error handling file change: {e}[/red]")
    
    def handle_file_move(self, src_path: Path, dest_path: Path):
        """Handle file moves using FileTracker"""
        try:
            console.print(f"[blue]File moved: {src_path.name} -> {dest_path.name}[/blue]")
            # Handle the file move immediately
            self.monitor.handle_file_move_sync(src_path, dest_path)
            # Also add to pending changes for processing
            self.pending_changes.add(dest_path)
            console.print(f"[cyan]Added to pending changes: {len(self.pending_changes)} files pending[/cyan]")
            self.schedule_processing()
        except Exception as e:
            console.print(f"[red]Error handling file move: {e}[/red]")
    
    def schedule_processing(self):
        """Schedule processing of pending changes after debounce delay"""
        # Cancel existing timer if one is running
        if self.debounce_timer and self.debounce_timer.is_alive():
            self.debounce_timer.cancel()
            console.print("[yellow]Rescheduling processing due to new changes...[/yellow]")
        
        # Schedule new processing
        self.processing_scheduled = True
        console.print(f"[cyan]Scheduling processing in {self.debounce_delay} seconds...[/cyan]")
        self.debounce_timer = threading.Timer(self.debounce_delay, self._process_scheduled)
        self.debounce_timer.start()
    
    def _process_scheduled(self):
        """Process scheduled changes and reset the flag"""
        self.processing_scheduled = False
        self.monitor.process_pending_changes_sync()
    
    def update_file_path_in_cache(self, old_path: Path, new_path: Path):
        """Update file paths in cached CSV files when a file is moved/renamed"""
        try:
            updated_count = 0
            old_path_str = str(old_path)
            new_path_str = str(new_path)
            
            # Update all CSV files in the content cache
            for csv_file in self.monitor.content_dir.glob("*.csv"):
                try:
                    import csv as csv_module
                    import io
                    
                    # Read the CSV file
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check if this CSV contains the old path
                    if old_path_str in content:
                        # Parse CSV, update paths, and write back
                        f = io.StringIO(content)
                        reader = csv_module.DictReader(f)
                        rows = list(reader)
                        
                        # Update source_file column
                        for row in rows:
                            if row.get('source_file') == old_path_str:
                                row['source_file'] = new_path_str
                        
                        # Write back the updated CSV
                        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                            if rows:
                                writer = csv_module.DictWriter(f, fieldnames=rows[0].keys())
                                writer.writeheader()
                                writer.writerows(rows)
                        
                        updated_count += 1
                        console.print(f"[yellow]Updated path in cache file: {csv_file.name}[/yellow]")
                        
                except Exception as e:
                    console.print(f"[yellow]Could not update {csv_file.name}: {e}[/yellow]")
                    continue
            
            if updated_count > 0:
                console.print(f"[green]Updated {updated_count} cache files for moved file: {old_path.name} -> {new_path.name}[/green]")
            else:
                console.print(f"[yellow]No cache files found for moved file: {old_path.name}[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error updating cache for moved file {old_path.name}: {e}[/red]")
    
    async def process_pending_changes(self):
        """Process all pending file changes"""
        if not self.pending_changes:
            console.print("[yellow]No pending changes to process[/yellow]")
            return
            
        self.last_processed = time.time()
        changes = self.pending_changes.copy()
        self.pending_changes.clear()
        
        console.print(f"[cyan]Processing {len(changes)} file changes...[/cyan]")
        for file_path in changes:
            console.print(f"[cyan]  - {file_path}[/cyan]")
        
        # Process each changed file
        for file_path in changes:
            if file_path.exists():
                # File exists - process it
                console.print(f"[green]Processing file: {file_path}[/green]")
                await self.monitor.process_single_file(file_path)
            else:
                # File was deleted - remove from cache
                console.print(f"[red]File deleted: {file_path}[/red]")
                await self.monitor.remove_file_from_cache(file_path)
        
        # Reorganize and rebuild database
        console.print("[cyan]Rebuilding database...[/cyan]")
        await self.monitor.reorganize_and_rebuild()


class VaultMonitor:
    """Monitor daemon for Obsidian vault changes using FileTracker"""
    
    def __init__(self, vault_path: Path, max_concurrent: int = 5, server_port: int = 7001):
        self.vault_path = vault_path
        self.max_concurrent = max_concurrent
        self.kineviz_dir = vault_path / ".kineviz_graph"
        self.cache_dir = self.kineviz_dir / "cache"
        self.content_dir = self.cache_dir / "content"
        self.db_input_dir = self.cache_dir / "db_input"
        self.database_dir = self.kineviz_dir / "database"
        self.db_path = str(self.database_dir / "knowledge_graph.kz")
        
        # Ensure directories exist
        for dir_path in [self.kineviz_dir, self.cache_dir, self.content_dir, self.db_input_dir, self.database_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize file tracker
        self.file_tracker = FileTracker(vault_path)
        
        # Initialize manual trigger for processing
        self.manual_trigger = None  # Will be initialized after server_manager
        
        # Initialize Kuzu server manager
        self.server_manager = KuzuServerManager(
            db_path=str(self.db_path),
            port=server_port
        )
        
        # Initialize manual trigger with server manager
        self.manual_trigger = ManualTrigger(vault_path, self.server_manager)
        
        self.observer = None
        self.handler = None
        self.running = False
        self.processing_lock = threading.Lock()
        self.is_processing = False
        
    async def process_single_file(self, file_path: Path):
        """Process a single markdown file with full pipeline including metadata extraction"""
        try:
            # Check if file should be processed first
            if not self.should_process_file(file_path):
                console.print(f"[yellow]Skipping file: {file_path.name}[/yellow]")
                return
            
            console.print(f"[cyan]Processing single file: {file_path.name}[/cyan]")
            
            # Use manual trigger to run the full processing pipeline
            # This ensures metadata extraction and all other steps are included
            self.manual_trigger.run_full_cycle()
            
            console.print(f"[green]Processed: {file_path.name}[/green]")
            
        except Exception as e:
            console.print(f"[red]Error processing {file_path.name}: {e}[/red]")
    
    async def remove_file_from_cache(self, file_path: Path):
        """Remove a deleted file from cache"""
        try:
            # Find CSV files that contain this file path in their content
            removed_count = 0
            for csv_file in self.content_dir.glob("*.csv"):
                try:
                    # Read the CSV file to check if it contains the deleted file path
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if str(file_path) in content:
                            csv_file.unlink()
                            removed_count += 1
                            console.print(f"[yellow]Removed cache file: {csv_file.name}[/yellow]")
                except Exception as e:
                    console.print(f"[yellow]Could not read {csv_file.name}: {e}[/yellow]")
                    continue
            
            if removed_count > 0:
                console.print(f"[green]Removed {removed_count} cache files for deleted file: {file_path.name}[/green]")
            else:
                console.print(f"[yellow]No cache files found for deleted file: {file_path.name}[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error removing cache for {file_path.name}: {e}[/red]")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        import hashlib
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    async def reorganize_and_rebuild(self):
        """Reorganize cache and rebuild database"""
        try:
            # Stop Kuzu server before rebuilding database
            if self.server_manager.is_server_healthy():
                console.print("[cyan]Stopping Kuzu server for database rebuild...[/cyan]")
                self.server_manager.stop_server()
            
            # Step 2: Organize cache
            from step2_organize import Step2Organizer
            organizer = Step2Organizer(self.vault_path)
            organizer.organize_cache()
            console.print("[green]Cache reorganized[/green]")
            
            # Step 3: Rebuild database (clear and rebuild)
            from step3_build import Step3Builder
            db_path = str(self.database_dir / "knowledge_graph.kz")
            
            # Delete existing database to ensure clean rebuild
            if Path(db_path).exists():
                import shutil
                if Path(db_path).is_dir():
                    shutil.rmtree(db_path)
                else:
                    Path(db_path).unlink()
                console.print("[yellow]Cleared existing database[/yellow]")
            
            builder = Step3Builder(self.vault_path, db_path)
            try:
                builder.build_database()
                console.print("[green]Database rebuilt[/green]")
            finally:
                builder.cleanup()
            
            # Restart Kuzu server after database rebuild
            console.print("[cyan]Restarting Kuzu server...[/cyan]")
            if self.server_manager.start_server(force_restart=True):
                console.print(f"[green]Kuzu server restarted at {self.server_manager.get_server_url()}[/green]")
            else:
                console.print("[red]Failed to restart Kuzu server[/red]")
            
        except Exception as e:
            console.print(f"[red]Error reorganizing/rebuilding: {e}[/red]")
            # Try to restart server even if rebuild failed
            if not self.server_manager.is_server_healthy():
                console.print("[cyan]Attempting to restart Kuzu server...[/cyan]")
                self.server_manager.start_server()
    
    def process_pending_changes_sync(self):
        """Process pending changes using manual trigger"""
        with self.processing_lock:
            if self.is_processing:
                console.print("[yellow]Processing already in progress, skipping...[/yellow]")
                return
                
            if not self.handler or not self.handler.pending_changes:
                console.print("[yellow]No pending changes to process (sync)[/yellow]")
                return
                
            self.is_processing = True
            try:
                self.handler.last_processed = time.time()
                changes = self.handler.pending_changes.copy()
                self.handler.pending_changes.clear()
                
                console.print(f"[cyan]Processing {len(changes)} file changes using manual trigger...[/cyan]")
                for file_path in changes:
                    console.print(f"[cyan]  - {file_path}[/cyan]")
                
                # Use manual trigger to process changes
                self.manual_trigger.run_full_cycle()
                
                console.print("[green]✓ Processing completed successfully[/green]")
                
            except Exception as e:
                console.print(f"[red]Error during processing: {e}[/red]")
            finally:
                self.is_processing = False
    
    # Old processing methods removed - now using manual_trigger
    
    def remove_file_from_cache_sync(self, file_path: Path):
        """Synchronous version of remove_file_from_cache"""
        try:
            # Find CSV files that contain this file path in their content
            removed_count = 0
            for csv_file in self.content_dir.glob("*.csv"):
                try:
                    # Read the CSV file to check if it contains the deleted file path
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if str(file_path) in content:
                            csv_file.unlink()
                            removed_count += 1
                            console.print(f"[yellow]Removed cache file: {csv_file.name}[/yellow]")
                except Exception as e:
                    console.print(f"[yellow]Could not read {csv_file.name}: {e}[/yellow]")
                    continue
            
            if removed_count > 0:
                console.print(f"[green]Removed {removed_count} cache files for deleted file: {file_path.name}[/green]")
            else:
                console.print(f"[yellow]No cache files found for deleted file: {file_path.name}[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error removing cache for {file_path.name}: {e}[/red]")
    
    def convert_absolute_paths_to_relative(self):
        """Convert absolute paths in CSV files to relative paths"""
        console.print("[cyan]Converting absolute paths to relative paths in cache files...[/cyan]")
        
        converted_count = 0
        for csv_file in self.content_dir.glob("*.csv"):
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check if file contains absolute paths
                if str(self.vault_path) in content:
                    # Replace absolute paths with relative paths
                    relative_content = content.replace(str(self.vault_path) + '/', '')
                    relative_content = relative_content.replace(str(self.vault_path), '')
                    
                    # Write back the updated content
                    with open(csv_file, 'w', encoding='utf-8') as f:
                        f.write(relative_content)
                    
                    converted_count += 1
                    console.print(f"[yellow]Converted paths in: {csv_file.name}[/yellow]")
                    
            except Exception as e:
                console.print(f"[yellow]Could not convert {csv_file.name}: {e}[/yellow]")
                continue
        
        if converted_count > 0:
            console.print(f"[green]Converted {converted_count} cache files to use relative paths[/green]")
        else:
            console.print("[green]All cache files already use relative paths[/green]")

    def validate_and_process_changes(self):
        """Use manual trigger to detect and process file changes"""
        console.print("[cyan]Running startup validation using manual trigger...[/cyan]")
        
        try:
            # Check if database exists, if not, run full build process
            db_path = self.vault_path / ".kineviz_graph" / "database" / "knowledge_graph.kz"
            if not db_path.exists():
                console.print("[yellow]Database not found, running full build process...[/yellow]")
                self._run_full_build_process()
            else:
                console.print("[green]Database found, running incremental processing...[/green]")
                # Create a manual trigger without server management for validation
                from manual_trigger import ManualTrigger
                validation_trigger = ManualTrigger(self.vault_path, None)  # No server manager
                
                # Run the full cycle without server management
                validation_trigger.run_full_cycle()
            
            console.print("[green]Startup validation completed[/green]")
                
        except Exception as e:
            console.print(f"[red]Error during startup validation: {e}[/red]")
    
    def _run_full_build_process(self):
        """Run the complete build process from scratch"""
        console.print("[cyan]Running full build process...[/cyan]")
        
        # Step 1: Extract relationships
        console.print("[cyan]Step 1: Extracting relationships...[/cyan]")
        from step1_extract import Step1Extractor
        extractor = Step1Extractor(self.vault_path)
        asyncio.run(extractor.process_vault())
        
        # Step 2: Organize cache
        console.print("[cyan]Step 2: Organizing cache...[/cyan]")
        from step2_organize import Step2Organizer
        organizer = Step2Organizer(self.vault_path)
        organizer.organize_cache()
        
        # Step 3: Build database
        console.print("[cyan]Step 3: Building database...[/cyan]")
        from step3_build import Step3Builder
        db_path = str(self.vault_path / ".kineviz_graph" / "database" / "knowledge_graph.kz")
        builder = Step3Builder(self.vault_path, db_path)
        try:
            builder.build_database()
        finally:
            # Ensure database connections are closed
            builder.cleanup()
        
        console.print("[green]Full build process completed[/green]")
    
    def handle_file_move_sync(self, old_path: Path, new_path: Path):
        """Handle file moves by updating paths in cache and database"""
        try:
            console.print(f"[cyan]Handling file move: {old_path.name} -> {new_path.name}[/cyan]")
            
            # Update FileTracker database
            self.file_tracker.update_file_path_in_db(old_path, new_path)
            
            # Update CSV files with new path
            self.update_file_path_in_cache_sync(old_path, new_path)
            
            console.print(f"[green]Successfully updated paths for moved file: {old_path.name}[/green]")
            
        except Exception as e:
            console.print(f"[red]Error handling file move {old_path.name}: {e}[/red]")
    
    def update_file_path_in_cache_sync(self, old_path: Path, new_path: Path):
        """Synchronous version of update_file_path_in_cache"""
        try:
            updated_count = 0
            old_path_str = str(old_path)
            new_path_str = str(new_path)
            
            # Update all CSV files in the content cache
            for csv_file in self.content_dir.glob("*.csv"):
                try:
                    import csv as csv_module
                    import io
                    
                    # Read the CSV file
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check if this CSV contains the old path
                    if old_path_str in content:
                        # Parse CSV, update paths, and write back
                        f = io.StringIO(content)
                        reader = csv_module.DictReader(f)
                        rows = list(reader)
                        
                        # Update source_file column
                        for row in rows:
                            if row.get('source_file') == old_path_str:
                                row['source_file'] = new_path_str
                        
                        # Write back the updated CSV
                        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                            if rows:
                                writer = csv_module.DictWriter(f, fieldnames=rows[0].keys())
                                writer.writeheader()
                                writer.writerows(rows)
                        
                        updated_count += 1
                        console.print(f"[yellow]Updated path in cache file: {csv_file.name}[/yellow]")
                        
                except Exception as e:
                    console.print(f"[yellow]Could not update {csv_file.name}: {e}[/yellow]")
                    continue
            
            if updated_count > 0:
                console.print(f"[green]Updated {updated_count} cache files for moved file: {old_path.name} -> {new_path.name}[/green]")
            else:
                console.print(f"[yellow]No cache files found for moved file: {old_path.name}[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error updating cache for moved file {old_path.name}: {e}[/red]")
    
    # Old reorganize_and_rebuild_sync method removed - now using manual_trigger
    
    def start_monitoring(self):
        """Start the file monitoring daemon"""
        if self.running:
            console.print("[yellow]Monitor is already running[/yellow]")
            return
        
        console.print(f"[cyan]Starting vault monitor for: {self.vault_path}[/cyan]")
        
        try:
            # Set up file system observer
            self.handler = VaultFileHandler(self.vault_path, self)
            self.observer = Observer()
            self.observer.schedule(self.handler, str(self.vault_path), recursive=True)
            
            # Start monitoring
            self.observer.start()
            self.running = True
            
            console.print("[green]Vault monitor started successfully![/green]")
            console.print("[cyan]Watching for markdown file changes...[/cyan]")
            console.print("[yellow]Press Ctrl+C to stop[/yellow]")
            
            # Run initial validation after monitoring is started
            console.print("[cyan]Running initial validation...[/cyan]")
            self.validate_and_process_changes()
            
            # Start Kuzu server after database is built
            console.print("[cyan]Starting Kuzu Neo4j server...[/cyan]")
            if self.server_manager.start_server(force_restart=True):
                console.print(f"[green]Kuzu server started at {self.server_manager.get_server_url()}[/green]")
            else:
                console.print("[yellow]Failed to start Kuzu server, continuing without it[/yellow]")
            
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop_monitoring()
        except Exception as e:
            console.print(f"[red]Error starting monitor: {e}[/red]")
            self.running = False
    
    def stop_monitoring(self):
        """Stop the file monitoring daemon"""
        if not self.running:
            console.print("[yellow]Monitor is not running[/yellow]")
            return
        
        console.print("\n[yellow]Stopping vault monitor...[/yellow]")
        
        # Cancel any pending debounce timer
        if self.handler and self.handler.debounce_timer and self.handler.debounce_timer.is_alive():
            self.handler.debounce_timer.cancel()
            console.print("[yellow]Cancelled pending processing[/yellow]")
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        # Stop Kuzu server
        console.print("[cyan]Stopping Kuzu server...[/cyan]")
        self.server_manager.stop_server()
        
        self.running = False
        console.print("[green]Vault monitor stopped[/green]")


@click.command()
@click.option("--vault-path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
              default=lambda: os.getenv("VAULT_PATH"), 
              help="Path to Obsidian vault (default: VAULT_PATH env var)")
@click.option("--max-concurrent", default=lambda: int(os.getenv("MAX_CONCURRENT", "5")), 
              type=int,
              help="Maximum number of concurrent file processing tasks (default: MAX_CONCURRENT env var or 5)")
@click.option("--server-port", default=lambda: int(os.getenv("SERVER_PORT", "7001")), 
              type=int,
              help="Port for Kuzu Neo4j server (default: SERVER_PORT env var or 7001)")
@click.option("--daemon", is_flag=True, help="Run as daemon (detached from terminal)")
def main(vault_path: Path, max_concurrent: int, server_port: int, daemon: bool):
    """Step 4: Monitor Obsidian vault for changes and auto-update knowledge graph"""
    
    # Validate vault path
    if not vault_path:
        console.print("[red]Error: Vault path is required. Set VAULT_PATH environment variable or use --vault-path[/red]")
        console.print("[yellow]Example: uv run step4_monitor.py --vault-path '/path/to/vault'[/yellow]")
        console.print("[yellow]Or set VAULT_PATH in your .env file[/yellow]")
        sys.exit(1)
    
    if not vault_path.exists():
        console.print(f"[red]Error: Vault path does not exist: {vault_path}[/red]")
        sys.exit(1)
    
    # Validate it's a valid Obsidian vault
    obsidian_config = vault_path / ".obsidian"
    if not obsidian_config.exists():
        console.print(f"[yellow]Warning: {vault_path} doesn't appear to be an Obsidian vault (no .obsidian directory)[/yellow]")
        console.print("Continuing anyway...")
    
    # Create monitor instance
    monitor = VaultMonitor(vault_path, max_concurrent, server_port)
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        console.print(f"\n[yellow]Received signal {signum}, shutting down...[/yellow]")
        monitor.stop_monitoring()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if daemon:
        # TODO: Implement proper daemon mode with PID file
        console.print("[yellow]Daemon mode not yet implemented, running in foreground[/yellow]")
    
    # Start monitoring
    monitor.start_monitoring()


if __name__ == "__main__":
    main()
