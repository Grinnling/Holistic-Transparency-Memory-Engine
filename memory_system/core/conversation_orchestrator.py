#!/usr/bin/env python3
"""
conversation_orchestrator.py - Sidebar and Conversation Management

Coordinates the sidebar lifecycle:
- Spawn sidebars (branch from parent context)
- Merge sidebars (return findings to parent)
- Switch focus between contexts
- Track inherited vs local memory separation

This wraps existing rich_chat.py conversation methods without breaking them.

Created: 2025-12-04
Source: UNIFIED_SIDEBAR_ARCHITECTURE.md
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid_extensions import uuid7

from datashapes import (
    SidebarContext,
    SidebarStatus,
    SidebarPriority,
    Scratchpad,
    # OZOLITH payloads
    OzolithEventType,
    OzolithPayloadExchange,
    OzolithPayloadSidebarSpawn,
    OzolithPayloadSidebarMerge,
    OzolithPayloadSession,
    OzolithPayloadContextPause,
    OzolithPayloadContextResume,
    payload_to_dict,
)
from context_registry import get_registry, ContextType

# Lazy import persistence to avoid circular dependencies
_persistence_instance = None


def _get_persistence():
    """Lazy load persistence instance."""
    global _persistence_instance
    if _persistence_instance is None:
        try:
            from sidebar_persistence import get_persistence
            _persistence_instance = get_persistence()
        except ImportError:
            logging.warning("Sidebar persistence not available - state will not survive restarts")
            return None
    return _persistence_instance

# Lazy import Ozolith to avoid circular dependencies
_ozolith_instance = None


def _get_ozolith():
    """Lazy load Ozolith instance."""
    global _ozolith_instance
    if _ozolith_instance is None:
        try:
            from ozolith import Ozolith
            _ozolith_instance = Ozolith()
        except ImportError:
            logging.warning("Ozolith not available - events will not be logged")
            return None
    return _ozolith_instance


logger = logging.getLogger(__name__)

# =============================================================================
# REF TYPE INVERSE MAPPING
# =============================================================================
# When creating bidirectional refs, the reverse ref needs the inverse type.
# e.g., if A depends_on B, then B informs A (not B depends_on A)

INVERSE_REF_TYPES = {
    # Directional pairs
    "cites": "cited_by",
    "cited_by": "cites",
    "derived_from": "source_of",
    "source_of": "derived_from",
    "supersedes": "superseded_by",
    "superseded_by": "supersedes",
    "obsoletes": "obsoleted_by",
    "obsoleted_by": "obsoletes",
    "implements": "implemented_by",
    "implemented_by": "implements",
    "blocks": "blocked_by",
    "blocked_by": "blocks",
    "depends_on": "informs",
    "informs": "depends_on",
    # Symmetric (same in both directions)
    "related_to": "related_to",
    "contradicts": "contradicts",
}


class ConversationOrchestrator:
    """
    Manages conversation tree, sidebar lifecycle, and context flow.

    This is the layer that sits between rich_chat.py and the memory services.
    It adds sidebar/branching capabilities while keeping existing methods working.

    Key Concepts:
        - inherited_memory: READ ONLY snapshot from parent at branch point
        - local_memory: What happens IN this sidebar (the work)
        - On merge: Only local_memory gets consolidated into parent

    Usage:
        orchestrator = ConversationOrchestrator(error_handler)

        # Start main conversation (root)
        main_id = orchestrator.create_root_context()

        # Branch into sidebar
        sidebar_id = orchestrator.spawn_sidebar(
            parent_id=main_id,
            reason="Investigate auth issue",
            inherit_last_n=10
        )

        # Do work in sidebar...
        orchestrator.add_exchange(sidebar_id, user_msg, assistant_msg)

        # Merge back
        result = orchestrator.merge_sidebar(sidebar_id)
        # result contains summary injected into parent
    """

    def __init__(self, error_handler=None, auto_load: bool = True):
        """
        Initialize orchestrator.

        Args:
            error_handler: Optional ErrorHandler instance for error routing
            auto_load: Whether to automatically load persisted state on init
        """
        self.error_handler = error_handler
        self.registry = get_registry()

        # Active contexts: sidebar_id -> SidebarContext
        self._contexts: Dict[str, SidebarContext] = {}

        # Currently focused context (what the user is looking at)
        self._active_context_id: Optional[str] = None

        # Agent registry: agent_id -> AgentCapability
        # Tracks agent specialties for queue routing
        self._agents: Dict[str, 'AgentCapability'] = {}
        self._init_default_agents()

        # Grab huddles: context_id -> huddle_sidebar_id
        # One coordination huddle per context for grab collisions (prevents sidebar explosion)
        self._grab_huddles: Dict[str, str] = {}

        # Auto-load persisted state if available
        if auto_load:
            self._load_from_persistence()

    def _init_default_agents(self):
        """Initialize default agents with their specialties."""
        from datashapes import AgentCapability, AgentAvailability

        # Curator agent - central validation for all scratchpad entries
        self._agents["AGENT-curator"] = AgentCapability(
            agent_id="AGENT-curator",
            specialties=["validation", "quality_control", "routing"],
            availability=AgentAvailability.AVAILABLE
        )

        # Operator (human) - always present
        self._agents["AGENT-operator"] = AgentCapability(
            agent_id="AGENT-operator",
            specialties=["oversight", "decision_making", "approval"],
            availability=AgentAvailability.AVAILABLE
        )

        # Example specialty agents (extend as needed)
        self._agents["AGENT-researcher"] = AgentCapability(
            agent_id="AGENT-researcher",
            specialties=["research", "information_gathering", "analysis"],
            availability=AgentAvailability.AVAILABLE
        )

        self._agents["AGENT-debugger"] = AgentCapability(
            agent_id="AGENT-debugger",
            specialties=["debugging", "error_analysis", "troubleshooting"],
            availability=AgentAvailability.AVAILABLE
        )

        self._agents["AGENT-architect"] = AgentCapability(
            agent_id="AGENT-architect",
            specialties=["design", "architecture", "planning", "security"],
            availability=AgentAvailability.AVAILABLE
        )

    def _load_from_persistence(self) -> int:
        """
        Load persisted contexts from SQLite.

        Called on startup to restore state from previous session.
        SQLite should be CONSIDERED the source of truth for SB-type contexts.
        Registry is cleared and rebuilt from SQLite to ensure consistency.

        Returns:
            Number of contexts loaded
        """
        db = _get_persistence()
        if db is None:
            return 0

        try:
            # Load all contexts including archived (needed for tree visualization)
            contexts = db.load_all_contexts(include_archived=True)

            # Clear SB entries from registry before importing
            # This ensures SQLite is authoritative - registry becomes derived index
            self.registry.clear_type("SB")

            # Sort so parents come before children (needed for registry import)
            # Roots first (parent_context_id is None), then by depth
            def get_depth(ctx):
                depth = 0
                current = ctx.parent_context_id
                visited = set()
                while current and current not in visited:
                    visited.add(current)
                    depth += 1
                    # Find parent in our list
                    parent = next((c for c in contexts if c.sidebar_id == current), None)
                    current = parent.parent_context_id if parent else None
                return depth

            contexts_sorted = sorted(contexts, key=get_depth)

            # Import each context
            imported_count = 0
            for ctx in contexts_sorted:
                self._contexts[ctx.sidebar_id] = ctx

                # Import into registry with existing display_id
                was_imported = self.registry.import_context(
                    display_id=ctx.sidebar_id,
                    uuid=ctx.uuid,
                    context_type="SB",
                    parent_id=ctx.parent_context_id,
                    created_by=ctx.participants[0] if ctx.participants else "system",
                    description=ctx.task_description
                )
                if was_imported:
                    imported_count += 1

            # Save registry after batch import
            if imported_count > 0:
                self.registry.save()
                logger.debug(f"Imported {imported_count} contexts into registry")

            # Restore active context from session state
            stored_active = db.get_session_state('active_context_id')
            if stored_active and stored_active in self._contexts:
                self._active_context_id = stored_active
            elif contexts:
                # Default to most recently active non-archived context
                active_contexts = [c for c in contexts if c.status != SidebarStatus.ARCHIVED]
                if active_contexts:
                    most_recent = max(active_contexts, key=lambda c: c.last_activity)
                    self._active_context_id = most_recent.sidebar_id

            logger.info(f"Loaded {len(contexts)} contexts from persistence, active: {self._active_context_id}")
            return len(contexts)

        except Exception as e:
            logger.error(f"Failed to load from persistence: {e}")
            return 0

    def _persist_context(self, context: SidebarContext) -> bool:
        """
        Persist a context to SQLite (write-through).

        Args:
            context: The context to persist

        Returns:
            True if persisted successfully
        """
        db = _get_persistence()
        if db is None:
            return False

        try:
            return db.save_context(context)
        except Exception as e:
            logger.error(f"Failed to persist context {context.sidebar_id}: {e}")
            # Don't crash - data is still in memory and OZOLITH
            return False

    def _persist_focus(self) -> bool:
        """
        Persist current focus state to SQLite.

        Returns:
            True if persisted successfully
        """
        db = _get_persistence()
        if db is None:
            return False

        try:
            return db.set_session_state('active_context_id', self._active_context_id)
        except Exception as e:
            logger.error(f"Failed to persist focus state: {e}")
            return False

    def save_all_contexts(self) -> Optional[str]:
        """
        Persist all in-memory contexts to SQLite.

        This is a batch save operation - useful before tests or shutdown.
        Individual context changes are normally persisted immediately via
        _persist_context(), but this ensures everything is written.

        Returns:
            Path to persistence DB if successful, None if persistence unavailable
        """
        db = _get_persistence()
        if db is None:
            logger.warning("No persistence backend available for save_all_contexts")
            return None

        try:
            saved_count = 0
            for context in self._contexts.values():
                if db.save_context(context):
                    saved_count += 1

            # Also persist current focus state
            self._persist_focus()

            logger.info(f"Saved {saved_count} contexts to persistence")
            return db.db_path if hasattr(db, 'db_path') else "sqlite:memory"
        except Exception as e:
            logger.error(f"Failed to save all contexts: {e}")
            return None

    def load_all_contexts(self, path: Optional[str] = None) -> int:
        """
        Load contexts from persistence.

        This is a public wrapper around _load_from_persistence() for use
        in tests and recovery scenarios.

        Args:
            path: Optional path (ignored - uses configured persistence)
                  Kept for API compatibility with test expectations.

        Returns:
            Number of contexts loaded
        """
        return self._load_from_persistence()

    # =========================================================================
    # CONTEXT CREATION
    # =========================================================================

    def create_root_context(
        self,
        task_description: Optional[str] = None,
        created_by: str = "human"
    ) -> str:
        """
        Create a new root conversation (no parent).

        This is the "main" conversation that sidebars branch from.

        Args:
            task_description: What this conversation is about
            created_by: Who started it

        Returns:
            The new context's display ID (e.g., "SB-1")
        """
        uuid = str(uuid7())

        # Register in global registry
        display_id = self.registry.register(
            context_type="SB",
            uuid=uuid,
            parent_id=None,
            created_by=created_by,
            description=task_description
        )

        # Create context object
        context = SidebarContext(
            sidebar_id=display_id,
            uuid=uuid,
            parent_context_id=None,
            status=SidebarStatus.ACTIVE,
            priority=SidebarPriority.NORMAL,
            task_description=task_description,
            coordinator_agent="AGENT-operator",  # Human by default
            participants=[created_by],
            inherited_memory=[],  # Root has no inherited memory
            local_memory=[],
        )

        self._contexts[display_id] = context
        self._active_context_id = display_id

        # Persist to SQLite
        self._persist_context(context)
        self._persist_focus()

        # Register conversation root mapping
        db = _get_persistence()
        if db:
            db.register_conversation_root(uuid, display_id)

        # Log SESSION_START to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadSession(
                session_id=uuid,
                interface="orchestrator",
                extra={"task_description": task_description or ""}
            )
            oz.append(
                event_type=OzolithEventType.SESSION_START,
                context_id=display_id,
                actor=created_by,
                payload=payload_to_dict(payload)
            )

        logger.info(f"Created root context {display_id}")
        return display_id

    def spawn_sidebar(
        self,
        parent_id: str,
        reason: str,
        inherit_last_n: Optional[int] = None,
        created_by: str = "human",
        priority: SidebarPriority = SidebarPriority.NORMAL,
        success_criteria: Optional[str] = None
    ) -> str:
        """
        Spawn a sidebar from a parent context.

        This is the "hold that thought" operation. Creates a new context
        that inherits memory from parent but has its own local workspace.

        Args:
            parent_id: Display ID of parent context (e.g., "SB-1")
            reason: Why we're branching (becomes task_description)
            inherit_last_n: How many parent exchanges to inherit.
                           None = all, 0 = none
            created_by: Who spawned this sidebar
            priority: Priority level for load management
            success_criteria: What "done" looks like

        Returns:
            The new sidebar's display ID (e.g., "SB-2")

        Raises:
            ValueError: If parent_id doesn't exist
        """
        # Validate parent exists
        parent = self._contexts.get(parent_id)
        if parent is None:
            raise ValueError(f"Parent context '{parent_id}' not found")

        # Pause parent (it's now waiting for sidebar to complete)
        parent.status = SidebarStatus.PAUSED
        parent.last_activity = datetime.now()

        uuid = str(uuid7())

        # Register in global registry
        display_id = self.registry.register(
            context_type="SB",
            uuid=uuid,
            parent_id=parent_id,
            created_by=created_by,
            created_in=parent_id,
            description=reason
        )

        # Build inherited memory (snapshot from parent)
        if inherit_last_n is None:
            # Inherit all
            inherited = list(parent.local_memory)
        elif inherit_last_n == 0:
            inherited = []
        else:
            inherited = list(parent.local_memory[-inherit_last_n:])

        # Mark inherited exchanges as read-only snapshots
        for exchange in inherited:
            exchange["_inherited"] = True
            exchange["_inherited_from"] = parent_id

        # Create sidebar context
        context = SidebarContext(
            sidebar_id=display_id,
            uuid=uuid,
            parent_context_id=parent_id,
            status=SidebarStatus.ACTIVE,
            priority=priority,
            task_description=reason,
            success_criteria=success_criteria,
            coordinator_agent="AGENT-operator",
            participants=[created_by],
            inherited_memory=inherited,
            local_memory=[],
        )

        self._contexts[display_id] = context

        # Update parent's children list
        parent.child_sidebar_ids.append(display_id)

        # Switch focus to new sidebar
        self._active_context_id = display_id

        # Persist both contexts to SQLite
        self._persist_context(context)  # New sidebar
        self._persist_context(parent)    # Parent updated (PAUSED, new child)
        self._persist_focus()

        # Log SIDEBAR_SPAWN to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadSidebarSpawn(
                spawn_reason=reason,
                parent_context=parent_id,
                child_id=display_id,
                inherited_count=len(inherited),
                task_description=reason,
                success_criteria=success_criteria or ""
            )
            oz.append(
                event_type=OzolithEventType.SIDEBAR_SPAWN,
                context_id=display_id,
                actor=created_by,
                payload=payload_to_dict(payload)
            )

        logger.info(f"Spawned sidebar {display_id} from {parent_id}: {reason}")
        return display_id

    # =========================================================================
    # CONTEXT OPERATIONS
    # =========================================================================

    def add_exchange(
        self,
        context_id: str,
        user_message: str,
        assistant_response: str,
        exchange_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add an exchange to a context's local memory.

        Args:
            context_id: Which context to add to
            user_message: What the user said
            assistant_response: What the assistant replied
            exchange_id: Optional ID (generated if not provided)
            metadata: Optional additional data

        Returns:
            The exchange ID
        """
        context = self._contexts.get(context_id)
        if context is None:
            raise ValueError(f"Context '{context_id}' not found")

        if exchange_id is None:
            exchange_id = self.registry.register(
                context_type="EXCH",
                created_by="system",
                created_in=context_id
            )

        exchange = {
            "exchange_id": exchange_id,
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": datetime.now().isoformat(),
            "context_id": context_id,
            **(metadata or {})
        }

        context.local_memory.append(exchange)
        context.last_activity = datetime.now()

        # [DEBUG-SYNC] Log what was stored to local_memory
        print(f"[DEBUG-SYNC] orchestrator.add_exchange():")
        print(f"[DEBUG-SYNC]   context_id: {context_id}")
        print(f"[DEBUG-SYNC]   Stored exchange keys: {list(exchange.keys())}")
        print(f"[DEBUG-SYNC]   Has 'user' key: {'user' in exchange}")
        print(f"[DEBUG-SYNC]   Has 'role' key: {'role' in exchange}")
        print(f"[DEBUG-SYNC]   Has retrieved_memories: {'retrieved_memories' in exchange}")
        print(f"[DEBUG-SYNC]   local_memory length now: {len(context.local_memory)}")

        # Persist updated context
        self._persist_context(context)

        # Log EXCHANGE to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadExchange(
                content=f"[exchange:{exchange_id}]",  # Reference, not raw content
                confidence=metadata.get("confidence", 0.0) if metadata else 0.0,
                uncertainty_flags=metadata.get("uncertainty_flags", []) if metadata else [],
                context_depth=len(context.inherited_memory),
                extra={
                    "exchange_id": exchange_id,
                    "has_user_message": bool(user_message),
                    "has_assistant_response": bool(assistant_response),
                }
            )
            oz.append(
                event_type=OzolithEventType.EXCHANGE,
                context_id=context_id,
                actor="assistant",
                payload=payload_to_dict(payload)
            )

        return exchange_id

    def get_context_for_llm(self, context_id: str) -> List[Dict]:
        """
        Get the full context to send to LLM.

        Combines inherited_memory + local_memory in correct order.

        Args:
            context_id: Which context

        Returns:
            List of exchanges ready for LLM consumption
        """
        context = self._contexts.get(context_id)
        if context is None:
            return []

        # Inherited first (the snapshot), then local (the work)
        return context.inherited_memory + context.local_memory

    def get_active_context(self) -> Optional[SidebarContext]:
        """Get the currently focused context."""
        if self._active_context_id:
            return self._contexts.get(self._active_context_id)
        return None

    def get_active_context_id(self) -> Optional[str]:
        """Get the currently focused context's ID."""
        return self._active_context_id

    def get_context(self, context_id: str) -> Optional[SidebarContext]:
        """Get a specific context by ID."""
        return self._contexts.get(context_id)

    # =========================================================================
    # FOCUS MANAGEMENT
    # =========================================================================

    def switch_focus(self, context_id: str) -> bool:
        """
        Switch which context is "active" (what user sees).

        Unlike switch_conversation in rich_chat.py, this doesn't
        abandon the previous context - just changes focus.

        Args:
            context_id: Context to focus on

        Returns:
            True if switched, False if context not found
        """
        if context_id not in self._contexts:
            logger.warning(f"Cannot switch to unknown context {context_id}")
            return False

        old_focus = self._active_context_id
        self._active_context_id = context_id

        # Persist focus change
        self._persist_focus()

        logger.debug(f"Switched focus from {old_focus} to {context_id}")
        return True

    def pause_context(self, context_id: str, reason: str = "") -> bool:
        """
        Pause a context (not branching, just stepping away).

        Args:
            context_id: Context to pause
            reason: Why pausing

        Returns:
            True if paused, False if not found
        """
        context = self._contexts.get(context_id)
        if context is None:
            return False

        context.status = SidebarStatus.PAUSED
        context.last_activity = datetime.now()

        # Persist status change
        self._persist_context(context)

        # Log CONTEXT_PAUSE to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadContextPause(
                reason=reason or "manual",
                state_summary=f"{len(context.local_memory)} local exchanges"
            )
            oz.append(
                event_type=OzolithEventType.CONTEXT_PAUSE,
                context_id=context_id,
                actor="system",
                payload=payload_to_dict(payload)
            )

        logger.info(f"Paused context {context_id}: {reason}")
        return True

    def resume_context(self, context_id: str) -> bool:
        """
        Resume a paused or archived context.

        Args:
            context_id: Context to resume/restore

        Returns:
            True if resumed, False if not found or not resumable
        """
        context = self._contexts.get(context_id)
        if context is None:
            return False

        resumable = [SidebarStatus.PAUSED, SidebarStatus.ARCHIVED, SidebarStatus.WAITING]
        if context.status not in resumable:
            logger.warning(f"Context {context_id} is not resumable (status: {context.status})")
            return False

        context.status = SidebarStatus.ACTIVE
        context.last_activity = datetime.now()
        self._active_context_id = context_id

        # Persist status and focus changes
        self._persist_context(context)
        self._persist_focus()

        # Log CONTEXT_RESUME to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadContextResume(
                reason="manual",
                state_on_resume=f"{len(context.local_memory)} local exchanges"
            )
            oz.append(
                event_type=OzolithEventType.CONTEXT_RESUME,
                context_id=context_id,
                actor="system",
                payload=payload_to_dict(payload)
            )

        logger.info(f"Resumed context {context_id}")
        return True

    # =========================================================================
    # MERGE OPERATIONS
    # =========================================================================

    def merge_sidebar(
        self,
        sidebar_id: str,
        summary: Optional[str] = None,
        auto_summarize: bool = False
    ) -> Dict:
        """
        Merge a sidebar back into its parent.

        This is the "back to main with findings" operation.

        Args:
            sidebar_id: The sidebar to merge
            summary: Manual summary of findings. If None and auto_summarize
                    is False, uses a default summary.
            auto_summarize: Use LLM to generate summary (TODO: implement)

        Returns:
            Dict with merge results:
            {
                "success": bool,
                "parent_id": str,
                "summary": str,
                "exchanges_merged": int,
                "error": Optional[str]
            }
        """
        sidebar = self._contexts.get(sidebar_id)
        if sidebar is None:
            return {
                "success": False,
                "error": f"Sidebar '{sidebar_id}' not found"
            }

        parent_id = sidebar.parent_context_id
        if parent_id is None:
            return {
                "success": False,
                "error": f"Sidebar '{sidebar_id}' has no parent (is it a root?)"
            }

        parent = self._contexts.get(parent_id)
        if parent is None:
            return {
                "success": False,
                "error": f"Parent '{parent_id}' not found"
            }

        # Generate summary if not provided
        if summary is None:
            if auto_summarize:
                # TODO: Call LLM to summarize sidebar.local_memory
                summary = f"[Auto-summary of {len(sidebar.local_memory)} exchanges - TODO]"
            else:
                # Default summary
                exchange_count = len(sidebar.local_memory)
                summary = f"Sidebar {sidebar_id} completed: {sidebar.task_description or 'investigation'} ({exchange_count} exchanges)"

        # Update sidebar status
        sidebar.status = SidebarStatus.MERGED
        sidebar.last_activity = datetime.now()

        # Inject summary into parent's local memory
        merge_exchange = {
            "exchange_id": self.registry.register(
                context_type="EXCH",
                created_by="system",
                created_in=parent_id,
                description=f"Merge from {sidebar_id}"
            ),
            "user": f"[SYSTEM] Sidebar {sidebar_id} merged",
            "assistant": summary,
            "timestamp": datetime.now().isoformat(),
            "context_id": parent_id,
            "_merge_from": sidebar_id,
            "_merge_type": "sidebar_completion",
            "_exchanges_merged": len(sidebar.local_memory),
        }
        parent.local_memory.append(merge_exchange)

        # Resume parent
        parent.status = SidebarStatus.ACTIVE
        parent.last_activity = datetime.now()

        # Switch focus back to parent
        self._active_context_id = parent_id

        # Persist both contexts and focus
        self._persist_context(sidebar)
        self._persist_context(parent)
        self._persist_focus()

        # Log SIDEBAR_MERGE to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadSidebarMerge(
                merge_summary=summary,
                parent_context=parent_id,
                exchange_count=len(sidebar.local_memory),
                summary_hash=hashlib.sha256(summary.encode()).hexdigest()
            )
            oz.append(
                event_type=OzolithEventType.SIDEBAR_MERGE,
                context_id=sidebar_id,
                actor="system",
                payload=payload_to_dict(payload)
            )

        logger.info(f"Merged {sidebar_id} into {parent_id}")

        return {
            "success": True,
            "parent_id": parent_id,
            "sidebar_id": sidebar_id,
            "summary": summary,
            "exchanges_merged": len(sidebar.local_memory),
        }

    # =========================================================================
    # REPARENT OPERATIONS
    # =========================================================================

    def reparent_context(
        self,
        context_id: str,
        new_parent_id: Optional[str],
        reason: str,
        confidence: float = 0.0,
        suggested_by_model: bool = False,
        pattern_detected: str = ""
    ) -> Dict:
        """
        Change a context's parent, preserving full audit trail.

        Use cases:
        - Unify multiple roots under umbrella context
        - Move sidebar to different parent
        - Promote sidebar to root (new_parent_id=None)

        Children move WITH the reparented context automatically.

        Args:
            context_id: Context to reparent
            new_parent_id: New parent (None = become root)
            reason: Why reparenting ("unification", "reorganization", etc.)
            confidence: Model's confidence this is correct (0.0-1.0)
            suggested_by_model: Did a model suggest this, or human initiate?
            pattern_detected: What pattern triggered the suggestion

        Returns:
            Dict with reparent results
        """
        from datashapes import OzolithPayloadContextReparent

        context = self._contexts.get(context_id)
        if context is None:
            return {
                "success": False,
                "error": f"Context '{context_id}' not found"
            }

        old_parent_id = context.parent_context_id

        # Validate new parent exists (unless becoming root)
        if new_parent_id is not None and new_parent_id not in self._contexts:
            return {
                "success": False,
                "error": f"New parent '{new_parent_id}' not found"
            }

        # Prevent cycles - new parent can't be a descendant of this context
        if new_parent_id is not None:
            check = new_parent_id
            while check is not None:
                if check == context_id:
                    return {
                        "success": False,
                        "error": f"Cannot reparent: would create cycle ('{new_parent_id}' is descendant of '{context_id}')"
                    }
                parent_ctx = self._contexts.get(check)
                check = parent_ctx.parent_context_id if parent_ctx else None

        # Store original conversation_id for history
        original_conversation_id = context.uuid if old_parent_id is None else None

        # Remove from old parent's children list
        if old_parent_id is not None and old_parent_id in self._contexts:
            old_parent = self._contexts[old_parent_id]
            if context_id in old_parent.child_sidebar_ids:
                old_parent.child_sidebar_ids.remove(context_id)
            self._persist_context(old_parent)

        # Update context's parent
        context.parent_context_id = new_parent_id
        context.last_activity = datetime.now()

        # Add to new parent's children list
        if new_parent_id is not None:
            new_parent = self._contexts[new_parent_id]
            if context_id not in new_parent.child_sidebar_ids:
                new_parent.child_sidebar_ids.append(context_id)
            self._persist_context(new_parent)

        # Persist the reparented context
        self._persist_context(context)

        # Collect children that moved with this context
        children_moved = list(context.child_sidebar_ids)

        # Log CONTEXT_REPARENT to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadContextReparent(
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
                reason=reason,
                confidence=confidence,
                suggested_by_model=suggested_by_model,
                pattern_detected=pattern_detected,
                children_moved=children_moved,
                original_conversation_id=original_conversation_id,
                requested_by="human" if not suggested_by_model else "model"
            )
            oz.append(
                event_type=OzolithEventType.CONTEXT_REPARENT,
                context_id=context_id,
                actor="system",
                payload=payload_to_dict(payload)
            )

        logger.info(f"Reparented {context_id}: {old_parent_id} -> {new_parent_id} ({reason})")

        return {
            "success": True,
            "context_id": context_id,
            "old_parent_id": old_parent_id,
            "new_parent_id": new_parent_id,
            "children_moved": children_moved,
            "reason": reason,
        }

    # =========================================================================
    # CROSS-REFERENCE OPERATIONS
    # =========================================================================

    CLUSTERING_THRESHOLD = 3  # Auto-flag when this many sources suggest same ref

    def add_cross_ref(
        self,
        source_context_id: str,
        target_context_id: str,
        ref_type: str = "related_to",
        reason: str = "",
        confidence: float = 0.0,
        discovery_method: str = "explicit",
        strength: str = "normal",
        bidirectional: bool = True,
        exchange_id: Optional[str] = None,
        validation_priority: str = "normal",
        suggested_by: Optional[str] = None
    ) -> Dict:
        """
        Add a cross-reference between contexts (possibly in different trees).

        This creates the "stumble upon related work" capability.
        By default, creates bidirectional refs so we can query from either side.

        Clustering: When 3+ unique sources suggest the same ref, auto-flags
        for urgent validation (increases confidence it's a real pattern).

        Args:
            source_context_id: Context containing the reference
            target_context_id: Context being referenced
            ref_type: Type of reference ("cites", "related_to", "derived_from", "contradicts")
            reason: Why the reference was created
            confidence: How confident Claude is this connection is real (0.0-1.0)
            discovery_method: How was this found? ("explicit_mention", "semantic_similarity", etc.)
            strength: "weak", "normal", "strong", "definitive"
            bidirectional: Auto-create reverse reference
            exchange_id: Specific exchange containing the reference
            validation_priority: "urgent" if actively citing, "normal" otherwise
            suggested_by: Agent/context ID that suggested this ref (for clustering)

        Returns:
            Dict with cross-ref results including cluster_flagged status
        """
        from datashapes import OzolithPayloadCrossRefAdded

        source = self._contexts.get(source_context_id)
        target = self._contexts.get(target_context_id)

        if source is None:
            return {"success": False, "error": f"Source context '{source_context_id}' not found"}
        if target is None:
            return {"success": False, "error": f"Target context '{target_context_id}' not found"}

        # Validate enum fields before storing (fail fast, fail loud)
        valid_strengths = ['speculative', 'weak', 'normal', 'strong', 'definitive']
        valid_ref_types = list(INVERSE_REF_TYPES.keys())  # All types from inverse mapping
        valid_discovery_methods = ['explicit', 'user_indicated', 'semantic_similarity', 'topic_overlap', 'citation_extracted', 'temporal_proximity', 'pattern_match']

        if strength not in valid_strengths:
            return {"success": False, "error": f"Invalid strength '{strength}'. Valid: {valid_strengths}"}
        if ref_type not in valid_ref_types:
            return {"success": False, "error": f"Invalid ref_type '{ref_type}'. Valid: {valid_ref_types}"}
        if discovery_method not in valid_discovery_methods:
            return {"success": False, "error": f"Invalid discovery_method '{discovery_method}'. Valid: {valid_discovery_methods}"}
        if not (0.0 <= confidence <= 1.0):
            return {"success": False, "error": f"Confidence must be 0.0-1.0, got {confidence}"}
        valid_priorities = ['urgent', 'normal']
        if validation_priority not in valid_priorities:
            return {"success": False, "error": f"Invalid validation_priority '{validation_priority}'. Valid: {valid_priorities}"}

        # Determine suggester (default to source context if not specified)
        suggester = suggested_by or source_context_id
        now = datetime.now()

        # Check if ref already exists - if so, add to sources for clustering
        cluster_flagged = False
        existing = source.cross_sidebar_refs.get(target_context_id)

        if existing:
            # Ref already exists - add suggester to sources if not already there
            sources = existing.get("suggested_sources", [])
            # Check if suggester already in sources (sources is now List[Dict])
            existing_source_ids = [s.get("source_id") if isinstance(s, dict) else s for s in sources]
            if suggester not in existing_source_ids:
                sources.append({
                    "source_id": suggester,
                    "suggested_at": now.isoformat()
                })
                existing["suggested_sources"] = sources

                # Check clustering threshold
                if len(sources) >= self.CLUSTERING_THRESHOLD and not existing.get("cluster_flagged"):
                    existing["cluster_flagged"] = True
                    existing["validation_priority"] = "urgent"
                    cluster_flagged = True
                    logger.info(f"Cross-ref {source_context_id}→{target_context_id} cluster-flagged ({len(sources)} sources)")

                self._persist_context(source)

            return {
                "success": True,
                "source_context_id": source_context_id,
                "target_context_id": target_context_id,
                "ref_type": existing.get("ref_type"),
                "already_existed": True,
                "suggested_sources": sources,
                "source_count": len(sources),
                "cluster_flagged": existing.get("cluster_flagged", False),
                "newly_flagged": cluster_flagged
            }

        # Build metadata dict (matches CrossRefMetadata structure)
        metadata = {
            "ref_type": ref_type,
            "strength": strength,
            "confidence": confidence,
            "discovery_method": discovery_method,
            "human_validated": None,  # Not yet reviewed
            "created_at": now.isoformat(),
            "reason": reason,
            "validation_priority": validation_priority,
            "suggested_sources": [{"source_id": suggester, "suggested_at": now.isoformat()}],
            "cluster_flagged": False,
        }

        # Add to source's cross_sidebar_refs
        source.cross_sidebar_refs[target_context_id] = metadata
        self._persist_context(source)

        # Add reverse reference if bidirectional
        if bidirectional and source_context_id not in target.cross_sidebar_refs:
            # Reverse ref gets INVERSE type (if A depends_on B, then B informs A)
            reverse_metadata = metadata.copy()
            reverse_metadata["ref_type"] = INVERSE_REF_TYPES[ref_type]
            reverse_metadata["suggested_sources"] = [{"source_id": suggester, "suggested_at": now.isoformat()}]
            target.cross_sidebar_refs[source_context_id] = reverse_metadata
            self._persist_context(target)

        # Log CROSS_REF_ADDED to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadCrossRefAdded(
                source_context_id=source_context_id,
                target_context_id=target_context_id,
                ref_type=ref_type,
                confidence=confidence,
                discovery_method=discovery_method,
                strength=strength,
                human_validated=None,  # Not yet reviewed
                reason=reason,
                bidirectional=bidirectional,
                exchange_id=exchange_id
            )
            oz.append(
                event_type=OzolithEventType.CROSS_REF_ADDED,
                context_id=source_context_id,
                actor="claude" if discovery_method != "user_indicated" else "human",
                payload=payload_to_dict(payload)
            )

        logger.info(f"Added cross-ref: {source_context_id} --[{ref_type}]--> {target_context_id} (suggested by {suggester})")

        return {
            "success": True,
            "source_context_id": source_context_id,
            "target_context_id": target_context_id,
            "ref_type": ref_type,
            "bidirectional": bidirectional,
            "already_existed": False,
            "suggested_sources": [{"source_id": suggester, "suggested_at": now.isoformat()}],
            "source_count": 1,
            "cluster_flagged": False,
            "newly_flagged": False
        }

    def get_cross_refs(
        self,
        context_id: str,
        ref_type: Optional[str] = None,
        min_strength: Optional[str] = None
    ) -> List[str]:
        """
        Get all contexts that this context references or is referenced by.

        Args:
            context_id: Context to query
            ref_type: Filter by ref_type (e.g., "implements", "cites")
            min_strength: Filter by minimum strength level

        Returns:
            List of context IDs matching the filters
        """
        context = self._contexts.get(context_id)
        if context is None:
            return []

        # Strength ordering for comparison
        strength_order = ["speculative", "weak", "normal", "strong", "definitive"]

        results = []
        for target_id, metadata in context.cross_sidebar_refs.items():
            # Apply ref_type filter
            if ref_type and metadata.get("ref_type") != ref_type:
                continue

            # Apply min_strength filter
            if min_strength:
                current_strength = metadata.get("strength", "normal")
                if strength_order.index(current_strength) < strength_order.index(min_strength):
                    continue

            results.append(target_id)

        return results

    def get_cluster_flagged_refs(
        self,
        context_id: Optional[str] = None,
        include_validated: bool = False
    ) -> Dict:
        """
        Get all cross-refs that have been cluster-flagged (3+ sources suggested).

        These are high-confidence candidates for validation since multiple
        independent sources suggested the same connection.

        Args:
            context_id: Limit to specific context, or None for all contexts
            include_validated: Include refs that have already been validated

        Returns:
            Dict with flagged refs grouped by source context
        """
        flagged_refs = []

        contexts_to_check = (
            [self._contexts.get(context_id)] if context_id
            else self._contexts.values()
        )

        for context in contexts_to_check:
            if context is None:
                continue

            for target_id, metadata in context.cross_sidebar_refs.items():
                if not metadata.get("cluster_flagged"):
                    continue

                # Skip already validated unless requested
                if not include_validated and metadata.get("human_validated") is not None:
                    continue

                flagged_refs.append({
                    "source_context_id": context.sidebar_id,
                    "target_context_id": target_id,
                    "ref_type": metadata.get("ref_type"),
                    "suggested_sources": metadata.get("suggested_sources", []),
                    "source_count": len(metadata.get("suggested_sources", [])),
                    "confidence": metadata.get("confidence", 0.0),
                    "reason": metadata.get("reason", ""),
                    "human_validated": metadata.get("human_validated"),
                })

        # Sort by source count (most suggestions first)
        flagged_refs.sort(key=lambda x: x["source_count"], reverse=True)

        return {
            "success": True,
            "cluster_flagged_refs": flagged_refs,
            "count": len(flagged_refs),
            "threshold": self.CLUSTERING_THRESHOLD
        }

    def revoke_cross_ref(
        self,
        source_context_id: str,
        target_context_id: str,
        reason: str,
        revoked_by: str = "human",
        replacement_refs: Optional[List[str]] = None,
        corrected_understanding: str = ""
    ) -> Dict:
        """
        Revoke a cross-reference between contexts (append-only pattern).

        This doesn't delete the original CROSS_REF_ADDED event - it adds a new
        CROSS_REF_REVOKED event that marks the relationship as no longer valid.
        This preserves history for learning from mistakes.

        Args:
            source_context_id: Original source context
            target_context_id: Original target context
            reason: Why revoking this cross-ref
            revoked_by: "human" or "model"
            replacement_refs: List of correct context IDs if the revoked one was wrong
            corrected_understanding: Explanation of why the original was wrong

        Returns:
            Dict with revocation results
        """
        from datashapes import OzolithPayloadCrossRefRevoked

        source = self._contexts.get(source_context_id)
        target = self._contexts.get(target_context_id)

        if source is None:
            return {"success": False, "error": f"Source context '{source_context_id}' not found"}
        if target is None:
            return {"success": False, "error": f"Target context '{target_context_id}' not found"}

        # Check if the cross-ref actually exists
        if target_context_id not in source.cross_sidebar_refs:
            return {"success": False, "error": f"No cross-ref exists from '{source_context_id}' to '{target_context_id}'"}

        # Remove from source's cross_sidebar_refs
        del source.cross_sidebar_refs[target_context_id]
        self._persist_context(source)

        # Also remove reverse ref if it exists (bidirectional cleanup)
        if source_context_id in target.cross_sidebar_refs:
            del target.cross_sidebar_refs[source_context_id]
            self._persist_context(target)

        # Log CROSS_REF_REVOKED to OZOLITH (append-only - preserves history)
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadCrossRefRevoked(
                source_context_id=source_context_id,
                target_context_id=target_context_id,
                reason=reason,
                revoked_by=revoked_by,
                replacement_refs=replacement_refs or [],
                corrected_understanding=corrected_understanding
            )
            oz.append(
                event_type=OzolithEventType.CROSS_REF_REVOKED,
                context_id=source_context_id,
                actor=revoked_by,
                payload=payload_to_dict(payload)
            )

        logger.info(f"Revoked cross-ref: {source_context_id} --X--> {target_context_id} ({reason})")

        return {
            "success": True,
            "source_context_id": source_context_id,
            "target_context_id": target_context_id,
            "reason": reason,
            "replacement_refs": replacement_refs or [],
        }

    def update_cross_ref(
        self,
        source_context_id: str,
        target_context_id: str,
        reason: str,
        new_strength: Optional[str] = None,
        new_confidence: Optional[float] = None,
        new_ref_type: Optional[str] = None,
        new_validation_priority: Optional[str] = None,
        updated_by: str = "human"
    ) -> Dict:
        """
        Update metadata on an existing cross-reference.

        This is cleaner than revoke + re-add when you just need to change
        strength, confidence, ref_type, or validation_priority. Preserves
        full audit trail via CROSS_REF_UPDATED event.

        Args:
            source_context_id: Context containing the reference
            target_context_id: Context being referenced
            reason: Why updating (e.g., "additional evidence found")
            new_strength: New strength level (if changing)
            new_confidence: New confidence value (if changing)
            new_ref_type: New ref_type (if changing)
            new_validation_priority: New priority level (if changing) - "normal" or "urgent"
            updated_by: "human" or "model"

        Returns:
            Dict with update results
        """
        from datashapes import OzolithPayloadCrossRefUpdated

        source = self._contexts.get(source_context_id)
        if source is None:
            return {"success": False, "error": f"Source context '{source_context_id}' not found"}

        if target_context_id not in source.cross_sidebar_refs:
            return {"success": False, "error": f"No cross-ref exists from '{source_context_id}' to '{target_context_id}'"}

        # Validate new values if provided (fail fast, fail loud)
        valid_strengths = ['speculative', 'weak', 'normal', 'strong', 'definitive']
        valid_ref_types = list(INVERSE_REF_TYPES.keys())
        valid_priorities = ['normal', 'urgent']

        if new_strength is not None and new_strength not in valid_strengths:
            return {"success": False, "error": f"Invalid strength '{new_strength}'. Valid: {valid_strengths}"}
        if new_ref_type is not None and new_ref_type not in valid_ref_types:
            return {"success": False, "error": f"Invalid ref_type '{new_ref_type}'. Valid: {valid_ref_types}"}
        if new_confidence is not None and not (0.0 <= new_confidence <= 1.0):
            return {"success": False, "error": f"Confidence must be 0.0-1.0, got {new_confidence}"}
        if new_validation_priority is not None and new_validation_priority not in valid_priorities:
            return {"success": False, "error": f"Invalid validation_priority '{new_validation_priority}'. Valid: {valid_priorities}"}

        # Get current metadata
        current = source.cross_sidebar_refs[target_context_id]
        old_strength = current.get("strength")
        old_confidence = current.get("confidence")
        old_ref_type = current.get("ref_type")
        old_validation_priority = current.get("validation_priority")

        # Apply updates
        if new_strength is not None:
            current["strength"] = new_strength
        if new_confidence is not None:
            current["confidence"] = new_confidence
        if new_ref_type is not None:
            current["ref_type"] = new_ref_type
        if new_validation_priority is not None:
            current["validation_priority"] = new_validation_priority

        self._persist_context(source)

        # Log CROSS_REF_UPDATED to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadCrossRefUpdated(
                source_context_id=source_context_id,
                target_context_id=target_context_id,
                reason=reason,
                old_strength=old_strength if new_strength else None,
                new_strength=new_strength,
                old_confidence=old_confidence if new_confidence is not None else None,
                new_confidence=new_confidence,
                old_ref_type=old_ref_type if new_ref_type else None,
                new_ref_type=new_ref_type,
                old_validation_priority=old_validation_priority if new_validation_priority else None,
                new_validation_priority=new_validation_priority,
                updated_by=updated_by
            )
            oz.append(
                event_type=OzolithEventType.CROSS_REF_UPDATED,
                context_id=source_context_id,
                actor=updated_by,
                payload=payload_to_dict(payload)
            )

        logger.info(f"Updated cross-ref: {source_context_id} --> {target_context_id} ({reason})")

        return {
            "success": True,
            "source_context_id": source_context_id,
            "target_context_id": target_context_id,
            "reason": reason,
            "changes": {
                "strength": {"old": old_strength, "new": new_strength} if new_strength else None,
                "confidence": {"old": old_confidence, "new": new_confidence} if new_confidence is not None else None,
                "ref_type": {"old": old_ref_type, "new": new_ref_type} if new_ref_type else None,
                "validation_priority": {"old": old_validation_priority, "new": new_validation_priority} if new_validation_priority else None,
            }
        }

    def validate_cross_ref(
        self,
        source_context_id: str,
        target_context_id: str,
        validation_state: str,
        validated_by: str = "human",
        validation_notes: Optional[str] = None,
        chase_after: Optional[str] = None,
        validation_context_id: Optional[str] = None
    ) -> Dict:
        """
        Record human validation of a cross-reference.

        This captures whether a human confirms, rejects, or is unsure about
        a model-detected connection. Critical for calibration - we snapshot
        the model's confidence at validation time to learn from feedback.

        Args:
            source_context_id: Context containing the reference
            target_context_id: Context being referenced
            validation_state: "true", "false", or "not_sure"
            validated_by: Who validated (default "human")
            validation_notes: Optional free text feedback
            chase_after: ISO datetime string for per-ref follow-up override
            validation_context_id: What sidebar was active during validation

        Returns:
            Dict with validation results
        """
        from datashapes import OzolithPayloadCrossRefValidated

        # Validate state
        valid_states = ['true', 'false', 'not_sure']
        if validation_state not in valid_states:
            return {"success": False, "error": f"Invalid validation_state '{validation_state}'. Valid: {valid_states}"}

        source = self._contexts.get(source_context_id)
        if source is None:
            return {"success": False, "error": f"Source context '{source_context_id}' not found"}

        if target_context_id not in source.cross_sidebar_refs:
            return {"success": False, "error": f"No cross-ref exists from '{source_context_id}' to '{target_context_id}'"}

        # Get current metadata
        current = source.cross_sidebar_refs[target_context_id]
        previous_state = current.get("human_validated")
        confidence_at_validation = current.get("confidence", 0.0)

        # Determine validation priority (urgent if actively cited)
        validation_priority = current.get("validation_priority", "normal")

        # Build history entry for flips
        now = datetime.now()
        history_entry = {
            "state": validation_state,
            "timestamp": now.isoformat(),
            "validated_by": validated_by,
            "notes": validation_notes,
            "confidence_at_validation": confidence_at_validation,
        }

        # Update validation_history
        if "validation_history" not in current:
            current["validation_history"] = []
        current["validation_history"].append(history_entry)

        # Update current validation fields
        current["human_validated"] = validation_state
        current["validated_at"] = now.isoformat()
        current["validated_by"] = validated_by
        current["validation_notes"] = validation_notes
        current["confidence_at_validation"] = confidence_at_validation
        current["validation_context_id"] = validation_context_id
        if chase_after:
            current["chase_after"] = chase_after

        self._persist_context(source)

        # Log CROSS_REF_VALIDATED to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadCrossRefValidated(
                source_context_id=source_context_id,
                target_context_id=target_context_id,
                validation_state=validation_state,
                validated_by=validated_by,
                validation_notes=validation_notes,
                confidence_at_validation=confidence_at_validation,
                validation_context_id=validation_context_id,
                validation_priority=validation_priority,
                previous_state=previous_state,
                chase_after=chase_after
            )
            oz.append(
                event_type=OzolithEventType.CROSS_REF_VALIDATED,
                context_id=source_context_id,
                actor=validated_by,
                payload=payload_to_dict(payload)
            )

        logger.info(f"Validated cross-ref: {source_context_id} --> {target_context_id} = {validation_state}")

        return {
            "success": True,
            "source_context_id": source_context_id,
            "target_context_id": target_context_id,
            "validation_state": validation_state,
            "previous_state": previous_state,
            "confidence_at_validation": confidence_at_validation,
            "is_flip": previous_state is not None and previous_state != validation_state,
        }

    def get_pending_validations(self) -> List[Dict]:
        """
        Get all cross-refs awaiting human validation.

        Returns refs where human_validated is None across all contexts.
        Useful for batch review: "show me everything I haven't looked at yet."

        Returns:
            List of dicts with source_id, target_id, and ref metadata
        """
        pending = []
        for context_id, context in self._contexts.items():
            for target_id, metadata in context.cross_sidebar_refs.items():
                if metadata.get("human_validated") is None:
                    pending.append({
                        "source_context_id": context_id,
                        "target_context_id": target_id,
                        "ref_type": metadata.get("ref_type"),
                        "strength": metadata.get("strength"),
                        "confidence": metadata.get("confidence"),
                        "reason": metadata.get("reason"),
                        "created_at": metadata.get("created_at"),
                        "validation_priority": metadata.get("validation_priority", "normal"),
                    })

        # Sort by priority (urgent first), then by created_at
        pending.sort(key=lambda x: (
            0 if x.get("validation_priority") == "urgent" else 1,
            x.get("created_at") or ""
        ))

        return pending

    # =========================================================================
    # VALIDATION PROMPTS (End-of-Exchange Surfacing)
    # =========================================================================
    # Surfaces refs needing validation at natural conversation breakpoints.
    # Inline: only if actively citing. Everything else → scratchpad.
    # See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9.

    VALIDATION_CONFIDENCE_THRESHOLD = 0.7  # Below this, prompt for validation
    STALENESS_DAYS = 3  # Bump priority after this many days pending

    def get_validation_prompts(
        self,
        current_context_id: str,
        citing_refs: Optional[List[str]] = None,
        exchange_created_refs: Optional[List[str]] = None
    ) -> Dict:
        """
        Get refs needing validation, routed for end-of-exchange prompts.

        Applies urgency signals:
        - About-to-cite: refs in citing_refs list get INLINE routing
        - Staleness: pending > STALENESS_DAYS bumps priority
        - Cluster-flagged: 3+ sources suggested same ref
        - Low confidence: below VALIDATION_CONFIDENCE_THRESHOLD
        - Contradiction: conflicting ref_types between same contexts

        Args:
            current_context_id: Active context for this exchange
            citing_refs: List of "{source}:{target}" refs being actively cited
            exchange_created_refs: Refs created this exchange (for inline routing)

        Returns:
            Dict with inline_prompts and scratchpad_prompts
        """
        citing_refs = citing_refs or []
        exchange_created_refs = exchange_created_refs or []

        inline_prompts = []
        scratchpad_prompts = []

        now = datetime.now()

        for context_id, context in self._contexts.items():
            for target_id, metadata in context.cross_sidebar_refs.items():
                # Skip already validated
                if metadata.get("human_validated") is not None:
                    continue

                ref_key = f"{context_id}:{target_id}"

                # Calculate urgency score
                urgency_score = 0
                urgency_reasons = []

                # About-to-cite (highest priority)
                is_citing = ref_key in citing_refs
                if is_citing:
                    urgency_score += 100
                    urgency_reasons.append("actively_citing")

                # Created this exchange
                is_current_exchange = ref_key in exchange_created_refs
                if is_current_exchange:
                    urgency_score += 50
                    urgency_reasons.append("created_this_exchange")

                # Cluster-flagged
                if metadata.get("cluster_flagged"):
                    urgency_score += 30
                    urgency_reasons.append(f"cluster_flagged_{len(metadata.get('suggested_sources', []))}_sources")

                # Low confidence
                confidence = metadata.get("confidence", 0.0)
                if confidence < self.VALIDATION_CONFIDENCE_THRESHOLD:
                    urgency_score += 20
                    urgency_reasons.append(f"low_confidence_{confidence:.2f}")

                # Staleness
                created_at = metadata.get("created_at")
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(created_at)
                        days_pending = (now - created_dt).days
                        if days_pending >= self.STALENESS_DAYS:
                            urgency_score += 15
                            urgency_reasons.append(f"stale_{days_pending}_days")
                    except (ValueError, TypeError):
                        pass

                # Urgent priority already set
                if metadata.get("validation_priority") == "urgent":
                    urgency_score += 25
                    if "urgent_priority" not in urgency_reasons:
                        urgency_reasons.append("urgent_priority")

                # Skip if no urgency signals
                if urgency_score == 0:
                    continue

                prompt_data = {
                    "source_context_id": context_id,
                    "target_context_id": target_id,
                    "ref_type": metadata.get("ref_type"),
                    "strength": metadata.get("strength"),
                    "confidence": confidence,
                    "reason": metadata.get("reason"),
                    "urgency_score": urgency_score,
                    "urgency_reasons": urgency_reasons,
                    "suggested_sources": metadata.get("suggested_sources", []),
                }

                # Route: inline if citing, else scratchpad
                if is_citing:
                    inline_prompts.append(prompt_data)
                else:
                    scratchpad_prompts.append(prompt_data)

        # Sort by urgency score (highest first)
        inline_prompts.sort(key=lambda x: x["urgency_score"], reverse=True)
        scratchpad_prompts.sort(key=lambda x: x["urgency_score"], reverse=True)

        return {
            "success": True,
            "inline_prompts": inline_prompts,
            "scratchpad_prompts": scratchpad_prompts,
            "inline_count": len(inline_prompts),
            "scratchpad_count": len(scratchpad_prompts),
            "total_pending": len(inline_prompts) + len(scratchpad_prompts)
        }

    def detect_contradictions(self, context_id: Optional[str] = None) -> List[Dict]:
        """
        Detect contradicting cross-refs (e.g., A implements B AND A contradicts B).

        These are high-priority validation targets - something is wrong.

        Args:
            context_id: Limit to specific context, or None for all

        Returns:
            List of contradiction pairs needing resolution
        """
        # Contradicting ref_type pairs
        CONTRADICTIONS = {
            ("implements", "contradicts"),
            ("derived_from", "contradicts"),
            ("cites", "contradicts"),
            ("depends_on", "blocks"),
            ("informs", "contradicts"),
        }

        contradictions = []
        contexts_to_check = (
            [self._contexts.get(context_id)] if context_id
            else self._contexts.values()
        )

        for context in contexts_to_check:
            if context is None:
                continue

            # Group refs by target
            refs_by_target = {}
            for target_id, metadata in context.cross_sidebar_refs.items():
                if target_id not in refs_by_target:
                    refs_by_target[target_id] = []
                refs_by_target[target_id].append(metadata.get("ref_type"))

            # Check for contradicting types to same target
            # (This would require multiple refs to same target with different types,
            #  which our current model doesn't support. But leaving logic for future.)

        # Cross-context contradiction check
        # If context A says "A implements B" but context B says "B contradicts A"
        seen_refs = {}  # {(sorted_pair): [(context, target, ref_type), ...]}

        for context in (contexts_to_check if context_id else self._contexts.values()):
            if context is None:
                continue

            for target_id, metadata in context.cross_sidebar_refs.items():
                pair = tuple(sorted([context.sidebar_id, target_id]))
                ref_type = metadata.get("ref_type")

                if pair not in seen_refs:
                    seen_refs[pair] = []
                seen_refs[pair].append({
                    "from": context.sidebar_id,
                    "to": target_id,
                    "ref_type": ref_type
                })

        # Find pairs with contradicting ref_types
        for pair, refs in seen_refs.items():
            ref_types = set(r["ref_type"] for r in refs)
            for t1, t2 in CONTRADICTIONS:
                if t1 in ref_types and t2 in ref_types:
                    contradictions.append({
                        "contexts": list(pair),
                        "conflicting_refs": refs,
                        "contradiction_type": f"{t1}_vs_{t2}"
                    })

        return contradictions

    def check_chain_stability(self, context_id: str) -> Dict:
        """
        Check if context's dependencies have unvalidated refs (chain instability).

        If A depends_on B, and B's refs are unvalidated, A's foundation is shaky.

        Args:
            context_id: Context to check

        Returns:
            Dict with stability assessment and unstable dependencies
        """
        context = self._contexts.get(context_id)
        if context is None:
            return {"success": False, "error": f"Context '{context_id}' not found"}

        unstable_deps = []

        for target_id, metadata in context.cross_sidebar_refs.items():
            ref_type = metadata.get("ref_type")

            # Only check dependency-type refs
            if ref_type not in ["depends_on", "derived_from", "implements"]:
                continue

            # Check if the target has unvalidated DEPENDENCY refs
            # (inverse refs like 'informs', 'cited_by' don't count - not real dependencies)
            target = self._contexts.get(target_id)
            if target is None:
                continue

            DEPENDENCY_TYPES = {"depends_on", "derived_from", "implements"}
            unvalidated_count = 0
            for _, target_metadata in target.cross_sidebar_refs.items():
                # Only count dependency-type refs, not inverse/symmetric refs
                if target_metadata.get("ref_type") in DEPENDENCY_TYPES:
                    if target_metadata.get("human_validated") is None:
                        unvalidated_count += 1

            if unvalidated_count > 0:
                unstable_deps.append({
                    "dependency": target_id,
                    "ref_type": ref_type,
                    "unvalidated_refs_in_dependency": unvalidated_count,
                    "our_ref_validated": metadata.get("human_validated") is not None
                })

        return {
            "success": True,
            "context_id": context_id,
            "is_stable": len(unstable_deps) == 0,
            "unstable_dependencies": unstable_deps,
            "stability_score": 1.0 if len(unstable_deps) == 0 else max(0.0, 1.0 - (len(unstable_deps) * 0.2))
        }

    # =========================================================================
    # YARN BOARD OPERATIONS
    # =========================================================================
    # Yarn board is a VIEW layer over OZOLITH + Redis + cross-refs.
    # Layout persists to SQLite (via SidebarContext.yarn_board_layout).
    # Hot state (grabbed yarn) will live in Redis when implemented.
    # See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9.

    def get_yarn_layout(self, context_id: str) -> Dict:
        """
        Get the yarn board layout for a context.

        Returns the visual layout (point positions, zoom, filters) for
        rendering the yarn board. If no layout exists, returns default.

        Args:
            context_id: Context whose board layout to retrieve

        Returns:
            Dict with layout data (point_positions, zoom_level, etc.)
        """
        context = self._contexts.get(context_id)
        if context is None:
            return {"success": False, "error": f"Context '{context_id}' not found"}

        layout = context.yarn_board_layout
        if not layout:
            # Return default layout
            return {
                "success": True,
                "context_id": context_id,
                "layout": {
                    "point_positions": {},
                    "zoom_level": 1.0,
                    "focus_point": None,
                    "show_archived": False,
                    "filter_by_priority": None,
                    "filter_by_type": None,
                }
            }

        return {
            "success": True,
            "context_id": context_id,
            "layout": layout
        }

    def save_yarn_layout(
        self,
        context_id: str,
        point_positions: Optional[Dict[str, Dict]] = None,
        zoom_level: Optional[float] = None,
        focus_point: Optional[str] = None,
        show_archived: Optional[bool] = None,
        filter_by_priority: Optional[str] = None,
        filter_by_type: Optional[str] = None
    ) -> Dict:
        """
        Save or update the yarn board layout for a context.

        Only updates fields that are provided (not None).
        Persists so the board can "grow over time" between sessions.

        Args:
            context_id: Context whose board layout to save
            point_positions: {point_id: {x, y, collapsed}} positions
            zoom_level: Current zoom level (default 1.0)
            focus_point: Currently centered point ID
            show_archived: Whether to show archived points
            filter_by_priority: Only show certain priority levels
            filter_by_type: Only show certain point types

        Returns:
            Dict with success status and updated layout
        """
        context = self._contexts.get(context_id)
        if context is None:
            return {"success": False, "error": f"Context '{context_id}' not found"}

        # Initialize layout if empty
        if not context.yarn_board_layout:
            context.yarn_board_layout = {
                "point_positions": {},
                "zoom_level": 1.0,
                "focus_point": None,
                "show_archived": False,
                "filter_by_priority": None,
                "filter_by_type": None,
                "last_modified": datetime.now().isoformat()
            }

        # Update only provided fields
        if point_positions is not None:
            context.yarn_board_layout["point_positions"] = point_positions
        if zoom_level is not None:
            context.yarn_board_layout["zoom_level"] = zoom_level
        if focus_point is not None:
            context.yarn_board_layout["focus_point"] = focus_point
        if show_archived is not None:
            context.yarn_board_layout["show_archived"] = show_archived
        if filter_by_priority is not None:
            context.yarn_board_layout["filter_by_priority"] = filter_by_priority
        if filter_by_type is not None:
            context.yarn_board_layout["filter_by_type"] = filter_by_type

        context.yarn_board_layout["last_modified"] = datetime.now().isoformat()

        self._persist_context(context)

        logger.info(f"Saved yarn board layout for context: {context_id}")

        return {
            "success": True,
            "context_id": context_id,
            "layout": context.yarn_board_layout
        }

    def update_point_position(
        self,
        context_id: str,
        point_id: str,
        x: float,
        y: float,
        collapsed: bool = False
    ) -> Dict:
        """
        Update a single point's position on the yarn board.

        Convenience method for drag-and-drop positioning without
        sending the entire layout.

        Args:
            context_id: Context whose board to update
            point_id: Point being positioned
            x: X coordinate
            y: Y coordinate
            collapsed: Whether point is visually collapsed

        Returns:
            Dict with success status
        """
        context = self._contexts.get(context_id)
        if context is None:
            return {"success": False, "error": f"Context '{context_id}' not found"}

        # Initialize layout if empty
        if not context.yarn_board_layout:
            context.yarn_board_layout = {
                "point_positions": {},
                "zoom_level": 1.0,
                "focus_point": None,
                "show_archived": False,
                "filter_by_priority": None,
                "filter_by_type": None,
                "last_modified": datetime.now().isoformat()
            }

        # Update point position
        context.yarn_board_layout["point_positions"][point_id] = {
            "x": x,
            "y": y,
            "collapsed": collapsed
        }
        context.yarn_board_layout["last_modified"] = datetime.now().isoformat()

        self._persist_context(context)

        return {
            "success": True,
            "context_id": context_id,
            "point_id": point_id,
            "position": {"x": x, "y": y, "collapsed": collapsed}
        }

    def get_yarn_state(self, context_id: str) -> Dict:
        """
        Get the hot state for a yarn board (what's currently grabbed).

        NOTE: This is a stub. When Redis is implemented, this will fetch
        from Redis cache. For now, returns empty/default state.

        Args:
            context_id: Context whose hot state to retrieve

        Returns:
            Dict with grabbed points, priority overrides, hot refs
        """
        from datashapes import redis_interface

        # Try Redis first (will return None until implemented)
        cached = redis_interface.get_yarn_state(context_id)
        if cached:
            return {
                "success": True,
                "context_id": context_id,
                "state": {
                    "grabbed_point_ids": cached.get("grabbed_point_ids", []),
                    "priority_overrides": cached.get("priority_overrides", {}),
                    "hot_refs": cached.get("hot_refs", []),
                },
                "source": "redis"
            }

        # Fallback: return empty state
        return {
            "success": True,
            "context_id": context_id,
            "state": {
                "grabbed_point_ids": [],
                "priority_overrides": {},
                "hot_refs": [],
            },
            "source": "default"
        }

    def get_or_create_grab_huddle(self, context_id: str) -> str:
        """
        Get existing grab coordination huddle for this context, or create one.

        Design: ONE huddle per context. Any grab collisions in that context
        funnel into the same sidebar. Prevents coordination sidebar explosion.
        (Pizza Index pattern - huddle activity = collaboration intensity signal)

        Returns: sidebar_id of the huddle
        """
        # Check if huddle exists for this context
        existing = self._grab_huddles.get(context_id)

        if existing:
            # Verify it's still active (not archived/merged)
            huddle = self.get_context(existing)
            if huddle and huddle.status not in [SidebarStatus.ARCHIVED, SidebarStatus.MERGED]:
                return existing

        # Create new huddle
        huddle_id = self.spawn_sidebar(
            parent_id=context_id,
            reason="Point Grab Coordination Huddle",
            created_by="system",
            priority=SidebarPriority.HIGH,
            success_criteria="Agents sync up on contested points - clarify shared interest or divide work"
        )

        self._grab_huddles[context_id] = huddle_id
        logger.info(f"Created grab huddle {huddle_id} for context {context_id}")
        return huddle_id

    def set_grabbed(
        self,
        context_id: str,
        point_id: str,
        grabbed: bool,
        agent_id: str = "operator"
    ) -> Dict:
        """
        Mark a point as grabbed (focused) or released.

        Uses atomic HSETNX for collision detection (bathroom door lock pattern).
        If collision detected, routes to grab huddle (one per context) instead
        of spawning separate coordination sidebars.

        Args:
            context_id: Context whose board to update
            point_id: Point to grab/release
            grabbed: True to grab, False to release
            agent_id: Who is grabbing (for collision detection)

        Returns:
            Dict with success status, coordination info if collision occurred
        """
        from datashapes import redis_interface

        coordination_info = None

        if grabbed:
            # Atomic grab attempt - returns None if we got it, Dict if collision
            collision = redis_interface.try_grab_point(context_id, point_id, agent_id)

            if collision and collision.get("agent_id") != agent_id:
                # Collision! Get or create the huddle for this context
                other_agent = collision.get("agent_id", "unknown")
                grabbed_at = collision.get("grabbed_at", "unknown")

                logger.info(
                    f"Grab collision on {point_id}: {agent_id} and {other_agent} "
                    f"(grabbed since {grabbed_at}). Routing to huddle."
                )

                try:
                    huddle_id = self.get_or_create_grab_huddle(context_id)
                    huddle = self.get_context(huddle_id)

                    # Track contested points in huddle (store as metadata)
                    if not hasattr(huddle, 'contested_points'):
                        huddle.contested_points = {}

                    huddle.contested_points[point_id] = {
                        "agents": [agent_id, other_agent],
                        "added_at": datetime.now().isoformat()
                    }

                    # Notify both agents via queue
                    for aid in [agent_id, other_agent]:
                        redis_interface.queue_for_agent(aid, {
                            "type": "coordination_needed",
                            "huddle_id": huddle_id,
                            "point_id": point_id,
                            "contested_with": other_agent if aid == agent_id else agent_id,
                            "all_contested_points": list(huddle.contested_points.keys())
                        })

                    coordination_info = {
                        "huddle_id": huddle_id,
                        "point_id": point_id,
                        "agents": [agent_id, other_agent],
                        "total_contested_points": len(huddle.contested_points),
                        "reason": "grab_collision"
                    }
                    logger.info(f"Agents routed to huddle {huddle_id}, now {len(huddle.contested_points)} contested points")

                except Exception as e:
                    logger.error(f"Failed to create/update huddle: {e}")
                    coordination_info = {
                        "failed": True,
                        "error": str(e),
                        "agents": [agent_id, other_agent],
                        "point_id": point_id
                    }

                # Still set the grab (both agents can hold same point)
                redis_interface.set_grabbed(context_id, point_id, grabbed, agent_id)
                success = True
            else:
                # No collision - atomic grab already succeeded via try_grab_point
                success = collision is None
        else:
            # Release - just remove the grab
            success = redis_interface.set_grabbed(context_id, point_id, grabbed, agent_id)

        if grabbed:
            if success:
                logger.info(f"Grabbed point {point_id} in {context_id} by {agent_id}")
            else:
                logger.debug(f"Grab point {point_id} in {context_id} by {agent_id} (Redis not available)")
        else:
            logger.info(f"Released point {point_id} in {context_id} by {agent_id}")

        result = {
            "success": True,  # Always succeed - graceful degradation
            "context_id": context_id,
            "point_id": point_id,
            "grabbed": grabbed,
            "agent_id": agent_id,
            "persisted": success
        }

        if coordination_info:
            result["coordination"] = coordination_info

        return result

    def render_yarn_board(
        self,
        context_id: str,
        highlights: Optional[List[str]] = None,
        expanded: bool = False
    ) -> Dict:
        """
        Render the yarn board as a minimal minimap structure.

        The yarn board is a VIEW layer - all rich data lives in OZOLITH/SQLite/cross-refs.
        This just returns dots and strings for visualization.

        Point ID convention (self-describing):
        - context:{sidebar_id} - e.g., context:SB-1
        - crossref:{sorted_a}:{sorted_b} - e.g., crossref:SB-1:SB-2
        - finding:{entry_id} - e.g., finding:ENTRY-001

        Args:
            context_id: Context whose board to render
            highlights: Optional list of point IDs to highlight (model suggestions)
            expanded: If True, include detail dict with rich metadata for each point/connection

        Returns:
            Dict with points, connections, cushion, highlights
            When expanded=True, points and connections include 'detail' dict
        """
        context = self._contexts.get(context_id)
        if context is None:
            return {"success": False, "error": f"Context '{context_id}' not found"}

        layout = context.yarn_board_layout or {}
        point_positions = layout.get("point_positions", {})

        # Color scheme for point types
        TYPE_COLORS = {
            "context": "#4A90D9",    # Blue - sidebars/conversations
            "crossref": "#7B68EE",   # Purple - relationships
            "finding": "#50C878",    # Green - discoveries
            "question": "#FF6B6B",   # Red - questions needing answers
        }

        points = []
        connections = []
        cushion = []  # Items without positions

        # Helper to build context detail
        def _build_context_detail(ctx) -> Dict:
            """Build expanded detail for a context point."""
            scratchpad = ctx.scratchpad_entries if hasattr(ctx, 'scratchpad_entries') else []
            findings = [e for e in scratchpad if e.get("entry_type") == "finding"]
            questions = [e for e in scratchpad if e.get("entry_type") == "question"]
            return {
                "task_description": ctx.task_description or "",
                "status": ctx.status.value if hasattr(ctx.status, 'value') else str(ctx.status),
                "findings_count": len(findings),
                "questions_count": len(questions),
                "child_count": len(ctx.child_sidebar_ids),
                "cross_ref_count": len(ctx.cross_sidebar_refs),
                "created_at": ctx.created_at.isoformat() if hasattr(ctx, 'created_at') and ctx.created_at else None
            }

        # --- Collect context points ---
        # This context
        ctx_point_id = f"context:{context.sidebar_id}"
        pos = point_positions.get(ctx_point_id)
        point_data = {
            "id": ctx_point_id,
            "label": context.sidebar_id,
            "type": "context",
            "color": TYPE_COLORS["context"]
        }
        if expanded:
            point_data["detail"] = _build_context_detail(context)
        if pos:
            point_data["x"] = pos.get("x", 0)
            point_data["y"] = pos.get("y", 0)
            points.append(point_data)
        else:
            cushion.append(point_data)

        # Child contexts
        for child_id in context.child_sidebar_ids:
            child = self._contexts.get(child_id)
            if child:
                child_point_id = f"context:{child.sidebar_id}"
                pos = point_positions.get(child_point_id)
                child_data = {
                    "id": child_point_id,
                    "label": child.sidebar_id,
                    "type": "context",
                    "color": TYPE_COLORS["context"]
                }
                if expanded:
                    child_data["detail"] = _build_context_detail(child)
                if pos:
                    child_data["x"] = pos.get("x", 0)
                    child_data["y"] = pos.get("y", 0)
                    points.append(child_data)
                else:
                    cushion.append(child_data)

                # Connection: parent -> child
                conn_data = {
                    "from_id": ctx_point_id,
                    "to_id": child_point_id,
                    "ref_type": "parent_child"
                }
                if expanded:
                    conn_data["detail"] = {
                        "ref_type": "parent_child",
                        "relationship": "hierarchical"
                    }
                connections.append(conn_data)

        # Helper to build crossref detail
        def _build_crossref_detail(meta: Dict) -> Dict:
            """Build expanded detail for a crossref point."""
            if not isinstance(meta, dict):
                return {"ref_type": "related_to"}
            return {
                "ref_type": meta.get("ref_type", "related_to"),
                "strength": meta.get("strength", "normal"),
                "confidence": meta.get("confidence", 0.0),
                "human_validated": meta.get("human_validated"),
                "validation_state": "validated" if meta.get("human_validated") is not None else "pending",
                "reason": meta.get("reason", ""),
                "suggested_sources_count": len(meta.get("suggested_sources", [])),
                "cluster_flagged": meta.get("cluster_flagged", False),
                "discovery_method": meta.get("discovery_method", "unknown"),
                "created_at": meta.get("created_at")
            }

        # --- Collect cross-ref points and connections ---
        for target_id, metadata in context.cross_sidebar_refs.items():
            # Cross-ref as a point (sorted IDs for consistency)
            sorted_ids = sorted([context.sidebar_id, target_id])
            crossref_point_id = f"crossref:{sorted_ids[0]}:{sorted_ids[1]}"

            # Only add if not already added (bidirectional refs share a point)
            if not any(p["id"] == crossref_point_id for p in points + cushion):
                ref_type = metadata.get("ref_type", "related_to") if isinstance(metadata, dict) else "related_to"
                pos = point_positions.get(crossref_point_id)
                crossref_data = {
                    "id": crossref_point_id,
                    "label": ref_type,
                    "type": "crossref",
                    "color": TYPE_COLORS["crossref"]
                }
                if expanded:
                    crossref_data["detail"] = _build_crossref_detail(metadata)
                if pos:
                    crossref_data["x"] = pos.get("x", 0)
                    crossref_data["y"] = pos.get("y", 0)
                    points.append(crossref_data)
                else:
                    cushion.append(crossref_data)

            # Connection: context -> crossref point
            ref_type_val = metadata.get("ref_type", "related_to") if isinstance(metadata, dict) else "related_to"
            conn_data = {
                "from_id": ctx_point_id,
                "to_id": crossref_point_id,
                "ref_type": ref_type_val
            }
            if expanded:
                conn_data["detail"] = _build_crossref_detail(metadata)
            connections.append(conn_data)

            # Connection: crossref point -> target (if target exists)
            target = self._contexts.get(target_id)
            if target:
                target_point_id = f"context:{target.sidebar_id}"
                # Ensure target point exists
                if not any(p["id"] == target_point_id for p in points + cushion):
                    pos = point_positions.get(target_point_id)
                    target_data = {
                        "id": target_point_id,
                        "label": target.sidebar_id,
                        "type": "context",
                        "color": TYPE_COLORS["context"]
                    }
                    if expanded:
                        target_data["detail"] = _build_context_detail(target)
                    if pos:
                        target_data["x"] = pos.get("x", 0)
                        target_data["y"] = pos.get("y", 0)
                        points.append(target_data)
                    else:
                        cushion.append(target_data)

                target_conn_data = {
                    "from_id": crossref_point_id,
                    "to_id": target_point_id,
                    "ref_type": ref_type_val
                }
                if expanded:
                    target_conn_data["detail"] = _build_crossref_detail(metadata)
                connections.append(target_conn_data)

        # --- Process highlights ---
        highlight_list = highlights or []

        return {
            "success": True,
            "context_id": context_id,
            "points": points,
            "connections": connections,
            "cushion": cushion,
            "cushion_count": len(cushion),  # For UI to show "X items pending"
            "highlights": highlight_list,
            "type_colors": TYPE_COLORS,
            "expanded": expanded  # So frontend knows if details are included
        }

    # =========================================================================
    # QUEUE ROUTING (Scratchpad → Curator → Agents)
    # =========================================================================
    # Flow: Entry created → Curator validates → Route to destination agent
    # Uses RedisInterface stubs (gracefully degrades until Redis implemented)
    # See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9 for design.

    CURATOR_AGENT_ID = "AGENT-curator"

    def route_scratchpad_entry(
        self,
        entry: Dict,
        context_id: str,
        explicit_route_to: Optional[str] = None
    ) -> Dict:
        """
        Route a scratchpad entry through the validation/delivery pipeline.

        Flow:
        1. quick_note with no route → just store, done
        2. Everything else → queue for curator validation
        3. After validation → infer destination (or use explicit_route_to)
        4. Queue for destination agent

        Args:
            entry: ScratchpadEntry as dict (entry_id, content, entry_type, etc.)
            context_id: Context this entry belongs to
            explicit_route_to: Override auto-routing with specific agent

        Returns:
            Dict with routing status and destination
        """
        from datashapes import redis_interface

        entry_type = entry.get("entry_type", "finding")
        routed_to = explicit_route_to or entry.get("routed_to")

        # Quick notes with no explicit route → just store, no routing
        if entry_type == "quick_note" and not routed_to:
            logger.debug(f"Quick note {entry.get('entry_id')} stored without routing")
            return {
                "success": True,
                "entry_id": entry.get("entry_id"),
                "routed": False,
                "reason": "quick_note_no_route"
            }

        # Everything else goes through curator first
        curator_message = {
            "type": "validate_entry",
            "entry": entry,
            "context_id": context_id,
            "explicit_route_to": routed_to,
            "submitted_at": datetime.now().isoformat()
        }

        # Queue for curator (uses Redis stub - returns False until implemented)
        queued = redis_interface.queue_for_agent(self.CURATOR_AGENT_ID, curator_message)

        if queued:
            logger.info(f"Entry {entry.get('entry_id')} queued for curator validation")
        else:
            # Graceful degradation: log intent, store in context for manual pickup
            logger.debug(f"Entry {entry.get('entry_id')} pending curator (Redis unavailable)")

        return {
            "success": True,
            "entry_id": entry.get("entry_id"),
            "routed": True,
            "destination": self.CURATOR_AGENT_ID,
            "queued_to_redis": queued,
            "awaiting": "curator_validation"
        }

    def curator_approve_entry(
        self,
        entry_id: str,
        context_id: str,
        approved: bool,
        rejection_reason: Optional[str] = None
    ) -> Dict:
        """
        Curator approves or rejects an entry, then routes to destination.

        Called by curator agent after validation review.

        Args:
            entry_id: Entry being validated
            context_id: Context containing the entry
            approved: True to approve and route, False to reject
            rejection_reason: Why rejected (if not approved)

        Returns:
            Dict with approval status and final routing
        """
        from datashapes import redis_interface

        if not approved:
            logger.info(f"Entry {entry_id} rejected by curator: {rejection_reason}")
            return {
                "success": True,
                "entry_id": entry_id,
                "approved": False,
                "rejection_reason": rejection_reason
            }

        # Entry approved - find destination agent
        # TODO: Fetch entry from context to get explicit_route_to and content
        # For now, infer based on entry_type pattern

        destination = self._infer_destination(entry_id, context_id)

        # Queue for destination agent
        delivery_message = {
            "type": "routed_entry",
            "entry_id": entry_id,
            "context_id": context_id,
            "validated_by": self.CURATOR_AGENT_ID,
            "validated_at": datetime.now().isoformat()
        }

        queued = redis_interface.queue_for_agent(destination, delivery_message)

        if queued:
            logger.info(f"Entry {entry_id} approved and queued for {destination}")
        else:
            logger.debug(f"Entry {entry_id} approved, pending delivery to {destination} (Redis unavailable)")

        return {
            "success": True,
            "entry_id": entry_id,
            "approved": True,
            "destination": destination,
            "queued_to_redis": queued
        }

    def _infer_destination(
        self,
        entry_id: str,
        context_id: str,
        content_hint: Optional[str] = None
    ) -> str:
        """
        Infer best destination agent based on content and agent specialties.

        Simple keyword matching for now - can be enhanced with embeddings later.

        Args:
            entry_id: Entry being routed
            context_id: Context for additional hints
            content_hint: Optional content snippet for matching

        Returns:
            Agent ID of best match (defaults to operator if no match)
        """
        # Keyword to specialty mapping
        KEYWORD_SPECIALTIES = {
            "bug": "debugging",
            "error": "debugging",
            "crash": "debugging",
            "fix": "debugging",
            "research": "research",
            "find": "research",
            "look up": "research",
            "investigate": "research",
            "design": "design",
            "architecture": "architecture",
            "plan": "planning",
            "security": "security",
            "auth": "security",
            "permission": "security",
        }

        content = (content_hint or "").lower()

        # Find matching specialty
        matched_specialty = None
        for keyword, specialty in KEYWORD_SPECIALTIES.items():
            if keyword in content:
                matched_specialty = specialty
                break

        # Find agent with that specialty
        if matched_specialty:
            for agent_id, capability in self._agents.items():
                if matched_specialty in capability.specialties:
                    return agent_id

        # Default to operator (human) if no match
        return "AGENT-operator"

    def get_agent_queue(self, agent_id: str) -> Dict:
        """
        Get pending queue for an agent.

        Args:
            agent_id: Agent whose queue to fetch

        Returns:
            Dict with queue contents
        """
        from datashapes import redis_interface

        messages = redis_interface.get_agent_queue(agent_id)

        return {
            "success": True,
            "agent_id": agent_id,
            "queue": messages,
            "count": len(messages),
            "source": "redis" if messages else "stub"
        }

    def register_agent(
        self,
        agent_id: str,
        specialties: List[str],
        max_concurrent: int = 5
    ) -> Dict:
        """
        Register a new agent with their specialties.

        Args:
            agent_id: Unique agent identifier (AGENT-{name})
            specialties: List of specialty keywords
            max_concurrent: Max sidebars this agent can handle

        Returns:
            Dict with registration status
        """
        from datashapes import AgentCapability, AgentAvailability

        if agent_id in self._agents:
            # Update existing
            self._agents[agent_id].specialties = specialties
            self._agents[agent_id].max_concurrent = max_concurrent
            logger.info(f"Updated agent {agent_id} with specialties: {specialties}")
        else:
            # Create new
            self._agents[agent_id] = AgentCapability(
                agent_id=agent_id,
                specialties=specialties,
                availability=AgentAvailability.AVAILABLE,
                max_concurrent=max_concurrent
            )
            logger.info(f"Registered agent {agent_id} with specialties: {specialties}")

        return {
            "success": True,
            "agent_id": agent_id,
            "specialties": specialties,
            "registered": True
        }

    def list_agents(self) -> Dict:
        """List all registered agents and their specialties."""
        agents_list = []
        for agent_id, capability in self._agents.items():
            agents_list.append({
                "agent_id": agent_id,
                "specialties": capability.specialties,
                "availability": capability.availability.value,
                "current_load": capability.current_load,
                "max_concurrent": capability.max_concurrent
            })

        return {
            "success": True,
            "agents": agents_list,
            "count": len(agents_list)
        }

    # =========================================================================
    # ARCHIVE OPERATIONS
    # =========================================================================

    def archive_context(
        self,
        context_id: str,
        reason: str = "manual"
    ) -> bool:
        """
        Archive a context (move to episodic memory).

        Args:
            context_id: Context to archive
            reason: Why archiving ("merged", "manual", "timeout", etc.)

        Returns:
            True if archived, False if not found
        """
        context = self._contexts.get(context_id)
        if context is None:
            return False

        context.status = SidebarStatus.ARCHIVED
        context.last_activity = datetime.now()

        # Persist archived status
        self._persist_context(context)

        # Log SESSION_END to OZOLITH
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadSession(
                session_id=context.uuid,
                interface="orchestrator",
                summary=f"Archived: {reason}",
                exchange_count=len(context.local_memory),
                extra={"archive_reason": reason}
            )
            oz.append(
                event_type=OzolithEventType.SESSION_END,
                context_id=context_id,
                actor="system",
                payload=payload_to_dict(payload)
            )

        # TODO: Actually persist to episodic memory service
        # For now just mark the status

        logger.info(f"Archived context {context_id}: {reason}")

        # If this was active, switch to parent or None
        if self._active_context_id == context_id:
            if context.parent_context_id:
                self._active_context_id = context.parent_context_id
            else:
                self._active_context_id = None
            # Persist focus change
            self._persist_focus()

        return True

    # =========================================================================
    # QUERIES
    # =========================================================================

    def list_contexts(
        self,
        status: Optional[SidebarStatus] = None,
        include_archived: bool = False
    ) -> List[SidebarContext]:
        """
        List contexts, optionally filtered.

        Args:
            status: Filter by status (None = all non-archived)
            include_archived: Include archived contexts

        Returns:
            List of matching contexts
        """
        results = []
        for context in self._contexts.values():
            if not include_archived and context.status == SidebarStatus.ARCHIVED:
                continue
            if status is not None and context.status != status:
                continue
            results.append(context)
        return results

    def list_sidebars(self, parent_id: str) -> List[SidebarContext]:
        """Get all sidebars (children) of a context."""
        parent = self._contexts.get(parent_id)
        if parent is None:
            return []

        return [
            self._contexts[child_id]
            for child_id in parent.child_sidebar_ids
            if child_id in self._contexts
        ]

    def get_lineage(self, context_id: str) -> List[str]:
        """
        Get full lineage from root to this context.

        Returns:
            List of display IDs from root to context_id
        """
        return self.registry.get_lineage(context_id)

    def get_tree(self, root_id: Optional[str] = None) -> Dict:
        """
        Get tree structure for visualization.

        Args:
            root_id: Starting point. None = all roots.

        Returns:
            Nested dict representing the tree
        """
        return self.registry.get_tree(root_id)

    # =========================================================================
    # STATS
    # =========================================================================

    def stats(self) -> Dict:
        """Get orchestrator statistics."""
        status_counts = {}
        for context in self._contexts.values():
            status_name = context.status.value
            status_counts[status_name] = status_counts.get(status_name, 0) + 1

        return {
            "total_contexts": len(self._contexts),
            "active_context_id": self._active_context_id,
            "by_status": status_counts,
            "registry_stats": self.registry.stats(),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_orchestrator_instance: Optional[ConversationOrchestrator] = None


def get_orchestrator(error_handler=None, auto_load: bool = True) -> ConversationOrchestrator:
    """
    Get the global orchestrator instance.

    Args:
        error_handler: Optional ErrorHandler for error routing
        auto_load: Whether to load persisted state (default True)

    Usage:
        from conversation_orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        sidebar_id = orchestrator.spawn_sidebar(...)
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = ConversationOrchestrator(
            error_handler=error_handler,
            auto_load=auto_load
        )

    return _orchestrator_instance


def reset_orchestrator():
    """Reset the global orchestrator and persistence (for testing)."""
    global _orchestrator_instance
    global _persistence_instance
    _orchestrator_instance = None
    _persistence_instance = None
