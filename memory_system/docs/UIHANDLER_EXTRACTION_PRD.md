# UIHandler Extraction PRD

**Created:** December 19, 2025
**Status:** DEPRIORITIZED - Valid but lower priority than visibility work
**Purpose:** Define remaining UIHandler extraction work in context of OZOLITH and sidebar architecture

---

## ⚠️ PRIORITY NOTE (December 24, 2025)

**This PRD is valid but deprioritized.**

During review, we identified that UIHandler extraction primarily benefits CLI users, but the operator primarily uses React. The higher-value work is **visibility/event streaming** to React so the operator can see what Claude sees.

**New priority:** VISIBILITY_STREAM_PRD.md - Event visibility for React layer
**This PRD:** Valid for future CLI cleanup, not blocking

**Why the pivot:**
- Operator uses React, not CLI
- UIHandler extraction makes CLI prettier but doesn't help React
- Real need: visibility into data flow to catch "poison" before it affects reasoning
- Solution: Event stream to React showing context, retrievals, validation, OZOLITH events

**What's still useful from this PRD:**
- Enum definitions and styling patterns (Section 3)
- Dependency verification (Section 7)
- Confidence display trace (Reference section)
- Success criteria patterns (Section 9)

---

---

## Context: What's Changed Since Initial UI Work

### Now Built (Dec 2025):
1. **OZOLITH** - Immutable append-only audit log
2. **ConversationManager** - Conversation persistence with OZOLITH events
3. **ConversationOrchestrator** - Session/sidebar/context tree management
4. **UNIFIED_SIDEBAR_ARCHITECTURE.md** - Comprehensive sidebar specification

### Implication for UIHandler:
The UIHandler isn't just "display some panels" anymore. It needs to:
- Display 10 sidebar states (ACTIVE, TESTING, PAUSED, WAITING, etc.)
- Show context tree visualization
- Display memory separation (inherited vs local)
- Show OZOLITH audit status indicators
- Support the entire sidebar lifecycle (spawn, pause, merge, archive)

---

## Current State

### UIHandler (ui_handler.py) - 18 Methods Exist:

| Category | Methods | Status |
|----------|---------|--------|
| **Display** | show_welcome, show_status, show_help, show_context_preview, show_memory_stats | DONE |
| **Recovery** | display_recovery_result, display_error_panel_if_enabled | DONE |
| **Toggles** | toggle_token_display, toggle_confidence_display, toggle_debug_display | DONE |
| **Progress** | show_progress, update_status | DONE |
| **Response** | render_response | DONE |
| **Command** | parse_command, is_command | DONE |
| **Error** | display_error | DONE |

### rich_chat.py - Direct console.print Calls NOT Delegating:

**Conversation UI (6 calls - should move):**
| Line | What |
|------|------|
| 811 | start_new_conversation Panel |
| 827 | list_conversations empty Panel |
| 854 | list_conversations table Panel |
| 861 | list_conversations overflow message |
| 872 | switch_conversation failed Panel |
| 888 | switch_conversation success Panel |

**Sidebar UI (10 calls - should move):**
| Line | What |
|------|------|
| 950 | spawn_sidebar Panel |
| 963 | spawn_sidebar processing message |
| 968 | spawn_sidebar response Panel |
| 1007 | merge_current_sidebar Panel |
| 1056 | back_to_parent Panel |
| 1093 | focus_context Panel |
| 1127 | pause_current_context Panel |
| 1190 | show_context_tree empty message |
| 1196 | show_context_tree tree display |
| 1200 | show_context_tree stats |

**Toggles (2 calls - should move):**
| Line | What |
|------|------|
| 1377 | FIWB toggle Panel |
| 1460 | error panel toggle message |

**Run Loop / Core (8 calls - keep or special handling):**
| Line | What |
|------|------|
| 1250 | Rich not available warning |
| 1288 | welcome message |
| 1308 | "You" prompt |
| 1311 | Goodbye message |
| 1319 | Goodbye message |
| 1342 | response_panel display |
| 1348 | confidence display |
| 1353 | Goodbye message |

**Total to move:** 18 calls (6 conversation + 10 sidebar + 2 toggles)
**Total to keep/review:** 8 calls (core run loop)

---

## Alignment with Sidebar Architecture

### From UNIFIED_SIDEBAR_ARCHITECTURE.md Phase 8 (UI Integration):

| UI Component | Backend Phase | UIHandler Needed | Priority |
|--------------|---------------|------------------|----------|
| Status indicators (10 states) | Phase 2 | YES - sidebar status display | HIGH |
| Spawn/merge/archive controls | Phase 2 | YES - action feedback panels | HIGH |
| Context tree display | Phase 2 | YES - show_context_tree | HIGH |
| Scratchpad display | Phase 3 | Future | MEDIUM |
| Curator validation UI | Phase 3 | Future | MEDIUM |
| GOLD flagging UI | Phase 3 | Future | MEDIUM |
| Agent presence display | Phase 5 | Future | LOW |
| Emergency mode indicators | Phase 4 | YES - show_emergency_status | MEDIUM |
| Recovery audit UI | Phase 4 | Partial (display_recovery_result) | MEDIUM |

### Sidebar States Requiring Display (from datashapes.py:25-39):

```python
class SidebarStatus(Enum):
    ACTIVE = "active"                    # Green, doing real work
    TESTING = "testing"                  # Yellow, experimental/debug, may discard
    PAUSED = "paused"                    # Yellow, temporarily stopped, resumable
    WAITING = "waiting"                  # Blue, blocked on human/external
    REVIEWING = "reviewing"              # Cyan, validating before consolidation
    SPAWNING_CHILD = "spawning_child"    # Magenta, creating sub-sidebar
    CONSOLIDATING = "consolidating"      # Cyan, determining what to merge
    MERGED = "merged"                    # Green, successfully integrated
    ARCHIVED = "archived"                # Dim, stored in episodic memory
    FAILED = "failed"                    # Red, unrecoverable error
```

### OZOLITH Event Types (from datashapes.py:362-395):

```python
class OzolithEventType(Enum):
    # Core exchanges
    EXCHANGE = "exchange"                # User/assistant message pair

    # Sidebar lifecycle
    SIDEBAR_SPAWN = "sidebar_spawn"      # New sidebar created
    SIDEBAR_MERGE = "sidebar_merge"      # Sidebar merged back to parent
    CONTEXT_PAUSE = "context_pause"      # Context paused
    CONTEXT_RESUME = "context_resume"    # Context resumed

    # Session lifecycle
    SESSION_START = "session_start"      # New session began
    SESSION_END = "session_end"          # Session ended (clean)

    # Learning signals
    CORRECTION = "correction"            # Something I said was corrected

    # Content federation
    CONTENT_INGESTION = "content_ingestion"    # External content entered
    CONTENT_REEMBEDDED = "content_reembedded"  # Content got new embedding

    # Memory lifecycle
    MEMORY_STORED = "memory_stored"            # Exchange archived
    MEMORY_DISTILLED = "memory_distilled"      # Old memories compressed

    # System events
    ERROR_LOGGED = "error_logged"              # Error occurred
    ANCHOR_CREATED = "anchor_created"          # Checkpoint created
    VERIFICATION_RUN = "verification_run"      # Chain verified
```

### SidebarPriority (from datashapes.py:42-48):

```python
class SidebarPriority(Enum):
    CRITICAL = "critical"    # Never auto-pause, queue jumper
    HIGH = "high"            # Don't auto-pause, queue normally
    NORMAL = "normal"        # Default priority
    LOW = "low"              # Can be auto-paused for higher priority
    BACKGROUND = "background"  # Can be auto-paused, lowest priority
```

### CitationType (from datashapes.py:2259-2269):

```python
class CitationType(Enum):
    # Basic reference/navigation types (Phase B - UIHandler)
    CONTEXTUAL_BOOKMARK = "contextual_bookmark"  # Reference to conversation moment
    DOCUMENT_LINK = "document_link"              # Link to static artifact/file (clickable!)
    RELATIONSHIP_MARKER = "relationship_marker"  # Indicates connection between items
    CONFIDENCE_ANCHOR = "confidence_anchor"      # Certainty + source tracking

    # Learning signal types (Agent Integration Phase - deferred)
    GOLD_REFERENCE = "gold_reference"            # Realignment waypoint - trusted anchor (>= 0.8 confidence)
    ICK_REFERENCE = "ick_reference"              # Inverse of GOLD - "this was wrong" (<= 0.3 confidence)
```

**Why split?** Basic citations (bookmarks, links, relationships) are useful now for navigation and clickable references. Learning signals (GOLD/ICK) are most valuable in multi-agent contexts where agents need to communicate "trust this" or "avoid this" to each other.

### AgentAvailability (from datashapes.py:51-55):

```python
class AgentAvailability(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
```

**UIHandler needs:** Helper methods for styling all these enums consistently

---

## Proposed UIHandler Additions

### Category 1: Conversation UI (Move from rich_chat.py)

```python
def show_new_conversation_panel(self, old_id: str, old_count: int, new_id: str):
    """Display new conversation started notification"""

def show_conversation_list(self, conversations: List[Dict], current_id: str):
    """Display conversation list table"""

def show_conversation_not_found(self, target_id: str):
    """Display switch failed notification"""

def show_conversation_switched(self, old_id: str, old_count: int, new_id: str, new_count: int):
    """Display conversation switch success"""
```

### Category 2: Sidebar UI (Move from rich_chat.py)

```python
def show_sidebar_spawned(self, sidebar_id: str, reason: str, parent_id: str,
                          inherited_count: int, status: SidebarStatus):
    """Display sidebar creation notification"""

def show_sidebar_processing(self):
    """Display 'Processing your question in sidebar...'"""

def show_sidebar_response(self, response: str, sidebar_id: str):
    """Display response panel with sidebar ID"""

def show_merge_complete(self, result: Dict):
    """Display merge success notification"""

def show_back_to_parent(self, left_id: str, now_in_id: str):
    """Display context switch back to parent"""

def show_focus_changed(self, from_id: str, to_id: str, status: SidebarStatus,
                        task_desc: str, local_count: int):
    """Display focus change notification"""

def show_context_paused(self, context_id: str):
    """Display context paused notification"""

def show_context_tree(self, tree_data: Dict, active_id: str, status_lookup: Callable):
    """Display full context tree visualization"""
```

### Category 2b: Toggle Feedback (Move from rich_chat.py)

```python
def show_fiwb_toggle(self, is_on: bool):
    """Display FUCK IT WE BALL mode toggle feedback

    Shows rich Panel with:
    - Status: ON 🎱 / OFF 🔇 (color coded red/green)
    - What it enables when ON: full stack traces, backup details,
      recovery state, episodic coordinator responses, emergency backup ops
    - Border color matches state

    Future: React "idiot light" GUI switch with color state indicator
    """

def show_error_panel_toggle(self, is_on: bool):
    """Display error panel toggle feedback

    Simple status message: "Error panel: ON/OFF"

    Future: React "idiot light" GUI switch with color state indicator
    """
```

### Category 3: Sidebar Status Helpers (New)

```python
def get_status_style(self, status: SidebarStatus) -> Tuple[str, str]:
    """Return (color, icon) for status display"""
    STATUS_STYLES = {
        SidebarStatus.ACTIVE: ("green", "🟢"),
        SidebarStatus.TESTING: ("yellow", "🧪"),
        SidebarStatus.PAUSED: ("yellow", "⏸️"),
        SidebarStatus.WAITING: ("blue", "⏳"),
        SidebarStatus.REVIEWING: ("cyan", "🔍"),
        SidebarStatus.SPAWNING_CHILD: ("magenta", "🔀"),  # Note: spawning_child not spawning
        SidebarStatus.CONSOLIDATING: ("cyan", "📋"),
        SidebarStatus.MERGED: ("green", "✅"),
        SidebarStatus.ARCHIVED: ("dim", "📦"),
        SidebarStatus.FAILED: ("red", "❌"),
    }
    return STATUS_STYLES.get(status, ("white", "❓"))

def get_event_style(self, event_type: OzolithEventType) -> Tuple[str, str]:
    """Return (color, icon) for OZOLITH event display"""
    EVENT_STYLES = {
        OzolithEventType.EXCHANGE: ("white", "💬"),
        OzolithEventType.SIDEBAR_SPAWN: ("cyan", "🔀"),
        OzolithEventType.SIDEBAR_MERGE: ("green", "🔗"),
        OzolithEventType.CONTEXT_PAUSE: ("yellow", "⏸️"),
        OzolithEventType.CONTEXT_RESUME: ("green", "▶️"),
        OzolithEventType.SESSION_START: ("blue", "🚀"),
        OzolithEventType.SESSION_END: ("blue", "🏁"),
        OzolithEventType.CORRECTION: ("magenta", "📝"),
        OzolithEventType.ERROR_LOGGED: ("red", "⚠️"),
        OzolithEventType.ANCHOR_CREATED: ("cyan", "⚓"),
    }
    return EVENT_STYLES.get(event_type, ("dim", "📋"))

def get_priority_style(self, priority: SidebarPriority) -> Tuple[str, str]:
    """Return (color, icon) for priority display"""
    PRIORITY_STYLES = {
        SidebarPriority.CRITICAL: ("red bold", "🔴"),
        SidebarPriority.HIGH: ("yellow", "🟠"),
        SidebarPriority.NORMAL: ("white", "⚪"),
        SidebarPriority.LOW: ("dim", "🔵"),
        SidebarPriority.BACKGROUND: ("dim", "⚫"),
    }
    return PRIORITY_STYLES.get(priority, ("white", "⚪"))

def get_citation_style(self, citation_type: CitationType) -> Tuple[str, str]:
    """Return (color, icon) for basic citation display (reference/navigation types)"""
    CITATION_STYLES = {
        CitationType.CONTEXTUAL_BOOKMARK: ("cyan", "🔖"),      # Conversation moment reference
        CitationType.DOCUMENT_LINK: ("blue", "📄"),            # Clickable file/artifact link
        CitationType.RELATIONSHIP_MARKER: ("magenta", "🔗"),   # Connection between items
        CitationType.CONFIDENCE_ANCHOR: ("green", "⚓"),       # "Confident because of source X"
    }
    return CITATION_STYLES.get(citation_type, ("white", "📌"))

# FUTURE (Agent Integration Phase): Learning signal citations
# def get_learning_citation_style(self, citation_type: CitationType) -> Tuple[str, str]:
#     """Return (color, icon) for learning signal citations (GOLD/ICK)"""
#     LEARNING_STYLES = {
#         CitationType.GOLD_REFERENCE: ("yellow bold", "⭐"),  # Trusted waypoint (>=0.8 confidence)
#         CitationType.ICK_REFERENCE: ("red", "💩"),           # Anti-pattern marker (<=0.3 confidence)
#     }
#     return LEARNING_STYLES.get(citation_type, ("dim", "❓"))

def get_agent_availability_style(self, availability: AgentAvailability) -> Tuple[str, str]:
    """Return (color, icon) for agent availability display"""
    AVAILABILITY_STYLES = {
        AgentAvailability.AVAILABLE: ("green", "🟢"),
        AgentAvailability.BUSY: ("yellow", "🟡"),
        AgentAvailability.OFFLINE: ("dim", "⚫"),
    }
    return AVAILABILITY_STYLES.get(availability, ("dim", "❓"))
```

### Category 4: OZOLITH/Audit UI (Delegate to OzolithRenderer)

**IMPORTANT:** ozolith.py already has `OzolithRenderer` class (lines 896-1097) with display methods.
UIHandler should DELEGATE to this rather than duplicate logic.

**OzolithRenderer methods to integrate:**
```python
# Already exists in ozolith.py - OzolithRenderer class
render_entry(entry, compact=False)     # Single entry display
render_chain(entries, compact=True)    # Timeline of entries
render_context_history(context_id)     # Everything in one sidebar
render_around_error(error_seq, window) # Forensics view
render_anchor(anchor)                  # Anchor summary
render_verification_report(result)     # Chain verification
render_stats()                         # Overall statistics
```

**UIHandler wrapper methods needed:**
```python
def show_audit_status(self, ozolith: Ozolith):
    """Display OZOLITH stats using OzolithRenderer"""
    renderer = OzolithRenderer(ozolith)
    self.console.print(renderer.render_stats())

def show_ozolith_event(self, entry: OzolithEntry, compact: bool = True):
    """Display single OZOLITH event using OzolithRenderer"""
    renderer = OzolithRenderer(entry._ozolith)  # or pass ozolith
    self.console.print(renderer.render_entry(entry, compact=compact))

def show_error_forensics(self, ozolith: Ozolith, error_seq: int, window: int = 5):
    """Display entries around an error for debugging"""
    renderer = OzolithRenderer(ozolith)
    self.console.print(renderer.render_around_error(error_seq, window))

def show_verification_result(self, ozolith: Ozolith):
    """Display chain verification results"""
    renderer = OzolithRenderer(ozolith)
    result = ozolith.verify_chain()
    self.console.print(renderer.render_verification_report(result))
```

**OZOLITH Helper Functions (lines 1317-2030) - for /audit command:**
```python
# Correction system
log_correction(oz, original_seq, what_was_wrong, correction_type)
log_correction_validated(oz, original_seq, what_was_wrong, reasoning, ...)
confirm_correction(oz, correction_seq, confirmed_by, notes)
validate_correction_target(oz, original_seq, what_was_wrong, reasoning)
audit_corrections(oz)          # Returns categorized issues
correction_analytics(oz)       # Detailed analytics

# Analysis helpers
log_uncertainty(oz, context_id, reason, details)
export_incident(oz, sequence, window)
session_summary(oz, session_start_seq)
find_learning_opportunities(oz)
```

### Category 5: Memory/Emergency UI (Future Phase 4)

```python
def show_memory_pressure_warning(self, pressure: float, buffer_status: str):
    """Display memory pressure indicator"""

def show_emergency_mode(self, reason: str, cached_sidebars: int):
    """Display emergency cache mode indicator"""

def show_recovery_needed(self, unresolved_count: int, details: List[Dict]):
    """Display startup recovery alert"""
```

---

## Implementation Order

### Phase A: Move Existing Code (No New Logic)
Move display code from rich_chat.py to UIHandler without changing behavior.

1. Conversation UI methods (4 methods, ~70 lines)
2. Sidebar UI methods (8 methods, ~120 lines)
3. Toggle feedback methods (2 methods, ~25 lines)
   - `show_fiwb_toggle(is_on: bool)` - FUCK IT WE BALL mode Panel with status, color, description
   - `show_error_panel_toggle(is_on: bool)` - Error panel status message

**Future:** These toggles are candidates for React "idiot light" GUI switches with color state indicators.

**Result:** rich_chat.py delegates all display, UIHandler owns rendering

### Phase B: Add All Styling Helpers
Add styling helpers for all enums defined in datashapes.py.

1. `get_status_style(SidebarStatus)` - 10 sidebar states
2. `get_event_style(OzolithEventType)` - OZOLITH event types
3. `get_priority_style(SidebarPriority)` - 5 priority levels
4. `get_agent_availability_style(AgentAvailability)` - 3 availability states
5. `get_citation_style(CitationType)` - basic citation types (not GOLD/ICK)
6. Update all sidebar display methods to use consistent styling

**Result:** Consistent styling across all enum-driven displays

### Phase C: OZOLITH Integration (B.5 - Apply Learnings from B)
Add audit trail visibility for debugging. Apply styling patterns learned in Phase B.

1. show_audit_status() - status bar indicator
2. show_ozolith_event() - debug mode event display
3. Delegate to OzolithRenderer for complex displays

**Result:** Visibility into OZOLITH activity

### Phase D: Emergency/Memory UI (Wire to Existing Backend)
Backend already exists in recovery_monitoring.py and rich_chat.py. Wire UIHandler to display these states.

**Existing backend:**
- `recovery_monitoring.py:67` - emergency_modes dict (backlog_explosion, cascade_failure, memory_pressure, disk_critical)
- `recovery_monitoring.py:470` - handle_memory_pressure()
- `recovery_monitoring.py:482` - check_disk_space() with staged alerts
- `rich_chat.py:630` - check_memory_pressure() triggers distillation

**UIHandler methods to add:**
1. Memory pressure indicators (wire to rich_chat.check_memory_pressure)
2. Emergency mode display (wire to recovery_monitoring.emergency_modes)
3. Disk space alerts (wire to recovery_monitoring.check_disk_space)

**Result:** Full UI support for existing emergency/memory systems

---

## Testing Requirements

### Unit Tests (Before Integration)

**Styling Helpers (Phase B):**
```python
# SidebarStatus styling
def test_get_status_style_returns_tuple():
    """Each status returns (color, icon) tuple"""

def test_all_statuses_have_styles():
    """No KeyError for any SidebarStatus value (all 10 states)"""

# OzolithEventType styling
def test_get_event_style_returns_tuple():
    """Each event type returns (color, icon) tuple"""

def test_all_event_types_have_styles():
    """No KeyError for any OzolithEventType value"""

# SidebarPriority styling
def test_get_priority_style_returns_tuple():
    """Each priority returns (color, icon) tuple"""

def test_all_priorities_have_styles():
    """No KeyError for any SidebarPriority value (all 5 levels)"""

# CitationType styling (basic types only)
def test_get_citation_style_returns_tuple():
    """Each citation type returns (color, icon) tuple"""

def test_basic_citation_types_have_styles():
    """CONTEXTUAL_BOOKMARK, DOCUMENT_LINK, RELATIONSHIP_MARKER, CONFIDENCE_ANCHOR all styled"""

def test_gold_ick_citations_return_default():
    """GOLD_REFERENCE and ICK_REFERENCE return default style (deferred to Agent phase)"""

# AgentAvailability styling
def test_get_agent_availability_style_returns_tuple():
    """Each availability returns (color, icon) tuple"""

def test_all_availabilities_have_styles():
    """No KeyError for any AgentAvailability value (all 3 states)"""
```

**Conversation UI (Phase A):**
```python
def test_show_new_conversation_panel_renders():
    """Panel displays with old/new conversation info"""

def test_show_conversation_list_empty():
    """Graceful display when no conversations"""

def test_show_conversation_list_with_data():
    """Table renders with conversation data"""

def test_show_conversation_not_found():
    """Error panel displays for missing conversation"""

def test_show_conversation_switched():
    """Success panel displays with switch info"""
```

**Sidebar UI (Phase A):**
```python
def test_show_sidebar_spawned():
    """Spawn notification displays with all parameters"""

def test_show_sidebar_response():
    """Response panel displays with sidebar ID"""

def test_show_merge_complete():
    """Merge notification displays with result data"""

def test_show_context_tree_handles_empty():
    """Graceful display when no contexts"""

def test_show_context_tree_handles_deep_nesting():
    """Renders 5+ levels without breaking"""

def test_show_context_tree_shows_active_indicator():
    """Active context is visually distinguished"""
```

**Toggle Feedback (Phase A):**
```python
def test_show_fiwb_toggle_on():
    """FIWB ON shows red panel with 🎱 and feature list"""

def test_show_fiwb_toggle_off():
    """FIWB OFF shows green panel with 🔇"""

def test_show_error_panel_toggle_on():
    """Error panel ON shows status message"""

def test_show_error_panel_toggle_off():
    """Error panel OFF shows status message"""
```

**OZOLITH Display (Phase C):**
```python
def test_show_audit_status_delegates_to_renderer():
    """Uses OzolithRenderer.render_stats()"""

def test_show_ozolith_event_compact():
    """Compact mode renders single line"""

def test_show_ozolith_event_full():
    """Full mode renders detailed entry"""

def test_show_error_forensics():
    """Renders entries around error with window"""
```

**Emergency/Memory UI (Phase D):**
```python
def test_show_memory_pressure_warning():
    """Displays pressure percentage and buffer status"""

def test_show_emergency_mode_displays_reason():
    """Shows which emergency mode triggered and why"""

def test_show_disk_space_alert_staged():
    """Different display for info/warning/critical/emergency levels"""
```

### Integration Tests (After Delegation)

**Conversation UI Delegation:**
```python
def test_start_new_conversation_uses_ui_handler():
    """rich_chat.start_new_conversation calls ui_handler.show_new_conversation_panel"""

def test_list_conversations_uses_ui_handler():
    """rich_chat.list_conversations calls ui_handler.show_conversation_list"""

def test_switch_conversation_uses_ui_handler():
    """rich_chat.switch_conversation calls ui_handler methods for success/failure"""
```

**Sidebar UI Delegation:**
```python
def test_spawn_sidebar_uses_ui_handler():
    """rich_chat.spawn_sidebar calls ui_handler.show_sidebar_spawned"""

def test_merge_sidebar_uses_ui_handler():
    """rich_chat.merge_current_sidebar calls ui_handler.show_merge_complete"""

def test_show_context_tree_uses_ui_handler():
    """rich_chat.show_context_tree calls ui_handler.show_context_tree"""
```

**Toggle Delegation:**
```python
def test_fiwb_toggle_uses_ui_handler():
    """rich_chat.toggle_fuck_it_we_ball_mode calls ui_handler.show_fiwb_toggle"""

def test_error_panel_toggle_uses_ui_handler():
    """rich_chat.toggle_error_panel calls ui_handler.show_error_panel_toggle"""
```

**No Direct Console.print Verification:**
```python
def test_no_direct_console_print_in_conversation_methods():
    """Grep for self.console.print in conversation methods returns 0"""

def test_no_direct_console_print_in_sidebar_methods():
    """Grep for self.console.print in sidebar methods returns 0"""

def test_no_direct_console_print_in_toggle_methods():
    """Grep for self.console.print in toggle methods returns 0"""
```

### Edge Case / Error Handling Tests

```python
# Graceful handling of None/missing data
def test_show_sidebar_spawned_handles_none_parent():
    """Displays correctly when parent_id is None (root sidebar)"""

def test_show_conversation_list_handles_malformed_data():
    """Doesn't crash on missing keys in conversation dicts"""

def test_get_status_style_handles_unknown_status():
    """Returns default style for unrecognized status (future-proofing)"""

def test_show_context_tree_handles_circular_reference():
    """Detects and handles circular parent references without infinite loop"""

# OzolithRenderer availability
def test_ozolith_display_graceful_without_renderer():
    """Falls back to simple display if OzolithRenderer unavailable"""

# Toggle state consistency
def test_toggle_display_matches_actual_state():
    """Display reflects actual toggle state, not stale value"""
```

### Testing Protocol Note

Per CLAUDE.md two-stage testing protocol:

**Stage 1: Unit Logic Testing** (covered above)
- Test UIHandler methods in isolation
- Verify return values, state changes, no crashes

**Stage 2: In-Field Simulation** (manual + integration)
- Test full command flow: `/sidebar spawn` → rich_chat → UIHandler → display
- Verify visual output matches expectations
- Run actual chat session with all toggles exercised

**Why both:** Unit tests catch logic bugs. Integration tests catch wiring bugs. Manual testing catches UX issues that automated tests miss.

---

## Dependencies

### Required Before Phase A:
- [x] UIHandler exists and working (`ui_handler.py:17`)
- [x] rich_chat.py uses UIHandler for some operations (10+ calls verified)
- [x] ConversationOrchestrator working (`conversation_orchestrator.py:60`)

### Required Before Phase B:
- [x] SidebarStatus enum (`datashapes.py:25`)
- [x] SidebarPriority enum (`datashapes.py:42`)
- [x] AgentAvailability enum (`datashapes.py:51`)
- [x] OzolithEventType enum (`datashapes.py:362`)
- [x] CitationType enum (`datashapes.py:2259`)

### Required Before Phase C:
- [x] OZOLITH implemented (`ozolith.py:78`)
- [x] OzolithRenderer exists (`ozolith.py:896`)
- [x] ConversationManager uses OZOLITH (imports + lazy loading)

### Required Before Phase D:
- [x] Memory pressure detection (`rich_chat.py:630`, `recovery_monitoring.py:383-389`)
- [x] Emergency modes system (`recovery_monitoring.py:67-72` - 4 modes)
- [x] Disk space alerts (`recovery_monitoring.py:482`)

**Status:** All dependencies met. Ready to implement all phases.

---

## Questions to Resolve

### 1. Should UIHandler import SidebarStatus directly?
**Options:**
- Option A: Yes, UIHandler knows about sidebar statuses (direct import)
- Option B: No, pass status as string, UIHandler has its own mapping

**RESOLVED:** Option A - Direct import

**Decision:** UIHandler imports SidebarStatus (and other enums) directly from datashapes.py

**Why:**
- Type-safe: IDE autocomplete, compile-time error catching
- Single source of truth: enum definition lives in one place
- Testable: can iterate over all values with `for s in SidebarStatus`
- Cleaner: no string mapping to maintain separately

### 2. Context tree rendering - Rich Tree vs custom?
**Options:**
- Option A: Keep Rich.Tree as-is
- Option B: Abstract into custom tree renderer

**RESOLVED:** Option A - Keep Rich.Tree, don't abstract

**Decision:** Continue using Rich.Tree for context tree rendering (`rich_chat.py:1186`)

**Why:**
- Already works well
- Rich handles terminal width, colors, unicode box-drawing
- Abstracting adds complexity with no current benefit
- If we switch UI libraries later, we'd rewrite anyway

**Future Enhancement (noted):** Make context tree renderable to separate UI section / expandable item for:
- Quick glance during audits
- Future "poison tracing" tooling for sidebar context windows
- Don't over-engineer now - more features planned for this section later

### 3. How much OZOLITH visibility in UI?
**Options:**
- Option A: Status bar only (minimal)
- Option B: Debug mode shows all events
- Option C: Dedicated /audit command

**RESOLVED:** Option B + C

**Decision:** Debug mode shows events live + dedicated /audit command for deep dive

**Why:**
- Maximum visibility for both {US}
- Debug mode: see events as they happen during development/troubleshooting
- /audit command: forensic deep dive when needed, doesn't clutter normal usage
- Aligns with Phase C implementation plan

---

## Success Criteria

### Phase A Complete When:
**Conversation UI:**
- [ ] Zero `self.console.print` calls in conversation methods of rich_chat.py
- [ ] `show_new_conversation_panel()` delegated to UIHandler
- [ ] `show_conversation_list()` delegated to UIHandler
- [ ] `show_conversation_switched()` delegated to UIHandler
- [ ] `show_conversation_not_found()` delegated to UIHandler

**Sidebar UI:**
- [ ] Zero `self.console.print` calls in sidebar methods of rich_chat.py
- [ ] `show_sidebar_spawned()` delegated to UIHandler
- [ ] `show_merge_complete()` delegated to UIHandler
- [ ] `show_context_tree()` delegated to UIHandler
- [ ] All 8 sidebar display methods use UIHandler

**Toggle Feedback:**
- [ ] `show_fiwb_toggle()` delegated to UIHandler
- [ ] `show_error_panel_toggle()` delegated to UIHandler
- [ ] Zero `self.console.print` calls in toggle methods

**General:**
- [ ] Existing tests still pass
- [ ] Visual output unchanged from user perspective

### Phase B Complete When:
**Styling Helpers Implemented:**
- [ ] `get_status_style(SidebarStatus)` - all 10 states styled
- [ ] `get_event_style(OzolithEventType)` - all event types styled
- [ ] `get_priority_style(SidebarPriority)` - all 5 levels styled
- [ ] `get_agent_availability_style(AgentAvailability)` - all 3 states styled
- [ ] `get_citation_style(CitationType)` - 4 basic types styled (not GOLD/ICK)

**Integration:**
- [ ] All sidebar display methods use `get_status_style()` for consistent colors/icons
- [ ] Context tree shows status with correct styling
- [ ] Status colors/icons match UNIFIED_SIDEBAR_ARCHITECTURE.md

### Phase C Complete When:
**OZOLITH Visibility:**
- [ ] OZOLITH activity visible when debug mode enabled
- [ ] `/audit` command shows event history
- [ ] Events use `get_event_style()` for consistent display

**OzolithRenderer Delegation:**
- [ ] `show_audit_status()` delegates to `OzolithRenderer.render_stats()`
- [ ] `show_ozolith_event()` delegates to `OzolithRenderer.render_entry()`
- [ ] `show_error_forensics()` delegates to `OzolithRenderer.render_around_error()`
- [ ] No duplicated render logic between UIHandler and OzolithRenderer

### Phase D Complete When:
**Memory Pressure:**
- [ ] Memory pressure percentage visible in UI
- [ ] Buffer status displayed (current/limit)
- [ ] Wired to `rich_chat.check_memory_pressure()`

**Emergency Modes:**
- [ ] All 4 emergency modes displayable (backlog_explosion, cascade_failure, memory_pressure, disk_critical)
- [ ] Clear indication of which mode triggered and why
- [ ] Wired to `recovery_monitoring.emergency_modes`

**Disk Alerts:**
- [ ] Staged alerts display correctly (info → warning → critical → emergency)
- [ ] Wired to `recovery_monitoring.check_disk_space()`

**Recovery:**
- [ ] Startup recovery prompts work
- [ ] Recovery results displayed clearly

---

## Reference: Confidence Display Trace

**Source:** Confidence comes from `validation_data`, not just episodic memory.

### React Layer (Rich Display)
| File | Line | What |
|------|------|------|
| `src/App.tsx` | 16 | Message interface has `confidence_score?: number` |
| `src/App.tsx` | 227-235 | `getConfidenceInfo(score)` - returns color/label/icon |
| `src/App.tsx` | 266 | Captures `confidence_score` from backend data |
| `src/App.tsx` | 408-414 | Renders inline with messages |

### React Confidence Thresholds
| Score | Color | Label | Icon |
|-------|-------|-------|------|
| >= 0.9 | Green (#10b981) | High confidence | ● |
| >= 0.7 | Cyan (#22d3ee) | Good confidence | ● |
| >= 0.5 | Yellow (#fbbf24) | Medium confidence | ◐ |
| >= 0.3 | Orange (#fb923c) | Low confidence | ◔ |
| < 0.3 | Red (#ef4444) | Very uncertain | ○ |

### Backend Flow
| File | Line | What |
|------|------|------|
| `api_server_bridge.py` | 68 | ChatResponse dataclass has `confidence_score` |
| `api_server_bridge.py` | 259 | Gets from `validation_data.get('confidence_score')` |
| `api_server_bridge.py` | 282 | Returns to React |
| `conversation_file_management.py` | 41 | StoredMessage has `confidence_score` |
| `rich_chat.py` | 596 | Gets from `validation.get('confidence_score')` |

### CLI Layer (Simple Display)
| File | Line | What |
|------|------|------|
| `ui_handler.py` | 454-473 | `render_response()` takes optional `confidence_score` |
| `ui_handler.py` | 472-473 | Displays as "Confidence: 0.XX" in metadata |

**Note:** React has rich color-coded display; CLI has simpler text display. Consider adding color thresholds to CLI for parity (future enhancement, not blocking).

---

## Revision History
- 2025-12-19: Initial PRD created
- 2025-12-19: Added citation type split (basic now, GOLD/ICK deferred to Agent phase)
- 2025-12-19: Added confidence display trace reference
- 2025-12-24: Comprehensive review with operator
  - Expanded Phase B to include all 5 styling helpers
  - Added toggle feedback methods (FIWB, error panel) to Phase A
  - Verified all dependencies exist with file:line references
  - Phase D updated: backend already exists, just needs UIHandler wiring
  - Resolved all 3 questions with options preserved and reasoning documented
  - Expanded Success Criteria to ~38 checkboxes across all phases
  - Added edge case tests and testing protocol note
  - Updated roadmap with Procedural Validation task and citation notes
- 2025-12-24: **DEPRIORITIZED** - Pivot to visibility/event stream work
  - Operator uses React, not CLI - UIHandler extraction low value for their use case
  - New priority: VISIBILITY_STREAM_PRD.md for React event visibility
  - This PRD remains valid for future CLI cleanup work
  - Useful sections preserved: enum definitions, dependency verification, confidence trace
