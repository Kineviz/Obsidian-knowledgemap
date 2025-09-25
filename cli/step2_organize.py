#!/usr/bin/env python3
"""
Step 2: Organize cache/content/*.csv files to cache/db_input/ structure
This step converts individual CSV files to organized entity and relationship CSVs.
"""

import csv
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict

import click
from dotenv import load_dotenv
from rich.console import Console

# Load environment variables
load_dotenv()

console = Console()


class Step2Organizer:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        # Import entity resolver for resolution mappings
        try:
            from entity_resolution import EntityResolver
            self.entity_resolver = EntityResolver(vault_path)
        except ImportError:
            self.entity_resolver = None

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

    def _get_db_input_dir(self) -> Path:
        """Get the cache/db_input directory path"""
        db_input_dir = self._get_cache_dir() / "db_input"
        db_input_dir.mkdir(exist_ok=True)
        return db_input_dir

    def _get_entity_resolution_mappings(self) -> Dict[str, str]:
        """Get all entity resolution mappings from all files"""
        if not self.entity_resolver:
            return {}
        
        try:
            file_mappings = self.entity_resolver.detect_rename_patterns()
            # Flatten all mappings into a single dictionary
            all_mappings = {}
            for file_path, mappings in file_mappings.items():
                all_mappings.update(mappings)
            return all_mappings
        except Exception as e:
            console.print(f"[yellow]Warning: Could not get entity resolution mappings: {e}[/yellow]")
            return {}

    def _apply_entity_resolution(self, entity_name: str, mappings: Dict[str, str]) -> str:
        """Apply entity resolution to an entity name"""
        return mappings.get(entity_name, entity_name)

    def _load_relationships_from_csv(self, csv_path: Path) -> List[dict]:
        """Load relationships from a CSV file"""
        relationships = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    relationships.append(row)
        except Exception as e:
            console.print(f"[red]Error loading CSV {csv_path}: {e}[/red]")
        return relationships

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
        db_input_dir = self._get_db_input_dir()
        csv_path = db_input_dir / f"{entity_type}.csv"
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['id', 'label', 'metadata'])
            for entity in entities.values():
                metadata = entity.get('metadata', '')
                writer.writerow([entity['id'], entity['label'], metadata])
        
        console.print(f"[green]Created {csv_path}[/green]")

    def _write_relationship_csv(self, relationship_type: str, relationships: set, headers: list) -> None:
        """Write relationship CSV file"""
        db_input_dir = self._get_db_input_dir()
        csv_path = db_input_dir / f"{relationship_type}.csv"
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for rel in sorted(relationships):
                writer.writerow(rel)
        
        console.print(f"[green]Created {csv_path}[/green]")

    def _create_organized_csvs_from_relationships(self, relationships: List[dict]) -> None:
        """Create organized CSV files from relationships"""
        console.print("[cyan]Creating organized CSV files...[/cyan]")
        
        # Get entity resolution mappings
        resolution_mappings = self._get_entity_resolution_mappings()
        if resolution_mappings:
            console.print(f"[cyan]Applying entity resolution for {len(resolution_mappings)} mappings[/cyan]")
        
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
                source_id = self._apply_entity_resolution(rel['target_label'], resolution_mappings)
                target_id = self._apply_entity_resolution(rel['source_label'], resolution_mappings)
                source_category = 'Person'
                target_category = 'Company'
                # Reverse the relationship meaning
                relationship = self._reverse_relationship(rel['relationship'])
            else:
                source_id = self._apply_entity_resolution(rel['source_label'], resolution_mappings)
                target_id = self._apply_entity_resolution(rel['target_label'], resolution_mappings)
                source_category = rel['source_category']
                target_category = rel['target_category']
                relationship = rel['relationship']
            
            # Track entities (always track, even for self-referential relationships)
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
            
            # Skip self-referential relationships (where source and target are the same)
            if source_id == target_id:
                continue
            
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

    def organize_cache(self) -> None:
        """Organize cache/content/*.csv files to cache/db_input/ structure"""
        console.print("[cyan]Starting organization from cache/content/ to cache/db_input/[/cyan]")
        
        # Load all relationships from content CSV files
        all_relationships = []
        content_csv_files = list(self._get_content_dir().glob("*.csv"))
        
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
        
        console.print("[green]Step 2 completed: Cache organized to cache/db_input/[/green]")


@click.command()
@click.option("--vault-path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
              default=lambda: os.getenv("VAULT_PATH"), 
              help="Path to Obsidian vault (default: VAULT_PATH env var)")
def main(vault_path: Path):
    """Step 2: Organize cache/content/*.csv files to cache/db_input/ structure"""
    
    # Validate vault path
    if not vault_path:
        console.print("[red]Error: Vault path is required. Set VAULT_PATH environment variable or use --vault-path[/red]")
        console.print("[yellow]Example: uv run step2_organize.py --vault-path '/path/to/vault'[/yellow]")
        console.print("[yellow]Or set VAULT_PATH in your .env file[/yellow]")
        sys.exit(1)
    
    try:
        organizer = Step2Organizer(vault_path)
        organizer.organize_cache()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
