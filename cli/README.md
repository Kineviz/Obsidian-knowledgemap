# Knowledge Map Tool

A CLI tool for converting markdown files to a Kuzu knowledge graph with semantic chunking and real-time monitoring.

## Features

- **Semantic Chunking**: Uses chonkie library for intelligent content chunking based on semantic similarity
- **Knowledge Graph**: Creates a Kuzu database with entities, observations, and relationships
- **Incremental Updates**: Only processes changed files based on content hash
- **Concurrent Processing**: Processes multiple files in parallel
- **LLM Integration**: Extracts observations and entities using OpenAI GPT models
- **Real-time Monitoring**: Watches Obsidian vault for changes and auto-updates the knowledge graph
- **Neo4j-Compatible API**: Provides a Neo4j-compatible REST API server for external access
- **Obsidian Integration**: Supports Obsidian `[[link]]` syntax for note-to-note relationships

## Installation

The tool uses uv for dependency management. Dependencies are defined in the script header:

```python
# requires-python = ">=3.13"
# dependencies = [
#     "chonkie[semantic]",
#     "click",
#     "httpx",
#     "hishel",
#     "kuzu",
#     "python-dotenv",
#     "rich",
#     "openai",
#     "pydantic",
# ]
```

## Quick Start

### 1. Set up Environment

Create a `.env` file with your OpenAI API key:
```bash
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

### 2. Start the Monitor with Integrated Server

For real-time monitoring of an Obsidian vault with integrated Neo4j-compatible API server:

```bash
uv run step4_monitor.py --vault-path /path/to/obsidian/vault --server-port 7001
```

This will:
- Start monitoring your Obsidian vault for markdown file changes
- Automatically extract knowledge and update the database when files change
- Start a Neo4j-compatible API server on port 7001
- Provide endpoints at `http://localhost:7001/`

### 3. Access the API

Once running, you can access:
- **Health Check**: `http://localhost:7001/health`
- **Neo4j API**: `http://localhost:7001/` (Neo4j-compatible endpoints)
- **Debug Info**: `http://localhost:7001/debug/crashes`

## Usage

### Real-time Monitoring (Recommended)

```bash
# Start monitor with integrated server
uv run step4_monitor.py --vault-path /path/to/obsidian/vault --server-port 7001

# With custom options
uv run step4_monitor.py \
  --vault-path /path/to/obsidian/vault \
  --server-port 7001 \
  --max-concurrent 3
```

### Manual Processing

For one-time processing without monitoring:

```bash
# Process entire vault
uv run main_obsidian.py /path/to/obsidian/vault

# Individual steps
uv run step1_extract.py --vault-path /path/to/obsidian/vault
uv run step2_organize.py --vault-path /path/to/obsidian/vault  
uv run step3_build.py --vault-path /path/to/obsidian/vault
```

### Standalone Server

To run just the Neo4j-compatible server:

```bash
uv run kuzu_neo4j_server.py /path/to/kuzu/database --port 7001
```

### Command Line Options

#### Monitor (step4_monitor.py)
- `--vault-path`: Path to Obsidian vault (required)
- `--server-port`: Port for Kuzu Neo4j server (default: 7001)
- `--max-concurrent`: Maximum number of concurrent file processing tasks (default: 5)

#### Manual Processing (main_obsidian.py)
- `vault_path`: Path to Obsidian vault (required)
- `--openai-api-key`: OpenAI API key (or set OPENAI_API_KEY env var)
- `--max-concurrent`: Maximum number of concurrent file processing tasks (default: 5)
- `--chunk-threshold`: Semantic similarity threshold for chunking (0.0-1.0, default: 0.75)
- `--chunk-size`: Maximum chunk size in tokens (default: 1024)
- `--embedding-model`: Embedding model for semantic chunking (default: minishlab/potion-base-8M)

#### Server (kuzu_neo4j_server.py)
- `db_path`: Path to Kuzu database (required)
- `--port`: Port to run server on (default: 7001)
- `--host`: Host to bind to (default: 0.0.0.0)
- `--ssl-cert`: Path to SSL certificate file (enables HTTPS)
- `--ssl-key`: Path to SSL private key file (required with --ssl-cert)

## Skip Extraction Mode

When using the `--skip-extraction` flag, the tool will:

- ✅ Process markdown files and create Source nodes
- ✅ Perform semantic chunking and create Chunk nodes
- ❌ Skip LLM-based observation and entity extraction
- ❌ Skip creating Observation and Entity nodes

This mode is useful for:
- Testing semantic chunking without expensive LLM calls
- Creating a basic document structure for later processing
- When you only need the chunked content without knowledge extraction
- Development and debugging

**Note**: When using `--skip-extraction`, you don't need an OpenAI API key.

## Semantic Chunking

The tool uses chonkie's SemanticChunker to create intelligent content chunks based on semantic similarity rather than simple word count. This ensures that related content stays together in the same chunk, improving the quality of knowledge extraction.

### Chunking Parameters

- **threshold**: Controls how similar content must be to be grouped together (0.0-1.0)
  - Higher values (0.8-0.9): More strict grouping, smaller chunks
  - Lower values (0.5-0.7): More lenient grouping, larger chunks
- **chunk_size**: Maximum number of tokens per chunk
- **embedding_model**: The embedding model used for semantic similarity

## Database Schema

The tool creates a Kuzu database with the following simplified schema:

### Node Types
- **Person**: Extracted person entities
- **Company**: Extracted company/organization entities (including educational institutions)
- **Note**: Markdown files with content and Obsidian links

### Relationship Types
- **PERSON_TO_PERSON**: Relationships between people
- **PERSON_TO_COMPANY**: Relationships between people and companies
- **COMPANY_TO_COMPANY**: Relationships between companies
- **PERSON_REFERENCE**: Person entities referenced in notes
- **COMPANY_REFERENCE**: Company entities referenced in notes
- **NOTE_TO_NOTE**: Obsidian `[[link]]` relationships between notes

### Data Storage
- **Vault-centric**: All data stored in `.kineviz_graph/` within the Obsidian vault
- **Cache system**: CSV files for incremental updates and reliability
- **Auto-cleanup**: Database is cleared and rebuilt on each update

## Monitoring Workflow

When you start the monitor, it follows this workflow:

1. **Startup**: 
   - Starts Kuzu Neo4j server on specified port
   - Begins watching Obsidian vault for file changes

2. **File Change Detection**:
   - Detects markdown file changes (create/edit/delete)
   - Debounces rapid changes (waits 10 seconds for stability)

3. **Processing Pipeline**:
   - **Step 1**: Extract relationships from changed files → `cache/content/`
   - **Step 2**: Organize cache → `cache/db_input/` (entities and relationships)
   - **Step 3**: Stop server, rebuild database, restart server

4. **Server Management**:
   - Automatically stops server before database rebuild
   - Restarts server after successful rebuild
   - Provides Neo4j-compatible API endpoints

## Example Queries

Once the server is running, you can query the knowledge graph:

```bash
# Check server health
curl http://localhost:7001/health

# Query via Neo4j-compatible API
curl -X POST http://localhost:7001/db/data/transaction/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (p:Person) RETURN p.label LIMIT 5"}]}'
```

## Deploy with pyinstaller

```bash
pyinstaller main.py
```