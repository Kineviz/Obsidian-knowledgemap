# LLM Benchmark: Qwen3 vs GPT-4o-mini

**Date:** November 29, 2025  
**Task:** Knowledge Graph Relationship Extraction with Structured JSON Output

## Test Configuration

- **Test Document:** 1,857 characters (Tech Startup Network scenario)
- **Expected Relationships:** 14 ground-truth relationships
- **Ollama Server:** `bsrs-mac-studio:11434`

## Results Summary

| Model | Time (s) | Relationships | Precision | Recall | F1 Score | Tokens |
|-------|----------|---------------|-----------|--------|----------|--------|
| **Qwen3:8b** 🏆 | 13.41 | 14 | **100.0%** | **100.0%** | **100.0%** | 692 |
| Qwen3:14b | 19.33 | 14 | 92.9% | 92.9% | 92.9% | 621 |
| OpenAI GPT-4o-mini | 16.21 | 17 | 76.5% | 92.9% | 83.9% | 1,481 |
| Qwen3:4b ⚡ | **7.79** | 14 | 78.6% | 78.6% | 78.6% | 572 |

## Key Findings

### 🏆 Winner: Qwen3:8b

- **Perfect 100% F1 score** - All expected relationships correctly extracted
- **Faster than GPT-4o-mini** (13.4s vs 16.2s)
- **Lower token usage** (692 vs 1,481 tokens)

### ⚡ Speed Champion: Qwen3:4b

- **2x faster than GPT-4o-mini** (7.8s vs 16.2s)
- Good accuracy for speed-critical applications (78.6% F1)
- Lowest token usage (572 tokens)

### GPT-4o-mini Analysis

- Extracts more relationships (17 vs 14 expected)
- Higher recall (92.9%) but lower precision (76.5%)
- **Over-extraction issue**: Generates false positive relationships
- Highest token usage (1,481 tokens)

### Qwen3:14b Observation

- Slower than Qwen3:8b (19.3s vs 13.4s)
- Slightly less accurate (92.9% vs 100% F1)
- Diminishing returns from larger model size for this task

## Speed vs Accuracy Trade-off

```
⚡ 🎯 Qwen3:4b:        7.8s,  F1=78.6%  (Best speed)
⚡ 🎯 Qwen3:8b:       13.4s,  F1=100%   (Best overall)
🐢 🎯 GPT-4o-mini:   16.2s,  F1=83.9%  (Cloud API)
🐢 🎯 Qwen3:14b:     19.3s,  F1=92.9%  (Overkill)
```

## Recommendations

### For Production Use

| Use Case | Recommended Model | Reason |
|----------|-------------------|--------|
| **High Accuracy** | Qwen3:8b | Perfect F1, fast, local |
| **Speed Critical** | Qwen3:4b | 2x faster, acceptable accuracy |
| **Cloud/API Only** | GPT-4o-mini | Easy setup, good recall |

### Configuration for Qwen3 (Ollama)

To get clean JSON output without chain-of-thought reasoning:

```json
{
  "model": "qwen3:8b",
  "format": "json",
  "messages": [
    {"role": "system", "content": "Do not output chain-of-thought. Only return the final JSON."},
    {"role": "user", "content": "Your extraction prompt here..."}
  ],
  "options": {
    "temperature": 0,
    "top_p": 1
  }
}
```

### Key Settings for Structured Output

1. **`"format": "json"`** - Forces JSON-only output
2. **System message** - Explicitly disable reasoning output
3. **`temperature: 0`** - Deterministic output
4. **Clear schema in prompt** - nodes/edges format with examples

## Cost Analysis

| Model | Cost per 1M tokens | Est. Cost per 1000 docs |
|-------|-------------------|------------------------|
| Qwen3:8b (local) | $0.00 | $0.00 |
| Qwen3:4b (local) | $0.00 | $0.00 |
| GPT-4o-mini | ~$0.15 input / $0.60 output | ~$0.90 |

## Conclusion

**Qwen3:8b running locally on Mac Studio is the optimal choice** for knowledge graph extraction:

- ✅ Perfect accuracy (100% F1)
- ✅ Faster than cloud API (13.4s vs 16.2s)
- ✅ No API costs
- ✅ Data stays local (privacy)
- ✅ Lower token usage (more efficient)

For speed-critical batch processing where some accuracy loss is acceptable, **Qwen3:4b** offers 2x speedup with 78.6% accuracy.

