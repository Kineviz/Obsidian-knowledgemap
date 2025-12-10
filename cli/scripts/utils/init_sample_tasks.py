#!/usr/bin/env python3
"""
Initialize Sample Classification Tasks

Creates example single-tag and multi-tag tasks that can be used as templates.

Usage:
    cd cli
    uv run init_sample_tasks.py
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

def init_sample_tasks():
    """Initialize sample classification tasks"""
    print("📋 Initializing Sample Classification Tasks\n")
    
    vault_path = get_vault_path()
    db_path = vault_path / ".kineviz_graph" / "classification.db"
    db = TaskDatabase(db_path)
    
    # Sample single-tag tasks
    single_tag_tasks = [
        TaskDefinition(
            tag="gxr_professional_interests",
            task_type=TaskType.SINGLE,
            name="Professional Interests",
            description="Extract professional interests and focus areas",
            prompt="""Extract the professional interests, focus areas, or expertise topics mentioned in this note.
Return a comma-separated list of interests. If no professional interests are found, return an empty string.

Examples:
- "Venture Capital, Technology Investing, Board Governance"
- "AI/ML, Enterprise SaaS, Data Analytics"
- "Healthcare, Biotech, Medical Devices"
""",
            output_type=OutputType.LIST,
            enabled=True
        ),
        TaskDefinition(
            tag="gxr_personal_interests",
            task_type=TaskType.SINGLE,
            name="Personal Interests",
            description="Extract personal hobbies and interests",
            prompt="""Extract personal interests, hobbies, or activities mentioned in this note.
Return a comma-separated list. If no personal interests are found, return an empty string.

Examples:
- "Skiing, Wine Collecting, Travel"
- "Photography, Hiking, Reading"
""",
            output_type=OutputType.LIST,
            enabled=True
        ),
        TaskDefinition(
            tag="gxr_is_investor",
            task_type=TaskType.SINGLE,
            name="Is Investor",
            description="Determine if the person/entity is an investor",
            prompt="""Is this person or entity an investor (venture capitalist, angel investor, etc.)?
Return exactly "true" or "false".
""",
            output_type=OutputType.BOOLEAN,
            enabled=True
        ),
        TaskDefinition(
            tag="gxr_years_experience",
            task_type=TaskType.SINGLE,
            name="Years of Experience",
            description="Extract years of professional experience",
            prompt="""Based on this note, estimate the person's years of professional experience.
Return a number. If cannot determine, return 0.
""",
            output_type=OutputType.NUMBER,
            enabled=True
        ),
    ]
    
    # VC Analysis multi-tag task (from design doc)
    vc_analysis_task = TaskDefinition(
        tag="gxr_vc_analysis",
        task_type=TaskType.MULTI,
        name="VC Profile Analysis",
        description="Extract comprehensive VC investment profile with stages, sectors, check sizes, geography, and firm characteristics",
        prompt="""You are an expert VC researcher. Analyze this venture capital firm profile and extract structured information.

Use only evidence from the text provided. Do not hallucinate missing details. If unclear, return empty list or "unknown".

Extract the following information:
1. Investment stages they focus on (Pre-Seed, Seed, Seed+, Series A, Series B, Growth, Late-Stage, Multi-Stage, Opportunity Fund)
2. Sectors/industries they invest in (AI/ML, LLMs, DevTools, Cloud/SaaS, Cybersecurity, Data/Analytics, Bio/HealthTech, Fintech, Climate, Robotics, Consumer, GovTech, Deep Tech, etc.)
3. Typical check size range (Micro-checks <$250k, Small Seed $250k-$1M, Large Seed $1M-$3M, Series A Checks $3M-$10M, Growth Checks $10M+)
4. Geographic focus (US-National, SF-Bay Area, NYC, Boston, EU/UK, DACH, Nordics, APAC, Global)
5. Firm characteristics (Technical Partners, Operator-Led Fund, Corporate VC, Family Office, Government/Sovereign Fund, Impact-Oriented, AI-Native Fund, Security-Focused Fund, Hard-Tech Thesis)

Return a JSON object with a "results" key containing all the extracted information.""",
        output_type=OutputType.TEXT,  # Primary type (not used for multi-tag)
        tag_schema=[
            TagSchema(
                tag="gxr_vc_investment_stages",
                output_type=OutputType.LIST,
                name="Investment Stages",
                description="Stages of investment focus: Pre-Seed, Seed, Seed+, Series A, Series B, Growth, Late-Stage, Multi-Stage, Opportunity Fund"
            ),
            TagSchema(
                tag="gxr_vc_sectors",
                output_type=OutputType.LIST,
                name="Investment Sectors",
                description="Sectors and industries: AI/ML, LLMs, DevTools, Cloud/SaaS, Cybersecurity, Data/Analytics, Bio/HealthTech, Fintech, Climate, Robotics, Consumer, GovTech, Deep Tech, Enterprise SaaS, Vertical AI, etc."
            ),
            TagSchema(
                tag="gxr_vc_check_size",
                output_type=OutputType.TEXT,
                name="Check Size Range",
                description="Typical check size: Micro-checks (<$250k), Small Seed ($250k-$1M), Large Seed ($1M-$3M), Series A Checks ($3M-$10M), Growth Checks ($10M+)"
            ),
            TagSchema(
                tag="gxr_vc_geography",
                output_type=OutputType.LIST,
                name="Geographic Focus",
                description="Investment geography: US-National, SF-Bay Area, NYC, Boston, EU/UK, DACH, Nordics, APAC, Global"
            ),
            TagSchema(
                tag="gxr_vc_firm_type",
                output_type=OutputType.LIST,
                name="Firm Characteristics",
                description="Firm type: Technical Partners, Operator-Led Fund, Corporate VC, Family Office, Government/Sovereign Fund, Impact-Oriented, AI-Native Fund, Security-Focused Fund, Hard-Tech Thesis"
            ),
        ],
        enabled=True
    )
    
    created_count = 0
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    print("Creating single-tag tasks...")
    for task in single_tag_tasks:
        try:
            existing = db.get_task(task.tag)
            if existing:
                print(f"  ⏭️  Skipped (exists): {task.tag}")
                skipped_count += 1
            else:
                task_id = db.create_task(task)
                print(f"  ✅ Created: {task.tag} (id={task_id})")
                created_count += 1
        except Exception as e:
            print(f"  ❌ Error creating {task.tag}: {e}")
            error_count += 1
    
    print("\nCreating multi-tag task...")
    try:
        existing = db.get_task(vc_analysis_task.tag)
        if existing:
            print(f"  ⏭️  Skipped (exists): {vc_analysis_task.tag}")
            skipped_count += 1
        else:
            task_id = db.create_task(vc_analysis_task)
            print(f"  ✅ Created: {vc_analysis_task.tag} (id={task_id})")
            print(f"     Tags: {len(vc_analysis_task.tag_schema)} tags defined")
            created_count += 1
    except Exception as e:
        print(f"  ❌ Error creating {vc_analysis_task.tag}: {e}")
        error_count += 1
    
    print(f"\n📊 Summary:")
    print(f"  Created: {created_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    
    if created_count > 0:
        print(f"\n✅ Sample tasks initialized! You can now:")
        print(f"  - View them: uv run classification_task_manager.py list-tasks")
        print(f"  - Use as templates in the web UI")
        print(f"  - Run classification: uv run classification_task_manager.py run gxr_vc_analysis --folder <folder>")
    
    return created_count > 0

if __name__ == "__main__":
    success = init_sample_tasks()
    sys.exit(0 if success else 1)

