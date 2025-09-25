# Knowledge Map Tool - Obsidian Integration

## Quick Start

### 1. Setup
```bash
# Set OpenAI API key
echo "OPENAI_API_KEY=your_api_key_here" > .env

# Install dependencies
uv sync
```

### 2. Start Monitoring
```bash
# Start monitor with integrated Neo4j server
uv run step4_monitor.py --vault-path /path/to/obsidian/vault --server-port 7001
```

## What It Does

- **Watches** your Obsidian vault for markdown file changes
- **Extracts** Person and Company entities using AI
- **Creates** relationships between entities
- **Builds** a Kuzu knowledge graph database
- **Serves** Neo4j-compatible API on port 7001
- **Auto-updates** when you edit/create/delete markdown files

## Data Storage

All data is stored within your vault:
```
.vault/
├── .obsidian/          # Obsidian config
├── .kineviz_graph/     # Knowledge graph data
│   ├── cache/          # CSV cache files
│   ├── database/       # Kuzu database
│   └── logs/           # Server logs
└── your-notes.md       # Your markdown files
```

## API Access

Once running, access at `http://localhost:7001/`:

- **Health**: `http://localhost:7001/health`
- **Neo4j API**: `http://localhost:7001/kuzudb/kuzu_db/` (Neo4j-compatible)
- **Debug**: `http://localhost:7001/debug/crashes`

## Example Queries

```bash
# Check if running
curl http://localhost:7001/health

# Query people
curl -X POST http://localhost:7001/db/data/transaction/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (p:Person) RETURN p.label LIMIT 5"}]}'

# Query companies
curl -X POST http://localhost:7001/db/data/transaction/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (c:Company) RETURN c.label LIMIT 5"}]}'
```

## Workflow

1. **Start monitor** → Server starts, begins watching
2. **Edit markdown** → Detects change, waits 10s for stability
3. **Extract knowledge** → AI processes content, extracts entities
4. **Update database** → Stops server, rebuilds DB, restarts server
5. **API available** → Query your knowledge graph

## Stopping

Press `Ctrl+C` to stop monitoring and server.

## Troubleshooting

- **Port in use**: Change `--server-port` to different port
- **No entities found**: Check OpenAI API key in `.env`
- **Server won't start**: Check if database exists, run manual build first

## Manual Processing

If you prefer one-time processing without monitoring:

```bash
# Process entire vault once
uv run main_obsidian.py /path/to/obsidian/vault

# Then start server separately
uv run kuzu_server.py /path/to/obsidian/vault/.kineviz_graph/database/knowledge_graph.kz --port 7001
```
