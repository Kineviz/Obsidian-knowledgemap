# Multi-Tag Task Design Specification

## Overview

This document specifies the design for a hybrid classification task system that supports both:
- **Single-tag tasks** (current system): One task produces one `gxr_xxx` tag
- **Multi-tag tasks** (new feature): One task produces multiple `gxr_xxx` tags in a single LLM call

## Goals

1. **Efficiency**: Reduce LLM API calls for related extractions (e.g., VC analysis)
2. **Consistency**: Extract related fields atomically from the same model state
3. **Backward Compatibility**: Existing single-tag tasks continue to work unchanged
4. **Flexibility**: Users can choose single-tag or multi-tag based on their needs

---

## 1. Task Type System

### 1.1 Task Types

```python
class TaskType(str, Enum):
    SINGLE = "single"  # Current system: one tag per task
    MULTI = "multi"    # New: multiple tags per task
```

### 1.2 Task Definition Schema

#### Single-Tag Task (Current)
```python
TaskDefinition(
    tag="gxr_professional_interests",
    task_type="single",  # Default, can be omitted
    prompt="Extract professional interests...",
    output_type="list",
    # ... other fields
)
```

#### Multi-Tag Task (New)
```python
TaskDefinition(
    tag="gxr_vc_analysis",  # Parent identifier
    task_type="multi",
    prompt="Analyze this VC profile and extract...",
    tag_schema=[
        TagSchema(tag="gxr_investment_stage", output_type="list"),
        TagSchema(tag="gxr_investment_sector", output_type="list"),
        TagSchema(tag="gxr_investment_thesis", output_type="text"),
        TagSchema(tag="gxr_is_active_investor", output_type="boolean"),
    ],
    # ... other fields
)
```

---

## 2. Database Schema Changes

### 2.1 Updated `classification_tasks` Table

```sql
ALTER TABLE classification_tasks ADD COLUMN task_type TEXT DEFAULT 'single'
    CHECK(task_type IN ('single', 'multi'));

ALTER TABLE classification_tasks ADD COLUMN tag_schema TEXT;
-- JSON string storing array of TagSchema objects for multi-tag tasks
-- Example: '[{"tag": "gxr_stage", "output_type": "list"}, ...]'
```

### 2.2 New `tag_schema` Table (Alternative Approach)

**Option A: JSON Column (Simpler)**
- Store `tag_schema` as JSON text in `classification_tasks.tag_schema`
- Pros: Simple, no joins needed
- Cons: Less queryable, harder to validate

**Option B: Separate Table (More Normalized)**
```sql
CREATE TABLE classification_task_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES classification_tasks(id),
    tag TEXT NOT NULL,  -- e.g., "gxr_investment_stage"
    output_type TEXT NOT NULL,
    display_order INTEGER DEFAULT 0,
    UNIQUE(task_id, tag)
);
```
- Pros: Normalized, queryable, easier validation
- Cons: More complex queries, requires joins

**Recommendation: Start with Option A (JSON column) for simplicity, can migrate to Option B later if needed.**

### 2.3 Migration Strategy

```sql
-- Migration script
BEGIN TRANSACTION;

-- Add new columns with defaults
ALTER TABLE classification_tasks ADD COLUMN task_type TEXT DEFAULT 'single';
ALTER TABLE classification_tasks ADD COLUMN tag_schema TEXT;

-- Update existing tasks to explicitly set task_type
UPDATE classification_tasks SET task_type = 'single' WHERE task_type IS NULL;

-- Add check constraint
-- (SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we'll validate in application)

COMMIT;
```

---

## 3. Data Models

### 3.1 Updated Models

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class TaskType(str, Enum):
    SINGLE = "single"
    MULTI = "multi"

class TagSchema(BaseModel):
    """Schema for a single tag in a multi-tag task"""
    tag: str = Field(..., description="Tag name (must start with gxr_)")
    output_type: OutputType = Field(..., description="Output type for this tag")
    name: Optional[str] = Field(None, description="Display name for this tag")
    description: Optional[str] = Field(None, description="Description of what this tag represents")

class TaskDefinition(BaseModel):
    """Definition of a classification task"""
    id: Optional[int] = None
    tag: str  # Parent tag identifier
    task_type: TaskType = TaskType.SINGLE  # NEW
    prompt: str
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    output_type: OutputType  # For single-tag tasks, or primary type for multi-tag
    tag_schema: Optional[List[TagSchema]] = None  # NEW: For multi-tag tasks
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('tag')
    @classmethod
    def tag_must_start_with_gxr(cls, v: str) -> str:
        if not v.startswith('gxr_'):
            raise ValueError('tag must start with "gxr_"')
        return v
    
    @model_validator(mode='after')
    def validate_task_type(self):
        """Validate task configuration based on type"""
        if self.task_type == TaskType.MULTI:
            if not self.tag_schema or len(self.tag_schema) == 0:
                raise ValueError('Multi-tag tasks must have tag_schema')
            # Validate all tags in schema start with gxr_
            for tag_def in self.tag_schema:
                if not tag_def.tag.startswith('gxr_'):
                    raise ValueError(f'All tags in schema must start with "gxr_": {tag_def.tag}')
        elif self.task_type == TaskType.SINGLE:
            # Single-tag tasks don't need tag_schema
            if self.tag_schema:
                raise ValueError('Single-tag tasks should not have tag_schema')
        return self
```

### 3.2 Multi-Tag Result Model

```python
class MultiTagResult(BaseModel):
    """Result from a multi-tag classification task"""
    results: Dict[str, Any]  # tag -> value mapping
    # Example: {"gxr_investment_stage": "Series A, Series B", ...}
```

---

## 4. LLM Integration

### 4.1 Structured Output for Multi-Tag Tasks

For multi-tag tasks, we'll use structured outputs (JSON schema) to ensure reliable parsing. The prompt structure should:

1. **Provide clear taxonomy**: List all possible values for each tag category
2. **Set expectations**: Instruct LLM to only use evidence from text, avoid hallucination
3. **Define output format**: Specify exact JSON structure expected
4. **Include examples**: Show expected format (optional but helpful)

#### Example Prompt Structure (VC Analysis)

```
System: You are an expert VC researcher. Your job is to classify venture capital 
firms into standardized tags. Only use evidence from the text provided. 
Do not hallucinate missing details. If unclear, return empty list or "unknown".

User: Below is information about a VC firm.

Extract structured tags using this taxonomy:

Stages: Pre-Seed, Seed, Seed+, Series A, Series B, Growth, Late Stage, Multi-Stage
Sectors: AI/ML, LLMs, DevTools, Cloud/SaaS, Cybersecurity, Data/Analytics, 
         Bio/HealthTech, Fintech, Climate, Robotics, Consumer, GovTech, Deep Tech, etc.
Check Size: Micro, Small Seed, Large Seed, Series A Checks, Growth Checks
Geography: US-National, SF-Bay Area, NYC, EU/UK, Global, etc.
Firm Type: Operator-Led, Corporate VC, Family Office, Technical Partners, Impact
Behavioral Traits: Thesis-Driven, Conviction-Driven, Fast Decision Maker, 
                   Metrics-Driven, Founder-First

Return strict JSON:
{
  "results": {
    "gxr_vc_investment_stages": "...",
    "gxr_vc_sectors": "...",
    ...
  }
}

Here is the VC information:
[NOTE CONTENT]
```

#### Pydantic Model for LLM Response

```python
class MultiTagResponse(BaseModel):
    """Structured response from LLM for multi-tag tasks"""
    results: Dict[str, Any] = Field(
        description="Dictionary mapping tag names to their extracted values"
    )
```

#### Prompt Construction

```python
def _build_multi_tag_prompt(
    self, 
    task: TaskDefinition, 
    note_content: str
) -> List[Dict[str, str]]:
    """Build prompt for multi-tag classification"""
    
    # Build tag descriptions for prompt
    tag_descriptions = []
    for tag_schema in task.tag_schema:
        desc = f"- {tag_schema.tag}: {tag_schema.description or tag_schema.tag}"
        desc += f" (type: {tag_schema.output_type.value})"
        tag_descriptions.append(desc)
    
    system = f"""You are a classification assistant.
Analyze the note and extract multiple pieces of information.

You must return a JSON object with the following structure:
{{
    "results": {{
        {chr(10).join([f'        "{ts.tag}": <value>,' for ts in task.tag_schema])}
    }}
}}

Output format rules:
{self._get_output_format_rules(task.tag_schema)}

Return ONLY valid JSON, no explanation."""
    
    user = f"""{task.prompt}

=== NOTE ===
{note_content}
=== END ===

Extract the following information:
{chr(10).join(tag_descriptions)}"""
    
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]

def _get_output_format_rules(self, tag_schemas: List[TagSchema]) -> str:
    """Get output format rules for all tags"""
    rules = []
    for ts in tag_schemas:
        if ts.output_type == OutputType.LIST:
            rules.append(f'- {ts.tag}: Comma-separated list (e.g., "item1, item2")')
        elif ts.output_type == OutputType.TEXT:
            rules.append(f'- {ts.tag}: Text string')
        elif ts.output_type == OutputType.BOOLEAN:
            rules.append(f'- {ts.tag}: true or false')
        elif ts.output_type == OutputType.NUMBER:
            rules.append(f'- {ts.tag}: Number')
    return '\n'.join(rules)
```

### 4.2 LLM Client Integration

The LLM client should support structured outputs when available:

```python
# In classifier.py
if task.task_type == TaskType.MULTI:
    # Use structured output if supported
    response = await llm.generate(
        messages, 
        response_format=MultiTagResponse,  # Pydantic model for structured output
        skip_relationship_suffix=True
    )
    # Parse structured response
    multi_result = response.output_parsed  # If using OpenAI structured outputs
else:
    # Single-tag: use existing text parsing
    response = await llm.generate(messages, skip_relationship_suffix=True)
    result = self._parse_result(response.content, task.output_type)
```

**Note**: Not all LLM providers support structured outputs. We'll need:
1. Fallback to JSON parsing if structured outputs not available
2. Validation and error handling for malformed JSON

---

## 5. Classification Logic Changes

### 5.1 Updated `classify_note` Method

```python
async def classify_note(
    self, 
    task_tag: str, 
    note_path: str, 
    force: bool = False,
    dry_run: bool = False,
    store_timestamp: bool = False
) -> Tuple[bool, Optional[Any], Optional[str]]:
    """Classify a single note (supports both single and multi-tag tasks)"""
    
    task = self.task_db.get_task(task_tag)
    if not task:
        return False, None, f"Task not found: {task_tag}"
    
    if task.task_type == TaskType.MULTI:
        return await self._classify_note_multi(task, note_path, force, dry_run, store_timestamp)
    else:
        return await self._classify_note_single(task, note_path, force, dry_run, store_timestamp)
```

### 5.2 Multi-Tag Classification

```python
async def _classify_note_multi(
    self,
    task: TaskDefinition,
    note_path: str,
    force: bool,
    dry_run: bool,
    store_timestamp: bool
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Classify note with multi-tag task"""
    
    full_path = self._resolve_note_path(note_path)
    relative_path = str(full_path.relative_to(self.vault_path))
    
    # Check if already classified (all tags present)
    if not force:
        metadata = self._get_metadata(full_path)
        if metadata:
            all_tags_present = all(
                tag_schema.tag in metadata 
                for tag_schema in task.tag_schema
            )
            if all_tags_present:
                return True, None, "already_classified"
    
    if dry_run:
        return True, None, "dry_run"
    
    # Record run start
    run_id = self.task_db.record_run_start(task.id, relative_path)
    start_time = time.time()
    
    try:
        # Read note content
        note_content = self._read_note_content(full_path)
        if not note_content.strip():
            self.task_db.record_run_failed(run_id, "Note content is empty")
            return False, None, "Note content is empty"
        
        # Build prompt
        messages = self._build_multi_tag_prompt(task, note_content)
        
        # Get LLM response
        llm = self._get_llm_client()
        
        # Try structured output first, fallback to JSON parsing
        try:
            response = await llm.generate(
                messages,
                response_format=MultiTagResponse,  # If supported
                skip_relationship_suffix=True
            )
            if hasattr(response, 'output_parsed'):
                multi_result = response.output_parsed
            else:
                # Fallback: parse JSON manually
                multi_result = MultiTagResponse.model_validate_json(response.content)
        except Exception as e:
            # Fallback to manual JSON parsing
            import json
            try:
                parsed = json.loads(response.content)
                multi_result = MultiTagResponse(results=parsed.get('results', {}))
            except json.JSONDecodeError:
                self.task_db.record_run_failed(run_id, f"Invalid JSON response: {e}")
                return False, None, f"Invalid JSON response: {e}"
        
        if not response.success:
            self.task_db.record_run_failed(run_id, response.error or "LLM request failed")
            return False, None, response.error or "LLM request failed"
        
        # Validate all expected tags are present
        results = multi_result.results
        missing_tags = [
            ts.tag for ts in task.tag_schema 
            if ts.tag not in results
        ]
        if missing_tags:
            self.task_db.record_run_failed(
                run_id, 
                f"Missing tags in response: {', '.join(missing_tags)}"
            )
            return False, None, f"Missing tags in response: {', '.join(missing_tags)}"
        
        # Parse and validate each result
        parsed_results = {}
        for tag_schema in task.tag_schema:
            raw_value = results[tag_schema.tag]
            parsed_value = self._parse_result(str(raw_value), tag_schema.output_type)
            parsed_results[tag_schema.tag] = parsed_value
        
        # Store all tags in frontmatter
        for tag_schema in task.tag_schema:
            value = parsed_results[tag_schema.tag]
            self._store_result(full_path, tag_schema, value, store_timestamp=store_timestamp)
        
        # Record success (store JSON of all results)
        processing_time_ms = int((time.time() - start_time) * 1000)
        result_json = json.dumps(parsed_results)
        self.task_db.record_run_complete(
            run_id,
            result_json,
            response.model,
            processing_time_ms
        )
        
        console.print(f"[green]✓ Classified: {relative_path}[/green] → {len(parsed_results)} tags")
        return True, parsed_results, None
        
    except Exception as e:
        self.task_db.record_run_failed(run_id, str(e))
        console.print(f"[red]✗ Failed: {relative_path} - {e}[/red]")
        return False, None, str(e)
```

### 5.3 Helper Method for Storing Results

```python
def _store_result_multi(
    self, 
    note_path: Path, 
    tag_schema: TagSchema, 
    result: Any, 
    store_timestamp: bool = False
):
    """Store result for a single tag from multi-tag task"""
    self._add_metadata(note_path, tag_schema.tag, result)
    
    if store_timestamp:
        timestamp = datetime.now().isoformat()
        self._add_metadata(note_path, f"{tag_schema.tag}_at", timestamp)
```

---

## 6. API Changes

### 6.1 Task Creation/Update

```python
class TaskCreate(BaseModel):
    tag: str
    task_type: TaskType = TaskType.SINGLE  # NEW
    prompt: str
    name: Optional[str] = None
    description: Optional[str] = None
    output_type: str = "text"  # For single-tag or primary type
    tag_schema: Optional[List[Dict[str, Any]]] = None  # NEW: For multi-tag
    model: Optional[str] = None

class TagSchemaInput(BaseModel):
    """Input schema for tag in multi-tag task"""
    tag: str
    output_type: str
    name: Optional[str] = None
    description: Optional[str] = None
```

### 6.2 Task Response

```python
class TaskResponse(BaseModel):
    id: Optional[int]
    tag: str
    task_type: TaskType  # NEW
    name: Optional[str]
    description: Optional[str]
    prompt: str
    output_type: str
    tag_schema: Optional[List[TagSchema]] = None  # NEW
    model: Optional[str]
    enabled: bool
    created_at: Optional[str]
    updated_at: Optional[str]
```

---

## 7. UI Changes

### 7.1 Task Creation Form

Add UI elements for:
- Task type selector (Single / Multi)
- Conditional display:
  - Single: Show `output_type` selector (current)
  - Multi: Show `tag_schema` editor (list of tags with types)

### 7.2 Task Display

- Show task type badge
- For multi-tag tasks, show list of tags that will be generated
- Show which tags are already classified (for multi-tag tasks)

### 7.3 Progress Tracking

- Multi-tag tasks: Show progress for all tags being generated
- History: Show which tags were generated in each run

---

## 8. CLI Changes

### 8.1 Add Task Command

```bash
# Single-tag task (current)
uv run classification_task_manager.py add-task \
  --tag gxr_interests \
  --prompt "Extract interests" \
  --output-type list

# Multi-tag task (new)
uv run classification_task_manager.py add-task \
  --tag gxr_vc_analysis \
  --task-type multi \
  --prompt "Analyze VC profile" \
  --tag-schema '[
    {"tag": "gxr_investment_stage", "output_type": "list"},
    {"tag": "gxr_investment_sector", "output_type": "list"},
    {"tag": "gxr_is_active_investor", "output_type": "boolean"}
  ]'
```

### 8.2 Show Task Command

Display task type and tag schema for multi-tag tasks.

---

## 9. Example Use Cases

### 9.1 VC Analysis Task (Comprehensive Example)

This is a real-world example based on a comprehensive VC taxonomy for analyzing venture capital firms.

#### Task Definition

```python
TaskDefinition(
    tag="gxr_vc_analysis",
    task_type=TaskType.MULTI,
    name="VC Profile Analysis",
    description="Extract comprehensive VC investment profile with stages, sectors, check sizes, geography, firm characteristics, and behavioral traits",
    prompt="""You are an expert VC researcher. Analyze this venture capital firm profile and extract structured information.

Use only evidence from the text provided. Do not hallucinate missing details. If unclear, return empty list or "unknown".

Extract the following information:
1. Investment stages they focus on (Pre-Seed, Seed, Seed+, Series A, Series B, Growth, Late-Stage, Multi-Stage, Opportunity Fund)
2. Sectors/industries they invest in (AI/ML, LLMs, DevTools, Cloud/SaaS, Cybersecurity, Data/Analytics, Bio/HealthTech, Fintech, Climate, Robotics, Consumer, GovTech, Deep Tech, etc.)
3. Typical check size range (Micro-checks <$250k, Small Seed $250k-$1M, Large Seed $1M-$3M, Series A Checks $3M-$10M, Growth Checks $10M+)
4. Geographic focus (US-National, SF-Bay Area, NYC, Boston, EU/UK, DACH, Nordics, APAC, Global)
5. Firm characteristics (Technical Partners, Operator-Led Fund, Corporate VC, Family Office, Government/Sovereign Fund, Impact-Oriented, AI-Native Fund, Security-Focused Fund, Hard-Tech Thesis)""",
    tag_schema=[
        # Investment Stages
        TagSchema(
            tag="gxr_vc_investment_stages",
            output_type=OutputType.LIST,
            name="Investment Stages",
            description="Stages of investment focus: Pre-Seed, Seed, Seed+, Series A, Series B, Growth, Late-Stage, Multi-Stage, Opportunity Fund"
        ),
        
        # Sectors / Investment Interests
        TagSchema(
            tag="gxr_vc_sectors",
            output_type=OutputType.LIST,
            name="Investment Sectors",
            description="Sectors and industries: AI/ML, LLMs, DevTools, Cloud/SaaS, Cybersecurity, Data/Analytics, Bio/HealthTech, Fintech, Climate, Robotics, Consumer, GovTech, Deep Tech, Enterprise SaaS, Vertical AI, etc."
        ),
        
        # Check Size
        TagSchema(
            tag="gxr_vc_check_size",
            output_type=OutputType.TEXT,
            name="Check Size Range",
            description="Typical check size: Micro-checks (<$250k), Small Seed ($250k-$1M), Large Seed ($1M-$3M), Series A Checks ($3M-$10M), Growth Checks ($10M+)"
        ),
        
        # Geography
        TagSchema(
            tag="gxr_vc_geography",
            output_type=OutputType.LIST,
            name="Geographic Focus",
            description="Investment geography: US-National, SF-Bay Area, NYC, Boston, EU/UK, DACH, Nordics, APAC, Global"
        ),
        
        # Firm Characteristics
        TagSchema(
            tag="gxr_vc_firm_type",
            output_type=OutputType.LIST,
            name="Firm Characteristics",
            description="Firm type: Technical Partners, Operator-Led Fund, Corporate VC, Family Office, Government/Sovereign Fund, Impact-Oriented, AI-Native Fund, Security-Focused Fund, Hard-Tech Thesis"
        ),
    ],
    enabled=True
)
```

#### Expected JSON Response from LLM

```json
{
  "results": {
    "gxr_vc_investment_stages": "Seed, Series A, Series B",
    "gxr_vc_sectors": "AI/ML, DevTools, Enterprise SaaS, Data/Analytics",
    "gxr_vc_check_size": "Large Seed ($1M-$3M)",
    "gxr_vc_geography": "US-National, SF-Bay Area",
    "gxr_vc_firm_type": "Operator-Led Fund, Technical Partners"
  }
}
```

#### Resulting Frontmatter

```yaml
---
type: company
name: Example Capital
gxr_vc_investment_stages: "Seed, Series A, Series B"
gxr_vc_investment_stages_at: "2024-12-04T15:30:00Z"
gxr_vc_sectors: "AI/ML, DevTools, Enterprise SaaS, Data/Analytics"
gxr_vc_sectors_at: "2024-12-04T15:30:00Z"
gxr_vc_check_size: "Large Seed ($1M-$3M)"
gxr_vc_check_size_at: "2024-12-04T15:30:00Z"
gxr_vc_geography: "US-National, SF-Bay Area"
gxr_vc_geography_at: "2024-12-04T15:30:00Z"
gxr_vc_firm_type: "Operator-Led Fund, Technical Partners"
gxr_vc_firm_type_at: "2024-12-04T15:30:00Z"
---
```

#### Benefits of This Approach

1. **Comprehensive Coverage**: 5 tags extracted in one LLM call instead of 5 separate calls
2. **Consistency**: All tags derived from the same model state, ensuring coherence
3. **Efficiency**: ~80% reduction in API calls (5 calls → 1 call)
4. **Graph-Ready**: Tags are structured for easy clustering and relationship mapping in GraphXR/KuzuDB
5. **Taxonomy-Based**: Uses standardized categories that enable better graph analysis
6. **Simple & Focused**: Core tags that are most useful for VC analysis and matching


### 9.2 Person Profile Task

```python
TaskDefinition(
    tag="gxr_person_profile",
    task_type=TaskType.MULTI,
    name="Person Profile Extraction",
    prompt="Extract comprehensive person profile information",
    tag_schema=[
        TagSchema(tag="gxr_professional_interests", output_type=OutputType.LIST),
        TagSchema(tag="gxr_personal_interests", output_type=OutputType.LIST),
        TagSchema(tag="gxr_years_experience", output_type=OutputType.NUMBER),
        TagSchema(tag="gxr_current_role", output_type=OutputType.TEXT),
        TagSchema(tag="gxr_is_investor", output_type=OutputType.BOOLEAN),
    ]
)
```

---

## 10. Implementation Plan

### Phase 1: Database & Models
1. Add `task_type` and `tag_schema` columns to database
2. Update `TaskDefinition` model with validation
3. Create `TagSchema` model
4. Migration script for existing data

### Phase 2: Core Classification Logic
1. Update `classify_note` to handle both types
2. Implement `_classify_note_multi` method
3. Add prompt building for multi-tag tasks
4. Add JSON parsing and validation

### Phase 3: LLM Integration
1. Add structured output support (if available)
2. Add JSON fallback parsing
3. Error handling for malformed responses

### Phase 4: API Updates
1. Update task creation/update endpoints
2. Update task response models
3. Add validation for multi-tag tasks

### Phase 5: UI Updates
1. Add task type selector
2. Add tag schema editor
3. Update task display
4. Update progress tracking

### Phase 6: CLI Updates
1. Update add-task command
2. Update show-task command
3. Update export/import

### Phase 7: Testing & Documentation
1. Unit tests for multi-tag classification
2. Integration tests
3. Update documentation
4. Example tasks

---

## 11. Backward Compatibility

### 11.1 Existing Tasks
- All existing tasks default to `task_type="single"`
- No changes needed to existing task definitions
- Existing classification runs continue to work

### 11.2 Migration
- Database migration adds columns with safe defaults
- Application code handles both old and new formats
- No data loss or breaking changes

---

## 12. Error Handling

### 12.1 Partial Failures
- **Option A**: All-or-nothing (recommended)
  - If any tag fails validation, entire task fails
  - Ensures consistency
  
- **Option B**: Partial success
  - Store successfully parsed tags
  - Mark task as "partial" in history
  - More complex but more resilient

**Recommendation: Start with Option A, add Option B later if needed.**

### 12.2 JSON Parsing Errors
- Try structured output first
- Fallback to manual JSON parsing
- Validate all required tags present
- Clear error messages for missing/invalid tags

---

## 13. Performance Considerations

### 13.1 Efficiency Gains
- **Single-tag**: N notes × M tasks = N×M LLM calls
- **Multi-tag**: N notes × 1 task = N LLM calls (for M tags)
- **Savings**: (M-1) × N fewer calls

### 13.2 Trade-offs
- Larger prompts (more tokens)
- More complex parsing
- All tags succeed or fail together

---

## 14. Future Enhancements

1. **Tag Dependencies**: Some tags depend on others
2. **Conditional Tags**: Only extract certain tags based on note content
3. **Tag Validation Rules**: Custom validation per tag
4. **Tag Relationships**: Define relationships between tags
5. **Incremental Updates**: Update only changed tags in multi-tag task

---

## 15. Open Questions

1. **Should multi-tag tasks support partial updates?**
   - Currently: All-or-nothing
   - Future: Update only changed tags?

2. **How to handle tag conflicts?**
   - What if a tag exists in both single-tag and multi-tag task?
   - Recommendation: Multi-tag takes precedence, or error on conflict

3. **Tag schema versioning?**
   - What if we change tag schema after notes are classified?
   - Recommendation: Version tag schemas, re-classify on schema change

4. **Progress tracking for multi-tag?**
   - Show progress per tag or overall?
   - Recommendation: Overall progress, show tag-level in details

---

## 16. Success Criteria

1. ✅ Backward compatible with existing single-tag tasks
2. ✅ Multi-tag tasks generate all tags in one LLM call
3. ✅ All tags stored correctly in frontmatter
4. ✅ Error handling for malformed responses
5. ✅ UI supports creating and managing multi-tag tasks
6. ✅ CLI supports multi-tag task operations
7. ✅ Documentation updated with examples

---

## Appendix A: VC Analysis Tag Taxonomy Reference

### Complete Tag Categories

**A. Investment Stages**
- Pre-Seed, Seed, Seed+ / Pre-A, Series A, Series B, Growth (C–E), Late-Stage / Pre-IPO, Multi-Stage, Opportunity Fund

**B. Sectors / Investment Interests**
- AI/ML, LLM/Foundation Models, DevTools/Infra, Cloud/SaaS, Cybersecurity, Data/Analytics/BI, Vertical AI (finance, healthcare, law, etc.), Deep Tech/Frontier, Bio/HealthTech/MedTech, Fintech, Climate/Energy/Sustainability, Gaming/Metaverse, Robotics, Enterprise SaaS, GovTech/Defense/Dual Use, Consumer/Social, Industrial/Supply Chain

**C. Check Size**
- Micro-checks (<$250k), Small Seed ($250k–$1M), Large Seed ($1M–$3M), Series A Checks ($3M–$10M), Growth Checks ($10M+)

**D. Geography**
- US-National, SF-Bay Area, NYC, Boston, EU/UK, DACH, Nordics, APAC, Global

**E. Firm Characteristics**
- Technical Partners, Operator-Led Fund, Corporate VC, Family Office, Government/Sovereign Fund, Impact-Oriented, AI-Native Fund, Security-Focused Fund, Hard-Tech Thesis

### Example JSON Response

```json
{
  "results": {
    "gxr_vc_investment_stages": "Seed, Series A, Series B",
    "gxr_vc_sectors": "AI/ML, DevTools, Enterprise SaaS, Data/Analytics",
    "gxr_vc_check_size": "Large Seed ($1M-$3M)",
    "gxr_vc_geography": "US-National, SF-Bay Area",
    "gxr_vc_firm_type": "Operator-Led Fund, Technical Partners"
  }
}
```

## Appendix B: Example Frontmatter Result

### VC Analysis Task Result

```yaml
---
type: company
name: Example Capital
gxr_vc_investment_stages: "Seed, Series A, Series B"
gxr_vc_investment_stages_at: "2024-12-04T15:30:00Z"
gxr_vc_sectors: "AI/ML, DevTools, Enterprise SaaS, Data/Analytics"
gxr_vc_sectors_at: "2024-12-04T15:30:00Z"
gxr_vc_check_size: "Large Seed ($1M-$3M)"
gxr_vc_check_size_at: "2024-12-04T15:30:00Z"
gxr_vc_geography: "US-National, SF-Bay Area"
gxr_vc_geography_at: "2024-12-04T15:30:00Z"
gxr_vc_firm_type: "Operator-Led Fund, Technical Partners"
gxr_vc_firm_type_at: "2024-12-04T15:30:00Z"
---
```

### Simple Person Profile Example

```yaml
---
type: person
name: John Smith
gxr_investment_stage: "Series A, Series B"
gxr_investment_stage_at: "2024-12-04T15:30:00Z"
gxr_investment_sector: "B2B SaaS, Enterprise Software"
gxr_investment_sector_at: "2024-12-04T15:30:00Z"
gxr_is_active_investor: true
gxr_is_active_investor_at: "2024-12-04T15:30:00Z"
gxr_investment_thesis: "Focus on early-stage B2B SaaS companies with strong product-market fit"
gxr_investment_thesis_at: "2024-12-04T15:30:00Z"
---
```

