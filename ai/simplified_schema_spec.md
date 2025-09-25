# Simplified Knowledge Graph Schema Specification

## Overview

This specification defines a simplified knowledge graph model that focuses on entity relationships with incremental update capabilities through CSV caching.

## Graph Model

### Node Types

#### Person
- **Properties:**
  - `id`: STRING PRIMARY KEY (person name)
  - `label`: STRING (person name)

#### Company
- **Properties:**
  - `id`: STRING PRIMARY KEY (company name)
  - `label`: STRING (company name)

#### Note
- **Properties:**
  - `id`: STRING PRIMARY KEY (format: `{url}` - the full path to markdown file)
  - `label`: STRING (simplified filename without extension, e.g., "file_name" from "document/file_name.md")
  - `url`: STRING (path to the markdown file, can be recursive)
  - `content`: STRING (text content from the markdown file)

### Relationship Types

#### PERSON_TO_PERSON
- **Properties:**
  - `relationship`: STRING (one-word summary of the relationship)
- **Connects:** Person → Person

#### PERSON_TO_COMPANY
- **Properties:**
  - `relationship`: STRING (one-word summary of the relationship)
- **Connects:** Person → Company

#### COMPANY_TO_COMPANY
- **Properties:**
  - `relationship`: STRING (one-word summary of the relationship)
- **Connects:** Company → Company

#### COMPANY_TO_PERSON
- **Properties:**
  - `relationship`: STRING (one-word summary of the relationship)
- **Connects:** Company → Person

#### PERSON_REFERENCE
- **Properties:**
  - `meta`: JSON (optional metadata)
- **Connects:** Person → Note

#### COMPANY_REFERENCE
- **Properties:**
  - `meta`: JSON (optional metadata)
- **Connects:** Company → Note

## Database Schema (Kuzu)

```cypher
-- Person nodes
CREATE NODE TABLE IF NOT EXISTS Person (
    id STRING PRIMARY KEY,
    label STRING
);

-- Company nodes
CREATE NODE TABLE IF NOT EXISTS Company (
    id STRING PRIMARY KEY,
    label STRING
);

-- Note nodes
CREATE NODE TABLE IF NOT EXISTS Note (
    id STRING PRIMARY KEY,
    label STRING,
    url STRING,
    content STRING
);

-- Person to Person relationships
CREATE REL TABLE IF NOT EXISTS PERSON_TO_PERSON(
    FROM Person TO Person,
    relationship STRING
);

-- Person to Company relationships
CREATE REL TABLE IF NOT EXISTS PERSON_TO_COMPANY(
    FROM Person TO Company,
    relationship STRING
);

-- Company to Company relationships
CREATE REL TABLE IF NOT EXISTS COMPANY_TO_COMPANY(
    FROM Company TO Company,
    relationship STRING
);

-- Company to Person relationships
CREATE REL TABLE IF NOT EXISTS COMPANY_TO_PERSON(
    FROM Company TO Person,
    relationship STRING
);

-- Person to Note references
CREATE REL TABLE IF NOT EXISTS PERSON_REFERENCE(
    FROM Person TO Note,
    meta JSON
);

-- Company to Note references
CREATE REL TABLE IF NOT EXISTS COMPANY_REFERENCE(
    FROM Company TO Note,
    meta JSON
);
```

## Processing Pipeline

### 1. Markdown Processing
- **Input:** Markdown files (processed individually)
- **Content Extraction:** Read full text content from markdown file
- **Chunking:** Use existing semantic chunking per file
- **LLM Extraction:** Extract only Person and Company entities and their relationships
- **Output:** One CSV file per markdown file + Note node with content
- **Mapping:** `markdown_file.md` → `{hash}_{timestamp}.csv` + Note node

### 2. CSV Caching System

#### Cache Structure
- **Location:** `cache/` folder
- **File Format:** CSV with timestamp
- **Organized Structure:** Separate files for entities and relationship types
- **Legacy Support:** Individual file CSVs maintained for backward compatibility

#### Cache Directory Structure
```
.kineviz_graph/                   # Hidden from Obsidian, contains all KG data
├── cache/
│   ├── content/                  # Content hash tracking
│   │   └── {content_hash}_{timestamp}.csv  # Individual file relationship cache
│   └── db_input/                 # Database input files
│       ├── person.csv            # All unique Person entities
│       ├── company.csv           # All unique Company entities
│       ├── person_to_person.csv  # Person-to-Person relationships
│       ├── person_to_company.csv # Person-to-Company relationships
│       └── company_to_company.csv # Company-to-Company relationships
├── database/
│   └── knowledge_graph.kz        # Kuzu database
├── config/
│   └── settings.json             # Processing settings
└── logs/
    └── processing.log            # Processing logs
```

#### Cache Benefits
- **Organized Structure:** Separate files for entities and relationship types
- **Directory Separation:** Content hashes in `cache/content/`, database inputs in `cache/db_input/`
- **Deduplication:** No duplicate entity pairs across relationship types
- **Fast Queries:** Direct access to specific relationship types
- **Incremental Updates:** Update only changed entities and relationships
- **Audit Trail:** Track when entities and relationships were first/last seen
- **Clean Separation:** Content tracking separate from database preparation

#### Entity CSV Formats

##### person.csv
```csv
id,label,first_seen,last_seen
John Smith,John Smith,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
Sarah Johnson,Sarah Johnson,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
```

##### company.csv
```csv
id,label,first_seen,last_seen
Microsoft,Microsoft,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
GitHub,GitHub,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
```

#### Relationship CSV Formats

##### person_to_person.csv
```csv
source_id,target_id,relationship,first_seen,last_seen
Sarah Johnson,John Smith,reports_to,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
Mike Davis,Sarah Johnson,reports_to,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
```

##### person_to_company.csv
```csv
person_id,company_id,relationship,first_seen,last_seen
John Smith,Microsoft,works_at,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
Sarah Johnson,Microsoft,works_at,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
```

##### company_to_company.csv
```csv
source_id,target_id,relationship,first_seen,last_seen
Microsoft,GitHub,acquired,2024-01-15T10:30:00Z,2024-01-15T10:30:00Z
```

#### Relationship Normalization Rules

1. **COMPANY_TO_PERSON Reordering**: All Company-to-Person relationships are reordered to Person-to-Company
   - `Company,Microsoft,hires,Person,John` → `Person,John,works_at,Company,Microsoft`

2. **PERSON_TO_PERSON Deduplication**: Sort entity IDs alphabetically to ensure no duplicate pairs
   - `Person,Alice,reports_to,Person,Bob` and `Person,Bob,manages,Person,Alice` → Keep only one relationship
   - Use lexicographically smaller ID as source, larger as target

3. **COMPANY_TO_COMPANY Deduplication**: Sort entity IDs alphabetically to ensure no duplicate pairs
   - `Company,Acme,acquires,Company,Widget` and `Company,Widget,acquired_by,Company,Acme` → Keep only one relationship

#### Legacy CSV Schema (for backward compatibility)
```csv
source_category,source_label,relationship,target_category,target_label,source_file,extracted_at
Person,John Smith,works_at,Company,Microsoft,documents/people/john.md,2024-01-15T10:30:00Z
Company,Microsoft,acquired,Company,LinkedIn,documents/companies/microsoft.md,2024-01-15T10:30:00Z
Person,Jane Doe,reports_to,Person,John Smith,projects/team/org-chart.md,2024-01-15T10:30:00Z
```

### 3. Vault-Centric Architecture

#### Obsidian Vault Integration
- **Input:** Obsidian vault path (e.g., `/path/to/obsidian-vault/`)
- **Storage:** All knowledge graph data stored in `.kineviz_graph/` within the vault
- **Hidden:** `.kineviz_graph/` is hidden from Obsidian (starts with dot)
- **Self-contained:** Complete knowledge graph data travels with the vault
- **Non-intrusive:** Doesn't interfere with Obsidian's file watching or functionality

#### Directory Structure Benefits
- **Portable:** Move vault = move knowledge graph data
- **Organized:** Clear separation of cache, database, config, and logs
- **Scalable:** Easy to add API server, plugins, or other tools
- **Clean:** All KG data in one place, easy to backup or delete

### 4. Processing Logic

#### Vault-Centric Processing
1. **Input:** Obsidian vault path (e.g., `/path/to/obsidian-vault/`)
2. **Create:** `.kineviz_graph/` directory structure in vault root
3. **Extract relationships** from markdown files using LLM
4. **Update entity CSVs in `.kineviz_graph/cache/db_input/`:**
   - Add new Person entities to `person.csv`
   - Add new Company entities to `company.csv`
5. **Update relationship CSVs in `.kineviz_graph/cache/db_input/`:**
   - Normalize relationships (reorder COMPANY_TO_PERSON to PERSON_TO_COMPANY)
   - Deduplicate entity pairs (sort alphabetically)
   - Add to appropriate relationship CSV file
6. **Maintain legacy CSV in `.kineviz_graph/cache/content/`** for backward compatibility
7. **Store database** in `.kineviz_graph/database/knowledge_graph.kz`

#### Cache Management
- **Entity Deduplication:** Merge entities with same ID, update timestamps
- **Relationship Deduplication:** Ensure no duplicate entity pairs
- **Timestamp Tracking:** Track first_seen and last_seen for entities and relationships
- **Validation:** Verify CSV integrity before processing

### 4. Knowledge Graph Construction

#### From Organized CSVs to Kuzu
1. **Load entity CSVs from `.kineviz_graph/cache/db_input/`:**
   - Load all Person entities from `person.csv`
   - Load all Company entities from `company.csv`
2. **Create Note nodes** (one per source file with full content)
3. **Create Obsidian link relationships** (NOTE_TO_NOTE from `[[link]]` syntax)
4. **Load relationship CSVs from `.kineviz_graph/cache/db_input/`:**
   - Load Person-to-Person relationships from `person_to_person.csv`
   - Load Person-to-Company relationships from `person_to_company.csv`
   - Load Company-to-Company relationships from `company_to_company.csv`
5. **Create Kuzu nodes and relationships:**
   - Create Person, Company, and Note nodes
   - Create appropriate edge types based on relationship CSV
   - Create reference edges from entities to their source Note nodes
   - Create NOTE_TO_NOTE edges from Obsidian links
6. **Store database** in `.kineviz_graph/database/knowledge_graph.kz`

#### Legacy Support
- **Backward Compatibility:** Still support individual file CSVs in `cache/content/`
- **Migration Path:** Convert legacy CSVs from `cache/content/` to organized structure in `cache/db_input/`
- **Fallback:** Use legacy CSVs if organized CSVs don't exist

#### Deduplication Strategy
- **Entity ID:** Use entity label as ID (e.g., "John Smith", "Microsoft")
- **Note ID:** `{url}` (full path to markdown file)
- **Relationship Deduplication:** Sort entity pairs alphabetically to ensure uniqueness
- **Conflict Resolution:** Prefer most recent extraction

## Implementation Phases

### Phase 1: Core Infrastructure
- [x] Update database schema (Person, Company, Note nodes)
- [x] Implement basic CSV caching system
- [x] Create file change detection
- [ ] **NEW:** Implement organized CSV structure (`cache/db_input/` directory)
- [ ] **NEW:** Add relationship normalization and deduplication logic
- [ ] Build CSV to Kuzu conversion
- [x] Implement markdown content extraction

### Phase 2: LLM Integration
- [x] Update extraction prompts for Person/Company only
- [x] Implement entity relationship extraction (Person and Company only)
- [x] Add validation for Person/Company categories
- [ ] **NEW:** Add relationship reordering (COMPANY_TO_PERSON → PERSON_TO_COMPANY)
- [ ] **NEW:** Add entity pair deduplication logic
- [x] Filter out non-Person/Company entities during extraction

### Phase 3: Cache Management
- [x] Implement cache cleanup
- [ ] **NEW:** Entity CSV management (`cache/db_input/person.csv`, `cache/db_input/company.csv`)
- [ ] **NEW:** Relationship CSV management (`cache/db_input/person_to_person.csv`, etc.)
- [ ] **NEW:** Timestamp tracking (first_seen, last_seen)
- [ ] Add backup/restore functionality
- [ ] Create update monitoring
- [ ] Add error handling and recovery

### Phase 4: Migration & Testing
- [ ] **NEW:** Migrate existing individual CSVs from `cache/content/` to organized structure in `cache/db_input/`
- [ ] **NEW:** Test relationship normalization and deduplication
- [ ] Update command-line interface
- [ ] Add cache management commands
- [ ] Implement progress reporting
- [ ] Add validation and testing

## LLM Extraction Constraints

### Entity Categories (Only)
- **Person**: Individual people, employees, founders, executives
- **Company**: Organizations, businesses, institutions, startups

### Filtered Out
- **Concepts**: Technical terms, methodologies, technologies
- **Locations**: Cities, countries, addresses
- **Products**: Software, hardware, services
- **Events**: Meetings, conferences, launches
- **Other**: Any non-Person/Company entities

### Extraction Focus
- **Relationships**: Only between Person and Company entities
- **One-word summaries**: Simple relationship types
- **Direct connections**: Person-Person, Person-Company, Company-Company

### Content Processing
- **Full Text**: Store complete markdown content in Note nodes
- **Raw Format**: Preserve original markdown formatting
- **Reference**: Enable full document context for relationships
- **Search**: Allow content-based queries and searches

## Benefits

### Simplified Model
- **Reduced Complexity:** Only 2 node types, 2 relationship types
- **Clear Semantics:** Person/Company entities with direct relationships
- **Easy Querying:** Simple graph traversal patterns
- **Focused Extraction:** Only relevant business relationships

### Incremental Updates
- **Efficient Processing:** Only process changed files
- **Fast Updates:** CSV-based caching enables quick rebuilds
- **Audit Trail:** Timestamped extractions for debugging

### Scalability
- **Modular Design:** Separate extraction and graph building
- **Cache Management:** Automatic cleanup and optimization
- **Parallel Processing:** Independent file processing

## Example Usage

### Processing Individual Files
```bash
# Process a single markdown file
python main.py documents/john.md --update-cache
# Creates: cache/john_hash_2024-01-15T10-30-00Z.csv

# Process a folder of markdown files
python main.py documents/ --update-cache
# Creates: cache/john_hash_*.csv, mary_hash_*.csv, company_hash_*.csv
```

### Rebuilding Knowledge Graph
```bash
# Rebuild from all CSV files in cache
python main.py --rebuild-from-cache --db-path knowledge.kz
```

### Checking Cache Status
```bash
# Show cache status per file
python main.py --cache-status
```

### File-to-CSV Mapping Example
```
documents/
├── people/
│   ├── john.md     → cache/john_hash_2024-01-15T10-30-00Z.csv
│   └── mary.md     → cache/mary_hash_2024-01-15T11-15-00Z.csv
├── companies/
│   └── microsoft.md → cache/microsoft_hash_2024-01-15T12-00-00Z.csv
└── projects/
    └── team.md     → cache/team_hash_2024-01-15T13-45-00Z.csv
```

## Migration from Current Schema

### Data Transformation
1. **Extract entities** from current Observation/Entity nodes
2. **Map relationships** to simplified RELATED_TO format
3. **Create Note nodes** from Source nodes
4. **Generate initial CSV cache** from existing data

### Backward Compatibility
- Keep current schema as fallback
- Provide migration script
- Support both schemas during transition
