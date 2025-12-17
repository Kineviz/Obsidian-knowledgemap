# Tag Naming Options for VC Analysis

## Current Tags (Too Long)
- `gxr_vc_investment_stages` (25 chars)
- `gxr_vc_sectors` (15 chars)
- `gxr_vc_check_size` (18 chars)
- `gxr_vc_geography` (18 chars)
- `gxr_vc_firm_type` (17 chars)

## Selected: `_vc_` prefix (IMPLEMENTED)
**Pros:** 
- Very short and readable
- Underscore prefix clearly indicates system-generated metadata
- Follows common convention for post-processing tags
- ~60% shorter than original

**Tags:**
- `_vc_stages` (10 chars) ← `gxr_vc_investment_stages` (60% shorter)
- `_vc_sectors` (12 chars) ← `gxr_vc_sectors` (20% shorter)
- `_vc_size` (9 chars) ← `gxr_vc_check_size` (50% shorter)
- `_vc_geo` (9 chars) ← `gxr_vc_geography` (50% shorter)
- `_vc_type` (10 chars) ← `gxr_vc_firm_type` (41% shorter)

## Rationale
- The `_` prefix is a common convention for system-generated metadata
- `_vc_` clearly indicates these are VC-related post-processing tags
- Much shorter for Obsidian UI display
- Still readable and self-documenting

