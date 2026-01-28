# Session Notes - January 24, 2026

## Summary

Continued UI Verification Checklist (Sections 5-8), added collapsible sidebar with notification system, fixed breadcrumb persistence, added New Root button, and resolved the critical chat history persistence gap.

---

## What We Accomplished

### UI Verification Checklist Progress (Sections 5-8)

| Section | Status | Issues Found & Fixed |
|---------|--------|---------------------|
| 5 - Pagination | PASS | Polling reset bug (stale closure), hidden in tree view, black-on-black text, invisible arrow buttons |
| 6 - Rename/Alias | PASS | Alias not updating in breadcrumb |
| 7 - Tags | PASS | Tags rendered as plain grey text (now colored pills, 13-color hash-based system) |
| 8 - Browse Aliases | PASS | All items pass |

### Pagination Polling Fix
The 5-second polling interval was calling `loadSidebars()` with no offset, resetting to page 1 every tick. Fixed with `currentOffsetRef` to preserve current page across poll cycles.

### Tag Color System (Baker's Dozen)
13 hash-based deterministic colors for tag pills. Same tag always gets same color across sessions.

### Collapsible Sidebar Panel (New Feature)
- Collapse replaces resize handle with a 2px vertical strip
- Centered chevron on both collapse and expand states
- Hover reveals the expand chevron
- Error notification overlay slides from right edge (semi-transparent, doesn't shift layout)
- Auto-dismiss after 3 seconds, severity-based coloring

### Breadcrumb Persistence for Archived Contexts
Active context was disappearing from breadcrumb when archived. Added `activeContextInfo` state as fallback so the breadcrumb always shows the last-known context info.

### New Root Button
Green "Root" button next to "New" in sidebar panel. Creates a new root conversation node.

### Chat History Persistence (Critical Fix)
**The gap:** `chat.conversation_history` was purely in-memory on `RichMemoryChat`. Exchanges were never written to sidebar's `local_memory`. Server restart = all chat gone.

**The fix (3 parts in api_server_bridge.py):**
1. Chat endpoint writes each exchange to active context's `local_memory` and persists to SQLite
2. Focus endpoint swaps `chat.conversation_history` to match the focused context's `local_memory`
3. Startup event loads active context's `local_memory` into `chat.conversation_history`

**Confirmed working:** Post-fix exchanges survive server restarts. Pre-fix exchanges were lost (expected - never written to disk).

### Alias & Tag Persistence (Schema v3 Migration)
`display_names` and `tags` weren't in the SQLite schema. Added v3 migration with `display_names_json` and `tags_json` columns in `sidebar_persistence.py`.

### Scratchpad Attribute Fix
`/sidebars/{id}` endpoint crashed on `ctx.scratchpad` access. Added `scratchpad: Optional['Scratchpad'] = None` to `SidebarContext` dataclass and used `getattr()` in the endpoint for backward compat.

---

## Files Modified

| File | Changes |
|------|---------|
| `src/components/SidebarsPanel.tsx` | TreeData interface, tree node display with fallback chain, 13-color tag pills, pagination styling, onCreateRoot prop |
| `src/App.tsx` | Resizable sidebar, collapsible panel + notifications, breadcrumb fallback, currentOffsetRef, activeContextInfo state |
| `api_server_bridge.py` | Tree augmentation fix, chat persistence (3 parts), scratchpad safe access |
| `sidebar_persistence.py` | Schema v3 migration (display_names_json, tags_json columns) |
| `datashapes.py` | Added `scratchpad: Optional['Scratchpad'] = None` to SidebarContext |

---

## Memory Services Confirmed

| Service | Port | Status |
|---------|------|--------|
| Working Memory | 5001 | Healthy, buffer 0/20 |
| Episodic Memory | 8005 | Healthy, SQLite DB present |
| Memory Curator | 8004 | Healthy, linguistic model loaded |

These handle LLM context recall. The chat persistence gap was specifically about UI display persistence (SQLite), not the memory services themselves.

---

## Remaining Work (Next Session)

### UI Verification Checklist
- Section 9: Bulk Archive
- Section 10: Prune
- Section 11: Search
- Section 12: Context Switching
- Section 13: Error Handling
- Section 14: Performance

### Known Issues
- LLM Studio 400 error (noted, not blocking UI work)
- Alias citation history (the "2 versions" provenance tracking - separate from display_names persistence)

---

## Key Insight

The fundamental disconnect was between the **chat system** (RichMemoryChat, in-memory) and the **sidebar system** (Orchestrator, persisted). Exchanges flowed through chat but never got written to the sidebar's `local_memory`. The memory services (working/episodic/curator) handle LLM recall quality - they were already wired. The gap was purely in the UI persistence layer.
