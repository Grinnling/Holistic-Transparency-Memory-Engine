# SITREP: Sidebar/Conversation Architecture Document Review

**Date:** 2025-12-02
**Purpose:** Consolidate 5 documents about sidebar/conversation/agent architecture into one unified reference
**Requesting Instance:** CODE_IMPLEMENTATION
**For:** Information Review Instance

---

## Documents to Review

### 1. My Sketch (Simplest, Start Here)
**Path:** `/home/grinnling/Development/CODE_IMPLEMENTATION/CONVERSATION_ORCHESTRATOR_ARCHITECTURE.md`
**Lines:** ~405
**What it covers:**
- Basic sidebar branching concept
- ConversationNode dataclass with 4 states (ACTIVE, PAUSED, MERGED, ARCHIVED)
- ConversationOrchestrator class outline
- User commands (/sidebar, /merge, /back, /focus)
- 5-phase implementation plan
- Questions to resolve

**Limitation:** Simplified subset of what the other docs contain. Missing citation system, memory separation details, trust evolution, emergency procedures.

---

### 2. WebSocket Message Types (Schema/Types Only)
**Path:** `/home/grinnling/Downloads/WebSocket_Message_Types___Schema.txt`
**Lines:** ~241
**What it covers:**
- TypeScript interfaces for ALL WebSocket message types
- BaseMessage interface (type, timestamp, id, source)
- ChatMessage with citations array
- ErrorMessage with severity and user_impact
- ServiceStatus, MemoryUpdate, ConversationEvent, MediaEvent
- Citation interface (source, content, relevance_score, type)
- Type guards and createMessage helper

**Key for consolidation:** This defines the DATA SHAPES, not the behavior. Other docs reference these types.

---

### 3. Citation-Based Sidebar Checklist (Implementation Tasks)
**Path:** `/home/grinnling/Downloads/Citation-Based_Sidebar_System_Implementation_Checklist.md`
**Lines:** ~295
**What it covers:**
- 5-phase implementation checklist with checkboxes
- Phase 1: Memory-aware citation system (highlight detection, right-click menu)
- Phase 2: Sidebar branching with memory integration
- Phase 3: File citation & listening, context versioning
- Phase 4: Full memory curator integration
- Phase 5: Pause system, visualization
- "This is gold" trigger for immediate episodic archival
- Emergency backup integration
- Memory confidence inheritance throughout

**Key for consolidation:** This is the CHECKLIST version - what needs to be built. Heavy memory system integration focus.

---

### 4. Multi-Agent Architecture (Conceptual Design)
**Path:** `/home/grinnling/Development/STORAGE/Artifacts_Archive/architecture/updated_multi_agent_architecture.md`
**Lines:** ~423
**What it covers:**
- Forum-style collaboration concept
- "Not The Borg" - agents maintain individuality
- Local-first economics argument (why cloud can't do this)
- SidebarCollaboration Python class with:
  - immutable_source
  - live_conversation
  - citations dictionary
  - add_message(), ask_question(), add_citation(), break_tie()
- Context format translation layer (JSON vs Protobuf vs Custom)
- "Context Presentation Instead of Translation" concept
- Hardware scaling architecture (Turing Pi, Cyberdeck)

**Key for consolidation:** This is the PHILOSOPHY and WHY. Explains the collaborative model between agents.

---

### 5. WebSocket Architecture (Most Comprehensive)
**Path:** `/home/grinnling/Development/docs/github/repo/MARKDOWNS/websocket_architecture.md`
**Lines:** ~1500+
**What it covers:**
- SidebarContext dataclass with 10 states:
  - ACTIVE, TESTING, PAUSED, WAITING, REVIEWING
  - SPAWNING_CHILD, CONSOLIDATING, MERGED, ARCHIVED, FAILED
- Memory separation: inherited_memory vs local_memory
- fork_sidebar(), spawn_child_sidebar(), merge_back_to_parent()
- Citation system: [MSG-X] for messages, [CITE-X] for artifacts
- Backpressure handling, circuit breakers
- Tool chain supervision with mandatory audit logging
- Trust evolution system (agents earn autonomy)
- Complete data flow examples
- WebSocket connection management
- Error handling patterns

**Key for consolidation:** This is the DETAILED SPEC. Most complete but also most overwhelming.

---

## What Needs Consolidation

### Overlap Areas (Same Concept, Different Detail Levels)
| Concept | My Sketch | Checklist | Multi-Agent | WebSocket Arch |
|---------|-----------|-----------|-------------|----------------|
| Sidebar states | 4 basic | implied | implied | 10 detailed |
| Memory separation | mentioned | detailed | mentioned | detailed |
| Citation system | none | detailed | detailed | detailed |
| Agent collaboration | basic | memory-focused | philosophy | implementation |
| Emergency procedures | none | detailed | none | detailed |
| Trust evolution | none | none | mentioned | detailed |

### Potential Conflicts to Check
1. **State names** - Do the 10 states in websocket_architecture.md align with what checklist expects?
2. **Memory integration** - Checklist is very memory-curator focused. Does websocket_architecture.md assume same integration?
3. **Citation format** - Is [MSG-X]/[CITE-X] consistent across all docs?
4. **Agent model** - Multi-agent doc has SidebarCollaboration class. WebSocket doc has SidebarContext. Are these the same thing with different names?

### Missing From All Docs
- How does this connect to current rich_chat.py code?
- Migration path from current simple conversation model
- React UI implementation details (backend focused)

---

## Requested Output

A single consolidated document that:
1. Defines the unified data model (states, structures)
2. Lists implementation phases with checklist items
3. Explains the philosophy (why this design)
4. Notes any conflicts found and resolution decisions
5. Keeps technical detail but organizes it better than 1500 lines in one file

---

## File Locations Summary

```
TO REVIEW:
/home/grinnling/Development/CODE_IMPLEMENTATION/CONVERSATION_ORCHESTRATOR_ARCHITECTURE.md
/home/grinnling/Downloads/WebSocket_Message_Types___Schema.txt
/home/grinnling/Downloads/Citation-Based_Sidebar_System_Implementation_Checklist.md
/home/grinnling/Development/STORAGE/Artifacts_Archive/architecture/updated_multi_agent_architecture.md
/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/websocket_architecture.md

OUTPUT LOCATION (suggestion):
/home/grinnling/Development/CODE_IMPLEMENTATION/UNIFIED_SIDEBAR_ARCHITECTURE.md
```

---

## Notes for Review Instance

- The CODE_IMPLEMENTATION instance doesn't need every detail - we need a working reference we can actually use
- User preference: "distill/combine > replace"
- User gets overwhelmed by too many layers - aim for clarity over completeness
- Technical importance layers should be visible (what's critical vs nice-to-have)
- This will guide actual implementation in rich_chat.py refactoring

---

**Status:** Ready for information review and consolidation
