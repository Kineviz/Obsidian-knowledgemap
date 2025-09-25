# Entity Resolution Specification

## Overview

Entity resolution allows users to rename entities in their knowledge graph by defining rename patterns in markdown files. When the system detects a pattern like `"Old Name" is "New Name"`, it will update all references to that entity **only within the relationships extracted from that specific markdown file**.

## Feature Goals

1. **Detect Entity Rename Patterns**: Identify when a markdown file contains entity rename declarations
2. **Apply Scoped Resolution**: Apply renames only to relationships extracted from the same markdown file
3. **Maintain Context**: Keep entity resolution scoped to the specific file where it's defined
4. **Preserve History**: Keep track of entity renames for audit purposes

## Entity Resolution Region Definition

### YAML Frontmatter Method

The system will look for entity resolution patterns in YAML frontmatter at the top of markdown files using a single-line format:

```markdown
---
resolves: John => John Heimann, Paco => Paco Gomaz, Mary1 => Mary
---

# My Knowledge Base

Content here...
```

### Alternative: Multiple Lines

For better readability with many resolutions:

```markdown
---
resolves: |
  John => John Heimann
  Paco => Paco Gomaz
  Mary1 => Mary
  Company A => Acme Corporation
---

# My Knowledge Base

Content here...
```

### Pattern Rules

- **YAML Key**: Use `resolves:` key (shorter than `entity_resolution`)
- **Arrow Format**: Use `=>` to separate old name from new name
- **Comma Separated**: Multiple resolutions separated by commas
- **No Quotes Required**: Names don't need quotes unless they contain special characters
- **Case Sensitive**: Matching is case-sensitive by default
- **Whitespace**: Leading/trailing whitespace is trimmed
- **Multiple Mappings**: Multiple renames can be defined in the same line or multiple lines

## Implementation Details

### 1. Detection Phase

**Location**: `step1_extract.py` or new `entity_resolution.py`

**Process**:
1. Scan all markdown files for YAML frontmatter with `resolves` section
2. Extract all rename mappings from each file
3. Validate that both old and new names are non-empty
4. Store mappings in a temporary structure

**YAML Parsing**:
- Use PyYAML to parse frontmatter
- Look for `resolves` key in YAML
- Parse arrow-separated format: `old => new`
- Split by commas for multiple resolutions
- Handle both single-line and multi-line formats

**Output**: Dictionary of `{file_path: {old_name: new_name}}` mappings

### 2. Resolution Phase

**Location**: New `entity_resolution.py` module

**Process**:
1. For each markdown file with entity resolution patterns:
   - Extract the entity resolution mappings
   - Find the corresponding CSV file in `cache/content/`
   - Apply entity resolution mappings only to that specific CSV file
   - Update the CSV file with resolved names
2. Update organized CSV files in `cache/db_input/`

**Scoped Application**:
- Entity resolution is applied only to the CSV file generated from the same markdown file
- Each markdown file's entity resolution is independent
- No cross-file entity resolution occurs

**Columns to Update**:
- `source_entity` (Person/Company names)
- `target_entity` (Person/Company names)
- `entity_name` (in person.csv, company.csv)
- Any other entity reference columns

### 3. Database Update Phase

**Location**: `step3_build.py`

**Process**:
1. Rebuild the Kuzu database with resolved entity names
2. Ensure all relationships use the new entity names
3. Maintain referential integrity

## File Structure

```
cli/
├── entity_resolution.py          # Main entity resolution module
├── step1_extract.py             # Updated to detect patterns
├── step2_organize.py            # Updated to apply resolution
└── step3_build.py               # Updated to use resolved names
```

## Entity Resolution Module API

```python
class EntityResolver:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.content_dir = vault_path / ".kineviz_graph" / "cache" / "content"
        self.db_input_dir = vault_path / ".kineviz_graph" / "cache" / "db_input"
    
    def detect_rename_patterns(self) -> Dict[Path, Dict[str, str]]:
        """Scan markdown files for entity rename patterns, return file-specific mappings"""
        pass
    
    def extract_yaml_frontmatter(self, file_path: Path) -> Dict[str, str]:
        """Extract entity resolution from YAML frontmatter"""
        pass
    
    def apply_scoped_resolution(self, file_mappings: Dict[Path, Dict[str, str]]) -> None:
        """Apply entity resolution scoped to each markdown file's CSV"""
        pass
    
    def apply_resolution_to_csv(self, csv_path: Path, mappings: Dict[str, str]) -> None:
        """Apply entity resolution to a specific CSV file"""
        pass
    
    def validate_mappings(self, mappings: Dict[str, str]) -> List[str]:
        """Validate rename mappings for conflicts and issues"""
        pass
```

## Integration Points

### 1. Manual Trigger Integration

**Location**: `manual_trigger.py`

**Process**:
1. Run entity resolution after file processing
2. Apply mappings to all CSV files
3. Continue with normal organization and building

### 2. Monitor Integration

**Location**: `step4_monitor.py`

**Process**:
1. Detect when markdown files with entity resolution patterns change
2. Trigger entity resolution process
3. Update affected CSV files

## Error Handling

### 1. Conflicting Mappings

**Scenario**: Multiple files define different renames for the same entity
**Resolution**: 
- Log warning about conflict
- Use the most recent definition (by file modification time)
- Report conflicts to user

### 2. Circular References

**Scenario**: A → B and B → A
**Resolution**:
- Detect circular references
- Log error and skip conflicting mappings
- Report to user

### 3. Missing Entities

**Scenario**: Rename references an entity that doesn't exist
**Resolution**:
- Log warning about missing entity
- Skip the rename mapping
- Continue with other mappings

## Configuration

### Settings

```python
ENTITY_RESOLUTION_CONFIG = {
    "enabled": True,
    "yaml_key": "resolves",
    "case_sensitive": True,
    "trim_whitespace": True
}
```

## Testing Strategy

### Unit Tests

1. **YAML Parsing**: Test YAML frontmatter extraction
2. **CSV Updates**: Test entity resolution in CSV files
3. **Scoped Resolution**: Test file-specific entity resolution
4. **Edge Cases**: Test empty names, special characters, etc.

### Integration Tests

1. **End-to-End**: Test complete entity resolution workflow
2. **Database Consistency**: Verify database integrity after resolution
3. **Performance**: Test with large numbers of entities and mappings

## Example Usage

### Scenario: Multiple Files with Different Entity Resolutions

#### File 1: `project_alpha.md`

```markdown
---
title: "Project Alpha Documentation"
resolves: John Smith => John A. Smith, Acme Corp => Acme Corporation
---

# Project Alpha

John Smith works at Acme Corp on Project Alpha.
```

#### File 2: `project_beta.md`

```markdown
---
title: "Project Beta Documentation"
resolves: John Smith => John B. Smith, Acme Corp => Acme Industries
---

# Project Beta

John Smith works at Acme Corp on Project Beta.
```

### Before Resolution

#### CSV for `project_alpha.md`
```csv
source_file,source_entity,target_entity,relationship_type
project_alpha.md,John Smith,Acme Corp,works_at
project_alpha.md,Acme Corp,Project Alpha,manages
```

#### CSV for `project_beta.md`
```csv
source_file,source_entity,target_entity,relationship_type
project_beta.md,John Smith,Acme Corp,works_at
project_beta.md,Acme Corp,Project Beta,manages
```

### After Resolution

#### CSV for `project_alpha.md` (scoped resolution applied)
```csv
source_file,source_entity,target_entity,relationship_type
project_alpha.md,John A. Smith,Acme Corporation,works_at
project_alpha.md,Acme Corporation,Project Alpha,manages
```

#### CSV for `project_beta.md` (scoped resolution applied)
```csv
source_file,source_entity,target_entity,relationship_type
project_beta.md,John B. Smith,Acme Industries,works_at
project_beta.md,Acme Industries,Project Beta,manages
```

### Key Benefits of Scoped Resolution

1. **Context Preservation**: Each file can have its own entity resolution context
2. **No Conflicts**: Different files can resolve the same entity differently
3. **Maintainability**: Entity resolution is contained within the relevant file
4. **Flexibility**: Users can have different naming conventions per project/context

## Future Enhancements

1. **Fuzzy Matching**: Handle slight variations in entity names
2. **Bulk Operations**: Support for bulk entity renames
3. **Undo Functionality**: Ability to revert entity renames
4. **Visual Interface**: GUI for managing entity renames
5. **Import/Export**: Import rename mappings from external files
