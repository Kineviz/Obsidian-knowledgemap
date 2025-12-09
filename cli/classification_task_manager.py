#!/usr/bin/env python3
"""
Classification Task Manager CLI

Manage and run classification tasks on Obsidian notes.

Usage:
    # List all tasks
    uv run classification_task_manager.py list-tasks
    
    # Add a new task
    uv run classification_task_manager.py add-task --tag gxr_interests --prompt "Extract interests" --output-type list
    
    # Run classification on a single note
    uv run classification_task_manager.py run gxr_interests --note "People/John.md"
    
    # Run classification on a folder
    uv run classification_task_manager.py run gxr_interests --folder "People/"
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table

# Add cli directory to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDefinition, OutputType, TaskType, TagSchema, TaskDatabase, Classifier
from config_loader import get_config_loader

console = Console()


def get_vault_path() -> Path:
    """Get vault path from config"""
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        console.print("[red]Error: Vault path not configured[/red]")
        console.print("[yellow]Set vault.path in config.yaml or VAULT_PATH environment variable[/yellow]")
        sys.exit(1)
    return Path(vault_path)


def get_db() -> TaskDatabase:
    """Get TaskDatabase instance"""
    vault_path = get_vault_path()
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    return TaskDatabase(db_path)


# ==================== CLI Groups ====================

@click.group()
def cli():
    """Classification Task Manager - Manage and run classification tasks on Obsidian notes"""
    pass


# ==================== Task Management Commands ====================

@cli.command('list-tasks')
@click.option('--enabled-only', is_flag=True, help='Show only enabled tasks')
def list_tasks(enabled_only: bool):
    """List all classification tasks"""
    db = get_db()
    tasks = db.get_all_tasks(enabled_only=enabled_only)
    
    if not tasks:
        console.print("[yellow]No tasks found[/yellow]")
        if not enabled_only:
            console.print("[dim]Use 'add-task' to create a new task[/dim]")
        return
    
    table = Table(title="Classification Tasks")
    table.add_column("Tag", style="cyan")
    table.add_column("Name")
    table.add_column("Type", style="green")
    table.add_column("Task Type", style="blue")
    table.add_column("Enabled", justify="center")
    table.add_column("Description")
    
    for task in tasks:
        enabled = "✓" if task.enabled else "✗"
        enabled_style = "green" if task.enabled else "red"
        task_type_display = "multi" if task.task_type == TaskType.MULTI else "single"
        if task.task_type == TaskType.MULTI and task.tag_schema:
            task_type_display += f" ({len(task.tag_schema)} tags)"
        table.add_row(
            task.tag,
            task.name or "-",
            task.output_type.value,
            task_type_display,
            f"[{enabled_style}]{enabled}[/{enabled_style}]",
            (task.description or "-")[:50] + "..." if task.description and len(task.description) > 50 else (task.description or "-")
        )
    
    console.print(table)


@cli.command('show-task')
@click.argument('tag')
def show_task(tag: str):
    """Show details of a specific task"""
    db = get_db()
    task = db.get_task(tag)
    
    if not task:
        console.print(f"[red]Task not found: {tag}[/red]")
        return
    
    task_type_str = "Multi-Tag" if task.task_type == TaskType.MULTI else "Single-Tag"
    task_type_color = "purple" if task.task_type == TaskType.MULTI else "blue"
    
    console.print(f"\n[bold cyan]Task: {task.tag}[/bold cyan] [{task_type_color}]{task_type_str}[/{task_type_color}]")
    console.print(f"  Name: {task.name or '-'}")
    console.print(f"  Description: {task.description or '-'}")
    console.print(f"  Output Type: [green]{task.output_type.value}[/green]")
    console.print(f"  Model Override: {task.model or 'default'}")
    console.print(f"  Enabled: {'[green]Yes[/green]' if task.enabled else '[red]No[/red]'}")
    console.print(f"  Created: {task.created_at}")
    console.print(f"  Updated: {task.updated_at}")
    
    if task.task_type == TaskType.MULTI and task.tag_schema:
        console.print(f"\n[bold]Tag Schema ({len(task.tag_schema)} tags):[/bold]")
        for ts in task.tag_schema:
            console.print(f"  • [cyan]{ts.tag}[/cyan] ({ts.output_type.value})")
            if ts.name:
                console.print(f"    Name: {ts.name}")
            if ts.description:
                console.print(f"    Description: {ts.description}")
    
    console.print(f"\n[bold]Prompt:[/bold]")
    console.print(f"  {task.prompt}")


@cli.command('add-task')
@click.option('--tag', required=True, help='Unique tag (must start with gxr_)')
@click.option('--prompt', required=True, help='LLM prompt for classification')
@click.option('--name', default=None, help='Human-readable name')
@click.option('--description', default=None, help='Task description')
@click.option('--output-type', type=click.Choice(['list', 'text', 'boolean', 'number']), required=True, help='Output type (for single-tag tasks)')
@click.option('--task-type', type=click.Choice(['single', 'multi']), default='single', help='Task type: single or multi')
@click.option('--tag-schema', default=None, help='Tag schema JSON file path (for multi-tag tasks)')
@click.option('--model', default=None, help='Override LLM model')
def add_task(tag: str, prompt: str, name: str, description: str, output_type: str, task_type: str, tag_schema: str, model: str):
    """Add a new classification task
    
    For multi-tag tasks, use --tag-schema to specify a JSON file with tag definitions.
    Example tag-schema.json:
    [
        {"tag": "gxr_vc_stages", "output_type": "list", "name": "Stages"},
        {"tag": "gxr_vc_sectors", "output_type": "list", "name": "Sectors"}
    ]
    """
    db = get_db()
    
    # Check if tag already exists
    if db.get_task(tag):
        console.print(f"[red]Task already exists: {tag}[/red]")
        console.print("[yellow]Use 'edit-task' to modify existing task[/yellow]")
        return
    
    try:
        # Parse tag schema for multi-tag tasks
        tag_schema_list = None
        if task_type == 'multi':
            if not tag_schema:
                console.print("[red]Error: --tag-schema is required for multi-tag tasks[/red]")
                console.print("[yellow]Use --tag-schema <json-file> to specify tag definitions[/yellow]")
                return
            
            import json
            schema_path = Path(tag_schema)
            if not schema_path.exists():
                console.print(f"[red]Tag schema file not found: {tag_schema}[/red]")
                return
            
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)
            
            tag_schema_list = [
                TagSchema(
                    tag=item['tag'],
                    output_type=OutputType(item['output_type']),
                    name=item.get('name'),
                    description=item.get('description')
                )
                for item in schema_data
            ]
        
        task = TaskDefinition(
            tag=tag,
            task_type=TaskType(task_type),
            prompt=prompt,
            name=name,
            description=description,
            output_type=OutputType(output_type),
            tag_schema=tag_schema_list,
            model=model,
            enabled=True
        )
        
        task_id = db.create_task(task)
        task_type_str = "multi-tag" if task_type == 'multi' else "single-tag"
        console.print(f"[green]✓ Created {task_type_str} task: {tag} (id={task_id})[/green]")
        if task_type == 'multi' and tag_schema_list:
            console.print(f"[dim]  Tags: {len(tag_schema_list)} tags defined[/dim]")
        
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing tag schema JSON: {e}[/red]")


@cli.command('edit-task')
@click.argument('tag')
@click.option('--prompt', default=None, help='New prompt')
@click.option('--name', default=None, help='New name')
@click.option('--description', default=None, help='New description')
@click.option('--output-type', type=click.Choice(['list', 'text', 'boolean', 'number']), default=None, help='New output type')
@click.option('--tag-schema', default=None, help='Tag schema JSON file path (for multi-tag tasks)')
@click.option('--model', default=None, help='New model override')
def edit_task(tag: str, prompt: str, name: str, description: str, output_type: str, tag_schema: str, model: str):
    """Edit an existing task
    
    For multi-tag tasks, use --tag-schema to update tag definitions.
    """
    db = get_db()
    
    task = db.get_task(tag)
    if not task:
        console.print(f"[red]Task not found: {tag}[/red]")
        return
    
    updates = {}
    if prompt is not None:
        updates['prompt'] = prompt
    if name is not None:
        updates['name'] = name
    if description is not None:
        updates['description'] = description
    if output_type is not None:
        updates['output_type'] = OutputType(output_type)
    if model is not None:
        updates['model'] = model
    
    # Handle tag schema update for multi-tag tasks
    if tag_schema is not None:
        if task.task_type != TaskType.MULTI:
            console.print("[yellow]Warning: --tag-schema only applies to multi-tag tasks[/yellow]")
        else:
            import json
            schema_path = Path(tag_schema)
            if not schema_path.exists():
                console.print(f"[red]Tag schema file not found: {tag_schema}[/red]")
                return
            
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)
            
            tag_schema_list = [
                TagSchema(
                    tag=item['tag'],
                    output_type=OutputType(item['output_type']),
                    name=item.get('name'),
                    description=item.get('description')
                )
                for item in schema_data
            ]
            updates['tag_schema'] = tag_schema_list
    
    if not updates:
        console.print("[yellow]No updates provided[/yellow]")
        return
    
    if db.update_task(tag, updates):
        console.print(f"[green]✓ Updated task: {tag}[/green]")
    else:
        console.print(f"[red]Failed to update task: {tag}[/red]")


@cli.command('enable-task')
@click.argument('tag')
def enable_task(tag: str):
    """Enable a task"""
    db = get_db()
    if db.enable_task(tag):
        console.print(f"[green]✓ Enabled task: {tag}[/green]")
    else:
        console.print(f"[red]Task not found: {tag}[/red]")


@cli.command('disable-task')
@click.argument('tag')
def disable_task(tag: str):
    """Disable a task"""
    db = get_db()
    if db.disable_task(tag):
        console.print(f"[green]✓ Disabled task: {tag}[/green]")
    else:
        console.print(f"[red]Task not found: {tag}[/red]")


@cli.command('delete-task')
@click.argument('tag')
@click.confirmation_option(prompt='Are you sure you want to delete this task?')
def delete_task(tag: str):
    """Delete a task"""
    db = get_db()
    if db.delete_task(tag):
        console.print(f"[green]✓ Deleted task: {tag}[/green]")
    else:
        console.print(f"[red]Task not found: {tag}[/red]")


@cli.command('export-tasks')
@click.option('--output', '-o', default='classification_tasks.yaml', help='Output file path')
def export_tasks(output: str):
    """Export all tasks to YAML file"""
    db = get_db()
    yaml_content = db.export_tasks_to_yaml()
    
    output_path = Path(output)
    output_path.write_text(yaml_content, encoding='utf-8')
    
    tasks = db.get_all_tasks()
    console.print(f"[green]✓ Exported {len(tasks)} tasks to {output}[/green]")


@cli.command('import-tasks')
@click.argument('input_file', type=click.Path(exists=True))
def import_tasks(input_file: str):
    """Import tasks from YAML file"""
    db = get_db()
    
    yaml_content = Path(input_file).read_text(encoding='utf-8')
    imported = db.import_tasks_from_yaml(yaml_content)
    
    console.print(f"[green]✓ Imported {imported} tasks from {input_file}[/green]")


# ==================== Classification Commands ====================

@cli.command('run')
@click.argument('tags', nargs=-1, required=True)
@click.option('--note', default=None, help='Single note path (relative to vault)')
@click.option('--folder', default=None, help='Folder path (relative to vault)')
@click.option('--force', is_flag=True, help='Re-classify even if already classified')
@click.option('--dry-run', is_flag=True, help='Preview what would be classified')
@click.option('--store-timestamp', is_flag=True, help='Also store gxr_xxx_at timestamp (off by default)')
def run_classification(tags: tuple, note: str, folder: str, force: bool, dry_run: bool, store_timestamp: bool):
    """Run classification task(s) on note(s)
    
    TAGS: One or more task tags to run (e.g., gxr_professional_interests)
    
    Examples:
    
        # Single note
        uv run classification_task_manager.py run gxr_interests --note "People/John.md"
        
        # Folder
        uv run classification_task_manager.py run gxr_interests --folder "People/"
        
        # Multiple tasks
        uv run classification_task_manager.py run gxr_interests gxr_is_investor --folder "People/"
        
        # Force re-classify
        uv run classification_task_manager.py run gxr_interests --folder "People/" --force
        
        # Store timestamp (gxr_xxx_at)
        uv run classification_task_manager.py run gxr_interests --folder "People/" --store-timestamp
    """
    if not note and not folder:
        console.print("[red]Error: Must specify either --note or --folder[/red]")
        return
    if note and folder:
        console.print("[red]Error: Cannot specify both --note and --folder[/red]")
        return
    
    vault_path = get_vault_path()
    classifier = Classifier(vault_path)
    
    async def run():
        return await classifier.classify_notes(
            task_tags=list(tags),
            note_path=note,
            folder_path=folder,
            force=force,
            dry_run=dry_run,
            store_timestamp=store_timestamp
        )
    
    asyncio.run(run())


@cli.command('remove-tag')
@click.argument('tag')
@click.option('--note', default=None, help='Single note path (relative to vault)')
@click.option('--folder', default=None, help='Folder path (relative to vault)')
@click.option('--dry-run', is_flag=True, help='Preview what would be removed')
def remove_tag(tag: str, note: str, folder: str, dry_run: bool):
    """Remove a metadata tag from note(s)
    
    TAG: The tag to remove (e.g., gxr_is_investor_at)
    
    Examples:
    
        # Remove from single note
        uv run classification_task_manager.py remove-tag gxr_is_investor_at --note "People/John.md"
        
        # Remove from all notes in folder
        uv run classification_task_manager.py remove-tag gxr_is_investor_at --folder "Persons/"
        
        # Dry run (preview)
        uv run classification_task_manager.py remove-tag gxr_is_investor_at --folder "Persons/" --dry-run
    """
    if not note and not folder:
        console.print("[red]Error: Must specify either --note or --folder[/red]")
        return
    if note and folder:
        console.print("[red]Error: Cannot specify both --note and --folder[/red]")
        return
    
    vault_path = get_vault_path()
    classifier = Classifier(vault_path)
    
    if note:
        classifier.remove_tag_from_note(note, tag, dry_run=dry_run)
    else:
        classifier.remove_tag_from_folder(folder, tag, dry_run=dry_run)


# ==================== Status Commands ====================

@cli.command('status')
@click.argument('tag')
@click.option('--folder', default=None, help='Filter by folder')
def task_status(tag: str, folder: str):
    """Show classification status for a task"""
    db = get_db()
    status = db.get_task_status(tag, folder)
    
    if not status:
        console.print(f"[red]Task not found: {tag}[/red]")
        return
    
    task = status['task']
    console.print(f"\n[bold cyan]Task: {task.get_display_name()} ({tag})[/bold cyan]")
    console.print(f"  Type: [green]{task.output_type.value}[/green]")
    console.print(f"  Enabled: {'[green]Yes[/green]' if task.enabled else '[red]No[/red]'}")
    console.print()
    console.print(f"[bold]Run Statistics:[/bold]")
    console.print(f"  Total runs: {status['total']}")
    console.print(f"  [green]Completed: {status['completed']}[/green]")
    console.print(f"  [red]Failed: {status['failed']}[/red]")
    console.print(f"  Running: {status['running']}")


@cli.command('history')
@click.argument('tag')
@click.option('--limit', default=20, help='Number of records to show')
def task_history(tag: str, limit: int):
    """Show run history for a task"""
    db = get_db()
    
    task = db.get_task(tag)
    if not task:
        console.print(f"[red]Task not found: {tag}[/red]")
        return
    
    history = db.get_run_history(tag, limit)
    
    if not history:
        console.print(f"[yellow]No run history for: {tag}[/yellow]")
        return
    
    table = Table(title=f"Run History: {tag}")
    table.add_column("Note", style="cyan")
    table.add_column("Status")
    table.add_column("Result")
    table.add_column("Time (ms)")
    table.add_column("Date")
    
    for run in history:
        status_style = {
            'completed': 'green',
            'failed': 'red',
            'running': 'yellow',
            'pending': 'dim'
        }.get(run['status'], 'white')
        
        result_display = run['result'] or run.get('error') or '-'
        if len(result_display) > 40:
            result_display = result_display[:40] + "..."
        
        table.add_row(
            run['note_path'],
            f"[{status_style}]{run['status']}[/{status_style}]",
            result_display,
            str(run['processing_time_ms'] or '-'),
            run['created_at'].strftime('%Y-%m-%d %H:%M') if run['created_at'] else '-'
        )
    
    console.print(table)


if __name__ == '__main__':
    cli()

