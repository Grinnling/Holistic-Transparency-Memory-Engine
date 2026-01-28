# Debug Sheet: Message Duplication & Metadata Persistence Issues
**Date:** 2026-01-25
**Status:** Investigation paused - resume tomorrow
**Priority:** High - affects core chat functionality

---

## Observed Symptoms

### 1. Message Duplication
- Messages appear twice in React UI
- Pattern: one message WITHOUT episodic memories, one WITH
- Triggered by: browser refresh, API restart
- NOT visible during normal incremental chat (only on full history reload)

### 2. Metadata Persistence Loss
- Retrieved memories (episodic additions) lost after API cycle
- First message shows memories, subsequent loads don't
- Conversation context appears to reset

### 3. Root Context Generation
- API restart seems to generate TWO new root conversations
- Previous conversation context not restored properly

---

## Changes Made Today (potential regression sources)

### In `rich_chat.py`:
1. **Removed duplicate orchestrator.add_exchange()** (was lines 334-350)
   - Consolidated into single store_exchange() call with metadata

2. **Removed duplicate conversation_history.append()** (was lines 335-342)
   - Now relies on conversation_manager to handle this

3. **Reordered operations**: validation now happens BEFORE storage

### In `conversation_manager.py`:
1. **Updated store_exchange()** to include metadata in conversation_history append
   - Added `if metadata: history_entry.update(metadata)`

### In `api_server_bridge.py`:
1. Earlier fix removed duplicate storage in bridge (was also appending to local_memory)

---

## Data Flow (Current Understanding)

```
User sends message
    ↓
rich_chat.process_message()
    ↓
rich_chat.store_exchange(metadata={validation, retrieved_memories, source})
    ↓
conversation_manager.store_exchange(metadata)
    ├─→ orchestrator.add_exchange(metadata) → ctx.local_memory.append(exchange)
    └─→ conversation_history.append(entry + metadata)
```

### Two Data Sources for React:
1. `/history` endpoint → returns `chat.conversation_history`
   - Used by `loadHistory()` on startup

2. `/sidebars/{id}` endpoint → returns `ctx.local_memory`
   - Used by `focusSidebar()` when clicking sidebar items

**Question:** Are these staying in sync? Do they both have retrieved_memories?

---

## Investigation Steps for Tomorrow

### Step 1: Verify Storage
Add debug logging to see what's actually being stored:

```python
# In conversation_manager.store_exchange() after the append:
print(f"DEBUG CM: Stored to conversation_history: {history_entry.keys()}")
print(f"DEBUG CM: retrieved_memories present: {'retrieved_memories' in history_entry}")

# In orchestrator.add_exchange() after the append:
print(f"DEBUG ORCH: Stored to local_memory: {exchange.keys()}")
print(f"DEBUG ORCH: retrieved_memories present: {'retrieved_memories' in exchange}")
```

### Step 2: Verify Retrieval
Check what the API endpoints return:

```bash
# Check /history endpoint
curl http://localhost:8000/history | jq '.history[0] | keys'

# Check /sidebars/{id} endpoint
curl http://localhost:8000/sidebars/SB-XXX | jq '.context.local_memory[0] | keys'
```

### Step 3: Check Startup Sequence
The API startup might be creating contexts before chat is fully initialized:

```python
# In api_server_bridge.py startup section (around line 3005):
# Add logging to see what happens on startup
print(f"DEBUG STARTUP: Active context ID: {orchestrator.get_active_context_id()}")
print(f"DEBUG STARTUP: Total contexts: {len(orchestrator._contexts)}")
```

### Step 4: Check Root Creation
Why are TWO roots being created?

```python
# In create-root endpoint:
print(f"DEBUG CREATE-ROOT: Called with task_description={request.task_description}")
print(f"DEBUG CREATE-ROOT: Existing contexts before: {list(orchestrator._contexts.keys())}")
```

### Step 5: Check conversation_history Reference
Are rich_chat and conversation_manager actually sharing the same list?

```python
# In rich_chat.__init__ after setting up conversation_manager:
print(f"DEBUG INIT: conversation_history id: {id(self.conversation_history)}")
print(f"DEBUG INIT: cm.conversation_history id: {id(self.conversation_manager.conversation_history)}")
print(f"DEBUG INIT: Same object: {self.conversation_history is self.conversation_manager.conversation_history}")
```

---

## Suspected Root Causes

### Theory A: Reference vs Copy Issue
- `self.conversation_history = self.conversation_manager.conversation_history` might be a copy, not a reference
- Changes to one don't reflect in the other

### Theory B: Startup Race Condition
- API creates context before rich_chat is initialized
- rich_chat creates its own context on init
- Results in two roots

### Theory C: Persistence/Reload Mismatch
- Data saved to one format (local_memory structure)
- Loaded back in different format (conversation_history structure)
- Metadata fields lost in translation

### Theory D: /history vs /sidebars Inconsistency
- loadHistory() called on startup → uses conversation_history
- focusSidebar() called on click → uses local_memory
- These might have different data

---

## Files to Review

1. **rich_chat.py** - lines 309-345 (storage flow)
2. **conversation_manager.py** - lines 390-410 (store_exchange)
3. **conversation_orchestrator.py** - lines 561-610 (add_exchange)
4. **api_server_bridge.py** - lines 389-399 (/history endpoint)
5. **api_server_bridge.py** - lines 1165-1175 (/sidebars/{id} endpoint)
6. **api_server_bridge.py** - lines 3000-3020 (startup sequence)
7. **src/App.tsx** - lines 110-127 (useEffect startup)
8. **src/App.tsx** - lines 243-268 (loadHistory)
9. **src/App.tsx** - lines 451-513 (focusSidebar)

---

## Quick Rollback if Needed

If issues persist, the key changes to potentially revert:

1. **rich_chat.py**: Restore the conversation_history.append() block (but keep orchestrator.add_exchange removal)
2. **conversation_manager.py**: Revert the metadata update addition

---

## Session Summary - What We Fixed Today (Before This Bug)

Working fixes (keep these):
- Bulk archive alias search
- Bulk archive search modes (5 modes)
- Tree view sorting
- Pagination auto-jump to active context
- Pause/archive refresh sidebar tree

Uncertain fixes (may need revision):
- Double-write removal (rich_chat.py)
- Metadata inclusion in conversation_manager

---

## CONFIRMED ROOT CAUSES (2026-01-26 Session)

### ROOT CAUSE #0: start_new_conversation() Ignores Loaded Contexts (CRITICAL - NEW FINDING)
**Location:** `conversation_manager.py:103-130` (start_new_conversation)
**Found:** 2026-01-26 during deep investigation

**The Bug:**
```python
def start_new_conversation(self, task_description: str = None):
    # ...
    self.conversation_history = []  # Creates NEW empty list
    self._context_id = self.orchestrator.create_root_context(...)  # Creates NEW context!
```

**What happens:**
```
1. API starts
2. orchestrator.__init__() loads 13 contexts from SQLite (including SB-6399 with local_memory)
3. RichMemoryChat.__init__() calls start_new_conversation()
4. start_new_conversation() IGNORES loaded contexts, creates NEW root (SB-6400)
5. _context_id points to SB-6400 (empty)
6. SB-6399's local_memory is ORPHANED
7. api_server_bridge tries to restore from SB-6399 but chat is using SB-6400
```

**This explains:**
- Why `local_memory` appears empty (wrong context!)
- Why 13 contexts exist but exchanges seem lost
- Why new roots keep appearing on restart
- Why the reference breaking matters less than we thought (context mismatch is the real issue)

**Fix options:**
1. Check if active context exists before creating new one
2. Use active context's local_memory instead of creating fresh
3. Add "resume" vs "new" startup modes

**Verification needed:**
- [ ] Debug logging to confirm new context created on every startup
- [ ] Debug logging to show SB-6399 has data but SB-6400 doesn't

---

### ROOT CAUSE #1: Reference Breaking (CRITICAL)
**Location:** `api_server_bridge.py:3019`
**The Bug:**
```python
chat.conversation_history = restored  # Creates NEW list, breaks reference
```

**What happens:**
```
BEFORE line 3019:
  conversation_manager.conversation_history → ListA
  chat.conversation_history → ListA (same object)

AFTER line 3019:
  conversation_manager.conversation_history → ListA (orphaned)
  chat.conversation_history → ListB (new list)

RESULT: store_exchange() appends to ListA, /history returns ListB
```

**Fix:** Use `clear()` + `extend()` to modify in-place:
```python
chat.conversation_history.clear()
chat.conversation_history.extend(restored)
```

**Verification needed:**
- [ ] Add debug logging to confirm same object ID before/after startup
- [ ] Verify new messages appear in /history after fix

---

### ROOT CAUSE #2: Metadata Loss During Restoration
**Location:** `api_server_bridge.py:3009-3019` and `conversation_manager.py:295-302`

**The Bug:** Restored entries only capture basic fields:
```python
# What gets restored:
{'user': ..., 'assistant': ..., 'timestamp': ..., 'source': 'restored'}

# What's LOST:
{'retrieved_memories': [...], 'validation': {...}, 'exchange_id': ...}
```

**Why it matters:** Even if reference is fixed, metadata disappears on API restart.

**Fix options:**
1. Store metadata in orchestrator's `local_memory` (already happening via `add_exchange`)
2. Restore FROM `local_memory` which HAS the metadata
3. Define canonical `Exchange` dataclass in `datashapes.py`

**Verification needed:**
- [ ] Check if `local_memory` actually has `retrieved_memories` after storage
- [ ] If yes, restore from there instead of building stripped-down version

---

### ROOT CAUSE #3: Format Mismatch
**Location:** `api_server_bridge.py:3011`

**The Bug:**
```python
if ex.get("role") == "user"  # Expects role/content format
```

But orchestrator stores:
```python
{"user": user_message, "assistant": assistant_response}  # Different format!
```

**Result:** Restoration logic may silently match nothing.

**Fix:** Update restoration to use correct keys OR standardize on one format via `datashapes.py`.

**Verification needed:**
- [ ] Check what format `local_memory` actually contains after `add_exchange()`
- [ ] Update restoration logic to match

---

### ROOT CAUSE #4: Conflicting Restoration Paths
**Locations:**
- `rich_chat.py:188` calls `conversation_manager.restore_conversation_history()`
- `api_server_bridge.py:3005-3020` does its own restoration

**The Bug:** Two different systems try to restore history, potentially overwriting each other.

**Fix:** Single source of truth - one restoration path, not two.

**Verification needed:**
- [ ] Trace startup sequence to see which runs first
- [ ] Decide which restoration to keep

---

## FIX IMPLEMENTATION CHECKLIST

### Phase 1: Fix Reference Breaking (Issue #1)
**Priority:** CRITICAL - this causes the "drift" symptom

**Steps:**
1. [ ] Add debug logging to verify reference is currently breaking
2. [ ] Change `chat.conversation_history = restored` to `clear()/extend()`
3. [ ] Verify same object ID after startup
4. [ ] Test: send message, restart API, check /history has the message

**AI Satisfaction Criteria:**
- Object ID of `chat.conversation_history` must match `conversation_manager.conversation_history` after startup
- New messages must appear in /history after API restart

---

### Phase 2: Fix Format Mismatch (Issue #3)
**Priority:** HIGH - restoration may silently fail

**Steps:**
1. [ ] Add debug logging to see actual format in `local_memory`
2. [ ] Update restoration logic to use correct keys (`user`/`assistant` not `role`/`content`)
3. [ ] Verify restoration actually finds and loads exchanges

**AI Satisfaction Criteria:**
- Restoration must actually load exchanges (not empty list)
- Format must match what `add_exchange()` stores

---

### Phase 3: Fix Metadata Loss (Issue #2)
**Priority:** MEDIUM - affects episodic memory display

**Steps:**
1. [ ] Verify `local_memory` contains `retrieved_memories` after storage
2. [ ] Update restoration to include metadata fields
3. [ ] OR: Define `Exchange` dataclass in `datashapes.py` for consistency

**AI Satisfaction Criteria:**
- `retrieved_memories` must survive API restart
- React UI must show episodic memories after refresh

---

### Phase 4: Consolidate Restoration Paths (Issue #4)
**Priority:** LOW (after other fixes) - cleanup for maintainability

**Steps:**
1. [ ] Document startup sequence
2. [ ] Choose single restoration path
3. [ ] Remove redundant code

**AI Satisfaction Criteria:**
- One restoration path, clearly documented
- No conflicting overwrites

---

## Notes

- User's brain is "spongy" - stop for tonight
- This is interconnected: storage, retrieval, startup, React display
- Need methodical debugging with logging before more code changes

---

## Session 2026-01-26 Notes

- Confirmed Theory A (reference breaking) is real and happening at line 3019
- Confirmed Theory C (format mismatch) - restoration expects wrong keys
- Theory D partially confirmed - the two data sources CAN diverge
- No canonical Exchange dataclass exists - potential datashapes.py addition
