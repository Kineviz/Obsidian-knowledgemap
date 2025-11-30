#!/usr/bin/env python3
"""
File tracking system using SQLite database for reliable file change detection
"""

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from obsidian_config_reader import ObsidianConfigReader

console = Console()


class FileStatus(Enum):
    ACTIVE = "active"
    MOVED = "moved"
    DELETED = "deleted"


class ChangeType(Enum):
    CREATED = "created"
    MODIFIED = "modified"
    MOVED = "moved"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileMetadata:
    """File metadata for tracking"""
    id: Optional[int] = None
    current_path: str = ""
    original_path: Optional[str] = None
    file_name: str = ""
    file_size: int = 0
    modification_time: float = 0.0
    content_hash: str = ""
    status: FileStatus = FileStatus.ACTIVE
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class FileChange:
    """File change record"""
    id: Optional[int] = None
    file_id: int = 0
    change_type: ChangeType = ChangeType.CREATED
    old_path: Optional[str] = None
    new_path: Optional[str] = None
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    timestamp: float = 0.0


class FileTracker:
    """File tracking system using SQLite database"""
    
    def __init__(self, vault_path: Path, db_path: Optional[Path] = None):
        self.vault_path = vault_path
        self.db_path = db_path or vault_path / ".kineviz_graph" / "file_tracking.db"
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize Obsidian config reader for template exclusion
        self.obsidian_config = ObsidianConfigReader(vault_path)
        self.template_folder = self._get_template_folder()
        
        # Initialize database
        self._init_database()
    
    def _get_template_folder(self) -> Optional[str]:
        """Get template folder path from Obsidian configuration"""
        if self.obsidian_config.is_templates_enabled():
            template_folder = self.obsidian_config.get_template_folder()
            if template_folder:
                console.print(f"[cyan]Templates enabled, excluding folder: {template_folder}[/cyan]")
            return template_folder
        return None
    
    def _init_database(self):
        """Initialize the SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # File tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    current_path TEXT UNIQUE NOT NULL,
                    original_path TEXT,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    modification_time REAL,
                    content_hash TEXT,
                    status TEXT CHECK(status IN ('active', 'moved', 'deleted')) DEFAULT 'active',
                    processed_at REAL,
                    has_relationships INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (julianday('now')),
                    updated_at REAL DEFAULT (julianday('now'))
                )
            """)
            
            # File change history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER REFERENCES file_tracking(id),
                    change_type TEXT CHECK(change_type IN ('created', 'modified', 'moved', 'deleted', 'renamed')) NOT NULL,
                    old_path TEXT,
                    new_path TEXT,
                    old_hash TEXT,
                    new_hash TEXT,
                    timestamp REAL DEFAULT (julianday('now'))
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_tracking_path ON file_tracking(current_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_tracking_hash ON file_tracking(content_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_tracking_status ON file_tracking(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_changes_file_id ON file_changes(file_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_changes_timestamp ON file_changes(timestamp)")
            
            conn.commit()
    
    def _parse_frontmatter(self, content: str) -> str:
        """Extract content only, excluding YAML frontmatter.
        
        Frontmatter is the YAML block at the start of the file between --- markers.
        We exclude it because frontmatter changes don't affect relationship extraction.
        """
        if not content.startswith('---'):
            return content
        
        lines = content.split('\n')
        if len(lines) < 2:
            return content
        
        # Find the end of frontmatter (second ---)
        end_idx = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_idx = i
                break
        
        if end_idx is None:
            return content
        
        # Return content after frontmatter
        return '\n'.join(lines[end_idx + 1:]).strip()
    
    def _calculate_content_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content (excluding frontmatter).
        
        This ensures that frontmatter-only changes don't trigger reprocessing,
        since we only extract relationships from the content body.
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            content_only = self._parse_frontmatter(content)
            return hashlib.sha256(content_only.encode('utf-8')).hexdigest()
        except Exception:
            return ""
    
    def _get_file_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """Get file metadata from filesystem"""
        try:
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            relative_path = file_path.relative_to(self.vault_path)
            
            return FileMetadata(
                current_path=str(relative_path),
                file_name=file_path.name,
                file_size=stat.st_size,
                modification_time=stat.st_mtime,
                content_hash=self._calculate_content_hash(file_path),
                created_at=time.time(),
                updated_at=time.time()
            )
        except Exception as e:
            console.print(f"[yellow]Error getting metadata for {file_path}: {e}[/yellow]")
            return None
    
    def scan_vault(self) -> Tuple[List[FileChange], List[Path]]:
        """Scan vault and detect changes compared to database state.
        
        Simplified approach: pathname-based CSV tracking means:
        - New file = needs processing (no CSV exists for its path)
        - Modified file = needs reprocessing (delete old CSV, create new)
        - Moved file = treated as delete old + create new (simpler than tracking moves)
        - Deleted file = mark in DB, orphan cleanup handles CSV
        """
        console.print("[cyan]Scanning vault for file changes...[/cyan]")
        
        # Get all markdown files in vault
        vault_files = set()
        for md_file in self.vault_path.rglob("*.md"):
            # Skip files in hidden directories
            if any(part.startswith('.') for part in md_file.relative_to(self.vault_path).parts):
                continue
            
            # Skip files in template folder if templates are enabled
            if self.template_folder:
                try:
                    relative_path = md_file.relative_to(self.vault_path)
                    if str(relative_path).startswith(self.template_folder + "/"):
                        console.print(f"[yellow]Skipping template file: {relative_path}[/yellow]")
                        continue
                except ValueError:
                    continue
            
            vault_files.add(md_file)
        
        # Get current database state
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, current_path, file_name, file_size, modification_time, content_hash, status
                FROM file_tracking 
                WHERE status = 'active'
            """)
            db_files = {row[1]: {
                'id': row[0],
                'current_path': row[1],
                'file_name': row[2],
                'file_size': row[3],
                'modification_time': row[4],
                'content_hash': row[5],
                'status': row[6]
            } for row in cursor.fetchall()}
        
        changes = []
        files_to_process = []
        
        # Convert vault files to relative paths for comparison
        vault_file_paths = {str(f.relative_to(self.vault_path)): f for f in vault_files}
        
        # Check for new files (not in DB)
        for relative_path, file_path in vault_file_paths.items():
            if relative_path not in db_files:
                # New file - add to DB and mark for processing
                metadata = self._get_file_metadata(file_path)
                if metadata:
                    file_id = self._add_file_to_db(metadata)
                    changes.append(FileChange(
                        file_id=file_id,
                        change_type=ChangeType.CREATED,
                        new_path=relative_path,
                        new_hash=metadata.content_hash,
                        timestamp=time.time()
                    ))
                    files_to_process.append(file_path)
                    console.print(f"[green]New file: {relative_path}[/green]")
            else:
                # Existing file - check if content actually changed
                db_file = db_files[relative_path]
                stat = file_path.stat()
                
                # Quick check: if mtime AND size unchanged, skip (no need to hash)
                if (stat.st_size == db_file['file_size'] and 
                    stat.st_mtime == db_file['modification_time']):
                    continue  # File hasn't changed at all
                
                # Something changed - calculate content hash to check if CONTENT changed
                content_hash = self._calculate_content_hash(file_path)
                
                if content_hash != db_file['content_hash']:
                    # Content actually changed - update DB and mark for reprocessing
                    metadata = FileMetadata(
                        current_path=relative_path,
                        file_name=file_path.name,
                        file_size=stat.st_size,
                        modification_time=stat.st_mtime,
                        content_hash=content_hash,
                        created_at=time.time(),
                        updated_at=time.time()
                    )
                    self._update_file_in_db(metadata, db_file['id'])
                    changes.append(FileChange(
                        file_id=db_file['id'],
                        change_type=ChangeType.MODIFIED,
                        old_path=relative_path,
                        new_path=relative_path,
                        old_hash=db_file['content_hash'],
                        new_hash=content_hash,
                        timestamp=time.time()
                    ))
                    # Delete the old CSV so it will be reprocessed
                    self._delete_csv_for_file(file_path)
                    files_to_process.append(file_path)
                    console.print(f"[yellow]Modified file (content changed): {relative_path}[/yellow]")
                else:
                    # Only frontmatter/metadata changed, not content - just update DB, no reprocessing
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE file_tracking 
                            SET file_size = ?, modification_time = ?, updated_at = ?
                            WHERE id = ?
                        """, (stat.st_size, stat.st_mtime, time.time(), db_file['id']))
                    console.print(f"[dim]Metadata-only change (skipping reprocess): {relative_path}[/dim]")
        
        # Check for unprocessed files (no corresponding CSV)
        unprocessed_files = self._find_unprocessed_files(vault_file_paths)
        for file_path in unprocessed_files:
            if file_path not in files_to_process:  # Avoid duplicates
                files_to_process.append(file_path)
                console.print(f"[blue]Unprocessed file: {file_path.relative_to(self.vault_path)}[/blue]")
        
        # Check for deleted files
        for relative_path, db_file in db_files.items():
            if relative_path not in vault_file_paths:
                # File deleted - mark in DB
                self._mark_file_deleted(db_file['id'])
                changes.append(FileChange(
                    file_id=db_file['id'],
                    change_type=ChangeType.DELETED,
                    old_path=relative_path,
                    timestamp=time.time()
                ))
                console.print(f"[red]Deleted file: {relative_path}[/red]")
        
        # Record all changes
        self._record_changes(changes)
        
        console.print(f"[cyan]Detected {len(changes)} changes, {len(files_to_process)} files to process[/cyan]")
        return changes, files_to_process
    
    def _delete_csv_for_file(self, file_path: Path) -> None:
        """Delete the CSV file for a given markdown file (to trigger reprocessing)."""
        try:
            relative_path = file_path.relative_to(self.vault_path)
            csv_name = self._normalize_path_to_filename(relative_path)
            csv_path = self.vault_path / ".kineviz_graph" / "cache" / "content" / f"{csv_name}.csv"
            if csv_path.exists():
                csv_path.unlink()
                console.print(f"[yellow]Deleted old CSV for modified file: {csv_name}.csv[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Could not delete CSV for {file_path}: {e}[/yellow]")
    
    
    def _add_file_to_db(self, metadata: FileMetadata) -> int:
        """Add a new file to the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # First check if the file already exists
            cursor.execute("""
                SELECT id FROM file_tracking 
                WHERE current_path = ?
            """, (metadata.current_path,))
            
            existing_file = cursor.fetchone()
            if existing_file:
                # File already exists, return its ID
                console.print(f"[yellow]File {metadata.current_path} already exists in database, skipping add[/yellow]")
                return existing_file[0]
            
            # Add the new file
            cursor.execute("""
                INSERT INTO file_tracking 
                (current_path, original_path, file_name, file_size, modification_time, content_hash, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.current_path,
                metadata.original_path,
                metadata.file_name,
                metadata.file_size,
                metadata.modification_time,
                metadata.content_hash,
                metadata.status.value,
                metadata.created_at,
                metadata.updated_at
            ))
            return cursor.lastrowid
    
    def _update_file_in_db(self, metadata: FileMetadata, file_id: int):
        """Update file metadata in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_tracking 
                SET file_size = ?, modification_time = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
            """, (
                metadata.file_size,
                metadata.modification_time,
                metadata.content_hash,
                time.time(),
                file_id
            ))
    
    def _update_file_path_in_db(self, file_id: int, new_path: str):
        """Update file path in database (for moves)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # First check if the new path already exists
            cursor.execute("""
                SELECT id FROM file_tracking 
                WHERE current_path = ? AND id != ?
            """, (new_path, file_id))
            
            if cursor.fetchone():
                # Path already exists, mark the current file as deleted instead
                console.print(f"[yellow]Path {new_path} already exists, marking file as deleted instead of moving[/yellow]")
                self._mark_file_deleted(file_id)
                return
            
            # Update the path
            cursor.execute("""
                UPDATE file_tracking 
                SET current_path = ?, updated_at = ?
                WHERE id = ?
            """, (new_path, time.time(), file_id))
    
    def _mark_file_deleted(self, file_id: int):
        """Mark file as deleted in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_tracking 
                SET status = 'deleted', updated_at = ?
                WHERE id = ?
            """, (time.time(), file_id))
    
    def _record_changes(self, changes: List[FileChange]):
        """Record changes in the database"""
        if not changes:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for change in changes:
                cursor.execute("""
                    INSERT INTO file_changes 
                    (file_id, change_type, old_path, new_path, old_hash, new_hash, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    change.file_id,
                    change.change_type.value,
                    change.old_path,
                    change.new_path,
                    change.old_hash,
                    change.new_hash,
                    change.timestamp
                ))
            conn.commit()
    
    def get_files_to_process(self) -> List[Path]:
        """Get list of files that need processing (new or modified)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_path FROM file_tracking 
                WHERE status = 'active' AND id IN (
                    SELECT file_id FROM file_changes 
                    WHERE change_type IN ('created', 'modified') 
                    AND timestamp > (julianday('now') - 1)
                )
            """)
            return [self.vault_path / row[0] for row in cursor.fetchall()]
    
    def get_file_history(self, file_path: Path, limit: int = 10) -> List[FileChange]:
        """Get change history for a specific file"""
        relative_path = str(file_path.relative_to(self.vault_path))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fc.change_type, fc.old_path, fc.new_path, fc.old_hash, fc.new_hash, fc.timestamp
                FROM file_changes fc
                JOIN file_tracking ft ON fc.file_id = ft.id
                WHERE ft.current_path = ? OR fc.old_path = ? OR fc.new_path = ?
                ORDER BY fc.timestamp DESC
                LIMIT ?
            """, (relative_path, relative_path, relative_path, limit))
            
            changes = []
            for row in cursor.fetchall():
                changes.append(FileChange(
                    change_type=ChangeType(row[0]),
                    old_path=row[1],
                    new_path=row[2],
                    old_hash=row[3],
                    new_hash=row[4],
                    timestamp=row[5]
                ))
            return changes
    
    def _normalize_path_to_filename(self, relative_path: Path) -> str:
        """Convert a relative path to a safe filename for CSV lookup.
        
        Example: '30. People/John Smith.md' -> '30._People__John_Smith'
        Must match step1_extract.py's normalization exactly.
        """
        import re
        
        # Convert to string and remove .md extension
        path_str = str(relative_path)
        if path_str.endswith('.md'):
            path_str = path_str[:-3]
        
        # Replace path separators and spaces with underscores
        safe_name = path_str.replace('/', '__').replace('\\', '__').replace(' ', '_')
        
        # Remove or replace other problematic characters
        # Keep alphanumeric, underscore, dash, and dot
        safe_name = re.sub(r'[^\w\-.]', '_', safe_name)
        
        # Collapse multiple underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        
        # Trim leading/trailing underscores
        safe_name = safe_name.strip('_')
        
        return safe_name
    
    def _find_unprocessed_files(self, vault_file_paths: dict) -> List[Path]:
        """Find files that don't have corresponding CSV files (pathname-based).
        
        A file is considered processed if a CSV with its normalized pathname exists.
        Simple and deterministic - no content hashing needed.
        """
        unprocessed = []
        
        # Get cache directory
        cache_dir = self.vault_path / ".kineviz_graph" / "cache" / "content"
        if not cache_dir.exists():
            # If no cache directory, all files need processing
            return list(vault_file_paths.values())
        
        # Build set of existing CSV filenames (without .csv extension)
        existing_csvs = {csv_file.stem for csv_file in cache_dir.glob("*.csv")}
        
        # Find files that don't have a corresponding CSV
        for relative_path_str, file_path in vault_file_paths.items():
            relative_path = Path(relative_path_str)
            expected_csv_name = self._normalize_path_to_filename(relative_path)
            
            if expected_csv_name not in existing_csvs:
                unprocessed.append(file_path)
        
        return unprocessed
    
    def update_file_path_in_db(self, old_path: Path, new_path: Path):
        """Update file path in database for moved files"""
        old_relative_path = str(old_path.relative_to(self.vault_path))
        new_relative_path = str(new_path.relative_to(self.vault_path))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_tracking 
                SET current_path = ?, updated_at = ?
                WHERE current_path = ?
            """, (new_relative_path, time.time(), old_relative_path))
            conn.commit()
    
    def mark_file_processed(self, file_path: Path, has_relationships: bool = False):
        """Mark a file as processed in the database"""
        relative_path = str(file_path.relative_to(self.vault_path))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_tracking 
                SET processed_at = ?, has_relationships = ?, updated_at = ?
                WHERE current_path = ?
            """, (time.time(), 1 if has_relationships else 0, time.time(), relative_path))
            conn.commit()
    
    def cleanup_old_records(self, days: int = 30):
        """Clean up old deleted file records"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM file_tracking 
                WHERE status = 'deleted' AND updated_at < ?
            """, (cutoff_time,))
            deleted_count = cursor.rowcount
            conn.commit()
            
        console.print(f"[cyan]Cleaned up {deleted_count} old deleted file records[/cyan]")
