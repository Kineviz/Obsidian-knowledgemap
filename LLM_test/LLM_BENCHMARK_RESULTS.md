# LLM Benchmark Results: Knowledge Graph Relationship Extraction

## Overview

This document summarizes comprehensive benchmarking results comparing different LLM models for relationship extraction in knowledge graph construction. The tests evaluated instruction following, accuracy, speed, and token efficiency across various hardware configurations.

## Test Configuration

- **Document Size**: 1,956 characters (1024-character target)
- **Expected Relationships**: 16
- **Prompt**: Full system + user prompt from `prompts.yaml`
- **Evaluation Method**: Entity extraction accuracy (source/target matching)

## Hardware Specifications with Gemma3:12b

| Hardware | RAM | Performance Factor |
|----------|-----|-------------------|
| GPT-o4-mini | N/A | 1x |
| M4 Max Mac Studio | 64GB | 1.1x |
| M2 Max Mac Studio | 32GB | 0.8x |
| M4 Pro MBP | 48GB | 0.6x |
| M1 Max MBP | 64GB | 0.75x |

## Model Performance Summary

### Key Findings

1. **Gemma3:4b**: Unable to follow instructions properly - uses generic "works_at" instead of specific relationship types
2. **Gemma3:12b**: Follows instructions perfectly with accuracy similar to GPT-4o-mini
3. **Token Efficiency**: Gemma3:12b uses significantly fewer tokens (946 vs 1,508)

### Detailed Results

| Model | Hardware | Speed (s) | Accuracy | Relationships | Tokens | Status |
|-------|----------|-----------|----------|---------------|--------|--------|
| **OpenAI GPT-4o-mini** | API | 28.4 | **93.8%** | 17 | 1,508 | ✅ |
| **Gemma3:12b** | M4 Max Mac Studio | 26.6 | **87.5%** | 21 | 946 | ✅ |

## Speed Analysis

### Relative Performance (GPT-4o-mini = 1.0x baseline)

| Model | Hardware | Speed Factor | Notes |
|-------|----------|--------------|-------|
| **OpenAI GPT-4o-mini** | API | 1.0x | Baseline |
| **Gemma3:12b** | M4 Max Mac Studio | 1.07x | Fastest local |
| **Gemma3:12b** | M2 Max Mac Studio | 0.7x | Good speed |
| **Gemma3:12b** | M1 Max MBP | 0.65x | Good speed |
| **Gemma3:12b** | M4 Pro MBP | 0.5x | Slow |

### Token Processing Speed

| Model | Hardware | Tokens/s | Efficiency |
|-------|----------|----------|------------|
| **OpenAI GPT-4o-mini** | API | 53.1 | Baseline |
| **Gemma3:12b** | M4 Max Mac Studio | 35.6 | 67% of API speed |


## Quality vs Quantity Analysis

### Over-Extraction Issues

**Gemma3:12b** found 21 relationships vs expected 16:
- **Valid**: 14 relationships (87.5% accuracy)
- **Extra**: 7 relationships (5 self-reference "mentioned" + 2 duplicates)

**GPT-4o-mini** found 17 relationships vs expected 16:
- **Valid**: 15 relationships (93.8% accuracy)
- **Extra**: 2 relationships (duplicates only)

### Knowledge Graph Impact

| Model | Relationships | Noise Level | Graph Quality |
|-------|---------------|-------------|---------------|
| **GPT-4o-mini** | 17 | Low | High |
| **Gemma3:12b** | 21 | Medium | Good |
| **Gemma3:4b** | 20 | High | Poor |

## Cost Analysis

### Token Efficiency

| Model | Tokens | Cost per 1M tokens | Relative Cost |
|-------|--------|-------------------|---------------|
| **OpenAI GPT-4o-mini** | 1,508 | $0.15 | 100% |
| **Gemma3:12b** | 946 | $0.00 | 0% |

### Cost Savings

- **Gemma3:12b**: 37% fewer tokens + 100% cost savings = **Significant value**

## Recommendations

### For Production Use

#### **Primary Choice: OpenAI GPT-4o-mini**
- **Best accuracy**: 93.8%
- **Clean output**: Minimal noise
- **Reliable**: Consistent performance
- **Cost**: Paid but reasonable

#### **Cost-Effective Alternative: Gemma3:12b**
- **Good accuracy**: 87.5%
- **Free**: No API costs
- **Fast**: 1.07x faster than API
- **Acceptable noise**: Some over-extraction

#### **Can not use Gemma3:4b**

### Hardware Recommendations

1. **M4 Max Mac Studio**: Best overall performance for local models
2. **M2 Max Mac Studio**: Good balance of speed and cost
3. **M1 Max MBP**: Adequate for development/testing
4. **M4 Pro MBP**: Slow but OK

## Conclusion

The benchmark reveals clear trade-offs between accuracy, speed, and cost:

- **GPT-4o-mini**: Best accuracy and instruction following
- **Gemma3:12b**: Good accuracy with significant cost savings
- **Gemma3:4b**: Fastest but poor instruction following

For knowledge graph construction, **instruction following is crucial** - models must use specific relationship types rather than generic ones. The **Gemma3:12b model provides the best balance** of accuracy, speed, and cost for most use cases.

## Test Methodology

- **Document**: 1,956 character tech startup network description
- **Expected**: 16 specific entity relationships
- **Evaluation**: Source/target entity matching (relationship type ignored)
- **Hardware**: Various Apple Silicon configurations
- **Prompt**: Full system + user prompt from `prompts.yaml`
- **Runs**: Single test per configuration

## Future Improvements

### Testing Enhancements
- **Multiple runs**: Average results across 5-10 runs for statistical significance
- **Larger test corpus**: Include diverse document types and sizes
- **Edge case testing**: Handle malformed JSON, timeout scenarios, and error recovery

### Additional Model Testing

#### **LM Studio Integration**
- Test local models through LM Studio's OpenAI-compatible API
- Compare performance vs direct Ollama integration
- Evaluate model switching capabilities

#### **Promising Models to Evaluate**
- **Qwen2.5**: Strong reasoning capabilities, multilingual support
- **DeepSeek-Coder**: Optimized for structured output and JSON generation
- **Llama 3.1**: Latest Meta model with improved instruction following
- **Mistral 7B**: Efficient European alternative
- **CodeLlama**: Specialized for structured data extraction

#### **Cloud Alternatives**
- **Anthropic Claude**: Strong reasoning and safety features
- **Google Gemini**: Competitive accuracy and speed
- **Cohere Command**: Enterprise-focused with good JSON output

### Evaluation Metrics
- **Precision/Recall**: More granular accuracy measurement
- **F1 Score**: Balanced evaluation of extraction quality
- **Relationship type accuracy**: Evaluate semantic correctness
- **Consistency testing**: Multiple runs on same document
- **Scalability testing**: Performance with larger documents (10K+ chars)

### Hardware Expansion
- **NVIDIA RTX 4090**: Compare GPU vs Apple Silicon performance
- **AMD Radeon 7900 XTX**: Alternative GPU testing
- **Intel Arc**: Budget GPU option evaluation
- **Cloud instances**: AWS/GCP/Azure GPU comparison
