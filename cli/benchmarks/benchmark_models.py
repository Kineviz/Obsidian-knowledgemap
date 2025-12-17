#!/usr/bin/env python3
"""
Benchmark script to compare different LLM models for:
1. Knowledge Map extraction (relationship extraction)
2. VC multi-tag classification

Models tested:
- qwen3:8b (Ollama)
- qwen3:14b (Ollama)
- llama3.1:8b (Ollama)
- gpt-4o-mini (OpenAI)
"""

import sys
import asyncio
import time
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Add cli to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from llm_client import LLMClient
from config_loader import get_config_loader
from classification.classifier import Classifier
from classification.database import TaskDatabase
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run"""
    model: str
    provider: str
    task_type: str  # "knowledge_map" or "vc_classification"
    success: bool
    response_time: float  # seconds
    token_count: Optional[int] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    accuracy_score: Optional[float] = None  # 0.0-1.0, if we can measure it

class ModelBenchmark:
    """Benchmark different models for knowledge extraction and classification"""
    
    def __init__(self, test_file: Path):
        self.test_file = Path(test_file)
        if not self.test_file.exists():
            raise FileNotFoundError(f"Test file not found: {test_file}")
        
        self.test_content = self.test_file.read_text(encoding='utf-8')
        console.print(f"[green]Loaded test file: {self.test_file}[/green]")
        console.print(f"[dim]File size: {len(self.test_content)} characters[/dim]\n")
        
        # Initialize components
        self.config = get_config_loader()
        self.results: List[BenchmarkResult] = []
        
        # Models to test
        self.models = [
            {"name": "qwen3:8b", "provider": "ollama", "server": "http://bsrs-mac-studio:11434"},
            {"name": "qwen3:14b", "provider": "ollama", "server": "http://bsrs-mac-studio:11434"},
            {"name": "llama3.1:8b", "provider": "ollama", "server": "http://bsrs-mac-studio:11434"},
            {"name": "gpt-4o-mini", "provider": "cloud", "server": None},  # Use "cloud" not "openai" for LLMProvider enum
        ]
    
    async def benchmark_knowledge_map_extraction(self, model_config: Dict[str, str]) -> BenchmarkResult:
        """Benchmark knowledge map relationship extraction"""
        console.print(f"[cyan]Testing {model_config['name']} for Knowledge Map extraction...[/cyan]")
        
        start_time = time.time()
        original_provider = None
        
        try:
            # Create LLM client - it will use the model from config
            # We need to temporarily modify the config
            original_provider = self.config.config_data.get('llm', {}).get('provider', 'cloud')
            if 'llm' not in self.config.config_data:
                self.config.config_data['llm'] = {}
            if model_config['provider'] == 'ollama':
                self.config.config_data['llm']['provider'] = 'ollama'
                if 'ollama' not in self.config.config_data['llm']:
                    self.config.config_data['llm']['ollama'] = {}
                self.config.config_data['llm']['ollama']['model'] = model_config['name']
            else:
                self.config.config_data['llm']['provider'] = 'cloud'
                if 'cloud' not in self.config.config_data['llm']:
                    self.config.config_data['llm']['cloud'] = {}
                if 'openai' not in self.config.config_data['llm']['cloud']:
                    self.config.config_data['llm']['cloud']['openai'] = {}
                self.config.config_data['llm']['cloud']['openai']['model'] = model_config['name']
            
            # Create fresh LLM client with updated config
            llm_client = LLMClient()
            
            # Build knowledge map extraction prompt
            from prompt_loader import PromptLoader
            prompt_loader = PromptLoader()
            system_prompt = prompt_loader.get_system_prompt("relationship_extraction").content
            user_prompt = prompt_loader.get_user_prompt("relationship_extraction", text=self.test_content).content
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Generate response
            response = await llm_client.generate(messages)
            
            response_time = time.time() - start_time
            
            if response.success:
                # Parse JSON response
                try:
                    # Clean up response - remove markdown code blocks if present
                    content = response.content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    elif content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    # Try to find JSON object (some models add explanatory text)
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_content = content[json_start:json_end]
                        result = json.loads(json_content)
                    else:
                        # Try parsing the whole content
                        result = json.loads(content)
                    
                    relationships = result.get('relationships', [])
                    
                    return BenchmarkResult(
                        model=model_config['name'],
                        provider=model_config['provider'],
                        task_type="knowledge_map",
                        success=True,
                        response_time=response_time,
                        token_count=response.token_count,
                        result={"relationships_count": len(relationships), "relationships": relationships[:5]}  # First 5 for preview
                    )
                except json.JSONDecodeError as e:
                    return BenchmarkResult(
                        model=model_config['name'],
                        provider=model_config['provider'],
                        task_type="knowledge_map",
                        success=False,
                        response_time=response_time,
                        error=f"JSON parse error: {str(e)}"
                    )
            else:
                return BenchmarkResult(
                    model=model_config['name'],
                    provider=model_config['provider'],
                    task_type="knowledge_map",
                    success=False,
                    response_time=response_time,
                    error=response.error or "Unknown error"
                )
        
        except Exception as e:
            response_time = time.time() - start_time
            return BenchmarkResult(
                model=model_config['name'],
                provider=model_config['provider'],
                task_type="knowledge_map",
                success=False,
                response_time=response_time,
                error=str(e)
            )
        finally:
            # Restore original config
            if original_provider is not None and 'llm' in self.config.config_data:
                self.config.config_data['llm']['provider'] = original_provider
    
    async def benchmark_vc_classification(self, model_config: Dict[str, str]) -> BenchmarkResult:
        """Benchmark VC multi-tag classification"""
        console.print(f"[cyan]Testing {model_config['name']} for VC Classification...[/cyan]")
        
        start_time = time.time()
        original_provider = None
        original_model = None
        
        try:
            # Get VC analysis task
            vault_path = Path(self.config.get('vault.path'))
            # classification_task_manager uses .kineviz_graph/classification.db
            db_path = vault_path / ".kineviz_graph" / "classification.db"
            
            if not db_path.exists():
                return BenchmarkResult(
                    model=model_config['name'],
                    provider=model_config['provider'],
                    task_type="vc_classification",
                    success=False,
                    response_time=0,
                    error=f"Classification database not found: {db_path}"
                )
            
            task_db = TaskDatabase(db_path)
            task = task_db.get_task("_vc_analysis")
            
            # task was already retrieved above, now use it
            if not task:
                return BenchmarkResult(
                    model=model_config['name'],
                    provider=model_config['provider'],
                    task_type="vc_classification",
                    success=False,
                    response_time=0,
                    error="VC analysis task (_vc_analysis) not found"
                )
            
            # Temporarily override model in task
            original_model = task.model
            task.model = model_config['name']
            
            # Temporarily switch provider in config
            original_provider = self.config.config_data.get('llm', {}).get('provider', 'cloud')
            if 'llm' not in self.config.config_data:
                self.config.config_data['llm'] = {}
            
            # LLMProvider enum uses 'cloud' for OpenAI, not 'openai'
            provider = model_config['provider']
            if provider == 'openai':
                provider = 'cloud'
            
            if provider == 'ollama':
                self.config.config_data['llm']['provider'] = 'ollama'
                if 'ollama' not in self.config.config_data['llm']:
                    self.config.config_data['llm']['ollama'] = {}
                self.config.config_data['llm']['ollama']['model'] = model_config['name']
            else:
                self.config.config_data['llm']['provider'] = 'cloud'
                if 'cloud' not in self.config.config_data['llm']:
                    self.config.config_data['llm']['cloud'] = {}
                if 'openai' not in self.config.config_data['llm']['cloud']:
                    self.config.config_data['llm']['cloud']['openai'] = {}
                self.config.config_data['llm']['cloud']['openai']['model'] = model_config['name']
            
            # Create classifier (it will use the updated config)
            # Classifier takes vault_path and optional llm_client, not task_db
            classifier = Classifier(vault_path)
            
            # Run classification
            success, result, error = await classifier.classify_note(
                task_tag="_vc_analysis",
                note_path=str(self.test_file.relative_to(vault_path)),
                force=True,  # Force re-classification
                dry_run=False
            )
            
            response_time = time.time() - start_time
            
            # Restore original model and config
            if original_model is not None:
                task.model = original_model
            if original_provider is not None and 'llm' in self.config.config_data:
                self.config.config_data['llm']['provider'] = original_provider
            
            if success:
                return BenchmarkResult(
                    model=model_config['name'],
                    provider=model_config['provider'],
                    task_type="vc_classification",
                    success=True,
                    response_time=response_time,
                    result=result
                )
            else:
                return BenchmarkResult(
                    model=model_config['name'],
                    provider=model_config['provider'],
                    task_type="vc_classification",
                    success=False,
                    response_time=response_time,
                    error=error or "Unknown error"
                )
        
        except Exception as e:
            response_time = time.time() - start_time
            return BenchmarkResult(
                model=model_config['name'],
                provider=model_config['provider'],
                task_type="vc_classification",
                success=False,
                response_time=response_time,
                error=str(e)
            )
    
    async def run_all_benchmarks(self):
        """Run all benchmarks for all models"""
        console.print(Panel.fit("[bold]Model Benchmark Suite[/bold]\nComparing models for Knowledge Map extraction and VC classification", border_style="cyan"))
        console.print()
        
        for model_config in self.models:
            console.print(f"\n[bold yellow]{'='*80}[/bold yellow]")
            console.print(f"[bold yellow]Testing Model: {model_config['name']} ({model_config['provider']})[/bold yellow]")
            console.print(f"[bold yellow]{'='*80}[/bold yellow]\n")
            
            # Knowledge Map extraction
            km_result = await self.benchmark_knowledge_map_extraction(model_config)
            self.results.append(km_result)
            
            if km_result.success:
                console.print(f"[green]✓ Knowledge Map: {km_result.response_time:.2f}s, {km_result.result.get('relationships_count', 0)} relationships[/green]")
            else:
                console.print(f"[red]✗ Knowledge Map: {km_result.error}[/red]")
            
            # Small delay between tests
            await asyncio.sleep(1)
            
            # VC Classification
            vc_result = await self.benchmark_vc_classification(model_config)
            self.results.append(vc_result)
            
            if vc_result.success:
                console.print(f"[green]✓ VC Classification: {vc_result.response_time:.2f}s[/green]")
            else:
                console.print(f"[red]✗ VC Classification: {vc_result.error}[/red]")
            
            # Delay between models
            await asyncio.sleep(2)
    
    def print_results_table(self):
        """Print results in a formatted table"""
        console.print("\n")
        console.print(Panel.fit("[bold]Benchmark Results Summary[/bold]", border_style="green"))
        console.print()
        
        # Knowledge Map Results
        km_table = Table(title="Knowledge Map Extraction", show_header=True, header_style="bold magenta")
        km_table.add_column("Model", style="cyan")
        km_table.add_column("Provider", style="dim")
        km_table.add_column("Success", justify="center")
        km_table.add_column("Time (s)", justify="right")
        km_table.add_column("Relationships", justify="right")
        km_table.add_column("Error", style="red")
        
        km_results = [r for r in self.results if r.task_type == "knowledge_map"]
        for result in km_results:
            km_table.add_row(
                result.model,
                result.provider,
                "✓" if result.success else "✗",
                f"{result.response_time:.2f}" if result.success else "-",
                str(result.result.get('relationships_count', 0)) if result.success and result.result else "-",
                result.error or ""
            )
        
        console.print(km_table)
        console.print()
        
        # VC Classification Results
        vc_table = Table(title="VC Multi-Tag Classification", show_header=True, header_style="bold magenta")
        vc_table.add_column("Model", style="cyan")
        vc_table.add_column("Provider", style="dim")
        vc_table.add_column("Success", justify="center")
        vc_table.add_column("Time (s)", justify="right")
        vc_table.add_column("Error", style="red")
        
        vc_results = [r for r in self.results if r.task_type == "vc_classification"]
        for result in vc_results:
            vc_table.add_row(
                result.model,
                result.provider,
                "✓" if result.success else "✗",
                f"{result.response_time:.2f}" if result.success else "-",
                result.error or ""
            )
        
        console.print(vc_table)
        console.print()
        
        # Speed Comparison
        speed_table = Table(title="Speed Comparison (seconds)", show_header=True, header_style="bold yellow")
        speed_table.add_column("Model", style="cyan")
        speed_table.add_column("Knowledge Map", justify="right")
        speed_table.add_column("VC Classification", justify="right")
        speed_table.add_column("Total", justify="right")
        
        for model_config in self.models:
            model_name = model_config['name']
            km_result = next((r for r in km_results if r.model == model_name), None)
            vc_result = next((r for r in vc_results if r.model == model_name), None)
            
            km_time = f"{km_result.response_time:.2f}" if km_result and km_result.success else "N/A"
            vc_time = f"{vc_result.response_time:.2f}" if vc_result and vc_result.success else "N/A"
            
            if km_result and km_result.success and vc_result and vc_result.success:
                total = km_result.response_time + vc_result.response_time
                total_str = f"{total:.2f}"
            else:
                total_str = "N/A"
            
            speed_table.add_row(model_name, km_time, vc_time, total_str)
        
        console.print(speed_table)
    
    def save_results(self, output_file: Path):
        """Save results to JSON file"""
        output_data = {
            "test_file": str(self.test_file),
            "test_file_size": len(self.test_content),
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results]
        }
        
        output_file.write_text(json.dumps(output_data, indent=2), encoding='utf-8')
        console.print(f"\n[green]Results saved to: {output_file}[/green]")

async def main():
    """Main benchmark function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark LLM models for knowledge extraction and classification")
    parser.add_argument("test_file", type=str, help="Path to test markdown file (relative to vault or absolute)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output JSON file for results")
    
    args = parser.parse_args()
    
    # Resolve test file path
    config = get_config_loader()
    vault_path = Path(config.get('vault.path'))
    test_file = Path(args.test_file)
    
    # If relative path, resolve against vault
    if not test_file.is_absolute():
        test_file = vault_path / test_file
    
    if not test_file.exists():
        console.print(f"[red]Error: Test file not found: {test_file}[/red]")
        console.print(f"[yellow]Vault path: {vault_path}[/yellow]")
        console.print(f"[yellow]Try: Companies/VC/Eniac Ventures.md[/yellow]")
        sys.exit(1)
    
    benchmark = ModelBenchmark(test_file)
    await benchmark.run_all_benchmarks()
    benchmark.print_results_table()
    
    if args.output:
        benchmark.save_results(args.output)
    else:
        # Default output file
        output_file = Path(__file__).parent / f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        benchmark.save_results(output_file)

if __name__ == "__main__":
    asyncio.run(main())

