#!/usr/bin/env python3
"""
LLM Benchmarking Script
Compares different LLM setups for relationship extraction speed and accuracy
"""

import asyncio
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import aiohttp
import openai
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from prompt_loader import PromptLoader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

console = Console()

@dataclass
class LLMConfig:
    name: str
    type: str  # 'openai' or 'ollama'
    endpoint: str
    model: str
    api_key: Optional[str] = None
    timeout: int = 30

@dataclass
class BenchmarkResult:
    llm_name: str
    response_time: float
    success: bool
    error: Optional[str] = None
    extracted_relationships: List[Dict] = None
    accuracy_score: float = 0.0
    token_count: Optional[int] = None

class LLMBenchmark:
    def __init__(self):
        self.prompt_loader = PromptLoader()
        self.results: List[BenchmarkResult] = []
        
        # Load the full relationship extraction prompt pair
        self.system_prompt = self.prompt_loader.get_system_prompt("relationship_extraction").content
        self.user_prompt_template = self.prompt_loader.get_user_prompt("relationship_extraction", text="{text}").content
        
        # Test document content
        self.test_document = self._create_test_document()
        
        # Expected relationships for accuracy testing (~1024 chars)
        self.expected_relationships = [
            # Professional relationships
            {"source": "Alex Chen", "target": "TechFlow", "relationship": "ceo_of"},
            {"source": "Sarah Johnson", "target": "CloudSync Inc", "relationship": "vp_product_at"},
            {"source": "Dr. Mike Rodriguez", "target": "TechFlow", "relationship": "cso_of"},
            {"source": "Dr. Mike Rodriguez", "target": "Stanford University", "relationship": "professor_at"},
            
            # Personal relationships
            {"source": "Alex Chen", "target": "Sarah Johnson", "relationship": "married_to"},
            {"source": "Alex Chen", "target": "Dr. Mike Rodriguez", "relationship": "co_founded_with"},
            {"source": "Sarah Johnson", "target": "Dr. Mike Rodriguez", "relationship": "collaborates_with"},
            
            # Business partnerships
            {"source": "TechFlow", "target": "Google Cloud", "relationship": "partners_with"},
            {"source": "TechFlow", "target": "Microsoft Azure", "relationship": "partners_with"},
            {"source": "CloudSync Inc", "target": "Amazon Web Services", "relationship": "partners_with"},
            {"source": "CloudSync Inc", "target": "Microsoft Azure", "relationship": "partners_with"},
            
            # Educational background
            {"source": "Alex Chen", "target": "Stanford University", "relationship": "graduated_from"},
            {"source": "Sarah Johnson", "target": "UC Berkeley", "relationship": "graduated_from"},
            
            # Previous employment
            {"source": "Alex Chen", "target": "Google", "relationship": "previously_worked_at"},
            {"source": "Sarah Johnson", "target": "Microsoft", "relationship": "previously_worked_at"},
            
            # Advisory roles
            {"source": "Dr. Mike Rodriguez", "target": "CloudSync Inc", "relationship": "advises"},
        ]
        
        # LLM configurations - Testing instruction following: GPT-4o-mini vs Gemma3:12b
        self.llm_configs = [
            LLMConfig(
                name="OpenAI GPT-4o-mini",
                type="openai",
                endpoint="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY")
            ),
            LLMConfig(
                name=f"Gemma3:12b ({HOSTNAME})",
                type="ollama",
                endpoint="http://{HOST}:11434",
                model="gemma3:12b",
                timeout=60
            ),
        ]
    
    def _create_test_document(self) -> str:
        """Create a test document with known relationships (~1024 characters)"""
        return """---
title: "Tech Startup Network"
date: 2024-01-15
tags: [test, relationships, benchmark]
---

# Tech Startup Network

## Key People

**Alex Chen** is the CEO of TechFlow, a software company in San Francisco. He graduated from Stanford University and previously worked at Google. Alex is married to Sarah Johnson, who works as a product manager at CloudSync Inc.

**Sarah Johnson** is the VP of Product at CloudSync Inc, a cloud services company. She graduated from UC Berkeley and previously worked at Microsoft. Sarah is married to Alex Chen and frequently collaborates with Dr. Mike Rodriguez.

**Dr. Mike Rodriguez** is a professor at Stanford University and co-founded TechFlow with Alex Chen. He serves as Chief Scientific Officer and advises several startups including CloudSync Inc.

## Companies

**TechFlow** is an AI software company founded by Alex Chen and Dr. Mike Rodriguez in 2020. The company is based in San Francisco and has partnerships with Google Cloud and Microsoft Azure.

**CloudSync Inc** is a cloud infrastructure company founded in 2019. The company provides cloud migration services and is based in Seattle. CloudSync has partnerships with Amazon Web Services and Microsoft Azure.

## Key Relationships

- Alex Chen is CEO of TechFlow
- Sarah Johnson is VP of Product at CloudSync Inc  
- Dr. Mike Rodriguez is CSO of TechFlow
- Dr. Mike Rodriguez is professor at Stanford University
- Alex Chen is married to Sarah Johnson
- Alex Chen and Dr. Mike Rodriguez co-founded TechFlow
- Sarah Johnson collaborates with Dr. Mike Rodriguez
- TechFlow partners with Google Cloud
- TechFlow partners with Microsoft Azure
- CloudSync Inc partners with Amazon Web Services
- CloudSync Inc partners with Microsoft Azure
- Alex Chen graduated from Stanford University
- Sarah Johnson graduated from UC Berkeley
- Alex Chen previously worked at Google
- Sarah Johnson previously worked at Microsoft
- Dr. Mike Rodriguez advises CloudSync Inc
"""
    
    async def test_llm(self, config: LLMConfig) -> BenchmarkResult:
        """Test a single LLM configuration"""
        console.print(f"[cyan]Testing {config.name}...[/cyan]")
        
        start_time = time.time()
        
        try:
            if config.type == "openai":
                result = await self._test_openai(config)
            elif config.type == "ollama":
                result = await self._test_ollama(config)
            else:
                raise ValueError(f"Unknown LLM type: {config.type}")
            
            response_time = time.time() - start_time
            
            # Calculate accuracy
            accuracy = self._calculate_accuracy(result.get("relationships", []))
            
            return BenchmarkResult(
                llm_name=config.name,
                response_time=response_time,
                success=True,
                extracted_relationships=result.get("relationships", []),
                accuracy_score=accuracy,
                token_count=result.get("token_count")
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            console.print(f"[red]Error testing {config.name}: {e}[/red]")
            import traceback
            console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
            
            return BenchmarkResult(
                llm_name=config.name,
                response_time=response_time,
                success=False,
                error=str(e)
            )
    
    async def _test_openai(self, config: LLMConfig) -> Dict[str, Any]:
        """Test OpenAI API"""
        if not config.api_key:
            raise ValueError("OpenAI API key not provided")
        
        client = openai.AsyncOpenAI(api_key=config.api_key)
        
        # Prepare the prompts
        user_prompt = self.user_prompt_template.format(text=self.test_document)
        
        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Parse the response
        content = response.choices[0].message.content
        
        # Try to extract JSON from the response
        try:
            # Look for JSON in markdown code blocks first
            if '```json' in content:
                start_idx = content.find('```json') + 7
                end_idx = content.find('```', start_idx)
                if end_idx != -1:
                    json_str = content[start_idx:end_idx].strip()
                else:
                    # Fallback to regular JSON search
                    start_idx = content.find('[')
                    end_idx = content.rfind(']') + 1
                    json_str = content[start_idx:end_idx] if start_idx != -1 and end_idx > start_idx else content
            else:
                # Look for JSON array or object
                start_idx = content.find('[')
                end_idx = content.rfind(']') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                else:
                    start_idx = content.find('{')
                    end_idx = content.rfind('}') + 1
                    json_str = content[start_idx:end_idx] if start_idx != -1 and end_idx > start_idx else content
            
            if json_str:
                result = json.loads(json_str)
                # Handle different response formats
                if isinstance(result, list):
                    relationships = result
                elif isinstance(result, dict):
                    # Check if it has a relationships key
                    if "relationships" in result:
                        relationships = result.get("relationships", [])
                    else:
                        # Handle structured format with categories
                        print(f"Flattening structured data with keys: {list(result.keys())}")
                        relationships = self._flatten_structured_relationships(result)
                        print(f"Flattened to {len(relationships)} relationships")
                else:
                    relationships = []
                
                return {
                    "relationships": relationships,
                    "token_count": response.usage.total_tokens if response.usage else None
                }
            else:
                return {"relationships": [], "token_count": response.usage.total_tokens if response.usage else None}
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Content: {content[:200]}...")
            return {"relationships": [], "token_count": response.usage.total_tokens if response.usage else None}
    
    async def _test_ollama(self, config: LLMConfig) -> Dict[str, Any]:
        """Test Ollama API"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.timeout)) as session:
            # Prepare the combined prompt (Ollama doesn't use system prompts)
            user_prompt = self.user_prompt_template.format(text=self.test_document)
            combined_prompt = f"{self.system_prompt}\n\n{user_prompt}"
            
            payload = {
                "model": config.model,
                "prompt": combined_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2000
                }
            }
            
            async with session.post(
                f"{config.endpoint}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response.status}")
                
                result = await response.json()
                content = result.get("response", "")
                
                # Try to extract JSON from the response
                try:
                    # Look for JSON in markdown code blocks first
                    if '```json' in content:
                        start_idx = content.find('```json') + 7
                        end_idx = content.find('```', start_idx)
                        if end_idx != -1:
                            json_str = content[start_idx:end_idx].strip()
                        else:
                            # Fallback to regular JSON search
                            start_idx = content.find('[')
                            end_idx = content.rfind(']') + 1
                            json_str = content[start_idx:end_idx] if start_idx != -1 and end_idx > start_idx else content
                    else:
                        # Look for JSON array or object
                        start_idx = content.find('[')
                        end_idx = content.rfind(']') + 1
                        if start_idx != -1 and end_idx > start_idx:
                            json_str = content[start_idx:end_idx]
                        else:
                            start_idx = content.find('{')
                            end_idx = content.rfind('}') + 1
                            json_str = content[start_idx:end_idx] if start_idx != -1 and end_idx > start_idx else content
                    
                    if json_str:
                        parsed = json.loads(json_str)
                        # Handle different response formats
                        if isinstance(parsed, list):
                            relationships = parsed
                        elif isinstance(parsed, dict):
                            # Check if it has a relationships key
                            if "relationships" in parsed:
                                relationships = parsed.get("relationships", [])
                            else:
                                # Handle structured format with categories
                                relationships = self._flatten_structured_relationships(parsed)
                        else:
                            relationships = []
                        
                        return {
                            "relationships": relationships,
                            "token_count": result.get("eval_count")
                        }
                    else:
                        return {"relationships": [], "token_count": result.get("eval_count")}
                except json.JSONDecodeError as e:
                    print(f"Ollama JSON parsing error: {e}")
                    print(f"Content: {content[:200]}...")
                    return {"relationships": [], "token_count": result.get("eval_count")}
    
    def _flatten_structured_relationships(self, structured_data: Dict) -> List[Dict]:
        """Flatten structured relationship data into a list of relationships"""
        relationships = []
        
        # Professional relationships
        for item in structured_data.get("professional", []):
            if "person" in item and "company" in item:
                relationships.append({
                    "source": item["person"],
                    "target": item["company"],
                    "relationship": item.get("role", "").lower().replace(" ", "_")
                })
            elif "person" in item and "institution" in item:
                relationships.append({
                    "source": item["person"],
                    "target": item["institution"],
                    "relationship": item.get("role", "").lower().replace(" ", "_")
                })
        
        # Personal relationships
        for item in structured_data.get("personal", []):
            if "person1" in item and "person2" in item:
                relationships.append({
                    "source": item["person1"],
                    "target": item["person2"],
                    "relationship": item.get("relation", "").lower().replace(" ", "_")
                })
        
        # Business partnerships
        for item in structured_data.get("business_partnerships", []):
            if "company1" in item and "partner" in item:
                relationships.append({
                    "source": item["company1"],
                    "target": item["partner"],
                    "relationship": "partners_with"
                })
        
        # Educational background
        for item in structured_data.get("educational_background", []):
            if "person" in item and "institution" in item:
                relationships.append({
                    "source": item["person"],
                    "target": item["institution"],
                    "relationship": "graduated_from"
                })
        
        # Previous employment
        for item in structured_data.get("previous_employment", []):
            if "person" in item and "company" in item:
                relationships.append({
                    "source": item["person"],
                    "target": item["company"],
                    "relationship": "previously_worked_at"
                })
        
        # Advisory roles
        for item in structured_data.get("advisory_roles", []):
            if "person" in item and "company" in item:
                relationships.append({
                    "source": item["person"],
                    "target": item["company"],
                    "relationship": "advises"
                })
        
        return relationships

    def _calculate_accuracy(self, extracted_relationships: List[Dict]) -> float:
        """Calculate accuracy score based on expected relationships (source/target only)"""
        if not extracted_relationships:
            return 0.0
        
        correct = 0
        total = len(self.expected_relationships)
        
        for expected in self.expected_relationships:
            for extracted in extracted_relationships:
                # Skip if extracted is not a dictionary
                if not isinstance(extracted, dict):
                    continue
                    
                # Handle different field name formats from LLM
                source = (extracted.get("source") or extracted.get("source_label") or extracted.get("person1") or 
                         extracted.get("person") or extracted.get("company1") or extracted.get("company") or 
                         extracted.get("subject") or extracted.get("entity1"))
                target = (extracted.get("target") or extracted.get("target_label") or extracted.get("person2") or 
                         extracted.get("company2") or extracted.get("institution") or extracted.get("location") or 
                         extracted.get("object") or extracted.get("entity2"))
                
                # Normalize entity names for comparison
                if source:
                    source = str(source).strip().lower()
                if target:
                    target = str(target).strip().lower()
                
                # Check for matches with normalized names (ignore relationship type)
                expected_source = str(expected["source"]).strip().lower()
                expected_target = str(expected["target"]).strip().lower()
                
                # Match if source and target match (in either direction)
                if ((source == expected_source and target == expected_target) or
                    (source == expected_target and target == expected_source)):
                    correct += 1
                    break
        
        return correct / total if total > 0 else 0.0
    
    def _relationship_matches(self, extracted: str, expected: str) -> bool:
        """Check if relationship names match with common variations"""
        extracted = extracted.lower().replace("_", "").replace(" ", "")
        expected = expected.lower().replace("_", "").replace(" ", "")
        
        # Common relationship variations
        variations = {
            "worksat": ["works_at", "employed_at", "works_for"],
            "marriedto": ["married_to", "is_married_to", "has_been_married_to"],
            "partnerswith": ["partners_with", "partnership_with"],
            "graduatedfrom": ["graduated_from", "studied_at", "educated_at"],
            "locatedin": ["located_in", "is_located_in", "based_in"],
            "ceoof": ["ceo_of", "is_ceo_of", "chief_executive_officer_of"],
            "ctoof": ["cto_of", "is_cto_of", "chief_technology_officer_of"],
            "csoof": ["cso_of", "is_cso_of", "chief_scientific_officer_of", "is_cs_of"],
            "professorat": ["professor_at", "is_professor_at", "teaches_at"],
            "researcherat": ["researcher_at", "is_researcher_at", "researches_at"],
            "cofoundedwith": ["co_founded_with", "cofounded_with", "founded_with", "co_founded"],
            "friendof": ["friend_of", "is_friend_of", "friends_with"],
            "collaborateswith": ["collaborates_with", "collaborates", "works_with"],
            "previouslyworkedat": ["previously_worked_at", "worked_at", "was_employed_at", "previous_employment"],
            "advises": ["advises", "is_advisor_to", "advisor_of", "advised"],
            "vpproductat": ["vp_product_at", "is_vp_of_product_at", "vice_president_of_product_at"]
        }
        
        # Handle "is" prefix removal for better matching
        if extracted.startswith("is_"):
            extracted = extracted[3:]  # Remove "is_" prefix
        if expected.startswith("is_"):
            expected = expected[3:]  # Remove "is_" prefix
        
        for key, variants in variations.items():
            if key in extracted:
                return any(variant.replace("_", "") in expected for variant in variants)
            if key in expected:
                return any(variant.replace("_", "") in extracted for variant in variants)
        
        return False
    
    async def run_benchmark(self):
        """Run the complete benchmark"""
        console.print(Panel.fit(
            "[bold blue]LLM Benchmarking Tool[/bold blue]\n"
            "Comparing relationship extraction speed and accuracy",
            title="🚀 Benchmark"
        ))
        
        console.print(f"[cyan]Testing {len(self.llm_configs)} LLM configurations...[/cyan]")
        console.print(f"[cyan]Test document: {len(self.test_document)} characters[/cyan]")
        console.print(f"[cyan]Expected relationships: {len(self.expected_relationships)}[/cyan]\n")
        
        # Test each LLM
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running benchmarks...", total=len(self.llm_configs))
            
            for config in self.llm_configs:
                progress.update(task, description=f"Testing {config.name}")
                result = await self.test_llm(config)
                self.results.append(result)
                progress.advance(task)
        
        # Display results
        self._display_results()
    
    def _display_results(self):
        """Display benchmark results in a formatted table"""
        console.print("\n" + "="*80)
        console.print("[bold green]BENCHMARK RESULTS[/bold green]")
        console.print("="*80)
        
        # Create results table
        table = Table(title="LLM Performance Comparison")
        table.add_column("LLM", style="cyan", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("Time (s)", justify="right", style="yellow")
        table.add_column("Accuracy", justify="right", style="magenta")
        table.add_column("Relationships", justify="right", style="blue")
        table.add_column("Tokens", justify="right", style="dim")
        table.add_column("Error", style="red")
        
        for result in self.results:
            status = "✅ Success" if result.success else "❌ Failed"
            time_str = f"{result.response_time:.2f}"
            accuracy_str = f"{result.accuracy_score:.1%}" if result.success else "N/A"
            relationships_count = len(result.extracted_relationships) if result.extracted_relationships else 0
            tokens_str = str(result.token_count) if result.token_count else "N/A"
            error_str = result.error[:30] + "..." if result.error and len(result.error) > 30 else (result.error or "")
            
            table.add_row(
                result.llm_name,
                status,
                time_str,
                accuracy_str,
                str(relationships_count),
                tokens_str,
                error_str
            )
        
        console.print(table)
        
        # Summary statistics
        successful_results = [r for r in self.results if r.success]
        if successful_results:
            console.print("\n[bold]Summary Statistics:[/bold]")
            console.print(f"• Fastest: {min(successful_results, key=lambda x: x.response_time).llm_name} ({min(r.response_time for r in successful_results):.2f}s)")
            console.print(f"• Most Accurate: {max(successful_results, key=lambda x: x.accuracy_score).llm_name} ({max(r.accuracy_score for r in successful_results):.1%})")
            console.print(f"• Most Relationships: {max(successful_results, key=lambda x: len(x.extracted_relationships or [])).llm_name} ({max(len(r.extracted_relationships or []) for r in successful_results)})")
        
        # Save detailed results
        self._save_results()
    
    def _save_results(self):
        """Save detailed results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"llm_benchmark_results_{timestamp}.json"
        
        results_data = {
            "timestamp": timestamp,
            "test_document": self.test_document,
            "expected_relationships": self.expected_relationships,
            "results": [
                {
                    "llm_name": r.llm_name,
                    "response_time": r.response_time,
                    "success": r.success,
                    "error": r.error,
                    "extracted_relationships": r.extracted_relationships,
                    "accuracy_score": r.accuracy_score,
                    "token_count": r.token_count
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        console.print(f"\n[green]Detailed results saved to: {filename}[/green]")

async def main():
    """Main function"""
    benchmark = LLMBenchmark()
    await benchmark.run_benchmark()

if __name__ == "__main__":
    asyncio.run(main())
