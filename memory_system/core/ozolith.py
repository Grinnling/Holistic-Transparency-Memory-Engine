#!/usr/bin/env python3
"""
ozolith.py - Immutable Append-Only Log with Hash Chain

Named after the Magic: The Gathering card that preserves things.
This is the column of truth - tamper-evident, verifiable, trustworthy.

Architecture:
    Core (machine-optimized):
        - Ozolith: Main class for append, verify, anchor operations
        - Hash chain: Each entry links to previous via SHA-256
        - Signed entries: HMAC signature for provenance

    Anchor Policy (Skinflap-aware):
        - AnchorPolicy: Decides when to create checkpoints
        - Hybrid triggers: count, time, events, skinflap score

    Render Layer (human-readable, on-demand):
        - OzolithRenderer: Translates for human consumption
        - Never modifies the log - read only

    Future (stubbed):
        - MerkleLayer: O(log N) proofs when scale demands it

Why this exists (from the AI's perspective):
    - Decision provenance: What context did I have when I said X?
    - Uncertainty tracking: When was I confident vs uncertain?
    - Error forensics: When wrong, was it bad input, missing context, or bad reasoning?
    - Verifiable history: I can walk the chain and confirm nothing's been altered.

Storage: JSON Lines format (.jsonl) - one entry per line, append-only.

Usage:
    from ozolith import Ozolith, AnchorPolicy, OzolithRenderer

    ozolith = Ozolith()
    ozolith.append(OzolithEventType.EXCHANGE, "SB-1", "assistant", {...})
    valid, bad_index = ozolith.verify_chain()
    renderer = OzolithRenderer(ozolith)
    print(renderer.render_stats())

Created: 2025-12-05
See: datashapes.py for OzolithEntry, OzolithAnchor, OzolithEventType definitions
"""

import hashlib
import hmac
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from datashapes import (
    OzolithEntry,
    OzolithAnchor,
    OzolithEventType,
    OzolithPayloadExchange,
    OzolithPayloadCorrection,
    OzolithPayloadSidebar,
)


# =============================================================================
# OZOLITH EXCEPTIONS
# =============================================================================

class OzolithWriteError(Exception):
    """Raised when writing to the log fails (disk full, permissions, etc.)."""
    pass


# =============================================================================
# OZOLITH CORE - The immutable log
# =============================================================================

class Ozolith:
    """
    Immutable append-only log with hash chain verification.

    Each entry includes:
        - Hash of previous entry (chain integrity)
        - HMAC signature (provenance)
        - SHA-256 of entire entry (self-verification)

    Storage is JSON Lines format - human readable, easy to verify externally.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        signing_key: Optional[str] = None,
        anchor_policy: Optional['AnchorPolicy'] = None
    ):
        """
        Initialize OZOLITH.

        Args:
            storage_path: Where to store the log. Defaults to ~/.local/share/memory_system/ozolith.jsonl
            signing_key: HMAC key for signing entries. Defaults to machine-specific key.
            anchor_policy: When to create anchors. Defaults to hybrid policy.
        """
        # Storage setup
        if storage_path is None:
            base_dir = Path.home() / ".local" / "share" / "memory_system"
            base_dir.mkdir(parents=True, exist_ok=True)
            storage_path = str(base_dir / "ozolith.jsonl")

        self.storage_path = storage_path
        self.anchors_path = storage_path.replace(".jsonl", "_anchors.json")

        # Signing key - use provided or generate machine-specific
        if signing_key is None:
            signing_key = self._get_or_create_signing_key()
        self._signing_key = signing_key.encode() if isinstance(signing_key, str) else signing_key

        # Anchor policy
        self.anchor_policy = anchor_policy or AnchorPolicy()

        # In-memory state (loaded from disk)
        self._entries: List[OzolithEntry] = []
        self._anchors: List[OzolithAnchor] = []
        self._sequence = 0
        self._anchor_sequence = 0

        # Load existing data
        self._load()

    def _get_or_create_signing_key(self) -> str:
        """Get or create a machine-specific signing key."""
        key_path = Path(self.storage_path).parent / ".ozolith_key"

        if key_path.exists():
            return key_path.read_text().strip()

        # Generate new key
        import secrets
        key = secrets.token_hex(32)

        # Save with restrictive permissions
        key_path.write_text(key)
        os.chmod(key_path, 0o600)

        return key

    def _load(self):
        """
        Load existing log from disk with graceful error recovery.

        Recovery behavior:
        - Truncated/corrupted lines: Skip and log warning, load valid entries
        - Corrupted anchor file: Log warning, continue with empty anchors
        - Empty file: Initialize cleanly

        The load_warnings list captures any issues encountered.
        """
        self.load_warnings: List[str] = []

        # Load entries
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                line_number = 0
                for line in f:
                    line_number += 1
                    line = line.strip()
                    if not line:
                        continue  # Skip blank lines

                    try:
                        data = json.loads(line)
                        # Convert event_type string back to enum
                        data['event_type'] = OzolithEventType(data['event_type'])
                        entry = OzolithEntry(**data)
                        self._entries.append(entry)
                    except json.JSONDecodeError as e:
                        warning = f"Line {line_number}: Corrupted JSON, skipped ({e})"
                        self.load_warnings.append(warning)
                    except (KeyError, ValueError, TypeError) as e:
                        warning = f"Line {line_number}: Invalid entry data, skipped ({e})"
                        self.load_warnings.append(warning)

            if self._entries:
                self._sequence = self._entries[-1].sequence

        # Load anchors (with graceful fallback)
        if os.path.exists(self.anchors_path):
            try:
                with open(self.anchors_path, 'r') as f:
                    anchors_data = json.load(f)
                    for data in anchors_data:
                        # Convert tuple back from list
                        data['sequence_range'] = tuple(data['sequence_range'])
                        anchor = OzolithAnchor(**data)
                        self._anchors.append(anchor)

                if self._anchors:
                    # Extract sequence number from anchor_id (ANCHOR-X)
                    last_id = self._anchors[-1].anchor_id
                    self._anchor_sequence = int(last_id.split('-')[1])
            except json.JSONDecodeError as e:
                warning = f"Anchors file corrupted, starting with empty anchors ({e})"
                self.load_warnings.append(warning)
            except (KeyError, ValueError, TypeError) as e:
                warning = f"Anchors file has invalid data, starting with empty anchors ({e})"
                self.load_warnings.append(warning)

    def _save_entry(self, entry: OzolithEntry) -> bool:
        """
        Append single entry to log file.

        Returns:
            True if save succeeded, False if failed (disk full, permissions, etc.)

        Raises:
            OzolithWriteError: If write fails and caller needs to handle it
        """
        entry_dict = asdict(entry)
        # Convert enum to string for JSON
        entry_dict['event_type'] = entry.event_type.value

        try:
            with open(self.storage_path, 'a') as f:
                f.write(json.dumps(entry_dict) + '\n')
                f.flush()  # Ensure it's written to OS buffer
                os.fsync(f.fileno())  # Force to disk
            return True
        except OSError as e:
            # Disk full, permission denied, etc.
            raise OzolithWriteError(f"Failed to write entry: {e}") from e

    def _save_anchors(self):
        """Save all anchors to file."""
        anchors_data = []
        for anchor in self._anchors:
            data = asdict(anchor)
            # Convert tuple to list for JSON
            data['sequence_range'] = list(data['sequence_range'])
            anchors_data.append(data)

        # Atomic write
        temp_path = self.anchors_path + ".tmp"
        with open(temp_path, 'w') as f:
            json.dump(anchors_data, f, indent=2)
        os.replace(temp_path, self.anchors_path)

    def _compute_hash(self, data: Dict) -> str:
        """Compute SHA-256 hash of data."""
        # Canonical JSON encoding for consistent hashing
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _compute_signature(self, data: Dict) -> str:
        """Compute HMAC signature of data."""
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hmac.new(self._signing_key, canonical.encode(), hashlib.sha256).hexdigest()

    def _build_entry_for_hashing(self, entry: OzolithEntry) -> Dict:
        """Build dict for hashing (excludes entry_hash itself)."""
        return {
            'sequence': entry.sequence,
            'timestamp': entry.timestamp,
            'previous_hash': entry.previous_hash,
            'event_type': entry.event_type.value,
            'context_id': entry.context_id,
            'actor': entry.actor,
            'payload': entry.payload,
            'signature': entry.signature
        }

    # =========================================================================
    # PUBLIC API - Append and Query
    # =========================================================================

    def append(
        self,
        event_type: OzolithEventType,
        context_id: str,
        actor: str,
        payload: Dict,
        skinflap_score: Optional[float] = None
    ) -> OzolithEntry:
        """
        Append a new entry to the log.

        This is the ONLY way to add data. No updates, no deletes.

        Args:
            event_type: Type of event (EXCHANGE, SIDEBAR_SPAWN, etc.)
            context_id: Which context this relates to (SB-X)
            actor: Who created this ("human", "assistant", "system")
            payload: Event-specific data
            skinflap_score: Optional skinflap score for anchor policy

        Returns:
            The created OzolithEntry

        Raises:
            OzolithWriteError: If the entry cannot be persisted to disk.
                In this case, the in-memory state is NOT modified.
        """
        # Calculate next sequence (but don't commit yet)
        next_sequence = self._sequence + 1

        # Get previous hash (empty for first entry)
        previous_hash = ""
        if self._entries:
            previous_hash = self._entries[-1].entry_hash

        # Build entry without hash/signature first
        entry = OzolithEntry(
            sequence=next_sequence,
            timestamp=datetime.utcnow().isoformat() + "Z",
            previous_hash=previous_hash,
            event_type=event_type,
            context_id=context_id,
            actor=actor,
            payload=payload
        )

        # Compute signature (signs the content)
        content_for_signing = {
            'sequence': entry.sequence,
            'timestamp': entry.timestamp,
            'previous_hash': entry.previous_hash,
            'event_type': entry.event_type.value,
            'context_id': entry.context_id,
            'actor': entry.actor,
            'payload': entry.payload
        }
        entry.signature = self._compute_signature(content_for_signing)

        # Compute entry hash (includes signature)
        entry.entry_hash = self._compute_hash(self._build_entry_for_hashing(entry))

        # CRITICAL: Save to disk FIRST, before updating in-memory state.
        # If save fails, we raise OzolithWriteError and memory stays unchanged.
        # This prevents desync between disk and memory.
        self._save_entry(entry)

        # Only after successful save do we update in-memory state
        self._sequence = next_sequence
        self._entries.append(entry)

        # Check anchor policy
        # Note: ANCHOR_CREATED events skip this check to prevent recursion -
        # create_anchor() calls append(ANCHOR_CREATED), which would trigger
        # another anchor if we didn't exclude it. Circular logic makes no sense.
        if event_type != OzolithEventType.ANCHOR_CREATED and \
           self.anchor_policy.should_anchor(entry, skinflap_score):
            self.create_anchor(trigger_reason=self.anchor_policy.get_trigger_reason(entry, skinflap_score))
            self.anchor_policy.record_anchor()

        return entry

    def get_entries(
        self,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None
    ) -> List[OzolithEntry]:
        """Get entries in sequence range (inclusive)."""
        entries = self._entries

        if start_seq is not None:
            entries = [e for e in entries if e.sequence >= start_seq]
        if end_seq is not None:
            entries = [e for e in entries if e.sequence <= end_seq]

        return entries

    def get_by_context(self, context_id: str) -> List[OzolithEntry]:
        """Get all entries for a specific context."""
        return [e for e in self._entries if e.context_id == context_id]

    def get_by_type(self, event_type: OzolithEventType) -> List[OzolithEntry]:
        """Get all entries of a specific type."""
        return [e for e in self._entries if e.event_type == event_type]

    def get_around(self, sequence: int, window: int = 5) -> List[OzolithEntry]:
        """Get entries around a specific sequence (for error forensics)."""
        start = max(1, sequence - window)
        end = sequence + window
        return self.get_entries(start, end)

    def get_by_timerange(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[OzolithEntry]:
        """
        Get entries within a time range.

        Args:
            start: Start of range (inclusive). None = from beginning.
            end: End of range (inclusive). None = to present.

        Example:
            # What happened yesterday?
            yesterday = datetime.now() - timedelta(days=1)
            entries = oz.get_by_timerange(start=yesterday)
        """
        entries = self._entries

        if start is not None:
            start_iso = start.isoformat()
            entries = [e for e in entries if e.timestamp >= start_iso]

        if end is not None:
            end_iso = end.isoformat()
            entries = [e for e in entries if e.timestamp <= end_iso]

        return entries

    def get_by_payload(
        self,
        key: str,
        value: Any = None,
        comparator: str = "eq"
    ) -> List[OzolithEntry]:
        """
        Get entries where payload matches criteria.

        Args:
            key: Payload key to check (e.g., "confidence")
            value: Value to compare against (None = just check key exists)
            comparator: "eq", "ne", "lt", "le", "gt", "ge", "contains"

        Example:
            # Find low confidence exchanges
            low_conf = oz.get_by_payload("confidence", 0.5, "lt")
        """
        results = []

        for entry in self._entries:
            if key not in entry.payload:
                continue

            if value is None:
                # Just checking key exists
                results.append(entry)
                continue

            payload_val = entry.payload[key]

            if comparator == "eq" and payload_val == value:
                results.append(entry)
            elif comparator == "ne" and payload_val != value:
                results.append(entry)
            elif comparator == "lt" and payload_val < value:
                results.append(entry)
            elif comparator == "le" and payload_val <= value:
                results.append(entry)
            elif comparator == "gt" and payload_val > value:
                results.append(entry)
            elif comparator == "ge" and payload_val >= value:
                results.append(entry)
            elif comparator == "contains" and value in payload_val:
                results.append(entry)

        return results

    def get_corrections_for(self, sequence: int) -> List[OzolithEntry]:
        """
        Get all corrections that reference a specific entry.

        Useful for understanding: "What was wrong with exchange #23?"
        """
        corrections = self.get_by_type(OzolithEventType.CORRECTION)
        return [
            c for c in corrections
            if c.payload.get('original_exchange_seq') == sequence
        ]

    def get_entry_by_seq(self, sequence: int) -> Optional[OzolithEntry]:
        """
        Get a single entry by its sequence number.

        Returns None if not found.
        """
        for entry in self._entries:
            if entry.sequence == sequence:
                return entry
        return None

    def get_uncertain_exchanges(self, threshold: float = 0.6) -> List[OzolithEntry]:
        """
        Get exchanges where confidence was below threshold.

        Useful for self-improvement: "When am I typically uncertain?"
        """
        exchanges = self.get_by_type(OzolithEventType.EXCHANGE)
        return [
            e for e in exchanges
            if e.payload.get('confidence', 1.0) < threshold
        ]

    def query(self) -> 'OzolithQuery':
        """
        Start a chainable query.

        Example:
            results = oz.query()
                .by_type(OzolithEventType.EXCHANGE)
                .by_context("SB-5")
                .where_payload("confidence", "<", 0.6)
                .execute()
        """
        return OzolithQuery(self)

    def get_root_hash(self) -> str:
        """Get the current chain tip hash."""
        if not self._entries:
            return ""
        return self._entries[-1].entry_hash

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        """
        Walk the entire chain and verify integrity.

        Returns:
            (True, None) if valid
            (False, sequence) if invalid - sequence is first broken entry
        """
        if not self._entries:
            return True, None

        previous_hash = ""

        for entry in self._entries:
            # Check chain link
            if entry.previous_hash != previous_hash:
                return False, entry.sequence

            # Verify entry hash
            expected_hash = self._compute_hash(self._build_entry_for_hashing(entry))
            if entry.entry_hash != expected_hash:
                return False, entry.sequence

            # Verify signature
            content_for_signing = {
                'sequence': entry.sequence,
                'timestamp': entry.timestamp,
                'previous_hash': entry.previous_hash,
                'event_type': entry.event_type.value,
                'context_id': entry.context_id,
                'actor': entry.actor,
                'payload': entry.payload
            }
            expected_sig = self._compute_signature(content_for_signing)
            if entry.signature != expected_sig:
                return False, entry.sequence

            previous_hash = entry.entry_hash

        return True, None

    def verify_entry(self, sequence: int) -> bool:
        """Verify a single entry (checks hash and signature only, not chain)."""
        entry = next((e for e in self._entries if e.sequence == sequence), None)
        if not entry:
            return False

        # Verify hash
        expected_hash = self._compute_hash(self._build_entry_for_hashing(entry))
        if entry.entry_hash != expected_hash:
            return False

        # Verify signature
        content_for_signing = {
            'sequence': entry.sequence,
            'timestamp': entry.timestamp,
            'previous_hash': entry.previous_hash,
            'event_type': entry.event_type.value,
            'context_id': entry.context_id,
            'actor': entry.actor,
            'payload': entry.payload
        }
        expected_sig = self._compute_signature(content_for_signing)
        return entry.signature == expected_sig

    # =========================================================================
    # ANCHORING
    # =========================================================================

    def create_anchor(self, trigger_reason: str = "manual") -> OzolithAnchor:
        """
        Create an anchor (checkpoint) of current state.

        Export this and store somewhere you control for external verification.
        """
        self._anchor_sequence += 1

        first_seq = 1 if self._entries else 0
        last_seq = self._entries[-1].sequence if self._entries else 0

        anchor = OzolithAnchor(
            anchor_id=f"ANCHOR-{self._anchor_sequence}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            sequence_range=(first_seq, last_seq),
            root_hash=self.get_root_hash(),
            entry_count=len(self._entries),
            trigger_reason=trigger_reason
        )

        # Sign the anchor
        anchor_content = {
            'anchor_id': anchor.anchor_id,
            'timestamp': anchor.timestamp,
            'sequence_range': list(anchor.sequence_range),
            'root_hash': anchor.root_hash,
            'entry_count': anchor.entry_count,
            'trigger_reason': anchor.trigger_reason
        }
        anchor.signature = self._compute_signature(anchor_content)

        self._anchors.append(anchor)
        self._save_anchors()

        # Also log the anchor creation as an event
        self.append(
            event_type=OzolithEventType.ANCHOR_CREATED,
            context_id="SYSTEM",
            actor="system",
            payload={
                'anchor_id': anchor.anchor_id,
                'root_hash': anchor.root_hash,
                'entry_count': anchor.entry_count
            }
        )

        return anchor

    def verify_against_anchor(self, anchor: OzolithAnchor) -> bool:
        """
        Verify current log against a saved anchor.

        Returns True if log state matches anchor (no tampering since anchor).
        """
        # Check we have at least as many entries
        if len(self._entries) < anchor.entry_count:
            return False

        # Get entries up to anchor point
        _, last_seq = anchor.sequence_range
        entries_at_anchor = [e for e in self._entries if e.sequence <= last_seq]

        if len(entries_at_anchor) != anchor.entry_count:
            return False

        # Check root hash matches
        if entries_at_anchor:
            actual_root = entries_at_anchor[-1].entry_hash
            return actual_root == anchor.root_hash

        return anchor.root_hash == ""

    def get_anchors(self) -> List[OzolithAnchor]:
        """Get all anchors."""
        return self._anchors.copy()

    def export_anchor(self, anchor_id: Optional[str] = None) -> Dict:
        """
        Export an anchor for external storage.

        Returns dict that can be JSON serialized and stored elsewhere.
        """
        if anchor_id:
            anchor = next((a for a in self._anchors if a.anchor_id == anchor_id), None)
        else:
            anchor = self._anchors[-1] if self._anchors else None

        if not anchor:
            return {}

        return {
            'anchor_id': anchor.anchor_id,
            'timestamp': anchor.timestamp,
            'sequence_range': list(anchor.sequence_range),
            'root_hash': anchor.root_hash,
            'entry_count': anchor.entry_count,
            'signature': anchor.signature,
            'trigger_reason': anchor.trigger_reason,
            'export_time': datetime.utcnow().isoformat() + "Z"
        }

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def stats(self) -> Dict:
        """Get OZOLITH statistics."""
        by_type = {}
        by_context = {}
        by_actor = {}

        # Enhanced stats tracking
        confidences = []
        uncertainty_flags = {}
        corrections_by_type = {}
        entries_by_hour = {h: 0 for h in range(24)}

        for entry in self._entries:
            # By type
            type_key = entry.event_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            # By context
            by_context[entry.context_id] = by_context.get(entry.context_id, 0) + 1

            # By actor
            by_actor[entry.actor] = by_actor.get(entry.actor, 0) + 1

            # Time patterns (by hour)
            try:
                hour = int(entry.timestamp[11:13])
                entries_by_hour[hour] += 1
            except (ValueError, IndexError):
                pass

            # Exchange-specific stats
            if entry.event_type == OzolithEventType.EXCHANGE:
                # Confidence tracking
                conf = entry.payload.get('confidence')
                if conf is not None:
                    confidences.append(conf)

                # Uncertainty flags
                flags = entry.payload.get('uncertainty_flags', [])
                for flag in flags:
                    uncertainty_flags[flag] = uncertainty_flags.get(flag, 0) + 1

            # Correction stats
            if entry.event_type == OzolithEventType.CORRECTION:
                corr_type = entry.payload.get('correction_type', 'unknown')
                corrections_by_type[corr_type] = corrections_by_type.get(corr_type, 0) + 1

        # Calculate confidence distribution
        confidence_distribution = {'low': 0, 'medium': 0, 'high': 0}
        for c in confidences:
            if c < 0.5:
                confidence_distribution['low'] += 1
            elif c < 0.8:
                confidence_distribution['medium'] += 1
            else:
                confidence_distribution['high'] += 1

        # Calculate correction rate
        total_exchanges = by_type.get('exchange', 0)
        total_corrections = by_type.get('correction', 0)
        correction_rate = total_corrections / total_exchanges if total_exchanges > 0 else 0.0

        # Most active contexts (top 5)
        most_active_contexts = sorted(
            by_context.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            'total_entries': len(self._entries),
            'total_anchors': len(self._anchors),
            'current_sequence': self._sequence,
            'root_hash': self.get_root_hash()[:16] + "..." if self.get_root_hash() else "",
            'by_type': by_type,
            'by_context': by_context,
            'by_actor': by_actor,
            'first_entry': self._entries[0].timestamp if self._entries else None,
            'last_entry': self._entries[-1].timestamp if self._entries else None,
            'last_anchor': self._anchors[-1].timestamp if self._anchors else None,
            # Enhanced stats
            'avg_confidence': sum(confidences) / len(confidences) if confidences else None,
            'confidence_distribution': confidence_distribution,
            'uncertainty_flag_counts': uncertainty_flags,
            'correction_rate': correction_rate,
            'corrections_by_type': corrections_by_type,
            'entries_by_hour': entries_by_hour,
            'most_active_contexts': most_active_contexts,
        }


# =============================================================================
# ANCHOR POLICY - When to create checkpoints
# =============================================================================

class AnchorPolicy:
    """
    Decides when to create anchors (checkpoints).

    Hybrid approach:
        - Count-based: Safety net, anchor every N entries
        - Time-based: At least daily
        - Event-based: On significant events (spawns, merges, errors, session end)
        - Skinflap-aware: More frequent during important work
        - Stale-return: Anchor on first exchange after long idle
    """

    def __init__(
        self,
        count_threshold: int = 100,
        time_threshold_hours: int = 24,
        skinflap_threshold: float = 0.85,
        stale_threshold_hours: float = 4.0,
        significant_events: Optional[List[OzolithEventType]] = None
    ):
        self.count_threshold = count_threshold
        self.time_threshold = timedelta(hours=time_threshold_hours)
        self.skinflap_threshold = skinflap_threshold
        self.stale_threshold = timedelta(hours=stale_threshold_hours)

        self.significant_events = significant_events or [
            OzolithEventType.SIDEBAR_SPAWN,    # Checkpoint at branch point
            OzolithEventType.SIDEBAR_MERGE,    # Checkpoint after merge
            OzolithEventType.SESSION_END,      # Checkpoint at session end
            OzolithEventType.CORRECTION,       # Checkpoint when corrected (learning signal)
            OzolithEventType.ERROR_LOGGED,     # Checkpoint after errors (forensics)
        ]

        # Tracking
        self.entries_since_anchor = 0
        self.last_anchor_time = datetime.now()
        self.last_entry_time = datetime.now()
        self._last_trigger_reason = ""

    def should_anchor(
        self,
        entry: OzolithEntry,
        skinflap_score: Optional[float] = None
    ) -> bool:
        """Determine if we should create an anchor now."""
        self.entries_since_anchor += 1
        now = datetime.now()

        # Check for stale return BEFORE updating last_entry_time
        # "First exchange after coming back from long idle"
        time_since_last = now - self.last_entry_time
        is_stale_return = (
            time_since_last > self.stale_threshold and
            entry.event_type == OzolithEventType.EXCHANGE
        )

        # Update last entry time
        self.last_entry_time = now

        # Count-based (safety net)
        if self.entries_since_anchor >= self.count_threshold:
            self._last_trigger_reason = "count_threshold"
            return True

        # Time-based (at least daily)
        if now - self.last_anchor_time > self.time_threshold:
            self._last_trigger_reason = "time_threshold"
            return True

        # Stale return (first exchange after long idle)
        if is_stale_return:
            hours_idle = time_since_last.total_seconds() / 3600
            self._last_trigger_reason = f"stale_return:{hours_idle:.1f}h"
            return True

        # Event-based (significant events)
        if entry.event_type in self.significant_events:
            self._last_trigger_reason = f"event:{entry.event_type.value}"
            return True

        # Skinflap-aware (important exchanges)
        if skinflap_score is not None and skinflap_score >= self.skinflap_threshold:
            self._last_trigger_reason = f"skinflap_high:{skinflap_score:.2f}"
            return True

        return False

    def get_trigger_reason(
        self,
        entry: OzolithEntry,
        skinflap_score: Optional[float] = None
    ) -> str:
        """Get the reason why an anchor would be triggered."""
        # Re-evaluate to get reason (or return cached)
        return self._last_trigger_reason or "manual"

    def record_anchor(self):
        """Reset counters after anchoring."""
        self.entries_since_anchor = 0
        self.last_anchor_time = datetime.now()
        self._last_trigger_reason = ""


# =============================================================================
# RENDERER - Human-readable views
# =============================================================================

class OzolithRenderer:
    """
    Human-readable views of OZOLITH data.

    This is a READ-ONLY render layer - never modifies the log.
    Call when you need to understand what's happening,
    stays out of the way during normal operation.
    """

    def __init__(self, ozolith: Ozolith):
        self.ozolith = ozolith

    def render_entry(self, entry: OzolithEntry, compact: bool = False) -> str:
        """Render single entry, human readable."""
        if compact:
            return (
                f"#{entry.sequence} | {entry.timestamp[:19]} | "
                f"{entry.event_type.value} | {entry.context_id} | {entry.actor}"
            )

        lines = [
            f"╭─ Entry #{entry.sequence} {'─' * 50}",
            f"│ Time:    {entry.timestamp}",
            f"│ Type:    {entry.event_type.value}",
            f"│ Context: {entry.context_id}",
            f"│ Actor:   {entry.actor}",
        ]

        # Render payload based on event type
        if entry.event_type == OzolithEventType.EXCHANGE:
            payload = entry.payload
            lines.append(f"│ ─── Exchange Details ───")
            lines.append(f"│ Confidence:  {payload.get('confidence', 'N/A')}")
            lines.append(f"│ Skinflap:    {payload.get('skinflap_score', 'N/A')}")
            if payload.get('uncertainty_flags'):
                lines.append(f"│ Uncertainty: {', '.join(payload['uncertainty_flags'])}")
            if payload.get('reasoning_type'):
                lines.append(f"│ Reasoning:   {payload['reasoning_type']}")
            lines.append(f"│ Tokens:      {payload.get('token_count', 'N/A')}")

        elif entry.event_type in (OzolithEventType.SIDEBAR_SPAWN, OzolithEventType.SIDEBAR_MERGE):
            payload = entry.payload
            lines.append(f"│ ─── Sidebar Event ───")
            if payload.get('parent_id'):
                lines.append(f"│ Parent:     {payload['parent_id']}")
            if payload.get('child_id'):
                lines.append(f"│ Child:      {payload['child_id']}")
            if payload.get('reason'):
                lines.append(f"│ Reason:     {payload['reason']}")
            if payload.get('inherited_count'):
                lines.append(f"│ Inherited:  {payload['inherited_count']} exchanges")
            if payload.get('exchange_count'):
                lines.append(f"│ Exchanges:  {payload['exchange_count']}")

        elif entry.event_type == OzolithEventType.CORRECTION:
            payload = entry.payload
            lines.append(f"│ ─── Correction ───")
            lines.append(f"│ Original:    Entry #{payload.get('original_exchange_seq', 'N/A')}")
            lines.append(f"│ Type:        {payload.get('correction_type', 'N/A')}")
            lines.append(f"│ Corrected by: {payload.get('corrected_by', 'N/A')}")
            if payload.get('correction_notes'):
                lines.append(f"│ Notes:       {payload['correction_notes'][:50]}...")

        else:
            # Generic payload display
            for key, value in entry.payload.items():
                display_val = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                lines.append(f"│ {key}: {display_val}")

        lines.append(f"│ ─── Integrity ───")
        lines.append(f"│ Hash:     {entry.entry_hash[:16]}...")
        lines.append(f"│ Previous: {entry.previous_hash[:16]}..." if entry.previous_hash else "│ Previous: (genesis)")
        lines.append(f"╰{'─' * 60}")

        return '\n'.join(lines)

    def render_chain(
        self,
        entries: Optional[List[OzolithEntry]] = None,
        compact: bool = True,
        limit: int = 20
    ) -> str:
        """Render multiple entries as a timeline."""
        if entries is None:
            entries = self.ozolith.get_entries()

        if not entries:
            return "No entries in log."

        # Limit for display
        total = len(entries)
        if len(entries) > limit:
            entries = entries[-limit:]
            header = f"Showing last {limit} of {total} entries:\n\n"
        else:
            header = f"All {total} entries:\n\n"

        lines = [header]
        for entry in entries:
            lines.append(self.render_entry(entry, compact=compact))

        return '\n'.join(lines)

    def render_context_history(self, context_id: str) -> str:
        """Everything that happened in one sidebar/context."""
        entries = self.ozolith.get_by_context(context_id)

        if not entries:
            return f"No entries for context {context_id}"

        lines = [f"History for {context_id} ({len(entries)} entries):\n"]
        for entry in entries:
            lines.append(self.render_entry(entry, compact=True))

        return '\n'.join(lines)

    def render_around_error(self, error_seq: int, window: int = 5) -> str:
        """Show N entries before/after an error for forensics."""
        entries = self.ozolith.get_around(error_seq, window)

        if not entries:
            return f"No entries around sequence {error_seq}"

        lines = [f"Entries around #{error_seq} (±{window}):\n"]
        for entry in entries:
            marker = " >>> " if entry.sequence == error_seq else "     "
            lines.append(marker + self.render_entry(entry, compact=True))

        return '\n'.join(lines)

    def render_anchor(self, anchor: OzolithAnchor) -> str:
        """Human readable anchor summary."""
        first, last = anchor.sequence_range
        return (
            f"╭─ Anchor: {anchor.anchor_id} {'─' * 40}\n"
            f"│ Created:  {anchor.timestamp}\n"
            f"│ Coverage: Entries #{first} - #{last}\n"
            f"│ Count:    {anchor.entry_count} entries\n"
            f"│ Root:     {anchor.root_hash[:24]}...\n"
            f"│ Trigger:  {anchor.trigger_reason}\n"
            f"│ Sig:      {anchor.signature[:16]}...\n"
            f"╰{'─' * 55}"
        )

    def render_verification_report(self, result: Tuple[bool, Optional[int]]) -> str:
        """Chain verification results in plain language."""
        valid, bad_index = result
        stats = self.ozolith.stats()

        if valid:
            lines = [
                "✓ Chain Verified Successfully",
                f"  Entries: {stats['total_entries']}",
                f"  Range:   #1 - #{stats['current_sequence']}",
                f"  Root:    {stats['root_hash']}",
            ]
            if stats['last_anchor']:
                lines.append(f"  Last anchor: {stats['last_anchor'][:19]}")
        else:
            lines = [
                f"✗ Chain Verification FAILED at entry #{bad_index}",
                "",
                "Possible causes:",
                "  - Log file was modified externally",
                "  - Signing key changed",
                "  - Data corruption",
                "",
                f"Use renderer.render_around_error({bad_index}) to investigate"
            ]

        return '\n'.join(lines)

    def render_stats(self) -> str:
        """Overall OZOLITH statistics."""
        stats = self.ozolith.stats()

        lines = [
            "╭─ OZOLITH Statistics ─────────────────────────────────",
            f"│ Total entries: {stats['total_entries']}",
            f"│ Total anchors: {stats['total_anchors']}",
            f"│ Current seq:   #{stats['current_sequence']}",
            f"│ Root hash:     {stats['root_hash']}",
            "│",
            "│ By Event Type:",
        ]

        for event_type, count in sorted(stats['by_type'].items()):
            lines.append(f"│   {event_type}: {count}")

        lines.append("│")
        lines.append("│ By Actor:")
        for actor, count in sorted(stats['by_actor'].items()):
            lines.append(f"│   {actor}: {count}")

        if stats['first_entry']:
            lines.append("│")
            lines.append(f"│ First entry: {stats['first_entry'][:19]}")
            lines.append(f"│ Last entry:  {stats['last_entry'][:19]}")

        lines.append(f"╰{'─' * 55}")

        return '\n'.join(lines)


# =============================================================================
# MERKLE LAYER - Future stub for O(log N) proofs
# =============================================================================

class MerkleLayer:
    """
    STUB: Merkle tree layer for O(log N) verification proofs.

    Currently not implemented - full chain verification is used instead.
    When needed, integrate pymerkle or merkly library here.

    Future interface:
        tree = MerkleLayer(entry_hashes)
        root = tree.root_hash
        proof = tree.get_proof(entry_index)
        valid = tree.verify_proof(entry_hash, proof, root)

    Libraries to consider:
        - pymerkle: RFC 9162 compliant, handles tens of millions of entries
          https://pypi.org/project/pymerkle/
        - merkly: Simpler API, compatible with MerkleTreeJS
          https://pypi.org/project/merkly/
        - merklelib: Also well-maintained
          https://pypi.org/project/merklelib/

    When to implement:
        - When log exceeds ~100k entries and verification becomes slow
        - When external auditors need efficient proofs
        - When partial verification is needed (prove single entry without full chain)

    pip install pymerkle  # When ready
    """

    def __init__(self, entry_hashes: List[str]):
        raise NotImplementedError(
            "Merkle tree layer not yet implemented. "
            "Use Ozolith.verify_chain() for full verification. "
            "See: https://pypi.org/project/pymerkle/"
        )

    @property
    def root_hash(self) -> str:
        """The root hash - represents entire tree."""
        raise NotImplementedError()

    def get_proof(self, index: int) -> List[tuple]:
        """Get O(log N) proof for entry at index."""
        raise NotImplementedError()

    @staticmethod
    def verify_proof(entry_hash: str, proof: List[tuple], root: str) -> bool:
        """Verify entry belongs to tree without walking full chain."""
        raise NotImplementedError()


# =============================================================================
# CHAINABLE QUERY BUILDER
# =============================================================================

class OzolithQuery:
    """
    Chainable query builder for flexible OZOLITH searches.

    Lets you combine multiple filters to find exactly what you need.

    Example:
        results = oz.query()
            .by_type(OzolithEventType.EXCHANGE)
            .by_context("SB-5")
            .where_payload("confidence", "<", 0.6)
            .where_payload("skinflap_score", ">", 0.8)
            .in_timerange(yesterday, today)
            .execute()

    This finds: "exchanges in SB-5 where I was uncertain but the query was good"
    """

    def __init__(self, ozolith: 'Ozolith'):
        self._ozolith = ozolith
        self._filters = []

    def by_type(self, event_type: OzolithEventType) -> 'OzolithQuery':
        """Filter by event type."""
        self._filters.append(lambda e: e.event_type == event_type)
        return self

    def by_types(self, event_types: List[OzolithEventType]) -> 'OzolithQuery':
        """Filter by multiple event types (OR)."""
        self._filters.append(lambda e: e.event_type in event_types)
        return self

    def by_context(self, context_id: str) -> 'OzolithQuery':
        """Filter by context ID."""
        self._filters.append(lambda e: e.context_id == context_id)
        return self

    def by_contexts(self, context_ids: List[str]) -> 'OzolithQuery':
        """Filter by multiple context IDs (OR)."""
        self._filters.append(lambda e: e.context_id in context_ids)
        return self

    def by_actor(self, actor: str) -> 'OzolithQuery':
        """Filter by actor."""
        self._filters.append(lambda e: e.actor == actor)
        return self

    def in_sequence_range(self, start: int, end: int) -> 'OzolithQuery':
        """Filter by sequence range (inclusive)."""
        self._filters.append(lambda e: start <= e.sequence <= end)
        return self

    def in_timerange(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> 'OzolithQuery':
        """Filter by time range."""
        def time_filter(e):
            if start and e.timestamp < start.isoformat():
                return False
            if end and e.timestamp > end.isoformat():
                return False
            return True
        self._filters.append(time_filter)
        return self

    def where_payload(
        self,
        key: str,
        comparator: str,
        value: Any
    ) -> 'OzolithQuery':
        """
        Filter by payload field.

        Comparators: "=", "==", "!=", "<", "<=", ">", ">=", "in", "contains"

        Example:
            .where_payload("confidence", "<", 0.5)
            .where_payload("uncertainty_flags", "contains", "ambiguous")
        """
        def payload_filter(e):
            if key not in e.payload:
                return False

            val = e.payload[key]

            if comparator in ("=", "=="):
                return val == value
            elif comparator == "!=":
                return val != value
            elif comparator == "<":
                return val < value
            elif comparator == "<=":
                return val <= value
            elif comparator == ">":
                return val > value
            elif comparator == ">=":
                return val >= value
            elif comparator == "in":
                return val in value
            elif comparator == "contains":
                return value in val
            return False

        self._filters.append(payload_filter)
        return self

    def has_payload_key(self, key: str) -> 'OzolithQuery':
        """Filter for entries that have a specific payload key."""
        self._filters.append(lambda e: key in e.payload)
        return self

    def has_uncertainty_flag(self, flag: str) -> 'OzolithQuery':
        """Filter for exchanges with a specific uncertainty flag."""
        self._filters.append(
            lambda e: flag in e.payload.get('uncertainty_flags', [])
        )
        return self

    def with_corrections(self) -> 'OzolithQuery':
        """Filter for entries that have been corrected."""
        corrected_seqs = {
            c.payload.get('original_exchange_seq')
            for c in self._ozolith.get_by_type(OzolithEventType.CORRECTION)
        }
        self._filters.append(lambda e: e.sequence in corrected_seqs)
        return self

    def execute(self) -> List[OzolithEntry]:
        """Execute the query and return matching entries."""
        results = self._ozolith._entries

        for filter_fn in self._filters:
            results = [e for e in results if filter_fn(e)]

        return results

    def count(self) -> int:
        """Execute and return count only."""
        return len(self.execute())

    def first(self) -> Optional[OzolithEntry]:
        """Execute and return first match (or None)."""
        results = self.execute()
        return results[0] if results else None

    def last(self) -> Optional[OzolithEntry]:
        """Execute and return last match (or None)."""
        results = self.execute()
        return results[-1] if results else None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_exchange_payload(
    query: str,
    response: str,
    confidence: float = 0.0,
    skinflap_score: float = 0.0,
    uncertainty_flags: Optional[List[str]] = None,
    reasoning_type: str = "",
    retrieved_memory_ids: Optional[List[str]] = None,
    context_depth: int = 0,
    token_count: int = 0,
    latency_ms: int = 0
) -> Dict:
    """
    Create a properly structured EXCHANGE payload.

    Hashes the query and response for privacy while preserving verification.
    """
    return {
        'query_hash': hashlib.sha256(query.encode()).hexdigest(),
        'response_hash': hashlib.sha256(response.encode()).hexdigest(),
        'confidence': confidence,
        'skinflap_score': skinflap_score,
        'uncertainty_flags': uncertainty_flags or [],
        'reasoning_type': reasoning_type,
        'retrieved_memory_ids': retrieved_memory_ids or [],
        'context_depth': context_depth,
        'token_count': token_count,
        'latency_ms': latency_ms
    }


def create_sidebar_payload(
    parent_id: str = "",
    child_id: str = "",
    reason: str = "",
    inherited_count: int = 0,
    exchange_count: int = 0,
    summary: str = ""
) -> Dict:
    """Create a properly structured SIDEBAR_SPAWN or SIDEBAR_MERGE payload."""
    return {
        'parent_id': parent_id,
        'child_id': child_id,
        'reason': reason,
        'inherited_count': inherited_count,
        'exchange_count': exchange_count,
        'summary_hash': hashlib.sha256(summary.encode()).hexdigest() if summary else ""
    }


def create_correction_payload(
    original_exchange_seq: int,
    correction_type: str,
    corrected_by: str = "human",
    correction_notes: str = ""
) -> Dict:
    """Create a properly structured CORRECTION payload."""
    return {
        'original_exchange_seq': original_exchange_seq,
        'correction_type': correction_type,
        'corrected_by': corrected_by,
        'correction_notes': correction_notes
    }


# =============================================================================
# NICE-TO-HAVE HELPER FUNCTIONS
# =============================================================================

def log_correction(
    oz: Ozolith,
    original_seq: int,
    what_was_wrong: str,
    correction_type: str = "factual",
    context_id: str = "SYSTEM"
) -> OzolithEntry:
    """
    Quick way to log when I was wrong.

    Args:
        oz: Ozolith instance
        original_seq: Sequence number of the entry that was wrong
        what_was_wrong: Description of what was incorrect
        correction_type: "factual", "approach", "misunderstanding"
        context_id: Which context this correction applies to

    Example:
        log_correction(oz, 47, "Gave wrong function name", "factual")
    """
    payload = create_correction_payload(
        original_exchange_seq=original_seq,
        correction_type=correction_type,
        corrected_by="human",
        correction_notes=what_was_wrong
    )
    return oz.append(
        event_type=OzolithEventType.CORRECTION,
        context_id=context_id,
        actor="human",
        payload=payload
    )


def log_uncertainty(
    oz: Ozolith,
    context_id: str,
    reason: str,
    details: Optional[Dict] = None
) -> OzolithEntry:
    """
    Explicitly log when I'm uncertain about something.

    Use when I want to flag "I'm not sure about this" for future reference.

    Args:
        oz: Ozolith instance
        context_id: Which context
        reason: Why I'm uncertain
        details: Additional context

    Example:
        log_uncertainty(oz, "SB-5", "Multiple valid approaches, unclear which fits best",
                       {"options": ["A", "B", "C"], "leaning_toward": "B"})
    """
    payload = {
        'reason': reason,
        'details': details or {},
        'flagged_at': datetime.utcnow().isoformat() + "Z"
    }
    return oz.append(
        event_type=OzolithEventType.EXCHANGE,  # Could add UNCERTAINTY event type later
        context_id=context_id,
        actor="assistant",
        payload={
            'query_hash': '',
            'response_hash': '',
            'confidence': 0.0,  # Explicitly low
            'uncertainty_flags': ['explicit_uncertainty', reason],
            'reasoning_type': 'flagged_uncertainty',
            **payload
        }
    )


def export_incident(
    oz: Ozolith,
    sequence: int,
    window: int = 10
) -> Dict:
    """
    Export everything around an incident for external analysis.

    Creates a self-contained bundle with entries, context, and verification.

    Args:
        oz: Ozolith instance
        sequence: The sequence number of the incident
        window: How many entries before/after to include

    Returns:
        Dict with incident bundle
    """
    entries = oz.get_around(sequence, window)

    # Get any corrections for entries in this window
    corrections = []
    for entry in entries:
        corrections.extend(oz.get_corrections_for(entry.sequence))

    # Build export bundle
    return {
        'incident_sequence': sequence,
        'window': window,
        'export_time': datetime.utcnow().isoformat() + "Z",
        'entries': [
            {
                'sequence': e.sequence,
                'timestamp': e.timestamp,
                'event_type': e.event_type.value,
                'context_id': e.context_id,
                'actor': e.actor,
                'payload': e.payload,
                'entry_hash': e.entry_hash
            }
            for e in entries
        ],
        'corrections': [
            {
                'sequence': c.sequence,
                'original_seq': c.payload.get('original_exchange_seq'),
                'correction_type': c.payload.get('correction_type'),
                'notes': c.payload.get('correction_notes')
            }
            for c in corrections
        ],
        'chain_verified': oz.verify_chain()[0],
        'root_hash_at_export': oz.get_root_hash()
    }


def session_summary(oz: Ozolith, session_start_seq: int) -> Dict:
    """
    Summarize a complete session's activity.

    Args:
        oz: Ozolith instance
        session_start_seq: Sequence number of SESSION_START entry

    Returns:
        Dict with session summary
    """
    # Get all entries from session start onward
    entries = oz.get_entries(start_seq=session_start_seq)

    # Find session end (if exists)
    session_end = None
    for entry in entries:
        if entry.event_type == OzolithEventType.SESSION_END:
            session_end = entry
            break

    # Filter to just this session
    if session_end:
        entries = [e for e in entries if e.sequence <= session_end.sequence]

    # Analyze
    exchanges = [e for e in entries if e.event_type == OzolithEventType.EXCHANGE]
    sidebars_spawned = [e for e in entries if e.event_type == OzolithEventType.SIDEBAR_SPAWN]
    sidebars_merged = [e for e in entries if e.event_type == OzolithEventType.SIDEBAR_MERGE]
    corrections = [e for e in entries if e.event_type == OzolithEventType.CORRECTION]
    errors = [e for e in entries if e.event_type == OzolithEventType.ERROR_LOGGED]

    # Confidence stats
    confidences = [e.payload.get('confidence', 0) for e in exchanges if 'confidence' in e.payload]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    # Contexts touched
    contexts = list(set(e.context_id for e in entries))

    return {
        'session_start_seq': session_start_seq,
        'session_end_seq': session_end.sequence if session_end else None,
        'duration': None,  # Would need to parse timestamps to calculate
        'total_entries': len(entries),
        'exchanges': len(exchanges),
        'sidebars_spawned': len(sidebars_spawned),
        'sidebars_merged': len(sidebars_merged),
        'corrections': len(corrections),
        'errors': len(errors),
        'contexts_touched': contexts,
        'avg_confidence': avg_confidence,
        'session_complete': session_end is not None
    }


def find_learning_opportunities(oz: Ozolith) -> List[Dict]:
    """
    Find entries that might be good learning opportunities.

    Looks for:
    - Low confidence exchanges
    - Exchanges with corrections
    - Exchanges with uncertainty flags
    - Errors followed by successful retries

    Returns list of opportunities with context.
    """
    opportunities = []

    # Low confidence exchanges
    low_conf = oz.get_uncertain_exchanges(threshold=0.5)
    for entry in low_conf:
        opportunities.append({
            'type': 'low_confidence',
            'sequence': entry.sequence,
            'confidence': entry.payload.get('confidence'),
            'context_id': entry.context_id,
            'reason': 'Confidence below 0.5 - what made this uncertain?'
        })

    # Corrected exchanges
    corrections = oz.get_by_type(OzolithEventType.CORRECTION)
    for corr in corrections:
        opportunities.append({
            'type': 'correction',
            'sequence': corr.payload.get('original_exchange_seq'),
            'correction_type': corr.payload.get('correction_type'),
            'context_id': corr.context_id,
            'reason': f"Corrected: {corr.payload.get('correction_notes', 'No notes')}"
        })

    # Exchanges with explicit uncertainty flags
    uncertain = oz.query().by_type(OzolithEventType.EXCHANGE).has_payload_key('uncertainty_flags').execute()
    for entry in uncertain:
        flags = entry.payload.get('uncertainty_flags', [])
        if flags:
            opportunities.append({
                'type': 'uncertainty_flagged',
                'sequence': entry.sequence,
                'flags': flags,
                'context_id': entry.context_id,
                'reason': f"Uncertainty flags: {', '.join(flags)}"
            })

    return opportunities


# =============================================================================
# CORRECTION VALIDATION SYSTEM
# =============================================================================

class CorrectionValidationResult:
    """Result of correction validation check."""

    def __init__(
        self,
        valid: bool,
        target_entry: Optional[OzolithEntry] = None,
        target_summary: str = "",
        warnings: List[str] = None,
        errors: List[str] = None
    ):
        self.valid = valid
        self.target_entry = target_entry
        self.target_summary = target_summary
        self.warnings = warnings or []
        self.errors = errors or []

    def __bool__(self):
        return self.valid

    def __repr__(self):
        status = "VALID" if self.valid else "INVALID"
        return f"CorrectionValidationResult({status}, warnings={len(self.warnings)}, errors={len(self.errors)})"


def validate_correction_target(
    oz: Ozolith,
    original_seq: int,
    what_was_wrong: str,
    correction_reasoning: str = ""
) -> CorrectionValidationResult:
    """
    Validate that a correction makes sense before writing it.

    Performs checks:
    1. Target entry exists
    2. Target is an appropriate type (EXCHANGE, not system events)
    3. Correction text has some relationship to target content
    4. Agent has provided reasoning

    Returns:
        CorrectionValidationResult with validation status and any warnings/errors
    """
    errors = []
    warnings = []

    # Check 1: Target exists
    target = oz.get_entry_by_seq(original_seq)
    if not target:
        errors.append(f"Entry {original_seq} does not exist")
        return CorrectionValidationResult(
            valid=False,
            errors=errors
        )

    # Get target summary
    target_content = target.payload.get('message',
                     target.payload.get('correction_notes',
                     str(target.payload)))
    target_summary = target_content[:200] if target_content else str(target.payload)[:200]

    # Check 2: Target is appropriate type
    if target.event_type in [OzolithEventType.SESSION_START,
                              OzolithEventType.SESSION_END,
                              OzolithEventType.ANCHOR_CREATED,
                              OzolithEventType.VERIFICATION_RUN]:
        warnings.append(f"Target is a system event ({target.event_type.value}), not typically corrected")

    # Check 3: Keyword relationship check
    target_lower = target_summary.lower()
    correction_lower = what_was_wrong.lower()

    # Extract significant words (simple tokenization)
    def extract_words(text):
        import re
        return set(re.findall(r'\b[a-z]{3,}\b', text.lower()))

    target_words = extract_words(target_summary)
    correction_words = extract_words(what_was_wrong)

    # Check for common technical terms that should match
    technical_terms = ['array', 'list', 'sort', 'sorted', 'function', 'method',
                       'class', 'object', 'string', 'int', 'float', 'dict',
                       'python', 'javascript', 'java', 'typescript', 'react',
                       'api', 'database', 'query', 'sql', 'http', 'json']

    target_tech = set(w for w in target_words if w in technical_terms)
    correction_tech = set(w for w in correction_words if w in technical_terms)

    # If correction mentions tech terms not in target, warn
    unmatched_tech = correction_tech - target_tech
    if unmatched_tech:
        warnings.append(f"Correction mentions terms not in target: {unmatched_tech}")

    # If there's almost no word overlap, warn
    overlap = target_words & correction_words
    if len(overlap) < 2 and len(correction_words) > 3:
        warnings.append(f"Low word overlap between target and correction (only {len(overlap)} common words)")

    # Check 4: Reasoning provided
    if not correction_reasoning or len(correction_reasoning.strip()) < 10:
        warnings.append("No reasoning provided or reasoning too short - explain WHY this was wrong")

    # Determine overall validity
    # Errors = invalid, Warnings only = valid but should review
    is_valid = len(errors) == 0

    return CorrectionValidationResult(
        valid=is_valid,
        target_entry=target,
        target_summary=target_summary,
        warnings=warnings,
        errors=errors
    )


def log_correction_validated(
    oz: Ozolith,
    original_seq: int,
    what_was_wrong: str,
    correction_reasoning: str,
    correction_type: str = "factual",
    context_id: str = "SYSTEM",
    corrected_by: str = "human",
    skip_validation: bool = False,
    force_despite_warnings: bool = False
) -> Tuple[Optional[OzolithEntry], CorrectionValidationResult]:
    """
    Log a correction with validation and self-review.

    This is the preferred way to log corrections. It:
    1. Validates the target entry exists
    2. Checks for obvious mismatches
    3. Requires reasoning
    4. Captures validation metadata in the correction

    Args:
        oz: Ozolith instance
        original_seq: Sequence number of entry to correct
        what_was_wrong: Description of what was incorrect
        correction_reasoning: WHY it was wrong (required)
        correction_type: "factual", "approach", "misunderstanding"
        context_id: Which context
        corrected_by: Who is making the correction
        skip_validation: Skip validation checks (not recommended)
        force_despite_warnings: Write even if warnings exist

    Returns:
        Tuple of (entry or None, validation_result)
    """
    # Run validation unless skipped
    if not skip_validation:
        validation = validate_correction_target(oz, original_seq, what_was_wrong, correction_reasoning)

        # Hard stop on errors
        if not validation.valid:
            return None, validation

        # Soft stop on warnings unless forced
        if validation.warnings and not force_despite_warnings:
            return None, validation
    else:
        # Create a passing validation result
        target = oz.get_entry_by_seq(original_seq)
        validation = CorrectionValidationResult(
            valid=True,
            target_entry=target,
            target_summary=str(target.payload)[:200] if target else "",
            warnings=["Validation skipped"]
        )

    # Build enhanced payload with validation metadata
    payload = {
        'original_exchange_seq': original_seq,
        'correction_type': correction_type,
        'corrected_by': corrected_by,
        'correction_notes': what_was_wrong,
        # New validation fields
        'correction_reasoning': correction_reasoning,
        'target_summary': validation.target_summary,
        'validation_warnings': validation.warnings,
        'validation_status': 'validated',  # pending → validated → human_confirmed
        'agent_validated': True,
        'agent_validated_at': datetime.utcnow().isoformat() + "Z",
        'human_validated': None,  # To be filled by human review
        'human_validated_by': None,
        'human_validated_at': None,
        'reviewed_by': None,  # Optional neutral agent review
        'review_notes': None,
    }

    entry = oz.append(
        event_type=OzolithEventType.CORRECTION,
        context_id=context_id,
        actor=corrected_by,
        payload=payload
    )

    return entry, validation


def confirm_correction(
    oz: Ozolith,
    correction_seq: int,
    confirmed_by: str = "human",
    notes: str = ""
) -> bool:
    """
    Human confirms a correction is accurate.

    Note: This creates a NEW entry that references the correction,
    since we can't modify the original correction entry.

    Args:
        oz: Ozolith instance
        correction_seq: Sequence of the CORRECTION entry to confirm
        confirmed_by: Who is confirming
        notes: Optional confirmation notes

    Returns:
        True if confirmation logged, False if correction not found
    """
    correction = oz.get_entry_by_seq(correction_seq)
    if not correction or correction.event_type != OzolithEventType.CORRECTION:
        return False

    # Log confirmation as a linked entry
    oz.append(
        event_type=OzolithEventType.CORRECTION,  # Or could add CORRECTION_CONFIRMED type
        context_id=correction.context_id,
        actor=confirmed_by,
        payload={
            'original_exchange_seq': correction.payload.get('original_exchange_seq'),
            'correction_type': 'confirmation',
            'corrected_by': confirmed_by,
            'correction_notes': notes or f"Confirmed correction #{correction_seq}",
            'confirms_correction_seq': correction_seq,
            'validation_status': 'human_confirmed',
            'human_validated': True,
            'human_validated_by': confirmed_by,
            'human_validated_at': datetime.utcnow().isoformat() + "Z",
        }
    )
    return True


def audit_corrections(oz: Ozolith) -> Dict[str, List[Dict]]:
    """
    Audit all corrections for issues.

    Finds:
    - Orphan corrections (target doesn't exist)
    - Unvalidated corrections (no validation metadata)
    - Unconfirmed corrections (agent validated but not human confirmed)
    - Correction chains (corrections of corrections)
    - Potential mismatches (warnings were ignored)

    Returns:
        Dict with categorized issues
    """
    issues = {
        'orphan': [],           # Target doesn't exist
        'unvalidated': [],      # No validation metadata
        'needs_human_review': [], # Agent validated, human hasn't confirmed
        'correction_chains': [], # Corrections pointing to other corrections
        'had_warnings': [],     # Corrections that had validation warnings
    }

    corrections = oz.get_by_type(OzolithEventType.CORRECTION)

    for corr in corrections:
        seq = corr.sequence
        target_seq = corr.payload.get('original_exchange_seq')

        # Skip confirmation entries
        if corr.payload.get('correction_type') == 'confirmation':
            continue

        # Check for orphan
        if target_seq:
            target = oz.get_entry_by_seq(target_seq)
            if not target:
                issues['orphan'].append({
                    'correction_seq': seq,
                    'target_seq': target_seq,
                    'notes': corr.payload.get('correction_notes', '')[:50]
                })
            elif target.event_type == OzolithEventType.CORRECTION:
                # Correction of correction
                issues['correction_chains'].append({
                    'correction_seq': seq,
                    'corrects_correction_seq': target_seq,
                    'notes': corr.payload.get('correction_notes', '')[:50]
                })

        # Check validation status
        validation_status = corr.payload.get('validation_status')
        if not validation_status or validation_status == 'pending':
            issues['unvalidated'].append({
                'correction_seq': seq,
                'target_seq': target_seq,
                'notes': corr.payload.get('correction_notes', '')[:50]
            })
        elif validation_status == 'validated' and not corr.payload.get('human_validated'):
            issues['needs_human_review'].append({
                'correction_seq': seq,
                'target_seq': target_seq,
                'notes': corr.payload.get('correction_notes', '')[:50],
                'reasoning': corr.payload.get('correction_reasoning', '')[:50]
            })

        # Check for warnings that were ignored
        warnings = corr.payload.get('validation_warnings', [])
        if warnings:
            issues['had_warnings'].append({
                'correction_seq': seq,
                'target_seq': target_seq,
                'warnings': warnings
            })

    return issues


def correction_analytics(oz: Ozolith) -> Dict:
    """
    Get detailed analytics about corrections.

    Returns:
    - Correction rate over time
    - Correction types breakdown
    - Validation statistics
    - Failed validation count (if tracked)
    """
    corrections = oz.get_by_type(OzolithEventType.CORRECTION)
    exchanges = oz.get_by_type(OzolithEventType.EXCHANGE)

    # Filter out confirmation entries
    actual_corrections = [c for c in corrections
                          if c.payload.get('correction_type') != 'confirmation']
    confirmations = [c for c in corrections
                     if c.payload.get('correction_type') == 'confirmation']

    # Types breakdown
    types_breakdown = {}
    for corr in actual_corrections:
        ctype = corr.payload.get('correction_type', 'unknown')
        types_breakdown[ctype] = types_breakdown.get(ctype, 0) + 1

    # Validation statistics
    validated = [c for c in actual_corrections if c.payload.get('agent_validated')]
    had_warnings = [c for c in actual_corrections if c.payload.get('validation_warnings')]

    # Count human confirmations by looking at confirmation entries
    # (since we can't modify the original correction entry)
    confirmed_seqs = set()
    for conf in confirmations:
        confirmed_seq = conf.payload.get('confirms_correction_seq')
        if confirmed_seq:
            confirmed_seqs.add(confirmed_seq)

    # Also count corrections that have human_validated=True directly (for future flexibility)
    for c in actual_corrections:
        if c.payload.get('human_validated'):
            confirmed_seqs.add(c.sequence)

    human_confirmed_count = len(confirmed_seqs)

    # Corrections by context
    by_context = {}
    for corr in actual_corrections:
        ctx = corr.context_id
        by_context[ctx] = by_context.get(ctx, 0) + 1

    # Corrections over time (by day)
    by_day = {}
    for corr in actual_corrections:
        day = corr.timestamp[:10]  # YYYY-MM-DD
        by_day[day] = by_day.get(day, 0) + 1

    # Calculate rate
    total_exchanges = len(exchanges)
    total_corrections = len(actual_corrections)
    correction_rate = total_corrections / total_exchanges if total_exchanges > 0 else 0.0

    return {
        'total_corrections': total_corrections,
        'total_confirmations': len(confirmations),
        'correction_rate': correction_rate,
        'correction_rate_percent': f"{correction_rate * 100:.2f}%",
        'types_breakdown': types_breakdown,
        'by_context': by_context,
        'by_day': by_day,
        # Validation stats
        'validation_stats': {
            'total_validated': len(validated),
            'human_confirmed': human_confirmed_count,
            'awaiting_human_review': len(validated) - human_confirmed_count,
            'had_warnings': len(had_warnings),
            'unvalidated_legacy': len(actual_corrections) - len(validated),
        },
        # Trends
        'improvement_trend': _calculate_improvement_trend(by_day) if len(by_day) > 1 else None,
    }


def _calculate_improvement_trend(by_day: Dict[str, int]) -> str:
    """Calculate if correction rate is improving over time."""
    if len(by_day) < 2:
        return "insufficient_data"

    days = sorted(by_day.keys())

    # Compare first half to second half
    mid = len(days) // 2
    first_half = sum(by_day[d] for d in days[:mid])
    second_half = sum(by_day[d] for d in days[mid:])

    if second_half < first_half:
        return "improving"
    elif second_half > first_half:
        return "declining"
    else:
        return "stable"


# =============================================================================
# MAIN - Interactive testing
# =============================================================================

if __name__ == "__main__":
    print("OZOLITH - Immutable Log Testing\n")

    # Create instance
    oz = Ozolith()
    renderer = OzolithRenderer(oz)

    # Show current stats
    print(renderer.render_stats())
    print()

    # Add a test entry
    entry = oz.append(
        event_type=OzolithEventType.SESSION_START,
        context_id="SB-1",
        actor="system",
        payload={'session_type': 'test', 'client': 'terminal'}
    )
    print(f"Added entry #{entry.sequence}")
    print(renderer.render_entry(entry))
    print()

    # Add an exchange
    exchange_payload = create_exchange_payload(
        query="What is OZOLITH?",
        response="An immutable log system for tamper-evident storage.",
        confidence=0.92,
        skinflap_score=0.78,
        reasoning_type="retrieval",
        token_count=150,
        latency_ms=340
    )
    entry2 = oz.append(
        event_type=OzolithEventType.EXCHANGE,
        context_id="SB-1",
        actor="assistant",
        payload=exchange_payload,
        skinflap_score=0.78
    )
    print(f"Added exchange #{entry2.sequence}")
    print(renderer.render_entry(entry2))
    print()

    # Verify chain
    print("Verifying chain...")
    result = oz.verify_chain()
    print(renderer.render_verification_report(result))
    print()

    # Show updated stats
    print(renderer.render_stats())
