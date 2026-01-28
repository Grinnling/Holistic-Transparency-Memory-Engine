# Phase 5 Integration/Flow Test Requirements

This document defines comprehensive end-to-end flow tests for Phase 5 features including queue routing, clustering, validation prompts, yarn board rendering, and Redis failover handling.

**Document Version:** 1.0
**Created:** 2026-01-12
**Scope:** Integration tests for conversation_orchestrator.py Phase 5 features

---

## Test Environment Prerequisites

### Dependencies
```python
# Required modules
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# System under test
from conversation_orchestrator import ConversationOrchestrator, reset_orchestrator
from datashapes import (
    ScratchpadEntry, CrossRefMetadata, YarnBoardState,
    AgentCapability, AgentAvailability, redis_interface
)
from redis_client import RedisClient, get_redis_client, initialize_redis
```

### Fixtures
```python
@pytest.fixture
def fresh_orchestrator():
    """Reset and return a fresh orchestrator instance."""
    reset_orchestrator()
    return ConversationOrchestrator(auto_load=False)

@pytest.fixture
def orchestrator_with_contexts(fresh_orchestrator):
    """Orchestrator with pre-created contexts for testing."""
    orch = fresh_orchestrator
    root_id = orch.create_root_context(task_description="Test root", created_by="test")
    child_id = orch.spawn_sidebar(root_id, "Test sidebar", created_by="test")
    return orch, root_id, child_id

@pytest.fixture
def mock_redis():
    """Mock Redis client that tracks operations."""
    mock = MagicMock()
    mock.is_connected.return_value = True
    mock.queue_for_agent.return_value = True
    mock.get_agent_queue.return_value = []
    return mock

@pytest.fixture
def disconnected_redis():
    """Mock Redis client that simulates disconnection."""
    mock = MagicMock()
    mock.is_connected.return_value = False
    mock.queue_for_agent.return_value = False
    mock.get_agent_queue.return_value = []
    return mock
```

---

## Flow 1: Scratchpad -> Curator -> Agent Flow

### Flow Name
`test_scratchpad_curator_agent_routing_flow`

### Description
Tests the complete lifecycle of a scratchpad entry from creation through curator validation to final agent delivery.

### Step-by-Step Sequence

#### Step 1.1: Create Scratchpad Entry with entry_type="question"
```python
def test_scratchpad_entry_creation():
    """Step 1.1: Create scratchpad entry with question type."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_id = orch.create_root_context(task_description="Test context")

    # ACTION
    entry = {
        "entry_id": "ENTRY-001",
        "content": "How do we debug the authentication timeout?",
        "entry_type": "question",
        "submitted_by": "test-agent",
        "routed_to": None  # Let system infer destination
    }

    result = orch.route_scratchpad_entry(entry, ctx_id)

    # ASSERTIONS
    assert result["success"] == True
    assert result["routed"] == True
    assert result["destination"] == "AGENT-curator"
    assert result["awaiting"] == "curator_validation"
```

#### Step 1.2: Verify Entry Routes to Curator
```python
def test_entry_routes_to_curator(mock_redis):
    """Step 1.2: Verify question entry queues for curator."""
    # SETUP
    with patch('datashapes.redis_interface', mock_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        entry = {
            "entry_id": "ENTRY-002",
            "content": "Research the security implications",
            "entry_type": "question",
            "submitted_by": "test-agent"
        }

        # ACTION
        result = orch.route_scratchpad_entry(entry, ctx_id)

        # ASSERTIONS
        assert result["destination"] == "AGENT-curator"
        mock_redis.queue_for_agent.assert_called_once()
        call_args = mock_redis.queue_for_agent.call_args
        assert call_args[0][0] == "AGENT-curator"  # First arg is agent_id
        queued_message = call_args[0][1]
        assert queued_message["type"] == "validate_entry"
        assert queued_message["entry"]["entry_id"] == "ENTRY-002"
```

#### Step 1.3: Curator Approves Entry
```python
def test_curator_approves_entry(mock_redis):
    """Step 1.3: Curator approves and routes to destination agent."""
    # SETUP
    with patch('datashapes.redis_interface', mock_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        # ACTION
        result = orch.curator_approve_entry(
            entry_id="ENTRY-003",
            context_id=ctx_id,
            approved=True
        )

        # ASSERTIONS
        assert result["success"] == True
        assert result["approved"] == True
        assert result["destination"] is not None
        # Should have queued for destination agent
        assert mock_redis.queue_for_agent.call_count >= 1
```

#### Step 1.4: Verify Routing to Correct Agent Based on Specialty Inference
```python
def test_specialty_inference_routing():
    """Step 1.4: Verify content-based routing to specialist agents."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_id = orch.create_root_context()

    # Test cases: content -> expected specialty match
    test_cases = [
        ("debug the crash in auth module", "AGENT-debugger"),
        ("research best practices for API design", "AGENT-researcher"),
        ("design the new architecture for caching", "AGENT-architect"),
        ("fix the permission bug", "AGENT-debugger"),
        ("investigate the security vulnerability", "AGENT-researcher"),
    ]

    for content, expected_agent in test_cases:
        # ACTION
        destination = orch._infer_destination(
            entry_id="test",
            context_id=ctx_id,
            content_hint=content
        )

        # ASSERTION
        assert destination == expected_agent, \
            f"Content '{content}' should route to {expected_agent}, got {destination}"
```

#### Step 1.5: Test with Redis Unavailable (Fallback)
```python
def test_routing_with_redis_unavailable(disconnected_redis):
    """Step 1.5: Graceful degradation when Redis is unavailable."""
    # SETUP
    with patch('datashapes.redis_interface', disconnected_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        entry = {
            "entry_id": "ENTRY-004",
            "content": "Debug the timeout issue",
            "entry_type": "question",
            "submitted_by": "test-agent"
        }

        # ACTION
        result = orch.route_scratchpad_entry(entry, ctx_id)

        # ASSERTIONS
        assert result["success"] == True
        assert result["routed"] == True
        assert result["queued_to_redis"] == False  # Redis unavailable
        assert result["destination"] == "AGENT-curator"
        # Entry should still be logically routed, just not in Redis queue
```

#### Step 1.6: Test Quick Note Bypasses Routing
```python
def test_quick_note_bypasses_routing():
    """Step 1.6: quick_note entries without explicit route are stored only."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_id = orch.create_root_context()

    entry = {
        "entry_id": "ENTRY-005",
        "content": "Just a quick note to self",
        "entry_type": "quick_note",
        "submitted_by": "test-agent",
        "routed_to": None  # No explicit route
    }

    # ACTION
    result = orch.route_scratchpad_entry(entry, ctx_id)

    # ASSERTIONS
    assert result["success"] == True
    assert result["routed"] == False
    assert result["reason"] == "quick_note_no_route"
```

### Setup/Teardown Requirements
```python
def setup_function():
    """Reset state before each test."""
    reset_orchestrator()

def teardown_function():
    """Clean up after each test."""
    reset_orchestrator()
```

---

## Flow 2: Clustering Trigger Flow

### Flow Name
`test_cross_ref_clustering_trigger_flow`

### Description
Tests the automatic cluster flagging when 3+ independent sources suggest the same cross-reference.

### Step-by-Step Sequence

#### Step 2.1: Add Cross-Ref from Source A
```python
def test_clustering_step1_first_source():
    """Step 2.1: First source suggests cross-ref (no clustering yet)."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")

    # ACTION
    result = orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="related_to",
        reason="First discovery",
        confidence=0.6,
        suggested_by="source-A"
    )

    # ASSERTIONS
    assert result["success"] == True
    assert result["already_existed"] == False
    assert result["suggested_sources"] == ["source-A"]
    assert result["cluster_flagged"] == False
    assert result["newly_flagged"] == False
```

#### Step 2.2: Add Same Cross-Ref Suggested by Source B
```python
def test_clustering_step2_second_source():
    """Step 2.2: Second source confirms - sources list grows."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")

    # First source
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="source-A")

    # ACTION - Second source suggests same ref
    result = orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="related_to",
        reason="Independent discovery",
        suggested_by="source-B"
    )

    # ASSERTIONS
    assert result["success"] == True
    assert result["already_existed"] == True
    assert "source-A" in result["suggested_sources"]
    assert "source-B" in result["suggested_sources"]
    assert len(result["suggested_sources"]) == 2
    assert result["cluster_flagged"] == False  # Not at threshold yet
```

#### Step 2.3: Add Same Cross-Ref Suggested by Source C (Triggers Clustering)
```python
def test_clustering_step3_third_source_triggers_flag():
    """Step 2.3: Third source triggers cluster flag (threshold = 3)."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")

    # Add two sources first
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="source-A")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="source-B")

    # ACTION - Third source
    result = orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="related_to",
        reason="Third independent discovery",
        suggested_by="source-C"
    )

    # ASSERTIONS
    assert result["success"] == True
    assert result["already_existed"] == True
    assert len(result["suggested_sources"]) == 3
    assert result["cluster_flagged"] == True  # NOW flagged
    assert result["newly_flagged"] == True  # Just became flagged
```

#### Step 2.4: Verify cluster_flagged and validation_priority
```python
def test_clustering_verify_metadata_updates():
    """Step 2.4: Verify metadata updated correctly after clustering."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")

    # Trigger clustering
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="source-A")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="source-B")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="source-C")

    # ACTION - Get raw metadata from context
    context = orch.get_context(ctx_a)
    metadata = context.cross_sidebar_refs[ctx_b]

    # ASSERTIONS
    assert metadata["cluster_flagged"] == True
    assert metadata["validation_priority"] == "urgent"  # Auto-bumped to urgent
    assert len(metadata["suggested_sources"]) >= 3
```

#### Step 2.5: Verify get_cluster_flagged_refs Returns It
```python
def test_clustering_query_flagged_refs():
    """Step 2.5: get_cluster_flagged_refs returns cluster-flagged items."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")
    ctx_c = orch.create_root_context(task_description="Context C")

    # Create one clustered ref (A->B with 3 sources)
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="s1")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="s2")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="s3")

    # Create one non-clustered ref (A->C with 1 source)
    orch.add_cross_ref(ctx_a, ctx_c, ref_type="related_to", suggested_by="s1")

    # ACTION
    result = orch.get_cluster_flagged_refs()

    # ASSERTIONS
    assert result["success"] == True
    assert result["count"] >= 1
    assert result["threshold"] == 3

    flagged_refs = result["cluster_flagged_refs"]
    assert len(flagged_refs) >= 1

    # Find the A->B ref
    ab_ref = next((r for r in flagged_refs
                   if r["source_context_id"] == ctx_a
                   and r["target_context_id"] == ctx_b), None)
    assert ab_ref is not None
    assert ab_ref["source_count"] >= 3
```

#### Step 2.6: Verify Validated Refs Excluded by Default
```python
def test_clustering_excludes_validated_by_default():
    """Step 2.6: Validated refs excluded unless include_validated=True."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context()
    ctx_b = orch.create_root_context()

    # Create and cluster
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="s1")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="s2")
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="s3")

    # Validate the ref
    orch.validate_cross_ref(ctx_a, ctx_b, validation_state="true")

    # ACTION - Default query
    result_default = orch.get_cluster_flagged_refs(include_validated=False)

    # ACTION - Include validated
    result_include = orch.get_cluster_flagged_refs(include_validated=True)

    # ASSERTIONS
    assert result_default["count"] == 0  # Validated ref excluded
    assert result_include["count"] >= 1  # Validated ref included
```

### Setup/Teardown Requirements
```python
def setup_function():
    reset_orchestrator()

def teardown_function():
    reset_orchestrator()
```

---

## Flow 3: Validation Prompt Surfacing Flow

### Flow Name
`test_validation_prompt_surfacing_flow`

### Description
Tests the urgency-based validation prompt surfacing at end-of-exchange breakpoints.

### Step-by-Step Sequence

#### Step 3.1: Create Refs with Various Urgency Signals
```python
def test_validation_prompts_setup_refs():
    """Step 3.1: Create refs with different urgency signals."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_main = orch.create_root_context(task_description="Main context")
    ctx_a = orch.create_root_context(task_description="Context A")
    ctx_b = orch.create_root_context(task_description="Context B")
    ctx_c = orch.create_root_context(task_description="Context C")

    # Low confidence ref (urgency signal)
    orch.add_cross_ref(
        ctx_main, ctx_a,
        ref_type="related_to",
        confidence=0.3,  # Below VALIDATION_CONFIDENCE_THRESHOLD (0.7)
        suggested_by="test"
    )

    # Cluster-flagged ref (urgency signal)
    orch.add_cross_ref(ctx_main, ctx_b, ref_type="related_to", suggested_by="s1")
    orch.add_cross_ref(ctx_main, ctx_b, ref_type="related_to", suggested_by="s2")
    orch.add_cross_ref(ctx_main, ctx_b, ref_type="related_to", suggested_by="s3")

    # Normal ref (no special urgency)
    orch.add_cross_ref(
        ctx_main, ctx_c,
        ref_type="related_to",
        confidence=0.9,  # High confidence
        suggested_by="test"
    )

    # ASSERTIONS - setup verification
    flagged = orch.get_cluster_flagged_refs()
    assert flagged["count"] >= 1

    return orch, ctx_main, ctx_a, ctx_b, ctx_c
```

#### Step 3.2: Create Stale Ref
```python
def test_validation_prompts_stale_ref():
    """Step 3.2: Create a ref that's been pending beyond staleness threshold."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_main = orch.create_root_context()
    ctx_stale = orch.create_root_context()

    # Add ref and manually backdate its created_at
    orch.add_cross_ref(ctx_main, ctx_stale, ref_type="related_to", suggested_by="test")

    # Manually backdate (simulate old ref)
    context = orch.get_context(ctx_main)
    metadata = context.cross_sidebar_refs[ctx_stale]
    old_date = (datetime.now() - timedelta(days=5)).isoformat()
    metadata["created_at"] = old_date

    # ACTION
    result = orch.get_validation_prompts(
        current_context_id=ctx_main,
        citing_refs=[],
        exchange_created_refs=[]
    )

    # ASSERTIONS
    # Should appear in scratchpad_prompts with staleness urgency
    stale_prompt = next(
        (p for p in result["scratchpad_prompts"]
         if p["target_context_id"] == ctx_stale),
        None
    )
    assert stale_prompt is not None
    assert any("stale" in r for r in stale_prompt["urgency_reasons"])
```

#### Step 3.3: Test Inline vs Scratchpad Routing with citing_refs
```python
def test_validation_prompts_inline_vs_scratchpad():
    """Step 3.3: Citing refs go inline, others go to scratchpad."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_main = orch.create_root_context()
    ctx_cited = orch.create_root_context()  # Will be cited
    ctx_not_cited = orch.create_root_context()  # Won't be cited

    # Create refs
    orch.add_cross_ref(ctx_main, ctx_cited, ref_type="cites", confidence=0.5, suggested_by="test")
    orch.add_cross_ref(ctx_main, ctx_not_cited, ref_type="related_to", confidence=0.5, suggested_by="test")

    # ACTION - with citing_refs specified
    citing_ref_key = f"{ctx_main}:{ctx_cited}"
    result = orch.get_validation_prompts(
        current_context_id=ctx_main,
        citing_refs=[citing_ref_key],
        exchange_created_refs=[]
    )

    # ASSERTIONS
    assert result["success"] == True

    # Cited ref should be in inline_prompts
    inline_ids = [p["target_context_id"] for p in result["inline_prompts"]]
    assert ctx_cited in inline_ids

    # Non-cited ref should be in scratchpad_prompts
    scratchpad_ids = [p["target_context_id"] for p in result["scratchpad_prompts"]]
    assert ctx_not_cited in scratchpad_ids
```

#### Step 3.4: Verify Urgency Score Calculation
```python
def test_validation_prompts_urgency_scoring():
    """Step 3.4: Verify urgency scores calculated correctly."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_main = orch.create_root_context()
    ctx_target = orch.create_root_context()

    # Create cluster-flagged, low-confidence ref
    orch.add_cross_ref(ctx_main, ctx_target, ref_type="related_to",
                       confidence=0.3, suggested_by="s1")
    orch.add_cross_ref(ctx_main, ctx_target, ref_type="related_to", suggested_by="s2")
    orch.add_cross_ref(ctx_main, ctx_target, ref_type="related_to", suggested_by="s3")

    # ACTION - query with this ref being cited
    citing_ref_key = f"{ctx_main}:{ctx_target}"
    result = orch.get_validation_prompts(
        current_context_id=ctx_main,
        citing_refs=[citing_ref_key],
        exchange_created_refs=[citing_ref_key]
    )

    # ASSERTIONS
    prompt = result["inline_prompts"][0]  # Should be inline (being cited)

    # Expected urgency components:
    # - actively_citing: +100
    # - created_this_exchange: +50
    # - cluster_flagged: +30
    # - low_confidence: +20
    # - urgent_priority: +25 (auto-set by clustering)

    assert prompt["urgency_score"] >= 225  # At least these signals
    assert "actively_citing" in prompt["urgency_reasons"]
    assert "created_this_exchange" in prompt["urgency_reasons"]
    assert any("cluster_flagged" in r for r in prompt["urgency_reasons"])
    assert any("low_confidence" in r for r in prompt["urgency_reasons"])
```

#### Step 3.5: Verify No Prompts for Already-Validated Refs
```python
def test_validation_prompts_excludes_validated():
    """Step 3.5: Already-validated refs don't appear in prompts."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_main = orch.create_root_context()
    ctx_validated = orch.create_root_context()
    ctx_unvalidated = orch.create_root_context()

    # Create refs
    orch.add_cross_ref(ctx_main, ctx_validated, confidence=0.5, suggested_by="test")
    orch.add_cross_ref(ctx_main, ctx_unvalidated, confidence=0.5, suggested_by="test")

    # Validate one
    orch.validate_cross_ref(ctx_main, ctx_validated, validation_state="true")

    # ACTION
    result = orch.get_validation_prompts(current_context_id=ctx_main)

    # ASSERTIONS
    all_targets = (
        [p["target_context_id"] for p in result["inline_prompts"]] +
        [p["target_context_id"] for p in result["scratchpad_prompts"]]
    )

    assert ctx_validated not in all_targets  # Validated excluded
    assert ctx_unvalidated in all_targets  # Unvalidated included
```

### Setup/Teardown Requirements
```python
def setup_function():
    reset_orchestrator()

def teardown_function():
    reset_orchestrator()
```

---

## Flow 4: Yarn Board Render Flow

### Flow Name
`test_yarn_board_render_flow`

### Description
Tests the yarn board rendering with point position management (board vs cushion).

### Step-by-Step Sequence

#### Step 4.1: Create Context with Children and Cross-Refs
```python
def test_yarn_board_setup():
    """Step 4.1: Set up context with children and cross-refs for rendering."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)

    # Create parent with children
    parent_id = orch.create_root_context(task_description="Parent context")
    child1_id = orch.spawn_sidebar(parent_id, "Child 1")
    child2_id = orch.spawn_sidebar(parent_id, "Child 2")

    # Create another context and cross-ref to it
    other_id = orch.create_root_context(task_description="Other context")
    orch.add_cross_ref(parent_id, other_id, ref_type="related_to", suggested_by="test")

    # ASSERTIONS - setup verification
    parent = orch.get_context(parent_id)
    assert len(parent.child_sidebar_ids) == 2
    assert len(parent.cross_sidebar_refs) >= 1

    return orch, parent_id, child1_id, child2_id, other_id
```

#### Step 4.2: Save Some Point Positions
```python
def test_yarn_board_save_positions():
    """Step 4.2: Save positions for some points (others stay in cushion)."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    parent_id = orch.create_root_context()
    child1_id = orch.spawn_sidebar(parent_id, "Child 1")
    other_id = orch.create_root_context()
    orch.add_cross_ref(parent_id, other_id, ref_type="related_to", suggested_by="test")

    # ACTION - Save position for parent point only
    orch.update_point_position(
        context_id=parent_id,
        point_id=f"context:{parent_id}",
        x=100.0,
        y=200.0,
        collapsed=False
    )

    # ASSERTIONS
    layout = orch.get_yarn_layout(parent_id)
    assert layout["success"] == True
    positions = layout["layout"]["point_positions"]
    assert f"context:{parent_id}" in positions
    assert positions[f"context:{parent_id}"]["x"] == 100.0
    assert positions[f"context:{parent_id}"]["y"] == 200.0
```

#### Step 4.3: Call render_yarn_board
```python
def test_yarn_board_render():
    """Step 4.3: Render yarn board and verify structure."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    parent_id = orch.create_root_context()
    child1_id = orch.spawn_sidebar(parent_id, "Child 1")
    other_id = orch.create_root_context()
    orch.add_cross_ref(parent_id, other_id, ref_type="related_to", suggested_by="test")

    # Save position for parent only
    orch.update_point_position(parent_id, f"context:{parent_id}", x=100.0, y=200.0)

    # ACTION
    result = orch.render_yarn_board(parent_id)

    # ASSERTIONS
    assert result["success"] == True
    assert result["context_id"] == parent_id
    assert "points" in result
    assert "connections" in result
    assert "cushion" in result
    assert "type_colors" in result
```

#### Step 4.4: Verify Points with Positions Go to "points"
```python
def test_yarn_board_positioned_in_points():
    """Step 4.4: Points with saved positions appear in 'points' list."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    parent_id = orch.create_root_context()
    child_id = orch.spawn_sidebar(parent_id, "Child")

    # Position the parent
    parent_point_id = f"context:{parent_id}"
    orch.update_point_position(parent_id, parent_point_id, x=50.0, y=75.0)

    # ACTION
    result = orch.render_yarn_board(parent_id)

    # ASSERTIONS
    points = result["points"]
    point_ids = [p["id"] for p in points]

    assert parent_point_id in point_ids

    # Verify position data is present
    parent_point = next(p for p in points if p["id"] == parent_point_id)
    assert parent_point["x"] == 50.0
    assert parent_point["y"] == 75.0
```

#### Step 4.5: Verify Points without Positions Go to "cushion"
```python
def test_yarn_board_unpositioned_in_cushion():
    """Step 4.5: Points without positions appear in 'cushion' list."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    parent_id = orch.create_root_context()
    child_id = orch.spawn_sidebar(parent_id, "Child")

    # Position ONLY the parent, not the child
    orch.update_point_position(parent_id, f"context:{parent_id}", x=50.0, y=75.0)

    # ACTION
    result = orch.render_yarn_board(parent_id)

    # ASSERTIONS
    cushion = result["cushion"]
    cushion_ids = [p["id"] for p in cushion]

    # Child has no position -> should be in cushion
    child_point_id = f"context:{child_id}"
    assert child_point_id in cushion_ids

    # Cushion items should NOT have x/y
    child_in_cushion = next(p for p in cushion if p["id"] == child_point_id)
    assert "x" not in child_in_cushion
    assert "y" not in child_in_cushion
```

#### Step 4.6: Verify Point ID Format Convention
```python
def test_yarn_board_point_id_format():
    """Step 4.6: Verify point IDs follow convention (context:ID, crossref:A:B)."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    ctx_a = orch.create_root_context()
    ctx_b = orch.create_root_context()
    orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by="test")

    # ACTION
    result = orch.render_yarn_board(ctx_a)

    # ASSERTIONS
    all_point_ids = (
        [p["id"] for p in result["points"]] +
        [p["id"] for p in result["cushion"]]
    )

    # Context points should be "context:{sidebar_id}"
    context_points = [pid for pid in all_point_ids if pid.startswith("context:")]
    assert len(context_points) >= 1
    for cp in context_points:
        assert cp.startswith("context:")
        # ID part should be like SB-1
        id_part = cp.split(":", 1)[1]
        assert id_part.startswith("SB-") or id_part.startswith("ROOT")

    # Cross-ref points should be "crossref:{sorted_a}:{sorted_b}"
    crossref_points = [pid for pid in all_point_ids if pid.startswith("crossref:")]
    assert len(crossref_points) >= 1
    for xp in crossref_points:
        parts = xp.split(":")
        assert parts[0] == "crossref"
        # Should have exactly 3 parts: crossref, id1, id2
        assert len(parts) == 3
```

#### Step 4.7: Verify Connections Structure
```python
def test_yarn_board_connections():
    """Step 4.7: Verify connections link points correctly."""
    # SETUP
    orch = ConversationOrchestrator(auto_load=False)
    parent_id = orch.create_root_context()
    child_id = orch.spawn_sidebar(parent_id, "Child")

    # ACTION
    result = orch.render_yarn_board(parent_id)

    # ASSERTIONS
    connections = result["connections"]

    # Should have parent->child connection
    parent_child_conn = next(
        (c for c in connections
         if c["from_id"] == f"context:{parent_id}"
         and c["to_id"] == f"context:{child_id}"),
        None
    )
    assert parent_child_conn is not None
    assert parent_child_conn["ref_type"] == "parent_child"
```

### Setup/Teardown Requirements
```python
def setup_function():
    reset_orchestrator()

def teardown_function():
    reset_orchestrator()
```

---

## Flow 5: Redis Failover Flow

### Flow Name
`test_redis_failover_flow`

### Description
Tests graceful degradation and recovery when Redis becomes unavailable and then reconnects.

### Step-by-Step Sequence

#### Step 5.1: Start with Redis Connected
```python
def test_redis_connected_state():
    """Step 5.1: Verify operations work normally with Redis connected."""
    # SETUP
    client = RedisClient()

    # Skip if Redis not actually running
    if not client.is_connected():
        pytest.skip("Redis not available for integration test")

    # ACTION
    health = client.health_check()

    # ASSERTIONS
    assert health["connected"] == True
    assert health["status"] == "healthy"
```

#### Step 5.2: Queue Messages with Redis Connected
```python
def test_redis_queue_messages_connected(mock_redis):
    """Step 5.2: Queue messages successfully with Redis available."""
    # SETUP
    mock_redis.is_connected.return_value = True
    mock_redis.queue_for_agent.return_value = True

    with patch('datashapes.redis_interface', mock_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        entry = {
            "entry_id": "ENTRY-FAILOVER-001",
            "content": "Test message",
            "entry_type": "question",
            "submitted_by": "test"
        }

        # ACTION
        result = orch.route_scratchpad_entry(entry, ctx_id)

        # ASSERTIONS
        assert result["success"] == True
        assert result["queued_to_redis"] == True
        mock_redis.queue_for_agent.assert_called()
```

#### Step 5.3: Simulate Redis Disconnect
```python
def test_redis_disconnect_simulation():
    """Step 5.3: Simulate Redis going offline mid-operation."""
    # SETUP - Start connected, then disconnect
    mock_redis = MagicMock()
    connection_state = {"connected": True}

    def is_connected():
        return connection_state["connected"]

    def queue_for_agent(agent_id, message):
        if not connection_state["connected"]:
            return False
        return True

    mock_redis.is_connected = is_connected
    mock_redis.queue_for_agent = queue_for_agent
    mock_redis.get_agent_queue.return_value = []

    with patch('datashapes.redis_interface', mock_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        # First message - connected
        entry1 = {"entry_id": "E1", "content": "First", "entry_type": "question", "submitted_by": "test"}
        result1 = orch.route_scratchpad_entry(entry1, ctx_id)
        assert result1["queued_to_redis"] == True

        # ACTION - Disconnect Redis
        connection_state["connected"] = False

        # Second message - disconnected
        entry2 = {"entry_id": "E2", "content": "Second", "entry_type": "question", "submitted_by": "test"}
        result2 = orch.route_scratchpad_entry(entry2, ctx_id)

        # ASSERTIONS
        assert result2["success"] == True  # Graceful degradation
        assert result2["queued_to_redis"] == False  # But not in Redis
```

#### Step 5.4: Verify Operations Gracefully Degrade
```python
def test_redis_graceful_degradation(disconnected_redis):
    """Step 5.4: Verify all operations degrade gracefully when Redis down."""
    # SETUP
    with patch('datashapes.redis_interface', disconnected_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        # ACTION - Try various Redis-dependent operations

        # 1. Route scratchpad entry
        entry = {"entry_id": "E1", "content": "Test", "entry_type": "question", "submitted_by": "test"}
        route_result = orch.route_scratchpad_entry(entry, ctx_id)

        # 2. Get agent queue
        queue_result = orch.get_agent_queue("AGENT-curator")

        # 3. Set grabbed state
        grabbed_result = orch.set_grabbed(ctx_id, "context:SB-1", True)

        # 4. Get yarn state
        yarn_result = orch.get_yarn_state(ctx_id)

        # ASSERTIONS - All should succeed with degraded behavior
        assert route_result["success"] == True
        assert route_result["queued_to_redis"] == False

        assert queue_result["success"] == True
        assert queue_result["queue"] == []  # Empty when Redis down

        assert grabbed_result["success"] == True
        assert grabbed_result["persisted"] == False  # Not persisted without Redis

        assert yarn_result["success"] == True
        assert yarn_result["source"] == "default"  # Fallback source
```

#### Step 5.5: Reconnect Redis
```python
def test_redis_reconnect():
    """Step 5.5: Verify operations resume after Redis reconnects."""
    # SETUP
    mock_redis = MagicMock()
    connection_state = {"connected": False}
    queued_messages = []

    def is_connected():
        return connection_state["connected"]

    def queue_for_agent(agent_id, message):
        if not connection_state["connected"]:
            return False
        queued_messages.append((agent_id, message))
        return True

    def get_agent_queue(agent_id):
        if not connection_state["connected"]:
            return []
        return [m for a, m in queued_messages if a == agent_id]

    mock_redis.is_connected = is_connected
    mock_redis.queue_for_agent = queue_for_agent
    mock_redis.get_agent_queue = get_agent_queue

    with patch('datashapes.redis_interface', mock_redis):
        orch = ConversationOrchestrator(auto_load=False)
        ctx_id = orch.create_root_context()

        # Start disconnected
        entry_offline = {"entry_id": "E-OFF", "content": "Offline", "entry_type": "question", "submitted_by": "test"}
        result_offline = orch.route_scratchpad_entry(entry_offline, ctx_id)
        assert result_offline["queued_to_redis"] == False

        # ACTION - Reconnect
        connection_state["connected"] = True

        # Queue message after reconnect
        entry_online = {"entry_id": "E-ON", "content": "Online", "entry_type": "question", "submitted_by": "test"}
        result_online = orch.route_scratchpad_entry(entry_online, ctx_id)

        # ASSERTIONS
        assert result_online["success"] == True
        assert result_online["queued_to_redis"] == True

        # Verify message is in queue
        queue = orch.get_agent_queue("AGENT-curator")
        assert queue["count"] >= 1
```

#### Step 5.6: Test RedisClient Reconnection
```python
def test_redis_client_reconnection():
    """Step 5.6: Test RedisClient.reconnect() functionality."""
    # This test requires actual Redis or appropriate mocking

    # SETUP
    client = RedisClient()
    initial_state = client.is_connected()

    # ACTION
    reconnect_result = client.reconnect()

    # ASSERTIONS
    # If Redis is available, should reconnect
    # If not, should return False gracefully
    assert isinstance(reconnect_result, bool)

    # Health check should reflect state
    health = client.health_check()
    assert health["connected"] == reconnect_result
```

#### Step 5.7: Test Health Check During Failure
```python
def test_redis_health_check_during_failure():
    """Step 5.7: Health check returns degraded status during failure."""
    # SETUP
    client = RedisClient()

    # Force disconnection state
    client._connected = False
    client._client = None

    # ACTION
    health = client.health_check()

    # ASSERTIONS
    assert health["connected"] == False
    assert health["status"] == "disconnected"
    assert "host" in health
    assert "port" in health
```

### Setup/Teardown Requirements
```python
@pytest.fixture(autouse=True)
def reset_redis_state():
    """Reset Redis client state between tests."""
    yield
    # Cleanup if needed

def setup_function():
    reset_orchestrator()

def teardown_function():
    reset_orchestrator()
```

---

## Integration Test Suite Structure

### Recommended File Organization
```
tests/
  integration/
    test_phase5_flows.py           # All flows in one file
    conftest.py                    # Shared fixtures

  # OR split by flow:
  integration/
    test_scratchpad_routing.py     # Flow 1
    test_clustering.py             # Flow 2
    test_validation_prompts.py     # Flow 3
    test_yarn_board.py             # Flow 4
    test_redis_failover.py         # Flow 5
    conftest.py                    # Shared fixtures
```

### Test Markers
```python
# In conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "redis: marks tests requiring Redis")
    config.addinivalue_line("markers", "integration: marks integration tests")
```

### Running Tests
```bash
# Run all Phase 5 integration tests
pytest tests/integration/ -v

# Run only non-Redis tests (when Redis unavailable)
pytest tests/integration/ -v -m "not redis"

# Run with coverage
pytest tests/integration/ --cov=conversation_orchestrator --cov=redis_client
```

---

## Summary of Assertions by Flow

### Flow 1: Scratchpad -> Curator -> Agent
| Step | Key Assertions |
|------|----------------|
| 1.1 | Entry creates successfully, routes to curator |
| 1.2 | Message queued with correct type and entry data |
| 1.3 | Approved entries route to inferred destination |
| 1.4 | Content keywords map to correct agent specialties |
| 1.5 | Graceful degradation when Redis unavailable |
| 1.6 | quick_notes bypass routing when no explicit route |

### Flow 2: Clustering Trigger
| Step | Key Assertions |
|------|----------------|
| 2.1 | First source creates ref, no clustering |
| 2.2 | Second source adds to sources list |
| 2.3 | Third source triggers cluster_flagged=True |
| 2.4 | validation_priority auto-bumped to "urgent" |
| 2.5 | get_cluster_flagged_refs returns flagged items |
| 2.6 | Validated refs excluded by default |

### Flow 3: Validation Prompts
| Step | Key Assertions |
|------|----------------|
| 3.1 | Setup refs with various urgency signals |
| 3.2 | Stale refs have staleness urgency reason |
| 3.3 | Citing refs go inline, others to scratchpad |
| 3.4 | Urgency scores calculated with all signals |
| 3.5 | Validated refs excluded from prompts |

### Flow 4: Yarn Board Render
| Step | Key Assertions |
|------|----------------|
| 4.1 | Context created with children and cross-refs |
| 4.2 | Positions saved to layout correctly |
| 4.3 | render_yarn_board returns expected structure |
| 4.4 | Positioned points in "points" list with x/y |
| 4.5 | Unpositioned points in "cushion" without x/y |
| 4.6 | Point IDs follow convention (context:, crossref:) |
| 4.7 | Connections link points with correct ref_types |

### Flow 5: Redis Failover
| Step | Key Assertions |
|------|----------------|
| 5.1 | Health check reports connected when online |
| 5.2 | Messages queue successfully when connected |
| 5.3 | Operations handle mid-operation disconnect |
| 5.4 | All operations degrade gracefully |
| 5.5 | Operations resume after reconnection |
| 5.6 | RedisClient.reconnect() works correctly |
| 5.7 | Health check reports degraded during failure |

---

## Notes for Implementation

### Two-Stage Testing Protocol
As per CLAUDE.md testing protocol:
1. **Stage 1 (Unit Logic)**: Test functions directly (e.g., `orch._infer_destination()`)
2. **Stage 2 (In-Field Simulation)**: Test full command flow through routes

### Redis Testing Considerations
- Use `pytest.skip()` for tests requiring live Redis when unavailable
- Use mocks for deterministic behavior in CI
- Consider testcontainers for realistic Redis testing

### Performance Considerations
- Clustering tests should verify threshold is respected (not triggering early)
- Yarn board rendering should handle large numbers of points gracefully
- Redis reconnection tests should verify no message loss patterns
