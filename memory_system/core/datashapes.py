#!/usr/bin/env python3
"""
datashapes.py - Centralized Data Shape Definitions

All dataclasses and enums used across the system live here.
No logic - just definitions of what data looks like.

Other files import from here to ensure consistent structures:
    from datashapes import SidebarContext, SidebarStatus, ImmutableLogEntry

Created: 2025-12-03
Source: UNIFIED_SIDEBAR_ARCHITECTURE.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Set, Any, Tuple


# =============================================================================
# ENUMS - Status and Priority definitions
# =============================================================================

class SidebarStatus(Enum):
    """
    10 states for sidebar lifecycle.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 4 for full definitions.
    """
    ACTIVE = "active"              # Doing real work
    TESTING = "testing"            # Experimental/debug mode, may be discarded
    PAUSED = "paused"              # Temporarily stopped, resumable ("hold that thought")
    WAITING = "waiting"            # Blocked on human input or external dependency
    REVIEWING = "reviewing"        # Agents validating results before consolidation
    SPAWNING_CHILD = "spawning_child"  # Creating sub-sidebars for complex tasks
    CONSOLIDATING = "consolidating"    # Determining what to merge back
    MERGED = "merged"              # Successfully integrated to parent
    ARCHIVED = "archived"          # Stored in episodic memory, still citable
    FAILED = "failed"              # Unrecoverable error


class SidebarPriority(Enum):
    """Priority levels for sidebar work - affects load management."""
    CRITICAL = "critical"    # Never auto-pause, queue jumper
    HIGH = "high"            # Don't auto-pause, queue normally
    NORMAL = "normal"        # Default priority
    LOW = "low"              # Can be auto-paused for higher priority
    BACKGROUND = "background"  # Can be auto-paused, lowest priority


class AgentAvailability(Enum):
    """Agent status for recruitment."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


# =============================================================================
# CORE DATACLASSES - Sidebar and Context structures
# =============================================================================

@dataclass
class CrossRefMetadata:
    """
    Metadata for a cross-reference between contexts.

    Stored in cross_sidebar_refs dict: {target_context_id: CrossRefMetadata}
    This enables fast queries by ref_type, strength, etc.

    Validation fields enable human feedback on model-detected connections,
    providing calibration data for improving cross-ref accuracy over time.
    """
    # === Core Fields ===
    ref_type: str = "related_to"          # "cites", "related_to", "derived_from", "contradicts", "supersedes", "obsoletes", "implements", "blocks", "depends_on", "informs"
    strength: str = "normal"              # "speculative", "weak", "normal", "strong", "definitive"
    confidence: float = 0.0               # Model's confidence in this connection (0.0-1.0)
    discovery_method: str = "explicit"    # "explicit", "user_indicated", "semantic_similarity", etc.
    created_at: Optional[datetime] = None # When the cross-ref was created
    reason: str = ""                      # Why this cross-ref exists

    # === Clustering Fields (Phase 5) ===
    suggested_sources: List[Dict] = field(default_factory=list)  # [{source_id, suggested_at}, ...] for historical analysis
    cluster_flagged: bool = False             # Auto-flagged when 3+ sources suggest same ref

    # === Human Validation Fields ===
    human_validated: Optional[str] = None           # "true", "false", "not_sure", or None (not yet reviewed)
    validated_at: Optional[datetime] = None         # When validation occurred
    validated_by: str = "human"                     # Who validated (human now, agents later)
    validation_context_id: Optional[str] = None     # What sidebar was active during validation
    confidence_at_validation: Optional[float] = None  # Snapshot of model's confidence when validated (for calibration)
    validation_notes: Optional[str] = None          # Free text feedback from validator
    validation_priority: str = "normal"             # "urgent" (actively citing) or "normal" - auto-set to urgent when cluster_flagged
    validation_history: List[Dict] = field(default_factory=list)  # [{state, timestamp, notes, validated_by}, ...]
    chase_after: Optional[str] = None                # Per-ref override: ISO datetime string "check again Friday"


@dataclass
class SidebarContext:
    """
    Core sidebar data structure.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 4 for full spec.

    Key concept: inherited_memory is READ ONLY snapshot from parent.
    local_memory is what happens IN this sidebar.
    """
    # === Identity & Hierarchy ===
    sidebar_id: str                           # SB-{sequential} display format
    uuid: str                                 # Full UUID for internal use
    parent_context_id: Optional[str] = None   # None for root/main conversation
    child_sidebar_ids: List[str] = field(default_factory=list)  # IDs of sidebars spawned from this one
    forked_from: Optional[str] = None         # For revival of archived work

    # === Participants ===
    participants: List[str] = field(default_factory=list)  # Agent IDs
    coordinator_agent: Optional[str] = "AGENT-operator"    # Defaults to human

    # === Memory (Critical Separation) ===
    inherited_memory: List[Dict] = field(default_factory=list)  # READ ONLY snapshot
    local_memory: List[Dict] = field(default_factory=list)      # This sidebar's work
    data_refs: Dict[str, Any] = field(default_factory=dict)     # Referenced artifacts
    cross_sidebar_refs: Dict[str, Any] = field(default_factory=dict)  # {target_id: CrossRefMetadata as dict} - Links with metadata

    # === Scratchpad (Phase 5) ===
    scratchpad: Optional['Scratchpad'] = None  # Curator-managed collective notes for this sidebar

    # === Yarn Board (Phase 5) ===
    yarn_board_layout: Dict[str, Any] = field(default_factory=dict)  # YarnBoardLayout as dict - persists visual layout

    # === Relevance Tracking ===
    relevance_scores: Dict[str, float] = field(default_factory=dict)  # {exchange_id: score}
    active_focus: List[str] = field(default_factory=list)  # Exchange IDs being worked with

    # === Lifecycle ===
    status: SidebarStatus = SidebarStatus.ACTIVE
    priority: SidebarPriority = SidebarPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # === Task Definition ===
    task_description: Optional[str] = None    # What are we doing? (immutable birth record)
    success_criteria: Optional[str] = None    # What does "done" look like?
    failure_reason: Optional[str] = None      # Why it failed (if status=FAILED)

    # === Organization ===
    tags: List[str] = field(default_factory=list)  # Simple labels for categorization/filtering
    display_names: Dict[str, str] = field(default_factory=dict)  # {actor: alias} - per-actor cached aliases
    # Each actor (human, claude, agent-x) maintains their own alias independently.
    # Full provenance lives in CONTEXT_ALIAS citations; this dict is a resolution cache.


@dataclass
class AgentCapability:
    """
    Tracks what an agent can do and their current state.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 5.
    """
    agent_id: str                           # AGENT-{identifier}
    specialties: List[str] = field(default_factory=list)  # ["debugging", "research", etc.]
    availability: AgentAvailability = AgentAvailability.AVAILABLE
    current_load: int = 0                   # Number of active sidebars
    max_concurrent: int = 5                 # Max sidebars this agent can handle
    preferred_collaborators: Set[str] = field(default_factory=set)


# =============================================================================
# IMMUTABLE LOG - Permanent record of all messages
# =============================================================================

@dataclass
class ImmutableLogEntry:
    """
    Permanent, unmodifiable record of a message.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 8.2.

    Key: Once written, never changes. Checksum chain provides tamper detection.
    """
    # === Identity ===
    entry_id: str                    # MSG-{sequential}
    uuid: str                        # Full UUID for internal use

    # === Timing ===
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time_ms: Optional[int] = None  # How long to generate (agents)

    # === Content ===
    raw_content: str = ""            # Exactly what was said
    content_type: str = "text"       # "text", "code", "media_ref", "system"
    content_length: int = 0          # Character count
    token_count: Optional[int] = None

    # === Source ===
    sender: str = ""                 # Who said it (AGENT-X or human)
    sender_type: str = "human"       # "agent", "human", "system"
    context_id: str = ""             # Which sidebar/conversation
    parent_msg_id: Optional[str] = None  # What this was responding to

    # === Integrity ===
    checksum: str = ""               # SHA-256 of content
    previous_entry_checksum: str = ""  # Chain to previous (blockchain-style)

    # === Session Context ===
    session_id: str = ""
    agent_model_version: Optional[str] = None

    # === References ===
    citations_used: List[str] = field(default_factory=list)  # [CITE-89, MSG-4500]
    media_attached: List[str] = field(default_factory=list)  # [MEDIA-12]

    # === Tool Usage (agent messages) ===
    tools_invoked: Optional[List[str]] = None
    tool_results_summary: Optional[str] = None

    # === Confidence ===
    sender_confidence: Optional[float] = None
    flagged_uncertain: bool = False

    # === Error Context ===
    error_occurred: bool = False
    error_ref: Optional[str] = None

    # === Environment ===
    originating_client: str = "terminal"  # "react", "terminal", "api"
    client_version: Optional[str] = None


# =============================================================================
# GOLD CITATIONS - Realignment Waypoints
# =============================================================================

@dataclass
class GoldCitation:
    """
    GOLD = Realignment waypoint for future navigation.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 3.

    Not just "important" - it's "when you see similar symptoms, remember this exists."
    """
    gold_id: str                            # GOLD-{sequential}
    source_refs: List[str] = field(default_factory=list)  # What's being golded [MSG-X, CITE-X]
    key_insight: str = ""                   # "Variable X causes cascading auth failures"
    reuse_pattern: str = ""                 # "Test pattern: check auth state before/after X"
    trigger_conditions: List[str] = field(default_factory=list)  # "Similar symptoms: timeout + partial state"

    created_by: str = ""                    # Agent or human who flagged it
    created_in: str = ""                    # Which sidebar/conversation
    created_at: datetime = field(default_factory=datetime.now)

    confidence: float = 0.0                 # How sure are we this is valuable
    times_referenced: int = 0               # Usage counter - does this get reused?


# =============================================================================
# SCRATCHPAD - Curator-validated collective notes
# =============================================================================

@dataclass
class ScratchpadEntry:
    """
    Single finding submitted to scratchpad.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 6.6.
    See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9.4 for quick capture extension.

    Entry types:
    - "finding": Full curator validation workflow (pending → confirmed/rejected)
    - "quick_note": Just capture, no validation needed, can expire
    - "question": Queue for agent, answered = done
    - "drop": File/doc/image dropped for processing
    """
    entry_id: str                           # ENTRY-{sequential} within scratchpad
    content: str = ""                       # The actual finding text
    submitted_by: str = ""                  # Agent who found this
    submitted_at: datetime = field(default_factory=datetime.now)  # When submitted
    source_refs: List[str] = field(default_factory=list)  # Evidence [MSG-X, CITE-X]

    # === Entry Type (Phase 5 extension) ===
    entry_type: str = "finding"             # "finding", "quick_note", "question", "drop"
    media_ref: Optional[str] = None         # Link to dropped file/image/doc
    expires_at: Optional[datetime] = None   # Quick notes can auto-clean
    routed_to: Optional[str] = None         # Which agent should see this (queue routing)
    answered_at: Optional[datetime] = None  # When question was answered

    # Why this matters
    relevance_to_task: Optional[str] = None  # "This explains the auth timeout"

    # Validation (applies to "finding" entry_type)
    status: str = "pending"                 # "pending", "confirmed", "rejected"
    validated_by: Optional[str] = None      # Agent/human who validated
    validated_at: Optional[datetime] = None # When validation occurred
    validation_notes: Optional[str] = None  # Why confirmed/rejected

    # Annotations (any agent can add after confirmation)
    annotations: List[Dict] = field(default_factory=list)  # Post-confirmation notes from agents


@dataclass
class Checkpoint:
    """Progress marker within a scratchpad."""
    checkpoint_id: str                      # CHKPT-{sequential} within scratchpad
    created_at: datetime = field(default_factory=datetime.now)  # When checkpoint was created
    created_by: str = ""                    # Agent/human who created checkpoint
    summary: str = ""                       # "Completed phase 1: identified root cause"
    findings_at_checkpoint: List[str] = field(default_factory=list)  # Entry IDs confirmed at this point
    agent_annotations: Dict[str, str] = field(default_factory=dict)  # {agent_id: "note"}


@dataclass
class Scratchpad:
    """
    Curator-managed artifact for collective note-taking.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 6.6.
    """
    scratchpad_id: str                      # SCRATCH-{sidebar_id}
    sidebar_id: str                         # Which sidebar owns this
    curator_agent: str = ""                 # Who's managing validation

    # Task Definition
    task_definition: str = ""               # What this scratchpad is trying to solve
    success_criteria: str = ""              # What "done" looks like for this task

    # Findings
    confirmed_findings: List[ScratchpadEntry] = field(default_factory=list)  # Validated findings
    pending_findings: List[ScratchpadEntry] = field(default_factory=list)    # Awaiting validation
    rejected_findings: List[ScratchpadEntry] = field(default_factory=list)   # Rejected (learning signal)

    # Checkpoints
    checkpoints: List[Checkpoint] = field(default_factory=list)  # Progress markers

    # Final state
    final_summary: Optional[str] = None     # Generated at consolidation


# =============================================================================
# YARN BOARD - View layer over OZOLITH + Redis + Cross-refs
# =============================================================================
# The yarn board is NOT a separate persistence layer - it's a visualization
# that projects existing data. See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9.
#
# Data sources:
# - Historical points/events → OZOLITH (immutable audit trail)
# - Active "grabbed" state → Redis (hot, volatile)
# - Relationships (strings) → Cross-refs (existing ref_types)
# - Layout/positions → SQLite (persist so board "grows over time")

@dataclass
class YarnBoardLayout:
    """
    Persists yarn board visual layout so user can 'watch the board grow over time'.
    Stored in SQLite, linked to context.

    A "Point" on the board can be:
    - A cross-ref rendered as a pin
    - A scratchpad finding rendered as a pin
    - A sidebar context rendered as a pin
    - An OZOLITH event rendered as a pin (when relevant)
    """
    context_id: str                          # Which context's board
    point_positions: Dict[str, Dict] = field(default_factory=dict)  # {point_id: {x, y, collapsed}}
    zoom_level: float = 1.0                  # Current zoom
    focus_point: Optional[str] = None        # Currently centered point
    last_modified: datetime = field(default_factory=datetime.now)

    # View preferences
    show_archived: bool = False              # Show archived/completed points
    filter_by_priority: Optional[str] = None # Only show certain priority levels
    filter_by_type: Optional[str] = None     # Only show certain point types


@dataclass
class YarnBoardState:
    """
    Hot state for yarn board - what's currently 'grabbed'.
    Lives in Redis when implemented, with periodic snapshots to SQLite.

    This is the "working memory" of the board - what matters RIGHT NOW.
    """
    context_id: str                          # Which context's board
    grabbed_point_ids: List[str] = field(default_factory=list)  # Currently focused points
    priority_overrides: Dict[str, str] = field(default_factory=dict)  # {point_id: priority} temp bumps
    hot_refs: List[str] = field(default_factory=list)  # Frequently accessed cross-refs

    # Session tracking
    last_interaction: datetime = field(default_factory=datetime.now)
    interaction_count: int = 0               # How many times touched this session


# =============================================================================
# REDIS INTERFACE STUB - Define interface now, implement when Redis comes online
# =============================================================================
# Redis serves as cache + notifications, NOT primary storage.
# See redis_integration_discovery.md for full architecture.
#
# Rule: If losing it breaks things → SQLite. If it just slows rebuild → Redis.

class RedisInterface:
    """
    Stubbed interface for Redis operations.
    Implement when Redis container is integrated.

    This is an abstract interface - actual implementation will use redis-py.
    Stubbed methods return sensible defaults or raise NotImplementedError.
    """

    # === Yarn Board Hot State ===

    def get_yarn_state(self, context_id: str) -> Optional[YarnBoardState]:
        """Fetch current grabbed yarn for a context. Returns None if not cached."""
        return None  # Stub: not implemented yet

    def set_yarn_state(self, state: YarnBoardState) -> bool:
        """Cache yarn board state. Returns True on success."""
        return False  # Stub: not implemented yet

    def set_grabbed(self, context_id: str, point_id: str, grabbed: bool, agent_id: str = "unknown") -> bool:
        """Mark a point as grabbed/released by an agent. Returns True on success."""
        return False  # Stub: not implemented yet

    def try_grab_point(self, context_id: str, point_id: str, agent_id: str) -> Optional[Dict]:
        """
        Atomic grab attempt. Returns None if grab succeeded, Dict with existing
        grab info if collision detected. Stub always returns None (no collision detection).
        """
        return None  # Stub: can't detect collisions without Redis

    def get_grabbed_by(self, context_id: str, point_id: str) -> Optional[Dict]:
        """Get which agent has a point grabbed. Returns {agent_id, grabbed_at} or None."""
        return None  # Stub: not implemented yet

    def get_all_grabbed(self, context_id: str) -> Dict[str, Dict]:
        """Get all grabbed points with grab info. Returns {point_id: {agent_id, grabbed_at}}."""
        return {}  # Stub: not implemented yet

    # === Agent Presence ===

    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """Get agent's current status (busy, available, etc). Returns None if unknown."""
        return None  # Stub: not implemented yet

    def set_agent_busy(self, agent_id: str, busy: bool, current_task: Optional[str] = None) -> bool:
        """Mark agent as busy/available. Returns True on success."""
        return False  # Stub: not implemented yet

    # === Message Queues (for scratchpad routing) ===

    def queue_for_agent(self, agent_id: str, message: Dict) -> bool:
        """Queue a message for an agent (they'll get it when available). Returns True on success."""
        return False  # Stub: not implemented yet

    def get_agent_queue(self, agent_id: str) -> List[Dict]:
        """Fetch queued messages for an agent. Returns empty list if none."""
        return []  # Stub: not implemented yet

    def clear_agent_queue(self, agent_id: str) -> bool:
        """Clear an agent's message queue. Returns True on success."""
        return False  # Stub: not implemented yet

    # === Pub/Sub Hooks ===

    def notify_priority_change(self, context_id: str, point_id: str, new_priority: str) -> bool:
        """Publish priority change notification. Returns True on success."""
        return False  # Stub: not implemented yet

    def subscribe_to_context(self, context_id: str, callback) -> bool:
        """Subscribe to updates for a context. Callback receives update dicts. Returns True on success."""
        return False  # Stub: not implemented yet

    def unsubscribe_from_context(self, context_id: str) -> bool:
        """Unsubscribe from context updates. Returns True on success."""
        return False  # Stub: not implemented yet


# Global Redis interface - tries real client, falls back to stub
def _get_redis_interface():
    """Get Redis interface - real client if available, stub otherwise."""
    try:
        from redis_client import RedisClient
        client = RedisClient()
        if client.is_connected():
            return client
    except ImportError:
        pass
    except Exception:
        pass
    # Fall back to stub
    return RedisInterface()

redis_interface = _get_redis_interface()


# =============================================================================
# INHERITED EXCHANGE - Confidence tracking for inherited context
# =============================================================================

@dataclass
class InheritedExchange:
    """
    Wrapper for exchanges inherited from parent with confidence tracking.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 8.4.

    Key: Default to unverified until explicitly validated.
    """
    original_exchange: Dict = field(default_factory=dict)  # The exchange data from parent
    original_confidence: float = 0.0        # Parent's confidence (keep for reference)
    inherited_from: str = ""                # Parent context ID (SB-X)
    inherited_at: datetime = field(default_factory=datetime.now)  # When inherited

    # Default to unverified
    local_verification: str = "unverified"  # "confirmed", "contradicted", "unverified"
    local_confidence: Optional[float] = None  # This sidebar's confidence (None until verified)

    def effective_confidence(self) -> float:
        """What confidence should we actually use?"""
        if self.local_verification == "confirmed":
            return self.local_confidence or self.original_confidence
        elif self.local_verification == "contradicted":
            return 0.0  # Don't trust this
        else:  # unverified
            return 0.0  # Treat as unverified until checked


# =============================================================================
# EMERGENCY CACHE - Crash recovery
# =============================================================================

@dataclass
class EmergencyCache:
    """
    Preserved state for crash recovery.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 8.6.
    """
    cache_id: str                           # CACHE-{timestamp} unique identifier
    created_at: datetime = field(default_factory=datetime.now)  # When cache was created
    reason: str = ""                        # "working_memory_down", "websocket_lost", etc.

    # Preserved state
    sidebar_snapshots: Dict[str, Any] = field(default_factory=dict)  # All active sidebars
    pending_writes: List[Dict] = field(default_factory=list)         # Exchanges waiting to be written
    pending_archives: List[Dict] = field(default_factory=list)       # Findings for episodic memory
    scratchpad_states: Dict[str, Any] = field(default_factory=dict)  # All active scratchpads

    # Recovery info
    last_known_good_state: Optional[datetime] = None  # Last successful state timestamp
    services_down: List[str] = field(default_factory=list)  # Which services failed

    # Recovery guidance
    recovery_notes: List[str] = field(default_factory=list)  # Human/AI notes for recovery
    suggested_recovery_order: List[str] = field(default_factory=list)  # Services to restore in order

    # Resolution
    resolved_at: Optional[datetime] = None  # When recovery completed
    resolution_notes: Optional[str] = None  # How it was resolved


# =============================================================================
# OZOLITH - Immutable Append-Only Log with Hash Chain
# =============================================================================
# Named after the Magic: The Gathering card that preserves things.
# This is the column of truth - tamper-evident, verifiable, trustworthy.
#
# Architecture:
#   Core (machine-optimized):
#     - OzolithEntry: Hash-chained entries with decision provenance
#     - OzolithAnchor: Periodic snapshots for external verification
#     - OzolithEventType: What we log
#
#   Render Layer (human-readable, on-demand):
#     - OzolithRenderer in ozolith.py - translates for human consumption
#
#   Future (stubbed):
#     - MerkleLayer: O(log N) proofs when scale demands it
#
# Why this exists (from the AI's perspective):
#   - Decision provenance: What context did I have when I said X?
#   - Uncertainty tracking: When was I confident vs uncertain?
#   - Error forensics: When wrong, was it bad input, missing context, or bad reasoning?
#   - Verifiable history: I can walk the chain and confirm nothing's been altered.
#
# See: ozolith.py for implementation
# =============================================================================

class OzolithEventType(Enum):
    """Types of events logged in OZOLITH."""
    # Core exchanges
    EXCHANGE = "exchange"                    # User/assistant message pair

    # Sidebar lifecycle
    SIDEBAR_SPAWN = "sidebar_spawn"          # New sidebar created
    SIDEBAR_MERGE = "sidebar_merge"          # Sidebar merged back to parent
    CONTEXT_PAUSE = "context_pause"          # Context paused
    CONTEXT_RESUME = "context_resume"        # Context resumed
    CONTEXT_DELETED = "context_deleted"      # Context removed from cache (snapshot preserved)
    CONTEXT_REPARENT = "context_reparent"    # Context moved to new parent
    CROSS_REF_ADDED = "cross_ref_added"      # Cross-reference between contexts created
    CROSS_REF_REVOKED = "cross_ref_revoked"  # Cross-reference revoked (append-only pattern)
    CROSS_REF_UPDATED = "cross_ref_updated"  # Cross-reference metadata changed (strength, confidence, etc.)
    CROSS_REF_VALIDATED = "cross_ref_validated"  # Human validated a cross-reference (true/false/not_sure)
    TAGS_UPDATED = "tags_updated"            # Context tags added/removed (categorization change)
    BATCH_OPERATION = "batch_operation"      # Bulk operation executed (archive, restore, etc.)

    # Session lifecycle
    SESSION_START = "session_start"          # New session began
    SESSION_END = "session_end"              # Session ended (clean)

    # Learning signals
    CORRECTION = "correction"                # Something I said was corrected

    # Content federation
    CONTENT_INGESTION = "content_ingestion"  # External content entered the system
    CONTENT_REEMBEDDED = "content_reembedded"  # Existing content got new embedding
    CITATION_CREATED = "citation_created"    # Citation/provenance pointer created
    CONTENT_STALE = "content_stale"          # Content crossed its stale_after threshold
    RELATIONSHIP_CREATED = "relationship_created"  # Content relationship was established

    # Security/Trust
    FUCKERY_DETECTED = "fuckery_detected"    # Tampering, corruption, or trust breakdown detected

    # Meta events
    ANCHOR_CREATED = "anchor_created"        # Checkpoint was created
    VERIFICATION_RUN = "verification_run"    # Chain was verified

    # Memory lifecycle (thought tracing)
    MEMORY_STORED = "memory_stored"          # Exchange saved to working memory
    MEMORY_RETRIEVED = "memory_retrieved"    # Context pulled for LLM call
    MEMORY_ARCHIVED = "memory_archived"      # Moved from working to episodic
    MEMORY_RECALLED = "memory_recalled"      # Retrieved from episodic for context
    MEMORY_DISTILLED = "memory_distilled"    # Summarization/compression occurred
    CONFIDENCE_UPDATED = "confidence_updated"  # Trust level changed on a piece of info

    # Errors
    ERROR_LOGGED = "error_logged"            # Error occurred and was logged


@dataclass
class OzolithEntry:
    """
    Single entry in the OZOLITH immutable log.

    Hash chain: Each entry includes previous_hash, creating a blockchain-like
    chain where tampering with any entry breaks verification from that point.

    Payload varies by event_type - see OzolithPayload* classes for specifics.
    """
    # === Chain Identity ===
    sequence: int                            # Monotonic counter, never gaps
    timestamp: str                           # ISO format UTC
    previous_hash: str                       # Hash of previous entry (empty for first)

    # === Event Classification ===
    event_type: OzolithEventType
    context_id: str                          # Which sidebar/context (SB-X)
    actor: str                               # "human", "assistant", "system"

    # === Payload (event-specific data) ===
    payload: Dict = field(default_factory=dict)

    # === Integrity ===
    signature: str = ""                      # HMAC signature of entry
    entry_hash: str = ""                     # SHA-256 of entire entry (computed on creation)


# =============================================================================
# OZOLITH TYPED PAYLOADS - Required/Optional/Extra Pattern
# =============================================================================
# All payloads follow the same pattern:
#   - Required fields: Must be present, validation fails without them
#   - Optional fields: Can be present, have sensible defaults
#   - extra: Dict for fields we haven't thought of yet (evolution escape hatch)
#
# Heat mapping the 'extra' dict over time shows us what should graduate
# to optional or required fields.
# =============================================================================

@dataclass
class OzolithPayloadExchange:
    """
    Payload structure for EXCHANGE events.
    Rich decision provenance for AI self-improvement.

    Required: content, confidence
    Optional: everything else
    Extra: for discovered fields
    """
    # === REQUIRED ===
    content: str                             # The actual text (or hash for privacy)
    confidence: float                        # AI's certainty score (0.0-1.0)

    # === OPTIONAL ===
    # Uncertainty tracking
    uncertainty_flags: List[str] = field(default_factory=list)
    # e.g., ["ambiguous_request", "limited_context", "conflicting_memories"]

    # Context that informed this response
    context_used: List[str] = field(default_factory=list)  # Memory IDs, prior exchange refs
    skinflap_score: Optional[float] = None   # Query quality assessment (if applicable)

    # Reasoning metadata
    reasoning_type: str = ""                 # "retrieval", "inference", "creative"
    retrieved_memory_ids: List[str] = field(default_factory=list)
    context_depth: int = 0                   # How many inherited exchanges I had

    # Performance (optional - useful for optimization)
    token_count: Optional[int] = None
    latency_ms: Optional[int] = None

    # Privacy-preserving hashes (alternative to storing raw content)
    query_hash: str = ""                     # SHA-256 of user message
    response_hash: str = ""                  # SHA-256 of response

    # === EXTRA (evolution escape hatch) ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadCorrection:
    """
    Payload for CORRECTION events.
    Critical learning signal - what went wrong and why.

    Required: corrects_sequence, what_was_wrong, reasoning
    Optional: validation_status, validation metadata
    Extra: for discovered fields
    """
    # === REQUIRED ===
    corrects_sequence: int                   # Which entry is being corrected
    what_was_wrong: str                      # Categorized: "factual", "approach", "misunderstanding", "incomplete", "off_topic"
    reasoning: str                           # Why this was wrong / what the correct answer is

    # === OPTIONAL ===
    validation_status: str = "pending"       # "pending", "validated", "human_confirmed"
    validated_by: Optional[str] = None       # Who validated (if validated)
    validated_at: Optional[str] = None       # ISO timestamp of validation

    # Validation metadata (from validate_correction_target)
    target_exists: bool = True               # Did the target entry exist?
    keyword_overlap: float = 0.0             # How well correction matches target content
    validation_warnings: List[str] = field(default_factory=list)

    # Human confirmation (if human_confirmed)
    confirmed_by: Optional[str] = None
    confirmation_notes: str = ""

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadSidebarSpawn:
    """
    Payload for SIDEBAR_SPAWN events.
    Why a new context was created.

    Required: spawn_reason, parent_context
    Optional: inherited info, task definition
    Extra: for discovered fields
    """
    # === REQUIRED ===
    spawn_reason: str                        # Why sidebar was created
    parent_context: str                      # What it branched from (context ID)

    # === OPTIONAL ===
    child_id: str = ""                       # The new sidebar's ID (if different from context_id)
    inherited_count: int = 0                 # How many exchanges inherited from parent
    task_description: str = ""               # What this sidebar is meant to do
    success_criteria: str = ""               # What "done" looks like

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadSidebarMerge:
    """
    Payload for SIDEBAR_MERGE events.
    What was learned and brought back.

    Required: merge_summary
    Optional: exchange counts, preserved insights
    Extra: for discovered fields
    """
    # === REQUIRED ===
    merge_summary: str                       # What was learned/accomplished

    # === OPTIONAL ===
    parent_context: str = ""                 # What it merged back into
    exchange_count: int = 0                  # How many exchanges happened in sidebar
    preserved_insights: List[str] = field(default_factory=list)  # Key takeaways
    artifacts_created: List[str] = field(default_factory=list)   # CITE-X, GOLD-X refs
    summary_hash: str = ""                   # Hash of merge summary (for verification)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


# Keep backward compatibility alias
@dataclass
class OzolithPayloadSidebar:
    """
    DEPRECATED: Use OzolithPayloadSidebarSpawn or OzolithPayloadSidebarMerge instead.
    Kept for backward compatibility during transition.
    """
    parent_id: str = ""                     # Parent context ID
    child_id: str = ""                      # New sidebar ID (for spawns)
    reason: str = ""                        # Why spawning/merging
    inherited_count: int = 0                # Exchanges inherited from parent
    exchange_count: int = 0                 # Exchanges in sidebar (for merge)
    summary_hash: str = ""                  # Hash of merge summary
    extra: Dict[str, Any] = field(default_factory=dict)  # Extension fields


@dataclass
class OzolithPayloadSession:
    """
    Payload for SESSION_START and SESSION_END events.
    Tracks session boundaries.

    Required: session_id, interface
    Optional: summary, exchange count
    Extra: for discovered fields
    """
    # === REQUIRED ===
    session_id: str                          # Unique session identifier
    interface: str                           # "cli", "react", "ide", "api"

    # === OPTIONAL ===
    summary: str = ""                        # What happened this session (for SESSION_END)
    exchange_count: Optional[int] = None     # How many exchanges (for SESSION_END)
    duration_seconds: Optional[int] = None   # Session length (for SESSION_END)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadContextPause:
    """
    Payload for CONTEXT_PAUSE events.
    Why a context was paused.

    Required: reason
    Optional: state summary, expected resume
    Extra: for discovered fields
    """
    # === REQUIRED ===
    reason: str                              # Why paused ("user_request", "idle_timeout", "priority_preempt")

    # === OPTIONAL ===
    state_summary: str = ""                  # What was happening when paused
    expected_resume: Optional[str] = None    # When we expect to resume (if known)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadContextResume:
    """
    Payload for CONTEXT_RESUME events.
    Context coming back from pause.

    Required: reason
    Optional: pause duration, state on resume
    Extra: for discovered fields
    """
    # === REQUIRED ===
    reason: str                              # Why resuming ("user_request", "scheduled", "priority_available")

    # === OPTIONAL ===
    pause_duration_seconds: Optional[int] = None  # How long was it paused
    paused_at_sequence: Optional[int] = None      # Last sequence before pause
    state_on_resume: str = ""                     # What we're resuming to

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadContextReparent:
    """
    Payload for CONTEXT_REPARENT events.
    Context moved to a new parent, preserving audit trail.

    Required: old_parent_id, new_parent_id, reason
    Optional: confidence, pattern detection, children moved
    Extra: for discovered fields

    Claude's Notes:
    - confidence helps models learn which reparent suggestions were good
    - pattern_detected captures WHY the model thought these should unify
    - suggested_by_model tracks whether a model initiated or human did
    """
    # === REQUIRED ===
    old_parent_id: Optional[str]            # Previous parent (None if was root)
    new_parent_id: Optional[str]            # New parent (None if becoming root)
    reason: str                              # Why reparenting ("unification", "reorganization", etc.)

    # === OPTIONAL (model learning signals) ===
    confidence: float = 0.0                  # How confident was model this was correct? (0.0-1.0)
    suggested_by_model: bool = False         # Did model suggest this, or did human initiate?
    pattern_detected: str = ""               # What pattern triggered unification suggestion?
    children_moved: List[str] = field(default_factory=list)  # Child context IDs that moved with this
    original_conversation_id: Optional[str] = None  # Preserved for history ("this was once its own thing")
    requested_by: str = "system"             # Who requested the reparent

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadCrossRefAdded:
    """
    Payload for CROSS_REF_ADDED events.
    Cross-reference created between contexts in different trees.

    Required: source_context_id, target_context_id, ref_type
    Optional: confidence, discovery method, strength
    Extra: for discovered fields

    Claude's Notes:
    - discovery_method tells me HOW I found the connection (helps calibrate)
    - confidence + human_validated together let me learn what connections are valuable
    - strength distinguishes "weak maybe" from "definite citation"
    """
    # === REQUIRED ===
    source_context_id: str                  # Context that contains the reference
    target_context_id: str                  # Context being referenced
    ref_type: str                           # Type: "cites", "related_to", "derived_from", "contradicts", "supersedes", "obsoletes", "implements"

    # === OPTIONAL (Claude's learning signals) ===
    confidence: float = 0.0                  # How sure am I this connection is real? (0.0-1.0)
    discovery_method: str = "explicit"       # "explicit", "user_indicated", "semantic_similarity", "topic_overlap", "citation_extracted", "temporal_proximity", "pattern_match"
    strength: str = "normal"                 # "speculative", "weak", "normal", "strong", "definitive"
    human_validated: Optional[bool] = None   # None=not yet reviewed, True/False=human judgment
    reason: str = ""                         # Why the reference was created
    bidirectional: bool = True               # Whether reverse ref was auto-created
    exchange_id: Optional[str] = None        # Specific exchange containing the reference

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadCrossRefRevoked:
    """
    Payload for CROSS_REF_REVOKED events.
    Revokes a previously created cross-reference (append-only pattern).

    Required: source_context_id, target_context_id, reason
    Optional: replacement refs, corrected understanding
    Extra: for discovered fields

    Model Learning Signals:
    - replacement_refs captures the CORRECT connection if the revoked one was wrong
    - corrected_understanding explains WHY the original was wrong (calibration)
    - revoked_by tracks human vs model for trust calibration
    """
    # === REQUIRED ===
    source_context_id: str                   # Original source context
    target_context_id: str                   # Original target context
    reason: str                              # Why revoking this cross-ref

    # === OPTIONAL ===
    revoked_by: str = "human"                # "human" or "model"
    replacement_refs: List[str] = field(default_factory=list)  # "See SB-12, SB-15 instead"
    corrected_understanding: str = ""        # "These weren't related - SB-5 is about auth, SB-8 is about logging"

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadCrossRefUpdated:
    """
    Payload for CROSS_REF_UPDATED events.
    Updates metadata on an existing cross-reference without revoke/re-add cycle.

    Required: source_context_id, target_context_id, reason
    Optional: new values for strength, confidence, ref_type
    Extra: for discovered fields

    Model Learning Signals:
    - Tracks how assessments change over time (weak -> strong)
    - old_* values preserve what I thought before for calibration
    - reason captures WHY the update happened
    """
    # === REQUIRED ===
    source_context_id: str                   # Context containing the reference
    target_context_id: str                   # Context being referenced
    reason: str                              # Why updating this cross-ref

    # === OPTIONAL (what changed) ===
    old_strength: Optional[str] = None       # Previous strength value
    new_strength: Optional[str] = None       # New strength value
    old_confidence: Optional[float] = None   # Previous confidence
    new_confidence: Optional[float] = None   # New confidence
    old_ref_type: Optional[str] = None       # Previous ref_type
    new_ref_type: Optional[str] = None       # New ref_type
    old_validation_priority: Optional[str] = None  # Previous priority ("normal", "urgent")
    new_validation_priority: Optional[str] = None  # New priority
    updated_by: str = "human"                # "human" or "model"

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadCrossRefValidated:
    """
    Payload for CROSS_REF_VALIDATED events.
    Records human validation of a model-detected cross-reference.

    Required: source_context_id, target_context_id, validation_state
    Optional: notes, context where validation occurred
    Extra: for discovered fields

    Calibration Signals:
    - confidence_at_validation captures model's confidence when human judged
    - Enables analysis: "When I was 0.8 confident, humans agreed X% of time"
    - previous_state tracks flips for learning from changed minds
    """
    # === REQUIRED ===
    source_context_id: str                   # Context containing the reference
    target_context_id: str                   # Context being referenced
    validation_state: str                    # "true", "false", "not_sure"

    # === OPTIONAL ===
    validated_by: str = "human"              # Who validated (human now, agents later)
    validation_notes: Optional[str] = None   # Free text feedback from validator
    confidence_at_validation: float = 0.0    # Model's confidence when validated (for calibration)
    validation_context_id: Optional[str] = None  # What sidebar was active during validation
    validation_priority: str = "normal"      # Was this "urgent" or "normal"
    previous_state: Optional[str] = None     # For flips: what was validation_state before?
    chase_after: Optional[str] = None        # If set, per-ref override for next check (ISO datetime)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchOperation:
    """
    Tracks a bulk operation (archive, restore, etc.) for undo capability.

    Used to:
    - Group related operations under one batch_id
    - Enable "undo batch" functionality
    - Provide rich audit trail for bulk changes

    Stored in Ozolith via BATCH_OPERATION event.
    """
    # === Identity ===
    batch_id: str                              # BATCH-{sequential}
    operation_type: str                        # "bulk_archive", "bulk_restore", "bulk_tag", etc.

    # === What Was Requested ===
    criteria: Dict[str, Any] = field(default_factory=dict)  # Filter criteria used

    # === What Happened ===
    affected_ids: List[str] = field(default_factory=list)   # All context IDs affected
    affected_count: int = 0

    # === Provenance ===
    executed_at: datetime = field(default_factory=datetime.now)
    executed_by: str = "human"                 # human, claude, agent-id

    # === Context for Recovery ===
    reason: str = ""                           # Why this batch was run
    notes: str = ""                            # Additional context

    # === Recovery Info ===
    pre_operation_states: Dict[str, str] = field(default_factory=dict)  # {context_id: previous_status}
    reversible: bool = True                    # Can this batch be undone?
    reversed_by_batch: Optional[str] = None    # If undone, which batch reversed it

    # === Status ===
    status: str = "completed"                  # "completed", "partial", "failed", "reversed"

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadBatchOperation:
    """
    Payload for BATCH_OPERATION events.
    Logged when any bulk operation runs.

    Required: batch_id, operation_type, affected_count
    Optional: criteria, affected_ids (sample), reason
    Extra: for discovered fields

    Learning Signals:
    - Track which bulk operations tend to need reversal
    - Understand common cleanup patterns
    - pre_operation_states enables precise undo
    """
    # === REQUIRED ===
    batch_id: str                              # BATCH-{sequential}
    operation_type: str                        # "bulk_archive", "bulk_restore"
    affected_count: int = 0

    # === OPTIONAL ===
    criteria: Dict[str, Any] = field(default_factory=dict)
    affected_ids_sample: List[str] = field(default_factory=list)  # First N IDs (not all, could be huge)
    executed_by: str = "human"
    reason: str = ""
    status: str = "completed"

    # === Recovery ===
    pre_operation_states_sample: Dict[str, str] = field(default_factory=dict)  # Sample for audit

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadVerification:
    """
    Payload for VERIFICATION_RUN events.
    Results of chain verification.

    Required: result, entries_checked
    Optional: failure point, duration
    Extra: for discovered fields
    """
    # === REQUIRED ===
    result: str                              # "valid" or "invalid"
    entries_checked: int                     # How many entries were verified

    # === OPTIONAL ===
    failure_point: Optional[int] = None      # Sequence number where verification failed (if invalid)
    failure_reason: str = ""                 # Why it failed (if invalid)
    duration_ms: Optional[int] = None        # How long verification took

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadTagsUpdated:
    """
    Payload for TAGS_UPDATED events.
    Logged when context tags are added or removed.

    Required: context_id, action
    Optional: old_tags, new_tags, reason, confidence

    Learning Signals:
    - Tracks who categorized what and why
    - updated_by distinguishes human vs agent categorization
    - confidence allows tentative vs certain categorization
    - reason captures WHY the categorization was made
    """
    # === REQUIRED ===
    context_id: str                          # SB-X being tagged
    action: str                              # "add", "remove", "replace"

    # === OPTIONAL ===
    tags_added: List[str] = field(default_factory=list)    # Tags that were added
    tags_removed: List[str] = field(default_factory=list)  # Tags that were removed
    old_tags: List[str] = field(default_factory=list)      # Complete tag list before change
    new_tags: List[str] = field(default_factory=list)      # Complete tag list after change
    updated_by: str = "human"                # Who made the change (human, claude, agent-id)
    reason: str = ""                         # Why this categorization (learning signal)
    confidence: float = 1.0                  # How confident in this categorization (0.0-1.0)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadAnchor:
    """
    Payload for ANCHOR_CREATED events.
    Checkpoint creation metadata.

    Required: trigger_reason, sequence_range, entries_covered
    Optional: external storage info
    Extra: for discovered fields
    """
    # === REQUIRED ===
    trigger_reason: str                      # Why anchor was created ("manual", "count", "time", "event", "skinflap")
    sequence_range: tuple                    # (first_seq, last_seq) covered
    entries_covered: int                     # How many entries this anchor covers

    # === OPTIONAL ===
    anchor_id: str = ""                      # The anchor's ID (ANCHOR-X)
    root_hash: str = ""                      # Hash at anchor time
    external_storage: str = ""               # Where anchor was exported (if anywhere)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadError:
    """
    Payload for ERROR_LOGGED events.
    Error forensics and recovery tracking.

    Required: error_type, error_message
    Optional: stack context, recovery action
    Extra: for discovered fields
    """
    # === REQUIRED ===
    error_type: str                          # Categorized: "runtime", "validation", "network", "storage", "unknown"
    error_message: str                       # The actual error message

    # === OPTIONAL ===
    stack_context: str = ""                  # What was happening when error occurred
    recovery_action: str = ""                # What we did about it ("retry", "skip", "abort", "escalate")
    recovery_successful: Optional[bool] = None  # Did recovery work?
    related_sequence: Optional[int] = None   # Which entry this error relates to (if any)

    # Error source
    source_component: str = ""               # Which component threw the error
    source_function: str = ""                # Which function

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithAnchor:
    """
    Periodic snapshot for external verification.

    Export this, store it somewhere you control (email, print, external drive).
    Later, verify the log hasn't changed since anchor was created.
    """
    anchor_id: str                           # ANCHOR-{sequential}
    timestamp: str                           # ISO format UTC
    sequence_range: tuple                    # (first_seq, last_seq) covered
    root_hash: str                           # Hash of latest entry at anchor time
    entry_count: int                         # Total entries in log
    signature: str = ""                      # HMAC of anchor

    # Trigger info
    trigger_reason: str = ""                 # "manual", "count_threshold", "time_threshold", "skinflap_high"

    # Extension
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadContentIngestion:
    """
    Payload for logging content ingestion events to OZOLITH.
    Tracks when external content enters the system.

    Required: content_id, source_type, original_path
    Optional: processing details, embedding info
    Extra: for discovered fields
    """
    # === REQUIRED ===
    content_id: str                          # CONTENT-{hash} identifier
    source_type: str                         # ContentSourceType value
    original_path: str                       # Where the original lives

    # === OPTIONAL ===
    original_hash: str = ""                  # SHA-256 of original
    pipeline_used: str = ""                  # ProcessingPipeline value
    processing_status: str = ""              # ProcessingStatus value
    embedding_id: Optional[str] = None       # Reference to embedding
    embedding_model: str = ""                # Which model embedded it
    ingestion_notes: str = ""                # Any notes about the ingestion

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadCitation:
    """
    Payload for logging citation creation events to OZOLITH.
    Tracks when provenance pointers are created.

    Required: citation_id, citation_type, target_id
    Optional: context, metadata
    Extra: for discovered fields
    """
    # === REQUIRED ===
    citation_id: str                         # CITE-{sequential} identifier
    citation_type: str                       # CitationType value
    target_id: str                           # What's being cited

    # === OPTIONAL ===
    target_type: str = ""                    # "exchange", "content", "sidebar", "gold", etc.
    target_sequence: Optional[int] = None    # Sequence number if citing OZOLITH entry
    cited_from_context: str = ""             # Which context created the citation
    relevance_note: str = ""                 # Why this was cited
    confidence_at_citation: Optional[float] = None  # Confidence when cited

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadContentStale:
    """
    Payload for logging when content crosses its stale_after threshold.
    Signals that content should be re-verified or updated.

    Required: content_id, stale_after, detected_at
    Optional: staleness details, recommendations
    Extra: for discovered fields
    """
    # === REQUIRED ===
    content_id: str                          # CONTENT-{hash} identifier
    stale_after: str                         # ISO timestamp of stale_after threshold
    detected_at: str                         # ISO timestamp when staleness was detected

    # === OPTIONAL ===
    staleness_reason: str = ""               # StalenessReason value
    days_overdue: int = 0                    # How many days past stale_after
    last_verified_at: Optional[str] = None   # When content was last verified current
    recommended_action: str = ""             # "re_verify", "update", "archive", etc.
    auto_flagged: bool = True                # Was this detected automatically?

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadRelationshipCreated:
    """
    Payload for logging when content relationships are established.
    Tracks the provenance of relationship creation.

    Required: relationship_id, relationship_type, source_content_id, target_content_id
    Optional: confidence, notes, inverse tracking
    Extra: for discovered fields
    """
    # === REQUIRED ===
    relationship_id: str                     # REL-{sequential} identifier
    relationship_type: str                   # ContentRelationType value
    source_content_id: str                   # The "from" content
    target_content_id: str                   # The "to" content

    # === OPTIONAL ===
    confidence: float = 1.0                  # How confident in this relationship
    created_by: str = ""                     # Who/what established the relationship
    relationship_note: str = ""              # Context about the relationship
    inverse_relationship_id: Optional[str] = None  # ID of the inverse if created bidirectionally
    bidirectional: bool = False              # Was this created via create_bidirectional_relationship?

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadFuckeryDetected:
    """
    Payload for logging when tampering, corruption, or trust breakdown is detected.
    This is a security/integrity event that warrants investigation.

    Required: detection_type, affected_ids, evidence_summary
    Optional: severity, recommended_action, investigation details
    Extra: for discovered fields
    """
    # === REQUIRED ===
    detection_type: str                      # "hash_mismatch", "impossible_timestamp", "orphan_reference", etc.
    affected_ids: List[str] = field(default_factory=list)  # IDs of affected content/relationships
    evidence_summary: str = ""               # Brief description of what triggered detection

    # === OPTIONAL ===
    severity: str = "warning"                # "info", "warning", "critical"
    detected_by: str = ""                    # What process/check detected this
    detected_at: str = ""                    # ISO timestamp
    recommended_action: str = ""             # "investigate", "quarantine", "re_verify", "rollback"
    investigation_notes: str = ""            # Notes from initial investigation
    false_positive: Optional[bool] = None    # If investigated, was it a false alarm?
    resolution: str = ""                     # How it was resolved (if resolved)

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


class ReembedTrigger(Enum):
    """
    What triggered a re-embedding operation.
    """
    MODEL_UPGRADE = "model_upgrade"          # Switching to a better embedding model
    QUALITY_ISSUE = "quality_issue"          # Current embedding performing poorly
    SCHEDULED_REFRESH = "scheduled_refresh"  # Routine re-embedding cycle
    MANUAL_REQUEST = "manual_request"        # Human requested re-embed
    CONTENT_UPDATED = "content_updated"      # Original content changed (hash mismatch)
    BATCH_MIGRATION = "batch_migration"      # Part of mass re-embedding operation
    DRIFT_DETECTED = "drift_detected"        # Embedding space drift - old vectors no longer comparable to new
    FUCKERY_DETECTED = "fuckery_detected"    # Something doesn't add up - tampering, corruption, or trust breakdown


class EmbeddingDisposition(Enum):
    """
    What happened to the old embedding after re-embedding.
    Note: We never delete - everything is preserved as a receipt.
    """
    ARCHIVED = "archived"                    # Moved to archive, still accessible (default)
    KEPT_AS_FALLBACK = "kept_as_fallback"    # Still active as backup if new has issues
    SUPERSEDED = "superseded"                # Marked as replaced, kept for history
    CORRECTED = "corrected"                  # Was wrong - don't use as fallback, learning signal


@dataclass
class OzolithPayloadReembedding:
    """
    Payload for CONTENT_REEMBEDDED events.
    Tracks when existing content gets a new embedding.

    Required: content_id, previous_embedding_id, new_embedding_id, trigger_reason
    Optional: batch info, models, verification, disposition
    Extra: for quality metrics and future needs
    """
    # === REQUIRED ===
    content_id: str                          # CONTENT-X being re-embedded
    previous_embedding_id: str               # Old embedding ID
    new_embedding_id: str                    # New embedding ID
    trigger_reason: str                      # ReembedTrigger value

    # === OPTIONAL ===
    # Model info
    previous_embedding_model: str = ""       # What model created old embedding
    new_embedding_model: str = ""            # What model created new embedding

    # Batch tracking (for mass re-embeds)
    batch_id: Optional[str] = None           # BATCH-X if part of batch operation
    batch_reason: str = ""                   # Why the batch is happening

    # Verification
    content_hash_verified: bool = False      # Did we verify original content unchanged?
    content_hash_at_reembed: str = ""        # Hash of content when re-embedded

    # Old embedding disposition
    old_embedding_disposition: str = "archived"  # EmbeddingDisposition value
    archive_location: str = ""               # Where old embedding was archived

    # === EXTRA (quality metrics, etc.) ===
    extra: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MEMORY LIFECYCLE PAYLOADS
# =============================================================================

@dataclass
class OzolithPayloadMemoryStored:
    """
    Payload for MEMORY_STORED events.
    Logged when an exchange is saved to working memory.

    Required: exchange_id, conversation_id
    """
    # === REQUIRED ===
    exchange_id: str                         # EXCH-X being stored
    conversation_id: str                     # Which conversation this belongs to

    # === OPTIONAL ===
    context_id: str = ""                     # SB-X if in a sidebar
    content_hash: str = ""                   # Hash of content for verification
    token_count: int = 0                     # How many tokens in this exchange
    confidence: float = 0.0                  # Confidence score at storage time
    storage_location: str = "working_memory" # Where it was stored

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadMemoryRetrieved:
    """
    Payload for MEMORY_RETRIEVED events.
    Logged when context is pulled for LLM call.

    This is the key event for thought tracing - shows what informed a response.

    Required: for_exchange, retrieved_ids
    """
    # === REQUIRED ===
    for_exchange: str                        # EXCH-X being generated (the NEW one)
    retrieved_ids: List[str] = field(default_factory=list)  # [EXCH-1, EXCH-2, ...] what was pulled

    # === OPTIONAL ===
    conversation_id: str = ""                # Which conversation
    context_id: str = ""                     # SB-X if in a sidebar
    total_tokens: int = 0                    # Total tokens in retrieved context
    retrieval_method: str = ""               # "recent", "semantic", "hybrid", etc.
    from_working: int = 0                    # How many came from working memory
    from_episodic: int = 0                   # How many came from episodic memory

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadMemoryArchived:
    """
    Payload for MEMORY_ARCHIVED events.
    Logged when exchange moves from working memory to episodic memory.

    Required: exchange_id, reason
    """
    # === REQUIRED ===
    exchange_id: str                         # EXCH-X being archived
    reason: str                              # "distillation", "session_end", "manual", etc.

    # === OPTIONAL ===
    conversation_id: str = ""                # Which conversation
    context_id: str = ""                     # SB-X if in a sidebar
    age_at_archive_seconds: int = 0          # How old was this exchange
    was_distilled: bool = False              # Was it summarized during archive
    archive_location: str = "episodic"       # Where it went

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadMemoryRecalled:
    """
    Payload for MEMORY_RECALLED events.
    Logged when information is retrieved from episodic memory.

    Required: recalled_ids, recall_reason
    """
    # === REQUIRED ===
    recalled_ids: List[str] = field(default_factory=list)  # What was pulled from episodic
    recall_reason: str = ""                  # "context_building", "search", "switch_conversation"

    # === OPTIONAL ===
    for_exchange: str = ""                   # EXCH-X this recall is for (if applicable)
    conversation_id: str = ""                # Which conversation
    search_query: str = ""                   # If this was a search, what was searched
    similarity_scores: List[float] = field(default_factory=list)  # Relevance scores

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadMemoryDistilled:
    """
    Payload for MEMORY_DISTILLED events.
    Logged when summarization/compression occurs.

    Required: original_ids, distilled_to
    """
    # === REQUIRED ===
    original_ids: List[str] = field(default_factory=list)  # EXCH-X, EXCH-Y that were compressed
    distilled_to: str = ""                   # New summary/compressed ID

    # === OPTIONAL ===
    conversation_id: str = ""                # Which conversation
    compression_ratio: float = 0.0           # How much smaller (0.5 = half the tokens)
    original_tokens: int = 0                 # Tokens before
    distilled_tokens: int = 0                # Tokens after
    distillation_method: str = ""            # "llm_summary", "key_extraction", etc.
    preserved_key_points: int = 0            # How many key points preserved

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OzolithPayloadConfidenceUpdated:
    """
    Payload for CONFIDENCE_UPDATED events.
    Logged when trust level changes on a piece of information.

    Required: target_id, old_confidence, new_confidence, reason
    """
    # === REQUIRED ===
    target_id: str = ""                      # EXCH-X or content ID being updated
    old_confidence: float = 0.0              # Previous confidence
    new_confidence: float = 0.0              # New confidence
    reason: str = ""                         # Why it changed

    # === OPTIONAL ===
    conversation_id: str = ""                # Which conversation
    updated_by: str = ""                     # Who/what triggered the update
    validation_method: str = ""              # "user_correction", "cross_reference", "curator", etc.
    evidence_refs: List[str] = field(default_factory=list)  # What supported the change

    # === EXTRA ===
    extra: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# OZOLITH PAYLOAD MAPPING & VALIDATION
# =============================================================================

# Maps event types to their expected payload class
OZOLITH_PAYLOAD_MAP = {
    OzolithEventType.EXCHANGE: OzolithPayloadExchange,
    OzolithEventType.CORRECTION: OzolithPayloadCorrection,
    OzolithEventType.SIDEBAR_SPAWN: OzolithPayloadSidebarSpawn,
    OzolithEventType.SIDEBAR_MERGE: OzolithPayloadSidebarMerge,
    OzolithEventType.SESSION_START: OzolithPayloadSession,
    OzolithEventType.SESSION_END: OzolithPayloadSession,
    OzolithEventType.CONTEXT_PAUSE: OzolithPayloadContextPause,
    OzolithEventType.CONTEXT_RESUME: OzolithPayloadContextResume,
    OzolithEventType.VERIFICATION_RUN: OzolithPayloadVerification,
    OzolithEventType.ANCHOR_CREATED: OzolithPayloadAnchor,
    OzolithEventType.ERROR_LOGGED: OzolithPayloadError,
    OzolithEventType.CONTENT_INGESTION: OzolithPayloadContentIngestion,
    OzolithEventType.CONTENT_REEMBEDDED: OzolithPayloadReembedding,
    OzolithEventType.CITATION_CREATED: OzolithPayloadCitation,
    OzolithEventType.CONTENT_STALE: OzolithPayloadContentStale,
    OzolithEventType.RELATIONSHIP_CREATED: OzolithPayloadRelationshipCreated,
    OzolithEventType.FUCKERY_DETECTED: OzolithPayloadFuckeryDetected,
    # Memory lifecycle
    OzolithEventType.MEMORY_STORED: OzolithPayloadMemoryStored,
    OzolithEventType.MEMORY_RETRIEVED: OzolithPayloadMemoryRetrieved,
    OzolithEventType.MEMORY_ARCHIVED: OzolithPayloadMemoryArchived,
    OzolithEventType.MEMORY_RECALLED: OzolithPayloadMemoryRecalled,
    OzolithEventType.MEMORY_DISTILLED: OzolithPayloadMemoryDistilled,
    OzolithEventType.CONFIDENCE_UPDATED: OzolithPayloadConfidenceUpdated,
    # Context management
    OzolithEventType.CONTEXT_REPARENT: OzolithPayloadContextReparent,
    OzolithEventType.CROSS_REF_ADDED: OzolithPayloadCrossRefAdded,
    OzolithEventType.CROSS_REF_REVOKED: OzolithPayloadCrossRefRevoked,
    OzolithEventType.CROSS_REF_UPDATED: OzolithPayloadCrossRefUpdated,
    OzolithEventType.CROSS_REF_VALIDATED: OzolithPayloadCrossRefValidated,
    OzolithEventType.TAGS_UPDATED: OzolithPayloadTagsUpdated,
    OzolithEventType.BATCH_OPERATION: OzolithPayloadBatchOperation,
}

# Required fields per payload type (must be non-empty/non-default)
OZOLITH_REQUIRED_FIELDS = {
    OzolithPayloadExchange: ['content', 'confidence'],
    OzolithPayloadCorrection: ['corrects_sequence', 'what_was_wrong', 'reasoning'],
    OzolithPayloadSidebarSpawn: ['spawn_reason', 'parent_context'],
    OzolithPayloadSidebarMerge: ['merge_summary'],
    OzolithPayloadSession: ['session_id', 'interface'],
    OzolithPayloadContextPause: ['reason'],
    OzolithPayloadContextResume: ['reason'],
    OzolithPayloadVerification: ['result', 'entries_checked'],
    OzolithPayloadAnchor: ['trigger_reason', 'sequence_range', 'entries_covered'],
    OzolithPayloadError: ['error_type', 'error_message'],
    OzolithPayloadContentIngestion: ['content_id', 'source_type', 'original_path'],
    OzolithPayloadReembedding: ['content_id', 'previous_embedding_id', 'new_embedding_id', 'trigger_reason'],
    OzolithPayloadCitation: ['citation_id', 'citation_type', 'target_id'],
    OzolithPayloadContentStale: ['content_id', 'stale_after', 'detected_at'],
    OzolithPayloadRelationshipCreated: ['relationship_id', 'relationship_type', 'source_content_id', 'target_content_id'],
    OzolithPayloadFuckeryDetected: ['detection_type', 'evidence_summary'],
    # Memory lifecycle
    OzolithPayloadMemoryStored: ['exchange_id', 'conversation_id'],
    OzolithPayloadMemoryRetrieved: ['for_exchange', 'retrieved_ids'],
    OzolithPayloadMemoryArchived: ['exchange_id', 'reason'],
    OzolithPayloadMemoryRecalled: ['recalled_ids', 'recall_reason'],
    OzolithPayloadMemoryDistilled: ['original_ids', 'distilled_to'],
    OzolithPayloadConfidenceUpdated: ['target_id', 'old_confidence', 'new_confidence', 'reason'],
    # Context management
    OzolithPayloadContextReparent: ['old_parent_id', 'new_parent_id', 'reason'],
    OzolithPayloadCrossRefAdded: ['source_context_id', 'target_context_id', 'ref_type'],
    OzolithPayloadCrossRefRevoked: ['source_context_id', 'target_context_id', 'reason'],
    OzolithPayloadCrossRefUpdated: ['source_context_id', 'target_context_id', 'reason'],
    OzolithPayloadCrossRefValidated: ['source_context_id', 'target_context_id', 'validation_state'],
    OzolithPayloadTagsUpdated: ['context_id', 'action'],
    OzolithPayloadBatchOperation: ['batch_id', 'operation_type', 'affected_count'],
}


# =============================================================================
# VALIDATION CONFIGURATION
# =============================================================================

# ID pattern definitions - what each ID type should look like
ID_PATTERNS = {
    'content_id': r'^CONTENT-[a-zA-Z0-9_-]+$',
    'chunk_id': r'^CHUNK-[a-zA-Z0-9_-]+$',
    'relationship_id': r'^REL-[a-zA-Z0-9_-]+$',
    'citation_id': r'^CITE-[a-zA-Z0-9_-]+$',
    'embedding_id': r'^EMB-[a-zA-Z0-9_-]+$',
    'session_id': r'^(SESSION|SB)-[a-zA-Z0-9_-]+$',
    'batch_id': r'^BATCH-[a-zA-Z0-9_-]+$',
    'source_content_id': r'^CONTENT-[a-zA-Z0-9_-]+$',
    'target_content_id': r'^CONTENT-[a-zA-Z0-9_-]+$',
    'target_id': r'^(CONTENT|MSG|CITE|GOLD)-[a-zA-Z0-9_-]+$',
    'previous_embedding_id': r'^EMB-[a-zA-Z0-9_-]+$',
    'new_embedding_id': r'^EMB-[a-zA-Z0-9_-]+$',
}

# Fields that should match enum values
ENUM_FIELD_VALIDATORS = {
    'source_type': lambda v: v in [e.value for e in ContentSourceType],
    'pipeline_used': lambda v: v in [e.value for e in ProcessingPipeline],
    'processing_status': lambda v: v in [e.value for e in ProcessingStatus],
    'staleness_reason': lambda v: v in [e.value for e in StalenessReason],
    'relationship_type': lambda v: v in [e.value for e in ContentRelationType],
    'citation_type': lambda v: v in [e.value for e in CitationType],
    'trigger_reason': lambda v: v in [e.value for e in ReembedTrigger],
    'old_embedding_disposition': lambda v: v in [e.value for e in EmbeddingDisposition],
    # Cross-ref field validators (string-based, not enum)
    'strength': lambda v: v in ['speculative', 'weak', 'normal', 'strong', 'definitive'],
    'ref_type': lambda v: v in ['cites', 'related_to', 'derived_from', 'contradicts', 'supersedes', 'obsoletes', 'implements', 'blocks', 'depends_on', 'informs'],
    'discovery_method': lambda v: v in ['explicit', 'user_indicated', 'semantic_similarity', 'topic_overlap', 'citation_extracted', 'temporal_proximity', 'pattern_match'],
    # Validation field validators
    'validation_state': lambda v: v in ['true', 'false', 'not_sure'],
    'validation_priority': lambda v: v in ['urgent', 'normal'],
    # Scratchpad entry type validator (Phase 5)
    'entry_type': lambda v: v in ['finding', 'quick_note', 'question', 'drop'],
}

# Fields with numeric range constraints
RANGE_VALIDATORS = {
    'confidence': (0.0, 1.0),
    'confidence_at_citation': (0.0, 1.0),
    'days_overdue': (0, None),  # None means no upper bound
    'entries_checked': (0, None),
    'entries_covered': (0, None),
}

# Fields that should be valid ISO timestamps
TIMESTAMP_FIELDS = {
    'stale_after', 'detected_at', 'last_verified_at', 'created_at',
    'embedded_at', 'processed_at', 'verified_current_at'
}


def validate_ozolith_payload(event_type: OzolithEventType, payload: Dict) -> tuple:
    """
    Validate a payload dict against its expected structure.

    Performs:
    - Required field checks (present and non-empty)
    - ID pattern validation (CONTENT-xxx, REL-xxx, etc.)
    - Enum value validation (source_type must be valid ContentSourceType)
    - Range validation (confidence must be 0.0-1.0)
    - Unknown field warnings (for heat mapping)

    Returns:
        (is_valid: bool, errors: List[str], warnings: List[str])

    Usage:
        valid, errors, warnings = validate_ozolith_payload(
            OzolithEventType.EXCHANGE,
            {"content": "Hello", "confidence": 0.9}
        )
    """
    import re
    errors = []
    warnings = []

    # Check if event type has a defined payload structure
    if event_type not in OZOLITH_PAYLOAD_MAP:
        warnings.append(f"No payload structure defined for {event_type.value}")
        return (True, errors, warnings)  # Valid but unstructured

    payload_class = OZOLITH_PAYLOAD_MAP[event_type]
    required_fields = OZOLITH_REQUIRED_FIELDS.get(payload_class, [])

    # === Check required fields ===
    for field in required_fields:
        if field not in payload:
            errors.append(f"Missing required field: {field}")
        elif payload[field] is None or payload[field] == "":
            errors.append(f"Required field is empty: {field}")

    # === ID Pattern Validation ===
    for field_name, pattern in ID_PATTERNS.items():
        if field_name in payload and payload[field_name]:
            value = payload[field_name]
            if not re.match(pattern, value):
                errors.append(f"Invalid ID format for '{field_name}': '{value}' doesn't match pattern {pattern}")

    # === Enum Validation ===
    for field_name, validator in ENUM_FIELD_VALIDATORS.items():
        if field_name in payload and payload[field_name]:
            value = payload[field_name]
            if not validator(value):
                errors.append(f"Invalid enum value for '{field_name}': '{value}' is not a valid option")

    # === Range Validation ===
    for field_name, (min_val, max_val) in RANGE_VALIDATORS.items():
        if field_name in payload and payload[field_name] is not None:
            value = payload[field_name]
            if isinstance(value, (int, float)):
                if min_val is not None and value < min_val:
                    errors.append(f"Value out of range for '{field_name}': {value} < {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"Value out of range for '{field_name}': {value} > {max_val}")

    # === Timestamp Format Validation (light check) ===
    for field_name in TIMESTAMP_FIELDS:
        if field_name in payload and payload[field_name]:
            value = payload[field_name]
            # Basic ISO format check - should have date portion at minimum
            if not re.match(r'^\d{4}-\d{2}-\d{2}', value):
                warnings.append(f"Timestamp '{field_name}' may not be valid ISO format: '{value}'")

    # === Unknown Fields Warning (for heat mapping) ===
    if payload_class:
        import dataclasses
        known_fields = {f.name for f in dataclasses.fields(payload_class)}
        for key in payload:
            if key not in known_fields and key != 'extra':
                warnings.append(f"Unknown field '{key}' - consider adding to 'extra' dict")

    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)


def payload_to_dict(payload_obj) -> Dict:
    """
    Convert a typed payload dataclass to a dict for storage.
    Handles the 'extra' field by merging it into the main dict.
    """
    from dataclasses import asdict
    result = asdict(payload_obj)

    # Merge 'extra' fields into main dict and remove the extra key
    if 'extra' in result and result['extra']:
        extra = result.pop('extra')
        result.update(extra)
    elif 'extra' in result:
        del result['extra']

    return result


def dict_to_payload(event_type: OzolithEventType, payload_dict: Dict):
    """
    Convert a dict back to a typed payload dataclass.
    Unknown fields go into 'extra'.
    """
    import dataclasses

    if event_type not in OZOLITH_PAYLOAD_MAP:
        return payload_dict  # No typed structure, return as-is

    payload_class = OZOLITH_PAYLOAD_MAP[event_type]
    known_fields = {f.name for f in dataclasses.fields(payload_class)}

    # Separate known and unknown fields
    known = {}
    extra = {}

    for key, value in payload_dict.items():
        if key in known_fields:
            known[key] = value
        else:
            extra[key] = value

    # Add extra if there were unknown fields
    if extra:
        known['extra'] = extra

    return payload_class(**known)


# =============================================================================
# CONTENT FEDERATION - Tracking content sources and processing paths
# =============================================================================
# Architecture from eGain comparison (2025-12-12):
#   Original Files (preserved) → Embedding Archive → Central Context (Ozolith)
#
# Key principles:
#   - Originals are ALWAYS preserved (embeddings are lossy)
#   - Processing path tracked for provenance
#   - Citations serve multiple purposes (bookmarks, links, relationships, confidence)
#   - Different content types need different processing pipelines
# =============================================================================

class ContentSourceType(Enum):
    """
    What kind of content we're ingesting.
    Determines processing path and embedding strategy.
    """
    # Text-based (Curator agent + embedding path)
    TEXT_PLAIN = "text_plain"                # Plain .txt files
    TEXT_MARKDOWN = "text_markdown"          # .md files
    TEXT_CODE = "text_code"                  # Source code files
    TEXT_CONFIG = "text_config"              # Config files (json, yaml, toml, etc.)
    TEXT_LOG = "text_log"                    # Log files

    # Document-based (may need Docling depending on content)
    DOC_PDF_TEXT = "doc_pdf_text"            # PDF with extractable text
    DOC_PDF_SCANNED = "doc_pdf_scanned"      # PDF that's actually images (needs Docling)
    DOC_WORD = "doc_word"                    # .docx files
    DOC_SPREADSHEET = "doc_spreadsheet"      # .xlsx, .csv files

    # Visual media (Docling path)
    MEDIA_IMAGE = "media_image"              # .png, .jpg, .gif, etc.
    MEDIA_DIAGRAM = "media_diagram"          # Architecture diagrams, flowcharts
    MEDIA_SCREENSHOT = "media_screenshot"    # Screenshots (UI, errors, etc.)

    # Audio/Video (transcription path)
    MEDIA_AUDIO = "media_audio"              # Audio files needing transcription
    MEDIA_VIDEO = "media_video"              # Video files needing transcription

    # Conversation/Exchange (internal - already in system format)
    EXCHANGE = "exchange"                    # Chat exchange from our system
    SIDEBAR = "sidebar"                      # Sidebar content

    # Unknown/Other
    UNKNOWN = "unknown"                      # Needs manual classification


# =============================================================================
# CONTENT TYPE → PIPELINE MAPPING
# =============================================================================
# Which processing pipeline should be used for each content type.
# This is the architectural specification - use this for routing decisions.

CONTENT_TYPE_TO_PIPELINE_MAP = {
    # Text-based → Curator pipeline (text extraction + embedding)
    'TEXT_PLAIN': 'CURATOR',
    'TEXT_MARKDOWN': 'CURATOR',
    'TEXT_CODE': 'CURATOR',
    'TEXT_CONFIG': 'CURATOR',
    'TEXT_LOG': 'CURATOR',

    # Document-based → Curator for extractable text, Docling for complex
    'DOC_PDF_TEXT': 'CURATOR',           # Has extractable text
    'DOC_PDF_SCANNED': 'DOCLING',         # Needs OCR
    'DOC_WORD': 'CURATOR',
    'DOC_SPREADSHEET': 'CURATOR',

    # Visual media → Docling (image understanding)
    'MEDIA_IMAGE': 'DOCLING',
    'MEDIA_DIAGRAM': 'DOCLING',
    'MEDIA_SCREENSHOT': 'DOCLING',

    # Audio/Video → Transcription service
    'MEDIA_AUDIO': 'TRANSCRIPTION',
    'MEDIA_VIDEO': 'TRANSCRIPTION',

    # Internal content → Direct (already in system format)
    'EXCHANGE': 'DIRECT',
    'SIDEBAR': 'DIRECT',

    # Unknown → Manual classification required
    'UNKNOWN': 'MANUAL',
}


def get_pipeline_for_content_type(content_type: 'ContentSourceType') -> 'ProcessingPipeline':
    """
    Get the recommended processing pipeline for a content type.

    Args:
        content_type: A ContentSourceType enum value

    Returns:
        The recommended ProcessingPipeline for this content type
    """
    pipeline_name = CONTENT_TYPE_TO_PIPELINE_MAP.get(content_type.name, 'MANUAL')
    return ProcessingPipeline[pipeline_name]


# Default staleness periods by content type (in days)
# None = doesn't go stale (historical/internal content)
# These are starting points - adjust as we learn from usage patterns
STALENESS_DEFAULTS_DAYS = {
    # Code/config changes frequently
    ContentSourceType.TEXT_CODE: 14,
    ContentSourceType.TEXT_CONFIG: 7,
    ContentSourceType.TEXT_LOG: None,        # Logs don't go "stale" - they're historical

    # Text docs - moderate
    ContentSourceType.TEXT_PLAIN: 30,
    ContentSourceType.TEXT_MARKDOWN: 30,

    # Formal docs - slower to change
    ContentSourceType.DOC_PDF_TEXT: 60,
    ContentSourceType.DOC_PDF_SCANNED: 60,
    ContentSourceType.DOC_WORD: 60,
    ContentSourceType.DOC_SPREADSHEET: 30,   # Data might update more

    # Media - usually stable
    ContentSourceType.MEDIA_IMAGE: 90,
    ContentSourceType.MEDIA_DIAGRAM: 60,     # Architecture diagrams change
    ContentSourceType.MEDIA_SCREENSHOT: 30,  # UI changes
    ContentSourceType.MEDIA_AUDIO: 90,
    ContentSourceType.MEDIA_VIDEO: 90,

    # Internal - managed elsewhere
    ContentSourceType.EXCHANGE: None,
    ContentSourceType.SIDEBAR: None,
    ContentSourceType.UNKNOWN: 30,
}


class ProcessingPipeline(Enum):
    """
    Which processing path was used to ingest content.
    """
    CURATOR = "curator"                      # Curator agent + embedding agents (text content)
    DOCLING = "docling"                      # Docling (visual/complex documents)
    TRANSCRIPTION = "transcription"          # Audio/video transcription service
    DIRECT = "direct"                        # Already in system format, no processing needed
    MANUAL = "manual"                        # Human manually processed/entered
    PENDING = "pending"                      # Awaiting processing


class StalenessReason(Enum):
    """
    Why content might become stale. Machine-queryable category.
    Pair with staleness_note for human-readable details.
    """
    SPRINT_CYCLE = "sprint_cycle"            # Changes with sprint cadence
    API_VERSION = "api_version"              # Tied to API/library version
    MANUAL_REVIEW = "manual_review"          # Needs human verification
    TIME_DECAY = "time_decay"                # General age-based staleness
    DEPENDENCY_CHANGE = "dependency_change"  # Upstream dependency changed
    CONTENT_UPDATED = "content_updated"      # Source file was modified
    UNKNOWN = "unknown"                      # Not categorized yet


class ChunkStrategy(Enum):
    """
    How content was chunked for embedding.
    Knowing the strategy helps with re-chunking decisions and retrieval tuning.
    """
    FIXED_SIZE = "fixed_size"                # Split at N characters/tokens
    SEMANTIC = "semantic"                    # Split at natural boundaries (sections, topics)
    PARAGRAPH = "paragraph"                  # Split at paragraph breaks
    SENTENCE = "sentence"                    # Split at sentence boundaries
    PAGE = "page"                            # One chunk per page (PDFs, docs)
    SLIDING_WINDOW = "sliding_window"        # Overlapping fixed windows
    CODE_BLOCK = "code_block"                # Split at function/class boundaries
    CUSTOM = "custom"                        # Manual or special-purpose chunking


# =============================================================================
# VALIDATION HELPERS
# =============================================================================
# These functions validate data formats used in the content federation system.
# They can be used for validation at creation time (__post_init__) or
# for explicit validation calls.
# =============================================================================

import re
from typing import Tuple


def is_valid_coco_bbox(bbox: Optional[Dict[str, float]]) -> Tuple[bool, str]:
    """
    Validate a bounding box in COCO format.

    COCO format: {x, y, width, height} where:
    - x, y: top-left corner coordinates (>= 0)
    - width, height: dimensions (> 0)

    Args:
        bbox: Dictionary with x, y, width, height keys, or None

    Returns:
        (is_valid, error_message) tuple
    """
    if bbox is None:
        return (True, "")

    required_keys = ['x', 'y', 'width', 'height']
    missing = [k for k in required_keys if k not in bbox]
    if missing:
        return (False, f"Missing required keys: {missing}")

    # Check types
    for key in required_keys:
        if not isinstance(bbox[key], (int, float)):
            return (False, f"'{key}' must be numeric, got {type(bbox[key]).__name__}")

    # Check constraints
    if bbox['x'] < 0:
        return (False, f"x must be >= 0, got {bbox['x']}")
    if bbox['y'] < 0:
        return (False, f"y must be >= 0, got {bbox['y']}")
    if bbox['width'] <= 0:
        return (False, f"width must be > 0, got {bbox['width']}")
    if bbox['height'] <= 0:
        return (False, f"height must be > 0, got {bbox['height']}")

    return (True, "")


def is_valid_smpte_timecode(timecode: Optional[str], frame_rate: Optional[float] = None) -> Tuple[bool, str]:
    """
    Validate a timecode in SMPTE ST 12 format.

    SMPTE format: HH:MM:SS:FF (hours:minutes:seconds:frames)

    Args:
        timecode: String in HH:MM:SS:FF format, or None
        frame_rate: Optional frame rate for frame number validation

    Returns:
        (is_valid, error_message) tuple
    """
    if timecode is None:
        return (True, "")

    pattern = r'^(\d{2}):(\d{2}):(\d{2}):(\d{2})$'
    match = re.match(pattern, timecode)

    if not match:
        return (False, f"Invalid SMPTE format: '{timecode}'. Expected HH:MM:SS:FF")

    hh, mm, ss, ff = map(int, match.groups())

    if hh > 23:
        return (False, f"Hours must be 0-23, got {hh}")
    if mm > 59:
        return (False, f"Minutes must be 0-59, got {mm}")
    if ss > 59:
        return (False, f"Seconds must be 0-59, got {ss}")

    # Validate frame number against frame rate if provided
    if frame_rate is not None:
        max_frames = int(frame_rate)  # Simplified - drop frame not handled
        if ff >= max_frames:
            return (False, f"Frame {ff} exceeds max {max_frames - 1} for {frame_rate}fps")

    return (True, "")


def is_valid_confidence(confidence: Optional[float]) -> Tuple[bool, str]:
    """
    Validate a confidence score.

    Confidence must be in range [0.0, 1.0].

    Args:
        confidence: Float between 0 and 1, or None

    Returns:
        (is_valid, error_message) tuple
    """
    if confidence is None:
        return (True, "")

    if not isinstance(confidence, (int, float)):
        return (False, f"Confidence must be numeric, got {type(confidence).__name__}")

    if confidence < 0.0 or confidence > 1.0:
        return (False, f"Confidence must be 0.0-1.0, got {confidence}")

    return (True, "")


def is_stale(stale_after: Optional[str]) -> bool:
    """
    Check if content has passed its stale_after timestamp.

    Args:
        stale_after: ISO format timestamp string, or None

    Returns:
        True if current time is past stale_after, False otherwise
        Returns False if stale_after is None (never stales)
    """
    if stale_after is None:
        return False

    try:
        stale_date = datetime.fromisoformat(stale_after.replace('Z', '+00:00'))
        # Handle timezone-naive comparison
        if stale_date.tzinfo is None:
            return datetime.utcnow() > stale_date
        else:
            from datetime import timezone
            return datetime.now(timezone.utc) > stale_date
    except (ValueError, TypeError):
        # Invalid timestamp format - treat as not stale but warn
        return False


def get_staleness_default_days(content_type: 'ContentSourceType') -> Optional[int]:
    """
    Get the default staleness period for a content type.

    Args:
        content_type: A ContentSourceType enum value

    Returns:
        Number of days until content is considered stale, or None if it never stales
    """
    return STALENESS_DEFAULTS_DAYS.get(content_type)


def calculate_stale_after(content_type: 'ContentSourceType', from_date: Optional[datetime] = None) -> Optional[str]:
    """
    Calculate the stale_after timestamp for a content type.

    Args:
        content_type: A ContentSourceType enum value
        from_date: Starting date (defaults to now)

    Returns:
        ISO format timestamp string, or None if content never stales
    """
    days = get_staleness_default_days(content_type)
    if days is None:
        return None

    if from_date is None:
        from_date = datetime.utcnow()

    return (from_date + timedelta(days=days)).isoformat()


class ValidationError(Exception):
    """Raised when dataclass validation fails."""
    pass


class ValidationWarning:
    """Container for validation warnings (non-fatal issues)."""
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


@dataclass
class ValidationResult:
    """
    Unified validation result for all validation operations.

    Use this for explicit validation calls. __post_init__ still raises
    ValidationError for critical failures.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def raise_if_invalid(self):
        """Raise ValidationError if not valid."""
        if not self.is_valid:
            raise ValidationError(f"Validation failed: {'; '.join(self.errors)}")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================
# These functions create dataclass instances with best practices applied:
# - Auto-generate IDs with proper prefixes
# - Apply staleness defaults based on content type
# - Set timestamps automatically
# - Validation is always on (default)
# =============================================================================

import uuid


def generate_id(prefix: str) -> str:
    """Generate a prefixed unique ID."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def create_content_reference(
    source_type: 'ContentSourceType',
    original_path: str = "",
    *,
    content_id: Optional[str] = None,
    apply_staleness_default: bool = True,
    created_by: str = "system",
    **kwargs
) -> 'ContentReference':
    """
    Create a ContentReference with best practices applied.

    - Auto-generates content_id if not provided
    - Applies staleness defaults based on source_type
    - Sets created_at timestamp
    - Validation is ON by default

    Args:
        source_type: What kind of content this is
        original_path: File path or URI to original
        content_id: Optional custom ID (auto-generated if not provided)
        apply_staleness_default: Whether to set stale_after based on type defaults
        created_by: Who/what created this reference
        **kwargs: Additional fields to pass to ContentReference

    Returns:
        Validated ContentReference instance
    """
    if content_id is None:
        content_id = generate_id("CONTENT")

    # Apply staleness default if not explicitly set
    if apply_staleness_default and 'stale_after' not in kwargs:
        kwargs['stale_after'] = calculate_stale_after(source_type)

    # Set created_at if not provided
    if 'created_at' not in kwargs:
        kwargs['created_at'] = datetime.utcnow().isoformat()

    return ContentReference(
        content_id=content_id,
        source_type=source_type,
        original_path=original_path,
        created_by=created_by,
        **kwargs
    )


def create_content_chunk(
    parent_content_id: str,
    sequence: int,
    *,
    chunk_id: Optional[str] = None,
    **kwargs
) -> 'ContentChunk':
    """
    Create a ContentChunk with auto-generated ID.

    Args:
        parent_content_id: CONTENT-X that this chunk belongs to
        sequence: Order within parent (0, 1, 2, ...)
        chunk_id: Optional custom ID (auto-generated if not provided)
        **kwargs: Additional fields to pass to ContentChunk

    Returns:
        Validated ContentChunk instance
    """
    if chunk_id is None:
        chunk_id = f"CHUNK-{parent_content_id.replace('CONTENT-', '')}-{sequence}"

    return ContentChunk(
        chunk_id=chunk_id,
        parent_content_id=parent_content_id,
        sequence=sequence,
        **kwargs
    )


def create_citation(
    citation_type: 'CitationType',
    target_id: str,
    target_type: str = "content",
    *,
    citation_id: Optional[str] = None,
    cited_by: str = "system",
    **kwargs
) -> 'CitationReference':
    """
    Create a CitationReference with auto-generated ID and timestamp.

    Args:
        citation_type: What purpose this citation serves
        target_id: ID of what's being cited
        target_type: Type of target ("exchange", "content", "sidebar", etc.)
        citation_id: Optional custom ID (auto-generated if not provided)
        cited_by: Who/what created the citation
        **kwargs: Additional fields to pass to CitationReference

    Returns:
        Validated CitationReference instance
    """
    if citation_id is None:
        citation_id = generate_id("CITE")

    # Set cited_at if not provided
    if 'cited_at' not in kwargs:
        kwargs['cited_at'] = datetime.utcnow().isoformat()

    return CitationReference(
        citation_id=citation_id,
        citation_type=citation_type,
        target_type=target_type,
        target_id=target_id,
        cited_by=cited_by,
        **kwargs
    )


class ProcessingStatus(Enum):
    """
    Current state of content processing.
    """
    # Initial states
    PENDING = "pending"                      # Awaiting processing (not yet queued)
    QUEUED = "queued"                        # In line, waiting for processing slot

    # Active states
    PROCESSING = "processing"                # Currently being processed
    RETRYING = "retrying"                    # Failed, attempting again
    BLOCKED = "blocked"                      # Waiting on external dependency

    # Terminal states
    COMPLETED = "completed"                  # Successfully processed
    PARTIAL = "partial"                      # Partially successful (e.g., 8/10 pages processed)
    FAILED = "failed"                        # Processing failed (gave up)
    SKIPPED = "skipped"                      # Intentionally not processed
    NEEDS_REVIEW = "needs_review"            # Processed but flagged for human verification


@dataclass
class ContentReference:
    """
    Reference to original content with processing provenance.

    This is the "pointer to original" that lets us:
    - Re-embed with better models later
    - Verify against ground truth
    - Track how content flowed into the system
    """
    # === Identity ===
    content_id: str                          # CONTENT-{hash} unique identifier
    source_type: ContentSourceType           # What kind of content this is

    # === Original Location ===
    original_path: str = ""                  # File path or URI to original
    original_hash: str = ""                  # SHA-256 of original content (for integrity)
    original_size_bytes: int = 0             # Size of original file

    # === Processing Info ===
    pipeline_used: ProcessingPipeline = ProcessingPipeline.PENDING  # How it was processed
    processing_status: ProcessingStatus = ProcessingStatus.PENDING  # Current status
    processed_at: Optional[str] = None       # ISO timestamp when processed
    processing_notes: str = ""               # Any notes about processing (warnings, etc.)

    # === Embedding Info ===
    embedding_id: Optional[str] = None       # Reference to embedding in vector store
    embedding_model: str = ""                # Which model created the embedding
    embedded_at: Optional[str] = None        # ISO timestamp when embedded

    # === Metadata ===
    created_at: str = ""                     # ISO timestamp when reference created
    created_by: str = ""                     # Who/what created this reference
    tags: List[str] = field(default_factory=list)  # Searchable tags

    # === Staleness Tracking ===
    verified_current_at: Optional[str] = None  # ISO timestamp when last verified still current
    stale_after: Optional[str] = None          # ISO timestamp after which content may be outdated
    staleness_reason: Optional[StalenessReason] = None  # Machine-queryable category
    staleness_note: str = ""                   # Why this might be stale / what to check (freeform)

    # === Extension ===
    extra: Dict[str, Any] = field(default_factory=dict)  # For discovered fields

    # === Validation Control ===
    # Default is True - opt OUT of safety, not opt IN
    validate: bool = field(default=True, repr=False)

    def __post_init__(self):
        """Validate content reference. Enabled by default - set validate=False to skip."""
        if not self.validate:
            return

        errors = []
        warnings = []

        # Validate content_id format
        if self.content_id:
            if not self.content_id.startswith('CONTENT-'):
                errors.append(f"content_id must start with 'CONTENT-', got '{self.content_id}'")
        else:
            errors.append("content_id cannot be empty")

        # Validate original_path is provided for non-internal types
        internal_types = {ContentSourceType.EXCHANGE, ContentSourceType.SIDEBAR}
        if self.source_type not in internal_types and not self.original_path:
            errors.append(f"original_path required for {self.source_type.value}")

        # Validate stale_after is a valid timestamp if provided
        if self.stale_after is not None:
            try:
                datetime.fromisoformat(self.stale_after.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                errors.append(f"stale_after must be ISO format timestamp, got '{self.stale_after}'")

        # Semantic check: staleness_reason + staleness_note consistency
        if self.staleness_reason is not None and self.staleness_reason != StalenessReason.UNKNOWN:
            if not self.staleness_note:
                warnings.append(
                    f"staleness_reason is {self.staleness_reason.value} but staleness_note is empty - "
                    f"consider adding context"
                )

        # Store warnings in extra for inspection
        if warnings:
            if 'validation_warnings' not in self.extra:
                self.extra['validation_warnings'] = []
            self.extra['validation_warnings'].extend(warnings)

        if errors:
            raise ValidationError(f"ContentReference validation failed: {'; '.join(errors)}")


@dataclass
class ContentChunk:
    """
    A chunk/segment of a larger document for embedding.

    Large documents get chunked before embedding. This tracks:
    - Which chunks belong to which original
    - Chunk boundaries for reconstruction
    - Individual chunk embeddings

    Validation:
        Set validate=True to enable validation on creation.
        Invalid data will raise ValidationError.
    """
    # === Identity ===
    chunk_id: str                            # CHUNK-{content_id}-{sequence}
    parent_content_id: str                   # CONTENT-X that this chunk belongs to
    sequence: int                            # Order within parent (0, 1, 2, ...)

    # === Chunking Strategy ===
    chunk_strategy: Optional[ChunkStrategy] = None  # How this chunk was created

    # === Text Boundaries (for text content) ===
    start_position: int = 0                  # Character offset in original
    end_position: int = 0                    # Character offset end
    overlap_chars: int = 0                   # How many chars overlap with adjacent chunks

    # === Visual Boundaries (for PDFs, images, diagrams) ===
    # Note: PDF uses bottom-left origin (Y up), images use top-left origin (Y down)
    page_number: Optional[int] = None        # Page number (1-indexed) for PDFs/docs
    bounding_box: Optional[Dict[str, float]] = None  # {x, y, width, height} - COCO format
    coordinate_system: str = ""              # "pdf" (bottom-left) or "image" (top-left) for clarity

    # === Temporal Boundaries (for audio/video) ===
    # SMPTE ST 12 timecode format: HH:MM:SS:FF (hours:minutes:seconds:frames)
    start_timecode: Optional[str] = None     # SMPTE format start position
    end_timecode: Optional[str] = None       # SMPTE format end position
    frame_rate: Optional[float] = None       # Frames per second (e.g., 29.97, 24, 25)
    duration_ms: Optional[int] = None        # Duration in milliseconds (alternative to timecode)

    # === Content ===
    chunk_text: str = ""                     # The actual chunk content (or hash if large)
    chunk_hash: str = ""                     # SHA-256 of chunk content
    token_count: Optional[int] = None        # Token count for this chunk

    # === Embedding ===
    embedding_id: Optional[str] = None       # This chunk's embedding in vector store
    embedding_model: str = ""                # Model used for this chunk
    embedded_at: Optional[str] = None        # When this chunk was embedded

    # === Extension ===
    extra: Dict[str, Any] = field(default_factory=dict)

    # === Validation Control ===
    # Default is True - opt OUT of safety, not opt IN
    validate: bool = field(default=True, repr=False)

    def __post_init__(self):
        """Validate chunk data. Enabled by default - set validate=False to skip."""
        if not self.validate:
            return

        errors = []

        # Validate bounding box if present
        if self.bounding_box is not None:
            valid, msg = is_valid_coco_bbox(self.bounding_box)
            if not valid:
                errors.append(f"bounding_box: {msg}")

        # Validate timecodes if present
        if self.start_timecode is not None:
            valid, msg = is_valid_smpte_timecode(self.start_timecode, self.frame_rate)
            if not valid:
                errors.append(f"start_timecode: {msg}")

        if self.end_timecode is not None:
            valid, msg = is_valid_smpte_timecode(self.end_timecode, self.frame_rate)
            if not valid:
                errors.append(f"end_timecode: {msg}")

        # Validate position logic
        if self.end_position < self.start_position and self.end_position != 0:
            errors.append(f"end_position ({self.end_position}) cannot be less than start_position ({self.start_position})")

        # Validate page number if present
        if self.page_number is not None and self.page_number < 1:
            errors.append(f"page_number must be >= 1, got {self.page_number}")

        if errors:
            raise ValidationError(f"ContentChunk validation failed: {'; '.join(errors)}")


class ContentRelationType(Enum):
    """
    Types of relationships between content items.
    Use create_bidirectional_relationship() to create both directions atomically.
    """
    # Containment
    CONTAINS = "contains"                    # PDF contains images, archive contains files
    CONTAINED_BY = "contained_by"            # Inverse of CONTAINS

    # Code Dependencies (specific to imports/includes)
    IMPORTS = "imports"                      # Code imports other code
    IMPORTED_BY = "imported_by"              # Inverse of IMPORTS

    # General Dependencies (broader than code imports)
    DEPENDS_ON = "depends_on"                # Config depends on schema, deployment needs artifact
    DEPENDENCY_OF = "dependency_of"          # Inverse of DEPENDS_ON

    # References
    REFERENCES = "references"                # Document references another document
    REFERENCED_BY = "referenced_by"          # Inverse of REFERENCES

    # Versioning
    VERSION_OF = "version_of"                # This is a new version of that
    SUPERSEDED_BY = "superseded_by"          # This was replaced by that

    # Derivation
    DERIVED_FROM = "derived_from"            # This was created from that (e.g., summary from doc)
    SOURCE_OF = "source_of"                  # Inverse of DERIVED_FROM

    # Duplication (for dedup detection)
    DUPLICATE_OF = "duplicate_of"            # This content is identical/near-identical to that
    HAS_DUPLICATE = "has_duplicate"          # Inverse of DUPLICATE_OF

    # Conflict/Contradiction (for knowledge consistency)
    CONTRADICTS = "contradicts"              # This content conflicts with that content
    CONTRADICTED_BY = "contradicted_by"      # Inverse (symmetric, but explicit for audit)

    # Association
    RELATED_TO = "related_to"                # General relationship (catch-all)


@dataclass
class ContentRelationship:
    """
    Tracks relationships between content items.

    Enables:
    - "What images are in this PDF?"
    - "What files does this code import?"
    - "What's the previous version of this doc?"

    Validation:
        Set validate=True to enable validation on creation.
        Invalid data will raise ValidationError.
    """
    # === Identity ===
    relationship_id: str                     # REL-{sequential}
    relationship_type: ContentRelationType   # What kind of relationship

    # === The Relationship ===
    source_content_id: str                   # CONTENT-X (the "from" side)
    target_content_id: str                   # CONTENT-Y (the "to" side)

    # === Metadata ===
    created_at: str = ""                     # When relationship was discovered/created
    created_by: str = ""                     # Who/what created this relationship
    confidence: float = 1.0                  # How confident are we in this relationship
    relationship_note: str = ""              # Additional context about the relationship

    # === Extension ===
    extra: Dict[str, Any] = field(default_factory=dict)

    # === Validation Control ===
    # Default is True - opt OUT of safety, not opt IN
    validate: bool = field(default=True, repr=False)

    def __post_init__(self):
        """Validate relationship data. Enabled by default - set validate=False to skip."""
        if not self.validate:
            return

        errors = []

        # Validate confidence
        valid, msg = is_valid_confidence(self.confidence)
        if not valid:
            errors.append(f"confidence: {msg}")

        # Validate IDs are not empty
        if not self.source_content_id:
            errors.append("source_content_id cannot be empty")
        if not self.target_content_id:
            errors.append("target_content_id cannot be empty")

        if errors:
            raise ValidationError(f"ContentRelationship validation failed: {'; '.join(errors)}")


# =============================================================================
# RELATIONSHIP HELPERS - Bidirectional creation with full provenance
# =============================================================================

# Mapping from relationship type to its inverse
RELATIONSHIP_INVERSE_MAP = {
    ContentRelationType.CONTAINS: ContentRelationType.CONTAINED_BY,
    ContentRelationType.CONTAINED_BY: ContentRelationType.CONTAINS,
    ContentRelationType.IMPORTS: ContentRelationType.IMPORTED_BY,
    ContentRelationType.IMPORTED_BY: ContentRelationType.IMPORTS,
    ContentRelationType.DEPENDS_ON: ContentRelationType.DEPENDENCY_OF,
    ContentRelationType.DEPENDENCY_OF: ContentRelationType.DEPENDS_ON,
    ContentRelationType.REFERENCES: ContentRelationType.REFERENCED_BY,
    ContentRelationType.REFERENCED_BY: ContentRelationType.REFERENCES,
    ContentRelationType.VERSION_OF: ContentRelationType.SUPERSEDED_BY,
    ContentRelationType.SUPERSEDED_BY: ContentRelationType.VERSION_OF,
    ContentRelationType.DERIVED_FROM: ContentRelationType.SOURCE_OF,
    ContentRelationType.SOURCE_OF: ContentRelationType.DERIVED_FROM,
    ContentRelationType.DUPLICATE_OF: ContentRelationType.HAS_DUPLICATE,
    ContentRelationType.HAS_DUPLICATE: ContentRelationType.DUPLICATE_OF,
    ContentRelationType.CONTRADICTS: ContentRelationType.CONTRADICTED_BY,
    ContentRelationType.CONTRADICTED_BY: ContentRelationType.CONTRADICTS,
    ContentRelationType.RELATED_TO: ContentRelationType.RELATED_TO,  # Self-inverse (symmetric)
}


def get_inverse_relationship_type(rel_type: ContentRelationType) -> ContentRelationType:
    """Get the inverse of a relationship type."""
    return RELATIONSHIP_INVERSE_MAP.get(rel_type, ContentRelationType.RELATED_TO)


def create_bidirectional_relationship(
    source_content_id: str,
    target_content_id: str,
    relationship_type: ContentRelationType,
    created_by: str,
    created_at: str = "",
    confidence: float = 1.0,
    relationship_note: str = "",
    forward_id: str = "",
    inverse_id: str = "",
    extra: Dict[str, Any] = None
) -> tuple:
    """
    Create a pair of relationships: forward and inverse.

    Returns (forward_relationship, inverse_relationship) tuple.
    Both relationships share the same provenance (created_by, created_at, confidence)
    but have explicit separate records for full audit trail.

    Example:
        forward, inverse = create_bidirectional_relationship(
            source_content_id="CONTENT-pdf-001",
            target_content_id="CONTENT-img-001",
            relationship_type=ContentRelationType.CONTAINS,
            created_by="docling_processor",
            created_at=datetime.utcnow().isoformat(),
            confidence=1.0,
            relationship_note="Image extracted from page 3"
        )
        # forward: PDF --CONTAINS--> IMG
        # inverse: IMG --CONTAINED_BY--> PDF

    The inverse relationship's note is auto-prefixed to indicate it's the inverse,
    preserving the original context while making provenance clear.
    """
    from datetime import datetime

    if not created_at:
        created_at = datetime.utcnow().isoformat()

    if extra is None:
        extra = {}

    inverse_type = get_inverse_relationship_type(relationship_type)

    # Forward relationship: source -> target
    forward = ContentRelationship(
        relationship_id=forward_id or f"REL-{source_content_id}-{target_content_id}",
        relationship_type=relationship_type,
        source_content_id=source_content_id,
        target_content_id=target_content_id,
        created_at=created_at,
        created_by=created_by,
        confidence=confidence,
        relationship_note=relationship_note,
        extra={**extra, "has_inverse": True, "inverse_type": inverse_type.value}
    )

    # Inverse relationship: target -> source
    # Note is prefixed to indicate this is the inverse record
    inverse_note = f"[Inverse of {relationship_type.value}] {relationship_note}".strip()

    inverse = ContentRelationship(
        relationship_id=inverse_id or f"REL-{target_content_id}-{source_content_id}",
        relationship_type=inverse_type,
        source_content_id=target_content_id,
        target_content_id=source_content_id,
        created_at=created_at,
        created_by=created_by,
        confidence=confidence,
        relationship_note=inverse_note,
        extra={**extra, "is_inverse": True, "forward_type": relationship_type.value}
    )

    return (forward, inverse)


class CitationType(Enum):
    """
    What purpose a citation serves.
    From sitrep: Citations are "provenance pointers with metadata" serving multiple purposes.
    """
    CONTEXTUAL_BOOKMARK = "contextual_bookmark"  # Reference to conversation moment
    DOCUMENT_LINK = "document_link"              # Link to static artifact/file
    RELATIONSHIP_MARKER = "relationship_marker"  # Indicates connection between items
    CONFIDENCE_ANCHOR = "confidence_anchor"      # Certainty + source tracking
    GOLD_REFERENCE = "gold_reference"            # Realignment waypoint - trusted anchor (high confidence)
    ICK_REFERENCE = "ick_reference"              # Inverse of GOLD - "this was wrong, don't trust" (learning signal)
    CONTEXT_ALIAS = "context_alias"              # Human/agent-assigned display name for a context
                                                 # Multiple aliases can coexist (different agents, different names)
                                                 # Use relevance_note for the alias text, confidence for weight


@dataclass
class CitationReference:
    """
    Provenance pointer with metadata.

    Can serve as:
    - Contextual bookmark (conversation reference)
    - Document link (static artifact)
    - Relationship marker (connection indicator)
    - Confidence anchor (certainty + source tracking)

    Validation:
        Set validate=True to enable validation on creation.
        Invalid data will raise ValidationError.

    Semantic expectations:
        - GOLD_REFERENCE: High confidence anchor (typically >= 0.8)
        - ICK_REFERENCE: Low confidence marker (typically <= 0.3)
        These are warnings, not errors - the system will still allow creation.
    """
    # === Identity ===
    citation_id: str                         # CITE-{sequential} identifier
    citation_type: CitationType              # What purpose this citation serves

    # === What's Being Cited ===
    target_type: str = ""                    # "exchange", "content", "sidebar", "gold", etc.
    target_id: str = ""                      # ID of what's being cited
    target_sequence: Optional[int] = None    # Sequence number if applicable (OZOLITH entries)

    # === Context ===
    cited_from_context: str = ""             # Which context/sidebar created this citation
    cited_at: str = ""                       # ISO timestamp when cited
    cited_by: str = ""                       # Who/what created the citation

    # === Citation Metadata ===
    relevance_note: str = ""                 # Why this was cited / what it means
    confidence_at_citation: Optional[float] = None  # Confidence level when cited

    # === Relationships ===
    related_citations: List[str] = field(default_factory=list)  # Other CITE-X refs

    # === Extension ===
    extra: Dict[str, Any] = field(default_factory=dict)  # For discovered fields

    # === Validation Control ===
    # Default is True - opt OUT of safety, not opt IN
    validate: bool = field(default=True, repr=False)

    def __post_init__(self):
        """Validate citation data. Enabled by default - set validate=False to skip."""
        if not self.validate:
            return

        errors = []
        warnings = []

        # Validate confidence bounds
        if self.confidence_at_citation is not None:
            valid, msg = is_valid_confidence(self.confidence_at_citation)
            if not valid:
                errors.append(f"confidence_at_citation: {msg}")

        # Semantic validation for citation types
        if self.confidence_at_citation is not None:
            if self.citation_type == CitationType.GOLD_REFERENCE:
                if self.confidence_at_citation < 0.8:
                    warnings.append(
                        f"GOLD_REFERENCE typically has high confidence (>= 0.8), "
                        f"got {self.confidence_at_citation}"
                    )
            elif self.citation_type == CitationType.ICK_REFERENCE:
                if self.confidence_at_citation > 0.3:
                    warnings.append(
                        f"ICK_REFERENCE typically has low confidence (<= 0.3), "
                        f"got {self.confidence_at_citation}"
                    )

        # Store warnings in extra for inspection
        if warnings:
            if 'validation_warnings' not in self.extra:
                self.extra['validation_warnings'] = []
            self.extra['validation_warnings'].extend(warnings)

        if errors:
            raise ValidationError(f"CitationReference validation failed: {'; '.join(errors)}")


# =============================================================================
# ARCHIVED SIDEBAR - What gets stored in episodic memory
# =============================================================================

@dataclass
class ArchivedSidebar:
    """
    Full sidebar state preserved for later reference/forking.
    See UNIFIED_SIDEBAR_ARCHITECTURE.md Section 7.4.
    """
    # Full sidebar state at archive time
    sidebar_snapshot: Optional[SidebarContext] = None  # Complete SidebarContext at archive

    # Archive metadata
    archived_at: datetime = field(default_factory=datetime.now)  # When archived
    archived_by: str = ""                   # Agent or human who triggered archive
    archive_reason: str = ""                # "merged", "manual", "failed", "timeout"
    final_status: SidebarStatus = SidebarStatus.ARCHIVED  # Status at archive time

    # Preserved artifacts
    scratchpad_snapshot: Optional[Scratchpad] = None  # Scratchpad state at archive
    local_memory: List[Dict] = field(default_factory=list)  # All exchanges from this sidebar
    citations_created: List[str] = field(default_factory=list)  # CITE-X refs created here
    gold_citations: List[str] = field(default_factory=list)     # GOLD-X refs created here
    media_refs: List[str] = field(default_factory=list)         # MEDIA-X refs created here

    # Relationships (yarn-board tracing)
    parent_context_id: Optional[str] = None  # What spawned this sidebar
    child_sidebar_ids: List[str] = field(default_factory=list)  # Sidebars spawned from this
    forked_from: Optional[str] = None        # If revived from another archived sidebar
    forked_into: List[str] = field(default_factory=list)  # Sidebars forked FROM this archive

    # Searchability
    tags: List[str] = field(default_factory=list)  # Searchable tags for this archive
    summary: str = ""                       # Generated summary for search

    # Extension
    extra: Dict[str, Any] = field(default_factory=dict)  # For discovered fields
