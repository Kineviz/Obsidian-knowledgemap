# Obsidian Knowledge Map

Transform your Obsidian vault into an intelligent knowledge graph using AI-powered entity and relationship extraction.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A powerful CLI tool that transforms your Obsidian vault into an intelligent knowledge map using semantic chunking and AI-powered entity and relationship extraction. Built with Kuzu database and connect to Kineviz's GraphXR.

## 🚀 Features

- **🖼️ Image Serving**: NEW! Serve images directly from your vault with automatic markdown link transformation ([details](README_IMAGE_SERVING.md))
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
  - [Environment Variables](#environment-variables-env-file)
  - [AI Prompt Configuration](#ai-prompt-configuration)
  - [LLM Configuration](#llm-configuration-llm_configyaml)
- [Docker Support](#-docker-support)
- [Contributing](#-contributing)
- [License](#-license)

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

### 2. Start Monitoring and Kuzu Server
```bash
# Start monitoring - builds database automatically if needed
uv run cli/step4_monitor.py
```

### 3. Use the API
The system provides a REST API for accessing your knowledge graph:

```bash
# Query the graph
curl "http://localhost:7001/cypher?query=MATCH (n) RETURN n LIMIT 10"

# Upload a markdown file
curl -X POST "http://localhost:7001/save-markdown" \
  -H "Content-Type: application/json" \
  -d '{"filename": "My Note.md", "content": "# My Note\n\nThis is a test note with some content."}'
```

## 📋 API Endpoints

### Graph Query
- **GET** `/cypher?query={cypher_query}` - Execute Cypher queries
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