# Phase 5 Orchestrator Test Requirements

## Overview

Comprehensive test requirements for Phase 5 orchestrator methods in `/home/grinnling/Development/CODE_IMPLEMENTATION/conversation_orchestrator.py`.

**Target File:** `tests/test_phase5_orchestrator.py`

**Key Constants to Note:**
- `CLUSTERING_THRESHOLD = 3` - triggers cluster_flagged when this many sources suggest same ref
- `VALIDATION_CONFIDENCE_THRESHOLD = 0.7` - below this bumps urgency score
- `STALENESS_DAYS = 3` - pending refs older than this get priority bump
- `CURATOR_AGENT_ID = "AGENT-curator"` - all entries route through curator first

---

## Section 1: YARN BOARD OPERATIONS

### 1.1 get_yarn_layout

#### Test: test_get_yarn_layout_existing_layout
- **Type:** Happy path
- **Setup:** Create context with populated `yarn_board_layout` containing point_positions, zoom_level, focus_point, filters
- **Expected:** Returns `success=True`, layout dict matches stored layout
- **Assertions:**
  - `result["success"] == True`
  - `result["context_id"] == context_id`
  - `result["layout"]["point_positions"] == expected_positions`
  - `result["layout"]["zoom_level"] == expected_zoom`

#### Test: test_get_yarn_layout_default_layout
- **Type:** Happy path (empty state)
- **Setup:** Create context with empty/None `yarn_board_layout`
- **Expected:** Returns default layout structure
- **Assertions:**
  - `result["success"] == True`
  - `result["layout"]["point_positions"] == {}`
  - `result["layout"]["zoom_level"] == 1.0`
  - `result["layout"]["focus_point"] is None`
  - `result["layout"]["show_archived"] == False`

#### Test: test_get_yarn_layout_invalid_context
- **Type:** Error case
- **Setup:** No context created
- **Expected:** Returns error
- **Assertions:**
  - `result["success"] == False`
  - `"not found" in result["error"]`

---

### 1.2 save_yarn_layout

#### Test: test_save_yarn_layout_full_update
- **Type:** Happy path
- **Setup:** Create context
- **Action:** Call with all parameters provided
- **Expected:** Layout saved with all fields, `last_modified` updated
- **Assertions:**
  - `result["success"] == True`
  - All provided fields in `result["layout"]`
  - `"last_modified" in result["layout"]`

#### Test: test_save_yarn_layout_partial_update
- **Type:** Happy path
- **Setup:** Create context with existing layout
- **Action:** Call with only `zoom_level=2.0`
- **Expected:** Only zoom_level changes, other fields preserved
- **Assertions:**
  - Existing `point_positions` preserved
  - `result["layout"]["zoom_level"] == 2.0`

#### Test: test_save_yarn_layout_initializes_empty
- **Type:** Edge case
- **Setup:** Create context with `yarn_board_layout = None`
- **Action:** Save partial layout
- **Expected:** Initializes full layout structure before updating
- **Assertions:**
  - All default fields present in result
  - Provided field updated

#### Test: test_save_yarn_layout_persistence
- **Type:** Integration
- **Setup:** Create context, save layout
- **Expected:** `_persist_context` called
- **Assertions:**
  - Mock persistence shows context was saved
  - Retrieved layout matches saved

---

### 1.3 update_point_position

#### Test: test_update_point_position_new_point
- **Type:** Happy path
- **Setup:** Create context with empty layout
- **Action:** `update_point_position(ctx_id, "context:SB-1", 100.0, 200.0, collapsed=False)`
- **Expected:** Point added to positions
- **Assertions:**
  - `result["success"] == True`
  - `result["position"]["x"] == 100.0`
  - `result["position"]["y"] == 200.0`
  - `result["position"]["collapsed"] == False`

#### Test: test_update_point_position_update_existing
- **Type:** Happy path
- **Setup:** Create context with existing point at (0, 0)
- **Action:** Update to (50, 75)
- **Expected:** Position updated, not duplicated
- **Assertions:**
  - Point positions dict has single entry
  - New coordinates in place

#### Test: test_update_point_position_collapsed_state
- **Type:** Edge case
- **Setup:** Create context
- **Action:** Set `collapsed=True`
- **Expected:** Collapsed state saved
- **Assertions:**
  - `context.yarn_board_layout["point_positions"][point_id]["collapsed"] == True`

#### Test: test_update_point_position_invalid_context
- **Type:** Error case
- **Setup:** No context
- **Expected:** Returns error dict
- **Assertions:**
  - `result["success"] == False`

---

### 1.4 get_yarn_state

#### Test: test_get_yarn_state_redis_available
- **Type:** Happy path (mock Redis)
- **Setup:** Mock `redis_interface.get_yarn_state` to return `YarnBoardState`
- **Expected:** Returns cached state with `source="redis"`
- **Assertions:**
  - `result["source"] == "redis"`
  - `result["state"]["grabbed_point_ids"]` matches mock

#### Test: test_get_yarn_state_fallback_default
- **Type:** Happy path (degraded)
- **Setup:** Redis stub returns None
- **Expected:** Returns default empty state
- **Assertions:**
  - `result["success"] == True`
  - `result["source"] == "default"`
  - `result["state"]["grabbed_point_ids"] == []`
  - `result["state"]["priority_overrides"] == {}`

---

### 1.5 set_grabbed

#### Test: test_set_grabbed_redis_available
- **Type:** Happy path (mock Redis)
- **Setup:** Mock `redis_interface.set_grabbed` to return True
- **Expected:** Persisted to Redis
- **Assertions:**
  - `result["persisted"] == True`
  - `result["grabbed"] == True`

#### Test: test_set_grabbed_graceful_degradation
- **Type:** Edge case
- **Setup:** Redis stub returns False
- **Expected:** Still returns success (graceful degradation)
- **Assertions:**
  - `result["success"] == True` (always succeeds)
  - `result["persisted"] == False`

#### Test: test_set_grabbed_release
- **Type:** Happy path
- **Setup:** Mock Redis
- **Action:** `set_grabbed(ctx_id, point_id, grabbed=False)`
- **Expected:** Release recorded
- **Assertions:**
  - `result["grabbed"] == False`

---

### 1.6 render_yarn_board

#### Test: test_render_yarn_board_basic_structure
- **Type:** Happy path
- **Setup:** Create context with no children or cross-refs
- **Expected:** Self rendered as point, structure complete
- **Assertions:**
  - `result["success"] == True`
  - At least 1 point (the context itself)
  - `result["type_colors"]` contains expected color keys

#### Test: test_render_yarn_board_with_children
- **Type:** Happy path
- **Setup:** Create parent context, spawn 2 child sidebars
- **Expected:** Parent and children as points, parent->child connections
- **Assertions:**
  - 3 points total (or in cushion)
  - 2 connections with `ref_type="parent_child"`

#### Test: test_render_yarn_board_with_cross_refs
- **Type:** Happy path
- **Setup:** Create 2 contexts, add cross-ref between them
- **Expected:** Both contexts + crossref midpoint rendered
- **Assertions:**
  - Point with ID starting with `crossref:` exists
  - Connections from context -> crossref -> target

#### Test: test_render_yarn_board_positioned_vs_cushion
- **Type:** Edge case
- **Setup:** Create context, set position for some points, not others
- **Expected:** Positioned points in `points[]`, others in `cushion[]`
- **Assertions:**
  - Points with x/y in `result["points"]`
  - Points without position in `result["cushion"]`

#### Test: test_render_yarn_board_highlights
- **Type:** Happy path
- **Setup:** Create context
- **Action:** Call with `highlights=["context:SB-1", "crossref:SB-1:SB-2"]`
- **Expected:** Highlights returned unchanged
- **Assertions:**
  - `result["highlights"] == provided_highlights`

#### Test: test_render_yarn_board_bidirectional_dedup
- **Type:** Edge case
- **Setup:** Create bidirectional cross-ref (A->B and B->A)
- **Expected:** Single crossref point (not duplicated)
- **Assertions:**
  - Only one point with `crossref:` prefix for the pair

---

## Section 2: QUEUE ROUTING

### 2.1 route_scratchpad_entry

#### Test: test_route_quick_note_no_routing
- **Type:** Happy path
- **Setup:** Entry with `entry_type="quick_note"`, no `routed_to`
- **Expected:** Returns without routing
- **Assertions:**
  - `result["routed"] == False`
  - `result["reason"] == "quick_note_no_route"`

#### Test: test_route_quick_note_with_explicit_route
- **Type:** Happy path
- **Setup:** Entry with `entry_type="quick_note"`, `routed_to="AGENT-debugger"`
- **Expected:** Routes through curator
- **Assertions:**
  - `result["routed"] == True`
  - `result["destination"] == "AGENT-curator"`

#### Test: test_route_finding_through_curator
- **Type:** Happy path
- **Setup:** Entry with `entry_type="finding"`
- **Expected:** Queued for curator validation
- **Assertions:**
  - `result["routed"] == True`
  - `result["destination"] == "AGENT-curator"`
  - `result["awaiting"] == "curator_validation"`

#### Test: test_route_question_through_curator
- **Type:** Happy path
- **Setup:** Entry with `entry_type="question"`
- **Expected:** Routes through curator
- **Assertions:**
  - `result["routed"] == True`

#### Test: test_route_with_redis_available
- **Type:** Integration (mock Redis)
- **Setup:** Mock `redis_interface.queue_for_agent` returns True
- **Expected:** `queued_to_redis=True`
- **Assertions:**
  - `result["queued_to_redis"] == True`

#### Test: test_route_graceful_degradation
- **Type:** Edge case
- **Setup:** Redis stub returns False
- **Expected:** Still succeeds, logs intent
- **Assertions:**
  - `result["success"] == True`
  - `result["queued_to_redis"] == False`

---

### 2.2 curator_approve_entry

#### Test: test_curator_approve_routes_to_destination
- **Type:** Happy path
- **Setup:** Create context
- **Action:** `curator_approve_entry(entry_id, ctx_id, approved=True)`
- **Expected:** Entry routed to inferred destination
- **Assertions:**
  - `result["success"] == True`
  - `result["approved"] == True`
  - `result["destination"]` is valid agent ID

#### Test: test_curator_reject_entry
- **Type:** Happy path
- **Setup:** Create context
- **Action:** `curator_approve_entry(entry_id, ctx_id, approved=False, rejection_reason="Duplicate")`
- **Expected:** Entry rejected, not routed
- **Assertions:**
  - `result["approved"] == False`
  - `result["rejection_reason"] == "Duplicate"`
  - No `"destination"` key or destination is None

#### Test: test_curator_approve_with_redis
- **Type:** Integration (mock Redis)
- **Setup:** Mock Redis queue
- **Expected:** Delivery message queued
- **Assertions:**
  - `result["queued_to_redis"] == True`

---

### 2.3 _infer_destination

#### Test: test_infer_destination_debugging_keywords
- **Type:** Happy path
- **Setup:** Default agents registered
- **Action:** `_infer_destination(entry_id, ctx_id, content_hint="There's a bug in the auth")`
- **Expected:** Returns debugger agent
- **Assertions:**
  - Result == "AGENT-debugger"

#### Test: test_infer_destination_research_keywords
- **Type:** Happy path
- **Setup:** Default agents
- **Action:** Content hint with "research", "investigate", "find"
- **Expected:** Returns researcher agent
- **Assertions:**
  - Result == "AGENT-researcher"

#### Test: test_infer_destination_security_keywords
- **Type:** Happy path
- **Setup:** Default agents
- **Action:** Content hint with "security", "auth", "permission"
- **Expected:** Returns architect agent (has security specialty)
- **Assertions:**
  - Result == "AGENT-architect"

#### Test: test_infer_destination_no_match_defaults_operator
- **Type:** Edge case
- **Setup:** Default agents
- **Action:** Content hint with unmatched terms
- **Expected:** Defaults to human operator
- **Assertions:**
  - Result == "AGENT-operator"

#### Test: test_infer_destination_empty_content
- **Type:** Edge case
- **Setup:** Default agents
- **Action:** `content_hint=None` or `content_hint=""`
- **Expected:** Defaults to operator
- **Assertions:**
  - Result == "AGENT-operator"

---

### 2.4 get_agent_queue

#### Test: test_get_agent_queue_with_messages
- **Type:** Happy path (mock Redis)
- **Setup:** Mock `redis_interface.get_agent_queue` returns list of dicts
- **Expected:** Messages returned
- **Assertions:**
  - `result["queue"]` matches mocked messages
  - `result["count"] == len(mocked_messages)`
  - `result["source"] == "redis"`

#### Test: test_get_agent_queue_empty
- **Type:** Edge case
- **Setup:** Redis stub returns empty list
- **Expected:** Empty queue returned
- **Assertions:**
  - `result["queue"] == []`
  - `result["count"] == 0`
  - `result["source"] == "stub"`

---

### 2.5 register_agent

#### Test: test_register_new_agent
- **Type:** Happy path
- **Setup:** Orchestrator initialized
- **Action:** `register_agent("AGENT-new", ["specialty1", "specialty2"], max_concurrent=10)`
- **Expected:** Agent added to registry
- **Assertions:**
  - `result["registered"] == True`
  - Agent appears in `list_agents()`

#### Test: test_register_update_existing_agent
- **Type:** Happy path
- **Setup:** Register agent, then register again with different specialties
- **Expected:** Specialties updated, not duplicated
- **Assertions:**
  - `result["registered"] == True`
  - Agent's specialties match new list
  - Only one entry for agent ID

---

### 2.6 list_agents

#### Test: test_list_agents_includes_defaults
- **Type:** Happy path
- **Setup:** Fresh orchestrator (uses `_init_default_agents`)
- **Expected:** Default agents present
- **Assertions:**
  - "AGENT-curator" in agent IDs
  - "AGENT-operator" in agent IDs
  - "AGENT-researcher" in agent IDs
  - "AGENT-debugger" in agent IDs
  - "AGENT-architect" in agent IDs

#### Test: test_list_agents_structure
- **Type:** Happy path
- **Setup:** Fresh orchestrator
- **Expected:** Each agent has required fields
- **Assertions:**
  - Each agent dict has: `agent_id`, `specialties`, `availability`, `current_load`, `max_concurrent`

---

## Section 3: CLUSTERING

### 3.1 CLUSTERING_THRESHOLD Constant

#### Test: test_clustering_threshold_value
- **Type:** Constant validation
- **Setup:** Import orchestrator
- **Expected:** Threshold is 3
- **Assertions:**
  - `ConversationOrchestrator.CLUSTERING_THRESHOLD == 3`

---

### 3.2 add_cross_ref with suggested_by (Clustering Logic)

#### Test: test_add_cross_ref_first_source
- **Type:** Happy path
- **Setup:** Create source and target contexts
- **Action:** Add cross-ref with `suggested_by="AGENT-researcher"`
- **Expected:** Ref created with single source
- **Assertions:**
  - `result["success"] == True`
  - `result["suggested_sources"] == ["AGENT-researcher"]`
  - `result["cluster_flagged"] == False`

#### Test: test_add_cross_ref_second_source
- **Type:** Happy path
- **Setup:** Existing cross-ref with 1 source
- **Action:** Add same ref with different `suggested_by`
- **Expected:** Source added, still not flagged
- **Assertions:**
  - `result["already_existed"] == True`
  - `len(result["suggested_sources"]) == 2`
  - `result["cluster_flagged"] == False`

#### Test: test_add_cross_ref_third_source_triggers_clustering
- **Type:** Critical - cluster trigger
- **Setup:** Existing cross-ref with 2 sources
- **Action:** Add same ref with 3rd unique `suggested_by`
- **Expected:** **cluster_flagged=True, validation_priority="urgent"**
- **Assertions:**
  - `result["cluster_flagged"] == True`
  - `result["newly_flagged"] == True`
  - Verify stored metadata: `metadata["validation_priority"] == "urgent"`

#### Test: test_add_cross_ref_same_source_no_duplicate
- **Type:** Edge case
- **Setup:** Existing cross-ref with 1 source
- **Action:** Add same ref with same `suggested_by`
- **Expected:** Source list unchanged
- **Assertions:**
  - `len(result["suggested_sources"]) == 1`

#### Test: test_add_cross_ref_default_suggested_by
- **Type:** Edge case
- **Setup:** Create contexts
- **Action:** Add cross-ref without explicit `suggested_by`
- **Expected:** Defaults to source_context_id
- **Assertions:**
  - `result["suggested_sources"][0] == source_context_id`

#### Test: test_add_cross_ref_fourth_source_stays_flagged
- **Type:** Edge case
- **Setup:** Already cluster-flagged ref
- **Action:** Add 4th source
- **Expected:** Still flagged, not newly flagged
- **Assertions:**
  - `result["cluster_flagged"] == True`
  - `result["newly_flagged"] == False`

---

### 3.3 get_cluster_flagged_refs

#### Test: test_get_cluster_flagged_refs_returns_flagged
- **Type:** Happy path
- **Setup:** Create cross-ref with 3+ sources (cluster_flagged=True)
- **Expected:** Ref appears in result
- **Assertions:**
  - `result["count"] >= 1`
  - First ref has `"source_count" >= 3`

#### Test: test_get_cluster_flagged_refs_excludes_validated
- **Type:** Happy path
- **Setup:** Create cluster-flagged ref, validate it
- **Action:** `get_cluster_flagged_refs(include_validated=False)`
- **Expected:** Validated ref excluded
- **Assertions:**
  - Validated ref not in result

#### Test: test_get_cluster_flagged_refs_includes_validated_when_requested
- **Type:** Happy path
- **Setup:** Create cluster-flagged ref, validate it
- **Action:** `get_cluster_flagged_refs(include_validated=True)`
- **Expected:** Validated ref included
- **Assertions:**
  - Validated ref appears in result
  - `human_validated` field present

#### Test: test_get_cluster_flagged_refs_specific_context
- **Type:** Happy path
- **Setup:** Create cluster-flagged refs in different contexts
- **Action:** Query specific context
- **Expected:** Only refs from that context
- **Assertions:**
  - All returned refs have matching source_context_id

#### Test: test_get_cluster_flagged_refs_sorted_by_count
- **Type:** Edge case
- **Setup:** Create refs with 3, 5, 4 sources respectively
- **Expected:** Sorted descending by source_count
- **Assertions:**
  - `result["cluster_flagged_refs"][0]["source_count"] == 5`
  - `result["cluster_flagged_refs"][1]["source_count"] == 4`

---

## Section 4: VALIDATION PROMPTS

### 4.1 get_validation_prompts

#### Test: test_validation_prompts_actively_citing_inline
- **Type:** Critical - inline routing
- **Setup:** Create unvalidated cross-ref SB-1 -> SB-2
- **Action:** `get_validation_prompts(ctx_id, citing_refs=["SB-1:SB-2"])`
- **Expected:** Ref in `inline_prompts`, not `scratchpad_prompts`
- **Assertions:**
  - `result["inline_count"] >= 1`
  - Ref in `result["inline_prompts"]`
  - "actively_citing" in first prompt's `urgency_reasons`

#### Test: test_validation_prompts_not_citing_scratchpad
- **Type:** Critical - scratchpad routing
- **Setup:** Create unvalidated cross-ref with low confidence
- **Action:** `get_validation_prompts(ctx_id, citing_refs=[])`
- **Expected:** Ref in `scratchpad_prompts`
- **Assertions:**
  - `result["scratchpad_count"] >= 1`
  - Ref in `result["scratchpad_prompts"]`

#### Test: test_validation_prompts_urgency_score_citing
- **Type:** Urgency scoring
- **Setup:** Create unvalidated cross-ref
- **Action:** Call with ref in `citing_refs`
- **Expected:** High urgency score (+100)
- **Assertions:**
  - Prompt's `urgency_score >= 100`

#### Test: test_validation_prompts_urgency_score_cluster_flagged
- **Type:** Urgency scoring
- **Setup:** Create cluster-flagged cross-ref (3+ sources)
- **Action:** `get_validation_prompts(ctx_id)`
- **Expected:** Urgency score includes +30
- **Assertions:**
  - "cluster_flagged" substring in `urgency_reasons`

#### Test: test_validation_prompts_urgency_score_low_confidence
- **Type:** Urgency scoring
- **Setup:** Create cross-ref with `confidence=0.5` (below 0.7 threshold)
- **Action:** `get_validation_prompts(ctx_id)`
- **Expected:** Urgency score includes +20
- **Assertions:**
  - "low_confidence" substring in `urgency_reasons`

#### Test: test_validation_prompts_urgency_score_stale
- **Type:** Urgency scoring
- **Setup:** Create cross-ref with `created_at` 5 days ago
- **Action:** `get_validation_prompts(ctx_id)`
- **Expected:** Urgency score includes +15
- **Assertions:**
  - "stale_" substring in `urgency_reasons`

#### Test: test_validation_prompts_urgency_score_urgent_priority
- **Type:** Urgency scoring
- **Setup:** Create cross-ref with `validation_priority="urgent"`
- **Action:** `get_validation_prompts(ctx_id)`
- **Expected:** Urgency score includes +25
- **Assertions:**
  - "urgent_priority" in `urgency_reasons`

#### Test: test_validation_prompts_skips_validated
- **Type:** Edge case
- **Setup:** Create cross-ref, validate it
- **Action:** `get_validation_prompts(ctx_id)`
- **Expected:** Validated ref not in prompts
- **Assertions:**
  - `result["total_pending"] == 0` (if only ref was validated)

#### Test: test_validation_prompts_sorted_by_urgency
- **Type:** Edge case
- **Setup:** Create multiple refs with different urgency signals
- **Expected:** Sorted by urgency_score descending
- **Assertions:**
  - First prompt has highest score
  - Scores are descending

#### Test: test_validation_prompts_exchange_created_ref
- **Type:** Happy path
- **Setup:** Create cross-ref
- **Action:** Include ref in `exchange_created_refs`
- **Expected:** +50 urgency, "created_this_exchange" in reasons
- **Assertions:**
  - `urgency_score >= 50`
  - "created_this_exchange" in `urgency_reasons`

#### Test: test_validation_prompts_combined_urgency_signals
- **Type:** Integration
- **Setup:** Create cross-ref that is: citing + cluster_flagged + low_confidence
- **Expected:** All signals combine (100 + 30 + 20 = 150+)
- **Assertions:**
  - `urgency_score >= 150`
  - All three signals in `urgency_reasons`

---

### 4.2 detect_contradictions

#### Test: test_detect_contradictions_implements_vs_contradicts
- **Type:** Happy path
- **Setup:** Context A refs B with "implements", B refs A with "contradicts"
- **Expected:** Contradiction detected
- **Assertions:**
  - `len(result) >= 1`
  - `"implements_vs_contradicts" in result[0]["contradiction_type"]`

#### Test: test_detect_contradictions_depends_vs_blocks
- **Type:** Happy path
- **Setup:** A refs B with "depends_on", same pair has "blocks" ref
- **Expected:** Contradiction detected
- **Assertions:**
  - `"depends_on_vs_blocks" in result[0]["contradiction_type"]`

#### Test: test_detect_contradictions_no_contradictions
- **Type:** Edge case
- **Setup:** Create refs with non-contradicting types
- **Expected:** Empty list
- **Assertions:**
  - `len(result) == 0`

#### Test: test_detect_contradictions_specific_context
- **Type:** Happy path
- **Setup:** Create contradictions in different contexts
- **Action:** Query specific context
- **Expected:** Only that context's contradictions
- **Assertions:**
  - All returned contradictions involve the queried context

#### Test: test_detect_contradictions_derived_vs_contradicts
- **Type:** Happy path
- **Setup:** A refs B with "derived_from", B refs A with "contradicts"
- **Expected:** Contradiction detected
- **Assertions:**
  - `"derived_from_vs_contradicts"` in result

---

### 4.3 check_chain_stability

#### Test: test_check_chain_stability_stable
- **Type:** Happy path
- **Setup:** Context A depends_on B, B has all refs validated
- **Expected:** Stable
- **Assertions:**
  - `result["is_stable"] == True`
  - `result["stability_score"] == 1.0`
  - `result["unstable_dependencies"] == []`

#### Test: test_check_chain_stability_unstable_dependency
- **Type:** Happy path
- **Setup:** Context A depends_on B, B has unvalidated refs
- **Expected:** Unstable
- **Assertions:**
  - `result["is_stable"] == False`
  - `len(result["unstable_dependencies"]) >= 1`
  - `result["stability_score"] < 1.0`

#### Test: test_check_chain_stability_derived_from_unstable
- **Type:** Happy path
- **Setup:** A derived_from B, B has unvalidated refs
- **Expected:** Marked unstable
- **Assertions:**
  - B appears in `unstable_dependencies`
  - `ref_type == "derived_from"` in unstable entry

#### Test: test_check_chain_stability_implements_unstable
- **Type:** Happy path
- **Setup:** A implements B, B has unvalidated refs
- **Expected:** Marked unstable
- **Assertions:**
  - B appears in `unstable_dependencies`

#### Test: test_check_chain_stability_ignores_non_dependency_refs
- **Type:** Edge case
- **Setup:** A has "cites" ref to B (not a dependency), B has unvalidated refs
- **Expected:** Still stable (cites is not a dependency type)
- **Assertions:**
  - `result["is_stable"] == True`

#### Test: test_check_chain_stability_invalid_context
- **Type:** Error case
- **Setup:** No context created
- **Expected:** Error returned
- **Assertions:**
  - `result["success"] == False`

#### Test: test_check_chain_stability_score_calculation
- **Type:** Edge case
- **Setup:** Create context with multiple unstable dependencies (e.g., 5)
- **Expected:** Score decreases by 0.2 per unstable dep, min 0.0
- **Assertions:**
  - `result["stability_score"] == 0.0` (5 * 0.2 = 1.0 deducted, but capped at 0.0)

#### Test: test_check_chain_stability_unvalidated_count_accurate
- **Type:** Happy path
- **Setup:** A depends_on B, B has 3 unvalidated refs
- **Expected:** Accurate count in response
- **Assertions:**
  - `unstable_dependencies[0]["unvalidated_refs_in_dependency"] == 3`

---

## Section 5: Test Fixtures and Helpers

### Required Fixtures

```python
@pytest.fixture
def orchestrator():
    """Fresh orchestrator with auto_load=False to avoid persistence side effects."""
    from conversation_orchestrator import ConversationOrchestrator, reset_orchestrator
    reset_orchestrator()
    return ConversationOrchestrator(auto_load=False)

@pytest.fixture
def context_pair(orchestrator):
    """Two contexts for cross-ref testing."""
    ctx1 = orchestrator.create_root_context(task_description="Context A")
    ctx2 = orchestrator.create_root_context(task_description="Context B")
    return ctx1, ctx2

@pytest.fixture
def mock_redis():
    """Mock redis_interface for queue/yarn tests."""
    from unittest.mock import MagicMock, patch
    from datashapes import YarnBoardState

    with patch('datashapes.redis_interface') as mock:
        mock.get_yarn_state.return_value = None
        mock.set_grabbed.return_value = False
        mock.queue_for_agent.return_value = False
        mock.get_agent_queue.return_value = []
        yield mock
```

### Helper Functions

```python
def create_aged_cross_ref(orchestrator, source_id, target_id, days_old):
    """Create a cross-ref with backdated created_at for staleness testing."""
    result = orchestrator.add_cross_ref(source_id, target_id)
    # Manually backdate the created_at
    ctx = orchestrator.get_context(source_id)
    metadata = ctx.cross_sidebar_refs[target_id]
    old_date = datetime.now() - timedelta(days=days_old)
    metadata["created_at"] = old_date.isoformat()
    return result

def add_multiple_sources(orchestrator, source_id, target_id, source_count):
    """Add cross-ref with multiple sources to trigger clustering."""
    for i in range(source_count):
        orchestrator.add_cross_ref(
            source_id, target_id,
            suggested_by=f"AGENT-source-{i}"
        )
```

---

## Section 6: Test Matrix Summary

| Area | Happy Path | Edge Case | Error Case | Integration |
|------|------------|-----------|------------|-------------|
| get_yarn_layout | 2 | 0 | 1 | 0 |
| save_yarn_layout | 2 | 1 | 0 | 1 |
| update_point_position | 2 | 1 | 1 | 0 |
| get_yarn_state | 1 | 1 | 0 | 0 |
| set_grabbed | 1 | 1 | 0 | 0 |
| render_yarn_board | 3 | 2 | 0 | 0 |
| route_scratchpad_entry | 3 | 1 | 0 | 1 |
| curator_approve_entry | 2 | 0 | 0 | 1 |
| _infer_destination | 3 | 2 | 0 | 0 |
| get_agent_queue | 1 | 1 | 0 | 0 |
| register_agent | 2 | 0 | 0 | 0 |
| list_agents | 2 | 0 | 0 | 0 |
| CLUSTERING_THRESHOLD | 1 | 0 | 0 | 0 |
| add_cross_ref clustering | 2 | 3 | 0 | 0 |
| get_cluster_flagged_refs | 2 | 2 | 0 | 0 |
| get_validation_prompts | 4 | 3 | 0 | 1 |
| detect_contradictions | 3 | 2 | 0 | 0 |
| check_chain_stability | 3 | 3 | 1 | 0 |

**Total: ~60 tests**

---

## Section 7: Critical Path Tests (Must Pass for Phase 5)

These tests verify the core Phase 5 behaviors. If any fail, the feature is broken:

1. **test_add_cross_ref_third_source_triggers_clustering** - The 3rd source MUST set `cluster_flagged=True` and `validation_priority="urgent"`

2. **test_validation_prompts_actively_citing_inline** - Refs in `citing_refs` MUST route to `inline_prompts`

3. **test_validation_prompts_not_citing_scratchpad** - Non-cited refs with urgency signals MUST route to `scratchpad_prompts`

4. **test_route_finding_through_curator** - All findings MUST go through curator first

5. **test_check_chain_stability_unstable_dependency** - Dependencies with unvalidated refs MUST mark parent as unstable

6. **test_detect_contradictions_implements_vs_contradicts** - Contradicting ref types MUST be detected

---

## Section 8: Notes for Implementation

### Mocking Strategy
- Redis operations should be mocked since Redis stub returns empty/False
- Persistence operations can be mocked or use in-memory only (`auto_load=False`)
- Ozolith logging can be mocked to verify events are emitted

### Two-Stage Testing (per CLAUDE.md)
1. **Unit Logic Testing:** Test methods directly with controlled inputs
2. **Integration Simulation:** Test through command/API flow if applicable

### Datetime Handling
- Use `freezegun` or manual datetime injection for staleness tests
- Store ISO strings, parse with `datetime.fromisoformat()`

### Cleanup
- Always call `reset_orchestrator()` in fixtures to avoid state leakage
- Use fresh contexts for each test (don't share contexts between tests)
