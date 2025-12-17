"""
Pydantic models for Classification Task System
"""

from enum import Enum
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Any, List
from datetime import datetime


class OutputType(str, Enum):
    """Supported output types for classification tasks"""
    LIST = "list"
    TEXT = "text"
    BOOLEAN = "boolean"
    NUMBER = "number"


class TaskType(str, Enum):
    """Task type: single-tag or multi-tag"""
    SINGLE = "single"
    MULTI = "multi"


class TagSchema(BaseModel):
    """Schema for a single tag in a multi-tag task"""
    tag: str
    output_type: OutputType
    name: Optional[str] = None
    description: Optional[str] = None
    
    @field_validator('tag')
    @classmethod
    def tag_must_start_with_gxr(cls, v: str) -> str:
        # Allow tags starting with "gxr_" (legacy) or "_" (system-generated metadata)
        if not (v.startswith('gxr_') or v.startswith('_')):
            raise ValueError('tag must start with "gxr_" or "_" (for system-generated metadata)')
        return v


class TaskDefinition(BaseModel):
    """Definition of a classification task"""
    id: Optional[int] = None
    tag: str                            # Must start with "gxr_" or "_" (for system-generated metadata)
    task_type: TaskType = TaskType.SINGLE  # NEW: single or multi
    prompt: str
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None         # Override model (null = use default)
    output_type: OutputType
    tag_schema: Optional[List[TagSchema]] = None  # NEW: For multi-tag tasks
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('tag')
    @classmethod
    def tag_must_start_with_gxr(cls, v: str) -> str:
        # Allow tags starting with "gxr_" (legacy) or "_" (system-generated metadata)
        if not (v.startswith('gxr_') or v.startswith('_')):
            raise ValueError('tag must start with "gxr_" or "_" (for system-generated metadata)')
        return v
    
    @model_validator(mode='after')
    def validate_task_type(self):
        """Validate task configuration based on type"""
        if self.task_type == TaskType.MULTI:
            if not self.tag_schema or len(self.tag_schema) == 0:
                raise ValueError('Multi-tag tasks must have tag_schema')
            # Validate all tags in schema start with gxr_ or _
            for tag_def in self.tag_schema:
                if not (tag_def.tag.startswith('gxr_') or tag_def.tag.startswith('_')):
                    raise ValueError(f'All tags in schema must start with "gxr_" or "_": {tag_def.tag}')
        elif self.task_type == TaskType.SINGLE:
            # Single-tag tasks don't need tag_schema
            if self.tag_schema:
                raise ValueError('Single-tag tasks should not have tag_schema')
        return self
    
    def get_display_name(self) -> str:
        """Get display name (name if set, otherwise tag)"""
        return self.name or self.tag


class ClassificationResult(BaseModel):
    """Result of a classification run"""
    task_tag: str
    note_path: str
    status: str                         # pending | running | completed | failed
    result: Optional[Any] = None        # The classification result
    error: Optional[str] = None         # Error message if failed
    model_used: Optional[str] = None    # Actual model used
    processing_time_ms: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

