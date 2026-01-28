#!/usr/bin/env python3
"""
ChatLogger - Raw exchange logging to JSONL files.

This is the "lab notes" layer - raw, unprocessed, for reprocessing later.
Writes to both daily log and session log for redundancy.

Design principle: Logging failures NEVER crash the chat.

Part of Layer 5 extraction from rich_chat.py.
"""

import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from error_handler import ErrorHandler


class ChatLogger:
    """
    Handles raw exchange logging to JSONL files.

    This is the "lab notes" layer - raw, unprocessed, for reprocessing later.
    Writes to both daily log and session log for redundancy.

    Design principle: Logging failures NEVER crash the chat.

    Path priority: explicit > CHAT_LOG_PATH env var > project-relative default
    """

    def __init__(
        self,
        base_path: Optional[str] = None,
        error_handler: Optional['ErrorHandler'] = None,
        debug_mode: bool = False
    ):
        """
        Initialize ChatLogger.

        Path priority: explicit > CHAT_LOG_PATH env var > project-relative default

        Args:
            base_path: Explicit override for log directory
            error_handler: Optional ErrorHandler for error routing
            debug_mode: Whether to show debug messages
        """
        # Determine base path with priority chain
        if base_path:
            self.base_path = Path(base_path)
        elif os.environ.get('CHAT_LOG_PATH'):
            self.base_path = Path(os.environ['CHAT_LOG_PATH'])
        else:
            # Project-relative default
            self.base_path = Path(__file__).parent / 'data' / 'chat_logs'

        self.error_handler = error_handler
        self.debug_mode = debug_mode
        self._logger = logging.getLogger(__name__)

        # Ensure directories exist
        self._ensure_directories()

    def log_exchange(
        self,
        user_message: str,
        assistant_response: str,
        conversation_id: str,
        exchange_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log a raw exchange to JSONL files.

        Writes to:
        - daily/{YYYY-MM-DD}.jsonl (for time-based analysis)
        - sessions/{conversation_id}.jsonl (for conversation replay)

        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            conversation_id: Current conversation ID
            exchange_id: Optional exchange ID (generates UUID if None)
            request_id: Optional request ID for distributed tracing
            metadata: Optional additional metadata to include

        Returns:
            True if logging succeeded (both files), False if any write failed
        """
        # Build entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "exchange_id": exchange_id or str(uuid.uuid4()),
            "request_id": request_id or "unknown",
            "user": user_message,
            "assistant": assistant_response
        }

        if metadata:
            entry["metadata"] = metadata

        entry_line = json.dumps(entry) + "\n"

        try:
            # Write to daily log
            daily_path = self.get_daily_log_path()
            with open(daily_path, "a", encoding="utf-8") as f:
                f.write(entry_line)

            # Write to session log
            session_path = self.get_session_log_path(conversation_id)
            with open(session_path, "a", encoding="utf-8") as f:
                f.write(entry_line)

            if self.debug_mode:
                self._logger.debug(f"Logged exchange {entry['exchange_id']} to {daily_path} and {session_path}")

            return True

        except Exception as e:
            # Never crash - just report failure
            self._handle_error(e, "chat logging")
            return False

    def get_daily_log_path(self, date: Optional[datetime] = None) -> Path:
        """
        Get path to daily log file for given date (default: today).

        Args:
            date: Date for the log file (default: today)

        Returns:
            Path to the daily log file
        """
        date = date or datetime.now()
        return self.base_path / "daily" / f"{date.strftime('%Y-%m-%d')}.jsonl"

    def get_session_log_path(self, conversation_id: str) -> Path:
        """
        Get path to session log file for given conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            Path to the session log file
        """
        return self.base_path / "sessions" / f"{conversation_id}.jsonl"

    def get_log_location(self) -> str:
        """
        Return the base path - useful for debugging and {AI} orientation.

        Returns:
            String representation of the base log directory
        """
        return str(self.base_path)

    def _ensure_directories(self) -> None:
        """Ensure daily/ and sessions/ subdirectories exist."""
        try:
            (self.base_path / "daily").mkdir(parents=True, exist_ok=True)
            (self.base_path / "sessions").mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._handle_error(e, "creating log directories")

    def _handle_error(self, error: Exception, context: str) -> None:
        """
        Handle errors without crashing.

        Routes through ErrorHandler if available, otherwise logs to stderr.
        """
        if self.error_handler:
            try:
                from error_handler import ErrorCategory, ErrorSeverity
                self.error_handler.handle_error(
                    error=error,
                    category=ErrorCategory.FILE_OPERATIONS,
                    severity=ErrorSeverity.LOW_DEBUG,
                    context=context,
                    operation="chat_logger"
                )
            except ImportError:
                # Fallback if error_handler imports fail
                self._logger.warning(f"ChatLogger error ({context}): {error}")
        else:
            self._logger.warning(f"ChatLogger error ({context}): {error}")
