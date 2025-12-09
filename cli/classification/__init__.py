"""
Classification Task System for Obsidian Notes

Provides structured classification/extraction tasks on notes with LLM support.
Results are stored in YAML frontmatter metadata.
"""

from .models import TaskDefinition, OutputType, TaskType, TagSchema, ClassificationResult
from .database import TaskDatabase
from .classifier import Classifier

__all__ = [
    'TaskDefinition',
    'OutputType',
    'TaskType',
    'TagSchema',
    'ClassificationResult',
    'TaskDatabase',
    'Classifier',
]

