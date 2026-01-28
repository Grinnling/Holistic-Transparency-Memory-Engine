# Unified Sidebar Architecture
**Created:** 2025-12-02
**Status:** Active Development - Consolidated from 5 source documents
**Purpose:** Single reference for sidebar/conversation/agent collaboration system

---

## Source Documents Consolidated
1. `CONVERSATION_ORCHESTRATOR_ARCHITECTURE.md` - Initial sketch, basic concept
2. `WebSocket_Message_Types___Schema.txt` - TypeScript interfaces
3. `Citation-Based_Sidebar_System_Implementation_Checklist.md` - Implementation tasks
4. `updated_multi_agent_architecture.md` - Philosophy and "why"
5. `websocket_architecture.md` - Detailed specification

---

## 1. Vision & Philosophy

### What We're Building
A **symmetric collaboration system** where humans and agents have equal access to:
- Spin up sidebars (branched conversations)
- Recruit other agents into those sidebars
- Merge findings back to parent context
- Use the same citation/reference system

### Core Principles

**"Not The Borg"**
Each agent maintains individual thinking and personality. This is a research lab model - like university researchers with shared whiteboards - not a hive mind.

**Local-First Economics**
This architecture is financially impossible for cloud providers but perfect for local systems:
- Cloud: 5 models talking = 5x token costs + massive context windows = $$$
- Local: 5 models talking = same hardware cost + unlimited context = $0 per conversation

**Symmetric Tooling**
An agent deep in a research sidebar can think "I need the security agent's perspective" and pull them in directly. The human isn't always the orchestrator - anyone can spawn, recruit, and merge.

**Memory Integrity First**
The citation and sidebar system enhances the existing Working Memory → Episodic Memory flow. Memory integrity is critical infrastructure, not an afterthought.

---

## 2. Identification System

### Global Unique References
Every referenceable object gets a **globally unique ID** - not scoped to sidebar or conversation. This enables yarn-board style tracing across the entire system.

### ID Structure

```
Internal Storage:    UUID (collision-proof, distributed-safe)
Display Reference:   TYPE-{global_sequential} (human-readable)
```

| Type | Format | Example | Description |
|------|--------|---------|-------------|
| Message | `MSG-{n}` | `MSG-4521` | Any message in any conversation/sidebar |
| Citation | `CITE-{n}` | `CITE-892` | Artifact, document, code snippet, external source |
| Sidebar | `SB-{n}` | `SB-89` | A sidebar context |
| File | `FILE-{hash}` | `FILE-a3b2` | Referenced file with optional line range |
| Fragment | `FRAG-{n}` | `FRAG-156` | Working memory fragment |
| Exchange | `EXCH-{n}` | `EXCH-2341` | Full user/assistant exchange pair |
| Gold | `GOLD-{n}` | `GOLD-47` | Realignment waypoint (see below) |
| Agent | `AGENT-{id}` | `AGENT-security_001` | Agent identifier |

### Sequential Counter Rules
- Global counter across entire system (not per-sidebar)
- Higher number = happened later (natural chronological ordering)
- Once assigned, never changes
- Enables yarn-board tracing: "follow MSG-4521 to MSG-4525"

### Origin Tracking
Each reference carries metadata about where it was created:
```python
{
    "id": "MSG-4521",
    "uuid": "msg_7f3a9b2c-1234-5678-abcd-ef0123456789",
    "created_in": "SB-89",        # Which sidebar
    "created_by": "AGENT-research_001",  # Who created it
    "created_at": "2025-12-02T14:32:00Z"
}
```

---

## 3. GOLD Citations (Realignment Waypoints)

### Purpose
GOLD is not just "this is important" - it's **"this is a waypoint for navigation."**

When you discover something valuable - a root cause, a reusable test pattern, a key insight - you GOLD it so future agents/humans can realign when encountering similar problems.

### Use Case Example
1. Debugging a problem in System A
2. Discover root cause is Variable X
3. Design a test pattern that catches this
4. Run it against Systems B, C, D - it works
5. GOLD this because the pattern is reusable and Variable X is the key insight

### Data Structure

```python
@dataclass
class GoldCitation:
    gold_id: str                    # GOLD-{sequential}
    source_refs: List[str]          # What's being golded [MSG-4521, CITE-892, SB-89]
    key_insight: str                # "Variable X causes cascading auth failures"
    reuse_pattern: str              # "Test pattern: check auth state before/after X"
    trigger_conditions: List[str]   # "Similar symptoms: timeout + partial state"
    created_by: str                 # Agent or human who flagged it
    created_in: str                 # Which sidebar/conversation
    confidence: float               # How sure are we this is valuable
    times_referenced: int           # Usage counter - does this actually get reused?
```

### Trigger Conditions
The `trigger_conditions` field is the "when you see THIS, remember THIS exists" hook. When a future agent/human encounters similar symptoms, the system can surface: "Hey, GOLD-47 dealt with something like this."

---

## 4. Sidebar Data Model

### Core Structure

```python
@dataclass
class SidebarContext:
    # === Identity & Hierarchy ===
    sidebar_id: str                           # SB-{sequential}
    uuid: str                                 # Full UUID for internal use
    parent_context_id: Optional[str]          # None for root/main conversation
    child_sidebar_ids: List[str]              # Can have children (nested sidebars)
    forked_from: Optional[str]                # For revival of archived work

    # === Participants ===
    participants: List[str]                   # Agent IDs (human is also an "agent")
    coordinator_agent: Optional[str]          # Optional lead for complex tasks
    agent_capabilities: Dict[str, AgentCapability]  # What each agent can do

    # === Memory (Critical Separation) ===
    inherited_memory: List[Dict]              # From parent - READ ONLY snapshot
    local_memory: List[Dict]                  # What happens IN this sidebar
    data_refs: Dict[str, Any]                 # Referenced artifacts
    cross_sidebar_refs: List[str]             # Links to related sidebars

    # === Lifecycle ===
    status: SidebarStatus                     # See status table below
    priority: SidebarPriority                 # CRITICAL, HIGH, NORMAL, LOW, BACKGROUND
    created_at: datetime
    last_activity: datetime
    success_criteria: Optional[str]           # What "done" looks like
    failure_reason: Optional[str]             # Why it failed (if status=FAILED)
```

### Memory Separation (Critical Concept)

When a sidebar is created:
1. **Inherited Memory**: Snapshot of parent context (READ ONLY)
2. **Local Memory**: Everything that happens inside this sidebar
3. **On Merge**: Only local_memory gets consolidated into parent
4. **Result**: Parent context isn't polluted by sidebar exploration

```
Parent Conversation
├── Exchange 1
├── Exchange 2
├── Exchange 3 ←── [BRANCH POINT]
│                   │
│                   └── Sidebar SB-89
│                       ├── inherited_memory: [Exch 1, 2, 3] (frozen snapshot)
│                       ├── local_memory: [everything in sidebar]
│                       └── On MERGE: consolidate local → inject into parent
│
├── Exchange 4 (+ merged findings from SB-89)
└── ...
```

### Sidebar Status (10 States)

| State | Definition | Transitions To |
|-------|------------|----------------|
| **ACTIVE** | Doing real work | PAUSED, WAITING, SPAWNING_CHILD, CONSOLIDATING, FAILED |
| **TESTING** | Experimental/debug mode, mechanical testing, parallel instance comparison, frequent context exchange | ACTIVE (promote), ARCHIVED (discard), FAILED |
| **PAUSED** | Temporarily stopped, resumable ("hold that thought") | ACTIVE, ARCHIVED |
| **WAITING** | Blocked on human input or external dependency | ACTIVE (unblocked), FAILED (timeout) |
| **REVIEWING** | Agents validating results before consolidation | CONSOLIDATING (approved), ACTIVE (needs more work) |
| **SPAWNING_CHILD** | Creating sub-sidebars for complex tasks | ACTIVE (child created), WAITING (child working) |
| **CONSOLIDATING** | Collaboratively determining what to merge back (mutual extraction) | MERGED (success), ACTIVE (needs revision) |
| **MERGED** | Successfully integrated to parent | ARCHIVED |
| **ARCHIVED** | Stored in episodic memory, still citable | (terminal, but can be FORKED to new sidebar) |
| **FAILED** | Unrecoverable error | ARCHIVED (for reference) |

### TESTING vs ACTIVE
- **ACTIVE** = "doing real work that matters"
- **TESTING** = "experimental work that might be thrown away"

TESTING is for:
- Security issue investigation
- Implementation debugging
- Parallel instance comparison
- Frequent context exchange between test instances

TESTING results may need explicit "promote to real" action before merging.

### CONSOLIDATING vs MERGED
- **CONSOLIDATING** = Collaborative activity: "What's actually important from this sidebar?"
- **MERGED** = Completed state: "We've integrated findings into parent"

Consolidation can involve:
- Automated LLM summarization
- Agents discussing what to bring back
- Parent context agent reviewing: "Here's what we found, what's relevant to you?"

---

## 5. Agent Capabilities

```python
@dataclass
class AgentCapability:
    agent_id: str                           # AGENT-{identifier}
    specialties: List[str]                  # ["debugging", "research", "code_generation", "testing"]
    availability: str                       # "available", "busy", "offline"
    current_load: int                       # Number of active sidebars
    preferred_collaborators: Set[str]       # Agents this one works well with
```

---

## 6. WebSocket Message Types

### Message Categories Overview

All messages extend a base structure:
```typescript
interface BaseMessage {
    message_id: string;      // UUID for deduplication
    timestamp: string;
    sender_agent_id?: string;
}
```

### 6.1 Sidebar Operations

| Message Type | Purpose | Key Fields |
|--------------|---------|------------|
| `sidebar_spawn` | Create new sidebar | `parent_id`, `participants`, `task_description`, `priority` |
| `sidebar_pause` | Pause a sidebar | `sidebar_id`, `reason`, `resume_condition` |
| `sidebar_resume` | Resume paused sidebar | `sidebar_id`, `reason` |
| `sidebar_fork` | Fork archived sidebar into new work | `original_sidebar_id`, `new_sidebar_id`, `fork_reason` |
| `sidebar_child_spawn` | Create nested child sidebar | `parent_sidebar_id`, `child_sidebar_id`, `sub_task_description` |
| `sidebar_merge` | Merge findings back to parent | `sidebar_id`, `parent_id`, `consolidated_findings`, `success` |
| `sidebar_archive` | Archive completed sidebar | `sidebar_id`, `archive_reason`, `final_status` |
| `sidebar_status_update` | Status state change | `sidebar_id`, `old_status`, `new_status`, `reason` |
| `sidebar_waiting_update` | Blocked on something | `sidebar_id`, `waiting_for`, `description`, `dependency_refs` |
| `sidebar_test_result` | Results from TESTING sidebar | `sidebar_id`, `test_description`, `result`, `findings` |

### 6.2 Memory Operations

| Message Type | Purpose | Key Fields |
|--------------|---------|------------|
| `memory_update` | New exchange stored | `exchange`, `context_id`, `priority` |
| `memory_archived` | Moved to episodic memory | `exchange_id`, `archive_reason` |
| `gold_created` | New GOLD waypoint flagged | `gold_id`, `source_refs`, `key_insight`, `trigger_conditions` |

### 6.3 Agent Coordination

| Message Type | Purpose | Key Fields |
|--------------|---------|------------|
| `agent_presence` | Agent status update | `agent_id`, `status`, `current_context`, `active_sidebars` |
| `mention_route` | @mention routing | `target_agents`, `message`, `context_refs`, `priority` |
| `agent_recruited` | Agent joined sidebar | `agent_id`, `sidebar_id`, `recruited_by` |
| `agent_left` | Agent left sidebar | `agent_id`, `sidebar_id`, `reason` |

### 6.4 Chat & Content

| Message Type | Purpose | Key Fields |
|--------------|---------|------------|
| `chat_message` | Regular message | `role`, `content`, `citations`, `confidence_score` |
| `citation_created` | New CITE-X reference | `citation_id`, `source`, `content`, `relevance_score` |

### 6.5 Media Events

Media attachments with temporal relevance tracking:

```python
@dataclass
class MediaEvent:
    media_id: str                   # MEDIA-{sequential}
    type: str                       # "media_uploaded" | "media_processed" | "media_error"
    media_type: str                 # "video" | "audio" | "document" | "image" | "code"
    file_path: str
    file_size: Optional[int]
    processing_status: str          # "pending" | "processing" | "complete" | "failed"

    # Temporal context (enables future relevance tracking)
    uploaded_during: str            # Which sidebar/conversation
    in_response_to: Optional[str]   # MSG-X that prompted this upload
    uploaded_by: str                # Agent or human
    uploaded_at: datetime
```

**Temporal Relevance:** When temporal memory is implemented, MEDIA references can be traced:
- "Show me what we looked at for auth issues" → Surfaces MEDIA-89 because it was uploaded in response to MSG-4521 during that investigation.

### 6.6 Scratchpad System (Curator-Gated)

The scratchpad is a **curator-managed artifact** for collective note-taking during sidebar work.

#### Scratchpad Structure

```python
@dataclass
class Scratchpad:
    scratchpad_id: str              # SCRATCH-{sidebar_id}
    sidebar_id: str                 # Which sidebar owns this
    curator_agent: str              # Who's managing validation

    # Task Definition (set at sidebar creation)
    task_definition: str
    success_criteria: str

    # Findings (curator-validated)
    confirmed_findings: List[ScratchpadEntry]
    pending_findings: List[ScratchpadEntry]   # Awaiting validation
    rejected_findings: List[ScratchpadEntry]  # Rejected with reason (learning signal)

    # Checkpoints
    checkpoints: List[Checkpoint]

    # Final state
    final_summary: Optional[str]    # Generated at consolidation

@dataclass
class ScratchpadEntry:
    entry_id: str
    content: str
    submitted_by: str               # Agent who found this
    submitted_at: datetime
    source_refs: List[str]          # [MSG-4521, CITE-89] evidence

    # Why this matters (prevents "why did we care about this?" confusion)
    relevance_to_task: Optional[str]  # "This explains the auth timeout in success_criteria"

    # Validation
    status: str                     # "pending" | "confirmed" | "rejected"
    validated_by: Optional[str]     # Curator who validated
    validated_at: Optional[datetime]
    validation_notes: Optional[str] # Why confirmed/rejected

    # Annotations (any agent can add after confirmation)
    annotations: List[Annotation]

@dataclass
class Checkpoint:
    checkpoint_id: str
    created_at: datetime
    created_by: str                 # Usually curator
    summary: str                    # "Completed phase 1: identified root cause"
    findings_at_checkpoint: List[str]  # Entry IDs included at this point
    agent_annotations: Dict[str, str]  # {agent_id: "their note"}
```

#### Scratchpad Validation Flow

```
Agent finds something
        │
        ▼
┌─────────────────────────────────────────┐
│  Submit to Curator                      │
│  "Found X, evidence: [MSG-4521]"        │
│  "Relevance: This explains the timeout" │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│  Curator Validation                     │
│  - Does this align with task?           │
│  - Does evidence support claim?         │
│  - Does it contradict other findings?   │
└─────────────────────────────────────────┘
        │
        ├─── CONFIRMED ──→ Added to scratchpad, agents notified
        │
        ├─── PENDING ────→ Visible but flagged, triggers discussion
        │
        └─── REJECTED ───→ Stored with reason (learning signal)
```

#### Conflict Detection

When agents submit contradictory findings:

```python
async def submit_finding(self, finding: ScratchpadEntry):
    # Check for conflicts with existing findings
    conflicts = self.detect_conflicts(finding, self.confirmed_findings)

    if conflicts:
        # Don't reject either - trigger collaborative review
        finding.status = "pending"
        finding.validation_notes = f"Conflicts with {conflicts}, needs discussion"

        # Notify both agents
        await self.notify_agents(
            [finding.submitted_by, conflicts[0].submitted_by],
            f"Conflicting findings detected - let's discuss"
        )

        # Could spawn a child sidebar for complex conflicts
        if self.conflict_is_complex(conflicts):
            await self.spawn_resolution_sidebar(finding, conflicts)
```

This keeps with "Not The Borg" - agents can disagree, disagreement triggers collaboration rather than one agent "winning."

#### Scratchpad Message Types

| Message Type | Purpose | Key Fields |
|--------------|---------|------------|
| `scratchpad_created` | New scratchpad initialized | `scratchpad_id`, `sidebar_id`, `task_definition` |
| `scratchpad_entry_submitted` | Agent submits finding | `entry_id`, `content`, `source_refs`, `relevance_to_task` |
| `scratchpad_entry_validated` | Curator validates entry | `entry_id`, `status`, `validation_notes` |
| `scratchpad_checkpoint` | Checkpoint created | `checkpoint_id`, `summary`, `findings_at_checkpoint` |
| `scratchpad_conflict` | Conflicting findings detected | `entry_ids`, `conflict_description` |

### 6.7 System Messages

| Message Type | Purpose | Key Fields |
|--------------|---------|------------|
| `system_shutdown` | Graceful shutdown warning | `message`, `countdown_seconds`, `urgency` |
| `connection_established` | New connection | `client_id`, `client_type` |
| `connection_lost` | Connection dropped | `client_id`, `reason` |
| `duplicate_ack` | Deduplication acknowledgment | `original_message_id`, `message` |

#### duplicate_ack Explained

This handles **message delivery reliability**, not sidebar duplication:

```
Agent sends MSG-4521
    │
    ├─ Network hiccup, agent unsure if delivered
    │
    ├─ Agent retries, sends MSG-4521 again
    │
    └─ Server receives duplicate
        │
        ├─ Recognizes: "Already processed this UUID"
        │
        └─ Sends: duplicate_ack
            {
                "type": "duplicate_ack",
                "original_message_id": "MSG-4521",
                "message": "Already processed, no action taken"
            }

Agent knows: "OK it got there, stop retrying"
```

---

## 7. Orchestration Patterns

### 7.1 Spawn Flow

#### Who Can Spawn
- Any agent (symmetric access)
- Any human
- The system itself (automated triggers)

#### Required vs Optional Fields

| Field | Required? | Default | Notes |
|-------|-----------|---------|-------|
| `parent_context_id` | Yes | - | Where to inherit from (null = root conversation) |
| `task_description` | Yes | - | What are we doing? Can't validate findings without goal |
| `success_criteria` | Recommended | - | What does "done" look like? |
| `participants` | Yes | [spawner] | At least the spawner must be included |
| `priority` | Optional | NORMAL | Can be changed later if urgency changes |
| `coordinator_agent` | Optional | AGENT-operator | **Defaults to human** for safety |

#### Coordinator Defaults to Human

The human/operator is the default coordinator. This provides:
1. **Safety net** - Human is always the fallback
2. **Gradual autonomy** - As trust builds, explicitly set `coordinator_agent="AGENT-curator"` for routine tasks
3. **Learning signal** - Observe which sidebars need intervention vs resolve themselves

Escalation path:
```
Agent hits problem in sidebar
    │
    ├─ Coordinator = AGENT-curator → Curator tries to resolve
    │       │
    │       └─ Can't resolve → Escalate to AGENT-operator (human)
    │
    └─ Coordinator = AGENT-operator → Comes directly to human
```

#### Context Inheritance

**Full copy with working relevance:**

```
Parent Conversation (before fork)
├── Exchange 1
├── Exchange 2
├── Exchange 3
├── Exchange 4
├── Exchange 5 ←── [FORK POINT - sidebar spawned here]

Sidebar SB-89 created:
├── inherited_memory: [Exch 1, 2, 3, 4, 5] (FULL immutable copy)
│
└── First action in sidebar:
    └── Agents do relevance review:
        "Given our task_description, which of these matter?"

        Result:
        ├── Exch 2: HIGH relevance
        ├── Exch 4: HIGH relevance
        ├── Exch 1: LOW relevance
        ├── Exch 3: LOW relevance
        └── Exch 5: MEDIUM relevance
```

**Key distinction:**
- `inherited_memory` = FULL copy (immutable, complete record, nothing lost)
- `relevance_scores` = What agents are focusing on (can be filtered/updated)
- `active_focus` = Exchange IDs agents are currently working with

```python
@dataclass
class SidebarContext:
    # ... existing fields ...

    # Full immutable inheritance
    inherited_memory: List[Dict]              # Everything from parent at fork point

    # Working focus (agents can update)
    relevance_scores: Dict[str, float]        # {exchange_id: relevance_score}
    active_focus: List[str]                   # Exchange IDs currently being worked with
```

#### Relevance Consensus

Agents must agree on what's relevant before diving in:

```python
async def initialize_sidebar_focus(self):
    """Each agent reviews inherited context and marks what's relevant to them"""
    for agent in self.participants:
        agent_relevance = await agent.review_context(
            self.inherited_memory,
            self.task_description
        )
        self.merge_relevance_scores(agent_relevance)

    # Agents can discuss disagreements
    if self.has_relevance_conflicts():
        await self.discuss_relevance_priorities()

    # Build shared active_focus from consensus
    self.active_focus = self.get_high_relevance_exchanges()
```

---

### 7.2 Fork Flow (Reviving Archived Sidebars)

Fork is for picking up old work - an archived sidebar with relevant findings you want to build on.

#### When to Fork vs Spawn Fresh

| Scenario | Fork | Spawn Fresh |
|----------|------|-------------|
| "That auth investigation from last week is relevant again" | ✓ | |
| "New problem, unrelated to anything previous" | | ✓ |
| "I want to try a different approach to the same problem" | ✓ | |
| "The old sidebar failed, but had useful partial findings" | ✓ | |

#### Fork Inheritance

```python
forked = SidebarContext(
    sidebar_id="SB-102",
    forked_from="SB-89",                    # Link to original
    parent_context_id=None,                  # Forks don't have a "parent" in tree sense

    # Inherit EVERYTHING from the archived sidebar
    inherited_memory=(
        original.inherited_memory +          # What SB-89 inherited
        original.local_memory                # What happened IN SB-89
    ),

    # Start fresh
    local_memory=[],
    status=SidebarStatus.ACTIVE,

    # New task (might be same, might be variation)
    task_description="Revisiting auth issue with new information",
    success_criteria="...",
)
```

#### Scratchpad Handling on Fork

**Fresh scratchpad, original is citable:**
- New sidebar gets its own scratchpad
- Original scratchpad remains accessible via citations (SCRATCH-89:FINDING-3)
- Original scratchpad triggers backup (being referenced = protect it)

```python
async def fork_sidebar(self, original_sidebar_id: str, fork_reason: str) -> SidebarContext:
    original = await self.get_sidebar(original_sidebar_id)

    # Original scratchpad gets backup signal
    await original.scratchpad.trigger_backup(
        reason=f"Referenced by fork: {fork_reason}",
        priority="high"  # Being actively used = protect it
    )

    forked = SidebarContext(
        sidebar_id=self.generate_id(),
        forked_from=original_sidebar_id,
        # ... rest of fork setup

        # Reference to original scratchpad (not a copy)
        source_scratchpad_ref=original.scratchpad.scratchpad_id  # SCRATCH-89
    )

    # New fresh scratchpad for this fork
    forked.scratchpad = Scratchpad(
        scratchpad_id=f"SCRATCH-{forked.sidebar_id}",
        # ... fresh scratchpad

        # But knows where to look for prior art
        citable_sources=[original.scratchpad.scratchpad_id]
    )

    return forked
```

---

### 7.3 Merge Flow

The CONSOLIDATING → MERGED handoff. Critical question: what goes back to parent?

#### Merge Process

```
Sidebar SB-89 finishing up
├── Status: ACTIVE → REVIEWING → CONSOLIDATING
│
├── CONSOLIDATING phase:
│   ├── Scratchpad has confirmed findings
│   ├── Agents discuss: "What's actually useful to parent context?"
│   ├── Curator validates merge package
│   └── Coordinator (human by default) approves
│
├── Merge package created:
│   {
│       "summary": "Brief description of what we found",
│       "key_findings": [references to scratchpad entries],
│       "new_citations": [CITE-X created during sidebar],
│       "recommendations": "What parent should do with this",
│       "gold_candidates": [any GOLD-worthy insights]
│   }
│
├── Status: CONSOLIDATING → MERGED
│
└── Parent receives merge injection:
    └── Exchange added to parent: "Sidebar SB-89 completed: {summary}"
        └── With citations linking to full details
```

#### Merge Approval: Toggle + Whitelist

**Master toggle** - Start with everything requiring human approval, whitelist safe operations over time.

```python
@dataclass
class AutoMergeConfig:
    # Master toggle - everything requires approval when False
    auto_merge_enabled: bool = False  # Default: OFF

    # Whitelist - only matters if auto_merge_enabled is True
    allowed_task_types: List[str] = field(default_factory=list)

    # Additional safety constraints (all must pass even if whitelisted)
    require_curator_approval: bool = True
    require_no_conflicts: bool = True
    require_sources_cited: bool = True
    block_if_proposes_changes: bool = True

    # Trust evolution tracking
    auto_merge_history: List[AutoMergeResult] = field(default_factory=list)


def can_auto_merge(sidebar: SidebarContext, config: AutoMergeConfig) -> bool:
    # Master toggle check first
    if not config.auto_merge_enabled:
        return False  # Everything goes to human

    # Must be on whitelist
    if sidebar.task_type not in config.allowed_task_types:
        return False

    # Safety constraints still apply
    if config.require_curator_approval and not sidebar.curator_approved_findings():
        return False
    if config.require_no_conflicts and sidebar.scratchpad.has_conflicts():
        return False
    if config.require_sources_cited and not sidebar.all_findings_have_sources():
        return False
    if config.block_if_proposes_changes and sidebar.proposes_changes():
        return False

    return True
```

#### Candidates for Auto-Merge Whitelist

These are **read-only operations with objective results** - safe starting points once you're ready:

| Task Type | Why Safe | Condition |
|-----------|----------|-----------|
| `status_check` | Factual answer, no changes | Query succeeded, boolean/simple result |
| `documentation_lookup` | Read-only, just retrieved info | Findings cite sources, no contradictions |
| `definition_retrieval` | Reading existing code | Found it, summarized, no edits proposed |
| `search_discovery` | Listing results | Results are just references |
| `format_validation` | Objective pass/fail | Clear test results |

**Never auto-merge:**
- Any proposed code changes
- Architectural recommendations
- Conflicting findings
- Security-related anything
- First time doing a new task type

#### Trust Evolution Path

```
Day 1:   auto_merge_enabled = False
         (Approve everything, learn what's routine)

Week 2:  auto_merge_enabled = True
         allowed_task_types = ["status_check"]
         (Just status checks, watch the history)

Week 4:  allowed_task_types = ["status_check", "documentation_lookup"]
         (Add after status checks proved safe)

Month 2: allowed_task_types.append("search_discovery")
         (Gradually expand as trust builds)
```

The `auto_merge_history` enables auditing:
- "Did any auto-merged sidebars cause problems?"
- "Which task types have 100% clean history?"

---

### 7.4 Archive Flow

#### Archive Triggers

| Trigger | From Status | Notes |
|---------|-------------|-------|
| Successful merge | MERGED | Normal completion - findings went to parent |
| Manual archive | ACTIVE, PAUSED, WAITING | "I'm done with this, save it for later" |
| Failed sidebar | FAILED | Preserve for debugging/learning |
| Timeout | WAITING, PAUSED | Configurable - stale sidebars auto-archive |
| Testing discard | TESTING | Test completed, not promoting to real work |

#### What Gets Preserved

Everything. Archive is not lossy - it's a snapshot that can be forked later.

```python
@dataclass
class ArchivedSidebar:
    # Full sidebar state at archive time
    sidebar_snapshot: SidebarContext

    # Archive metadata
    archived_at: datetime
    archived_by: str                    # Agent or human who triggered
    archive_reason: str                 # "merged", "manual", "failed", "timeout", "test_discard"
    final_status: SidebarStatus         # Status before archiving

    # Preserved artifacts
    scratchpad_snapshot: Scratchpad     # Full scratchpad state
    local_memory: List[Dict]            # All exchanges in sidebar
    citations_created: List[str]        # CITE-X refs created during sidebar
    gold_citations: List[str]           # Any GOLD-X created
    media_refs: List[str]               # MEDIA-X attached during sidebar

    # Relationships (for yarn-board tracing)
    parent_context_id: Optional[str]
    child_sidebar_ids: List[str]
    forked_from: Optional[str]
    forked_into: List[str]              # Sidebars that forked FROM this one later

    # Searchability
    tags: List[str]                     # Auto-generated + manual tags
    summary: str                        # Generated summary for search
```

#### Archive Search

Full search capabilities across all archived sidebars:

```python
class ArchiveSearch:
    async def search(
        self,
        # Direct lookups
        sidebar_id: Optional[str] = None,

        # Time
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,

        # Categorical
        task_types: Optional[List[str]] = None,
        statuses: Optional[List[SidebarStatus]] = None,
        participants: Optional[List[str]] = None,

        # Relationships
        parent_id: Optional[str] = None,
        forked_from: Optional[str] = None,

        # Fuzzy matching (typos, partial matches)
        fuzzy_text: Optional[str] = None,      # "authentcation" finds "authentication"
        fuzzy_threshold: float = 0.8,

        # Semantic (embedding-based)
        query_text: Optional[str] = None,       # "login problems" finds "auth failures"
        similarity_threshold: float = 0.7,

        # Pagination
        limit: int = 20,
        offset: int = 0,
    ) -> List[ArchivedSidebar]:
        """Unified search - combine any filters"""
        ...
```

| Search Type | Implementation | Difficulty |
|-------------|----------------|------------|
| By ID | Direct lookup | Trivial |
| By time range | Index on `archived_at` | Trivial |
| By task type | Index on `task_type` | Trivial |
| By outcome | Index on `final_status` | Trivial |
| By participant | Index on `participants` array | Easy |
| By relationship | Index on `parent_context_id`, `forked_from` | Easy |
| Fuzzy | Levenshtein/trigram (pg_trgm or RapidFuzz) | Easy |
| Semantic | Embedding vectors + similarity search | Medium (reuse memory infrastructure) |

---

### 7.5 Agent Recruitment

#### Recruitment Scenarios

| Scenario | Initiated By | Example |
|----------|--------------|---------|
| Spawn with team | Spawner | "Start sidebar with me, security agent, and curator" |
| Mid-work recruitment | Any participant | "I need the debugging agent's help here" |
| Agent self-volunteers | Agent | "I noticed you're working on auth - I have relevant expertise" |
| Coordinator assigns | Coordinator | "Security agent, please join SB-89" |
| System auto-suggests | System | "Based on task_description, AGENT-database might be useful" |

#### Recruitment Flow

```
Recruitment Request
    │
    ├─ Who's requesting? (participant, coordinator, system)
    │
    ├─ Who's being recruited?
    │   ├─ Specific agent: "I need AGENT-security"
    │   └─ Capability match: "I need someone who knows databases"
    │
    ├─ Agent availability check
    │   ├─ Available → Proceed
    │   ├─ At capacity → Load management (see below)
    │   └─ Offline → Notify requester
    │
    ├─ Agent accepts/declines?
    │   ├─ Auto-accept (most cases)
    │   └─ Agent can decline if overloaded or task outside expertise
    │
    └─ Onboarding
        ├─ Agent receives: inherited_memory, active_focus, scratchpad state
        ├─ Agent does own relevance review
        └─ Agent joins participant list
```

#### Context Isolation

Agents can work multiple sidebars simultaneously. Each sidebar has isolated context:

```
AGENT-security juggling 3 sidebars:

SB-89 (auth debugging)
├── inherited_memory: [context A]
├── local_memory: [work in SB-89]
└── Agent pulls from THIS pool when working here

SB-102 (permission review)
├── inherited_memory: [context B]
├── local_memory: [work in SB-102]
└── Agent pulls from THIS pool when working here

SB-115 (encryption audit)
├── inherited_memory: [context C]
├── local_memory: [work in SB-115]
└── Agent pulls from THIS pool when working here
```

When agent hops from SB-89 to SB-102, they load SB-102's context fresh. No bleed between pools.

#### Load Management

```python
@dataclass
class AgentLoadManager:
    agent_id: str
    max_concurrent_per_instance: int = 5

    async def handle_recruitment(self, new_sidebar: SidebarContext) -> RecruitmentResult:

        # First: Can we spawn another instance of this agent?
        if self.system_has_capacity_for_new_instance():
            new_instance = await self.spawn_agent_instance(self.agent_id)
            await self.notify_coordinator(
                f"Spawned {new_instance.instance_id} to handle additional load"
            )
            return await new_instance.join_sidebar(new_sidebar)

        # No hardware capacity - manage what we have
        if not self.is_at_capacity():
            return await self.join_sidebar(new_sidebar)

        # At capacity, no room for new instance
        await self.notify_coordinator(
            f"Agent {self.agent_id} at capacity, no hardware for new instance"
        )

        # Priority-based handling
        if new_sidebar.priority == SidebarPriority.CRITICAL:
            # CRITICAL always gets in - pause lowest non-critical
            pauseable = self.get_pauseable_sidebars()  # LOW, BACKGROUND only
            if pauseable:
                await self.pause_sidebar(pauseable[0], reason="CRITICAL task needed capacity")
                return await self.join_sidebar(new_sidebar)
            else:
                # Everything is CRITICAL/HIGH/NORMAL - queue but escalate
                await self.notify_coordinator(
                    f"CRITICAL task {new_sidebar.sidebar_id} queued - all current work is HIGH priority or above",
                    urgency="high"
                )
                return RecruitmentResult(status="queued", queue_position=1)

        elif new_sidebar.priority in [SidebarPriority.HIGH, SidebarPriority.NORMAL]:
            # Queue it, don't interrupt ongoing work
            return RecruitmentResult(
                status="queued",
                queue_position=self.calculate_queue_position(new_sidebar),
                alternatives=await self.find_alternative_agents(new_sidebar)
            )

        else:  # LOW, BACKGROUND
            # These can wait indefinitely
            return RecruitmentResult(
                status="queued",
                queue_position=self.calculate_queue_position(new_sidebar),
                message="Queued for when capacity available"
            )

    def get_pauseable_sidebars(self) -> List[str]:
        """Only LOW and BACKGROUND can be auto-paused"""
        return [
            sb for sb in self.active_sidebars
            if sb.priority in [SidebarPriority.LOW, SidebarPriority.BACKGROUND]
        ]
```

#### Priority-Based Load Handling

| Situation | Action |
|-----------|--------|
| Hardware available | Spawn new agent instance, notify coordinator |
| At capacity, new CRITICAL comes in | Auto-pause LOW/BACKGROUND if any, else queue + escalate |
| At capacity, new HIGH/NORMAL comes in | Queue, offer alternatives |
| At capacity, new LOW/BACKGROUND comes in | Queue, wait indefinitely |
| Any time capacity is hit | Notify coordinator |

#### Auto-Pause Whitelist

| Priority | Can Auto-Pause? |
|----------|-----------------|
| CRITICAL | Never |
| HIGH | No - queue instead |
| NORMAL | No - queue instead |
| LOW | Yes - safe to auto-pause |
| BACKGROUND | Yes - safe to auto-pause |

#### Notification Levels

| Level | Meaning | Example |
|-------|---------|---------|
| Info | "FYI, handled it" | "Spawned new agent instance" |
| Warning | "Handled it, but worth knowing" | "Paused SB-125 (LOW) for CRITICAL task" |
| Escalate | "Need your decision" | "CRITICAL queued, can't auto-resolve" |

#### Resume Notification

When a paused sidebar resumes, agent receives context about what happened:

```python
async def resume_sidebar(self, sidebar_id: str):
    sidebar = await self.get_sidebar(sidebar_id)

    # Tell the agent what happened while paused
    await self.notify_agent(sidebar.participants, {
        "type": "sidebar_resumed",
        "sidebar_id": sidebar_id,
        "paused_duration": self.calculate_pause_duration(sidebar_id),
        "paused_reason": sidebar.pause_reason,
        "what_happened_while_paused": await self.get_system_changes_during_pause(sidebar_id),
        # e.g., "SB-130 (CRITICAL) completed, 2 new citations created"
    })
```

---

## 8. Memory System Integration

### 8.1 Memory Layers

Four distinct memory layers, each with a specific purpose:

```
1. IMMUTABLE LOG (Hard copy - append only, never modified)
   └── Every MSG-X, every exchange, raw as it happened
   └── Write-once, read-many
   └── For: Audit, legal, "what actually was said", debugging disputes

2. WORKING MEMORY (Active, mutable)
   └── Current sidebar local_memory
   └── Confidence scores can update
   └── For: Active work, context for responses

3. EPISODIC MEMORY (Archived, searchable)
   └── Processed/summarized versions
   └── Tagged, embedded for search
   └── For: Long-term recall, pattern finding

4. SIDEBAR CONTEXT (Scoped structures)
   └── inherited_memory (frozen snapshot)
   └── scratchpad (curator-validated findings)
   └── For: Sidebar-specific work
```

**Key principle:** The immutable log is separate from everything else. Working memory can update confidence, episodic can summarize and consolidate - but the raw log never changes.

### 8.2 Immutable Log Entry

Every message gets a permanent, unmodifiable record:

```python
@dataclass
class ImmutableLogEntry:
    # === Identity ===
    entry_id: str                    # MSG-4521
    uuid: str                        # Full UUID for internal use

    # === Timing ===
    timestamp: datetime              # When it happened
    processing_time_ms: Optional[int] # How long to generate (agents)

    # === Content ===
    raw_content: str                 # Exactly what was said
    content_type: str                # "text", "code", "media_ref", "system"
    content_length: int              # Character count
    token_count: Optional[int]       # Token count if relevant

    # === Source ===
    sender: str                      # Who said it (AGENT-X or human)
    sender_type: str                 # "agent", "human", "system"
    context_id: str                  # Which sidebar/conversation
    parent_msg_id: Optional[str]     # What this was responding to (thread tracing)

    # === Integrity ===
    checksum: str                    # Tamper detection (SHA-256 of content)
    previous_entry_checksum: str     # Chain to previous entry (blockchain-style)

    # === Session Context ===
    session_id: str                  # Which session
    agent_model_version: Optional[str]  # Model version if agent

    # === References ===
    citations_used: List[str]        # [CITE-89, MSG-4500] - what was referenced
    media_attached: List[str]        # [MEDIA-12] - files attached

    # === Tool Usage (agent messages) ===
    tools_invoked: Optional[List[str]]  # ["web_search", "file_read"]
    tool_results_summary: Optional[str] # Brief outcome of tool use

    # === Confidence ===
    sender_confidence: Optional[float]  # How confident was sender
    flagged_uncertain: bool = False     # Sender marked this as uncertain

    # === Error Context ===
    error_occurred: bool = False        # Did this message involve an error
    error_ref: Optional[str]            # Link to error log if so

    # === Environment ===
    originating_client: str             # "react", "terminal", "api"
    client_version: Optional[str]       # Version of client software
```

#### Metadata Overhead

| Category | Approximate Size |
|----------|------------------|
| Metadata per message | ~300-500 bytes |
| Average message content | ~500-5000 bytes |
| Overhead ratio | 5-50% depending on message length |

**Performance note:** Metadata is just stored data - it sits doing nothing until queried. No ongoing processing cost, only storage. The expensive operation (LLM inference) already happened; adding metadata is negligible in comparison.

#### Checksum Chain

The `previous_entry_checksum` creates a blockchain-style integrity chain:
- If anyone deletes or modifies an entry, the chain breaks
- Integrity verification walks the chain and validates each link
- Provides tamper detection for audit purposes

### 8.3 Where Sidebar Memory Lives

```
While sidebar ACTIVE:
├── inherited_memory: Snapshot (frozen, read-only)
│   └── Lives in: Sidebar context object (not working memory)
│
├── local_memory: Active exchanges
│   └── Lives in: Working memory (sidebar-scoped)
│   └── Also written to: Immutable log (permanent record)
│
└── scratchpad: Curator-validated findings
    └── Lives in: Sidebar context object

When sidebar ARCHIVED:
├── Everything moves to episodic memory
├── Immutable log entries remain unchanged
└── Citable via SB-X, MSG-X, CITE-X, SCRATCH-X references
```

### 8.4 Confidence Inheritance

#### The Problem: Blind Confidence

When a sidebar inherits context from parent, it often includes claims with confidence scores. Without validation, agents build on potentially shaky foundations:

```
Parent says: "The issue is in Redis" (confidence: 0.6)
    │
    └─ Without validation:
        ├─ Agent spends an hour debugging Redis
        ├─ Builds a fix for Redis
        ├─ Tests the Redis fix
        └─ ...only to discover the issue was in auth service
```

#### Hybrid Approach: Tag + Default Unverified

Combine the best of both approaches:
- **Keep original confidence** for reference
- **Default to unverified** until explicitly validated
- **Mechanical validation** for checkable claims
- **Agent judgment** for hypotheses and interpretations

```python
@dataclass
class InheritedExchange:
    original_exchange: Exchange
    original_confidence: float        # Keep for reference
    inherited_from: str               # Parent context ID
    inherited_at: datetime

    # Default to unverified - must be explicitly validated
    local_verification: str = "unverified"  # "confirmed", "contradicted", "unverified"
    local_confidence: Optional[float] = None  # None until verified

    def effective_confidence(self) -> float:
        """What confidence should we actually use?"""
        if self.local_verification == "confirmed":
            return self.local_confidence or self.original_confidence
        elif self.local_verification == "contradicted":
            return 0.0  # Don't trust this
        else:  # unverified
            return 0.0  # Treat as unverified until checked
```

#### Mechanical Validation System

Quick automated checks for verifiable claims:

```python
async def auto_validate_inherited(exchange: InheritedExchange) -> InheritedExchange:
    """Quick mechanical validation for verifiable claims"""

    claim_type = classify_claim(exchange.original_exchange.content)

    if claim_type == "factual_checkable":
        # "The auth timeout is 500ms" - can verify by checking config
        result = await verify_factual_claim(exchange)
        exchange.local_verification = "confirmed" if result else "contradicted"
        exchange.local_confidence = 0.95 if result else 0.1

    elif claim_type == "system_state":
        # "Redis connection pool exhausted" - can check current state
        result = await check_system_state(exchange)
        exchange.local_verification = "confirmed" if result else "contradicted"
        exchange.local_confidence = 0.9 if result else 0.2

    elif claim_type == "hypothesis":
        # "I think the issue is in Redis" - can't mechanically verify
        exchange.local_verification = "unverified"
        exchange.local_confidence = None  # Needs agent judgment

    return exchange
```

#### Validation Whitelist (Toggle Pattern)

Same pattern as auto-merge - start locked down, whitelist as trust builds:

```python
@dataclass
class MechanicalValidationConfig:
    # Master toggle
    auto_validation_enabled: bool = False  # Default: OFF, all manual

    # Whitelisted validation types
    allowed_validations: List[str] = field(default_factory=list)

    # History for trust building
    validation_history: List[ValidationResult] = field(default_factory=list)
```

#### Safe Starting Candidates for Whitelist

| Validation Type | What It Checks | How | Risk Level |
|-----------------|----------------|-----|------------|
| `config_value` | "Timeout is 500ms" | Read config file, compare | Very Low |
| `file_exists` | "The file is at /path/x" | Check filesystem | Very Low |
| `service_status` | "Redis is running" | Health check endpoint | Low |
| `current_state` | "Connection pool at 80%" | Query metrics | Low |
| `code_structure` | "Function X exists in file Y" | Parse/grep code | Low |
| `version_check` | "Using Python 3.11" | Check runtime | Very Low |
| `dependency_exists` | "Package X is installed" | pip list / check | Very Low |

#### NOT Safe to Auto-Validate (Needs Agent Judgment)

| Type | Example | Why Not |
|------|---------|---------|
| `hypothesis` | "I think Redis is the issue" | Needs investigation |
| `causation` | "X caused Y" | Correlation vs causation |
| `recommendation` | "We should refactor this" | Subjective |
| `interpretation` | "The user wants X" | Intent is ambiguous |

#### Multi-Method Validation (Addressing Real Failure Patterns)

**The problem:** Single-check validation often fails due to:
- Wrong environment (user vs system, Docker vs bare metal)
- Wrong path (file exists, just in different location)
- Ambiguous results (process running but not healthy)

**The solution:** Validation methods should be multi-attempt and parallelizable:

```python
async def validate_service_status(service_name: str) -> ValidationResult:
    checks_to_try = [
        f"systemctl status {service_name}",
        f"systemctl status {service_name} --user",
        f"docker ps | grep {service_name}",
        f"pgrep -f {service_name}",
        f"ss -tlnp | grep {service_name}",  # Check if port is listening
    ]

    results = []
    for check in checks_to_try:
        result = await run_check(check)
        results.append(result)

        if result.is_conclusive:
            return ValidationResult(
                verified=True,
                method=check,
                result=result.output
            )

    # None conclusive - return uncertainty, don't claim
    return ValidationResult(
        verified=False,
        attempts=results,
        message="Could not conclusively verify - needs manual check"
    )
```

#### Validation Method Priorities

Ranked by how much they help agents avoid common failures:

| Priority | Validation Type | Why It Helps |
|----------|-----------------|--------------|
| 1 | Multi-method service checks | Single check, wrong env, false failure claims |
| 2 | File/path existence with search fallback | "File not found" when just in different directory |
| 3 | Config value extraction | Wrong file, file changed, misparse |
| 4 | Dependency verification | pip vs pip3, venv vs system, version mismatches |
| 5 | Port/connection status | "Process running" vs "actually listening" |

#### Validation Scratchpad

Intermediate results during multi-method validation:

```python
@dataclass
class ValidationScratchpad:
    validation_id: str
    claim_being_validated: str

    attempts: List[ValidationAttempt]      # All methods tried
    conflicts: List[str]                   # "Check 1 said X, check 2 said Y"

    conclusion: Optional[str]              # Final determination
    confidence: Optional[float]            # How sure are we
    needs_human_review: bool = False       # Conflicts couldn't be resolved
```

This allows:
- **Parallel validation checks** - Try 5 methods at once
- **Scratchpad intermediate results** - Track what each method found
- **Conflict detection** - "These two checks disagree, need resolution"
- **No penalty for multiple attempts** - Architecture expects multi-try

#### Validation Flow Summary

```
Inherited exchange arrives
    │
    ├─ Classify the claim type
    │
    ├─ Is claim type in allowed_validations whitelist?
    │   ├─ YES → Run mechanical check (multi-method)
    │   │         ├─ Conclusive → confirmed/contradicted
    │   │         └─ Inconclusive → unverified, flag for review
    │   └─ NO → Mark as "unverified", needs agent review
    │
    └─ Agent sees:
        ├─ ✓ Confirmed: "Timeout is 500ms" (auto-verified via config)
        ├─ ✗ Contradicted: "Redis is running" (checked 5 ways, it's down)
        └─ ? Unverified: "Issue is in Redis" (hypothesis, needs judgment)
```

### 8.5 Archival Triggers

#### When Things Move to Episodic Memory

| Trigger | What Gets Archived | When |
|---------|-------------------|------|
| Sidebar completion | Full sidebar (local_memory, scratchpad, artifacts) | Status → MERGED or ARCHIVED |
| GOLD citation | Specific finding + context | Immediately when flagged |
| Manual archive | Selected exchanges/findings | User or agent explicitly triggers |
| Time-based | Stale sidebars | Configurable timeout |
| Mid-sidebar checkpoint | Confirmed findings so far | At scratchpad checkpoints |

#### Provisional Archival (Mid-Sidebar)

Findings can be archived before sidebar completes, but tagged as provisional:

```
Mid-sidebar flow:

Sidebar active, work happening
    │
    ├─ Checkpoint 1: 3 confirmed findings
    │   └─ Archive with provisional: true
    │       └─ "These look good, but sidebar still working"
    │
    ├─ Checkpoint 2: 2 more findings, 1 revision to earlier finding
    │   └─ Archive new findings (provisional: true)
    │   └─ Update revision in episodic (still provisional)
    │
    ├─ Checkpoint 3: GOLD flagged on finding #2
    │   └─ GOLD gets archived immediately
    │   └─ Still provisional until sidebar completes
    │
    └─ Sidebar completes (MERGED)
        └─ Final pass:
            ├─ All provisional: true → provisional: false
            ├─ Any findings that got contradicted → mark as superseded
            └─ Scratchpad final_summary generated
```

**Benefits of provisional archival:**
- Findings are protected even if sidebar fails later
- Other sidebars can cite them immediately (with provisional warning)
- Reduces risk of losing work

#### Episodic Entry Structure

```python
@dataclass
class EpisodicEntry:
    entry_id: str
    content: Any                      # The archived thing
    source_sidebar: str               # SB-89
    source_checkpoint: Optional[str]  # Which checkpoint, if mid-sidebar

    # Provisional tracking
    provisional: bool = True          # True until sidebar completes
    finalized_at: Optional[datetime] = None

    # Revision tracking
    superseded_by: Optional[str] = None  # If this was revised later
    supersedes: Optional[str] = None     # What this replaced
```

#### GOLD Archival (No Validation Bypass)

**Critical principle: Protection ≠ Validation**

GOLD means:
- ✓ "This is worth protecting" (immediate backup)
- ✓ "This is a potential waypoint" (flagged for future reference)
- ✓ Higher priority in archival
- ✗ "This skips validation" (NEVER)

```python
async def flag_as_gold(finding: ScratchpadEntry, gold_reason: GoldCitation):
    # Immediate archive for protection
    await archive_to_episodic(
        content=finding,
        gold_citation=gold_reason,
        provisional=True,          # STILL provisional
        requires_validation=True,  # STILL requires validation
        priority="high"            # Just protected sooner
    )

    # Trigger backup of source scratchpad
    await finding.source_scratchpad.trigger_backup(
        reason=f"Contains GOLD: {gold_reason.gold_id}"
    )
```

**GOLD validation flow:**
```
GOLD flagged
    │
    ├─ Archived immediately (protected, backed up)
    │
    ├─ provisional: true (still needs final validation)
    │
    └─ When sidebar completes:
        ├─ Final validation pass on ALL findings, including GOLD
        ├─ GOLD confirmed → provisional: false
        └─ GOLD contradicted → marked superseded, learning signal
```

The guardrail holds for everything. No exceptions, no bypasses.

### 8.6 Emergency Procedures

#### Failure Scenarios

| Scenario | What Breaks | Risk |
|----------|-------------|------|
| Working memory service goes down | Can't store new exchanges | Lose active work |
| Episodic memory service goes down | Can't archive | Work stuck in working memory |
| WebSocket connection drops | Can't communicate | Agents isolated |
| Agent crashes mid-task | Work in progress lost | Partial findings orphaned |
| System shutdown (planned/unplanned) | Everything stops | All active sidebars at risk |

#### Priority: Preserve State for Resume

Hybrid approach:
1. **Preserve state aggressively** - Cache locally, backup immediately when trouble detected
2. **Degrade gracefully** - Keep what works running, notify what's broken
3. **Resume from checkpoint** - When services come back, pick up where we left off

#### Emergency Response Flow

```
Memory service goes down mid-sidebar:

Normal operation
    │
    ├─ Trouble detected (health check fails, write fails, timeout)
    │
    ├─ IMMEDIATE: Emergency cache write (all layers)
    │   ├─ Layer 1: Filesystem (raw JSON)
    │   ├─ Layer 2: SQLite (queryable)
    │   └─ Layer 3: Redis (broadcast to other services)
    │
    ├─ NOTIFY: Coordinator (human) alerted
    │   └─ "Working memory service down, operating in cached mode"
    │
    ├─ DEGRADE: What can continue?
    │   ├─ Read-only operations: YES (if data cached)
    │   ├─ New exchanges: Queue locally, write when service returns
    │   ├─ Archival: Blocked until episodic back
    │   └─ New sidebars: Blocked (can't inherit properly)
    │
    └─ RESUME: Service returns
        ├─ Query SQLite for sitrep (what's pending, any conflicts?)
        ├─ Replay queued writes in suggested order
        ├─ Verify cached state matches service state
        ├─ Resolve conflicts if any
        └─ Clear emergency_cache flag
```

#### Emergency Cache Structure

```python
@dataclass
class EmergencyCache:
    cache_id: str
    created_at: datetime
    reason: str                          # "working_memory_down", "websocket_lost", etc.

    # Preserved state
    sidebar_snapshots: Dict[str, SidebarContext]   # All active sidebars
    pending_writes: List[Dict]                      # Exchanges waiting to be stored
    pending_archives: List[Dict]                    # Findings waiting for episodic
    scratchpad_states: Dict[str, Scratchpad]       # All active scratchpads

    # Recovery info
    last_known_good_state: datetime      # When things were last working
    services_down: List[str]             # Which services triggered this

    # Recovery guidance
    recovery_notes: List[str] = field(default_factory=list)
    # "Sidebar SB-89 was mid-validation when memory dropped"
    # "Pending write conflicts with existing MSG-4521"

    suggested_recovery_order: List[str] = field(default_factory=list)
    # ["resolve_conflicts", "replay_pending_writes", "resume_sidebars"]

    # Resolution
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
```

#### Cache Size Estimates

```
Typical active session:
├── 3 active sidebars
│   ├── Each with ~20 exchanges inherited
│   ├── Each with ~10 local exchanges
│   └── ~5KB per sidebar = ~15KB
│
├── 5 pending writes
│   └── ~1KB each = ~5KB
│
├── 3 scratchpads
│   └── ~2KB each = ~6KB
│
└── Metadata: ~1KB

Total: ~25-50KB for typical session
Heavy session: Maybe 200-500KB
```

Small enough to write quickly to multiple locations.

#### Multi-Layer Cache Storage

```python
CACHE_LOCATIONS = [
    # Layer 1: Local filesystem (immediate, always works)
    # Raw JSON dump - fast, simple, survives anything but disk death
    "/var/lib/sidebar_system/emergency/",

    # Layer 2: User home (different mount sometimes)
    "~/.sidebar_cache/emergency/",

    # Layer 3: SQLite (queryable local - mechanical sitrep)
    # Structured tables for recovery analysis before replay
    "sqlite:///var/lib/sidebar_system/emergency_cache.db",

    # Layer 4: Redis (broadcast to other services)
    # Shared awareness - "is there an emergency?"
    "redis://emergency_cache",

    # Future Layer 5: NAS (offsite durability)
    # Survives full machine failure - when available
]
```

#### Why Each Layer Exists

| Layer | Purpose | Survives |
|-------|---------|----------|
| Filesystem (JSON) | Raw preservation, always available | Service crashes |
| Filesystem (home) | Backup if primary mount fails | Mount issues |
| SQLite | Queryable sitrep before replay | Service crashes |
| Redis | Broadcast emergency state to all services | Filesystem issues |
| NAS (future) | Offsite durability | Machine failure |

#### SQLite as Mechanical Sitrep

Before replaying cached data, query the situation:

```sql
-- What's unresolved?
SELECT cache_id, reason, created_at,
       json_array_length(pending_writes) as pending_count
FROM emergency_cache
WHERE resolved_at IS NULL
ORDER BY created_at DESC;

-- Any conflicts to handle?
SELECT cache_id, recovery_notes, suggested_recovery_order
FROM emergency_cache
WHERE recovery_notes LIKE '%conflict%';

-- What sidebars were active?
SELECT cache_id, sidebar_id, status, last_activity
FROM emergency_sidebar_snapshots
WHERE cache_id = ?;
```

This prevents blind replay - understand the situation before acting.

#### Redis Emergency Broadcast

Other services check for emergency state:

```python
# Services can check:
if redis.exists("emergency:active"):
    emergency_info = redis.get("emergency:active")
    # "Working memory down since 14:32, 3 sidebars cached"
    # Services adapt behavior accordingly

# When emergency resolves:
redis.delete("emergency:active")
redis.publish("system:emergency_resolved", resolution_info)
```

#### Emergency Cache Write

```python
async def emergency_cache_write(cache: EmergencyCache):
    # Write to ALL layers for redundancy

    # Layer 1 & 2: Filesystem
    for path in [PRIMARY_CACHE_PATH, HOME_CACHE_PATH]:
        await write_atomic(f"{path}/{cache.cache_id}.json", cache.to_json())

    # Layer 3: SQLite (queryable)
    await sqlite_insert_cache(cache)

    # Layer 4: Redis (broadcast)
    if "redis" not in cache.services_down:
        await redis.set(f"emergency:{cache.cache_id}", cache.to_json())
        await redis.set("emergency:active", cache.summary())

    # Future Layer 5: NAS when available
    if nas_available():
        await nas_write(f"emergency/{cache.cache_id}.json", cache.to_json())
```

#### Graceful Degradation Matrix

| Service Down | Can Still Do | Cannot Do |
|--------------|--------------|-----------|
| Working Memory | Read from cache, queue new writes | Store new exchanges directly |
| Episodic Memory | Work normally, queue archives | Archive findings, search history |
| WebSocket | Local operations, cache state | Agent communication, broadcasts |
| Redis | Filesystem cache, local SQLite | Broadcast emergency, shared state |
| All services | Emergency cache only | Everything except preserve state |

#### Startup Recovery Check

On system startup, check for unresolved emergencies and notify:

```python
async def startup_recovery_check():
    """Run on every system startup - detect if previous session crashed"""

    # Check all cache locations for unresolved emergencies
    unresolved = await sqlite_query("""
        SELECT cache_id, reason, created_at, pending_writes, recovery_notes
        FROM emergency_cache
        WHERE resolved_at IS NULL
    """)

    if unresolved:
        # System didn't shut down cleanly
        await notify_coordinator({
            "type": "startup_recovery_alert",
            "severity": "warning",
            "message": f"Previous session ended abnormally. {len(unresolved)} unresolved emergency cache(s) found.",
            "details": [
                {
                    "cache_id": cache.cache_id,
                    "reason": cache.reason,
                    "occurred_at": cache.created_at,
                    "pending_items": len(cache.pending_writes),
                    "notes": cache.recovery_notes
                }
                for cache in unresolved
            ],
            "recommendation": "Recovery audit recommended before resuming normal operations.",
            "actions": [
                "review_cached_state",
                "replay_pending_writes",
                "resolve_conflicts",
                "mark_resolved"
            ]
        })

        # Block normal operations until acknowledged
        return StartupState.RECOVERY_NEEDED

    # Check for dirty shutdown flag (set on clean shutdown, absent = crash)
    if not await check_clean_shutdown_flag():
        await notify_coordinator({
            "type": "startup_recovery_alert",
            "severity": "info",
            "message": "Previous session did not shut down cleanly. No cached emergencies found, but audit recommended.",
            "recommendation": "Quick health check recommended."
        })
        return StartupState.AUDIT_RECOMMENDED

    return StartupState.CLEAN

async def clean_shutdown():
    """Called on graceful shutdown"""
    # Set flag so next startup knows we exited cleanly
    await set_clean_shutdown_flag()

    # Clear any stale emergency broadcasts
    await redis.delete("emergency:active")
```

#### Startup States

| State | Meaning | Action Required |
|-------|---------|-----------------|
| `CLEAN` | Previous shutdown was graceful | None, proceed normally |
| `AUDIT_RECOMMENDED` | Unclean shutdown but no cached emergencies | Optional health check |
| `RECOVERY_NEEDED` | Unresolved emergency caches exist | Must review before normal ops |

#### Recovery Audit Flow

```
System starts up
    │
    ├─ Check for unresolved emergency caches
    │   ├─ Found → RECOVERY_NEEDED
    │   └─ None → Check clean shutdown flag
    │               ├─ Present → CLEAN
    │               └─ Absent → AUDIT_RECOMMENDED
    │
    ├─ If RECOVERY_NEEDED:
    │   ├─ Display: "Previous session crashed. Recovery audit required."
    │   ├─ Show: What was pending, what sidebars were active
    │   ├─ Options:
    │   │   ├─ "Review and replay" → Walk through cached state
    │   │   ├─ "Discard and start fresh" → Clear caches, lose pending work
    │   │   └─ "Export for manual review" → Dump to file for human analysis
    │   └─ Block normal operations until resolved
    │
    └─ If AUDIT_RECOMMENDED:
        ├─ Display: "Unclean shutdown detected. Quick audit recommended."
        └─ Allow proceeding, but suggest health check
```

---

## 9. Implementation Checklist

### Phase Overview

| Phase | Focus | Depends On |
|-------|-------|------------|
| 1 | Foundation | Nothing |
| 2 | Core Sidebar Ops | Phase 1 |
| 3 | Scratchpad & Quality | Phase 2 |
| 4 | Memory Integration | Phase 3 |
| 5 | Agent Coordination | Phase 4 |
| 6 | Automation | Phase 5 |
| 7 | Search | Phase 4+ |
| 8 | UI | Parallel track |

---

### Phase 1: Foundation

**Must have before anything else.**

| Component | Why First | Status |
|-----------|-----------|--------|
| Immutable Log | Everything writes to this - need it from day one | ☐ |
| Global ID System (MSG-X, SB-X, etc.) | All references depend on this | ☐ |
| Basic SidebarContext dataclass | Core data structure | ☐ |
| 10 Status states enum | Need state machine working | ☐ |
| Emergency cache (filesystem layer only) | Safety net before building complex stuff | ☐ |

**Milestone:** Can create a log entry with a global ID and basic sidebar structure.

---

### Phase 2: Core Sidebar Operations

**Basic sidebar lifecycle working end-to-end, all manual/human-approved.**

| Component | Why Here | Status |
|-----------|----------|--------|
| Spawn flow | Create sidebars | ☐ |
| Inherited memory (full copy) | Sidebars need context | ☐ |
| Local memory separation | Don't pollute parent | ☐ |
| Basic merge flow (manual approval only) | Get findings back to parent | ☐ |
| Archive flow | Complete the lifecycle | ☐ |
| Coordinator defaults to human | Safety net in place | ☐ |
| Status transitions | State machine logic | ☐ |

**Milestone:** Can spawn sidebar, do work, merge back to parent, archive. All human-approved.

---

### Phase 3: Scratchpad & Curator

**Quality control layer before adding automation.**

| Component | Why Here | Status |
|-----------|----------|--------|
| Scratchpad dataclass | Collective note-taking | ☐ |
| ScratchpadEntry with relevance_to_task | Track why findings matter | ☐ |
| Curator validation flow | Findings go through review | ☐ |
| Pending/confirmed/rejected states | Validation tracking | ☐ |
| Conflict detection | Catch contradictory findings | ☐ |
| Checkpoint system | Mid-sidebar progress markers | ☐ |
| Provisional flag on episodic entries | Safe early archival | ☐ |
| GOLD citations (with provisional) | Protect valuable findings | ☐ |

**Milestone:** Curator validates findings, checkpoints work, GOLD flags valuable insights.

---

### Phase 4: Memory Integration

**Full memory system integration with safety features.**

| Component | Why Here | Status |
|-----------|----------|--------|
| Working memory ↔ sidebar connection | Real memory system integration | ☐ |
| Episodic archival triggers | Automatic archival | ☐ |
| Confidence inheritance (tag + unverified default) | Trust tracking | ☐ |
| InheritedExchange dataclass | Track original vs local confidence | ☐ |
| SQLite emergency layer | Queryable sitrep | ☐ |
| Redis emergency broadcast | Multi-service awareness | ☐ |
| Startup recovery check | Crash detection | ☐ |
| Clean shutdown flag | Know if previous exit was graceful | ☐ |

**Milestone:** Full memory flow working, emergency procedures in place, crash recovery functional.

---

### Phase 5: Agent Recruitment & Load Management

**Multi-agent coordination after core is solid.**

| Component | Why Here | Status |
|-----------|----------|--------|
| AgentCapability dataclass | Track what agents can do | ☐ |
| Agent presence (online/offline/busy) | Know who's available | ☐ |
| Recruitment flow | Agents join sidebars | ☐ |
| Context isolation verification | Confirm no bleed between sidebars | ☐ |
| AgentLoadManager | Handle capacity | ☐ |
| Priority-based pause/queue | CRITICAL > HIGH > NORMAL > LOW | ☐ |
| Auto-pause whitelist (LOW/BACKGROUND only) | Safe automatic pausing | ☐ |
| Spawn new agent instance (if hardware allows) | Scale up when needed | ☐ |
| Resume notifications | Agents know what happened while paused | ☐ |
| Notification levels (info/warning/escalate) | Appropriate alerting | ☐ |

**Milestone:** Multiple agents can join sidebars, load is managed, priority respected.

---

### Phase 6: Validation & Automation

**Automation after manual processes proven safe.**

| Component | Why Here | Status |
|-----------|----------|--------|
| Claim classification (factual/system_state/hypothesis) | Know what's checkable | ☐ |
| MechanicalValidationConfig | Toggle + whitelist | ☐ |
| Basic validators (config_value, file_exists, version_check) | Safe starting set | ☐ |
| Multi-method validation | Retry patterns, parallel checks | ☐ |
| ValidationScratchpad | Track attempts, conflicts | ☐ |
| Validation whitelist management | Add validators as trust builds | ☐ |
| AutoMergeConfig | Toggle + whitelist | ☐ |
| Auto-merge for safe task types | status_check, documentation_lookup, etc. | ☐ |
| Auto-merge history tracking | Audit what auto-merged | ☐ |
| Fork flow | Revive archived sidebars | ☐ |
| Scratchpad backup on fork | Protect referenced content | ☐ |

**Milestone:** Mechanical validation working, auto-merge for whitelisted types, fork available.

---

### Phase 7: Search & Discovery

**Polish after core functionality complete.**

| Component | Why Here | Status |
|-----------|----------|--------|
| Archive search: by ID | Direct lookup | ☐ |
| Archive search: by time range | Find recent/old sidebars | ☐ |
| Archive search: by task type | Filter by what was done | ☐ |
| Archive search: by outcome/status | Find failed, merged, etc. | ☐ |
| Archive search: by participant | Who was involved | ☐ |
| Archive search: by relationship | Parent/child/fork connections | ☐ |
| Fuzzy search (RapidFuzz or similar) | Typo tolerance | ☐ |
| Semantic search (embedding-based) | Conceptual matching | ☐ |
| Yarn-board tracing | Follow citation chains across sidebars | ☐ |

**Milestone:** Can find any archived sidebar through multiple search methods.

---

### Phase 8: UI Integration (Parallel Track)

**Can develop alongside backend phases.**

| Component | Can Start At | Status |
|-----------|--------------|--------|
| React sidebar panel (basic) | Phase 2 | ☐ |
| Status indicators (10 states) | Phase 2 | ☐ |
| Spawn/merge/archive controls | Phase 2 | ☐ |
| Scratchpad display | Phase 3 | ☐ |
| Curator validation UI | Phase 3 | ☐ |
| Checkpoint visualization | Phase 3 | ☐ |
| GOLD flagging UI | Phase 3 | ☐ |
| Agent presence display | Phase 5 | ☐ |
| Load/capacity indicators | Phase 5 | ☐ |
| Recovery audit UI | Phase 4 | ☐ |
| Emergency mode indicators | Phase 4 | ☐ |
| Search interface | Phase 7 | ☐ |
| Yarn-board visualization | Phase 7 | ☐ |

**Milestone:** Full UI reflecting all backend capabilities.

---

## 10. Integration Points

### 10.1 rich_chat.py Connection

*TO BE DEFINED - Need to discuss current rich_chat.py architecture*

Questions to resolve:
- How does current chat flow work?
- Where do sidebars hook in?
- What state does rich_chat.py currently manage?

### 10.2 React UI Patterns

*TO BE DEFINED - Need to discuss current React architecture*

Questions to resolve:
- Current component structure?
- State management approach?
- WebSocket connection patterns?

### 10.3 Backend Service Integration

*TO BE DEFINED - Need to map to existing services*

Questions to resolve:
- Which services exist already?
- How do they communicate currently?
- What needs to be added vs modified?

---

## 11. Open Questions

### Unresolved Decisions

| Question | Options | Current Lean | Status |
|----------|---------|--------------|--------|
| Database choice for immutable log | PostgreSQL, SQLite, both | PostgreSQL primary + SQLite emergency | Open |
| Embedding model for semantic search | Local model, API-based | Local (privacy, cost) | Open |
| Agent instance spawning | Docker, subprocess, threads | Depends on agent architecture | Open |
| NAS integration timing | Phase 4, Phase 7, Post-launch | When hardware available | Open |

### Migration Path Considerations

- How to integrate with existing chat without breaking it?
- Gradual rollout strategy (feature flags?)
- Data migration for existing conversations?
- Rollback plan if issues discovered?

### Future Enhancements (Post-Launch)

- Temporal memory integration (when media was uploaded)
- Cross-sidebar agent learning (patterns across all work)
- Advanced yarn-board visualization
- Natural language sidebar commands ("branch this and investigate X")

---

## Revision History
- 2025-12-02: Initial consolidation from 5 source documents
- 2025-12-03: Added Sections 6-9, comprehensive architecture defined
