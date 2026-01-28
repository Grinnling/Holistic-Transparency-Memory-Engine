# CODE_IMPLEMENTATION File Structure

**Last Updated:** December 18, 2025
**Purpose:** So Claude stops guessing what files do

---

## Quick Reference

### Core Orchestration
| File | Lines | What It Does |
|------|-------|--------------|
| `rich_chat.py` | 1496 | Main orchestrator - coordinates everything |
| `datashapes.py` | 2396 | ALL data structures, enums, payloads |

### Conversation System
| File | Lines | What It Does |
|------|-------|--------------|
| `conversation_manager.py` | 782 | Conversation persistence + OZOLITH events |
| `conversation_orchestrator.py` | 772 | Sessions, sidebars, context tree |
| `conversation_file_management.py` | 503 | File-based conversation storage |
| `context_registry.py` | 893 | Context tracking |

### Audit Trail
| File | Lines | What It Does |
|------|-------|--------------|
| `ozolith.py` | 2107 | Immutable append-only audit log |

### Memory System
| File | Lines | What It Does |
|------|-------|--------------|
| `memory_handler.py` | 603 | Memory operations |
| `memory_distillation.py` | 474 | Memory compression/summarization |
| `episodic_memory_coordinator.py` | 502 | Episodic memory coordination |

### UI Layer
| File | Lines | What It Does |
|------|-------|--------------|
| `ui_handler.py` | 533 | Display rendering (Rich library) |
| `command_handler.py` | 398 | Command routing (/tokens, /help, etc.) |

### Error & Services
| File | Lines | What It Does |
|------|-------|--------------|
| `error_handler.py` | 477 | Error management and routing |
| `service_manager.py` | 680 | Service lifecycle (start/stop/health) |
| `service_connector.py` | 393 | Service connections |

### LLM & API
| File | Lines | What It Does |
|------|-------|--------------|
| `llm_connector.py` | 428 | LLM communication |
| `api_server_bridge.py` | 597 | API layer |

### Recovery System
| File | Lines | What It Does |
|------|-------|--------------|
| `recovery_thread.py` | 840 | Recovery threading |
| `recovery_monitoring.py` | 770 | Recovery monitoring |
| `recovery_chat_commands.py` | 429 | Recovery commands |

### Utilities
| File | Lines | What It Does |
|------|-------|--------------|
| `skinflap_stupidity_detection.py` | 551 | Query validation (is user being vague?) |
| `emergency_backup.py` | 384 | Backup system |

---

## Directories

| Directory | What's In It |
|-----------|--------------|
| `stash/` | Files stashed for later review (don't delete) |
| `stash/august_2025_review/` | August 2025 files pending integration review |
| `stash/refactor_history/` | Superseded refactoring docs (see REFACTOR_STATUS.md) |
| `deprecated/` | Dead code (safe to ignore) |
| `src/` | React/TypeScript frontend (NOT Python) |
| `tests/` | Test files |
| `data/` | Data files |

---

## Stashed Files (Review Later)

### stash/august_2025_review/
- `advanced_orchestration_functions.py` - Multi-agent orchestration, progress tracking, context continuation (REVIEW FOR INTEGRATION)
- `enhanced_chat.py` - Legacy predecessor to rich_chat.py
- `chat_interface.py` - Legacy predecessor to rich_chat.py

See `stash/august_2025_review/README.md` for details.

### stash/refactor_history/
Superseded refactoring docs consolidated into `REFACTOR_STATUS.md`. See that file for current state.

---

## How Things Connect

```
User Input
    ↓
rich_chat.py (orchestrator)
    ├── command_handler.py (if starts with /)
    ├── skinflap_stupidity_detection.py (validate query)
    ├── conversation_manager.py (get context)
    │   ├── conversation_orchestrator.py (session/sidebar logic)
    │   │   └── ozolith.py (audit trail)
    │   └── service_manager.py (health checks)
    ├── memory_handler.py (retrieve memories)
    ├── llm_connector.py (generate response)
    ├── ui_handler.py (display response)
    └── error_handler.py (if anything fails)
```

---

## Refactoring Status

**Current:** Backend refactoring ~60% complete (Dec 2025)

**Done:**
- ServiceManager extracted
- UIHandler extracted
- CommandHandler extracted
- ErrorHandler extracted
- MemoryHandler extracted
- ConversationManager extracted (Dec 2025)
- OZOLITH built (Dec 2025)

**Remaining (optional):**
- ResponseEnhancer (~125 lines)
- ChatLogger (~37 lines)
- OrchestratorUIHandler (~310 lines)

**Pending Integration:**
- Multi-agent orchestration from `stash/august_2025_review/`

---

## When Final Integration Happens

All files will move to organized directories. Until then, this flat structure with READMEs is the workaround.

Target structure (future):
```
CODE_IMPLEMENTATION/
├── core/           # Orchestration, datashapes
├── conversation/   # Conversation system
├── memory/         # Memory system
├── ui/             # UI layer
├── services/       # Service management
├── audit/          # OZOLITH
└── agents/         # Multi-agent (from stash)
```
