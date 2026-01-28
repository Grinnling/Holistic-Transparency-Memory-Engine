# Phase 5 Consolidated Test Requirements

**Created:** 2026-01-12
**Total Estimated Tests:** ~170
**Scope:** Yarn Board, Queue Routing, Clustering, Validation Prompts, Redis Integration

## Source Documents (Full Detail)

This is a **test index/checklist**. For full implementation details (code examples, request/response structures, detailed assertions), reference the original documents:

| Source Document | Location | Coverage |
|-----------------|----------|----------|
| API Tests | `TEST_REQUIREMENTS_PHASE5_API.md` | Yarn board endpoints, Redis health, WebSocket broadcasts |
| Orchestrator Tests | `tests/TEST_REQUIREMENTS_PHASE5_ORCHESTRATOR.md` | Yarn ops, queue routing, clustering, validation prompts |
| Integration Flows | `PHASE5_INTEGRATION_TEST_REQUIREMENTS.md` | End-to-end flows, Redis failover scenarios |
| Redis Client | `tests/test_redis_client_requirements.md` | Connection, queues, pub/sub, graceful degradation |

---

## Table of Contents

1. [Test Infrastructure](#1-test-infrastructure)
2. [Yarn Board Operations](#2-yarn-board-operations)
3. [Queue Routing](#3-queue-routing)
4. [Clustering](#4-clustering)
5. [Validation Prompts](#5-validation-prompts)
6. [Redis Client](#6-redis-client)
7. [Integration Flows](#7-integration-flows)
8. [Critical Path Tests](#8-critical-path-tests)

---

## 1. Test Infrastructure

### Dependencies

```python
# requirements-test.txt
pytest>=7.0.0
pytest-asyncio>=0.21.0
fakeredis>=2.20.0
pytest-mock>=3.10.0
freezegun>=1.2.0
httpx>=0.24.0  # For FastAPI TestClient
```

### Key Constants

```python
CLUSTERING_THRESHOLD = 3
VALIDATION_CONFIDENCE_THRESHOLD = 0.7
STALENESS_DAYS = 3
CURATOR_AGENT_ID = "AGENT-curator"
```

### Core Fixtures

```python
@pytest.fixture
def fresh_orchestrator():
    """Reset and return a fresh orchestrator instance."""
    from conversation_orchestrator import ConversationOrchestrator, reset_orchestrator
    reset_orchestrator()
    return ConversationOrchestrator(auto_load=False)

@pytest.fixture
def context_pair(fresh_orchestrator):
    """Two contexts for cross-ref testing."""
    orch = fresh_orchestrator
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")
    return orch, ctx_a, ctx_b

@pytest.fixture
def connected_redis_client():
    """RedisClient with working fakeredis backend."""
    with patch('redis.Redis', fakeredis.FakeRedis):
        from redis_client import RedisClient
        client = RedisClient()
        client._connected = True
        yield client

@pytest.fixture
def disconnected_redis_client():
    """RedisClient in disconnected/stub mode."""
    from redis_client import RedisClient
    client = RedisClient()
    client._connected = False
    yield client

@pytest.fixture
def mock_redis():
    """Mock redis_interface for orchestrator tests."""
    with patch('datashapes.redis_interface') as mock:
        mock.get_yarn_state.return_value = None
        mock.set_grabbed.return_value = False
        mock.queue_for_agent.return_value = False
        mock.get_agent_queue.return_value = []
        yield mock
```

### File Organization

```
tests/
  conftest.py                              # Shared fixtures
  test_phase5_yarn_board.py               # Yarn board unit tests
  test_phase5_queue_routing.py            # Queue routing tests
  test_phase5_clustering.py               # Clustering tests
  test_phase5_validation_prompts.py       # Validation prompt tests
  test_redis_client.py                    # Redis client unit tests
  integration/
    test_phase5_flows.py                  # End-to-end flow tests
    test_redis_integration.py             # Real Redis tests
```

---

## 2. Yarn Board Operations

> **Full details:** `tests/TEST_REQUIREMENTS_PHASE5_ORCHESTRATOR.md` Section 1, `TEST_REQUIREMENTS_PHASE5_API.md` Section 1

### 2.1 Layout Management (~15 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_get_yarn_layout_existing` | Happy | Returns stored layout |
| `test_get_yarn_layout_default` | Happy | Returns default when none exists |
| `test_get_yarn_layout_invalid_context` | Error | Returns error for missing context |
| `test_save_yarn_layout_full` | Happy | Saves all layout fields |
| `test_save_yarn_layout_partial` | Happy | Partial update preserves other fields |
| `test_save_yarn_layout_initializes_empty` | Edge | Creates layout if none exists |
| `test_save_yarn_layout_updates_timestamp` | Happy | last_modified updated on save |
| `test_update_point_position_new` | Happy | Adds new point position |
| `test_update_point_position_existing` | Happy | Updates existing position |
| `test_update_point_position_collapsed` | Edge | Collapsed state saved |
| `test_update_point_position_invalid_context` | Error | Error for missing context |
| `test_layout_persistence` | Integration | Layout persists to storage |

### 2.2 Hot State (Redis-backed) (~10 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_get_yarn_state_redis` | Happy | Returns state from Redis |
| `test_get_yarn_state_fallback` | Edge | Returns default when Redis unavailable |
| `test_get_yarn_state_source_indicator` | Happy | Response shows "redis" or "default" |
| `test_set_grabbed_redis` | Happy | Persists to Redis |
| `test_set_grabbed_degradation` | Edge | Success but persisted=false |
| `test_release_grabbed` | Happy | Removes from grabbed set |
| `test_get_grabbed_points_multiple` | Happy | Returns all grabbed points |
| `test_get_grabbed_points_empty` | Edge | Empty list for no grabs |

### 2.3 Render (~12 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_render_basic_structure` | Happy | Returns points, connections, cushion |
| `test_render_with_children` | Happy | Parent-child connections rendered |
| `test_render_with_cross_refs` | Happy | Cross-ref midpoints rendered |
| `test_render_positioned_in_points` | Edge | Points with x/y in points array |
| `test_render_unpositioned_in_cushion` | Edge | Points without x/y in cushion |
| `test_render_highlights` | Happy | Highlights passed through |
| `test_render_bidirectional_dedup` | Edge | Bidirectional refs not duplicated |
| `test_render_point_id_format` | Happy | IDs follow context:/crossref: convention |
| `test_render_connections_structure` | Happy | Connections have from_id, to_id, ref_type |
| `test_render_type_colors` | Happy | Type colors included in response |
| `test_render_large_board` | Perf | Handles 50+ points |

### 2.4 API Endpoints (~10 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_api_get_yarn_board_success` | Happy | GET /sidebars/{id}/yarn-board |
| `test_api_put_yarn_board_success` | Happy | PUT /sidebars/{id}/yarn-board |
| `test_api_get_yarn_state` | Happy | GET /sidebars/{id}/yarn-board/state |
| `test_api_grab_point` | Happy | POST /sidebars/{id}/yarn-board/points/{id}/grab |
| `test_api_release_point` | Happy | POST with grabbed=false |
| `test_api_render_yarn_board` | Happy | POST /sidebars/{id}/yarn-board/render |
| `test_api_render_with_highlights` | Happy | Render with highlights param |
| `test_api_websocket_broadcast_layout` | Integration | Layout update broadcasts |
| `test_api_websocket_broadcast_grab` | Integration | Grab action broadcasts |

---

## 3. Queue Routing

> **Full details:** `tests/TEST_REQUIREMENTS_PHASE5_ORCHESTRATOR.md` Section 2, `TEST_REQUIREMENTS_PHASE5_API.md` Section 3

### 3.1 route_scratchpad_entry (~10 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_route_quick_note_no_route` | Happy | quick_note without route stored only |
| `test_route_quick_note_explicit` | Happy | quick_note with route goes to curator |
| `test_route_finding` | Happy | Findings route through curator |
| `test_route_question` | Happy | Questions route through curator |
| `test_route_with_explicit_destination` | Happy | explicit_route_to respected |
| `test_route_redis_available` | Integration | queued_to_redis=True |
| `test_route_graceful_degradation` | Edge | Success with queued_to_redis=False |

### 3.2 curator_approve_entry (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_curator_approve_routes` | Happy | Approved entry routes to destination |
| `test_curator_reject` | Happy | Rejected entry not routed |
| `test_curator_approve_with_redis` | Integration | Delivery queued to Redis |
| `test_curator_infers_destination` | Happy | Uses content-based inference |

### 3.3 _infer_destination (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_infer_debugging_keywords` | Happy | bug/debug -> debugger |
| `test_infer_research_keywords` | Happy | research/investigate -> researcher |
| `test_infer_security_keywords` | Happy | security/auth -> architect |
| `test_infer_no_match_operator` | Edge | Unknown -> operator |
| `test_infer_empty_content` | Edge | None/empty -> operator |

### 3.4 Agent Registry (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_register_new_agent` | Happy | Agent added to registry |
| `test_register_update_existing` | Happy | Specialties updated |
| `test_list_agents_defaults` | Happy | Default agents present |
| `test_list_agents_structure` | Happy | Required fields present |
| `test_get_agent_queue_messages` | Happy | Returns queued messages |
| `test_get_agent_queue_empty` | Edge | Empty queue returns [] |

### 3.5 Queue API Endpoints (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_api_queue_route` | Happy | POST /queue/route |
| `test_api_queue_approve` | Happy | POST /queue/approve |
| `test_api_get_agent_queue` | Happy | GET /queue/{agent_id} |
| `test_api_get_queue_length` | Happy | GET /queue/{agent_id}/length |
| `test_api_pop_agent_queue` | Happy | POST /queue/{agent_id}/pop |
| `test_api_clear_agent_queue` | Happy | DELETE /queue/{agent_id} |
| `test_api_get_all_agent_status` | Happy | GET /queue/agents/status |
| `test_api_queue_redis_unavailable` | Edge | Graceful degradation |

---

## 4. Clustering

> **Full details:** `tests/TEST_REQUIREMENTS_PHASE5_ORCHESTRATOR.md` Section 3

### 4.1 Threshold Behavior (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_clustering_threshold_value` | Const | CLUSTERING_THRESHOLD == 3 |
| `test_first_source_no_flag` | Happy | 1 source: cluster_flagged=False |
| `test_second_source_no_flag` | Happy | 2 sources: cluster_flagged=False |
| `test_third_source_triggers` | Critical | 3 sources: cluster_flagged=True, newly_flagged=True |
| `test_fourth_source_stays_flagged` | Edge | 4+ sources: flagged, newly_flagged=False |
| `test_same_source_no_duplicate` | Edge | Duplicate source not added |
| `test_default_suggested_by` | Edge | Defaults to source_context_id |

### 4.2 suggested_sources Timestamps (~4 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_source_has_timestamp` | Happy | Source includes suggested_at |
| `test_source_timestamp_format` | Happy | ISO format timestamp |
| `test_multiple_sources_unique_timestamps` | Edge | Each source has own timestamp |
| `test_source_order_preserved` | Edge | Sources in chronological order |

### 4.3 get_cluster_flagged_refs (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_returns_flagged_refs` | Happy | Returns cluster_flagged=True refs |
| `test_excludes_validated_default` | Happy | Validated excluded by default |
| `test_includes_validated_when_requested` | Happy | include_validated=True works |
| `test_specific_context_filter` | Happy | context_id filter works |
| `test_sorted_by_count` | Edge | Descending source_count order |
| `test_empty_when_none_flagged` | Edge | Returns empty when no flagged |

---

## 5. Validation Prompts

> **Full details:** `tests/TEST_REQUIREMENTS_PHASE5_ORCHESTRATOR.md` Section 4

### 5.1 Routing Logic (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_citing_refs_inline` | Critical | Cited refs in inline_prompts |
| `test_not_citing_scratchpad` | Critical | Non-cited refs in scratchpad_prompts |
| `test_exchange_created_urgency` | Happy | +50 for current exchange refs |
| `test_excludes_validated` | Happy | Validated refs not in prompts |
| `test_sorted_by_urgency` | Edge | Highest urgency first |

### 5.2 Urgency Scoring (~10 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_urgency_actively_citing` | Happy | +100 for cited refs |
| `test_urgency_current_exchange` | Happy | +50 for exchange-created |
| `test_urgency_cluster_flagged` | Happy | +30 for clustered |
| `test_urgency_urgent_priority` | Happy | +25 for urgent priority |
| `test_urgency_low_confidence` | Happy | +20 for confidence < 0.7 |
| `test_urgency_stale` | Happy | +15 for 3+ days old |
| `test_urgency_combined` | Integration | Multiple signals combine |
| `test_urgency_reasons_list` | Happy | All signals in reasons list |

### 5.3 detect_contradictions (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_implements_vs_contradicts` | Happy | Detects contradiction |
| `test_depends_vs_blocks` | Happy | Detects contradiction |
| `test_derived_vs_contradicts` | Happy | Detects contradiction |
| `test_no_contradictions` | Edge | Empty list when none |
| `test_specific_context` | Happy | Context filter works |

### 5.4 check_chain_stability (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_stable_chain` | Happy | All deps validated -> stable |
| `test_unstable_dependency` | Happy | Unvalidated dep -> unstable |
| `test_derived_from_unstable` | Happy | derived_from checked |
| `test_implements_unstable` | Happy | implements checked |
| `test_ignores_non_dependency` | Edge | cites not a dependency type |
| `test_stability_score_calc` | Edge | -0.2 per unstable, min 0.0 |
| `test_unvalidated_count_accurate` | Happy | Correct count in response |
| `test_invalid_context_error` | Error | Error for missing context |

---

## 6. Redis Client

> **Full details:** `tests/test_redis_client_requirements.md` (all sections)

### 6.1 Connection Handling (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_connect_success` | Happy | Connected state on init |
| `test_connect_unavailable` | Edge | Graceful failure on unavailable |
| `test_connect_not_installed` | Edge | Handles missing redis-py |
| `test_is_connected_verifies_ping` | Happy | Actually pings Redis |
| `test_reconnect_success` | Happy | Reconnection works |
| `test_reconnect_still_unavailable` | Edge | Returns False if still down |

### 6.2 Yarn Board State (~10 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_get_yarn_state_exists` | Happy | Returns stored state |
| `test_get_yarn_state_not_found` | Edge | Returns None |
| `test_get_yarn_state_disconnected` | Edge | Returns None gracefully |
| `test_set_yarn_state_success` | Happy | Stores with TTL |
| `test_set_yarn_state_disconnected` | Edge | Returns False |
| `test_set_grabbed_add` | Happy | Adds to set |
| `test_set_grabbed_remove` | Happy | Removes from set |
| `test_get_grabbed_points` | Happy | Returns set members |
| `test_get_grabbed_empty` | Edge | Returns [] |

### 6.3 Agent Presence (~8 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_get_agent_status_exists` | Happy | Returns stored status |
| `test_get_agent_status_not_found` | Edge | Returns None |
| `test_set_agent_busy_with_task` | Happy | Stores busy + task |
| `test_set_agent_available` | Happy | Stores busy=False |
| `test_heartbeat_updates_timestamp` | Happy | Refreshes last_heartbeat |
| `test_heartbeat_creates_default` | Happy | Creates status if none exists |
| `test_agent_status_ttl` | Happy | TTL ~300 seconds |

### 6.4 Message Queues (~12 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_queue_for_agent_success` | Happy | Message queued |
| `test_queue_adds_timestamp` | Happy | queued_at added |
| `test_queue_preserves_timestamp` | Edge | Existing timestamp kept |
| `test_queue_fifo_order` | Happy | FIFO ordering |
| `test_get_agent_queue_limit` | Happy | Limit parameter works |
| `test_get_agent_queue_peek` | Edge | Doesn't remove messages |
| `test_pop_agent_queue_removes` | Happy | Removes oldest |
| `test_pop_agent_queue_empty` | Edge | Returns None |
| `test_clear_agent_queue` | Happy | Clears all messages |
| `test_get_queue_length` | Happy | Accurate count |
| `test_get_queue_length_disconnected` | Edge | Returns 0 |

### 6.5 Pub/Sub (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_notify_priority_change` | Happy | Publishes to channel |
| `test_notify_disconnected` | Edge | Returns False |
| `test_subscribe_to_context` | Happy | Creates subscription |
| `test_subscribe_disconnected` | Edge | Returns False |
| `test_unsubscribe` | Happy | Unsubscribes pattern |
| `test_unsubscribe_no_pubsub` | Edge | Returns False |

### 6.6 Health Check (~4 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_health_connected` | Happy | connected=True, status=healthy |
| `test_health_disconnected` | Edge | connected=False, status=disconnected |
| `test_health_degraded` | Edge | Connected but info fails |
| `test_api_redis_health` | Happy | GET /redis/health |

### 6.7 Graceful Degradation (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_all_methods_return_defaults` | Critical | All methods have safe defaults |
| `test_disconnect_mid_operation` | Edge | Handles sudden disconnect |
| `test_reconnects_after_failure` | Happy | Operations resume after reconnect |
| `test_data_persists_reconnect` | Integration | Data survives reconnect |

### 6.8 Adapter (~6 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_adapter_returns_dataclass` | Happy | Returns YarnBoardState |
| `test_adapter_returns_none` | Edge | Returns None when missing |
| `test_adapter_serializes_dataclass` | Happy | Correctly serializes |
| `test_adapter_matches_interface` | Happy | All methods present |
| `test_initialize_replaces_stub` | Integration | datashapes.redis_interface replaced |
| `test_initialize_keeps_stub` | Edge | Stub kept when unavailable |

---

## 7. Integration Flows

> **Full details:** `PHASE5_INTEGRATION_TEST_REQUIREMENTS.md` (all flows with step-by-step code)

### Flow 1: Scratchpad -> Curator -> Agent (~6 tests)

```python
def test_scratchpad_curator_agent_flow():
    """Complete lifecycle: create entry -> curator validation -> agent delivery."""
    # Step 1: Create question entry
    # Step 2: Verify routes to curator
    # Step 3: Curator approves
    # Step 4: Verify routes to inferred agent
    # Step 5: Test with Redis unavailable
    # Step 6: Test quick_note bypass
```

### Flow 2: Clustering Trigger (~6 tests)

```python
def test_clustering_trigger_flow():
    """3+ sources triggers clustering."""
    # Step 1: First source - no flag
    # Step 2: Second source - no flag
    # Step 3: Third source - TRIGGERS FLAG
    # Step 4: Verify metadata updated
    # Step 5: Verify appears in get_cluster_flagged_refs
    # Step 6: Verify validated excluded
```

### Flow 3: Validation Prompt Surfacing (~5 tests)

```python
def test_validation_prompt_surfacing_flow():
    """Urgency-based validation routing."""
    # Step 1: Create refs with various signals
    # Step 2: Test stale ref urgency
    # Step 3: Test inline vs scratchpad routing
    # Step 4: Verify urgency score calculation
    # Step 5: Verify validated excluded
```

### Flow 4: Yarn Board Render (~7 tests)

```python
def test_yarn_board_render_flow():
    """Board vs cushion point management."""
    # Step 1: Create context with children and cross-refs
    # Step 2: Save some positions
    # Step 3: Render board
    # Step 4: Verify positioned in points[]
    # Step 5: Verify unpositioned in cushion[]
    # Step 6: Verify point ID format
    # Step 7: Verify connections structure
```

### Flow 5: Redis Failover (~7 tests)

```python
def test_redis_failover_flow():
    """Graceful degradation and recovery."""
    # Step 1: Start with Redis connected
    # Step 2: Queue messages successfully
    # Step 3: Simulate disconnect
    # Step 4: Verify graceful degradation
    # Step 5: Reconnect
    # Step 6: Verify operations resume
    # Step 7: Health check during failure
```

---

## 8. Gap Resolution Tests (Added 2026-01-13)

These tests address gaps identified during test review session.

> **Context:** Gaps identified by testing instance, resolved through discussion.

### 8.1 Concurrency - Coordination Events (~2 tests)

**Design Decision:** Two agents grabbing same point = coordination signal, not conflict. System spawns impromptu sidebar for agents to sync up.

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_same_point_grab_spawns_coordination_sidebar` | Integration | Two agents grab same point → coordination sidebar created |
| `test_coordination_sidebar_includes_both_agents` | Happy | Both agents are participants in spawned sidebar |

### 8.2 Persistence Round-Trip (~2 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_layout_survives_restart` | Critical | Save layout → restart orchestrator → layout exists |
| `test_grabbed_points_persist_in_redis` | Integration | Grabbed state survives Redis reconnect |

### 8.3 Render Expansion (~4 tests)

**Design Decision:** `expanded: false` = minimap mode (dot/string), `expanded: true` = includes detail dict with rich metadata.

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_render_expanded_false_minimal` | Happy | Default render returns minimal point structure |
| `test_render_expanded_true_includes_detail` | Happy | expanded=True adds detail dict to points |
| `test_point_detail_contains_context_summary` | Happy | Context points include summary, findings, questions |
| `test_connection_detail_contains_ref_metadata` | Happy | Connection detail has ref_type, strength, validation_state |

### 8.4 Pin Cushion Buffer Pattern (~5 tests)

**Design Decision:** Cushion is a CPU/human catch-up buffer. New items accumulate during fast activity, flush on refresh with auto-positioning.

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_new_items_land_in_cushion` | Happy | New connections go to cushion, not immediate render |
| `test_cushion_accumulates_multiple_items` | Happy | Multiple adds → cushion grows |
| `test_refresh_empties_cushion_to_board` | Critical | Refresh action → cushion items auto-position on board |
| `test_positioned_items_stay_locked_on_refresh` | Happy | Existing positions preserved during refresh |
| `test_cushion_count_in_render_response` | Happy | Render includes cushion item count for UI |

### 8.5 Performance Thresholds (~2 tests)

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_render_50_points_under_100ms` | Perf | 50 points renders in < 100ms |
| `test_render_100_points_under_200ms` | Perf | 100 points renders in < 200ms (linear scaling) |

### 8.6 WebSocket Broadcast Mechanics (~7 tests)

**Design Decision:** Timestamps + server-side coalescing. Rapid updates pool and batch before broadcast. Client can sort by timestamp if needed.

| Test Name | Type | Description |
|-----------|------|-------------|
| `test_layout_save_broadcasts` | Happy | Layout save triggers WebSocket event |
| `test_grab_broadcasts` | Happy | Grab action triggers WebSocket event |
| `test_release_broadcasts` | Happy | Release action triggers WebSocket event |
| `test_broadcast_includes_timestamp` | Happy | All broadcasts include ISO timestamp |
| `test_rapid_updates_coalesce` | Happy | 5 quick changes → 1 batched broadcast |
| `test_coalesced_batch_sorted_by_timestamp` | Happy | Batched items ordered chronologically |
| `test_broadcast_no_clients_graceful` | Edge | No connected clients → no exception |

---

## 9. Critical Path Tests

These tests MUST pass for Phase 5 to be considered functional:

### Clustering
1. **`test_third_source_triggers`** - 3rd source MUST set cluster_flagged=True and validation_priority="urgent"

### Validation Prompts
2. **`test_citing_refs_inline`** - Refs in citing_refs MUST route to inline_prompts
3. **`test_not_citing_scratchpad`** - Non-cited refs with urgency MUST route to scratchpad_prompts

### Queue Routing
4. **`test_route_finding`** - All findings MUST go through curator first

### Stability
5. **`test_unstable_dependency`** - Dependencies with unvalidated refs MUST mark parent unstable

### Contradictions
6. **`test_implements_vs_contradicts`** - Contradicting ref types MUST be detected

### Redis
7. **`test_all_methods_return_defaults`** - ALL Redis methods MUST return safe defaults when disconnected

### Persistence
8. **`test_layout_survives_restart`** - Layout MUST persist across orchestrator restart

### Pin Cushion
9. **`test_refresh_empties_cushion_to_board`** - Refresh MUST move cushion items to board with auto-positioning

---

## Test Execution

### Run Commands

```bash
# Run all Phase 5 tests
pytest tests/ -v -k "phase5 or yarn or queue or cluster or validation or redis"

# Run unit tests only (fast)
pytest tests/ -v -m "not integration"

# Run integration tests (requires Redis)
pytest tests/ -v -m "integration"

# Run critical path tests
pytest tests/ -v -k "critical"

# Run with coverage
pytest tests/ --cov=conversation_orchestrator --cov=redis_client --cov=api_server_bridge --cov-report=html
```

### Markers

```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires real services")
    config.addinivalue_line("markers", "slow: long-running tests")
    config.addinivalue_line("markers", "critical: must-pass tests")
    config.addinivalue_line("markers", "redis: requires Redis")
```

---

## Summary Statistics

| Category | Test Count |
|----------|------------|
| Yarn Board Operations | ~47 |
| Queue Routing | ~38 |
| Clustering | ~18 |
| Validation Prompts | ~32 |
| Redis Client | ~60 |
| Integration Flows | ~31 |
| **Gap Resolutions (new)** | **~22** |
| **Total** | **~248** |

*Note: Gap resolution tests added 2026-01-13 after testing instance review. Some tests overlap between categories. Actual unique test count is approximately 190.*

---

## Two-Stage Testing Protocol

Per project CLAUDE.md, implement tests in two stages:

1. **Stage 1: Unit Logic Testing** - Test methods directly with controlled inputs
2. **Stage 2: In-Field Simulation** - Test full HTTP request/response flow

Example:
```python
# Stage 1: Unit test
def test_route_finding_logic():
    result = orchestrator.route_scratchpad_entry(entry, context_id)
    assert result["destination"] == "AGENT-curator"

# Stage 2: API test
def test_route_finding_api():
    response = client.post("/queue/route", json=request_body)
    assert response.json()["destination"] == "AGENT-curator"
```
