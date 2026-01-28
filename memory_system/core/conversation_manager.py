#!/usr/bin/env python3
"""
ConversationManager - Handles conversation persistence and lifecycle.

Extracted from rich_chat.py to separate persistence concerns from orchestration.

This module:
- Manages conversation state (conversation_id, conversation_history)
- Talks to episodic memory service for persistence
- Uses ConversationOrchestrator for session tracking + OZOLITH logging
- Logs memory lifecycle events for thought tracing

Created: 2025-12-16
Source: RICH_CHAT_REFACTORING_PRD.md, Option B from DRAFT_conversation_manager_options.md
"""

import logging
import requests
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from datashapes import (
    OzolithEventType,
    OzolithPayloadMemoryStored,
    OzolithPayloadMemoryRetrieved,
    OzolithPayloadMemoryArchived,
    OzolithPayloadMemoryRecalled,
    payload_to_dict,
)
from conversation_orchestrator import get_orchestrator, ConversationOrchestrator

logger = logging.getLogger(__name__)


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
            logger.warning("Ozolith not available - memory events will not be logged")
            return None
    return _ozolith_instance


class ConversationManager:
    """
    Manages conversation persistence to/from memory services.
    Uses ConversationOrchestrator for session tracking + OZOLITH logging.

    Responsibilities:
    - Conversation lifecycle (start, switch, list)
    - Conversation state (conversation_id, conversation_history)
    - Episodic memory persistence (list/load/save conversations)
    - Working memory storage (store exchanges)
    - Memory lifecycle event logging (MEMORY_STORED, etc.)

    Does NOT handle:
    - UI display (that's UIHandler)
    - Sidebar branching (that's ConversationOrchestrator)
    - LLM calls (that's rich_chat.py orchestrator)
    """

    def __init__(
        self,
        service_manager,
        error_handler,
        orchestrator: Optional[ConversationOrchestrator] = None
    ):
        """
        Initialize ConversationManager.

        Args:
            service_manager: ServiceManager for memory service URLs
            error_handler: ErrorHandler for error routing (REQUIRED - no silent errors)
            orchestrator: Optional ConversationOrchestrator (creates one if not provided)
        """
        if error_handler is None:
            raise ValueError("error_handler is required - no silent errors allowed in memory operations")

        self.service_manager = service_manager
        self.error_handler = error_handler
        self.orchestrator = orchestrator or get_orchestrator(error_handler=error_handler)

        # Conversation state
        self.conversation_id: str = str(uuid.uuid4())
        self.conversation_history: List[Dict[str, Any]] = []

        # Track the orchestrator context for this conversation
        self._context_id: Optional[str] = None

    # =========================================================================
    # CONVERSATION LIFECYCLE
    # =========================================================================

    def start_new_conversation(self, task_description: str = None) -> str:
        """
        Start a fresh conversation (keeps memory services, resets local context).

        Args:
            task_description: Optional description of what this conversation is about

        Returns:
            The new conversation_id
        """
        old_id = self.conversation_id[:8] if self.conversation_id else "none"
        old_count = len(self.conversation_history)

        # [DEBUG-SYNC] Check what orchestrator already has loaded
        existing_active = self.orchestrator.get_active_context_id()
        existing_contexts = self.orchestrator.list_contexts()
        print(f"[DEBUG-SYNC] start_new_conversation() called:")
        print(f"[DEBUG-SYNC]   Existing active context: {existing_active}")
        print(f"[DEBUG-SYNC]   Total existing contexts: {len(existing_contexts)}")
        if existing_active:
            existing_ctx = self.orchestrator.get_context(existing_active)
            if existing_ctx:
                print(f"[DEBUG-SYNC]   Existing context local_memory length: {len(existing_ctx.local_memory)}")
        print(f"[DEBUG-SYNC]   ⚠️ About to CREATE NEW context (ignoring existing!)")

        # Generate new conversation ID
        self.conversation_id = str(uuid.uuid4())

        # Clear local history
        self.conversation_history = []

        # Create root context in orchestrator (logs SESSION_START to OZOLITH)
        self._context_id = self.orchestrator.create_root_context(
            task_description=task_description or f"Conversation {self.conversation_id[:8]}",
            created_by="human"
        )

        print(f"[DEBUG-SYNC]   Created new context: {self._context_id}")
        print(f"[DEBUG-SYNC]   New active context: {self.orchestrator.get_active_context_id()}")

        logger.info(f"Started new conversation {self.conversation_id[:8]} (was {old_id}, {old_count} exchanges)")

        return self.conversation_id

    def list_conversations(self, limit: int = 50) -> List[Dict]:
        """
        List previous conversations from episodic memory.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of conversation summaries, or empty list if unavailable
        """
        if not self._check_episodic_health():
            logger.warning("Episodic memory not available for list_conversations")
            return []

        try:
            response = requests.get(
                f"{self._get_episodic_url()}/recent",
                params={"limit": limit},
                headers=self._get_trace_headers(),
                timeout=5
            )

            if response.status_code == 200:
                conversations = response.json().get('conversations', [])
                logger.debug(f"Listed {len(conversations)} conversations from episodic memory")
                return conversations
            else:
                logger.warning(f"Episodic memory returned {response.status_code} for list")
                return []

        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            if self.error_handler:
                from error_handler import ErrorCategory, ErrorSeverity
                self.error_handler.handle_error(
                    e,
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.HIGH_DEGRADE,
                    context="Listing conversations",
                    operation="list_conversations"
                )
            return []

    def switch_conversation(self, target_id: str) -> bool:
        """
        Switch to a different conversation by ID.

        Args:
            target_id: Full or partial conversation ID to switch to

        Returns:
            True if switch successful, False otherwise
        """
        if not self._check_episodic_health():
            logger.warning("Episodic memory not available for switch_conversation")
            return False

        try:
            # Expand partial ID if needed
            full_target_id = self._expand_conversation_id(target_id)
            if not full_target_id:
                return False

            # Load target conversation from episodic memory
            response = requests.get(
                f"{self._get_episodic_url()}/conversation/{full_target_id}",
                headers=self._get_trace_headers(),
                timeout=5
            )

            if response.status_code != 200:
                logger.error(f"Could not load conversation {target_id[:8]} from episodic memory")
                return False

            conv_data = response.json().get('conversation', {})
            exchanges = conv_data.get('exchanges', [])

            old_id = self.conversation_id[:8]
            old_count = len(self.conversation_history)

            # Switch to new conversation
            self.conversation_id = full_target_id
            self.conversation_history = []

            # Load exchanges into conversation history
            recalled_ids = []
            for exchange in exchanges:
                exchange_id = exchange.get('exchange_id', '')
                self.conversation_history.append({
                    'user': exchange.get('user_input', ''),
                    'assistant': exchange.get('assistant_response', ''),
                    'exchange_id': exchange_id,
                    'timestamp': exchange.get('timestamp'),
                    'restored': True,
                    'source': 'episodic_memory'
                })
                if exchange_id:
                    recalled_ids.append(exchange_id)

            # Create new root context in orchestrator for this resumed conversation
            self._context_id = self.orchestrator.create_root_context(
                task_description=f"Resumed: {full_target_id[:8]}...",
                created_by="human"
            )

            # Log MEMORY_RECALLED to OZOLITH
            oz = _get_ozolith()
            if oz and recalled_ids:
                payload = OzolithPayloadMemoryRecalled(
                    recalled_ids=recalled_ids,
                    recall_reason="switch_conversation",
                    conversation_id=self.conversation_id
                )
                oz.append(
                    event_type=OzolithEventType.MEMORY_RECALLED,
                    context_id=self._context_id or "unknown",
                    actor="system",
                    payload=payload_to_dict(payload)
                )

            logger.info(f"Switched conversation from {old_id} ({old_count} exchanges) to {full_target_id[:8]} ({len(exchanges)} exchanges)")
            return True

        except Exception as e:
            logger.error(f"Error switching conversation: {e}")
            if self.error_handler:
                from error_handler import ErrorCategory, ErrorSeverity
                self.error_handler.handle_error(
                    e,
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.HIGH_DEGRADE,
                    context=f"Switching to conversation {target_id[:8]}",
                    operation="switch_conversation"
                )
            return False

    def restore_conversation_history(self) -> int:
        """
        Restore recent conversation history from working memory and episodic memory.

        Returns:
            Total number of exchanges restored
        """
        # [DEBUG-SYNC] Log state when restore is called
        print(f"[DEBUG-SYNC] restore_conversation_history() called:")
        print(f"[DEBUG-SYNC]   Current _context_id: {self._context_id}")
        print(f"[DEBUG-SYNC]   Orchestrator active: {self.orchestrator.get_active_context_id()}")
        print(f"[DEBUG-SYNC]   conversation_history id: {id(self.conversation_history)}")
        print(f"[DEBUG-SYNC]   conversation_history length: {len(self.conversation_history)}")
        # Check if the active context has local_memory we should be using
        active_ctx = self.orchestrator.get_context(self.orchestrator.get_active_context_id())
        if active_ctx:
            print(f"[DEBUG-SYNC]   Active ctx local_memory length: {len(active_ctx.local_memory)}")
            print(f"[DEBUG-SYNC]   ⚠️ Note: This restore pulls from working_memory SERVICE, not local_memory!")

        working_count = 0
        episodic_count = 0
        recalled_ids = []

        # First try working memory for recent exchanges
        if self._check_working_memory_health():
            try:
                response = requests.get(
                    f"{self._get_working_memory_url()}/working-memory",
                    params={"limit": 30},
                    headers=self._get_trace_headers(),
                    timeout=5
                )

                if response.status_code == 200:
                    data = response.json()
                    exchanges = data.get('context', [])

                    for exchange in exchanges:
                        exchange_id = exchange.get('exchange_id', '')
                        self.conversation_history.append({
                            'user': exchange.get('user_message', ''),
                            'assistant': exchange.get('assistant_response', ''),
                            'exchange_id': exchange_id,
                            'timestamp': exchange.get('created_at', ''),
                            'restored': True,
                            'source': 'working_memory'
                        })
                        if exchange_id:
                            recalled_ids.append(exchange_id)

                    working_count = len(exchanges)

            except Exception as e:
                logger.warning(f"Could not restore from working memory: {e}")

        # Then try episodic memory for additional context
        if self._check_episodic_health():
            try:
                response = requests.get(
                    f"{self._get_episodic_url()}/recent",
                    params={"limit": 20},
                    headers=self._get_trace_headers(),
                    timeout=5
                )

                if response.status_code == 200:
                    data = response.json()
                    conversations = data.get('conversations', [])

                    # Avoid duplicates by checking timestamps
                    existing_timestamps = {ex.get('timestamp', '') for ex in self.conversation_history}

                    for conv in conversations:
                        exchanges = conv.get('exchanges', [])
                        for exchange in exchanges[-2:]:  # Last 2 from each conversation
                            timestamp = exchange.get('timestamp', '')
                            if timestamp not in existing_timestamps:
                                exchange_id = exchange.get('exchange_id', '')
                                self.conversation_history.append({
                                    'user': exchange.get('user_input', ''),
                                    'assistant': exchange.get('assistant_response', ''),
                                    'exchange_id': exchange_id,
                                    'timestamp': timestamp,
                                    'restored': True,
                                    'source': 'episodic_memory'
                                })
                                if exchange_id:
                                    recalled_ids.append(exchange_id)
                                episodic_count += 1

            except Exception as e:
                logger.warning(f"Could not restore from episodic memory: {e}")

        # Log MEMORY_RECALLED if we restored anything
        oz = _get_ozolith()
        if oz and recalled_ids:
            payload = OzolithPayloadMemoryRecalled(
                recalled_ids=recalled_ids,
                recall_reason="restore_conversation_history",
                conversation_id=self.conversation_id
            )
            oz.append(
                event_type=OzolithEventType.MEMORY_RECALLED,
                context_id=self._context_id or "startup",
                actor="system",
                payload=payload_to_dict(payload)
            )

        total_restored = working_count + episodic_count
        logger.info(f"Restored {total_restored} exchanges ({working_count} working + {episodic_count} episodic)")

        return total_restored

    # =========================================================================
    # EXCHANGE STORAGE
    # =========================================================================

    def store_exchange(
        self,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Store an exchange - both to orchestrator (OZOLITH) AND working memory service.

        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            metadata: Optional metadata (confidence, etc.)

        Returns:
            The exchange_id if successful, None otherwise
        """
        # First, log to orchestrator (in-memory + OZOLITH)
        exchange_id = self.orchestrator.add_exchange(
            context_id=self._context_id or self.orchestrator.get_active_context_id(),
            user_message=user_message,
            assistant_response=assistant_response,
            metadata=metadata
        )

        # Also add to local conversation history (include metadata for consistency with local_memory)
        history_entry = {
            'user': user_message,
            'assistant': assistant_response,
            'exchange_id': exchange_id,
            'timestamp': datetime.now().isoformat(),
            'restored': False,
            'source': 'current_session'
        }
        # Include metadata (validation, retrieved_memories, etc.) if provided
        if metadata:
            history_entry.update(metadata)
        self.conversation_history.append(history_entry)

        # [DEBUG-SYNC] Log what was stored to conversation_history
        print(f"[DEBUG-SYNC] conversation_manager.store_exchange():")
        print(f"[DEBUG-SYNC]   conversation_history id: {id(self.conversation_history)}")
        print(f"[DEBUG-SYNC]   Stored entry keys: {list(history_entry.keys())}")
        print(f"[DEBUG-SYNC]   Has retrieved_memories: {'retrieved_memories' in history_entry}")
        print(f"[DEBUG-SYNC]   Has validation: {'validation' in history_entry}")
        print(f"[DEBUG-SYNC]   History length now: {len(self.conversation_history)}")

        # Then persist to working memory service
        if self._check_working_memory_health():
            try:
                response = requests.post(
                    f"{self._get_working_memory_url()}/working-memory",
                    json={
                        "user_message": user_message,
                        "assistant_response": assistant_response,
                        "context_used": ["rich_chat"],
                        "exchange_id": exchange_id,
                        "conversation_id": self.conversation_id
                    },
                    headers=self._get_trace_headers(),
                    timeout=5
                )

                if response.status_code == 200:
                    # Log MEMORY_STORED to OZOLITH
                    oz = _get_ozolith()
                    if oz:
                        payload = OzolithPayloadMemoryStored(
                            exchange_id=exchange_id,
                            conversation_id=self.conversation_id,
                            context_id=self._context_id or "",
                            confidence=metadata.get('confidence', 0.0) if metadata else 0.0
                        )
                        oz.append(
                            event_type=OzolithEventType.MEMORY_STORED,
                            context_id=self._context_id or "unknown",
                            actor="system",
                            payload=payload_to_dict(payload)
                        )

                    logger.debug(f"Stored exchange {exchange_id} to working memory")
                else:
                    logger.warning(f"Working memory returned {response.status_code} for store")

            except Exception as e:
                logger.error(f"Error storing to working memory: {e}")
                if self.error_handler:
                    from error_handler import ErrorCategory, ErrorSeverity
                    self.error_handler.handle_error(
                        e,
                        ErrorCategory.WORKING_MEMORY,
                        ErrorSeverity.HIGH_DEGRADE,
                        context=f"Storing exchange {exchange_id}",
                        operation="store_exchange"
                    )

        return exchange_id

    def get_context_for_llm(self) -> List[Dict]:
        """
        Get context to send to LLM, logging what was retrieved.

        Returns:
            List of exchanges formatted for LLM context
        """
        # Get from orchestrator (includes inherited + local memory)
        context_id = self._context_id or self.orchestrator.get_active_context_id()
        if context_id:
            context = self.orchestrator.get_context_for_llm(context_id)
        else:
            # Fall back to local conversation history
            context = self.conversation_history

        # Log MEMORY_RETRIEVED to OZOLITH
        oz = _get_ozolith()
        if oz and context:
            retrieved_ids = [ex.get('exchange_id', '') for ex in context if ex.get('exchange_id')]
            if retrieved_ids:
                payload = OzolithPayloadMemoryRetrieved(
                    for_exchange="pending",  # Will be filled in by actual exchange
                    retrieved_ids=retrieved_ids,
                    conversation_id=self.conversation_id,
                    context_id=context_id or "",
                    total_tokens=0,  # Could estimate if needed
                    from_working=len([ex for ex in context if ex.get('source') == 'working_memory']),
                    from_episodic=len([ex for ex in context if ex.get('source') == 'episodic_memory'])
                )
                oz.append(
                    event_type=OzolithEventType.MEMORY_RETRIEVED,
                    context_id=context_id or "unknown",
                    actor="system",
                    payload=payload_to_dict(payload)
                )

        return context

    # =========================================================================
    # ARCHIVING
    # =========================================================================

    def archive_conversation(self, reason: str = "manual") -> bool:
        """
        Archive current conversation to episodic memory for long-term storage.

        This sends the conversation to episodic memory but does NOT clear
        working memory - that happens naturally when a new conversation starts.

        Args:
            reason: Why archiving was triggered - "manual", "session_end",
                    "distillation", "auto_checkpoint"

        Returns:
            True if archive succeeded, False otherwise
        """
        # Nothing to archive?
        if not self.conversation_history:
            logger.info("No conversation history to archive")
            return True  # Not a failure, just nothing to do

        # Check if episodic service is available
        if not self._check_episodic_health():
            logger.warning("Episodic memory not available for archiving")
            if self.error_handler:
                from error_handler import ErrorCategory, ErrorSeverity
                self.error_handler.handle_error(
                    Exception("Episodic memory unavailable"),
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.MEDIUM_ALERT,
                    context="archive_conversation",
                    operation="archive_conversation"
                )
            return False

        # Build conversation data for episodic memory
        exchanges = []
        for entry in self.conversation_history:
            exchanges.append({
                'user_message': entry.get('user', ''),
                'assistant_response': entry.get('assistant', ''),
                'exchange_id': entry.get('exchange_id', ''),
                'timestamp': entry.get('timestamp', datetime.now().isoformat())
            })

        conversation_data = {
            'conversation_id': self.conversation_id,
            'exchanges': exchanges,
            'participants': ['human', 'assistant']
        }

        # POST to episodic memory /archive endpoint
        try:
            response = requests.post(
                f"{self._get_episodic_url()}/archive",
                json={
                    'conversation_data': conversation_data,
                    'trigger_reason': reason
                },
                headers=self._get_trace_headers(),
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"Archive failed with status {response.status_code}")
                if self.error_handler:
                    from error_handler import ErrorCategory, ErrorSeverity
                    self.error_handler.handle_error(
                        Exception(f"Archive returned {response.status_code}"),
                        ErrorCategory.EPISODIC_MEMORY,
                        ErrorSeverity.HIGH_DEGRADE,
                        context=f"Archiving conversation {self.conversation_id}",
                        operation="archive_conversation"
                    )
                return False

            # Log MEMORY_ARCHIVED events for each exchange
            oz = _get_ozolith()
            if oz:
                archive_time = datetime.now()
                for entry in self.conversation_history:
                    exchange_id = entry.get('exchange_id', '')
                    if exchange_id:
                        # Calculate age if we have timestamp
                        age_seconds = 0
                        if entry.get('timestamp'):
                            try:
                                created = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                                age_seconds = int((archive_time - created.replace(tzinfo=None)).total_seconds())
                            except (ValueError, TypeError):
                                pass

                        payload = OzolithPayloadMemoryArchived(
                            exchange_id=exchange_id,
                            reason=reason,
                            conversation_id=self.conversation_id,
                            context_id=self._context_id or "",
                            age_at_archive_seconds=age_seconds,
                            was_distilled=False,
                            archive_location="episodic"
                        )
                        oz.append(
                            event_type=OzolithEventType.MEMORY_ARCHIVED,
                            context_id=self._context_id or "archive",
                            actor="system",
                            payload=payload_to_dict(payload)
                        )

            logger.info(f"Archived conversation {self.conversation_id} with {len(exchanges)} exchanges (reason: {reason})")
            return True

        except requests.RequestException as e:
            logger.error(f"Archive request failed: {e}")
            if self.error_handler:
                from error_handler import ErrorCategory, ErrorSeverity
                self.error_handler.handle_error(
                    e,
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.HIGH_DEGRADE,
                    context=f"Archiving conversation {self.conversation_id}",
                    operation="archive_conversation"
                )
            return False

    # =========================================================================
    # CONTEXT HELPERS
    # =========================================================================

    def get_recent_context_hint(self) -> str:
        """
        Get hints from recent conversation for better clarification.

        Returns:
            String with recent topic hints, or empty string
        """
        if len(self.conversation_history) < 2:
            return ""

        recent_topics = []
        for exchange in self.conversation_history[-3:]:
            user_msg = exchange.get('user', '').lower()

            # Extract potential topics
            topic_keywords = ['bug', 'feature', 'function', 'error', 'issue', 'code', 'script', 'library']
            for keyword in topic_keywords:
                if keyword in user_msg:
                    words = user_msg.split()
                    for i, word in enumerate(words):
                        if keyword in word:
                            start = max(0, i - 2)
                            end = min(len(words), i + 3)
                            context = ' '.join(words[start:end])
                            recent_topics.append(context)
                            break

        if recent_topics:
            return ', '.join(recent_topics[-2:])
        return ""

    # =========================================================================
    # SERVICE HELPERS
    # =========================================================================

    def _check_episodic_health(self) -> bool:
        """Check if episodic memory service is available."""
        if not self.service_manager:
            return False
        return self.service_manager.check_service_health('episodic_memory')

    def _check_working_memory_health(self) -> bool:
        """Check if working memory service is available."""
        if not self.service_manager:
            return False
        return self.service_manager.check_service_health('working_memory')

    def _get_episodic_url(self) -> str:
        """Get episodic memory service URL."""
        return self.service_manager.services.get('episodic_memory', '')

    def _get_working_memory_url(self) -> str:
        """Get working memory service URL."""
        return self.service_manager.services.get('working_memory', '')

    def _get_trace_headers(self) -> Dict[str, str]:
        """Get trace headers for inter-service calls."""
        return {
            "X-Conversation-ID": self.conversation_id,
            "X-Request-ID": str(uuid.uuid4()),
            "X-Source": "conversation_manager"
        }

    def _expand_conversation_id(self, partial_id: str) -> Optional[str]:
        """
        Expand a partial conversation ID to full ID.

        Args:
            partial_id: Full or partial conversation ID

        Returns:
            Full conversation ID if found, None otherwise
        """
        if len(partial_id) >= 36:  # Already a full UUID
            return partial_id

        # Get conversation list and find match
        conversations = self.list_conversations(limit=50)
        matches = [
            conv for conv in conversations
            if conv.get('conversation_id', '').startswith(partial_id)
        ]

        if len(matches) == 0:
            logger.warning(f"No conversation found starting with '{partial_id}'")
            return None
        elif len(matches) > 1:
            logger.warning(f"Multiple conversations match '{partial_id}', be more specific")
            return None
        else:
            return matches[0]['conversation_id']

    # =========================================================================
    # STATE ACCESS
    # =========================================================================

    def get_conversation_id(self) -> str:
        """Get current conversation ID."""
        return self.conversation_id

    def get_context_id(self) -> Optional[str]:
        """Get current orchestrator context ID."""
        return self._context_id

    def get_history_count(self) -> int:
        """Get number of exchanges in current conversation history."""
        return len(self.conversation_history)

    def get_history(self) -> List[Dict]:
        """Get current conversation history."""
        return self.conversation_history.copy()


# =============================================================================
# MODULE-LEVEL CONVENIENCE
# =============================================================================

_manager_instance: Optional[ConversationManager] = None


def get_conversation_manager(
    service_manager=None,
    error_handler=None,
    orchestrator=None
) -> ConversationManager:
    """
    Get or create the global ConversationManager instance.

    Args:
        service_manager: ServiceManager for memory service URLs (required on first call)
        error_handler: ErrorHandler for error routing (required on first call)
        orchestrator: Optional ConversationOrchestrator

    Returns:
        ConversationManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        if service_manager is None:
            raise ValueError("service_manager required for first ConversationManager creation")
        if error_handler is None:
            raise ValueError("error_handler required for first ConversationManager creation - no silent errors")
        _manager_instance = ConversationManager(
            service_manager=service_manager,
            error_handler=error_handler,
            orchestrator=orchestrator
        )

    return _manager_instance


def reset_conversation_manager():
    """Reset the global ConversationManager (for testing)."""
    global _manager_instance
    _manager_instance = None
