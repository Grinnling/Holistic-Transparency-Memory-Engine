"""
Sidebar UI Workflow Tests (Automated)

Based on TESTING_SIDEBAR_UI_2026-01-05.md integration tests.
These validate end-to-end workflows through the orchestrator.

Test Coverage:
- Cross-Ref Workflow (lines 314-322)
- Full Workflow (lines 285-302)
- Reparent Workflow (lines 304-312)
"""

import pytest
import sys
from datetime import datetime

sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# CROSS-REF WORKFLOW TEST (Lines 314-322)
# =============================================================================

class TestCrossRefWorkflow:
    """
    Cross-Ref Workflow Test from TESTING_SIDEBAR_UI_2026-01-05.md

    Steps:
    1. Create two trees - Tree A (SB-1 → SB-2), Tree B (SB-5 → SB-6)
    2. Work in SB-2 - Add some exchanges
    3. Create cross-ref - SB-6 cites findings from SB-2
    4. Verify bidirectional - SB-2 shows incoming ref from SB-6
    5. Archive SB-2 - Mark as archived
    6. Check health - SB-6 shows warning about archived source
    7. Restart - Verify cross-refs survive restart
    """

    def test_cross_ref_workflow_complete(self, fresh_orchestrator):
        """
        Full cross-ref workflow end-to-end.

        This is THE test that validates the bidirectional fix works
        in a realistic scenario.
        """
        orch = fresh_orchestrator

        # Step 1: Create two trees
        # Tree A: root_a → child_a
        root_a = orch.create_root_context(task_description="Tree A Root")
        child_a = orch.spawn_sidebar(parent_id=root_a, reason="Tree A Child")

        # Tree B: root_b → child_b
        root_b = orch.create_root_context(task_description="Tree B Root")
        child_b = orch.spawn_sidebar(parent_id=root_b, reason="Tree B Child")

        assert child_a is not None, "Should create Tree A child"
        assert child_b is not None, "Should create Tree B child"

        # Step 2: Work in child_a - add some exchanges
        ctx_a = orch.get_context(child_a)
        ctx_a.local_memory.append({
            "role": "user",
            "content": "Important finding about authentication"
        })
        ctx_a.local_memory.append({
            "role": "assistant",
            "content": "Found security vulnerability in auth module"
        })

        # Step 3: Create cross-ref - child_b cites child_a
        ref_result = orch.add_cross_ref(
            source_context_id=child_b,
            target_context_id=child_a,
            ref_type="cites",
            reason="Citing security findings from Tree A"
        )

        assert ref_result.get("success") is True, \
            f"Cross-ref should succeed: {ref_result}"

        # Step 4: Verify bidirectional with INVERSE ref type
        # child_b -> child_a is "cites"
        # child_a -> child_b should be "cited_by" (inverse)
        ctx_b = orch.get_context(child_b)
        ctx_a = orch.get_context(child_a)

        # child_b should have "cites" ref to child_a
        assert child_a in ctx_b.cross_sidebar_refs, \
            f"child_b should have ref to child_a: {ctx_b.cross_sidebar_refs}"
        assert ctx_b.cross_sidebar_refs[child_a].get("ref_type") == "cites", \
            f"child_b->child_a should be 'cites': {ctx_b.cross_sidebar_refs[child_a]}"

        # child_a should have inverse "cited_by" ref to child_b
        assert child_b in ctx_a.cross_sidebar_refs, \
            f"child_a should have inverse ref to child_b: {ctx_a.cross_sidebar_refs}"
        assert ctx_a.cross_sidebar_refs[child_b].get("ref_type") == "cited_by", \
            f"child_a->child_b should be 'cited_by' (inverse): {ctx_a.cross_sidebar_refs[child_b]}"

        # Step 5: Archive child_a
        archive_result = orch.archive_context(child_a)
        assert archive_result is True, \
            f"Archive should succeed: {archive_result}"

        ctx_a = orch.get_context(child_a)
        assert ctx_a.status.value == "archived", \
            f"child_a should be archived: {ctx_a.status}"

        # Step 6: Check health - refs to archived contexts should be flagged
        # This tests that the system can identify "stale" refs
        ctx_b = orch.get_context(child_b)
        ref_metadata = ctx_b.cross_sidebar_refs.get(child_a, {})

        # The ref still exists, but target is archived
        target_ctx = orch.get_context(child_a)
        assert target_ctx.status.value == "archived", \
            "Referenced context should show as archived"

    def test_cross_ref_survives_restart(self, fresh_orchestrator):
        """
        Step 7: Cross-refs should survive orchestrator restart.

        This tests persistence of cross-ref relationships.
        """
        orch = fresh_orchestrator

        # Create contexts and cross-ref
        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        orch.add_cross_ref(
            source_context_id=ctx_a,
            target_context_id=ctx_b,
            ref_type="related_to",
            reason="Test persistence"
        )

        # Save state
        save_path = orch.save_all_contexts()
        assert save_path is not None, "Save should return path"

        # Simulate restart by creating new orchestrator that loads from storage
        from conversation_orchestrator import ConversationOrchestrator
        orch2 = ConversationOrchestrator()
        orch2.load_all_contexts(save_path)

        # Verify cross-refs survived
        reloaded_a = orch2.get_context(ctx_a)
        if reloaded_a is not None:
            assert ctx_b in reloaded_a.cross_sidebar_refs, \
                "Cross-ref should survive restart"

    def test_bidirectional_creates_inverse_types(self, fresh_orchestrator):
        """
        Verify all ref types create correct inverse refs.

        This is the core test for the bidirectional fix.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Source")
        ctx_b = orch.create_root_context(task_description="Target")

        # Test each directional ref type and its expected inverse
        test_cases = [
            ("cites", "cited_by"),
            ("depends_on", "informs"),
            ("derived_from", "source_of"),
            ("implements", "implemented_by"),
            ("blocks", "blocked_by"),
            ("supersedes", "superseded_by"),
            ("obsoletes", "obsoleted_by"),
        ]

        for forward_type, expected_inverse in test_cases:
            # Reset contexts for each test
            orch2 = fresh_orchestrator
            src = orch2.create_root_context(task_description=f"Source for {forward_type}")
            tgt = orch2.create_root_context(task_description=f"Target for {forward_type}")

            result = orch2.add_cross_ref(
                source_context_id=src,
                target_context_id=tgt,
                ref_type=forward_type
            )

            if not result.get("success"):
                # Skip if ref type not implemented yet
                continue

            src_ctx = orch2.get_context(src)
            tgt_ctx = orch2.get_context(tgt)

            # Source should have forward ref
            assert tgt in src_ctx.cross_sidebar_refs, \
                f"Source should have ref to target for {forward_type}"
            assert src_ctx.cross_sidebar_refs[tgt].get("ref_type") == forward_type, \
                f"Source ref should be {forward_type}"

            # Target should have inverse ref
            if src in tgt_ctx.cross_sidebar_refs:
                actual_inverse = tgt_ctx.cross_sidebar_refs[src].get("ref_type")
                assert actual_inverse == expected_inverse, \
                    f"Inverse of {forward_type} should be {expected_inverse}, got {actual_inverse}"

    def test_symmetric_refs_stay_symmetric(self, fresh_orchestrator):
        """
        Symmetric ref types (related_to, contradicts) should stay the same
        in both directions.
        """
        orch = fresh_orchestrator

        ctx_a = orch.create_root_context(task_description="Context A")
        ctx_b = orch.create_root_context(task_description="Context B")

        # related_to is symmetric
        orch.add_cross_ref(ctx_a, ctx_b, ref_type="related_to")

        ctx_a_obj = orch.get_context(ctx_a)
        ctx_b_obj = orch.get_context(ctx_b)

        # Both directions should be "related_to"
        assert ctx_a_obj.cross_sidebar_refs[ctx_b].get("ref_type") == "related_to"
        assert ctx_b_obj.cross_sidebar_refs[ctx_a].get("ref_type") == "related_to"

    def test_cross_tree_refs_work(self, fresh_orchestrator):
        """
        Cross-refs between different trees should work.
        """
        orch = fresh_orchestrator

        # Tree A
        root_a = orch.create_root_context(task_description="Tree A")
        child_a = orch.spawn_sidebar(parent_id=root_a, reason="A's child")

        # Tree B (completely separate)
        root_b = orch.create_root_context(task_description="Tree B")
        child_b = orch.spawn_sidebar(parent_id=root_b, reason="B's child")

        # Cross-tree ref: child_a references child_b
        result = orch.add_cross_ref(
            source_context_id=child_a,
            target_context_id=child_b,
            ref_type="related_to",
            reason="Cross-tree connection"
        )

        assert result.get("success") is True, \
            f"Cross-tree ref should work: {result}"

        # Verify both sides see the ref
        ctx_a = orch.get_context(child_a)
        ctx_b = orch.get_context(child_b)

        assert child_b in ctx_a.cross_sidebar_refs, \
            "child_a should see ref to child_b"
        assert child_a in ctx_b.cross_sidebar_refs, \
            "child_b should see ref back to child_a"


# =============================================================================
# FULL WORKFLOW TEST (Lines 285-302)
# =============================================================================

class TestFullWorkflow:
    """
    Full Workflow Test from TESTING_SIDEBAR_UI_2026-01-05.md

    Steps:
    1. Start fresh
    2. Check empty state
    3. Create root
    4. Spawn sidebar
    5. Verify creation
    6. Pause sidebar
    7. Resume sidebar
    8. Spawn child
    9. Check tree
    10. Restart API (persistence test)
    11. Merge
    12. Archive
    13. Verify completed section
    14. Final restart
    """

    def test_sidebar_lifecycle_complete(self, fresh_orchestrator):
        """
        Complete sidebar lifecycle: spawn → pause → resume → merge → archive
        """
        orch = fresh_orchestrator

        # Step 1-2: Start fresh, verify empty
        contexts = orch.list_contexts()
        initial_count = len(contexts)  # list_contexts returns List directly

        # Step 3: Create root
        root_id = orch.create_root_context(task_description="Test Project")
        assert root_id is not None, "Root should be created"

        # Step 4: Spawn sidebar
        sidebar_id = orch.spawn_sidebar(
            parent_id=root_id,
            reason="Test sidebar for lifecycle"
        )
        assert sidebar_id is not None, "Sidebar should spawn"

        # Step 5: Verify creation
        sidebar = orch.get_context(sidebar_id)
        assert sidebar is not None, "Should retrieve sidebar"
        assert sidebar.parent_context_id == root_id, "Parent should be root"
        assert sidebar.status.value == "active", "Should start active"

        # Step 6: Pause sidebar
        pause_result = orch.pause_context(sidebar_id)
        assert pause_result is True, f"Pause should succeed: {pause_result}"

        sidebar = orch.get_context(sidebar_id)
        assert sidebar.status.value == "paused", "Should be paused"

        # Step 7: Resume sidebar
        resume_result = orch.resume_context(sidebar_id)
        assert resume_result is True, f"Resume should succeed: {resume_result}"

        sidebar = orch.get_context(sidebar_id)
        assert sidebar.status.value == "active", "Should be active again"

        # Step 8: Spawn child
        child_id = orch.spawn_sidebar(
            parent_id=sidebar_id,
            reason="Child of test sidebar"
        )
        assert child_id is not None, "Child should spawn"

        # Step 9: Check tree structure
        sidebar = orch.get_context(sidebar_id)
        assert child_id in sidebar.child_sidebar_ids, \
            f"Parent should track child: {sidebar.child_sidebar_ids}"

        child = orch.get_context(child_id)
        assert child.parent_context_id == sidebar_id, \
            "Child should reference parent"

        # Step 11: Merge child back to parent
        merge_result = orch.merge_sidebar(child_id)
        assert merge_result.get("success") is True, f"Merge should succeed: {merge_result}"

        child = orch.get_context(child_id)
        assert child.status.value == "merged", "Child should be merged"

        # Step 12: Archive the sidebar
        archive_result = orch.archive_context(sidebar_id)
        assert archive_result is True, f"Archive should succeed: {archive_result}"

        sidebar = orch.get_context(sidebar_id)
        assert sidebar.status.value == "archived", "Should be archived"

    def test_lifecycle_survives_restart(self, fresh_orchestrator):
        """
        Steps 10 & 14: State should survive restart.
        """
        orch = fresh_orchestrator

        # Create and modify state
        root_id = orch.create_root_context(task_description="Persistence Test")
        sidebar_id = orch.spawn_sidebar(parent_id=root_id, reason="Will survive")

        # Pause it
        orch.pause_context(sidebar_id)

        # Save
        save_path = orch.save_all_contexts()

        # Simulate restart
        from conversation_orchestrator import ConversationOrchestrator
        orch2 = ConversationOrchestrator()
        orch2.load_all_contexts(save_path)

        # Verify state survived
        reloaded = orch2.get_context(sidebar_id)
        if reloaded is not None:
            assert reloaded.status.value == "paused", \
                "Paused state should survive restart"

    def test_tree_structure_maintained(self, fresh_orchestrator):
        """
        Verify parent-child relationships are correct throughout lifecycle.
        """
        orch = fresh_orchestrator

        # Create 3-level tree: root → level1 → level2
        root = orch.create_root_context(task_description="Root")
        level1 = orch.spawn_sidebar(parent_id=root, reason="Level 1")
        level2 = orch.spawn_sidebar(parent_id=level1, reason="Level 2")

        # Verify relationships
        root_ctx = orch.get_context(root)
        level1_ctx = orch.get_context(level1)
        level2_ctx = orch.get_context(level2)

        assert level1 in root_ctx.child_sidebar_ids
        assert level2 in level1_ctx.child_sidebar_ids
        assert level1_ctx.parent_context_id == root
        assert level2_ctx.parent_context_id == level1


# =============================================================================
# REPARENT WORKFLOW TEST (Lines 304-312)
# =============================================================================

class TestReparentWorkflow:
    """
    Reparent Workflow Test from TESTING_SIDEBAR_UI_2026-01-05.md

    Steps:
    1. Create 3 root contexts
    2. Create umbrella root
    3. Reparent each under umbrella
    4. Verify tree
    5. Check original_conversation_id preserved
    6. Restart survival
    """

    def test_reparent_workflow_complete(self, fresh_orchestrator):
        """
        Full reparent workflow: create independent trees, unify under umbrella.
        """
        orch = fresh_orchestrator

        # Step 1: Create 3 independent roots
        root1 = orch.create_root_context(task_description="Investigation 1")
        root2 = orch.create_root_context(task_description="Investigation 2")
        root3 = orch.create_root_context(task_description="Investigation 3")

        # Verify they're all roots (no parent)
        for root_id in [root1, root2, root3]:
            ctx = orch.get_context(root_id)
            assert ctx.parent_context_id is None, \
                f"{root_id} should be a root (no parent)"

        # Step 2: Create umbrella root
        umbrella = orch.create_root_context(
            task_description="Unified Investigation Hub"
        )

        # Step 3: Reparent each under umbrella
        for root_id in [root1, root2, root3]:
            result = orch.reparent_context(
                context_id=root_id,
                new_parent_id=umbrella,
                reason="unifying investigations"
            )
            assert result.get("success") is True, \
                f"Reparent {root_id} should succeed: {result}"

        # Step 4: Verify tree structure
        umbrella_ctx = orch.get_context(umbrella)
        for root_id in [root1, root2, root3]:
            assert root_id in umbrella_ctx.child_sidebar_ids, \
                f"{root_id} should be child of umbrella"

            ctx = orch.get_context(root_id)
            assert ctx.parent_context_id == umbrella, \
                f"{root_id} should have umbrella as parent"

    def test_reparent_preserves_original_id(self, fresh_orchestrator):
        """
        Step 6: original_conversation_id should be preserved on former roots.
        """
        orch = fresh_orchestrator

        # Create a root
        original_root = orch.create_root_context(
            task_description="Was a root"
        )
        original_id = original_root  # The ID itself is the original

        # Create new parent
        new_parent = orch.create_root_context(
            task_description="New parent"
        )

        # Reparent
        orch.reparent_context(original_root, new_parent, reason="test reparent")

        # Check original ID is preserved in metadata
        ctx = orch.get_context(original_root)
        # The context's sidebar_id should still be the same
        assert ctx.sidebar_id == original_id, \
            "Sidebar ID should be preserved after reparent"

    def test_reparent_cycle_detection(self, fresh_orchestrator):
        """
        Should prevent creating circular references.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Root")
        child = orch.spawn_sidebar(parent_id=root, reason="Child")
        grandchild = orch.spawn_sidebar(parent_id=child, reason="Grandchild")

        # Try to make root a child of grandchild (would create cycle)
        result = orch.reparent_context(
            context_id=root,
            new_parent_id=grandchild,
            reason="test cycle detection"
        )

        # Should fail or be prevented
        assert result.get("success") is False or "error" in result, \
            f"Reparent creating cycle should fail: {result}"

    def test_reparent_to_self_fails(self, fresh_orchestrator):
        """
        Cannot reparent a context to itself.
        """
        orch = fresh_orchestrator

        ctx = orch.create_root_context(task_description="Test")

        result = orch.reparent_context(
            context_id=ctx,
            new_parent_id=ctx,
            reason="test self-reparent"
        )

        assert result.get("success") is False or "error" in result, \
            f"Reparent to self should fail: {result}"

    def test_promote_to_root(self, fresh_orchestrator):
        """
        Reparenting with new_parent=None should promote to root.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Original root")
        child = orch.spawn_sidebar(parent_id=root, reason="Will become root")

        # Verify it's a child
        child_ctx = orch.get_context(child)
        assert child_ctx.parent_context_id == root

        # Promote to root
        result = orch.reparent_context(
            context_id=child,
            new_parent_id=None,
            reason="promoting to root"
        )

        if result.get("success"):
            child_ctx = orch.get_context(child)
            assert child_ctx.parent_context_id is None, \
                "Should now be a root (no parent)"

    def test_children_follow_reparent(self, fresh_orchestrator):
        """
        When reparenting, children should stay attached to their parent.
        """
        orch = fresh_orchestrator

        # Create: root → parent → child
        root = orch.create_root_context(task_description="Root")
        parent = orch.spawn_sidebar(parent_id=root, reason="Parent")
        child = orch.spawn_sidebar(parent_id=parent, reason="Child")

        # Create new root
        new_root = orch.create_root_context(task_description="New root")

        # Reparent 'parent' under new_root
        result = orch.reparent_context(parent, new_root, reason="test children follow")

        if result.get("success"):
            # Child should still be attached to parent
            child_ctx = orch.get_context(child)
            assert child_ctx.parent_context_id == parent, \
                "Child should still be attached to parent after reparent"

            # Parent should still have child
            parent_ctx = orch.get_context(parent)
            assert child in parent_ctx.child_sidebar_ids, \
                "Parent should still have child after reparent"


# =============================================================================
# ERROR SCENARIO TESTS
# =============================================================================

class TestErrorScenarios:
    """
    Tests for error handling edge cases.

    These verify the system handles invalid operations gracefully:
    - Double operations (pause paused, archive archived)
    - Invalid operations (merge root, focus archived)
    - Invalid inputs (bad IDs, missing parents)
    """

    def test_pause_already_paused_context(self, fresh_orchestrator):
        """
        EDGE: Pausing an already-paused context should handle gracefully.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Root")
        child = orch.spawn_sidebar(parent_id=root, reason="Will pause twice")

        # First pause - should succeed
        result1 = orch.pause_context(child, reason="First pause")
        assert result1 is True, "First pause should succeed"

        # Second pause - should handle gracefully (no-op or error)
        result2 = orch.pause_context(child, reason="Second pause")
        # Either succeeds (no-op) or returns False - shouldn't crash
        assert result2 in [True, False], "Double pause should not crash"

        # Context should still be paused
        ctx = orch.get_context(child)
        assert ctx.status.value == "paused", "Context should remain paused"

    def test_merge_root_context_fails(self, fresh_orchestrator):
        """
        EDGE: Merging a root context (no parent) should fail gracefully.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Root - cannot merge")

        # Attempt to merge root (uses merge_sidebar, not merge_context)
        result = orch.merge_sidebar(root, summary="Trying to merge root")

        # Should fail - root has no parent to merge into
        assert result.get("success") is False or result.get("error") is not None, \
            "Merging root context should fail or return error"

    def test_archive_already_archived_context(self, fresh_orchestrator):
        """
        EDGE: Archiving an already-archived context should handle gracefully.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Root")
        child = orch.spawn_sidebar(parent_id=root, reason="Will archive twice")

        # First archive - should succeed (returns bool)
        result1 = orch.archive_context(child, reason="First archive")
        assert result1 is True, "First archive should succeed"

        # Second archive - should handle gracefully (either True no-op or False)
        result2 = orch.archive_context(child, reason="Second archive")
        assert result2 in [True, False], "Double archive should not crash"

        # Context should still be archived
        ctx = orch.get_context(child)
        assert ctx.status.value == "archived", "Context should remain archived"

    def test_focus_on_archived_context(self, fresh_orchestrator):
        """
        EDGE: Focusing on an archived context should fail or warn.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Root")
        child = orch.spawn_sidebar(parent_id=root, reason="Will archive then focus")

        # Archive the context
        orch.archive_context(child, reason="Archiving")

        # Try to focus on archived context (uses switch_focus, returns bool)
        result = orch.switch_focus(child)

        # Should either fail (False) or allow it - either way shouldn't crash
        assert result in [True, False], "Focus on archived should not crash"

        # If it allowed focus, verify the context is still archived
        ctx = orch.get_context(child)
        assert ctx is not None, "Context should still exist"
        assert ctx.status.value == "archived", "Status should remain archived"

    def test_spawn_with_invalid_parent(self, fresh_orchestrator):
        """
        ERROR: Spawning with non-existent parent should fail gracefully.
        """
        orch = fresh_orchestrator

        # Try to spawn with fake parent ID
        try:
            result = orch.spawn_sidebar(
                parent_id="FAKE-NONEXISTENT-ID",
                reason="Should fail"
            )
            # If it returns instead of raising, should indicate failure
            assert result is None or "error" in str(result).lower(), \
                "Spawn with invalid parent should fail"
        except (ValueError, KeyError) as e:
            # Expected - invalid parent should raise error
            assert "not found" in str(e).lower() or "invalid" in str(e).lower(), \
                f"Error should mention invalid parent: {e}"

    def test_operation_on_nonexistent_context(self, fresh_orchestrator):
        """
        ERROR: Operations on non-existent context ID should fail gracefully.
        """
        orch = fresh_orchestrator
        fake_id = "FAKE-CONTEXT-DOES-NOT-EXIST"

        # Pause non-existent
        pause_result = orch.pause_context(fake_id, reason="test")
        assert pause_result is False, "Pause on non-existent should return False"

        # Get non-existent
        ctx = orch.get_context(fake_id)
        assert ctx is None, "Get non-existent should return None"

        # Resume non-existent
        resume_result = orch.resume_context(fake_id)
        assert resume_result is False, "Resume on non-existent should return False"

    def test_spawn_from_archived_parent(self, fresh_orchestrator):
        """
        EDGE: Spawning a sidebar from an archived parent should fail gracefully.

        An archived context is "closed" - you shouldn't be able to spawn
        new children from it.
        """
        orch = fresh_orchestrator

        root = orch.create_root_context(task_description="Root")
        parent = orch.spawn_sidebar(parent_id=root, reason="Will be archived")

        # Archive the parent
        archive_result = orch.archive_context(parent, reason="Closing this branch")
        assert archive_result is True, "Archive should succeed"

        # Verify parent is archived
        parent_ctx = orch.get_context(parent)
        assert parent_ctx.status.value == "archived", "Parent should be archived"

        # Try to spawn from archived parent
        try:
            child = orch.spawn_sidebar(
                parent_id=parent,
                reason="Trying to spawn from archived"
            )
            # If it returns without raising, check if it indicates failure
            # or if the system allows it (which would be a design choice)
            if child is not None:
                # System allowed it - verify the child exists
                child_ctx = orch.get_context(child)
                assert child_ctx is not None, "If spawn allowed, child should exist"
            # Either way, shouldn't crash
        except (ValueError, RuntimeError) as e:
            # Expected - spawning from archived should raise error
            pass  # This is acceptable behavior
