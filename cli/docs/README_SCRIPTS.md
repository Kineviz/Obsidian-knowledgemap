# Knowledge Graph Scripts

This directory contains shell scripts to manage your knowledge graph system.

## Available Scripts

### 1. `update_knowledge_graph.sh` (Recommended)
**Simple and efficient** - runs manual trigger and starts the server in foreground.

```bash
./update_knowledge_graph.sh <vault_path> [port]
```

**Example:**
```bash
./update_knowledge_graph.sh '/Users/username/Documents/Obsidian_root/test' 7001
```

**What it does:**
1. ✅ Runs manual trigger (detects changes, processes files, builds database)
2. ✅ Starts Kuzu server in foreground (you can see all server activity)

### 2. `rebuild_knowledge_graph.sh` (Full rebuild)
**Complete rebuild** - runs all steps separately for maximum control.

```bash
./rebuild_knowledge_graph.sh <vault_path> [port]
```

**Example:**
```bash
./rebuild_knowledge_graph.sh '/Users/username/Documents/Obsidian_root/test' 7001
```

**What it does:**
1. ✅ Runs manual trigger
2. ✅ Stops Kuzu server
3. ✅ Builds Kuzu database
4. ✅ Starts Kuzu server in foreground (you can see all server activity)

### 3. `start_server.sh` (Server only)
**Just start the server** - if you've already processed files and just want to start the server.

```bash
./start_server.sh <vault_path> [port]
```

**Example:**
```bash
./start_server.sh '/Users/username/Documents/Obsidian_root/test' 7001
```

**What it does:**
1. ✅ Checks if database exists
2. ✅ Starts Kuzu server in foreground (you can see all server activity)

## Manual Commands

### Process Changes Only
```bash
uv run manual_trigger.py --vault-path '/path/to/vault'
```

### Start Server Only
```bash
uv run kuzu_server.py '/path/to/vault/.kineviz_graph/database/knowledge_graph.kz' --port 7001
```

### Stop Server
```bash
pkill -f kuzu_server
```

## Server Access

Once running, access your knowledge graph at:
- **Graph Interface**: http://localhost:7001
- **Health Check**: http://localhost:7001/health
- **Debug Info**: http://localhost:7001/debug/crashes

## Logs

- **Server Logs**: `logs/kuzu_server.log`
- **Error Logs**: `logs/kuzu_errors.log`

## Simple Usage

The shell scripts provide a simple way to manage your knowledge graph:

1. **Update**: `./update_knowledge_graph.sh '/path/to/vault' [port]` - Processes changes and starts server in foreground
2. **Rebuild**: `./rebuild_knowledge_graph.sh '/path/to/vault' [port]` - Complete rebuild and starts server in foreground
3. **Start Server**: `./start_server.sh '/path/to/vault' [port]` - Just start the server in foreground
4. **Check Status**: `./check_knowledge_graph_status.sh [port]` - Check if server is running

### Quick Start

```bash
# Update your knowledge graph (recommended)
./update_knowledge_graph.sh '/Users/username/Documents/Obsidian_root/test'

# Rebuild from scratch
./rebuild_knowledge_graph.sh '/Users/username/Documents/Obsidian_root/test'

# Just start the server (if already processed)
./start_server.sh '/Users/username/Documents/Obsidian_root/test'

# Check if server is running
./check_knowledge_graph_status.sh
```

### Foreground vs Background

All scripts now run the server in **foreground** by default, which means:
- ✅ **Real-time logs** - You can see all server activity
- ✅ **Easy debugging** - Any errors are immediately visible
- ✅ **Simple control** - Press `Ctrl+C` to stop the server
- ✅ **No background processes** - Cleaner system resource usage

If you need to run the server in background, you can still use the manual commands below.

## Troubleshooting

### Server won't start
1. Check if port is already in use: `lsof -i :7001`
2. Kill existing processes: `pkill -f kuzu`
3. Check logs: `tail -f logs/kuzu_server.log`

### Database issues
1. Clear database: `rm -rf /path/to/vault/.kineviz_graph/database/`
2. Run manual trigger to rebuild

### File changes not detected
1. Run manual trigger: `uv run manual_trigger.py --vault-path '/path/to/vault'`
2. Check file permissions and paths
