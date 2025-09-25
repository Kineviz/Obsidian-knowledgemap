"""
Unit tests for query validation functionality
"""
import pytest
from pathlib import Path
import sys

# Add cli directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))

from kuzu_neo4j_server import KuzuQueryProcessor

class TestQueryValidation:
    def setup_method(self):
        """Set up test instance"""
        self.processor = KuzuQueryProcessor("/tmp/test_db")
    
    def test_empty_query_rejection(self):
        """Test that empty queries are rejected"""
        valid, message = self.processor.validate_query("")
        assert not valid
        assert "empty" in message.lower()
        
        valid, message = self.processor.validate_query("   ")
        assert not valid
        assert "empty" in message.lower()
    
    def test_long_query_rejection(self):
        """Test that very long queries are rejected"""
        long_query = "MATCH (n) RETURN n " + "x" * 10000
        valid, message = self.processor.validate_query(long_query)
        assert not valid
        assert "too long" in message.lower()
    
    def test_dangerous_patterns_rejection(self):
        """Test that dangerous patterns are rejected"""
        dangerous_queries = [
            "DROP DATABASE test",
            "DELETE DATABASE test", 
            "SHUTDOWN",
            "KILL PROCESS",
            "TERMINATE"
        ]
        
        for query in dangerous_queries:
            valid, message = self.processor.validate_query(query)
            assert not valid
            assert "dangerous" in message.lower()
    
    def test_high_skip_rejection(self):
        """Test that high SKIP values are rejected"""
        high_skip_query = "MATCH (n) RETURN n SKIP 15000 LIMIT 100"
        valid, message = self.processor.validate_query(high_skip_query)
        assert not valid
        assert "SKIP value too high" in message
    
    def test_high_skip_warning(self):
        """Test that medium SKIP values trigger warnings but are allowed"""
        medium_skip_query = "MATCH (n) RETURN n SKIP 7500 LIMIT 100"
        valid, message = self.processor.validate_query(medium_skip_query)
        assert valid
        assert message == "Query is valid"
    
    def test_valid_queries(self):
        """Test that valid queries pass validation"""
        valid_queries = [
            "MATCH (n) RETURN n LIMIT 10",
            "MATCH (n)-[r]->(m) RETURN n, r, m",
            "MATCH (n) WHERE n.id = 'test' RETURN n",
            "MATCH (n) RETURN n SKIP 100 LIMIT 50",
            "MATCH (n) RETURN count(n) as total"
        ]
        
        for query in valid_queries:
            valid, message = self.processor.validate_query(query)
            assert valid, f"Query should be valid: {query}"
            assert message == "Query is valid"
