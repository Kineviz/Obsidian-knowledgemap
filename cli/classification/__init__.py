"""
Classification Task System for Obsidian Notes

Provides structured classification/extraction tasks on notes with LLM support.
Results are stored in YAML frontmatter metadata.
"""

from .models import TaskDefinition, OutputType, ClassificationResult
from .database import TaskDatabase
from .classifier import Classifier

__all__ = [
    'TaskDefinition',
    'OutputType', 
    'ClassificationResult',
    'TaskDatabase',
    'Classifier',
]

