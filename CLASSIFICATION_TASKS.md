# Classification Task System Specification

## Overview

A system for running structured classification/extraction tasks on Obsidian notes, storing results in YAML frontmatter metadata. This enables automated enrichment of notes with structured data extracted by LLMs.

**Key Principles:**
- Tasks are reusable and configurable
- Task definitions stored in SQLite for easy CRUD operations
- Results are stored as **flat values** in note metadata (frontmatter)
- Each task = one `gxr_xxx` key with a simple value (no nested objects)
- Lists stored as comma-separated strings (KuzuDB compatibility)
- Idempotent execution (can re-run safely)
- Integration with existing `metadata_manager.py` and `llm_client.py`

---

## 1. Task Definition Schema

Each classification task is defined with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tag` | string | ✓ | Unique identifier, must start with `gxr_` (used as metadata key) |
| `prompt` | text | ✓ | LLM prompt for classification |
| `name` | string | | Human-readable name (defaults to tag) |
| `description` | text | | Task description |
| `model` | string | | LLM model override (defaults to config.yaml) |
| `output_type` | enum | ✓ | "list" \| "text" \| "boolean" \| "number" |
| `enabled` | boolean | | Whether task is active (default: true) |
| `created_at` | datetime | | Auto-generated timestamp |
| `updated_at` | datetime | | Auto-updated timestamp |

### Output Types (Flat Values Only)

| Type | Description | Stored As | Example |
|------|-------------|-----------|---------|
| `list` | Multiple items | Comma-separated string | `"Series A, B2B SaaS, Healthcare"` |
| `text` | Free-form text | String | `"Focus on AI-powered solutions"` |
| `boolean` | Yes/No | Boolean | `true` or `false` |
| `number` | Numeric value | Number | `42` or `3.14` |

**Important:** No nested objects allowed. Each task produces exactly one flat value.

---

## 2. Task Storage (SQLite Database)

Tasks are stored in SQLite database at `{vault_path}/.kineviz_graph/classification.db`

### Database Schema

```sql
-- Classification Tasks Table
CREATE TABLE IF NOT EXISTS classification_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT UNIQUE NOT NULL,              -- Unique identifier (e.g., "gxr_professional_interests")
    name TEXT,                              -- Human-readable name
    description TEXT,                       -- Task description
    prompt TEXT NOT NULL,                   -- LLM prompt template
    model TEXT,                             -- Override model (null = use default)
    output_type TEXT NOT NULL               -- list | text | boolean | number
        CHECK(output_type IN ('list', 'text', 'boolean', 'number')),
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
    result TEXT,                            -- The classification result
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
-- Insert example tasks (each extracts ONE piece of information)
INSERT INTO classification_tasks (tag, name, description, prompt, output_type) VALUES

-- Professional interests (list)
(
    'gxr_professional_interests',
    'Professional Interests',
    'Extract professional/career interests',
    'Analyze this note and extract the person''s professional interests and career focus areas.
Return as a comma-separated list. Example: "Venture Capital, Technology, Healthcare"
If no professional interests found, return empty string.',
    'list'
),

-- Personal interests (list)
(
    'gxr_personal_interests',
    'Personal Interests', 
    'Extract hobbies and personal interests',
    'Analyze this note and extract the person''s personal interests, hobbies, and passions.
Return as a comma-separated list. Example: "Skiing, Wine Collecting, Travel"
If no personal interests found, return empty string.',
    'list'
),

-- Investment focus (list)
(
    'gxr_investment_focus',
    'Investment Focus',
    'Extract investment focus areas',
    'Analyze this note and extract what investment stages or sectors this person focuses on.
Return as a comma-separated list. Example: "Series A, B2B SaaS, Enterprise Software"
If not an investor or no focus areas found, return empty string.',
    'list'
),

-- Is active investor (boolean)
(
    'gxr_is_active_investor',
    'Active Investor Check',
    'Determine if person is an active investor',
    'Based on this note, is this person currently an active investor?
Return true if they are actively making investments, false otherwise.',
    'boolean'
),

-- Investment thesis (text)
(
    'gxr_investment_thesis',
    'Investment Thesis',
    'Extract investment thesis summary',
    'Analyze this note and summarize the investment thesis in one sentence.
If no investment thesis found, return empty string.',
    'text'
),

-- Years of experience (number)
(
    'gxr_years_experience',
    'Years of Experience',
    'Extract years of professional experience',
    'Based on this note, estimate the person''s years of professional experience.
Return a number. If cannot determine, return 0.',
    'number'
);
```

---

## 3. Classification Results Storage

Results are stored as **flat key-value pairs** in note frontmatter. Each task creates:
- One key: the task's `tag` (e.g., `gxr_professional_interests`)
- One value: the classification result (string, boolean, or number)

Optional metadata keys use the pattern `{tag}_at` for timestamp.

### Example: Note before classification
```markdown
---
type: person
name: John Smith
---

John Smith is a partner at Sequoia Capital focusing on Series A investments in B2B SaaS...
He enjoys skiing and wine collecting in his free time.
```

### Example: Note after classification
```markdown
---
type: person
name: John Smith
gxr_professional_interests: "Venture Capital, Technology Investing, Board Governance"
gxr_professional_interests_at: "2024-12-04T15:30:00Z"
gxr_personal_interests: "Skiing, Wine Collecting"
gxr_personal_interests_at: "2024-12-04T15:30:05Z"
gxr_investment_focus: "Series A, B2B SaaS, Enterprise Software"
gxr_investment_focus_at: "2024-12-04T15:30:10Z"
gxr_is_active_investor: true
gxr_is_active_investor_at: "2024-12-04T15:30:15Z"
gxr_investment_thesis: "Focus on early-stage B2B SaaS companies with strong product-market fit"
gxr_investment_thesis_at: "2024-12-04T15:30:20Z"
gxr_years_experience: 15
gxr_years_experience_at: "2024-12-04T15:30:25Z"
---

John Smith is a partner at Sequoia Capital focusing on Series A investments in B2B SaaS...
```

### Value Format by Type

| Output Type | Stored Format | Example |
|-------------|---------------|---------|
| `list` | Comma-separated string | `"Series A, B2B SaaS, Healthcare"` |
| `text` | Plain string | `"Focus on AI-powered healthcare solutions"` |
| `boolean` | YAML boolean | `true` or `false` |
| `number` | YAML number | `15` or `3.5` |

### Handling Empty Results

If no relevant information is found, store empty value:

```yaml
gxr_professional_interests: ""           # Empty list
gxr_professional_interests_at: "2024-12-04T15:30:00Z"
gxr_investment_thesis: ""                # Empty text
gxr_is_active_investor: false            # Default false for boolean
gxr_years_experience: 0                  # Zero for number
```

This indicates the classification was run but no data was found.

---

## 4. CLI Interface

### 4.1 Task Management Commands (CRUD)

```bash
# List all tasks
uv run classification_task_manager.py list-tasks
uv run classification_task_manager.py list-tasks --enabled-only

# Show task details
uv run classification_task_manager.py show-task gxr_professional_interests

# Add new task
uv run classification_task_manager.py add-task \
  --tag "gxr_professional_interests" \
  --name "Professional Interests" \
  --prompt "Extract professional interests as comma-separated list..." \
  --output-type "list"

# Add task interactively
uv run classification_task_manager.py add-task --interactive

# Edit existing task
uv run classification_task_manager.py edit-task gxr_professional_interests \
  --prompt "Updated prompt text..."

# Enable/disable task
uv run classification_task_manager.py enable-task gxr_professional_interests
uv run classification_task_manager.py disable-task gxr_professional_interests

# Delete task
uv run classification_task_manager.py delete-task gxr_professional_interests

# Import/export for backup
uv run classification_task_manager.py export-tasks --output tasks.yaml
uv run classification_task_manager.py import-tasks tasks.yaml
```

### 4.2 Classification Execution Commands

#### Target Selection (required - choose one)

| Option | Description |
|--------|-------------|
| `--note "path/to/note.md"` | Classify a single specific note |
| `--folder "path/"` | Classify all `.md` files under a folder (recursive) |

#### Run Behavior

| Option | Description |
|--------|-------------|
| (default) | Skip notes that already have the `gxr_xxx` key |
| `--force` | Run always, overwrite existing classification |

#### Examples

```bash
# ===== SINGLE NOTE =====

# Classify a single note (skip if already classified)
uv run classification_task_manager.py run gxr_professional_interests \
  --note "People/John Smith.md"

# Force re-classify a single note (overwrite existing)
uv run classification_task_manager.py run gxr_professional_interests \
  --note "People/John Smith.md" \
  --force

# Run multiple tasks on a single note
uv run classification_task_manager.py run \
  gxr_professional_interests \
  gxr_personal_interests \
  gxr_is_active_investor \
  --note "People/John Smith.md"

# ===== FOLDER =====

# Classify all notes in a folder (skip already classified)
uv run classification_task_manager.py run gxr_professional_interests \
  --folder "People/"

# Force re-classify all notes in a folder
uv run classification_task_manager.py run gxr_professional_interests \
  --folder "People/" \
  --force

# Run multiple tasks on a folder
uv run classification_task_manager.py run \
  gxr_professional_interests \
  gxr_is_active_investor \
  --folder "People/"

# ===== DRY RUN =====

# Preview what would be classified (no changes made)
uv run classification_task_manager.py run gxr_professional_interests \
  --folder "People/" \
  --dry-run
```

#### Behavior Summary

| Scenario | Default | With `--force` |
|----------|---------|----------------|
| Note has `gxr_xxx` key | SKIP | RUN (overwrite) |
| Note missing `gxr_xxx` key | RUN | RUN |

### 4.3 Status and History

```bash
# Show classification status
uv run classification_task_manager.py status gxr_professional_interests
# Output:
#   Task: gxr_professional_interests (Professional Interests)
#   Type: list
#   Total notes: 50
#   Classified: 45 (90%)
#   Missing: 5
#   Failed: 0

# Show run history
uv run classification_task_manager.py history gxr_professional_interests --limit 20

# Export results to CSV
uv run classification_task_manager.py export-results gxr_professional_interests \
  --output professional_interests.csv
```

---

## 5. Implementation Architecture

### 5.1 File Structure

```
cli/
├── classification_task_manager.py   # Main CLI entry point
├── classification/
│   ├── __init__.py
│   ├── models.py                    # Pydantic models
│   ├── database.py                  # SQLite operations
│   ├── classifier.py                # Core classification logic
│   └── result_storage.py            # Store results via metadata_manager
```

### 5.2 Core Classes

#### TaskDefinition (Pydantic Model)
```python
from enum import Enum
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class OutputType(str, Enum):
    LIST = "list"
    TEXT = "text"
    BOOLEAN = "boolean"
    NUMBER = "number"

class TaskDefinition(BaseModel):
    id: Optional[int] = None
    tag: str                          # Must start with "gxr_"
    prompt: str
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    output_type: OutputType
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('tag')
    def tag_must_start_with_gxr(cls, v):
        if not v.startswith('gxr_'):
            raise ValueError('tag must start with "gxr_"')
        return v
```

#### TaskDatabase
```python
class TaskDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()
    
    # CRUD
    def create_task(self, task: TaskDefinition) -> int
    def get_task(self, tag: str) -> Optional[TaskDefinition]
    def get_all_tasks(self, enabled_only: bool = False) -> List[TaskDefinition]
    def update_task(self, tag: str, updates: Dict) -> bool
    def delete_task(self, tag: str) -> bool
    def enable_task(self, tag: str) -> bool
    def disable_task(self, tag: str) -> bool
    
    # History
    def record_run(self, task_id: int, note_path: str, status: str, result: str = None)
    def get_run_history(self, tag: str, limit: int = 100) -> List[Dict]
    def get_status(self, tag: str) -> Dict
```

#### Classifier
```python
class Classifier:
    def __init__(self, vault_path: Path, llm_client: LLMClient):
        self.vault_path = vault_path
        self.llm_client = llm_client
        self.task_db = TaskDatabase(vault_path / ".kineviz_graph" / "classification.db")
    
    async def classify_note(self, task_tag: str, note_path: Path, force: bool = False) -> str:
        """Run classification task on a note, return result."""
        pass
    
    def is_classified(self, note_path: Path, task_tag: str) -> bool:
        """Check if note has this classification key."""
        pass
    
    def store_result(self, note_path: Path, task: TaskDefinition, result: str):
        """Store result in note frontmatter."""
        # Uses metadata_manager to set:
        #   gxr_xxx: <result>
        #   gxr_xxx_at: <timestamp>
        pass
```

### 5.3 LLM Prompt Construction

```python
def build_prompt(task: TaskDefinition, note_content: str) -> List[Dict]:
    type_instructions = {
        'list': 'Return a comma-separated list. Example: "item1, item2, item3". Return empty string if nothing found.',
        'text': 'Return a single text string. Return empty string if nothing found.',
        'boolean': 'Return exactly "true" or "false".',
        'number': 'Return a single number. Return 0 if cannot determine.'
    }
    
    system = f"""You are a classification assistant.
Analyze the note and extract the requested information.

Output format: {task.output_type.value}
{type_instructions[task.output_type.value]}

Return ONLY the result, no explanation."""
    
    user = f"""{task.prompt}

=== NOTE ===
{note_content}
=== END ==="""
    
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
```

### 5.4 Result Parsing

```python
def parse_result(raw: str, output_type: OutputType) -> Any:
    """Parse LLM output to correct type."""
    raw = raw.strip()
    
    if output_type == OutputType.LIST:
        # Already comma-separated string, just clean it
        return raw.strip('"\'')
    
    elif output_type == OutputType.TEXT:
        return raw.strip('"\'')
    
    elif output_type == OutputType.BOOLEAN:
        return raw.lower() in ('true', 'yes', '1')
    
    elif output_type == OutputType.NUMBER:
        try:
            if '.' in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return 0
```

---

## 6. Error Handling

| Error | Handling |
|-------|----------|
| Note not found | Skip, log warning |
| LLM timeout | Retry 3x, then record failure |
| Invalid output | Store as-is with error flag |
| Task not found | Exit with error |
| Task disabled | Skip with warning |

Errors are recorded in `classification_runs` table with `status='failed'` and `error` message.

---

## 7. Example Use Cases

### Use Case 1: Extract Professional Interests from People Folder

```bash
# Add task
uv run classification_task_manager.py add-task \
  --tag "gxr_professional_interests" \
  --name "Professional Interests" \
  --prompt "Extract professional interests as comma-separated list" \
  --output-type "list"

# Run on People folder (skips notes already classified)
uv run classification_task_manager.py run gxr_professional_interests \
  --folder "People/"

# Check status
uv run classification_task_manager.py status gxr_professional_interests
```

### Use Case 2: Boolean Classification on Single Note

```bash
# Add task
uv run classification_task_manager.py add-task \
  --tag "gxr_is_investor" \
  --prompt "Is this person an investor? Return true or false." \
  --output-type "boolean"

# Run on a single note
uv run classification_task_manager.py run gxr_is_investor \
  --note "People/John Smith.md"
```

### Use Case 3: Re-classify All Notes in a Folder

```bash
# Force re-run on all notes (overwrite existing)
uv run classification_task_manager.py run gxr_professional_interests \
  --folder "People/" \
  --force
```

### Use Case 4: Run Multiple Tasks on a Folder

```bash
# Run multiple tasks on all notes in folder
uv run classification_task_manager.py run \
  gxr_professional_interests \
  gxr_personal_interests \
  gxr_is_active_investor \
  --folder "People/"
```

---

## 8. Configuration

```yaml
# config.yaml
classification:
  default_model: "qwen3:8b"
  timeout: 120
  retry_count: 3
  database: "classification.db"  # Relative to .kineviz_graph/
  store_timestamp: true          # Whether to create gxr_xxx_at keys
```

---

## 9. Future Enhancements

- [ ] Web UI for task management
- [ ] Scheduled classification on new notes
- [ ] Confidence scores
- [ ] Task templates/presets
- [ ] Bulk operations (classify all tasks on all notes)
- [ ] Integration with knowledge graph node properties
