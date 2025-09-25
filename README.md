# Obsidian Knowledge Map

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A powerful CLI tool that transforms your Obsidian vault into an intelligent knowledge map using semantic chunking and AI-powered entity and relationship extraction. Built with Kuzu database and connect to Kineviz's GraphXR.

## 🚀 Features

- **🧠 Semantic Chunking**: Intelligent content chunking based on semantic similarity using the chonkie library
- **📊 Knowledge Graph**: Creates a Kuzu database with entities, observations, and relationships
- **⚡ Real-time Monitoring**: Watches your Obsidian vault for changes and auto-updates the knowledge graph
- **🔄 Incremental Updates**: Only processes changed files based on content hash for efficiency
- **🔗 Obsidian Integration**: Supports Obsidian `[[link]]` syntax for note-to-note relationships
- **📝 Metadata Support**: Extracts and processes Obsidian frontmatter metadata (YAML, tags, properties)
- **🔍 Entity Resolution**: Declarative entity resolution through metadata - specify entity mappings directly in note frontmatter
- **🤖 AI-Powered**: Extracts observations and entities using OpenAI GPT models (other models to follow)
- **🌐 Connect to GraphXR**: Provides a REST API server for access and visualization in GraphXR
- **⚡ Concurrent Processing**: Processes multiple files in parallel for better performance

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Database Schema](#-database-schema)
- [Configuration](#-configuration)
- [Docker Support](#-docker-support)
- [Contributing](#-contributing)
- [License](#-license)

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key

### 1. Clone and Setup

```bash
git clone https://github.com/kineviz/Obsidian-knowledgemap.git
cd Obsidian-knowledgemap
```

### 2. Environment Configuration

Create a `.env` file in the `cli/` directory:

```bash
cd cli
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

### 3. Start Real-time Monitoring (Recommended)

```bash
# Start monitoring with integrated server
uv run step4_monitor.py --vault-path /path/to/obsidian/vault --server-port 7001
```

This will:
- ✅ Start monitoring your Obsidian vault for markdown file changes
- ✅ Automatically extract knowledge and update the database when files change
- ✅ Start a Neo4j-compatible API server on port 7001
- ✅ Provide endpoints at `http://localhost:7001/`

### 4. Access Your Knowledge Graph

Once running, you can access:
- **Health Check**: `http://localhost:7001/health`
- **GraphXR**: `http://localhost:7001/kuzudb/kuzu_db` (Neo4j-compatible endpoints)
- **Debug Info**: `http://localhost:7001/debug/crashes`

### 5. Visual analysis with GraphXR

To visualize and analyze your knowledge graph with advanced graph analytics:

1. **Create Account**: Visit [https://graphxr.kineviz.com](https://graphxr.kineviz.com) and create a free account
2. **Request Access**: Contact support to request access to GraphXR 3.0, which includes Kuzu database support
3. **Connect**: Once approved, you can connect GraphXR directly to your running knowledge map server at `http://localhost:7001/kuzudb/kuzu_db`

This enables advanced graph visualization, analytics, and exploration of your Obsidian knowledge network.


## 📦 Installation

### Using uv (Recommended)

```bash
# Install dependencies
cd cli
uv sync

# Run the tool
uv run step4_monitor.py --vault-path /path/to/vault --server-port 7001
```

### Using pip

```bash
cd cli
pip install -e .
```

## 💻 Usage

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
uv run kuzu_server.py /path/to/kuzu/database --port 7001
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

#### Server (kuzu_server.py)
- `db_path`: Path to Kuzu database (required)
- `--port`: Port to run server on (default: 7001)
- `--host`: Host to bind to (default: 0.0.0.0)
- `--ssl-cert`: Path to SSL certificate file (enables HTTPS)
- `--ssl-key`: Path to SSL private key file (required with --ssl-cert)

## 🔧 API Reference

### Health Check
```bash
curl http://localhost:7001/health
```

### Cypher Queries
```bash
curl -X POST http://localhost:7001/db/data/transaction/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (p:Person) RETURN p.label LIMIT 5"}]}'
```

### Debug Information
```bash
curl http://localhost:7001/debug/crashes
```

## 🗄️ Database Schema

In Default, the tool creates a Kuzu database with the following schema: (Will add configurability later)

### Node Types
- **Person**: Extracted person entities
- **Company**: Extracted company/organization entities (including educational institutions)
- **Note**: Markdown files with content and Obsidian links
- **Source**: Original markdown files
- **Chunk**: Semantically chunked content pieces
- **Observation**: AI-extracted insights and facts
- **Entity**: AI-extracted entities (people, companies, concepts)

### Relationship Types
- **PERSON_TO_PERSON**: Relationships between people
- **PERSON_TO_COMPANY**: Relationships between people and companies
- **COMPANY_TO_COMPANY**: Relationships between companies
- **PERSON_REFERENCE**: Person entities referenced in notes
- **COMPANY_REFERENCE**: Company entities referenced in notes
- **NOTE_TO_NOTE**: Obsidian `[[link]]` relationships between notes
- **HAS_CHUNK**: Source files contain chunks
- **HAS_OBSERVATION**: Chunks contain observations
- **HAS_ENTITY**: Observations reference entities

### Data Storage
- **Vault-centric**: All data stored in `.kineviz_graph/` within the Obsidian vault
- **Cache system**: CSV files for incremental updates and reliability
- **Auto-cleanup**: Database is cleared and rebuilt on each update

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the `cli/` directory:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
CHUNK_THRESHOLD=0.75
CHUNK_SIZE=1024
EMBEDDING_MODEL=minishlab/potion-base-8M
MAX_CONCURRENT=5
```

### Semantic Chunking Parameters

- **threshold**: Controls how similar content must be to be grouped together (0.0-1.0)
  - Higher values (0.8-0.9): More strict grouping, smaller chunks
  - Lower values (0.5-0.7): More lenient grouping, larger chunks
- **chunk_size**: Maximum number of tokens per chunk
- **embedding_model**: The embedding model used for semantic similarity

## 🐳 Docker Support

The project includes Docker support for easy deployment:

```bash
# Build the image
docker build -t obsidian-knowledgemap .

# Run with docker-compose
docker-compose up -d

# Or run directly
docker run -p 7001:7001 -v /path/to/vault:/vault obsidian-knowledgemap
```

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

## 🔄 Monitoring Workflow

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

## 🧪 Skip Extraction Mode

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

## 📁 Project Structure

```
Obsidian-knowledgemap/
├── cli/                          # Main CLI application
│   ├── main_obsidian.py         # Main entry point
│   ├── step1_extract.py         # File extraction
│   ├── step2_organize.py        # Data organization
│   ├── step3_build.py           # Database building
│   ├── step4_monitor.py         # Real-time monitoring
│   ├── kuzu_server.py           # Neo4j-compatible server
│   ├── entity_resolution.py     # Entity resolution logic
│   ├── metadata_extractor.py    # Metadata extraction
│   └── tests/                   # Test suite
├── ai/                          # AI specifications and schemas
├── docker-compose.yml           # Docker configuration
├── Dockerfile                   # Docker image definition
└── README.md                    # This file
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/kineviz/Obsidian-knowledgemap.git
cd Obsidian-knowledgemap

# Install development dependencies
cd cli
uv sync --dev

# Run tests
uv run pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Kuzu](https://github.com/kuzudb/kuzu) - High-performance graph database
- [chonkie](https://github.com/ai2ys/chonkie) - Semantic chunking library
- [OpenAI](https://openai.com/) - AI-powered entity extraction
- [Obsidian](https://obsidian.md/) - The amazing note-taking app

## 📞 Support

- 📧 Email: info@kineviz.com
- 🐛 Issues: [GitHub Issues](https://github.com/kineviz/Obsidian-knowledgemap/issues)
- 📖 Documentation: [Project Wiki](https://github.com/kineviz/Obsidian-knowledgemap/wiki)


