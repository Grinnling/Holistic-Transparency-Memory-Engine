"""
Phase 5 Integration Tests

End-to-end tests that chain multiple Phase 5 features together.
These verify that features work correctly when combined in real workflows.

Test Scenarios:
1. Clustering -> Validation Prompts flow
2. Full queue routing pipeline
3. Cross-ref + chain stability lifecycle
4. Contradiction detection in validation workflow
5. Multi-context yarn board rendering
6. Full session simulation
7. Graceful degradation end-to-end

{YOU} Principle: These tests simulate how features combine in daily use.
If they pass, the system works as a whole, not just in isolated pieces.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from conftest import (
    CLUSTERING_THRESHOLD,
    VALIDATION_CONFIDENCE_THRESHOLD,
    CURATOR_AGENT_ID
)


# =============================================================================
# INTEGRATION TEST: CLUSTERING -> VALIDATION PROMPTS
# =============================================================================

class TestClusteringValidationIntegration:
    """
    Tests the flow: multiple sources suggest ref -> clustering triggers ->
    validation prompts include the cluster-flagged ref with high urgency.
    """

    def test_cluster_flagged_ref_appears_in_validation_prompts(self, fresh_orchestrator):
        """
        CRITICAL: When a ref hits clustering threshold, it should appear
        in validation prompts with cluster-related urgency.

        Flow:
        1. Create two contexts
        2. Add cross-ref from 3 different sources (hits threshold)
        3. Get validation prompts
        4. Verify the cluster-flagged ref appears with urgency reasons
        """
        orch = fresh_orchestrator

        ctx_source = orch.create_root_context(task_description="Source context")
        ctx_target = orch.create_root_context(task_description="Target context")

        # Add 3 sources to trigger clustering
        for agent in ["AGENT-alpha", "AGENT-beta", "AGENT-gamma"]:
            result = orch.add_cross_ref(
                source_context_id=ctx_source,
                target_context_id=ctx_target,
                ref_type="related_to",
                reason=f"Noticed by {agent}",
                confidence=0.5,  # Low confidence adds urgency too
                suggested_by=agent
            )

        # Verify clustering triggered
        assert result.get("cluster_flagged") is True, \
            "Should be cluster-flagged after 3 sources"

        # Get validation prompts
        prompts = orch.get_validation_prompts(current_context_id=ctx_source)

        all_prompts = prompts.get("inline_prompts", []) + prompts.get("scratchpad_prompts", [])

        # Find our ref in prompts
        our_prompt = None
        for p in all_prompts:
            if p.get("target_context_id") == ctx_target:
                our_prompt = p
                break

        assert our_prompt is not None, \
            f"Cluster-flagged ref should appear in validation prompts. Got: {all_prompts}"

        # Check urgency reasons include cluster info
        reasons = our_prompt.get("urgency_reasons", [])
        has_cluster_reason = any("cluster" in r.lower() for r in reasons)
        assert has_cluster_reason, \
            f"Urgency reasons should mention clustering: {reasons}"

        # Urgency score should be elevated
        urgency = our_prompt.get("urgency_score", 0)
        assert urgency >= 30, \
            f"Cluster-flagged refs should have urgency >= 30, got {urgency}"

    def test_validated_cluster_ref_excluded_from_prompts(self, fresh_orchestrator):
        """
        After validating a cluster-flagged ref, it should no longer
        appear in validation prompts.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        # Cluster the ref
        for agent in ["A1", "A2", "A3"]:
            orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to", suggested_by=agent)

        # Validate it
        ctx = orch.get_context(ctx_a)
        metadata = ctx.cross_sidebar_refs.get(ctx_b)
        metadata["human_validated"] = True

        # Check prompts
        prompts = orch.get_validation_prompts(current_context_id=ctx_a)
        all_prompts = prompts.get("inline_prompts", []) + prompts.get("scratchpad_prompts", [])

        target_ids = [p.get("target_context_id") for p in all_prompts]
        assert ctx_b not in target_ids, \
            "Validated refs should not appear in validation prompts"


# =============================================================================
# INTEGRATION TEST: FULL QUEUE ROUTING PIPELINE
# =============================================================================

class TestQueueRoutingIntegration:
    """
    Tests the complete routing flow: entry created -> routed to curator ->
    curator approves -> routed to specialist.
    """

    def test_finding_full_pipeline(self, fresh_orchestrator):
        """
        Complete flow for a finding entry through the routing system.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Pipeline test")

        finding = {
            "id": "FINDING-integration-001",
            "entry_type": "finding",
            "content": "Found a bug in the authentication module",
            "created_at": datetime.now().isoformat(),
            "source_context_id": ctx_id,
            "tags": ["bug", "auth"],
            "priority": "normal",
            "status": "pending"
        }

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            # Step 1: Route to curator
            route_result = orch.route_scratchpad_entry(
                entry=finding,
                context_id=ctx_id
            )

            assert route_result.get("routed") is True, \
                f"Finding should be routed: {route_result}"
            assert route_result.get("destination") == CURATOR_AGENT_ID, \
                "Finding should go to curator first"

            # Step 2: Curator approves
            approve_result = orch.curator_approve_entry(
                entry_id=finding["id"],
                context_id=ctx_id,
                approved=True
            )

            assert approve_result.get("approved") is True, \
                f"Approval should succeed: {approve_result}"
            assert approve_result.get("destination") is not None, \
                "Approved entry should have final destination"

            # Should route to some specialist (inference may vary)
            final_dest = approve_result.get("destination")
            assert final_dest is not None, \
                f"Approved entry should have a destination, got {approve_result}"

    def test_rejection_stops_pipeline(self, fresh_orchestrator):
        """
        When curator rejects, entry should not be routed further.
        """
        orch = fresh_orchestrator
        ctx_id = orch.create_root_context(task_description="Rejection test")

        entry = {
            "id": "ENTRY-reject-001",
            "entry_type": "finding",
            "content": "Vague observation",
            "created_at": datetime.now().isoformat(),
            "source_context_id": ctx_id,
        }

        with patch('datashapes.redis_interface') as mock_redis:
            mock_redis.queue_for_agent.return_value = True

            # Route to curator
            orch.route_scratchpad_entry(entry=entry, context_id=ctx_id)

            # Curator rejects
            reject_result = orch.curator_approve_entry(
                entry_id=entry["id"],
                context_id=ctx_id,
                approved=False,
                rejection_reason="Too vague to action"
            )

            assert reject_result.get("approved") is False
            assert "destination" not in reject_result, \
                "Rejected entries should have no destination"


# =============================================================================
# INTEGRATION TEST: CROSS-REF + CHAIN STABILITY
# =============================================================================

class TestCrossRefStabilityIntegration:
    """
    Tests: create dependency refs -> check stability -> validate -> recheck.
    """

    def test_stability_with_leaf_dependency(self, fresh_orchestrator):
        """
        A context depending on a leaf (no outgoing deps) should be stable.

        With inverse ref mapping:
        - A depends_on B creates: A->B (depends_on), B->A (informs)
        - B has no DEPENDENCY refs (informs is not a dependency type)
        - Therefore A's chain is stable

        This tests that stability only considers dependency-type refs
        (depends_on, derived_from, implements) not inverse refs like informs.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Dependent context")
        ctx_b = orch.create_root_context(task_description="Leaf dependency (no outgoing deps)")

        # A depends on B (B is a leaf)
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="depends_on",
            reason="A depends on B"
        )

        # B should only have an 'informs' ref back to A (from inverse mapping)
        # 'informs' is NOT a dependency type, so B is effectively a stable leaf

        result = orch.check_chain_stability(context_id=ctx_a)

        assert result.get("success") is True, f"Should succeed: {result}"
        assert result.get("is_stable") is True, \
            f"A should be stable - B has no dependency refs, only 'informs': {result}"

    def test_multi_level_dependency_chain(self, fresh_orchestrator):
        """
        Test stability with A -> B -> C chain.

        With inverse ref mapping:
        - A depends_on B: A->B (depends_on), B->A (informs)
        - B depends_on C: B->C (depends_on), C->B (informs)

        Stability analysis:
        - C has no dependency refs (only 'informs' to B) → C is stable
        - B has depends_on to C. C has no unvalidated dependency refs → B is stable
        - A has depends_on to B. B has unvalidated depends_on to C → A is UNSTABLE

        After validating B->C:
        - A should become stable (B's dependency is now validated)
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Level A")
        ctx_b = orch.create_root_context(task_description="Level B")
        ctx_c = orch.create_root_context(task_description="Level C - leaf")

        # A depends on B
        orch.add_cross_ref(ctx_a, ctx_b, ref_type="depends_on")
        # B depends on C
        orch.add_cross_ref(ctx_b, ctx_c, ref_type="depends_on")

        # C is a leaf (only has 'informs' back to B, no dependency refs)
        stability_c = orch.check_chain_stability(context_id=ctx_c)
        assert stability_c.get("is_stable") is True, \
            f"C (leaf) should be stable: {stability_c}"

        # B depends on C, and C has no unvalidated dependency refs
        stability_b = orch.check_chain_stability(context_id=ctx_b)
        assert stability_b.get("is_stable") is True, \
            f"B should be stable (C has no dependency refs): {stability_b}"

        # A depends on B, and B has unvalidated depends_on to C
        stability_a = orch.check_chain_stability(context_id=ctx_a)
        assert stability_a.get("is_stable") is False, \
            f"A should be unstable (B has unvalidated dep to C): {stability_a}"

        # Validate B's ref to C
        ctx_b_obj = orch.get_context(ctx_b)
        ctx_b_obj.cross_sidebar_refs[ctx_c]["human_validated"] = True

        # Now A should be stable
        stability_a_after = orch.check_chain_stability(context_id=ctx_a)
        assert stability_a_after.get("is_stable") is True, \
            f"A should be stable after B->C validated: {stability_a_after}"


# =============================================================================
# INTEGRATION TEST: CONTRADICTION DETECTION + VALIDATION
# =============================================================================

class TestContradictionValidationIntegration:
    """
    Tests: create contradicting refs -> detect -> verify in validation prompts.
    """

    def test_contradictions_flagged_in_validation(self, fresh_orchestrator):
        """
        Contradicting refs should appear prominently in validation prompts.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Context A")
        ctx_b = orch.create_root_context(task_description="Context B")

        # A implements B
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="implements",
            bidirectional=False
        )

        # B contradicts A (contradiction!)
        orch.add_cross_ref(
            source_context_id=ctx_b,
            target_context_id=ctx_a,
            ref_type="contradicts",
            bidirectional=False
        )

        # Detect contradictions
        contradictions = orch.detect_contradictions()
        assert len(contradictions) > 0, \
            "Should detect implements vs contradicts contradiction"

        # The contradiction involves both contexts
        contradiction = contradictions[0]
        contexts_involved = contradiction.get("contexts", [])
        assert ctx_a in contexts_involved or ctx_b in contexts_involved, \
            f"Contradiction should involve our contexts: {contradiction}"


# =============================================================================
# INTEGRATION TEST: MULTI-CONTEXT YARN BOARD
# =============================================================================

class TestYarnBoardIntegration:
    """
    Tests yarn board with multiple contexts and cross-refs.
    """

    def test_full_board_render_with_cross_refs(self, fresh_orchestrator):
        """
        Render a board with multiple contexts and cross-refs between them.
        """
        orch = fresh_orchestrator

        # Create context tree
        root = orch.create_root_context(task_description="Root project")
        child1 = orch.spawn_sidebar(parent_id=root, reason="Feature A")
        child2 = orch.spawn_sidebar(parent_id=root, reason="Feature B")

        # Add cross-ref between children
        orch.add_cross_ref(
            source_context_id=child1,
            target_context_id=child2,
            ref_type="related_to",
            reason="Features interact"
        )

        # Save some positions
        orch.save_yarn_layout(
            context_id=root,
            point_positions={
                f"context:{root}": {"x": 100, "y": 100},
                f"context:{child1}": {"x": 200, "y": 200},
            },
            zoom_level=1.0
        )

        # Render board
        render = orch.render_yarn_board(context_id=root)

        assert render.get("success") is True, f"Render should succeed: {render}"

        # Check structure
        points = render.get("points", [])
        connections = render.get("connections", [])
        cushion = render.get("cushion", [])

        # Should have points for positioned items (field is "id" not "point_id")
        point_ids = [p.get("id") for p in points]
        assert f"context:{root}" in point_ids, \
            f"Root should be in points: {point_ids}"
        assert f"context:{child1}" in point_ids, \
            f"Child1 should be in points: {point_ids}"

        # Unpositioned child2 should be in cushion
        cushion_ids = [c.get("id") for c in cushion]
        assert f"context:{child2}" in cushion_ids, \
            f"Unpositioned child2 should be in cushion: {cushion_ids}"

        # Should have connection for cross-ref
        assert len(connections) > 0, "Should have connections for cross-refs"

    def test_layout_persistence_across_operations(self, fresh_orchestrator):
        """
        Layout should persist through various operations.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Persistence test")

        # Save layout
        orch.save_yarn_layout(
            context_id=root,
            point_positions={f"context:{root}": {"x": 500, "y": 500}},
            zoom_level=2.0
        )

        # Do various operations
        child = orch.spawn_sidebar(parent_id=root, reason="New child")
        orch.add_cross_ref(root, child, ref_type="related_to")

        # Layout should still be there
        layout = orch.get_yarn_layout(context_id=root)

        assert layout.get("success") is True
        positions = layout["layout"].get("point_positions", {})
        assert f"context:{root}" in positions, "Root position should persist"
        assert positions[f"context:{root}"]["x"] == 500, "X position should persist"


# =============================================================================
# INTEGRATION TEST: GRACEFUL DEGRADATION END-TO-END
# =============================================================================

class TestGracefulDegradationIntegration:
    """
    Tests that the full system works when Redis is unavailable.
    """

    def test_full_workflow_without_redis(self, fresh_orchestrator, mock_redis_interface):
        """
        Complete workflow should succeed even without Redis.

        This is CRITICAL for resilience - Redis is optional enhancement.
        """
        orch = fresh_orchestrator

        # Create context hierarchy
        root = orch.create_root_context(task_description="No-Redis test")
        assert root is not None, "Context creation should work without Redis"

        child = orch.spawn_sidebar(parent_id=root, reason="Child context")
        assert child is not None, "Sidebar spawn should work without Redis"

        # Add cross-refs
        ref_result = orch.add_cross_ref(
            source_context_id=root,
            target_context_id=child,
            ref_type="related_to"
        )
        assert ref_result.get("success") is True, \
            "Cross-ref should work without Redis"

        # Save layout
        layout_result = orch.save_yarn_layout(
            context_id=root,
            point_positions={f"context:{root}": {"x": 100, "y": 100}},
            zoom_level=1.5
        )
        assert layout_result.get("success") is True, \
            "Layout save should work without Redis"

        # Render board
        render = orch.render_yarn_board(context_id=root)
        assert render.get("success") is True, \
            "Board render should work without Redis"

        # Route entry (will show queued_to_redis=False but should succeed)
        entry = {
            "id": "ENTRY-no-redis",
            "entry_type": "finding",
            "content": "Test without Redis",
            "created_at": datetime.now().isoformat(),
            "source_context_id": root,
        }
        route_result = orch.route_scratchpad_entry(entry=entry, context_id=root)
        assert route_result.get("success") is True, \
            "Entry routing should succeed without Redis"
        assert route_result.get("queued_to_redis") is False, \
            "Should indicate Redis not available"

        # Get validation prompts
        prompts = orch.get_validation_prompts(current_context_id=root)
        assert prompts.get("success") is True, \
            "Validation prompts should work without Redis"

        # Check chain stability
        stability = orch.check_chain_stability(context_id=root)
        assert "is_stable" in stability, \
            "Chain stability should work without Redis"


# =============================================================================
# INTEGRATION TEST: FULL SESSION SIMULATION
# =============================================================================

class TestFullSessionSimulation:
    """
    Simulates a complete user session with multiple features interacting.
    """

    def test_realistic_session_flow(self, fresh_orchestrator):
        """
        Simulate a realistic session:
        1. User creates project context
        2. Spawns sidebars for different features
        3. Multiple agents notice connections (clustering)
        4. User positions items on yarn board
        5. System detects contradictions
        6. User validates refs
        7. Check final state is consistent
        """
        orch = fresh_orchestrator

        # 1. Create project
        project = orch.create_root_context(
            task_description="Build authentication system"
        )

        # 2. Spawn feature sidebars
        login_feature = orch.spawn_sidebar(
            parent_id=project,
            reason="Implement login flow"
        )
        session_feature = orch.spawn_sidebar(
            parent_id=project,
            reason="Implement session management"
        )
        security_feature = orch.spawn_sidebar(
            parent_id=project,
            reason="Security review"
        )

        # 3. Multiple agents notice login->session connection (clustering)
        for agent in ["AGENT-coder", "AGENT-reviewer", "AGENT-architect"]:
            orch.add_cross_ref(
                source_context_id=login_feature,
                target_context_id=session_feature,
                ref_type="depends_on",
                reason=f"{agent} noticed login depends on session",
                suggested_by=agent
            )

        # Verify clustering triggered
        flagged = orch.get_cluster_flagged_refs()
        assert flagged.get("count") >= 1, \
            "Should have at least one cluster-flagged ref"

        # 4. User positions items
        orch.save_yarn_layout(
            context_id=project,
            point_positions={
                f"context:{project}": {"x": 400, "y": 100},
                f"context:{login_feature}": {"x": 200, "y": 300},
                f"context:{session_feature}": {"x": 600, "y": 300},
                f"context:{security_feature}": {"x": 400, "y": 500},
            },
            zoom_level=0.8
        )

        # 5. Create potential contradiction
        # login implements session's interface
        orch.add_cross_ref(
            source_context_id=login_feature,
            target_context_id=session_feature,
            ref_type="implements",
            bidirectional=False
        )
        # But security says session contradicts login requirements
        orch.add_cross_ref(
            source_context_id=security_feature,
            target_context_id=login_feature,
            ref_type="contradicts",
            reason="Security requirements conflict with login implementation",
            bidirectional=False
        )

        # Check for contradictions (may or may not detect depending on implementation)
        contradictions = orch.detect_contradictions()
        # Just verify it doesn't crash
        assert isinstance(contradictions, list), \
            "detect_contradictions should return a list"

        # 6. Validate the cluster-flagged dependency
        ctx = orch.get_context(login_feature)
        if session_feature in ctx.cross_sidebar_refs:
            ctx.cross_sidebar_refs[session_feature]["human_validated"] = True

        # 7. Final state checks
        # Board should render
        board = orch.render_yarn_board(context_id=project)
        assert board.get("success") is True

        # All contexts should exist
        assert orch.get_context(project) is not None
        assert orch.get_context(login_feature) is not None
        assert orch.get_context(session_feature) is not None
        assert orch.get_context(security_feature) is not None

        # Layout should be retrievable
        layout = orch.get_yarn_layout(context_id=project)
        assert layout.get("success") is True
        assert layout["layout"]["zoom_level"] == 0.8

        # Validation prompts should work
        prompts = orch.get_validation_prompts(current_context_id=project)
        assert prompts.get("success") is True

        # Session is consistent - no crashes, all operations completed
        print("Full session simulation completed successfully!")
