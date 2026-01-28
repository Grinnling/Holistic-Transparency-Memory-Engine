# SITREP: Request ID Propagation Gap

**Date:** 2025-11-24
**Context:** Error Handler Testing - Tier 2 Critical Path
**Discovered By:** Claude (testing instance)
**Priority:** Medium (doesn't break functionality, limits debugging capability)

---

## Issue Summary

Request IDs are generated correctly within each service, but they are **NOT propagated** between services during inter-service calls. This means you cannot trace a single user request across the entire pipeline.

---

## Current State

### What's Working
| Service | Generates Request ID | Location |
|---------|---------------------|----------|
| api_server_bridge | ✅ Yes | FastAPI middleware (line 38-42) |
| working_memory | ✅ Yes | Flask @before_request (line 24-27) |
| episodic_memory | ✅ Yes | Flask g object |
| memory_curator | ✅ Yes | Flask g object |
| mcp_logger | ✅ Yes | Flask @before_request (newly added) |

### What's NOT Working
- When `rich_chat.store_exchange()` calls `working_memory`, no request ID is passed
- When `api_server_bridge` proxies to `rich_chat`, the request ID stays local
- Each service generates its own independent UUID for each incoming request

---

## Example of the Problem

```
User sends chat message
    ↓
api_server_bridge receives request
    → Generates request_id: "aaa-111"
    → Calls rich_chat.process_message()
        ↓
    rich_chat.store_exchange() calls working_memory
        → working_memory generates NEW request_id: "bbb-222"
        → Exchange stored, but no link to "aaa-111"
```

**Result:** If something fails in working_memory, you see request_id "bbb-222" in logs, but you can't correlate it back to the original user request "aaa-111".

---

## Impact

| Scenario | Current Behavior | Desired Behavior |
|----------|-----------------|------------------|
| Debugging errors | Must check each service's logs separately | Single request_id traces entire flow |
| Performance tracking | Can't measure end-to-end latency per request | Full request lifecycle visible |
| Error correlation | Errors in downstream services orphaned | Errors linked to originating request |

---

## Proposed Fix

### Option A: Header Propagation (Recommended)
Pass `X-Request-ID` header in all inter-service HTTP calls.

**In rich_chat.py `store_exchange()` (line 409):**
```python
response = requests.post(
    f"{self.service_manager.services['working_memory']}/working-memory",
    json={...},
    headers={"X-Request-ID": current_request_id},  # ADD THIS
    timeout=5
)
```

**In working_memory service.py, modify @before_request:**
```python
@app.before_request
def add_request_id():
    # Use incoming header if present, otherwise generate new
    g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
```

### Option B: Context Variable Threading
Use Python's `contextvars` to thread request ID through entire call chain.

**Pros:** No header modification needed
**Cons:** Only works within single process, not across HTTP boundaries

### Recommendation
**Option A** is the standard approach for distributed tracing and works across HTTP boundaries.

---

## Files That Need Changes

1. **rich_chat.py** - Add header to all `requests.post/get` calls
   - `store_exchange()` (line 409)
   - `restore_conversation_history()` (line 190)
   - `validate_with_curator()` (line 425+)
   - Any other inter-service calls

2. **working_memory/service.py** - Accept header in @before_request
   - Already has the middleware, just needs to check header first

3. **episodic_memory/service.py** - Same pattern

4. **memory_curator/curator_service.py** - Same pattern

5. **mcp_logger server.py** - Same pattern

---

## Scope Estimate

- **Effort:** ~2-3 hours
- **Risk:** Low (additive change, backward compatible)
- **Testing:** Add test to verify request_id propagates through chat → working_memory → response

---

## Decision Needed

This is outside the scope of the current error handler refactor testing. Options:

1. **Log and defer** - Continue testing, add to backlog
2. **Fix now** - Pause testing, implement propagation
3. **Partial fix** - Add header passing to critical paths only (store_exchange)

---

## Related Documents

- `/home/grinnling/Development/CODE_IMPLEMENTATION/ERROR_HANDLER_TESTING_GUIDE.md`
- `/home/grinnling/Development/CODE_IMPLEMENTATION/ERROR_HANDLER_SERVICE_AUDIT_2025-10-31.md`

---

**Status:** Awaiting decision
