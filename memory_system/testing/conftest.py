"""
Phase 5 Test Configuration and Fixtures

Shared fixtures for yarn board, queue routing, clustering, validation prompts,
and Redis integration tests.

See TEST_REQUIREMENTS_PHASE5_CONSOLIDATED.md for test plan.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# PYTEST MARKERS
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: requires real services (Redis, etc.)")
    config.addinivalue_line("markers", "slow: long-running tests")
    config.addinivalue_line("markers", "critical: must-pass tests for Phase 5 functionality")
    config.addinivalue_line("markers", "redis: requires Redis connection")
    config.addinivalue_line("markers", "persistence: tests data persistence/survival")


# =============================================================================
# KEY CONSTANTS (must match orchestrator)
# =============================================================================

CLUSTERING_THRESHOLD = 3
VALIDATION_CONFIDENCE_THRESHOLD = 0.7
STALENESS_DAYS = 3
CURATOR_AGENT_ID = "AGENT-curator"


# =============================================================================
# ORCHESTRATOR FIXTURES
# =============================================================================

@pytest.fixture
def fresh_orchestrator():
    """
    Reset and return a fresh orchestrator instance.

    Uses auto_load=False to skip loading from SQLite persistence,
    giving us a clean slate for each test.
    """
    from conversation_orchestrator import ConversationOrchestrator, reset_orchestrator

    # Reset global state
    reset_orchestrator()

    # Create fresh instance without loading persisted state
    orch = ConversationOrchestrator(auto_load=False)

    return orch


@pytest.fixture
def orchestrator_with_root(fresh_orchestrator):
    """
    Orchestrator with a single root context already created.

    Common setup for tests that need at least one context to exist.
    """
    orch = fresh_orchestrator
    root_id = orch.create_root_context(task_description="Test Root Context")
    return orch, root_id


@pytest.fixture
def context_pair(fresh_orchestrator):
    """
    Two independent root contexts for cross-ref testing.

    Returns (orchestrator, context_a_id, context_b_id)
    """
    orch = fresh_orchestrator
    ctx_a = orch.create_root_context(task_description="Context A - Source")
    ctx_b = orch.create_root_context(task_description="Context B - Target")
    return orch, ctx_a, ctx_b


@pytest.fixture
def context_tree(fresh_orchestrator):
    """
    A three-level context tree for hierarchy tests.

    Structure:
        root
        ├── child1
        │   └── grandchild1
        └── child2

    Returns (orchestrator, {root, child1, child2, grandchild1})
    """
    orch = fresh_orchestrator
    root = orch.create_root_context(task_description="Root")
    child1 = orch.spawn_sidebar(parent_id=root, reason="Child 1")
    child2 = orch.spawn_sidebar(parent_id=root, reason="Child 2")
    grandchild1 = orch.spawn_sidebar(parent_id=child1, reason="Grandchild 1")

    return orch, {
        "root": root,
        "child1": child1,
        "child2": child2,
        "grandchild1": grandchild1
    }


# =============================================================================
# REDIS FIXTURES
# =============================================================================

@pytest.fixture
def mock_redis_interface():
    """
    Mock the redis_interface stub in datashapes.

    All Redis operations return safe defaults.
    """
    with patch('datashapes.redis_interface') as mock:
        # Yarn board state
        mock.get_yarn_state.return_value = None
        mock.set_yarn_state.return_value = False
        mock.set_grabbed.return_value = False
        mock.get_grabbed_by.return_value = None
        mock.get_all_grabbed.return_value = {}

        # Agent operations
        mock.get_agent_status.return_value = None
        mock.set_agent_busy.return_value = False
        mock.queue_for_agent.return_value = False
        mock.get_agent_queue.return_value = []
        mock.clear_agent_queue.return_value = False

        # Pub/sub
        mock.notify_priority_change.return_value = False
        mock.subscribe_to_context.return_value = False
        mock.unsubscribe_from_context.return_value = False

        yield mock


@pytest.fixture
def connected_redis_client():
    """
    RedisClient with working fakeredis backend.

    Requires: pip install fakeredis
    """
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed - run: pip install fakeredis")

    with patch('redis.Redis', fakeredis.FakeRedis):
        from redis_client import RedisClient
        client = RedisClient()
        client._connected = True
        client._client = fakeredis.FakeRedis(decode_responses=True)
        yield client


@pytest.fixture
def disconnected_redis_client():
    """
    RedisClient in disconnected/stub mode.

    All operations should return safe defaults.
    Works even when redis module is not installed.
    """
    from redis_client import RedisClient

    # Create client directly and force disconnected state
    # Don't try to patch redis.Redis - it may not exist
    client = RedisClient.__new__(RedisClient)
    client._client = None
    client._connected = False
    client._pubsub = None
    yield client


# =============================================================================
# SCRATCHPAD / QUEUE FIXTURES
# =============================================================================

@pytest.fixture
def sample_finding_entry():
    """A sample ScratchpadEntry dict for queue routing tests."""
    return {
        "id": "ENTRY-001",
        "entry_type": "finding",
        "content": "Discovered potential memory leak in context switching",
        "created_at": datetime.now().isoformat(),
        "source_context_id": "SB-1",
        "tags": ["bug", "memory"],
        "priority": "normal",
        "status": "pending"
    }


@pytest.fixture
def sample_question_entry():
    """A sample question entry for queue routing tests."""
    return {
        "id": "ENTRY-002",
        "entry_type": "question",
        "content": "Should we use Redis or in-memory caching for hot state?",
        "created_at": datetime.now().isoformat(),
        "source_context_id": "SB-1",
        "tags": ["architecture", "research"],
        "priority": "normal",
        "status": "pending"
    }


@pytest.fixture
def sample_quick_note_entry():
    """A sample quick_note entry (should bypass curator)."""
    return {
        "id": "ENTRY-003",
        "entry_type": "quick_note",
        "content": "Remember to check auth token expiry",
        "created_at": datetime.now().isoformat(),
        "source_context_id": "SB-1",
        "tags": [],
        "priority": "low",
        "status": "pending"
    }


# =============================================================================
# CROSS-REF FIXTURES
# =============================================================================

@pytest.fixture
def cross_ref_with_sources(context_pair):
    """
    Set up a cross-ref with multiple suggested sources for clustering tests.

    Returns (orchestrator, source_id, target_id, ref_metadata)
    """
    orch, ctx_a, ctx_b = context_pair

    # Add cross-ref from A -> B
    result = orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="related_to",
        reason="Both discuss authentication",
        confidence=0.6,
        discovery_method="explicit",
        strength="normal"
    )

    return orch, ctx_a, ctx_b


@pytest.fixture
def stale_cross_ref(context_pair):
    """
    Cross-ref that is older than STALENESS_DAYS for urgency testing.
    """
    orch, ctx_a, ctx_b = context_pair

    # Add cross-ref
    orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="related_to",
        reason="Old connection",
        confidence=0.5
    )

    # Manually backdate the created_at in metadata
    ctx = orch.get_context(ctx_a)
    if ctx and ctx_b in ctx.cross_sidebar_refs:
        metadata = ctx.cross_sidebar_refs[ctx_b]
        if hasattr(metadata, 'created_at'):
            metadata.created_at = datetime.now() - timedelta(days=5)

    return orch, ctx_a, ctx_b


# =============================================================================
# YARN BOARD FIXTURES
# =============================================================================

@pytest.fixture
def yarn_board_with_positions(orchestrator_with_root):
    """
    Orchestrator with a context that has yarn board positions saved.
    """
    orch, root_id = orchestrator_with_root

    # Save some positions
    orch.save_yarn_layout(
        context_id=root_id,
        point_positions={
            f"context:{root_id}": {"x": 100, "y": 100, "collapsed": False}
        },
        zoom_level=1.0
    )

    return orch, root_id


# =============================================================================
# API CLIENT FIXTURES
# =============================================================================

@pytest.fixture
def api_client():
    """
    FastAPI TestClient for API endpoint tests.

    Requires: pip install httpx
    """
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi.testclient not available")

    from api_server_bridge import app
    return TestClient(app)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def add_cross_ref_source(orch, source_id: str, target_id: str, suggested_by: str) -> Dict:
    """
    Helper to add a source to an existing cross-ref's suggested_sources.

    This simulates multiple agents suggesting the same connection.
    """
    # Get current metadata
    ctx = orch.get_context(source_id)
    if not ctx or target_id not in ctx.cross_sidebar_refs:
        # Create the ref first
        orch.add_cross_ref(
            source_context_id=source_id,
            target_context_id=target_id,
            ref_type="related_to",
            reason="Test connection",
            suggested_by=suggested_by
        )
        ctx = orch.get_context(source_id)

    # Add another source
    metadata = ctx.cross_sidebar_refs.get(target_id)
    if metadata and hasattr(metadata, 'suggested_sources'):
        # Check if source already exists
        existing_sources = [s.get('source_id') for s in metadata.suggested_sources]
        if suggested_by not in existing_sources:
            metadata.suggested_sources.append({
                "source_id": suggested_by,
                "suggested_at": datetime.now().isoformat()
            })

            # Check clustering threshold
            if len(metadata.suggested_sources) >= CLUSTERING_THRESHOLD:
                metadata.cluster_flagged = True
                metadata.validation_priority = "urgent"

    return {"sources": len(metadata.suggested_sources) if metadata else 0}


def create_contradicting_refs(orch, ctx_a: str, ctx_b: str) -> Dict:
    """
    Helper to create a pair of contradicting cross-refs.

    Creates: A implements B AND A contradicts B (which is logically impossible)
    """
    orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="implements",
        reason="A implements B's design",
        confidence=0.8
    )

    orch.add_cross_ref(
        source_context_id=ctx_a,
        target_context_id=ctx_b,
        ref_type="contradicts",
        reason="A contradicts B's approach",
        confidence=0.7
    )

    return {"implements": True, "contradicts": True}
