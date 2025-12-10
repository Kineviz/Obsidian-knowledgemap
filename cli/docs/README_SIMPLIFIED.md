# Simplified Knowledge Map Tool

## Quick Start

### Option 1: Use the run script (Recommended)
```bash
# Make it executable (one time)
chmod +x run.sh

# Run the tool
./run.sh /path/to/markdown/folder --db-path knowledge.kz
./run.sh --cache-status
./run.sh --rebuild-from-cache --db-path knowledge.kz
```

### Option 2: Add to your shell profile
Add this to your `~/.zshrc` or `~/.bashrc`:

```bash
alias kmt="cd /path/to/knowledge-map-tool/cli && ./run.sh"
```

Then you can use:
```bash
kmt /path/to/markdown/folder --db-path knowledge.kz
kmt --cache-status
kmt --rebuild-from-cache --db-path knowledge.kz
```

### Option 3: Direct uv run (if you prefer)
```bash
uv run --with "chonkie[semantic]" --with click --with httpx --with hishel --with kuzu --with python-dotenv --with rich --with openai --with pydantic --with jsonschema main.py /path/to/markdown/folder
```

## Why So Many --with Flags?

The `--with` flags are needed because:
1. The script uses PEP 723 inline script metadata
2. uv needs to know all dependencies at runtime
3. Each `--with` flag installs a specific package

The `run.sh` script hides this complexity and makes it much easier to use!

## Commands

- **Process markdown files**: `./run.sh /path/to/markdown --db-path knowledge.kz`
- **Check cache status**: `./run.sh --cache-status`
- **Rebuild from cache**: `./run.sh --rebuild-from-cache --db-path knowledge.kz`
- **Skip extraction**: `./run.sh /path/to/markdown --skip-extraction`


### to load to graphxr:
```
deno run \
    --unsafely-ignore-certificate-errors=localhost \
    --allow-net \
    --allow-read \
    --allow-env \
    graphxr.ts \
    uploadKuzuFile \
    --baseUrl 'https://graphxrdev.kineviz.com' \
    --username 'weidong@kineviz.com' \
    --password 'xyz' \
    --file default.kz \
    --projectId 68b0c6167a1788ffa82e5d03
```