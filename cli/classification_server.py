#!/usr/bin/env python3
"""
Classification Task Manager Web Server

A web interface for managing and running classification tasks on Obsidian notes.

Usage:
    uv run classification_server.py
    uv run classification_server.py --port 8080

Then open http://localhost:8000 in your browser.
"""

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# Add cli directory to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDefinition, OutputType, TaskDatabase, Classifier
from config_loader import get_config_loader

# Initialize app
app = FastAPI(title="Classification Task Manager", version="1.0.0")

# Global state
_classifier: Optional[Classifier] = None
_task_db: Optional[TaskDatabase] = None

# Job tracking: job_id -> progress info
_job_progress: Dict[str, Dict[str, Any]] = {}


def get_vault_path() -> Path:
    """Get vault path from config"""
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        raise ValueError("Vault path not configured")
    return Path(vault_path)


def get_db() -> TaskDatabase:
    """Get TaskDatabase instance"""
    global _task_db
    if _task_db is None:
        vault_path = get_vault_path()
        db_path = vault_path / ".kineviz_graph" / "classification.db"
        _task_db = TaskDatabase(db_path)
    return _task_db


def get_classifier() -> Classifier:
    """Get Classifier instance"""
    global _classifier
    if _classifier is None:
        vault_path = get_vault_path()
        _classifier = Classifier(vault_path)
    return _classifier


# ==================== Pydantic Models ====================

class TaskCreate(BaseModel):
    tag: str
    prompt: str
    name: Optional[str] = None
    description: Optional[str] = None
    output_type: str = "text"
    model: Optional[str] = None


class TaskUpdate(BaseModel):
    prompt: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    output_type: Optional[str] = None
    model: Optional[str] = None


class RunRequest(BaseModel):
    tags: List[str]
    note: Optional[str] = None
    folder: Optional[str] = None
    force: bool = False
    store_timestamp: bool = False


class TaskResponse(BaseModel):
    id: Optional[int]
    tag: str
    name: Optional[str]
    description: Optional[str]
    prompt: str
    output_type: str
    model: Optional[str]
    enabled: bool
    created_at: Optional[str]
    updated_at: Optional[str]


# ==================== API Routes ====================

@app.get("/")
async def root():
    """Serve the main HTML page"""
    html_path = Path(__file__).parent / "classification_ui.html"
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>Classification Task Manager</h1><p>UI file not found</p>")


@app.get("/api/tasks")
async def list_tasks(enabled_only: bool = False):
    """List all tasks"""
    db = get_db()
    tasks = db.get_all_tasks(enabled_only=enabled_only)
    return [
        TaskResponse(
            id=t.id,
            tag=t.tag,
            name=t.name,
            description=t.description,
            prompt=t.prompt,
            output_type=t.output_type.value,
            model=t.model,
            enabled=t.enabled,
            created_at=t.created_at.isoformat() if t.created_at else None,
            updated_at=t.updated_at.isoformat() if t.updated_at else None
        )
        for t in tasks
    ]


@app.get("/api/tasks/{tag}")
async def get_task(tag: str):
    """Get a specific task"""
    db = get_db()
    task = db.get_task(tag)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {tag}")
    return TaskResponse(
        id=task.id,
        tag=task.tag,
        name=task.name,
        description=task.description,
        prompt=task.prompt,
        output_type=task.output_type.value,
        model=task.model,
        enabled=task.enabled,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None
    )


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    """Create a new task"""
    db = get_db()
    
    # Check if exists
    if db.get_task(task.tag):
        raise HTTPException(status_code=400, detail=f"Task already exists: {task.tag}")
    
    try:
        task_def = TaskDefinition(
            tag=task.tag,
            prompt=task.prompt,
            name=task.name,
            description=task.description,
            output_type=OutputType(task.output_type),
            model=task.model,
            enabled=True
        )
        task_id = db.create_task(task_def)
        return {"message": "Task created", "id": task_id, "tag": task.tag}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/tasks/{tag}")
async def update_task(tag: str, updates: TaskUpdate):
    """Update a task"""
    db = get_db()
    
    task = db.get_task(tag)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {tag}")
    
    update_dict = {}
    if updates.prompt is not None:
        update_dict['prompt'] = updates.prompt
    if updates.name is not None:
        update_dict['name'] = updates.name
    if updates.description is not None:
        update_dict['description'] = updates.description
    if updates.output_type is not None:
        update_dict['output_type'] = updates.output_type
    if updates.model is not None:
        update_dict['model'] = updates.model
    
    if update_dict:
        db.update_task(tag, update_dict)
    
    return {"message": "Task updated", "tag": tag}


@app.delete("/api/tasks/{tag}")
async def delete_task(tag: str):
    """Delete a task"""
    db = get_db()
    if db.delete_task(tag):
        return {"message": "Task deleted", "tag": tag}
    raise HTTPException(status_code=404, detail=f"Task not found: {tag}")


@app.post("/api/tasks/{tag}/enable")
async def enable_task(tag: str):
    """Enable a task"""
    db = get_db()
    if db.enable_task(tag):
        return {"message": "Task enabled", "tag": tag}
    raise HTTPException(status_code=404, detail=f"Task not found: {tag}")


@app.post("/api/tasks/{tag}/disable")
async def disable_task(tag: str):
    """Disable a task"""
    db = get_db()
    if db.disable_task(tag):
        return {"message": "Task disabled", "tag": tag}
    raise HTTPException(status_code=404, detail=f"Task not found: {tag}")


@app.get("/api/tasks/{tag}/status")
async def get_task_status(tag: str, folder: Optional[str] = None):
    """Get task status"""
    db = get_db()
    status = db.get_task_status(tag, folder)
    if not status:
        raise HTTPException(status_code=404, detail=f"Task not found: {tag}")
    
    task = status['task']
    return {
        "tag": task.tag,
        "name": task.name,
        "output_type": task.output_type.value,
        "enabled": task.enabled,
        "completed": status['completed'],
        "failed": status['failed'],
        "running": status['running'],
        "total": status['total']
    }


@app.get("/api/tasks/{tag}/history")
async def get_task_history(tag: str, limit: int = 50):
    """Get task run history"""
    db = get_db()
    history = db.get_run_history(tag, limit)
    return [
        {
            "id": h['id'],
            "note_path": h['note_path'],
            "status": h['status'],
            "result": h['result'],
            "error": h['error'],
            "model_used": h['model_used'],
            "processing_time_ms": h['processing_time_ms'],
            "created_at": h['created_at'].isoformat() if h['created_at'] else None,
            "completed_at": h['completed_at'].isoformat() if h['completed_at'] else None
        }
        for h in history
    ]


# Background task for running classification
async def run_classification_task(
    job_id: str,
    tags: List[str], 
    note: Optional[str], 
    folder: Optional[str], 
    force: bool,
    store_timestamp: bool
):
    """Background task to run classification with progress tracking"""
    try:
        # Initialize job progress
        _job_progress[job_id] = {
            "status": "running",
            "progress": 0,
            "total": 0,
            "current": 0,
            "current_note": None,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "error": None,
            "results": {}
        }
        
        classifier = get_classifier()
        
        # Track progress per task
        task_progress = {tag: {"current": 0, "total": 0} for tag in tags}
        
        # Create progress callback
        def progress_callback(task_tag: str, current: int, total: int, note_path: Optional[str] = None):
            """Update progress for a specific task"""
            if job_id in _job_progress:
                # Update task-specific progress
                task_progress[task_tag] = {"current": current, "total": total}
                
                # Calculate overall progress across all tasks
                total_current = sum(t["current"] for t in task_progress.values())
                total_max = sum(t["total"] for t in task_progress.values())
                
                _job_progress[job_id]["current"] = total_current
                _job_progress[job_id]["total"] = total_max
                _job_progress[job_id]["current_note"] = note_path
                
                if total_max > 0:
                    _job_progress[job_id]["progress"] = int((total_current / total_max) * 100)
        
        # Run classification with progress tracking
        results = await classifier.classify_notes(
            task_tags=tags,
            note_path=note,
            folder_path=folder,
            force=force,
            store_timestamp=store_timestamp,
            progress_callback=progress_callback
        )
        
        # Update final status
        if job_id in _job_progress:
            total_completed = sum(r.get('classified', 0) for r in results.values())
            total_failed = sum(r.get('failed', 0) for r in results.values())
            total_skipped = sum(r.get('skipped', 0) for r in results.values())
            
            _job_progress[job_id].update({
                "status": "completed",
                "progress": 100,
                "completed": total_completed,
                "failed": total_failed,
                "skipped": total_skipped,
                "results": results
            })
    except Exception as e:
        # Mark job as failed
        if job_id in _job_progress:
            _job_progress[job_id].update({
                "status": "failed",
                "error": str(e)
            })
        else:
            _job_progress[job_id] = {
                "status": "failed",
                "error": str(e)
            }


@app.post("/api/run")
async def run_classification(request: RunRequest, background_tasks: BackgroundTasks):
    """Run classification task(s)"""
    if not request.note and not request.folder:
        raise HTTPException(status_code=400, detail="Must specify either note or folder")
    if request.note and request.folder:
        raise HTTPException(status_code=400, detail="Cannot specify both note and folder")
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Run in background
    background_tasks.add_task(
        run_classification_task,
        job_id,
        request.tags,
        request.note,
        request.folder,
        request.force,
        request.store_timestamp
    )
    
    return {
        "message": "Classification started",
        "job_id": job_id,
        "tags": request.tags,
        "target": request.note or request.folder,
        "force": request.force
    }


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job progress status"""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    progress = _job_progress[job_id]
    return progress


@app.get("/api/folders")
async def list_folders():
    """List folders in vault"""
    vault_path = get_vault_path()
    folders = []
    
    for path in vault_path.iterdir():
        if path.is_dir() and not path.name.startswith('.'):
            folders.append(path.name + "/")
            # Add one level of subfolders
            for subpath in path.iterdir():
                if subpath.is_dir() and not subpath.name.startswith('.'):
                    folders.append(f"{path.name}/{subpath.name}/")
    
    return sorted(folders)


@app.get("/api/vault-info")
async def vault_info():
    """Get vault information"""
    vault_path = get_vault_path()
    md_count = len(list(vault_path.rglob("*.md")))
    return {
        "path": str(vault_path),
        "name": vault_path.name,
        "note_count": md_count
    }


# ==================== Main ====================

if __name__ == "__main__":
    import click
    
    @click.command()
    @click.option("--port", default=8000, help="Port to run server on")
    @click.option("--host", default="127.0.0.1", help="Host to bind to")
    def main(port: int, host: str):
        """Start the Classification Task Manager web server"""
        print(f"\n🚀 Classification Task Manager")
        print(f"   Open http://{host}:{port} in your browser\n")
        uvicorn.run(app, host=host, port=port)
    
    main()

