# Image Serving Feature

This document describes the image serving feature that allows the Kuzu server to serve images from the Obsidian vault and automatically transform markdown image links.

## Overview

The Kuzu server now includes:
1. An `/images/{path}` endpoint to serve images from the vault
2. Automatic transformation of markdown image links in Note content
3. A `/transform_markdown` endpoint for manual markdown transformation

## Image Serving Endpoint

### Endpoint: `GET /images/{path}`

Serves images directly from the Obsidian vault.

**Example:**
```
GET http://localhost:7001/images/assets/screenshot.png
```

**Security:**
- Only serves files within the vault directory
- Path traversal attacks are prevented
- Only serves files with image extensions (.jpg, .jpeg, .png, .gif, .bmp, .svg, .webp, .ico)

### Starting the Server with Image Support

To enable image serving, start the server with the `--vault-path` argument:

```bash
python kuzu_server.py /path/to/database.kz --vault-path /path/to/obsidian/vault
```

Or with the full command:
```bash
python kuzu_server.py /path/to/database.kz \
    --vault-path /path/to/obsidian/vault \
    --port 7001 \
    --host 0.0.0.0
```

## Automatic Markdown Transformation

When the server is started with `--vault-path`, markdown content in Note nodes is automatically transformed to use the server's image endpoint.

### Transformation Examples

**Obsidian Wiki-style Links:**
```markdown
# Before
![[screenshot.png]]

# After
![screenshot.png](http://localhost:7001/images/screenshot.png)
```

**Standard Markdown Links:**
```markdown
# Before
![My Image](./images/photo.jpg)
![Diagram](../assets/diagram.png)

# After
![My Image](http://localhost:7001/images/images/photo.jpg)
![Diagram](http://localhost:7001/images/assets/diagram.png)
```

**External URLs (unchanged):**
```markdown
![External](https://example.com/image.png)
# Remains unchanged
```

### How It Works

1. When querying Note nodes with content, the server automatically detects Obsidian image links
2. It transforms them to point to the `/images/` endpoint
3. The transformation handles:
   - Wiki-style links: `![[image.png]]`
   - Relative paths: `./image.png`, `../folder/image.png`
   - Absolute vault paths: `folder/subfolder/image.png`
4. The transformation preserves:
   - Alt text
   - External URLs (http/https)

## Manual Markdown Transformation

### Endpoint: `POST /transform_markdown`

For manual transformation of markdown content.

**Request Body:**
```json
{
  "content": "# My Doc\n![[image.png]]",
  "server_url": "http://localhost:7001",
  "vault_path": "/path/to/vault",
  "current_file_path": "folder/file.md"
}
```

**Response:**
```json
{
  "original": "# My Doc\n![[image.png]]",
  "transformed": "# My Doc\n![image.png](http://localhost:7001/images/image.png)",
  "status": 0,
  "message": "Successful"
}
```

## Using the Python API

You can also use the transformation functions directly in Python:

```python
from markdown_transformer import transform_markdown_images

# Basic transformation
markdown = "![[screenshot.png]]"
transformed = transform_markdown_images(
    markdown,
    server_url="http://localhost:7001"
)

# With vault context for relative path resolution
transformed = transform_markdown_images(
    markdown,
    server_url="http://localhost:7001",
    vault_path="/path/to/vault",
    current_file_path="notes/my-note.md"
)
```

### Batch Transform Notes

```python
from markdown_transformer import batch_transform_notes

notes = [
    {"content": "![[image1.png]]", "url": "note1.md"},
    {"content": "![[image2.png]]", "url": "note2.md"}
]

transformed_notes = batch_transform_notes(
    notes,
    server_url="http://localhost:7001",
    vault_path="/path/to/vault"
)
```

## Integration with Monitoring Script

The monitoring script (`step4_monitor.py`) can automatically pass the vault path to the server:

```bash
# The server will be started with --vault-path automatically
uv run step4_monitor.py --vault-path /path/to/vault
```

## Supported Image Formats

- JPEG/JPG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- BMP (`.bmp`)
- SVG (`.svg`)
- WebP (`.webp`)
- ICO (`.ico`)

## Security Considerations

1. **Path Traversal Protection**: The server validates that all image paths remain within the vault directory
2. **File Type Validation**: Only files with image extensions are served
3. **CORS Support**: The server includes CORS middleware for cross-origin requests
4. **SSL Support**: Can be enabled with `--ssl-cert` and `--ssl-key` arguments

## Example Workflow

1. Start the Kuzu server with vault path:
   ```bash
   python kuzu_server.py ./my_database.kz --vault-path ~/Obsidian/MyVault
   ```

2. Query for Note content:
   ```cypher
   MATCH (n:Note) RETURN n.content LIMIT 1
   ```

3. The returned content will have transformed image links:
   ```markdown
   # My Note
   ![screenshot](http://localhost:7001/images/attachments/screenshot.png)
   ```

4. Access images directly via browser:
   ```
   http://localhost:7001/images/attachments/screenshot.png
   ```

## Troubleshooting

### Images not loading

1. Check that the server was started with `--vault-path`
2. Verify the image path exists in the vault
3. Check server logs for path resolution errors

### Transformation not working

1. Ensure vault_path is correctly set
2. Check that Note nodes have the `content` property
3. Verify the markdown format is supported

### Path resolution issues

1. Use vault-relative paths in markdown
2. Check that the file's `url` property is correctly set
3. Enable debug logging with `--debug` flag

## Future Enhancements

Possible future improvements:
- Image caching and optimization
- Thumbnail generation
- Image format conversion
- CDN support for distributed access







