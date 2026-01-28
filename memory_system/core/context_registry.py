#!/usr/bin/env python3
"""
context_registry.py - Centralized Context Relationship Tracking

All context IDs (SB-X, MSG-X, etc.) and their relationships are tracked here.
This is the single source of truth for "who is parent of whom" across all memory types.

Other services store just the context_id string - they query here for relationships.

Storage Backend Architecture:
    Layer 1: JSON file - Simple, always works, good for dev/testing
    Layer 2: SQLite - Local queries, indexes, concurrent reads
    Layer 3: Redis - Distributed access, pub/sub, real-time sync

Created: 2025-12-03
Source: UNIFIED_SIDEBAR_ARCHITECTURE.md Section 2 (Identification System)
"""

import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# STORAGE BACKEND ABSTRACTION
# =============================================================================

class StorageBackend(ABC):
    """
    Abstract base for registry storage backends.

    Implement this interface to add new storage layers (SQLite, Redis, etc.)
    The registry calls save() and load() - backend handles the rest.
    """

    @abstractmethod
    def save(self, state: Dict) -> bool:
        """
        Save registry state.

        Args:
            state: Dict with 'counters' and 'contexts' keys

        Returns:
            True if save succeeded, False otherwise
        """
        pass

    @abstractmethod
    def load(self) -> Optional[Dict]:
        """
        Load registry state.

        Returns:
            State dict if found, None if no saved state exists
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available/configured."""
        pass

    def get_name(self) -> str:
        """Human-readable backend name."""
        return self.__class__.__name__


class JSONFileBackend(StorageBackend):
    """
    Layer 1: JSON file storage.

    Simple, always works, good for development and testing.
    Uses atomic write (temp file + rename) for crash safety.
    """

    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            file_path = os.path.expanduser(
                "~/.local/share/memory_system/context_registry.json"
            )
        self.file_path = file_path

    def save(self, state: Dict) -> bool:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

            # Backup current file before overwriting (cheap insurance)
            # If new write goes bad, we have previous state
            backup_path = self.file_path + ".bak"
            if os.path.exists(self.file_path):
                try:
                    import shutil
                    shutil.copy2(self.file_path, backup_path)
                except Exception as e:
                    logger.debug(f"Could not create backup: {e}")
                    # Continue anyway - backup is nice-to-have

            # Atomic write: write to temp, then rename
            # This prevents corruption if crash happens mid-write
            temp_path = self.file_path + ".tmp"
            with open(temp_path, "w") as f:
                json.dump(state, f, indent=2)

            # Set restrictive permissions before rename (owner read/write only)
            # Protects against other users on the system reading/modifying
            os.chmod(temp_path, 0o600)

            os.replace(temp_path, self.file_path)

            return True
        except Exception as e:
            logger.warning(f"JSONFileBackend save failed: {e}")
            return False

    def restore_from_backup(self) -> bool:
        """
        Restore from backup file if main file is corrupted.

        Returns:
            True if restored successfully, False otherwise
        """
        backup_path = self.file_path + ".bak"
        if not os.path.exists(backup_path):
            logger.warning("No backup file exists to restore from")
            return False

        try:
            import shutil
            shutil.copy2(backup_path, self.file_path)
            logger.info(f"Restored context registry from backup")
            return True
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False

    def load(self) -> Optional[Dict]:
        try:
            if not os.path.exists(self.file_path):
                return None

            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"JSONFileBackend load failed: {e}")
            return None

    def is_available(self) -> bool:
        # JSON file backend is always available
        return True


class SQLiteBackend(StorageBackend):
    """
    Layer 2: SQLite storage.

    Benefits over JSON:
    - Concurrent reads from multiple processes
    - Indexed queries (find by type, by parent, etc.)
    - Atomic transactions
    - Better for large datasets

    TODO: Implement when JSON becomes a bottleneck
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.expanduser(
                "~/.local/share/memory_system/context_registry.db"
            )
        self.db_path = db_path
        self._connection = None

    def save(self, state: Dict) -> bool:
        # TODO: Implement SQLite save
        # Schema:
        #   CREATE TABLE contexts (
        #       display_id TEXT PRIMARY KEY,
        #       uuid TEXT UNIQUE,
        #       context_type TEXT,
        #       parent_id TEXT,
        #       created_at TEXT,
        #       created_by TEXT,
        #       created_in TEXT,
        #       description TEXT,
        #       FOREIGN KEY (parent_id) REFERENCES contexts(display_id)
        #   );
        #   CREATE TABLE context_children (
        #       parent_id TEXT,
        #       child_id TEXT,
        #       PRIMARY KEY (parent_id, child_id)
        #   );
        #   CREATE TABLE context_tags (
        #       display_id TEXT,
        #       tag TEXT,
        #       PRIMARY KEY (display_id, tag)
        #   );
        #   CREATE TABLE counters (
        #       context_type TEXT PRIMARY KEY,
        #       next_value INTEGER
        #   );
        logger.debug("SQLiteBackend.save() called but not yet implemented")
        return False

    def load(self) -> Optional[Dict]:
        # TODO: Implement SQLite load
        logger.debug("SQLiteBackend.load() called but not yet implemented")
        return None

    def is_available(self) -> bool:
        # Check if SQLite is configured and database exists
        # For now, always return False until implemented
        return False

    def _get_connection(self):
        """Get or create database connection."""
        # TODO: Implement connection management
        # import sqlite3
        # if self._connection is None:
        #     self._connection = sqlite3.connect(self.db_path)
        #     self._init_schema()
        # return self._connection
        pass

    def _init_schema(self):
        """Create tables if they don't exist."""
        # TODO: Implement schema creation
        pass


class RedisBackend(StorageBackend):
    """
    Layer 3: Redis storage.

    Benefits over SQLite:
    - Network accessible (multiple services can share)
    - Pub/sub for real-time updates
    - Very fast reads (in-memory)
    - Can broadcast context changes to other services

    TODO: Implement when we need distributed access
    """

    def __init__(self, redis_url: Optional[str] = None):
        if redis_url is None:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.redis_url = redis_url
        self._client = None

        # Redis key prefixes
        self.KEY_PREFIX = "context_registry:"
        self.COUNTERS_KEY = f"{self.KEY_PREFIX}counters"
        self.CONTEXTS_KEY = f"{self.KEY_PREFIX}contexts"

    def save(self, state: Dict) -> bool:
        # TODO: Implement Redis save
        # Use Redis hash for contexts: HSET context_registry:contexts SB-1 {json}
        # Use Redis hash for counters: HSET context_registry:counters SB 42
        # Publish change notification: PUBLISH context_registry:changes {event}
        logger.debug("RedisBackend.save() called but not yet implemented")
        return False

    def load(self) -> Optional[Dict]:
        # TODO: Implement Redis load
        # HGETALL context_registry:contexts
        # HGETALL context_registry:counters
        logger.debug("RedisBackend.load() called but not yet implemented")
        return None

    def is_available(self) -> bool:
        # Check if Redis is reachable
        # For now, always return False until implemented
        return False

    def _get_client(self):
        """Get or create Redis client."""
        # TODO: Implement client management
        # import redis
        # if self._client is None:
        #     self._client = redis.from_url(self.redis_url)
        # return self._client
        pass

    def publish_change(self, event_type: str, display_id: str, data: Dict):
        """
        Publish context change for other services to hear.

        Event types: 'created', 'updated', 'deleted'
        """
        # TODO: Implement pub/sub
        # client = self._get_client()
        # event = {"type": event_type, "id": display_id, "data": data}
        # client.publish(f"{self.KEY_PREFIX}changes", json.dumps(event))
        pass


class MultiLayerBackend(StorageBackend):
    """
    Orchestrates multiple storage backends with fallback.

    Write order: All backends (for redundancy)
    Read order: First available (fastest first)

    Example:
        backend = MultiLayerBackend([
            RedisBackend(),    # Try Redis first (fastest)
            SQLiteBackend(),   # Fall back to SQLite
            JSONFileBackend(), # Last resort: JSON file
        ])
    """

    def __init__(self, backends: List[StorageBackend]):
        self.backends = backends

    def save(self, state: Dict) -> bool:
        """Save to all available backends."""
        success = False
        for backend in self.backends:
            if backend.is_available():
                if backend.save(state):
                    success = True
                    logger.debug(f"Saved to {backend.get_name()}")
                else:
                    logger.warning(f"Failed to save to {backend.get_name()}")
        return success

    def load(self) -> Optional[Dict]:
        """Load from first available backend."""
        for backend in self.backends:
            if backend.is_available():
                state = backend.load()
                if state is not None:
                    logger.debug(f"Loaded from {backend.get_name()}")
                    return state
        return None

    def is_available(self) -> bool:
        """Available if any backend is available."""
        return any(b.is_available() for b in self.backends)

    def get_name(self) -> str:
        available = [b.get_name() for b in self.backends if b.is_available()]
        return f"MultiLayer({', '.join(available)})"


# =============================================================================
# CONTEXT TYPES AND ENTRY
# =============================================================================

class ContextType(Enum):
    """Types of referenceable objects in the system."""
    MESSAGE = "MSG"           # Any message in any conversation/sidebar
    CITATION = "CITE"         # Artifact, document, code snippet
    SIDEBAR = "SB"            # A sidebar context
    FILE = "FILE"             # Referenced file
    FRAGMENT = "FRAG"         # Working memory fragment
    EXCHANGE = "EXCH"         # Full user/assistant exchange pair
    GOLD = "GOLD"             # Realignment waypoint
    AGENT = "AGENT"           # Agent identifier
    MEDIA = "MEDIA"           # Media attachment
    SCRATCHPAD = "SCRATCH"    # Scratchpad for a sidebar


@dataclass
class ContextEntry:
    """
    Single entry in the context registry.
    Tracks identity, relationships, and origin.
    """
    # Display ID (human-readable)
    display_id: str               # e.g., "SB-89", "MSG-4521"

    # Full UUID (internal use)
    uuid: str

    # Type
    context_type: ContextType

    # Relationships
    parent_id: Optional[str] = None       # Display ID of parent (e.g., "SB-88")
    children_ids: List[str] = field(default_factory=list)  # Display IDs of children

    # Origin tracking
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""                  # Agent or human
    created_in: Optional[str] = None      # Which context this was created in

    # Metadata
    description: Optional[str] = None     # Brief description
    tags: List[str] = field(default_factory=list)


class ContextRegistry:
    """
    Centralized registry for all context IDs and relationships.

    This is the ONE place that knows:
    - What contexts exist
    - Who is parent of whom
    - The full lineage of any context

    Thread-safe for concurrent access.

    Usage:
        registry = ContextRegistry()

        # Create root conversation
        main_id = registry.register("SB", created_by="human")
        # Returns: "SB-1"

        # Create child sidebar
        sidebar_id = registry.register("SB", parent_id=main_id, created_by="human")
        # Returns: "SB-2"

        # Query relationships
        registry.get_parent(sidebar_id)  # Returns: "SB-1"
        registry.get_children(main_id)   # Returns: ["SB-2"]
        registry.get_lineage(sidebar_id) # Returns: ["SB-1", "SB-2"]
    """

    def __init__(
        self,
        backend: Optional[StorageBackend] = None,
        persistence_path: Optional[str] = None  # Legacy param, prefer backend
    ):
        """
        Initialize registry with storage backend.

        Args:
            backend: Storage backend to use. If None, uses JSONFileBackend.
                     For multi-layer storage, pass MultiLayerBackend.
            persistence_path: Legacy param for JSON file path. Ignored if
                              backend is provided.

        Examples:
            # Simple JSON (default)
            registry = ContextRegistry()

            # Explicit JSON path
            registry = ContextRegistry(persistence_path="/custom/path.json")

            # Multi-layer with fallback
            registry = ContextRegistry(backend=MultiLayerBackend([
                RedisBackend(),
                SQLiteBackend(),
                JSONFileBackend(),
            ]))
        """
        self._lock = threading.RLock()

        # Counters for each context type (for sequential IDs)
        self._counters: Dict[str, int] = {}

        # All registered contexts: display_id -> ContextEntry
        self._contexts: Dict[str, ContextEntry] = {}

        # Reverse lookup: uuid -> display_id
        self._uuid_to_display: Dict[str, str] = {}

        # Set up storage backend
        if backend is not None:
            self._backend = backend
        else:
            # Default to JSON file backend
            self._backend = JSONFileBackend(file_path=persistence_path)

        # Legacy compat - keep this for any code that checks it directly
        if isinstance(self._backend, JSONFileBackend):
            self._persistence_path = self._backend.file_path
        else:
            self._persistence_path = None

        # Load existing state if available
        self._load_state()

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register(
        self,
        context_type: str,
        uuid: Optional[str] = None,
        parent_id: Optional[str] = None,
        created_by: str = "",
        created_in: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Register a new context and get its display ID.

        Args:
            context_type: Type prefix ("SB", "MSG", "CITE", etc.)
            uuid: Full UUID. If None, one is generated.
            parent_id: Display ID of parent context (for hierarchy).
            created_by: Who created this (agent ID or "human").
            created_in: Which context this was created in.
            description: Brief description.
            tags: Optional tags for searchability.

        Returns:
            Display ID (e.g., "SB-89", "MSG-4521")
        """
        from uuid_extensions import uuid7

        with self._lock:
            # Generate UUID if not provided
            if uuid is None:
                uuid = str(uuid7())

            # Get next sequential number for this type
            if context_type not in self._counters:
                self._counters[context_type] = 0
            self._counters[context_type] += 1
            seq_num = self._counters[context_type]

            # Create display ID
            display_id = f"{context_type}-{seq_num}"

            # Validate parent exists if specified
            if parent_id is not None and parent_id not in self._contexts:
                raise ValueError(f"Parent context '{parent_id}' not found in registry")

            # Create entry
            entry = ContextEntry(
                display_id=display_id,
                uuid=uuid,
                context_type=ContextType(context_type) if context_type in [t.value for t in ContextType] else ContextType.SIDEBAR,
                parent_id=parent_id,
                created_by=created_by,
                created_in=created_in,
                description=description,
                tags=tags or []
            )

            # Store entry
            self._contexts[display_id] = entry
            self._uuid_to_display[uuid] = display_id

            # Update parent's children list
            if parent_id is not None:
                self._contexts[parent_id].children_ids.append(display_id)

            # Persist state
            self._save_state()

            return display_id

    def import_context(
        self,
        display_id: str,
        uuid: str,
        context_type: str,
        parent_id: Optional[str] = None,
        created_by: str = "",
        created_in: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        update_counter: bool = True
    ) -> bool:
        """
        Import an existing context with known display_id.

        Unlike register(), this does NOT generate a new ID - it uses the
        provided display_id. Used for rebuilding registry from external
        sources (like SQLite persistence).

        Args:
            display_id: The existing display ID (e.g., "SB-5")
            uuid: The context's UUID
            context_type: Type prefix ("SB", "MSG", etc.)
            parent_id: Display ID of parent context
            created_by: Who created this
            created_in: Which context this was created in
            description: Brief description
            tags: Optional tags
            update_counter: If True, ensures counter is at least as high
                           as this ID's number (prevents future collisions)

        Returns:
            True if imported, False if already exists
        """
        with self._lock:
            # Skip if already exists
            if display_id in self._contexts:
                return False

            # Parse the number from display_id to update counter
            if update_counter:
                try:
                    # Extract number from "SB-5" -> 5
                    parts = display_id.rsplit("-", 1)
                    if len(parts) == 2:
                        prefix, num_str = parts
                        num = int(num_str)
                        # Ensure counter is at least this high
                        current = self._counters.get(prefix, 0)
                        if num > current:
                            self._counters[prefix] = num
                except (ValueError, IndexError):
                    pass  # Non-numeric ID, skip counter update

            # Validate parent exists if specified
            if parent_id is not None and parent_id not in self._contexts:
                # Parent not imported yet - this can happen with out-of-order loading
                # We'll allow it and let the caller ensure ordering
                logger.debug(f"Parent '{parent_id}' not found during import of '{display_id}' - continuing anyway")

            # Create entry
            try:
                ctx_type = ContextType(context_type)
            except ValueError:
                ctx_type = ContextType.SIDEBAR  # Fallback

            entry = ContextEntry(
                display_id=display_id,
                uuid=uuid,
                context_type=ctx_type,
                parent_id=parent_id,
                created_by=created_by,
                created_in=created_in,
                description=description,
                tags=tags or []
            )

            # Store entry
            self._contexts[display_id] = entry
            self._uuid_to_display[uuid] = display_id

            # Update parent's children list if parent exists
            if parent_id is not None and parent_id in self._contexts:
                if display_id not in self._contexts[parent_id].children_ids:
                    self._contexts[parent_id].children_ids.append(display_id)

            # Don't persist here - caller should call save after batch import
            return True

    def save(self):
        """Explicitly save registry state. Call after batch imports."""
        self._save_state()

    def clear_type(self, context_type: str) -> int:
        """
        Clear all entries of a given type from the registry.

        Used to refresh derived state from an authoritative source.
        For SB-type contexts, SQLite should be CONSIDERED the source of truth,
        so we clear before importing from SQLite on startup.

        Args:
            context_type: Type prefix to clear (e.g., "SB")

        Returns:
            Number of entries cleared
        """
        with self._lock:
            to_remove = [
                display_id for display_id in self._contexts
                if display_id.startswith(f"{context_type}-")
            ]

            for display_id in to_remove:
                entry = self._contexts.pop(display_id)
                # Also remove from uuid lookup
                if entry.uuid in self._uuid_to_display:
                    del self._uuid_to_display[entry.uuid]
                # Remove from parent's children list
                if entry.parent_id and entry.parent_id in self._contexts:
                    parent = self._contexts[entry.parent_id]
                    if display_id in parent.children_ids:
                        parent.children_ids.remove(display_id)

            if to_remove:
                logger.info(f"Cleared {len(to_remove)} {context_type}-type entries from registry (will rebuild from SQLite)")

            return len(to_remove)

    # =========================================================================
    # RELATIONSHIP QUERIES
    # =========================================================================

    def get_parent(self, display_id: str) -> Optional[str]:
        """Get parent's display ID, or None if root."""
        with self._lock:
            entry = self._contexts.get(display_id)
            return entry.parent_id if entry else None

    def get_children(self, display_id: str) -> List[str]:
        """Get list of children's display IDs."""
        with self._lock:
            entry = self._contexts.get(display_id)
            return list(entry.children_ids) if entry else []

    def get_lineage(self, display_id: str) -> List[str]:
        """
        Get full lineage from root to this context.

        Returns:
            List of display IDs from root to display_id (inclusive).
            e.g., ["SB-1", "SB-5", "SB-12"] for a grandchild.
        """
        with self._lock:
            lineage = []
            current = display_id

            while current is not None:
                lineage.insert(0, current)
                entry = self._contexts.get(current)
                current = entry.parent_id if entry else None

            return lineage

    def get_root(self, display_id: str) -> Optional[str]:
        """Get the root ancestor of this context."""
        lineage = self.get_lineage(display_id)
        return lineage[0] if lineage else None

    def get_siblings(self, display_id: str) -> List[str]:
        """Get siblings (other children of same parent), excluding self."""
        with self._lock:
            entry = self._contexts.get(display_id)
            if not entry or not entry.parent_id:
                return []

            parent = self._contexts.get(entry.parent_id)
            if not parent:
                return []

            return [c for c in parent.children_ids if c != display_id]

    def get_descendants(self, display_id: str) -> List[str]:
        """Get all descendants (children, grandchildren, etc.)."""
        with self._lock:
            descendants = []
            to_visit = list(self.get_children(display_id))

            while to_visit:
                child = to_visit.pop(0)
                descendants.append(child)
                to_visit.extend(self.get_children(child))

            return descendants

    # =========================================================================
    # LOOKUP
    # =========================================================================

    def get_entry(self, display_id: str) -> Optional[ContextEntry]:
        """Get full entry for a context."""
        with self._lock:
            return self._contexts.get(display_id)

    def get_by_uuid(self, uuid: str) -> Optional[ContextEntry]:
        """Look up entry by UUID."""
        with self._lock:
            display_id = self._uuid_to_display.get(uuid)
            if display_id:
                return self._contexts.get(display_id)
            return None

    def display_id_from_uuid(self, uuid: str) -> Optional[str]:
        """Convert UUID to display ID."""
        with self._lock:
            return self._uuid_to_display.get(uuid)

    def uuid_from_display_id(self, display_id: str) -> Optional[str]:
        """Convert display ID to UUID."""
        with self._lock:
            entry = self._contexts.get(display_id)
            return entry.uuid if entry else None

    def exists(self, display_id: str) -> bool:
        """Check if a context exists."""
        with self._lock:
            return display_id in self._contexts

    # =========================================================================
    # QUERIES BY TYPE
    # =========================================================================

    def get_all_of_type(self, context_type: str) -> List[str]:
        """Get all display IDs of a given type."""
        with self._lock:
            return [
                entry.display_id
                for entry in self._contexts.values()
                if entry.display_id.startswith(f"{context_type}-")
            ]

    def get_roots(self, context_type: Optional[str] = None) -> List[str]:
        """
        Get all root contexts (no parent).

        Args:
            context_type: Optional filter - only return roots of this type
                         e.g., "SB" for sidebars only
        """
        with self._lock:
            results = []
            for entry in self._contexts.values():
                if entry.parent_id is not None:
                    continue
                # Filter by type if specified
                if context_type is not None:
                    entry_type = entry.context_type.value if isinstance(entry.context_type, ContextType) else str(entry.context_type)
                    if entry_type != context_type:
                        continue
                results.append(entry.display_id)
            return results

    # =========================================================================
    # TREE VISUALIZATION
    # =========================================================================

    def get_tree(self, root_id: Optional[str] = None, context_type: Optional[str] = "SB") -> Dict:
        """
        Get tree structure starting from root.

        Args:
            root_id: Starting point. If None, returns forest of all roots.
            context_type: Filter roots by type. Default "SB" for sidebars only.
                         Set to None to include all types.

        Returns:
            Nested dict representing the tree.
        """
        with self._lock:
            def build_subtree(display_id: str) -> Dict:
                entry = self._contexts.get(display_id)
                if not entry:
                    return {}

                # Only include SB children (not EXCH entries)
                sb_children = [
                    c for c in entry.children_ids
                    if c.startswith("SB-")
                ]

                return {
                    "id": display_id,
                    "uuid": entry.uuid,
                    "type": entry.context_type.value if isinstance(entry.context_type, ContextType) else str(entry.context_type),
                    "created_by": entry.created_by,
                    "description": entry.description,
                    "children": [build_subtree(c) for c in sb_children]
                }

            if root_id:
                return build_subtree(root_id)
            else:
                # Return forest of all roots (filtered by type)
                return {
                    "roots": [build_subtree(r) for r in self.get_roots(context_type=context_type)]
                }

    def print_tree(self, root_id: Optional[str] = None, indent: int = 0):
        """Print tree structure to console (for debugging)."""
        with self._lock:
            def print_subtree(display_id: str, level: int):
                entry = self._contexts.get(display_id)
                if not entry:
                    return

                prefix = "  " * level
                desc = f" - {entry.description}" if entry.description else ""
                print(f"{prefix}{display_id}{desc}")

                for child_id in entry.children_ids:
                    print_subtree(child_id, level + 1)

            if root_id:
                print_subtree(root_id, indent)
            else:
                for root in self.get_roots():
                    print_subtree(root, indent)

    # =========================================================================
    # PERSISTENCE (via StorageBackend)
    # =========================================================================

    def _serialize_state(self) -> Dict:
        """Serialize registry state to dict for storage."""
        return {
            "counters": self._counters,
            "contexts": {
                display_id: {
                    "display_id": entry.display_id,
                    "uuid": entry.uuid,
                    "context_type": entry.context_type.value if isinstance(entry.context_type, ContextType) else str(entry.context_type),
                    "parent_id": entry.parent_id,
                    "children_ids": entry.children_ids,
                    "created_at": entry.created_at.isoformat(),
                    "created_by": entry.created_by,
                    "created_in": entry.created_in,
                    "description": entry.description,
                    "tags": entry.tags
                }
                for display_id, entry in self._contexts.items()
            }
        }

    def _deserialize_state(self, state: Dict):
        """Deserialize state dict into registry."""
        self._counters = state.get("counters", {})

        for display_id, data in state.get("contexts", {}).items():
            # Parse context type
            try:
                ctx_type = ContextType(data["context_type"])
            except ValueError:
                ctx_type = ContextType.SIDEBAR  # Fallback

            entry = ContextEntry(
                display_id=data["display_id"],
                uuid=data["uuid"],
                context_type=ctx_type,
                parent_id=data.get("parent_id"),
                children_ids=data.get("children_ids", []),
                created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
                created_by=data.get("created_by", ""),
                created_in=data.get("created_in"),
                description=data.get("description"),
                tags=data.get("tags", [])
            )

            self._contexts[display_id] = entry
            self._uuid_to_display[entry.uuid] = display_id

    def _save_state(self):
        """Save registry state via backend."""
        if not self._backend.is_available():
            logger.warning(f"Storage backend {self._backend.get_name()} not available")
            return

        state = self._serialize_state()
        if not self._backend.save(state):
            logger.warning(f"Failed to save to {self._backend.get_name()}")

    def _load_state(self):
        """Load registry state via backend."""
        if not self._backend.is_available():
            logger.debug(f"Storage backend {self._backend.get_name()} not available, starting fresh")
            return

        state = self._backend.load()
        if state is not None:
            self._deserialize_state(state)
            logger.debug(f"Loaded {len(self._contexts)} contexts from {self._backend.get_name()}")

    def get_backend_info(self) -> Dict:
        """Get info about current storage backend."""
        return {
            "backend": self._backend.get_name(),
            "available": self._backend.is_available(),
            "persistence_path": getattr(self._backend, 'file_path', None) or
                               getattr(self._backend, 'db_path', None) or
                               getattr(self._backend, 'redis_url', None)
        }

    # =========================================================================
    # STATS
    # =========================================================================

    def stats(self) -> Dict:
        """Get registry statistics."""
        with self._lock:
            type_counts = {}
            for entry in self._contexts.values():
                type_name = entry.context_type.value if isinstance(entry.context_type, ContextType) else str(entry.context_type)
                type_counts[type_name] = type_counts.get(type_name, 0) + 1

            return {
                "total_contexts": len(self._contexts),
                "by_type": type_counts,
                "root_count": len(self.get_roots()),
                "counters": dict(self._counters)
            }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Global registry instance - import this to use
_registry_instance: Optional[ContextRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ContextRegistry:
    """
    Get the global context registry instance.

    Usage:
        from context_registry import get_registry

        registry = get_registry()
        sidebar_id = registry.register("SB", created_by="human")
    """
    global _registry_instance

    with _registry_lock:
        if _registry_instance is None:
            _registry_instance = ContextRegistry()
        return _registry_instance


def reset_registry():
    """Reset the global registry (for testing)."""
    global _registry_instance

    with _registry_lock:
        _registry_instance = None
