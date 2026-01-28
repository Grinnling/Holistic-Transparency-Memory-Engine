# Visibility Stream PRD

**Created:** December 24, 2025
**Status:** Active - Primary UI priority
**Purpose:** Enable operator to see what Claude sees via event stream to React

---

## Context: Why Visibility Matters

### The Problem
The operator uses React as their primary interface, but significant system activity is only visible in CLI or not visible at all. This creates a "poison detection" gap - if bad data affects Claude's reasoning, the operator can't trace it.

### The Need
- Operator sees what Claude sees
- Claude sees what operator sees
- Raw/unformatted is acceptable initially
- Ability to trace "thought trail" without interrupting work
- Catch poison before it compounds

### Why Not UIHandler Extraction?
UIHandler extraction (see UIHANDLER_EXTRACTION_PRD.md) focuses on CLI formatting. The operator doesn't use CLI. The real value is **visibility into data flow**, not pretty CLI panels.

---

## What Operator Needs to See

### Tier 1: Critical Visibility (Poison Detection)
| Event Type | What It Shows | Why It Matters |
|------------|---------------|----------------|
| `context_loaded` | What context Claude is working with | See if wrong/stale context affects reasoning |
| `memory_retrieved` | What memories were fetched, confidence scores | Catch low-confidence or irrelevant retrievals |
| `validation_result` | Response validation data | See confidence, source citations |
| `error_occurred` | Errors and recovery attempts | Catch silent failures |

### Tier 2: System Visibility (Understanding Flow)
| Event Type | What It Shows | Why It Matters |
|------------|---------------|----------------|
| `ozolith_logged` | OZOLITH events as they happen | Audit trail visibility |
| `sidebar_lifecycle` | Sidebar spawn/pause/merge/archive | Context tree changes |
| `memory_pressure` | Buffer status, distillation triggers | System health |
| `emergency_mode` | Which emergency mode, why | Critical system state |

### Tier 3: Debug Visibility (Deep Dive)
| Event Type | What It Shows | Why It Matters |
|------------|---------------|----------------|
| `llm_prompt` | Actual prompt sent to LLM | See exactly what Claude received |
| `llm_response_raw` | Raw LLM response before processing | Pre-enhancement visibility |
| `citation_created` | Citation tracking | Knowledge graph foundation |
| `correction_logged` | When something was corrected | Learning visibility |
| `tool_invocation` | When Claude uses tools (MCP, file ops) | See what actions are taken |
| `search_performed` | When codebase is searched | See what Claude is looking for |
| `file_read` / `file_write` | File access events | See what code is being touched |
| `distillation_triggered` | Memory compression events | Know when old context compressed |
| `anchor_created` | OZOLITH checkpoint creation | See where waypoints are set |
| `conversation_switch` | Context changes | Know when working context changed |

### Event View Priority Defaults
| Tier | Default Visibility | User Control |
|------|-------------------|--------------|
| Tier 1 (Critical) | Always visible | Cannot hide |
| Tier 2 (System) | Collapsed by default | Expand on click |
| Tier 3 (Debug) | Hidden by default | Toggle to show |

---

## Current State

### What Already Exists
| Component | Location | What It Does |
|-----------|----------|--------------|
| `api_server_bridge.py` | lines 68-282 | Sends chat responses to React via WebSocket |
| `confidence_score` | Already flows to React | See UIHANDLER_EXTRACTION_PRD.md confidence trace |
| OZOLITH events | `ozolith.py` | Logged but not streamed to React |
| Error handler | `error_handler.py` | Tracks errors but limited React visibility |

### What's Missing
- Event emission system (central place to emit events)
- WebSocket channel for system events (separate from chat messages)
- React component to display event stream
- Event filtering/search capability

---

## Proposed Solution

### Architecture
```
rich_chat.py / conversation_manager.py / etc.
        ↓
    emit_event("event_type", payload)
        ↓
    EventEmitter (new component)
        ↓
    api_server_bridge.py (WebSocket)
        ↓
    React EventStream component
```

### EventEmitter Interface
```python
# Simple event emission
class EventEmitter:
    def emit(self, event_type: str, payload: dict):
        """Emit event to all listeners (React, logs, etc.)"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "payload": payload,
            "sequence": self.next_seq()
        }
        self.broadcast(event)
```

### React Component (Basic)
```jsx
// Initial version - just show raw events
function EventStream({ events }) {
    return (
        <div className="event-stream">
            {events.map(e => (
                <div key={e.sequence} className={`event-${e.type}`}>
                    <span className="timestamp">{e.timestamp}</span>
                    <span className="type">{e.type}</span>
                    <pre>{JSON.stringify(e.payload, null, 2)}</pre>
                </div>
            ))}
        </div>
    );
}
```

---

## Implementation Phases

### Phase 1: Foundation (Event Emission)
1. Create `event_emitter.py` with basic EventEmitter class
2. Add WebSocket channel in `api_server_bridge.py` for events (separate from chat)
3. Wire EventEmitter to api_server_bridge
4. Add basic React EventStream component (raw JSON display)

**Result:** Events can flow from backend to React

### Phase 2: Critical Events (Tier 1)
1. Add `context_loaded` emission in conversation_manager.py
2. Add `memory_retrieved` emission in memory retrieval path
3. Add `validation_result` emission after response validation
4. Add `error_occurred` emission in error_handler.py

**Result:** Operator can see critical data flow

### Phase 3: System Events (Tier 2)
1. Add `ozolith_logged` emission in ozolith.py
2. Add `sidebar_lifecycle` emission in conversation_orchestrator.py
3. Add `memory_pressure` emission in rich_chat.check_memory_pressure()
4. Add `emergency_mode` emission in recovery_monitoring.py

**Result:** Full system visibility

### Phase 4: Polish (Optional)
1. Event filtering in React
2. Event search
3. Collapsible event details
4. Color coding by event type
5. Export event history

**Result:** Usable forensics tool

---

## What We Can Reuse from UIHandler PRD

| Section | What's Useful | How to Reuse |
|---------|---------------|--------------|
| Enum definitions (Section 3) | SidebarStatus, OzolithEventType, etc. | Event payloads can include these typed values |
| Confidence Display Trace | Shows data flow for confidence | Same pattern for other event types |
| Dependency verification | File:line references | Know where to add event emissions |
| Success criteria patterns | Checkbox structure | Apply to visibility phases |

---

## Dependencies

### Required for Phase 1:
- [x] `api_server_bridge.py` exists with WebSocket support
- [x] React app exists and connects via WebSocket
- [ ] New: EventEmitter class
- [ ] New: WebSocket event channel

### Required for Phase 2:
- [x] `conversation_manager.py` exists
- [x] Memory retrieval path exists
- [x] Validation exists in response flow
- [x] `error_handler.py` exists

### Required for Phase 3:
- [x] OZOLITH implemented
- [x] ConversationOrchestrator implemented
- [x] Memory pressure detection in rich_chat.py
- [x] Emergency modes in recovery_monitoring.py

---

## Success Criteria

### Phase 1 Complete When:
- [x] EventEmitter class created and importable (`event_emitter.py`)
- [x] api_server_bridge has event WebSocket channel (`/ws/events` endpoint)
- [x] React receives and displays test event (`EventStreamPanel.tsx`)
- [ ] Round-trip verified: emit → bridge → React (needs manual testing)

### Phase 2 Complete When:
- [ ] `context_loaded` events appear in React when conversation loads
- [ ] `memory_retrieved` events show retrieval results and confidence
- [ ] `validation_result` events show response validation data
- [ ] `error_occurred` events show errors as they happen
- [ ] Operator can trace a complete request flow

### Phase 3 Complete When:
- [ ] OZOLITH events visible as they're logged
- [ ] Sidebar lifecycle visible (spawn/merge/archive)
- [ ] Memory pressure warnings visible
- [ ] Emergency modes visible when triggered

### Phase 4 Complete When:
- [ ] Events filterable by type
- [ ] Events searchable
- [ ] Event details collapsible
- [ ] Reasonable performance with many events

---

## Event Type Extensibility

**Event types are NOT a closed set.** The tier classifications above represent the initial implementation, but:

- New event types can be added at any time
- Tier assignments can be adjusted based on operational experience
- The system should be designed to handle unknown event types gracefully
- React should display unrecognized events rather than hiding them

This ensures we don't need to get it perfect on the first pass - we iterate based on what the operator actually needs to see.

---

## Questions to Resolve

### 1. Event persistence - store or just stream?
**Options:**
- Option A: Stream only (events disappear on refresh)
- Option B: Store in memory (keep last N events)
- Option C: Persist to OZOLITH (full audit trail)

**RESOLVED:** Option C - Persist to OZOLITH

**Decision:** Let OZOLITH handle record keeping. Events become part of the immutable audit trail.

**Why:**
- OZOLITH already handles append-only logging
- Full audit trail baked in
- Operator instinct: let OZOLITH handle as much as possible
- Can always query history, not just live stream

### 2. Event volume - everything or filtered?
**Options:**
- Option A: Emit everything, filter in React
- Option B: Configurable emission (debug levels)
- Option C: Always emit Tier 1, optionally emit Tier 2/3

**RESOLVED:** Hybrid - C for live stream + A for OZOLITH storage

**Decision:** Tier classification controls live traffic, OZOLITH stores everything, React can query history.

**The hybrid model:**
1. **Emit with tier classification** - Tier 1 always streams, Tier 2/3 optional for live traffic
2. **OZOLITH stores ALL events** - Nothing lost, complete audit trail (from Q1)
3. **React tier settings control LIVE visibility** - What streams by default
4. **React can query OZOLITH for history** - Pull any event regardless of original tier
5. **Tier assignments changeable in React** - Operator can reconfigure what's "critical" vs "debug"

**Why this hybrid:**
- Traffic managed for performance (C benefit)
- Nothing cheesable - OZOLITH has everything (A benefit)
- Operator controls visibility, Claude controls classification
- Historical truth always accessible via OZOLITH query
- "No one can hide an event but can hide what events aren't important to them" - preserved via OZOLITH

**Skinflap principle:** Claude's column of truth is not cheesable because OZOLITH stores everything regardless of tier. Tiers only affect what streams live.

### 3. Separate WebSocket or same channel?
**Options:**
- Option A: Same WebSocket as chat, different message type
- Option B: Separate WebSocket connection for events

**RESOLVED:** Option B - Separate WebSocket for events

**Decision:** Separate socket for better siloing

**Why:**
- Independent reconnection (events don't drop if chat hiccups)
- Different retention policies possible
- Cleaner React message handling
- Could have "debug socket" that's off by default
- Better siloing - event stream is its own concern
- Slightly more work but cleaner architecture

---

## Revision History
- 2025-12-24: Initial PRD created
  - Pivot from UIHandler extraction (CLI) to visibility stream (React)
  - Focus on operator seeing what Claude sees
  - Three-tier event classification (Critical, System, Debug)
  - Four-phase implementation plan
- 2025-12-24: Refined with operator feedback
  - Added additional Tier 3 events: tool_invocation, search_performed, file_read/write, distillation_triggered, anchor_created, conversation_switch
  - Added Event View Priority Defaults table
  - Resolved Q1: Option C - OZOLITH persistence
  - Resolved Q2: Hybrid (C for live + A for storage) - tiers control live stream, OZOLITH stores everything, nothing cheesable
  - Resolved Q3: Option B - Separate WebSocket for siloing
  - Added "Skinflap principle" - Claude's column of truth not cheesable via OZOLITH
- 2025-12-24: Phase 1 Implementation Complete
  - Created `event_emitter.py` with EventEmitter class, EventTier enum, tier mapping
  - Added `/ws/events` WebSocket endpoint in api_server_bridge.py (separate from chat)
  - Added REST endpoints: `/events/stats`, `/events/history`, `/events/types`
  - Created `EventStreamPanel.tsx` React component with tier filtering, search, pause/play
  - EventEmitter wired to broadcast via async listener on startup
  - OZOLITH persistence integrated (all events logged regardless of tier)
  - Ready for Phase 2: Add event emissions at integration points in rich_chat.py
- 2025-12-24: EventStreamPanel.tsx Code Review & Fixes
  - Added try-catch around JSON.parse to prevent crashes on malformed messages
  - Fixed useEffect dependency storm - tier/pause changes no longer trigger reconnections
  - Added exponential backoff for WebSocket reconnection (1s → 2s → 4s → max 30s)
  - Updated WebSocket URL to use environment variable (VITE_WS_EVENTS_URL)
- 2025-12-24: Environment Configuration System
  - Created `.env.example` as system topology map (documents all services)
  - Created `check_services.py` health validation script
  - Updated all React components to use VITE_* environment variables
  - Updated all Python services to use os.environ.get() with defaults
  - Updated vite.config.ts to use loadEnv for proxy configuration
  - Created `.gitignore` for CODE_IMPLEMENTATION folder
  - Documentation: `docs/ENVIRONMENT_CONFIGURATION.md`
