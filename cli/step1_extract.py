#!/usr/bin/env python3
"""
Step 1: Extract relationships from markdown folder to cache/content/
This step processes markdown files and saves individual CSV files with content hashes.
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
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from rich.console import Console
from prompt_loader import get_prompt_loader
from obsidian_config_reader import ObsidianConfigReader

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
        openai_api_key: Optional[str] = None,
        chunking_backend: str = "recursive-markdown",
        chunk_threshold: float = 0.75,
        chunk_size: int = 1024,
        embedding_model: str = "minishlab/potion-base-8M",
    ):
        self.vault_path = vault_path
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.chunking_backend = chunking_backend
        self.chunk_threshold = chunk_threshold
        self.chunk_size = chunk_size
        self.embedding_model = embedding_model
        
        # Initialize Obsidian config reader
        self.obsidian_config = ObsidianConfigReader(vault_path)
        self.template_folder = self._get_template_folder()
        
        # Initialize OpenAI client
        if self.openai_api_key:
            self.client = AsyncOpenAI(api_key=self.openai_api_key)
        else:
            self.client = None
            
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

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate hash of content (excluding metadata)"""
        _, content_only = self._parse_frontmatter(content)
        return hashlib.sha256(content_only.encode('utf-8')).hexdigest()

    def _calculate_metadata_hash(self, content: str) -> str:
        """Calculate hash of metadata section only"""
        frontmatter, _ = self._parse_frontmatter(content)
        import json
        # Convert non-serializable objects to strings for JSON serialization
        serializable_frontmatter = self._make_serializable(frontmatter)
        metadata_str = json.dumps(serializable_frontmatter, sort_keys=True)
        return hashlib.sha256(metadata_str.encode('utf-8')).hexdigest()
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert non-serializable objects to strings for JSON serialization."""
        if isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__str__') and not isinstance(obj, (str, int, float, bool, type(None))):
            return str(obj)
        else:
            return obj

    def _find_existing_csv(self, file_path: Path) -> Optional[Path]:
        """Find existing CSV file for this content hash"""
        content_hash = self._get_file_hash(file_path)
        content_dir = self._get_content_dir()
        
        # Look for existing CSV with this content hash
        for csv_file in content_dir.glob(f"{content_hash}_*.csv"):
            return csv_file
        return None

    def _find_existing_content_csv(self, file_path: Path) -> Optional[Path]:
        """Find existing CSV file for this content hash (excluding metadata)"""
        content = file_path.read_text(encoding='utf-8')
        content_hash = self._calculate_content_hash(content)
        content_dir = self._get_content_dir()
        
        # Look for existing CSV with this content hash
        for csv_file in content_dir.glob(f"{content_hash}_*.csv"):
            return csv_file
        return None

    async def _extract_relationships_from_text(self, text: str, source_file: str) -> List[Relationship]:
        """Extract relationships from text using OpenAI"""
        if not self.client:
            console.print("[yellow]No OpenAI client available, skipping extraction[/yellow]")
            return []

        try:
            # Load prompts from configuration
            prompt_loader = get_prompt_loader()
            messages = prompt_loader.get_prompt_pair("relationship_extraction", text=text)
            model_config = prompt_loader.get_model_config("relationship_extraction")
            
            response = await self.client.chat.completions.create(
                model=model_config["model"],
                messages=messages,
                response_format={"type": model_config["response_format"]},
                temperature=model_config["temperature"],
            )

            result = RelationshipResponse.model_validate_json(
                response.choices[0].message.content
            )
            
            # Add source file info to each relationship
            for rel in result.relationships:
                rel.source_file = source_file
                rel.extracted_at = "2024-01-01T00:00:00Z"  # Default timestamp
                
            return result.relationships

        except Exception as e:
            console.print(f"[red]Error extracting relationships: {e}[/red]")
            return []

    def _save_relationships_to_csv(self, file_path: Path, relationships: List[Relationship]) -> str:
        """Save relationships to CSV file with content hash (excluding metadata)"""
        content = file_path.read_text(encoding='utf-8')
        content_hash = self._calculate_content_hash(content)
        timestamp = "2024-01-01T00-00-00Z"  # Default timestamp
        csv_filename = f"{content_hash}_{timestamp}.csv"
        csv_path = self._get_content_dir() / csv_filename
        
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
        """Process a single markdown file with metadata/content separation"""
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
            
            # Calculate hashes
            file_hash = self._get_file_hash(file_path)
            content_hash = self._calculate_content_hash(content)
            metadata_hash = self._calculate_metadata_hash(content)
            
            # Check if we already have a CSV for this content (excluding metadata)
            existing_csv = self._find_existing_content_csv(file_path)
            if existing_csv:
                console.print(f"[yellow]Skipping {file_path} - content unchanged (metadata may have changed)[/yellow]")
                return
            
            # Parse frontmatter and get content only
            frontmatter, content_only = self._parse_frontmatter(content)
            
            # Chunk the content (excluding metadata)
            if self.chunking_backend == "recursive-markdown":
                chunks = self.chunker.chunk(content_only)
            else:  # semantic
                chunks = self.chunker.chunk(content_only)
            
            console.print(f"[cyan]Created {len(chunks)} chunks from {file_path}[/cyan]")
            
            # Extract relationships from each chunk
            all_relationships = []
            for i, chunk in enumerate(chunks):
                console.print(f"[cyan]Processing chunk {i+1}/{len(chunks)}[/cyan]")
                relationships = await self._extract_relationships_from_text(
                    chunk.text, str(relative_path)
                )
                all_relationships.extend(relationships)
            
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
        
        # Process files with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(file_path):
            async with semaphore:
                await self._process_file(file_path)
        
        # Process all files
        tasks = [process_with_semaphore(file_path) for file_path in markdown_files]
        await asyncio.gather(*tasks)
        
        console.print("[green]Step 1 completed: All files processed to .kineviz_graph/cache/content/[/green]")


@click.command()
@click.option("--vault-path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
              default=lambda: os.getenv("VAULT_PATH"), 
              help="Path to Obsidian vault (default: VAULT_PATH env var)")
@click.option("--openai-api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
@click.option("--max-concurrent", default=lambda: int(os.getenv("MAX_CONCURRENT", "5")), 
              type=int,
              help="Maximum number of concurrent file processing tasks (default: MAX_CONCURRENT env var or 5)")
@click.option("--chunk-threshold", default=0.75, help="Semantic similarity threshold for chunking (0.0-1.0)")
@click.option("--chunk-size", default=1024, help="Maximum chunk size in tokens")
@click.option("--embedding-model", default="minishlab/potion-base-8M", help="Embedding model for semantic chunking")
@click.option("--chunking-backend", default="recursive-markdown", help="Chunking backend to use")
def main(
    vault_path: Path,
    openai_api_key: Optional[str],
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
    
    # Only require OpenAI API key if extraction is enabled
    if not openai_api_key and not os.getenv("OPENAI_API_KEY"):
        console.print(
            "[red]Error: OpenAI API key required. Set OPENAI_API_KEY env var or use --openai-api-key[/red]"
        )
        sys.exit(1)

    try:
        extractor = Step1Extractor(
            vault_path=vault_path,
            openai_api_key=openai_api_key,
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
