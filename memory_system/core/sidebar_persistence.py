#!/usr/bin/env python3
"""
sidebar_persistence.py - SQLite persistence layer for sidebar state

Handles saving/loading SidebarContext objects across API restarts.
Uses JSON blobs for complex fields, matching the episodic_memory pattern.

Created: 2026-01-06
Source: SIDEBAR_PERSISTENCE_IMPLEMENTATION.md
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from dataclasses import asdict

from datashapes import (
    SidebarContext,
    SidebarStatus,
    SidebarPriority,
    OzolithEventType,
)

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
            logger.warning("Ozolith not available - deletions will not be logged")
            return None
    return _ozolith_instance

logger = logging.getLogger(__name__)

# Schema version - increment when schema changes
SCHEMA_VERSION = 3


class SidebarPersistence:
    """
    SQLite persistence layer for sidebar state.

    Follows the pattern from episodic_memory/database.py:
    - Context manager for connections
    - WAL mode for performance
    - JSON blobs for complex fields
    - Migration support via PRAGMA user_version

    Usage:
        db = SidebarPersistence()

        # Save a context
        db.save_context(sidebar_context)

        # Load all contexts
        contexts = db.load_all_contexts()

        # Get/set session state
        db.set_session_state('active_context_id', 'SB-1')
        active = db.get_session_state('active_context_id')
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize persistence layer.

        Args:
            db_path: Path to SQLite file. Defaults to data/sidebar_state.db
        """
        if db_path is None:
            # Default location: same folder as episodic_memory.db
            base_dir = Path(__file__).parent / "data"
            db_path = base_dir / "sidebar_state.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema (with migrations if needed)
        self._init_schema()

        logger.info(f"Sidebar persistence initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            # Don't use PARSE_DECLTYPES - we handle all conversions manually
            # This avoids issues with timestamp format (ISO vs space-separated)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys and WAL mode for better performance
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('PRAGMA journal_mode = WAL')
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _init_schema(self):
        """Create database tables and run migrations."""
        with self._get_connection() as conn:
            # Check current schema version
            current_version = conn.execute("PRAGMA user_version").fetchone()[0]

            if current_version < SCHEMA_VERSION:
                logger.info(f"Migrating database from v{current_version} to v{SCHEMA_VERSION}")

                # Run migrations in order
                if current_version < 1:
                    self._migrate_v0_to_v1(conn)

                if current_version < 2:
                    self._migrate_v1_to_v2(conn)

                if current_version < 3:
                    self._migrate_v2_to_v3(conn)

                # Update version
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                conn.commit()
                logger.info(f"Migration complete: now at v{SCHEMA_VERSION}")

    def _migrate_v0_to_v1(self, conn):
        """Initial schema creation."""

        # Core context state table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sidebar_contexts (
                sidebar_id TEXT PRIMARY KEY,
                uuid TEXT UNIQUE NOT NULL,
                parent_context_id TEXT,
                forked_from TEXT,
                original_conversation_id TEXT,

                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                task_description TEXT,
                success_criteria TEXT,
                failure_reason TEXT,
                coordinator_agent TEXT,

                created_at TIMESTAMP NOT NULL,
                last_activity TIMESTAMP NOT NULL,

                -- JSON blobs for complex fields
                child_sidebar_ids_json TEXT,
                participants_json TEXT,
                inherited_memory_json TEXT,
                local_memory_json TEXT,
                data_refs_json TEXT,
                cross_sidebar_refs_json TEXT,
                relevance_scores_json TEXT,
                active_focus_json TEXT,
                yarn_board_layout_json TEXT,

                FOREIGN KEY (parent_context_id) REFERENCES sidebar_contexts(sidebar_id)
            )
        ''')

        # Indexes for common queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_contexts_status ON sidebar_contexts(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_contexts_parent ON sidebar_contexts(parent_context_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_contexts_last_activity ON sidebar_contexts(last_activity)')

        # Track conversation_id -> root mapping
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversation_roots (
                conversation_id TEXT PRIMARY KEY,
                root_context_id TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (root_context_id) REFERENCES sidebar_contexts(sidebar_id)
            )
        ''')

        # Session state (focus tracking, etc.)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS session_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        logger.info("Created v1 schema: sidebar_contexts, conversation_roots, session_state")

    def _migrate_v1_to_v2(self, conn):
        """Add yarn_board_layout_json column for yarn board persistence."""
        try:
            conn.execute('''
                ALTER TABLE sidebar_contexts
                ADD COLUMN yarn_board_layout_json TEXT
            ''')
            logger.info("v1->v2 migration: Added yarn_board_layout_json column")
        except sqlite3.OperationalError as e:
            # Column might already exist if table was created fresh with v2 schema
            if "duplicate column name" in str(e).lower():
                logger.debug("yarn_board_layout_json column already exists")
            else:
                raise

    def _migrate_v2_to_v3(self, conn):
        """Add display_names_json and tags_json columns for alias and tag persistence."""
        for col in ('display_names_json', 'tags_json'):
            try:
                conn.execute(f'''
                    ALTER TABLE sidebar_contexts
                    ADD COLUMN {col} TEXT
                ''')
                logger.info(f"v2->v3 migration: Added {col} column")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug(f"{col} column already exists")
                else:
                    raise

    # =========================================================================
    # CONTEXT OPERATIONS
    # =========================================================================

    def save_context(self, context: SidebarContext) -> bool:
        """
        Save or update a SidebarContext.

        Uses INSERT OR REPLACE for upsert behavior.

        Args:
            context: The SidebarContext to save

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO sidebar_contexts (
                        sidebar_id, uuid, parent_context_id, forked_from,
                        original_conversation_id,
                        status, priority, task_description, success_criteria,
                        failure_reason, coordinator_agent,
                        created_at, last_activity,
                        child_sidebar_ids_json, participants_json,
                        inherited_memory_json, local_memory_json,
                        data_refs_json, cross_sidebar_refs_json,
                        relevance_scores_json, active_focus_json,
                        yarn_board_layout_json,
                        display_names_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    context.sidebar_id,
                    context.uuid,
                    context.parent_context_id,
                    context.forked_from,
                    getattr(context, 'original_conversation_id', None),
                    context.status.value if isinstance(context.status, SidebarStatus) else context.status,
                    context.priority.value if isinstance(context.priority, SidebarPriority) else context.priority,
                    context.task_description,
                    context.success_criteria,
                    context.failure_reason,
                    context.coordinator_agent,
                    context.created_at.isoformat() if isinstance(context.created_at, datetime) else context.created_at,
                    context.last_activity.isoformat() if isinstance(context.last_activity, datetime) else context.last_activity,
                    json.dumps(context.child_sidebar_ids),
                    json.dumps(context.participants),
                    json.dumps(context.inherited_memory),
                    json.dumps(context.local_memory),
                    json.dumps(context.data_refs),
                    json.dumps(context.cross_sidebar_refs),
                    json.dumps(context.relevance_scores),
                    json.dumps(context.active_focus),
                    json.dumps(context.yarn_board_layout) if context.yarn_board_layout else None,
                    json.dumps(context.display_names) if context.display_names else None,
                    json.dumps(context.tags) if context.tags else None,
                ))

            logger.debug(f"Saved context {context.sidebar_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save context {context.sidebar_id}: {e}")
            raise

    def load_context(self, sidebar_id: str) -> Optional[SidebarContext]:
        """
        Load a single SidebarContext by ID.

        Args:
            sidebar_id: The context ID to load

        Returns:
            SidebarContext or None if not found
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    'SELECT * FROM sidebar_contexts WHERE sidebar_id = ?',
                    (sidebar_id,)
                ).fetchone()

                if row:
                    return self._row_to_context(row)
                return None

        except Exception as e:
            logger.error(f"Failed to load context {sidebar_id}: {e}")
            raise

    def load_all_contexts(self, include_archived: bool = False) -> List[SidebarContext]:
        """
        Load all contexts from database.

        Args:
            include_archived: Whether to include archived contexts

        Returns:
            List of SidebarContext objects
        """
        try:
            with self._get_connection() as conn:
                if include_archived:
                    rows = conn.execute(
                        'SELECT * FROM sidebar_contexts ORDER BY last_activity DESC'
                    ).fetchall()
                else:
                    rows = conn.execute(
                        'SELECT * FROM sidebar_contexts WHERE status != ? ORDER BY last_activity DESC',
                        (SidebarStatus.ARCHIVED.value,)
                    ).fetchall()

                contexts = [self._row_to_context(row) for row in rows]
                logger.info(f"Loaded {len(contexts)} contexts from persistence")
                return contexts

        except Exception as e:
            logger.error(f"Failed to load contexts: {e}")
            raise

    def delete_context(self, sidebar_id: str, reason: str = "manual", deleted_by: str = "system") -> bool:
        """
        Delete a context from SQLite cache, with full audit trail in OZOLITH.

        The context data is preserved in OZOLITH before deletion, so it can
        be recovered if needed. This is NOT a true deletion - it's removal
        from active state with full audit trail.

        Args:
            sidebar_id: Context to delete
            reason: Why deleting ("manual", "cleanup", "corrupt", "test")
            deleted_by: Who initiated the deletion

        Returns:
            True if deleted, False if not found
        """
        try:
            # First, load the full context so we can preserve it
            context = self.load_context(sidebar_id)
            if context is None:
                logger.warning(f"Context {sidebar_id} not found for deletion")
                return False

            # Log to OZOLITH FIRST - preserve full snapshot before deletion
            oz = _get_ozolith()
            if oz:
                # Serialize the full context for the audit trail
                context_snapshot = {
                    'sidebar_id': context.sidebar_id,
                    'uuid': context.uuid,
                    'parent_context_id': context.parent_context_id,
                    'forked_from': context.forked_from,
                    'status': context.status.value if isinstance(context.status, SidebarStatus) else context.status,
                    'priority': context.priority.value if isinstance(context.priority, SidebarPriority) else context.priority,
                    'task_description': context.task_description,
                    'success_criteria': context.success_criteria,
                    'failure_reason': context.failure_reason,
                    'coordinator_agent': context.coordinator_agent,
                    'created_at': context.created_at.isoformat() if isinstance(context.created_at, datetime) else context.created_at,
                    'last_activity': context.last_activity.isoformat() if isinstance(context.last_activity, datetime) else context.last_activity,
                    'child_sidebar_ids': context.child_sidebar_ids,
                    'participants': context.participants,
                    'inherited_memory': context.inherited_memory,
                    'local_memory': context.local_memory,
                    'data_refs': context.data_refs,
                    'cross_sidebar_refs': context.cross_sidebar_refs,
                    'relevance_scores': context.relevance_scores,
                    'active_focus': context.active_focus,
                }

                oz.append(
                    event_type=OzolithEventType.CONTEXT_DELETED,
                    context_id=sidebar_id,
                    actor=deleted_by,
                    payload={
                        'reason': reason,
                        'deleted_by': deleted_by,
                        'context_snapshot': context_snapshot,  # Full data preserved!
                        'had_children': len(context.child_sidebar_ids),
                        'had_exchanges': len(context.local_memory),
                    }
                )
                logger.info(f"Logged deletion of {sidebar_id} to OZOLITH")

            # NOW delete from SQLite
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'DELETE FROM sidebar_contexts WHERE sidebar_id = ?',
                    (sidebar_id,)
                )
                deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"Deleted context {sidebar_id} from SQLite (reason: {reason})")

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete context {sidebar_id}: {e}")
            raise

    def _migrate_cross_refs(self, raw_json: str, context_id: str) -> Dict[str, Any]:
        """
        Migrate cross_sidebar_refs from old List[str] format to new Dict[str, metadata] format.

        On first load after the data model change, this converts:
            ["SB-2", "SB-3"]
        To:
            {"SB-2": {...metadata...}, "SB-3": {...metadata...}}

        Tries to pull real metadata from OZOLITH CROSS_REF_ADDED events.
        Falls back to sensible defaults if OZOLITH not available.

        Args:
            raw_json: The JSON string from database
            context_id: The context ID (for OZOLITH lookup)

        Returns:
            Dict[str, Any] in new format
        """
        parsed = json.loads(raw_json or '{}')

        # Already a dict? No migration needed
        if isinstance(parsed, dict):
            return parsed

        # Empty list? Return empty dict
        if not parsed:
            return {}

        # It's a list - need to migrate!
        logger.info(f"Migrating cross_sidebar_refs for {context_id}: {len(parsed)} refs to convert")

        migrated = {}
        oz = _get_ozolith()

        for target_id in parsed:
            metadata = None

            # Try to get real metadata from OZOLITH
            if oz:
                try:
                    # Query for CROSS_REF_ADDED events from this context to this target
                    events = oz.query(
                        event_type=OzolithEventType.CROSS_REF_ADDED,
                        context_id=context_id
                    )
                    # Find the matching event (most recent one for this target)
                    for event in reversed(events):
                        if event.payload.get('target_context_id') == target_id:
                            payload = event.payload
                            metadata = {
                                "ref_type": payload.get("ref_type", "related_to"),
                                "strength": payload.get("strength", "normal"),
                                "confidence": payload.get("confidence", 0.0),
                                "discovery_method": payload.get("discovery_method", "explicit"),
                                "human_validated": payload.get("human_validated"),
                                "created_at": payload.get("created_at"),
                                "reason": payload.get("reason", ""),
                            }
                            logger.debug(f"Found OZOLITH metadata for {context_id}->{target_id}")
                            break
                except Exception as e:
                    logger.warning(f"OZOLITH lookup failed for {context_id}->{target_id}: {e}")

            # Fallback to defaults if no OZOLITH data
            if metadata is None:
                metadata = {
                    "ref_type": "related_to",
                    "strength": "normal",
                    "confidence": 0.0,
                    "discovery_method": "explicit",
                    "human_validated": None,
                    "created_at": None,
                    "reason": "migrated from legacy format",
                }
                logger.debug(f"Using default metadata for {context_id}->{target_id}")

            migrated[target_id] = metadata

        logger.info(f"Migration complete for {context_id}: {len(migrated)} refs migrated")
        return migrated

    def _row_to_context(self, row: sqlite3.Row) -> SidebarContext:
        """Convert database row to SidebarContext."""
        # Handle yarn_board_layout - may not exist in older DBs
        yarn_layout = None
        try:
            layout_json = row['yarn_board_layout_json']
            if layout_json:
                yarn_layout = json.loads(layout_json)
        except (KeyError, IndexError):
            pass

        # Handle display_names - added in v3
        display_names = {}
        try:
            names_json = row['display_names_json']
            if names_json:
                display_names = json.loads(names_json)
        except (KeyError, IndexError):
            pass

        # Handle tags - added in v3
        tags = []
        try:
            tags_json = row['tags_json']
            if tags_json:
                tags = json.loads(tags_json)
        except (KeyError, IndexError):
            pass

        return SidebarContext(
            sidebar_id=row['sidebar_id'],
            uuid=row['uuid'],
            parent_context_id=row['parent_context_id'],
            forked_from=row['forked_from'],

            status=SidebarStatus(row['status']),
            priority=SidebarPriority(row['priority']),
            task_description=row['task_description'],
            success_criteria=row['success_criteria'],
            failure_reason=row['failure_reason'],
            coordinator_agent=row['coordinator_agent'],

            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
            last_activity=datetime.fromisoformat(row['last_activity']) if row['last_activity'] else datetime.now(),

            child_sidebar_ids=json.loads(row['child_sidebar_ids_json'] or '[]'),
            participants=json.loads(row['participants_json'] or '[]'),
            inherited_memory=json.loads(row['inherited_memory_json'] or '[]'),
            local_memory=json.loads(row['local_memory_json'] or '[]'),
            data_refs=json.loads(row['data_refs_json'] or '{}'),
            cross_sidebar_refs=self._migrate_cross_refs(row['cross_sidebar_refs_json'], row['sidebar_id']),
            relevance_scores=json.loads(row['relevance_scores_json'] or '{}'),
            active_focus=json.loads(row['active_focus_json'] or '[]'),
            yarn_board_layout=yarn_layout,
            display_names=display_names,
            tags=tags,
        )

    # =========================================================================
    # SESSION STATE OPERATIONS
    # =========================================================================

    def get_session_state(self, key: str, default: Any = None) -> Any:
        """
        Get a session state value.

        Args:
            key: State key (e.g., 'active_context_id')
            default: Default value if not found

        Returns:
            The stored value (JSON-decoded) or default
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    'SELECT value FROM session_state WHERE key = ?',
                    (key,)
                ).fetchone()

                if row and row['value']:
                    return json.loads(row['value'])
                return default

        except Exception as e:
            logger.error(f"Failed to get session state '{key}': {e}")
            return default

    def set_session_state(self, key: str, value: Any) -> bool:
        """
        Set a session state value.

        Args:
            key: State key
            value: Value to store (will be JSON-encoded)

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO session_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (key, json.dumps(value), datetime.now().isoformat()))

            logger.debug(f"Set session state '{key}'")
            return True

        except Exception as e:
            logger.error(f"Failed to set session state '{key}': {e}")
            raise

    # =========================================================================
    # CONVERSATION ROOT OPERATIONS
    # =========================================================================

    def register_conversation_root(self, conversation_id: str, root_context_id: str) -> bool:
        """
        Register a conversation_id -> root context mapping.

        Args:
            conversation_id: The conversation identifier
            root_context_id: The root context's sidebar_id

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO conversation_roots
                    (conversation_id, root_context_id, created_at, is_active)
                    VALUES (?, ?, ?, 1)
                ''', (conversation_id, root_context_id, datetime.now().isoformat()))

            logger.debug(f"Registered conversation root: {conversation_id} -> {root_context_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register conversation root: {e}")
            raise

    def get_conversation_root(self, conversation_id: str) -> Optional[str]:
        """
        Get the root context ID for a conversation.

        Args:
            conversation_id: The conversation identifier

        Returns:
            The root context's sidebar_id or None
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    'SELECT root_context_id FROM conversation_roots WHERE conversation_id = ? AND is_active = 1',
                    (conversation_id,)
                ).fetchone()

                return row['root_context_id'] if row else None

        except Exception as e:
            logger.error(f"Failed to get conversation root for {conversation_id}: {e}")
            return None

    def mark_conversation_historical(self, conversation_id: str) -> bool:
        """
        Mark a conversation as historical (when its root is reparented).

        Args:
            conversation_id: The conversation to mark

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    'UPDATE conversation_roots SET is_active = 0 WHERE conversation_id = ?',
                    (conversation_id,)
                )

            logger.debug(f"Marked conversation {conversation_id} as historical")
            return True

        except Exception as e:
            logger.error(f"Failed to mark conversation historical: {e}")
            raise

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with self._get_connection() as conn:
                total = conn.execute('SELECT COUNT(*) FROM sidebar_contexts').fetchone()[0]

                by_status = {}
                for row in conn.execute('''
                    SELECT status, COUNT(*) as count
                    FROM sidebar_contexts
                    GROUP BY status
                ''').fetchall():
                    by_status[row['status']] = row['count']

                roots = conn.execute(
                    'SELECT COUNT(*) FROM sidebar_contexts WHERE parent_context_id IS NULL'
                ).fetchone()[0]

                conversations = conn.execute(
                    'SELECT COUNT(*) FROM conversation_roots WHERE is_active = 1'
                ).fetchone()[0]

                # Oldest active context (staleness check)
                oldest_active = conn.execute('''
                    SELECT sidebar_id, last_activity
                    FROM sidebar_contexts
                    WHERE status = 'active'
                    ORDER BY last_activity ASC
                    LIMIT 1
                ''').fetchone()

                # Largest context by local_memory size
                largest = conn.execute('''
                    SELECT sidebar_id, LENGTH(local_memory_json) as size
                    FROM sidebar_contexts
                    ORDER BY size DESC
                    LIMIT 1
                ''').fetchone()

                # Depth distribution (how nested are things)
                # Count contexts at each depth level
                depth_counts = {}
                all_contexts = conn.execute(
                    'SELECT sidebar_id, parent_context_id FROM sidebar_contexts'
                ).fetchall()

                # Build parent lookup
                parent_map = {row['sidebar_id']: row['parent_context_id'] for row in all_contexts}

                def get_depth(sid):
                    depth = 0
                    current = sid
                    while parent_map.get(current):
                        depth += 1
                        current = parent_map[current]
                    return depth

                for sid in parent_map.keys():
                    d = get_depth(sid)
                    depth_counts[d] = depth_counts.get(d, 0) + 1

                return {
                    'total_contexts': total,
                    'by_status': by_status,
                    'root_contexts': roots,
                    'active_conversations': conversations,
                    'schema_version': SCHEMA_VERSION,
                    'oldest_active': {
                        'sidebar_id': oldest_active['sidebar_id'] if oldest_active else None,
                        'last_activity': oldest_active['last_activity'] if oldest_active else None,
                    },
                    'largest_context': {
                        'sidebar_id': largest['sidebar_id'] if largest else None,
                        'memory_size_bytes': largest['size'] if largest else 0,
                    },
                    'contexts_by_depth': depth_counts,
                }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}

    def context_exists(self, sidebar_id: str) -> bool:
        """
        Check if a context exists without loading it.

        Args:
            sidebar_id: The context ID to check

        Returns:
            True if exists, False otherwise
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    'SELECT 1 FROM sidebar_contexts WHERE sidebar_id = ? LIMIT 1',
                    (sidebar_id,)
                ).fetchone()
                return row is not None
        except Exception as e:
            logger.error(f"Failed to check context existence: {e}")
            return False


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_persistence_instance: Optional[SidebarPersistence] = None


def get_persistence(db_path: Optional[str] = None) -> SidebarPersistence:
    """
    Get the global persistence instance.

    Usage:
        from sidebar_persistence import get_persistence

        db = get_persistence()
        db.save_context(context)
    """
    global _persistence_instance

    if _persistence_instance is None:
        _persistence_instance = SidebarPersistence(db_path=db_path)

    return _persistence_instance


def reset_persistence():
    """Reset the global persistence instance (for testing)."""
    global _persistence_instance
    _persistence_instance = None


def quick_save(context: SidebarContext) -> bool:
    """
    One-liner to save a context without getting instance first.

    Usage:
        from sidebar_persistence import quick_save
        quick_save(my_context)
    """
    return get_persistence().save_context(context)


def quick_load(sidebar_id: str) -> Optional[SidebarContext]:
    """
    One-liner to load a context without getting instance first.

    Usage:
        from sidebar_persistence import quick_load
        context = quick_load('SB-1')
    """
    return get_persistence().load_context(sidebar_id)


def context_exists(sidebar_id: str) -> bool:
    """
    One-liner to check if a context exists.

    Usage:
        from sidebar_persistence import context_exists
        if context_exists('SB-1'):
            ...
    """
    return get_persistence().context_exists(sidebar_id)
