"""
SQLite Database for Classification Tasks
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import TaskDefinition, OutputType, TaskType, TagSchema, ClassificationResult


class TaskDatabase:
    """SQLite database for managing classification tasks and run history"""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Classification Tasks Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classification_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT UNIQUE NOT NULL,
                    name TEXT,
                    description TEXT,
                    prompt TEXT NOT NULL,
                    model TEXT,
                    output_type TEXT NOT NULL
                        CHECK(output_type IN ('list', 'text', 'boolean', 'number')),
                    enabled INTEGER DEFAULT 1,
                    created_at REAL DEFAULT (julianday('now')),
                    updated_at REAL DEFAULT (julianday('now'))
                )
            """)
            
            # Migration: Add new columns if they don't exist
            try:
                cursor.execute("ALTER TABLE classification_tasks ADD COLUMN task_type TEXT DEFAULT 'single'")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE classification_tasks ADD COLUMN tag_schema TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Update existing rows to have task_type = 'single' if NULL
            cursor.execute("""
                UPDATE classification_tasks 
                SET task_type = 'single' 
                WHERE task_type IS NULL
            """)
            
            # Classification Runs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classification_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES classification_tasks(id),
                    note_path TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                        CHECK(status IN ('pending', 'running', 'completed', 'failed')),
                    result TEXT,
                    error TEXT,
                    model_used TEXT,
                    processing_time_ms INTEGER,
                    created_at REAL DEFAULT (julianday('now')),
                    completed_at REAL
                )
            """)
            
            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tag ON classification_tasks(tag)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_enabled ON classification_tasks(enabled)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON classification_runs(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_note_path ON classification_runs(note_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON classification_runs(status)")
            
            conn.commit()
    
    def _julian_to_datetime(self, julian: Optional[float]) -> Optional[datetime]:
        """Convert Julian day to datetime"""
        if julian is None:
            return None
        # Julian day 0 = November 24, 4714 BC
        # We need to convert from Julian day to Unix timestamp
        return datetime.fromtimestamp((julian - 2440587.5) * 86400)
    
    def _row_to_task(self, row: tuple) -> TaskDefinition:
        """Convert database row to TaskDefinition"""
        # Handle both old schema (9 fields) and new schema (11 fields)
        if len(row) >= 11:
            # New schema with task_type and tag_schema
            task_type = TaskType(row[10] if row[10] else 'single')
            tag_schema_json = row[11] if len(row) > 11 else None
            
            # Parse tag_schema from JSON
            tag_schema = None
            if tag_schema_json:
                try:
                    tag_schema_data = json.loads(tag_schema_json)
                    tag_schema = [TagSchema(**item) for item in tag_schema_data]
                except (json.JSONDecodeError, TypeError, ValueError):
                    tag_schema = None
            
            return TaskDefinition(
                id=row[0],
                tag=row[1],
                name=row[2],
                description=row[3],
                prompt=row[4],
                model=row[5],
                output_type=OutputType(row[6]),
                enabled=bool(row[7]),
                created_at=self._julian_to_datetime(row[8]),
                updated_at=self._julian_to_datetime(row[9]),
                task_type=task_type,
                tag_schema=tag_schema
            )
        else:
            # Old schema - default to single task type
            return TaskDefinition(
                id=row[0],
                tag=row[1],
                name=row[2],
                description=row[3],
                prompt=row[4],
                model=row[5],
                output_type=OutputType(row[6]),
                enabled=bool(row[7]),
                created_at=self._julian_to_datetime(row[8]),
                updated_at=self._julian_to_datetime(row[9]),
                task_type=TaskType.SINGLE,
                tag_schema=None
            )
    
    # ==================== CRUD Operations ====================
    
    def create_task(self, task: TaskDefinition) -> int:
        """Create a new classification task"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Serialize tag_schema to JSON
            tag_schema_json = None
            if task.tag_schema:
                tag_schema_json = json.dumps([
                    {
                        'tag': ts.tag,
                        'output_type': ts.output_type.value,
                        'name': ts.name,
                        'description': ts.description
                    }
                    for ts in task.tag_schema
                ])
            
            cursor.execute("""
                INSERT INTO classification_tasks (tag, name, description, prompt, model, output_type, enabled, task_type, tag_schema)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.tag,
                task.name,
                task.description,
                task.prompt,
                task.model,
                task.output_type.value,
                1 if task.enabled else 0,
                task.task_type.value,
                tag_schema_json
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_task(self, tag: str) -> Optional[TaskDefinition]:
        """Get a task by tag"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Try new schema first, fallback to old schema
            try:
                cursor.execute("""
                    SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at, task_type, tag_schema
                    FROM classification_tasks WHERE tag = ?
                """, (tag,))
            except sqlite3.OperationalError:
                # Fallback to old schema
                cursor.execute("""
                    SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at
                    FROM classification_tasks WHERE tag = ?
                """, (tag,))
            row = cursor.fetchone()
            if row:
                return self._row_to_task(row)
            return None
    
    def get_task_by_id(self, task_id: int) -> Optional[TaskDefinition]:
        """Get a task by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Try new schema first, fallback to old schema
            try:
                cursor.execute("""
                    SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at, task_type, tag_schema
                    FROM classification_tasks WHERE id = ?
                """, (task_id,))
            except sqlite3.OperationalError:
                # Fallback to old schema
                cursor.execute("""
                    SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at
                    FROM classification_tasks WHERE id = ?
                """, (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_task(row)
            return None
    
    def get_all_tasks(self, enabled_only: bool = False) -> List[TaskDefinition]:
        """Get all tasks"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Try new schema first, fallback to old schema
            try:
                if enabled_only:
                    cursor.execute("""
                        SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at, task_type, tag_schema
                        FROM classification_tasks WHERE enabled = 1 ORDER BY tag
                    """)
                else:
                    cursor.execute("""
                        SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at, task_type, tag_schema
                        FROM classification_tasks ORDER BY tag
                    """)
            except sqlite3.OperationalError:
                # Fallback to old schema
                if enabled_only:
                    cursor.execute("""
                        SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at
                        FROM classification_tasks WHERE enabled = 1 ORDER BY tag
                    """)
                else:
                    cursor.execute("""
                        SELECT id, tag, name, description, prompt, model, output_type, enabled, created_at, updated_at
                        FROM classification_tasks ORDER BY tag
                    """)
            rows = cursor.fetchall()
            return [self._row_to_task(row) for row in rows]
    
    def update_task(self, tag: str, updates: Dict[str, Any]) -> bool:
        """Update a task by tag"""
        if not updates:
            return False
        
        # Build SET clause
        set_parts = []
        values = []
        for key, value in updates.items():
            if key in ('tag', 'name', 'description', 'prompt', 'model', 'output_type', 'enabled', 'task_type'):
                set_parts.append(f"{key} = ?")
                if key == 'output_type' and isinstance(value, OutputType):
                    values.append(value.value)
                elif key == 'task_type' and isinstance(value, TaskType):
                    values.append(value.value)
                elif key == 'enabled':
                    values.append(1 if value else 0)
                else:
                    values.append(value)
            elif key == 'tag_schema':
                # Serialize tag_schema to JSON
                if value is None:
                    set_parts.append("tag_schema = ?")
                    values.append(None)
                else:
                    tag_schema_json = json.dumps([
                        {
                            'tag': ts.tag if isinstance(ts, TagSchema) else ts.get('tag'),
                            'output_type': ts.output_type.value if isinstance(ts, TagSchema) else ts.get('output_type'),
                            'name': ts.name if isinstance(ts, TagSchema) else ts.get('name'),
                            'description': ts.description if isinstance(ts, TagSchema) else ts.get('description')
                        }
                        for ts in value
                    ])
                    set_parts.append("tag_schema = ?")
                    values.append(tag_schema_json)
        
        if not set_parts:
            return False
        
        # Add updated_at
        set_parts.append("updated_at = julianday('now')")
        values.append(tag)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE classification_tasks SET {', '.join(set_parts)} WHERE tag = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_task(self, tag: str) -> bool:
        """Delete a task by tag"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # First delete related runs
            cursor.execute("""
                DELETE FROM classification_runs 
                WHERE task_id = (SELECT id FROM classification_tasks WHERE tag = ?)
            """, (tag,))
            # Then delete the task
            cursor.execute("DELETE FROM classification_tasks WHERE tag = ?", (tag,))
            conn.commit()
            return cursor.rowcount > 0
    
    def enable_task(self, tag: str) -> bool:
        """Enable a task"""
        return self.update_task(tag, {'enabled': True})
    
    def disable_task(self, tag: str) -> bool:
        """Disable a task"""
        return self.update_task(tag, {'enabled': False})
    
    # ==================== Run History ====================
    
    def record_run_start(self, task_id: int, note_path: str) -> int:
        """Record the start of a classification run"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO classification_runs (task_id, note_path, status)
                VALUES (?, ?, 'running')
            """, (task_id, note_path))
            conn.commit()
            return cursor.lastrowid
    
    def record_run_complete(
        self, 
        run_id: int, 
        result: str, 
        model_used: str, 
        processing_time_ms: int
    ):
        """Record successful completion of a run"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE classification_runs 
                SET status = 'completed', result = ?, model_used = ?, 
                    processing_time_ms = ?, completed_at = julianday('now')
                WHERE id = ?
            """, (result, model_used, processing_time_ms, run_id))
            conn.commit()
    
    def record_run_failed(self, run_id: int, error: str):
        """Record failed run"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE classification_runs 
                SET status = 'failed', error = ?, completed_at = julianday('now')
                WHERE id = ?
            """, (error, run_id))
            conn.commit()
    
    def get_run_history(self, tag: str, limit: int = 100) -> List[Dict]:
        """Get run history for a task"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.note_path, r.status, r.result, r.error, 
                       r.model_used, r.processing_time_ms, r.created_at, r.completed_at
                FROM classification_runs r
                JOIN classification_tasks t ON r.task_id = t.id
                WHERE t.tag = ?
                ORDER BY r.created_at DESC
                LIMIT ?
            """, (tag, limit))
            rows = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'note_path': row[1],
                    'status': row[2],
                    'result': row[3],
                    'error': row[4],
                    'model_used': row[5],
                    'processing_time_ms': row[6],
                    'created_at': self._julian_to_datetime(row[7]),
                    'completed_at': self._julian_to_datetime(row[8])
                }
                for row in rows
            ]
    
    def get_task_status(self, tag: str, folder: Optional[str] = None) -> Dict:
        """Get status summary for a task"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get task info
            task = self.get_task(tag)
            if not task:
                return {}
            
            # Count runs by status
            if folder:
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM classification_runs r
                    JOIN classification_tasks t ON r.task_id = t.id
                    WHERE t.tag = ? AND r.note_path LIKE ?
                    GROUP BY status
                """, (tag, f"{folder}%"))
            else:
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM classification_runs r
                    JOIN classification_tasks t ON r.task_id = t.id
                    WHERE t.tag = ?
                    GROUP BY status
                """, (tag,))
            
            status_counts = dict(cursor.fetchall())
            
            return {
                'task': task,
                'completed': status_counts.get('completed', 0),
                'failed': status_counts.get('failed', 0),
                'running': status_counts.get('running', 0),
                'pending': status_counts.get('pending', 0),
                'total': sum(status_counts.values())
            }
    
    # ==================== Import/Export ====================
    
    def export_tasks_to_yaml(self) -> str:
        """Export all tasks to YAML format"""
        import yaml
        tasks = self.get_all_tasks()
        data = {
            'classification_tasks': [
                {
                    'tag': t.tag,
                    'name': t.name,
                    'description': t.description,
                    'prompt': t.prompt,
                    'model': t.model,
                    'output_type': t.output_type.value,
                    'enabled': t.enabled
                }
                for t in tasks
            ]
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    
    def import_tasks_from_yaml(self, yaml_content: str) -> int:
        """Import tasks from YAML content. Returns number of tasks imported."""
        import yaml
        data = yaml.safe_load(yaml_content)
        tasks = data.get('classification_tasks', [])
        
        imported = 0
        for task_data in tasks:
            tag = task_data.get('tag')
            if not tag:
                continue
            
            # Check if task exists
            existing = self.get_task(tag)
            if existing:
                # Update existing task
                self.update_task(tag, {
                    'name': task_data.get('name'),
                    'description': task_data.get('description'),
                    'prompt': task_data.get('prompt'),
                    'model': task_data.get('model'),
                    'output_type': task_data.get('output_type'),
                    'enabled': task_data.get('enabled', True)
                })
            else:
                # Create new task
                task = TaskDefinition(
                    tag=tag,
                    name=task_data.get('name'),
                    description=task_data.get('description'),
                    prompt=task_data.get('prompt'),
                    model=task_data.get('model'),
                    output_type=OutputType(task_data.get('output_type', 'text')),
                    enabled=task_data.get('enabled', True)
                )
                self.create_task(task)
            imported += 1
        
        return imported

