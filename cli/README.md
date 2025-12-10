# CLI Directory Structure

This directory contains the main CLI application for the Obsidian Knowledge Map.

## Core Application Files

- `main.py` - Main entry point for knowledge graph operations
- `main_obsidian.py` - Obsidian-specific entry point
- `step1_extract.py` - Step 1: Extract relationships from markdown files
- `step2_organize.py` - Step 2: Organize extracted relationships
- `step3_build.py` - Step 3: Build knowledge graph database
- `step3b_postprocess.py` - Step 3b: Post-processing operations
- `step4_monitor.py` - Step 4: Monitor vault for changes

## Core Modules

- `classification/` - Classification task system (tasks, database, classifier)
- `config_loader.py` - Configuration management
- `llm_client.py` - LLM client with load balancing
- `prompt_loader.py` - Prompt loading and management
- `entity_resolution.py` - Entity name resolution
- `file_tracker.py` - File change tracking
- `metadata_extractor.py` - Metadata extraction
- `metadata_manager.py` - Metadata management
- `obsidian_config_reader.py` - Obsidian configuration reading
- `kuzu_server.py` - Kuzu database server
- `kuzu_server_manager.py` - Kuzu server management
- `kuzu_pool.py` - Connection pooling

## Server & UI

- `classification_server.py` - FastAPI server for classification tasks
- `classification_task_manager.py` - CLI for managing classification tasks
- `classification_ui.html` - Web UI for classification tasks

## Directory Structure

- `tests/` - Test scripts
- `scripts/debug/` - Debug and diagnostic scripts
- `scripts/utils/` - Utility scripts (init_sample_tasks, etc.)
- `benchmarks/` - Benchmark scripts and results
- `docs/` - Documentation files
- `cache/` - Cache directory for extracted data
- `logs/` - Log files

## Shell Scripts

- `run.sh` - Run the application
- `start_server.sh` - Start the server
- `monitor.sh` - Monitor script
- `rebuild_knowledge_graph.sh` - Rebuild knowledge graph
- `update_knowledge_graph.sh` - Update knowledge graph

