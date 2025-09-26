# LLM Benchmarking Tool

This tool compares different LLM setups for relationship extraction speed and accuracy.

## Setup

1. **Install additional dependencies:**
   ```bash
   uv add aiohttp openai
   ```

2. **Ensure Ollama is running on target machines:**
   ```bash
   # On each target machine
   ollama serve
   ollama pull gemma2:12b
   ```

3. **Set up OpenAI API key in .env:**
   ```bash
   OPENAI_API_KEY=your_key_here
   ```

## Usage

### 1. Test Ollama Endpoints
First, check which Ollama endpoints are available:

```bash
uv run python test_ollama_endpoints.py
```

### 2. Run Full Benchmark
Run the complete benchmark comparing all LLM setups:

```bash
uv run python llm_benchmark.py
```

## What It Tests

- **OpenAI GPT-4o-mini** (your current setup)
- **Gemma2:12b on Ollama** (4 different endpoints)
- **Speed**: Response time per request
- **Accuracy**: Correctly extracted relationships vs expected
- **Reliability**: Success rate and error handling

## Test Document

The benchmark uses a standardized test document with known relationships:
- John Smith works at Acme Corp
- John Smith is married to Sarah Johnson
- Sarah Johnson works at TechCorp
- Acme Corp partners with TechCorp
- John Smith graduated from Harvard University
- Acme Corp is located in Silicon Valley

## Output

The tool generates:
1. **Console table** with performance comparison
2. **JSON file** with detailed results (`llm_benchmark_results_TIMESTAMP.json`)
3. **Summary statistics** (fastest, most accurate, etc.)

## Expected Results

- **OpenAI**: Fast, accurate, but costs tokens
- **Ollama**: Free, but may be slower depending on hardware
- **Local Ollama**: Fastest if running locally
- **Remote Ollama**: Depends on network and remote hardware

## Troubleshooting

### Ollama Issues
- Ensure Ollama is running: `ollama serve`
- Check model is installed: `ollama list`
- Install model: `ollama pull gemma2:12b`
- Check network connectivity

### OpenAI Issues
- Verify API key in `.env` file
- Check API quota and billing
- Ensure internet connectivity

### Performance Issues
- Increase timeout in `LLMConfig` if needed
- Check system resources (CPU, RAM)
- Monitor network latency for remote endpoints
