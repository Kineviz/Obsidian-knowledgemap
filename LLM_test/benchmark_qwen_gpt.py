#!/usr/bin/env python3
"""
Benchmark Script: Qwen3 vs GPT-4o-mini for Knowledge Graph Extraction
Compares accuracy and speed of structured output for relationship extraction.
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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))
from prompt_loader import PromptLoader
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()

@dataclass
class LLMConfig:
    name: str
    type: str  # 'openai' or 'ollama'
    endpoint: str
    model: str
    api_key: Optional[str] = None
    timeout: int = 120

@dataclass
class BenchmarkResult:
    llm_name: str
    response_time: float
    success: bool
    error: Optional[str] = None
    extracted_relationships: List[Dict] = None
    accuracy_score: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    token_count: Optional[int] = None
    raw_response: str = ""

class QwenGPTBenchmark:
    def __init__(self):
        self.prompt_loader = PromptLoader()
        self.results: List[BenchmarkResult] = []
        
        # Load the relationship extraction prompt for OpenAI
        self.system_prompt = self.prompt_loader.get_system_prompt("relationship_extraction").content
        self.user_prompt_template = self.prompt_loader.get_user_prompt("relationship_extraction", text="{text}").content
        
        # Optimized prompt for Qwen3 models - thinking-free pattern
        self.qwen_prompt = """You MUST NOT output chain-of-thought reasoning.
Only output the final JSON. No explanation, no notes, no extra text.
If you must think, do so silently.

You are a knowledge graph extraction engine.
Convert the text into a structured knowledge graph in JSON.

RULES:
- Output ONLY valid JSON.
- Follow the schema exactly.
- Do not invent facts.
- Use lowercase alphanumeric IDs with underscores.

JSON SCHEMA:
{"nodes": [{"id": "string", "type": "Person|Company", "name": "string"}], "edges": [{"source": "id", "target": "id", "type": "RELATION"}]}

EXAMPLE:
Input: "John works at Google. Sarah is married to John."
Output: {"nodes": [{"id": "john", "type": "Person", "name": "John"}, {"id": "google", "type": "Company", "name": "Google"}, {"id": "sarah", "type": "Person", "name": "Sarah"}], "edges": [{"source": "john", "target": "google", "type": "WORKS_AT"}, {"source": "sarah", "target": "john", "type": "MARRIED_TO"}]}

Now extract from this text:
"""
        
        # Test document
        self.test_document = self._create_test_document()
        
        # Expected relationships for accuracy testing
        self.expected_relationships = [
            {"source": "Alex Chen", "source_category": "Person", "target": "TechFlow", "target_category": "Company", "relationship": "ceo_of"},
            {"source": "Sarah Johnson", "source_category": "Person", "target": "CloudSync Inc", "target_category": "Company", "relationship": "vp_product_at"},
            {"source": "Dr. Mike Rodriguez", "source_category": "Person", "target": "TechFlow", "target_category": "Company", "relationship": "cso_of"},
            {"source": "Dr. Mike Rodriguez", "source_category": "Person", "target": "Stanford University", "target_category": "Company", "relationship": "professor_at"},
            {"source": "Alex Chen", "source_category": "Person", "target": "Sarah Johnson", "target_category": "Person", "relationship": "married_to"},
            {"source": "Alex Chen", "source_category": "Person", "target": "Dr. Mike Rodriguez", "target_category": "Person", "relationship": "co_founded_with"},
            {"source": "TechFlow", "source_category": "Company", "target": "Google Cloud", "target_category": "Company", "relationship": "partners_with"},
            {"source": "TechFlow", "source_category": "Company", "target": "Microsoft Azure", "target_category": "Company", "relationship": "partners_with"},
            {"source": "CloudSync Inc", "source_category": "Company", "target": "Amazon Web Services", "target_category": "Company", "relationship": "partners_with"},
            {"source": "Alex Chen", "source_category": "Person", "target": "Stanford University", "target_category": "Company", "relationship": "graduated_from"},
            {"source": "Sarah Johnson", "source_category": "Person", "target": "UC Berkeley", "target_category": "Company", "relationship": "graduated_from"},
            {"source": "Alex Chen", "source_category": "Person", "target": "Google", "target_category": "Company", "relationship": "previously_worked_at"},
            {"source": "Sarah Johnson", "source_category": "Person", "target": "Microsoft", "target_category": "Company", "relationship": "previously_worked_at"},
            {"source": "Dr. Mike Rodriguez", "source_category": "Person", "target": "CloudSync Inc", "target_category": "Company", "relationship": "advises"},
        ]
        
        # LLM configurations
        self.llm_configs = [
            LLMConfig(
                name="OpenAI GPT-4o-mini",
                type="openai",
                endpoint="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY"),
                timeout=60
            ),
            LLMConfig(
                name="Qwen3:4b (bsrs-mac-studio)",
                type="ollama",
                endpoint="http://bsrs-mac-studio:11434",
                model="qwen3:4b",
                timeout=120
            ),
            LLMConfig(
                name="Qwen3:8b (bsrs-mac-studio)",
                type="ollama",
                endpoint="http://bsrs-mac-studio:11434",
                model="qwen3:8b",
                timeout=180
            ),
            LLMConfig(
                name="Qwen3:14b (bsrs-mac-studio)",
                type="ollama",
                endpoint="http://bsrs-mac-studio:11434",
                model="qwen3:14b",
                timeout=300
            ),
        ]
    
    def _create_test_document(self) -> str:
        """Create a test document with known relationships"""
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
- TechFlow partners with Google Cloud
- TechFlow partners with Microsoft Azure
- CloudSync Inc partners with Amazon Web Services
- Alex Chen graduated from Stanford University
- Sarah Johnson graduated from UC Berkeley
- Alex Chen previously worked at Google
- Sarah Johnson previously worked at Microsoft
- Dr. Mike Rodriguez advises CloudSync Inc
"""
    
    async def test_llm(self, config: LLMConfig) -> BenchmarkResult:
        """Test a single LLM configuration"""
        console.print(f"\n[cyan]Testing {config.name}...[/cyan]")
        console.print(f"  Model: {config.model}")
        console.print(f"  Endpoint: {config.endpoint}")
        
        start_time = time.time()
        
        try:
            if config.type == "openai":
                result = await self._test_openai(config)
            elif config.type == "ollama":
                result = await self._test_ollama(config)
            else:
                raise ValueError(f"Unknown LLM type: {config.type}")
            
            response_time = time.time() - start_time
            
            # Calculate accuracy metrics
            precision, recall, accuracy = self._calculate_metrics(result.get("relationships", []))
            
            console.print(f"  [green]✓ Completed in {response_time:.2f}s[/green]")
            console.print(f"  [blue]Extracted {len(result.get('relationships', []))} relationships[/blue]")
            
            return BenchmarkResult(
                llm_name=config.name,
                response_time=response_time,
                success=True,
                extracted_relationships=result.get("relationships", []),
                accuracy_score=accuracy,
                precision=precision,
                recall=recall,
                token_count=result.get("token_count"),
                raw_response=result.get("raw_response", "")
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            console.print(f"  [red]✗ Error: {e}[/red]")
            import traceback
            console.print(f"  [red]{traceback.format_exc()}[/red]")
            
            return BenchmarkResult(
                llm_name=config.name,
                response_time=response_time,
                success=False,
                error=str(e)
            )
    
    async def _test_openai(self, config: LLMConfig) -> Dict[str, Any]:
        """Test OpenAI API with structured output"""
        if not config.api_key:
            raise ValueError("OpenAI API key not provided")
        
        client = openai.AsyncOpenAI(api_key=config.api_key)
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
        
        content = response.choices[0].message.content
        relationships = self._parse_json_response(content)
        
        return {
            "relationships": relationships,
            "token_count": response.usage.total_tokens if response.usage else None,
            "raw_response": content
        }
    
    async def _test_ollama(self, config: LLMConfig) -> Dict[str, Any]:
        """Test Ollama API with structured output using chat API"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.timeout)) as session:
            # Use optimized Qwen prompt with nodes/edges schema
            full_prompt = self.qwen_prompt + self.test_document
            
            # Use chat API with system message to suppress thinking
            payload = {
                "model": config.model,
                "messages": [
                    {"role": "system", "content": "Do not output chain-of-thought. Only return the final JSON."},
                    {"role": "user", "content": full_prompt}
                ],
                "stream": False,
                "format": "json",  # Request JSON format
                "options": {
                    "temperature": 0,  # Deterministic for structured output
                    "top_p": 1,
                    "num_predict": 4000,
                    "num_ctx": 8192
                }
            }
            
            async with session.post(f"{config.endpoint}/api/chat", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")
                
                result = await response.json()
                content = result.get("message", {}).get("content", "")
                
                # Parse the response - handle thinking models
                relationships = self._parse_json_response(content)
                
                # Debug: show first/last part of response if no relationships found
                if not relationships and content:
                    console.print(f"  [yellow]Response preview: {content[:300]}...[/yellow]")
                    console.print(f"  [yellow]Response end: ...{content[-500:]}[/yellow]")
                
                return {
                    "relationships": relationships,
                    "token_count": result.get("eval_count"),
                    "raw_response": content
                }
    
    def _parse_json_response(self, content: str) -> List[Dict]:
        """Parse JSON from LLM response"""
        try:
            # Handle Qwen3 thinking models - extract content after </think> tag
            if '</think>' in content:
                content = content.split('</think>')[-1].strip()
            
            json_str = None
            
            # Look for JSON in markdown code blocks
            if '```json' in content:
                start_idx = content.find('```json') + 7
                end_idx = content.find('```', start_idx)
                if end_idx != -1:
                    json_str = content[start_idx:end_idx].strip()
            
            # Also check for plain ``` blocks
            elif '```' in content:
                start_idx = content.find('```') + 3
                # Skip language identifier if present
                newline_idx = content.find('\n', start_idx)
                if newline_idx != -1:
                    start_idx = newline_idx + 1
                end_idx = content.find('```', start_idx)
                if end_idx != -1:
                    json_str = content[start_idx:end_idx].strip()
            
            # Look for JSON object (nodes/edges format)
            if not json_str:
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
            
            # Look for JSON array
            if not json_str:
                start_idx = content.find('[')
                end_idx = content.rfind(']') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
            
            if json_str:
                return self._parse_and_normalize(json_str)
            
            return []
            
        except json.JSONDecodeError as e:
            console.print(f"  [yellow]JSON parse error: {e}[/yellow]")
            return []
        except Exception as e:
            console.print(f"  [yellow]Parse error: {e}[/yellow]")
            return []
    
    def _parse_and_normalize(self, json_str: str) -> List[Dict]:
        """Parse JSON string and normalize to relationship list"""
        parsed = json.loads(json_str)
        
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            # Check for nodes/edges format (Qwen3 style)
            if "nodes" in parsed and "edges" in parsed:
                return self._convert_nodes_edges_to_relationships(parsed)
            # Check for relationships key
            if "relationships" in parsed:
                return parsed["relationships"]
            # Flatten structured format
            return self._flatten_structured(parsed)
        return []
    
    def _convert_nodes_edges_to_relationships(self, data: Dict) -> List[Dict]:
        """Convert nodes/edges format to relationship list"""
        relationships = []
        
        # Build node lookup by id
        node_lookup = {}
        for node in data.get("nodes", []):
            node_id = node.get("id", "")
            node_lookup[node_id] = {
                "name": node.get("name", node_id),
                "type": node.get("type", "Unknown")
            }
        
        # Convert edges to relationships
        for edge in data.get("edges", []):
            source_id = edge.get("source", "")
            target_id = edge.get("target", "")
            rel_type = edge.get("type", "RELATED_TO")
            
            source_node = node_lookup.get(source_id, {"name": source_id, "type": "Unknown"})
            target_node = node_lookup.get(target_id, {"name": target_id, "type": "Unknown"})
            
            relationships.append({
                "source": source_node["name"],
                "target": target_node["name"],
                "relationship": rel_type,
                "source_category": source_node["type"],
                "target_category": target_node["type"]
            })
        
        return relationships
    
    def _flatten_structured(self, data: Dict) -> List[Dict]:
        """Flatten structured relationship data"""
        relationships = []
        
        # Handle various structured formats
        for category in ["professional", "personal", "business_partnerships", 
                        "educational_background", "previous_employment", "advisory_roles"]:
            if category in data:
                for item in data[category]:
                    rel = self._extract_relationship(item)
                    if rel:
                        relationships.append(rel)
        
        return relationships
    
    def _extract_relationship(self, item: Dict) -> Optional[Dict]:
        """Extract standardized relationship from item"""
        # Try different field name combinations
        source = item.get("source") or item.get("source_label") or item.get("person") or item.get("company1")
        target = item.get("target") or item.get("target_label") or item.get("company") or item.get("institution")
        relationship = item.get("relationship") or item.get("relation") or item.get("role")
        
        if source and target:
            return {
                "source": source,
                "target": target,
                "relationship": relationship or "related_to",
                "source_category": item.get("source_category", "Unknown"),
                "target_category": item.get("target_category", "Unknown")
            }
        return None
    
    def _calculate_metrics(self, extracted: List[Dict]) -> tuple:
        """Calculate precision, recall, and F1 score"""
        if not extracted:
            return 0.0, 0.0, 0.0
        
        # Count true positives (matched relationships)
        true_positives = 0
        
        for expected in self.expected_relationships:
            for ext in extracted:
                if not isinstance(ext, dict):
                    continue
                
                # Normalize names for comparison
                ext_source = str(ext.get("source", "") or ext.get("source_label", "")).lower().strip()
                ext_target = str(ext.get("target", "") or ext.get("target_label", "")).lower().strip()
                exp_source = expected["source"].lower().strip()
                exp_target = expected["target"].lower().strip()
                
                # Match if source/target match in either direction
                if ((ext_source == exp_source and ext_target == exp_target) or
                    (ext_source == exp_target and ext_target == exp_source)):
                    true_positives += 1
                    break
        
        # Precision = TP / (TP + FP) = TP / extracted count
        precision = true_positives / len(extracted) if extracted else 0
        
        # Recall = TP / (TP + FN) = TP / expected count
        recall = true_positives / len(self.expected_relationships) if self.expected_relationships else 0
        
        # F1 Score (accuracy proxy)
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0
        
        return precision, recall, f1
    
    async def run_benchmark(self):
        """Run the complete benchmark"""
        console.print(Panel.fit(
            "[bold blue]Qwen3 vs GPT-4o-mini Benchmark[/bold blue]\n"
            "Knowledge Graph Relationship Extraction with Structured Output",
            title="🚀 LLM Benchmark"
        ))
        
        console.print(f"\n[cyan]Test Configuration:[/cyan]")
        console.print(f"  • Models to test: {len(self.llm_configs)}")
        console.print(f"  • Test document: {len(self.test_document)} characters")
        console.print(f"  • Expected relationships: {len(self.expected_relationships)}")
        console.print(f"  • Ollama server: bsrs-mac-studio:11434")
        
        # Test each LLM
        for config in self.llm_configs:
            result = await self.test_llm(config)
            self.results.append(result)
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Display results
        self._display_results()
        self._save_results()
    
    def _display_results(self):
        """Display benchmark results"""
        console.print("\n" + "="*100)
        console.print("[bold green]BENCHMARK RESULTS[/bold green]")
        console.print("="*100)
        
        # Create results table
        table = Table(title="Model Performance Comparison", show_lines=True)
        table.add_column("Model", style="cyan", width=25)
        table.add_column("Status", style="green", width=10)
        table.add_column("Time (s)", justify="right", style="yellow", width=10)
        table.add_column("Relations", justify="right", style="blue", width=10)
        table.add_column("Precision", justify="right", style="magenta", width=10)
        table.add_column("Recall", justify="right", style="magenta", width=10)
        table.add_column("F1 Score", justify="right", style="bold magenta", width=10)
        table.add_column("Tokens", justify="right", style="dim", width=10)
        
        for result in self.results:
            status = "✅ OK" if result.success else "❌ Fail"
            time_str = f"{result.response_time:.2f}"
            rel_count = len(result.extracted_relationships) if result.extracted_relationships else 0
            precision = f"{result.precision:.1%}" if result.success else "N/A"
            recall = f"{result.recall:.1%}" if result.success else "N/A"
            f1 = f"{result.accuracy_score:.1%}" if result.success else "N/A"
            tokens = str(result.token_count) if result.token_count else "N/A"
            
            table.add_row(
                result.llm_name,
                status,
                time_str,
                str(rel_count),
                precision,
                recall,
                f1,
                tokens
            )
        
        console.print(table)
        
        # Summary
        successful = [r for r in self.results if r.success]
        if successful:
            console.print("\n[bold]📊 Summary:[/bold]")
            fastest = min(successful, key=lambda x: x.response_time)
            most_accurate = max(successful, key=lambda x: x.accuracy_score)
            most_complete = max(successful, key=lambda x: len(x.extracted_relationships or []))
            
            console.print(f"  🏃 Fastest: {fastest.llm_name} ({fastest.response_time:.2f}s)")
            console.print(f"  🎯 Best F1 Score: {most_accurate.llm_name} ({most_accurate.accuracy_score:.1%})")
            console.print(f"  📝 Most Relations: {most_complete.llm_name} ({len(most_complete.extracted_relationships or [])})")
            
            # Speed vs Accuracy trade-off
            console.print("\n[bold]⚖️ Speed vs Accuracy Trade-off:[/bold]")
            for r in sorted(successful, key=lambda x: x.response_time):
                speed_rating = "🚀" if r.response_time < 5 else ("⚡" if r.response_time < 15 else "🐢")
                acc_rating = "🎯" if r.accuracy_score > 0.7 else ("✓" if r.accuracy_score > 0.5 else "⚠️")
                console.print(f"  {speed_rating} {acc_rating} {r.llm_name}: {r.response_time:.1f}s, F1={r.accuracy_score:.1%}")
    
    def _save_results(self):
        """Save detailed results to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qwen_gpt_benchmark_{timestamp}.json"
        
        results_data = {
            "timestamp": timestamp,
            "test_document_length": len(self.test_document),
            "expected_relationships_count": len(self.expected_relationships),
            "results": [
                {
                    "model": r.llm_name,
                    "response_time_seconds": r.response_time,
                    "success": r.success,
                    "error": r.error,
                    "relationships_extracted": len(r.extracted_relationships) if r.extracted_relationships else 0,
                    "precision": r.precision,
                    "recall": r.recall,
                    "f1_score": r.accuracy_score,
                    "token_count": r.token_count,
                    "extracted_relationships": r.extracted_relationships
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        console.print(f"\n[green]📁 Detailed results saved to: {filename}[/green]")

async def main():
    """Main function"""
    benchmark = QwenGPTBenchmark()
    await benchmark.run_benchmark()

if __name__ == "__main__":
    asyncio.run(main())

