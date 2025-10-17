# Step4 Monitor - Markdown Transformation Integration

## Overview

The `step4_monitor.py` script now includes built-in markdown image transformation capabilities, allowing you to transform image links across your entire vault.

## New Features

### 1. Bulk Transformation Mode
Transform all markdown files in your vault with a single command.

**Dry Run (Preview):**
```bash
uv run step4_monitor.py \
  --vault-path /path/to/vault \
  --transform-images \
  --dry-run
```

**Apply Changes:**
```bash
uv run step4_monitor.py \
  --vault-path /path/to/vault \
  --transform-images
```

### 2. Preview Single File
Preview transformation for a specific file without modifying it:

```bash
uv run step4_monitor.py \
  --vault-path /path/to/vault \
  --preview-file path/to/file.md
```

### 3. Normal Monitoring Mode
Start monitoring with automatic transformation support (server handles transformation on-the-fly):

```bash
uv run step4_monitor.py --vault-path /path/to/vault
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--vault-path` | Path to Obsidian vault (required) |
| `--transform-images` | Transform all markdown files in vault |
| `--dry-run` | Preview changes without modifying files |
| `--preview-file` | Preview transformation for a specific file |
| `--server-port` | Server port (default: 7001) |
| `--max-concurrent` | Max concurrent processing tasks (default: 5) |
| `--daemon` | Run as daemon (detached from terminal) |

## Usage Examples

### Example 1: Transform AlphabetVault (Dry Run)

```bash
cd cli
python step4_monitor.py \
  --vault-path /Users/dienert/projects/keep2obsidian/AlphabetVault \
  --transform-images \
  --dry-run
```

**Output:**
```
============================================================
Markdown Image Transformation
============================================================
Vault: /Users/dienert/projects/keep2obsidian/AlphabetVault
Server URL: http://localhost:7001
Mode: DRY RUN (no files will be modified)
============================================================

Scanning vault for markdown files with image links...
Would transform: keep-2023-10--10.md
Would transform: keep-2023-10--11.md
...
Would transform: sa.md

Dry run complete: 92 files would be transformed
Run without --dry-run flag to apply changes
```

### Example 2: Preview Specific File

```bash
python step4_monitor.py \
  --vault-path /Users/dienert/projects/keep2obsidian/AlphabetVault \
  --preview-file /Users/dienert/projects/keep2obsidian/AlphabetVault/keep-2023-10--10.md
```

**Output:**
```
============================================================
Preview transformation for: keep-2023-10--10.md
============================================================

ORIGINAL:
![[assets/keep/2023-10-30T13_28_06.659-03_00-1.gif]]

TRANSFORMED:
![2023-10-30T13_28_06.659-03_00-1.gif](http://localhost:7001/images/assets/keep/2023-10-30T13_28_06.659-03_00-1.gif)
============================================================
```

### Example 3: Apply Transformations

```bash
python step4_monitor.py \
  --vault-path /Users/dienert/projects/keep2obsidian/AlphabetVault \
  --transform-images
```

**Output:**
```
✓ Transformed: keep-2023-10--10.md
✓ Transformed: keep-2023-10--11.md
...
✓ Transformed: sa.md

✓ Transformed 92 markdown files

Note: Changes have been applied to markdown files.
The server will automatically transform these links when serving Note content.
```

## How It Works

### 1. Transformation Process

```
┌─────────────────────┐
│  Markdown File      │
│  ![[image.png]]     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Transformer        │
│  - Detects format   │
│  - Resolves paths   │
│  - URL encodes      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Transformed File   │
│  ![image.png](.../) │
└─────────────────────┘
```

### 2. Integration Points

**New Methods in `VaultMonitor` class:**

- `transform_vault_markdown_images(dry_run=False)` - Transform all files
- `preview_markdown_transformation(file_path)` - Preview single file
- `get_server_url()` - Get server URL for transformations

### 3. Supported Link Formats

**Obsidian Wiki-style:**
```markdown
![[image.png]]
![[folder/image.png]]
![[assets/keep/image.gif]]
```

**Standard Markdown:**
```markdown
![alt](./image.png)
![alt](../folder/image.png)
![alt](path/to/image.png)
```

**External URLs (unchanged):**
```markdown
![alt](https://example.com/image.png)
```

## Best Practices

### 1. Always Dry Run First
Before applying transformations, run with `--dry-run` to see what will change:

```bash
# Preview first
python step4_monitor.py --vault-path /path/to/vault --transform-images --dry-run

# Then apply
python step4_monitor.py --vault-path /path/to/vault --transform-images
```

### 2. Preview Important Files
Check specific files before bulk transformation:

```bash
python step4_monitor.py --vault-path /path/to/vault --preview-file important.md
```

### 3. Backup Your Vault
Always backup your vault before bulk transformations:

```bash
# Create backup
cp -r /path/to/vault /path/to/vault-backup

# Then transform
python step4_monitor.py --vault-path /path/to/vault --transform-images
```

### 4. Server Must Be Running
For images to be accessible, start the server with vault path:

```bash
# Start server
python kuzu_server.py database.kz --vault-path /path/to/vault

# Or use monitoring mode (starts server automatically)
python step4_monitor.py --vault-path /path/to/vault
```

## Workflow

### Option A: Transform Then Monitor

```bash
# 1. Transform all files
python step4_monitor.py --vault-path /path/to/vault --transform-images

# 2. Build knowledge graph
uv run main_obsidian.py /path/to/vault

# 3. Start monitoring (server handles images automatically)
python step4_monitor.py --vault-path /path/to/vault
```

### Option B: Monitor Only (On-the-fly Transformation)

```bash
# Server transforms Note content automatically when retrieved
python step4_monitor.py --vault-path /path/to/vault
```

The server's `_node_to_dict()` method automatically transforms Note content when queries are made, so explicit file transformation is optional.

## Technical Details

### Imports Added
```python
from markdown_transformer import transform_markdown_images, batch_transform_notes
```

### New CLI Options
```python
@click.option("--transform-images", is_flag=True, ...)
@click.option("--dry-run", is_flag=True, ...)
@click.option("--preview-file", type=click.Path(...), ...)
```

### New Instance Variables
```python
self.server_port = server_port  # Track server port for URL generation
```

## Troubleshooting

### Issue: "No files would be transformed"
**Solution:** Check that files contain image links (`![[` or `![`)

### Issue: Images not loading after transformation
**Solution:** 
1. Verify server is running with `--vault-path`
2. Check image paths are correct
3. Verify images exist in vault

### Issue: Transformation changes too many files
**Solution:** Use `--preview-file` to check specific files first

### Issue: Need to undo transformations
**Solution:** 
1. Restore from backup
2. Or manually edit files to revert

## Next Steps

After transforming your vault:

1. **Build the knowledge graph:**
   ```bash
   uv run main_obsidian.py /path/to/vault
   ```

2. **Start the server:**
   ```bash
   python kuzu_server.py database.kz --vault-path /path/to/vault
   ```

3. **Query Note content:**
   ```cypher
   MATCH (n:Note) RETURN n.content LIMIT 1
   ```

Images in the returned content will be accessible via the server!

## Related Documentation

- [IMAGE_SERVING.md](IMAGE_SERVING.md) - Complete image serving documentation
- [README_IMAGE_SERVING.md](../README_IMAGE_SERVING.md) - Quick start guide
- [markdown_transformer.py](markdown_transformer.py) - Transformation utilities







