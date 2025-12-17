#!/usr/bin/env python3
"""Test Gemini with knowledge map extraction and classification tasks"""

import asyncio
import sys
import json
import re
from pathlib import Path

# Add cli directory to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from llm_client import get_llm_client, close_llm_client
from prompt_loader import get_prompt_loader
from config_loader import get_config_loader
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Test content for knowledge map extraction
KM_TEST_CONTENT = """
Alex Chen is the CEO of TechFlow, a software company in San Francisco. 
He graduated from Stanford University and previously worked at Google. 
Alex is married to Sarah Johnson, who works as a product manager at CloudSync Inc.

TechFlow is an AI software company founded by Alex Chen and Dr. Mike Rodriguez in 2020. 
The company is based in San Francisco and has partnerships with Google Cloud and Microsoft Azure.
"""

# Test content for classification
CLASSIFICATION_TEST_CONTENT = """
John Smith is a venture capitalist at Sequoia Capital. He focuses on Series A and Series B investments 
in B2B SaaS companies, particularly in AI/ML and Enterprise Software sectors. 
He typically writes checks between $3M-$10M and invests primarily in the SF-Bay Area and NYC.
John has 15 years of experience in venture capital and is known for his technical background.
"""

async def test_knowledge_map_extraction():
    """Test knowledge map extraction with Gemini"""
    console.print("\n[bold cyan]=" * 60)
    console.print("[bold cyan]Test 1: Knowledge Map Extraction[/bold cyan]")
    console.print("[bold cyan]=" * 60 + "\n")
    
    try:
        # Get prompt loader
        prompt_loader = get_prompt_loader()
        messages = prompt_loader.get_prompt_pair("relationship_extraction", text=KM_TEST_CONTENT)
        
        console.print("[dim]Prompt loaded from prompts.yaml[/dim]\n")
        
        # Get LLM client
        llm_client = await get_llm_client()
        
        console.print("[cyan]Calling Gemini API...[/cyan]")
        response = await llm_client.generate(messages, temperature=0.1, max_tokens=2000)
        
        if not response.success:
            console.print(f"[red]❌ API call failed: {response.error}[/red]")
            return False
        
        console.print(f"[green]✅ API call successful![/green]")
        console.print(f"[dim]Response time: {response.response_time:.2f}s[/dim]")
        console.print(f"[dim]Provider: {response.provider}, Model: {response.model}[/dim]\n")
        
        # Parse JSON response
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
        
        if json_start == -1 or json_end <= json_start:
            console.print(f"[red]❌ No JSON object found in response[/red]")
            console.print(f"[yellow]Response: {content[:500]}...[/yellow]")
            return False
        
        json_content = content[json_start:json_end]
        
        # Fix common JSON issues (trailing commas)
        json_content = re.sub(r',(\s*[}\]])', r'\1', json_content)
        
        try:
            result = json.loads(json_content)
            relationships = result.get('relationships', [])
            
            console.print(f"[green]✅ Successfully parsed JSON![/green]")
            console.print(f"[green]Found {len(relationships)} relationships[/green]\n")
            
            # Validate format
            valid_format = True
            for rel in relationships:
                required_fields = ['source_category', 'source_label', 'relationship', 'target_category', 'target_label']
                missing = [f for f in required_fields if f not in rel]
                if missing:
                    console.print(f"[red]❌ Missing fields in relationship: {missing}[/red]")
                    valid_format = False
                
                # Check categories are valid
                if rel.get('source_category') not in ['Person', 'Company']:
                    console.print(f"[red]❌ Invalid source_category: {rel.get('source_category')}[/red]")
                    valid_format = False
                if rel.get('target_category') not in ['Person', 'Company']:
                    console.print(f"[red]❌ Invalid target_category: {rel.get('target_category')}[/red]")
                    valid_format = False
            
            if not valid_format:
                return False
            
            # Display results
            if relationships:
                table = Table(title="Extracted Relationships", show_header=True, header_style="bold magenta")
                table.add_column("Source", style="cyan")
                table.add_column("Category", style="dim")
                table.add_column("Relationship", style="yellow")
                table.add_column("Target", style="magenta")
                table.add_column("Category", style="dim")
                
                for rel in relationships[:10]:  # Show first 10
                    table.add_row(
                        rel.get('source_label', 'N/A'),
                        rel.get('source_category', 'N/A'),
                        rel.get('relationship', 'N/A'),
                        rel.get('target_label', 'N/A'),
                        rel.get('target_category', 'N/A')
                    )
                console.print(table)
            
            console.print(f"\n[green]✅ Knowledge Map Extraction: PASSED[/green]")
            return True
            
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ JSON parsing error: {e}[/red]")
            console.print(f"[yellow]JSON content: {json_content[:500]}...[/yellow]")
            return False
            
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


async def test_single_tag_classification():
    """Test single-tag classification with Gemini"""
    console.print("\n[bold cyan]=" * 60)
    console.print("[bold cyan]Test 2: Single-Tag Classification[/bold cyan]")
    console.print("[bold cyan]=" * 60 + "\n")
    
    try:
        # Create a test task
        from classification.models import TaskDefinition, TaskType, OutputType
        
        test_task = TaskDefinition(
            tag="_test_prof_interests",
            task_type=TaskType.SINGLE,
            name="Professional Interests Test",
            description="Extract professional interests",
            prompt="""Extract the professional interests, focus areas, or expertise topics mentioned in this note.
Return a comma-separated list of interests. If no professional interests are found, return an empty string.

Examples:
- "Venture Capital, Technology Investing, Board Governance"
- "AI/ML, Enterprise SaaS, Data Analytics"
""",
            output_type=OutputType.LIST,
            enabled=True
        )
        
        # Build messages
        messages = [
            {"role": "system", "content": test_task.prompt},
            {"role": "user", "content": CLASSIFICATION_TEST_CONTENT}
        ]
        
        console.print("[cyan]Calling Gemini API for single-tag classification...[/cyan]")
        llm_client = await get_llm_client()
        response = await llm_client.generate(
            messages, 
            temperature=0.1, 
            max_tokens=500,
            skip_relationship_suffix=True
        )
        
        if not response.success:
            console.print(f"[red]❌ API call failed: {response.error}[/red]")
            return False
        
        console.print(f"[green]✅ API call successful![/green]")
        console.print(f"[dim]Response time: {response.response_time:.2f}s[/dim]\n")
        
        # Parse result (should be a simple string/list)
        result = response.content.strip()
        
        # Remove quotes if present
        if (result.startswith('"') and result.endswith('"')) or (result.startswith("'") and result.endswith("'")):
            result = result[1:-1]
        
        console.print(f"[green]✅ Classification Result:[/green]")
        console.print(Panel(result, title="Result", border_style="green"))
        
        # Validate it's a comma-separated list
        if result and ',' in result:
            items = [item.strip() for item in result.split(',')]
            console.print(f"[dim]Parsed into {len(items)} items: {items}[/dim]\n")
        
        console.print(f"[green]✅ Single-Tag Classification: PASSED[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


async def test_multi_tag_classification():
    """Test multi-tag classification with Gemini"""
    console.print("\n[bold cyan]=" * 60)
    console.print("[bold cyan]Test 3: Multi-Tag Classification[/bold cyan]")
    console.print("[bold cyan]=" * 60 + "\n")
    
    try:
        # Create a test multi-tag task (simplified VC analysis)
        from classification.models import TaskDefinition, TaskType, TagSchema, OutputType
        
        test_task = TaskDefinition(
            tag="_test_vc_analysis",
            task_type=TaskType.MULTI,
            name="VC Profile Analysis Test",
            description="Extract VC investment profile",
            prompt="""You are an expert VC researcher. Analyze this venture capital firm profile and extract structured information.

Use only evidence from the text provided. Do not hallucinate missing details. If unclear, return empty list or "unknown".

Extract the following information:
1. Investment stages they focus on (Pre-Seed, Seed, Series A, Series B, Growth)
2. Sectors/industries they invest in (AI/ML, Enterprise SaaS, Fintech, etc.)
3. Typical check size range (Small Seed $250k-$1M, Large Seed $1M-$3M, Series A Checks $3M-$10M, Growth Checks $10M+)

Return a JSON object with a "results" key containing all the extracted information.""",
            output_type=OutputType.TEXT,
            tag_schema=[
                TagSchema(tag="_test_vc_stages", output_type=OutputType.LIST, name="Investment Stages", description="Stages: Pre-Seed, Seed, Series A, Series B, Growth"),
                TagSchema(tag="_test_vc_sectors", output_type=OutputType.LIST, name="Investment Sectors", description="Sectors: AI/ML, Enterprise SaaS, Fintech, etc."),
                TagSchema(tag="_test_vc_size", output_type=OutputType.TEXT, name="Check Size Range", description="Size: Small Seed, Large Seed, Series A Checks, Growth Checks"),
            ],
            enabled=True
        )
        
        # Build messages (same format as classifier does)
        system_prompt = test_task.prompt
        user_prompt = f"Analyze this note and extract the information:\n\n{CLASSIFICATION_TEST_CONTENT}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        console.print("[cyan]Calling Gemini API for multi-tag classification...[/cyan]")
        llm_client = await get_llm_client()
        response = await llm_client.generate(
            messages,
            skip_relationship_suffix=True,
            max_tokens=2000,
            needs_json_format=True
        )
        
        if not response.success:
            console.print(f"[red]❌ API call failed: {response.error}[/red]")
            return False
        
        console.print(f"[green]✅ API call successful![/green]")
        console.print(f"[dim]Response time: {response.response_time:.2f}s[/dim]\n")
        
        # Parse JSON response
        content = response.content.strip()
        
        # Remove markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # Find JSON object
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        
        if json_start == -1 or json_end <= json_start:
            console.print(f"[red]❌ No JSON object found[/red]")
            console.print(f"[yellow]Response: {content[:500]}...[/yellow]")
            return False
        
        json_content = content[json_start:json_end]
        json_content = re.sub(r',(\s*[}\]])', r'\1', json_content)
        
        try:
            result = json.loads(json_content)
            
            # Check for "results" key
            if "results" not in result:
                console.print(f"[red]❌ Missing 'results' key in JSON[/red]")
                console.print(f"[yellow]Keys found: {list(result.keys())}[/yellow]")
                return False
            
            results = result["results"]
            
            console.print(f"[green]✅ Successfully parsed JSON![/green]")
            console.print(f"[green]Found {len(results)} tags[/green]\n")
            
            # Display results
            table = Table(title="Classification Results", show_header=True, header_style="bold magenta")
            table.add_column("Tag", style="cyan")
            table.add_column("Value", style="green")
            
            for tag, value in results.items():
                if isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                table.add_row(tag, value_str)
            console.print(table)
            
            # Validate expected tags are present
            expected_tags = ["_test_vc_stages", "_test_vc_sectors", "_test_vc_size"]
            missing_tags = [tag for tag in expected_tags if tag not in results]
            
            if missing_tags:
                console.print(f"[yellow]⚠ Missing tags: {missing_tags}[/yellow]")
            else:
                console.print(f"[green]✅ All expected tags present[/green]")
            
            console.print(f"\n[green]✅ Multi-Tag Classification: PASSED[/green]")
            return True
            
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ JSON parsing error: {e}[/red]")
            console.print(f"[yellow]JSON content: {json_content[:500]}...[/yellow]")
            return False
            
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


async def main():
    """Run all tests"""
    console.print("\n[bold green]🧪 Testing Gemini Integration[/bold green]")
    console.print("[bold green]Testing with Knowledge Map Extraction and Classification Tasks[/bold green]\n")
    
    # Check config
    config = get_config_loader()
    provider = config.get('llm.provider', 'cloud')
    model = config.get('llm.gemini.model', 'gemini-2.0-flash-exp')
    
    console.print(f"[dim]Provider: {provider}, Model: {model}[/dim]\n")
    
    if provider != 'gemini':
        console.print(f"[yellow]⚠️  Warning: Config shows provider='{provider}', expected 'gemini'[/yellow]")
        console.print("[yellow]   Update config.yaml: llm.provider: 'gemini'[/yellow]\n")
    
    results = []
    
    # Test 1: Knowledge Map Extraction
    results.append(await test_knowledge_map_extraction())
    
    # Test 2: Single-Tag Classification
    results.append(await test_single_tag_classification())
    
    # Test 3: Multi-Tag Classification
    results.append(await test_multi_tag_classification())
    
    # Summary
    console.print("\n[bold cyan]=" * 60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    console.print("[bold cyan]=" * 60 + "\n")
    
    test_names = [
        "Knowledge Map Extraction",
        "Single-Tag Classification",
        "Multi-Tag Classification"
    ]
    
    summary_table = Table(title="Test Results", show_header=True, header_style="bold")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Status", style="bold")
    
    for name, result in zip(test_names, results):
        status = "[green]✅ PASSED[/green]" if result else "[red]❌ FAILED[/red]"
        summary_table.add_row(name, status)
    
    console.print(summary_table)
    
    all_passed = all(results)
    if all_passed:
        console.print("\n[bold green]🎉 All tests passed! Gemini is working correctly.[/bold green]\n")
    else:
        console.print("\n[bold red]❌ Some tests failed. Please check the errors above.[/bold red]\n")
    
    await close_llm_client()
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
