#!/usr/bin/env python3
"""
Step 1: Extract relationships from markdown folder to cache/content/
This step processes markdown files and saves individual CSV files named by path.

CSV naming: Each markdown file gets a CSV named after its path.
Example: '30. People/John Smith.md' -> '30._People__John_Smith.csv'
"""

import asyncio
import csv
import hashlib
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import click
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from prompt_loader import get_prompt_loader
from obsidian_config_reader import ObsidianConfigReader
from llm_client import get_llm_client, close_llm_client

# Load environment variables
load_dotenv()

console = Console()


class Relationship(BaseModel):
    source_category: str = Field(description="Source entity category (Person or Company)")
    source_label: str = Field(description="Source entity name")
    relationship: str = Field(description="One-word relationship type")
    target_category: str = Field(description="Target entity category (Person or Company)")
    target_label: str = Field(description="Target entity name")
    source_file: Optional[str] = Field(default=None, description="Source file path")
    extracted_at: Optional[str] = Field(default=None, description="Extraction timestamp")


class RelationshipResponse(BaseModel):
    relationships: List[Relationship] = Field(
        description="List of relationships found in the text"
    )


class Step1Extractor:
    def __init__(
        self,
        vault_path: Path,
        chunking_backend: str = "recursive-markdown",
        chunk_threshold: float = 0.75,
        chunk_size: int = 1024,
        embedding_model: str = "minishlab/potion-base-8M",
    ):
        self.vault_path = vault_path
        self.chunking_backend = chunking_backend
        self.chunk_threshold = chunk_threshold
        self.chunk_size = chunk_size
        self.embedding_model = embedding_model
        
        # Initialize Obsidian config reader
        self.obsidian_config = ObsidianConfigReader(vault_path)
        self.template_folder = self._get_template_folder()
        
        # LLM client will be initialized when needed
        self.llm_client = None
            
        # Initialize chunker
        self._init_chunker()

    def _get_template_folder(self) -> Optional[str]:
        """Get template folder path from Obsidian configuration"""
        if self.obsidian_config.is_templates_enabled():
            template_folder = self.obsidian_config.get_template_folder()
            if template_folder:
                console.print(f"[cyan]Templates enabled, excluding folder: {template_folder}[/cyan]")
            return template_folder
        return None
    
    def _init_chunker(self):
        """Initialize the chunking backend"""
        if self.chunking_backend == "recursive-markdown":
            from chonkie import RecursiveChunker
            self.chunker = RecursiveChunker()
        elif self.chunking_backend == "semantic":
            from chonkie import SemanticChunker
            self.chunker = SemanticChunker(
                threshold=self.chunk_threshold,
                chunk_size=self.chunk_size,
                embedding_model=self.embedding_model,
            )
        else:
            raise ValueError(f"Unknown chunking backend: {self.chunking_backend}")

    def _get_kineviz_dir(self) -> Path:
        """Get the .kineviz_graph directory path"""
        kineviz_dir = self.vault_path / ".kineviz_graph"
        kineviz_dir.mkdir(exist_ok=True)
        return kineviz_dir

    def _get_cache_dir(self) -> Path:
        """Get the cache directory path"""
        cache_dir = self._get_kineviz_dir() / "cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    def _get_content_dir(self) -> Path:
        """Get the cache/content directory path"""
        content_dir = self._get_cache_dir() / "content"
        content_dir.mkdir(exist_ok=True)
        return content_dir

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def _normalize_path_to_filename(self, relative_path: Path) -> str:
        """Convert a relative path to a safe filename for CSV storage.
        
        Example: '30. People/John Smith.md' -> '30._People__John_Smith'
        """
        # Convert to string and remove .md extension
        path_str = str(relative_path)
        if path_str.endswith('.md'):
            path_str = path_str[:-3]
        
        # Replace path separators and spaces with underscores
        safe_name = path_str.replace('/', '__').replace('\\', '__').replace(' ', '_')
        
        # Remove or replace other problematic characters
        # Keep alphanumeric, underscore, dash, and dot
        import re
        safe_name = re.sub(r'[^\w\-.]', '_', safe_name)
        
        # Collapse multiple underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        
        # Trim leading/trailing underscores
        safe_name = safe_name.strip('_')
        
        return safe_name

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content"""
        if not content.startswith('---'):
            return {}, content
        
        lines = content.split('\n')
        if len(lines) < 2:
            return {}, content
        
        # Find the end of frontmatter
        end_idx = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_idx = i
                break
        
        if end_idx is None:
            return {}, content
        
        # Extract frontmatter and content
        frontmatter_lines = lines[1:end_idx]
        content_lines = lines[end_idx + 1:]
        
        frontmatter_text = '\n'.join(frontmatter_lines)
        content_text = '\n'.join(content_lines)
        
        # Parse YAML frontmatter
        try:
            import yaml
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except Exception:
            frontmatter = {}
        
        return frontmatter, content_text

    def _get_csv_path_for_file(self, file_path: Path) -> Path:
        """Get the CSV path for a given markdown file (pathname-based)."""
        relative_path = file_path.relative_to(self.vault_path)
        safe_name = self._normalize_path_to_filename(relative_path)
        return self._get_content_dir() / f"{safe_name}.csv"

    def _find_existing_csv(self, file_path: Path) -> Optional[Path]:
        """Find existing CSV file for this markdown file (pathname-based)."""
        csv_path = self._get_csv_path_for_file(file_path)
        if csv_path.exists():
            return csv_path
        return None

    async def _extract_relationships_from_text(self, text: str, source_file: str) -> tuple:
        """Extract relationships from text using LLM client.
        
        Args:
            text: The text to extract relationships from
            source_file: Source file path for tracking
        
        Returns:
            tuple: (relationships: List[Relationship], server_info: str or None)
        """
        try:
            # Initialize LLM client if not already done
            if not self.llm_client:
                self.llm_client = await get_llm_client()
            
            # Load prompts from configuration
            prompt_loader = get_prompt_loader()
            messages = prompt_loader.get_prompt_pair("relationship_extraction", text=text)
            model_config = prompt_loader.get_model_config("relationship_extraction")
            
            # Generate response using LLM client
            response = await self.llm_client.generate(
                messages=messages,
                temperature=model_config["temperature"],
                max_tokens=8000  # Increased from 2000 to handle large JSON responses
            )
            
            # Extract server info for logging
            server_info = None
            if response.server_url:
                # Extract server name from URL (e.g., "http://bsrs-mac-studio:11434" -> "bsrs-mac-studio")
                server_name = response.server_url.replace("http://", "").replace(":11434", "")
                server_info = f"{server_name} ({response.response_time:.1f}s)"
            
            if not response.success:
                console.print(f"[red]LLM generation failed: {response.error}[/red]")
                return [], server_info

            # Clean and parse JSON response
            cleaned_json = self._clean_json_response(response.content)
            
            try:
                result = RelationshipResponse.model_validate_json(cleaned_json)
                relationships = result.relationships
                
                # Filter out relationships with invalid categories (only Person and Company allowed)
                valid_relationships = []
                invalid_count = 0
                for rel in relationships:
                    if rel.source_category in ['Person', 'Company'] and rel.target_category in ['Person', 'Company']:
                        valid_relationships.append(rel)
                    else:
                        invalid_count += 1
                        console.print(f"[yellow]⚠ Filtered invalid category: {rel.source_category} -> {rel.target_category} ({rel.source_label} -> {rel.target_label})[/yellow]")
                
                if invalid_count > 0:
                    console.print(f"[yellow]Filtered {invalid_count} relationships with invalid categories (only Person/Company allowed)[/yellow]")
                
                relationships = valid_relationships
            except Exception as validation_error:
                # Try to salvage partial relationships from incomplete responses
                relationships = self._extract_partial_relationships(cleaned_json)
                if relationships:
                    console.print(f"[yellow]Recovered {len(relationships)} partial relationships[/yellow]")
                else:
                    # Find and show the specific problematic relationship
                    console.print(f"[red]Error extracting relationships: {validation_error}[/red]")
                    self._show_problematic_relationship(cleaned_json)
                    return [], server_info
            
            # Filter out relationships with invalid categories (only Person and Company allowed)
            valid_relationships = []
            invalid_count = 0
            for rel in relationships:
                if rel.source_category in ['Person', 'Company'] and rel.target_category in ['Person', 'Company']:
                    valid_relationships.append(rel)
                else:
                    invalid_count += 1
                    console.print(f"[yellow]⚠ Filtered invalid category: {rel.source_category} -> {rel.target_category} ({rel.source_label} -> {rel.target_label})[/yellow]")
            
            if invalid_count > 0:
                console.print(f"[yellow]Filtered {invalid_count} relationships with invalid categories (only Person/Company allowed)[/yellow]")
            
            relationships = valid_relationships
            
            # Add source file info to each relationship (both normal and partial)
            for rel in relationships:
                rel.source_file = source_file
                rel.extracted_at = "2024-01-01T00:00:00Z"  # Default timestamp
                
            return relationships, server_info

        except Exception as e:
            console.print(f"[red]Error extracting relationships: {e}[/red]")
            return [], None
    
    def _show_problematic_relationship(self, json_str: str) -> None:
        """Find and display the specific relationship that failed to parse."""
        import re
        
        # Try to find all relationship objects using regex
        # Pattern matches: {"source_category": ... } allowing for incomplete objects
        pattern = r'\{[^{}]*"source_category"[^{}]*\}'
        
        # Also try to find incomplete objects at the end
        incomplete_pattern = r'\{[^{}]*"source_category"[^}]*$'
        
        complete_matches = re.findall(pattern, json_str)
        incomplete_match = re.search(incomplete_pattern, json_str)
        
        console.print(f"[yellow]Found {len(complete_matches)} complete relationship objects[/yellow]")
        
        # Validate each complete match to find which ones are problematic
        import json
        last_valid_idx = -1
        first_invalid = None
        
        for i, match in enumerate(complete_matches):
            try:
                obj = json.loads(match)
                required = ['source_category', 'source_label', 'relationship', 'target_category', 'target_label']
                if all(obj.get(field) for field in required):
                    last_valid_idx = i
                else:
                    if first_invalid is None:
                        first_invalid = (i, match, "Missing required fields")
            except json.JSONDecodeError as e:
                if first_invalid is None:
                    first_invalid = (i, match, str(e))
        
        if first_invalid:
            idx, match, error = first_invalid
            console.print(f"[red]❌ Relationship #{idx + 1} is invalid: {error}[/red]")
            console.print(f"[yellow]{match[:200]}{'...' if len(match) > 200 else ''}[/yellow]")
        
        if incomplete_match:
            console.print(f"[red]❌ Incomplete/truncated relationship at end:[/red]")
            incomplete_text = incomplete_match.group()
            console.print(f"[yellow]{incomplete_text[:300]}{'...' if len(incomplete_text) > 300 else ''}[/yellow]")
        elif not first_invalid:
            # Show the end of the JSON where the problem likely is
            console.print(f"[red]❌ JSON truncated or malformed at end:[/red]")
            console.print(f"[yellow]{repr(json_str[-200:])}[/yellow]")
        
        console.print(f"[dim]Total response length: {len(json_str)} chars[/dim]")
    
    def _extract_partial_relationships(self, json_str: str) -> List[Relationship]:
        """Try to extract valid relationships from partially invalid JSON"""
        import json
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict) or 'relationships' not in data:
                return []
            
            valid_rels = []
            for rel in data.get('relationships', []):
                # Check all required fields are present
                required = ['source_category', 'source_label', 'relationship', 'target_category', 'target_label']
                if all(rel.get(field) for field in required):
                    try:
                        valid_rels.append(Relationship(**rel))
                    except Exception:
                        pass  # Skip invalid relationships
            
            return valid_rels
        except json.JSONDecodeError:
            return []
    
    def _clean_json_response(self, content: str) -> str:
        """Clean LLM response to extract valid JSON"""
        # Remove markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
        
        # Remove any leading/trailing whitespace and newlines
        content = content.strip()
        
        # Always try to find the JSON object by locating first { and last }
        # This handles cases where models add explanatory text before or after JSON
        json_start = content.find('{')
        json_end = content.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_end > json_start:
            # Extract just the JSON object
            json_content = content[json_start:json_end+1]
            
            # Fix common JSON issues: trailing commas before closing brackets/braces
            # (re is already imported at the top for _show_problematic_relationship)
            import re
            json_content = re.sub(r',(\s*[}\]])', r'\1', json_content)
            
            return json_content
        
        # If no JSON object found, return original (will fail validation but that's expected)
        return content

    def _save_relationships_to_csv(self, file_path: Path, relationships: List[Relationship]) -> str:
        """Save relationships to CSV file (pathname-based naming)."""
        csv_path = self._get_csv_path_for_file(file_path)
        csv_filename = csv_path.name
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['source_category', 'source_label', 'relationship', 'target_category', 'target_label', 'source_file', 'extracted_at'])
            for rel in relationships:
                writer.writerow([
                    rel.source_category,
                    rel.source_label,
                    rel.relationship,
                    rel.target_category,
                    rel.target_label,
                    rel.source_file,
                    rel.extracted_at
                ])
        
        console.print(f"[green]Saved {len(relationships)} relationships to {csv_filename}[/green]")
        return csv_filename

    async def _process_file(self, file_path: Path) -> None:
        """Process a single markdown file and extract relationships."""
        # Check if file should be processed (template exclusion)
        try:
            relative_path = file_path.relative_to(self.vault_path)
            
            # Skip files in template folder if templates are enabled
            if self.template_folder:
                if str(relative_path).startswith(self.template_folder + "/"):
                    console.print(f"[yellow]Skipping template file: {relative_path}[/yellow]")
                    return
        except ValueError:
            # File is not relative to vault path, skip it
            console.print(f"[yellow]Skipping file outside vault: {file_path}[/yellow]")
            return
        
        console.print(f"[cyan]Processing {file_path}[/cyan]")
        
        try:
            # Read file content
            content = file_path.read_text(encoding='utf-8')
            relative_path = file_path.relative_to(self.vault_path)
            
            # Check if we already have a CSV for this file (pathname-based)
            existing_csv = self._find_existing_csv(file_path)
            if existing_csv:
                console.print(f"[yellow]Skipping {file_path} - already processed (CSV exists)[/yellow]")
                return
            
            # Parse frontmatter and get content only
            frontmatter, content_only = self._parse_frontmatter(content)
            
            # Chunk the content (excluding metadata)
            if self.chunking_backend == "recursive-markdown":
                chunks = self.chunker.chunk(content_only)
            else:  # semantic
                chunks = self.chunker.chunk(content_only)
            
            console.print(f"[cyan]Created {len(chunks)} chunks from {file_path}[/cyan]")
            
            # Extract relationships from chunks - SEQUENTIAL processing
            # This prevents Ollama from being overwhelmed with queued requests
            # which can cause timeouts and errors
            import time as time_module
            start_time = time_module.time()
            
            results = []
            for i, chunk in enumerate(chunks):
                send_time = time_module.time() - start_time
                console.print(f"[blue]  ⬆ Chunk {i+1}/{len(chunks)} sent @ {send_time:.1f}s[/blue]")
                
                relationships, server_info = await self._extract_relationships_from_text(
                    chunk.text, str(relative_path)
                )
                
                done_time = time_module.time() - start_time
                rel_count = len(relationships) if relationships else 0
                server_str = f"→ {server_info}" if server_info else ""
                console.print(f"[green]  ⬇ Chunk {i+1}/{len(chunks)} done @ {done_time:.1f}s {server_str} ({rel_count} rels)[/green]")
                
                results.append((i, relationships, server_info))
            
            # Collect results
            all_relationships = []
            for i, relationships, server_info in sorted(results, key=lambda x: x[0]):
                if relationships:
                    all_relationships.extend(relationships)
            
            total_time = time_module.time() - start_time
            console.print(f"[cyan]All {len(chunks)} chunks completed in {total_time:.1f}s[/cyan]")
            
            # Save relationships to CSV (always create a file, even if empty)
            self._save_relationships_to_csv(file_path, all_relationships)
            if all_relationships:
                console.print(f"[green]Processed {file_path} -> {len(all_relationships)} relationships[/green]")
            else:
                console.print(f"[yellow]No relationships found in {file_path} - created empty CSV[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error processing {file_path}: {e}[/red]")

    async def process_vault(self, max_concurrent: int = 5) -> None:
        """Process all markdown files in the Obsidian vault"""
        console.print(f"[cyan]Processing Obsidian vault: {self.vault_path}[/cyan]")
        
        # Find all markdown files in the vault (excluding .obsidian, .kineviz_graph, and template folder)
        markdown_files = []
        for file_path in self.vault_path.rglob("*.md"):
            # Skip files in hidden directories
            if any(part.startswith('.') for part in file_path.relative_to(self.vault_path).parts):
                continue
            
            # Skip files in template folder if templates are enabled
            if self.template_folder:
                try:
                    relative_path = file_path.relative_to(self.vault_path)
                    if str(relative_path).startswith(self.template_folder + "/"):
                        console.print(f"[yellow]Skipping template file: {relative_path}[/yellow]")
                        continue
                except ValueError:
                    # File is not relative to vault path, skip it
                    continue
            
            markdown_files.append(file_path)
        
        console.print(f"[cyan]Found {len(markdown_files)} markdown files[/cyan]")
        
        if not markdown_files:
            console.print("[yellow]No markdown files found[/yellow]")
            return
        
        # Initialize LLM client
        if not self.llm_client:
            self.llm_client = await get_llm_client()
        
        # Process files sequentially to avoid overwhelming Ollama
        # Each file's chunks are also processed sequentially
        # This prevents request piling and timeout errors
        console.print(f"[cyan]Processing files sequentially (1 chunk at a time to Ollama)[/cyan]")
        
        for file_path in markdown_files:
            await self._process_file(file_path)
        
        console.print("[green]Step 1 completed: All files processed to .kineviz_graph/cache/content/[/green]")


@click.command()
@click.option("--vault-path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
              default=lambda: os.getenv("VAULT_PATH"), 
              help="Path to Obsidian vault (default: VAULT_PATH env var)")
@click.option("--max-concurrent", default=lambda: int(os.getenv("MAX_CONCURRENT", "5")), 
              type=int,
              help="Maximum number of concurrent file processing tasks (default: MAX_CONCURRENT env var or 5)")
@click.option("--chunk-threshold", default=0.75, help="Semantic similarity threshold for chunking (0.0-1.0)")
@click.option("--chunk-size", default=1024, help="Maximum chunk size in tokens")
@click.option("--embedding-model", default="minishlab/potion-base-8M", help="Embedding model for semantic chunking")
@click.option("--chunking-backend", default="recursive-markdown", help="Chunking backend to use")
def main(
    vault_path: Path,
    max_concurrent: int,
    chunk_threshold: float,
    chunk_size: int,
    embedding_model: str,
    chunking_backend: str,
):
    """Step 1: Extract relationships from Obsidian vault to cache/content/"""
    
    # Validate vault path
    if not vault_path:
        console.print("[red]Error: Vault path is required. Set VAULT_PATH environment variable or use --vault-path[/red]")
        console.print("[yellow]Example: uv run step1_extract.py --vault-path '/path/to/vault'[/yellow]")
        console.print("[yellow]Or set VAULT_PATH in your .env file[/yellow]")
        sys.exit(1)
    
    try:
        extractor = Step1Extractor(
            vault_path=vault_path,
            chunking_backend=chunking_backend,
            chunk_threshold=chunk_threshold,
            chunk_size=chunk_size,
            embedding_model=embedding_model,
        )
        asyncio.run(extractor.process_vault(max_concurrent))
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
