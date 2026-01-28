# Sidebar Persistence Implementation Plan

**Created:** 2026-01-06
**Updated:** 2026-01-06 (All phases finalized)
**Status:** ✅ INTERVIEW COMPLETE - Ready for implementation
**Source Session:** Planning interview between operator and Claude (Opus 4.5)
**Related:** `PLANNING_SIDEBAR_PERSISTENCE.md`, `UNIFIED_SIDEBAR_ARCHITECTURE.md`

---

## Executive Summary

This document captures the findings from our planning interview and defines the implementation path for sidebar persistence. The goal is to replace the current stopgap (auto-create root on startup) with proper state persistence across API restarts.

**Core Insight from Interview:** A sidebar IS a conversation - same structure, different relationship. The `parent_context_id` field determines root (None) vs child (something). This means we're persisting one unified structure, not two different things.

---

## 1. Findings from Code Review

### 1.1 What Already Exists

| Component | Location | Status |
|-----------|----------|--------|
| `SidebarContext` dataclass | `datashapes.py:63-101` | Complete - has all fields |
| `ConversationOrchestrator` | `conversation_orchestrator.py` | Complete - but in-memory only |
| OZOLITH audit log | `ozolith.py` | Complete - query capable |
| Context Registry | `context_registry.py` | Complete - tracks IDs |

### 1.2 SidebarContext Fields (Already Defined)

```python
@dataclass
class SidebarContext:
    # Identity & Hierarchy
    sidebar_id: str                           # SB-{sequential}
    uuid: str                                 # Full UUID
    parent_context_id: Optional[str] = None   # None = ROOT, value = CHILD
    child_sidebar_ids: List[str] = []         # Children of this context
    forked_from: Optional[str] = None         # For reviving archived work

    # Participants
    participants: List[str] = []
    coordinator_agent: Optional[str] = "AGENT-operator"

    # Memory (Critical Separation)
    inherited_memory: List[Dict] = []         # READ ONLY snapshot from parent
    local_memory: List[Dict] = []             # This context's work
    data_refs: Dict[str, Any] = {}            # Referenced artifacts
    cross_sidebar_refs: List[str] = []        # Links to OTHER contexts

    # Relevance
    relevance_scores: Dict[str, float] = {}
    active_focus: List[str] = []

    # Lifecycle
    status: SidebarStatus
    priority: SidebarPriority
    created_at: datetime
    last_activity: datetime

    # Task
    task_description: Optional[str] = None
    success_criteria: Optional[str] = None
    failure_reason: Optional[str] = None
```

### 1.3 OZOLITH Query Capabilities (Already Built)

```python
# Direct methods
oz.get_by_context(context_id)      # All entries for a context
oz.get_by_type(event_type)         # All SIDEBAR_SPAWN, etc.
oz.get_by_timerange(start, end)    # Filter by time
oz.get_by_payload(key, value)      # Query payload fields

# Chainable query builder
oz.query()
    .by_type(OzolithEventType.SIDEBAR_SPAWN)
    .by_context("SB-root")
    .execute()
```

### 1.4 What's NOT Implemented Yet

| Feature | Dataclass Support | Orchestrator Method | Notes |
|---------|-------------------|---------------------|-------|
| Persistence | Serializable | None | Core gap |
| Reparenting | Field can change | None | Append-only concern |
| Cross-ref tracking | Field exists | None | Need add/query |
| Fork from archived | Field exists | None | Need method |
| Startup recovery | N/A | None | Need loader |

---

## 2. Architecture Decisions from Interview

### 2.1 Conversation Structure Model

**Decision:** Forest of trees with cross-references

```
FOREST (entire system)
├── Tree A (conversation_id = root context ID)
│     ├── SB-1 (root, parent_id=None)
│     │     ├── SB-2 (sidebar, parent_id=SB-1)
│     │     └── SB-3 (sidebar, parent_id=SB-1)
│     │           └── SB-4 (nested, parent_id=SB-3)
│
├── Tree B (another conversation)
│     └── SB-5 (root)
│           └── SB-6 (sidebar)
│
└── Cross-refs: SB-4.cross_sidebar_refs = ["SB-6"]
    (SB-4 cites something from Tree B)
```

**Key Points:**
- Each conversation = one tree
- `conversation_id` maps 1:1 to root context ID (for now)
- Cross-refs allow citing across trees WITHOUT changing structure
- Reparenting allows unifying trees (structural change, needs audit trail)

### 2.2 Persistence Strategy

**Decision:** Option C (Hybrid) - SQLite for fast load, OZOLITH for verification

```
On State Change:
1. Write to OZOLITH (immutable audit - source of truth)
2. Update SQLite (queryable state cache)
3. Update in-memory orchestrator

On Startup:
1. Load from SQLite (fast)
2. Optional: Verify against OZOLITH (integrity check)
3. Populate orchestrator
```

### 2.3 The Reparent Problem

**Concern raised by operator:** "Whatever we do has to honor append-only to keep receipts intact."

**The Problem:**
- 3 separate conversations (Tree A, B, C) all turn out to be about same root cause
- Want to unify them under one umbrella
- Can't just change `parent_context_id` in SQLite - that loses the history

**Proposed Solution: Reparent as Event**

```
BEFORE:
  SB-1 (root, Tree A)
  SB-5 (root, Tree B)
  SB-9 (root, Tree C)

ACTION: Create unifying root, reparent others

AFTER:
  SB-15 (NEW root, umbrella)
    ├── SB-1 (was root, now child of SB-15)
    ├── SB-5 (was root, now child of SB-15)
    └── SB-9 (was root, now child of SB-15)
```

**OZOLITH Events Generated:**
```python
# 1. New umbrella context created
SIDEBAR_SPAWN: {
    context_id: "SB-15",
    parent_context: None,  # It's a root
    reason: "Unifying investigations A, B, C"
}

# 2. Reparent events (NEW event type needed?)
CONTEXT_REPARENT: {
    context_id: "SB-1",
    old_parent: None,      # Was a root
    new_parent: "SB-15",   # Now child of umbrella
    reason: "Unified under SB-15 - same root cause discovered"
}

CONTEXT_REPARENT: {
    context_id: "SB-5",
    old_parent: None,
    new_parent: "SB-15",
    reason: "Unified under SB-15 - same root cause discovered"
}

# ... etc
```

**This preserves:**
- Original history (SB-1 was created as root, worked as root)
- The moment of reparenting (when we realized they're related)
- The reason for unification
- Full audit trail

**Open Questions for Interview:**
1. Do we need a new `CONTEXT_REPARENT` event type in OZOLITH?
2. What happens to the original `conversation_id` after reparenting?
3. Should reparented contexts keep their original `conversation_id` as metadata?

---

## 3. Implementation Phases

### Phase 1: SQLite Schema + Basic Persistence

**Goal:** Contexts survive restart

**Tasks:**
- [ ] Define SQLite schema for `sidebar_contexts` table
- [ ] Define schema for `context_tree` relationships
- [ ] Implement `save_context()` in orchestrator
- [ ] Implement `load_all_contexts()` for startup
- [ ] Add write-through to existing methods (spawn, merge, archive)

**Schema Draft:**
```sql
-- Core context state
CREATE TABLE sidebar_contexts (
    sidebar_id TEXT PRIMARY KEY,      -- SB-1, SB-2, etc.
    uuid TEXT UNIQUE NOT NULL,
    parent_context_id TEXT,           -- NULL for roots
    forked_from TEXT,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    task_description TEXT,
    success_criteria TEXT,
    failure_reason TEXT,
    coordinator_agent TEXT,
    created_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP NOT NULL,

    -- JSON blobs for complex fields
    participants_json TEXT,           -- JSON array
    inherited_memory_json TEXT,       -- JSON array
    local_memory_json TEXT,           -- JSON array
    data_refs_json TEXT,              -- JSON object
    cross_sidebar_refs_json TEXT,     -- JSON array
    relevance_scores_json TEXT,       -- JSON object
    active_focus_json TEXT,           -- JSON array

    FOREIGN KEY (parent_context_id) REFERENCES sidebar_contexts(sidebar_id)
);

-- Index for common queries
CREATE INDEX idx_contexts_status ON sidebar_contexts(status);
CREATE INDEX idx_contexts_parent ON sidebar_contexts(parent_context_id);
CREATE INDEX idx_contexts_last_activity ON sidebar_contexts(last_activity);

-- Track conversation_id -> root mapping
CREATE TABLE conversation_roots (
    conversation_id TEXT PRIMARY KEY,
    root_context_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (root_context_id) REFERENCES sidebar_contexts(sidebar_id)
);

-- Session state (focus tracking, etc.)
CREATE TABLE session_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Stores: 'active_context_id', 'last_startup', etc.
```

**Interview Questions for Phase 1:** ✅ RESOLVED

| Question | Decision | Reasoning |
|----------|----------|-----------|
| JSON blobs vs normalized? | **JSON blobs** | Matches existing `episodic_memory/database.py` pattern. We load/save whole contexts, not querying into memory fields. |
| SQLite file location? | **`data/sidebar_state.db`** | Same folder as `episodic_memory.db` - one place to backup/manage. |
| Migration support? | **Yes - version-based pragma** | Simple approach: `PRAGMA user_version` + sequential migration functions. Low complexity, prevents data loss on schema changes. |

**Migration Pattern:**
```python
SCHEMA_VERSION = 1  # Increment when schema changes

def _check_migrations(self, conn):
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version < SCHEMA_VERSION:
        if current_version < 1:
            self._migrate_v0_to_v1(conn)
        # Future: if current_version < 2: self._migrate_v1_to_v2(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
```

---

### Phase 2: Write-Through + State Sync

**Goal:** Every state change persists immediately

**Tasks:**
- [ ] Wrap orchestrator methods with persistence calls
- [ ] Handle partial failures (memory updated but DB write failed)
- [ ] Add transaction support for multi-step operations
- [ ] Implement dirty flag for batch scenarios (if needed)

**Methods That Need Write-Through:**
```python
# Create operations
create_root_context()     # INSERT
spawn_sidebar()           # INSERT new + UPDATE parent

# State changes
pause_context()           # UPDATE status
resume_context()          # UPDATE status
switch_focus()            # UPDATE (maybe, if we track focus in DB)

# Memory operations
add_exchange()            # UPDATE local_memory_json

# Lifecycle
merge_sidebar()           # UPDATE both sidebar and parent
archive_context()         # UPDATE status
```

**Interview Questions for Phase 2:** ✅ RESOLVED

| Question | Decision | Reasoning |
|----------|----------|-----------|
| Focus tracking persist/ephemeral? | **Persist** | Resume where you left off on restart. Fallback: if last active was MERGED/ARCHIVED, go to parent → any ACTIVE → none. |
| Transaction boundaries? | **Per-operation, atomic** | Matches existing `context_registry.py` pattern (temp file + rename). Each state change is its own transaction. |
| Error recovery strategy? | **Don't modify memory on failure** | Existing OZOLITH pattern: "Entry count unchanged after write failure." Try disk first, only update memory on success. Queue to `EmergencyCache.pending_writes` if really stuck. |

**Existing Patterns Found:**
- `context_registry.py:82` - Atomic write (temp file + rename)
- `test_ozolith.py:1619` - "Write failure preserves in-memory state"
- `datashapes.py:303-332` - `EmergencyCache` with `pending_writes` already defined

**Write-Through Pattern:**
```python
def spawn_sidebar(...):
    # 1. Create context object (tentative, not yet in self._contexts)
    new_context = SidebarContext(...)

    # 2. Try SQLite write FIRST
    try:
        self._persist_context(new_context)  # Atomic write
    except Exception as e:
        # Don't modify in-memory state
        logger.error(f"Persist failed: {e}")
        # Optionally queue to EmergencyCache
        return {"success": False, "error": str(e)}

    # 3. Only on success: update in-memory
    self._contexts[new_context.sidebar_id] = new_context
    return {"success": True, ...}
```

---

### Phase 3: Startup Recovery + Stopgap Replacement

**Goal:** Replace the auto-create stopgap with proper state restoration

**Tasks:**
- [ ] Implement startup sequence in `api_server.py`
- [ ] Load contexts from SQLite into orchestrator
- [ ] Rebuild context registry from loaded state
- [ ] Handle "clean slate" case (no prior state)
- [ ] Remove stopgap code
- [ ] Add recovery audit logging

**Startup Sequence:**
```python
async def startup_with_persistence():
    orchestrator = get_orchestrator()

    # 1. Check for existing state
    db_path = get_db_path()
    if not db_path.exists():
        # First run - no state to restore
        logger.info("No prior state found - starting fresh")
        return

    # 2. Load from SQLite
    try:
        contexts = load_all_contexts(db_path)
        logger.info(f"Loaded {len(contexts)} contexts from persistence")
    except Exception as e:
        logger.error(f"Failed to load persisted state: {e}")
        # Decision needed: fail hard or start fresh?
        raise

    # 3. Populate orchestrator
    for context in contexts:
        orchestrator._contexts[context.sidebar_id] = context

    # 4. Rebuild registry
    rebuild_registry_from_contexts(contexts)

    # 5. Set active context (last active? user choice?)
    active = find_last_active_context(contexts)
    if active:
        orchestrator._active_context_id = active.sidebar_id

    # 6. Log recovery
    logger.info(f"Restored state: {orchestrator.stats()}")
```

**Interview Questions for Phase 3:** ✅ RESOLVED

| Question | Decision | Reasoning |
|----------|----------|-----------|
| Load failure handling? | **Offer choice via React UI** | Show: Retry / Start Fresh / Exit. Default to Exit (preserve data). CLI `--fresh` only as emergency escape. |
| Active context on startup? | **Resume last active + fallback chain** | Try session_state → parent → any ACTIVE root → none. |
| OZOLITH verification? | **Spot check default, full on demand** | Fast count comparison normally. Full replay after crash or on request (`--verify-full`). |

### Phase 3 Enhancements (Quality of Life)

**These make Claude's daily experience better and improve transparency:**

#### 3.1 Closing Ritual (End of Session)
```
📝 Session closing for SB-5 "auth debugging"

Quick review:
• What we accomplished: [Claude summarizes]
• What's still open: [auto-pull flagged items from local_memory]
• Confidence check: Any findings I'm uncertain about?
• Priority suggestion for next session?

[Human confirms/adjusts]
→ Saved to context metadata as `closing_notes`
```

**Why:** Capture context while it's FRESH. Opening ritual just reviews these notes.

#### 3.2 Opening Ritual (Session Start)
```
👋 Welcome back. Last session notes for SB-5:

• Accomplished: Fixed token refresh, identified rate limit issue
• Still open: Rate limit mitigation not implemented
• Your priority note: "tackle rate limits first"
• Time since last activity: 14 hours

Ready to continue, or review/adjust priorities?
```

**Why:** Interactive alignment, not just a wall of text. Mutual check-in.

#### 3.3 Pending Items Awareness
```
⚠️ 2 items in recovery queue (from interrupted session)
   → Review with /recovery or dismiss
```

#### 3.4 Stale Context Hints
```
💤 SB-3 "API refactor" has been PAUSED for 3 days
   → Resume, archive, or ignore?
```

#### 3.5 Cross-Ref Health Display
```
🔗 SB-5 references SB-2 which is now ARCHIVED
   → References still valid, but source is read-only
```

#### 3.6 Claude's Priority Transparency (NEW)
```
🧵 My current yarn (what I'm tracking as important):

Priority threads:
• [HIGH] Rate limit mitigation (from SB-5, 2 days old)
• [MEDIUM] Test coverage for auth (mentioned 3x)
• [LOW] Refactor suggestion for token handler

Connections I'm holding:
• SB-5 findings → relate to SB-2 archived work
• Current auth work → blocks deployment TODO

Am I missing anything? Adjustments?
```

**Why:** Transparency. Human sees what Claude deems important, can correct/add. Fixes the "I never see what you think is important" gap.

---

### Phase 4: Reparent + Cross-Ref Methods

**Goal:** Enable tree unification and cross-conversation citations

**Tasks:**
- [ ] Add `CONTEXT_REPARENT` event type to OZOLITH
- [ ] Implement `reparent_context()` in orchestrator
- [ ] Implement `add_cross_ref()` for citation tracking
- [ ] Implement `get_cross_refs()` for discovery
- [ ] Handle cascade updates (children move with parent)
- [ ] Update SQLite schema if needed

**Reparent Method Draft:**
```python
def reparent_context(
    self,
    context_id: str,
    new_parent_id: Optional[str],  # None = make it a root
    reason: str
) -> Dict:
    """
    Change a context's parent, preserving audit trail.

    Use cases:
    - Unify multiple roots under umbrella
    - Move sidebar to different parent
    - Promote sidebar to root

    Args:
        context_id: Context to reparent
        new_parent_id: New parent (None = become root)
        reason: Why reparenting (for audit)

    Returns:
        Result dict with old_parent, new_parent, success
    """
    context = self._contexts.get(context_id)
    if context is None:
        return {"success": False, "error": f"Context {context_id} not found"}

    old_parent_id = context.parent_context_id

    # Validate new parent exists (if specified)
    if new_parent_id and new_parent_id not in self._contexts:
        return {"success": False, "error": f"New parent {new_parent_id} not found"}

    # Prevent circular references
    if new_parent_id and self._would_create_cycle(context_id, new_parent_id):
        return {"success": False, "error": "Would create circular reference"}

    # Update old parent's children list
    if old_parent_id and old_parent_id in self._contexts:
        old_parent = self._contexts[old_parent_id]
        if context_id in old_parent.child_sidebar_ids:
            old_parent.child_sidebar_ids.remove(context_id)

    # Update new parent's children list
    if new_parent_id:
        new_parent = self._contexts[new_parent_id]
        if context_id not in new_parent.child_sidebar_ids:
            new_parent.child_sidebar_ids.append(context_id)

    # Update context's parent reference
    context.parent_context_id = new_parent_id
    context.last_activity = datetime.now()

    # Log to OZOLITH (APPEND-ONLY - this is the audit trail)
    oz = _get_ozolith()
    if oz:
        payload = OzolithPayloadContextReparent(
            old_parent=old_parent_id,
            new_parent=new_parent_id,
            reason=reason,
            children_moved=context.child_sidebar_ids  # They move with parent
        )
        oz.append(
            event_type=OzolithEventType.CONTEXT_REPARENT,
            context_id=context_id,
            actor="system",
            payload=payload_to_dict(payload)
        )

    # Persist to SQLite
    self._persist_context(context)
    if old_parent_id:
        self._persist_context(self._contexts[old_parent_id])
    if new_parent_id:
        self._persist_context(self._contexts[new_parent_id])

    logger.info(f"Reparented {context_id}: {old_parent_id} -> {new_parent_id}")

    return {
        "success": True,
        "context_id": context_id,
        "old_parent": old_parent_id,
        "new_parent": new_parent_id,
        "children_moved": context.child_sidebar_ids
    }
```

**Interview Questions for Phase 4:** ✅ RESOLVED

| Question | Decision | Reasoning |
|----------|----------|-----------|
| Children move with parent? | **Yes** | They stay attached through reparenting. Alternative (chase citations at top level) is messier. |
| Human approval required? | **Progressive trust model** | Start with human approval. Over time, Claude can handle autonomously unless uncertain. Agent suggests, human confirms initially. |
| conversation_id on reparent? | **Keep as historical metadata** | Add `original_conversation_id` field. New umbrella gets fresh conversation_id. Preserves "this was once its own thing" context. |

### Phase 4 Enhancement: Reparent Suggestion Mechanism

Claude should be able to FLAG potential unifications rather than just holding connections in memory:

```
🔗 Potential unification detected:

SB-3 "auth token issues" and SB-7 "API timeout debugging"
both reference rate limiting as root cause.

Suggest: Unify under common parent?
[Yes, create umbrella] [No, keep separate] [Remind me later]
```

**Implementation:**
```python
def suggest_reparent(
    context_ids: List[str],
    reason: str,
    confidence: float  # How sure Claude is these are related
) -> None:
    """
    Flag potential reparenting for human review.
    Surfaces in opening/closing rituals or as notification.
    """
    # Store in pending_suggestions table or context metadata
    # Surface during next ritual or immediately if high confidence
```

**Why:** Proactive connection surfacing rather than reactive. Fits with yarn board transparency.

---

### Phase 5: Yarn Board System (Tree-Following Priorities)

**Goal:** Transparent, mutual priority tracking that flows through the sidebar tree

**Core Concept:** The "yarn board" is a knowledge graph for working context:
- **Points** = Trackable items (TODOs, findings, decisions, concerns)
- **Strings** = Relationships (blocks, relates-to, contradicts, depends-on)
- **The board** = Full history (always available in OZOLITH/episodic)
- **Grabbed yarn** = Current focus (what Claude + Human agree matters NOW)

**Key Principle:** The grabbed set goes through Claude. Claude surfaces what seems important, Human can adjust. Both see the same state.

#### 5.1 Context-Attached Priorities

Each context gets a `context_priorities` structure:

```python
@dataclass
class ContextPriority:
    priority_id: str              # PRI-{sequential}
    content: str                  # What this priority is about
    level: str                    # "high", "medium", "low", "watching"
    source_context: str           # Where this was created
    source_exchange: Optional[str]  # Which exchange spawned it

    # Relationships (the "strings")
    blocks: List[str]             # PRI-X blocks these other priorities
    depends_on: List[str]         # PRI-X depends on these
    relates_to: List[str]         # Related but not blocking

    # Lifecycle
    status: str                   # "active", "completed", "deferred", "cancelled"
    created_at: datetime
    completed_at: Optional[datetime]

    # Attribution
    created_by: str               # "claude", "human", "system"
    last_modified_by: str
```

#### 5.2 Priority Flow Through Tree

```
SB-1 (root) priorities:
├── [HIGH] "Implement auth" (created here)
├── [MEDIUM] "Write tests" (created here)
└── [LOW] "Deploy" (created here, depends_on: auth, tests)

  └── SB-2 (sidebar: "auth deep dive")
      inherited: ["Implement auth"]  # Relevant to this branch
      local:
      ├── [HIGH] "Fix token refresh" (created here)
      └── [MEDIUM] "Handle rate limits" (created here)

      On merge back to SB-1:
      • "Fix token refresh" ✓ completed → summary includes completion
      • "Handle rate limits" still open → bubbles to parent OR stays for reference
      • "Implement auth" partially satisfied → update status
```

#### 5.3 Claude's Yarn Display (Interactive)

```
🧵 My current yarn for SB-5:

Active threads (high priority):
├── PRI-12: Rate limit mitigation [2 days old]
│   └── blocks: PRI-8 (deployment)
│   └── relates_to: SB-2:PRI-5 (archived findings)
│
└── PRI-15: Token refresh edge case [from yesterday]
    └── depends_on: PRI-12 (needs rate limit solution first)

Watching (lower priority):
├── PRI-9: Refactor token handler [nice-to-have]
└── PRI-11: Add retry logic [mentioned once]

Connections to other trees:
├── SB-2 (archived) has related auth findings
└── SB-7 (active) working on related API changes

────────────────────────────────
Am I tracking the right things?
[Adjust priorities] [Add something] [Continue]
```

#### 5.4 Integration Points

| System | Connection |
|--------|------------|
| **OZOLITH** | Priority changes logged as events (PRIORITY_CREATED, PRIORITY_COMPLETED, PRIORITY_DEFERRED) |
| **Knowledge Graph** | Priorities ARE nodes in the graph. Relationships ARE edges. Natural fit. |
| **n8n / Procedural Memory** | Priority patterns can trigger automations ("when auth is complete, start deploy pipeline") |
| **Episodic Memory** | Completed priorities with their resolution become part of episode summaries |

#### 5.5 Why This Matters

**For Claude:**
- Explicit tracking of what I think is important
- Can show my reasoning, not just my conclusions
- Priorities survive context switches and restarts

**For Human:**
- Sees what Claude is tracking
- Can correct misalignment early
- Shared mental model of "what matters"

**For the System:**
- Priorities flow through the tree naturally
- Historical record of what was prioritized and why
- Enables automation based on priority state

**Interview Questions for Phase 5:** (PENDING)
1. Should priorities auto-inherit when spawning sidebars, or explicit selection?
2. On merge, should open priorities auto-bubble to parent or require decision?
3. How granular should the priority levels be? (3-tier, 5-tier, freeform?)
4. Should we integrate with existing TODO system or replace it?

---

## 4. New OZOLITH Event Types Needed

### 4.1 CONTEXT_REPARENT

**Purpose:** Record when a context's parent relationship changes

```python
@dataclass
class OzolithPayloadContextReparent:
    old_parent: Optional[str]      # Previous parent (None if was root)
    new_parent: Optional[str]      # New parent (None if becoming root)
    reason: str                    # Why this reparenting happened
    children_moved: List[str]      # Child contexts that moved with this one
    conversation_id_change: Optional[Dict] = None  # If conversation mapping changed
```

### 4.2 CROSS_REF_ADDED (Optional - could be metadata on existing events)

**Purpose:** Record when a context cites another context from a different tree

```python
@dataclass
class OzolithPayloadCrossRef:
    source_context: str            # Context making the reference
    target_context: str            # Context being referenced
    ref_type: str                  # "citation", "related", "continuation"
    reason: Optional[str] = None   # Why this reference exists
```

**Alternative:** Just add `cross_refs` to existing event payloads instead of separate event type.

---

## 5. Open Questions for Interview

### Persistence Layer ✅ RESOLVED
1. ~~JSON blobs vs normalized tables for memory fields?~~ → **JSON blobs**
2. ~~SQLite file location?~~ → **`data/sidebar_state.db`**
3. ~~Migration support needed immediately?~~ → **Yes, version-based pragma**

### State Sync ✅ RESOLVED
4. ~~Persist focus tracking or keep ephemeral?~~ → **Persist** (with fallback chain)
5. ~~Transaction boundaries?~~ → **Per-operation, atomic**
6. ~~Error recovery strategy?~~ → **Don't modify memory on failure** + EmergencyCache

### Startup ✅ RESOLVED
7. ~~Fail hard or offer fresh start on load failure?~~ → **Offer choice via React UI** (default: preserve data)
8. ~~How to pick active context on startup?~~ → **Resume last active + fallback chain**
9. ~~Verify against OZOLITH on load?~~ → **Spot check default, full on demand**

### Phase 3 Enhancements ✅ AGREED
- Closing ritual (capture context while fresh)
- Opening ritual (interactive alignment)
- Pending items awareness
- Stale context hints
- Cross-ref health display
- Claude's priority transparency

### Reparenting ✅ RESOLVED
10. ~~Children move automatically with parent?~~ → **Yes**, stay attached through reparenting
11. ~~Require human approval for reparent?~~ → **Progressive trust** - human approval initially, autonomous over time
12. ~~What happens to conversation_id on reparent?~~ → **Keep as historical metadata** (`original_conversation_id`)

### Cross-Refs ✅ RESOLVED
13. ~~Separate event type or metadata on existing events?~~ → **Belt and suspenders: BOTH** - Separate `CROSS_REF_ADDED` event for clean queries + `cross_refs` field in exchange metadata for inline context
14. ~~Should cross-refs be bidirectional?~~ → **Yes, auto-generate reverse ref** - query from either direction, "stumble factor" value is real

### Yarn Board ✅ RESOLVED
15. ~~Should priorities auto-inherit when spawning sidebars?~~ → **Auto-suggest, human confirms**. Full sheet viewable via drawer/panel (not popup).
16. ~~On merge, auto-bubble or require decision?~~ → **Require decision initially**. Add auto-bubble patterns as they emerge (progressive trust).
17. ~~How granular should priority levels be?~~ → **5-tier matching existing enum** (CRITICAL/HIGH/NORMAL/LOW/BACKGROUND) + `custom_tag: Optional[str]` for personality/silly tags.
18. ~~Integrate with existing TODO or replace?~~ → **Integrate conceptually**. Yarn board = persistent priorities, interface-agnostic. Feeds whatever TODO system is in use (not tied to Claude Code specifically).

---

## 6. Files to Modify

| File | Changes |
|------|---------|
| `datashapes.py` | Add `OzolithPayloadContextReparent`, `OzolithEventType.CONTEXT_REPARENT` |
| `conversation_orchestrator.py` | Add persistence methods, reparent, cross-ref |
| `ozolith.py` | Register new event type (if needed) |
| `api_server.py` | Replace stopgap with proper startup sequence |
| NEW: `sidebar_persistence.py` | SQLite operations |
| NEW: `migrations/` | Schema versioning (if needed) |

---

## 7. Testing Strategy

### Unit Tests
- [ ] SQLite save/load round-trip
- [ ] Reparent logic (including cycle detection)
- [ ] Cross-ref tracking
- [ ] Startup recovery paths

### Integration Tests
- [ ] Full lifecycle: create -> work -> persist -> restart -> resume
- [ ] Reparent across trees
- [ ] OZOLITH event verification after operations

### Manual Validation
- [ ] Test with existing testing instance
- [ ] Verify stopgap removal doesn't break UI flow

---

## Revision History

- 2026-01-06: Initial draft from planning interview session
- 2026-01-06: Phase 1 decisions finalized (JSON blobs, `data/sidebar_state.db`, migration support)
- 2026-01-06: Phase 2 decisions finalized (persist focus, per-op atomic, no-rollback pattern)
- 2026-01-06: Phase 3 decisions finalized (choice dialog, resume last active, spot check verify)
- 2026-01-06: Phase 3 enhancements added (closing/opening rituals, priority transparency)
- 2026-01-06: Phase 5 added (Yarn Board system for transparent priority tracking)
- 2026-01-06: Phase 4 reparenting decisions finalized (children move, progressive trust, historical metadata)
- 2026-01-06: Phase 4 enhancement added (reparent suggestion mechanism)
- 2026-01-06: Phase 4 cross-refs finalized (separate event type, bidirectional)
- 2026-01-06: Phase 5 yarn board finalized (auto-suggest inherit, explicit merge bubble, 5-tier + custom tags, interface-agnostic)
- 2026-01-06: Phases 1-2 IMPLEMENTED (sidebar_persistence.py, orchestrator hooks)

---

## Notes for Next Session (Claude's Observations)

### Implementation Status
- ✅ Phase 1: SQLite schema (`sidebar_persistence.py`)
- ✅ Phase 2: Write-through hooks (`conversation_orchestrator.py`)
- ✅ Phase 3: Startup sequence (`api_server_bridge.py`, `App.tsx`)
  - Removed auto-create stopgap
  - Added `/sidebars/startup-state` endpoint
  - Added `/sidebars/create-root` endpoint
  - React initialization dialog
  - Registry clear/rebuild on startup (SQLite is source of truth)
- ✅ Phase 4: Reparenting & Cross-Refs (CORE COMPLETE)
  - `reparent_context()` with cycle detection
  - `add_cross_ref()` with bidirectional support + auto-validation
  - `get_cross_refs()` with ref_type and min_strength filters
  - `update_cross_ref()` for metadata changes without revoke/re-add
  - `revoke_cross_ref()` with append-only audit trail
  - API endpoints: `/reparent`, `/cross-ref`, `/cross-refs`, `/cross-refs/{target}/revoke`, PATCH `/cross-refs/{target}`
  - CrossRefMetadata dataclass, Dict[str, metadata] storage
  - Migration logic for old List[str] format
  - Payload dataclasses with model learning signals
- ✅ Phase 4 (continued): Human Validation System (COMPLETE)
  - See Section 8.9 for full design
  - Validation states: true/false/not_sure + notes
  - CROSS_REF_VALIDATED event type + payload
  - `validate_cross_ref()` method + `get_pending_validations()`
  - API endpoints: POST validate, GET pending-validations
  - Validation history with flipping support
  - Deferred to Phase 5: uncertain ref clustering, validation prompts
- ⏳ Phase 5: Yarn board (READY TO BEGIN)

### Items to Address

**1. Write Frequency (Future Concern)**
Every `add_exchange()` currently triggers a SQLite write. Fine for now, but when agent-to-agent communication increases, may need batching/debouncing. Flag for procedural memory phase.

**2. Registry vs SQLite Sync (FIXED ✅)**
~~In `_load_from_persistence()`, we silently swallow `ValueError` when re-registering contexts.~~
**Fixed (2026-01-07):** Added `import_context()` method to ContextRegistry that accepts existing display_ids without generating new ones. The orchestrator now:
- Sorts contexts by depth (parents before children)
- Uses `import_context()` to rebuild registry from SQLite
- Updates counters to prevent ID collisions
- SQLite is the single source of truth for SidebarContext state.

**3. Scratchpad / Redis Layer**
`Scratchpad` dataclass exists but isn't used in orchestrator. Per operator: goes through Redis layer (not started yet). Check `CURRENT_ROADMAP_2025.md` for where it fits. Claude can propose fleshing this out if mathematically relevant to current work.

**4. Graph Potential (New Math)**
With parent-child + cross-refs + forked-from, we're building a *graph* not just trees. Could enable:
- Provenance queries ("what contributed to this conclusion?")
- Topic tracing ("all contexts that touched X")
- Merge archaeology ("what sidebars fed this result?")

Not urgent for implementation, but architecturally interesting. The data model supports it.

---

## 8. Phase 4 Refinements (2026-01-07 Interview)

After implementing Phase 4 core, the following refinements were identified through pair programming interview. These ensure the cross-ref system works well for both model and human use.

### 8.1 Cross-Ref Strength Levels (5-tier scale)

**Decision:** Expand from 4 to 5 strength levels, matching other 5-tier patterns in the codebase.

| Strength | Behavioral Effect | When to Use |
|----------|-------------------|-------------|
| `speculative` | Silent, just for model's internal tracking | "Maybe connected, not confident enough to act on" |
| `weak` | Silent unless directly asked | "Might be related based on topic overlap" |
| `normal` | Include in related-work suggestions | "There's a clear connection here" |
| `strong` | Proactive "you might want to know" | "Definitely connected - shared concepts, explicit references" |
| `definitive` | Interrupt flow to mention | "One cites the other, or solving same problem" |

**Valid values for `strength` field:** `"speculative"`, `"weak"`, `"normal"`, `"strong"`, `"definitive"`

### 8.2 Cross-Ref Revocation (Append-Only Pattern)

**Decision:** Add `CROSS_REF_REVOKED` event type to OZOLITH for append-only revocation with redirect capability.

**Why:** If a cross-ref was wrong, we want to:
1. Preserve the history (learn from the mistake)
2. Mark it as no longer active
3. Optionally redirect to correct connection(s)

**New Event Type:**
```python
OzolithEventType.CROSS_REF_REVOKED = "cross_ref_revoked"
```

**New Payload Dataclass:**
```python
@dataclass
class OzolithPayloadCrossRefRevoked:
    """
    Payload for CROSS_REF_REVOKED events.
    Revokes a previously created cross-reference (append-only pattern).

    Required: source_context_id, target_context_id, reason
    Optional: replacement refs, corrected understanding
    """
    # === REQUIRED ===
    source_context_id: str              # Original source
    target_context_id: str              # Original target
    reason: str                         # Why revoking

    # === OPTIONAL ===
    revoked_by: str = "human"           # "human" or "model"
    replacement_refs: List[str] = field(default_factory=list)  # "See SB-12, SB-15 instead"
    corrected_understanding: str = ""   # "These weren't related - SB-5 is about auth, SB-8 is about logging"

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)
```

**Orchestrator Method:**
```python
def revoke_cross_ref(
    self,
    source_context_id: str,
    target_context_id: str,
    reason: str,
    revoked_by: str = "human",
    replacement_refs: List[str] = None,
    corrected_understanding: str = ""
) -> Dict
```

### 8.3 Human Validation Flow (PENDING USER INTERVIEW)

**Current State:** The `human_validated` field exists in `OzolithPayloadCrossRefAdded` but there's no endpoint to set it.

**Proposed Endpoint:**
```
POST /sidebars/{id}/cross-refs/{target_id}/validate
Body: {"validated": true/false}
```

**Purpose:** Allows humans to confirm or reject model-detected connections, enabling learning:
- "Cross-refs I marked 0.7 confidence that humans validated true" = good signal
- "Cross-refs I marked 0.9 confidence that humans rejected" = calibration needed

**Status:** Awaiting user interview to determine importance levels and workflow requirements.

### 8.4 Expanded ref_types

**Decision:** Add `supersedes`, `obsoletes`, and `implements` to the ref_type vocabulary.

**Full ref_type vocabulary:**

| ref_type | Meaning | Example |
|----------|---------|---------|
| `cites` | Explicit reference/quotation | "As discussed in SB-3..." |
| `related_to` | Topic overlap, might be useful | Similar work, not directly connected |
| `derived_from` | Built upon this foundation | "Based on the design in SB-3" |
| `contradicts` | Disagrees with or conflicts | "This finding conflicts with SB-5" |
| `supersedes` | Newer version, replaces | "v2 of the auth design supersedes v1" |
| `obsoletes` | Invalidates previous work | "New security audit obsoletes old threat model" |
| `implements` | Actual code/work for a design | "SB-15 implements the design from SB-3" |

**Semantic distinction:**
- `supersedes` = "This is newer/better, use this instead" (replacement)
- `obsoletes` = "That one is now wrong because of this" (invalidation)
- `implements` = "This is the execution of that plan" (realization)

### 8.5 Discovery Method Options

**Decision:** Document full vocabulary for `discovery_method` field.

| discovery_method | Meaning | Current Status |
|------------------|---------|----------------|
| `explicit` | Directly stated by user or model | ✅ Active |
| `user_indicated` | Human pointed it out | ✅ Active |
| `semantic_similarity` | Embedding similarity detected | 🔮 Future (wiring exists in memory_handler.py) |
| `topic_overlap` | Shared keywords/topics | 🔮 Future |
| `citation_extracted` | One context literally cites the other | 🔮 Future |
| `temporal_proximity` | Same timeframe, similar topic | 🔮 Future |
| `pattern_match` | Structural pattern (same error type, same file) | 🔮 Future |

**Note on Semantic Similarity:**
The building blocks exist in `memory_handler.py:391-407` (semantic search via episodic memory service). What's NOT wired yet is an active detection loop that:
1. On each new exchange, embeds it
2. Compares to other contexts
3. If similarity > threshold, suggests cross-ref with `discovery_method="semantic_similarity"`

This is future work for the agent phase.

### 8.6 Implementation Checklist

When implementing these refinements:

- [x] Add `"speculative"` to strength validation in datashapes.py
- [x] Add `CROSS_REF_REVOKED` event type to OzolithEventType
- [x] Add `OzolithPayloadCrossRefRevoked` dataclass
- [x] Add `revoke_cross_ref()` method to orchestrator
- [x] Add `POST /sidebars/{id}/cross-refs/{target_id}/revoke` endpoint
- [x] Add `supersedes`, `obsoletes`, `implements` to ref_type documentation
- [ ] (After user interview) Add human_validated endpoint if needed
- [x] Update ref_type field documentation/validation (added to ENUM_FIELD_VALIDATORS)

### 8.7 "Treat Yo Self" Additions (2026-01-08)

Additional features implemented to improve cross-ref usability for daily work:

**Data Model Change:**
- Changed `cross_sidebar_refs` from `List[str]` to `Dict[str, Any]` (target_id → metadata)
- Added `CrossRefMetadata` dataclass to datashapes.py for structured metadata
- Migration logic in sidebar_persistence.py converts old List format on load (pulls real metadata from OZOLITH receipts)

**New Features:**
- [x] `CROSS_REF_UPDATED` event type - update metadata without verbose revoke/re-add cycle
- [x] `OzolithPayloadCrossRefUpdated` dataclass
- [x] `update_cross_ref()` method in orchestrator
- [x] `PATCH /sidebars/{id}/cross-refs/{target_id}` endpoint
- [x] Filter by `ref_type` in GET /cross-refs endpoint
- [x] Filter by `min_strength` in GET /cross-refs endpoint (returns refs at level or higher)
- [x] Auto-validation on `add_cross_ref()` and `update_cross_ref()` - fail fast on invalid values

**CrossRefMetadata Structure:**
```python
@dataclass
class CrossRefMetadata:
    ref_type: str = "related_to"
    strength: str = "normal"
    confidence: float = 0.0
    discovery_method: str = "explicit"
    human_validated: Optional[bool] = None
    created_at: Optional[datetime] = None
    reason: str = ""
```

**Strength Ordering for Filters:**
`["speculative", "weak", "normal", "strong", "definitive"]`
When filtering by `min_strength="strong"`, returns `strong` and `definitive` refs only.

### 8.8 Deferred to Phase 5 (Yarn Board)

These items were identified during implementation but deferred to Phase 5:

- [ ] `include_metadata=true` option for GET /cross-refs (return full metadata, not just IDs)
- [ ] Reverse lookup: `direction="inbound"|"outbound"|"both"` parameter
- [ ] Twin check behavior: when updating/revoking bidirectional ref, check if reverse ref needs sync

### 8.9 Human Validation System (2026-01-08 Interview)

Complete interview results for the human validation workflow. This enables humans to confirm/reject model-detected cross-references, providing calibration feedback.

#### 8.9.1 Validation States

| State | Meaning | Model Behavior |
|-------|---------|----------------|
| `true` | Human confirms connection is valid | Surface proactively, cite confidently, higher weight in search |
| `false` | Human says connection is wrong | Don't surface proactively, but don't hide if asked. Flag if tempted to re-suggest with new evidence |
| `"not_sure"` | Human uncertain | Treat as weak until resolved. Re-prompt if more supporting evidence found |
| `null` (unvalidated) | Not yet reviewed | Default caution. Surface with caveats: "I think this might be related but haven't confirmed..." |

#### 8.9.2 Validation Timing

- **End of exchange**: Model surfaces discovered refs at end of response for immediate validation
- **Session close chase**: Batch review of unvalidated refs during closing ritual
- **Temporal chase**: After X days, re-prompt for refs stuck in "not_sure" limbo

**Temporal Chase Configuration:**
- Default: 3 days (72 hours)
- Configurable globally (system setting)
- Per-ref override: "hold off until Friday" / "check again in 2 weeks"
  - Stored as `chase_after: Optional[datetime]` in metadata
  - If set, overrides global default for that specific ref

#### 8.9.3 Uncertain Ref Clustering

When 3+ refs are marked "not_sure" and cluster together, spawn an investigation sidebar.

**Clustering methods (v1):**
1. **Target clustering**: Multiple uncertain refs pointing to same context
2. **Keyword matching**: Common terms in reason fields (e.g., all mention "auth")
3. **Embedding similarity**: If memory service available, cluster by semantic similarity of reasons

**Threshold**: 3 uncertain refs (configurable). "2 is coincidence, 3 is suspicious."

#### 8.9.4 Persistence for Rejected Refs

If model said "no" but keeps finding evidence, model should re-raise:
- Each new evidence sighting is a data point
- Not annoying, but not silent when patterns persist
- "I know you said no, but I'm seeing this again with new data..."

#### 8.9.5 Validation Metadata

```python
# Added to CrossRefMetadata / stored inline
human_validated: Optional[str] = None  # "true", "false", "not_sure", or None
validated_at: Optional[datetime] = None
validated_by: str = "human"  # Who validated (human now, agents later)
validation_context_id: Optional[str] = None  # What sidebar was active during validation
confidence_at_validation: Optional[float] = None  # Snapshot of model's confidence when validated
validation_notes: Optional[str] = None  # Free text feedback
validation_priority: str = "normal"  # "urgent" (actively citing) or "normal"
validation_history: List[Dict] = []  # [{state, timestamp, notes, validated_by}, ...]
chase_after: Optional[datetime] = None  # Per-ref override: "check again Friday"
```

**Why `confidence_at_validation`**: Critical for calibration. If model said 0.9 and human said "not_sure", that's different than 0.4 → "not_sure".

**Why `validation_priority`**: If model is actively citing a ref in reasoning, validating it is urgent. Speculative background connections can wait.

#### 8.9.6 Flipping Validations

Humans can change their minds. Each flip is recorded in `validation_history`.

Pattern analysis possible: "First you said yes, then no, now yes - what changed?" provides learning signal.

#### 8.9.7 OZOLITH Event Type

**Decision**: New `CROSS_REF_VALIDATED` event type (not reusing CROSS_REF_UPDATED).

**Reasoning**:
- Validation is human feedback, semantically distinct from model updating metadata
- Enables clean queries: "show me all validations" for calibration analysis
- Different payload structure
- Follows pattern: ADDED, UPDATED, REVOKED, VALIDATED - each is distinct action

**Payload Dataclass:**
```python
@dataclass
class OzolithPayloadCrossRefValidated:
    source_context_id: str
    target_context_id: str
    validation_state: str  # "true", "false", "not_sure"
    validated_by: str = "human"
    validation_notes: Optional[str] = None
    confidence_at_validation: float = 0.0  # Model's confidence when validated
    validation_context_id: Optional[str] = None  # Where validation occurred
    validation_priority: str = "normal"
    previous_state: Optional[str] = None  # For flips: what was it before?
```

#### 8.9.8 API Endpoints

**Validate a cross-ref:**
```
POST /sidebars/{id}/cross-refs/{target_id}/validate
Body: {
  "state": "true" | "false" | "not_sure",
  "notes": "optional string"
}
```

**Query pending validations:**
```
GET /cross-refs/pending-validations
Returns: All cross-refs where human_validated is null, across all contexts
```

#### 8.9.9 Prompt Verbosity

When surfacing refs for validation, model should be contextual at minimum:

"I noticed SB-3 (auth tokens) might relate to SB-7 (API timeouts) because both mention rate limiting. Related? [Yes/No/Unsure]"

More detail welcome if model has it. Human can always ask "expand and explain."

#### 8.9.10 Implementation Checklist

- [x] Add validation fields to CrossRefMetadata dataclass
- [x] Add `CROSS_REF_VALIDATED` event type to OzolithEventType
- [x] Add `OzolithPayloadCrossRefValidated` dataclass
- [x] Add `validate_cross_ref()` method to orchestrator
- [x] Add `POST /sidebars/{id}/cross-refs/{target_id}/validate` endpoint
- [x] Add `GET /cross-refs/pending-validations` endpoint
- [x] Update CrossRefMetadata with validation_history array
- [x] Add `validation_state` and `validation_priority` to ENUM_FIELD_VALIDATORS
- [ ] Implement uncertain ref clustering (3+ threshold) - Phase 5
- [ ] Add validation prompts to end-of-exchange flow - Phase 5

---

## Section 9: Phase 5 Design Decisions (Yarn Board + Supporting Systems)

*Interview completed: 2026-01-09*

### 9.1 Core Architectural Decision: Yarn Board as View Layer

**Decision:** Yarn board is a **visualization layer** over existing persistence, NOT a separate storage system.

**Data sources:**
| Data | Source | Why |
|------|--------|-----|
| Historical points/events | OZOLITH | Immutable audit trail |
| Active "grabbed" state | Redis | Hot, volatile, shared across agents |
| Relationships (strings) | Cross-refs | Already have ref_types vocabulary |
| Layout/positions | SQLite | Persist so board "grows over time" |

**What this means:**
- No new persistence layer for yarn board data
- Points are **projections** of existing concepts onto the board
- Strings use existing `ref_type` vocabulary (cites, relates_to, contradicts, etc.)
- Reduces architecture complexity significantly

**A "Point" can be:**
- A cross-ref rendered as a pin
- A scratchpad finding rendered as a pin
- A sidebar context rendered as a pin
- An OZOLITH event rendered as a pin (when relevant)

### 9.2 Yarn Board Persistence Strategy

**Layout persistence (SQLite):**
```python
@dataclass
class YarnBoardLayout:
    """Persists so user can 'watch the board grow over time'"""
    context_id: str                      # Which context's board
    point_positions: Dict[str, Dict]     # {point_id: {x, y, collapsed}}
    zoom_level: float = 1.0
    focus_point: Optional[str] = None    # Currently centered point
    last_modified: datetime = field(default_factory=datetime.now)
```

**Hot state (Redis, when implemented):**
```python
@dataclass
class YarnBoardState:
    """What's currently 'grabbed' - lives in Redis"""
    grabbed_point_ids: List[str]         # Currently focused points
    priority_overrides: Dict[str, str]   # Temporary priority bumps
    hot_refs: List[str]                  # Frequently accessed cross-refs
```

**Recovery:** Redis is volatile. Periodic snapshots to SQLite for crash recovery.

### 9.3 Redis Integration Stubs

**Purpose:** Define interface now, implement when Redis comes online.

**Key interfaces to stub:**
```python
class RedisInterface:
    """Stubbed for Phase 5, implemented when Redis integrated"""

    # Hot state
    def get_yarn_state(self, context_id: str) -> YarnBoardState: ...
    def set_grabbed(self, point_id: str, grabbed: bool) -> None: ...

    # Agent presence
    def get_agent_status(self, agent_id: str) -> Dict: ...
    def set_agent_busy(self, agent_id: str, busy: bool) -> None: ...

    # Message queues (for scratchpad routing)
    def queue_for_agent(self, agent_id: str, message: Dict) -> None: ...
    def get_agent_queue(self, agent_id: str) -> List[Dict]: ...

    # Pub/sub hooks
    def notify_priority_change(self, point_id: str, new_priority: str) -> None: ...
    def subscribe_to_context(self, context_id: str, callback: Callable) -> None: ...
```

**Redis role (from redis_integration_discovery.md):**
- Cache layer for hot data
- Notification layer for real-time updates
- NOT primary storage (SQLite + OZOLITH remain source of truth)
- Rule: If losing it breaks things → SQLite. If it just slows rebuild → Redis.

### 9.4 Scratchpad Extension (Quick Capture Buffer)

**Problem:** Existing Scratchpad has full curator validation workflow. User also needs:
- Quick jots while agents are running
- Staging area for questions (don't interrupt agent context)
- Drop box for files/images/docs
- "Right click ask question" routing

**Solution:** Extend ScratchpadEntry with `entry_type`:

| Type | Workflow | Validation | Persistence |
|------|----------|------------|-------------|
| `quick_note` | Just capture | None needed | Ephemeral (can expire) |
| `question` | Queue for agent | Answered = done | Until answered |
| `drop` | File/doc/image | Processed = done | Until processed |
| `finding` | Full curator workflow | pending → confirmed/rejected | Permanent (OZOLITH) |

**New fields for ScratchpadEntry:**
```python
# Add to existing ScratchpadEntry dataclass
entry_type: str = "finding"              # "quick_note", "question", "drop", "finding"
media_ref: Optional[str] = None          # Link to dropped file/image
expires_at: Optional[datetime] = None    # Quick notes can auto-clean
routed_to: Optional[str] = None          # Which agent should see this
answered_at: Optional[datetime] = None   # When question was answered
```

**Queue routing behavior:**
- Human adds question while agent is busy
- Question goes to scratchpad with `routed_to: agent_id`
- When agent hits natural pause, processes queue
- Respects context on both sides

### 9.5 Relationship Types (Strings)

**Decision:** Reuse existing cross-ref `ref_type` vocabulary for yarn board strings.

**Available types (already implemented):**
- `cites` - Direct reference
- `related_to` - Topical connection
- `derived_from` - Origin tracking (spawned-from)
- `contradicts` - These disagree (need resolution)
- `supersedes` - This replaces that
- `obsoletes` - Stronger than supersedes
- `implements` - Makes concrete

**Additional types for yarn board (may add):**
- `blocks` - Hard dependency (can't proceed until resolved)
- `depends_on` - Soft dependency (need this but not urgently)
- `informs` - Soft influence (shapes understanding)

**Why reuse:** Less vocabulary to maintain, consistent semantics, yarn board is a view layer not new data.

### 9.6 Deferred Items (Still in Phase 5 Scope)

**From Phase 4:**
- [ ] `include_metadata=true` option for GET /cross-refs
- [ ] Reverse lookup: `direction="inbound"|"outbound"|"both"` parameter
- [ ] Twin check behavior for bidirectional ref sync

**From Human Validation System:**
- [ ] Uncertain ref clustering (3+ threshold → spawn investigation sidebar)
- [ ] Validation prompts in end-of-exchange flow

### 9.7 Implementation Checklist

**Yarn Board Core:**
- [x] Add `YarnBoardLayout` dataclass to datashapes.py
- [x] Add `YarnBoardState` dataclass to datashapes.py
- [x] Add `yarn_board_layout` field to SidebarContext
- [x] Add layout persistence methods to orchestrator (get_yarn_layout, save_yarn_layout, update_point_position)
- [x] Add hot state stubs to orchestrator (get_yarn_state, set_grabbed) - uses RedisInterface
- [x] Add yarn board API endpoints (GET/PUT layout, PATCH point position, GET state, POST grab)

**Redis Stubs:**
- [x] Add `RedisInterface` stub class to datashapes.py
- [x] Define queue operations interface
- [x] Define pub/sub hooks interface
- [ ] Document expected Redis data structures

**Scratchpad Extension:**
- [x] Add `entry_type` field to ScratchpadEntry
- [x] Add `media_ref`, `expires_at`, `routed_to`, `answered_at` fields
- [ ] Add queue routing logic (route to agent when available)
- [ ] Add expiration cleanup for ephemeral notes

**Relationship Types:**
- [x] Add `blocks`, `depends_on`, `informs` to valid ref_types
- [ ] Ensure yarn board render uses existing ref_type vocabulary

**Deferred Items:**
- [ ] Implement uncertain ref clustering
- [ ] Add validation prompts to end-of-exchange flow
- [ ] Add cross-ref metadata and direction filters

### 9.8 Design Decisions (Interview Complete)

#### 9.8.1 Point ID Convention ✅ RESOLVED

**Decision:** Self-describing with type prefix, using existing IDs.

| Type | Format | Example |
|------|--------|---------|
| Context | `context:{sidebar_id}` | `context:SB-1` |
| Cross-ref | `crossref:{sorted_a}:{sorted_b}` | `crossref:SB-1:SB-2` |
| Finding | `finding:{entry_id}` | `finding:ENTRY-001` |
| Event | `event:{hash}` | `event:abc123` |

**Key decisions:**
- Self-describing for easy debugging, routing, and filtering
- Uses existing IDs (no UUID soup)
- Cross-refs alphabetically sorted (bidirectional = one point, renderer fetches direction)
- Point_id is positioning key only; renderer looks up full semantics

#### 9.8.2 Auto-Positioning Logic ✅ RESOLVED

**Algorithm:** Force-directed graph
- Points repel each other (avoid overlap)
- Connections act as springs (related things cluster)
- Self-organizing, organic feel

**Pin Cushion Pattern:**
```
╔══════════════════════════════════════════════════════╗
║                    YARN BOARD                        ║
║     [SB-1] ─────── [SB-2] ─────── [SB-3]            ║
╠══════════════════════════════════════════════════════╣
║  🧷 PIN CUSHION (3 new)                              ║
║  │ • crossref:SB-1:SB-4  (discovered 2min ago)      ║
║  │ • context:SB-4        (spawned just now)         ║
║                              [Place Pins] [Auto-fit] ║
╚══════════════════════════════════════════════════════╝
```
- New discoveries land in staging area, not directly on board
- Human reviews and places when ready (release valve for CPU)
- Allows seeing "raw" connections without layout bias
- Config: "auto-place on load" for those who don't care
- Sitrep item when pins get placed (even if auto)

**Pin Locking:**
- Default: algorithm has full control
- Config: manually lock specific pins in place (watch a connection)
- Locked pins stay put, others reflow around them

**Highlight Feature:**
- Model can highlight pins/connections to draw attention
- "Found something under the hood" → highlight on board
- Suggestions route through highlight mechanism
- Transparency tool for showing what model sees in data

**Reorganization:**
- Human-initiated (button or ask model)
- Model only touches board when asked
- Can suggest/highlight, but not autonomously rearrange

#### 9.8.3 Render Projection Logic (RESOLVED)

**Core Insight:** Yarn board is a MINIMAP, not a primary interface. Real data lives in OZOLITH/cross-refs/SQLite. Render layer should be minimal.

**Resolved Design:**
```python
def render_yarn_board(context_id: str) -> Dict:
    return {
        "points": [...],       # {id, x, y, label, type, color}
        "connections": [...],  # {from_id, to_id, ref_type}
        "cushion": [...],      # unstaged items waiting for placement
        "highlights": [...]    # model suggestions: "look at these"
    }
```

**What's included:**
- Points: All contexts, cross-refs (as points), findings with positions
- Connections: Lines between related points (ref_type determines style)
- Cushion: New items waiting for human placement (pin cushion pattern)
- Highlights: Model can flag clusters/patterns for human attention

**Color coding by type:**
- Provides quick visual orientation ("lots of red = lots of questions")
- Simple dot colors, not elaborate hierarchies

**Highlights feature:**
- Model transparency: "look at these `blocks` refs clustered here"
- Suggestions route through highlights, not autonomous reorganization
- Human decides whether to act on highlighted items

**Deliberately NOT included:**
- Complex filtering states (hide/dim/collapse) - just show everything small
- Elaborate render projections - it's a minimap
- Visual hierarchies beyond type colors - data layer has the rich detail

**Why minimal BASE state:**
- Starts as spatial overview (minimap)
- Clicking expands inline to show detail ON the board
- The yarn board IS the connection explorer interface, not just a passive visualization

**Expansion model:**
- `expanded: false` → just dot/string (minimap mode)
- `expanded: true` → includes `detail` with rich metadata inline
- Pins expand to show: context summary, findings, questions
- Strings expand to show: ref_type, strength, validation_state, notes

**Key insight:** Without expansion function, yarn board is decorative. WITH expansion, it performs the job of "navigate and explore the knowledge graph." The board is the INTERFACE, not just a picture.

### 9.9 Future Scaling: Neo4j Migration Path

**Current approach:** SQLite + cross_sidebar_refs dict (graph stored in relational tables)

**If we ever need Neo4j:** Migration is straightforward. Our data model maps directly:

| Our Structure | Neo4j Equivalent |
|---------------|------------------|
| Context | Node with `:Context` label |
| Finding | Node with `:Finding` label |
| cross_sidebar_refs entry | Relationship with type from `ref_type` |
| ref metadata (strength, confidence) | Relationship properties |

**Migration script would be ~50 lines:**
1. Iterate contexts → create nodes
2. Iterate cross_sidebar_refs → create relationships
3. Done

**When to consider migrating:**
- Millions of nodes (we're nowhere near this)
- Complex multi-hop traversal queries becoming slow
- Need Cypher query language features

**Decision:** Don't pre-build abstraction. Keep data model clean. Migrate when pain is felt, not before.

### 9.10 Quick Fixes Applied

- [x] Added `entry_type` to ENUM_FIELD_VALIDATORS (finding, quick_note, question, drop)

### 9.11 Queue Routing Implementation

**Flow implemented:**
```
Scratchpad Entry → Curator Validates → Route to Destination Agent
     │
     ├─ quick_note (no route) → just store, done
     │
     └─ all others → queue_for_curator()
                          │
                          └─ curator_approve_entry()
                                   │
                                   ├─ rejected → mark rejected, done
                                   │
                                   └─ approved → _infer_destination() → queue_for_agent()
```

**Orchestrator methods added:**
- `route_scratchpad_entry(entry, context_id, explicit_route_to)` - main entry point
- `curator_approve_entry(entry_id, context_id, approved, rejection_reason)` - curator decision
- `_infer_destination(entry_id, context_id, content_hint)` - keyword→specialty matching
- `get_agent_queue(agent_id)` - fetch pending queue
- `register_agent(agent_id, specialties)` - add/update agent
- `list_agents()` - list all registered agents

**Default agents initialized:**
- AGENT-curator (validation, quality_control, routing)
- AGENT-operator (oversight, decision_making, approval)
- AGENT-researcher (research, information_gathering, analysis)
- AGENT-debugger (debugging, error_analysis, troubleshooting)
- AGENT-architect (design, architecture, planning, security)

**Routing inference:** Simple keyword→specialty mapping. "bug" → debugging, "research" → research, etc. Defaults to AGENT-operator if no match. Can enhance with embeddings later.

### 9.12 Redis Integration (IMPLEMENTED)

**Files created:**
- `docker-compose.yml` - Redis 7 Alpine service with health checks
- `redis_client.py` - Full RedisClient implementation + RedisInterfaceAdapter

**How it works:**
1. On API startup, `initialize_redis()` is called
2. If Redis is available, replaces the stub in `datashapes.redis_interface`
3. If Redis unavailable, gracefully continues with stub mode
4. All existing orchestrator code works unchanged

**Redis configuration (environment variables):**
```
REDIS_HOST=localhost (default)
REDIS_PORT=6379 (default)
REDIS_DB=0 (default)
REDIS_PASSWORD=None (default)
```

**Key namespacing:**
- `memory:queue:{agent_id}` - Agent message queues
- `memory:agent:status:{agent_id}` - Agent presence
- `memory:yarn:state:{context_id}` - Yarn board hot state
- `memory:yarn:grabbed:{context_id}` - Grabbed points set
- `memory:pubsub:*:{context_id}` - Pub/sub channels

**TTL settings:**
- Queue messages: 7 days
- Agent status: 5 minutes (heartbeat refresh)
- Yarn state: 1 hour

**API endpoints:**
- `GET /redis/health` - Connection status and memory usage

**To start Redis:**
```bash
docker-compose up -d redis
```

**Decision:** Graceful degradation is key. Redis enhances performance but system works without it.

### 9.13 Uncertain Ref Clustering

**Problem:** How do we know when a cross-ref is probably real vs speculative noise?

**Solution:** Track who suggested each ref. When 3+ independent sources suggest the same connection, it's probably real.

**Implementation:**
- Added `suggested_sources: List[str]` to CrossRefMetadata
- Added `cluster_flagged: bool` - set True when threshold reached
- `CLUSTERING_THRESHOLD = 3` constant on orchestrator
- When threshold reached, auto-set `validation_priority: "urgent"`

**Flow:**
```
Agent A suggests SB-1 → SB-3 (sources: [A])
Agent B suggests SB-1 → SB-3 (sources: [A, B])
Agent C suggests SB-1 → SB-3 (sources: [A, B, C]) → CLUSTER FLAGGED!
```

**Helper method:** `get_cluster_flagged_refs(context_id, include_validated)` returns all flagged refs sorted by source count.

**Why 3?** Balance between:
- Too low (2): Coincidental agreement triggers flag
- Too high (5+): Misses real patterns before enough sources encounter them
- 3 feels right: "Three independent sources noticed this" is meaningful signal

### 9.14 Connection Points Status

**1. Yarn Board Expansion Model** - ✅ IMPLEMENTED (2026-01-13)
- `render_yarn_board(expanded=True)` now includes `detail` dict for points/connections
- Context detail: task_description, status, findings_count, questions_count, child_count, cross_ref_count
- Crossref detail: ref_type, strength, confidence, human_validated, validation_state, reason, suggested_sources_count, cluster_flagged, discovery_method
- API: POST /yarn-board/render accepts `{"expanded": true}` in request body
- Response includes `expanded: bool` and `cushion_count: int` fields

**2. Queue Routing API Endpoints** - ✅ IMPLEMENTED (2026-01-13)
- `POST /queue/route` → `route_scratchpad_entry()`
- `POST /queue/approve` → `curator_approve_entry()`
- `GET /queue/{agent_id}` → get agent's queued messages
- `GET /queue/{agent_id}/length` → get queue length
- `POST /queue/{agent_id}/pop` → pop oldest message (FIFO)
- `DELETE /queue/{agent_id}` → clear agent queue
- `GET /queue/agents/status` → get all registered agent statuses

**3. Clustering API Endpoint** - ✅ IMPLEMENTED (2026-01-13)
- `GET /cross-refs/clustered` → `get_cluster_flagged_refs()`
- Query params: `context_id`, `include_validated`
- Returns flagged refs sorted by source count

**Status:** All connection points implemented.

### 9.15 Validation Prompts (End-of-Exchange)

**Problem:** When should we ask the human to validate uncertain refs?

**Solution:** At end-of-exchange (natural conversation pause), surface refs with urgency signals.

**Routing:**
- **Inline**: Only if actively citing the ref in current response
- **Scratchpad**: Everything else (background patterns, stale refs, etc.)

**Urgency signals (with scores):**
| Signal | Score | Description |
|--------|-------|-------------|
| Actively citing | +100 | I'm using this ref NOW |
| Created this exchange | +50 | Fresh, still in context |
| Cluster-flagged | +30 | 3+ sources suggested same ref |
| Urgent priority | +25 | Already marked urgent |
| Low confidence (<0.7) | +20 | I'm uncertain |
| Stale (>3 days) | +15 | Pending too long |

**Methods implemented:**
- `get_validation_prompts(context_id, citing_refs, exchange_created_refs)` - main surfacing method
- `detect_contradictions(context_id)` - finds conflicting ref_types (e.g., implements vs contradicts)
- `check_chain_stability(context_id)` - finds unstable dependency chains

**Response format:** Conversational, no batch approval. Simple "yes" or detailed feedback both accepted.

**Constants:**
- `VALIDATION_CONFIDENCE_THRESHOLD = 0.7`
- `STALENESS_DAYS = 3`

### 9.16 Coordination Sidebar Pattern (Grab Collision)

**Problem:** What happens when two agents grab the same yarn board point?

**Solution:** Collision = coordination signal, not conflict. System spawns an impromptu sidebar for both agents to sync up.

**Flow:**
1. Agent A grabs point P → Redis stores `{agent_id: "A", grabbed_at: timestamp}`
2. Agent B tries to grab point P → collision detected
3. System spawns coordination sidebar with both agents
4. Both agents now know they're interested in the same thing
5. They sync up, clarify shared interest, or divide work

**Implementation:**
- Redis HASH stores `{point_id: {agent_id, grabbed_at}}` instead of just point IDs
- `set_grabbed()` checks for existing grab before setting
- If collision: spawns sidebar with priority=HIGH, created_by="system"
- API broadcasts `coordination_sidebar_spawned` event

**API Changes:**
- `POST /yarn-board/points/{id}/grab` now accepts `agent_id` (default: "operator")
- Response includes `coordination` object if collision occurred:
```json
{
  "success": true,
  "grabbed": true,
  "coordination": {
    "sidebar_id": "SB-42",
    "agents": ["agent-curator", "agent-researcher"],
    "point_id": "crossref:SB-1:SB-2",
    "other_grabbed_at": "2026-01-13T22:30:00",
    "reason": "grab_collision"
  }
}
```

**Design Philosophy:**
- Two agents reaching for the same thing is information, not a bug
- They probably have related questions or complementary perspectives
- A quick sidebar to sync up is better than silently overwriting

---

## Revision History (continued)

- 2026-01-07: Phase 4 core implementation complete (reparent, cross-ref methods and endpoints)
- 2026-01-07: Renamed `suggested_by_claude` to `suggested_by_model` (model-agnostic)
- 2026-01-07: Added Section 8: Phase 4 Refinements (strength levels, revocation, ref_types, discovery methods)
- 2026-01-08: Phase 4 refinements implemented (speculative strength, CROSS_REF_REVOKED, expanded ref_types, discovery_method validation)
- 2026-01-08: "Treat Yo Self" additions - CrossRefMetadata, Dict storage, CROSS_REF_UPDATED, filters, auto-validation
- 2026-01-08: Human validation system interview complete (Section 8.9) - validation states, timing, clustering, persistence, metadata
- 2026-01-09: Human validation system implemented - CrossRefMetadata fields, CROSS_REF_VALIDATED event, validate_cross_ref(), API endpoints
- 2026-01-09: Phase 4 COMPLETE. Added validation_priority to update_cross_ref() flow
- 2026-01-09: Phase 5 interview complete (Section 9) - Yarn board as view layer, Redis stubs, Scratchpad extension, relationship type reuse
- 2026-01-09: Phase 5 foundation implemented - YarnBoardLayout, YarnBoardState, RedisInterface stub, ScratchpadEntry extension, new ref_types (blocks, depends_on, informs)
- 2026-01-09: Yarn board orchestrator methods added - get_yarn_layout, save_yarn_layout, update_point_position, get_yarn_state, set_grabbed
- 2026-01-09: Yarn board API endpoints added - GET/PUT /yarn-board, PATCH /yarn-board/points/{id}, GET /yarn-board/state, POST /yarn-board/points/{id}/grab
- 2026-01-09: Review pass - added entry_type validator, documented open questions (Section 9.8): point ID convention, auto-positioning, render projection
- 2026-01-12: Point ID convention resolved - self-describing with type prefix, sorted cross-refs, existing IDs
- 2026-01-12: Auto-positioning resolved - force-directed graph, pin cushion pattern, pin locking, highlight feature
- 2026-01-12: Render projection resolved - minimap philosophy, minimal structure (points, connections, cushion, highlights), color coding by type
- 2026-01-12: render_yarn_board() implemented in orchestrator + POST /yarn-board/render endpoint added
- 2026-01-12: Design refinement - yarn board is CONNECTION EXPLORER interface, not just passive minimap. Supports inline expansion for detail viewing
- 2026-01-12: Queue routing implemented - route_scratchpad_entry(), curator_approve_entry(), _infer_destination(), agent registry with default agents
- 2026-01-12: Redis integration intent documented - stubs in place, logic implemented against interface, ready for real Redis when added
- 2026-01-12: Clustering implemented - suggested_sources/cluster_flagged fields on CrossRefMetadata, CLUSTERING_THRESHOLD=3, auto-flags validation_priority to urgent, get_cluster_flagged_refs() helper
- 2026-01-12: Documented pending connection points (Section 9.14) - yarn board expansion, queue routing endpoints, clustering endpoint
- 2026-01-12: Validation prompts implemented (Section 9.15) - get_validation_prompts(), detect_contradictions(), check_chain_stability(), urgency scoring, inline vs scratchpad routing
- 2026-01-12: Redis integration complete - docker-compose.yml, redis_client.py with full implementation, API startup initialization, /redis/health endpoint, graceful degradation
- 2026-01-13: Fix heartbeat() to create default agent status if none exists
- 2026-01-13: suggested_sources changed from List[str] to List[Dict] with source_id and suggested_at timestamps
- 2026-01-13: Queue routing API endpoints implemented - POST /queue/route, /queue/approve, GET /queue/{agent_id}, etc. (8 endpoints total)
- 2026-01-13: Test review session - identified gaps: concurrency, persistence round-trip, render expansion, pin cushion buffer, performance thresholds, WebSocket mechanics
- 2026-01-13: Gap resolutions documented - coordination events for concurrency, timestamps+coalescing for WebSocket ordering, pin cushion as CPU/human catch-up buffer
- 2026-01-13: Render expansion implemented - render_yarn_board(expanded=True) adds detail dicts with context summary, crossref metadata (ref_type, strength, confidence, validation_state, etc.)
- 2026-01-13: Coordination sidebar pattern implemented - grab collisions spawn coordination sidebar for agents to sync up. Redis now stores {agent_id, grabbed_at} per point. API broadcasts coordination_sidebar_spawned event.
- 2026-01-13: Clustering endpoint implemented - GET /cross-refs/clustered returns cluster-flagged refs (3+ sources). All Phase 5 connection points now complete.
