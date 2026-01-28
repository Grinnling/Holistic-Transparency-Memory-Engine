#!/usr/bin/env python3
"""
event_emitter.py - Central Event Emission for Visibility Stream

Purpose: Enable operator to see what Claude sees via event stream to React.
Per VISIBILITY_STREAM_PRD.md decision: Events persist to OZOLITH, tiers control live stream.

Architecture:
    EventEmitter (this module)
        ↓
    OZOLITH (persistence) + WebSocket (live stream)
        ↓
    React EventStream component

Event Tiers:
    Tier 1 (Critical): Always stream live - context_loaded, memory_retrieved, validation_result, error_occurred
    Tier 2 (System): Collapsed by default - ozolith_logged, sidebar_lifecycle, memory_pressure, emergency_mode
    Tier 3 (Debug): Hidden by default - llm_prompt, llm_response_raw, tool_invocation, etc.

Key Decision (from PRD):
    - OZOLITH stores ALL events regardless of tier (nothing cheesable)
    - Tier classification only controls what streams live
    - React can query OZOLITH history for any event

Usage:
    from event_emitter import EventEmitter, EventTier

    emitter = EventEmitter(ozolith_instance)
    emitter.emit("context_loaded", {"conversation_id": "SB-5", "messages": 12})

Created: 2025-12-24
See: VISIBILITY_STREAM_PRD.md for full specification
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

# Import OZOLITH for persistence
try:
    from ozolith import Ozolith, OzolithEventType
except ImportError:
    Ozolith = None
    OzolithEventType = None


class EventTier(Enum):
    """
    Event visibility tiers - controls live streaming behavior.
    OZOLITH stores everything regardless of tier (skinflap principle).
    """
    CRITICAL = 1   # Always stream live, cannot hide
    SYSTEM = 2     # Collapsed by default in UI
    DEBUG = 3      # Hidden by default in UI


@dataclass
class VisibilityEvent:
    """
    A single event in the visibility stream.

    Designed for both machine processing (OZOLITH) and human visibility (React).
    """
    sequence: int
    timestamp: str
    event_type: str
    payload: Dict[str, Any]
    tier: EventTier
    context_id: str = "SYSTEM"  # Which sidebar/conversation
    actor: str = "system"       # Who triggered this

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "type": self.event_type,
            "payload": self.payload,
            "tier": self.tier.value,
            "tier_name": self.tier.name.lower(),
            "context_id": self.context_id,
            "actor": self.actor
        }


# Event type to tier mapping
# This is the default classification - operator can reconfigure in React
EVENT_TIER_MAP: Dict[str, EventTier] = {
    # Tier 1: Critical (Poison Detection)
    "context_loaded": EventTier.CRITICAL,
    "memory_retrieved": EventTier.CRITICAL,
    "validation_result": EventTier.CRITICAL,
    "error_occurred": EventTier.CRITICAL,

    # Tier 2: System Visibility
    "ozolith_logged": EventTier.SYSTEM,
    "sidebar_lifecycle": EventTier.SYSTEM,
    "memory_pressure": EventTier.SYSTEM,
    "emergency_mode": EventTier.SYSTEM,

    # Tier 3: Debug Visibility
    "llm_prompt": EventTier.DEBUG,
    "llm_response_raw": EventTier.DEBUG,
    "citation_created": EventTier.DEBUG,
    "correction_logged": EventTier.DEBUG,
    "tool_invocation": EventTier.DEBUG,
    "search_performed": EventTier.DEBUG,
    "file_read": EventTier.DEBUG,
    "file_write": EventTier.DEBUG,
    "distillation_triggered": EventTier.DEBUG,
    "anchor_created": EventTier.DEBUG,
    "conversation_switch": EventTier.DEBUG,
}


class EventEmitter:
    """
    Central hub for event emission to visibility stream.

    Responsibilities:
    - Assign sequence numbers to events
    - Classify events by tier
    - Persist ALL events to OZOLITH (nothing cheesable)
    - Stream events to registered listeners (WebSocket callbacks)
    - Maintain tier configuration for live streaming

    The skinflap principle: Claude's column of truth is not cheesable
    because OZOLITH stores everything regardless of tier.
    """

    def __init__(
        self,
        ozolith: Optional['Ozolith'] = None,
        enable_ozolith: bool = True,
        stream_tiers: Optional[Set[EventTier]] = None
    ):
        """
        Initialize EventEmitter.

        Args:
            ozolith: OZOLITH instance for persistence. Created if not provided.
            enable_ozolith: Whether to persist to OZOLITH (default True).
            stream_tiers: Which tiers to stream live. Default: Tier 1 only.
        """
        self._sequence = 0
        self._listeners: List[Callable[[VisibilityEvent], None]] = []
        self._async_listeners: List[Callable[[VisibilityEvent], Any]] = []

        # OZOLITH persistence
        self._enable_ozolith = enable_ozolith
        if enable_ozolith:
            if ozolith is not None:
                self._ozolith = ozolith
            elif Ozolith is not None:
                self._ozolith = Ozolith()
            else:
                self._ozolith = None
                self._enable_ozolith = False
        else:
            self._ozolith = None

        # Tier configuration for live streaming
        # Default: Only stream Tier 1 (Critical) live
        self._stream_tiers = stream_tiers or {EventTier.CRITICAL}

        # Custom tier overrides (operator can reconfigure)
        self._tier_overrides: Dict[str, EventTier] = {}

        # Event buffer for recent events (in-memory cache)
        self._event_buffer: List[VisibilityEvent] = []
        self._buffer_max_size = 1000

    def _next_seq(self) -> int:
        """Get next sequence number."""
        self._sequence += 1
        return self._sequence

    def _get_tier(self, event_type: str) -> EventTier:
        """
        Get tier for event type, respecting overrides.

        Unknown event types default to DEBUG tier (visible but not intrusive).
        """
        # Check overrides first
        if event_type in self._tier_overrides:
            return self._tier_overrides[event_type]

        # Then default mapping
        return EVENT_TIER_MAP.get(event_type, EventTier.DEBUG)

    def _should_stream(self, tier: EventTier) -> bool:
        """Check if this tier should be streamed live."""
        return tier in self._stream_tiers

    def set_tier_override(self, event_type: str, tier: EventTier) -> None:
        """
        Override tier classification for an event type.

        Allows operator to promote/demote event types based on operational needs.
        """
        self._tier_overrides[event_type] = tier

    def clear_tier_override(self, event_type: str) -> None:
        """Remove tier override, restoring default classification."""
        self._tier_overrides.pop(event_type, None)

    def set_stream_tiers(self, tiers: Set[EventTier]) -> None:
        """
        Configure which tiers stream live.

        Args:
            tiers: Set of tiers to stream. E.g., {EventTier.CRITICAL, EventTier.SYSTEM}
        """
        self._stream_tiers = tiers

    def add_listener(self, callback: Callable[[VisibilityEvent], None]) -> None:
        """
        Add synchronous listener for events.

        Listener is called for events in configured stream_tiers.
        """
        self._listeners.append(callback)

    def add_async_listener(self, callback: Callable[[VisibilityEvent], Any]) -> None:
        """
        Add async listener for events (e.g., WebSocket broadcast).

        Listener is called for events in configured stream_tiers.
        """
        self._async_listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
        if callback in self._async_listeners:
            self._async_listeners.remove(callback)

    def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
        context_id: str = "SYSTEM",
        actor: str = "system",
        tier_override: Optional[EventTier] = None
    ) -> VisibilityEvent:
        """
        Emit an event to the visibility stream.

        This is the main method. It:
        1. Creates the event with sequence and timestamp
        2. Persists to OZOLITH (ALL events, regardless of tier)
        3. Streams to listeners (only if tier is in stream_tiers)

        Args:
            event_type: Type of event (e.g., "context_loaded")
            payload: Event-specific data
            context_id: Which context/sidebar this relates to
            actor: Who triggered this ("human", "assistant", "system")
            tier_override: Override tier for this specific emit

        Returns:
            The created VisibilityEvent
        """
        # Determine tier
        tier = tier_override if tier_override else self._get_tier(event_type)

        # Create event
        event = VisibilityEvent(
            sequence=self._next_seq(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type,
            payload=payload,
            tier=tier,
            context_id=context_id,
            actor=actor
        )

        # Buffer event (in-memory cache)
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._buffer_max_size:
            self._event_buffer.pop(0)

        # Persist to OZOLITH (ALL events - nothing cheesable)
        if self._enable_ozolith and self._ozolith is not None:
            self._persist_to_ozolith(event)

        # Stream to listeners (only if tier is configured for streaming)
        if self._should_stream(tier):
            self._notify_listeners(event)

        return event

    def _persist_to_ozolith(self, event: VisibilityEvent) -> None:
        """
        Persist event to OZOLITH.

        Maps visibility event types to OZOLITH event types where applicable,
        or uses a generic VISIBILITY_EVENT type.
        """
        if self._ozolith is None:
            return

        # Map to OZOLITH event type if possible
        ozolith_type_map = {
            "error_occurred": OzolithEventType.ERROR_LOGGED if OzolithEventType else None,
            "anchor_created": OzolithEventType.ANCHOR_CREATED if OzolithEventType else None,
            "sidebar_lifecycle": OzolithEventType.SIDEBAR_SPAWN if OzolithEventType else None,
            "correction_logged": OzolithEventType.CORRECTION if OzolithEventType else None,
        }

        ozolith_event_type = ozolith_type_map.get(event.event_type)

        # For visibility events, we'll use a generic approach
        # The payload includes the visibility event type for querying
        payload = {
            "visibility_event_type": event.event_type,
            "visibility_tier": event.tier.name,
            "visibility_sequence": event.sequence,
            **event.payload
        }

        try:
            # Use EXCHANGE type as generic container if no specific mapping
            if ozolith_event_type is None and OzolithEventType is not None:
                ozolith_event_type = OzolithEventType.EXCHANGE

            if ozolith_event_type is not None:
                self._ozolith.append(
                    event_type=ozolith_event_type,
                    context_id=event.context_id,
                    actor=event.actor,
                    payload=payload
                )
        except Exception as e:
            # Log but don't fail - visibility shouldn't break the system
            print(f"[EventEmitter] OZOLITH persistence failed: {e}")

    def _notify_listeners(self, event: VisibilityEvent) -> None:
        """Notify all registered listeners of the event."""
        event_dict = event.to_dict()

        # Sync listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"[EventEmitter] Listener error: {e}")

        # Async listeners - schedule them
        for async_listener in self._async_listeners:
            try:
                # Check if we're in an async context
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(async_listener(event))
                except RuntimeError:
                    # No running loop - use asyncio.run or skip
                    pass
            except Exception as e:
                print(f"[EventEmitter] Async listener error: {e}")

    def get_recent_events(
        self,
        count: int = 100,
        tier: Optional[EventTier] = None,
        event_type: Optional[str] = None
    ) -> List[VisibilityEvent]:
        """
        Get recent events from buffer.

        Args:
            count: Maximum number of events to return
            tier: Filter by tier (optional)
            event_type: Filter by event type (optional)

        Returns:
            List of recent events (newest last)
        """
        events = self._event_buffer

        if tier is not None:
            events = [e for e in events if e.tier == tier]

        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        return events[-count:]

    def get_event_types(self) -> Dict[str, str]:
        """Get all known event types and their tiers."""
        result = {}
        for event_type, tier in EVENT_TIER_MAP.items():
            effective_tier = self._tier_overrides.get(event_type, tier)
            result[event_type] = effective_tier.name.lower()
        return result

    def stats(self) -> Dict[str, Any]:
        """Get emitter statistics."""
        tier_counts = {tier.name.lower(): 0 for tier in EventTier}
        type_counts: Dict[str, int] = {}

        for event in self._event_buffer:
            tier_counts[event.tier.name.lower()] += 1
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

        return {
            "total_emitted": self._sequence,
            "buffer_size": len(self._event_buffer),
            "buffer_max": self._buffer_max_size,
            "stream_tiers": [t.name.lower() for t in self._stream_tiers],
            "listener_count": len(self._listeners) + len(self._async_listeners),
            "ozolith_enabled": self._enable_ozolith,
            "tier_counts": tier_counts,
            "type_counts": type_counts,
            "tier_overrides": {k: v.name for k, v in self._tier_overrides.items()}
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Global emitter instance - use this for most cases
_global_emitter: Optional[EventEmitter] = None


def get_emitter() -> EventEmitter:
    """
    Get the global EventEmitter instance.

    Creates one if it doesn't exist. This is the recommended way to
    access the emitter from other modules.
    """
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = EventEmitter()
    return _global_emitter


def emit(
    event_type: str,
    payload: Dict[str, Any],
    context_id: str = "SYSTEM",
    actor: str = "system"
) -> VisibilityEvent:
    """
    Convenience function to emit via global emitter.

    Usage:
        from event_emitter import emit
        emit("context_loaded", {"conversation_id": "SB-5"})
    """
    return get_emitter().emit(event_type, payload, context_id, actor)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("EventEmitter - Visibility Stream Testing\n")

    # Create emitter without OZOLITH for testing
    emitter = EventEmitter(enable_ozolith=False)

    # Add test listener
    def test_listener(event: VisibilityEvent):
        print(f"  [LISTENER] {event.tier.name}: {event.event_type}")

    emitter.add_listener(test_listener)

    # Enable all tiers for testing
    emitter.set_stream_tiers({EventTier.CRITICAL, EventTier.SYSTEM, EventTier.DEBUG})

    print("Emitting test events...")

    # Tier 1 event
    e1 = emitter.emit("context_loaded", {
        "conversation_id": "SB-5",
        "message_count": 12
    })
    print(f"Emitted #{e1.sequence}: {e1.event_type} (tier: {e1.tier.name})")

    # Tier 2 event
    e2 = emitter.emit("memory_pressure", {
        "buffer_used": 0.85,
        "threshold": 0.80
    })
    print(f"Emitted #{e2.sequence}: {e2.event_type} (tier: {e2.tier.name})")

    # Tier 3 event
    e3 = emitter.emit("tool_invocation", {
        "tool": "file_read",
        "path": "/some/file.py"
    })
    print(f"Emitted #{e3.sequence}: {e3.event_type} (tier: {e3.tier.name})")

    # Unknown event type (should default to DEBUG)
    e4 = emitter.emit("custom_new_event", {
        "data": "extensible system"
    })
    print(f"Emitted #{e4.sequence}: {e4.event_type} (tier: {e4.tier.name})")

    print("\nEmitter stats:")
    for key, value in emitter.stats().items():
        print(f"  {key}: {value}")

    print("\nRecent events:")
    for event in emitter.get_recent_events(10):
        print(f"  #{event.sequence} [{event.tier.name}] {event.event_type}")
