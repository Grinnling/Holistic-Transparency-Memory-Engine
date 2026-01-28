# Error Categories and Severities Guide

**Date Created:** October 31, 2025
**Purpose:** Comprehensive reference for error handling across all memory system services
**Source:** error_handler.py (lines 15-73)

---

## Error Severity Levels

Error severities determine how the system responds to errors. They follow a clear action-based hierarchy.

### ErrorSeverity Enum

| Severity | Enum Value | Action Required | When to Use |
|----------|-----------|-----------------|-------------|
| **CRITICAL_STOP** | `critical_stop` | Stop everything, human intervention needed | Data corruption risk, service completely down, unrecoverable state |
| **HIGH_DEGRADE** | `high_degrade` | Feature broken, continue with degraded functionality | Core feature unavailable but system can continue, memory storage failed but reads work |
| **MEDIUM_ALERT** | `medium_alert` | User should know, show in alerts panel | Non-critical failures, temporary service issues, recoverable errors |
| **LOW_DEBUG** | `low_debug` | Background issue, show only in debug mode | Minor issues, informational warnings, expected edge cases |
| **TRACE_FIWB** | `trace_fiwb` | Deep debugging, show only in FIWB mode | Extreme verbosity for troubleshooting, "fuck it we ball" debugging |

### Severity Decision Tree

```
Is data at risk of loss or corruption?
├─ YES → CRITICAL_STOP
└─ NO → Can the core feature still work?
    ├─ NO → HIGH_DEGRADE
    └─ YES → Should the user be notified?
        ├─ YES → MEDIUM_ALERT
        └─ NO → Is this for debugging?
            ├─ YES → LOW_DEBUG or TRACE_FIWB
            └─ NO → MEDIUM_ALERT (default)
```

### Gray Area Examples: Choosing the Right Severity

Real-world errors often fall in between severity levels. Here's how to decide:

#### CRITICAL_STOP vs HIGH_DEGRADE

**Use CRITICAL_STOP when:**
- Data corruption is likely: "SQLite database locked permanently"
- Service cannot continue at all: "LLM API authentication permanently revoked"
- Manual intervention required: "Disk full, cannot write anywhere"
- Recovery attempts exhausted: "Service restart failed 5 times"

**Use HIGH_DEGRADE when:**
- Feature broken but alternatives exist: "Episodic archival failed, but working memory still stores exchanges"
- Degraded functionality possible: "Multi-query disabled, falling back to basic query"
- Service continues with reduced capability: "Curator validation offline, skipping quality checks"
- Automatic recovery likely: "Database connection lost, reconnect scheduled"

**Example Decision:**
```python
# Scenario: Working memory archival to episodic failed
# - Working memory still works (can store new exchanges)
# - User can still chat (core functionality intact)
# - Only long-term storage is affected
# Decision: HIGH_DEGRADE (not CRITICAL_STOP)

logger.error(f"Archival failed, episodic unavailable: {e}")
error_handler.handle_error(e, ErrorCategory.MEMORY_ARCHIVAL, ErrorSeverity.HIGH_DEGRADE)
```

#### MEDIUM_ALERT vs LOW_DEBUG

**Use MEDIUM_ALERT when:**
- User experience affected: "Search returned no results due to service timeout"
- Operation failed but can retry: "Health check failed, will retry in 30s"
- Non-critical feature unavailable: "Confidence scoring unavailable"
- User should be aware: "Memory stats incomplete"

**Use LOW_DEBUG when:**
- Expected behavior: "Empty search results (no matches found)"
- Informational only: "Cache miss, fetching from source"
- Developer debugging: "Query reformulation skipped (query already optimal)"
- Background optimization: "Memory consolidation postponed (low priority)"

**Example Decision:**
```python
# Scenario: Memory search returned empty results
# - Could be expected (no matches) → LOW_DEBUG
# - Could be service failure (database down) → MEDIUM_ALERT
# Decision depends on WHY it's empty

if service_unavailable:
    # Service down = user should know
    logger.warning(f"Search failed due to service unavailable")
    severity = ErrorSeverity.MEDIUM_ALERT
else:
    # No matches = normal behavior
    logger.debug(f"Search returned no results for query")
    severity = ErrorSeverity.LOW_DEBUG
```

#### MEDIUM_ALERT vs HIGH_DEGRADE

**Use HIGH_DEGRADE when:**
- Core feature completely broken: "Cannot store ANY new exchanges"
- Multiple operations affected: "All database writes failing"
- Service operating in limp mode: "Read-only mode due to write failures"
- Requires operator attention: "Service degraded, check logs"

**Use MEDIUM_ALERT when:**
- Single operation failed: "One exchange failed to store (others succeeded)"
- Temporary issue: "Service timeout (likely transient)"
- Recoverable error: "Retry succeeded on attempt 2"
- User can work around: "Validation failed, continuing without validation"

**Example Decision:**
```python
# Scenario: Working memory buffer lock timeout
# - Single operation failed
# - Other requests still working
# - Retry likely to succeed
# Decision: MEDIUM_ALERT (not HIGH_DEGRADE)

logger.warning(f"Buffer lock timeout on request {g.request_id}")
error_handler.handle_error(e, ErrorCategory.WORKING_MEMORY, ErrorSeverity.MEDIUM_ALERT)
```

---

## Error Categories

Error categories organize errors by system component for better tracking and recovery.

### Memory System Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **EPISODIC_MEMORY** | `episodic` | Long-term memory storage | SQLite write failures, database corruption, archival errors |
| **WORKING_MEMORY** | `working` | Short-term active memory | Buffer overflow, deque errors, recent context retrieval failures |
| **MEMORY_DISTILLATION** | `distillation` | Memory processing/compression | Summarization failures, embedding errors, consolidation issues |
| **MEMORY_ARCHIVAL** | `archival` | Moving between memory types | Working→Episodic transfer failures, conversation save errors |

### Communication & Logging Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **MCP_LOGGER** | `mcp_logger` | Message logging service | Log routing failures, proxy errors, service unavailable |
| **CURATOR** | `curator` | Content validation/curation | Validation failures, quality check errors, group chat session issues |

### AI/LLM System Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **LLM_CONNECTION** | `llm` | LLM service connection | Anthropic API down, authentication failures, rate limits |
| **LLM_GENERATION** | `llm_generation` | Response generation | Generation timeouts, malformed responses, token limit exceeded |
| **SKINFLAP_DETECTION** | `skinflap` | Query stupidity detection | Detection algorithm failures, false positives |
| **QUERY_REFORMING** | `query_reform` | Query improvement | Reformulation failures, multi-query generation errors |

### Recovery & Backup Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **RECOVERY_SYSTEM** | `recovery` | Overall recovery process health | Recovery coordinator failures, health check errors |
| **RECOVERY_THREAD** | `recovery_thread` | Individual thread lifecycle | Thread spawn failures, thread death, monitoring issues |
| **BACKUP_SYSTEM** | `backup` | Regular backup operations | Scheduled backup failures, backup file write errors |
| **EMERGENCY_BACKUP** | `emergency_backup` | Critical backup operations | Crash backup failures, emergency save errors |

### Infrastructure & Services Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **SERVICE_CONNECTION** | `service` | General service connectivity | HTTP connection failures, timeout errors, port unavailable |
| **SERVICE_HEALTH** | `service_health` | Service health monitoring | Health check failures, monitoring errors, status unknown |
| **AUTO_START** | `auto_start` | Service auto-start system | Docker start failures, service spawn errors, startup timeout |

### User Interface Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **UI_RENDERING** | `ui` | UI display/rendering | Rich panel rendering errors, table display failures |
| **UI_INPUT** | `ui_input` | User input processing | Input validation failures, prompt errors |
| **UI_LAYOUT** | `ui_layout` | Layout management | Panel sizing errors, layout calculation failures |

### Message Processing Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **MESSAGE_PROCESSING** | `processing` | Core message processing | Pipeline failures, processing step errors |
| **MESSAGE_VALIDATION** | `validation` | Message validation | Invalid message format, validation rule failures |
| **CONVERSATION_FLOW** | `conversation` | Conversation management | Turn tracking errors, context management failures |

### File & Data Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **FILE_OPERATIONS** | `file_ops` | File read/write operations | Permission denied, file not found, disk full |
| **DATA_SERIALIZATION** | `serialization` | JSON/data serialization | JSON parse errors, encoding failures, malformed data |
| **HISTORY_RESTORATION** | `history` | Conversation history operations | History load failures, corrupted history files |

### Threading & Concurrency Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **THREADING** | `threading` | General thread management | Thread creation failures, deadlocks, race conditions |
| **SIGNAL_HANDLING** | `signals` | Signal handling (Ctrl+C, etc) | Signal handler failures, graceful shutdown errors |

### Catch-all Categories

| Category | Enum Value | Description | Example Errors |
|----------|-----------|-------------|----------------|
| **GENERAL** | `general` | Uncategorized errors | Errors that don't fit specific categories |
| **UNKNOWN** | `unknown` | When category can't be determined | Completely unexpected errors, system anomalies |

---

## Usage Examples by Service

### Working Memory Service

```python
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity

# Data loss scenario - CRITICAL
try:
    exchange, summary = working_memory_service.add_exchange(user_msg, assistant_msg)
except Exception as e:
    logger.error(f"Error adding exchange (request: {g.request_id}): {e}")
    # Use CRITICAL because losing conversation exchanges is serious
    # Category: WORKING_MEMORY because it's the working memory buffer
    return jsonify({
        "status": "error",
        "message": str(e),
        "request_id": g.request_id
    }), 500
```

**Severity:** HIGH_DEGRADE (feature broken but service continues)
**Category:** WORKING_MEMORY

### Episodic Memory Service

```python
# Archival failure - HIGH severity
try:
    conversation_id = episodic_service.archive_conversation(data, reason)
except Exception as e:
    logger.error(f"Error archiving conversation (request: {g.request_id}): {e}")
    # HIGH_DEGRADE: Long-term storage failed but working memory still works
    # Category: MEMORY_ARCHIVAL because we're moving working→episodic
    return jsonify({
        "status": "error",
        "message": str(e),
        "request_id": g.request_id
    }), 500
```

**Severity:** HIGH_DEGRADE (archival broken but reads work)
**Category:** MEMORY_ARCHIVAL

### API Server Bridge

```python
# Chat processing failure
try:
    result = chat.process_message(message.message)
except Exception as e:
    error_msg = f"Chat processing failed: {str(e)}"
    track_error(error_msg, context, "chat_processor", "critical", original_exception=e)
    # CRITICAL: Main chat feature completely broken
    # Category: MESSAGE_PROCESSING mapped from "chat_processor"
    return ChatResponse(
        response="Sorry, I encountered an error",
        error=error_msg,
        request_id=get_request_id()
    )
```

**Severity:** CRITICAL_STOP (chat completely broken)
**Category:** MESSAGE_PROCESSING

### MCP Logger (Proxy Pattern)

```python
# Service timeout with retry
for attempt in range(retry_count):
    try:
        response = requests.post(url, json=data, timeout=timeout)
        if response.status_code == 200:
            return True, response.json()
    except requests.exceptions.Timeout:
        router_logger.log_warning("SERVICE_TIMEOUT", ...)
        # MEDIUM_ALERT: Service temporarily unavailable, will retry
        # Category: SERVICE_CONNECTION
        if attempt == retry_count - 1:
            return False, {"error": "Service timeout"}
```

**Severity:** MEDIUM_ALERT (temporary issue with retry)
**Category:** SERVICE_CONNECTION

---

## Common Patterns by Service Type

### Flask Microservices (working_memory, episodic_memory, curator)

**Standard Error Handling Pattern:**
```python
@app.route('/endpoint', methods=['POST'])
def endpoint():
    try:
        result = service.operation(data)
        return jsonify({
            "status": "success",
            "result": result,
            "request_id": g.request_id
        })
    except Exception as e:
        logger.error(f"Error in operation (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500
```

**Category Selection:**
- Database operations → EPISODIC_MEMORY or WORKING_MEMORY
- Validation operations → CURATOR or MESSAGE_VALIDATION
- Service routing → SERVICE_CONNECTION

**Severity Selection:**
- Data loss risk → CRITICAL_STOP or HIGH_DEGRADE
- Temporary failures → MEDIUM_ALERT
- Expected edge cases → LOW_DEBUG

### FastAPI Bridge (api_server_bridge)

**Hybrid Pattern with track_error():**
```python
@app.post("/endpoint")
async def endpoint(data: Model):
    try:
        result = process(data)
        return Response(result=result, request_id=get_request_id())
    except Exception as e:
        error_msg = f"Operation failed: {str(e)}"
        track_error(error_msg, context, service_name, severity, original_exception=e)
        return Response(error=error_msg, request_id=get_request_id())
```

**Category Mapping in track_error():**
- "chat_processor" → MESSAGE_PROCESSING
- "memory_system" → WORKING_MEMORY
- "websocket" → SERVICE_CONNECTION
- "api_server" → SERVICE_CONNECTION

**Severity Mapping in track_error():**
- "critical" → CRITICAL_STOP
- "warning" → MEDIUM_ALERT
- "normal" → MEDIUM_ALERT
- "debug" → LOW_DEBUG

---

## Decision Matrix: Which Category/Severity?

### By Error Type

| Error Type | Category | Typical Severity | Rationale |
|------------|----------|-----------------|-----------|
| Database write failure | EPISODIC_MEMORY | HIGH_DEGRADE | Data might be lost but reads work |
| Database read failure | EPISODIC_MEMORY | MEDIUM_ALERT | Temporary issue, retry likely works |
| Buffer overflow | WORKING_MEMORY | HIGH_DEGRADE | Recent context lost but system continues |
| LLM API timeout | LLM_CONNECTION | MEDIUM_ALERT | Temporary, user can retry |
| LLM API auth failure | LLM_CONNECTION | CRITICAL_STOP | Won't work until fixed |
| Service health check fail | SERVICE_HEALTH | MEDIUM_ALERT | Monitoring issue, service may be fine |
| Service completely down | SERVICE_CONNECTION | HIGH_DEGRADE | Feature broken, need recovery |
| Validation failure | MESSAGE_VALIDATION | LOW_DEBUG | Expected, not an error |
| File not found | FILE_OPERATIONS | MEDIUM_ALERT | Missing expected file |
| Permission denied | FILE_OPERATIONS | HIGH_DEGRADE | Can't access needed resource |
| JSON parse error | DATA_SERIALIZATION | MEDIUM_ALERT | Bad data format, likely recoverable |
| Thread creation failure | THREADING | CRITICAL_STOP | System resource exhaustion |

### By Service

| Service | Primary Categories | Common Severities |
|---------|-------------------|-------------------|
| working_memory | WORKING_MEMORY, MEMORY_ARCHIVAL | HIGH_DEGRADE, MEDIUM_ALERT |
| episodic_memory | EPISODIC_MEMORY, MEMORY_ARCHIVAL | HIGH_DEGRADE, MEDIUM_ALERT |
| memory_curator | CURATOR, MESSAGE_VALIDATION | MEDIUM_ALERT, LOW_DEBUG |
| mcp_logger | MCP_LOGGER, SERVICE_CONNECTION | MEDIUM_ALERT |
| api_server_bridge | MESSAGE_PROCESSING, SERVICE_CONNECTION | CRITICAL_STOP, MEDIUM_ALERT |
| rich_chat | MESSAGE_PROCESSING, LLM_CONNECTION, WORKING_MEMORY | All severities depending on operation |

---

## Best Practices

### 1. Always Include Request ID
```python
# GOOD
logger.error(f"Error in operation (request: {g.request_id}): {e}")
return jsonify({"status": "error", "message": str(e), "request_id": g.request_id}), 500

# BAD
logger.error(f"Error in operation: {e}")
return jsonify({"status": "error", "message": str(e)}), 500
```

### 2. Preserve Original Exceptions
```python
# GOOD
track_error(error_msg, context, service, severity, original_exception=e)

# BAD
track_error(error_msg, context, service, severity)  # Loses stack trace!
```

### 3. Use Specific Categories
```python
# GOOD
error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.HIGH_DEGRADE)

# BAD
error_handler.handle_error(e, ErrorCategory.GENERAL, ErrorSeverity.MEDIUM_ALERT)
```

### 4. Match Severity to Impact
```python
# Data loss? → CRITICAL_STOP or HIGH_DEGRADE
# Temporary issue? → MEDIUM_ALERT
# Expected behavior? → LOW_DEBUG
# Deep debugging? → TRACE_FIWB
```

### 5. Log Context, Not Just Errors
```python
# GOOD
logger.error(f"Failed to archive conversation {conv_id} (request: {g.request_id}): {e}")

# BAD
logger.error(f"Error: {e}")
```

---

## Recovery Actions by Severity

Each severity level implies specific recovery actions that services should take.

### CRITICAL_STOP Recovery Actions

**Immediate Actions:**
1. **Log with full context** - Stack trace, request ID, service state
2. **Stop accepting new requests** - Return 503 Service Unavailable
3. **Alert operator** - Send notification (if alerting system exists)
4. **Preserve current state** - Emergency backup if possible
5. **Wait for manual intervention** - Do NOT auto-restart

**Example Implementation:**
```python
except Exception as e:
    logger.critical(f"CRITICAL: Service cannot continue (request: {g.request_id}): {e}")
    error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.CRITICAL_STOP)

    # Stop accepting requests
    app.config['ACCEPTING_REQUESTS'] = False

    # Return 503
    return jsonify({
        "status": "critical_error",
        "message": "Service unavailable due to critical error",
        "request_id": g.request_id,
        "action_required": "Contact operator"
    }), 503
```

**When to Use:**
- Database corrupted beyond auto-repair
- Disk full (cannot write logs/data)
- Authentication permanently revoked
- Memory exhaustion (OOM imminent)

### HIGH_DEGRADE Recovery Actions

**Immediate Actions:**
1. **Log degradation state** - What's broken, what still works
2. **Enable fallback mode** - Use alternative approach if available
3. **Continue serving requests** - Degraded but functional
4. **Track degradation metrics** - Count affected operations
5. **Attempt auto-recovery** - Retry connection, clear cache, etc.

**Example Implementation:**
```python
except Exception as e:
    logger.error(f"Feature degraded (request: {g.request_id}): {e}")
    error_handler.handle_error(e, ErrorCategory.MEMORY_ARCHIVAL, ErrorSeverity.HIGH_DEGRADE)

    # Enable fallback mode
    memory_handler.episodic_archival_enabled = False
    memory_handler.episodic_archival_failures += 1

    # Still return success (working memory stored it)
    return jsonify({
        "status": "success_degraded",
        "message": "Stored in working memory (episodic archival unavailable)",
        "exchange": exchange,
        "degradation": "long_term_storage_offline",
        "request_id": g.request_id
    })
```

**When to Use:**
- Episodic archival fails (working memory still works)
- Multi-query disabled (basic query still works)
- Validation service down (skip validation, continue)
- Read-only database mode (reads work, writes fail)

### MEDIUM_ALERT Recovery Actions

**Immediate Actions:**
1. **Log warning with context** - Request ID, operation, error
2. **Return error to user** - Clear error message in response
3. **Continue normal operation** - No degradation needed
4. **Track error frequency** - Pattern detection
5. **Retry if appropriate** - For transient failures

**Example Implementation:**
```python
except Exception as e:
    logger.warning(f"Operation failed (request: {g.request_id}): {e}")
    error_handler.handle_error(e, ErrorCategory.SERVICE_CONNECTION, ErrorSeverity.MEDIUM_ALERT)

    # Return error to user
    return jsonify({
        "status": "error",
        "message": f"Service temporarily unavailable: {str(e)}",
        "retry_recommended": True,
        "request_id": g.request_id
    }), 503
```

**When to Use:**
- Service health check timeout
- Single request failure (others succeed)
- Temporary network issue
- Cache miss (expected but notable)

### LOW_DEBUG Recovery Actions

**Immediate Actions:**
1. **Log at debug level** - Only visible in debug mode
2. **No user notification** - Not shown in UI
3. **Continue silently** - No impact on operation
4. **Optional metrics tracking** - For analysis

**Example Implementation:**
```python
if not results:
    logger.debug(f"Search returned no results for query (request: {g.request_id})")
    # No error handler call needed - this is expected behavior

    return jsonify({
        "status": "success",
        "results": [],
        "count": 0,
        "request_id": g.request_id
    })
```

**When to Use:**
- Empty search results (no matches)
- Cache hit/miss (informational)
- Optimization skipped (not needed)
- Expected edge cases

### TRACE_FIWB Recovery Actions

**Immediate Actions:**
1. **Log extreme detail** - Only in FIWB mode
2. **Include all state** - Full object dumps, stack traces
3. **Performance impact acceptable** - Debug trumps speed
4. **No production use** - Development/troubleshooting only

**Example Implementation:**
```python
if error_handler.fuck_it_we_ball_mode:
    logger.debug(f"[FIWB] Full context dump: {json.dumps(full_state, indent=2)}")
    logger.debug(f"[FIWB] Stack trace: {traceback.format_exc()}")
    logger.debug(f"[FIWB] All variables: {locals()}")
```

**When to Use:**
- Deep troubleshooting sessions
- Debugging cascading failures
- Reproducing intermittent issues
- Performance profiling

---

## Cross-Service Error Propagation

When one service fails, errors can cascade through the system. Understanding these cascades helps with categorization and severity decisions.

### Scenario 1: Episodic Memory Down

**Cascade:**
```
episodic_memory (DOWN)
└─> memory_handler.archive_conversation() → FAILS
    └─> rich_chat.store_exchange() → DEGRADES
        └─> working_memory.add_exchange() → SUCCEEDS (fallback)
            └─> User chat experience → CONTINUES (slight delay)
```

**Error Handling:**
- **episodic_memory**: Returns 503 Service Unavailable
- **memory_handler**: Catches error, increments failure counter
- **Severity**: HIGH_DEGRADE (long-term storage broken, short-term still works)
- **Category**: MEMORY_ARCHIVAL (the operation that failed)
- **User Impact**: Chat continues, but conversations won't be permanently saved

**Code Example:**
```python
# In memory_handler.py
try:
    response = requests.post(f"{self.services['episodic']}/archive", json=data)
    response.raise_for_status()
except requests.RequestException as e:
    self.episodic_archival_failures += 1
    logger.error(f"Episodic archival failed ({self.episodic_archival_failures} consecutive): {e}")

    if self.episodic_archival_failures >= 3:
        # After 3 failures, mark as degraded
        error_handler.handle_error(e, ErrorCategory.MEMORY_ARCHIVAL, ErrorSeverity.HIGH_DEGRADE)
    else:
        # First few failures are just warnings
        error_handler.handle_error(e, ErrorCategory.MEMORY_ARCHIVAL, ErrorSeverity.MEDIUM_ALERT)
```

### Scenario 2: LLM Service Down

**Cascade:**
```
anthropic_api (DOWN)
└─> llm_handler.generate_response() → FAILS
    └─> rich_chat.process_message() → FAILS
        └─> api_server_bridge.chat_endpoint() → RETURNS ERROR
            └─> User chat experience → BROKEN
```

**Error Handling:**
- **llm_handler**: Raises exception with connection error
- **rich_chat**: Cannot provide alternative (no fallback LLM)
- **Severity**: CRITICAL_STOP (core feature completely broken)
- **Category**: LLM_CONNECTION
- **User Impact**: Cannot chat at all, system unusable

**Code Example:**
```python
# In rich_chat.py
try:
    response = self.llm_handler.generate_response(prompt)
except anthropic.APIConnectionError as e:
    logger.critical(f"LLM service unreachable: {e}")
    error_handler.handle_error(e, ErrorCategory.LLM_CONNECTION, ErrorSeverity.CRITICAL_STOP)

    return {
        "response": "I'm unable to connect to my AI service. Please try again later or contact support.",
        "error": "llm_connection_failed",
        "severity": "critical"
    }
```

### Scenario 3: Working Memory Full (Buffer Overflow)

**Cascade:**
```
working_memory (BUFFER FULL)
└─> working_memory.add_exchange() → Evicts oldest exchange (SUCCESS)
    └─> episodic_memory.archive() → TRIGGERED (background)
        └─> Oldest exchange archived → SUCCESS
            └─> User chat experience → CONTINUES (seamless)
```

**Error Handling:**
- **working_memory**: No error! This is expected behavior
- **Severity**: LOW_DEBUG (informational, working as designed)
- **Category**: WORKING_MEMORY
- **User Impact**: None (transparent to user)

**Code Example:**
```python
# In buffer.py
def add_exchange(self, user_message, assistant_response, context_used):
    exchange = {
        "exchange_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "user": user_message,
        "assistant": assistant_response,
        "context": context_used
    }

    if len(self.buffer) >= self.buffer.maxlen:
        logger.debug(f"Buffer full ({self.buffer.maxlen}), evicting oldest exchange")
        # Deque automatically evicts oldest - this is expected behavior
        # No error handler needed, this is LOW_DEBUG informational

    self.buffer.append(exchange)
    return exchange
```

### Scenario 4: MCP Logger Proxy Failure

**Cascade:**
```
target_service (working_memory) → TIMEOUT
└─> mcp_logger.route_request() → RETRY (3 attempts)
    └─> Retry #1 → TIMEOUT
        └─> Retry #2 → TIMEOUT
            └─> Retry #3 → TIMEOUT
                └─> Return error to caller → MEDIUM_ALERT
```

**Error Handling:**
- **mcp_logger**: Sophisticated retry with backoff
- **Severity**: MEDIUM_ALERT (transient issue, retries exhausted)
- **Category**: SERVICE_CONNECTION
- **User Impact**: Log routing failed, but doesn't block user

**Code Example:**
```python
# In router.py
for attempt in range(service.retry_count):
    try:
        response = requests.post(url, json=data, timeout=service.timeout)
        if response.status_code == 200:
            return True, response.json()
    except requests.exceptions.Timeout:
        if attempt == service.retry_count - 1:
            # Last attempt failed
            router_logger.log_warning("SERVICE_TIMEOUT",
                f"Service {service_name} timeout after {attempt+1} attempts")
            error_handler.handle_error(
                TimeoutError(f"Service timeout after {attempt+1} attempts"),
                ErrorCategory.SERVICE_CONNECTION,
                ErrorSeverity.MEDIUM_ALERT
            )
            return False, {"error": "Service timeout"}
        else:
            # Retry
            logger.debug(f"Timeout on attempt {attempt+1}, retrying...")
            time.sleep(0.5 * (attempt + 1))  # Exponential backoff
```

### Scenario 5: Database Lock (SQLite)

**Cascade:**
```
episodic_memory.db (LOCKED by long query)
└─> archive_conversation() → WAITS (5 seconds)
    └─> SQLite timeout → RAISES OperationalError
        └─> Flask endpoint → CATCHES exception
            └─> Returns 500 → MEDIUM_ALERT (if transient) or HIGH_DEGRADE (if persistent)
```

**Error Handling:**
- **episodic_memory**: SQLite raises OperationalError
- **Severity**: Depends on frequency
  - First occurrence: MEDIUM_ALERT (transient lock)
  - Repeated failures: HIGH_DEGRADE (database issue)
- **Category**: EPISODIC_MEMORY
- **User Impact**: Archival delayed, but working memory still stores exchanges

**Code Example:**
```python
# In episodic_memory service
try:
    cursor.execute("INSERT INTO conversations ...", data)
    conn.commit()
except sqlite3.OperationalError as e:
    if "database is locked" in str(e):
        self.db_lock_failures += 1

        if self.db_lock_failures >= 3:
            # Persistent locking issue
            logger.error(f"Database locked persistently ({self.db_lock_failures} times)")
            error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.HIGH_DEGRADE)
        else:
            # Transient lock
            logger.warning(f"Database locked temporarily (attempt {self.db_lock_failures})")
            error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.MEDIUM_ALERT)

        conn.rollback()
        raise
```

### Cascade Pattern Summary

| Failure Point | Propagates To | Severity | User Impact |
|---------------|---------------|----------|-------------|
| episodic_memory | memory_handler → working_memory (fallback) | HIGH_DEGRADE | Chat works, no long-term storage |
| working_memory | rich_chat → LLM still works | HIGH_DEGRADE | Chat works, no context |
| LLM service | rich_chat → complete failure | CRITICAL_STOP | Chat broken |
| curator service | rich_chat → validation skipped | MEDIUM_ALERT | Chat works, no quality checks |
| mcp_logger | Original service → logs not routed | LOW_DEBUG | Transparent to user |
| Database lock | Single operation → retry likely succeeds | MEDIUM_ALERT → HIGH_DEGRADE | Depends on frequency |

---

## Service-Specific Deep Dives

### Working Memory Service

**What Can Go Wrong:**

1. **Buffer Lock Timeout**
   - **Cause**: Thread contention on buffer_lock
   - **Symptom**: Add/get operations hang
   - **Severity**: MEDIUM_ALERT (single request affected)
   - **Category**: WORKING_MEMORY
   - **Recovery**: Timeout and retry

2. **Buffer Overflow (Expected)**
   - **Cause**: Buffer reaches maxlen
   - **Symptom**: Oldest exchanges evicted
   - **Severity**: LOW_DEBUG (working as designed)
   - **Category**: WORKING_MEMORY
   - **Recovery**: None needed (automatic eviction)

3. **Invalid Exchange Data**
   - **Cause**: Missing user_message or assistant_response
   - **Symptom**: 400 Bad Request
   - **Severity**: LOW_DEBUG (client error)
   - **Category**: MESSAGE_VALIDATION
   - **Recovery**: Return 400 with clear error message

4. **Deque Corruption (Rare)**
   - **Cause**: Memory corruption, concurrent modification
   - **Symptom**: Unexpected deque state
   - **Severity**: CRITICAL_STOP (data structure compromised)
   - **Category**: WORKING_MEMORY
   - **Recovery**: Restart service, clear buffer

**Common Error Patterns:**
```python
# Pattern 1: Lock timeout
try:
    if not self.buffer_lock.acquire(timeout=5):
        raise TimeoutError("Buffer lock timeout")
    try:
        # operation
    finally:
        self.buffer_lock.release()
except TimeoutError as e:
    logger.warning(f"Lock timeout (request: {g.request_id})")
    # MEDIUM_ALERT - single request affected
```

### Episodic Memory Service

**What Can Go Wrong:**

1. **SQLite Database Locked**
   - **Cause**: Long-running query, concurrent writes
   - **Symptom**: OperationalError: database is locked
   - **Severity**: MEDIUM_ALERT (transient) → HIGH_DEGRADE (persistent)
   - **Category**: EPISODIC_MEMORY
   - **Recovery**: Retry with backoff, increase timeout

2. **Database Corruption**
   - **Cause**: Disk failure, improper shutdown, SQLite bug
   - **Symptom**: DatabaseError: database disk image is malformed
   - **Severity**: CRITICAL_STOP (data loss risk)
   - **Category**: EPISODIC_MEMORY
   - **Recovery**: Stop service, restore from backup

3. **Disk Full**
   - **Cause**: Database growth, insufficient space
   - **Symptom**: OperationalError: disk full
   - **Severity**: CRITICAL_STOP (cannot write)
   - **Category**: EPISODIC_MEMORY
   - **Recovery**: Stop service, free disk space

4. **Invalid Conversation Data**
   - **Cause**: Missing required fields, bad JSON
   - **Symptom**: 400 Bad Request
   - **Severity**: LOW_DEBUG (client error)
   - **Category**: MESSAGE_VALIDATION
   - **Recovery**: Return 400 with clear error message

**SQLite-Specific Error Handling:**
```python
try:
    cursor.execute("INSERT INTO conversations VALUES (?, ?, ?)", data)
    conn.commit()
except sqlite3.OperationalError as e:
    if "database is locked" in str(e):
        # Transient lock - retry
        severity = ErrorSeverity.MEDIUM_ALERT
    elif "disk full" in str(e):
        # Critical - cannot continue
        severity = ErrorSeverity.CRITICAL_STOP
    else:
        # Unknown operational error
        severity = ErrorSeverity.HIGH_DEGRADE

    logger.error(f"Database error (request: {g.request_id}): {e}")
    error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, severity)
    conn.rollback()
    raise

except sqlite3.DatabaseError as e:
    # Corruption or severe database issue
    logger.critical(f"Database corruption detected: {e}")
    error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.CRITICAL_STOP)
    raise
```

### Memory Curator Service

**What Can Go Wrong:**

1. **Validation Engine Failure**
   - **Cause**: LLM timeout, malformed validation response
   - **Symptom**: Validation returns error
   - **Severity**: MEDIUM_ALERT (validation unavailable)
   - **Category**: CURATOR
   - **Recovery**: Skip validation, continue processing

2. **Group Chat Session Timeout**
   - **Cause**: Session inactive, expired
   - **Symptom**: Session ID not found
   - **Severity**: LOW_DEBUG (expected cleanup)
   - **Category**: CURATOR
   - **Recovery**: Return 404 with clear message

3. **Validation False Positive**
   - **Cause**: Overzealous quality checks
   - **Symptom**: Valid content marked as invalid
   - **Severity**: MEDIUM_ALERT (quality issue)
   - **Category**: MESSAGE_VALIDATION
   - **Recovery**: Log for review, allow override

### MCP Logger Service

**What Can Go Wrong:**

1. **Target Service Timeout**
   - **Cause**: Slow service, network issue
   - **Symptom**: requests.Timeout
   - **Severity**: MEDIUM_ALERT (after retries exhausted)
   - **Category**: SERVICE_CONNECTION
   - **Recovery**: Retry 3x with backoff, then fail

2. **Target Service Down**
   - **Cause**: Service crashed, not started
   - **Symptom**: ConnectionRefusedError
   - **Severity**: HIGH_DEGRADE (routing broken)
   - **Category**: SERVICE_CONNECTION
   - **Recovery**: Return error, alert operator

3. **Invalid Routing Configuration**
   - **Cause**: Bad service URL, port mismatch
   - **Symptom**: Connection fails immediately
   - **Severity**: HIGH_DEGRADE (misconfiguration)
   - **Category**: SERVICE_CONNECTION
   - **Recovery**: Log config error, return 500

---

## Real Error Examples

### Example 1: SQLite Database Locked

**Stack Trace:**
```
Traceback (most recent call last):
  File "/app/service.py", line 142, in archive_conversation
    cursor.execute("INSERT INTO conversations VALUES (?, ?, ?, ?)",
                   (conversation_id, data, timestamp, trigger_reason))
sqlite3.OperationalError: database is locked
```

**Analysis:**
- **Exception Type**: `sqlite3.OperationalError`
- **Error Message**: "database is locked"
- **Root Cause**: Another transaction holding database lock
- **Category**: EPISODIC_MEMORY (database operation)
- **Severity Decision**:
  - First occurrence: MEDIUM_ALERT (likely transient)
  - Repeated failures (3+): HIGH_DEGRADE (persistent locking issue)

**Proper Handling:**
```python
try:
    cursor.execute("INSERT INTO conversations VALUES (?, ?, ?, ?)", data)
    conn.commit()
except sqlite3.OperationalError as e:
    if "database is locked" in str(e):
        self.lock_failures += 1

        if self.lock_failures >= 3:
            logger.error(f"Persistent database lock (request: {g.request_id})")
            error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.HIGH_DEGRADE)
        else:
            logger.warning(f"Transient database lock (request: {g.request_id})")
            error_handler.handle_error(e, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.MEDIUM_ALERT)

        conn.rollback()
        return jsonify({
            "status": "error",
            "message": "Database temporarily unavailable, please retry",
            "request_id": g.request_id
        }), 503
```

### Example 2: LLM API Connection Timeout

**Stack Trace:**
```
Traceback (most recent call last):
  File "/app/rich_chat.py", line 523, in process_message
    response = self.llm_handler.generate_response(prompt, context)
  File "/app/llm_handler.py", line 89, in generate_response
    message = self.client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
  File "/usr/local/lib/python3.11/site-packages/anthropic/_base_client.py", line 1026, in request
    raise APIConnectionError(request=request) from err
anthropic.APIConnectionError: Connection error
```

**Analysis:**
- **Exception Type**: `anthropic.APIConnectionError`
- **Error Message**: "Connection error"
- **Root Cause**: Network issue or Anthropic API down
- **Category**: LLM_CONNECTION
- **Severity Decision**: CRITICAL_STOP (chat completely broken, no fallback)

**Proper Handling:**
```python
try:
    response = self.llm_handler.generate_response(prompt, context)
except anthropic.APIConnectionError as e:
    logger.critical(f"LLM service unreachable (request: {g.request_id}): {e}")
    error_handler.handle_error(e, ErrorCategory.LLM_CONNECTION, ErrorSeverity.CRITICAL_STOP)

    return {
        "response": "I'm unable to connect to my AI service. Please check your connection and try again.",
        "error": "llm_connection_failed",
        "severity": "critical"
    }
```

### Example 3: Working Memory Buffer Lock Timeout

**Stack Trace:**
```
Traceback (most recent call last):
  File "/app/service.py", line 165, in add_exchange
    exchange, summary = working_memory_service.add_exchange(user_message, assistant_response, context_used)
  File "/app/service.py", line 53, in add_exchange
    with self.buffer_lock:
TimeoutError: Buffer lock acquisition timeout
```

**Analysis:**
- **Exception Type**: `TimeoutError`
- **Error Message**: "Buffer lock acquisition timeout"
- **Root Cause**: Thread contention on lock (rare)
- **Category**: WORKING_MEMORY
- **Severity Decision**: MEDIUM_ALERT (single request affected, others still work)

**Proper Handling:**
```python
try:
    exchange, summary = working_memory_service.add_exchange(user_msg, assistant_msg, context)
except TimeoutError as e:
    logger.warning(f"Buffer lock timeout (request: {g.request_id})")
    error_handler.handle_error(e, ErrorCategory.WORKING_MEMORY, ErrorSeverity.MEDIUM_ALERT)

    return jsonify({
        "status": "error",
        "message": "Service busy, please retry",
        "request_id": g.request_id
    }), 503
```

### Example 4: Requests Connection Refused (Service Down)

**Stack Trace:**
```
Traceback (most recent call last):
  File "/app/memory_handler.py", line 87, in archive_conversation
    response = requests.post(f"{self.services['episodic']}/archive", json=data, timeout=5)
  File "/usr/local/lib/python3.11/site-packages/requests/api.py", line 115, in post
    return request('post', url, data=data, json=json, **kwargs)
requests.exceptions.ConnectionError: HTTPConnectionPool(host='episodic-memory', port=5002): Max retries exceeded with url: /archive (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f8c2a3b4d90>: Failed to establish a new connection: [Errno 111] Connection refused'))
```

**Analysis:**
- **Exception Type**: `requests.exceptions.ConnectionError`
- **Error Message**: "Connection refused"
- **Root Cause**: episodic_memory service not running
- **Category**: SERVICE_CONNECTION
- **Severity Decision**: HIGH_DEGRADE (archival broken, but working memory still works)

**Proper Handling:**
```python
try:
    response = requests.post(f"{self.services['episodic']}/archive", json=data, timeout=5)
    response.raise_for_status()
except requests.exceptions.ConnectionError as e:
    self.episodic_archival_failures += 1

    if self.episodic_archival_failures >= 3:
        logger.error(f"Episodic service unreachable (consecutive failures: {self.episodic_archival_failures})")
        error_handler.handle_error(e, ErrorCategory.SERVICE_CONNECTION, ErrorSeverity.HIGH_DEGRADE)
    else:
        logger.warning(f"Episodic service connection failed (attempt {self.episodic_archival_failures})")
        error_handler.handle_error(e, ErrorCategory.SERVICE_CONNECTION, ErrorSeverity.MEDIUM_ALERT)

    # Continue with degraded functionality (working memory only)
    return {"status": "success_degraded", "note": "Long-term storage unavailable"}
```

### Example 5: JSON Decode Error (Malformed Response)

**Stack Trace:**
```
Traceback (most recent call last):
  File "/app/api_server_bridge.py", line 372, in search_memories
    results = chat.memory_handler.search_memories(query)
  File "/app/memory_handler.py", line 156, in search_memories
    data = response.json()
  File "/usr/local/lib/python3.11/site-packages/requests/models.py", line 975, in json
    return complexjson.loads(self.text, **kwargs)
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Analysis:**
- **Exception Type**: `json.decoder.JSONDecodeError`
- **Error Message**: "Expecting value: line 1 column 1"
- **Root Cause**: Service returned non-JSON response (maybe HTML error page)
- **Category**: DATA_SERIALIZATION
- **Severity Decision**: MEDIUM_ALERT (single operation failed, likely service issue)

**Proper Handling:**
```python
try:
    response = requests.get(f"{service_url}/search", params={"query": query})
    response.raise_for_status()
    data = response.json()
except json.JSONDecodeError as e:
    logger.warning(f"Invalid JSON response from search (request: {g.request_id}): {e}")
    logger.debug(f"Response content: {response.text[:200]}")  # Log first 200 chars
    error_handler.handle_error(e, ErrorCategory.DATA_SERIALIZATION, ErrorSeverity.MEDIUM_ALERT)

    return jsonify({
        "status": "error",
        "message": "Service returned invalid response",
        "request_id": g.request_id
    }), 502
```

---

## Testing Error Handling

See **ERROR_HANDLER_TESTING_GUIDE.md** for comprehensive testing procedures for each service type.

---

## Reference

- **Source Code:** `/home/grinnling/Development/CODE_IMPLEMENTATION/error_handler.py`
- **Service Implementations:**
  - working_memory: `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/working_memory/service.py`
  - episodic_memory: `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/episodic_memory/service.py`
  - memory_curator: `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/memory_curator/curator_service.py`
  - mcp_logger: `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/mcp_logger/server.py`
  - api_server_bridge: `/home/grinnling/Development/CODE_IMPLEMENTATION/api_server_bridge.py`
- **Audit Document:** `/home/grinnling/Development/CODE_IMPLEMENTATION/ERROR_HANDLER_SERVICE_AUDIT_2025-10-31.md`
