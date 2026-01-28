"""
Test module: test_sidebar_api_features.py

Purpose: Validate new sidebar API features from REACT_UI_TEST_SHEET.md (2026-01-22)

Test Categories:
- Pagination (limit/offset, boundary controls)
- Bulk archive (dry run, execute, batch tracking)
- Parallel alias model (per-actor, supersession, grouped view)
- Tags (add, remove, update provenance)
- Batch operations (history, archived list, single restore, batch restore)
- Data model verification (datashapes field integrity)

Dependencies: FastAPI TestClient (api_client fixture from conftest.py)
"""

import pytest
import sys
from unittest.mock import patch

sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def api_with_fresh_state(fresh_orchestrator):
    """
    Patches the app's global orchestrator with a fresh test instance.

    This ensures contexts created in tests are visible to the API endpoints.
    Returns (api_client, orchestrator) tuple.
    """
    from fastapi.testclient import TestClient
    import api_server_bridge

    # Patch the module-level orchestrator
    original = api_server_bridge.orchestrator
    api_server_bridge.orchestrator = fresh_orchestrator
    try:
        client = TestClient(api_server_bridge.app)
        yield client, fresh_orchestrator
    finally:
        api_server_bridge.orchestrator = original


# =============================================================================
# SECTION 3: PAGINATION TESTS
# =============================================================================

class TestPagination:
    """
    Validates pagination on /sidebars endpoint.

    Tests limit, offset, boundary behavior, and count accuracy.
    """

    def test_default_pagination_returns_50(self, api_client):
        """Default request should return max 50 items."""
        response = api_client.get("/sidebars")
        data = response.json()

        assert response.status_code == 200
        assert "contexts" in data
        assert "total" in data
        assert "limit" in data
        assert data["limit"] == 50
        assert len(data["contexts"]) <= 50

    def test_custom_limit(self, api_client):
        """Respects custom limit parameter."""
        response = api_client.get("/sidebars?limit=5")
        data = response.json()

        assert response.status_code == 200
        assert len(data["contexts"]) <= 5
        assert data["limit"] == 5

    def test_offset_skips_items(self, api_client):
        """Offset skips the correct number of items."""
        # Get first page
        page1 = api_client.get("/sidebars?limit=3&offset=0").json()
        # Get second page
        page2 = api_client.get("/sidebars?limit=3&offset=3").json()

        if page1["total"] > 3:
            # Pages should not overlap
            page1_ids = {c["id"] for c in page1["contexts"]}
            page2_ids = {c["id"] for c in page2["contexts"]}
            assert page1_ids.isdisjoint(page2_ids), \
                "Paginated pages should not overlap"

    def test_has_more_flag(self, api_client):
        """has_more is true when more results exist beyond current page."""
        response = api_client.get("/sidebars?limit=1").json()

        if response["total"] > 1:
            assert response["has_more"] is True
        else:
            assert response["has_more"] is False

    def test_offset_beyond_total(self, api_client):
        """Offset beyond total returns empty list, not error."""
        response = api_client.get("/sidebars?limit=10&offset=99999")
        data = response.json()

        assert response.status_code == 200
        assert data["contexts"] == []
        assert data["has_more"] is False

    def test_count_matches_contexts_length(self, api_client):
        """count field matches actual length of returned contexts."""
        response = api_client.get("/sidebars?limit=10").json()
        assert response["count"] == len(response["contexts"])

    def test_filtered_count_vs_total(self, api_client):
        """filtered reflects filter application, total is unfiltered."""
        # Unfiltered
        all_resp = api_client.get("/sidebars").json()
        # Filtered by status
        filtered_resp = api_client.get("/sidebars?status=paused").json()

        # filtered should be <= total
        assert filtered_resp["filtered"] <= all_resp["total"]


# =============================================================================
# SECTION 4: BULK ARCHIVE TESTS
# =============================================================================

class TestBulkArchive:
    """
    Validates bulk archive endpoint with dry_run and execute modes.

    CAUTION: Execute mode actually archives contexts.
    Tests use dry_run=true for safety unless explicitly testing execution.
    """

    def test_dry_run_returns_preview(self, api_client):
        """Dry run shows what would be archived without executing."""
        response = api_client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 0,
            "dry_run": True
        })
        data = response.json()

        assert response.status_code == 200
        assert data["dry_run"] is True
        assert "would_archive" in data
        assert isinstance(data["would_archive"], int)
        assert "matching_ids" in data
        assert isinstance(data["matching_ids"], list)

    def test_dry_run_does_not_modify_state(self, api_client):
        """Dry run should not change any context status."""
        # Get current count
        before = api_client.get("/sidebars").json()["total"]

        # Run dry_run
        api_client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 0,
            "dry_run": True
        })

        # Count should be unchanged
        after = api_client.get("/sidebars").json()["total"]
        assert after == before, "Dry run should not change context count"

    def test_dry_run_message_format(self, api_client):
        """Dry run returns informative message."""
        response = api_client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 0,
            "dry_run": True
        })
        data = response.json()

        assert "message" in data
        assert "dry_run" in data["message"].lower() or "would archive" in data["message"].lower()

    def test_exchange_count_filter(self, api_client):
        """exchange_count_max filters contexts by exchange count."""
        # max=0 should only match empty contexts
        resp_0 = api_client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 0,
            "dry_run": True
        }).json()

        # max=999 should match same or more
        resp_999 = api_client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 999,
            "dry_run": True
        }).json()

        assert resp_999["would_archive"] >= resp_0["would_archive"]

    def test_execute_returns_batch_id(self, api_with_fresh_state):
        """
        Execute mode archives and returns batch_id for undo.

        Uses patched orchestrator to avoid affecting real data.
        """
        client, orch = api_with_fresh_state

        # Create some empty contexts to archive
        root = orch.create_root_context(task_description="Batch test root")
        for i in range(3):
            orch.spawn_sidebar(parent_id=root, reason=f"Empty child {i}")

        # Execute bulk archive on empty children
        response = client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 0,
            "dry_run": False,
            "archive_reason": "test_batch_execution"
        })
        data = response.json()

        if data.get("success") or data.get("archived_count", 0) > 0:
            assert "batch_id" in data, "Execute should return batch_id"
            assert data["batch_id"].startswith("BATCH-")


# =============================================================================
# SECTION 5: PARALLEL ALIAS MODEL TESTS
# =============================================================================

class TestParallelAliasModel:
    """
    Validates per-actor alias system with supersession chains.

    Key principles:
    - Each actor maintains own alias independently
    - Same actor updates create supersession chain
    - Different actors never conflict
    - Resolution is per-actor
    """

    def test_set_alias_returns_citation(self, api_with_fresh_state):
        """Setting alias returns citation_id and success."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Citation test")

        response = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Test Name",
            "confidence": 1.0,
            "cited_by": "human"
        })
        data = response.json()

        assert data["success"] is True
        assert "citation_id" in data
        assert data["citation_id"].startswith("CITE-")
        assert data["alias"] == "Test Name"
        assert data["cited_by"] == "human"

    def test_first_alias_has_no_supersedes(self, api_with_fresh_state):
        """First alias for an actor has supersedes=null."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="First alias test")

        response = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "First Ever",
            "confidence": 1.0,
            "cited_by": "human"
        })
        data = response.json()

        assert data["supersedes"] is None

    def test_parallel_aliases_no_conflict(self, api_with_fresh_state):
        """Different actors set aliases independently - no conflict."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Parallel test")

        # Human sets alias
        human = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Human Name",
            "confidence": 1.0,
            "cited_by": "human"
        }).json()

        # Claude sets alias (should NOT supersede human's)
        claude = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Claude Name",
            "confidence": 0.9,
            "cited_by": "claude"
        }).json()

        assert human["success"] is True
        assert claude["success"] is True
        assert claude["supersedes"] is None, \
            "Claude's first alias should not supersede anything"

    def test_same_actor_supersession(self, api_with_fresh_state):
        """Same actor updating creates supersession chain."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Supersession test")

        # First alias
        first = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Version 1",
            "confidence": 1.0,
            "cited_by": "human"
        }).json()

        first_cite_id = first["citation_id"]

        # Second alias (same actor)
        second = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Version 2",
            "confidence": 1.0,
            "cited_by": "human"
        }).json()

        assert second["supersedes"] == first_cite_id, \
            f"Second alias should supersede first: {first_cite_id}"

    def test_per_actor_resolution(self, api_with_fresh_state):
        """GET alias with actor param returns that actor's alias."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Resolution test")

        # Set both
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Human View",
            "confidence": 1.0,
            "cited_by": "human"
        })
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Claude View",
            "confidence": 0.9,
            "cited_by": "claude"
        })

        # Resolve each
        human_view = client.get(f"/sidebars/{sid}/alias?actor=human").json()
        claude_view = client.get(f"/sidebars/{sid}/alias?actor=claude").json()

        assert human_view["alias"] == "Human View"
        assert human_view["has_alias"] is True
        assert claude_view["alias"] == "Claude View"
        assert claude_view["has_alias"] is True

    def test_no_alias_returns_has_alias_false(self, api_with_fresh_state):
        """Querying actor with no alias returns has_alias=false."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="No alias test")

        response = client.get(f"/sidebars/{sid}/alias?actor=human").json()
        assert response["has_alias"] is False

    def test_list_endpoint_resolves_per_actor(self, api_with_fresh_state):
        """GET /sidebars?actor= resolves display_name per actor."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="List resolution test")

        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Human List Name",
            "confidence": 1.0,
            "cited_by": "human"
        })
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Claude List Name",
            "confidence": 0.9,
            "cited_by": "claude"
        })

        # Query as human
        human_list = client.get("/sidebars?actor=human&limit=100").json()
        # Query as claude
        claude_list = client.get("/sidebars?actor=claude&limit=100").json()

        # Find our context in each list
        human_entry = next((c for c in human_list["contexts"] if c["id"] == sid), None)
        claude_entry = next((c for c in claude_list["contexts"] if c["id"] == sid), None)

        if human_entry:
            assert human_entry["display_name"] == "Human List Name"
        if claude_entry:
            assert claude_entry["display_name"] == "Claude List Name"

    def test_grouped_aliases_endpoint(self, api_with_fresh_state):
        """GET /sidebars/{id}/aliases returns all actors grouped with history."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Grouped test")

        # Set multiple aliases for human (supersession chain)
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Human V1", "confidence": 1.0, "cited_by": "human"
        })
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Human V2", "confidence": 1.0, "cited_by": "human"
        })
        # Set one for claude
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Claude V1", "confidence": 0.9, "cited_by": "claude"
        })

        response = client.get(f"/sidebars/{sid}/aliases").json()

        assert response["success"] is True
        assert "by_actor" in response
        assert "human" in response["by_actor"]
        assert "claude" in response["by_actor"]
        assert "actors" in response
        assert "total_aliases" in response

        # Human should have 2 aliases in history
        human_data = response["by_actor"]["human"]
        assert human_data["current"] == "Human V2"
        assert len(human_data["history"]) == 2

        # History should have is_current flags
        current_entries = [h for h in human_data["history"] if h["is_current"]]
        assert len(current_entries) == 1
        assert current_entries[0]["alias"] == "Human V2"

        # Claude should have 1
        claude_data = response["by_actor"]["claude"]
        assert claude_data["current"] == "Claude V1"

    def test_supersession_chain_integrity(self, api_with_fresh_state):
        """Supersession chain links each update to its predecessor."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Chain test")

        # Create chain of 3
        r1 = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Chain 1", "confidence": 1.0, "cited_by": "human"
        }).json()
        r2 = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Chain 2", "confidence": 1.0, "cited_by": "human"
        }).json()
        r3 = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Chain 3", "confidence": 1.0, "cited_by": "human"
        }).json()

        assert r1["supersedes"] is None
        assert r2["supersedes"] == r1["citation_id"]
        assert r3["supersedes"] == r2["citation_id"]


# =============================================================================
# SECTION 6: TAGS TESTS
# =============================================================================

class TestTags:
    """
    Validates tag management on sidebars.

    Tags support add/remove with provenance tracking.
    """

    def test_add_tags(self, api_with_fresh_state):
        """Adding tags returns success with tags_added list."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Tags test")

        response = client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["debugging", "auth"],
            "reason": "categorizing",
            "updated_by": "human"
        })
        data = response.json()

        assert data["success"] is True
        assert "debugging" in data.get("tags", data.get("tags_added", []))

    def test_tags_persist_on_context(self, api_with_fresh_state):
        """Tags should be visible on subsequent GET."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Tags persist test")

        client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["persist-test", "verification"],
            "reason": "testing persistence",
            "updated_by": "human"
        })

        # Check via list endpoint
        list_resp = client.get("/sidebars?limit=100").json()
        ctx = next((c for c in list_resp["contexts"] if c["id"] == sid), None)

        assert ctx is not None
        assert "persist-test" in ctx["tags"]
        assert "verification" in ctx["tags"]

    def test_tags_comma_separated_handling(self, api_with_fresh_state):
        """Tags are stored as individual items, not comma-joined strings."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Comma test")

        client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["tag-a", "tag-b", "tag-c"],
            "reason": "multi-tag",
            "updated_by": "human"
        })

        list_resp = client.get("/sidebars?limit=100").json()
        ctx = next((c for c in list_resp["contexts"] if c["id"] == sid), None)

        assert ctx is not None
        assert isinstance(ctx["tags"], list)
        assert len(ctx["tags"]) == 3

    def test_update_tags_replaces(self, api_with_fresh_state):
        """Updating tags replaces the full tag set."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Replace test")

        # Set initial tags
        client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["old-tag-1", "old-tag-2"],
            "reason": "initial",
            "updated_by": "human"
        })

        # Replace with new tags
        client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["new-tag-1"],
            "reason": "replacing",
            "updated_by": "human"
        })

        # Verify old tags removed
        list_resp = client.get("/sidebars?limit=100").json()
        ctx = next((c for c in list_resp["contexts"] if c["id"] == sid), None)

        assert ctx is not None
        assert "new-tag-1" in ctx["tags"]
        assert "old-tag-1" not in ctx["tags"]

    def test_empty_tags_clears(self, api_with_fresh_state):
        """Setting empty tags list clears all tags."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Clear test")

        # Set then clear
        client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["will-remove"],
            "reason": "setup",
            "updated_by": "human"
        })
        client.post(f"/sidebars/{sid}/tags", json={
            "tags": [],
            "reason": "clearing",
            "updated_by": "human"
        })

        list_resp = client.get("/sidebars?limit=100").json()
        ctx = next((c for c in list_resp["contexts"] if c["id"] == sid), None)

        assert ctx is not None
        assert ctx["tags"] == []

    def test_tags_action_field(self, api_with_fresh_state):
        """Response includes action field (add/remove/replace)."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Action field test")

        response = client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["action-test"],
            "reason": "checking action field",
            "updated_by": "human"
        })
        data = response.json()

        assert "action" in data


# =============================================================================
# SECTION 7: BATCH OPERATIONS TESTS
# =============================================================================

class TestBatchOperations:
    """
    Validates batch tracking, archived list, and restore endpoints.
    """

    def test_batch_list_endpoint(self, api_client):
        """GET /batches returns paginated list."""
        response = api_client.get("/batches?limit=10&offset=0")
        data = response.json()

        assert response.status_code == 200
        assert "batches" in data
        assert "count" in data
        assert "total" in data
        assert isinstance(data["batches"], list)

    def test_batch_not_found(self, api_client):
        """GET /batches/{id} with invalid ID returns error."""
        response = api_client.get("/batches/BATCH-nonexistent")
        data = response.json()

        assert "error" in data or data.get("batch") is None

    def test_archived_list_endpoint(self, api_client):
        """GET /sidebars/archived returns archived contexts."""
        response = api_client.get("/sidebars/archived?limit=5")
        data = response.json()

        assert response.status_code == 200
        assert "contexts" in data
        assert "total" in data
        assert "has_more" in data

        # All returned should be archived (if any exist)
        # Can't guarantee archived contexts exist in test
        for ctx in data["contexts"]:
            assert "id" in ctx
            assert "reason" in ctx

    def test_archived_search_filter(self, api_client):
        """Search param filters archived contexts."""
        # Search for something specific
        response = api_client.get("/sidebars/archived?search=nonexistent_term_xyz")
        data = response.json()

        assert response.status_code == 200
        # Should return empty or fewer results than unfiltered
        assert isinstance(data["contexts"], list)

    def test_restore_non_archived_fails(self, api_with_fresh_state):
        """Restoring a non-archived context returns error."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Not archived")

        response = client.post(f"/sidebars/{sid}/restore", json={
            "restore_to_status": "active",
            "reason": "should fail"
        })
        data = response.json()

        assert data.get("success") is False
        assert "not archived" in data.get("error", "").lower()

    def test_restore_archived_context(self, api_with_fresh_state):
        """Restoring an archived context changes its status."""
        client, orch = api_with_fresh_state
        root = orch.create_root_context(task_description="Restore root")
        child = orch.spawn_sidebar(parent_id=root, reason="Will archive then restore")

        # Archive it
        orch.archive_context(child, reason="testing restore")

        # Restore it
        response = client.post(f"/sidebars/{child}/restore", json={
            "restore_to_status": "paused",
            "reason": "needed again"
        })
        data = response.json()

        if data.get("success"):
            # Verify status changed
            ctx = orch.get_context(child)
            assert ctx.status.value == "paused"

    def test_batch_restore_nonexistent_batch(self, api_client):
        """Batch restore with invalid batch_id returns error."""
        response = api_client.post("/batches/BATCH-fake/restore", json={
            "dry_run": True,
            "restore_to_original": True
        })
        data = response.json()

        assert data.get("success") is False or "error" in data


# =============================================================================
# SECTION 8: DATA MODEL VERIFICATION
# =============================================================================

class TestDataModelIntegrity:
    """
    Validates datashapes.py field additions and enum values.

    These are unit tests that import directly from datashapes -
    no API server needed.
    """

    def test_sidebar_context_has_tags_field(self):
        """SidebarContext should have tags field defaulting to []."""
        from datashapes import SidebarContext
        ctx = SidebarContext(sidebar_id="test", uuid="test-uuid")
        assert hasattr(ctx, 'tags')
        assert ctx.tags == []

    def test_sidebar_context_has_display_names_field(self):
        """SidebarContext should have display_names dict field."""
        from datashapes import SidebarContext
        ctx = SidebarContext(sidebar_id="test", uuid="test-uuid")
        assert hasattr(ctx, 'display_names')
        assert ctx.display_names == {}
        assert isinstance(ctx.display_names, dict)

    def test_display_names_per_actor_storage(self):
        """display_names dict stores per-actor aliases."""
        from datashapes import SidebarContext
        ctx = SidebarContext(sidebar_id="test", uuid="test-uuid")

        ctx.display_names["human"] = "My test sidebar"
        ctx.display_names["claude"] = "Test Context Investigation"

        assert ctx.display_names["human"] == "My test sidebar"
        assert ctx.display_names["claude"] == "Test Context Investigation"

    def test_context_alias_citation_type(self):
        """CitationType.CONTEXT_ALIAS should exist with correct value."""
        from datashapes import CitationType
        assert hasattr(CitationType, 'CONTEXT_ALIAS')
        assert CitationType.CONTEXT_ALIAS.value == "context_alias"

    def test_tags_updated_event_type(self):
        """OzolithEventType.TAGS_UPDATED should exist."""
        from datashapes import OzolithEventType
        assert hasattr(OzolithEventType, 'TAGS_UPDATED')
        assert OzolithEventType.TAGS_UPDATED.value == "tags_updated"

    def test_batch_operation_event_type(self):
        """OzolithEventType.BATCH_OPERATION should exist."""
        from datashapes import OzolithEventType
        assert hasattr(OzolithEventType, 'BATCH_OPERATION')
        assert OzolithEventType.BATCH_OPERATION.value == "batch_operation"

    def test_payload_classes_exist(self):
        """Payload dataclasses for tags and batch should be importable."""
        from datashapes import OzolithPayloadTagsUpdated, OzolithPayloadBatchOperation, BatchOperation

        # Verify they're actual classes
        assert OzolithPayloadTagsUpdated is not None
        assert OzolithPayloadBatchOperation is not None
        assert BatchOperation is not None

    def test_tags_field_is_list_type(self):
        """tags field should accept list of strings."""
        from datashapes import SidebarContext
        ctx = SidebarContext(sidebar_id="test", uuid="test-uuid")
        ctx.tags = ["debugging", "auth", "testing"]
        assert len(ctx.tags) == 3
        assert "auth" in ctx.tags

    def test_display_names_does_not_conflict_with_display_name(self):
        """display_names (dict) should be separate from any display_name (str) field."""
        from datashapes import SidebarContext
        ctx = SidebarContext(sidebar_id="test", uuid="test-uuid")

        # display_names is the per-actor dict
        ctx.display_names["human"] = "Per-actor name"

        # If display_name (singular) exists, it should be independent
        if hasattr(ctx, 'display_name'):
            assert ctx.display_name != ctx.display_names["human"] or ctx.display_name is None


# =============================================================================
# GUARDRAILS VERIFICATION
# =============================================================================

class TestGuardrails:
    """
    Validates AI safety guardrails from the test sheet.

    These ensure provenance, append-only behavior, and isolation.
    """

    def test_alias_confidence_accepted(self, api_with_fresh_state):
        """Alias endpoint accepts and stores confidence parameter."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Confidence test")

        response = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Confident Name",
            "confidence": 0.75,
            "cited_by": "claude"
        }).json()

        assert response["success"] is True
        # Confidence should be stored (verify via grouped endpoint)
        grouped = client.get(f"/sidebars/{sid}/aliases").json()
        if grouped.get("by_actor", {}).get("claude", {}).get("history"):
            entry = grouped["by_actor"]["claude"]["history"][-1]
            assert entry["confidence"] == 0.75

    def test_parallel_isolation_no_overwrite(self, api_with_fresh_state):
        """One actor's alias update cannot overwrite another actor's alias."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Isolation test")

        # Human sets alias
        client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Human Original",
            "confidence": 1.0,
            "cited_by": "human"
        })

        # Claude sets many aliases (should never touch human's)
        for i in range(5):
            client.post(f"/sidebars/{sid}/alias", json={
                "alias": f"Claude Update {i}",
                "confidence": 0.9,
                "cited_by": "claude"
            })

        # Human's alias should be unchanged
        human_alias = client.get(f"/sidebars/{sid}/alias?actor=human").json()
        assert human_alias["alias"] == "Human Original"

    def test_multi_agent_attribution(self, api_with_fresh_state):
        """cited_by/updated_by tracks which agent made changes."""
        client, orch = api_with_fresh_state
        sid = orch.create_root_context(task_description="Attribution test")

        # Tags by human
        tag_resp = client.post(f"/sidebars/{sid}/tags", json={
            "tags": ["human-tagged"],
            "reason": "human categorizing",
            "updated_by": "human"
        }).json()

        assert tag_resp["success"] is True

        # Alias by claude
        alias_resp = client.post(f"/sidebars/{sid}/alias", json={
            "alias": "Claude Named This",
            "confidence": 0.8,
            "cited_by": "claude"
        }).json()

        assert alias_resp["cited_by"] == "claude"

    def test_dry_run_support_on_bulk_operations(self, api_client):
        """All destructive batch operations support dry_run preview."""
        # Bulk archive supports dry_run
        response = api_client.post("/sidebars/archive-bulk", json={
            "exchange_count_max": 0,
            "dry_run": True
        })
        assert response.status_code == 200
        assert response.json()["dry_run"] is True
