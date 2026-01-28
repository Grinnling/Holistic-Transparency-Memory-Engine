# Conversation Orchestrator Architecture
**Created:** November 25, 2025
**Status:** Planning/Sketch Phase
**Purpose:** Define the vision for parallel conversations, sidebars, and agent handoffs

---

## Vision Statement

Enable "hold that thought" workflows where users can:
- Branch into sidebar investigations without losing main context
- Have specialist agents handle specific tasks
- Merge findings back into the main conversation
- Run parallel conversations with different agents

---

## Current State (What We Have)

### Existing Code in rich_chat.py

| Method | Lines | What It Does | Limitations |
|--------|-------|--------------|-------------|
| `start_new_conversation` | 875-898 | Reset to fresh session | Abandons previous, no branching |
| `list_conversations` | 900-970 | Show past conversations | Display only, no relationships |
| `switch_conversation` | 973-1077 | Load different conversation | Complete switch, not parallel |
| `restore_conversation_history` | 233-315 | Load context on startup | Single conversation only |
| `get_recent_context_hint` | 835-862 | Extract topic hints | Helper, stays as-is |

### Current Data Model

```
conversation_id: uuid (single active)
conversation_history: List[Dict] (linear, in-memory)

Each exchange:
{
    'user': str,
    'assistant': str,
    'exchange_id': str,
    'timestamp': str,
    'source': 'working_memory' | 'episodic_memory' | 'current'
}
```

**Key Limitation:** One conversation at a time, no relationships between them.

---

## Proposed Architecture

### Core Concept: Conversation Tree

```
Main Conversation (root)
│
├── Exchange 1
├── Exchange 2
├── Exchange 3
│   └── [BRANCH POINT] "Hold that thought"
│       │
│       └── Sidebar A (child)
│           ├── Exchange A1 (inherits context from Exchange 3)
│           ├── Exchange A2
│           └── Exchange A3
│               └── [MERGE POINT] "Back to main"
│                   └── Summary injected into Main
│
├── Exchange 4 (continues with sidebar summary)
├── Exchange 5
│   └── [BRANCH POINT] "Let me check something"
│       │
│       ├── Sidebar B (specialist: code_reviewer)
│       │   └── (runs with code review agent)
│       │
│       └── Sidebar C (specialist: researcher)
│           └── (runs with research agent)
│
└── Exchange 6 (continues with both sidebar results)
```

### New Data Model

```python
@dataclass
class ConversationNode:
    """Single conversation thread"""
    conversation_id: str
    parent_id: Optional[str]  # None for root/main
    branch_point_exchange_id: Optional[str]  # Where it branched from
    agent_id: str  # Which agent handles this thread
    status: ConversationStatus  # ACTIVE, PAUSED, MERGED, ARCHIVED
    created_at: datetime

    # Context inheritance
    inherited_context: List[Exchange]  # Snapshot from parent at branch
    local_exchanges: List[Exchange]  # This thread's exchanges

    # Merge tracking
    merge_summary: Optional[str]  # Generated when merged back
    merged_at: Optional[datetime]

class ConversationStatus(Enum):
    ACTIVE = "active"      # Currently in use
    PAUSED = "paused"      # "Hold that thought" state
    MERGED = "merged"      # Findings returned to parent
    ARCHIVED = "archived"  # Stored in episodic memory
```

### ConversationOrchestrator Class

```python
class ConversationOrchestrator:
    """
    Manages conversation tree, agent assignments, and context flow.
    Replaces simple conversation_id + conversation_history model.
    """

    def __init__(self, error_handler, service_manager, agent_registry):
        self.conversations: Dict[str, ConversationNode] = {}
        self.active_conversation_id: str = None  # Currently focused
        self.agent_registry = agent_registry  # Available agents

    # === Conversation Lifecycle ===

    def start_main_conversation(self, agent_id: str = "general") -> str:
        """Start a new root conversation"""

    def branch_sidebar(self,
                       reason: str,
                       agent_id: Optional[str] = None,
                       inherit_last_n: int = 5) -> str:
        """
        "Hold that thought" - create child conversation

        Args:
            reason: Why we're branching ("research X", "check Y")
            agent_id: Specialist agent for sidebar (None = same as parent)
            inherit_last_n: How many parent exchanges to copy as context

        Returns:
            New sidebar conversation_id
        """

    def merge_sidebar(self,
                      sidebar_id: str,
                      summary: Optional[str] = None,
                      auto_summarize: bool = True) -> Dict:
        """
        Return to parent with findings

        Args:
            sidebar_id: The sidebar to merge
            summary: Manual summary (or auto-generate)
            auto_summarize: Use LLM to summarize sidebar findings

        Returns:
            Merge result with summary injected into parent
        """

    def switch_focus(self, conversation_id: str):
        """Change which conversation is "active" in UI"""

    def pause_conversation(self, conversation_id: str):
        """Pause without branching (just step away)"""

    def resume_conversation(self, conversation_id: str):
        """Resume a paused conversation"""

    # === Context Management ===

    def get_full_context(self, conversation_id: str) -> List[Exchange]:
        """Get inherited + local context for a conversation"""

    def get_context_for_llm(self, conversation_id: str) -> List[Dict]:
        """Format context for LLM consumption"""

    def inject_context(self, conversation_id: str, context: str, source: str):
        """Add external context (e.g., sidebar summary)"""

    # === Agent Management ===

    def assign_agent(self, conversation_id: str, agent_id: str):
        """Change which agent handles a conversation"""

    def get_conversation_agent(self, conversation_id: str) -> Agent:
        """Get the agent for a conversation"""

    # === Query/Navigation ===

    def list_active_conversations(self) -> List[ConversationNode]:
        """All non-archived conversations"""

    def list_sidebars(self, parent_id: str) -> List[ConversationNode]:
        """Get all sidebars for a conversation"""

    def get_conversation_tree(self, root_id: str) -> Dict:
        """Full tree structure for visualization"""
```

---

## User Interaction Patterns

### Pattern 1: Simple Sidebar

```
User: "Explain how the memory system works"
Assistant: [starts explaining...]

User: "/sidebar research"  # or "hold that thought, let me check something"
System: [Creates sidebar, inherits last 5 exchanges]
        [Switches focus to sidebar]
        "📌 Sidebar started. Main conversation paused."
        "What would you like to research?"

User: "What embedding models are available?"
Assistant: [researches in sidebar context...]

User: "/merge" or "/back"
System: [Summarizes sidebar findings]
        [Injects summary into main conversation]
        [Switches focus back to main]
        "📎 Sidebar merged. Summary added to context."

User: [continues main conversation with sidebar knowledge]
```

### Pattern 2: Specialist Agent Sidebar

```
User: "Review this code for security issues"
Assistant: "I can do a general review, or I can spin up the security specialist."

User: "/sidebar security-agent"
System: [Creates sidebar with security_reviewer agent]
        "🔒 Security review sidebar started with security-agent"

[Security agent does thorough review in sidebar]

User: "/merge"
System: [Security findings injected into main]
```

### Pattern 3: Parallel Sidebars

```
User: "I need to understand both the frontend and backend of this feature"

User: "/sidebar frontend-focus"
System: "📌 Frontend sidebar created"

User: "/sidebar backend-focus"
System: "📌 Backend sidebar created"

User: "/list"
System: Shows:
        - Main (paused)
        - Sidebar: frontend-focus (active)
        - Sidebar: backend-focus (paused)

User: "/focus main"
User: "/merge-all"
System: [Merges both sidebars into main]
```

---

## New Commands

| Command | Action |
|---------|--------|
| `/sidebar [name]` | Branch into new sidebar |
| `/sidebar [name] --agent [agent-id]` | Sidebar with specialist |
| `/back` or `/merge` | Return to parent with summary |
| `/merge --no-summary` | Return without auto-summary |
| `/focus [id]` | Switch active conversation |
| `/pause` | Pause current, go to parent |
| `/tree` | Show conversation tree |
| `/list` | Show all active conversations |

---

## Agent Registry (Future)

```python
class AgentRegistry:
    """Registry of available agents"""

    agents = {
        "general": GeneralAssistant,
        "code_reviewer": CodeReviewAgent,
        "security": SecurityAuditAgent,
        "researcher": ResearchAgent,
        "debugger": DebugAgent,
        "planner": PlanningAgent,
    }

    def get_agent(self, agent_id: str) -> Agent:
        """Get agent instance by ID"""

    def list_available(self) -> List[str]:
        """List available agent types"""
```

---

## Implementation Phases

### Phase 1: Extract & Preserve (Current - Stabilization)
- [ ] Extract current conversation methods to `ConversationSessionManager`
- [ ] Keep current functionality working exactly as-is
- [ ] Add data model for `ConversationNode` (not used yet, just defined)
- [ ] No user-facing changes

### Phase 2: Single Sidebar Support
- [ ] Add `parent_id` tracking to conversations
- [ ] Implement `/sidebar` and `/back` commands
- [ ] Context inheritance (copy last N exchanges)
- [ ] Basic merge (manual summary)
- [ ] UI shows "main" vs "sidebar" indicator

### Phase 3: Agent Assignment
- [ ] Create `AgentRegistry` stub
- [ ] Allow `/sidebar --agent X` syntax
- [ ] Different agents handle different sidebars
- [ ] Agent identity shown in UI

### Phase 4: Parallel Sidebars
- [ ] Multiple active sidebars
- [ ] `/focus` command to switch
- [ ] `/merge-all` to combine multiple
- [ ] Tree visualization (`/tree`)

### Phase 5: Auto-Summary & Intelligence
- [ ] LLM-generated merge summaries
- [ ] Smart context inheritance (relevance-based, not just last N)
- [ ] Sidebar suggestions ("This seems like a tangent, want to sidebar?")
- [ ] Auto-pause detection (conversation drift)

---

## Integration Points

### With Existing Systems

| System | Integration |
|--------|-------------|
| `MemoryHandler` | Each conversation archives separately, with parent links |
| `EpisodicMemoryCoordinator` | Store conversation trees, not just linear |
| `ErrorHandler` | Errors scoped to conversation, shown in right sidebar |
| `ServiceManager` | No change needed |
| `UIHandler` | New displays for tree, sidebar indicators |
| `CommandHandler` | New commands for sidebar/merge/focus |

### New Dependencies

| New Component | Purpose |
|---------------|---------|
| `ConversationOrchestrator` | Core tree management |
| `AgentRegistry` | Agent lookup and instantiation |
| `ContextBridge` | Manage context flow between conversations |
| `MergeSummarizer` | Generate summaries when merging |

---

## Questions to Resolve

1. **Context Size:** How much parent context does a sidebar inherit? All? Last N? Relevance-filtered?

2. **Merge Conflict:** What if sidebar contradicts main conversation knowledge?

3. **Deep Nesting:** Can sidebars have sidebars? (sidebar of sidebar of main)

4. **Persistence:** Do sidebars persist to episodic memory separately or only when merged?

5. **Agent Availability:** What happens if requested agent isn't available? Fallback to general?

6. **UI Complexity:** How do we show this in CLI vs React? Tree view? Tabs? Breadcrumbs?

---

## Success Criteria

When complete, user should be able to:

1. ✅ Say "hold that thought" and branch into investigation
2. ✅ Return to main conversation with findings preserved
3. ✅ Have specialist agents handle specific sidebars
4. ✅ See where they are in the conversation tree
5. ✅ Run multiple investigations in parallel
6. ✅ Not lose any context or work when branching/merging

---

## References

- Current code: `rich_chat.py` lines 233-315, 835-898, 900-1077
- Roadmap phase: "Agent Integration" (future phase)
- Related: `RICH_CHAT_REFACTORING_PRD.md` for extraction plan

---

**Next Step:** Extract current conversation methods as Phase 1, preserving exact current behavior, while this architecture doc guides future development.
