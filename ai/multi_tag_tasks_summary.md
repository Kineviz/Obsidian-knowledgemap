# Multi-Tag Tasks - Design Summary

## Quick Overview

**Goal**: Support both single-tag and multi-tag classification tasks in a hybrid system.

- **Single-tag** (current): One task → One `gxr_xxx` tag
- **Multi-tag** (new): One task → Multiple `gxr_xxx` tags in one LLM call

## Key Design Decisions

### 1. Database Schema
- Add `task_type` column: `'single'` or `'multi'` (default: `'single'`)
- Add `tag_schema` column: JSON string storing array of tag definitions
- **Migration**: Safe, backward compatible (existing tasks default to `'single'`)

### 2. Data Models
```python
class TaskType(str, Enum):
    SINGLE = "single"
    MULTI = "multi"

class TagSchema(BaseModel):
    tag: str  # e.g., "gxr_investment_stage"
    output_type: OutputType  # list, text, boolean, number
    name: Optional[str] = None
    description: Optional[str] = None

class TaskDefinition(BaseModel):
    # ... existing fields ...
    task_type: TaskType = TaskType.SINGLE  # NEW
    tag_schema: Optional[List[TagSchema]] = None  # NEW (for multi-tag)
```

### 3. LLM Integration
- Use structured outputs (JSON) for multi-tag tasks
- Fallback to manual JSON parsing if structured outputs not available
- Validate all required tags are present in response

### 4. Classification Flow

**Single-tag** (unchanged):
1. Build prompt → Call LLM → Parse text → Store one tag

**Multi-tag** (new):
1. Build prompt with all tag requirements
2. Call LLM with JSON response format
3. Parse JSON response
4. Validate all tags present
5. Parse each tag value according to its output_type
6. Store all tags in frontmatter atomically

### 5. Example: VC Analysis Task (Comprehensive)

Real-world example with 8 tags extracted in one call:

```python
TaskDefinition(
    tag="gxr_vc_analysis",
    task_type=TaskType.MULTI,
    prompt="[Comprehensive VC analysis prompt with taxonomy]",
    tag_schema=[
        TagSchema(tag="gxr_vc_investment_stages", output_type="list"),
        TagSchema(tag="gxr_vc_sectors", output_type="list"),
        TagSchema(tag="gxr_vc_check_size", output_type="text"),
        TagSchema(tag="gxr_vc_geography", output_type="list"),
        TagSchema(tag="gxr_vc_firm_type", output_type="list"),
        TagSchema(tag="gxr_vc_behavioral_traits", output_type="list"),
        TagSchema(tag="gxr_vc_investment_thesis", output_type="text"),
        TagSchema(tag="gxr_vc_is_active", output_type="boolean"),
    ]
)
```

**Result**: One LLM call generates all 8 tags simultaneously.

**Tag Categories**:
- Investment Stages (Pre-Seed, Seed, Series A, etc.)
- Sectors (AI/ML, DevTools, SaaS, etc.)
- Check Size (Micro, Small Seed, Large Seed, etc.)
- Geography (US-National, SF-Bay Area, EU/UK, etc.)
- Firm Type (Operator-Led, Corporate VC, Technical Partners, etc.)
- Behavioral Traits (Thesis-Driven, Founder-First, etc.)
- Investment Thesis (text summary)
- Active Status (boolean)

See full example in `ai/multi_tag_tasks_design.md` section 9.1.

## Benefits

1. **Efficiency**: N×M → N calls (for M related tags)
2. **Consistency**: All tags from same model state
3. **Atomicity**: All tags succeed or fail together
4. **Backward Compatible**: Existing tasks unchanged

## Implementation Phases

1. **Phase 1**: Database & Models (schema changes, validation)
2. **Phase 2**: Core Logic (multi-tag classification)
3. **Phase 3**: LLM Integration (structured outputs)
4. **Phase 4**: API Updates (endpoints, validation)
5. **Phase 5**: UI Updates (task creation, display)
6. **Phase 6**: CLI Updates (commands)
7. **Phase 7**: Testing & Docs

## Open Questions

1. Partial failures: All-or-nothing vs partial success?
2. Tag conflicts: What if tag exists in both single and multi-tag task?
3. Schema versioning: How to handle schema changes after classification?

## Files to Modify

- `cli/classification/models.py` - Add TaskType, TagSchema
- `cli/classification/database.py` - Schema migration, CRUD updates
- `cli/classification/classifier.py` - Multi-tag classification logic
- `cli/classification_server.py` - API updates
- `cli/classification_ui.html` - UI for multi-tag tasks
- `cli/classification_task_manager.py` - CLI updates

## See Also

Full design document: `ai/multi_tag_tasks_design.md`

