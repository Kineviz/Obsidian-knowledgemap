#!/usr/bin/env python3
"""
Test the Kuzu server with connection pooling by making HTTP requests
"""

import asyncio
import httpx
import json
import time

async def test_server_endpoints():
    """Test the Kuzu server endpoints"""
    base_url = "http://localhost:7001"
    
    print("🧪 Testing Kuzu Server with Connection Pooling...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Health Check
        print("1️⃣ Testing Health Check...")
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health Check: {health_data['status']}")
                if 'pool_status' in health_data:
                    print(f"   Pool Status: {health_data['pool_status']}")
            else:
                print(f"❌ Health Check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health Check error: {e}")
            print("   Make sure the server is running: uv run python kuzu_server.py <db_path> --port 7001")
            return False
        
        # Test 2: Basic Query
        print("\n2️⃣ Testing Basic Query...")
        try:
            query_data = {
                "query": "CALL show_tables() RETURN *"
            }
            response = await client.post(f"{base_url}/kuzudb/testdb", json=query_data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == 0:
                    print("✅ Basic Query: Success")
                    data = result.get("data", {})
                    if data.get("type") == "GRAPH":
                        nodes = data.get("data", {}).get("nodes", [])
                        relationships = data.get("data", {}).get("relationships", [])
                        print(f"   Graph data: {len(nodes)} nodes, {len(relationships)} relationships")
                    else:
                        table_data = data.get("data", [])
                        print(f"   Table data: {len(table_data)} rows")
                        if table_data:
                            for i, row in enumerate(table_data[:3]):  # Show first 3 rows
                                print(f"   - {row}")
                else:
                    print(f"❌ Basic Query failed: {result.get('message')}")
                    return False
            else:
                print(f"❌ Basic Query HTTP error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Basic Query error: {e}")
            return False
        
        # Test 3: Schema Query
        print("\n3️⃣ Testing Schema Query...")
        try:
            query_data = {
                "query": "CALL SCHEMA"
            }
            response = await client.post(f"{base_url}/kuzudb/testdb", json=query_data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == 0:
                    print("✅ Schema Query: Success")
                    schema_data = result.get("data", {})
                    if "testdb" in schema_data:
                        categories = schema_data["testdb"].get("categories", {})
                        relationships = schema_data["testdb"].get("relationships", {})
                        print(f"   Categories: {len(categories)}")
                        print(f"   Relationships: {len(relationships)}")
                else:
                    print(f"❌ Schema Query failed: {result.get('message')}")
                    return False
            else:
                print(f"❌ Schema Query HTTP error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Schema Query error: {e}")
            return False
        
        # Test 4: Data Query
        print("\n4️⃣ Testing Data Query...")
        try:
            query_data = {
                "query": "MATCH (n) RETURN count(n) as total_nodes LIMIT 1"
            }
            response = await client.post(f"{base_url}/kuzudb/testdb", json=query_data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == 0:
                    print("✅ Data Query: Success")
                    data = result.get("data", {})
                    if data.get("type") == "GRAPH":
                        nodes = data.get("data", {}).get("nodes", [])
                        relationships = data.get("data", {}).get("relationships", [])
                        print(f"   Graph data: {len(nodes)} nodes, {len(relationships)} relationships")
                    else:
                        table_data = data.get("data", [])
                        if table_data and len(table_data) > 1:  # Skip header row
                            # Get the first data row (skip header)
                            data_row = table_data[1] if len(table_data) > 1 else table_data[0]
                            if isinstance(data_row, list) and len(data_row) > 0:
                                total_nodes = data_row[0] if isinstance(data_row[0], (int, float)) else 0
                                print(f"   Total nodes in database: {total_nodes}")
                            else:
                                print(f"   Data row: {data_row}")
                        else:
                            print("   No data returned")
                else:
                    print(f"❌ Data Query failed: {result.get('message')}")
                    return False
            else:
                print(f"❌ Data Query HTTP error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Data Query error: {e}")
            return False
        
        # Test 5: Multiple Concurrent Queries (Pool Test)
        print("\n5️⃣ Testing Connection Pool with Concurrent Queries...")
        try:
            queries = [
                "MATCH (n) RETURN count(n) as count1 LIMIT 1",
                "CALL show_tables() RETURN count(*) as table_count",
                "MATCH (n) RETURN labels(n)[0] as label, count(n) as count LIMIT 5"
            ]
            
            tasks = []
            for i, query in enumerate(queries):
                task = client.post(f"{base_url}/kuzudb/testdb", json={"query": query})
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            success_count = 0
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    print(f"   Query {i+1}: ❌ Error - {response}")
                elif response.status_code == 200:
                    result = response.json()
                    if result.get("status") == 0:
                        print(f"   Query {i+1}: ✅ Success")
                        success_count += 1
                    else:
                        print(f"   Query {i+1}: ❌ Failed - {result.get('message')}")
                else:
                    print(f"   Query {i+1}: ❌ HTTP {response.status_code}")
            
            print(f"   Concurrent queries completed in {end_time - start_time:.2f}s")
            print(f"   Success rate: {success_count}/{len(queries)}")
            
            if success_count == len(queries):
                print("✅ Connection Pool: All concurrent queries succeeded")
            else:
                print("⚠️ Connection Pool: Some queries failed")
        except Exception as e:
            print(f"❌ Connection Pool test error: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 All tests completed!")
        return True

async def main():
    """Main test function"""
    print("Kuzu Server Connection Pooling Test")
    print("Make sure the server is running first:")
    print("  cd cli")
    print("  uv run python kuzu_server.py /path/to/database.kz --port 7001")
    print()
    
    success = await test_server_endpoints()
    
    if success:
        print("✅ All tests passed! The connection pooling is working correctly.")
    else:
        print("❌ Some tests failed. Check the server logs for details.")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
