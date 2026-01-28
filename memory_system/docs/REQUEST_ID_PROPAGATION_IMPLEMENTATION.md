# Request ID Propagation Implementation Guide

**Date:** 2025-11-24
**Related:** `SITREP_REQUEST_ID_PROPAGATION_GAP.md`
**Status:** Ready to implement (after Tier 3-4 testing complete)

---

## Overview

This document provides the complete implementation for cross-service request ID propagation using UUID7 (chronologically sortable).

### What We're Fixing

Currently, each service generates its own request ID. A single user request creates 5+ unrelated IDs:

```
User Request → api_server_bridge (aaa-111)
            → rich_chat (no ID)
            → working_memory (bbb-222)
            → episodic_memory (ccc-333)
            → memory_curator (ddd-444)
```

After this fix:

```
User Request → api_server_bridge (018c1b6e-85a0-7...)
            → rich_chat (018c1b6e-85a0-7...)    ← same ID
            → working_memory (018c1b6e-85a0-7...) ← same ID
            → episodic_memory (018c1b6e-85a0-7...) ← same ID
            → memory_curator (018c1b6e-85a0-7...)  ← same ID
```

### Why UUID7

- **Chronologically sortable** - IDs sort by creation time automatically
- **Timestamp extractable** - Can derive when request occurred from the ID itself
- **Future-proof** - Works with temporal queries later

### Known Edge Case: Standalone rich_chat

When rich_chat runs directly (not through api_server_bridge), there's no request context to inherit from. The `get_request_id()` call will return `"unknown"`.

**Options:**
1. **Accept it** - Downstream services generate fresh IDs, trace starts there
2. **Add fallback** - rich_chat generates its own ID when not in API context (see Part 3.1 below)

We recommend Option 2 for completeness - it means traces always have a valid ID regardless of entry point.

---

## Prerequisites

### Install uuid7 package

```bash
pip install uuid7
```

Add to requirements.txt:
```
uuid7>=0.1.0
```

---

## Implementation

### Part 1: Shared Validation Helper

Create this file to be imported by all services:

**File:** `/home/grinnling/Development/CODE_IMPLEMENTATION/shared/request_id_utils.py`

```python
"""
Request ID utilities for cross-service tracing
Uses UUID7 for chronologically sortable IDs
"""
import re
import uuid7
import logging

# UUID pattern - works for both v4 and v7
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

def generate_request_id() -> str:
    """Generate a new UUID7 request ID (chronologically sortable)"""
    return str(uuid7.uuid7())

def validate_request_id(request_id: str) -> bool:
    """
    Validate that a request ID is a properly formatted UUID.
    Accepts both UUID4 and UUID7 formats.
    """
    if not request_id:
        return False
    return bool(UUID_PATTERN.match(request_id))

def get_or_create_request_id(incoming_id: str | None, logger: logging.Logger = None) -> tuple[str, bool]:
    """
    Get request ID from incoming header or create new one.

    Args:
        incoming_id: The X-Request-ID header value (may be None)
        logger: Optional logger for trace debugging

    Returns:
        tuple: (request_id, is_continuation)
            - request_id: The ID to use for this request
            - is_continuation: True if we're continuing an existing trace
    """
    if incoming_id and validate_request_id(incoming_id):
        if logger:
            logger.debug(f"Continuing trace {incoming_id} from upstream")
        return incoming_id, True
    else:
        new_id = generate_request_id()
        if logger:
            logger.debug(f"New trace started {new_id}")
        return new_id, False

def extract_timestamp_ms(uuid7_str: str) -> int | None:
    """
    Extract Unix timestamp (milliseconds) from UUID7.
    Returns None if not a valid UUID7.

    Useful for temporal queries and debugging.
    """
    try:
        import uuid
        u = uuid.UUID(uuid7_str)
        # UUID7 has timestamp in first 48 bits
        timestamp_ms = u.int >> 80
        return timestamp_ms
    except (ValueError, AttributeError):
        return None
```

---

### Part 2: Entry Point (api_server_bridge.py)

The public entry point ALWAYS generates a fresh ID. Never trust incoming `X-Request-ID` from external users.

**File:** `/home/grinnling/Development/CODE_IMPLEMENTATION/api_server_bridge.py`

**Changes:**

1. Replace `import uuid` with `import uuid7`
2. Update the middleware to use UUID7
3. Store request ID in a way rich_chat can access

```python
# --- FIND AND REPLACE ---

# OLD (around line 12):
import uuid

# NEW:
import uuid7

# -----------------------------

# OLD (around line 36-45):
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for distributed tracing"""
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# NEW:
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Add unique request ID to each request for distributed tracing.

    SECURITY: Always generate fresh ID at entry point.
    Never trust incoming X-Request-ID from external users.
    Uses UUID7 for chronological sorting.
    """
    # Always generate fresh - don't trust external headers
    request_id = str(uuid7.uuid7())
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

---

### Part 3: rich_chat.py (The Caller)

rich_chat makes all the inter-service calls. It needs to:
1. Receive the request ID from api_server_bridge (or generate its own if standalone)
2. Pass it to all downstream services via `X-Request-ID` header

**File:** `/home/grinnling/Development/CODE_IMPLEMENTATION/rich_chat.py`

**Changes:**

1. Add method to build headers with request ID (with standalone fallback)
2. Update all `requests.get()` and `requests.post()` calls to include headers

#### Part 3.1: Standalone Fallback

When rich_chat runs directly (not via api_server_bridge), we need to generate our own trace ID. Add this at the module level or in the class:

```python
# --- ADD NEAR TOP OF FILE (imports section) ---
import uuid7
from contextvars import ContextVar

# Fallback request ID for standalone mode
_standalone_request_id: ContextVar[str] = ContextVar('standalone_request_id', default=None)

def _get_or_create_standalone_id() -> str:
    """Get or create a request ID for standalone rich_chat usage."""
    current = _standalone_request_id.get()
    if current is None:
        current = str(uuid7.uuid7())
        _standalone_request_id.set(current)
    return current
```

#### Part 3.2: Trace Headers Method

```python
# --- ADD THIS METHOD to the MemoryHandler class (or wherever appropriate) ---

def _get_trace_headers(self, source_service: str = "rich_chat") -> dict:
    """
    Build headers for inter-service calls with request ID propagation.

    Tries to get request ID from api_server_bridge context first.
    Falls back to standalone ID if running outside API context.

    Args:
        source_service: Name of this service (for X-Source-Service header)

    Returns:
        dict: Headers to include in requests
    """
    # Try to get ID from api_server_bridge context
    try:
        from api_server_bridge import get_request_id
        request_id = get_request_id()
        if request_id and request_id != "unknown":
            return {
                "X-Request-ID": request_id,
                "X-Source-Service": source_service
            }
    except ImportError:
        pass  # Not running through api_server_bridge

    # Fallback: generate/reuse standalone ID
    return {
        "X-Request-ID": _get_or_create_standalone_id(),
        "X-Source-Service": source_service
    }
```

#### Part 3.3: Update Inter-Service Calls

```python
# Example - Line 189 (restore_conversation_history):
# OLD:
response = requests.get(
    f"{self.service_manager.services['working_memory']}/working-memory",
    params={"limit": 30},
    timeout=5
)

# NEW:
response = requests.get(
    f"{self.service_manager.services['working_memory']}/working-memory",
    params={"limit": 30},
    headers=self._get_trace_headers(),
    timeout=5
)

# ----- FULL LIST OF CALLS TO UPDATE -----

# Line 189: GET working_memory
# Line 214: GET episodic_memory/recent
# Line 409: POST working_memory
# Line 436: POST curator/validate
# Line 803: GET episodic_memory/recent
# Line 877: GET episodic_memory/recent
# Line 911: GET episodic_memory/conversation/{id}
```

**Complete diff for rich_chat.py inter-service calls:**

```python
# Line ~189
response = requests.get(
    f"{self.service_manager.services['working_memory']}/working-memory",
    params={"limit": 30},
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)

# Line ~214
episodic_response = requests.get(
    f"{self.service_manager.services['episodic_memory']}/recent",
    params={"limit": 20},
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)

# Line ~409
response = requests.post(
    f"{self.service_manager.services['working_memory']}/working-memory",
    json={
        "user_message": user_message,
        "assistant_response": assistant_response,
        "context_used": context_used
    },
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)

# Line ~436
response = requests.post(
    f"{self.service_manager.services['curator']}/validate",
    json={
        "exchange_data": {
            "user_message": user_message,
            "assistant_response": assistant_response
        }
    },
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)

# Line ~803
response = requests.get(
    f"{self.service_manager.services['episodic_memory']}/recent?limit=50",
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)

# Line ~877
response = requests.get(
    f"{self.service_manager.services['episodic_memory']}/recent?limit=50",
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)

# Line ~911
response = requests.get(
    f"{self.service_manager.services['episodic_memory']}/conversation/{target_id}",
    headers=self._get_trace_headers(),  # ADD THIS
    timeout=5
)
```

---

### Part 4: Internal Services (Accept Propagated ID)

Each Flask service needs to check for incoming `X-Request-ID` header before generating a new one.

#### 4.1 working_memory/service.py

**File:** `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/working_memory/service.py`

```python
# --- FIND AND REPLACE ---

# OLD (line 11-12):
import uuid

# NEW:
import uuid7
import re

# UUID pattern for validation
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

# -----------------------------

# OLD (line 24-27):
@app.before_request
def add_request_id():
    """Add unique request ID to each request for distributed tracing"""
    g.request_id = str(uuid.uuid4())

# NEW:
@app.before_request
def add_request_id():
    """
    Add request ID to each request for distributed tracing.
    Uses incoming X-Request-ID if valid, otherwise generates new UUID7.
    """
    incoming_id = request.headers.get('X-Request-ID')
    source_service = request.headers.get('X-Source-Service', 'unknown')

    if incoming_id and UUID_PATTERN.match(incoming_id):
        g.request_id = incoming_id
        logger.debug(f"Continuing trace {incoming_id} from {source_service}")
    else:
        g.request_id = str(uuid7.uuid7())
        logger.debug(f"New trace started {g.request_id}")
```

#### 4.2 episodic_memory/service.py

**File:** `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/episodic_memory/service.py`

Same pattern - find the `@app.before_request` block (around line 319) and replace:

```python
# OLD:
@app.before_request
def add_request_id():
    g.request_id = str(uuid.uuid4())

# NEW:
import uuid7
import re

UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

@app.before_request
def add_request_id():
    """
    Add request ID to each request for distributed tracing.
    Uses incoming X-Request-ID if valid, otherwise generates new UUID7.
    """
    incoming_id = request.headers.get('X-Request-ID')
    source_service = request.headers.get('X-Source-Service', 'unknown')

    if incoming_id and UUID_PATTERN.match(incoming_id):
        g.request_id = incoming_id
        logger.debug(f"Continuing trace {incoming_id} from {source_service}")
    else:
        g.request_id = str(uuid7.uuid7())
        logger.debug(f"New trace started {g.request_id}")
```

#### 4.3 memory_curator/curator_service.py

**File:** `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/memory_curator/curator_service.py`

Same pattern - find `@app.before_request` (around line 273) and apply same change.

#### 4.4 mcp_logger/server.py

**File:** `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/mcp_logger/server.py`

Same pattern - find `@app.before_request` (around line 52) and apply same change.

---

## Verification Tests

After implementation, run these tests to verify propagation works:

### Test 1: Single Request ID Across Services

```bash
# Send a chat message and capture the request ID
REQUEST_ID=$(http POST http://localhost:8000/chat message="propagation test" | jq -r '.request_id')
echo "Request ID: $REQUEST_ID"

# Search all service logs for that ID
echo "--- api_server_bridge ---"
grep "$REQUEST_ID" /path/to/api_server.log | head -3

echo "--- working_memory ---"
docker logs working-memory 2>&1 | grep "$REQUEST_ID" | head -3

echo "--- episodic_memory ---"
docker logs episodic-memory 2>&1 | grep "$REQUEST_ID" | head -3
```

**Expected:** Same request ID appears in ALL service logs.

### Test 2: UUID7 Format Verification

```bash
# Get a request ID
REQUEST_ID=$(http GET http://localhost:5001/health | jq -r '.request_id')
echo "Request ID: $REQUEST_ID"

# Should start with timestamp prefix (018 or 019 for 2020s-2030s dates)
# Format: 018xxxxx-xxxx-7xxx-xxxx-xxxxxxxxxxxx
#         ^^^^^^^^      ^
#         timestamp     version 7 marker
```

### Test 3: Chronological Sorting

```bash
# Send multiple requests
for i in {1..5}; do
    http GET http://localhost:5001/health | jq -r '.request_id' >> /tmp/ids.txt
    sleep 0.1
done

# Sort by ID (should be in order)
echo "--- Sorted by ID (should match creation order) ---"
sort /tmp/ids.txt

# Clean up
rm /tmp/ids.txt
```

**Expected:** IDs naturally sort in chronological order.

### Test 4: Source Service Tracking

```bash
# Enable debug logging temporarily, then send a chat message
http POST http://localhost:8000/chat message="source tracking test"

# Check working_memory logs
docker logs working-memory 2>&1 | grep "from rich_chat"
```

**Expected:** Log shows "Continuing trace xxx from rich_chat"

### Test 5: Verify Entry Point Ignores Spoofed IDs

```bash
# Try to inject a fake request ID from outside
http POST http://localhost:8000/chat \
    X-Request-ID:"FAKE-INJECTED-ID" \
    message="injection test" | jq '.request_id'
```

**Expected:** Response contains a valid UUID7, NOT "FAKE-INJECTED-ID"

---

## Rollback Plan

If issues occur, revert changes in this order:

1. Revert `@app.before_request` in Flask services back to simple `uuid.uuid4()`
2. Remove `headers=` parameter from rich_chat requests calls
3. Revert api_server_bridge middleware to `uuid.uuid4()`

The system will work exactly as before - each service just generates independent IDs again.

---

## Testing Tags Reference

During Tier 3-4 testing, tag any failures that would benefit from this with `[TRACE-GAP]`.

After implementation, re-run those specific tests to verify the fix helps.

---

## Files Changed Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `shared/request_id_utils.py` | NEW | Shared validation helper |
| `api_server_bridge.py` | MODIFY | UUID7 generation, ignore incoming header |
| `rich_chat.py` | MODIFY | Add `_get_trace_headers()`, update 7 request calls |
| `working_memory/service.py` | MODIFY | Accept/validate incoming header |
| `episodic_memory/service.py` | MODIFY | Accept/validate incoming header |
| `memory_curator/curator_service.py` | MODIFY | Accept/validate incoming header |
| `mcp_logger/server.py` | MODIFY | Accept/validate incoming header |

---

## Estimated Time

- Implementation: 30-45 minutes
- Verification testing: 15-20 minutes
- Total: ~1 hour

---

**Document Status:** Complete and ready for implementation
