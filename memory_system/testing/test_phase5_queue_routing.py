"""
Phase 5 Queue Routing Tests

Tests for scratchpad entry routing, curator validation, and agent registry.
Covers Section 3 of TEST_REQUIREMENTS_PHASE5_CONSOLIDATED.md.

Test Categories:
- 3.1 route_scratchpad_entry: Entry routing to curator
- 3.2 curator_approve_entry: Curator approval/rejection flow
- 3.3 _infer_destination: Keyword-based routing inference
- 3.4 Agent Registry: Agent registration and queues

{YOU} Principle: Each test explains WHY it matters for daily use.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from conftest import CURATOR_AGENT_ID


# =============================================================================
# 3.1 ROUTE_SCRATCHPAD_ENTRY TESTS
# =============================================================================

class TestRouteScratchpadEntry:
    """
    Entry routing tests.

    All findings/questions go through the curator for validation.
    Quick notes without explicit routes bypass the pipeline.
    """

    def test_route_quick_note_no_route(self, fresh_orchestrator, sample_quick_note_entry):
        """
        HAPPY PATH: quick_note without explicit route is stored only, not routed.

        WHY: Quick notes are transient thoughts - no need to burden the curator.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Quick note test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            result = orch.route_scratchpad_entry(
                entry=sample_quick_note_entry,
                context_id=ctx_id
            )

        assert result.get("routed") is False, \
            f"Quick note without route should NOT be routed: {result}"
        assert result.get("reason") == "quick_note_no_route", \
            f"Should explain why not routed: {result.get('reason')}"

    def test_route_finding_to_curator(self, fresh_orchestrator, sample_finding_entry):
        """
        CRITICAL: All findings MUST go through curator first.

        WHY: Findings need validation before being actionable.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Finding test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            result = orch.route_scratchpad_entry(
                entry=sample_finding_entry,
                context_id=ctx_id
            )

        assert result.get("routed") is True, \
            f"Finding MUST be routed: {result}"
        assert result.get("destination") == CURATOR_AGENT_ID, \
            f"Finding MUST go to curator first, got: {result.get('destination')}"

    def test_route_question_to_curator(self, fresh_orchestrator, sample_question_entry):
        """
        HAPPY PATH: Questions route through curator.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Question test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            result = orch.route_scratchpad_entry(
                entry=sample_question_entry,
                context_id=ctx_id
            )

        assert result.get("routed") is True, \
            f"Question should be routed: {result}"
        assert result.get("destination") == CURATOR_AGENT_ID, \
            f"Question should go to curator: {result.get('destination')}"

    def test_route_with_explicit_destination(self, fresh_orchestrator, sample_finding_entry):
        """
        HAPPY PATH: explicit_route_to is respected.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Explicit dest test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            result = orch.route_scratchpad_entry(
                entry=sample_finding_entry,
                context_id=ctx_id,
                explicit_route_to="AGENT-architect"
            )

        # Still goes to curator first, but explicit dest is recorded
        assert result.get("routed") is True, \
            f"Should be routed: {result}"

    def test_route_graceful_degradation(self, fresh_orchestrator, sample_finding_entry, mock_redis_interface):
        """
        EDGE: Success with queued_to_redis=False when Redis unavailable.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Graceful deg test")

        result = orch.route_scratchpad_entry(
            entry=sample_finding_entry,
            context_id=ctx_id
        )

        assert result.get("success") is True, \
            f"Routing should succeed even without Redis: {result}"
        assert result.get("queued_to_redis") is False, \
            "Should indicate Redis not available"


# =============================================================================
# 3.2 CURATOR_APPROVE_ENTRY TESTS
# =============================================================================

class TestCuratorApproveEntry:
    """
    Curator approval/rejection tests.

    The curator validates entries before routing to specialists.
    """

    def test_curator_approve_routes_to_destination(self, fresh_orchestrator, mock_redis_interface):
        """
        HAPPY PATH: Approved entry routes to inferred destination.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Approval test")

        result = orch.curator_approve_entry(
            entry_id="ENTRY-001",
            context_id=ctx_id,
            approved=True
        )

        assert result.get("success") is True, \
            f"Approval should succeed: {result}"
        assert result.get("approved") is True, \
            "Result should show approved"
        assert "destination" in result, \
            f"Approved entry should have destination: {result}"

    def test_curator_reject_not_routed(self, fresh_orchestrator, mock_redis_interface):
        """
        HAPPY PATH: Rejected entry not routed.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Rejection test")

        result = orch.curator_approve_entry(
            entry_id="ENTRY-002",
            context_id=ctx_id,
            approved=False,
            rejection_reason="Too vague"
        )

        assert result.get("success") is True, \
            "Rejection should succeed as an operation"
        assert result.get("approved") is False, \
            "Result should show rejected"
        assert "destination" not in result, \
            "Rejected entries should NOT have destination"

    def test_curator_approve_with_redis(self, fresh_orchestrator):
        """
        INTEGRATION: Approved entry queued to Redis.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Redis approval test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            result = orch.curator_approve_entry(
                entry_id="ENTRY-003",
                context_id=ctx_id,
                approved=True
            )

        assert result.get("queued_to_redis") is True, \
            f"Should indicate queued to Redis: {result}"


# =============================================================================
# 3.3 _INFER_DESTINATION TESTS
# =============================================================================

class TestInferDestination:
    """
    Keyword-based routing inference tests.

    Maps content keywords to agent specialties.
    """

    def test_infer_debugging_keywords(self, fresh_orchestrator):
        """
        HAPPY PATH: bug/debug keywords -> debugger.
        """
        orch = fresh_orchestrator

        test_cases = [
            ("Found a bug in the parser", "AGENT-debugger"),
            ("Need to debug the auth flow", "AGENT-debugger"),
            ("Fix the crash on startup", "AGENT-debugger"),
        ]

        for content, expected in test_cases:
            destination = orch._infer_destination(
                entry_id="TEST",
                context_id="SB-1",
                content_hint=content
            )
            assert destination == expected, \
                f"'{content}' should route to {expected}, got {destination}"

    def test_infer_research_keywords(self, fresh_orchestrator):
        """
        HAPPY PATH: research/investigate keywords -> researcher.
        """
        orch = fresh_orchestrator

        test_cases = [
            ("Research best practices for caching", "AGENT-researcher"),
            ("Investigate the memory leak", "AGENT-researcher"),
        ]

        for content, expected in test_cases:
            destination = orch._infer_destination(
                entry_id="TEST",
                context_id="SB-1",
                content_hint=content
            )
            assert destination == expected, \
                f"'{content}' should route to {expected}, got {destination}"

    def test_infer_architecture_keywords(self, fresh_orchestrator):
        """
        HAPPY PATH: architecture/design keywords -> architect.
        """
        orch = fresh_orchestrator

        test_cases = [
            ("Design the new API", "AGENT-architect"),
            ("Review the architecture", "AGENT-architect"),
            ("Security review needed", "AGENT-architect"),
        ]

        for content, expected in test_cases:
            destination = orch._infer_destination(
                entry_id="TEST",
                context_id="SB-1",
                content_hint=content
            )
            assert destination == expected, \
                f"'{content}' should route to {expected}, got {destination}"

    def test_infer_no_match_defaults_to_operator(self, fresh_orchestrator):
        """
        EDGE: Unknown content -> operator (human).
        """
        orch = fresh_orchestrator

        destination = orch._infer_destination(
            entry_id="TEST",
            context_id="SB-1",
            content_hint="Random thoughts about life"
        )

        assert destination == "AGENT-operator", \
            f"Unmatched content should go to operator, got {destination}"

    def test_infer_empty_content(self, fresh_orchestrator):
        """
        EDGE: Empty/None content -> operator.
        """
        orch = fresh_orchestrator

        for content in [None, "", "   "]:
            destination = orch._infer_destination(
                entry_id="TEST",
                context_id="SB-1",
                content_hint=content
            )
            assert destination == "AGENT-operator", \
                f"Empty content '{content}' should go to operator"


# =============================================================================
# 3.4 AGENT REGISTRY TESTS
# =============================================================================

class TestAgentRegistry:
    """
    Agent registration and queue management tests.
    """

    def test_register_new_agent(self, fresh_orchestrator):
        """
        HAPPY PATH: New agent added to registry.
        """
        orch = fresh_orchestrator

        result = orch.register_agent(
            agent_id="AGENT-test-new",
            specialties=["testing", "qa"]
        )

        assert result.get("success") is True, \
            f"Registration should succeed: {result}"
        assert result.get("agent_id") == "AGENT-test-new"

    def test_register_update_existing(self, fresh_orchestrator):
        """
        HAPPY PATH: Existing agent specialties updated.
        """
        orch = fresh_orchestrator

        # First registration
        orch.register_agent(agent_id="AGENT-updatable", specialties=["initial"])

        # Update
        result = orch.register_agent(
            agent_id="AGENT-updatable",
            specialties=["updated", "new"]
        )

        assert result.get("success") is True
        assert result.get("specialties") == ["updated", "new"]

    def test_list_agents_defaults(self, fresh_orchestrator):
        """
        HAPPY PATH: Default agents present.
        """
        orch = fresh_orchestrator

        result = orch.list_agents()

        assert result.get("success") is True
        agent_ids = {a["agent_id"] for a in result.get("agents", [])}

        expected = {"AGENT-curator", "AGENT-operator"}
        for agent in expected:
            assert agent in agent_ids, \
                f"Default agent {agent} should be present"

    def test_get_agent_queue_empty(self, fresh_orchestrator, mock_redis_interface):
        """
        EDGE: Empty queue returns [].
        """
        orch = fresh_orchestrator

        result = orch.get_agent_queue("AGENT-debugger")

        assert result.get("success") is True
        assert result.get("queue") == []
        assert result.get("count") == 0


# =============================================================================
# INTEGRATION: FULL PIPELINE
# =============================================================================

class TestQueueRoutingPipeline:
    """
    End-to-end tests for the complete routing pipeline.
    """

    def test_full_routing_pipeline(self, fresh_orchestrator, sample_finding_entry):
        """
        Test complete flow: route -> curator approve -> final destination.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Pipeline test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            # Step 1: Route to curator
            route_result = orch.route_scratchpad_entry(
                entry=sample_finding_entry,
                context_id=ctx_id
            )

            assert route_result.get("routed") is True
            assert route_result.get("destination") == CURATOR_AGENT_ID

            # Step 2: Curator approves
            approve_result = orch.curator_approve_entry(
                entry_id=sample_finding_entry["id"],
                context_id=ctx_id,
                approved=True
            )

            assert approve_result.get("approved") is True
            assert approve_result.get("destination") is not None

    def test_quick_note_bypass(self, fresh_orchestrator, sample_quick_note_entry):
        """
        Quick notes without routes bypass the entire pipeline.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Bypass test")

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            result = orch.route_scratchpad_entry(
                entry=sample_quick_note_entry,
                context_id=ctx_id
            )

            assert result.get("routed") is False
            # queue_for_agent should NOT be called for bypassed entries
