# Confidence Scoring Guide
**Created:** October 4, 2025
**Purpose:** Explain what confidence scores mean and how to interpret them

---

## 🎯 What Are Confidence Scores?

Confidence scores (0.0 - 1.0) indicate how certain the system is about its response. Higher scores mean the system has strong evidence to support its answer.

---

## 📊 Score Ranges & Meanings

### **0.9 - 1.0: High Confidence** 🟢
**Icon:** ● (Solid green circle)
**What it means:**
- System found exact matches or very strong semantic matches
- Multiple sources confirm the same information
- Retrieved context directly answers the question

**Example:**
```
User: "What's my favorite color?"
System finds: "My favorite color is purple" (exact match)
Confidence: 0.95 ● High confidence (95%)
```

**Trust level:** Very reliable, act on this information

---

### **0.7 - 0.89: Good Confidence** 🔵
**Icon:** ● (Solid cyan circle)
**What it means:**
- Strong semantic matches found
- Context is relevant but may not be exact
- Information is likely accurate but worth verifying for critical decisions

**Example:**
```
User: "What did we discuss about colors?"
System finds: "I mentioned I like purple shirts"
Confidence: 0.82 ● Good confidence (82%)
```

**Trust level:** Generally reliable, good for most use cases

---

### **0.5 - 0.69: Medium Confidence** 🟡
**Icon:** ◐ (Half-filled yellow circle)
**What it means:**
- Partial matches found
- System is making educated guesses
- Context is related but not directly answering the question

**Example:**
```
User: "What's my schedule tomorrow?"
System finds: "I usually work Tuesdays" (general info, not specific)
Confidence: 0.61 ◐ Medium confidence (61%)
```

**Trust level:** Use with caution, verify important details

---

### **0.3 - 0.49: Low Confidence** 🟠
**Icon:** ◔ (Mostly empty orange circle)
**What it means:**
- Weak matches or very general context
- System is struggling to find relevant information
- Answer is speculative or based on loose connections

**Example:**
```
User: "What's the weather like?"
System finds: "I went outside yesterday" (tangentially related)
Confidence: 0.42 ◔ Low confidence (42%)
```

**Trust level:** Treat as suggestions, not facts

---

### **0.0 - 0.29: Very Uncertain** 🔴
**Icon:** ○ (Empty red circle)
**What it means:**
- No good matches found
- System is guessing or making very loose connections
- Answer may be completely wrong

**Example:**
```
User: "What's the capital of Mars?"
System has no relevant context
Confidence: 0.15 ○ Very uncertain (15%)
```

**Trust level:** Likely unreliable, don't act on this

---

## 🔧 How Confidence is Calculated

### **For Chat Responses:**
Confidence is calculated based on:
1. **Semantic Similarity**: How well retrieved context matches the question
2. **Context Quality**: How relevant and complete the context is
3. **Multiple Sources**: Higher confidence when multiple memories confirm
4. **Recency**: More recent information may boost confidence

### **For Memory Search:**
Each search result includes:
- **`_semantic_score`**: Vector similarity score (0.0 - 1.0)
- **`_keyword_score`**: FTS5 keyword match score
- **Combined score**: Weighted average of both

---

## 💡 When to Use Confidence Scores

### **As a User:**
1. **High/Good Confidence (≥0.7):** Trust the response, use for decisions
2. **Medium Confidence (0.5-0.7):** Verify if important, treat as suggestions
3. **Low/Uncertain (<0.5):** Ask follow-up questions, don't rely on it

### **As a Developer:**
1. **Log low-confidence responses** to improve retrieval
2. **Track confidence patterns** to find data gaps
3. **Use thresholds** to trigger fallback behaviors:
   ```python
   if confidence < 0.5:
       return "I'm not confident about this. Could you ask differently?"
   ```

---

## 🎨 UI Display Guidelines

### **Color Coding:**
- **Green** (≥0.9): High confidence - solid trust
- **Cyan** (≥0.7): Good confidence - generally reliable
- **Yellow** (≥0.5): Medium confidence - verify if important
- **Orange** (≥0.3): Low confidence - be skeptical
- **Red** (<0.3): Very uncertain - don't trust

### **Icon Meanings:**
- **●** (Solid): Strong confidence
- **◐** (Half): Moderate confidence
- **◔** (Quarter): Weak confidence
- **○** (Empty): No confidence

---

## 🚨 Important Notes

### **Confidence ≠ Correctness**
- High confidence means the system *thinks* it's right
- It doesn't guarantee the answer is actually correct
- The system can be confidently wrong if the stored data is wrong

**Example:**
```
Stored memory: "My favorite color is blue" (wrong info)
User: "What's my favorite color?"
System: "Blue" with 0.95 confidence (confidently wrong!)
```

### **Low Confidence Doesn't Mean Wrong**
- Sometimes correct answers have low confidence
- Happens when the system has limited context
- The answer might still be right, just uncertain

---

## 📈 Confidence Over Time

As the system learns more about you:
- **Early conversations**: Lower confidence (limited context)
- **After many exchanges**: Higher confidence (rich context)
- **Familiar topics**: Higher confidence
- **New topics**: Lower confidence initially

---

## 🛠️ Improving Confidence

### **For Users:**
1. **Be specific**: "What did I say about my favorite color?" > "Tell me about colors"
2. **Provide context**: "In our conversation yesterday about preferences..."
3. **Confirm information**: "Yes, that's correct" helps the system learn

### **For Developers:**
1. **Better embeddings**: Upgrade to better models (e.g., BGE-M3 → OpenAI Ada-003)
2. **Tuned thresholds**: Adjust semantic similarity cutoffs
3. **Context enrichment**: Provide more metadata (timestamps, sources)
4. **Feedback loops**: Let users rate responses to improve confidence calibration

---

## 📝 Technical Details

### **Backend Calculation (Simplified):**
```python
def calculate_confidence(semantic_score, keyword_score, source_count):
    # Weighted combination
    base_score = (semantic_score * 0.7) + (keyword_score * 0.3)

    # Boost for multiple confirming sources
    if source_count > 1:
        base_score = min(1.0, base_score * 1.1)

    return round(base_score, 2)
```

### **Actual Implementation:**
See `memory_handler.py` → `search_memories()` for full logic

---

## ✅ Summary

**What confidence tells you:**
- **How much context** the system found
- **How relevant** that context is
- **How certain** it is about the answer

**What confidence DOESN'T tell you:**
- Whether the answer is factually correct
- Whether the stored data is accurate
- Whether you should always trust high confidence

**Best practice:**
Use confidence as a **signal, not a guarantee**. High confidence = good evidence, but always apply critical thinking!

---

**Questions or feedback?**
This is a living document - update as the system evolves!
