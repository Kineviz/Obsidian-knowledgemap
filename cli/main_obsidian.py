#!/usr/bin/env python3
"""
Knowledge Map Tool - Main orchestrator
This script coordinates the 3-step process:
1. Extract relationships from markdown folder to cache/content/
2. Organize cache/content/*.csv to cache/db_input/
3. Build Kuzu database from cache/db_input/
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console

# Load environment variables
load_dotenv()

console = Console()


def run_step(step: str, args: list = None) -> bool:
    """Run a specific step with given arguments"""
    if args is None:
        args = []
    
    try:
        step_files = {
            "1": "step1_extract.py",
            "2": "step2_organize.py", 
            "3": "step3_build.py",
            "4": "step4_monitor.py"
        }
        cmd = [sys.executable, step_files[step]] + args
        console.print(f"[cyan]Running step {step}: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, check=True, capture_output=False)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Step {step} failed with exit code {e.returncode}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Error running step {step}: {e}[/red]")
        return False


@click.command()
@click.argument("vault_path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
               required=False, default=lambda: os.getenv("VAULT_PATH"))
@click.option("--openai-api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
@click.option("--max-concurrent", default=5, help="Maximum number of concurrent file processing tasks")
@click.option("--chunk-threshold", default=0.75, help="Semantic similarity threshold for chunking (0.0-1.0)")
@click.option("--chunk-size", default=1024, help="Maximum chunk size in tokens")
@click.option("--embedding-model", default="minishlab/potion-base-8M", help="Embedding model for semantic chunking")
@click.option("--chunking-backend", default="recursive-markdown", help="Chunking backend to use")
@click.option("--step", type=click.Choice(["1", "2", "3", "4", "all"]), default="all", help="Which step to run: 1=extract, 2=organize, 3=build, 4=monitor, all=run all steps")
@click.option("--query", help="Execute a query on the database (step 3 only)")
def main(
    vault_path: Optional[Path],
    openai_api_key: Optional[str],
    max_concurrent: int,
    chunk_threshold: float,
    chunk_size: int,
    embedding_model: str,
    chunking_backend: str,
    step: str,
    query: Optional[str],
):
    """Knowledge Map Tool - Convert Obsidian vault to a Kuzu knowledge graph"""
    
    console.print("[bold cyan]Knowledge Map Tool - Obsidian Vault Integration[/bold cyan]")
    console.print("=" * 60)
    
    # Validate vault path
    if not vault_path:
        console.print("[red]Error: vault_path is required[/red]")
        console.print("[yellow]Example: uv run main_obsidian.py /path/to/obsidian-vault[/yellow]")
        console.print("[yellow]Or set VAULT_PATH in your .env file[/yellow]")
        sys.exit(1)
    
    # Validate it's a valid Obsidian vault (has .obsidian directory)
    obsidian_config = vault_path / ".obsidian"
    if not obsidian_config.exists():
        console.print(f"[yellow]Warning: {vault_path} doesn't appear to be an Obsidian vault (no .obsidian directory)[/yellow]")
        console.print("Continuing anyway...")
    
    # Set up vault-relative paths
    kineviz_dir = vault_path / ".kineviz_graph"
    cache_dir = kineviz_dir / "cache"
    content_dir = cache_dir / "content"
    db_input_dir = cache_dir / "db_input"
    database_dir = kineviz_dir / "database"
    config_dir = kineviz_dir / "config"
    logs_dir = kineviz_dir / "logs"
    
    # Create directory structure
    for dir_path in [kineviz_dir, cache_dir, content_dir, db_input_dir, database_dir, config_dir, logs_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    console.print(f"[green]Vault: {vault_path}[/green]")
    console.print(f"[green]Knowledge Graph: {kineviz_dir}[/green]")
    
    # Common arguments for all steps
    common_args = [
        "--vault-path", str(vault_path),
        "--chunk-threshold", str(chunk_threshold),
        "--chunk-size", str(chunk_size),
        "--embedding-model", embedding_model,
        "--chunking-backend", chunking_backend,
    ]
    
    if openai_api_key:
        common_args.extend(["--openai-api-key", openai_api_key])
    
    success = True
    
    if step == "1" or step == "all":
        console.print("\n[bold cyan]Step 1: Extract relationships from Obsidian vault[/bold cyan]")
        step1_args = ["--max-concurrent", str(max_concurrent)] + common_args
        success = run_step("1", step1_args)
        if not success:
            console.print("[red]Step 1 failed[/red]")
            sys.exit(1)
    
    if step == "2" or step == "all":
        console.print("\n[bold cyan]Step 2: Organize cache/content/*.csv to cache/db_input/[/bold cyan]")
        step2_args = ["--vault-path", str(vault_path)]
        success = run_step("2", step2_args)
        if not success:
            console.print("[red]Step 2 failed[/red]")
            sys.exit(1)
    
    if step == "3" or step == "all":
        console.print("\n[bold cyan]Step 3: Build Kuzu database from cache/db_input/[/bold cyan]")
        db_path = str(database_dir / "knowledge_graph.kz")
        step3_args = ["--vault-path", str(vault_path), "--db-path", db_path]
        if query:
            step3_args.extend(["--query", query])
        
        success = run_step("3", step3_args)
        if not success:
            console.print("[red]Step 3 failed[/red]")
            sys.exit(1)
    
    if step == "4":
        console.print("\n[bold cyan]Step 4: Monitor vault for changes[/bold cyan]")
        step4_args = ["--vault-path", str(vault_path), "--max-concurrent", str(max_concurrent)]
        success = run_step("4", step4_args)
        if not success:
            console.print("[red]Step 4 failed[/red]")
            sys.exit(1)
    
    if success:
        console.print("\n[bold green]All steps completed successfully![/bold green]")
        if step == "3" or step == "all":
            console.print(f"[green]Database created at: {database_dir / 'knowledge_graph.kz'}[/green]")
        else:
            console.print(f"[green]Knowledge graph data stored in: {kineviz_dir}[/green]")
        
        if not query and (step == "3" or step == "all"):
            db_path = str(database_dir / "knowledge_graph.kz")
            console.print("\n[cyan]Example queries you can run:[/cyan]")
            console.print(f"uv run step3_build.py --vault-path {vault_path} --query \"MATCH (p:Person) RETURN p.label LIMIT 5\"")
            console.print(f"uv run step3_build.py --vault-path {vault_path} --query \"MATCH (p:Person)-[r]->(c:Company) RETURN p.label, r.relationship, c.label LIMIT 5\"")


if __name__ == "__main__":
    main()
