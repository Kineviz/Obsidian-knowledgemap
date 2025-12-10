#!/usr/bin/env python3
"""
Test llama3.1:8b for both Knowledge Map extraction and Classification tasks
"""

import sys
import asyncio
import json
from pathlib import Path

# Add cli to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from llm_client import LLMClient
from config_loader import get_config_loader
from prompt_loader import PromptLoader
from classification.database import TaskDatabase
from classification.classifier import Classifier
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()

async def test_knowledge_map_extraction(test_file: Path):
    """Test Knowledge Map extraction with llama3.1:8b"""
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold cyan]Test 1: Knowledge Map Extraction[/bold cyan]")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")
    
    config = get_config_loader()
    vault_path = Path(config.get('vault.path'))
    
    if not test_file.is_absolute():
        test_file = vault_path / test_file
    
    if not test_file.exists():
        console.print(f"[red]Error: Test file not found: {test_file}[/red]")
        return False
    
    test_content = test_file.read_text(encoding='utf-8')
    console.print(f"[green]Test file: {test_file}[/green]")
    console.print(f"[dim]File size: {len(test_content)} characters[/dim]\n")
    
    # Verify config
    provider = config.get('llm.provider')
    model = config.get('llm.ollama.model') if provider == 'ollama' else config.get('llm.cloud.openai.model')
    console.print(f"[dim]Provider: {provider}, Model: {model}[/dim]\n")
    
    if provider != 'ollama' or model != 'llama3.1:8b':
        console.print(f"[yellow]Warning: Config shows {provider}/{model}, expected ollama/llama3.1:8b[/yellow]")
    
    # Create LLM client
    llm_client = LLMClient()
    
    # Build prompt
    prompt_loader = PromptLoader()
    system_prompt = prompt_loader.get_system_prompt("relationship_extraction").content
    user_prompt = prompt_loader.get_user_prompt("relationship_extraction", text=test_content).content
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    console.print("[yellow]Sending request to llama3.1:8b...[/yellow]")
    import time
    start_time = time.time()
    
    # Generate response
    response = await llm_client.generate(messages)
    
    response_time = time.time() - start_time
    
    if not response.success:
        console.print(f"[red]✗ Failed: {response.error}[/red]")
        return False
    
    console.print(f"[green]✓ Response received in {response_time:.2f}s[/green]")
    
    # Parse JSON
    try:
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # Try to find JSON object
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        
        if json_start != -1 and json_end > json_start:
            json_content = content[json_start:json_end]
            
            # Fix common JSON issues from LLMs
            # Remove trailing commas before closing brackets/braces
            import re
            json_content = re.sub(r',(\s*[}\]])', r'\1', json_content)
            
            result = json.loads(json_content)
            relationships = result.get('relationships', [])
            
            console.print(f"[bold green]✓ Successfully parsed JSON![/bold green]")
            console.print(f"[green]Found {len(relationships)} relationships[/green]")
            
            # Show first few relationships
            if relationships:
                table = Table(title="Sample Relationships")
                table.add_column("Source", style="cyan")
                table.add_column("Relationship", style="yellow")
                table.add_column("Target", style="magenta")
                
                for rel in relationships[:5]:
                    table.add_row(
                        rel.get('source_label', 'N/A'),
                        rel.get('relationship', 'N/A'),
                        rel.get('target_label', 'N/A')
                    )
                console.print(table)
            
            return True
        else:
            console.print(f"[red]✗ No JSON object found in response[/red]")
            console.print(f"[yellow]Response starts with: {content[:200]}...[/yellow]")
            return False
            
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ JSON parse error: {e}[/red]")
        if hasattr(e, 'pos') and e.pos:
            start = max(0, e.pos - 50)
            end = min(len(content), e.pos + 50)
            console.print(f"\n[bold]Context around error:[/bold]")
            console.print(Syntax(content[start:end], "json", theme="monokai"))
        return False

async def test_classification(test_file: Path):
    """Test VC classification with llama3.1:8b"""
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold cyan]Test 2: VC Multi-Tag Classification[/bold cyan]")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")
    
    config = get_config_loader()
    vault_path = Path(config.get('vault.path'))
    
    if not test_file.is_absolute():
        test_file = vault_path / test_file
    
    if not test_file.exists():
        console.print(f"[red]Error: Test file not found: {test_file}[/red]")
        return False
    
    # Verify config
    provider = config.get('llm.provider')
    model = config.get('llm.ollama.model') if provider == 'ollama' else config.get('llm.cloud.openai.model')
    console.print(f"[dim]Provider: {provider}, Model: {model}[/dim]\n")
    
    if provider != 'ollama' or model != 'llama3.1:8b':
        console.print(f"[yellow]Warning: Config shows {provider}/{model}, expected ollama/llama3.1:8b[/yellow]")
    
    # Load VC analysis task - get db path from vault
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    task_db = TaskDatabase(db_path)
    task = task_db.get_task("gxr_vc_analysis")
    
    if not task:
        console.print(f"[red]✗ VC analysis task (gxr_vc_analysis) not found[/red]")
        console.print(f"[yellow]Run: uv run classification_task_manager.py add-task to create it[/yellow]")
        return False
    
    console.print(f"[green]Found task: {task.name}[/green]")
    console.print(f"[dim]Task type: {task.task_type}, Tags: {len(task.tag_schema)}[/dim]\n")
    
    # Create classifier - pass vault_path, not db_path
    classifier = Classifier(vault_path)
    
    # Test classification
    console.print(f"[yellow]Classifying: {test_file.name}[/yellow]")
    import time
    start_time = time.time()
    
    try:
        # Force re-classification to test the model
        success, result, error = await classifier.classify_note(task.tag, str(test_file), force=True)
        
        response_time = time.time() - start_time
        
        if success:
            console.print(f"[green]✓ Classification completed in {response_time:.2f}s[/green]")
            
            # result is a dict for multi-tag tasks
            if isinstance(result, dict):
                console.print(f"[green]Tags extracted: {len(result)}[/green]\n")
                
                # Show results
                table = Table(title="Classification Results")
                table.add_column("Tag", style="cyan")
                table.add_column("Value", style="yellow")
                
                for tag_name, tag_value in result.items():
                    # Truncate long values
                    value_str = str(tag_value)
                    if len(value_str) > 60:
                        value_str = value_str[:57] + "..."
                    table.add_row(tag_name, value_str)
                
                console.print(table)
                
                # Check if tags were written to file
                content = test_file.read_text(encoding='utf-8')
                if '---' in content:
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end != -1:
                        frontmatter = content[3:frontmatter_end]
                        console.print(f"\n[green]✓ Tags written to frontmatter[/green]")
                        for tag_name in result.keys():
                            if tag_name in frontmatter:
                                console.print(f"  [dim]✓ {tag_name}[/dim]")
            else:
                console.print(f"[green]Result: {result}[/green]")
            
            return True
        else:
            console.print(f"[red]✗ Classification failed: {error}[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]✗ Exception: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False

async def main():
    """Run both tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test llama3.1:8b for Knowledge Map and Classification")
    parser.add_argument("test_file", type=str, help="Path to test markdown file")
    parser.add_argument("--skip-km", action="store_true", help="Skip Knowledge Map test")
    parser.add_argument("--skip-class", action="store_true", help="Skip Classification test")
    
    args = parser.parse_args()
    
    test_file = Path(args.test_file)
    
    console.print(Panel.fit(
        "[bold]llama3.1:8b Test Suite[/bold]\n"
        "Testing Knowledge Map extraction and VC classification",
        border_style="cyan"
    ))
    
    results = {}
    
    # Test Knowledge Map extraction
    if not args.skip_km:
        results['knowledge_map'] = await test_knowledge_map_extraction(test_file)
    else:
        console.print("[yellow]Skipping Knowledge Map test[/yellow]")
    
    # Test Classification
    if not args.skip_class:
        results['classification'] = await test_classification(test_file)
    else:
        console.print("[yellow]Skipping Classification test[/yellow]")
    
    # Summary
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold cyan]Test Summary[/bold cyan]")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")
    
    summary_table = Table(title="Results")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Status", style="green")
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        style = "green" if passed else "red"
        summary_table.add_row(test_name.replace('_', ' ').title(), f"[{style}]{status}[/{style}]")
    
    console.print(summary_table)
    
    # Exit code
    all_passed = all(results.values()) if results else False
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())

