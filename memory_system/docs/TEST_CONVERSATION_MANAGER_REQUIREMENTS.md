# ConversationManager Test Requirements

**Created:** December 16, 2025
**Module:** `/home/grinnling/Development/CODE_IMPLEMENTATION/conversation_manager.py`
**Purpose:** Define what's needed to properly test the extracted ConversationManager module

---

## What I Need to Test This Module

### 1. Mock Dependencies

The ConversationManager has three main dependencies that need mocking:

```python
# These need to be mockable/injectable
self.service_manager      # For health checks and service URLs
self.error_handler        # For error logging
self.orchestrator         # ConversationOrchestrator (for add_exchange, create_root_context, etc.)
```

**What I'd find helpful:** The current implementation creates these internally or requires them in `__init__`. For testability, I need:
- A way to inject mock `ServiceManager` that returns controlled health check responses
- A way to inject mock `ConversationOrchestrator` to verify correct method calls
- The error_handler is already optional (good)

### 2. External Service Mocks

The module makes HTTP calls to:

| Service | Endpoints Used | What to Mock |
|---------|---------------|--------------|
| Working Memory | `POST /store`, `GET /recent` | Store success/failure, retrieval results |
| Episodic Memory | `GET /recent`, `GET /conversation/{id}` | List results, conversation load |

**What I'd find helpful:**
- `responses` or `httpx-mock` library for mocking HTTP calls
- Fixture data representing typical working/episodic memory responses

### 3. OZOLITH Integration Verification

The module logs these events to OZOLITH:
- `MEMORY_STORED` (in store_exchange)
- `MEMORY_RETRIEVED` (in get_context_for_llm)
- `MEMORY_RECALLED` (in switch_conversation)

**What I'd find helpful:**
- A way to capture/verify OZOLITH append calls happened with correct event types
- Mock for `_get_ozolith()` that returns a test double

---

## Test Categories

### Unit Tests (isolated logic)

```python
# test_conversation_manager_unit.py

class TestConversationManagerUnit:

    def test_start_new_conversation_generates_uuid(self):
        """Verify conversation_id is valid UUID after start"""

    def test_start_new_conversation_calls_orchestrator(self):
        """Verify create_root_context called with task_description"""

    def test_get_recent_context_hint_empty_history(self):
        """Returns empty string when < 2 exchanges"""

    def test_get_recent_context_hint_extracts_topics(self):
        """Extracts bug/feature/error keywords from recent exchanges"""

    def test_store_exchange_adds_to_history(self):
        """Local conversation_history updated after store"""

    def test_store_exchange_returns_exchange_id(self):
        """Returns ID from orchestrator.add_exchange"""
```

### Integration Tests (with mocked services)

```python
# test_conversation_manager_integration.py

class TestConversationManagerWithMockedServices:

    @responses.activate
    def test_list_conversations_queries_episodic(self):
        """Verify correct API call to episodic memory"""

    @responses.activate
    def test_switch_conversation_loads_history(self):
        """Verify history loaded from episodic on switch"""

    @responses.activate
    def test_store_exchange_persists_to_working_memory(self):
        """Verify POST to working memory service"""

    @responses.activate
    def test_restore_pulls_from_both_services(self):
        """Verify working + episodic both queried on restore"""
```

### OZOLITH Verification Tests

```python
# test_conversation_manager_ozolith.py

class TestConversationManagerOzolithLogging:

    def test_store_exchange_logs_memory_stored(self):
        """MEMORY_STORED event logged with correct payload"""

    def test_get_context_logs_memory_retrieved(self):
        """MEMORY_RETRIEVED event logged with exchange IDs"""

    def test_switch_conversation_logs_memory_recalled(self):
        """MEMORY_RECALLED event logged on conversation load"""
```

### Error Handling Tests

```python
# test_conversation_manager_errors.py

class TestConversationManagerErrorHandling:

    def test_list_conversations_handles_service_down(self):
        """Returns empty list when episodic unavailable"""

    def test_switch_conversation_handles_not_found(self):
        """Returns False when conversation doesn't exist"""

    def test_store_exchange_continues_on_working_memory_failure(self):
        """Exchange still stored to orchestrator if working memory fails"""
```

---

## Test Fixtures Needed

### 1. Mock Service Manager

```python
@pytest.fixture
def mock_service_manager():
    """ServiceManager that reports all services healthy"""
    manager = MagicMock()
    manager.check_service_health.return_value = True
    manager.get_service_url.side_effect = lambda name: {
        'working_memory': 'http://localhost:8001',
        'episodic_memory': 'http://localhost:8002'
    }.get(name)
    return manager
```

### 2. Mock Orchestrator

```python
@pytest.fixture
def mock_orchestrator():
    """ConversationOrchestrator that tracks calls"""
    orch = MagicMock()
    orch.create_root_context.return_value = "CTX-test-123"
    orch.add_exchange.return_value = "EXCH-test-456"
    orch.get_active_context_id.return_value = "CTX-test-123"
    return orch
```

### 3. Sample Conversation Data

```python
@pytest.fixture
def sample_episodic_conversations():
    """What episodic memory API returns for list"""
    return {
        'conversations': [
            {'id': 'conv-1', 'created_at': '2025-12-15T10:00:00Z', 'exchange_count': 5},
            {'id': 'conv-2', 'created_at': '2025-12-14T14:30:00Z', 'exchange_count': 12}
        ]
    }

@pytest.fixture
def sample_conversation_history():
    """What episodic memory returns for a specific conversation"""
    return {
        'exchanges': [
            {'id': 'EXCH-1', 'user': 'Hello', 'assistant': 'Hi there!'},
            {'id': 'EXCH-2', 'user': 'Help with bug', 'assistant': 'What bug?'}
        ]
    }
```

---

## Questions for You (Operator)

1. **Where should these tests live?**
   - `tests/test_conversation_manager.py` (new file)?
   - Inside existing test structure?

2. **Do we have `responses` or `httpx-mock` already?**
   - Need to mock HTTP calls to working/episodic memory services

3. **Should I create a test harness for OZOLITH verification?**
   - Something like `OzolithTestCapture` that records all append calls

4. **Priority?**
   - Unit tests first (no external deps)?
   - Integration tests first (more realistic)?
   - OZOLITH verification first (audit trail is critical)?

---

## What Would Help ME Work Better

1. **Dependency injection pattern** - If we refactored ConversationManager to accept `ozolith` as an optional parameter instead of calling `_get_ozolith()` internally, testing becomes much cleaner.

2. **Service URL configuration** - Currently uses `self.service_manager.get_service_url()`. A constant or config-based approach would be easier to test.

3. **Trace header generation** - The `_get_trace_headers()` method could be extracted to make correlation ID testing easier.

These aren't blockers - I can work around them with mocking. But if we're doing more extraction work later, building in testability from the start saves effort.

---

## Estimated Test Count

| Category | Test Count |
|----------|------------|
| Unit tests | ~8-10 |
| Integration tests | ~6-8 |
| OZOLITH verification | ~4-5 |
| Error handling | ~5-6 |
| **Total** | **~25-30 tests** |

---

**Next Step:** Pick a category and I'll write the actual test file.
