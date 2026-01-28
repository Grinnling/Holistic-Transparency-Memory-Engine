"""
Concurrency/Coordination Tests (Section 8.1)

Tests for multi-agent coordination when simultaneous access occurs.

Design Decision: Two agents grabbing same point = coordination signal, not conflict.
System routes to a "huddle" sidebar (one per context) for agents to sync up.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# 8.1 CONCURRENCY - COORDINATION EVENTS (HUDDLE PATTERN)
# =============================================================================

class TestHuddleCoordination:
    """
    Tests for the grab huddle pattern.

    When two agents try to grab the same yarn board point, the system
    routes them to a shared "huddle" sidebar (one per context) instead
    of spawning separate coordination sidebars.
    """

    def test_collision_creates_huddle(self, fresh_orchestrator):
        """
        INTEGRATION: Grab collision routes agents to a huddle.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")
        point_id = f"context:{root_id}"

        with patch('datashapes.redis_interface') as mock_redis:
            # Agent-A already has the point (collision scenario)
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-A",
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True
            mock_redis.queue_for_agent.return_value = True

            # Agent-B tries to grab same point
            result = orch.set_grabbed(
                context_id=root_id,
                point_id=point_id,
                grabbed=True,
                agent_id="AGENT-B"
            )

        assert "coordination" in result, "Collision should trigger coordination"
        coord = result["coordination"]
        assert "huddle_id" in coord, "Should route to huddle"
        assert coord["huddle_id"].startswith("SB-"), "Huddle should be a valid sidebar"
        assert coord["reason"] == "grab_collision"

    def test_huddle_tracks_contested_points(self, fresh_orchestrator):
        """
        HAPPY PATH: Huddle accumulates contested points.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-A",
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True
            mock_redis.queue_for_agent.return_value = True

            # First collision
            result1 = orch.set_grabbed(root_id, "point1", True, "AGENT-B")
            # Second collision on different point
            result2 = orch.set_grabbed(root_id, "point2", True, "AGENT-C")

        # Both should route to SAME huddle
        assert result1["coordination"]["huddle_id"] == result2["coordination"]["huddle_id"]
        # Huddle should now have 2 contested points
        assert result2["coordination"]["total_contested_points"] == 2

    def test_huddle_includes_both_agents(self, fresh_orchestrator):
        """
        HAPPY PATH: Both colliding agents are listed.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-Alpha",
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True
            mock_redis.queue_for_agent.return_value = True

            result = orch.set_grabbed(root_id, "point1", True, "AGENT-Beta")

        agents = result["coordination"]["agents"]
        assert "AGENT-Alpha" in agents
        assert "AGENT-Beta" in agents

    def test_no_collision_no_huddle(self, fresh_orchestrator):
        """
        HAPPY PATH: No collision = no huddle, just successful grab.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            # No collision - try_grab_point returns None (we got the lock)
            mock_redis.try_grab_point.return_value = None
            mock_redis.set_grabbed.return_value = True

            result = orch.set_grabbed(root_id, "point1", True, "AGENT-A")

        assert "coordination" not in result, "No collision = no coordination needed"
        assert result["success"] is True

    def test_same_agent_regrab_no_collision(self, fresh_orchestrator):
        """
        EDGE: Same agent re-grabbing should not trigger collision.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            # Same agent already has it - not a collision
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-A",  # Same as requesting agent
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True

            result = orch.set_grabbed(root_id, "point1", True, "AGENT-A")

        # Same agent = not a collision
        assert "coordination" not in result

    def test_release_no_coordination(self, fresh_orchestrator):
        """
        EDGE: Releasing a point never triggers coordination.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.set_grabbed.return_value = True

            result = orch.set_grabbed(root_id, "point1", False, "AGENT-A")

        assert "coordination" not in result

    def test_agents_notified_via_queue(self, fresh_orchestrator):
        """
        HAPPY PATH: Both agents receive queue notifications.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-A",
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True
            mock_redis.queue_for_agent.return_value = True

            orch.set_grabbed(root_id, "point1", True, "AGENT-B")

        # Should have queued for both agents
        assert mock_redis.queue_for_agent.call_count == 2
        queued_agents = [call[0][0] for call in mock_redis.queue_for_agent.call_args_list]
        assert "AGENT-A" in queued_agents
        assert "AGENT-B" in queued_agents


class TestHuddleGracefulDegradation:
    """
    Tests for graceful degradation when coordination fails.
    """

    def test_grab_succeeds_when_huddle_fails(self, fresh_orchestrator):
        """
        EDGE: If huddle creation fails, grab still succeeds.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.try_grab_point.return_value = {
                "agent_id": "AGENT-A",
                "grabbed_at": datetime.now().isoformat()
            }
            mock_redis.set_grabbed.return_value = True

            # Make spawn_sidebar fail
            with patch.object(orch, 'spawn_sidebar', side_effect=Exception("Spawn failed")):
                result = orch.set_grabbed(root_id, "point1", True, "AGENT-B")

        # Grab should succeed even when huddle fails
        assert result["success"] is True
        # Coordination should indicate failure
        assert result["coordination"]["failed"] is True

    def test_grab_works_without_redis(self, fresh_orchestrator):
        """
        EDGE: Without Redis, grabs work but can't detect collisions.

        Note: When try_grab_point returns None, it means either:
        1. We got the lock atomically (persisted = True)
        2. Redis is unavailable (stub returns None, can't detect collision)

        Either way, the grab "succeeds" - graceful degradation.
        """
        orch = fresh_orchestrator
        root_id = orch.create_root_context(task_description="Test Context")

        with patch('datashapes.redis_interface') as mock_redis:
            # Redis unavailable - try_grab_point returns None (can't check)
            mock_redis.try_grab_point.return_value = None
            mock_redis.set_grabbed.return_value = False  # Can't persist

            result = orch.set_grabbed(root_id, "point1", True, "AGENT-B")

        # Grab "succeeds" (graceful degradation)
        assert result["success"] is True
        # No coordination (couldn't detect collision without Redis)
        assert "coordination" not in result
