"""
Unit tests for entity resolution functionality
"""
import pytest
from pathlib import Path
import sys

# Add cli directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))

from entity_resolution import EntityResolver

class TestEntityResolver:
    def test_parse_resolves_string_comma_separated(self):
        """Test parsing comma-separated resolves string"""
        resolver = EntityResolver(Path("/tmp"))
        
        # Test comma-separated
        result = resolver._parse_resolves_string("Person A, Person B, Company C")
        assert result == ["Person A", "Person B", "Company C"]
        
        # Test with spaces
        result = resolver._parse_resolves_string("Person A, Person B , Company C")
        assert result == ["Person A", "Person B", "Company C"]
    
    def test_parse_resolves_string_multiline(self):
        """Test parsing multiline resolves string"""
        resolver = EntityResolver(Path("/tmp"))
        
        multiline = """Person A
Person B
Company C"""
        result = resolver._parse_resolves_string(multiline)
        assert result == ["Person A", "Person B", "Company C"]
    
    def test_parse_resolves_list(self):
        """Test parsing resolves as list"""
        resolver = EntityResolver(Path("/tmp"))
        
        resolves_list = ["Person A", "Person B", "Company C"]
        result = resolver._parse_resolves_string(resolves_list)
        assert result == ["Person A", "Person B", "Company C"]
    
    def test_parse_resolves_empty(self):
        """Test parsing empty resolves"""
        resolver = EntityResolver(Path("/tmp"))
        
        # Empty string
        result = resolver._parse_resolves_string("")
        assert result == []
        
        # None
        result = resolver._parse_resolves_string(None)
        assert result == []
        
        # Empty list
        result = resolver._parse_resolves_string([])
        assert result == []
