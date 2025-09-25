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
        
        # Initialize database
        self._init_database()
    
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
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
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
                content_hash=self._calculate_file_hash(file_path),
                created_at=time.time(),
                updated_at=time.time()
            )
        except Exception as e:
            console.print(f"[yellow]Error getting metadata for {file_path}: {e}[/yellow]")
            return None
    
    def scan_vault(self) -> Tuple[List[FileChange], List[Path]]:
        """Scan vault and detect changes compared to database state"""
        console.print("[cyan]Scanning vault for file changes...[/cyan]")
        
        # Get all markdown files in vault
        vault_files = set()
        for md_file in self.vault_path.rglob("*.md"):
            if not any(part.startswith('.') for part in md_file.relative_to(self.vault_path).parts):
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
        
        # Check for new and modified files
        for relative_path, file_path in vault_file_paths.items():
            if relative_path not in db_files:
                # Check if this is a moved file by content hash
                metadata = self._get_file_metadata(file_path)
                if metadata:
                    # Look for a file with the same content hash that was deleted
                    moved_from = None
                    moved_db_file = None
                    for db_relative_path, db_file in db_files.items():
                        if (db_relative_path not in vault_file_paths and 
                            db_file['content_hash'] == metadata.content_hash):
                            moved_from = db_relative_path
                            moved_db_file = db_file
                            break
                    
                    if moved_from:
                        # This is a moved file - update path but don't reprocess
                        self._update_file_path_in_db(moved_db_file['id'], relative_path)
                        # Update CSV files with new path
                        self.update_csv_file_paths(Path(moved_from), file_path)
                        changes.append(FileChange(
                            file_id=moved_db_file['id'],
                            change_type=ChangeType.MOVED,
                            old_path=moved_from,
                            new_path=relative_path,
                            old_hash=moved_db_file['content_hash'],
                            new_hash=metadata.content_hash,
                            timestamp=time.time()
                        ))
                        # Don't add to files_to_process - just update the path
                        console.print(f"[blue]Moved file: {moved_from} -> {relative_path} (content unchanged, skipping reprocessing)[/blue]")
                    else:
                        # This is a truly new file
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
                # Existing file - check if modified
                db_file = db_files[relative_path]
                metadata = self._get_file_metadata(file_path)
                
                if metadata:
                    if (metadata.file_size != db_file['file_size'] or 
                        metadata.modification_time != db_file['modification_time'] or
                        metadata.content_hash != db_file['content_hash']):
                        # File modified
                        self._update_file_in_db(metadata, db_file['id'])
                        changes.append(FileChange(
                            file_id=db_file['id'],
                            change_type=ChangeType.MODIFIED,
                            old_path=relative_path,
                            new_path=relative_path,
                            old_hash=db_file['content_hash'],
                            new_hash=metadata.content_hash,
                            timestamp=time.time()
                        ))
                        files_to_process.append(file_path)
                        console.print(f"[yellow]Modified file: {relative_path}[/yellow]")
        
        # Check for unprocessed files (files in DB but no corresponding CSV files)
        unprocessed_files = self._find_unprocessed_files(vault_file_paths)
        for file_path in unprocessed_files:
            files_to_process.append(file_path)
            console.print(f"[blue]Unprocessed file: {file_path.relative_to(self.vault_path)}[/blue]")
        
        # Check for deleted files (but not moved files)
        for relative_path, db_file in db_files.items():
            if relative_path not in vault_file_paths:
                # Check if this file was moved by looking for a file with the same content hash
                moved_to = None
                for vault_relative_path, vault_file in vault_file_paths.items():
                    vault_metadata = self._get_file_metadata(vault_file)
                    if (vault_metadata and 
                        vault_metadata.content_hash == db_file['content_hash']):
                        moved_to = vault_relative_path
                        break
                
                if moved_to:
                    # This file was moved, not deleted
                    console.print(f"[blue]File moved: {relative_path} -> {moved_to}[/blue]")
                    # The move was already handled in the new files section
                else:
                    # File truly deleted
                    self._mark_file_deleted(db_file['id'])
                    changes.append(FileChange(
                        file_id=db_file['id'],
                        change_type=ChangeType.DELETED,
                        old_path=relative_path,
                        timestamp=time.time()
                    ))
                    console.print(f"[red]Deleted file: {relative_path}[/red]")
        
        # Check for moved files (by content hash)
        self._detect_moved_files(changes, vault_file_paths, db_files)
        
        # Record all changes
        self._record_changes(changes)
        
        console.print(f"[cyan]Detected {len(changes)} changes, {len(files_to_process)} files to process[/cyan]")
        return changes, files_to_process
    
    def _detect_moved_files(self, changes: List[FileChange], vault_files: Dict[str, Path], db_files: Dict[str, dict]):
        """Detect moved files by comparing content hashes"""
        # Group vault files by content hash
        vault_hashes = {}
        for relative_path, file_path in vault_files.items():
            metadata = self._get_file_metadata(file_path)
            if metadata and metadata.content_hash:
                if metadata.content_hash not in vault_hashes:
                    vault_hashes[metadata.content_hash] = []
                vault_hashes[metadata.content_hash].append((relative_path, file_path))
        
        # Check for moved files
        for relative_path, db_file in db_files.items():
            if relative_path not in vault_files and db_file['content_hash'] in vault_hashes:
                # Found a file with the same content hash - likely moved
                candidates = vault_hashes[db_file['content_hash']]
                if len(candidates) == 1:  # Only one candidate - safe to consider it moved
                    new_path, new_file_path = candidates[0]
                    
                    # Update the file record
                    self._update_file_path_in_db(db_file['id'], new_path)
                    
                    # Add move change
                    changes.append(FileChange(
                        file_id=db_file['id'],
                        change_type=ChangeType.MOVED,
                        old_path=relative_path,
                        new_path=new_path,
                        old_hash=db_file['content_hash'],
                        new_hash=db_file['content_hash'],
                        timestamp=time.time()
                    ))
                    console.print(f"[blue]Moved file: {relative_path} -> {new_path}[/blue]")
    
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
    
    def _find_unprocessed_files(self, vault_file_paths: dict) -> List[Path]:
        """Find files that are in the database but don't have corresponding CSV files"""
        unprocessed = []
        
        # Get all CSV files in the cache
        cache_dir = self.vault_path / ".kineviz_graph" / "cache" / "content"
        if not cache_dir.exists():
            # If no cache directory, all files need processing
            return list(vault_file_paths.values())
        
        csv_files = set()
        for csv_file in cache_dir.glob("*.csv"):
            try:
                import csv as csv_module
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    for row in reader:
                        if 'source_file' in row and row['source_file']:
                            source_file = row['source_file'].strip()
                            if source_file:
                                # Convert relative path to absolute for comparison
                                if not Path(source_file).is_absolute():
                                    abs_path = self.vault_path / source_file
                                else:
                                    abs_path = Path(source_file)
                                csv_files.add(abs_path)
            except Exception as e:
                console.print(f"[yellow]Could not read CSV file {csv_file.name}: {e}[/yellow]")
                continue
        
        # Find files that are in vault but not in CSV files
        for file_path in vault_file_paths.values():
            if file_path not in csv_files:
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
    
    def update_csv_file_paths(self, old_path: Path, new_path: Path):
        """Update source_file paths in CSV files when a file is moved"""
        import csv as csv_module
        
        # Handle both absolute and relative paths
        if old_path.is_absolute():
            old_relative_path = str(old_path.relative_to(self.vault_path))
        else:
            old_relative_path = str(old_path)
            
        if new_path.is_absolute():
            new_relative_path = str(new_path.relative_to(self.vault_path))
        else:
            new_relative_path = str(new_path)
        
        content_dir = self.vault_path / ".kineviz_graph" / "cache" / "content"
        if not content_dir.exists():
            return
        
        updated_files = 0
        for csv_file in content_dir.glob("*.csv"):
            try:
                # Read the CSV file
                rows = []
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        if 'source_file' in row and row['source_file'] == old_relative_path:
                            row['source_file'] = new_relative_path
                            updated_files += 1
                        rows.append(row)
                
                # Write back the updated CSV file
                if updated_files > 0:
                    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                        writer = csv_module.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    
            except Exception as e:
                console.print(f"[yellow]Could not update CSV file {csv_file.name}: {e}[/yellow]")
                continue
        
        if updated_files > 0:
            console.print(f"[green]Updated {updated_files} CSV entries for moved file: {old_relative_path} -> {new_relative_path}[/green]")
    
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
