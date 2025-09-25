# Simplified Schema Diagram

## Graph Model Visualization

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Entity      │    │   RELATED_TO    │    │     Entity      │
│                 │◄───┤                 ├───►│                 │
│ • id            │    │ • relationship  │    │ • id            │
│ • category      │    │                 │    │ • category      │
│ • label         │    └─────────────────┘    │ • label         │
└─────────────────┘                          └─────────────────┘
         │
         │ REFERENCE
         ▼
┌─────────────────┐
│      Note       │
│                 │
│ • id            │
│ • label         │
│ • url           │
│ • content       │
└─────────────────┘
```

## Processing Pipeline

```
Markdown Files (1:1)    CSV Cache (1:1)    Kuzu Database
      │                       │                    │
      ▼                       ▼                    ▼
  john.md ────────────► john_hash_2024-01-15T10-30-00Z.csv
  mary.md ────────────► mary_hash_2024-01-15T11-15-00Z.csv
  company.md ─────────► company_hash_2024-01-15T12-00-00Z.csv
```

## CSV Cache Structure

```
cache/
├── john_hash_2024-01-15T10-30-00Z.csv      (from john.md)
├── mary_hash_2024-01-15T11-15-00Z.csv      (from mary.md)
├── company_hash_2024-01-15T12-00-00Z.csv   (from company.md)
└── team_hash_2024-01-15T13-45-00Z.csv      (from team.md)
```

## One-to-One Mapping

- **Each markdown file** → **One CSV file**
- **File change detection** per individual file
- **Incremental updates** per file basis
- **Independent processing** of each source

## Entity Categories

- **Person**: Individual people
- **Company**: Organizations, businesses, institutions

## ID Generation Rules

### Entity IDs
- **Format**: `{category}-{label}`
- **Examples**: 
  - `Person-John Smith`
  - `Company-Microsoft`
  - `Person-Jane Doe`

### Note IDs, Labels, and Content
- **ID Format**: `{url}` (full path to markdown file)
- **Label Format**: `{filename}` (simplified filename without extension)
- **Content**: Full text content from markdown file
- **Examples**:
  - ID: `documents/people/john.md`, Label: `john`, Content: `"# John Smith\n\nJohn works at Microsoft..."`
  - ID: `projects/ai/company-profile.md`, Label: `company-profile`, Content: `"# Company Profile\n\nMicrosoft is a technology company..."`
  - ID: `nested/folder/structure/note.md`, Label: `note`, Content: `"# Note\n\nThis is the content..."`

## Relationship Types

- **works_at**: Person → Company
- **founded**: Person → Company  
- **acquired**: Company → Company
- **collaborates_with**: Company → Company
- **reports_to**: Person → Person
- **specializes_in**: Person/Company → Concept (if needed)
