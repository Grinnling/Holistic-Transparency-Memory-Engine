"""
Redis Client Implementation

Real implementation of RedisInterface for cache and message queue operations.
Gracefully degrades to stub behavior if Redis is unavailable.

Usage:
    from redis_client import get_redis_interface
    redis = get_redis_interface()
    redis.queue_for_agent("AGENT-curator", {"type": "validate", ...})

See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9.12 for design.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Redis connection settings (environment variables with defaults)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)

# Key prefixes for namespacing
KEY_PREFIX = "memory:"
QUEUE_PREFIX = f"{KEY_PREFIX}queue:"
AGENT_PREFIX = f"{KEY_PREFIX}agent:"
YARN_PREFIX = f"{KEY_PREFIX}yarn:"
PUBSUB_PREFIX = f"{KEY_PREFIX}pubsub:"

# TTL settings (seconds)
QUEUE_MESSAGE_TTL = 86400 * 7  # 7 days
AGENT_STATUS_TTL = 300  # 5 minutes (heartbeat refresh)
YARN_STATE_TTL = 3600  # 1 hour


class RedisClient:
    """
    Real Redis implementation of the RedisInterface.

    Handles connection management, graceful degradation, and all
    queue/cache operations used by the orchestrator.
    """

    def __init__(self):
        self._client = None
        self._connected = False
        self._pubsub = None
        self._connect()

    def _connect(self):
        """Attempt to connect to Redis."""
        try:
            import redis
            self._client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except ImportError:
            logger.warning("redis-py not installed. Run: pip install redis")
            self._connected = False
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Operating in stub mode.")
            self._connected = False

    def is_connected(self) -> bool:
        """Check if Redis is available."""
        if not self._connected or self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def reconnect(self) -> bool:
        """Attempt to reconnect to Redis."""
        self._connect()
        return self._connected

    # =========================================================================
    # YARN BOARD HOT STATE
    # =========================================================================

    def get_yarn_state(self, context_id: str) -> Optional[Dict]:
        """Fetch current grabbed yarn for a context."""
        if not self.is_connected():
            return None

        try:
            key = f"{YARN_PREFIX}state:{context_id}"
            data = self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get_yarn_state error: {e}")
            return None

    def set_yarn_state(self, context_id: str, state: Dict) -> bool:
        """Cache yarn board state."""
        if not self.is_connected():
            return False

        try:
            key = f"{YARN_PREFIX}state:{context_id}"
            self._client.setex(key, YARN_STATE_TTL, json.dumps(state))
            return True
        except Exception as e:
            logger.error(f"Redis set_yarn_state error: {e}")
            return False

    def set_grabbed(self, context_id: str, point_id: str, grabbed: bool, agent_id: str = "unknown") -> bool:
        """
        Mark a point as grabbed/released by an agent.

        Uses HASH to track which agent grabbed which point (for collision detection).
        Stores JSON with agent_id and grabbed_at timestamp.
        """
        if not self.is_connected():
            return False

        try:
            key = f"{YARN_PREFIX}grabbed:{context_id}"
            if grabbed:
                grab_data = json.dumps({
                    "agent_id": agent_id,
                    "grabbed_at": datetime.now().isoformat()
                })
                self._client.hset(key, point_id, grab_data)
            else:
                self._client.hdel(key, point_id)
            self._client.expire(key, YARN_STATE_TTL)
            return True
        except Exception as e:
            logger.error(f"Redis set_grabbed error: {e}")
            return False

    def try_grab_point(self, context_id: str, point_id: str, agent_id: str) -> Optional[Dict]:
        """
        Atomic grab attempt using HSETNX (hash set-if-not-exists).

        This is the "bathroom door lock" pattern - check and lock in ONE operation.
        No gap where another agent could slip in.

        Returns:
            None if we got the grab (no collision)
            Dict with existing grab info if someone else has it (collision detected)
        """
        if not self.is_connected():
            return None  # Can't detect collision without Redis

        try:
            key = f"{YARN_PREFIX}grabbed:{context_id}"
            grab_data = json.dumps({
                "agent_id": agent_id,
                "grabbed_at": datetime.now().isoformat()
            })

            # HSETNX = Hash SET if Not eXists - atomic operation
            # Returns 1 if field was set (we got it), 0 if field already exists (collision)
            acquired = self._client.hsetnx(key, point_id, grab_data)

            if acquired:
                # We got it, no collision
                self._client.expire(key, YARN_STATE_TTL)
                return None
            else:
                # Someone else has it - return their info
                existing = self._client.hget(key, point_id)
                if existing:
                    data = existing.decode('utf-8') if isinstance(existing, bytes) else existing
                    return json.loads(data)
                return {"agent_id": "unknown", "grabbed_at": "unknown"}
        except Exception as e:
            logger.error(f"Redis try_grab_point error: {e}")
            return None  # Fail open - can't detect collision

    def get_grabbed_by(self, context_id: str, point_id: str) -> Optional[Dict]:
        """
        Get which agent has a point grabbed and when.

        Returns:
            Dict with {agent_id, grabbed_at} if grabbed, None if not grabbed
        """
        if not self.is_connected():
            return None

        try:
            key = f"{YARN_PREFIX}grabbed:{context_id}"
            result = self._client.hget(key, point_id)
            if result:
                return json.loads(result.decode('utf-8'))
            return None
        except Exception as e:
            logger.error(f"Redis get_grabbed_by error: {e}")
            return None

    def get_grabbed_points(self, context_id: str) -> List[str]:
        """Get all grabbed points for a context (point IDs only)."""
        if not self.is_connected():
            return []

        try:
            key = f"{YARN_PREFIX}grabbed:{context_id}"
            # Get all keys from the hash
            # Handle both bytes (real Redis) and str (fakeredis)
            keys = self._client.hkeys(key)
            return [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
        except Exception as e:
            logger.error(f"Redis get_grabbed_points error: {e}")
            return []

    def get_all_grabbed(self, context_id: str) -> Dict[str, Dict]:
        """
        Get all grabbed points with their grab info.

        Returns:
            Dict mapping point_id -> {agent_id, grabbed_at}
        """
        if not self.is_connected():
            return {}

        try:
            key = f"{YARN_PREFIX}grabbed:{context_id}"
            result = self._client.hgetall(key)
            return {
                k.decode('utf-8'): json.loads(v.decode('utf-8'))
                for k, v in result.items()
            }
        except Exception as e:
            logger.error(f"Redis get_all_grabbed error: {e}")
            return {}

    # =========================================================================
    # AGENT PRESENCE
    # =========================================================================

    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """Get agent's current status."""
        if not self.is_connected():
            return None

        try:
            key = f"{AGENT_PREFIX}status:{agent_id}"
            data = self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get_agent_status error: {e}")
            return None

    def set_agent_busy(self, agent_id: str, busy: bool, current_task: Optional[str] = None) -> bool:
        """Mark agent as busy/available."""
        if not self.is_connected():
            return False

        try:
            key = f"{AGENT_PREFIX}status:{agent_id}"
            status = {
                "agent_id": agent_id,
                "busy": busy,
                "current_task": current_task,
                "last_heartbeat": datetime.now().isoformat()
            }
            self._client.setex(key, AGENT_STATUS_TTL, json.dumps(status))
            return True
        except Exception as e:
            logger.error(f"Redis set_agent_busy error: {e}")
            return False

    def heartbeat(self, agent_id: str) -> bool:
        """Refresh agent's presence (extend TTL). Creates default status if none exists."""
        if not self.is_connected():
            return False

        try:
            key = f"{AGENT_PREFIX}status:{agent_id}"
            # Get current status and refresh, or create default
            data = self._client.get(key)
            if data:
                status = json.loads(data)
                status["last_heartbeat"] = datetime.now().isoformat()
            else:
                # Create safe default status for agent
                status = {
                    "agent_id": agent_id,
                    "busy": False,
                    "current_task": None,
                    "last_heartbeat": datetime.now().isoformat()
                }
                logger.debug(f"Created default status for agent {agent_id}")

            self._client.setex(key, AGENT_STATUS_TTL, json.dumps(status))
            return True
        except Exception as e:
            logger.error(f"Redis heartbeat error: {e}")
            return False

    # =========================================================================
    # MESSAGE QUEUES (Scratchpad Routing)
    # =========================================================================

    def queue_for_agent(self, agent_id: str, message: Dict) -> bool:
        """Queue a message for an agent."""
        if not self.is_connected():
            return False

        try:
            key = f"{QUEUE_PREFIX}{agent_id}"
            # Add timestamp if not present
            if "queued_at" not in message:
                message["queued_at"] = datetime.now().isoformat()

            # Push to list (RPUSH for FIFO)
            self._client.rpush(key, json.dumps(message))
            self._client.expire(key, QUEUE_MESSAGE_TTL)

            logger.debug(f"Queued message for {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Redis queue_for_agent error: {e}")
            return False

    def get_agent_queue(self, agent_id: str, limit: int = 100) -> List[Dict]:
        """Fetch queued messages for an agent (peek, doesn't remove)."""
        if not self.is_connected():
            return []

        try:
            key = f"{QUEUE_PREFIX}{agent_id}"
            messages = self._client.lrange(key, 0, limit - 1)
            return [json.loads(m) for m in messages]
        except Exception as e:
            logger.error(f"Redis get_agent_queue error: {e}")
            return []

    def pop_agent_queue(self, agent_id: str) -> Optional[Dict]:
        """Pop oldest message from agent's queue (FIFO)."""
        if not self.is_connected():
            return None

        try:
            key = f"{QUEUE_PREFIX}{agent_id}"
            message = self._client.lpop(key)
            if message:
                return json.loads(message)
            return None
        except Exception as e:
            logger.error(f"Redis pop_agent_queue error: {e}")
            return None

    def clear_agent_queue(self, agent_id: str) -> bool:
        """Clear an agent's message queue."""
        if not self.is_connected():
            return False

        try:
            key = f"{QUEUE_PREFIX}{agent_id}"
            self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis clear_agent_queue error: {e}")
            return False

    def get_queue_length(self, agent_id: str) -> int:
        """Get number of messages in agent's queue."""
        if not self.is_connected():
            return 0

        try:
            key = f"{QUEUE_PREFIX}{agent_id}"
            return self._client.llen(key)
        except Exception as e:
            logger.error(f"Redis get_queue_length error: {e}")
            return 0

    # =========================================================================
    # PUB/SUB HOOKS
    # =========================================================================

    def notify_priority_change(self, context_id: str, point_id: str, new_priority: str) -> bool:
        """Publish priority change notification."""
        if not self.is_connected():
            return False

        try:
            channel = f"{PUBSUB_PREFIX}priority:{context_id}"
            message = {
                "type": "priority_change",
                "context_id": context_id,
                "point_id": point_id,
                "new_priority": new_priority,
                "timestamp": datetime.now().isoformat()
            }
            self._client.publish(channel, json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Redis notify_priority_change error: {e}")
            return False

    def subscribe_to_context(self, context_id: str, callback: Callable) -> bool:
        """Subscribe to updates for a context."""
        if not self.is_connected():
            return False

        try:
            if self._pubsub is None:
                self._pubsub = self._client.pubsub()

            channel = f"{PUBSUB_PREFIX}*:{context_id}"
            self._pubsub.psubscribe(**{channel: callback})
            return True
        except Exception as e:
            logger.error(f"Redis subscribe_to_context error: {e}")
            return False

    def unsubscribe_from_context(self, context_id: str) -> bool:
        """Unsubscribe from context updates."""
        if not self.is_connected() or self._pubsub is None:
            return False

        try:
            channel = f"{PUBSUB_PREFIX}*:{context_id}"
            self._pubsub.punsubscribe(channel)
            return True
        except Exception as e:
            logger.error(f"Redis unsubscribe_from_context error: {e}")
            return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def health_check(self) -> Dict:
        """Check Redis health and return status."""
        result = {
            "connected": self.is_connected(),
            "host": REDIS_HOST,
            "port": REDIS_PORT
        }

        if self.is_connected():
            try:
                info = self._client.info("memory")
                result["used_memory"] = info.get("used_memory_human", "unknown")
                result["status"] = "healthy"
            except Exception as e:
                result["status"] = f"degraded: {e}"
        else:
            result["status"] = "disconnected"

        return result


# =============================================================================
# ADAPTER: Bridge to datashapes.RedisInterface
# =============================================================================

class RedisInterfaceAdapter:
    """
    Adapter that wraps RedisClient to match the RedisInterface signature
    defined in datashapes.py.

    This allows existing orchestrator code to work without changes.
    """

    def __init__(self, client: RedisClient):
        self._client = client

    # Forward all methods to the real client
    def get_yarn_state(self, context_id: str):
        from datashapes import YarnBoardState
        data = self._client.get_yarn_state(context_id)
        if data:
            return YarnBoardState(**data)
        return None

    def set_yarn_state(self, state) -> bool:
        return self._client.set_yarn_state(state.context_id, {
            "context_id": state.context_id,
            "grabbed_point_ids": state.grabbed_point_ids,
            "priority_overrides": state.priority_overrides,
            "hot_refs": state.hot_refs,
            "last_interaction": state.last_interaction.isoformat() if hasattr(state.last_interaction, 'isoformat') else state.last_interaction,
            "interaction_count": state.interaction_count
        })

    def set_grabbed(self, context_id: str, point_id: str, grabbed: bool, agent_id: str = "unknown") -> bool:
        return self._client.set_grabbed(context_id, point_id, grabbed, agent_id)

    def get_grabbed_by(self, context_id: str, point_id: str) -> Optional[Dict]:
        return self._client.get_grabbed_by(context_id, point_id)

    def get_all_grabbed(self, context_id: str) -> Dict[str, Dict]:
        return self._client.get_all_grabbed(context_id)

    def get_agent_status(self, agent_id: str):
        return self._client.get_agent_status(agent_id)

    def set_agent_busy(self, agent_id: str, busy: bool, current_task=None) -> bool:
        return self._client.set_agent_busy(agent_id, busy, current_task)

    def queue_for_agent(self, agent_id: str, message: Dict) -> bool:
        return self._client.queue_for_agent(agent_id, message)

    def get_agent_queue(self, agent_id: str) -> List[Dict]:
        return self._client.get_agent_queue(agent_id)

    def clear_agent_queue(self, agent_id: str) -> bool:
        return self._client.clear_agent_queue(agent_id)

    def notify_priority_change(self, context_id: str, point_id: str, new_priority: str) -> bool:
        return self._client.notify_priority_change(context_id, point_id, new_priority)

    def subscribe_to_context(self, context_id: str, callback) -> bool:
        return self._client.subscribe_to_context(context_id, callback)

    def unsubscribe_from_context(self, context_id: str) -> bool:
        return self._client.unsubscribe_from_context(context_id)


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_redis_client: Optional[RedisClient] = None
_redis_interface: Optional[RedisInterfaceAdapter] = None


def get_redis_client() -> RedisClient:
    """Get the global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def get_redis_interface() -> RedisInterfaceAdapter:
    """Get a RedisInterface-compatible adapter."""
    global _redis_interface
    if _redis_interface is None:
        _redis_interface = RedisInterfaceAdapter(get_redis_client())
    return _redis_interface


def initialize_redis() -> bool:
    """
    Initialize Redis and replace the stub in datashapes.

    Call this at application startup to enable real Redis.
    Returns True if Redis is connected, False if operating in stub mode.
    """
    import datashapes

    client = get_redis_client()
    if client.is_connected():
        # Replace the stub with real implementation
        datashapes.redis_interface = get_redis_interface()
        logger.info("Redis initialized - real implementation active")
        return True
    else:
        logger.warning("Redis not available - using stub implementation")
        return False
