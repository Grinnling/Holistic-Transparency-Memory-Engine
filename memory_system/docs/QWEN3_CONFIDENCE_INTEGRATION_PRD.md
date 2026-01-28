# Qwen3 Native Confidence Integration PRD

**Created:** January 21, 2026
**Status:** Draft
**Owner:** {WE} - Collaborative design between operator and AI

---

## Executive Summary

Integrate Qwen3's native confidence metrics into the ResponseEnhancer system, replacing/augmenting heuristic-only confidence with actual model probabilities. This gives {US} more accurate confidence scores and enables better hallucination detection.

**Why This Matters:**
- Heuristic confidence (pattern matching on output) is {MY} current workaround
- Native confidence from logprobs is what the model actually "felt" during generation
- Cross-checking both catches more failure modes (high native + lots of hedging = suspicious)

---

## Background & Research

### Current State (ResponseEnhancer)
- **Heuristic confidence**: Pattern-based analysis (hedging phrases, uncertainty triggers)
- **Curator validation**: External validation feedback
- **Native confidence**: Placeholder - always `None`

### Qwen3 Capabilities (Validated via Web Search + Model Interview)

| Feature | Available | How to Access |
|---------|-----------|---------------|
| Token logprobs | ✅ Yes | `logprobs=True` parameter, response at `choices[0].logprobs.content` |
| Reasoning content | ✅ Yes | `reasoning_content` field or `<think>` blocks |
| Thinking mode toggle | ✅ Yes | Hard: `enable_thinking=True/False`, Soft: `/think` `/no_think` in prompt |
| Thinking budget | ✅ Yes | `thinking_budget` parameter (500-5000 tokens) |
| Explicit confidence field | ❌ No | Must derive from logprobs |
| Reasoning step count | ❌ No | Must count from reasoning_content |

### Sources
- [Alibaba Cloud Model Studio Docs](https://www.alibabacloud.com/help/en/model-studio/deep-thinking)
- [vLLM Reasoning Outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/)
- [DeepInfra Logprobs Docs](https://deepinfra.com/docs/advanced/log_probs)
- [GitHub QwenLM/Qwen3 Discussions](https://github.com/QwenLM/Qwen3/discussions/1300)

---

## Requirements

### Must Have (P0)

1. **Extract logprobs from Qwen3 responses**
   - Parse `choices[0].logprobs.content` array
   - Handle missing logprobs gracefully (fall back to heuristics)

2. **Aggregate logprobs to confidence score**
   - Calculate average logprob across response tokens
   - Convert to probability: `confidence = exp(avg_logprob)`
   - Include reasoning tokens if thinking mode enabled

3. **Wire into ResponseEnhancer**
   - Pass `native_confidence` to `analyze_confidence()`
   - Update `confidence_source` to "native" when available
   - Maintain heuristic as fallback + cross-check

4. **Parse reasoning depth**
   - Count tokens in `reasoning_content` field
   - Track as `reasoning_depth` metric
   - Use as secondary confidence signal (more reasoning = better calibrated)

### Should Have (P1)

5. **Thinking mode control**
   - Add `/think` to prompts for complex queries
   - Track whether thinking mode was used
   - Adjust confidence interpretation based on mode

6. **Budget exhaustion detection**
   - Detect if response hit `thinking_budget` limit
   - Flag as potential incomplete reasoning
   - Lower confidence weight when budget exhausted

7. **Calibration tracking over time**
   - Log (confidence, correctness) pairs to OZOLITH
   - Calculate ECE/AUROC periodically
   - Surface calibration drift alerts

### Nice to Have (P2)

8. **Domain-specific thresholds**
   - Configure confidence thresholds per query type
   - Medical/safety queries require higher threshold
   - Subjective queries accept lower threshold

9. **Multi-generation consistency**
   - Sample N responses, measure agreement
   - Expensive but most accurate calibration method

---

## Known Blind Spots (From Qwen3 Self-Report)

These are scenarios where native confidence may be unreliable. ResponseEnhancer should apply extra scrutiny or fallback heuristics.

| Blind Spot | Description | Mitigation Strategy |
|------------|-------------|---------------------|
| **Ambiguous queries** | No single right answer, reasoning varies | Already covered by `UncertaintyCategory.AMBIGUOUS_INPUT` |
| **Simple factual** | May overestimate (memorized, sparse reasoning) | Flag if high confidence + short reasoning_content |
| **Context ambiguity** | Pronouns, references unclear | Hedging detection + consider pronoun resolution |
| **Domain gaps** | Limited training data for specialized topics | External validation hooks (future) |
| **Short queries** | Lack context, sparse reasoning | Enforce minimum context for high-stakes |
| **Long queries** | May exceed thinking_budget | Detect budget exhaustion, flag incomplete |
| **Contradictory prompts** | May generate flawed "proof" | Skinflap already catches some; add logic checks |

### Recommended Thresholds (From Qwen3)
- General: Flag if avg logprob < 0.6
- High-stakes domains: Require > 0.8
- Subjective queries: Accept lower, show uncertainty note

---

## Technical Design

### Data Flow

```
Qwen3 Response
    │
    ├─► logprobs.content[] ──► aggregate_logprobs() ──► native_confidence (float)
    │
    ├─► reasoning_content ──► count_tokens() ──► reasoning_depth (int)
    │
    └─► budget_exhausted? ──► flag incomplete reasoning

                    │
                    ▼
            ResponseEnhancer.analyze_confidence(
                response=...,
                user_message=...,
                native_confidence=0.73,      # From logprobs
                curator_validation=...,       # From curator
                reasoning_depth=847,          # Token count
                thinking_mode_used=True,
                budget_exhausted=False
            )
                    │
                    ▼
            ConfidenceAnalysis(
                native_confidence=0.73,
                heuristic_confidence=0.85,
                curator_confidence=0.80,
                combined_confidence=0.76,     # Weighted blend
                confidence_mismatch=False,
                reasoning_depth=847,
                ...
            )
```

### New Dataclass Fields

```python
@dataclass
class ConfidenceAnalysis:
    # Existing fields...

    # New fields for Qwen3 integration
    reasoning_depth: Optional[int] = None          # Token count in reasoning_content
    thinking_mode_used: bool = False               # Was /think or enable_thinking=True used?
    budget_exhausted: bool = False                 # Did response hit thinking_budget?
    logprob_min: Optional[float] = None            # Minimum logprob (weakest token)
    logprob_variance: Optional[float] = None       # Variance in logprobs (consistency)
```

### Confidence Aggregation Function

```python
def aggregate_logprobs(logprobs: List[dict]) -> dict:
    """
    Aggregate token logprobs into confidence metrics.

    Args:
        logprobs: List of {"token": str, "logprob": float, "top_logprobs": [...]}

    Returns:
        {
            "confidence": float,      # exp(mean(logprobs))
            "min_logprob": float,     # Weakest token
            "variance": float,        # Consistency measure
            "token_count": int
        }
    """
    if not logprobs:
        return {"confidence": None, "min_logprob": None, "variance": None, "token_count": 0}

    probs = [entry["logprob"] for entry in logprobs]

    import math
    import statistics

    avg_logprob = statistics.mean(probs)
    confidence = math.exp(avg_logprob)  # Convert log probability to probability

    return {
        "confidence": min(1.0, max(0.0, confidence)),  # Clamp to [0, 1]
        "min_logprob": min(probs),
        "variance": statistics.variance(probs) if len(probs) > 1 else 0.0,
        "token_count": len(probs)
    }
```

### LLM Connector Changes

```python
# In llm_connector.py - when calling Qwen3

def generate_response(self, user_message: str, ...) -> dict:
    response = self.client.chat.completions.create(
        model="qwen3-...",
        messages=messages,
        logprobs=True,              # Enable logprobs
        top_logprobs=5,             # Get top 5 alternatives per token
        # For thinking mode:
        # enable_thinking=True,     # Or add /think to prompt
        # thinking_budget=2000,     # Adjust based on complexity
    )

    # Extract confidence data
    confidence_data = None
    if response.choices[0].logprobs:
        confidence_data = aggregate_logprobs(response.choices[0].logprobs.content)

    reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)
    reasoning_depth = len(reasoning_content.split()) if reasoning_content else 0

    return {
        "content": response.choices[0].message.content,
        "native_confidence": confidence_data["confidence"] if confidence_data else None,
        "reasoning_depth": reasoning_depth,
        "logprob_min": confidence_data["min_logprob"] if confidence_data else None,
        "logprob_variance": confidence_data["variance"] if confidence_data else None,
    }
```

---

## Testing Strategy

### Unit Tests

```python
class TestQwen3ConfidenceExtraction:
    def test_aggregate_logprobs_calculates_confidence(self)
    def test_aggregate_logprobs_handles_empty(self)
    def test_aggregate_logprobs_clamps_to_valid_range(self)
    def test_parse_reasoning_content_counts_tokens(self)
    def test_detect_budget_exhaustion(self)

class TestConfidenceIntegration:
    def test_native_confidence_used_when_available(self)
    def test_fallback_to_heuristic_when_no_logprobs(self)
    def test_mismatch_detection_with_native(self)
    def test_combined_confidence_weighting(self)
    def test_reasoning_depth_affects_analysis(self)
```

### Calibration Testing (Discovery Phase)

Track these metrics over time to tune the system:

1. **ECE (Expected Calibration Error)**
   - Bin responses by confidence, compare to actual accuracy
   - Target: ECE < 0.10

2. **AUROC**
   - Can confidence distinguish correct from incorrect?
   - Target: AUROC > 0.75

3. **Brier Score**
   - Mean squared error between confidence and correctness
   - Lower is better

### Blind Spot Discovery

During testing, specifically probe:
- [ ] Simple factual queries with high confidence - verify accuracy
- [ ] Ambiguous queries - verify uncertainty is expressed
- [ ] Long queries - verify thinking_budget doesn't truncate
- [ ] Domain-specific queries - note accuracy vs confidence gaps

---

## Implementation Phases

### Phase 1: Basic Integration (P0)
- [ ] Add `logprobs=True` to Qwen3 API calls
- [ ] Implement `aggregate_logprobs()` function
- [ ] Wire native_confidence into ResponseEnhancer
- [ ] Add unit tests
- **Effort:** 2-3 hours

### Phase 2: Reasoning Analysis (P0-P1)
- [ ] Parse reasoning_content for depth
- [ ] Add thinking mode control (detect `/think` usage)
- [ ] Detect budget exhaustion
- [ ] Update ConfidenceAnalysis dataclass
- **Effort:** 2 hours

### Phase 3: Calibration Tracking (P1)
- [ ] Log confidence + correctness to OZOLITH
- [ ] Implement ECE/AUROC calculation
- [ ] Add calibration dashboard or alerts
- **Effort:** 3-4 hours

### Phase 4: Advanced Features (P2)
- [ ] Domain-specific thresholds
- [ ] Multi-generation consistency (expensive)
- [ ] External validation hooks
- **Effort:** TBD based on needs

---

## Success Criteria

1. **Native confidence available** for all Qwen3 responses
2. **Fallback works** when logprobs unavailable (other models, API errors)
3. **Mismatch detection catches** high-confidence hallucinations
4. **ECE < 0.15** after calibration tuning
5. **No performance regression** - logprobs add minimal latency

---

## Open Questions

1. **Which Qwen3 model variant are we using?** (8B, 32B, 72B, MoE?)
   - Affects calibration characteristics

2. **What's our thinking_budget default?**
   - Qwen3 suggests 500-1000 for simple, 2000-5000 for complex

3. **How do we determine "correctness" for calibration metrics?**
   - Human annotation? Curator validation? Gold-standard benchmarks?

4. **Should we always use thinking mode, or dynamically enable?**
   - Trade-off: Better calibration vs latency/cost

---

## Related Documents

- `response_enhancer.py` - Current confidence analysis implementation
- `CURRENT_ROADMAP_2025.md` - Project roadmap
- `ERROR_CATEGORIES_AND_SEVERITIES_GUIDE.md` - Error handling patterns
- [Qwen3 GitHub](https://github.com/QwenLM/Qwen3) - Official repository

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-01-21 | Initial PRD draft | {WE} |
