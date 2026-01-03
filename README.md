# Obsidian Knowledge Map

Transform your Obsidian vault into an intelligent knowledge graph using AI-powered entity and relationship extraction.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Quick Start

### 1. Setup
```bash
git clone https://github.com/kineviz/Obsidian-knowledgemap.git
cd Obsidian-knowledgemap

# Install dependencies
uv sync

# Setup configuration
cp config_example.yaml config.yaml
cp .env.example .env

# Edit your settings
nano config.yaml  # Set vault path and other settings
nano .env         # Add your OpenAI API key
```

### 2. Start Classification Server, Monitoring and Kuzu Server
```bash
# Start monitoring - builds database automatically if needed
cd cli
uv run step4_monitor.py

# Start classification server on port 8000
uv run classification_server.py
```

### 3. Use the API
The system provides a REST API for accessing your knowledge graph:

```bash
# Query the graph (POST to /kuzudb/{database_name})
curl -X POST "http://localhost:7001/kuzudb/kuzu_db" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (n) RETURN n LIMIT 10"}'

# Get schema
curl -X POST "http://localhost:7001/kuzudb/kuzu_db" \
  -H "Content-Type: application/json" \
  -d '{"query": "CALL SCHEMA"}'

# Upload a markdown file
curl -X POST "http://localhost:7001/save-markdown" \
  -H "Content-Type: application/json" \
  -d '{"filename": "My Note.md", "content": "# My Note\n\nThis is a test note with some content."}'
```

## � Quick Docker Setup

If you prefer to run everything in Docker containers:

### 1. Setup Environment
```bash
git clone https://github.com/kineviz/Obsidian-knowledgemap.git
cd Obsidian-knowledgemap

# Copy and configure environment file
cp docker.env.example .env

# Edit the .env file with your settings:
# - OPENAI_API_KEY=your_openai_api_key_here  
# - VAULT_PATH=/path/to/your/obsidian/vault
# - SERVER_PORT=7001
nano .env
```

### 2. Start with Docker Management Script (Recommended)
```bash
# Start the service (builds if needed, cleans up old containers)
./docker-manage.sh start

# Check status and logs
./docker-manage.sh status
./docker-manage.sh logs
```

### 3. Alternative: Using Docker Compose Directly
```bash
# Start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop when done
docker-compose down
```

The Docker environment automatically:
- Builds the knowledge graph from your vault
- Starts the REST API server on the configured port
- Monitors for file changes and updates the graph
- Persists data in Docker volumes

## �📋 API Endpoints

### Graph Query
- **POST** `/kuzudb/{name}` - Execute Cypher queries
  ```json
  {"query": "MATCH (n) RETURN n LIMIT 10"}
  ```
- **GET** `/health` - Health check
- **GET** `/debug/crashes` - Debug information

### File Management
- **POST** `/save-markdown` - Upload markdown files to your vault
  ```json
  {
    "filename": "My Note.md",
    "content": "# My Note\n\nContent here..."
  }
  ```

## ⚙️ Configuration

The system uses two simple configuration files:

### `config.yaml` - All settings
```yaml
vault:
  path: "/path/to/your/obsidian/vault"

llm:
  provider: "cloud"  # or "ollama"
  cloud:
    openai:
      model: "gpt-4o-mini"

server:
  port: 7001
```

### `.env` - API keys only
```bash
OPENAI_API_KEY=your-openai-api-key-here
```

## 🔧 Management Commands

```bash
# Check configuration
uv run cli/manage_config.py status

# Validate setup
uv run cli/manage_config.py validate
```

## 📊 What It Does

1. **Scans** your Obsidian vault for markdown files
2. **Extracts** entities (people, companies, concepts) using AI
3. **Finds** relationships between entities
4. **Builds** a knowledge graph database
5. **Monitors** for changes and updates automatically
6. **Provides** REST API for GraphXR integration

## 🎯 Key Features

- **AI-Powered**: Uses OpenAI GPT models for entity extraction
- **Real-time**: Monitors vault changes and updates automatically  
- **REST API**: Connect to GraphXR or other visualization tools
- **Entity Resolution**: Handle aliases and name changes
- **Metadata Support**: Process Obsidian frontmatter and tags

## 📝 Obsidian Notes Guidelines

We use folder paths to organize different types of notes. The `entity_type` is derived from the path when entities are created in the database.

### Folder Structure

| Path Pattern | Entity Type | Notes |
|--------------|-------------|-------|
| `**/Persons/**/*.md` | Person | Note title should match person name |
| `**/Companies/**/*.md` | Company | Note title should match company name |
| `**/VC/**/*.md` | VC | Note title should match VC name |
| `**/Persons/VC/*.md` | Person + VC | Entities that are both Person and VC |
| `**/Companies/VC/*.md` | Company + VC | Entities that are both Company and VC |

### Best Practices

- **Use nested subfolders** to keep information organized (e.g., `Persons/Engineering/`, `Companies/Startups/`)
- **Match note titles to entity names** for proper entity resolution
- **Organize supporting content** (events, web research, etc.) under their respective folders

### Example Structure

```
vault/
├── Persons/
│   ├── Engineering/
│   │   └── John Doe.md
│   └── VC/
│       └── Jane Smith.md      # Both Person and VC
├── Companies/
│   ├── Startups/
│   │   └── Acme Corp.md
│   └── VC/
│       └── Sequoia Capital.md # Both Company and VC
├── VC/
│   └── Andreessen Horowitz.md
├── Events/
│   └── TechCrunch Disrupt 2024.md
└── Research/
    └── AI Trends Q4 2024.md
```

## 📁 Project Structure

```
├── cli/                    # Command-line tools
│   ├── step3_build.py     # Build knowledge graph
│   ├── step4_monitor.py   # Monitor for changes
│   └── kuzu_server.py     # REST API server
├── config.yaml            # Configuration file
├── .env                   # API keys
└── config_example.yaml    # Configuration template
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [GraphXR](https://www.kineviz.com/) - 3D graph visualization platform
- [Kuzu Database](https://kuzudb.com/) - Graph database engine
- [Obsidian](https://obsidian.md/) - Knowledge management tool