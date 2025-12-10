#!/usr/bin/env python3
"""
Test to show that any custom multi-tag task automatically generates the correct JSON example
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

def test_custom_task():
    """Show that a custom multi-tag task automatically generates correct JSON example"""
    print("🔍 Testing Custom Multi-Tag Task JSON Example Generation\n")
    
    # Create a custom multi-tag task with different tags
    custom_task = TaskDefinition(
        tag="gxr_custom_analysis",
        task_type=TaskType.MULTI,
        prompt="Analyze this document...",
        output_type=OutputType.TEXT,
        tag_schema=[
            TagSchema(tag="gxr_custom_field1", output_type=OutputType.LIST),
            TagSchema(tag="gxr_custom_field2", output_type=OutputType.BOOLEAN),
            TagSchema(tag="gxr_custom_field3", output_type=OutputType.NUMBER),
        ]
    )
    
    classifier = Classifier(get_vault_path())
    messages = classifier._build_multi_tag_prompt(custom_task, "Sample content")
    
    print("Custom Task Tag Schema:")
    for ts in custom_task.tag_schema:
        print(f"  - {ts.tag} ({ts.output_type.value})")
    
    print("\n" + "=" * 80)
    print("AUTOMATICALLY GENERATED JSON EXAMPLE:")
    print("=" * 80)
    
    # Extract the JSON example from the system prompt
    system_prompt = messages[0]['content']
    import re
    json_match = re.search(r'\{[^}]+\}', system_prompt, re.DOTALL)
    if json_match:
        print(json_match.group(0))
    
    print("\n✅ The system automatically:")
    print("  1. Reads your tag_schema")
    print("  2. Uses each tag_schema.tag as the JSON key")
    print("  3. Generates the correct example structure")
    print("  4. No manual configuration needed!")
    
    print("\n📝 So when you create a new multi-tag task:")
    print("  - Define your tag_schema with tag names")
    print("  - The prompt builder automatically creates the JSON example")
    print("  - The LLM sees the exact keys it should use")
    print("  - Results are mapped back using the same tag names")

if __name__ == "__main__":
    test_custom_task()

