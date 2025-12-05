"""
Pydantic models for Classification Task System
"""

from enum import Enum
from pydantic import BaseModel, field_validator
from typing import Optional, Any
from datetime import datetime


class OutputType(str, Enum):
    """Supported output types for classification tasks"""
    LIST = "list"
    TEXT = "text"
    BOOLEAN = "boolean"
    NUMBER = "number"


class TaskDefinition(BaseModel):
    """Definition of a classification task"""
    id: Optional[int] = None
    tag: str                            # Must start with "gxr_"
    prompt: str
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None         # Override model (null = use default)
    output_type: OutputType
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('tag')
    @classmethod
    def tag_must_start_with_gxr(cls, v: str) -> str:
        if not v.startswith('gxr_'):
            raise ValueError('tag must start with "gxr_"')
        return v
    
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

