#!/usr/bin/env python3
"""
Simple test for Kuzu server with pooling
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the cli directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))

async def test_server():
    """Test the Kuzu server with pooling"""
    print("Testing Kuzu Server with Connection Pooling...")
    
    # Import here to avoid issues if dependencies are missing
    try:
        from kuzu_server import KuzuQueryProcessor, PoolConfig
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Make sure you're in the cli directory and dependencies are installed")
        return False
    
    # Use existing database
    db_path = "/Users/weidongyang/Obsidian/ExampleVault/.kineviz_graph/database/knowledge_graph.kz"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        print("Please run step3_build.py first to create the database")
        return False
    
    print(f"✅ Database found at: {db_path}")
    
    # Create pool config
    config = PoolConfig(
        max_connections=2,
        max_retries=2,
        retry_delay=5,
        idle_timeout=60,
        health_check_interval=30
    )
    
    # Create query processor
    processor = KuzuQueryProcessor(db_path, config)
    
    try:
        print("Initializing connection pool...")
        await processor.initialize_connection()
        print("✅ Connection pool initialized successfully")
        
        # Test basic query
        print("Testing basic query...")
        result = await processor.execute_query("CALL show_tables() RETURN *")
        print(f"✅ Query executed successfully, returned {len(result)} rows")
        
        # Test pool status
        status = processor.connection_pool.get_pool_status()
        print(f"Pool status: {status}")
        
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        print("Cleaning up...")
        await processor.cleanup()
        print("✅ Cleanup completed")

if __name__ == "__main__":
    success = asyncio.run(test_server())
    sys.exit(0 if success else 1)
