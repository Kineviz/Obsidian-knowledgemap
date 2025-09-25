"""
Integration tests for the Kuzu Neo4j server
"""
import pytest
import asyncio
import aiohttp
import time
from pathlib import Path
import sys

# Add cli directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))

class TestServerIntegration:
    @pytest.fixture
    async def server_session(self):
        """Create an aiohttp session for testing"""
        async with aiohttp.ClientSession() as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, server_session):
        """Test that the health endpoint responds correctly"""
        # Note: This test requires the server to be running
        # In a real test suite, you'd start/stop the server in fixtures
        try:
            async with server_session.get("http://localhost:7001/health") as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] == "healthy"
                assert "database" in data
        except aiohttp.ClientConnectorError:
            pytest.skip("Server not running - integration test requires server")
    
    @pytest.mark.asyncio
    async def test_basic_query(self, server_session):
        """Test a basic query to the server"""
        try:
            query_data = {
                "query": "MATCH (n) RETURN count(n) as total_nodes LIMIT 1"
            }
            
            async with server_session.post(
                "http://localhost:7001/kuzudb/kuzu_db",
                json=query_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] == 0
                assert "data" in data
        except aiohttp.ClientConnectorError:
            pytest.skip("Server not running - integration test requires server")
    
    @pytest.mark.asyncio
    async def test_query_validation(self, server_session):
        """Test that query validation works through the API"""
        try:
            # Test rejected query (too long)
            long_query = "MATCH (n) RETURN n " + "x" * 10000
            query_data = {"query": long_query}
            
            async with server_session.post(
                "http://localhost:7001/kuzudb/kuzu_db",
                json=query_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] != 0  # Should be an error
                assert "too long" in data["message"].lower()
        except aiohttp.ClientConnectorError:
            pytest.skip("Server not running - integration test requires server")
