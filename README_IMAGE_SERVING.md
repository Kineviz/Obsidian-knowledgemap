# Image Serving Feature

This document provides a quick guide to using the image serving feature.

## Quick Start

### 1. Start the server with image serving enabled

```bash
cd cli
python kuzu_server.py /path/to/vault/.kineviz_graph/database/knowledge_graph.kz \
    --vault-path /path/to/vault \
    --port 7001
```

Or use the convenience script:
```bash
cd cli
./start_server.sh /path/to/vault 7001
```

### 2. Access images via the API

Images are available at: `http://localhost:7001/images/{path}`

For example, if your vault has an image at `assets/screenshot.png`, access it at:
```
http://localhost:7001/images/assets/screenshot.png
```

### 3. Automatic Markdown Transformation

When you query Note nodes, the markdown content is automatically transformed to use the server's image endpoint:

**Before (in Note):**
```markdown
![[screenshot.png]]
![My Image](./images/photo.jpg)
```

**After (in API response):**
```markdown
![screenshot.png](http://localhost:7001/images/screenshot.png)
![My Image](http://localhost:7001/images/images/photo.jpg)
```

## Supported Image Formats

- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- BMP (`.bmp`)
- SVG (`.svg`)
- WebP (`.webp`)
- ICO (`.ico`)

## Manual Transformation Endpoint

Transform markdown content manually using the `/transform_markdown` endpoint:

```bash
curl -X POST http://localhost:7001/transform_markdown \
  -H 'Content-Type: application/json' \
  -d '{
    "content": "# My Doc\n![[image.png]]",
    "server_url": "http://localhost:7001"
  }'
```

## Integration with Monitoring

The monitoring script (`step4_monitor.py`) automatically passes the vault path to the server:

```bash
uv run step4_monitor.py --vault-path /path/to/vault --server-port 7001
```

## Security

- Path traversal protection: Only files within the vault directory can be accessed
- File type validation: Only image files are served
- CORS enabled for cross-origin requests

## Testing

Run the test script to verify everything works:

```bash
cd cli
./test_image_serving.sh /path/to/vault
```

## Documentation

For detailed documentation, see [IMAGE_SERVING.md](cli/IMAGE_SERVING.md)

## Example Queries

Once the server is running with vault path:

```cypher
# Get a note with transformed image links
MATCH (n:Note) WHERE n.label = "My Note" RETURN n.content
```

The returned content will have all image links transformed to point to the server endpoint.

## Troubleshooting

### Images not loading
- Verify the server was started with `--vault-path`
- Check that the image path exists in the vault
- Review server logs for path resolution errors

### Transformation not working
- Ensure vault_path is correctly set when starting the server
- Verify Note nodes have the `content` property
- Check that the markdown format is supported (Obsidian wiki-style or standard markdown)

## Using in Python

You can also use the transformation functions directly:

```python
from markdown_transformer import transform_markdown_images

markdown = "![[screenshot.png]]"
transformed = transform_markdown_images(
    markdown,
    server_url="http://localhost:7001",
    vault_path="/path/to/vault",
    current_file_path="notes/my-note.md"
)
print(transformed)
# Output: ![screenshot.png](http://localhost:7001/images/screenshot.png)
```







