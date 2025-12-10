# Model Benchmark Script

This script benchmarks different LLM models for:
1. **Knowledge Map extraction** (relationship extraction from text)
2. **VC multi-tag classification** (extracting VC profile metadata)

## Models Tested

- `qwen3:8b` (Ollama on bsrs-mac-studio)
- `qwen3:14b` (Ollama on bsrs-mac-studio)
- `llama3.1:8b` (Ollama on bsrs-mac-studio)
- `gpt-4o-mini` (OpenAI cloud)

## Usage

```bash
cd cli
uv run benchmark_models.py "Companies/VC/Eniac Ventures.md"
```

Or with absolute path:
```bash
uv run benchmark_models.py "/path/to/Eniac Ventures.md"
```

### Options

- `--output, -o`: Specify output JSON file (default: `benchmark_results_YYYYMMDD_HHMMSS.json`)

Example:
```bash
uv run benchmark_models.py "Companies/VC/Eniac Ventures.md" -o results.json
```

## What It Tests

### 1. Knowledge Map Extraction
- Extracts relationships between Person and Company entities
- Uses the standard relationship extraction prompt
- Measures:
  - Success rate
  - Response time
  - Number of relationships extracted

### 2. VC Multi-Tag Classification
- Runs the `gxr_vc_analysis` multi-tag task
- Extracts VC profile metadata (stages, sectors, etc.)
- Measures:
  - Success rate
  - Response time
  - Classification accuracy (if measurable)

## Output

The script generates:
1. **Console output**: Real-time progress and formatted tables
2. **JSON file**: Detailed results with timestamps and full data

### Console Tables

- **Knowledge Map Extraction Results**: Shows success, time, and relationship count for each model
- **VC Classification Results**: Shows success and time for each model
- **Speed Comparison**: Side-by-side comparison of all models

### JSON Output Format

```json
{
  "test_file": "/path/to/file.md",
  "test_file_size": 7477,
  "timestamp": "2025-12-09T...",
  "results": [
    {
      "model": "qwen3:8b",
      "provider": "ollama",
      "task_type": "knowledge_map",
      "success": true,
      "response_time": 12.34,
      "token_count": 1234,
      "result": {
        "relationships_count": 15,
        "relationships": [...]
      }
    },
    ...
  ]
}
```

## Prerequisites

1. **VC Classification Task**: The `gxr_vc_analysis` task must exist in your database
2. **Ollama Server**: `bsrs-mac-studio:11434` must be accessible with the models loaded
3. **OpenAI API Key**: Must be set in `.env` for GPT-4o-mini testing
4. **Test File**: The specified markdown file must exist in your vault

## Notes

- The script temporarily modifies the config to test different models
- Each test runs with `force=True` to ensure fresh results
- There's a 1-2 second delay between tests to avoid overwhelming the servers
- Failed tests are logged with error messages for debugging

## Example Output

```
╭─────────────────────────────────────────────────────────────╮
│              Model Benchmark Suite                           │
│  Comparing models for Knowledge Map extraction and VC       │
│  classification                                             │
╰─────────────────────────────────────────────────────────────╯

Testing qwen3:8b for Knowledge Map extraction...
✓ Knowledge Map: 12.34s, 15 relationships
✓ VC Classification: 8.76s

Testing qwen3:14b for Knowledge Map extraction...
✓ Knowledge Map: 18.45s, 16 relationships
✓ VC Classification: 14.23s

...

╭─────────────────────────────────────────────────────────────╮
│              Benchmark Results Summary                      │
╰─────────────────────────────────────────────────────────────╯

Knowledge Map Extraction
┌─────────────┬──────────┬─────────┬──────────┬──────────────┬───────┐
│ Model       │ Provider │ Success │ Time (s)  │ Relationships │ Error │
├─────────────┼──────────┼─────────┼──────────┼──────────────┼───────┤
│ qwen3:8b    │ ollama   │   ✓     │   12.34  │      15       │       │
│ qwen3:14b   │ ollama   │   ✓     │   18.45  │      16       │       │
│ llama3.1:8b │ ollama   │   ✓     │   15.67  │      14       │       │
│ gpt-4o-mini │ openai   │   ✓     │    8.23  │      17       │       │
└─────────────┴──────────┴─────────┴──────────┴──────────────┴───────┘

Speed Comparison (seconds)
┌─────────────┬───────────────┬──────────────────┬────────┐
│ Model       │ Knowledge Map │ VC Classification │ Total  │
├─────────────┼───────────────┼──────────────────┼────────┤
│ qwen3:8b    │     12.34     │       8.76       │ 21.10  │
│ qwen3:14b   │     18.45     │      14.23       │ 32.68  │
│ llama3.1:8b │     15.67     │      12.45       │ 28.12  │
│ gpt-4o-mini │      8.23     │       6.45       │ 14.68  │
└─────────────┴───────────────┴──────────────────┴────────┘
```

