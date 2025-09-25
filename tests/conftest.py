"""
Pytest configuration and fixtures for Knowledge Map Tool tests
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import os
import sys

# Add the cli directory to the Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))

@pytest.fixture
def temp_vault():
    """Create a temporary vault directory for testing"""
    temp_dir = tempfile.mkdtemp(prefix="test_vault_")
    vault_path = Path(temp_dir)
    
    # Create some test markdown files
    (vault_path / "test_note1.md").write_text("""---
title: Test Note 1
tags: [test, person]
resolves:
  - "Test Person"
  - "Test Company"
---

# Test Note 1

This is a test note about Test Person and Test Company.
""")
    
    (vault_path / "test_note2.md").write_text("""---
title: Test Note 2
tags: [test, company]
---

# Test Note 2

This is another test note about Test Company.
""")
    
    yield vault_path
    
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_database_path():
    """Create a temporary database path for testing"""
    temp_dir = tempfile.mkdtemp(prefix="test_db_")
    db_path = Path(temp_dir) / "test.kz"
    
    yield str(db_path)
    
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_relationships():
    """Sample relationship data for testing"""
    return [
        {
            "source_category": "Person",
            "source_label": "Test Person",
            "relationship": "works_at",
            "target_category": "Company", 
            "target_label": "Test Company",
            "source_file": "test_note1.md",
            "extracted_at": "2024-01-01T00:00:00Z"
        },
        {
            "source_category": "Company",
            "source_label": "Test Company",
            "relationship": "founded_by",
            "target_category": "Person",
            "target_label": "Test Person", 
            "source_file": "test_note1.md",
            "extracted_at": "2024-01-01T00:00:00Z"
        }
    ]
