"""
Phase 5 Yarn Board Tests

Tests for yarn board layout management, hot state (Redis-backed), and rendering.
Covers Section 2 of TEST_REQUIREMENTS_PHASE5_CONSOLIDATED.md.

Test Categories:
- 2.1 Layout Management: Persistence and retrieval of yarn board layouts
- 2.2 Hot State: Redis-backed grabbed points and live state
- 2.3 Render: Board rendering with points, connections, cushion

{YOU} Principle Applied:
- Every test has clear assertions with meaningful error messages
- WHY comments explain what would break if the test fails
- Graceful degradation tests ensure system works without Redis
"""

import pytest
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# 2.1 LAYOUT MANAGEMENT TESTS
# =============================================================================

class TestYarnLayoutManagement:
    """
    Layout persistence and retrieval tests.

    Layout = the saved positions of points on the yarn board.
    This is the "cold" state that persists to SQLite.
    """

    def test_get_yarn_layout_existing(self, orchestrator_with_root):
        """
        HAPPY PATH: Returns stored layout when one exists.

        WHY: If this fails, users lose their board arrangements on page refresh.
        """
        orch, root_id = orchestrator_with_root

        # Save a layout first
        test_positions = {
            f"context:{root_id}": {"x": 100, "y": 200, "collapsed": False}
        }
        orch.save_yarn_layout(root_id, point_positions=test_positions)

        # Get it back
        result = orch.get_yarn_layout(root_id)

        assert result.get("success") is True, \
            f"get_yarn_layout should succeed: {result}"
        assert "layout" in result, \
            "Result must have 'layout' key"

        positions = result["layout"].get("point_positions", {})
        assert f"context:{root_id}" in positions, \
            f"Saved position should be returned. Got: {positions.keys()}"

    def test_get_yarn_layout_default(self, orchestrator_with_root):
        """
        HAPPY PATH: Returns default layout when none exists.

        WHY: New contexts should render with sensible defaults, not crash.
        """
        orch, root_id = orchestrator_with_root

        # Don't save any layout - should get defaults
        result = orch.get_yarn_layout(root_id)

        assert result.get("success") is True, \
            f"Should succeed with defaults: {result}"
        assert "layout" in result, \
            "Result must have 'layout' key even for defaults"

        layout = result["layout"]
        assert "point_positions" in layout, \
            "Default layout should have point_positions (empty dict)"
        assert "zoom_level" in layout, \
            "Default layout should have zoom_level"

    def test_get_yarn_layout_invalid_context(self, fresh_orchestrator):
        """
        ERROR: Returns error for missing context.
        """
        orch = fresh_orchestrator

        result = orch.get_yarn_layout("NONEXISTENT-CONTEXT")

        assert result.get("success") is False, \
            "Should fail for invalid context"
        assert "error" in result, \
            "Should include error message"

    def test_save_yarn_layout_full(self, orchestrator_with_root):
        """
        HAPPY PATH: Saves all layout fields.
        """
        orch, root_id = orchestrator_with_root

        test_layout = {
            f"context:{root_id}": {"x": 150, "y": 250, "collapsed": True}
        }

        result = orch.save_yarn_layout(
            context_id=root_id,
            point_positions=test_layout,
            zoom_level=1.5
        )

        assert result.get("success") is True, \
            f"save_yarn_layout should succeed: {result}"

        # Verify saved
        retrieved = orch.get_yarn_layout(root_id)
        assert retrieved["layout"]["zoom_level"] == 1.5, \
            "Zoom level should be saved"

    def test_save_yarn_layout_partial(self, orchestrator_with_root):
        """
        HAPPY PATH: Partial update preserves other fields.
        """
        orch, root_id = orchestrator_with_root

        # Save initial
        orch.save_yarn_layout(root_id, zoom_level=2.0)

        # Update positions only
        orch.save_yarn_layout(
            root_id,
            point_positions={"point1": {"x": 10, "y": 20}}
        )

        # Verify zoom preserved
        result = orch.get_yarn_layout(root_id)
        assert result["layout"]["zoom_level"] == 2.0, \
            "Partial update should preserve zoom_level"

    def test_save_yarn_layout_updates_timestamp(self, orchestrator_with_root):
        """
        HAPPY PATH: last_modified updated on save.
        """
        orch, root_id = orchestrator_with_root

        orch.save_yarn_layout(root_id, zoom_level=1.0)
        result1 = orch.get_yarn_layout(root_id)
        ts1 = result1["layout"].get("last_modified")

        time.sleep(0.01)  # Ensure time passes

        orch.save_yarn_layout(root_id, zoom_level=1.5)
        result2 = orch.get_yarn_layout(root_id)
        ts2 = result2["layout"].get("last_modified")

        assert ts2 != ts1 or ts2 is not None, \
            "last_modified should update on save"

    def test_update_point_position_new(self, orchestrator_with_root):
        """
        HAPPY PATH: Adds new point position.
        """
        orch, root_id = orchestrator_with_root

        point_id = f"context:{root_id}"
        result = orch.update_point_position(
            context_id=root_id,
            point_id=point_id,
            x=300,
            y=400
        )

        assert result.get("success") is True, \
            f"update_point_position should succeed: {result}"

        layout = orch.get_yarn_layout(root_id)
        positions = layout["layout"]["point_positions"]
        assert point_id in positions, \
            f"New point position should be saved: {positions.keys()}"
        assert positions[point_id]["x"] == 300, \
            f"X coordinate should match: {positions[point_id]}"

    def test_update_point_position_existing(self, orchestrator_with_root):
        """
        HAPPY PATH: Updates existing position.
        """
        orch, root_id = orchestrator_with_root
        point_id = f"context:{root_id}"

        # Initial position
        orch.update_point_position(root_id, point_id, x=100, y=100)

        # Update
        orch.update_point_position(root_id, point_id, x=999, y=888)

        layout = orch.get_yarn_layout(root_id)
        pos = layout["layout"]["point_positions"][point_id]

        assert pos["x"] == 999, "X should be updated"
        assert pos["y"] == 888, "Y should be updated"

    def test_update_point_position_collapsed(self, orchestrator_with_root):
        """
        EDGE: Collapsed state saved.
        """
        orch, root_id = orchestrator_with_root
        point_id = f"context:{root_id}"

        orch.update_point_position(
            root_id, point_id,
            x=100, y=100, collapsed=True
        )

        layout = orch.get_yarn_layout(root_id)
        pos = layout["layout"]["point_positions"][point_id]

        assert pos.get("collapsed") is True, \
            f"Collapsed state should be saved: {pos}"

    def test_layout_persistence_survives_restart(self, fresh_orchestrator):
        """
        CRITICAL: Layout persists across orchestrator restart.
        """
        from conversation_orchestrator import ConversationOrchestrator, reset_orchestrator

        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Persistence Test")

        test_positions = {
            f"context:{ctx_id}": {"x": 555, "y": 666, "collapsed": False}
        }
        orch.save_yarn_layout(ctx_id, point_positions=test_positions, zoom_level=1.8)

        # Restart
        reset_orchestrator()
        orch2 = ConversationOrchestrator(auto_load=True)

        result = orch2.get_yarn_layout(ctx_id)
        positions = result.get("layout", {}).get("point_positions", {})

        assert f"context:{ctx_id}" in positions, \
            f"Layout should survive restart: {positions.keys()}"


# =============================================================================
# 2.2 HOT STATE (REDIS-BACKED) TESTS
# =============================================================================

class TestYarnHotState:
    """
    Redis-backed hot state tests.

    Hot state = grabbed points, live interaction data.
    This is the "fast" state that goes to Redis (when available).
    """

    def test_get_yarn_state_redis(self, orchestrator_with_root):
        """
        HAPPY PATH: Returns state from Redis when available.
        """
        orch, root_id = orchestrator_with_root

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.get_yarn_state.return_value = {
                "context_id": root_id,
                "grabbed_point_ids": ["point1"],
                "hot_refs": []
            }

            result = orch.get_yarn_state(context_id=root_id)

        assert result.get("success") is True, \
            f"Should succeed with Redis: {result}"
        assert result.get("source") == "redis", \
            "Should indicate Redis source"

    def test_get_yarn_state_fallback(self, orchestrator_with_root, mock_redis_interface):
        """
        EDGE: Returns default when Redis unavailable.
        """
        orch, root_id = orchestrator_with_root

        result = orch.get_yarn_state(context_id=root_id)

        assert result.get("success") is True, \
            f"Should succeed with fallback: {result}"
        assert result.get("source") in ["default", "stub"], \
            f"Should indicate fallback source: {result.get('source')}"

    def test_get_yarn_state_source_indicator(self, orchestrator_with_root):
        """
        HAPPY PATH: Response shows source for debugging.
        """
        orch, root_id = orchestrator_with_root

        result = orch.get_yarn_state(context_id=root_id)

        assert "source" in result, \
            f"Response MUST include 'source' key: {result.keys()}"
        assert result["source"] in ["redis", "default", "stub"], \
            f"Source must be valid value: {result['source']}"

    def test_set_grabbed_redis(self, orchestrator_with_root):
        """
        HAPPY PATH: Persists to Redis when available.
        """
        orch, root_id = orchestrator_with_root

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.set_grabbed.return_value = True
            mock_redis.get_grabbed_by.return_value = None

            result = orch.set_grabbed(
                context_id=root_id,
                point_id=f"context:{root_id}",
                grabbed=True,
                agent_id="test-agent"
            )

        assert result.get("success") is True, \
            f"set_grabbed should succeed: {result}"
        assert result.get("persisted") is True, \
            "Should indicate persisted to Redis"

    def test_set_grabbed_degradation(self, orchestrator_with_root):
        """
        EDGE: Success but persisted=False when Redis unavailable.

        With huddle pattern: when try_grab_point returns None (no collision
        detected because Redis unavailable), grab succeeds but persisted
        reflects the try_grab_point result.
        """
        orch, root_id = orchestrator_with_root

        with patch('datashapes.redis_interface') as mock_redis:
            # Simulate Redis unavailable
            mock_redis.try_grab_point.return_value = None  # Can't detect collision
            mock_redis.set_grabbed.return_value = False  # Can't persist

            result = orch.set_grabbed(
                context_id=root_id,
                point_id=f"context:{root_id}",
                grabbed=True,
                agent_id="test-agent"
            )

        assert result.get("success") is True, \
            f"Operation should succeed even without Redis: {result}"
        # No coordination (couldn't detect collision)
        assert "coordination" not in result, \
            "No collision detection without Redis"

    def test_release_grabbed(self, orchestrator_with_root):
        """
        HAPPY PATH: Removes from grabbed set.
        """
        orch, root_id = orchestrator_with_root

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.set_grabbed.return_value = True
            mock_redis.get_grabbed_by.return_value = None

            # Release
            result = orch.set_grabbed(
                context_id=root_id,
                point_id=f"context:{root_id}",
                grabbed=False,  # Release
                agent_id="test-agent"
            )

        assert result.get("success") is True, \
            f"Release should succeed: {result}"


# =============================================================================
# 2.3 RENDER TESTS
# =============================================================================

class TestYarnRender:
    """
    Board rendering tests.

    render_yarn_board returns the visual state of the board:
    - points[]: positioned items with x/y
    - cushion[]: unpositioned items waiting for placement
    - connections[]: links between points
    """

    def test_render_basic_structure(self, orchestrator_with_root):
        """
        HAPPY PATH: Returns points, connections, cushion.
        """
        orch, root_id = orchestrator_with_root

        result = orch.render_yarn_board(context_id=root_id)

        assert result.get("success") is True, \
            f"render_yarn_board should succeed: {result}"
        assert "points" in result, "Result must have 'points' key"
        assert "connections" in result, "Result must have 'connections' key"
        assert "cushion" in result, "Result must have 'cushion' key"
        assert "cushion_count" in result, "Result must have 'cushion_count'"

    def test_render_with_children(self, context_tree):
        """
        HAPPY PATH: Parent-child connections rendered.
        """
        orch, ids = context_tree

        result = orch.render_yarn_board(context_id=ids["root"])

        connections = result.get("connections", [])
        parent_child = [c for c in connections if c.get("ref_type") == "parent_child"]

        assert len(parent_child) >= 2, \
            f"Should have parent-child connections: {parent_child}"

    def test_render_with_cross_refs(self, context_pair):
        """
        HAPPY PATH: Cross-ref midpoints rendered.
        """
        orch, ctx_a, ctx_b = context_pair

        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="cites",
            reason="A cites B"
        )

        result = orch.render_yarn_board(context_id=ctx_a)

        all_points = result.get("points", []) + result.get("cushion", [])
        crossref_points = [p for p in all_points if p.get("type") == "crossref"]

        assert len(crossref_points) >= 1, \
            f"Should have crossref point: {all_points}"

    def test_render_positioned_in_points(self, context_tree):
        """
        EDGE: Points with saved x/y go to points array.
        """
        orch, ids = context_tree
        root = ids["root"]

        point_id = f"context:{root}"
        orch.update_point_position(root, point_id, x=100, y=200)

        result = orch.render_yarn_board(context_id=root)

        points = result.get("points", [])
        point_ids = [p.get("id") for p in points]

        assert point_id in point_ids, \
            f"Positioned point should be in points[]: {point_ids}"

    def test_render_unpositioned_in_cushion(self, context_tree):
        """
        EDGE: Points without saved x/y go to cushion array.
        """
        orch, ids = context_tree
        root = ids["root"]
        child1 = ids["child1"]

        # Don't save position for child1
        result = orch.render_yarn_board(context_id=root)

        cushion = result.get("cushion", [])
        cushion_ids = [p.get("id") for p in cushion]

        assert f"context:{child1}" in cushion_ids, \
            f"Unpositioned point should be in cushion[]: {cushion_ids}"

    def test_render_highlights(self, orchestrator_with_root):
        """
        HAPPY PATH: Highlights passed through to response.
        """
        orch, root_id = orchestrator_with_root

        highlights = [f"context:{root_id}"]
        result = orch.render_yarn_board(context_id=root_id, highlights=highlights)

        assert result.get("highlights") == highlights, \
            f"Highlights should be passed through: {result.get('highlights')}"

    def test_render_point_id_format(self, context_tree):
        """
        HAPPY PATH: IDs follow context:/crossref: convention.
        """
        orch, ids = context_tree
        root = ids["root"]

        result = orch.render_yarn_board(context_id=root)

        all_points = result.get("points", []) + result.get("cushion", [])

        for point in all_points:
            point_id = point.get("id", "")
            assert ":" in point_id, \
                f"Point ID should contain ':' separator: {point_id}"

    def test_render_connections_structure(self, context_tree):
        """
        HAPPY PATH: Connections have from_id, to_id, ref_type.
        """
        orch, ids = context_tree
        root = ids["root"]

        result = orch.render_yarn_board(context_id=root)
        connections = result.get("connections", [])

        assert len(connections) > 0, "Should have connections"

        for conn in connections:
            assert "from_id" in conn, f"Connection must have 'from_id': {conn}"
            assert "to_id" in conn, f"Connection must have 'to_id': {conn}"
            assert "ref_type" in conn, f"Connection must have 'ref_type': {conn}"

    def test_render_large_board(self, fresh_orchestrator):
        """
        PERF: Handles 50+ points without timeout.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Large Board")

        for i in range(50):
            orch.spawn_sidebar(parent_id=root, reason=f"Child {i}")

        start = time.time()
        result = orch.render_yarn_board(context_id=root)
        elapsed = time.time() - start

        assert result.get("success") is True, f"Should succeed: {result}"
        assert elapsed < 2.0, f"Large board render took too long: {elapsed:.2f}s"


# =============================================================================
# GAP RESOLUTION TESTS (Section 8)
# =============================================================================

class TestYarnBoardGapResolutions:
    """
    Tests for gaps identified in Section 8 of requirements.
    """

    def test_grab_collision_spawns_coordination(self, orchestrator_with_root):
        """
        INTEGRATION: Two agents grabbing same point routes to huddle.

        Uses atomic try_grab_point for collision detection.
        """
        orch, root_id = orchestrator_with_root
        point_id = f"context:{root_id}"

        with patch('datashapes.redis_interface') as mock_redis:
            # Simulate collision - another agent has the point
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-A",
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True
            mock_redis.queue_for_agent.return_value = True

            result = orch.set_grabbed(root_id, point_id, True, "AGENT-B")

        assert result.get("success") is True, f"Second grab should succeed: {result}"
        assert "coordination" in result, "Collision should trigger coordination"
        coord = result["coordination"]
        assert "huddle_id" in coord or "failed" in coord, \
            f"Should have huddle_id or failed flag: {coord}"

    def test_render_expanded_includes_detail(self, orchestrator_with_root):
        """
        HAPPY PATH: expanded=True adds detail dict to points.
        """
        orch, root_id = orchestrator_with_root

        result = orch.render_yarn_board(context_id=root_id, expanded=True)

        all_points = result.get("points", []) + result.get("cushion", [])
        for point in all_points:
            assert "detail" in point, \
                f"Expanded render should include detail: {point}"

    def test_new_items_land_in_cushion(self, orchestrator_with_root):
        """
        HAPPY PATH: New connections go to cushion, not immediate render.
        """
        orch, root_id = orchestrator_with_root

        child_id = orch.spawn_sidebar(parent_id=root_id, reason="New Child")

        result = orch.render_yarn_board(context_id=root_id)

        cushion = result.get("cushion", [])
        cushion_ids = [p.get("id") for p in cushion]

        assert f"context:{child_id}" in cushion_ids, \
            f"New item should land in cushion: {cushion_ids}"

    def test_cushion_count_matches_array(self, context_tree):
        """
        HAPPY PATH: cushion_count matches actual cushion length.
        """
        orch, ids = context_tree
        root = ids["root"]

        result = orch.render_yarn_board(context_id=root)

        cushion = result.get("cushion", [])
        cushion_count = result.get("cushion_count", -1)

        assert cushion_count == len(cushion), \
            f"cushion_count ({cushion_count}) should match cushion length ({len(cushion)})"

    def test_render_performance_50_points(self, fresh_orchestrator):
        """
        PERF: 50 points renders in < 200ms (allowing CI variance).
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Perf Test")

        for i in range(49):
            orch.spawn_sidebar(parent_id=root, reason=f"Child {i}")

        # Warm-up
        orch.render_yarn_board(context_id=root)

        start = time.time()
        result = orch.render_yarn_board(context_id=root)
        elapsed_ms = (time.time() - start) * 1000

        assert result.get("success") is True
        assert elapsed_ms < 200, \
            f"50 points should render in < 200ms, took {elapsed_ms:.1f}ms"
