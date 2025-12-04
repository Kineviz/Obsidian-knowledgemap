# Classification Task System Specification

## Overview

A system for running structured classification/extraction tasks on Obsidian notes, storing results in YAML frontmatter metadata. This enables automated enrichment of notes with structured data extracted by LLMs.

**Key Principles:**
- Tasks are reusable and configurable
- Results are stored in note metadata (frontmatter)
- Idempotent execution (can re-run safely)
- Integration with existing `metadata_manager.py` and `llm_client.py`

---

## 1. Task Definition Schema

Each classification task is defined with the following structure:

```yaml
# Required fields
tag: "gxr_interests"              # Unique identifier (used as metadata key)
prompt: "Extract the main professional and personal interests of this person based on the note content"

# Optional fields
name: "Person Interests"          # Human-readable name (defaults to tag)
description: "Extract interests from person notes"
model: "qwen3:8b"                 # LLM model override (defaults to config.yaml)
output_type: "object"             # "object" | "list" | "text" | "boolean"
output_schema:                    # JSON schema for structured output
  type: "object"
  properties:
    professional_interests:
      type: "array"
      items: { type: "string" }
      description: "Professional areas of interest"
    personal_interests:
      type: "array"
      items: { type: "string" }
      description: "Personal hobbies and interests"
    investment_focus:
      type: "array"
      items: { type: "string" }
      description: "Investment focus areas"
```

### Output Types

| Type | Description | Example Result |
|------|-------------|----------------|
| `object` | Structured JSON object | `{interests: ["tech", "health"], focus: "AI"}` |
| `list` | Array of items | `["Series A", "B2B SaaS", "Healthcare"]` |
| `text` | Free-form text | `"Focus on AI-powered solutions..."` |
| `boolean` | Yes/No classification | `true` or `false` |

---

## 2. Task Storage

Tasks are stored in `classification_tasks.yaml` (in vault's `.kineviz_graph/` or project root):

```yaml
# classification_tasks.yaml

version: "1.0"

tasks:
  # Task 1: Extract person interests
  gxr_interests:
    name: "Person Interests"
    description: "Extract professional and personal interests from person notes"
    prompt: |
      Analyze this person's note and extract their interests.
      
      Return a JSON object with:
      - professional_interests: list of professional/career interests
      - personal_interests: list of hobbies and personal interests  
      - investment_focus: list of investment areas they focus on (if applicable)
      
      If a category has no relevant information, return an empty list.
    output_type: "object"
    output_schema:
      type: "object"
      properties:
        professional_interests:
          type: "array"
          items: { type: "string" }
        personal_interests:
          type: "array"
          items: { type: "string" }
        investment_focus:
          type: "array"
          items: { type: "string" }
      required: ["professional_interests", "personal_interests", "investment_focus"]

  # Task 2: Extract company investment thesis
  gxr_investment_thesis:
    name: "Investment Thesis"
    description: "Extract investment thesis from company/fund notes"
    prompt: |
      Analyze this company/fund note and extract their investment approach.
      
      Return a JSON object with:
      - thesis: One sentence summary of their investment thesis
      - focus_areas: List of sectors/areas they focus on
      - stage_preference: Investment stages (Seed, Series A, Growth, etc.)
      - geographic_focus: Geographic regions they invest in
    output_type: "object"
    output_schema:
      type: "object"
      properties:
        thesis:
          type: "string"
        focus_areas:
          type: "array"
          items: { type: "string" }
        stage_preference:
          type: "array"
          items: { type: "string" }
        geographic_focus:
          type: "array"
          items: { type: "string" }

  # Task 3: Simple boolean classification
  gxr_is_active_investor:
    name: "Active Investor Check"
    description: "Determine if person is an active investor"
    prompt: |
      Based on this note, is this person currently an active investor?
      Return true if they are actively making investments, false otherwise.
    output_type: "boolean"

  # Task 4: Extract key relationships (list)
  gxr_key_relationships:
    name: "Key Relationships"
    description: "Extract most important relationships from note"
    prompt: |
      Extract the 3-5 most important professional relationships mentioned in this note.
      Return as a list of names.
    output_type: "list"
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
    task_version: "1.0"                     # Task definition version
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

### 4.1 Task Management Commands

```bash
# List all defined tasks
uv run classification_task_manager.py list-tasks

# Show task details
uv run classification_task_manager.py show-task gxr_interests

# Add new task (interactive or via options)
uv run classification_task_manager.py add-task \
  --tag "gxr_interests" \
  --prompt "Extract interests from this person note" \
  --output-type "object"

# Modify existing task
uv run classification_task_manager.py modify-task gxr_interests \
  --prompt "New prompt text"

# Delete task
uv run classification_task_manager.py delete-task gxr_interests

# Validate task configuration
uv run classification_task_manager.py validate-tasks
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
uv run classification_task_manager.py run gxr_interests \
  --all

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

# Limit concurrency
uv run classification_task_manager.py run gxr_interests \
  --all \
  --max-concurrent 3

# Filter by note type (from existing metadata)
uv run classification_task_manager.py run gxr_interests \
  --all \
  --filter-type "person"

# Export results to CSV
uv run classification_task_manager.py export gxr_interests \
  --output interests.csv

# Show classification status/stats
uv run classification_task_manager.py status gxr_interests
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
│   ├── task_storage.py              # Load/save task definitions
│   ├── classifier.py                # Core classification logic
│   └── result_storage.py            # Store results in metadata
```

### 5.2 Core Classes

#### TaskDefinition (Pydantic Model)
```python
class TaskDefinition(BaseModel):
    tag: str                          # Unique identifier
    prompt: str                       # LLM prompt template
    name: Optional[str] = None        # Human-readable name
    description: Optional[str] = None
    model: Optional[str] = None       # Override default model
    output_type: Literal["object", "list", "text", "boolean"] = "object"
    output_schema: Optional[Dict] = None  # JSON schema for validation
    version: str = "1.0"
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
    task_version: str
    processing_time_ms: int
    error: Optional[str] = None
```

#### Classifier (Main Class)
```python
class Classifier:
    def __init__(self, vault_path: Path, llm_client: LLMClient):
        self.vault_path = vault_path
        self.llm_client = llm_client
        self.task_storage = TaskStorage(vault_path)
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
        skip_existing: bool = True,
        max_concurrent: int = 5
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
| `file_tracker.py` | Track which notes have been classified |

### 5.4 LLM Prompt Construction

The classifier constructs prompts by combining:

1. **System prompt** (classification-specific)
2. **Task prompt** (from task definition)
3. **Note content** (the actual note to classify)
4. **Output format instructions** (based on output_type)

```python
def build_classification_prompt(task: TaskDefinition, note_content: str) -> str:
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
| Note not found | Skip with warning |
| LLM timeout | Retry up to 3 times, then store error in metadata |
| Invalid JSON response | Attempt partial extraction, store error |
| Schema validation failed | Store raw result with validation error |
| Task not found | Exit with error message |

### 6.2 Error Storage

Errors are stored in the `_meta` field:

```yaml
gxr_interests:
  _meta:
    classified_at: "2024-12-04T15:30:00Z"
    model: "qwen3:8b"
    error: "LLM returned invalid JSON: Unexpected token at position 234"
    raw_response: "{ partial json..."
```

---

## 7. Example Use Cases

### Use Case 1: Enrich Person Notes with Interests

```bash
# Define task in classification_tasks.yaml (already done above)

# Run on all person notes
uv run classification_task_manager.py run gxr_interests \
  --folder "People/" \
  --skip-existing

# Check status
uv run classification_task_manager.py status gxr_interests
# Output: 45/50 notes classified, 5 skipped (already done)
```

### Use Case 2: Tag Notes as Active/Inactive Investors

```bash
# Boolean classification
uv run classification_task_manager.py run gxr_is_active_investor \
  --folder "People/" \
  --all

# Export for analysis
uv run classification_task_manager.py export gxr_is_active_investor \
  --output active_investors.csv
```

### Use Case 3: Re-run After Prompt Improvement

```bash
# Update the prompt
uv run classification_task_manager.py modify-task gxr_interests \
  --prompt "Improved prompt with better instructions..."

# Re-run on all notes (force overwrite)
uv run classification_task_manager.py run gxr_interests \
  --all \
  --force
```

---

## 8. Configuration

### 8.1 Default Settings (in config.yaml)

```yaml
classification:
  default_model: "qwen3:8b"
  max_concurrent: 5
  timeout: 120
  retry_count: 3
  tasks_file: "classification_tasks.yaml"  # Relative to vault
```

### 8.2 Task File Location

Tasks file is searched in order:
1. `{vault_path}/.kineviz_graph/classification_tasks.yaml`
2. `{project_root}/classification_tasks.yaml`
3. `{project_root}/config/classification_tasks.yaml`

---

## 9. Future Enhancements

- [ ] Web UI for task management
- [ ] Scheduled/automated classification on new notes
- [ ] Classification confidence scores
- [ ] Multi-model ensemble classification
- [ ] Classification history tracking
- [ ] Bulk re-classification on task update
- [ ] Integration with knowledge graph (store classifications as node properties)
