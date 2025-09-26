# LLM Testing Suite

This folder contains all LLM benchmarking and testing code for the Obsidian Knowledge Map project.

## Contents

### Core Files
- **`llm_benchmark.py`** - Main benchmarking script comparing different LLM models
- **`test_ollama_endpoints.py`** - Script to test Ollama endpoint connectivity
- **`requirements_benchmark.txt`** - Python dependencies for benchmarking

### Documentation
- **`LLM_BENCHMARK_RESULTS.md`** - Comprehensive benchmark results and analysis
- **`README_BENCHMARK.md`** - Instructions for running benchmarks
- **`README.md`** - This file

### Results
- **`llm_benchmark_results_*.json`** - Detailed benchmark results (if any exist)

## Quick Start

1. **Install dependencies:**
   ```bash
   cd LLM_test
   pip install -r requirements_benchmark.txt
   ```

2. **Test Ollama endpoints:**
   ```bash
   python test_ollama_endpoints.py
   ```

3. **Run benchmark:**
   ```bash
   python llm_benchmark.py
   ```

## Key Findings

- **Gemma3:4b**: Poor instruction following, uses generic "works_at" instead of specific relationship types
- **Gemma3:12b**: Good instruction following, accuracy similar to GPT-4o-mini
- **Token Efficiency**: Gemma3:12b uses 37% fewer tokens than GPT-4o-mini
- **Speed**: Local models are competitive with API models on high-end hardware

## Hardware Tested

- M4 Max Mac Studio (64GB RAM) - Best performance
- M2 Max Mac Studio (32GB RAM) - Good balance
- M1 Max MBP (64GB RAM) - Adequate for development
- M4 Pro MBP (48GB RAM) - Slower but functional

## Models Tested

- **OpenAI GPT-4o-mini** - API baseline
- **Gemma3:12b** - Best local alternative
- **Gemma3:4b** - Fast but poor instruction following

See `LLM_BENCHMARK_RESULTS.md` for detailed analysis and recommendations.
