# Metadata Pulling Specification

## Overview

Metadata pulling extracts structured metadata from markdown files and stores it as JSON attributes in the corresponding graph nodes. The system will only process markdown files that are **linked to** Person or Company nodes and have **identical names** (case insensitive).

## Feature Goals

1. **Linked File Detection**: Only process markdown files that are linked to Person/Company nodes
2. **Name Matching**: Match files with identical names to nodes (case insensitive)
3. **Metadata Extraction**: Extract metadata from matching linked files
4. **JSON Storage**: Store metadata as structured JSON in graph nodes
5. **Incremental Updates**: Update metadata when linked files change

## Metadata Detection

### File Matching Rules

1. **Linked Files Only**: Only process markdown files that are linked to Person/Company nodes
2. **Name Matching**: Node label must match filename (case insensitive)
3. **Case Insensitive**: "john smith" matches "John Smith.md"
4. **Exact Name Match**: "John A. Smith" matches "John A. Smith.md"
5. **Supported Extensions**: .md, .markdown files only

### Metadata Extraction Patterns

The system will look for metadata in markdown files using various patterns:

#### 1. Frontmatter (YAML)

```markdown
---
name: "John Smith"
title: "Software Engineer"
company: "Acme Corp"
email: "john@acme.com"
phone: "+1-555-0123"
location: "San Francisco, CA"
tags: ["engineer", "python", "ai"]
social:
  linkedin: "https://linkedin.com/in/johnsmith"
  twitter: "@johnsmith"
---
# John Smith

Content here...
```

#### 2. Metadata Sections

```markdown
# John Smith

## Metadata
- **Title**: Software Engineer
- **Company**: Acme Corp
- **Email**: john@acme.com
- **Phone**: +1-555-0123
- **Location**: San Francisco, CA
- **Tags**: engineer, python, ai
- **LinkedIn**: https://linkedin.com/in/johnsmith
- **Twitter**: @johnsmith

## Content
More content here...
```

#### 3. Key-Value Pairs

```markdown
# John Smith

**Title**: Software Engineer
**Company**: Acme Corp
**Email**: john@acme.com
**Phone**: +1-555-0123
**Location**: San Francisco, CA
**Tags**: engineer, python, ai
**LinkedIn**: https://linkedin.com/in/johnsmith
**Twitter**: @johnsmith

Content here...
```

#### 4. Structured Lists

```markdown
# John Smith

- Title: Software Engineer
- Company: Acme Corp
- Email: john@acme.com
- Phone: +1-555-0123
- Location: San Francisco, CA
- Tags: engineer, python, ai
- LinkedIn: https://linkedin.com/in/johnsmith
- Twitter: @johnsmith
```

## Implementation Details

### 1. Detection Phase

**Location**: New `metadata_extractor.py` module

**Process**:
1. Scan all Person and Company nodes in the graph
2. For each node, find linked markdown files
3. Check if any linked file has identical name (case insensitive)
4. Extract metadata from matching linked files
5. Store extracted metadata in structured format

**Output**: Dictionary of `{node_id: metadata_dict}`

### 2. Extraction Phase

**Location**: `metadata_extractor.py`

**Process**:
1. Parse frontmatter (YAML) if present
2. Look for metadata sections in markdown
3. Extract key-value pairs from content
4. Normalize and validate extracted data
5. Merge multiple sources of metadata

**Supported Formats**:
- YAML frontmatter
- Markdown tables
- Key-value pairs
- Structured lists
- Custom metadata sections

### 3. Database Integration

**Location**: `step3_build.py`

**Process**:
1. Add metadata as JSON properties to nodes
2. Update existing nodes with new metadata
3. Handle metadata updates and deletions

**Database Schema**:
```cypher
CREATE NODE TABLE Person(
    id INT64,
    name STRING,
    metadata JSON
);

CREATE NODE TABLE Company(
    id INT64,
    name STRING,
    metadata JSON
);
```

## File Structure

```
cli/
├── metadata_extractor.py        # Main metadata extraction module
├── metadata_patterns.py         # Pattern matching utilities
├── step3_build.py              # Updated to include metadata
└── manual_trigger.py           # Updated to run metadata extraction
```

## Metadata Extractor Module API

```python
class MetadataExtractor:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.patterns = MetadataPatterns()
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from a markdown file"""
        pass
    
    def find_linked_files(self, node_id: str) -> List[Path]:
        """Find markdown files linked to a specific node"""
        pass
    
    def find_matching_linked_file(self, node_label: str, linked_files: List[Path]) -> Optional[Path]:
        """Find linked file with identical name to node label (case insensitive)"""
        pass
    
    def normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate extracted metadata"""
        pass

class MetadataPatterns:
    def extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from markdown"""
        pass
    
    def extract_metadata_section(self, content: str) -> Dict[str, Any]:
        """Extract metadata from ## Metadata section"""
        pass
    
    def extract_key_value_pairs(self, content: str) -> Dict[str, Any]:
        """Extract key-value pairs from content"""
        pass
```

## Metadata Schema

### Standard Fields

```json
{
  "title": "string",
  "company": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "tags": ["string"],
  "social": {
    "linkedin": "string",
    "twitter": "string",
    "github": "string"
  },
  "bio": "string",
  "website": "string",
  "industry": "string",
  "founded": "string",
  "employees": "string",
  "revenue": "string"
}
```

### Custom Fields

Users can define custom metadata fields that will be preserved in the JSON structure.

## Integration Points

### 1. Manual Trigger Integration

**Location**: `manual_trigger.py`

**Process**:
1. Run metadata extraction after entity resolution
2. Update all nodes with extracted metadata
3. Continue with normal database building

### 2. Monitor Integration

**Location**: `step4_monitor.py`

**Process**:
1. Detect when markdown files with metadata change
2. Trigger metadata extraction for affected nodes
3. Update database with new metadata

### 3. Database Building

**Location**: `step3_build.py`

**Process**:
1. Include metadata in node creation
2. Update existing nodes with new metadata
3. Handle metadata conflicts and updates

## Error Handling

### 1. Invalid YAML

**Scenario**: Malformed frontmatter YAML
**Resolution**:
- Log warning about invalid YAML
- Skip frontmatter extraction
- Continue with other metadata patterns

### 2. File Not Found

**Scenario**: Node has no linked markdown files
**Resolution**:
- Log info about no linked files
- Skip metadata extraction for that node
- Continue with other nodes

### 2. No Matching Linked File

**Scenario**: Node has linked files but none match the node name
**Resolution**:
- Log info about no matching linked files
- Skip metadata extraction for that node
- Continue with other nodes

### 3. Metadata Conflicts

**Scenario**: Multiple sources define the same field differently
**Resolution**:
- Use priority order: frontmatter > metadata section > key-value pairs
- Log conflicts for user review
- Use most recent definition

## Configuration

### Settings

```python
METADATA_CONFIG = {
    "enabled": True,
    "extract_frontmatter": True,
    "extract_metadata_sections": True,
    "extract_key_value_pairs": True,
    "case_sensitive_matching": False,
    "normalize_whitespace": True,
    "supported_extensions": [".md", ".markdown", ".txt"],
    "metadata_sections": ["## Metadata", "## Properties", "## Info"],
    "excluded_fields": ["content", "body", "text"]
}
```

## Testing Strategy

### Unit Tests

1. **Pattern Matching**: Test various metadata extraction patterns
2. **File Matching**: Test node label to file matching
3. **Data Normalization**: Test metadata cleaning and validation
4. **Error Handling**: Test handling of malformed data

### Integration Tests

1. **End-to-End**: Test complete metadata extraction workflow
2. **Database Integration**: Test metadata storage in graph database
3. **Performance**: Test with large numbers of nodes and files

## Example Usage

### Scenario: Linked File with Matching Name

#### Graph Node
```cypher
CREATE (p:Person {
  name: "John Smith",
  id: "person_123"
})
```

#### Linked Markdown File: `John Smith.md`
```markdown
---
title: "Software Engineer"
company: "Acme Corp"
email: "john@acme.com"
location: "San Francisco, CA"
tags: ["engineer", "python", "ai"]
---

# John Smith

## Additional Info
- **Phone**: +1-555-0123
- **LinkedIn**: https://linkedin.com/in/johnsmith
- **GitHub**: https://github.com/johnsmith

John is a senior software engineer...
```

#### Link Relationship
```cypher
CREATE (p:Person {name: "John Smith"})-[:LINKED_TO]->(f:File {path: "John Smith.md"})
```

### Processing Result

#### Extracted Metadata (JSON)
```json
{
  "title": "Software Engineer",
  "company": "Acme Corp",
  "email": "john@acme.com",
  "location": "San Francisco, CA",
  "tags": ["engineer", "python", "ai"],
  "phone": "+1-555-0123",
  "linkedin": "https://linkedin.com/in/johnsmith",
  "github": "https://github.com/johnsmith"
}
```

#### Updated Database Node
```cypher
MATCH (p:Person {name: "John Smith"})
SET p.metadata = {
  "title": "Software Engineer",
  "company": "Acme Corp",
  "email": "john@acme.com",
  "location": "San Francisco, CA",
  "tags": ["engineer", "python", "ai"],
  "phone": "+1-555-0123",
  "linkedin": "https://linkedin.com/in/johnsmith",
  "github": "https://github.com/johnsmith"
}
```

### Key Requirements

1. **File Must Be Linked**: The markdown file must have a relationship to the Person/Company node
2. **Name Must Match**: The filename must match the node name (case insensitive)
3. **Case Insensitive**: "john smith.md" matches "John Smith" node
4. **Exact Match**: "John A. Smith.md" matches "John A. Smith" node

## Future Enhancements

1. **Custom Metadata Schemas**: Allow users to define custom metadata schemas
2. **Metadata Validation**: Validate metadata against schemas
3. **Metadata Templates**: Provide templates for common metadata patterns
4. **Bulk Metadata Operations**: Support for bulk metadata updates
5. **Metadata Search**: Search nodes by metadata properties
6. **Metadata Export**: Export metadata to external formats
7. **Metadata Visualization**: Visual representation of metadata in the graph
