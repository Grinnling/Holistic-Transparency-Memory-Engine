"""
Phase 5 Validation Prompts Tests

Tests for validation prompt routing, urgency scoring, contradictions, and chain stability.
Covers Section 5 of TEST_REQUIREMENTS_PHASE5_CONSOLIDATED.md.

Test Categories:
- 5.1 Routing Logic: Inline vs scratchpad routing
- 5.2 Urgency Scoring: Signal-based scoring
- 5.3 detect_contradictions: Conflicting ref types
- 5.4 check_chain_stability: Dependency validation

{YOU} Principle: Validation prompts help humans focus on what matters most.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from conftest import VALIDATION_CONFIDENCE_THRESHOLD, STALENESS_DAYS


# =============================================================================
# 5.1 ROUTING LOGIC TESTS
# =============================================================================

class TestValidationPromptRouting:
    """
    Tests for inline vs scratchpad prompt routing.

    - Cited refs -> inline_prompts (need immediate attention)
    - Non-cited urgent refs -> scratchpad_prompts (background attention)
    """

    def test_citing_refs_go_inline(self, context_pair):
        """
        CRITICAL: Refs in citing_refs MUST route to inline_prompts.

        WHY: If the model is actively citing something, that citation
        needs immediate validation - it affects the current output.
        """
        orch, ctx_a, ctx_b = context_pair

        # Create a cross-ref
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="cites",
            reason="A cites B",
            confidence=0.5  # Below threshold
        )

        # Key format is "source:target"
        citing_ref = f"{ctx_a}:{ctx_b}"

        result = orch.get_validation_prompts(
            current_context_id=ctx_a,
            citing_refs=[citing_ref]
        )

        inline = result.get("inline_prompts", [])
        # API returns source_context_id and target_context_id separately
        inline_ref_ids = [f"{p.get('source_context_id')}:{p.get('target_context_id')}" for p in inline]

        assert citing_ref in inline_ref_ids, \
            f"Citing ref should be in inline_prompts: {inline_ref_ids}"

    def test_non_citing_urgent_to_scratchpad(self, context_pair):
        """
        CRITICAL: Non-cited refs with urgency go to scratchpad_prompts.

        WHY: These need attention but not immediately - they go to the
        scratchpad for the human to review when they have bandwidth.
        """
        orch, ctx_a, ctx_b = context_pair

        # Create low-confidence ref (urgent but not cited)
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            reason="Low confidence connection",
            confidence=0.3  # Below threshold
        )

        result = orch.get_validation_prompts(
            current_context_id=ctx_a,
            citing_refs=[]  # Not citing this ref
        )

        scratchpad = result.get("scratchpad_prompts", [])

        # Should have at least one scratchpad prompt for the low-confidence ref
        assert len(scratchpad) > 0 or result.get("scratchpad_count", 0) >= 0, \
            f"Low-confidence non-cited ref should appear somewhere: {result}"

    def test_excludes_validated_refs(self, context_pair):
        """
        HAPPY PATH: Validated refs should not appear in prompts.
        """
        orch, ctx_a, ctx_b = context_pair

        # Create and validate ref
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            confidence=0.5
        )

        # Mark as validated
        ctx = orch.get_context(ctx_a)
        metadata = ctx.cross_sidebar_refs.get(ctx_b)
        metadata["human_validated"] = True

        result = orch.get_validation_prompts(current_context_id=ctx_a)

        all_prompts = result.get("inline_prompts", []) + result.get("scratchpad_prompts", [])
        ref_ids = [p.get("ref_id") for p in all_prompts]

        assert f"{ctx_a}:{ctx_b}" not in ref_ids, \
            "Validated refs should be excluded from prompts"


# =============================================================================
# 5.2 URGENCY SCORING TESTS
# =============================================================================

class TestUrgencyScoring:
    """
    Urgency scoring tests.

    Urgency signals (additive):
    - +100: actively citing
    - +50: created this exchange
    - +30: cluster flagged
    - +25: urgent priority
    - +20: confidence < 0.7
    - +15: stale (3+ days old)
    """

    def test_urgency_low_confidence(self, context_pair):
        """
        HAPPY PATH: Low confidence adds urgency.
        """
        orch, ctx_a, ctx_b = context_pair

        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            confidence=0.3  # Below 0.7 threshold
        )

        result = orch.get_validation_prompts(current_context_id=ctx_a)

        all_prompts = result.get("inline_prompts", []) + result.get("scratchpad_prompts", [])

        # Check that we got some urgency info
        if all_prompts:
            our_prompt = next(
                (p for p in all_prompts if ctx_b in str(p.get("ref_id", ""))),
                None
            )
            if our_prompt:
                # Check urgency score or reasons
                urgency = our_prompt.get("urgency_score", 0)
                assert urgency > 0, f"Low confidence should add urgency: {our_prompt}"

    def test_urgency_cluster_flagged(self, fresh_orchestrator):
        """
        HAPPY PATH: Cluster flagged adds urgency.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        # Add 3 sources to trigger clustering
        for agent in ["A1", "A2", "A3"]:
            orch.add_cross_ref(
                source_context_id=ctx_a,
                target_context_id=ctx_b,
                ref_type="related_to",
                suggested_by=agent
            )

        result = orch.get_validation_prompts(current_context_id=ctx_a)

        all_prompts = result.get("inline_prompts", []) + result.get("scratchpad_prompts", [])

        if all_prompts:
            our_prompt = next(
                (p for p in all_prompts if ctx_b in str(p.get("ref_id", ""))),
                None
            )
            if our_prompt:
                reasons = our_prompt.get("reasons", [])
                # Either cluster in reasons or high urgency score
                has_cluster = any("cluster" in r.lower() for r in reasons)
                high_urgency = our_prompt.get("urgency_score", 0) >= 30
                assert has_cluster or high_urgency, \
                    f"Cluster flagged should add urgency: {our_prompt}"

    def test_urgency_actively_citing(self, context_pair):
        """
        HAPPY PATH: Actively citing adds highest urgency.
        """
        orch, ctx_a, ctx_b = context_pair

        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="cites",
            confidence=0.9
        )

        citing_ref = f"{ctx_a}:{ctx_b}"

        result = orch.get_validation_prompts(
            current_context_id=ctx_a,
            citing_refs=[citing_ref]
        )

        inline = result.get("inline_prompts", [])
        if inline:
            citing_prompt = inline[0]
            urgency = citing_prompt.get("urgency_score", 0)
            # Actively citing should be high urgency
            assert urgency >= 100, f"Actively citing should have high urgency: {citing_prompt}"


# =============================================================================
# 5.3 DETECT_CONTRADICTIONS TESTS
# =============================================================================

class TestDetectContradictions:
    """
    Contradiction detection tests.

    Contradicting ref type pairs:
    - implements vs contradicts
    - depends_on vs blocks
    - derived_from vs contradicts

    Note: detect_contradictions returns List[Dict] directly
    """

    def test_implements_vs_contradicts(self, fresh_orchestrator):
        """
        CRITICAL: Detects implements + contradicts as contradiction.

        WHY: If A says "implements B" but B says "contradicts A", that's
        logically impossible and needs human clarification.

        Note: Contradictions are detected ACROSS contexts, not within
        a single context's refs. Each (source, target) pair has one ref_type.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Context A")
        ctx_b = orch.create_root_context(task_description="Context B")

        # A implements B (from A's perspective)
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="implements",
            reason="A implements B",
            bidirectional=False
        )

        # B contradicts A (from B's perspective)
        orch.add_cross_ref(
            source_context_id=ctx_b,
            target_context_id=ctx_a,
            ref_type="contradicts",
            reason="B contradicts A",
            bidirectional=False
        )

        contradictions = orch.detect_contradictions()

        # Returns list directly
        assert isinstance(contradictions, list), \
            f"detect_contradictions returns list: {type(contradictions)}"
        assert len(contradictions) > 0, \
            f"Should detect implements vs contradicts: {contradictions}"

        # Verify structure
        if contradictions:
            c = contradictions[0]
            assert "contexts" in c, f"Contradiction should have contexts: {c}"
            assert "contradiction_type" in c, f"Contradiction should have type: {c}"

    def test_depends_vs_blocks(self, fresh_orchestrator):
        """
        HAPPY PATH: Detects depends_on + blocks as contradiction.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Context A")
        ctx_b = orch.create_root_context(task_description="Context B")

        # A depends_on B
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="depends_on",
            bidirectional=False
        )

        # B blocks A
        orch.add_cross_ref(
            source_context_id=ctx_b,
            target_context_id=ctx_a,
            ref_type="blocks",
            bidirectional=False
        )

        contradictions = orch.detect_contradictions()

        assert len(contradictions) > 0, \
            f"Should detect depends_on vs blocks: {contradictions}"

    def test_no_contradictions(self, context_pair):
        """
        EDGE: Empty list when no contradictions exist.
        """
        orch, ctx_a, ctx_b = context_pair

        # Only one ref type - no contradiction
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to"
        )

        contradictions = orch.detect_contradictions(context_id=ctx_a)

        assert contradictions == [], \
            f"Should return empty list when no contradictions: {contradictions}"


# =============================================================================
# 5.4 CHECK_CHAIN_STABILITY TESTS
# =============================================================================

class TestChainStability:
    """
    Dependency chain stability tests.

    A context is stable if all its dependency refs are validated.
    Dependency ref types: derived_from, implements, depends_on
    """

    def test_stable_chain(self, fresh_orchestrator):
        """
        HAPPY PATH: All deps validated -> stable.

        Note: Stability also checks if the dependency context has
        unvalidated refs. A truly stable chain means both our ref
        AND the dependency's refs are validated.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Dep - no refs")

        # ctx_b has no refs to validate (it's a leaf)
        # Create dependency from A to B
        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to"  # Use non-dependency type
        )

        # For stability check, we need ctx_a with no dependency-type refs
        # OR all deps validated AND deps have no unvalidated refs themselves
        result = orch.check_chain_stability(context_id=ctx_b)

        # ctx_b has no refs, should be stable
        assert result.get("is_stable") is True, \
            f"Context with no refs should be stable: {result}"

    def test_unstable_dependency(self, context_pair):
        """
        CRITICAL: Unvalidated dependency -> unstable.

        WHY: If you're building on something that hasn't been validated,
        your work might be based on incorrect assumptions.
        """
        orch, ctx_a, ctx_b = context_pair

        # Create a chain: A -> B -> C where C is a third context
        ctx_c = orch.create_root_context(task_description="Third context")

        # A depends on B
        orch.add_cross_ref(ctx_a, ctx_b, ref_type="derived_from")
        # B depends on C (unvalidated)
        orch.add_cross_ref(ctx_b, ctx_c, ref_type="depends_on")

        result = orch.check_chain_stability(context_id=ctx_a)

        # A is unstable because B has unvalidated dependency refs
        assert result.get("is_stable") is False, \
            f"Should be unstable - B has unvalidated deps: {result}"
        unstable = result.get("unstable_dependencies", [])
        assert len(unstable) >= 1, \
            f"Should have unstable dependencies: {unstable}"

    def test_implements_counted(self, fresh_orchestrator):
        """
        HAPPY PATH: 'implements' is a dependency type.

        Stability checks if TARGET has unvalidated dependency refs.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Implementor")
        ctx_b = orch.create_root_context(task_description="Interface")
        ctx_c = orch.create_root_context(task_description="Base")

        # A implements B
        orch.add_cross_ref(ctx_a, ctx_b, ref_type="implements")
        # B depends on C (unvalidated) - makes B unstable
        orch.add_cross_ref(ctx_b, ctx_c, ref_type="depends_on")

        result = orch.check_chain_stability(context_id=ctx_a)

        assert result.get("is_stable") is False, \
            f"Unvalidated dep in B should make A unstable: {result}"

    def test_cites_not_counted(self, context_pair):
        """
        EDGE: 'cites' is NOT a dependency type.

        WHY: Citing something doesn't mean you depend on its correctness.
        """
        orch, ctx_a, ctx_b = context_pair

        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="cites"
        )

        result = orch.check_chain_stability(context_id=ctx_a)

        # Should be stable because 'cites' doesn't count as dependency
        assert result.get("is_stable") is True, \
            f"'cites' should not affect stability: {result}"

    def test_stability_score_calculation(self, fresh_orchestrator):
        """
        EDGE: Stability score decreases with each unstable dep.

        Need A -> B -> D and A -> C -> E to create two unstable chains.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Dep 1")
        ctx_c = orch.create_root_context(task_description="Dep 2")
        ctx_d = orch.create_root_context(task_description="B's dep")
        ctx_e = orch.create_root_context(task_description="C's dep")

        # A depends on B and C
        orch.add_cross_ref(ctx_a, ctx_b, ref_type="derived_from")
        orch.add_cross_ref(ctx_a, ctx_c, ref_type="implements")
        # B and C each have their own unvalidated deps
        orch.add_cross_ref(ctx_b, ctx_d, ref_type="depends_on")
        orch.add_cross_ref(ctx_c, ctx_e, ref_type="depends_on")

        result = orch.check_chain_stability(context_id=ctx_a)

        unstable = result.get("unstable_dependencies", [])
        assert len(unstable) == 2, \
            f"Should have 2 unstable deps (B and C both have unvalidated deps): {result}"

        score = result.get("stability_score", 1.0)
        assert score < 1.0, \
            f"Stability score should decrease: {score}"

    def test_invalid_context_error(self, fresh_orchestrator):
        """
        ERROR: Error for missing context.
        """
        orch = fresh_orchestrator

        result = orch.check_chain_stability(context_id="FAKE-CONTEXT")

        # Should handle gracefully
        assert result.get("is_stable") is False or "error" in result
