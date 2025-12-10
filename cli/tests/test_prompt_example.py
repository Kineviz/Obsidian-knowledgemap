#!/usr/bin/env python3
"""
Test script to show how the prompt instructs the LLM about JSON keys

This demonstrates how the tag names from tag_schema become the JSON keys.
"""

import sys
from pathlib import Path

cli_path = Path(__file__).parent
if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))

from classification import TaskDefinition, TaskType, TagSchema, OutputType, Classifier
from config_loader import get_config_loader

def get_vault_path() -> Path:
    config = get_config_loader()
    vault_path = config.get_vault_path()
    if not vault_path:
        print("Error: Vault path not configured")
        sys.exit(1)
    return Path(vault_path)

def show_prompt_example():
    """Show how the prompt is built for multi-tag tasks"""
    print("🔍 How Multi-Tag Prompt Instructs LLM About JSON Keys\n")
    
    # Create a sample task
    task = TaskDefinition(
        tag="gxr_vc_analysis",
        task_type=TaskType.MULTI,
        prompt="Analyze this VC profile...",
        output_type=OutputType.TEXT,
        tag_schema=[
            TagSchema(tag="gxr_vc_investment_stages", output_type=OutputType.LIST, name="Stages"),
            TagSchema(tag="gxr_vc_sectors", output_type=OutputType.LIST, name="Sectors"),
            TagSchema(tag="gxr_vc_check_size", output_type=OutputType.TEXT, name="Check Size"),
        ]
    )
    
    # Build the prompt
    classifier = Classifier(get_vault_path())
    messages = classifier._build_multi_tag_prompt(task, "Sample note content here...")
    
    print("=" * 80)
    print("SYSTEM PROMPT:")
    print("=" * 80)
    print(messages[0]['content'])
    print("\n" + "=" * 80)
    print("USER PROMPT:")
    print("=" * 80)
    print(messages[1]['content'])
    print("\n" + "=" * 80)
    
    print("\n📝 Key Points:")
    print("1. The JSON example explicitly shows the tag names as keys:")
    print("   - 'gxr_vc_investment_stages'")
    print("   - 'gxr_vc_sectors'")
    print("   - 'gxr_vc_check_size'")
    print("\n2. The LLM is instructed to use these EXACT tag names as JSON keys")
    print("\n3. When parsing, we look up results by tag name:")
    print("   results['gxr_vc_investment_stages'] → maps to tag_schema[0]")
    print("   results['gxr_vc_sectors'] → maps to tag_schema[1]")
    print("   results['gxr_vc_check_size'] → maps to tag_schema[2]")
    print("\n4. The mapping is: tag_schema.tag == JSON key")

if __name__ == "__main__":
    show_prompt_example()

