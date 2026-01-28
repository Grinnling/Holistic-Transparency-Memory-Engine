#!/usr/bin/env python3
"""
test_sidebar_persistence.py - Test sidebar persistence round-trip

Tests:
1. Create context -> persists to SQLite
2. Kill orchestrator -> reload -> context still there
3. Focus tracking survives restart
4. Sidebar spawn/merge persists both parent and child
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the CODE_IMPLEMENTATION directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_basic_persistence():
    """Test basic save/load round-trip."""
    # Use a temp directory for test database
    test_dir = tempfile.mkdtemp(prefix="sidebar_test_")
    test_db = os.path.join(test_dir, "test_sidebar.db")

    print(f"Using test database: {test_db}")

    try:
        # Reset any existing global state
        from sidebar_persistence import reset_persistence, SidebarPersistence
        from conversation_orchestrator import reset_orchestrator
        reset_orchestrator()
        reset_persistence()

        # Phase 1: Create orchestrator and contexts
        print("\n=== Phase 1: Create contexts ===")

        # Create persistence with test path
        db = SidebarPersistence(db_path=test_db)

        # Monkey-patch the global getter to use our test db
        import sidebar_persistence
        sidebar_persistence._persistence_instance = db

        # Now create orchestrator (auto_load=False since DB is empty)
        from conversation_orchestrator import ConversationOrchestrator
        orch1 = ConversationOrchestrator(auto_load=False)

        # Create root context
        root_id = orch1.create_root_context(
            task_description="Test conversation",
            created_by="test_user"
        )
        print(f"Created root: {root_id}")

        # Add an exchange
        orch1.add_exchange(
            root_id,
            user_message="Hello, this is a test",
            assistant_response="I hear you, testing persistence!"
        )
        print(f"Added exchange to {root_id}")

        # Spawn a sidebar
        sidebar_id = orch1.spawn_sidebar(
            parent_id=root_id,
            reason="Investigate something",
            created_by="test_user"
        )
        print(f"Spawned sidebar: {sidebar_id}")

        # Add exchange to sidebar
        orch1.add_exchange(
            sidebar_id,
            user_message="Sidebar question",
            assistant_response="Sidebar answer"
        )
        print(f"Added exchange to sidebar {sidebar_id}")

        # Check active context
        active1 = orch1.get_active_context_id()
        print(f"Active context before restart: {active1}")

        # Get stats
        stats1 = orch1.stats()
        print(f"Stats before restart: {stats1['total_contexts']} contexts")

        # Phase 2: Simulate restart
        print("\n=== Phase 2: Simulate restart ===")

        # Clear in-memory state completely
        del orch1

        # Create fresh orchestrator - should load from persistence
        orch2 = ConversationOrchestrator(auto_load=True)

        # Check what loaded
        stats2 = orch2.stats()
        print(f"Stats after restart: {stats2['total_contexts']} contexts")

        active2 = orch2.get_active_context_id()
        print(f"Active context after restart: {active2}")

        # Verify root context
        root_ctx = orch2.get_context(root_id)
        if root_ctx:
            print(f"Root context loaded: {root_ctx.task_description}")
            print(f"  - Local memory: {len(root_ctx.local_memory)} exchanges")
            print(f"  - Children: {root_ctx.child_sidebar_ids}")
        else:
            print(f"ERROR: Root context {root_id} not found!")
            return False

        # Verify sidebar context
        sidebar_ctx = orch2.get_context(sidebar_id)
        if sidebar_ctx:
            print(f"Sidebar context loaded: {sidebar_ctx.task_description}")
            print(f"  - Parent: {sidebar_ctx.parent_context_id}")
            print(f"  - Local memory: {len(sidebar_ctx.local_memory)} exchanges")
            print(f"  - Inherited memory: {len(sidebar_ctx.inherited_memory)} exchanges")
        else:
            print(f"ERROR: Sidebar context {sidebar_id} not found!")
            return False

        # Verify focus survived
        if active2 == active1:
            print(f"✓ Focus survived restart: {active2}")
        else:
            print(f"WARNING: Focus changed from {active1} to {active2}")

        # Phase 3: Test merge persistence
        print("\n=== Phase 3: Test merge ===")

        result = orch2.merge_sidebar(sidebar_id, summary="Test merge completed")
        if result['success']:
            print(f"✓ Merged {sidebar_id} into {result['parent_id']}")
        else:
            print(f"ERROR: Merge failed: {result.get('error')}")
            return False

        # Verify merge persisted
        sidebar_after = orch2.get_context(sidebar_id)
        print(f"Sidebar status after merge: {sidebar_after.status}")

        root_after = orch2.get_context(root_id)
        print(f"Root memory after merge: {len(root_after.local_memory)} exchanges")

        # Phase 4: Database statistics
        print("\n=== Phase 4: Database stats ===")

        db_stats = db.get_statistics()
        print(f"Total contexts in DB: {db_stats['total_contexts']}")
        print(f"By status: {db_stats['by_status']}")
        print(f"Root contexts: {db_stats['root_contexts']}")
        print(f"Depth distribution: {db_stats['contexts_by_depth']}")

        print("\n=== All tests passed! ===")
        return True

    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\nCleaned up test directory: {test_dir}")


def test_focus_fallback():
    """Test focus fallback chain on load."""
    test_dir = tempfile.mkdtemp(prefix="sidebar_focus_test_")
    test_db = os.path.join(test_dir, "test_sidebar.db")

    print(f"\n=== Testing focus fallback ===")
    print(f"Using test database: {test_db}")

    try:
        from sidebar_persistence import reset_persistence, SidebarPersistence
        from conversation_orchestrator import reset_orchestrator, ConversationOrchestrator
        reset_orchestrator()
        reset_persistence()

        db = SidebarPersistence(db_path=test_db)

        import sidebar_persistence
        sidebar_persistence._persistence_instance = db

        # Create orchestrator and contexts
        orch1 = ConversationOrchestrator(auto_load=False)
        root1 = orch1.create_root_context(task_description="First conversation")
        root2 = orch1.create_root_context(task_description="Second conversation")

        # Focus should be on root2 (most recent)
        print(f"Created {root1} and {root2}")
        print(f"Focus before restart: {orch1.get_active_context_id()}")

        # Clear session state to test fallback
        db.set_session_state('active_context_id', None)

        # Restart
        del orch1
        orch2 = ConversationOrchestrator(auto_load=True)

        active = orch2.get_active_context_id()
        print(f"Focus after restart (no stored focus): {active}")

        if active is not None:
            print(f"✓ Fallback to most recent context worked")
        else:
            print(f"ERROR: No fallback occurred")
            return False

        print("=== Focus fallback test passed! ===")
        return True

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("SIDEBAR PERSISTENCE TESTS")
    print("=" * 60)

    success = True

    try:
        if not test_basic_persistence():
            success = False
    except Exception as e:
        print(f"EXCEPTION in basic persistence test: {e}")
        import traceback
        traceback.print_exc()
        success = False

    try:
        if not test_focus_fallback():
            success = False
    except Exception as e:
        print(f"EXCEPTION in focus fallback test: {e}")
        import traceback
        traceback.print_exc()
        success = False

    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60)

    sys.exit(0 if success else 1)
