#!/usr/bin/env python3
"""
Test script for the new Kuzu connection pool
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the cli directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from kuzu_pool import KuzuConnectionPool, PoolConfig

async def test_pool():
    """Test the connection pool functionality"""
    print("Testing Kuzu Connection Pool...")
    
    # Use an existing database if available, otherwise create a test one
    test_db_path = "/Users/weidongyang/Obsidian/ExampleVault/.kineviz_graph/database/knowledge_graph.kz"
    
    if not os.path.exists(test_db_path):
        print(f"❌ Test database not found at: {test_db_path}")
        print("Please run step3_build.py first to create the database")
        return False
    
    # Create pool config
    config = PoolConfig(
        max_connections=3,
        max_retries=2,
        retry_delay=5,
        idle_timeout=60,
        health_check_interval=30
    )
    
    # Create connection pool
    pool = KuzuConnectionPool(test_db_path, config)
    
    try:
        # Test starting the pool
        print("Starting connection pool...")
        success = await pool.start()
        if not success:
            print("❌ Failed to start connection pool")
            return False
        
        print("✅ Connection pool started successfully")
        
        # Test basic query
        print("Testing basic query...")
        result = await pool.execute_query_with_retry("CALL show_tables() RETURN *")
        print(f"Query result: {result}")
        
        if result.get("status") == "success":
            print("✅ Basic query executed successfully")
        else:
            print(f"❌ Query failed: {result.get('message')}")
            return False
        
        # Test pool status
        status = pool.get_pool_status()
        print(f"Pool status: {status}")
        
        # Test multiple queries
        print("Testing multiple queries...")
        queries = [
            "CALL show_tables() RETURN *",
            "MATCH (n) RETURN count(n) LIMIT 1"
        ]
        
        for i, query in enumerate(queries):
            result = await pool.execute_query_with_retry(query)
            if result.get("status") == "success":
                print(f"✅ Query {i+1} executed successfully")
            else:
                print(f"❌ Query {i+1} failed: {result.get('message')}")
        
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        print("Stopping connection pool...")
        await pool.stop()
        print("✅ Connection pool stopped")
        
        # No need to clean up - we're using an existing database

if __name__ == "__main__":
    success = asyncio.run(test_pool())
    sys.exit(0 if success else 1)
