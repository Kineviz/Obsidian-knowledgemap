#!/usr/bin/env python3
"""
Test script for multi-tag task API endpoints

Tests the FastAPI endpoints for multi-tag task support.

Usage:
    # First start the server: uv run classification_server.py
    # Then run this test: uv run test_multi_tag_api.py
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_api():
    """Test multi-tag task API endpoints"""
    print("🧪 Testing Multi-Tag Task API Endpoints\n")
    
    # Test 1: Create a multi-tag task via API
    print("Test 1: Creating multi-tag task via API...")
    try:
        task_data = {
            "tag": "gxr_test_vc_api",
            "task_type": "multi",
            "name": "Test VC Analysis (API)",
            "description": "Test multi-tag task via API",
            "prompt": "Analyze this VC profile and extract investment information.",
            "output_type": "text",
            "tag_schema": [
                {
                    "tag": "gxr_vc_investment_stages",
                    "output_type": "list",
                    "name": "Investment Stages",
                    "description": "Stages of investment focus"
                },
                {
                    "tag": "gxr_vc_sectors",
                    "output_type": "list",
                    "name": "Investment Sectors",
                    "description": "Sectors and industries"
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_data)
        if response.status_code != 200:
            print(f"❌ Failed to create task: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        result = response.json()
        print(f"✅ Created task: {result.get('tag')}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is classification_server.py running?")
        print("   Start it with: uv run classification_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Get the task
    print("\nTest 2: Retrieving multi-tag task via API...")
    try:
        response = requests.get(f"{BASE_URL}/api/tasks/gxr_test_vc_api")
        if response.status_code != 200:
            print(f"❌ Failed to get task: {response.status_code}")
            return False
        
        task = response.json()
        print(f"✅ Retrieved task: {task.get('tag')}")
        print(f"   Task Type: {task.get('task_type')}")
        print(f"   Name: {task.get('name')}")
        
        tag_schema = task.get('tag_schema')
        if tag_schema:
            print(f"   Tag Schema ({len(tag_schema)} tags):")
            for ts in tag_schema:
                print(f"     - {ts.get('tag')} ({ts.get('output_type')})")
        
        # Verify
        if task.get('task_type') != 'multi':
            print("❌ Task type mismatch")
            return False
        if not tag_schema or len(tag_schema) != 2:
            print("❌ Tag schema mismatch")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: List all tasks
    print("\nTest 3: Listing all tasks via API...")
    try:
        response = requests.get(f"{BASE_URL}/api/tasks")
        if response.status_code != 200:
            print(f"❌ Failed to list tasks: {response.status_code}")
            return False
        
        tasks = response.json()
        print(f"✅ Found {len(tasks)} tasks")
        
        multi_tasks = [t for t in tasks if t.get('task_type') == 'multi']
        single_tasks = [t for t in tasks if t.get('task_type') == 'single']
        
        print(f"   Single-tag tasks: {len(single_tasks)}")
        print(f"   Multi-tag tasks: {len(multi_tasks)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Update the task
    print("\nTest 4: Updating multi-tag task via API...")
    try:
        update_data = {
            "description": "Updated description via API",
            "tag_schema": [
                {
                    "tag": "gxr_vc_investment_stages",
                    "output_type": "list",
                    "name": "Investment Stages",
                    "description": "Stages of investment focus"
                },
                {
                    "tag": "gxr_vc_sectors",
                    "output_type": "list",
                    "name": "Investment Sectors",
                    "description": "Sectors and industries"
                },
                {
                    "tag": "gxr_vc_geography",
                    "output_type": "list",
                    "name": "Geographic Focus",
                    "description": "Investment geography"
                }
            ]
        }
        
        response = requests.put(f"{BASE_URL}/api/tasks/gxr_test_vc_api", json=update_data)
        if response.status_code != 200:
            print(f"❌ Failed to update task: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        # Verify update
        response = requests.get(f"{BASE_URL}/api/tasks/gxr_test_vc_api")
        updated = response.json()
        if len(updated.get('tag_schema', [])) != 3:
            print("❌ Update verification failed")
            return False
        
        print(f"✅ Updated task successfully")
        print(f"   Tag schema now has {len(updated.get('tag_schema', []))} tags")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Cleanup - delete test task
    print("\nTest 5: Cleaning up test task...")
    try:
        response = requests.delete(f"{BASE_URL}/api/tasks/gxr_test_vc_api")
        if response.status_code == 200:
            print("✅ Test task deleted")
        else:
            print(f"⚠️  Failed to delete test task: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Failed to delete test task: {e}")
    
    print("\n✅ All API tests passed!")
    return True

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)

