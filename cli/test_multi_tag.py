#!/usr/bin/env python3
"""
Test script for multi-tag task functionality

Tests:
1. Creating a multi-tag task
2. Retrieving a multi-tag task
3. Updating a multi-tag task
4. Database persistence

Usage:
    cd cli
    uv run test_multi_tag.py
"""

import sys
from pathlib import Path

# Add cli directory to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDefinition, TaskType, TagSchema, OutputType, TaskDatabase
from config_loader import get_config_loader

def get_vault_path() -> Path:
    """Get vault path from config"""
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        print("Set vault.path in config.yaml or VAULT_PATH environment variable")
        sys.exit(1)
    return Path(vault_path)

def test_multi_tag_task():
    """Test multi-tag task creation and retrieval"""
    print("🧪 Testing Multi-Tag Task Functionality\n")
    
    # Get database
    vault_path = get_vault_path()
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    
    # Test 1: Create a multi-tag task
    print("Test 1: Creating multi-tag task...")
    try:
        task = TaskDefinition(
            tag="gxr_test_vc_analysis",
            task_type=TaskType.MULTI,
            name="Test VC Analysis",
            description="Test multi-tag task for VC analysis",
            prompt="Analyze this VC profile and extract investment information.",
            output_type=OutputType.TEXT,  # Primary type (not used for multi-tag)
            tag_schema=[
                TagSchema(
                    tag="gxr_vc_investment_stages",
                    output_type=OutputType.LIST,
                    name="Investment Stages",
                    description="Stages of investment focus"
                ),
                TagSchema(
                    tag="gxr_vc_sectors",
                    output_type=OutputType.LIST,
                    name="Investment Sectors",
                    description="Sectors and industries"
                ),
                TagSchema(
                    tag="gxr_vc_check_size",
                    output_type=OutputType.TEXT,
                    name="Check Size Range",
                    description="Typical check size"
                ),
            ],
            enabled=True
        )
        
        task_id = db.create_task(task)
        print(f"✅ Created task with ID: {task_id}")
        
    except Exception as e:
        print(f"❌ Failed to create task: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Retrieve the task
    print("\nTest 2: Retrieving multi-tag task...")
    try:
        retrieved = db.get_task("gxr_test_vc_analysis")
        if not retrieved:
            print("❌ Task not found")
            return False
        
        print(f"✅ Retrieved task: {retrieved.tag}")
        print(f"   Task Type: {retrieved.task_type.value}")
        print(f"   Name: {retrieved.name}")
        if retrieved.tag_schema:
            print(f"   Tag Schema ({len(retrieved.tag_schema)} tags):")
            for ts in retrieved.tag_schema:
                print(f"     - {ts.tag} ({ts.output_type.value})")
        
        # Verify fields
        if retrieved.task_type != TaskType.MULTI:
            print("❌ Task type mismatch")
            return False
        if not retrieved.tag_schema or len(retrieved.tag_schema) != 3:
            print("❌ Tag schema mismatch")
            return False
        
    except Exception as e:
        print(f"❌ Failed to retrieve task: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Update the task
    print("\nTest 3: Updating multi-tag task...")
    try:
        # Add a new tag to the schema
        new_tag = TagSchema(
            tag="gxr_vc_geography",
            output_type=OutputType.LIST,
            name="Geographic Focus",
            description="Investment geography"
        )
        
        updated_schema = retrieved.tag_schema + [new_tag]
        
        success = db.update_task("gxr_test_vc_analysis", {
            'tag_schema': updated_schema,
            'description': 'Updated description'
        })
        
        if not success:
            print("❌ Update failed")
            return False
        
        # Verify update
        updated = db.get_task("gxr_test_vc_analysis")
        if not updated or len(updated.tag_schema) != 4:
            print("❌ Update verification failed")
            return False
        
        print(f"✅ Updated task successfully")
        print(f"   Tag schema now has {len(updated.tag_schema)} tags")
        
    except Exception as e:
        print(f"❌ Failed to update task: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: List all tasks (verify backward compatibility)
    print("\nTest 4: Listing all tasks (backward compatibility)...")
    try:
        all_tasks = db.get_all_tasks()
        print(f"✅ Found {len(all_tasks)} total tasks")
        
        multi_tasks = [t for t in all_tasks if t.task_type == TaskType.MULTI]
        single_tasks = [t for t in all_tasks if t.task_type == TaskType.SINGLE]
        
        print(f"   Single-tag tasks: {len(single_tasks)}")
        print(f"   Multi-tag tasks: {len(multi_tasks)}")
        
        # Verify existing tasks default to single
        for task in single_tasks:
            if task.tag != "gxr_test_vc_analysis" and task.task_type != TaskType.SINGLE:
                print(f"❌ Existing task {task.tag} has wrong type")
                return False
        
    except Exception as e:
        print(f"❌ Failed to list tasks: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Cleanup - delete test task
    print("\nTest 5: Cleaning up test task...")
    try:
        db.delete_task("gxr_test_vc_analysis")
        print("✅ Test task deleted")
    except Exception as e:
        print(f"⚠️  Failed to delete test task: {e}")
        print("   (You may need to delete it manually)")
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    success = test_multi_tag_task()
    sys.exit(0 if success else 1)

