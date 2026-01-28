"""
Phase 5 Clustering Tests

Tests for cross-ref clustering when multiple sources suggest the same connection.
Covers Section 4 of TEST_REQUIREMENTS_PHASE5_CONSOLIDATED.md.

Test Categories:
- 4.1 Threshold Behavior: 3 sources triggers cluster_flagged
- 4.2 Suggested Sources: Timestamp tracking
- 4.3 get_cluster_flagged_refs: Query clustered refs

{YOU} Principle: Clustering is about signal amplification - when multiple
independent sources notice the same thing, that's worth attention.
"""

import pytest
import time
from datetime import datetime

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from conftest import CLUSTERING_THRESHOLD


# =============================================================================
# 4.1 THRESHOLD BEHAVIOR TESTS
# =============================================================================

class TestClusteringThreshold:
    """
    Clustering threshold tests.

    CLUSTERING_THRESHOLD = 3 (defined in conftest.py)

    When 3+ independent sources suggest the same cross-ref:
    - cluster_flagged becomes True
    - validation_priority becomes "urgent"
    """

    def test_clustering_threshold_constant(self):
        """
        Verify the clustering threshold is 3.
        """
        assert CLUSTERING_THRESHOLD == 3, \
            f"CLUSTERING_THRESHOLD should be 3, got {CLUSTERING_THRESHOLD}"

    def test_first_source_no_flag(self, context_pair):
        """
        HAPPY PATH: 1 source should NOT trigger clustering.
        """
        orch, ctx_a, ctx_b = context_pair

        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            reason="First observation",
            suggested_by="AGENT-alpha"
        )

        assert result.get("success") is True
        assert result.get("source_count") == 1
        assert result.get("cluster_flagged") is False, \
            "1 source should NOT flag for clustering"

    def test_second_source_no_flag(self, context_pair):
        """
        HAPPY PATH: 2 sources should NOT trigger clustering.
        """
        orch, ctx_a, ctx_b = context_pair

        # First source
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-alpha"
        )

        # Second source
        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-beta"
        )

        assert result.get("source_count") == 2
        assert result.get("cluster_flagged") is False, \
            "2 sources should NOT flag for clustering"

    def test_third_source_triggers_flag(self, context_pair):
        """
        CRITICAL: 3rd source MUST set cluster_flagged=True.

        WHY: This is the core clustering behavior. When 3 independent
        sources notice the same connection, that's a strong signal.
        """
        orch, ctx_a, ctx_b = context_pair

        # Sources 1 and 2
        for agent in ["AGENT-1", "AGENT-2"]:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_b,
                ref_type="related_to",
                suggested_by=agent
            )

        # Source 3 - TRIGGERS FLAG
        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-3"
        )

        assert result.get("source_count") == 3, \
            f"Should have 3 sources, got {result.get('source_count')}"
        assert result.get("cluster_flagged") is True, \
            "cluster_flagged MUST be True after 3 sources"
        assert result.get("newly_flagged") is True, \
            "newly_flagged MUST be True when THIS call triggered the flag"

        # Verify metadata updated
        ctx = orch.get_context(ctx_a)
        metadata = ctx.cross_sidebar_refs.get(ctx_b)
        assert metadata.get("validation_priority") == "urgent", \
            "validation_priority should become 'urgent' when cluster-flagged"

    def test_fourth_source_stays_flagged(self, context_pair):
        """
        EDGE: 4+ sources stays flagged but newly_flagged=False.
        """
        orch, ctx_a, ctx_b = context_pair

        # Add 3 sources to trigger flag
        for agent in ["A1", "A2", "A3"]:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_b,
                ref_type="related_to",
                suggested_by=agent
            )

        # 4th source
        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="A4"
        )

        assert result.get("source_count") == 4
        assert result.get("cluster_flagged") is True, \
            "Should stay flagged"
        assert result.get("newly_flagged") is False, \
            "newly_flagged should be False on 4th source"

    def test_same_source_no_duplicate(self, context_pair):
        """
        EDGE: Same source suggesting twice does NOT increment count.

        WHY: Prevents gaming the threshold by spamming.
        """
        orch, ctx_a, ctx_b = context_pair

        # First suggestion
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-spammer"
        )

        # Same agent suggests again
        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-spammer"  # Same!
        )

        assert result.get("source_count") == 1, \
            f"Duplicate source should NOT increment count, got {result.get('source_count')}"

    def test_default_suggested_by(self, context_pair):
        """
        EDGE: When suggested_by is None, defaults to source_context_id.
        """
        orch, ctx_a, ctx_b = context_pair

        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            reason="No explicit suggester"
            # suggested_by not specified
        )

        assert result.get("success") is True
        sources = result.get("suggested_sources", [])
        assert len(sources) == 1


# =============================================================================
# 4.2 SUGGESTED_SOURCES TIMESTAMPS TESTS
# =============================================================================

class TestSuggestedSourcesTimestamps:
    """
    Timestamp tracking for suggested sources.
    """

    def test_source_has_timestamp(self, context_pair):
        """
        HAPPY PATH: Each source has suggested_at timestamp.
        """
        orch, ctx_a, ctx_b = context_pair

        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-timestamped"
        )

        sources = result.get("suggested_sources", [])
        assert len(sources) == 1
        assert "suggested_at" in sources[0], \
            f"Source must have suggested_at: {sources[0]}"

    def test_timestamp_is_iso_format(self, context_pair):
        """
        HAPPY PATH: Timestamp is ISO 8601 format.
        """
        orch, ctx_a, ctx_b = context_pair

        result = orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="AGENT-iso"
        )

        sources = result.get("suggested_sources", [])
        ts_str = sources[0].get("suggested_at")

        try:
            datetime.fromisoformat(ts_str)
        except (ValueError, TypeError) as e:
            pytest.fail(f"suggested_at '{ts_str}' is not valid ISO format: {e}")

    def test_multiple_sources_ordered(self, context_pair):
        """
        EDGE: Sources in chronological order.
        """
        orch, ctx_a, ctx_b = context_pair

        agents = ["AGENT-first", "AGENT-second", "AGENT-third"]

        for agent in agents:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_b,
                ref_type="related_to",
                suggested_by=agent
            )
            time.sleep(0.01)

        ctx = orch.get_context(ctx_a)
        metadata = ctx.cross_sidebar_refs.get(ctx_b)
        sources = metadata.get("suggested_sources", [])

        source_ids = [s.get("source_id") for s in sources]
        assert source_ids == agents, \
            f"Sources should be in order: {source_ids}"


# =============================================================================
# 4.3 GET_CLUSTER_FLAGGED_REFS TESTS
# =============================================================================

class TestGetClusterFlaggedRefs:
    """
    Query clustered refs tests.
    """

    def test_returns_flagged_refs(self, fresh_orchestrator):
        """
        HAPPY PATH: Returns cluster_flagged=True refs only.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target Unflagged")
        ctx_c = orch.create_root_context(task_description="Target Flagged")

        # Unflagged ref (1 source)
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="solo"
        )

        # Flagged ref (3 sources)
        for agent in ["A1", "A2", "A3"]:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_c,
                ref_type="related_to",
                suggested_by=agent
            )

        result = orch.get_cluster_flagged_refs()

        assert result.get("success") is True
        flagged = result.get("cluster_flagged_refs", [])
        target_ids = [r.get("target_context_id") for r in flagged]

        assert ctx_c in target_ids, "Flagged ref should be in results"
        assert ctx_b not in target_ids, "Unflagged ref should NOT be in results"

    def test_excludes_validated_by_default(self, fresh_orchestrator):
        """
        HAPPY PATH: Validated refs excluded by default.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        # Create flagged ref
        for agent in ["A1", "A2", "A3"]:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_b,
                ref_type="related_to",
                suggested_by=agent
            )

        # Mark as validated
        ctx = orch.get_context(ctx_a)
        metadata = ctx.cross_sidebar_refs.get(ctx_b)
        metadata["human_validated"] = True

        result = orch.get_cluster_flagged_refs()
        flagged = result.get("cluster_flagged_refs", [])
        target_ids = [r.get("target_context_id") for r in flagged]

        assert ctx_b not in target_ids, \
            "Validated refs should be excluded by default"

    def test_includes_validated_when_requested(self, fresh_orchestrator):
        """
        HAPPY PATH: include_validated=True returns validated refs.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        # Create and flag
        for agent in ["A1", "A2", "A3"]:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_b,
                ref_type="related_to",
                suggested_by=agent
            )

        # Mark as validated
        ctx = orch.get_context(ctx_a)
        metadata = ctx.cross_sidebar_refs.get(ctx_b)
        metadata["human_validated"] = True

        result = orch.get_cluster_flagged_refs(include_validated=True)
        flagged = result.get("cluster_flagged_refs", [])
        target_ids = [r.get("target_context_id") for r in flagged]

        assert ctx_b in target_ids, \
            "With include_validated=True, validated refs SHOULD appear"

    def test_sorted_by_source_count(self, fresh_orchestrator):
        """
        EDGE: Results sorted by source_count descending.
        """
        orch = fresh_orchestrator

        ctx_source = orch.create_root_context(task_description="Source")
        ctx_3 = orch.create_root_context(task_description="3 sources")
        ctx_5 = orch.create_root_context(task_description="5 sources")

        # 3 sources
        for i in range(3):
            orch.add_cross_ref(
                source_context_id=ctx_source,
                target_context_id=ctx_3,
                ref_type="related_to",
                suggested_by=f"A{i}"
            )

        # 5 sources
        for i in range(5):
            orch.add_cross_ref(
                source_context_id=ctx_source,
                target_context_id=ctx_5,
                ref_type="related_to",
                suggested_by=f"B{i}"
            )

        result = orch.get_cluster_flagged_refs()
        flagged = result.get("cluster_flagged_refs", [])
        counts = [r.get("source_count") for r in flagged]

        assert counts == sorted(counts, reverse=True), \
            f"Should be sorted descending: {counts}"

    def test_empty_when_none_flagged(self, fresh_orchestrator):
        """
        EDGE: Empty list when no refs meet threshold.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        # Only 1 source - not flagged
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            suggested_by="lonely"
        )

        result = orch.get_cluster_flagged_refs()

        assert result.get("success") is True
        assert result.get("count") == 0
        assert result.get("cluster_flagged_refs") == []
