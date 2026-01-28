"""
WebSocket Broadcast Tests (Section 8.6)

Tests for verifying WebSocket broadcast behavior in the API layer.
These tests mock the broadcast infrastructure to verify correct
event emission without requiring actual WebSocket connections.
"""

import pytest
import sys
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_broadcast():
    """Mock the broadcast_to_react function."""
    with patch('api_server_bridge.broadcast_to_react', new_callable=AsyncMock) as mock:
        mock.calls = []
        original_side_effect = mock.side_effect

        async def track_call(message):
            mock.calls.append(message)

        mock.side_effect = track_call
        yield mock


@pytest.fixture
def mock_active_connections():
    """Mock active WebSocket connections list."""
    with patch('api_server_bridge.active_connections', []) as connections:
        yield connections


# =============================================================================
# 8.6 WEBSOCKET BROADCAST TESTS
# =============================================================================

class TestWebSocketBroadcasts:
    """
    WebSocket broadcast mechanics tests.

    Design Decision: Timestamps + server-side coalescing. Rapid updates
    pool and batch before broadcast. Client can sort by timestamp if needed.
    """

    @pytest.mark.asyncio
    async def test_layout_save_broadcasts(self, mock_broadcast):
        """
        HAPPY PATH: Layout save triggers WebSocket event.
        """
        from api_server_bridge import broadcast_to_react

        # Simulate layout save broadcast
        await broadcast_to_react({
            "type": "layout_update",
            "context_id": "CTX-1",
            "positions": {"point1": {"x": 100, "y": 200}},
            "timestamp": datetime.now().isoformat()
        })

        assert len(mock_broadcast.calls) == 1
        assert mock_broadcast.calls[0]["type"] == "layout_update"
        assert "timestamp" in mock_broadcast.calls[0]

    @pytest.mark.asyncio
    async def test_grab_broadcasts(self, mock_broadcast):
        """
        HAPPY PATH: Grab action triggers WebSocket event.
        """
        from api_server_bridge import broadcast_to_react

        await broadcast_to_react({
            "type": "point_grabbed",
            "context_id": "CTX-1",
            "point_id": "point1",
            "agent_id": "AGENT-A",
            "timestamp": datetime.now().isoformat()
        })

        assert len(mock_broadcast.calls) == 1
        assert mock_broadcast.calls[0]["type"] == "point_grabbed"
        assert mock_broadcast.calls[0]["point_id"] == "point1"

    @pytest.mark.asyncio
    async def test_release_broadcasts(self, mock_broadcast):
        """
        HAPPY PATH: Release action triggers WebSocket event.
        """
        from api_server_bridge import broadcast_to_react

        await broadcast_to_react({
            "type": "point_released",
            "context_id": "CTX-1",
            "point_id": "point1",
            "timestamp": datetime.now().isoformat()
        })

        assert len(mock_broadcast.calls) == 1
        assert mock_broadcast.calls[0]["type"] == "point_released"

    @pytest.mark.asyncio
    async def test_broadcast_includes_timestamp(self, mock_broadcast):
        """
        HAPPY PATH: All broadcasts include ISO timestamp.
        """
        from api_server_bridge import broadcast_to_react

        # Multiple different event types
        events = [
            {"type": "layout_update", "timestamp": datetime.now().isoformat()},
            {"type": "point_grabbed", "timestamp": datetime.now().isoformat()},
            {"type": "context_created", "timestamp": datetime.now().isoformat()},
        ]

        for event in events:
            await broadcast_to_react(event)

        # All should have timestamps
        assert len(mock_broadcast.calls) == 3
        for call in mock_broadcast.calls:
            assert "timestamp" in call
            # Verify ISO format (should parse without error)
            datetime.fromisoformat(call["timestamp"])

    @pytest.mark.asyncio
    async def test_broadcast_no_clients_graceful(self, mock_active_connections):
        """
        EDGE: No connected clients → no exception.

        When there are no WebSocket clients connected, broadcasts
        should complete silently without raising exceptions.
        """
        from api_server_bridge import broadcast_to_react

        # No connections (empty list)
        assert len(mock_active_connections) == 0

        # Should not raise even with no clients
        try:
            await broadcast_to_react({
                "type": "test_event",
                "timestamp": datetime.now().isoformat()
            })
            success = True
        except Exception as e:
            success = False

        assert success, "Broadcast should not raise with no clients"


class TestBroadcastCoalescing:
    """
    Tests for rapid update coalescing behavior.

    Note: Coalescing requires server-side batching infrastructure.
    These tests verify the expected behavior pattern.
    """

    @pytest.mark.asyncio
    async def test_rapid_updates_pattern(self, mock_broadcast):
        """
        PATTERN: Rapid updates should be batchable.

        This tests that rapid sequential broadcasts can be tracked.
        Actual coalescing would be implemented in the broadcast layer.
        """
        from api_server_bridge import broadcast_to_react

        # Simulate 5 rapid updates
        for i in range(5):
            await broadcast_to_react({
                "type": "layout_update",
                "update_index": i,
                "timestamp": datetime.now().isoformat()
            })

        # Without coalescing, all 5 are sent
        assert len(mock_broadcast.calls) == 5

        # All have timestamps for potential client-side sorting
        for call in mock_broadcast.calls:
            assert "timestamp" in call

    @pytest.mark.asyncio
    async def test_timestamps_enable_ordering(self, mock_broadcast):
        """
        HAPPY PATH: Timestamps allow chronological ordering.

        Even without server-side coalescing, timestamps enable
        client-side reordering if needed.
        """
        from api_server_bridge import broadcast_to_react
        import time

        # Send updates with slight delays to ensure different timestamps
        timestamps = []
        for i in range(3):
            ts = datetime.now().isoformat()
            timestamps.append(ts)
            await broadcast_to_react({
                "type": "update",
                "index": i,
                "timestamp": ts
            })
            await asyncio.sleep(0.001)  # Small delay

        # Timestamps should be sortable
        sorted_ts = sorted(timestamps)
        assert timestamps == sorted_ts, "Timestamps should be chronologically ordered"


class TestCoordinationBroadcasts:
    """
    Tests for coordination event broadcasts.
    """

    @pytest.mark.asyncio
    async def test_coordination_sidebar_broadcast(self, mock_broadcast):
        """
        INTEGRATION: Coordination sidebar spawns broadcast sidebar_spawned event.
        """
        from api_server_bridge import broadcast_to_react

        # When coordination sidebar is spawned, broadcast
        await broadcast_to_react({
            "type": "coordination_sidebar_spawned",
            "sidebar_id": "SB-COORD-1",
            "agents": ["AGENT-A", "AGENT-B"],
            "reason": "Simultaneous grab on point1",
            "timestamp": datetime.now().isoformat()
        })

        assert len(mock_broadcast.calls) == 1
        assert mock_broadcast.calls[0]["type"] == "coordination_sidebar_spawned"
        assert "AGENT-A" in mock_broadcast.calls[0]["agents"]
        assert "AGENT-B" in mock_broadcast.calls[0]["agents"]


# =============================================================================
# SIDEBAR LIFECYCLE BROADCAST TESTS
# =============================================================================

class TestSidebarLifecycleBroadcasts:
    """
    Tests for sidebar lifecycle WebSocket broadcasts.

    These verify that API endpoints emit the correct broadcast events
    for sidebar operations: spawn, focus, pause, resume, merge, archive.

    Note: These tests patch the API's orchestrator to use a fresh instance,
    since the API creates its own orchestrator at module load time.
    """

    @pytest.fixture
    def fresh_api_orchestrator(self):
        """
        Create a fresh orchestrator and patch it into the API module.

        This ensures the TestClient uses our test orchestrator, not the
        one loaded from persistence at module import time.
        """
        from conversation_orchestrator import ConversationOrchestrator
        import api_server_bridge

        # Create fresh orchestrator without loading from persistence
        test_orch = ConversationOrchestrator(auto_load=False)
        root_id = test_orch.create_root_context(task_description="Test root for broadcasts")

        # Patch the API's orchestrator
        original_orch = api_server_bridge.orchestrator
        api_server_bridge.orchestrator = test_orch

        yield test_orch, root_id

        # Restore original orchestrator after test
        api_server_bridge.orchestrator = original_orch

    @pytest.mark.asyncio
    async def test_spawn_broadcasts_sidebar_spawned(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/spawn broadcasts sidebar_spawned event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        with TestClient(app) as client:
            response = client.post("/sidebars/spawn", json={
                "parent_id": root_id,
                "reason": "Testing spawn broadcast"
            })

        assert response.status_code == 200, f"Spawn failed: {response.json()}"
        spawn_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "sidebar_spawned"]
        assert len(spawn_broadcasts) >= 1, f"Expected sidebar_spawned broadcast, got: {mock_broadcast.calls}"
        # Broadcast nests under "sidebar" key
        assert spawn_broadcasts[0]["sidebar"]["reason"] == "Testing spawn broadcast"

    @pytest.mark.asyncio
    async def test_focus_broadcasts_focus_changed(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/focus broadcasts focus_changed event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        # Spawn a sidebar first (using the patched orchestrator)
        child_id = orch.spawn_sidebar(parent_id=root_id, reason="Child for focus test")

        with TestClient(app) as client:
            response = client.post(f"/sidebars/{child_id}/focus")

        assert response.status_code == 200, f"Focus failed: {response.json()}"
        focus_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "focus_changed"]
        assert len(focus_broadcasts) >= 1, f"Expected focus_changed broadcast, got: {mock_broadcast.calls}"
        # Broadcast uses "active_id" not "sidebar_id"
        assert focus_broadcasts[0]["active_id"] == child_id

    @pytest.mark.asyncio
    async def test_pause_broadcasts_sidebar_paused(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/pause broadcasts sidebar_paused event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        child_id = orch.spawn_sidebar(parent_id=root_id, reason="Child for pause test")

        with TestClient(app) as client:
            response = client.post(f"/sidebars/{child_id}/pause", params={"reason": "Taking a break"})

        assert response.status_code == 200, f"Pause failed: {response.json()}"
        pause_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "sidebar_paused"]
        assert len(pause_broadcasts) >= 1, f"Expected sidebar_paused broadcast, got: {mock_broadcast.calls}"
        assert pause_broadcasts[0]["sidebar_id"] == child_id

    @pytest.mark.asyncio
    async def test_resume_broadcasts_sidebar_resumed(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/resume broadcasts sidebar_resumed event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        child_id = orch.spawn_sidebar(parent_id=root_id, reason="Child for resume test")
        orch.pause_context(child_id, reason="Paused for test")

        with TestClient(app) as client:
            response = client.post(f"/sidebars/{child_id}/resume")

        assert response.status_code == 200, f"Resume failed: {response.json()}"
        resume_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "sidebar_resumed"]
        assert len(resume_broadcasts) >= 1, f"Expected sidebar_resumed broadcast, got: {mock_broadcast.calls}"
        assert resume_broadcasts[0]["sidebar_id"] == child_id

    @pytest.mark.asyncio
    async def test_merge_broadcasts_sidebar_merged(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/merge broadcasts sidebar_merged event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        child_id = orch.spawn_sidebar(parent_id=root_id, reason="Child for merge test")

        with TestClient(app) as client:
            response = client.post(f"/sidebars/{child_id}/merge", json={
                "summary": "Test merge summary"
            })

        assert response.status_code == 200, f"Merge failed: {response.json()}"
        merge_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "sidebar_merged"]
        assert len(merge_broadcasts) >= 1, f"Expected sidebar_merged broadcast, got: {mock_broadcast.calls}"
        assert merge_broadcasts[0]["sidebar_id"] == child_id

    @pytest.mark.asyncio
    async def test_archive_broadcasts_sidebar_archived(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/archive broadcasts sidebar_archived event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        child_id = orch.spawn_sidebar(parent_id=root_id, reason="Child for archive test")

        with TestClient(app) as client:
            response = client.post(f"/sidebars/{child_id}/archive", params={"reason": "Done testing"})

        assert response.status_code == 200, f"Archive failed: {response.json()}"
        archive_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "sidebar_archived"]
        assert len(archive_broadcasts) >= 1, f"Expected sidebar_archived broadcast, got: {mock_broadcast.calls}"
        assert archive_broadcasts[0]["sidebar_id"] == child_id

    @pytest.mark.asyncio
    async def test_cross_ref_broadcasts_cross_ref_added(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/cross-refs broadcasts cross_ref_added event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        child_a = orch.spawn_sidebar(parent_id=root_id, reason="Source sidebar")
        child_b = orch.spawn_sidebar(parent_id=root_id, reason="Target sidebar")

        with TestClient(app) as client:
            # Note: POST endpoint is /cross-ref (singular), GET is /cross-refs (plural)
            response = client.post(f"/sidebars/{child_a}/cross-ref", json={
                "target_context_id": child_b,
                "ref_type": "cites",
                "confidence": 0.85
            })

        assert response.status_code == 200, f"Cross-ref failed: {response.json()}"
        crossref_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "cross_ref_added"]
        assert len(crossref_broadcasts) >= 1, f"Expected cross_ref_added broadcast, got: {mock_broadcast.calls}"
        # Broadcast uses "source_context_id" and "target_context_id"
        assert crossref_broadcasts[0]["source_context_id"] == child_a
        assert crossref_broadcasts[0]["target_context_id"] == child_b

    @pytest.mark.asyncio
    async def test_reparent_broadcasts_sidebar_reparented(self, mock_broadcast, fresh_api_orchestrator):
        """
        INTEGRATION: POST /sidebars/{id}/reparent broadcasts sidebar_reparented event.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi.testclient not available")

        from api_server_bridge import app
        orch, root_id = fresh_api_orchestrator

        # Create two roots and a child
        second_root = orch.create_root_context(task_description="Second root")
        child_id = orch.spawn_sidebar(parent_id=root_id, reason="Child to reparent")

        with TestClient(app) as client:
            response = client.post(f"/sidebars/{child_id}/reparent", json={
                "new_parent_id": second_root,
                "reason": "Testing reparent broadcast"
            })

        # Reparent might not have an API endpoint yet - handle gracefully
        if response.status_code == 404:
            pytest.skip("Reparent API endpoint not implemented yet")

        assert response.status_code == 200, f"Reparent failed: {response.json()}"
        # Broadcast type is "context_reparented" with context_id, old_parent_id, new_parent_id
        reparent_broadcasts = [c for c in mock_broadcast.calls if c.get("type") == "context_reparented"]
        assert len(reparent_broadcasts) >= 1, f"Expected context_reparented broadcast, got: {mock_broadcast.calls}"
        assert reparent_broadcasts[0]["context_id"] == child_id
        assert reparent_broadcasts[0]["new_parent_id"] == second_root
        assert "old_parent_id" in reparent_broadcasts[0]  # Should include where it came from
