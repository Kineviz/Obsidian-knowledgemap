#!/usr/bin/env python3
"""
Test script for multi-tag task classification

Tests the actual classification of a note with a multi-tag task.

Usage:
    cd cli
    uv run test_multi_tag_classification.py
"""

import sys
import asyncio
from pathlib import Path

# Add cli directory to path
cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDefinition, TaskType, TagSchema, OutputType, TaskDatabase, Classifier
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

async def test_classification():
    """Test multi-tag task classification"""
    print("🧪 Testing Multi-Tag Task Classification\n")
    
    vault_path = get_vault_path()
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    classifier = Classifier(vault_path)
    
    # Create a test note if it doesn't exist
    test_note_path = vault_path / "test_vc_note.md"
    if not test_note_path.exists():
        print("Creating test note...")
        test_note_path.write_text("""---
type: company
name: Example Capital
---

# Example Capital

Example Capital is a venture capital firm based in San Francisco, California. 

## Investment Focus

The firm focuses on early-stage investments, particularly in Seed and Series A rounds. They typically write checks between $1M and $3M for seed-stage companies.

## Sectors

Example Capital invests primarily in:
- AI/ML companies
- Enterprise SaaS
- DevTools and infrastructure
- Data analytics platforms

## Geography

They invest primarily in US-based companies, with a focus on the San Francisco Bay Area and New York City.

## Firm Characteristics

The firm is operator-led, with partners who have deep technical backgrounds. They are known for being thesis-driven and founder-first in their investment approach.
""")
        print(f"✅ Created test note: {test_note_path.relative_to(vault_path)}\n")
    
    # Create a multi-tag task
    print("Test 1: Creating multi-tag task...")
    try:
        task = TaskDefinition(
            tag="gxr_test_vc_classification",
            task_type=TaskType.MULTI,
            name="Test VC Classification",
            description="Test multi-tag classification on VC profile",
            prompt="""Analyze this venture capital firm profile and extract structured information.

Extract:
1. Investment stages they focus on (Pre-Seed, Seed, Seed+, Series A, Series B, Growth, Late-Stage, Multi-Stage)
2. Sectors/industries they invest in (AI/ML, DevTools, Cloud/SaaS, Enterprise SaaS, Data/Analytics, etc.)
3. Typical check size range (Micro-checks <$250k, Small Seed $250k-$1M, Large Seed $1M-$3M, Series A Checks $3M-$10M, Growth Checks $10M+)
4. Geographic focus (US-National, SF-Bay Area, NYC, Boston, EU/UK, APAC, Global)
5. Firm characteristics (Technical Partners, Operator-Led Fund, Corporate VC, Family Office, etc.)

Return a JSON object with a "results" key containing all the extracted information.""",
            output_type=OutputType.TEXT,
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
                TagSchema(
                    tag="gxr_vc_geography",
                    output_type=OutputType.LIST,
                    name="Geographic Focus",
                    description="Investment geography"
                ),
                TagSchema(
                    tag="gxr_vc_firm_type",
                    output_type=OutputType.LIST,
                    name="Firm Characteristics",
                    description="Firm type and characteristics"
                ),
            ],
            enabled=True
        )
        
        task_id = db.create_task(task)
        print(f"✅ Created task with ID: {task_id}\n")
        
    except Exception as e:
        print(f"❌ Failed to create task: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Run classification
    print("Test 2: Running classification on test note...")
    try:
        relative_note_path = str(test_note_path.relative_to(vault_path))
        
        success, result, error = await classifier.classify_note(
            "gxr_test_vc_classification",
            relative_note_path,
            force=True,  # Force re-classification
            store_timestamp=True
        )
        
        if not success:
            print(f"❌ Classification failed: {error}")
            return False
        
        if error == "already_classified":
            print("⚠️  Note already classified, skipping...")
        else:
            print(f"✅ Classification successful!")
            if isinstance(result, dict):
                print(f"   Extracted {len(result)} tags:")
                for tag, value in result.items():
                    print(f"     - {tag}: {value}")
            else:
                print(f"   Result: {result}")
        
    except Exception as e:
        print(f"❌ Classification error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Verify results in frontmatter
    print("\nTest 3: Verifying results in note frontmatter...")
    try:
        from metadata_manager import get_metadata
        metadata = get_metadata(test_note_path)
        
        expected_tags = [
            "gxr_vc_investment_stages",
            "gxr_vc_sectors",
            "gxr_vc_check_size",
            "gxr_vc_geography",
            "gxr_vc_firm_type"
        ]
        
        found_tags = []
        missing_tags = []
        
        for tag in expected_tags:
            if tag in metadata:
                found_tags.append(tag)
                print(f"   ✅ {tag}: {metadata[tag]}")
            else:
                missing_tags.append(tag)
                print(f"   ❌ {tag}: Missing")
        
        if missing_tags:
            print(f"\n⚠️  Missing {len(missing_tags)} tags in frontmatter")
            return False
        
        print(f"\n✅ All {len(found_tags)} tags found in frontmatter!")
        
    except Exception as e:
        print(f"❌ Failed to verify results: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Cleanup
    print("\nTest 4: Cleaning up...")
    try:
        db.delete_task("gxr_test_vc_classification")
        print("✅ Test task deleted")
        
        # Optionally delete test note
        # test_note_path.unlink()
        # print("✅ Test note deleted")
        
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    
    print("\n✅ All classification tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_classification())
    sys.exit(0 if success else 1)

