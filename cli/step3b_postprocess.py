#!/usr/bin/env python3
"""
Step 3b: Post-process the Kuzu database after initial build.

This step:
1. Alters Person and Company tables to add entity_types column
2. Creates PERSON_NOTE and COMPANY_NOTE relationship types
3. Links Person/Company nodes to Note nodes by matching labels (case insensitive)
4. Propagates entity_types from linked Note nodes to Person/Company nodes
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click
import kuzu
from dotenv import load_dotenv
from rich.console import Console
from config_loader import ConfigLoader

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()


class Step3bPostProcessor:
    def __init__(self, vault_path: Path, db_path: str):
        self.vault_path = vault_path
        self.db_path = db_path
        
        # Connect to existing database
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
    
    def cleanup(self):
        """Clean up database connections"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                self.conn = None
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self.cleanup()
        except Exception:
            pass

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            # Try to query the column - if it doesn't exist, this will fail
            result = self.conn.execute(f"MATCH (n:{table_name}) RETURN n.{column_name} LIMIT 1")
            list(result)  # Consume the result
            return True
        except Exception:
            return False

    def _rel_table_exists(self, rel_name: str) -> bool:
        """Check if a relationship table exists"""
        try:
            result = self.conn.execute(f"MATCH ()-[r:{rel_name}]->() RETURN r LIMIT 1")
            list(result)
            return True
        except Exception:
            return False

    def alter_schema(self) -> None:
        """Alter tables to add entity_types column if not present"""
        console.print("[cyan]Step 1: Altering schema to add entity_types column...[/cyan]")
        
        # Add entity_types to Person table
        if not self._column_exists("Person", "entity_types"):
            try:
                self.conn.execute("ALTER TABLE Person ADD entity_types STRING DEFAULT ''")
                console.print("[green]  ✓ Added entity_types column to Person table[/green]")
            except Exception as e:
                console.print(f"[yellow]  ⚠ Could not add entity_types to Person: {e}[/yellow]")
        else:
            console.print("[cyan]  → entity_types column already exists in Person table[/cyan]")
        
        # Add entity_types to Company table
        if not self._column_exists("Company", "entity_types"):
            try:
                self.conn.execute("ALTER TABLE Company ADD entity_types STRING DEFAULT ''")
                console.print("[green]  ✓ Added entity_types column to Company table[/green]")
            except Exception as e:
                console.print(f"[yellow]  ⚠ Could not add entity_types to Company: {e}[/yellow]")
        else:
            console.print("[cyan]  → entity_types column already exists in Company table[/cyan]")
        
        # Create PERSON_NOTE relationship table if not exists
        if not self._rel_table_exists("PERSON_NOTE"):
            try:
                self.conn.execute("CREATE REL TABLE PERSON_NOTE(FROM Person TO Note)")
                console.print("[green]  ✓ Created PERSON_NOTE relationship table[/green]")
            except Exception as e:
                console.print(f"[yellow]  ⚠ Could not create PERSON_NOTE table: {e}[/yellow]")
        else:
            console.print("[cyan]  → PERSON_NOTE relationship table already exists[/cyan]")
        
        # Create COMPANY_NOTE relationship table if not exists
        if not self._rel_table_exists("COMPANY_NOTE"):
            try:
                self.conn.execute("CREATE REL TABLE COMPANY_NOTE(FROM Company TO Note)")
                console.print("[green]  ✓ Created COMPANY_NOTE relationship table[/green]")
            except Exception as e:
                console.print(f"[yellow]  ⚠ Could not create COMPANY_NOTE table: {e}[/yellow]")
        else:
            console.print("[cyan]  → COMPANY_NOTE relationship table already exists[/cyan]")

    def create_entity_note_links(self) -> None:
        """Create PERSON_NOTE and COMPANY_NOTE relationships by matching labels (case insensitive)"""
        console.print("[cyan]Step 2: Creating entity-to-note links by matching labels...[/cyan]")
        
        # Create PERSON_NOTE relationships
        # Match Person nodes to Note nodes where labels match (case insensitive)
        try:
            # First, clear existing PERSON_NOTE relationships to avoid duplicates
            self.conn.execute("MATCH ()-[r:PERSON_NOTE]->() DELETE r")
            
            # Create new relationships using case-insensitive matching
            result = self.conn.execute("""
                MATCH (p:Person), (n:Note)
                WHERE lower(p.label) = lower(n.label)
                CREATE (p)-[:PERSON_NOTE]->(n)
                RETURN count(*) as count
            """)
            person_note_count = list(result)[0][0]
            console.print(f"[green]  ✓ Created {person_note_count} PERSON_NOTE relationships[/green]")
        except Exception as e:
            console.print(f"[red]  ✗ Error creating PERSON_NOTE relationships: {e}[/red]")
        
        # Create COMPANY_NOTE relationships
        try:
            # First, clear existing COMPANY_NOTE relationships to avoid duplicates
            self.conn.execute("MATCH ()-[r:COMPANY_NOTE]->() DELETE r")
            
            # Create new relationships using case-insensitive matching
            result = self.conn.execute("""
                MATCH (c:Company), (n:Note)
                WHERE lower(c.label) = lower(n.label)
                CREATE (c)-[:COMPANY_NOTE]->(n)
                RETURN count(*) as count
            """)
            company_note_count = list(result)[0][0]
            console.print(f"[green]  ✓ Created {company_note_count} COMPANY_NOTE relationships[/green]")
        except Exception as e:
            console.print(f"[red]  ✗ Error creating COMPANY_NOTE relationships: {e}[/red]")

    def propagate_entity_types(self) -> None:
        """Propagate entity_types from Note nodes to linked Person/Company nodes"""
        console.print("[cyan]Step 4: Propagating entity_types from Notes to entities...[/cyan]")
        
        # Update Person nodes with entity_types from linked Notes
        try:
            result = self.conn.execute("""
                MATCH (p:Person)-[:PERSON_NOTE]->(n:Note)
                WHERE n.entity_types IS NOT NULL AND n.entity_types <> ''
                SET p.entity_types = n.entity_types
                RETURN count(*) as count
            """)
            person_update_count = list(result)[0][0]
            console.print(f"[green]  ✓ Updated entity_types for {person_update_count} Person nodes[/green]")
        except Exception as e:
            console.print(f"[red]  ✗ Error updating Person entity_types: {e}[/red]")
        
        # Update Company nodes with entity_types from linked Notes
        try:
            result = self.conn.execute("""
                MATCH (c:Company)-[:COMPANY_NOTE]->(n:Note)
                WHERE n.entity_types IS NOT NULL AND n.entity_types <> ''
                SET c.entity_types = n.entity_types
                RETURN count(*) as count
            """)
            company_update_count = list(result)[0][0]
            console.print(f"[green]  ✓ Updated entity_types for {company_update_count} Company nodes[/green]")
        except Exception as e:
            console.print(f"[red]  ✗ Error updating Company entity_types: {e}[/red]")

    def create_missing_entities_from_notes(self) -> None:
        """
        Create Person/Company nodes for Notes that should have them but don't.
        
        If a Note has entity_types containing "Person" but no PERSON_NOTE relationship,
        create a Person node with the same label and link them.
        Same for Company.
        """
        console.print("[cyan]Step 3: Creating missing entities from orphan notes...[/cyan]")
        
        # Find Notes with "Person" in entity_types but no PERSON_NOTE relationship
        try:
            # First, find orphan Person notes
            result = self.conn.execute("""
                MATCH (n:Note)
                WHERE n.entity_types CONTAINS 'Person'
                AND NOT EXISTS {
                    MATCH (p:Person)-[:PERSON_NOTE]->(n)
                }
                RETURN n.id as note_id, n.label as label, n.entity_types as entity_types
            """)
            
            orphan_person_notes = list(result)
            
            if orphan_person_notes:
                console.print(f"  Found {len(orphan_person_notes)} Person notes without Person nodes")
                
                created_count = 0
                for row in orphan_person_notes:
                    note_id = row[0]
                    label = row[1]
                    entity_types = row[2] or ""
                    
                    # Check if Person with this label already exists
                    existing = self.conn.execute("""
                        MATCH (p:Person)
                        WHERE lower(p.label) = lower($label)
                        RETURN p.id
                    """, {"label": label})
                    existing_list = list(existing)
                    
                    if existing_list:
                        # Person exists, just create the relationship
                        person_id = existing_list[0][0]
                        try:
                            self.conn.execute("""
                                MATCH (p:Person {id: $person_id}), (n:Note {id: $note_id})
                                CREATE (p)-[:PERSON_NOTE]->(n)
                            """, {"person_id": person_id, "note_id": note_id})
                        except Exception:
                            pass  # Relationship might already exist
                    else:
                        # Create new Person node
                        person_id = f"person_{label.lower().replace(' ', '_').replace('.', '').replace(',', '')}"
                        try:
                            self.conn.execute("""
                                CREATE (p:Person {id: $id, label: $label, metadata: '', entity_types: $entity_types})
                            """, {"id": person_id, "label": label, "entity_types": entity_types})
                            
                            # Create relationship
                            self.conn.execute("""
                                MATCH (p:Person {id: $person_id}), (n:Note {id: $note_id})
                                CREATE (p)-[:PERSON_NOTE]->(n)
                            """, {"person_id": person_id, "note_id": note_id})
                            created_count += 1
                        except Exception as e:
                            console.print(f"    [yellow]⚠ Could not create Person '{label}': {e}[/yellow]")
                
                console.print(f"[green]  ✓ Created {created_count} new Person nodes from orphan notes[/green]")
            else:
                console.print("[green]  ✓ No orphan Person notes found[/green]")
                
        except Exception as e:
            console.print(f"[red]  ✗ Error processing Person orphan notes: {e}[/red]")
        
        # Find Notes with "Company" or "Family Office" or "VC" in entity_types but no COMPANY_NOTE relationship
        try:
            # Find orphan Company/FO/VC notes
            result = self.conn.execute("""
                MATCH (n:Note)
                WHERE (n.entity_types CONTAINS 'Company' 
                       OR n.entity_types CONTAINS 'Family Office'
                       OR n.entity_types CONTAINS 'VC')
                AND NOT EXISTS {
                    MATCH (c:Company)-[:COMPANY_NOTE]->(n)
                }
                RETURN n.id as note_id, n.label as label, n.entity_types as entity_types
            """)
            
            orphan_company_notes = list(result)
            
            if orphan_company_notes:
                console.print(f"  Found {len(orphan_company_notes)} Company/FO/VC notes without Company nodes")
                
                created_count = 0
                for row in orphan_company_notes:
                    note_id = row[0]
                    label = row[1]
                    entity_types = row[2] or ""
                    
                    # Check if Company with this label already exists
                    existing = self.conn.execute("""
                        MATCH (c:Company)
                        WHERE lower(c.label) = lower($label)
                        RETURN c.id
                    """, {"label": label})
                    existing_list = list(existing)
                    
                    if existing_list:
                        # Company exists, just create the relationship
                        company_id = existing_list[0][0]
                        try:
                            self.conn.execute("""
                                MATCH (c:Company {id: $company_id}), (n:Note {id: $note_id})
                                CREATE (c)-[:COMPANY_NOTE]->(n)
                            """, {"company_id": company_id, "note_id": note_id})
                        except Exception:
                            pass  # Relationship might already exist
                    else:
                        # Create new Company node
                        company_id = f"company_{label.lower().replace(' ', '_').replace('.', '').replace(',', '')}"
                        try:
                            self.conn.execute("""
                                CREATE (c:Company {id: $id, label: $label, metadata: '', entity_types: $entity_types})
                            """, {"id": company_id, "label": label, "entity_types": entity_types})
                            
                            # Create relationship
                            self.conn.execute("""
                                MATCH (c:Company {id: $company_id}), (n:Note {id: $note_id})
                                CREATE (c)-[:COMPANY_NOTE]->(n)
                            """, {"company_id": company_id, "note_id": note_id})
                            created_count += 1
                        except Exception as e:
                            console.print(f"    [yellow]⚠ Could not create Company '{label}': {e}[/yellow]")
                
                console.print(f"[green]  ✓ Created {created_count} new Company nodes from orphan notes[/green]")
            else:
                console.print("[green]  ✓ No orphan Company/FO/VC notes found[/green]")
                
        except Exception as e:
            console.print(f"[red]  ✗ Error processing Company orphan notes: {e}[/red]")

    def show_summary(self) -> None:
        """Show summary of entity_types distribution"""
        console.print("[cyan]Summary:[/cyan]")
        
        # Count Person nodes with entity_types
        try:
            result = self.conn.execute("""
                MATCH (p:Person)
                WHERE p.entity_types IS NOT NULL AND p.entity_types <> ''
                RETURN count(*) as count
            """)
            person_with_types = list(result)[0][0]
            
            result = self.conn.execute("MATCH (p:Person) RETURN count(*) as count")
            total_persons = list(result)[0][0]
            
            console.print(f"  • Persons with entity_types: {person_with_types}/{total_persons}")
        except Exception as e:
            console.print(f"  • Could not count Person entity_types: {e}")
        
        # Count Company nodes with entity_types
        try:
            result = self.conn.execute("""
                MATCH (c:Company)
                WHERE c.entity_types IS NOT NULL AND c.entity_types <> ''
                RETURN count(*) as count
            """)
            company_with_types = list(result)[0][0]
            
            result = self.conn.execute("MATCH (c:Company) RETURN count(*) as count")
            total_companies = list(result)[0][0]
            
            console.print(f"  • Companies with entity_types: {company_with_types}/{total_companies}")
        except Exception as e:
            console.print(f"  • Could not count Company entity_types: {e}")
        
        # Show entity_types breakdown
        try:
            console.print("\n[cyan]Entity types breakdown:[/cyan]")
            
            # Person entity types
            result = self.conn.execute("""
                MATCH (p:Person)
                WHERE p.entity_types IS NOT NULL AND p.entity_types <> ''
                RETURN p.entity_types as types, count(*) as count
                ORDER BY count DESC
            """)
            console.print("  [bold]Person:[/bold]")
            for row in result:
                console.print(f"    • {row[0]}: {row[1]}")
            
            # Company entity types
            result = self.conn.execute("""
                MATCH (c:Company)
                WHERE c.entity_types IS NOT NULL AND c.entity_types <> ''
                RETURN c.entity_types as types, count(*) as count
                ORDER BY count DESC
            """)
            console.print("  [bold]Company:[/bold]")
            for row in result:
                console.print(f"    • {row[0]}: {row[1]}")
                
        except Exception as e:
            console.print(f"  Could not show entity_types breakdown: {e}")

    def run(self) -> None:
        """Run all post-processing steps"""
        import time
        
        console.print("[bold cyan]Starting post-processing...[/bold cyan]\n")
        start_time = time.time()
        
        # Step 1: Alter schema (add entity_types column, create relationship tables)
        self.alter_schema()
        console.print()
        
        # Step 2: Create entity-note links by matching existing entity labels to note labels
        self.create_entity_note_links()
        console.print()
        
        # Step 3: Create missing entities from orphan notes
        # (Notes with entity_types but no corresponding Person/Company node)
        self.create_missing_entities_from_notes()
        console.print()
        
        # Step 4: Propagate entity_types from Notes to all linked Person/Company nodes
        # (This must come AFTER creating missing entities so they get their types too)
        self.propagate_entity_types()
        console.print()
        
        # Show summary
        self.show_summary()
        
        total_time = time.time() - start_time
        console.print(f"\n[green]🎉 Post-processing completed in {total_time:.2f}s![/green]")


@click.command()
@click.option("--vault-path", type=click.Path(exists=True, file_okay=False, path_type=Path), 
              default=None, 
              help="Path to Obsidian vault (default: auto-detect from config)")
@click.option("--db-path", help="Path to the Kuzu database file (default: auto-detect from vault)")
def main(vault_path: Path, db_path: Optional[str]):
    """Step 3b: Post-process the Kuzu database to link entities to notes and propagate entity_types"""
    
    # Load configuration
    config_loader = ConfigLoader()
    
    # Auto-detect vault path if not provided
    if not vault_path:
        vault_path_str = config_loader.get_vault_path()
        if vault_path_str:
            vault_path = Path(vault_path_str)
            console.print(f"[cyan]Auto-detected vault path: {vault_path}[/cyan]")
        else:
            vault_path_str = os.getenv("VAULT_PATH")
            if vault_path_str:
                vault_path = Path(vault_path_str)
            else:
                console.print("[red]Error: Vault path is required. Set vault.path in config.yaml or use --vault-path[/red]")
                sys.exit(1)
    
    # Set default database path if not provided
    if not db_path:
        db_path = str(vault_path / ".kineviz_graph" / "database" / "knowledge_graph.kz")
    
    # Check if database exists
    if not Path(db_path).exists():
        console.print(f"[red]Error: Database not found at {db_path}[/red]")
        console.print("[yellow]Run step3_build.py first to create the database.[/yellow]")
        sys.exit(1)
    
    try:
        processor = Step3bPostProcessor(vault_path, db_path)
        processor.run()
        processor.cleanup()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

