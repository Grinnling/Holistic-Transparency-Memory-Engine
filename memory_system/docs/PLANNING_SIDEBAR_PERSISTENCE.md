# Sidebar Persistence Planning Document
**Created:** 2026-01-05
**Purpose:** Design how sidebar/context trees persist across API restarts
**Status:** Needs planning session

---

## The Problem

The ConversationOrchestrator is **in-memory only**. When the API restarts:
- All contexts are lost
- No way to resume a conversation tree
- User loses all sidebar work

---

## Existing Pieces We Have

### 1. OZOLITH (Immutable Audit Log)
**Location:** `ozolith.py`

Already logs:
- `SIDEBAR_SPAWN` - When sidebars are created
- `SIDEBAR_MERGE` - When sidebars merge back
- `SESSION_START` / `SESSION_END`
- All exchanges with full metadata

**Could provide:** Source of truth for rebuilding context tree

### 2. Emergency Cache (UNIFIED_SIDEBAR_ARCHITECTURE.md)
**Status:** Designed but not implemented

Describes:
- SQLite layer for crash recovery
- Startup recovery checks
- Clean shutdown detection
- Multi-layer caching (filesystem → SQLite → Redis)

**Could provide:** Queryable state for fast recovery

### 3. ConversationOrchestrator
**Location:** `conversation_orchestrator.py`

Has methods but no persistence:
- `create_root_context()` - Creates root
- `spawn_sidebar()` - Creates children
- `list_contexts()` - Returns in-memory list
- `get_tree()` - Returns tree structure

**Needs:** Save/load capability

### 4. Conversation ID (rich_chat.py)
**Existing:** `conversation_id` in rich_chat.py

Already persists conversation exchanges to working memory / episodic memory.

**Could provide:** Anchor point for tying context tree to conversation

---

## Questions to Answer

### Core Architecture
1. **What is the source of truth for context state?**
   - Option A: OZOLITH (replay events to rebuild)
   - Option B: SQLite (direct state storage)
   - Option C: Both (SQLite for fast load, OZOLITH for verification)

2. **How do contexts relate to conversation_id?**
   - One context tree per conversation_id?
   - Or separate tracking?

3. **What triggers persistence?**
   - Every state change (spawn, pause, merge)?
   - Periodic snapshots?
   - On clean shutdown only?

### Recovery Scenarios
4. **Clean restart (API stopped and started):**
   - How do we know there's state to load?
   - How do we identify which conversation to resume?

5. **Crash recovery (unclean shutdown):**
   - Emergency cache already designed - implement it?
   - OZOLITH replay as fallback?

6. **Multiple conversations:**
   - Can user have multiple conversation trees?
   - How to select which to load on startup?

### User Experience
7. **Default behavior on startup:**
   - Auto-load last active conversation?
   - Prompt user to select?
   - Always start fresh (opt-in to resume)?

8. **UI for conversation selection:**
   - List of saved conversation trees?
   - "Continue last" vs "Start new"?

---

## Option Sketches

### Option A: OZOLITH-Based Rebuild
```
Startup:
1. Query OZOLITH for last session's events
2. Replay SIDEBAR_SPAWN events to rebuild tree
3. Set status based on last known state
4. Resume from where user left off
```
**Pros:** Single source of truth, audit trail
**Cons:** Slower startup, need replay logic

### Option B: SQLite State Storage
```
Startup:
1. Check SQLite for saved context tree
2. Load directly into orchestrator
3. Resume immediately

On every state change:
1. Update SQLite row for that context
```
**Pros:** Fast load, simple queries
**Cons:** Two sources of truth (OZOLITH + SQLite)

### Option C: Hybrid (Fast Load + Verification)
```
Startup:
1. Load from SQLite (fast)
2. Background verify against OZOLITH (integrity)
3. Flag any discrepancies

On state change:
1. Write to OZOLITH (immutable audit)
2. Update SQLite (queryable state)
```
**Pros:** Best of both
**Cons:** More complexity

---

## Files That Would Change

| File | Changes Needed |
|------|----------------|
| `conversation_orchestrator.py` | Add save/load methods |
| `api_server_bridge.py` | Call load on startup, save on changes |
| `ozolith.py` | Add replay/query methods for rebuild |
| NEW: `context_persistence.py` | SQLite layer if using Option B/C |

---

## Suggested Planning Approach

1. **Decide source of truth** - OZOLITH vs SQLite vs Hybrid
2. **Define startup flow** - What happens when API starts
3. **Define save triggers** - When to persist state
4. **Implement minimal version** - Just enough for testing
5. **Add recovery features** - Crash handling, verification

---

## Notes for Planning Session

- Keep it simple for v1 - we can add sophistication later
- The testing instance needs SOMETHING to work with
- Auto-create root on startup is fine as stopgap
- Full persistence can be Phase 2

---

*Take this doc to a side instance for focused planning discussion.*
