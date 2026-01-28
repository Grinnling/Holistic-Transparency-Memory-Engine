# Redis Client Test Requirements Document

This document specifies comprehensive test requirements for `/home/grinnling/Development/CODE_IMPLEMENTATION/redis_client.py`.

---

## Table of Contents

1. [Test Infrastructure](#test-infrastructure)
2. [RedisClient Class Tests](#redisclient-class-tests)
   - [Connection Handling](#1-connection-handling)
   - [Yarn Board State](#2-yarn-board-state)
   - [Agent Presence](#3-agent-presence)
   - [Message Queues](#4-message-queues)
   - [Pub/Sub](#5-pubsub)
   - [Health Check](#6-health-check)
3. [Graceful Degradation Tests](#graceful-degradation-tests)
4. [RedisInterfaceAdapter Tests](#redisinterfaceadapter-tests)
5. [Integration Tests](#integration-tests)

---

## Test Infrastructure

### Required Test Dependencies

```python
# requirements-test.txt additions
pytest>=7.0.0
pytest-asyncio>=0.21.0
fakeredis>=2.20.0  # In-memory Redis mock
pytest-mock>=3.10.0
freezegun>=1.2.0   # For datetime mocking
```

### Fixtures Required

```python
# conftest.py

import pytest
from unittest.mock import MagicMock, patch
import fakeredis

@pytest.fixture
def mock_redis_server():
    """Provides a fakeredis server instance."""
    return fakeredis.FakeServer()

@pytest.fixture
def connected_redis_client(mock_redis_server):
    """RedisClient with working fakeredis backend."""
    with patch('redis.Redis', fakeredis.FakeRedis):
        from redis_client import RedisClient
        client = RedisClient()
        client._client = fakeredis.FakeRedis(server=mock_redis_server)
        client._connected = True
        yield client

@pytest.fixture
def disconnected_redis_client():
    """RedisClient in disconnected/stub mode."""
    with patch('redis.Redis') as mock_redis:
        mock_redis.side_effect = ConnectionError("Redis unavailable")
        from redis_client import RedisClient
        client = RedisClient()
        yield client

@pytest.fixture
def flaky_redis_client(mock_redis_server):
    """RedisClient that can be toggled between connected/disconnected."""
    class FlakyClient:
        def __init__(self):
            self.client = None
            self.fake_redis = fakeredis.FakeRedis(server=mock_redis_server)

        def connect(self):
            with patch('redis.Redis', return_value=self.fake_redis):
                from redis_client import RedisClient
                self.client = RedisClient()
                self.client._connected = True

        def disconnect(self):
            self.client._connected = False
            self.client._client = MagicMock()
            self.client._client.ping.side_effect = ConnectionError()

        def reconnect(self):
            self.client._client = self.fake_redis
            self.client._connected = True

    flaky = FlakyClient()
    flaky.connect()
    yield flaky
```

---

## RedisClient Class Tests

### 1. Connection Handling

#### Test: `test_connect_success`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Successful Redis connection on initialization |
| **Setup** | Mock `redis.Redis` to return working client, mock `ping()` to succeed |
| **Expected behavior** | `_connected` is `True`, `_client` is set, info log emitted |
| **Assertions** | `client.is_connected() == True`, `client._client is not None` |

```python
def test_connect_success(mock_redis_server):
    with patch('redis.Redis', fakeredis.FakeRedis):
        client = RedisClient()
        assert client.is_connected() == True
        assert client._client is not None
```

---

#### Test: `test_connect_redis_unavailable`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Graceful handling when Redis is not available |
| **Setup** | Mock `redis.Redis` to raise `ConnectionError` |
| **Expected behavior** | `_connected` is `False`, warning log emitted, no exception raised |
| **Assertions** | `client.is_connected() == False`, `client._connected == False` |

```python
def test_connect_redis_unavailable():
    with patch('redis.Redis') as mock:
        mock.return_value.ping.side_effect = ConnectionError("Connection refused")
        client = RedisClient()
        assert client.is_connected() == False
```

---

#### Test: `test_connect_redis_not_installed`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Graceful handling when redis-py package is not installed |
| **Setup** | Mock `import redis` to raise `ImportError` |
| **Expected behavior** | `_connected` is `False`, warning log suggests `pip install redis` |
| **Assertions** | `client.is_connected() == False` |

```python
def test_connect_redis_not_installed():
    with patch.dict('sys.modules', {'redis': None}):
        # Force reimport
        import importlib
        import redis_client
        importlib.reload(redis_client)
        client = redis_client.RedisClient()
        assert client.is_connected() == False
```

---

#### Test: `test_is_connected_verifies_with_ping`

| Attribute | Value |
|-----------|-------|
| **What it tests** | `is_connected()` actually pings Redis to verify connection |
| **Setup** | Connected client, then make ping fail |
| **Expected behavior** | Returns `False` when ping fails, sets `_connected = False` |
| **Assertions** | First call returns `True`, after breaking ping returns `False` |

```python
def test_is_connected_verifies_with_ping(connected_redis_client):
    assert connected_redis_client.is_connected() == True

    # Break the connection
    connected_redis_client._client.ping = MagicMock(side_effect=ConnectionError())

    assert connected_redis_client.is_connected() == False
    assert connected_redis_client._connected == False
```

---

#### Test: `test_reconnect_success`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Successful reconnection after disconnect |
| **Setup** | Disconnected client, then make Redis available |
| **Expected behavior** | `reconnect()` returns `True`, `is_connected()` returns `True` |
| **Assertions** | `reconnect() == True`, `is_connected() == True` |

```python
def test_reconnect_success(flaky_redis_client):
    flaky_redis_client.disconnect()
    assert flaky_redis_client.client.is_connected() == False

    flaky_redis_client.reconnect()
    result = flaky_redis_client.client.reconnect()

    assert result == True
    assert flaky_redis_client.client.is_connected() == True
```

---

#### Test: `test_reconnect_still_unavailable`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Reconnect attempt when Redis is still down |
| **Setup** | Mock Redis to continue failing |
| **Expected behavior** | `reconnect()` returns `False`, stays disconnected |
| **Assertions** | `reconnect() == False`, `is_connected() == False` |

```python
def test_reconnect_still_unavailable(disconnected_redis_client):
    result = disconnected_redis_client.reconnect()
    assert result == False
    assert disconnected_redis_client.is_connected() == False
```

---

### 2. Yarn Board State

#### Test: `test_get_yarn_state_exists`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Retrieving existing yarn state from Redis |
| **Setup** | Pre-populate Redis with JSON state at correct key |
| **Expected behavior** | Returns parsed dict matching stored data |
| **Assertions** | Returned dict has correct `context_id`, `grabbed_point_ids`, etc. |

```python
def test_get_yarn_state_exists(connected_redis_client):
    state = {
        "context_id": "ctx-123",
        "grabbed_point_ids": ["point-1", "point-2"],
        "priority_overrides": {"point-1": "critical"}
    }
    connected_redis_client._client.set(
        "memory:yarn:state:ctx-123",
        json.dumps(state)
    )

    result = connected_redis_client.get_yarn_state("ctx-123")

    assert result == state
    assert result["context_id"] == "ctx-123"
```

---

#### Test: `test_get_yarn_state_not_found`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Retrieving non-existent yarn state |
| **Setup** | Empty Redis |
| **Expected behavior** | Returns `None` |
| **Assertions** | `result is None` |

```python
def test_get_yarn_state_not_found(connected_redis_client):
    result = connected_redis_client.get_yarn_state("nonexistent")
    assert result is None
```

---

#### Test: `test_get_yarn_state_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Graceful degradation when disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns `None` without throwing |
| **Assertions** | `result is None` |

```python
def test_get_yarn_state_disconnected(disconnected_redis_client):
    result = disconnected_redis_client.get_yarn_state("ctx-123")
    assert result is None
```

---

#### Test: `test_set_yarn_state_success`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Successfully storing yarn state |
| **Setup** | Connected client |
| **Expected behavior** | Returns `True`, data stored with TTL |
| **Assertions** | `result == True`, can retrieve stored data, TTL is set |

```python
def test_set_yarn_state_success(connected_redis_client):
    state = {"context_id": "ctx-123", "grabbed_point_ids": ["p1"]}

    result = connected_redis_client.set_yarn_state("ctx-123", state)

    assert result == True
    stored = connected_redis_client._client.get("memory:yarn:state:ctx-123")
    assert json.loads(stored) == state
    # Verify TTL is set (3600 seconds)
    ttl = connected_redis_client._client.ttl("memory:yarn:state:ctx-123")
    assert ttl > 0 and ttl <= 3600
```

---

#### Test: `test_set_yarn_state_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Graceful degradation when setting state while disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns `False` without throwing |
| **Assertions** | `result == False` |

```python
def test_set_yarn_state_disconnected(disconnected_redis_client):
    result = disconnected_redis_client.set_yarn_state("ctx-123", {"data": "test"})
    assert result == False
```

---

#### Test: `test_set_grabbed_add_point`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Adding a point to grabbed set |
| **Setup** | Connected client, empty grabbed set |
| **Expected behavior** | Point added to Redis set, TTL set |
| **Assertions** | Point in set members, `result == True` |

```python
def test_set_grabbed_add_point(connected_redis_client):
    result = connected_redis_client.set_grabbed("ctx-123", "point-1", True)

    assert result == True
    members = connected_redis_client._client.smembers("memory:yarn:grabbed:ctx-123")
    assert "point-1" in members
```

---

#### Test: `test_set_grabbed_remove_point`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Removing a point from grabbed set |
| **Setup** | Connected client with point already grabbed |
| **Expected behavior** | Point removed from Redis set |
| **Assertions** | Point not in set members after removal |

```python
def test_set_grabbed_remove_point(connected_redis_client):
    connected_redis_client._client.sadd("memory:yarn:grabbed:ctx-123", "point-1")

    result = connected_redis_client.set_grabbed("ctx-123", "point-1", False)

    assert result == True
    members = connected_redis_client._client.smembers("memory:yarn:grabbed:ctx-123")
    assert "point-1" not in members
```

---

#### Test: `test_get_grabbed_points_multiple`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Retrieving multiple grabbed points |
| **Setup** | Connected client with multiple points in set |
| **Expected behavior** | Returns list of all grabbed points |
| **Assertions** | All expected points in returned list |

```python
def test_get_grabbed_points_multiple(connected_redis_client):
    connected_redis_client._client.sadd("memory:yarn:grabbed:ctx-123", "point-1", "point-2", "point-3")

    result = connected_redis_client.get_grabbed_points("ctx-123")

    assert len(result) == 3
    assert set(result) == {"point-1", "point-2", "point-3"}
```

---

#### Test: `test_get_grabbed_points_empty`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Retrieving from context with no grabbed points |
| **Setup** | Connected client, no set exists |
| **Expected behavior** | Returns empty list |
| **Assertions** | `result == []` |

```python
def test_get_grabbed_points_empty(connected_redis_client):
    result = connected_redis_client.get_grabbed_points("ctx-123")
    assert result == []
```

---

#### Test: `test_get_grabbed_points_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Graceful degradation when disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns empty list |
| **Assertions** | `result == []` |

```python
def test_get_grabbed_points_disconnected(disconnected_redis_client):
    result = disconnected_redis_client.get_grabbed_points("ctx-123")
    assert result == []
```

---

### 3. Agent Presence

#### Test: `test_get_agent_status_exists`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Retrieving existing agent status |
| **Setup** | Pre-populate Redis with agent status JSON |
| **Expected behavior** | Returns parsed status dict |
| **Assertions** | `result["agent_id"]`, `result["busy"]` match stored values |

```python
def test_get_agent_status_exists(connected_redis_client):
    status = {
        "agent_id": "AGENT-curator",
        "busy": True,
        "current_task": "validation",
        "last_heartbeat": "2024-01-15T10:30:00"
    }
    connected_redis_client._client.set(
        "memory:agent:status:AGENT-curator",
        json.dumps(status)
    )

    result = connected_redis_client.get_agent_status("AGENT-curator")

    assert result["agent_id"] == "AGENT-curator"
    assert result["busy"] == True
```

---

#### Test: `test_get_agent_status_not_found`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Retrieving status for unknown agent |
| **Setup** | Empty Redis |
| **Expected behavior** | Returns `None` |
| **Assertions** | `result is None` |

```python
def test_get_agent_status_not_found(connected_redis_client):
    result = connected_redis_client.get_agent_status("AGENT-unknown")
    assert result is None
```

---

#### Test: `test_set_agent_busy_with_task`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Marking agent busy with current task |
| **Setup** | Connected client |
| **Expected behavior** | Status stored with busy=True, task set, TTL applied |
| **Assertions** | Stored status has correct values |

```python
def test_set_agent_busy_with_task(connected_redis_client):
    result = connected_redis_client.set_agent_busy(
        "AGENT-curator",
        busy=True,
        current_task="validating memory-123"
    )

    assert result == True
    stored = json.loads(connected_redis_client._client.get("memory:agent:status:AGENT-curator"))
    assert stored["busy"] == True
    assert stored["current_task"] == "validating memory-123"
    assert "last_heartbeat" in stored
```

---

#### Test: `test_set_agent_available`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Marking agent as available |
| **Setup** | Connected client |
| **Expected behavior** | Status stored with busy=False |
| **Assertions** | `stored["busy"] == False` |

```python
def test_set_agent_available(connected_redis_client):
    result = connected_redis_client.set_agent_busy("AGENT-curator", busy=False)

    assert result == True
    stored = json.loads(connected_redis_client._client.get("memory:agent:status:AGENT-curator"))
    assert stored["busy"] == False
```

---

#### Test: `test_heartbeat_updates_timestamp`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Heartbeat updates last_heartbeat and refreshes TTL |
| **Setup** | Connected client with existing agent status |
| **Expected behavior** | last_heartbeat updated, TTL refreshed |
| **Assertions** | New timestamp is more recent than original |

```python
def test_heartbeat_updates_timestamp(connected_redis_client):
    # Set initial status
    connected_redis_client.set_agent_busy("AGENT-curator", busy=True)
    original = json.loads(connected_redis_client._client.get("memory:agent:status:AGENT-curator"))
    original_timestamp = original["last_heartbeat"]

    # Wait a moment and heartbeat
    import time
    time.sleep(0.1)
    result = connected_redis_client.heartbeat("AGENT-curator")

    assert result == True
    updated = json.loads(connected_redis_client._client.get("memory:agent:status:AGENT-curator"))
    assert updated["last_heartbeat"] > original_timestamp
```

---

#### Test: `test_heartbeat_no_existing_status`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Heartbeat for agent with no existing status |
| **Setup** | Connected client, no agent status exists |
| **Expected behavior** | Returns `True` but doesn't create status (nothing to refresh) |
| **Assertions** | `result == True`, no status created |

```python
def test_heartbeat_no_existing_status(connected_redis_client):
    result = connected_redis_client.heartbeat("AGENT-unknown")

    assert result == True
    # Should not create a status entry
    stored = connected_redis_client._client.get("memory:agent:status:AGENT-unknown")
    assert stored is None
```

---

#### Test: `test_agent_status_expires_with_ttl`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Agent status expires after TTL (300 seconds) |
| **Setup** | Connected client, set agent status |
| **Expected behavior** | Key has TTL set to ~300 seconds |
| **Assertions** | `0 < TTL <= 300` |

```python
def test_agent_status_expires_with_ttl(connected_redis_client):
    connected_redis_client.set_agent_busy("AGENT-curator", busy=True)

    ttl = connected_redis_client._client.ttl("memory:agent:status:AGENT-curator")

    assert ttl > 0
    assert ttl <= 300
```

---

### 4. Message Queues

#### Test: `test_queue_for_agent_success`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Successfully queueing a message for an agent |
| **Setup** | Connected client |
| **Expected behavior** | Message added to list, has `queued_at` timestamp |
| **Assertions** | Queue length is 1, message retrievable |

```python
def test_queue_for_agent_success(connected_redis_client):
    message = {"type": "validate", "memory_id": "mem-123"}

    result = connected_redis_client.queue_for_agent("AGENT-curator", message)

    assert result == True
    length = connected_redis_client._client.llen("memory:queue:AGENT-curator")
    assert length == 1
```

---

#### Test: `test_queue_for_agent_adds_timestamp`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Automatic `queued_at` timestamp added if missing |
| **Setup** | Connected client, message without timestamp |
| **Expected behavior** | Stored message has `queued_at` field |
| **Assertions** | `queued_at` present in stored message |

```python
def test_queue_for_agent_adds_timestamp(connected_redis_client):
    message = {"type": "validate"}  # No queued_at

    connected_redis_client.queue_for_agent("AGENT-curator", message)

    stored = json.loads(connected_redis_client._client.lindex("memory:queue:AGENT-curator", 0))
    assert "queued_at" in stored
```

---

#### Test: `test_queue_preserves_existing_timestamp`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Existing `queued_at` not overwritten |
| **Setup** | Connected client, message with existing timestamp |
| **Expected behavior** | Original timestamp preserved |
| **Assertions** | `queued_at` equals original value |

```python
def test_queue_preserves_existing_timestamp(connected_redis_client):
    original_time = "2024-01-01T00:00:00"
    message = {"type": "validate", "queued_at": original_time}

    connected_redis_client.queue_for_agent("AGENT-curator", message)

    stored = json.loads(connected_redis_client._client.lindex("memory:queue:AGENT-curator", 0))
    assert stored["queued_at"] == original_time
```

---

#### Test: `test_queue_fifo_order`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Messages are queued in FIFO order (RPUSH) |
| **Setup** | Connected client, queue multiple messages |
| **Expected behavior** | First message in is first message out |
| **Assertions** | Order matches insertion order |

```python
def test_queue_fifo_order(connected_redis_client):
    connected_redis_client.queue_for_agent("AGENT-curator", {"order": 1})
    connected_redis_client.queue_for_agent("AGENT-curator", {"order": 2})
    connected_redis_client.queue_for_agent("AGENT-curator", {"order": 3})

    messages = connected_redis_client.get_agent_queue("AGENT-curator")

    assert messages[0]["order"] == 1
    assert messages[1]["order"] == 2
    assert messages[2]["order"] == 3
```

---

#### Test: `test_get_agent_queue_with_limit`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Queue retrieval respects limit parameter |
| **Setup** | Connected client, queue 10 messages |
| **Expected behavior** | Only returns up to limit messages |
| **Assertions** | `len(result) == limit` |

```python
def test_get_agent_queue_with_limit(connected_redis_client):
    for i in range(10):
        connected_redis_client.queue_for_agent("AGENT-curator", {"order": i})

    result = connected_redis_client.get_agent_queue("AGENT-curator", limit=5)

    assert len(result) == 5
    assert result[0]["order"] == 0  # Still FIFO
```

---

#### Test: `test_get_agent_queue_is_peek`

| Attribute | Value |
|-----------|-------|
| **What it tests** | `get_agent_queue` doesn't remove messages (peek only) |
| **Setup** | Connected client, queue messages |
| **Expected behavior** | Messages still exist after retrieval |
| **Assertions** | Length unchanged after get |

```python
def test_get_agent_queue_is_peek(connected_redis_client):
    connected_redis_client.queue_for_agent("AGENT-curator", {"test": "data"})

    connected_redis_client.get_agent_queue("AGENT-curator")
    connected_redis_client.get_agent_queue("AGENT-curator")

    length = connected_redis_client.get_queue_length("AGENT-curator")
    assert length == 1  # Still there
```

---

#### Test: `test_pop_agent_queue_removes_message`

| Attribute | Value |
|-----------|-------|
| **What it tests** | `pop_agent_queue` removes and returns oldest message |
| **Setup** | Connected client, queue multiple messages |
| **Expected behavior** | Returns first message, queue length decreases |
| **Assertions** | Returned message is first, length reduced by 1 |

```python
def test_pop_agent_queue_removes_message(connected_redis_client):
    connected_redis_client.queue_for_agent("AGENT-curator", {"order": 1})
    connected_redis_client.queue_for_agent("AGENT-curator", {"order": 2})

    result = connected_redis_client.pop_agent_queue("AGENT-curator")

    assert result["order"] == 1
    length = connected_redis_client.get_queue_length("AGENT-curator")
    assert length == 1
```

---

#### Test: `test_pop_agent_queue_empty`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Popping from empty queue |
| **Setup** | Connected client, empty queue |
| **Expected behavior** | Returns `None` |
| **Assertions** | `result is None` |

```python
def test_pop_agent_queue_empty(connected_redis_client):
    result = connected_redis_client.pop_agent_queue("AGENT-curator")
    assert result is None
```

---

#### Test: `test_clear_agent_queue`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Clearing all messages from agent queue |
| **Setup** | Connected client, queue with messages |
| **Expected behavior** | Queue empty after clear |
| **Assertions** | `result == True`, `get_queue_length() == 0` |

```python
def test_clear_agent_queue(connected_redis_client):
    connected_redis_client.queue_for_agent("AGENT-curator", {"test": 1})
    connected_redis_client.queue_for_agent("AGENT-curator", {"test": 2})

    result = connected_redis_client.clear_agent_queue("AGENT-curator")

    assert result == True
    assert connected_redis_client.get_queue_length("AGENT-curator") == 0
```

---

#### Test: `test_get_queue_length`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Accurate queue length reporting |
| **Setup** | Connected client, queue specific number of messages |
| **Expected behavior** | Returns correct count |
| **Assertions** | `length == expected_count` |

```python
def test_get_queue_length(connected_redis_client):
    for i in range(7):
        connected_redis_client.queue_for_agent("AGENT-curator", {"msg": i})

    length = connected_redis_client.get_queue_length("AGENT-curator")

    assert length == 7
```

---

#### Test: `test_get_queue_length_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Queue length returns 0 when disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns 0 |
| **Assertions** | `length == 0` |

```python
def test_get_queue_length_disconnected(disconnected_redis_client):
    length = disconnected_redis_client.get_queue_length("AGENT-curator")
    assert length == 0
```

---

### 5. Pub/Sub

#### Test: `test_notify_priority_change_publishes`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Priority change publishes to correct channel |
| **Setup** | Connected client, subscribe to channel first |
| **Expected behavior** | Message published with correct structure |
| **Assertions** | Message received on channel, contains expected fields |

```python
def test_notify_priority_change_publishes(connected_redis_client):
    # Subscribe first
    pubsub = connected_redis_client._client.pubsub()
    pubsub.subscribe("memory:pubsub:priority:ctx-123")
    pubsub.get_message()  # Consume subscription confirmation

    result = connected_redis_client.notify_priority_change(
        context_id="ctx-123",
        point_id="point-456",
        new_priority="critical"
    )

    assert result == True
    message = pubsub.get_message()
    if message:
        data = json.loads(message["data"])
        assert data["type"] == "priority_change"
        assert data["point_id"] == "point-456"
        assert data["new_priority"] == "critical"
```

---

#### Test: `test_notify_priority_change_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Priority notification fails gracefully when disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns `False` |
| **Assertions** | `result == False` |

```python
def test_notify_priority_change_disconnected(disconnected_redis_client):
    result = disconnected_redis_client.notify_priority_change("ctx", "point", "critical")
    assert result == False
```

---

#### Test: `test_subscribe_to_context`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Successfully subscribing to context updates |
| **Setup** | Connected client |
| **Expected behavior** | Pubsub created, pattern subscription registered |
| **Assertions** | `result == True`, `_pubsub is not None` |

```python
def test_subscribe_to_context(connected_redis_client):
    callback = MagicMock()

    result = connected_redis_client.subscribe_to_context("ctx-123", callback)

    assert result == True
    assert connected_redis_client._pubsub is not None
```

---

#### Test: `test_subscribe_to_context_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Subscription fails gracefully when disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns `False` |
| **Assertions** | `result == False` |

```python
def test_subscribe_to_context_disconnected(disconnected_redis_client):
    result = disconnected_redis_client.subscribe_to_context("ctx", lambda x: x)
    assert result == False
```

---

#### Test: `test_unsubscribe_from_context`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Successfully unsubscribing from context |
| **Setup** | Connected client with active subscription |
| **Expected behavior** | Pattern unsubscribed |
| **Assertions** | `result == True` |

```python
def test_unsubscribe_from_context(connected_redis_client):
    connected_redis_client.subscribe_to_context("ctx-123", lambda x: x)

    result = connected_redis_client.unsubscribe_from_context("ctx-123")

    assert result == True
```

---

#### Test: `test_unsubscribe_no_pubsub`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Unsubscribe when no pubsub exists |
| **Setup** | Connected client, never subscribed |
| **Expected behavior** | Returns `False` gracefully |
| **Assertions** | `result == False` |

```python
def test_unsubscribe_no_pubsub(connected_redis_client):
    result = connected_redis_client.unsubscribe_from_context("ctx-123")
    assert result == False
```

---

### 6. Health Check

#### Test: `test_health_check_connected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Health check returns full status when connected |
| **Setup** | Connected client |
| **Expected behavior** | Returns dict with connected=True, memory info, status="healthy" |
| **Assertions** | All expected fields present and correct |

```python
def test_health_check_connected(connected_redis_client):
    result = connected_redis_client.health_check()

    assert result["connected"] == True
    assert result["status"] == "healthy"
    assert "host" in result
    assert "port" in result
    assert "used_memory" in result
```

---

#### Test: `test_health_check_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Health check returns degraded status when disconnected |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns dict with connected=False, status="disconnected" |
| **Assertions** | `result["connected"] == False`, `result["status"] == "disconnected"` |

```python
def test_health_check_disconnected(disconnected_redis_client):
    result = disconnected_redis_client.health_check()

    assert result["connected"] == False
    assert result["status"] == "disconnected"
    assert "host" in result
    assert "port" in result
```

---

#### Test: `test_health_check_degraded`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Health check handles partial failures |
| **Setup** | Connected client, mock info() to fail |
| **Expected behavior** | Returns connected=True but status="degraded" |
| **Assertions** | `result["status"].startswith("degraded")` |

```python
def test_health_check_degraded(connected_redis_client):
    connected_redis_client._client.info = MagicMock(side_effect=Exception("info failed"))

    result = connected_redis_client.health_check()

    assert result["connected"] == True  # ping still works
    assert "degraded" in result["status"]
```

---

## Graceful Degradation Tests

These tests verify the system behaves correctly when Redis is unavailable or becomes unavailable.

### Test: `test_all_methods_return_defaults_when_disconnected`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Every method returns sensible default when Redis unavailable |
| **Setup** | Disconnected client |
| **Expected behavior** | No exceptions, appropriate defaults returned |
| **Assertions** | See table below |

| Method | Expected Default |
|--------|-----------------|
| `get_yarn_state()` | `None` |
| `set_yarn_state()` | `False` |
| `set_grabbed()` | `False` |
| `get_grabbed_points()` | `[]` |
| `get_agent_status()` | `None` |
| `set_agent_busy()` | `False` |
| `heartbeat()` | `False` |
| `queue_for_agent()` | `False` |
| `get_agent_queue()` | `[]` |
| `pop_agent_queue()` | `None` |
| `clear_agent_queue()` | `False` |
| `get_queue_length()` | `0` |
| `notify_priority_change()` | `False` |
| `subscribe_to_context()` | `False` |
| `unsubscribe_from_context()` | `False` |

```python
def test_all_methods_return_defaults_when_disconnected(disconnected_redis_client):
    client = disconnected_redis_client

    assert client.get_yarn_state("ctx") is None
    assert client.set_yarn_state("ctx", {}) == False
    assert client.set_grabbed("ctx", "point", True) == False
    assert client.get_grabbed_points("ctx") == []
    assert client.get_agent_status("agent") is None
    assert client.set_agent_busy("agent", True) == False
    assert client.heartbeat("agent") == False
    assert client.queue_for_agent("agent", {}) == False
    assert client.get_agent_queue("agent") == []
    assert client.pop_agent_queue("agent") is None
    assert client.clear_agent_queue("agent") == False
    assert client.get_queue_length("agent") == 0
    assert client.notify_priority_change("ctx", "point", "high") == False
    assert client.subscribe_to_context("ctx", lambda x: x) == False
    assert client.unsubscribe_from_context("ctx") == False
```

---

### Test: `test_redis_disconnects_mid_operation`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Operations handle Redis disconnecting mid-stream |
| **Setup** | Connected client, disconnect during operation |
| **Expected behavior** | Returns graceful default, logs error, updates _connected |
| **Assertions** | Default returned, no exception, `is_connected() == False` |

```python
def test_redis_disconnects_mid_operation(flaky_redis_client):
    client = flaky_redis_client.client

    # Start connected
    assert client.set_yarn_state("ctx", {"test": 1}) == True

    # Disconnect during next operation
    flaky_redis_client.disconnect()

    # Should fail gracefully
    result = client.get_yarn_state("ctx")
    assert result is None
    assert client.is_connected() == False
```

---

### Test: `test_redis_reconnects_after_failure`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Operations work again after reconnection |
| **Setup** | Disconnect then reconnect |
| **Expected behavior** | Operations succeed after reconnect() |
| **Assertions** | Operations return success values |

```python
def test_redis_reconnects_after_failure(flaky_redis_client):
    client = flaky_redis_client.client

    # Disconnect
    flaky_redis_client.disconnect()
    assert client.is_connected() == False

    # Reconnect
    flaky_redis_client.reconnect()
    client.reconnect()

    # Should work again
    assert client.is_connected() == True
    assert client.set_yarn_state("ctx", {"test": 1}) == True
```

---

### Test: `test_data_persists_across_reconnect`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Data written before disconnect is available after reconnect |
| **Setup** | Write data, disconnect, reconnect, read data |
| **Expected behavior** | Data still present after reconnection |
| **Assertions** | Retrieved data matches original |

```python
def test_data_persists_across_reconnect(flaky_redis_client):
    client = flaky_redis_client.client

    # Write data
    client.queue_for_agent("AGENT-curator", {"important": "data"})

    # Disconnect and reconnect
    flaky_redis_client.disconnect()
    flaky_redis_client.reconnect()
    client.reconnect()

    # Data should still be there
    messages = client.get_agent_queue("AGENT-curator")
    assert len(messages) == 1
    assert messages[0]["important"] == "data"
```

---

### Test: `test_concurrent_operations_during_disconnect`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Multiple operations fail gracefully during disconnect |
| **Setup** | Disconnected client, attempt multiple operations |
| **Expected behavior** | All return defaults, no exceptions |
| **Assertions** | All operations return gracefully |

```python
def test_concurrent_operations_during_disconnect(disconnected_redis_client):
    client = disconnected_redis_client

    # All should fail gracefully
    results = [
        client.set_yarn_state("ctx-1", {}),
        client.set_yarn_state("ctx-2", {}),
        client.queue_for_agent("agent-1", {}),
        client.queue_for_agent("agent-2", {}),
        client.set_agent_busy("agent-1", True),
    ]

    assert all(r == False for r in results)
```

---

## RedisInterfaceAdapter Tests

### Test: `test_adapter_get_yarn_state_returns_dataclass`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Adapter converts dict to YarnBoardState dataclass |
| **Setup** | Connected client with yarn state stored |
| **Expected behavior** | Returns `YarnBoardState` instance, not dict |
| **Assertions** | `isinstance(result, YarnBoardState)` |

```python
def test_adapter_get_yarn_state_returns_dataclass(connected_redis_client):
    from redis_client import RedisInterfaceAdapter
    from datashapes import YarnBoardState

    # Store state
    state_dict = {
        "context_id": "ctx-123",
        "grabbed_point_ids": ["p1", "p2"],
        "priority_overrides": {},
        "hot_refs": [],
        "last_interaction": "2024-01-15T10:00:00",
        "interaction_count": 5
    }
    connected_redis_client.set_yarn_state("ctx-123", state_dict)

    adapter = RedisInterfaceAdapter(connected_redis_client)
    result = adapter.get_yarn_state("ctx-123")

    assert isinstance(result, YarnBoardState)
    assert result.context_id == "ctx-123"
    assert result.grabbed_point_ids == ["p1", "p2"]
```

---

### Test: `test_adapter_get_yarn_state_returns_none`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Adapter returns None when no state exists |
| **Setup** | Connected client, no state stored |
| **Expected behavior** | Returns `None` |
| **Assertions** | `result is None` |

```python
def test_adapter_get_yarn_state_returns_none(connected_redis_client):
    from redis_client import RedisInterfaceAdapter

    adapter = RedisInterfaceAdapter(connected_redis_client)
    result = adapter.get_yarn_state("nonexistent")

    assert result is None
```

---

### Test: `test_adapter_set_yarn_state_from_dataclass`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Adapter correctly serializes YarnBoardState to Redis |
| **Setup** | Connected client |
| **Expected behavior** | Dataclass fields correctly stored |
| **Assertions** | Stored JSON contains all expected fields |

```python
def test_adapter_set_yarn_state_from_dataclass(connected_redis_client):
    from redis_client import RedisInterfaceAdapter
    from datashapes import YarnBoardState
    from datetime import datetime

    adapter = RedisInterfaceAdapter(connected_redis_client)
    state = YarnBoardState(
        context_id="ctx-123",
        grabbed_point_ids=["p1"],
        priority_overrides={"p1": "critical"},
        hot_refs=["ref-1"],
        last_interaction=datetime(2024, 1, 15, 10, 0, 0),
        interaction_count=3
    )

    result = adapter.set_yarn_state(state)

    assert result == True
    stored = json.loads(connected_redis_client._client.get("memory:yarn:state:ctx-123"))
    assert stored["context_id"] == "ctx-123"
    assert stored["grabbed_point_ids"] == ["p1"]
    assert stored["interaction_count"] == 3
```

---

### Test: `test_adapter_matches_redis_interface_signature`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Adapter has all methods defined in RedisInterface |
| **Setup** | Import both classes |
| **Expected behavior** | All interface methods exist on adapter |
| **Assertions** | All method names present |

```python
def test_adapter_matches_redis_interface_signature():
    from redis_client import RedisInterfaceAdapter
    from datashapes import RedisInterface

    interface_methods = [
        "get_yarn_state",
        "set_yarn_state",
        "set_grabbed",
        "get_agent_status",
        "set_agent_busy",
        "queue_for_agent",
        "get_agent_queue",
        "clear_agent_queue",
        "notify_priority_change",
        "subscribe_to_context",
        "unsubscribe_from_context",
    ]

    for method in interface_methods:
        assert hasattr(RedisInterfaceAdapter, method), f"Missing method: {method}"
```

---

### Test: `test_initialize_redis_replaces_stub`

| Attribute | Value |
|-----------|-------|
| **What it tests** | `initialize_redis()` replaces datashapes.redis_interface |
| **Setup** | Import datashapes, call initialize_redis |
| **Expected behavior** | datashapes.redis_interface is now RedisInterfaceAdapter |
| **Assertions** | `isinstance(datashapes.redis_interface, RedisInterfaceAdapter)` |

```python
def test_initialize_redis_replaces_stub(connected_redis_client, monkeypatch):
    import datashapes
    from redis_client import initialize_redis, RedisInterfaceAdapter

    # Mock get_redis_client to return our connected client
    monkeypatch.setattr('redis_client.get_redis_client', lambda: connected_redis_client)

    result = initialize_redis()

    assert result == True
    assert isinstance(datashapes.redis_interface, RedisInterfaceAdapter)
```

---

### Test: `test_initialize_redis_keeps_stub_when_unavailable`

| Attribute | Value |
|-----------|-------|
| **What it tests** | `initialize_redis()` leaves stub when Redis unavailable |
| **Setup** | Disconnected client |
| **Expected behavior** | Returns False, stub unchanged |
| **Assertions** | `result == False`, stub still in place |

```python
def test_initialize_redis_keeps_stub_when_unavailable(disconnected_redis_client, monkeypatch):
    import datashapes
    from redis_client import initialize_redis
    from datashapes import RedisInterface

    original_stub = datashapes.redis_interface
    monkeypatch.setattr('redis_client.get_redis_client', lambda: disconnected_redis_client)

    result = initialize_redis()

    assert result == False
    # Stub should still be the original (or same type)
    assert isinstance(datashapes.redis_interface, RedisInterface)
```

---

## Integration Tests

These tests require a real Redis instance (use `docker run -p 6379:6379 redis:alpine` for local testing).

### Test: `test_integration_full_workflow`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Complete workflow with real Redis |
| **Setup** | Real Redis container |
| **Expected behavior** | All operations work end-to-end |
| **Assertions** | Full round-trip data integrity |

```python
@pytest.mark.integration
def test_integration_full_workflow():
    """Requires running Redis instance."""
    from redis_client import RedisClient

    client = RedisClient()
    if not client.is_connected():
        pytest.skip("Redis not available for integration test")

    # Clean slate
    client._client.flushdb()

    # Full workflow
    # 1. Set agent status
    assert client.set_agent_busy("AGENT-curator", True, "testing") == True

    # 2. Queue message
    assert client.queue_for_agent("AGENT-curator", {"type": "test"}) == True

    # 3. Check queue
    messages = client.get_agent_queue("AGENT-curator")
    assert len(messages) == 1

    # 4. Pop message
    msg = client.pop_agent_queue("AGENT-curator")
    assert msg["type"] == "test"

    # 5. Set yarn state
    assert client.set_yarn_state("ctx-test", {"points": ["p1"]}) == True

    # 6. Get yarn state
    state = client.get_yarn_state("ctx-test")
    assert state["points"] == ["p1"]

    # 7. Health check
    health = client.health_check()
    assert health["status"] == "healthy"
```

---

### Test: `test_integration_pubsub_notification`

| Attribute | Value |
|-----------|-------|
| **What it tests** | Pub/sub messaging with real Redis |
| **Setup** | Real Redis container |
| **Expected behavior** | Published messages received by subscriber |
| **Assertions** | Callback receives message |

```python
@pytest.mark.integration
def test_integration_pubsub_notification():
    """Requires running Redis instance."""
    from redis_client import RedisClient
    import time

    client = RedisClient()
    if not client.is_connected():
        pytest.skip("Redis not available for integration test")

    received = []

    def callback(message):
        received.append(message)

    # Subscribe
    client.subscribe_to_context("ctx-pubsub-test", callback)

    # Give subscription time to register
    time.sleep(0.1)

    # Publish
    client.notify_priority_change("ctx-pubsub-test", "point-1", "critical")

    # Allow message propagation
    time.sleep(0.1)

    # Check pubsub (need to get messages)
    client._pubsub.get_message()  # May need multiple calls

    # Cleanup
    client.unsubscribe_from_context("ctx-pubsub-test")
```

---

## Test Markers and Configuration

### pytest.ini Configuration

```ini
[pytest]
markers =
    integration: marks tests as integration tests requiring real Redis
    slow: marks tests as slow running

testpaths = tests
python_files = test_*.py
python_functions = test_*
```

### Running Tests

```bash
# Run all unit tests (mocked)
pytest tests/test_redis_client.py -v

# Run integration tests (requires Redis)
pytest tests/test_redis_client.py -v -m integration

# Run with coverage
pytest tests/test_redis_client.py --cov=redis_client --cov-report=html

# Skip integration tests
pytest tests/test_redis_client.py -v -m "not integration"
```

---

## Test File Structure

```
tests/
  __init__.py
  conftest.py                    # Shared fixtures
  test_redis_client.py           # Main test file
  test_redis_integration.py      # Integration tests (separate file)
```

---

## Coverage Goals

| Category | Target Coverage |
|----------|----------------|
| Connection handling | 100% |
| Yarn board state | 100% |
| Agent presence | 100% |
| Message queues | 100% |
| Pub/sub | 90% (callback testing is complex) |
| Health check | 100% |
| Graceful degradation | 100% |
| Adapter | 100% |
| Overall | >= 95% |

---

## Notes for Implementation

1. **fakeredis vs real Redis**: Use `fakeredis` for unit tests, real Redis for integration tests. fakeredis doesn't fully support pub/sub, so those tests may need real Redis.

2. **Thread safety**: The current implementation is not thread-safe. Consider adding tests for concurrent access if threading is introduced.

3. **TTL testing**: Use fakeredis's time simulation or `freezegun` to test TTL expiration without waiting.

4. **Logging verification**: Consider using `pytest-caplog` to verify appropriate log messages are emitted.

5. **Environment variables**: Use `monkeypatch` to test different Redis configurations without modifying real environment.
