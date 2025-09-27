#!/usr/bin/env python3
"""
Step 3: Build Kuzu database from cache/db_input/ CSV files
This step loads organized CSV files and creates the Kuzu knowledge graph.
"""

import csv
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

import click
import kuzu
from dotenv import load_dotenv
from rich.console import Console
from obsidian_config_reader import ObsidianConfigReader

# Load environment variables
load_dotenv()

console = Console()


class Step3Builder:
    def __init__(self, vault_path: Path, db_path: str):
        self.vault_path = vault_path
        self.db_path = db_path
        
        # Ensure parent directory exists
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        
        # Initialize Obsidian config reader for template folder exclusion
        self.obsidian_config = ObsidianConfigReader(vault_path)
        self.template_folder = self._get_template_folder()
        
        self._init_schema()
    
    def cleanup(self):
        """Clean up database connections"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                self.conn = None
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")
        
        try:
            if hasattr(self, 'db') and self.db:
                # Kuzu Database doesn't have a close method, but we can set it to None
                self.db = None
        except Exception as e:
            print(f"Warning: Error cleaning up database: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors in destructor
    
    def _get_template_folder(self) -> Optional[str]:
        """Get template folder path from Obsidian configuration"""
        if self.obsidian_config.is_templates_enabled():
            template_folder = self.obsidian_config.get_template_folder()
            if template_folder:
                console.print(f"[cyan]Templates enabled, excluding folder: {template_folder}[/cyan]")
            return template_folder
        return None

    def _init_schema(self) -> None:
        """Initialize the Kuzu database schema"""
        console.print("[cyan]Initializing Kuzu database schema...[/cyan]")
        
        # Create node tables
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Person(id STRING, label STRING, metadata STRING, PRIMARY KEY(id))")
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Company(id STRING, label STRING, metadata STRING, PRIMARY KEY(id))")
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Note(id STRING, label STRING, content STRING, PRIMARY KEY(id))")
        
        # Create relationship tables
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS PERSON_TO_PERSON(FROM Person TO Person, relationship STRING)")
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS PERSON_TO_COMPANY(FROM Person TO Company, relationship STRING)")
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS COMPANY_TO_COMPANY(FROM Company TO Company, relationship STRING)")
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS PERSON_REFERENCE(FROM Person TO Note)")
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS COMPANY_REFERENCE(FROM Company TO Note)")
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS NOTE_TO_NOTE(FROM Note TO Note)")
        
        console.print("[green]Database schema initialized[/green]")

    def _get_kineviz_dir(self) -> Path:
        """Get the .kineviz_graph directory path"""
        kineviz_dir = self.vault_path / ".kineviz_graph"
        kineviz_dir.mkdir(exist_ok=True)
        return kineviz_dir

    def _get_db_input_dir(self) -> Path:
        """Get the cache/db_input directory path"""
        return self._get_kineviz_dir() / "cache" / "db_input"

    def _entity_exists(self, table_name: str, entity_id: str) -> bool:
        """Check if an entity already exists in the database"""
        try:
            result = self.conn.execute(f"MATCH (n:{table_name}) WHERE n.id = $id RETURN n.id", {"id": entity_id})
            return len(list(result)) > 0
        except:
            return False

    def _create_node(self, table_name: str, properties: dict) -> None:
        """Create a node in the database"""
        try:
            if table_name == "Person":
                metadata = properties.get("metadata", "")
                self.conn.execute(
                    "CREATE (p:Person {id: $id, label: $label, metadata: $metadata})",
                    {"id": properties["id"], "label": properties["label"], "metadata": metadata}
                )
            elif table_name == "Company":
                metadata = properties.get("metadata", "")
                self.conn.execute(
                    "CREATE (c:Company {id: $id, label: $label, metadata: $metadata})",
                    {"id": properties["id"], "label": properties["label"], "metadata": metadata}
                )
            elif table_name == "Note":
                self.conn.execute(
                    "CREATE (n:Note {id: $id, label: $label, content: $content})",
                    {"id": properties["id"], "label": properties["label"], "content": properties["content"]}
                )
        except Exception as e:
            console.print(f"[red]Error creating {table_name} node: {e}[/red]")

    def _create_edge(self, relationship_type: str, source_id: str, target_id: str, relationship: str = None) -> None:
        """Create an edge in the database"""
        try:
            if relationship_type == "PERSON_TO_PERSON":
                self.conn.execute(
                    "MATCH (p1:Person {id: $source_id}), (p2:Person {id: $target_id}) CREATE (p1)-[r:PERSON_TO_PERSON {relationship: $relationship}]->(p2)",
                    {"source_id": source_id, "target_id": target_id, "relationship": relationship}
                )
            elif relationship_type == "PERSON_TO_COMPANY":
                self.conn.execute(
                    "MATCH (p:Person {id: $source_id}), (c:Company {id: $target_id}) CREATE (p)-[r:PERSON_TO_COMPANY {relationship: $relationship}]->(c)",
                    {"source_id": source_id, "target_id": target_id, "relationship": relationship}
                )
            elif relationship_type == "COMPANY_TO_COMPANY":
                self.conn.execute(
                    "MATCH (c1:Company {id: $source_id}), (c2:Company {id: $target_id}) CREATE (c1)-[r:COMPANY_TO_COMPANY {relationship: $relationship}]->(c2)",
                    {"source_id": source_id, "target_id": target_id, "relationship": relationship}
                )
            elif relationship_type == "PERSON_REFERENCE":
                self.conn.execute(
                    "MATCH (p:Person {id: $source_id}), (n:Note {id: $target_id}) CREATE (p)-[r:PERSON_REFERENCE]->(n)",
                    {"source_id": source_id, "target_id": target_id}
                )
            elif relationship_type == "COMPANY_REFERENCE":
                self.conn.execute(
                    "MATCH (c:Company {id: $source_id}), (n:Note {id: $target_id}) CREATE (c)-[r:COMPANY_REFERENCE]->(n)",
                    {"source_id": source_id, "target_id": target_id}
                )
            elif relationship_type == "NOTE_TO_NOTE":
                self.conn.execute(
                    "MATCH (n1:Note {id: $source_id}), (n2:Note {id: $target_id}) CREATE (n1)-[r:NOTE_TO_NOTE]->(n2)",
                    {"source_id": source_id, "target_id": target_id}
                )
        except Exception as e:
            console.print(f"[red]Error creating {relationship_type} edge: {e}[/red]")

    def _create_bulk_reference_edges(self, relationship_type: str, references: List[Tuple[str, str]], batch_size: int = 1000) -> None:
        """
        Create reference edges in bulk for better performance.
        
        Args:
            relationship_type: Type of relationship (PERSON_REFERENCE or COMPANY_REFERENCE)
            references: List of (entity_id, note_id) tuples
            batch_size: Number of edges to process in each batch
        """
        if not references:
            return
        
        console.print(f"[cyan]    → Creating {len(references)} {relationship_type} edges in batches of {batch_size}...[/cyan]")
        
        # Process in batches to avoid memory issues and improve performance
        total_created = 0
        batch_count = 0
        
        for i in range(0, len(references), batch_size):
            batch = references[i:i + batch_size]
            batch_count += 1
            
            try:
                # Create batch query for bulk insertion
                if relationship_type == "PERSON_REFERENCE":
                    # Use UNWIND to create multiple edges in one query
                    query = """
                    UNWIND $batch AS ref
                    MATCH (p:Person {id: ref.entity_id}), (n:Note {id: ref.note_id})
                    CREATE (p)-[r:PERSON_REFERENCE]->(n)
                    """
                elif relationship_type == "COMPANY_REFERENCE":
                    query = """
                    UNWIND $batch AS ref
                    MATCH (c:Company {id: ref.entity_id}), (n:Note {id: ref.note_id})
                    CREATE (c)-[r:COMPANY_REFERENCE]->(n)
                    """
                else:
                    console.print(f"[red]Unknown relationship type: {relationship_type}[/red]")
                    continue
                
                # Prepare batch data
                batch_data = [{"entity_id": entity_id, "note_id": note_id} for entity_id, note_id in batch]
                
                # Execute batch query
                self.conn.execute(query, {"batch": batch_data})
                total_created += len(batch)
                
                # Show progress for large batches
                if len(references) > 1000 and batch_count % 10 == 0:
                    progress = (i + len(batch)) / len(references) * 100
                    console.print(f"[cyan]      Progress: {progress:.1f}% ({total_created}/{len(references)})[/cyan]")
                
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to create batch {batch_count}: {e}[/yellow]")
                # Continue with next batch instead of failing completely
                continue
        
        console.print(f"[green]    ✓ Created {total_created} {relationship_type} edges in {batch_count} batches[/green]")

    def _load_entities_from_csv(self, entity_type: str) -> List[dict]:
        """Load entities from CSV file"""
        entities = []
        csv_path = self._get_db_input_dir() / f"{entity_type}.csv"
        
        if not csv_path.exists():
            console.print(f"[yellow]No {entity_type}.csv file found[/yellow]")
            return entities
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    entities.append(row)
        except Exception as e:
            console.print(f"[red]Error loading {entity_type}.csv: {e}[/red]")
        
        return entities

    def _load_relationships_from_csv(self, relationship_type: str) -> List[dict]:
        """Load relationships from CSV file"""
        relationships = []
        csv_path = self._get_db_input_dir() / f"{relationship_type}.csv"
        
        if not csv_path.exists():
            console.print(f"[yellow]No {relationship_type}.csv file found[/yellow]")
            return relationships
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    relationships.append(row)
        except Exception as e:
            console.print(f"[red]Error loading {relationship_type}.csv: {e}[/red]")
        
        return relationships

    def _load_relationships_from_content_csv(self, csv_path: Path) -> List[dict]:
        """Load relationships from content CSV file"""
        relationships = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    relationships.append(row)
        except Exception as e:
            console.print(f"[yellow]Could not load {csv_path}: {e}[/yellow]")
        
        return relationships

    def _extract_obsidian_links(self, content: str) -> List[str]:
        """Extract Obsidian-style [[link]] patterns from markdown content"""
        # Pattern to match [[link]] or [[link|display text]]
        pattern = r'\[\[([^|\]]+)(?:\|[^\]]+)?\]\]'
        matches = re.findall(pattern, content)
        return [match.strip() for match in matches]

    def _create_note_to_note_relationships(self, notes: List[dict]) -> None:
        """Create NOTE_TO_NOTE relationships from Obsidian links"""
        console.print("[cyan]Creating Note-to-Note relationships from Obsidian links...[/cyan]")
        
        # Create a mapping from note labels to note IDs
        label_to_id = {}
        for note in notes:
            label_to_id[note['label']] = note['id']
        
        # Track created relationships to avoid duplicates
        created_relationships = set()
        relationship_count = 0
        
        for note in notes:
            note_id = note['id']
            note_content = note['content']
            
            # Extract Obsidian links from this note's content
            obsidian_links = self._extract_obsidian_links(note_content)
            
            for link_label in obsidian_links:
                # Try to find the target note by label
                if link_label in label_to_id:
                    target_note_id = label_to_id[link_label]
                    
                    # Create relationship if not already created
                    rel_key = tuple(sorted([note_id, target_note_id]))
                    if rel_key not in created_relationships:
                        self._create_edge("NOTE_TO_NOTE", note_id, target_note_id)
                        created_relationships.add(rel_key)
                        relationship_count += 1
                        console.print(f"[green]Linked: {note['label']} -> {link_label}[/green]")
                else:
                    # Link to non-existent note (broken link)
                    console.print(f"[yellow]Broken link: {note['label']} -> [[{link_label}]] (note not found)[/yellow]")
        
        console.print(f"[green]Created {relationship_count} Note-to-Note relationships[/green]")

    def _create_note_nodes(self) -> List[dict]:
        """Create Note nodes from all markdown files in the vault"""
        console.print("[cyan]Creating Note nodes...[/cyan]")
        
        # Get all markdown files in the vault
        source_files = set()
        for md_file in self.vault_path.rglob("*.md"):
            # Skip hidden directories
            if any(part.startswith('.') for part in md_file.relative_to(self.vault_path).parts):
                continue
            
            # Skip files in template folder if templates are enabled
            if self.template_folder:
                try:
                    relative_path = md_file.relative_to(self.vault_path)
                    if str(relative_path).startswith(self.template_folder + "/"):
                        console.print(f"[yellow]Skipping template file: {relative_path}[/yellow]")
                        continue
                except ValueError:
                    # File is not relative to vault path, skip it
                    continue
            
            source_files.add(str(md_file))
        
        console.print(f"[cyan]Found {len(source_files)} markdown files in vault[/cyan]")
        
        # Create Note nodes for each source file
        for source_file in source_files:
            # Create note ID from file path
            note_id = source_file
            # Create label from filename (without extension)
            note_label = Path(source_file).stem
            
            # Try to read the actual content of the markdown file
            try:
                if Path(source_file).exists():
                    note_content = Path(source_file).read_text(encoding='utf-8')
                else:
                    note_content = f"Source: {source_file}"
            except Exception as e:
                console.print(f"[yellow]Could not read {source_file}: {e}[/yellow]")
                note_content = f"Source: {source_file}"
            
            if not self._entity_exists("Note", note_id):
                self._create_node("Note", {
                    "id": note_id,
                    "label": note_label,
                    "content": note_content
                })
                console.print(f"[green]Created Note: {note_label}[/green]")
        
        if not source_files:
            # Fallback: create a placeholder note
            note_id = "placeholder_note"
            note_label = "Knowledge Base"
            note_content = "Generated from markdown files"
            
            if not self._entity_exists("Note", note_id):
                self._create_node("Note", {
                    "id": note_id,
                    "label": note_label,
                    "content": note_content
                })
                console.print(f"[green]Created Note: {note_label}[/green]")
        
        # Return list of created notes for relationship creation
        notes = []
        for source_file in source_files:
            note_id = source_file
            note_label = Path(source_file).stem
            try:
                if Path(source_file).exists():
                    note_content = Path(source_file).read_text(encoding='utf-8')
                else:
                    note_content = f"Source: {source_file}"
            except Exception as e:
                note_content = f"Source: {source_file}"
            
            notes.append({
                "id": note_id,
                "label": note_label,
                "content": note_content
            })
        
        return notes

    def build_database(self) -> None:
        """Build the Kuzu database from organized CSV files using COPY FROM for efficiency"""
        import time
        
        console.print("[cyan]Building Kuzu database from cache/db_input/...[/cyan]")
        total_start_time = time.time()
        step_times = {}  # Track individual step times
        
        # Step 1: Clear existing database
        step_start = time.time()
        console.print("[cyan]Step 1: Clearing existing database...[/cyan]")
        if Path(self.db_path).exists():
            import shutil
            if Path(self.db_path).is_dir():
                shutil.rmtree(self.db_path)
            else:
                Path(self.db_path).unlink()
            console.print("[yellow]Cleared existing database[/yellow]")
        step_times['clear'] = time.time() - step_start
        console.print(f"[green]✓ Step 1 completed in {step_times['clear']:.2f}s[/green]")
        
        # Step 2: Initialize database and schema
        step_start = time.time()
        console.print("[cyan]Step 2: Initializing database and schema...[/cyan]")
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()
        step_times['init'] = time.time() - step_start
        console.print(f"[green]✓ Step 2 completed in {step_times['init']:.2f}s[/green]")
        
        db_input_dir = self._get_db_input_dir()
        
        # Step 3: Import nodes using COPY FROM
        step_start = time.time()
        console.print("[cyan]Step 3: Importing nodes using COPY FROM...[/cyan]")
        
        # Import Person nodes
        person_csv = db_input_dir / "person.csv"
        if person_csv.exists():
            console.print("[cyan]  → Importing Person nodes...[/cyan]")
            person_start = time.time()
            self.conn.execute(f'COPY Person FROM "{person_csv}" (HEADER=true)')
            # Count imported persons
            result = self.conn.execute("MATCH (p:Person) RETURN count(p) as count")
            person_count = list(result)[0][0]
            person_time = time.time() - person_start
            console.print(f"[green]  ✓ Imported {person_count} Person nodes in {person_time:.2f}s[/green]")
        else:
            console.print("[yellow]  ⚠ Person CSV not found, skipping...[/yellow]")
        
        # Import Company nodes
        company_csv = db_input_dir / "company.csv"
        if company_csv.exists():
            console.print("[cyan]  → Importing Company nodes...[/cyan]")
            company_start = time.time()
            self.conn.execute(f'COPY Company FROM "{company_csv}" (HEADER=true)')
            # Count imported companies
            result = self.conn.execute("MATCH (c:Company) RETURN count(c) as count")
            company_count = list(result)[0][0]
            company_time = time.time() - company_start
            console.print(f"[green]  ✓ Imported {company_count} Company nodes in {company_time:.2f}s[/green]")
        else:
            console.print("[yellow]  ⚠ Company CSV not found, skipping...[/yellow]")
        
        step_times['nodes'] = time.time() - step_start
        console.print(f"[green]✓ Step 3 completed in {step_times['nodes']:.2f}s[/green]")
        
        # Step 4: Create Note nodes
        step_start = time.time()
        console.print("[cyan]Step 4: Creating Note nodes...[/cyan]")
        notes = self._create_note_nodes()
        console.print(f"[green]  ✓ Created {len(notes)} Note nodes[/green]")
        
        # Create Note-to-Note relationships from Obsidian links
        if notes:
            console.print("[cyan]  → Creating Note-to-Note relationships...[/cyan]")
            note_rel_start = time.time()
            self._create_note_to_note_relationships(notes)
            note_rel_time = time.time() - note_rel_start
            console.print(f"[green]  ✓ Note relationships created in {note_rel_time:.2f}s[/green]")
        
        step_times['notes'] = time.time() - step_start
        console.print(f"[green]✓ Step 4 completed in {step_times['notes']:.2f}s[/green]")
        
        # Step 5: Import relationships using COPY FROM
        step_start = time.time()
        console.print("[cyan]Step 5: Importing relationships using COPY FROM...[/cyan]")
        
        # Import Person to Person relationships
        person_to_person_csv = db_input_dir / "person_to_person.csv"
        if person_to_person_csv.exists():
            console.print("[cyan]  → Importing Person-to-Person relationships...[/cyan]")
            p2p_start = time.time()
            self.conn.execute(f'COPY PERSON_TO_PERSON FROM "{person_to_person_csv}" (HEADER=true)')
            # Count imported relationships
            result = self.conn.execute("MATCH ()-[r:PERSON_TO_PERSON]->() RETURN count(r) as count")
            rel_count = list(result)[0][0]
            p2p_time = time.time() - p2p_start
            console.print(f"[green]  ✓ Imported {rel_count} Person-to-Person relationships in {p2p_time:.2f}s[/green]")
        else:
            console.print("[yellow]  ⚠ Person-to-Person CSV not found, skipping...[/yellow]")
        
        # Import Person to Company relationships
        person_to_company_csv = db_input_dir / "person_to_company.csv"
        if person_to_company_csv.exists():
            console.print("[cyan]  → Importing Person-to-Company relationships...[/cyan]")
            p2c_start = time.time()
            self.conn.execute(f'COPY PERSON_TO_COMPANY FROM "{person_to_company_csv}" (HEADER=true)')
            # Count imported relationships
            result = self.conn.execute("MATCH ()-[r:PERSON_TO_COMPANY]->() RETURN count(r) as count")
            rel_count = list(result)[0][0]
            p2c_time = time.time() - p2c_start
            console.print(f"[green]  ✓ Imported {rel_count} Person-to-Company relationships in {p2c_time:.2f}s[/green]")
        else:
            console.print("[yellow]  ⚠ Person-to-Company CSV not found, skipping...[/yellow]")
        
        # Import Company to Company relationships
        company_to_company_csv = db_input_dir / "company_to_company.csv"
        if company_to_company_csv.exists():
            console.print("[cyan]  → Importing Company-to-Company relationships...[/cyan]")
            c2c_start = time.time()
            self.conn.execute(f'COPY COMPANY_TO_COMPANY FROM "{company_to_company_csv}" (HEADER=true)')
            # Count imported relationships
            result = self.conn.execute("MATCH ()-[r:COMPANY_TO_COMPANY]->() RETURN count(r) as count")
            rel_count = list(result)[0][0]
            c2c_time = time.time() - c2c_start
            console.print(f"[green]  ✓ Imported {rel_count} Company-to-Company relationships in {c2c_time:.2f}s[/green]")
        else:
            console.print("[yellow]  ⚠ Company-to-Company CSV not found, skipping...[/yellow]")
        
        step_times['relationships'] = time.time() - step_start
        console.print(f"[green]✓ Step 5 completed in {step_times['relationships']:.2f}s[/green]")
        
        # Step 6: Create reference edges from entities to their source Note nodes (OPTIMIZED)
        step_start = time.time()
        console.print("[cyan]Step 6: Creating reference edges (optimized)...[/cyan]")
        
        content_dir = self._get_kineviz_dir() / "cache" / "content"
        
        if not content_dir.exists():
            console.print("[yellow]  ⚠ Content directory not found, skipping reference edges...[/yellow]")
            step_times['references'] = time.time() - step_start
            console.print(f"[green]✓ Step 6 completed in {step_times['references']:.2f}s[/green]")
            return
        
        # Collect all reference edges in memory for bulk processing
        console.print("[cyan]  → Collecting reference edge data...[/cyan]")
        collect_start = time.time()
        
        person_references = []  # List of (person_id, note_id) tuples
        company_references = []  # List of (company_id, note_id) tuples
        reference_count = 0
        
        # Process all CSV files and collect reference edges
        csv_files = list(content_dir.glob("*.csv"))
        console.print(f"[cyan]  → Processing {len(csv_files)} content files...[/cyan]")
        
        for csv_file in csv_files:
            relationships = self._load_relationships_from_content_csv(csv_file)
            for rel in relationships:
                if 'source_file' in rel and rel['source_file']:
                    source_file = rel['source_file']
                    
                    # Convert relative path to absolute path for Note ID lookup
                    if not Path(source_file).is_absolute():
                        note_id = str(self.vault_path / source_file)
                    else:
                        note_id = source_file
                    
                    # Collect source entity references
                    if rel['source_category'] == 'Person':
                        person_references.append((rel['source_label'], note_id))
                        reference_count += 1
                    elif rel['source_category'] == 'Company':
                        company_references.append((rel['source_label'], note_id))
                        reference_count += 1
                    
                    # Collect target entity references
                    if rel['target_category'] == 'Person':
                        person_references.append((rel['target_label'], note_id))
                        reference_count += 1
                    elif rel['target_category'] == 'Company':
                        company_references.append((rel['target_label'], note_id))
                        reference_count += 1
        
        collect_time = time.time() - collect_start
        console.print(f"[green]  ✓ Collected {reference_count} reference edges in {collect_time:.2f}s[/green]")
        console.print(f"[cyan]    - Person references: {len(person_references)}[/cyan]")
        console.print(f"[cyan]    - Company references: {len(company_references)}[/cyan]")
        
        # Create reference edges in bulk
        console.print("[cyan]  → Creating reference edges in bulk...[/cyan]")
        bulk_start = time.time()
        
        # Process Person references in batches
        if person_references:
            self._create_bulk_reference_edges("PERSON_REFERENCE", person_references)
        
        # Process Company references in batches  
        if company_references:
            self._create_bulk_reference_edges("COMPANY_REFERENCE", company_references)
        
        bulk_time = time.time() - bulk_start
        console.print(f"[green]  ✓ Created {reference_count} reference edges in {bulk_time:.2f}s[/green]")
        
        step_times['references'] = time.time() - step_start
        console.print(f"[green]✓ Step 6 completed in {step_times['references']:.2f}s[/green]")
        
        # Final summary
        total_time = time.time() - total_start_time
        console.print(f"\n[green]🎉 Database build completed successfully in {total_time:.2f}s![/green]")
        console.print("[cyan]Summary of steps:[/cyan]")
        console.print(f"  • Step 1: Clear database - {step_times['clear']:.2f}s")
        console.print(f"  • Step 2: Initialize schema - {step_times['init']:.2f}s") 
        console.print(f"  • Step 3: Import nodes - {step_times['nodes']:.2f}s")
        console.print(f"  • Step 4: Create Note nodes - {step_times['notes']:.2f}s")
        console.print(f"  • Step 5: Import relationships - {step_times['relationships']:.2f}s")
        console.print(f"  • Step 6: Create reference edges - {step_times['references']:.2f}s")
        console.print(f"  • Total time: {total_time:.2f}s")
        
        # Identify slowest step
        slowest_step = max(step_times.items(), key=lambda x: x[1])
        console.print(f"[yellow]Slowest step: {slowest_step[0]} ({slowest_step[1]:.2f}s)[/yellow]")

    def query_database(self, query: str) -> None:
        """Execute a query on the database and display results"""
        try:
            result = self.conn.execute(query)
            console.print(f"[cyan]Query: {query}[/cyan]")
            console.print("[cyan]Results:[/cyan]")
            for record in result:
                console.print(record)
        except Exception as e:
            console.print(f"[red]Error executing query: {e}[/red]")


@click.command()
@click.option("--vault-path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
              default=lambda: os.getenv("VAULT_PATH"), 
              help="Path to Obsidian vault (default: VAULT_PATH env var)")
@click.option("--db-path", help="Path to the Kuzu database file (default: .kineviz_graph/database/knowledge_graph.kz)")
@click.option("--query", help="Execute a specific query on the database")
def main(vault_path: Path, db_path: Optional[str], query: Optional[str]):
    """Step 3: Build Kuzu database from organized CSV files"""
    
    # Validate vault path
    if not vault_path:
        console.print("[red]Error: Vault path is required. Set VAULT_PATH environment variable or use --vault-path[/red]")
        console.print("[yellow]Example: uv run step3_build.py --vault-path '/path/to/vault'[/yellow]")
        console.print("[yellow]Or set VAULT_PATH in your .env file[/yellow]")
        sys.exit(1)
    
    # Set default database path if not provided
    if not db_path:
        db_path = str(vault_path / ".kineviz_graph" / "database" / "knowledge_graph.kz")
    
    try:
        builder = Step3Builder(vault_path, db_path)
        
        if query:
            builder.query_database(query)
        else:
            builder.build_database()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
