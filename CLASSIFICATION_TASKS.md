# Classification Task System Specification

## Overview

A system for running structured classification/extraction tasks on Obsidian notes, storing results in YAML frontmatter metadata. This enables automated enrichment of notes with structured data extracted by LLMs.

**Key Principles:**
- Tasks are reusable and configurable
- Task definitions stored in SQLite for easy CRUD operations
- Results are stored in note metadata (frontmatter)
- Idempotent execution (can re-run safely)
- Integration with existing `metadata_manager.py` and `llm_client.py`

---

## 1. Task Definition Schema

Each classification task is defined with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tag` | string | ✓ | Unique identifier (used as metadata key) |
| `prompt` | text | ✓ | LLM prompt for classification |
| `name` | string | | Human-readable name (defaults to tag) |
| `description` | text | | Task description |
| `model` | string | | LLM model override (defaults to config.yaml) |
| `output_type` | enum | | "object" \| "list" \| "text" \| "boolean" (default: "object") |
| `output_schema` | JSON | | JSON schema for structured output validation |
| `enabled` | boolean | | Whether task is active (default: true) |
| `created_at` | datetime | | Auto-generated timestamp |
| `updated_at` | datetime | | Auto-updated timestamp |

### Output Types

| Type | Description | Example Result |
|------|-------------|----------------|
| `object` | Structured JSON object | `{interests: ["tech", "health"], focus: "AI"}` |
| `list` | Array of items | `["Series A", "B2B SaaS", "Healthcare"]` |
| `text` | Free-form text | `"Focus on AI-powered solutions..."` |
| `boolean` | Yes/No classification | `true` or `false` |

---

## 2. Task Storage (SQLite Database)

Tasks are stored in SQLite database at `{vault_path}/.kineviz_graph/classification.db`

### Database Schema

```sql
-- Classification Tasks Table
CREATE TABLE IF NOT EXISTS classification_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT UNIQUE NOT NULL,              -- Unique identifier (e.g., "gxr_interests")
    name TEXT,                              -- Human-readable name
    description TEXT,                       -- Task description
    prompt TEXT NOT NULL,                   -- LLM prompt template
    model TEXT,                             -- Override model (null = use default)
    output_type TEXT DEFAULT 'object'       -- object | list | text | boolean
        CHECK(output_type IN ('object', 'list', 'text', 'boolean')),
    output_schema TEXT,                     -- JSON schema as string (nullable)
    enabled INTEGER DEFAULT 1,              -- 1 = enabled, 0 = disabled
    created_at REAL DEFAULT (julianday('now')),
    updated_at REAL DEFAULT (julianday('now'))
);

-- Classification Runs Table (tracks execution history)
CREATE TABLE IF NOT EXISTS classification_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES classification_tasks(id),
    note_path TEXT NOT NULL,                -- Relative path to note
    status TEXT DEFAULT 'pending'           -- pending | running | completed | failed
        CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    result TEXT,                            -- JSON result (nullable)
    error TEXT,                             -- Error message if failed
    model_used TEXT,                        -- Actual model used
    processing_time_ms INTEGER,             -- Time taken in milliseconds
    created_at REAL DEFAULT (julianday('now')),
    completed_at REAL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_tag ON classification_tasks(tag);
CREATE INDEX IF NOT EXISTS idx_tasks_enabled ON classification_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_runs_task_id ON classification_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_note_path ON classification_runs(note_path);
CREATE INDEX IF NOT EXISTS idx_runs_status ON classification_runs(status);
```

### Example Task Records

```sql
-- Insert example tasks
INSERT INTO classification_tasks (tag, name, description, prompt, output_type, output_schema) VALUES
(
    'gxr_interests',
    'Person Interests',
    'Extract professional and personal interests from person notes',
    'Analyze this person''s note and extract their interests.

Return a JSON object with:
- professional_interests: list of professional/career interests
- personal_interests: list of hobbies and personal interests  
- investment_focus: list of investment areas they focus on (if applicable)

If a category has no relevant information, return an empty list.',
    'object',
    '{"type": "object", "properties": {"professional_interests": {"type": "array", "items": {"type": "string"}}, "personal_interests": {"type": "array", "items": {"type": "string"}}, "investment_focus": {"type": "array", "items": {"type": "string"}}}, "required": ["professional_interests", "personal_interests", "investment_focus"]}'
),
(
    'gxr_is_active_investor',
    'Active Investor Check',
    'Determine if person is an active investor',
    'Based on this note, is this person currently an active investor?
Return true if they are actively making investments, false otherwise.',
    'boolean',
    NULL
),
(
    'gxr_key_relationships',
    'Key Relationships',
    'Extract most important relationships from note',
    'Extract the 3-5 most important professional relationships mentioned in this note.
Return as a list of names.',
    'list',
    NULL
);
```

---

## 3. Classification Results Storage

Results are stored in note frontmatter using the task's `tag` as the key:

### Example: Note before classification
```markdown
---
type: person
name: John Smith
---

John Smith is a partner at Sequoia Capital focusing on Series A investments...
```

### Example: Note after classification
```markdown
---
type: person
name: John Smith
gxr_interests:
  professional_interests:
    - Venture Capital
    - Technology Investing
    - Board Governance
  personal_interests:
    - Skiing
    - Wine Collecting
  investment_focus:
    - Series A
    - B2B SaaS
    - Enterprise Software
  _meta:
    classified_at: "2024-12-04T15:30:00Z"
    model: "qwen3:8b"
    task_version: "1.0"
gxr_is_active_investor: true
---

John Smith is a partner at Sequoia Capital focusing on Series A investments...
```

### Metadata Structure

Every classification result includes a `_meta` sub-object:

```yaml
gxr_interests:
  # ... actual classification results ...
  _meta:
    classified_at: "2024-12-04T15:30:00Z"  # ISO timestamp
    model: "qwen3:8b"                       # Model used
    processing_time_ms: 1250                # Time taken
    error: null                             # Error message if failed
```

### Handling Empty Results

If no relevant information is found, store empty result with metadata:

```yaml
gxr_interests:
  professional_interests: []
  personal_interests: []
  investment_focus: []
  _meta:
    classified_at: "2024-12-04T15:30:00Z"
    model: "qwen3:8b"
    note: "No interests found in note content"
```

---

## 4. CLI Interface

### 4.1 Task Management Commands (CRUD)

```bash
# List all tasks
uv run classification_task_manager.py list-tasks
uv run classification_task_manager.py list-tasks --enabled-only
uv run classification_task_manager.py list-tasks --format json

# Show task details
uv run classification_task_manager.py show-task gxr_interests

# Add new task
uv run classification_task_manager.py add-task \
  --tag "gxr_interests" \
  --name "Person Interests" \
  --prompt "Extract interests from this person note..." \
  --output-type "object" \
  --output-schema '{"type": "object", "properties": {...}}'

# Add task interactively (prompts for each field)
uv run classification_task_manager.py add-task --interactive

# Modify existing task
uv run classification_task_manager.py edit-task gxr_interests \
  --prompt "Updated prompt text..."
uv run classification_task_manager.py edit-task gxr_interests \
  --name "New Name" \
  --model "qwen3:14b"

# Enable/disable task
uv run classification_task_manager.py enable-task gxr_interests
uv run classification_task_manager.py disable-task gxr_interests

# Delete task
uv run classification_task_manager.py delete-task gxr_interests
uv run classification_task_manager.py delete-task gxr_interests --force  # No confirmation

# Import tasks from YAML (for migration/sharing)
uv run classification_task_manager.py import-tasks tasks.yaml

# Export tasks to YAML (for backup/sharing)
uv run classification_task_manager.py export-tasks --output tasks.yaml
```

### 4.2 Classification Execution Commands

```bash
# Classify a single note
uv run classification_task_manager.py run gxr_interests \
  --note "People/John Smith.md"

# Classify all notes in a folder
uv run classification_task_manager.py run gxr_interests \
  --folder "People/"

# Classify all notes in vault
uv run classification_task_manager.py run gxr_interests --all

# Only classify notes that haven't been classified yet
uv run classification_task_manager.py run gxr_interests \
  --all \
  --skip-existing

# Force re-classification (overwrite existing)
uv run classification_task_manager.py run gxr_interests \
  --all \
  --force

# Dry run (show what would be classified)
uv run classification_task_manager.py run gxr_interests \
  --all \
  --dry-run
```

### 4.3 Advanced Options

```bash
# Use specific model (override task default)
uv run classification_task_manager.py run gxr_interests \
  --all \
  --model "qwen3:14b"

# Filter by note metadata type
uv run classification_task_manager.py run gxr_interests \
  --all \
  --filter-type "person"

# Show classification status/stats
uv run classification_task_manager.py status gxr_interests

# Show run history
uv run classification_task_manager.py history gxr_interests --limit 20

# Export classification results to CSV
uv run classification_task_manager.py export-results gxr_interests \
  --output interests.csv

# Clear classification history for a task
uv run classification_task_manager.py clear-history gxr_interests
```

---

## 5. Implementation Architecture

### 5.1 File Structure

```
cli/
├── classification_task_manager.py   # Main CLI entry point
├── classification/
│   ├── __init__.py
│   ├── models.py                    # Pydantic models for Task, Result
│   ├── database.py                  # SQLite database operations
│   ├── classifier.py                # Core classification logic
│   └── result_storage.py            # Store results in note metadata
```

### 5.2 Core Classes

#### TaskDefinition (Pydantic Model)
```python
class TaskDefinition(BaseModel):
    id: Optional[int] = None
    tag: str                          # Unique identifier
    prompt: str                       # LLM prompt template
    name: Optional[str] = None        # Human-readable name
    description: Optional[str] = None
    model: Optional[str] = None       # Override default model
    output_type: Literal["object", "list", "text", "boolean"] = "object"
    output_schema: Optional[Dict] = None  # JSON schema for validation
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

#### TaskDatabase (SQLite Operations)
```python
class TaskDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Create tables if not exist"""
        pass
    
    # CRUD operations
    def create_task(self, task: TaskDefinition) -> int:
        """Create new task, return ID"""
        pass
    
    def get_task(self, tag: str) -> Optional[TaskDefinition]:
        """Get task by tag"""
        pass
    
    def get_all_tasks(self, enabled_only: bool = False) -> List[TaskDefinition]:
        """Get all tasks"""
        pass
    
    def update_task(self, tag: str, updates: Dict) -> bool:
        """Update task fields"""
        pass
    
    def delete_task(self, tag: str) -> bool:
        """Delete task by tag"""
        pass
    
    def enable_task(self, tag: str) -> bool:
        pass
    
    def disable_task(self, tag: str) -> bool:
        pass
    
    # Run history
    def record_run(self, task_id: int, note_path: str, status: str, 
                   result: Optional[str] = None, error: Optional[str] = None):
        pass
    
    def get_run_history(self, tag: str, limit: int = 100) -> List[Dict]:
        pass
    
    def get_classification_status(self, tag: str) -> Dict:
        """Get stats: total notes, classified, pending, failed"""
        pass
```

#### ClassificationResult (Pydantic Model)
```python
class ClassificationResult(BaseModel):
    tag: str
    result: Any                       # The actual classification result
    meta: ClassificationMeta

class ClassificationMeta(BaseModel):
    classified_at: datetime
    model: str
    processing_time_ms: int
    error: Optional[str] = None
```

#### Classifier (Main Class)
```python
class Classifier:
    def __init__(self, vault_path: Path, llm_client: LLMClient):
        self.vault_path = vault_path
        self.llm_client = llm_client
        self.task_db = TaskDatabase(vault_path / ".kineviz_graph" / "classification.db")
        self.metadata_manager = MetadataManager()
    
    async def classify_note(
        self, 
        task_tag: str, 
        note_path: Path,
        force: bool = False
    ) -> ClassificationResult:
        """Classify a single note with the specified task."""
        pass
    
    async def classify_folder(
        self,
        task_tag: str,
        folder_path: Path,
        skip_existing: bool = True
    ) -> List[ClassificationResult]:
        """Classify all notes in a folder."""
        pass
    
    def is_classified(self, note_path: Path, task_tag: str) -> bool:
        """Check if note already has classification for this task."""
        pass
```

### 5.3 Integration Points

| Component | Integration |
|-----------|-------------|
| `llm_client.py` | Use existing LLM client for classification requests |
| `metadata_manager.py` | Use for reading/writing frontmatter |
| `config.yaml` | Load default model settings |
| `file_tracker.py` | Reuse SQLite patterns, vault path detection |

### 5.4 LLM Prompt Construction

The classifier constructs prompts by combining:

1. **System prompt** (classification-specific)
2. **Task prompt** (from database)
3. **Note content** (the actual note to classify)
4. **Output format instructions** (based on output_type)

```python
def build_classification_prompt(task: TaskDefinition, note_content: str) -> List[Dict]:
    system = f"""You are a classification assistant. 
Analyze the provided note and extract structured information.

Output Format: {task.output_type}
{f"Schema: {json.dumps(task.output_schema)}" if task.output_schema else ""}

Return ONLY valid JSON, no explanation."""
    
    user = f"""{task.prompt}

=== NOTE CONTENT ===
{note_content}
=== END NOTE ===

Respond with JSON only."""
    
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
```

---

## 6. Error Handling

### 6.1 Error Types

| Error | Handling |
|-------|----------|
| Note not found | Skip with warning, record in run history |
| LLM timeout | Retry up to 3 times, then store error |
| Invalid JSON response | Attempt partial extraction, store error |
| Schema validation failed | Store raw result with validation error |
| Task not found | Exit with error message |
| Task disabled | Skip with warning |

### 6.2 Error Storage

Errors are stored in both:

1. **Note frontmatter** (in `_meta.error`):
```yaml
gxr_interests:
  _meta:
    classified_at: "2024-12-04T15:30:00Z"
    model: "qwen3:8b"
    error: "LLM returned invalid JSON: Unexpected token at position 234"
```

2. **classification_runs table**:
```sql
INSERT INTO classification_runs (task_id, note_path, status, error)
VALUES (1, 'People/John.md', 'failed', 'LLM returned invalid JSON...');
```

---

## 7. Example Use Cases

### Use Case 1: Enrich Person Notes with Interests

```bash
# Add the task
uv run classification_task_manager.py add-task \
  --tag "gxr_interests" \
  --name "Person Interests" \
  --prompt "Analyze this person's note and extract their professional and personal interests..." \
  --output-type "object"

# Run on all person notes (skip already classified)
uv run classification_task_manager.py run gxr_interests \
  --folder "People/" \
  --skip-existing

# Check status
uv run classification_task_manager.py status gxr_interests
# Output: 
#   Total notes: 50
#   Classified: 45
#   Pending: 3
#   Failed: 2
```

### Use Case 2: Tag Notes as Active/Inactive Investors

```bash
# Add boolean classification task
uv run classification_task_manager.py add-task \
  --tag "gxr_is_active_investor" \
  --prompt "Is this person currently an active investor? Return true or false." \
  --output-type "boolean"

# Run on all notes
uv run classification_task_manager.py run gxr_is_active_investor --all

# Export for analysis
uv run classification_task_manager.py export-results gxr_is_active_investor \
  --output active_investors.csv
```

### Use Case 3: Re-run After Prompt Improvement

```bash
# Update the prompt
uv run classification_task_manager.py edit-task gxr_interests \
  --prompt "Improved prompt with better instructions..."

# Re-run on all notes (force overwrite)
uv run classification_task_manager.py run gxr_interests --all --force

# View history
uv run classification_task_manager.py history gxr_interests --limit 10
```

---

## 8. Configuration

### 8.1 Default Settings (in config.yaml)

```yaml
classification:
  default_model: "qwen3:8b"
  timeout: 120
  retry_count: 3
  database: "classification.db"  # Relative to .kineviz_graph/
```

### 8.2 Database Location

Database is stored at: `{vault_path}/.kineviz_graph/classification.db`

This keeps classification data alongside other knowledge graph data.

---

## 9. Migration & Backup

### Import from YAML
```bash
# Import tasks from YAML file
uv run classification_task_manager.py import-tasks tasks.yaml
```

### Export to YAML
```bash
# Export all tasks to YAML (for backup or sharing)
uv run classification_task_manager.py export-tasks --output backup_tasks.yaml
```

### YAML Format (for import/export)
```yaml
tasks:
  - tag: "gxr_interests"
    name: "Person Interests"
    prompt: |
      Analyze this person's note...
    output_type: "object"
    output_schema:
      type: "object"
      properties:
        professional_interests:
          type: "array"
          items: { type: "string" }
    enabled: true
    
  - tag: "gxr_is_active_investor"
    name: "Active Investor Check"
    prompt: "Is this person an active investor?"
    output_type: "boolean"
    enabled: true
```

---

## 10. Future Enhancements

- [ ] Web UI for task management
- [ ] Scheduled/automated classification on new notes
- [ ] Classification confidence scores
- [ ] Multi-model ensemble classification
- [ ] Bulk re-classification on task update
- [ ] Integration with knowledge graph (store classifications as node properties)
- [ ] Task templates/presets for common classification patterns
- [ ] Classification versioning (track changes over time)
