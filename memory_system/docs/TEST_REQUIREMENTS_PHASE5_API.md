# Phase 5 API Test Requirements

## Overview

This document defines comprehensive test requirements for the Phase 5 API endpoints in `/home/grinnling/Development/CODE_IMPLEMENTATION/api_server_bridge.py`. These endpoints cover:

1. **Yarn Board Endpoints** - Visual layout and hot state management
2. **Redis Health Endpoint** - Cache/queue service health checking
3. **Queue Routing** - Agent message queue operations (internal to orchestrator)

---

## 1. YARN BOARD ENDPOINTS

The Yarn Board is a VIEW layer over OZOLITH + Redis + cross-refs. It provides visual layout persistence and hot state management for the detective board metaphor.

### 1.1 GET /sidebars/{sidebar_id}/yarn-board

**Purpose:** Retrieve the yarn board layout for a context.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_get_yarn_board_layout_success` | Get layout for existing sidebar | Returns 200 with layout data |
| `test_get_yarn_board_layout_not_found` | Get layout for non-existent sidebar | Returns success=False, error message |
| `test_get_yarn_board_layout_default` | Get layout when no layout exists | Returns default layout structure |
| `test_get_yarn_board_layout_with_positions` | Get layout with saved point positions | Returns layout with point_positions populated |

#### Request/Response Structure

**Request:**
```
GET /sidebars/SB-1/yarn-board
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "layout": {
    "point_positions": {},
    "zoom_level": 1.0,
    "focus_point": null,
    "show_archived": false,
    "filter_by_priority": null,
    "filter_by_type": null
  }
}
```

**Error Response (context not found):**
```json
{
  "success": false,
  "error": "Context 'SB-999' not found"
}
```

#### Edge Cases

1. **Empty sidebar_id**: Should return validation error
2. **Invalid sidebar_id format**: Should return error (context not found)
3. **Archived context**: Should still return layout (archived contexts have layouts)
4. **Context with large point_positions**: Should handle layouts with 100+ points

---

### 1.2 PUT /sidebars/{sidebar_id}/yarn-board

**Purpose:** Save or update the yarn board layout for a context.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_save_yarn_board_layout_success` | Save layout with all fields | Returns 200 with updated layout |
| `test_save_yarn_board_layout_partial` | Save layout with only some fields | Updates only provided fields |
| `test_save_yarn_board_layout_not_found` | Save layout for non-existent sidebar | Returns success=False, error message |
| `test_save_yarn_board_creates_default` | Save layout when none exists | Creates layout with default values |
| `test_save_yarn_board_updates_timestamp` | Save layout updates last_modified | last_modified timestamp is updated |

#### Request/Response Structure

**Request:**
```
PUT /sidebars/SB-1/yarn-board
Content-Type: application/json

{
  "point_positions": {
    "context:SB-1": {"x": 100, "y": 200, "collapsed": false},
    "crossref:SB-1:SB-2": {"x": 300, "y": 150, "collapsed": true}
  },
  "zoom_level": 1.5,
  "focus_point": "context:SB-1",
  "show_archived": true,
  "filter_by_priority": "urgent",
  "filter_by_type": "context"
}
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "layout": {
    "point_positions": {
      "context:SB-1": {"x": 100, "y": 200, "collapsed": false},
      "crossref:SB-1:SB-2": {"x": 300, "y": 150, "collapsed": true}
    },
    "zoom_level": 1.5,
    "focus_point": "context:SB-1",
    "show_archived": true,
    "filter_by_priority": "urgent",
    "filter_by_type": "context",
    "last_modified": "2026-01-12T10:30:00"
  }
}
```

#### Request Model (YarnLayoutRequest)

```python
class YarnLayoutRequest(BaseModel):
    point_positions: dict | None = None  # {point_id: {x, y, collapsed}}
    zoom_level: float | None = None
    focus_point: str | None = None
    show_archived: bool | None = None
    filter_by_priority: str | None = None
    filter_by_type: str | None = None
```

#### Edge Cases

1. **Empty request body**: Should succeed (no-op update)
2. **Invalid zoom_level** (negative): Should validate and reject
3. **Invalid point_positions structure**: Should validate coordinate types
4. **WebSocket broadcast**: Should verify broadcast message is sent to React

---

### 1.3 PATCH /sidebars/{sidebar_id}/yarn-board/points/{point_id}

**Purpose:** Update a single point's position on the yarn board (drag-and-drop).

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_update_point_position_success` | Update existing point position | Returns 200 with new position |
| `test_update_point_position_new_point` | Add position for new point | Creates entry in point_positions |
| `test_update_point_position_not_found` | Update point in non-existent sidebar | Returns success=False, error |
| `test_update_point_position_collapsed` | Update with collapsed=True | Position includes collapsed flag |
| `test_update_point_position_triggers_broadcast` | Position update sends WebSocket | Broadcasts yarn_point_moved event |

#### Request/Response Structure

**Request:**
```
PATCH /sidebars/SB-1/yarn-board/points/context:SB-2
Content-Type: application/json

{
  "x": 450.5,
  "y": 320.0,
  "collapsed": false
}
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "point_id": "context:SB-2",
  "position": {
    "x": 450.5,
    "y": 320.0,
    "collapsed": false
  }
}
```

#### Request Model (PointPositionRequest)

```python
class PointPositionRequest(BaseModel):
    x: float
    y: float
    collapsed: bool = False
```

#### Edge Cases

1. **Special characters in point_id**: Handle IDs like `crossref:SB-1:SB-2`
2. **Very large coordinates**: Should accept large float values
3. **Negative coordinates**: Should be valid (board can extend in all directions)
4. **URL-encoded point_id**: Handle `context%3ASB-1` correctly

---

### 1.4 GET /sidebars/{sidebar_id}/yarn-board/state

**Purpose:** Get the hot state for a yarn board (grabbed points, priority overrides).

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_get_yarn_state_success` | Get state for existing sidebar | Returns 200 with state data |
| `test_get_yarn_state_default` | Get state when Redis unavailable | Returns default empty state |
| `test_get_yarn_state_not_found` | Get state for non-existent sidebar | Returns success=False, error |
| `test_get_yarn_state_with_grabbed` | Get state with grabbed points | Returns grabbed_point_ids populated |
| `test_get_yarn_state_source_indicator` | Response indicates data source | source field shows "redis" or "default" |

#### Request/Response Structure

**Request:**
```
GET /sidebars/SB-1/yarn-board/state
```

**Expected Response (200 OK - Redis available):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "state": {
    "grabbed_point_ids": ["context:SB-2", "finding:ENTRY-001"],
    "priority_overrides": {"context:SB-3": "urgent"},
    "hot_refs": ["SB-1:SB-2"]
  },
  "source": "redis"
}
```

**Expected Response (200 OK - Redis unavailable/stub mode):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "state": {
    "grabbed_point_ids": [],
    "priority_overrides": {},
    "hot_refs": []
  },
  "source": "default"
}
```

#### Edge Cases

1. **Redis connection failure mid-request**: Should gracefully degrade
2. **Stale Redis data**: Should handle TTL-expired data gracefully

---

### 1.5 POST /sidebars/{sidebar_id}/yarn-board/points/{point_id}/grab

**Purpose:** Mark a point as grabbed (focused) or released.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_grab_point_success` | Grab a point | Returns 200 with grabbed=true |
| `test_release_point_success` | Release a grabbed point | Returns 200 with grabbed=false |
| `test_grab_point_redis_unavailable` | Grab when Redis unavailable | Success but persisted=false |
| `test_grab_point_broadcasts` | Grab sends WebSocket event | Broadcasts yarn_point_grabbed |
| `test_release_point_broadcasts` | Release sends WebSocket event | Broadcasts yarn_point_released |
| `test_grab_point_context_not_found` | Grab point in non-existent sidebar | Returns success=False, error |

#### Request/Response Structure

**Request (Grab):**
```
POST /sidebars/SB-1/yarn-board/points/context:SB-2/grab
Content-Type: application/json

{
  "grabbed": true
}
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "point_id": "context:SB-2",
  "grabbed": true,
  "persisted": true
}
```

**Response when Redis unavailable:**
```json
{
  "success": true,
  "context_id": "SB-1",
  "point_id": "context:SB-2",
  "grabbed": true,
  "persisted": false
}
```

#### Request Model (GrabPointRequest)

```python
class GrabPointRequest(BaseModel):
    grabbed: bool
```

#### Edge Cases

1. **Grabbing same point twice**: Should be idempotent
2. **Releasing non-grabbed point**: Should succeed gracefully
3. **Multiple grabs in rapid succession**: Should handle concurrent requests

---

### 1.6 POST /sidebars/{sidebar_id}/yarn-board/render

**Purpose:** Render the yarn board as a minimal minimap structure.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_render_yarn_board_success` | Render board for existing sidebar | Returns 200 with points and connections |
| `test_render_yarn_board_not_found` | Render for non-existent sidebar | Returns success=False, error |
| `test_render_yarn_board_with_children` | Render board with child contexts | Includes child points and parent-child connections |
| `test_render_yarn_board_with_crossrefs` | Render board with cross-refs | Includes crossref points and connections |
| `test_render_yarn_board_cushion` | Render with unpositioned points | Points without positions in cushion array |
| `test_render_yarn_board_highlights` | Render with highlight list | Highlights array passed through |
| `test_render_yarn_board_empty` | Render board with no relationships | Returns minimal structure |

#### Request/Response Structure

**Request:**
```
POST /sidebars/SB-1/yarn-board/render
Content-Type: application/json

{
  "highlights": ["context:SB-2", "finding:ENTRY-001"]
}
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "context_id": "SB-1",
  "points": [
    {
      "id": "context:SB-1",
      "label": "SB-1",
      "type": "context",
      "color": "#4A90D9",
      "x": 100,
      "y": 200
    },
    {
      "id": "crossref:SB-1:SB-2",
      "label": "related_to",
      "type": "crossref",
      "color": "#7B68EE",
      "x": 300,
      "y": 150
    }
  ],
  "connections": [
    {
      "from_id": "context:SB-1",
      "to_id": "crossref:SB-1:SB-2",
      "ref_type": "related_to"
    }
  ],
  "cushion": [
    {
      "id": "finding:ENTRY-003",
      "label": "New discovery",
      "type": "finding",
      "color": "#50C878"
    }
  ],
  "highlights": ["context:SB-2", "finding:ENTRY-001"],
  "type_colors": {
    "context": "#4A90D9",
    "crossref": "#7B68EE",
    "finding": "#50C878",
    "question": "#FF6B6B"
  }
}
```

#### Request Model (RenderYarnBoardRequest)

```python
class RenderYarnBoardRequest(BaseModel):
    highlights: list[str] | None = None
```

#### Edge Cases

1. **Empty request body**: Should render without highlights
2. **Circular relationships**: Should handle bidirectional cross-refs
3. **Self-referential point**: Should handle gracefully
4. **Large board**: Should render boards with 50+ points efficiently

---

## 2. REDIS HEALTH ENDPOINT

### 2.1 GET /redis/health

**Purpose:** Check Redis connection health and status.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_redis_health_connected` | Check health when Redis online | Returns connected=true, status=healthy |
| `test_redis_health_disconnected` | Check health when Redis offline | Returns connected=false, appropriate status |
| `test_redis_health_import_error` | Check health when redis_client unavailable | Returns connected=false, import error message |
| `test_redis_health_memory_info` | Check health returns memory usage | Includes used_memory when connected |

#### Request/Response Structure

**Request:**
```
GET /redis/health
```

**Expected Response (Redis connected):**
```json
{
  "connected": true,
  "host": "localhost",
  "port": 6379,
  "used_memory": "2.5M",
  "status": "healthy"
}
```

**Expected Response (Redis disconnected):**
```json
{
  "connected": false,
  "host": "localhost",
  "port": 6379,
  "status": "disconnected"
}
```

**Expected Response (Import error):**
```json
{
  "connected": false,
  "status": "redis_client not available"
}
```

#### Edge Cases

1. **Redis connection timeout**: Should return appropriate error status
2. **Redis authentication failure**: Should return connected=false with error
3. **Redis cluster mode**: Should report cluster status if applicable

---

## 3. QUEUE ROUTING OPERATIONS

Queue routing is handled internally by the `ConversationOrchestrator`. These are not direct API endpoints but are critical operations that should be tested through integration tests.

### 3.1 Internal: route_scratchpad_entry()

**Purpose:** Route scratchpad entries through the curator validation pipeline.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_route_quick_note_no_route` | Quick note without explicit route | Returns routed=false, stored only |
| `test_route_finding_to_curator` | Finding entry routes to curator | Queued for AGENT-curator |
| `test_route_with_explicit_route` | Entry with explicit_route_to | Uses specified route after validation |
| `test_route_redis_unavailable` | Route when Redis offline | Graceful degradation, queued_to_redis=false |

### 3.2 Internal: curator_approve_entry()

**Purpose:** Curator approves/rejects entry then routes to destination.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_curator_approve_routes` | Approved entry routes to destination | Queued for inferred destination agent |
| `test_curator_reject` | Rejected entry not routed | Returns approved=false with reason |
| `test_curator_infers_destination` | Destination inferred from content | Matches keywords to agent specialties |

### 3.3 Internal: get_agent_queue()

**Purpose:** Get pending messages for an agent.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_get_agent_queue_empty` | Queue for agent with no messages | Returns empty queue |
| `test_get_agent_queue_with_messages` | Queue for agent with pending items | Returns queue contents |
| `test_get_agent_queue_redis_stub` | Queue when Redis unavailable | Returns empty queue (stub mode) |

### 3.4 Internal: register_agent() / list_agents()

**Purpose:** Register agents and list their specialties.

#### Test Cases

| Test Name | Description | Expected Behavior |
|-----------|-------------|-------------------|
| `test_register_new_agent` | Register new agent with specialties | Agent added to registry |
| `test_update_existing_agent` | Update existing agent | Specialties updated |
| `test_list_agents` | List all registered agents | Returns all agents with status |
| `test_default_agents_exist` | Default agents present | curator, operator, researcher, debugger, architect |

---

## 4. INTEGRATION TEST SCENARIOS

### 4.1 Yarn Board Round-Trip

```python
def test_yarn_board_full_lifecycle():
    """
    1. Create root context
    2. Spawn sidebar (creates parent-child)
    3. Add cross-ref (creates relationship)
    4. Render board -> verify points and connections
    5. Save layout with positions
    6. Grab a point
    7. Re-render -> verify positions applied
    8. Get state -> verify grabbed point
    9. Release point
    10. Get state -> verify empty grabbed list
    """
```

### 4.2 Redis Degradation

```python
def test_redis_graceful_degradation():
    """
    1. Verify Redis health (should be disconnected in test env)
    2. Get yarn state -> should return default
    3. Grab point -> success=true, persisted=false
    4. Get yarn state -> grabbed not persisted (default state)
    5. Layout operations still work (SQLite-backed)
    """
```

### 4.3 Point ID Conventions

```python
def test_point_id_conventions():
    """
    Verify point IDs follow convention:
    - context:{sidebar_id} -> context:SB-1
    - crossref:{sorted_a}:{sorted_b} -> crossref:SB-1:SB-2
    - finding:{entry_id} -> finding:ENTRY-001
    """
```

---

## 5. TEST FIXTURES REQUIRED

### 5.1 Sidebar Fixtures

```python
@pytest.fixture
def root_sidebar():
    """Create a root sidebar context for testing."""
    # POST /sidebars/create-root
    pass

@pytest.fixture
def child_sidebar(root_sidebar):
    """Create a child sidebar spawned from root."""
    # POST /sidebars/spawn
    pass

@pytest.fixture
def sidebar_with_crossrefs(root_sidebar, child_sidebar):
    """Create sidebars with cross-references between them."""
    # POST /sidebars/{id}/cross-ref
    pass
```

### 5.2 Layout Fixtures

```python
@pytest.fixture
def sidebar_with_layout(root_sidebar):
    """Sidebar with pre-saved yarn board layout."""
    # PUT /sidebars/{id}/yarn-board with positions
    pass
```

### 5.3 Mock Redis

```python
@pytest.fixture
def mock_redis_connected():
    """Mock Redis as connected and functional."""
    pass

@pytest.fixture
def mock_redis_disconnected():
    """Mock Redis as disconnected (stub mode)."""
    pass
```

---

## 6. STATUS CODES MATRIX

| Endpoint | Success | Not Found | Bad Request | Server Error |
|----------|---------|-----------|-------------|--------------|
| GET /yarn-board | 200 | 200 (error field) | 422 | 500 |
| PUT /yarn-board | 200 | 200 (error field) | 422 | 500 |
| PATCH /points/{id} | 200 | 200 (error field) | 422 | 500 |
| GET /yarn-board/state | 200 | 200 (error field) | 422 | 500 |
| POST /points/{id}/grab | 200 | 200 (error field) | 422 | 500 |
| POST /yarn-board/render | 200 | 200 (error field) | 422 | 500 |
| GET /redis/health | 200 | N/A | N/A | 500 |

**Note:** These endpoints return 200 with `success: false` for not-found cases rather than 404. This is the established pattern in the API.

---

## 7. WEBSOCKET BROADCAST VERIFICATION

Several endpoints broadcast WebSocket messages. Tests should verify:

| Endpoint | Broadcast Type | Payload |
|----------|----------------|---------|
| PUT /yarn-board | `yarn_board_layout_updated` | `{context_id, layout}` |
| PATCH /points/{id} | `yarn_point_moved` | `{context_id, point_id, position}` |
| POST /grab (grabbed=true) | `yarn_point_grabbed` | `{context_id, point_id, persisted}` |
| POST /grab (grabbed=false) | `yarn_point_released` | `{context_id, point_id, persisted}` |

---

## 8. IMPLEMENTATION NOTES

### 8.1 Two-Stage Testing Protocol

Per project CLAUDE.md, implement tests in two stages:

1. **Stage 1: Unit Logic Testing** - Test orchestrator methods directly
2. **Stage 2: In-Field Simulation** - Test full HTTP request/response flow

### 8.2 Test File Location

Tests should be placed in:
```
/home/grinnling/Development/CODE_IMPLEMENTATION/tests/test_api_phase5_yarn_board.py
```

### 8.3 Dependencies

```python
import pytest
from fastapi.testclient import TestClient
from api_server_bridge import app
```

### 8.4 Isolation

Tests should:
- Use temp directories for SQLite databases
- Reset orchestrator and persistence between tests
- Mock Redis client when testing degradation scenarios
