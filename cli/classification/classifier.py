"""
Core Classification Logic

Runs classification tasks on notes and stores results in frontmatter.

=== CLI USAGE (run from cli/ directory) ===

# List all tasks
uv run classification_task_manager.py list-tasks

# Add a task (list type - comma-separated values)
uv run classification_task_manager.py add-task \\
  --tag "gxr_professional_interests" \\
  --name "Professional Interests" \\
  --prompt "Extract professional interests as comma-separated list" \\
  --output-type list

# Add a task (boolean type)
uv run classification_task_manager.py add-task \\
  --tag "gxr_is_investor" \\
  --name "Is Investor" \\
  --prompt "Is this person an investor? Return true or false." \\
  --output-type boolean

# Show task details
uv run classification_task_manager.py show-task gxr_professional_interests

# Run on single note (skips if already classified)
uv run classification_task_manager.py run gxr_professional_interests \\
  --note "Persons/Joseph Tsai.md"

# Run on single note (force re-classify)
uv run classification_task_manager.py run gxr_professional_interests \\
  --note "Persons/Joseph Tsai.md" --force

# Run on folder (all .md files recursively)
uv run classification_task_manager.py run gxr_professional_interests \\
  --folder "Persons/"

# Run multiple tasks on folder
uv run classification_task_manager.py run gxr_professional_interests gxr_is_investor \\
  --folder "Persons/"

# Dry run (preview without changes)
uv run classification_task_manager.py run gxr_professional_interests \\
  --folder "Persons/" --dry-run

# Check status
uv run classification_task_manager.py status gxr_professional_interests

# View run history
uv run classification_task_manager.py history gxr_professional_interests

# Export/import tasks
uv run classification_task_manager.py export-tasks -o tasks.yaml
uv run classification_task_manager.py import-tasks tasks.yaml

# Manage tasks
uv run classification_task_manager.py edit-task gxr_interests --prompt "New prompt..."
uv run classification_task_manager.py enable-task gxr_interests
uv run classification_task_manager.py disable-task gxr_interests
uv run classification_task_manager.py delete-task gxr_interests

=== OUTPUT TYPES ===
- list:    Comma-separated string, e.g., "Tech, Finance, Healthcare"
- text:    Plain string
- boolean: true or false
- number:  Integer or float

=== RESULTS STORED IN FRONTMATTER ===
gxr_professional_interests: "Technology, Private Equity"
gxr_professional_interests_at: "2025-12-04T23:42:13.720484"
"""

import asyncio
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from rich.console import Console

from .models import TaskDefinition, OutputType
from .database import TaskDatabase

console = Console()


class Classifier:
    """
    Runs classification tasks on Obsidian notes.
    
    Usage:
        classifier = Classifier(vault_path)
        await classifier.classify_note("gxr_professional_interests", "People/John Smith.md")
        await classifier.classify_folder("gxr_professional_interests", "People/", force=True)
    """
    
    def __init__(self, vault_path: Path, llm_client=None):
        """
        Initialize classifier.
        
        Args:
            vault_path: Path to Obsidian vault
            llm_client: Optional LLMClient instance (will create one if not provided)
        """
        self.vault_path = Path(vault_path)
        self.llm_client = llm_client
        
        # Initialize database
        db_path = self.vault_path / ".kineviz_graph" / "classification.db"
        self.task_db = TaskDatabase(db_path)
        
        # Import metadata functions
        import sys
        cli_path = Path(__file__).parent.parent
        if str(cli_path) not in sys.path:
            sys.path.insert(0, str(cli_path))
        
        from metadata_manager import parse_frontmatter, add_metadata, get_metadata
        self._parse_frontmatter = parse_frontmatter
        self._add_metadata = add_metadata
        self._get_metadata = get_metadata
    
    def _get_llm_client(self):
        """Lazy-load LLM client"""
        if self.llm_client is None:
            import sys
            cli_path = Path(__file__).parent.parent
            if str(cli_path) not in sys.path:
                sys.path.insert(0, str(cli_path))
            
            from llm_client import LLMClient
            self.llm_client = LLMClient()
        return self.llm_client
    
    def _resolve_note_path(self, note_path: str) -> Path:
        """Resolve relative note path to absolute path"""
        path = Path(note_path)
        if path.is_absolute():
            return path
        return self.vault_path / path
    
    def is_classified(self, note_path: Path, task_tag: str) -> bool:
        """Check if note has been classified for this task"""
        metadata = self._get_metadata(note_path)
        if metadata is None:
            return False
        return task_tag in metadata
    
    def _read_note_content(self, note_path: Path) -> str:
        """Read note content (excluding frontmatter)"""
        content = note_path.read_text(encoding='utf-8')
        _, body = self._parse_frontmatter(content)
        return body.strip()
    
    def _build_prompt(self, task: TaskDefinition, note_content: str) -> List[Dict[str, str]]:
        """Build LLM prompt for classification"""
        type_instructions = {
            'list': 'Return a comma-separated list. Example: "item1, item2, item3". Return empty string if nothing found.',
            'text': 'Return a single text string. Return empty string if nothing found.',
            'boolean': 'Return exactly "true" or "false".',
            'number': 'Return a single number. Return 0 if cannot determine.'
        }
        
        system = f"""You are a classification assistant.
Analyze the note and extract the requested information.

Output format: {task.output_type.value}
{type_instructions[task.output_type.value]}

Return ONLY the result, no explanation, no quotes around the result."""
        
        user = f"""{task.prompt}

=== NOTE ===
{note_content}
=== END ==="""
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    
    def _parse_result(self, raw: str, output_type: OutputType) -> Any:
        """Parse LLM output to correct type"""
        raw = raw.strip()
        
        # Remove surrounding quotes if present
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        
        if output_type == OutputType.LIST:
            # Already comma-separated string, just clean it
            return raw
        
        elif output_type == OutputType.TEXT:
            return raw
        
        elif output_type == OutputType.BOOLEAN:
            return raw.lower() in ('true', 'yes', '1')
        
        elif output_type == OutputType.NUMBER:
            try:
                if '.' in raw:
                    return float(raw)
                return int(raw)
            except ValueError:
                return 0
        
        return raw
    
    def _store_result(self, note_path: Path, task: TaskDefinition, result: Any):
        """Store classification result in note frontmatter"""
        # Store the result
        self._add_metadata(note_path, task.tag, result)
        
        # Store timestamp
        timestamp = datetime.now().isoformat()
        self._add_metadata(note_path, f"{task.tag}_at", timestamp)
    
    async def classify_note(
        self, 
        task_tag: str, 
        note_path: str, 
        force: bool = False,
        dry_run: bool = False
    ) -> Tuple[bool, Optional[Any], Optional[str]]:
        """
        Classify a single note.
        
        Args:
            task_tag: The task tag (e.g., "gxr_professional_interests")
            note_path: Relative or absolute path to note
            force: If True, re-classify even if already classified
            dry_run: If True, don't actually modify the note
        
        Returns:
            Tuple of (success, result, error_message)
        """
        # Resolve path
        full_path = self._resolve_note_path(note_path)
        relative_path = str(full_path.relative_to(self.vault_path))
        
        # Check if note exists
        if not full_path.exists():
            return False, None, f"Note not found: {note_path}"
        
        # Get task
        task = self.task_db.get_task(task_tag)
        if not task:
            return False, None, f"Task not found: {task_tag}"
        
        if not task.enabled:
            return False, None, f"Task is disabled: {task_tag}"
        
        # Check if already classified
        if not force and self.is_classified(full_path, task_tag):
            console.print(f"[dim]Skipping (already classified): {relative_path}[/dim]")
            return True, None, "already_classified"
        
        if dry_run:
            console.print(f"[cyan]Would classify: {relative_path}[/cyan]")
            return True, None, "dry_run"
        
        # Record run start
        run_id = self.task_db.record_run_start(task.id, relative_path)
        start_time = time.time()
        
        try:
            # Read note content
            note_content = self._read_note_content(full_path)
            if not note_content.strip():
                self.task_db.record_run_failed(run_id, "Note content is empty")
                return False, None, "Note content is empty"
            
            # Build prompt
            messages = self._build_prompt(task, note_content)
            
            # Get LLM response
            llm = self._get_llm_client()
            model_override = task.model  # Task-specific model override
            
            # Use skip_relationship_suffix=True to prevent relationship extraction prompt from being appended
            response = await llm.generate(messages, skip_relationship_suffix=True)
            
            if not response.success:
                self.task_db.record_run_failed(run_id, response.error or "LLM request failed")
                return False, None, response.error or "LLM request failed"
            
            # Parse result
            result = self._parse_result(response.content, task.output_type)
            
            # Store in frontmatter
            self._store_result(full_path, task, result)
            
            # Record success
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.task_db.record_run_complete(
                run_id, 
                str(result), 
                response.model, 
                processing_time_ms
            )
            
            console.print(f"[green]✓ Classified: {relative_path}[/green] → {task_tag}: {result}")
            return True, result, None
            
        except Exception as e:
            self.task_db.record_run_failed(run_id, str(e))
            console.print(f"[red]✗ Failed: {relative_path} - {e}[/red]")
            return False, None, str(e)
    
    async def classify_folder(
        self, 
        task_tag: str, 
        folder_path: str, 
        force: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Classify all notes in a folder.
        
        Args:
            task_tag: The task tag (e.g., "gxr_professional_interests")
            folder_path: Relative path to folder within vault
            force: If True, re-classify even if already classified
            dry_run: If True, don't actually modify notes
        
        Returns:
            Dict with statistics: {total, classified, skipped, failed}
        """
        # Resolve folder path
        folder = self.vault_path / folder_path
        if not folder.exists():
            console.print(f"[red]Folder not found: {folder_path}[/red]")
            return {'total': 0, 'classified': 0, 'skipped': 0, 'failed': 0, 'error': 'Folder not found'}
        
        # Get task
        task = self.task_db.get_task(task_tag)
        if not task:
            console.print(f"[red]Task not found: {task_tag}[/red]")
            return {'total': 0, 'classified': 0, 'skipped': 0, 'failed': 0, 'error': 'Task not found'}
        
        # Find all markdown files
        md_files = list(folder.rglob("*.md"))
        
        # Filter out hidden files and folders
        md_files = [
            f for f in md_files 
            if not any(part.startswith('.') for part in f.relative_to(self.vault_path).parts)
        ]
        
        console.print(f"\n[bold]Task: {task.get_display_name()} ({task_tag})[/bold]")
        console.print(f"[cyan]Found {len(md_files)} notes in {folder_path}[/cyan]")
        if force:
            console.print("[yellow]Force mode: will re-classify all notes[/yellow]")
        if dry_run:
            console.print("[yellow]Dry run mode: no changes will be made[/yellow]")
        console.print()
        
        stats = {'total': len(md_files), 'classified': 0, 'skipped': 0, 'failed': 0}
        
        for i, md_file in enumerate(md_files, 1):
            relative_path = str(md_file.relative_to(self.vault_path))
            console.print(f"[dim][{i}/{len(md_files)}][/dim] ", end="")
            
            success, result, error = await self.classify_note(
                task_tag, relative_path, force=force, dry_run=dry_run
            )
            
            if error == "already_classified":
                stats['skipped'] += 1
            elif error == "dry_run":
                stats['classified'] += 1  # Would be classified
            elif success:
                stats['classified'] += 1
            else:
                stats['failed'] += 1
        
        # Print summary
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total: {stats['total']}")
        console.print(f"  [green]Classified: {stats['classified']}[/green]")
        console.print(f"  [dim]Skipped: {stats['skipped']}[/dim]")
        if stats['failed'] > 0:
            console.print(f"  [red]Failed: {stats['failed']}[/red]")
        
        return stats
    
    async def classify_notes(
        self,
        task_tags: List[str],
        note_path: Optional[str] = None,
        folder_path: Optional[str] = None,
        force: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run multiple classification tasks on note(s).
        
        Args:
            task_tags: List of task tags to run
            note_path: Single note path (mutually exclusive with folder_path)
            folder_path: Folder path (mutually exclusive with note_path)
            force: If True, re-classify even if already classified
            dry_run: If True, don't actually modify notes
        
        Returns:
            Dict mapping task_tag to stats
        """
        if note_path and folder_path:
            raise ValueError("Cannot specify both note_path and folder_path")
        if not note_path and not folder_path:
            raise ValueError("Must specify either note_path or folder_path")
        
        results = {}
        
        for task_tag in task_tags:
            if note_path:
                success, result, error = await self.classify_note(
                    task_tag, note_path, force=force, dry_run=dry_run
                )
                results[task_tag] = {
                    'total': 1,
                    'classified': 1 if success and error not in ('already_classified', 'dry_run') else 0,
                    'skipped': 1 if error == 'already_classified' else 0,
                    'failed': 0 if success else 1,
                    'error': error if not success else None
                }
            else:
                results[task_tag] = await self.classify_folder(
                    task_tag, folder_path, force=force, dry_run=dry_run
                )
        
        return results

