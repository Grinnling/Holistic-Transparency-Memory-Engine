# Sidebar UI Testing Requirements
**Date:** 2026-01-05
**Updated:** 2026-01-06 (Added persistence, reparent, yarn board tests)
**Components:** API endpoints + React UI + SQLite persistence + Yarn Board

---

## Pre-Test Setup

### Fresh Install (No Prior State)

1. **Ensure no existing database:**
   ```bash
   # Check if sidebar_state.db exists
   ls -la /home/grinnling/Development/CODE_IMPLEMENTATION/data/sidebar_state.db
   # If exists and want fresh start, remove it (DESTRUCTIVE)
   # rm data/sidebar_state.db
   ```

2. **Start API Server:**
   ```bash
   cd /home/grinnling/Development/CODE_IMPLEMENTATION
   python3 api_server_bridge.py
   ```
   - Fresh start: `🌿 No prior state found - starting fresh`
   - With persistence: `🌿 Loaded X contexts from persistence`
   - Should see: `🌿 Sidebar endpoints: GET/POST /sidebars/*`

3. **React Dev Server** (if not already running):
   ```bash
   npm start
   ```
   - Should open http://localhost:3000

### Existing State (Persistence Testing)

1. **Verify state survives restart:**
   - Note current context count before restart
   - Kill API (`Ctrl+C`)
   - Restart API
   - Verify same context count loaded

---

## API Endpoint Tests

### GET Endpoints (Read Operations)

| Endpoint | Test | Expected (Fresh) | Expected (With Data) |
|----------|------|------------------|----------------------|
| `GET /sidebars` | `curl http://localhost:8000/sidebars` | `{"contexts": [], "count": 0}` | `{"contexts": [...], "count": N}` |
| `GET /sidebars?status=active` | Filter by status | Empty or filtered list | Only active contexts |
| `GET /sidebars/tree` | `curl http://localhost:8000/sidebars/tree` | `{"tree": null}` | Nested tree structure |
| `GET /sidebars/active` | `curl http://localhost:8000/sidebars/active` | `{"active": null, "message": "No active context"}` | Active context details |
| `GET /sidebars/{id}` | With invalid ID | `{"error": "Context {id} not found", "context": null}` | Same |
| `GET /sidebars/{id}` | With valid ID | N/A | Full context object |

### POST Endpoints (Write Operations)

| Endpoint | Test | Expected Result |
|----------|------|-----------------|
| `POST /sidebars/spawn` | Create sidebar | Returns new context, persisted to SQLite |
| `POST /sidebars/{id}/focus` | Switch focus | `{"success": true, "active_id": "..."}`, focus persisted |
| `POST /sidebars/{id}/pause` | Pause context | `{"success": true, "status": "paused"}`, persisted |
| `POST /sidebars/{id}/resume` | Resume paused | `{"success": true, "status": "active"}`, persisted |
| `POST /sidebars/{id}/merge` | Merge to parent | `{"success": true, "summary": "..."}`, persisted |
| `POST /sidebars/{id}/archive` | Archive context | `{"success": true, "status": "archived"}`, persisted |
| `POST /sidebars/{id}/reparent` | Change parent | `{"success": true, "old_parent": "...", "new_parent": "..."}` |
| `POST /sidebars/{id}/cross-ref` | Add cross-ref | `{"success": true, "ref_id": "..."}`, bidirectional |

---

## Persistence Tests (Phases 1-3)

### SQLite Round-Trip

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Schema creation** | First startup with no DB | `sidebar_state.db` created with tables |
| **Save context** | Create sidebar | Row appears in `sidebar_contexts` table |
| **Load context** | Query DB directly | All fields match in-memory state |
| **JSON blob integrity** | Check `local_memory_json` | Proper JSON, deserializes correctly |
| **Relationship FK** | Child context | `parent_context_id` points to valid row |

### Restart Survival

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Basic survival** | Create context, restart API | Context exists after restart |
| **Status preserved** | Pause, restart | Still paused after restart |
| **Memory preserved** | Add exchanges, restart | All exchanges present |
| **Tree structure** | Create nested sidebars, restart | Parent-child relationships intact |
| **Focus preserved** | Set focus, restart | Same context focused after restart |
| **Focus fallback** | Focus on ARCHIVED, restart | Falls back to parent → ACTIVE → none |

### Migration Testing

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Version pragma** | Check DB | `PRAGMA user_version` returns current version |
| **Migration runs** | Upgrade schema version | Migration function executes |
| **Data preserved** | Run migration | Existing data not lost |

### Write-Through Failure Handling

| Test | Action | Expected Result |
|------|--------|-----------------|
| **DB write fails** | Simulate disk full/locked | In-memory state NOT modified |
| **EmergencyCache** | After write failure | Pending write queued |
| **Recovery** | Fix disk, retry | Queued writes succeed |

---

## React UI Tests

### SidebarControlBar (Above Chat Input)

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Renders** | Load page | Control bar visible above chat input |
| **Breadcrumb default** | No active context | Shows "Main" with home icon |
| **Status badge** | Hover over badge | Tooltip shows `{reason}: {status}` |
| **Fork button** | Click "Fork" | Inline input expands |
| **Fork input** | Type reason + Enter | Creates sidebar, input closes |
| **Fork cancel** | Press Escape | Input closes, no sidebar created |
| **Back button** | In a sidebar | Shows "Back" button; clicking navigates to parent |
| **Exchange counts** | With active context | Shows "X local + Y inherited" |

### SidebarsPanel (Sidebars Tab)

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Tab visible** | Check sidebar tabs | "Sidebars" tab present (shows count if > 0) |
| **Empty state** | No sidebars | Shows "No sidebars yet. Click 'New' to spawn one." |
| **List/Tree toggle** | Click toggle buttons | Switches between list and tree view |
| **Spawn form** | Click "New" button | Form expands with reason input |
| **Refresh button** | Click refresh icon | Reloads sidebar list from API |
| **Status colors** | Various statuses | Active=grey, Paused=blue, Failed=red, Merged=dim |
| **Action buttons** | Per context | Focus/Pause/Resume/Merge/Archive based on status |
| **Active highlight** | Click Focus | Ring highlight on active context |
| **Completed section** | Merged/archived contexts | Collapsible section at bottom |

### Status Handling (All 10 States)

| Status | Color | Badge | Actions Available |
|--------|-------|-------|-------------------|
| `active` | Grey | default | Pause, Merge*, Archive |
| `paused` | Blue | secondary | Focus, Resume, Merge*, Archive |
| `waiting` | Blue | secondary | Focus, Resume, Merge*, Archive |
| `testing` | Blue | secondary | Focus, Pause, Merge*, Archive |
| `reviewing` | Blue | secondary | Focus, Merge*, Archive |
| `spawning_child` | Blue | secondary | Focus, Archive |
| `consolidating` | Blue | secondary | Focus, Archive |
| `merged` | Dim grey | outline | Archive |
| `archived` | Dim grey | outline | (none) |
| `failed` | Red | destructive | Archive |

*Merge only available if context has a parent (not root)

---

## Reparent & Cross-Ref Tests (Phase 4)

### Reparent Operations

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Basic reparent** | Move SB-2 from SB-1 to SB-5 | Parent changes, both old/new parent child_ids updated |
| **Promote to root** | Reparent with `new_parent=null` | Context becomes root, no parent |
| **Create umbrella** | Create new root, reparent existing roots under it | All former roots now children |
| **Cycle detection** | Try to make parent a child of itself | Error: "Would create circular reference" |
| **Children move** | Reparent context with children | All descendants stay attached |
| **OZOLITH event** | Any reparent | `CONTEXT_REPARENT` event logged |
| **original_conversation_id** | Reparent former root | Original ID preserved in metadata |

### Cross-Ref Operations

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Add cross-ref** | SB-2 cites SB-7 | `cross_sidebar_refs` updated on SB-2 |
| **Bidirectional** | Add ref SB-2 → SB-7 | SB-7 also shows ref to SB-2 |
| **Cross-tree** | Ref context in different tree | Works, shows in both contexts |
| **OZOLITH event** | Add cross-ref | `CROSS_REF_ADDED` event logged |
| **Query refs** | Get all refs for context | Returns both outgoing and incoming |
| **Archived ref health** | Ref to archived context | Shows warning: "source is read-only" |

---

## Yarn Board Tests (Phase 5)

### Priority Creation

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Create priority** | Add HIGH priority "Fix auth" | PRI-X created, attached to context |
| **5-tier levels** | Create each level | CRITICAL/HIGH/NORMAL/LOW/BACKGROUND all work |
| **Custom tag** | Add priority with custom tag | `custom_tag` field populated |
| **Attribution** | Create priority | `created_by` shows "claude" or "human" |
| **OZOLITH event** | Create priority | `PRIORITY_CREATED` event logged |

### Priority Relationships

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Blocks** | PRI-1 blocks PRI-2 | Relationship tracked |
| **Depends on** | PRI-3 depends on PRI-1 | Relationship tracked |
| **Relates to** | PRI-4 relates to PRI-5 | Relationship tracked |
| **View connections** | Query priority | All relationships returned |

### Priority Inheritance (Sidebar Spawn)

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Auto-suggest** | Spawn sidebar | Relevant parent priorities suggested |
| **Human confirms** | Approve/modify suggestions | Selected priorities inherited |
| **Decline all** | Reject inheritance | Sidebar starts with no inherited priorities |

### Priority Merge Behavior

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Completed priority** | Merge with completed PRI | Summary includes completion |
| **Open priority** | Merge with open PRI | Decision prompt: bubble or keep |
| **Bubble to parent** | Choose bubble | Priority moves to parent context |
| **Keep in merged** | Choose keep | Priority stays as reference only |

### Yarn Display

| Test | Action | Expected Result |
|------|--------|-----------------|
| **View yarn** | Open yarn panel | Shows active threads, watching, connections |
| **Adjust priority** | Change level | Updates immediately, persists |
| **Add from yarn** | Create priority from yarn view | Works same as inline creation |

---

## Startup/Shutdown Ritual Tests (Phase 3 Enhancements)

### Closing Ritual

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Trigger** | End session / explicit close | Closing ritual UI appears |
| **Summary** | Claude fills in accomplishments | Auto-populated from local_memory |
| **Open items** | Flagged items shown | Pulled from context |
| **Confidence check** | Uncertainty prompt | Claude can flag uncertain findings |
| **Priority suggestion** | Next session priority | Editable suggestion |
| **Save notes** | Confirm closing | Saved to `closing_notes` metadata |

### Opening Ritual

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Display notes** | Startup with prior session | Shows last session's closing notes |
| **Time since** | Check elapsed time | Shows "14 hours since last activity" |
| **Interactive** | Ready/review options | Can continue or adjust before starting |

### Recovery Awareness

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Pending items** | Items in EmergencyCache | Warning: "2 items in recovery queue" |
| **Review recovery** | `/recovery` command | Shows pending items |
| **Dismiss** | Clear recovery queue | Queue emptied |

### Stale Context Hints

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Stale detection** | PAUSED context 3+ days | Hint: "SB-3 has been PAUSED for 3 days" |
| **Actions offered** | View hint | Resume / Archive / Ignore options |

### Cross-Ref Health

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Healthy ref** | Ref to active context | No warning |
| **Archived ref** | Ref to archived context | Warning: "source is read-only" |
| **Missing ref** | Ref to deleted context | Error: "referenced context not found" |

---

## Integration Tests

### Full Workflow Test (Updated for Persistence)

1. **Start fresh** - Remove `sidebar_state.db`, start API
2. **Check empty state** - Sidebars tab shows empty message
3. **Create root** - Root created (manually or via first spawn)
4. **Spawn sidebar** - Use Fork button, enter reason "Test sidebar"
5. **Verify creation** - New sidebar in list, becomes active
6. **Check breadcrumbs** - Shows Main > Test sidebar
7. **Pause sidebar** - Click Pause, verify status changes to blue
8. **Resume sidebar** - Click Resume, verify returns to grey/active
9. **Spawn child** - Fork again from within sidebar
10. **Check tree** - Switch to tree view, verify nesting
11. **⭐ Restart API** - Kill and restart `api_server_bridge.py`
12. **⭐ Verify survival** - All contexts still present, tree intact
13. **Merge** - Merge child back to parent
14. **Archive** - Archive the original sidebar
15. **Completed section** - Verify appears in collapsible completed section
16. **⭐ Final restart** - Kill and restart, verify merged/archived states persisted

### Reparent Workflow Test

1. **Create 3 root contexts** - SB-1, SB-5, SB-9 (independent trees)
2. **Create umbrella** - New root SB-15 with reason "Unifying investigations"
3. **Reparent each** - Move SB-1, SB-5, SB-9 under SB-15
4. **Verify tree** - All three now children of SB-15
5. **Check OZOLITH** - 3 `CONTEXT_REPARENT` events logged
6. **Check metadata** - `original_conversation_id` preserved on former roots
7. **Restart** - Verify reparented structure survives restart

### Cross-Ref Workflow Test

1. **Create two trees** - Tree A (SB-1 → SB-2), Tree B (SB-5 → SB-6)
2. **Work in SB-2** - Add some exchanges
3. **Create cross-ref** - SB-6 cites findings from SB-2
4. **Verify bidirectional** - SB-2 shows incoming ref from SB-6
5. **Archive SB-2** - Mark as archived
6. **Check health** - SB-6 shows warning about archived source
7. **Restart** - Verify cross-refs survive restart

### WebSocket Broadcast Test

When sidebar actions occur, connected clients should receive:
- `sidebar_spawned` - When new sidebar created
- `focus_changed` - When focus switches
- `sidebar_paused` - When context paused
- `sidebar_resumed` - When context resumed
- `sidebar_merged` - When merged to parent
- `sidebar_archived` - When archived
- `sidebar_reparented` - When parent changed
- `cross_ref_added` - When cross-reference created

---

## Error Scenario Tests

### API Error Handling

| Scenario | Test | Expected Result |
|----------|------|-----------------|
| **API down** | Stop API, try UI actions | UI shows error, doesn't crash |
| **Invalid context ID** | `POST /sidebars/invalid-id/focus` | Returns `{"error": "...", "success": false}` |
| **Spawn without parent** | `POST /sidebars/spawn` with bad parent_id | Returns error, no crash |
| **Double pause** | Pause already-paused context | Handles gracefully (no-op or error) |
| **Merge root** | Try to merge context with no parent | Returns error (root can't merge) |
| **Archive archived** | Archive already-archived context | Handles gracefully |
| **Focus on archived** | Try to focus on archived context | Fails or warns |
| **Reparent to self** | Try `reparent(SB-1, SB-1)` | Error: "Cannot reparent to self" |
| **Reparent cycle** | Make ancestor a child | Error: "Would create circular reference" |

### Persistence Error Handling

| Scenario | Test | Expected Result |
|----------|------|-----------------|
| **DB locked** | Lock SQLite file, try write | EmergencyCache queues write |
| **Corrupt DB** | Damage DB file, restart | Choice dialog: Retry/Fresh/Exit |
| **Missing DB** | Delete DB, restart | Fresh start (clean slate) |
| **Schema mismatch** | Wrong version pragma | Migration runs or error |

### Network Error Handling

| Scenario | Test | Expected Result |
|----------|------|-----------------|
| **Timeout** | Slow/hanging API response | UI shows loading state, eventually errors |
| **Partial response** | Malformed JSON | Error logged, UI doesn't crash |
| **Connection lost mid-action** | Kill API during spawn | Action fails, UI recovers |

### UI Edge Cases

| Scenario | Test | Expected Result |
|----------|------|-----------------|
| **Empty reason** | Try to spawn with blank reason | Button disabled or validation error |
| **Very long reason** | 500+ character reason string | Truncates in display, full in tooltip |
| **Rapid clicks** | Click spawn/merge multiple times fast | Debounced or queued, no duplicates |
| **Special characters** | Reason with `<script>`, quotes, unicode | Properly escaped, no XSS |

---

## Known Limitations / Notes

1. **~~Root context auto-created~~** - ~~STOPGAP replaced with proper persistence~~
   - On first run: No state, user can create root or API creates on first spawn
   - On subsequent runs: State loaded from SQLite

2. **Tree view** - Only populates after spawning sidebars. Initially null.

3. **Inherited counts** - Only visible on sidebars (not root context).

4. **Merge auto-summarize** - Currently uses `auto_summarize: true`, backend generates summary.

5. **Yarn Board Phase 5** - Priority system requires all Phase 1-4 to be complete first.

6. **Opening/Closing Rituals** - Only functional after Phase 3 persistence is complete.

---

## Files Modified This Session

```
api_server_bridge.py              - Added /sidebars/* endpoints
src/components/SidebarsPanel.tsx  - NEW: Full sidebar management panel
src/components/SidebarControlBar.tsx - NEW: Quick controls above chat
src/App.tsx                       - Wired in new components + state
```

## Files To Be Modified (Persistence Implementation)

```
datashapes.py                     - Add OzolithPayloadContextReparent, new event types
conversation_orchestrator.py      - Add persistence methods, reparent, cross-ref
ozolith.py                        - Register new event types
api_server.py                     - Replace stopgap with proper startup sequence
NEW: sidebar_persistence.py       - SQLite operations
NEW: data/sidebar_state.db        - SQLite database (auto-created)
```

---

*Testing instance can use this sheet to validate all functionality.*
