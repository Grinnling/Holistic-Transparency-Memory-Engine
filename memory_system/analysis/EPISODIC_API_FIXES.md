# Episodic Memory Service API Compatibility Fixes

**Date:** 2025-09-30
**Issue:** Our MemoryHandler expects different API formats than the episodic service provides

---

## CRITICAL ISSUES FOUND

### ❌ Issue 1: `/search` endpoint format mismatch
**What we call:**
```python
POST /search
{"query": str, "top_k": int}
```

**What service expects:**
```python
GET /search?query=str&limit=int
```

**Impact:** CRITICAL - Memory retrieval will fail

---

### ❌ Issue 2: `/stats` response format mismatch
**What we expect:**
```python
{"total_exchanges": int}  # or {"count": int}
```

**What service returns:**
```python
{
  "status": "success",
  "stats": {
    "service_stats": {
      "total_exchanges_archived": int  # ← We need this
    },
    "database_stats": {...}
  }
}
```

**Impact:** HIGH - Memory count display will show 0

---

### ❌ Issue 3: `/clear` endpoint doesn't exist!
**What we call:**
```python
POST /clear
```

**What service has:**
```
NOTHING - endpoint doesn't exist
```

**Impact:** HIGH - Clear memories test will fail

---

## FIXES REQUIRED

### Fix 1: Update MemoryHandler.retrieve_relevant_memories()

**File:** `/home/grinnling/Development/CODE_IMPLEMENTATION/memory_handler.py` line 398

**Change FROM:**
```python
response = requests.post(
    f"{self.services['episodic_memory']}/search",
    json={"query": query, "top_k": top_k},
    timeout=5
)
```

**Change TO:**
```python
response = requests.get(
    f"{self.services['episodic_memory']}/search",
    params={"query": query, "limit": top_k},
    timeout=5
)
```

---

### Fix 2: Update MemoryHandler.get_memory_count()

**File:** `/home/grinnling/Development/CODE_IMPLEMENTATION/memory_handler.py` line 437

**Change FROM:**
```python
if response.ok:
    data = response.json()
    # Episodic memory might return count in different formats
    return data.get('total_exchanges', data.get('count', 0))
```

**Change TO:**
```python
if response.ok:
    data = response.json()
    # Navigate nested stats structure
    if 'stats' in data:
        service_stats = data['stats'].get('service_stats', {})
        return service_stats.get('total_exchanges_archived', 0)
    # Fallback for other formats
    return data.get('total_exchanges', data.get('count', 0))
```

---

### Fix 3: Handle missing /clear endpoint

**Option A (Recommended):** Add endpoint to episodic service
**Option B:** Make clear_all_memories() graceful

**File:** `/home/grinnling/Development/CODE_IMPLEMENTATION/memory_handler.py` line 481

**Change FROM:**
```python
response = requests.post(
    f"{self.services['episodic_memory']}/clear",
    timeout=10
)
```

**Change TO:**
```python
# Try clear endpoint (may not exist)
try:
    response = requests.post(
        f"{self.services['episodic_memory']}/clear",
        timeout=10
    )

    if response.ok:
        self._info_message("✅ All episodic memories cleared", ErrorCategory.EPISODIC_MEMORY)
        self.episodic_archival_failures = 0
        return True
except requests.exceptions.RequestException:
    # Endpoint doesn't exist - warn user
    self._warning_message(
        "⚠️  Episodic service doesn't support /clear endpoint. Manual DB clear required.",
        ErrorCategory.EPISODIC_MEMORY
    )
    return False
```

---

## ADDITIONAL COMPATIBILITY CHECKS

### Archive endpoint format
**File to check:** How we call `/archive`

Our coordinator uses:
```python
POST /archive
{
  "conversation_id": str,
  "exchanges": [...],
  ...
}
```

Service expects (line 331):
```python
POST /archive
{
  "conversation_data": {...},  # Full conversation object
  "trigger_reason": str
}
```

**This might also need adjustment!**

---

## TESTING AFTER FIXES

1. **Test search:**
   ```bash
   curl "http://localhost:8005/search?query=test&limit=5"
   ```

2. **Test stats:**
   ```bash
   curl http://localhost:8005/stats
   ```
   Check the response structure

3. **Test archive format:**
   Check what episodic_memory_coordinator.py sends vs what service expects

---

## QUICK FIX SCRIPT

Want me to apply these fixes now? (Y/N)
