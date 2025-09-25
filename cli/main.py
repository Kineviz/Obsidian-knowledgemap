#!/usr/bin/env python3
"""
Knowledge Map Tool - Simplified Schema
Convert markdown files to a Kuzu knowledge graph with Person/Company relationships
"""

from dotenv import load_dotenv
import asyncio
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import hishel
import kuzu
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from chonkie import RecursiveChunker, SemanticChunker

load_dotenv()

console = Console()


# Pydantic models for simplified schema - Person/Company only
class Entity(BaseModel):
    label: str = Field(description="The entity name")
    category: str = Field(
        description="The entity category (Person or Company only)"
    )


class Relationship(BaseModel):
    source_category: str = Field(description="Source entity category (Person or Company)")
    source_label: str = Field(description="Source entity name")
    relationship: str = Field(description="One-word relationship type")
    target_category: str = Field(description="Target entity category (Person or Company)")
    target_label: str = Field(description="Target entity name")


class RelationshipResponse(BaseModel):
    relationships: List[Relationship] = Field(
        description="List of extracted relationships between Person and Company entities"
    )


class KnowledgeMapTool:
    def __init__(
        self,
        db_path: str = "default.kz",
        openai_api_key: Optional[str] = None,
        skip_extraction: bool = False,
        chunking_backend: str = "recursive-markdown",
        chunk_threshold: float = 0.75,
        chunk_size: int = 1024,
        embedding_model: str = "minishlab/potion-base-8M",
    ):
        console.print(
            f"[cyan]KnowledgeMapTool.__init__(db_path={db_path}, openai_api_key={'***' if openai_api_key else None}, skip_extraction={skip_extraction}, chunking_backend={chunking_backend})[/cyan]"
        )
        self.db_path = db_path
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self.skip_extraction = skip_extraction

        # Only initialize OpenAI client if extraction is enabled
        if not skip_extraction:
            self.openai_client = AsyncOpenAI(
                api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
            )
        else:
            self.openai_client = None

        # Setup HTTP client with caching
        storage = hishel.FileStorage()
        self.http_client = hishel.CacheClient(storage=storage)

        # Setup chunker based on backend choice
        self.chunking_backend = chunking_backend
        self.chunker = self._create_chunker(
            chunking_backend, chunk_threshold, chunk_size, embedding_model
        )

        self._init_schema()

    def _create_chunker(
        self, backend: str, threshold: float, chunk_size: int, embedding_model: str
    ):
        """Create the appropriate chunker based on backend choice"""
        console.print(f"[cyan]Creating {backend} chunker[/cyan]")
        
        if backend == "recursive-markdown":
            return RecursiveChunker.from_recipe("markdown", lang="en")
        elif backend == "semantic":
            return SemanticChunker(
                embedding_model=embedding_model,
                threshold=threshold,
                chunk_size=chunk_size,
            )
        else:
            raise ValueError(
                f"Unsupported chunking backend: {backend}. "
                "Supported backends: 'recursive-markdown', 'semantic'"
            )

    def _init_schema(self):
        """Initialize the simplified Kuzu database schema with separate Person and Company tables"""
        console.print("[cyan]KnowledgeMapTool._init_schema()[/cyan]")
        schema_queries = [
            """INSTALL JSON; LOAD EXTENSION JSON;""",
            # Person nodes
            """CREATE NODE TABLE IF NOT EXISTS Person (
                id STRING PRIMARY KEY,
                label STRING
            )""",
            # Company nodes
            """CREATE NODE TABLE IF NOT EXISTS Company (
                id STRING PRIMARY KEY,
                label STRING
            )""",
            # Note nodes (markdown files with content)
            """CREATE NODE TABLE IF NOT EXISTS Note (
                id STRING PRIMARY KEY,
                label STRING,
                url STRING,
                content STRING
            )""",
            # Person to Person relationships
            """CREATE REL TABLE IF NOT EXISTS PERSON_TO_PERSON(
                FROM Person TO Person,
                relationship STRING
            )""",
            # Person to Company relationships
            """CREATE REL TABLE IF NOT EXISTS PERSON_TO_COMPANY(
                FROM Person TO Company,
                relationship STRING
            )""",
            # Company to Company relationships
            """CREATE REL TABLE IF NOT EXISTS COMPANY_TO_COMPANY(
                FROM Company TO Company,
                relationship STRING
            )""",
            # Company to Person relationships
            """CREATE REL TABLE IF NOT EXISTS COMPANY_TO_PERSON(
                FROM Company TO Person,
                relationship STRING
            )""",
            # Person to Note references
            """CREATE REL TABLE IF NOT EXISTS PERSON_REFERENCE(
                FROM Person TO Note,
                meta JSON
            )""",
            # Company to Note references
            """CREATE REL TABLE IF NOT EXISTS COMPANY_REFERENCE(
                FROM Company TO Note,
                meta JSON
            )""",
        ]

        for query in schema_queries:
            self.conn.execute(query)

    def _get_cache_dir(self) -> Path:
        """Get cache directory path"""
        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    def _get_csv_filename(self, file_path: Path, content_hash: str) -> str:
        """Generate CSV filename for a markdown file"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        return f"{content_hash}_{timestamp}.csv"

    def _find_existing_csv(self, file_path: Path, content_hash: str) -> Optional[Path]:
        """Find existing CSV file for a markdown file based on content hash"""
        cache_dir = self._get_cache_dir()
        # Look for CSV files that start with the content hash
        pattern = f"{content_hash}_*.csv"
        matching_files = list(cache_dir.glob(pattern))
        
        if matching_files:
            # Return the most recent one (by filename timestamp)
            return max(matching_files, key=lambda p: p.name)
        return None

    def _save_relationships_to_csv(self, file_path: Path, relationships: List[Relationship]) -> str:
        """Save relationships to CSV file and return the filename"""
        content_hash = self._get_file_hash(file_path)
        csv_filename = self._get_csv_filename(file_path, content_hash)
        csv_path = self._get_cache_dir() / csv_filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['source_category', 'source_label', 'relationship', 'target_category', 'target_label', 'source_file', 'extracted_at']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for rel in relationships:
                writer.writerow({
                    'source_category': rel.source_category,
                    'source_label': rel.source_label,
                    'relationship': rel.relationship,
                    'target_category': rel.target_category,
                    'target_label': rel.target_label,
                    'source_file': str(file_path),
                    'extracted_at': datetime.now(timezone.utc).isoformat()
                })
        
        console.print(f"[green]Saved {len(relationships)} relationships to {csv_filename}[/green]")
        return csv_filename

    def _load_relationships_from_csv(self, csv_path: Path) -> List[dict]:
        """Load relationships from a CSV file"""
        relationships = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Keep as dictionary to preserve extracted_at and other fields
                    relationships.append(row)
        except Exception as e:
            console.print(f"[red]Error loading CSV {csv_path}: {e}[/red]")
        return relationships

    def _build_knowledge_graph_from_csvs(self) -> None:
        """Build knowledge graph from all CSV files in cache"""
        cache_dir = self._get_cache_dir()
        csv_files = list(cache_dir.glob("*.csv"))
        
        if not csv_files:
            console.print("[yellow]No CSV files found in cache[/yellow]")
            return
        
        console.print(f"[cyan]Loading {len(csv_files)} CSV files from cache[/cyan]")
        
        all_relationships = []
        for csv_file in csv_files:
            relationships = self._load_relationships_from_csv(csv_file)
            all_relationships.extend(relationships)
        
        console.print(f"[green]Loaded {len(all_relationships)} total relationships[/green]")
        
        # Create entities and relationships
        persons_created = set()
        companies_created = set()
        
        for rel in all_relationships:
            # Create source entity
            source_id = rel.source_label
            if rel.source_category == 'Person' and source_id not in persons_created:
                if not self._entity_exists("Person", source_id):
                    self._create_node(
                        "Person",
                        {
                            "id": source_id,
                            "label": rel.source_label,
                        },
                    )
                persons_created.add(source_id)
            elif rel.source_category == 'Company' and source_id not in companies_created:
                if not self._entity_exists("Company", source_id):
                    self._create_node(
                        "Company",
                        {
                            "id": source_id,
                            "label": rel.source_label,
                        },
                    )
                companies_created.add(source_id)
            
            # Create target entity
            target_id = rel.target_label
            if rel.target_category == 'Person' and target_id not in persons_created:
                if not self._entity_exists("Person", target_id):
                    self._create_node(
                        "Person",
                        {
                            "id": target_id,
                            "label": rel.target_label,
                        },
                    )
                persons_created.add(target_id)
            elif rel.target_category == 'Company' and target_id not in companies_created:
                if not self._entity_exists("Company", target_id):
                    self._create_node(
                        "Company",
                        {
                            "id": target_id,
                            "label": rel.target_label,
                        },
                    )
                companies_created.add(target_id)
            
            # Create appropriate relationship based on types
            relationship_type = self._get_relationship_type(rel.source_category, rel.target_category)
            self._create_edge(
                relationship_type,
                source_id,
                target_id,
                rel.relationship
            )
            
            # Create reference edges from entities to the note (if we have note info)
            if hasattr(rel, 'source_file') and rel.source_file:
                note_id = rel.source_file
                # Create reference from source entity to note
                if rel.source_category == 'Person':
                    self._create_edge("PERSON_REFERENCE", source_id, note_id)
                elif rel.source_category == 'Company':
                    self._create_edge("COMPANY_REFERENCE", source_id, note_id)
                
                # Create reference from target entity to note
                if rel.target_category == 'Person':
                    self._create_edge("PERSON_REFERENCE", target_id, note_id)
                elif rel.target_category == 'Company':
                    self._create_edge("COMPANY_REFERENCE", target_id, note_id)
        
        total_entities = len(persons_created) + len(companies_created)
        console.print(f"[green]Created {len(persons_created)} persons, {len(companies_created)} companies, and {len(all_relationships)} relationships[/green]")

    def _get_relationship_type(self, source_category: str, target_category: str) -> str:
        """Get the appropriate relationship type based on source and target categories"""
        if source_category == 'Person' and target_category == 'Person':
            return 'PERSON_TO_PERSON'
        elif source_category == 'Person' and target_category == 'Company':
            return 'PERSON_TO_COMPANY'
        elif source_category == 'Company' and target_category == 'Company':
            return 'COMPANY_TO_COMPANY'
        elif source_category == 'Company' and target_category == 'Person':
            return 'COMPANY_TO_PERSON'
        else:
            raise ValueError(f"Unknown relationship: {source_category} -> {target_category}")

    def _entity_exists(self, entity_type: str, entity_id: str) -> bool:
        """Check if an entity already exists in the database"""
        query = f"MATCH (n:{entity_type}) WHERE n.id = $entity_id RETURN n"
        result = self.conn.execute(query, {"entity_id": entity_id})
        return result.has_next()

    def _process_relationships(self, relationships: List[Relationship]) -> None:
        """Process a list of relationships into the knowledge graph"""
        persons_created = set()
        companies_created = set()
        
        for rel in relationships:
            # Create source entity
            source_id = rel.source_label
            if rel.source_category == 'Person' and source_id not in persons_created:
                if not self._entity_exists("Person", source_id):
                    self._create_node(
                        "Person",
                        {
                            "id": source_id,
                            "label": rel.source_label,
                        },
                    )
                persons_created.add(source_id)
            elif rel.source_category == 'Company' and source_id not in companies_created:
                if not self._entity_exists("Company", source_id):
                    self._create_node(
                        "Company",
                        {
                            "id": source_id,
                            "label": rel.source_label,
                        },
                    )
                companies_created.add(source_id)
            
            # Create target entity
            target_id = rel.target_label
            if rel.target_category == 'Person' and target_id not in persons_created:
                if not self._entity_exists("Person", target_id):
                    self._create_node(
                        "Person",
                        {
                            "id": target_id,
                            "label": rel.target_label,
                        },
                    )
                persons_created.add(target_id)
            elif rel.target_category == 'Company' and target_id not in companies_created:
                if not self._entity_exists("Company", target_id):
                    self._create_node(
                        "Company",
                        {
                            "id": target_id,
                            "label": rel.target_label,
                        },
                    )
                companies_created.add(target_id)
            
            # Create appropriate relationship based on types
            relationship_type = self._get_relationship_type(rel.source_category, rel.target_category)
            self._create_edge(
                relationship_type,
                source_id,
                target_id,
                rel.relationship
            )
            
            # Create reference edges from entities to the note (if we have note info)
            if hasattr(rel, 'source_file') and rel.source_file:
                note_id = rel.source_file
                # Create reference from source entity to note
                if rel.source_category == 'Person':
                    self._create_edge("PERSON_REFERENCE", source_id, note_id)
                elif rel.source_category == 'Company':
                    self._create_edge("COMPANY_REFERENCE", source_id, note_id)
                
                # Create reference from target entity to note
                if rel.target_category == 'Person':
                    self._create_edge("PERSON_REFERENCE", target_id, note_id)
                elif rel.target_category == 'Company':
                    self._create_edge("COMPANY_REFERENCE", target_id, note_id)

    def migrate_cache_to_organized_structure(self) -> None:
        """Migrate existing cache/content/*.csv files to organized cache/db_input/ structure"""
        console.print("[cyan]Starting migration from cache/content/ to cache/db_input/[/cyan]")
        
        # Create db_input directory
        db_input_dir = self._get_cache_dir() / "db_input"
        db_input_dir.mkdir(exist_ok=True)
        
        # Create content directory if it doesn't exist
        content_dir = self._get_cache_dir() / "content"
        content_dir.mkdir(exist_ok=True)
        
        # Move existing CSV files to content directory
        cache_dir = self._get_cache_dir()
        for csv_file in cache_dir.glob("*.csv"):
            if not csv_file.name.startswith("person") and not csv_file.name.startswith("company"):
                target_path = content_dir / csv_file.name
                if not target_path.exists():
                    csv_file.rename(target_path)
                    console.print(f"[green]Moved {csv_file.name} to content/[/green]")
        
        # Load all relationships from content CSV files
        all_relationships = []
        content_csv_files = list(content_dir.glob("*.csv"))
        
        if not content_csv_files:
            console.print("[yellow]No CSV files found in cache/content/[/yellow]")
            return
        
        console.print(f"[cyan]Loading {len(content_csv_files)} CSV files from cache/content/[/cyan]")
        
        for csv_file in content_csv_files:
            relationships = self._load_relationships_from_csv(csv_file)
            all_relationships.extend(relationships)
        
        console.print(f"[green]Loaded {len(all_relationships)} total relationships[/green]")
        
        # Process relationships into organized structure
        self._create_organized_csvs_from_relationships(all_relationships)
        
        console.print("[green]Migration completed![/green]")

    def _create_organized_csvs_from_relationships(self, relationships: List[dict]) -> None:
        """Create organized CSV files from relationships"""
        console.print("[cyan]Creating organized CSV files...[/cyan]")
        
        # Initialize data structures
        persons = {}  # id -> {id, label}
        companies = {}  # id -> {id, label}
        person_to_person = set()  # (source_id, target_id, relationship)
        person_to_company = set()  # (person_id, company_id, relationship)
        company_to_company = set()  # (source_id, target_id, relationship)
        
        for rel in relationships:
            # Normalize relationship (reorder COMPANY_TO_PERSON to PERSON_TO_COMPANY)
            if rel['source_category'] == 'Company' and rel['target_category'] == 'Person':
                # Reorder: Company -> Person becomes Person -> Company
                source_id = rel['target_label']
                target_id = rel['source_label']
                source_category = 'Person'
                target_category = 'Company'
                # Reverse the relationship meaning
                relationship = self._reverse_relationship(rel['relationship'])
            else:
                source_id = rel['source_label']
                target_id = rel['target_label']
                source_category = rel['source_category']
                target_category = rel['target_category']
                relationship = rel['relationship']
            
            # Track entities
            if source_category == 'Person' and source_id not in persons:
                persons[source_id] = {
                    'id': source_id,
                    'label': source_id
                }
            
            if target_category == 'Person' and target_id not in persons:
                persons[target_id] = {
                    'id': target_id,
                    'label': target_id
                }
            
            if source_category == 'Company' and source_id not in companies:
                companies[source_id] = {
                    'id': source_id,
                    'label': source_id
                }
            
            if target_category == 'Company' and target_id not in companies:
                companies[target_id] = {
                    'id': target_id,
                    'label': target_id
                }
            
            # Track relationships with deduplication
            if source_category == 'Person' and target_category == 'Person':
                # Sort IDs alphabetically for deduplication
                sorted_ids = tuple(sorted([source_id, target_id]))
                person_to_person.add((sorted_ids[0], sorted_ids[1], relationship))
            elif source_category == 'Person' and target_category == 'Company':
                person_to_company.add((source_id, target_id, relationship))
            elif source_category == 'Company' and target_category == 'Company':
                # Sort IDs alphabetically for deduplication
                sorted_ids = tuple(sorted([source_id, target_id]))
                company_to_company.add((sorted_ids[0], sorted_ids[1], relationship))
        
        # Create CSV files
        self._write_entity_csv('person', persons)
        self._write_entity_csv('company', companies)
        self._write_relationship_csv('person_to_person', person_to_person, ['source_id', 'target_id', 'relationship'])
        self._write_relationship_csv('person_to_company', person_to_company, ['person_id', 'company_id', 'relationship'])
        self._write_relationship_csv('company_to_company', company_to_company, ['source_id', 'target_id', 'relationship'])
        
        console.print(f"[green]Created organized CSVs: {len(persons)} persons, {len(companies)} companies, {len(person_to_person)} person-to-person, {len(person_to_company)} person-to-company, {len(company_to_company)} company-to-company relationships[/green]")

    def _reverse_relationship(self, relationship: str) -> str:
        """Reverse the meaning of a relationship for reordering"""
        reverse_map = {
            'hires': 'works_at',
            'employs': 'works_at',
            'manages': 'reports_to',
            'supervises': 'reports_to',
            'leads': 'reports_to',
            'acquires': 'acquired_by',
            'purchases': 'purchased_by',
            'buys': 'sold_to'
        }
        return reverse_map.get(relationship, relationship)

    def _write_entity_csv(self, entity_type: str, entities: dict) -> None:
        """Write entity CSV file"""
        db_input_dir = self._get_cache_dir() / "db_input"
        csv_path = db_input_dir / f"{entity_type}.csv"
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['id', 'label'])
            for entity in entities.values():
                writer.writerow([entity['id'], entity['label']])
        
        console.print(f"[green]Created {csv_path}[/green]")

    def _write_relationship_csv(self, relationship_type: str, relationships: set, headers: list) -> None:
        """Write relationship CSV file"""
        db_input_dir = self._get_cache_dir() / "db_input"
        csv_path = db_input_dir / f"{relationship_type}.csv"
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for rel in sorted(relationships):
                writer.writerow(rel)
        
        console.print(f"[green]Created {csv_path}[/green]")

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        console.print(
            f"[cyan]KnowledgeMapTool._get_file_hash(file_path={file_path})[/cyan]"
        )
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def _get_file_stats(self, file_path: Path) -> Dict[str, Any]:
        """Get file creation and modification times"""
        console.print(
            f"[cyan]KnowledgeMapTool._get_file_stats(file_path={file_path})[/cyan]"
        )
        stat = file_path.stat()
        return {
            "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        }

    def _crawl_markdown_files(self, input_folder: Path) -> List[Path]:
        """Crawl directory for markdown files"""
        console.print(
            f"[cyan]KnowledgeMapTool._crawl_markdown_files(input_folder={input_folder})[/cyan]"
        )
        markdown_files = []
        for file_path in input_folder.rglob("*.md"):
            if file_path.is_file():
                markdown_files.append(file_path)
        return markdown_files

    def _parse_markdown(self, content: str) -> str:
        """Parse markdown content (basic implementation)"""
        console.print(
            f"[cyan]KnowledgeMapTool._parse_markdown(content_len={len(content)})[/cyan]"
        )
        # For now, just return the raw content
        # In a more sophisticated implementation, you might want to strip markdown syntax
        return content

    def _chunk_content(self, content: str) -> List[Dict[str, Any]]:
        """Split content into chunks using the configured chunking backend"""
        console.print(
            f"[cyan]KnowledgeMapTool._chunk_content(content_len={len(content)}, backend={self.chunking_backend})[/cyan]"
        )

        # Use the configured chunker to create chunks
        chunks = self.chunker.chunk(content)

        # Convert chonkie chunks to our format
        result_chunks = []
        for i, chunk in enumerate(chunks):
            result_chunks.append(
                {
                    "content": chunk.text,
                    "index": i,
                    "token_count": chunk.token_count,
                    "meta": {
                        "token_count": chunk.token_count,
                        "chunk_type": self.chunking_backend,
                    },
                }
            )

        console.print(f"[green]Created {len(result_chunks)} {self.chunking_backend} chunks[/green]")
        return result_chunks

    async def _extract_relationships(self, content: str) -> List[Relationship]:
        """Extract Person/Company relationships using LLM with structured outputs"""
        console.print(
            f"[cyan]KnowledgeMapTool._extract_relationships(content_len={len(content)})[/cyan]"
        )
        try:
            response = await self.openai_client.responses.parse(
                model="gpt-4o-mini",
                input=[
                    {
                        "role": "system",
                        "content": """You are an expert at extracting relationships between people and companies from text. 
                        Extract ONLY relationships between Person and Company entities.
                        Focus on direct, factual relationships like:
                        - Person works_at Company
                        - Person founded Company
                        - Person reports_to Person
                        - Company acquired Company
                        - Company collaborates_with Company
                        
                        Use one-word relationship types. Ignore concepts, locations, products, or events.
                        Return relationships in the specified structured format.""",
                    },
                    {
                        "role": "user",
                        "content": f"Extract Person and Company relationships from this text:\n\n{content}",
                    },
                ],
                text_format=RelationshipResponse,
            )

            # Access the structured output directly
            relationship_response = response.output_parsed
            return relationship_response.relationships

        except Exception as e:
            console.print(f"[red]Error extracting relationships: {e}[/red]")
            return []

    def _create_node(self, node_type: str, properties: Dict[str, Any]) -> None:
        """Create a node in the database"""
        console.print(
            f"[cyan]KnowledgeMapTool._create_node(node_type={node_type}, properties_keys={list(properties.keys())})[/cyan]"
        )
        # Print node properties for debugging
        console.print(f"[dim]Creating {node_type} node with properties:[/dim]")
        for key, value in properties.items():
            console.print(f"[dim]  {key}: {value}[/dim]")
        # Convert properties to Cypher format, using timestamp() function for datetime fields
        props_list = []
        converted_props = {}

        for k, v in properties.items():
            if isinstance(v, datetime):
                # Convert to ISO-8601 format with timezone info for Kuzu TIMESTAMP
                if v.tzinfo is None:
                    # If no timezone info, assume UTC
                    v = v.replace(tzinfo=timezone.utc)
                timestamp_str = v.isoformat()
                props_list.append(f"{k}: timestamp(${k}_str)")
                converted_props[f"{k}_str"] = timestamp_str
            else:
                props_list.append(f"{k}: ${k}")
                converted_props[k] = v

        props_str = ", ".join(props_list)
        query = f"CREATE (n:{node_type} {{{props_str}}})"

        self.conn.execute(query, converted_props)

    def _create_edge(
        self, edge_type: str, from_id: str, to_id: str, relationship: str = None
    ) -> None:
        """Create an edge in the database"""
        console.print(
            f"[cyan]KnowledgeMapTool._create_edge(edge_type={edge_type}, from_id={from_id}, to_id={to_id})[/cyan]"
        )
        
        if relationship:
            query = f"""
            MATCH (from), (to)
            WHERE from.id = $from_id AND to.id = $to_id
            CREATE (from)-[r:{edge_type} {{relationship: $relationship}}]->(to)
            """
            self.conn.execute(
                query, {"from_id": from_id, "to_id": to_id, "relationship": relationship}
            )
        else:
            query = f"""
            MATCH (from), (to)
            WHERE from.id = $from_id AND to.id = $to_id
            CREATE (from)-[r:{edge_type}]->(to)
            """
            self.conn.execute(
                query, {"from_id": from_id, "to_id": to_id}
            )

    def _delete_node(self, node_id: str) -> None:
        """Delete a node and all its relationships"""
        console.print(f"[cyan]KnowledgeMapTool._delete_node(node_id={node_id})[/cyan]")
        query = "MATCH (n) WHERE n.id = $node_id DETACH DELETE n"
        self.conn.execute(query, {"node_id": node_id})

    def _get_note(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get existing note node from database"""
        console.print(
            f"[cyan]KnowledgeMapTool._get_note(file_path={file_path})[/cyan]"
        )
        query = "MATCH (n:Note) WHERE n.url = $url RETURN n"
        result = self.conn.execute(query, {"url": file_path})

        if result.has_next():
            record = result.get_next()
            return {"id": record[0]["id"], "url": record[0]["url"]}
        return None

    def _delete_note(self, note: Dict[str, Any]) -> None:
        """Delete note and all related nodes"""
        console.print(
            f"[cyan]KnowledgeMapTool._delete_note(note_id={note['id']})[/cyan]"
        )
        # Delete the note node
        query = "MATCH (n:Note) WHERE n.id = $note_id DETACH DELETE n"
        self.conn.execute(query, {"note_id": note["id"]})

    async def _add_source(self, file_path: Path) -> None:
        """Add a source file to the knowledge map with simplified schema"""
        console.print(
            f"[cyan]KnowledgeMapTool._add_source(file_path={file_path})[/cyan]"
        )
        
        # Read file content
        content = file_path.read_text(encoding="utf-8")
        
        # Create Note node
        note_id = str(file_path)
        note_label = file_path.stem  # filename without extension
        
        self._create_node(
            "Note",
            {
                "id": note_id,
                "label": note_label,
                "url": str(file_path),
                "content": content,
            },
        )

        # Extract relationships if not skipping extraction
        if not self.skip_extraction:
            # Parse and chunk content
            parsed_content = self._parse_markdown(content)
            chunks = self._chunk_content(parsed_content)
            
            all_relationships = []
            
            # Process each chunk for relationships
            for chunk in chunks:
                relationships = await self._extract_relationships(chunk["content"])
                all_relationships.extend(relationships)
            
            # Save relationships to CSV and process them
            if all_relationships:
                csv_filename = self._save_relationships_to_csv(file_path, all_relationships)
                console.print(f"[green]Processed {file_path} -> {csv_filename}[/green]")
                
                # Process relationships into the database
                self._process_relationships(all_relationships)
            else:
                console.print(f"[yellow]No relationships found in {file_path}[/yellow]")
        else:
            console.print(f"[dim]Skipping relationship extraction for {file_path}[/dim]")

    async def process_folder(self, input_folder: Path, max_concurrent: int = 5) -> None:
        """Process a folder of markdown files"""
        console.print(
            f"[cyan]KnowledgeMapTool.process_folder(input_folder={input_folder}, max_concurrent={max_concurrent})[/cyan]"
        )
        markdown_files = self._crawl_markdown_files(input_folder)

        if not markdown_files:
            console.print(
                "[yellow]No markdown files found in the specified folder[/yellow]"
            )
            return

        console.print(f"[green]Found {len(markdown_files)} markdown files[/green]")

        # Process files with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_file(file_path: Path):
            async with semaphore:
                try:
                    content_hash = self._get_file_hash(file_path)
                    existing_csv = self._find_existing_csv(file_path, content_hash)
                    
                    if existing_csv:
                        console.print(f"[green]Using cached data for {file_path} -> {existing_csv.name}[/green]")
                        # Create Note node but skip LLM extraction
                        content = file_path.read_text(encoding="utf-8")
                        note_id = str(file_path)
                        note_label = file_path.stem
                        
                        self._create_node(
                            "Note",
                            {
                                "id": note_id,
                                "label": note_label,
                                "url": str(file_path),
                                "content": content,
                            },
                        )
                        
                        # Load and process relationships from the cached CSV
                        relationships = self._load_relationships_from_csv(existing_csv)
                        console.print(f"[green]Loaded {len(relationships)} relationships from cache[/green]")
                        self._process_relationships(relationships)
                    else:
                        note = self._get_note(str(file_path))
                        if note:
                            console.print(f"[yellow]Updating existing file: {file_path}[/yellow]")
                            self._delete_note(note)
                        else:
                            console.print(f"[blue]Processing new file: {file_path}[/blue]")

                        await self._add_source(file_path)
                        console.print(f"[green]✓ Processed: {file_path}[/green]")

                except Exception as e:
                    console.print(f"[red]Error processing {file_path}: {e}[/red]")

        # Process all files concurrently
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing files...", total=len(markdown_files))

            tasks = [process_file(file_path) for file_path in markdown_files]

            for coro in asyncio.as_completed(tasks):
                await coro
                progress.advance(task)

        console.print(
            f"[green]✓ Processing complete! Database saved to: {self.db_path}[/green]"
        )


@click.command()
@click.argument(
    "input_folder", type=click.Path(exists=True, file_okay=False, path_type=Path), 
    required=False, default=lambda: os.getenv("VAULT_PATH")
)
@click.option("--db-path", default="default.kz", help="Path to the Kuzu database file")
@click.option("--openai-api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
@click.option(
    "--max-concurrent",
    default=5,
    help="Maximum number of concurrent file processing tasks",
)
@click.option(
    "--skip-extraction",
    is_flag=True,
    help="Skip LLM-based knowledge extraction (only create chunks)",
)
@click.option(
    "--chunking-backend",
    type=click.Choice(["recursive-markdown", "semantic"]),
    default="recursive-markdown",
    help="Chunking backend to use: 'recursive-markdown' for structure-based chunking, 'semantic' for similarity-based chunking",
)
@click.option("--migrate-cache", is_flag=True, help="Migrate existing cache/content/*.csv to organized cache/db_input/ structure")
@click.option(
    "--chunk-threshold",
    default=0.75,
    help="Semantic similarity threshold for chunking (0.0-1.0, only used with semantic backend)",
)
@click.option(
    "--chunk-size",
    default=1024,
    help="Maximum chunk size in tokens (only used with semantic backend)",
)
@click.option(
    "--embedding-model",
    default="minishlab/potion-base-8M",
    help="Embedding model for semantic chunking (only used with semantic backend)",
)
@click.option(
    "--rebuild-from-cache",
    is_flag=True,
    help="Rebuild knowledge graph from CSV cache files",
)
@click.option(
    "--cache-status",
    is_flag=True,
    help="Show cache status and file information",
)
def main(
    input_folder: Path,
    db_path: str,
    openai_api_key: Optional[str],
    max_concurrent: int,
    skip_extraction: bool,
    chunking_backend: str,
    chunk_threshold: float,
    chunk_size: int,
    embedding_model: str,
    rebuild_from_cache: bool,
    cache_status: bool,
    migrate_cache: bool,
):
    """Knowledge Map Tool - Convert markdown files to a Kuzu knowledge graph with simplified schema"""

    # Handle cache status check
    if cache_status:
        cache_dir = Path("cache")
        if cache_dir.exists():
            csv_files = list(cache_dir.glob("*.csv"))
            console.print(f"[green]Cache Status: {len(csv_files)} CSV files found[/green]")
            for csv_file in csv_files:
                console.print(f"  - {csv_file.name}")
        else:
            console.print("[yellow]Cache directory not found[/yellow]")
        return

    # Handle rebuild from cache
    if rebuild_from_cache:
        try:
            tool = KnowledgeMapTool(
                db_path=db_path,
                openai_api_key=None,  # Not needed for rebuild
                skip_extraction=True,  # Skip extraction, just rebuild
                chunking_backend=chunking_backend,
                chunk_threshold=chunk_threshold,
                chunk_size=chunk_size,
                embedding_model=embedding_model,
            )
            tool._build_knowledge_graph_from_csvs()
            console.print(f"[green]✓ Knowledge graph rebuilt from cache! Database saved to: {db_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error rebuilding from cache: {e}[/red]")
            sys.exit(1)
        return

    # Handle cache migration
    if migrate_cache:
        try:
            tool = KnowledgeMapTool(
                db_path=db_path,
                openai_api_key=openai_api_key,
                skip_extraction=True,  # No need for extraction during migration
                chunking_backend=chunking_backend,
                chunk_threshold=chunk_threshold,
                chunk_size=chunk_size,
                embedding_model=embedding_model,
            )
            tool.migrate_cache_to_organized_structure()
        except Exception as e:
            console.print(f"[red]Error during migration: {e}[/red]")
            sys.exit(1)
        return

    # Require input_folder for normal processing
    if not input_folder:
        console.print("[red]Error: input_folder is required for normal processing[/red]")
        console.print("[yellow]Example: uv run main.py /path/to/vault[/yellow]")
        console.print("[yellow]Or set VAULT_PATH in your .env file[/yellow]")
        sys.exit(1)

    # Only require OpenAI API key if extraction is not skipped
    if not skip_extraction and not openai_api_key and not os.getenv("OPENAI_API_KEY"):
        console.print(
            "[red]Error: OpenAI API key required when extraction is enabled. Set OPENAI_API_KEY env var, use --openai-api-key, or use --skip-extraction[/red]"
        )
        sys.exit(1)

    try:
        tool = KnowledgeMapTool(
            db_path=db_path,
            openai_api_key=openai_api_key,
            skip_extraction=skip_extraction,
            chunking_backend=chunking_backend,
            chunk_threshold=chunk_threshold,
            chunk_size=chunk_size,
            embedding_model=embedding_model,
        )
        asyncio.run(tool.process_folder(input_folder, max_concurrent))
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
