#!/usr/bin/env python3
"""
Metadata Extractor Module

This module extracts metadata from markdown files that are linked to Person/Company nodes
and have identical names (case insensitive). The metadata is stored as JSON in the graph nodes.

Usage:
    from metadata_extractor import MetadataExtractor
    
    extractor = MetadataExtractor(vault_path)
    metadata = extractor.extract_metadata_for_nodes()
    extractor.update_database_with_metadata(metadata)
"""

import re
import yaml
import json
import csv
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from rich.console import Console
from rich.progress import Progress, TaskID

console = Console()


class MetadataExtractor:
    """Handles metadata extraction from linked markdown files."""
    
    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.content_dir = self.vault_path / ".kineviz_graph" / "cache" / "content"
        self.db_input_dir = self.vault_path / ".kineviz_graph" / "cache" / "db_input"
        self.database_dir = self.vault_path / ".kineviz_graph" / "database"
        
        # Ensure directories exist
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.db_input_dir.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for markdown files to avoid repeated scanning
        self._cached_markdown_files = None
        self._file_cache_timestamp = 0
    
    def extract_metadata_for_nodes(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract metadata for all Person and Company nodes.
        
        Returns:
            Dictionary mapping node_id to metadata: {node_id: metadata_dict}
        """
        console.print("[cyan]Extracting metadata for nodes...[/cyan]")
        
        # Get all Person and Company nodes from the database
        nodes = self._get_person_company_nodes()
        
        if not nodes:
            console.print("[yellow]No Person or Company nodes found[/yellow]")
            return {}
        
        metadata_results = {}
        
        with Progress() as progress:
            task = progress.add_task("Processing nodes...", total=len(nodes))
            
            for node_id, node_label, node_type in nodes:
                try:
                    # Find linked files for this node
                    linked_files = self._find_linked_files(node_id)
                    
                    if not linked_files:
                        progress.advance(task)
                        continue
                    
                    # Find matching file (same name, case insensitive)
                    matching_file = self._find_matching_linked_file(node_label, linked_files)
                    
                    if matching_file:
                        # Extract metadata from the matching file
                        metadata = self.extract_metadata_from_file(matching_file)
                        if metadata:
                            metadata_results[node_id] = {
                                'label': node_label,
                                'type': node_type,
                                'file': str(matching_file),
                                'metadata': metadata
                            }
                            console.print(f"[green]Extracted metadata for {node_label} from {matching_file.name}[/green]")
                    else:
                        console.print(f"[yellow]No matching file found for {node_label}[/yellow]")
                
                except Exception as e:
                    console.print(f"[red]Error processing node {node_id}: {e}[/red]")
                
                progress.advance(task)
        
        console.print(f"[green]Extracted metadata for {len(metadata_results)} nodes[/green]")
        return metadata_results
    
    def _get_person_company_nodes(self) -> List[Tuple[str, str, str]]:
        """
        Get all Person and Company nodes from the organized CSV files.
        
        Returns:
            List of (node_id, label, type) tuples
        """
        nodes = []
        
        # Read person.csv
        person_file = self.db_input_dir / "person.csv"
        if person_file.exists():
            with open(person_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'id' in row and 'label' in row:
                        nodes.append((row['id'], row['label'], 'Person'))
        
        # Read company.csv
        company_file = self.db_input_dir / "company.csv"
        if company_file.exists():
            with open(company_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'id' in row and 'label' in row:
                        nodes.append((row['id'], row['label'], 'Company'))
        
        return nodes
    
    def _get_cached_markdown_files(self) -> List[Path]:
        """
        Get all markdown files in the vault with caching to avoid repeated scanning.
        
        Returns:
            List of markdown file paths
        """
        import time
        
        current_time = time.time()
        
        # Return cached files if they exist and are recent (within 5 minutes)
        if (self._cached_markdown_files is not None and 
            current_time - self._file_cache_timestamp < 300):
            return self._cached_markdown_files
        
        # Scan for markdown files (only once)
        console.print("[cyan]Scanning vault for markdown files...[/cyan]")
        start_time = time.time()
        
        markdown_files = []
        for md_file in self.vault_path.rglob("*.md"):
            # Skip hidden files and directories
            if any(part.startswith('.') for part in md_file.parts):
                continue
            markdown_files.append(md_file)
        
        # Cache the results
        self._cached_markdown_files = markdown_files
        self._file_cache_timestamp = current_time
        
        scan_time = time.time() - start_time
        console.print(f"[green]Found {len(markdown_files)} markdown files in {scan_time:.2f}s[/green]")
        
        return markdown_files
    
    def clear_file_cache(self):
        """Clear the cached markdown files to force a fresh scan on next access."""
        self._cached_markdown_files = None
        self._file_cache_timestamp = 0
        console.print("[yellow]File cache cleared, will rescan on next access[/yellow]")
    
    def _find_linked_files(self, node_id: str) -> List[Path]:
        """
        Find markdown files linked to a specific node.
        This is a simplified implementation - in practice, you'd query the graph database.
        
        Args:
            node_id: ID of the node
            
        Returns:
            List of linked markdown file paths
        """
        # Use cached markdown files instead of scanning every time
        # This dramatically improves performance, especially in Docker mode
        return self._get_cached_markdown_files()
    
    def _find_matching_linked_file(self, node_label: str, linked_files: List[Path]) -> Optional[Path]:
        """
        Find linked file with identical name to node label (case insensitive).
        
        Args:
            node_label: Label of the node
            linked_files: List of linked markdown files
            
        Returns:
            Path to matching file, or None if not found
        """
        # Convert to lowercase once for comparison
        node_label_lower = node_label.lower()
        
        for file_path in linked_files:
            # Get filename without extension and convert to lowercase once
            file_name_lower = file_path.stem.lower()
            
            # Case insensitive comparison
            if file_name_lower == node_label_lower:
                return file_path
        
        return None
    
    def extract_metadata_from_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from a markdown file.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            Dictionary of extracted metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = {}
            
            # Extract YAML frontmatter
            frontmatter_metadata = self._extract_yaml_frontmatter(content)
            metadata.update(frontmatter_metadata)
            
            # Extract metadata sections
            section_metadata = self._extract_metadata_sections(content)
            metadata.update(section_metadata)
            
            # Extract key-value pairs
            kv_metadata = self._extract_key_value_pairs(content)
            metadata.update(kv_metadata)
            
            # Normalize and clean metadata
            metadata = self._normalize_metadata(metadata)
            
            return metadata
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract metadata from {file_path.name}: {e}[/yellow]")
            return {}
    
    def _extract_yaml_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from markdown content."""
        metadata = {}
        
        if not content.startswith('---'):
            return metadata
        
        try:
            # Find the end of frontmatter
            end_marker = content.find('---', 3)
            if end_marker == -1:
                return metadata
            
            frontmatter_text = content[3:end_marker].strip()
            frontmatter = yaml.safe_load(frontmatter_text)
            
            if frontmatter and isinstance(frontmatter, dict):
                # Exclude entity resolution and other system fields
                excluded_fields = {'resolves', 'entity_resolution'}
                for key, value in frontmatter.items():
                    if key not in excluded_fields and value is not None:
                        metadata[key] = value
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse YAML frontmatter: {e}[/yellow]")
        
        return metadata
    
    def _extract_metadata_sections(self, content: str) -> Dict[str, Any]:
        """Extract metadata from ## Metadata sections."""
        metadata = {}
        
        # Look for metadata sections
        metadata_sections = [
            r'##\s+Metadata\s*\n(.*?)(?=\n##|\n#|\Z)',
            r'##\s+Properties\s*\n(.*?)(?=\n##|\n#|\Z)',
            r'##\s+Info\s*\n(.*?)(?=\n##|\n#|\Z)'
        ]
        
        for pattern in metadata_sections:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                section_metadata = self._parse_metadata_section(match)
                metadata.update(section_metadata)
        
        return metadata
    
    def _parse_metadata_section(self, section_content: str) -> Dict[str, Any]:
        """Parse a metadata section into key-value pairs."""
        metadata = {}
        
        lines = section_content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Look for key-value patterns
            patterns = [
                r'^\*\*(.*?)\*\*:\s*(.*)$',  # **Key**: Value
                r'^-\s*\*\*(.*?)\*\*:\s*(.*)$',  # - **Key**: Value
                r'^-\s*(.*?):\s*(.*)$',  # - Key: Value
                r'^(.*?):\s*(.*)$'  # Key: Value
            ]
            
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    if key and value:
                        metadata[key.lower().replace(' ', '_')] = value
                    break
        
        return metadata
    
    def _extract_key_value_pairs(self, content: str) -> Dict[str, Any]:
        """Extract key-value pairs from content, but only from specific metadata sections."""
        metadata = {}
        
        # Only extract from specific metadata sections, not from the entire content
        metadata_sections = [
            r'##\s+Metadata\s*\n(.*?)(?=\n##|\n#|\Z)',
            r'##\s+Properties\s*\n(.*?)(?=\n##|\n#|\Z)',
            r'##\s+Info\s*\n(.*?)(?=\n##|\n#|\Z)',
            r'##\s+Additional Info\s*\n(.*?)(?=\n##|\n#|\Z)'
        ]
        
        for section_pattern in metadata_sections:
            section_match = re.search(section_pattern, content, re.MULTILINE | re.DOTALL)
            if section_match:
                section_content = section_match.group(1)
                
                # Look for key-value patterns within the metadata section only
                patterns = [
                    r'\*\*(.*?)\*\*:\s*([^\n]+)',  # **Key**: Value
                    r'^[\-\*]\s*\*\*(.*?)\*\*:\s*([^\n]+)$',  # - **Key**: Value or * **Key**: Value
                    r'^(.*?):\s*([^\n]+)$'  # Key: Value (start of line)
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, section_content, re.MULTILINE)
                    for key, value in matches:
                        key = key.strip()
                        value = value.strip()
                        if key and value and len(key) < 50:  # Reasonable key length
                            metadata[key.lower().replace(' ', '_')] = value
        
        return metadata
    
    def _normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and clean extracted metadata."""
        normalized = {}
        
        for key, value in metadata.items():
            if value is None or value == '':
                continue
            
            # Clean key
            clean_key = key.lower().strip()
            clean_key = re.sub(r'[^\w\s]', '', clean_key)
            clean_key = re.sub(r'\s+', '_', clean_key)
            
            # Clean value
            if isinstance(value, str):
                clean_value = value.strip()
                if clean_value:
                    normalized[clean_key] = clean_value
            else:
                normalized[clean_key] = value
        
        return normalized
    
    def update_database_with_metadata(self, metadata_results: Dict[str, Dict[str, Any]]) -> None:
        """
        Update the database with extracted metadata.
        
        Args:
            metadata_results: Dictionary mapping node_id to metadata
        """
        if not metadata_results:
            console.print("[yellow]No metadata to update[/yellow]")
            return
        
        console.print(f"[cyan]Updating database with metadata for {len(metadata_results)} nodes...[/cyan]")
        
        # Update person.csv
        self._update_person_csv(metadata_results)
        
        # Update company.csv
        self._update_company_csv(metadata_results)
        
        console.print("[green]✓ Database updated with metadata[/green]")
    
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
    
    def _update_person_csv(self, metadata_results: Dict[str, Dict[str, Any]]) -> None:
        """Update person.csv with metadata."""
        person_file = self.db_input_dir / "person.csv"
        if not person_file.exists():
            return
        
        # Read existing data
        rows = []
        with open(person_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
        
        # Add metadata column if not present
        if 'metadata' not in fieldnames:
            fieldnames = list(fieldnames) + ['metadata']
        
        # Update rows with metadata
        for row in rows:
            node_id = row.get('id', '')
            if node_id in metadata_results:
                metadata = metadata_results[node_id]['metadata']
                if metadata:
                    # Convert any non-serializable objects to strings
                    serializable_metadata = self._make_serializable(metadata)
                    row['metadata'] = json.dumps(serializable_metadata)
                else:
                    row['metadata'] = ''
            else:
                row['metadata'] = ''
        
        # Write updated data
        with open(person_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    
    def _update_company_csv(self, metadata_results: Dict[str, Dict[str, Any]]) -> None:
        """Update company.csv with metadata."""
        company_file = self.db_input_dir / "company.csv"
        if not company_file.exists():
            return
        
        # Read existing data
        rows = []
        with open(company_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
        
        # Add metadata column if not present
        if 'metadata' not in fieldnames:
            fieldnames = list(fieldnames) + ['metadata']
        
        # Update rows with metadata
        for row in rows:
            node_id = row.get('id', '')
            if node_id in metadata_results:
                metadata = metadata_results[node_id]['metadata']
                if metadata:
                    # Convert any non-serializable objects to strings
                    serializable_metadata = self._make_serializable(metadata)
                    row['metadata'] = json.dumps(serializable_metadata)
                else:
                    row['metadata'] = ''
            else:
                row['metadata'] = ''
        
        # Write updated data
        with open(company_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def main():
    """Main function for testing the metadata extractor."""
    import argparse
    import csv
    
    parser = argparse.ArgumentParser(description="Metadata Extractor Tool")
    parser.add_argument("--vault-path", type=Path, required=True, help="Path to Obsidian vault")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted without updating database")
    
    args = parser.parse_args()
    
    extractor = MetadataExtractor(args.vault_path)
    
    # Extract metadata
    metadata_results = extractor.extract_metadata_for_nodes()
    
    if not metadata_results:
        console.print("[yellow]No metadata found[/yellow]")
        return
    
    # Show what would be extracted
    console.print(f"\n[cyan]Found metadata for {len(metadata_results)} nodes:[/cyan]")
    for node_id, data in metadata_results.items():
        console.print(f"\n[bold]{data['label']} ({data['type']}):[/bold]")
        console.print(f"  File: {data['file']}")
        console.print(f"  Metadata: {json.dumps(data['metadata'], indent=2)}")
    
    if args.dry_run:
        console.print("\n[yellow]Dry run - no database updates made[/yellow]")
        return
    
    # Update database
    extractor.update_database_with_metadata(metadata_results)


if __name__ == "__main__":
    main()
