#!/usr/bin/env python3
"""
Server Load Testing Script
Sends multiple queries one by one to test server stability and identify potential crash patterns.
"""

import asyncio
import aiohttp
import time
import json
import random
from datetime import datetime
from typing import List, Dict, Any
import sys

class ServerLoadTester:
    def __init__(self, server_url: str = "http://localhost:7001", database: str = "kuzu_db"):
        self.server_url = server_url
        self.database = database
        self.base_url = f"{server_url}/kuzudb/{database}"
        self.results = []
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_test_queries(self) -> List[Dict[str, Any]]:
        """Generate various types of test queries to stress test the server"""
        return [
            # Basic queries
            {"name": "count_nodes", "query": "MATCH (n) RETURN count(n) as total_nodes LIMIT 1"},
            {"name": "count_relationships", "query": "MATCH ()-[r]->() RETURN count(r) as total_relationships LIMIT 1"},
            {"name": "list_node_types", "query": "MATCH (n) RETURN DISTINCT labels(n) as node_types LIMIT 10"},
            {"name": "list_relationship_types", "query": "MATCH ()-[r]->() RETURN DISTINCT type(r) as rel_types LIMIT 10"},
            
            # Complex queries
            {"name": "complex_graph_query", "query": """
                MATCH (n)-[r:NOTE_TO_NOTE|PERSON_REFERENCE|COMPANY_REFERENCE]-(m)  
                WHERE id(n) IN ([internal_id(2, 0),internal_id(2, 1),internal_id(2, 2)])
                RETURN n,r,m SKIP 0 LIMIT 100
            """},
            {"name": "large_skip_query", "query": """
                MATCH (n)-[r:NOTE_TO_NOTE|PERSON_REFERENCE|COMPANY_REFERENCE]-(m)  
                WHERE id(n) IN ([internal_id(2, 0),internal_id(2, 1),internal_id(2, 2),internal_id(2, 3),internal_id(2, 4),internal_id(2, 5)])
                RETURN n,r,m SKIP 1000 LIMIT 1000
            """},
            {"name": "pattern_matching", "query": "MATCH (p:Person)-[r]->(c:Company) RETURN p,r,c LIMIT 50"},
            {"name": "aggregation_query", "query": "MATCH (n) RETURN labels(n) as type, count(n) as count GROUP BY labels(n) LIMIT 20"},
            
            # Edge case queries
            {"name": "empty_result", "query": "MATCH (n) WHERE n.nonexistent = 'value' RETURN n LIMIT 1"},
            {"name": "large_limit", "query": "MATCH (n) RETURN n LIMIT 10000"},
            {"name": "deep_traversal", "query": "MATCH (n)-[r*1..3]-(m) RETURN n,r,m LIMIT 100"},
            {"name": "property_filter", "query": "MATCH (n) WHERE n.id IS NOT NULL RETURN n.id LIMIT 100"},
            
            # Stress test queries
            {"name": "multiple_joins", "query": """
                MATCH (p:Person)-[r1]->(c:Company)-[r2]->(n:Note)
                RETURN p, r1, c, r2, n LIMIT 50
            """},
            {"name": "complex_where", "query": """
                MATCH (n) 
                WHERE n.id IS NOT NULL AND n.label IS NOT NULL
                RETURN n.id, n.label, labels(n) LIMIT 100
            """},
            {"name": "order_by_query", "query": "MATCH (n) RETURN n ORDER BY n.id LIMIT 100"},
            {"name": "distinct_query", "query": "MATCH (n) RETURN DISTINCT n.id LIMIT 100"},
            
            # Potential problem queries
            {"name": "very_long_query", "query": "MATCH " + "()-[r]->() " * 50 + "RETURN count(r) LIMIT 1"},
            {"name": "nested_query", "query": "MATCH (n) WHERE n.id IN (SELECT id FROM (MATCH (m) RETURN m.id LIMIT 10)) RETURN n LIMIT 10"},
            {"name": "regex_query", "query": "MATCH (n) WHERE n.label =~ '.*[A-Z].*' RETURN n LIMIT 10"},
            {"name": "range_query", "query": "MATCH (n) WHERE n.id >= 'a' AND n.id <= 'z' RETURN n LIMIT 10"},
        ]
    
    async def send_query(self, query_info: Dict[str, Any], delay: float = 0.1) -> Dict[str, Any]:
        """Send a single query to the server"""
        query_name = query_info["name"]
        query = query_info["query"]
        
        start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        print(f"🧪 Testing [{timestamp}] - {query_name}")
        print(f"   Query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
        try:
            payload = {"query": query}
            
            async with self.session.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_time = time.time() - start_time
                response_text = await response.text()
                
                result = {
                    "name": query_name,
                    "query": query,
                    "timestamp": timestamp,
                    "response_time": response_time,
                    "status_code": response.status,
                    "success": response.status == 200,
                    "response_size": len(response_text),
                    "error": None
                }
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        result["data_status"] = response_data.get("status", "unknown")
                        result["has_data"] = bool(response_data.get("data", {}).get("data"))
                        print(f"   ✅ Success - {response_time:.3f}s - Status: {response.status}")
                    except json.JSONDecodeError:
                        result["error"] = "Invalid JSON response"
                        print(f"   ⚠️  Invalid JSON - {response_time:.3f}s - Status: {response.status}")
                else:
                    result["error"] = f"HTTP {response.status}: {response_text[:200]}"
                    print(f"   ❌ Error - {response_time:.3f}s - Status: {response.status}")
                
                # Add delay between queries
                if delay > 0:
                    await asyncio.sleep(delay)
                
                return result
                
        except asyncio.TimeoutError:
            result = {
                "name": query_name,
                "query": query,
                "timestamp": timestamp,
                "response_time": time.time() - start_time,
                "status_code": 0,
                "success": False,
                "response_size": 0,
                "error": "Timeout after 30 seconds"
            }
            print(f"   ⏰ Timeout - {result['response_time']:.3f}s")
            return result
            
        except Exception as e:
            result = {
                "name": query_name,
                "query": query,
                "timestamp": timestamp,
                "response_time": time.time() - start_time,
                "status_code": 0,
                "success": False,
                "response_size": 0,
                "error": str(e)
            }
            print(f"   💥 Exception - {result['response_time']:.3f}s - {e}")
            return result
    
    async def run_load_test(self, num_iterations: int = 3, delay_between_queries: float = 0.1, delay_between_iterations: float = 1.0):
        """Run the complete load test"""
        print(f"🚀 Starting Server Load Test")
        print(f"   Server: {self.server_url}")
        print(f"   Database: {self.database}")
        print(f"   Iterations: {num_iterations}")
        print(f"   Delay between queries: {delay_between_queries}s")
        print(f"   Delay between iterations: {delay_between_iterations}s")
        print("=" * 80)
        
        test_queries = self.get_test_queries()
        all_results = []
        
        for iteration in range(num_iterations):
            print(f"\n🔄 Iteration {iteration + 1}/{num_iterations}")
            print("-" * 40)
            
            iteration_results = []
            for i, query_info in enumerate(test_queries):
                print(f"\n[{i+1}/{len(test_queries)}] ", end="")
                result = await self.send_query(query_info, delay_between_queries)
                iteration_results.append(result)
                all_results.append(result)
                
                # Check if server is still responding
                if not result["success"] and "Timeout" in str(result.get("error", "")):
                    print(f"\n⚠️  Server appears to be unresponsive. Stopping test.")
                    break
            
            if iteration < num_iterations - 1:
                print(f"\n⏳ Waiting {delay_between_iterations}s before next iteration...")
                await asyncio.sleep(delay_between_iterations)
        
        self.results = all_results
        return all_results
    
    def print_summary(self):
        """Print a summary of the test results"""
        if not self.results:
            print("No results to summarize.")
            return
        
        total_queries = len(self.results)
        successful_queries = sum(1 for r in self.results if r["success"])
        failed_queries = total_queries - successful_queries
        
        print("\n" + "=" * 80)
        print("📊 LOAD TEST SUMMARY")
        print("=" * 80)
        print(f"Total queries: {total_queries}")
        print(f"Successful: {successful_queries} ({successful_queries/total_queries*100:.1f}%)")
        print(f"Failed: {failed_queries} ({failed_queries/total_queries*100:.1f}%)")
        
        if self.results:
            response_times = [r["response_time"] for r in self.results if r["success"]]
            if response_times:
                print(f"Average response time: {sum(response_times)/len(response_times):.3f}s")
                print(f"Min response time: {min(response_times):.3f}s")
                print(f"Max response time: {max(response_times):.3f}s")
        
        # Show failed queries
        failed_results = [r for r in self.results if not r["success"]]
        if failed_results:
            print(f"\n❌ FAILED QUERIES:")
            for result in failed_results:
                print(f"   • {result['name']}: {result.get('error', 'Unknown error')}")
        
        # Show slow queries
        slow_results = [r for r in self.results if r["success"] and r["response_time"] > 5.0]
        if slow_results:
            print(f"\n🐌 SLOW QUERIES (>5s):")
            for result in slow_results:
                print(f"   • {result['name']}: {result['response_time']:.3f}s")

async def main():
    """Main function to run the load test"""
    server_url = "http://localhost:7001"
    database = "kuzu_db"
    
    # Check if server is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{server_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    print(f"❌ Server health check failed: {response.status}")
                    return
    except Exception as e:
        print(f"❌ Cannot connect to server at {server_url}: {e}")
        print("Make sure the server is running with: uv run step4_monitor.py")
        return
    
    print("✅ Server is running, starting load test...")
    
    async with ServerLoadTester(server_url, database) as tester:
        results = await tester.run_load_test(
            num_iterations=2,  # Run each query set twice
            delay_between_queries=0.2,  # 200ms between queries
            delay_between_iterations=2.0  # 2s between iterations
        )
        tester.print_summary()

if __name__ == "__main__":
    asyncio.run(main())
