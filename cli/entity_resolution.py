#!/usr/bin/env python3
"""
Entity Resolution Module

This module handles entity resolution by detecting rename patterns in markdown files
and applying them to the corresponding CSV files. Entity resolution is scoped to
each markdown file - only affecting relationships extracted from that specific file.

Usage:
    from entity_resolution import EntityResolver
    
    resolver = EntityResolver(vault_path)
    file_mappings = resolver.detect_rename_patterns()
    resolver.apply_scoped_resolution(file_mappings)
"""

import re
import yaml
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.progress import Progress, TaskID

console = Console()


class EntityResolver:
    """Handles entity resolution for scoped file-based renames."""
    
    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.content_dir = self.vault_path / ".kineviz_graph" / "cache" / "content"
        self.db_input_dir = self.vault_path / ".kineviz_graph" / "cache" / "db_input"
        
        # Ensure directories exist
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.db_input_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for markdown files to avoid repeated scanning
        self._cached_markdown_files = None
        self._file_cache_timestamp = 0
    
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
    
    def detect_rename_patterns(self) -> Dict[Path, Dict[str, str]]:
        """
        Scan all markdown files for entity resolution patterns.
        
        Returns:
            Dictionary mapping file paths to their rename mappings
            Format: {file_path: {old_name: new_name}}
        """
        console.print("[cyan]Detecting entity resolution patterns...[/cyan]")
        
        file_mappings = {}
        markdown_files = self._get_cached_markdown_files()
        
        with Progress() as progress:
            task = progress.add_task("Scanning markdown files...", total=len(markdown_files))
            
            for md_file in markdown_files:
                try:
                    mappings = self.extract_yaml_frontmatter(md_file)
                    if mappings:
                        file_mappings[md_file] = mappings
                        console.print(f"[green]Found {len(mappings)} entity resolutions in {md_file.name}[/green]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not process {md_file.name}: {e}[/yellow]")
                
                progress.advance(task)
        
        console.print(f"[green]Found entity resolution patterns in {len(file_mappings)} files[/green]")
        return file_mappings
    
    def extract_yaml_frontmatter(self, file_path: Path) -> Dict[str, str]:
        """
        Extract entity resolution from YAML frontmatter.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            Dictionary of {old_name: new_name} mappings
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract frontmatter
            if not content.startswith('---'):
                return {}
            
            # Find the end of frontmatter
            end_marker = content.find('---', 3)
            if end_marker == -1:
                return {}
            
            frontmatter_text = content[3:end_marker].strip()
            frontmatter = yaml.safe_load(frontmatter_text)
            
            if not frontmatter or 'resolves' not in frontmatter:
                return {}
            
            return self._parse_resolves_string(frontmatter['resolves'])
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse frontmatter in {file_path.name}: {e}[/yellow]")
            return {}
    
    def _parse_resolves_string(self, resolves_data) -> Dict[str, str]:
        """
        Parse the resolves data into a dictionary of mappings.
        Supports multiple formats from YAML:
        
        1. List format (with dashes):
           resolves:
             - Old Name => New Name
             - Another Old => Another New
        
        2. Comma-separated format:
           resolves: Old Name => New Name, Another Old => Another New
        
        3. Multi-line string format:
           resolves: |
             Old Name => New Name
             Another Old => Another New
        
        Args:
            resolves_data: String or list containing entity resolutions
            
        Returns:
            Dictionary of {old_name: new_name} mappings
        """
        mappings = {}
        
        # Handle list format (YAML array with dashes)
        if isinstance(resolves_data, list):
            for item in resolves_data:
                if isinstance(item, str) and '=>' in item:
                    old_name, new_name = self._parse_resolution_line(item)
                    if old_name and new_name:
                        mappings[old_name] = new_name
        
        # Handle string format
        elif isinstance(resolves_data, str):
            # Handle multi-line format (YAML literal block)
            if '\n' in resolves_data:
                lines = resolves_data.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and '=>' in line:
                        old_name, new_name = self._parse_resolution_line(line)
                        if old_name and new_name:
                            mappings[old_name] = new_name
            
            # Handle single-line comma-separated format
            else:
                resolutions = [r.strip() for r in resolves_data.split(',')]
                for resolution in resolutions:
                    if resolution and '=>' in resolution:
                        old_name, new_name = self._parse_resolution_line(resolution)
                        if old_name and new_name:
                            mappings[old_name] = new_name
        
        return mappings
    
    def _parse_resolution_line(self, line: str) -> Tuple[str, str]:
        """
        Parse a single resolution line.
        
        Args:
            line: Line containing one resolution (e.g., "John => John Heimann")
            
        Returns:
            Tuple of (old_name, new_name)
        """
        if '=>' not in line:
            return "", ""
        
        parts = line.split('=>', 1)
        if len(parts) != 2:
            return "", ""
        
        old_name = parts[0].strip()
        new_name = parts[1].strip()
        
        # Remove quotes if present
        old_name = old_name.strip('"\'')
        new_name = new_name.strip('"\'')
        
        return old_name, new_name
    
    def apply_scoped_resolution(self, file_mappings: Dict[Path, Dict[str, str]]) -> None:
        """
        Apply entity resolution scoped to each markdown file's CSV.
        
        Args:
            file_mappings: Dictionary mapping file paths to their rename mappings
        """
        if not file_mappings:
            console.print("[yellow]No entity resolution patterns found[/yellow]")
            return
        
        console.print(f"[cyan]Applying entity resolution to {len(file_mappings)} files...[/cyan]")
        
        for md_file, mappings in file_mappings.items():
            try:
                # Find the corresponding CSV file
                csv_file = self._find_csv_file_for_markdown(md_file)
                if csv_file and csv_file.exists():
                    self.apply_resolution_to_csv(csv_file, mappings)
                    console.print(f"[green]Applied {len(mappings)} resolutions to {csv_file.name}[/green]")
                else:
                    console.print(f"[yellow]No CSV file found for {md_file.name}[/yellow]")
            except Exception as e:
                console.print(f"[red]Error processing {md_file.name}: {e}[/red]")
        
        # Update organized CSV files
        self._update_organized_csvs()
        console.print("[green]Entity resolution completed[/green]")
    
    def _find_csv_file_for_markdown(self, md_file: Path) -> Optional[Path]:
        """
        Find the CSV file corresponding to a markdown file.
        
        Args:
            md_file: Path to the markdown file
            
        Returns:
            Path to the corresponding CSV file, or None if not found
        """
        # Look for CSV files that contain this markdown file as source
        for csv_file in self.content_dir.glob("*.csv"):
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if 'source_file' in row and row['source_file']:
                            source_file = row['source_file'].strip()
                            # Convert to relative path for comparison
                            if source_file.startswith(str(self.vault_path)):
                                source_file = str(Path(source_file).relative_to(self.vault_path))
                            
                            if source_file == str(md_file.relative_to(self.vault_path)):
                                return csv_file
            except Exception:
                continue
        
        return None
    
    def apply_resolution_to_csv(self, csv_path: Path, mappings: Dict[str, str]) -> None:
        """
        Apply entity resolution to a specific CSV file.
        
        Args:
            csv_path: Path to the CSV file
            mappings: Dictionary of {old_name: new_name} mappings
        """
        if not mappings:
            return
        
        # Read the CSV file
        rows = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                # Apply entity resolution to relevant columns
                for old_name, new_name in mappings.items():
                    for field in fieldnames:
                        if field in row and row[field]:
                            # Only replace exact matches to avoid multiple replacements
                            if row[field].strip() == old_name:
                                row[field] = new_name
                
                rows.append(row)
        
        # Write the updated CSV file
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    
    def _update_organized_csvs(self) -> None:
        """
        Update the organized CSV files in db_input directory.
        This is a simplified version - in practice, you might want to call
        the step2_organize module to regenerate the organized CSVs.
        """
        console.print("[cyan]Updating organized CSV files...[/cyan]")
        
        # For now, just log that this should be done
        # In a full implementation, you would call step2_organize here
        console.print("[yellow]Note: Organized CSV files should be regenerated after entity resolution[/yellow]")
    
    def validate_mappings(self, mappings: Dict[str, str]) -> List[str]:
        """
        Validate rename mappings for conflicts and issues.
        
        Args:
            mappings: Dictionary of {old_name: new_name} mappings
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check for empty names
        for old_name, new_name in mappings.items():
            if not old_name.strip():
                errors.append("Empty old name found")
            if not new_name.strip():
                errors.append("Empty new name found")
        
        # Check for circular references
        for old_name, new_name in mappings.items():
            if new_name in mappings and mappings[new_name] == old_name:
                errors.append(f"Circular reference: {old_name} => {new_name} => {old_name}")
        
        # Check for duplicate old names
        old_names = list(mappings.keys())
        if len(old_names) != len(set(old_names)):
            errors.append("Duplicate old names found")
        
        return errors


def main():
    """Main function for testing the entity resolver."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Entity Resolution Tool")
    parser.add_argument("--vault-path", type=Path, required=True, help="Path to Obsidian vault")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    
    args = parser.parse_args()
    
    resolver = EntityResolver(args.vault_path)
    
    # Detect patterns
    file_mappings = resolver.detect_rename_patterns()
    
    if not file_mappings:
        console.print("[yellow]No entity resolution patterns found[/yellow]")
        return
    
    # Show what would be changed
    console.print(f"\n[cyan]Found entity resolution patterns in {len(file_mappings)} files:[/cyan]")
    for md_file, mappings in file_mappings.items():
        console.print(f"\n[bold]{md_file.name}:[/bold]")
        for old_name, new_name in mappings.items():
            console.print(f"  {old_name} => {new_name}")
    
    if args.dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return
    
    # Apply resolution
    resolver.apply_scoped_resolution(file_mappings)


if __name__ == "__main__":
    main()
