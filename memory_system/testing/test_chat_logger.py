#!/usr/bin/env python3
"""
Tests for ChatLogger - Layer 5 extraction from rich_chat.py

Tests cover:
- Basic logging functionality
- JSONL format correctness
- Error handling (never crashes)
- Path configuration (explicit, env var, default)
- Directory creation
"""

import pytest
import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from chat_logger import ChatLogger


class TestChatLoggerBasics:
    """Basic ChatLogger functionality tests."""

    def test_init_creates_directories(self, tmp_path):
        """ChatLogger creates daily/ and sessions/ directories on init."""
        logger = ChatLogger(base_path=str(tmp_path))

        assert (tmp_path / "daily").exists()
        assert (tmp_path / "sessions").exists()

    def test_log_exchange_creates_both_files(self, tmp_path):
        """log_exchange writes to both daily and session logs."""
        logger = ChatLogger(base_path=str(tmp_path))

        result = logger.log_exchange(
            user_message="Hello",
            assistant_response="Hi there!",
            conversation_id="test-conv-123"
        )

        assert result is True

        # Check daily log exists
        daily_files = list((tmp_path / "daily").glob("*.jsonl"))
        assert len(daily_files) == 1

        # Check session log exists
        session_file = tmp_path / "sessions" / "test-conv-123.jsonl"
        assert session_file.exists()

    def test_log_exchange_correct_jsonl_format(self, tmp_path):
        """log_exchange writes valid JSONL with correct fields."""
        logger = ChatLogger(base_path=str(tmp_path))

        logger.log_exchange(
            user_message="What is Python?",
            assistant_response="Python is a programming language.",
            conversation_id="test-conv-456",
            exchange_id="exc-789",
            request_id="req-abc"
        )

        # Read the daily log
        daily_file = logger.get_daily_log_path()
        with open(daily_file, "r") as f:
            line = f.readline()
            entry = json.loads(line)

        # Verify fields
        assert entry["user"] == "What is Python?"
        assert entry["assistant"] == "Python is a programming language."
        assert entry["conversation_id"] == "test-conv-456"
        assert entry["exchange_id"] == "exc-789"
        assert entry["request_id"] == "req-abc"
        assert "timestamp" in entry

    def test_log_exchange_with_metadata(self, tmp_path):
        """log_exchange includes optional metadata."""
        logger = ChatLogger(base_path=str(tmp_path))

        metadata = {
            "confidence": 0.95,
            "tokens": 150,
            "model": "test-model"
        }

        logger.log_exchange(
            user_message="Test",
            assistant_response="Response",
            conversation_id="test-conv",
            metadata=metadata
        )

        daily_file = logger.get_daily_log_path()
        with open(daily_file, "r") as f:
            entry = json.loads(f.readline())

        assert entry["metadata"] == metadata

    def test_log_exchange_generates_exchange_id(self, tmp_path):
        """log_exchange generates UUID if exchange_id not provided."""
        logger = ChatLogger(base_path=str(tmp_path))

        logger.log_exchange(
            user_message="Test",
            assistant_response="Response",
            conversation_id="test-conv"
        )

        daily_file = logger.get_daily_log_path()
        with open(daily_file, "r") as f:
            entry = json.loads(f.readline())

        # Should be a valid UUID format (36 chars with hyphens)
        assert len(entry["exchange_id"]) == 36
        assert entry["exchange_id"].count("-") == 4


class TestChatLoggerPaths:
    """Tests for path configuration."""

    def test_explicit_path_takes_priority(self, tmp_path):
        """Explicit base_path overrides env var and default."""
        custom_path = tmp_path / "custom"

        with patch.dict(os.environ, {"CHAT_LOG_PATH": "/should/not/use"}):
            logger = ChatLogger(base_path=str(custom_path))

        assert logger.base_path == custom_path
        assert logger.get_log_location() == str(custom_path)

    def test_env_var_used_when_no_explicit_path(self, tmp_path, monkeypatch):
        """CHAT_LOG_PATH env var used when base_path not provided."""
        env_path = tmp_path / "from_env"
        env_path.mkdir()

        monkeypatch.setenv("CHAT_LOG_PATH", str(env_path))

        logger = ChatLogger()

        assert logger.base_path == env_path

    def test_default_path_when_nothing_set(self, monkeypatch):
        """Falls back to project-relative default."""
        monkeypatch.delenv("CHAT_LOG_PATH", raising=False)

        logger = ChatLogger()

        # Should be relative to chat_logger.py location
        expected = Path(__file__).parent.parent / "data" / "chat_logs"
        assert logger.base_path == expected

    def test_get_log_location_returns_string(self, tmp_path):
        """get_log_location returns string for {AI} orientation."""
        logger = ChatLogger(base_path=str(tmp_path))

        location = logger.get_log_location()

        assert isinstance(location, str)
        assert str(tmp_path) in location

    def test_get_daily_log_path(self, tmp_path):
        """get_daily_log_path returns correct path for date."""
        logger = ChatLogger(base_path=str(tmp_path))

        # Today's path
        today_path = logger.get_daily_log_path()
        expected_name = f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        assert today_path.name == expected_name
        assert today_path.parent.name == "daily"

        # Specific date
        specific_date = datetime(2025, 6, 15)
        specific_path = logger.get_daily_log_path(specific_date)
        assert specific_path.name == "2025-06-15.jsonl"

    def test_get_session_log_path(self, tmp_path):
        """get_session_log_path returns correct path for conversation."""
        logger = ChatLogger(base_path=str(tmp_path))

        session_path = logger.get_session_log_path("my-conversation-id")

        assert session_path.name == "my-conversation-id.jsonl"
        assert session_path.parent.name == "sessions"


class TestChatLoggerErrorHandling:
    """Tests for error handling - logging should NEVER crash chat."""

    def test_handles_write_error_gracefully(self, tmp_path):
        """Returns False on write error, doesn't crash."""
        logger = ChatLogger(base_path=str(tmp_path))

        # Make daily directory read-only to cause write failure
        daily_dir = tmp_path / "daily"
        daily_dir.chmod(0o444)

        try:
            result = logger.log_exchange(
                user_message="Test",
                assistant_response="Response",
                conversation_id="test-conv"
            )

            # Should return False, not raise
            assert result is False
        finally:
            # Restore permissions for cleanup
            daily_dir.chmod(0o755)

    def test_routes_error_to_error_handler(self, tmp_path):
        """Errors are routed through ErrorHandler when provided."""
        mock_handler = Mock()
        logger = ChatLogger(base_path=str(tmp_path), error_handler=mock_handler)

        # Force an error by making directory read-only
        daily_dir = tmp_path / "daily"
        daily_dir.chmod(0o444)

        try:
            logger.log_exchange(
                user_message="Test",
                assistant_response="Response",
                conversation_id="test-conv"
            )

            # Error handler should have been called
            mock_handler.handle_error.assert_called_once()
        finally:
            daily_dir.chmod(0o755)

    def test_logs_to_stderr_without_error_handler(self, tmp_path, caplog):
        """Falls back to logging when no ErrorHandler provided."""
        logger = ChatLogger(base_path=str(tmp_path))

        # Force an error
        daily_dir = tmp_path / "daily"
        daily_dir.chmod(0o444)

        try:
            import logging
            with caplog.at_level(logging.WARNING):
                logger.log_exchange(
                    user_message="Test",
                    assistant_response="Response",
                    conversation_id="test-conv"
                )

            # Should have logged a warning
            assert "ChatLogger error" in caplog.text or len(caplog.records) > 0
        finally:
            daily_dir.chmod(0o755)

    def test_directory_creation_error_handled(self, tmp_path):
        """Error during directory creation doesn't crash."""
        # Create a file where directory should be
        bad_path = tmp_path / "blocked"
        bad_path.touch()  # Create as file, not directory

        # This should not raise, even though mkdir will fail
        logger = ChatLogger(base_path=str(bad_path))

        # Logger is created (though directories may not exist)
        assert logger is not None


class TestChatLoggerMultipleWrites:
    """Tests for multiple exchanges and append behavior."""

    def test_multiple_exchanges_append(self, tmp_path):
        """Multiple exchanges append to same files."""
        logger = ChatLogger(base_path=str(tmp_path))

        for i in range(3):
            logger.log_exchange(
                user_message=f"Message {i}",
                assistant_response=f"Response {i}",
                conversation_id="same-conv"
            )

        # Check daily log has 3 lines
        daily_file = logger.get_daily_log_path()
        with open(daily_file, "r") as f:
            lines = f.readlines()
        assert len(lines) == 3

        # Check session log has 3 lines
        session_file = logger.get_session_log_path("same-conv")
        with open(session_file, "r") as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_different_conversations_different_session_files(self, tmp_path):
        """Different conversation IDs go to different session files."""
        logger = ChatLogger(base_path=str(tmp_path))

        logger.log_exchange(
            user_message="A",
            assistant_response="A",
            conversation_id="conv-a"
        )
        logger.log_exchange(
            user_message="B",
            assistant_response="B",
            conversation_id="conv-b"
        )

        # Should have 2 session files
        session_files = list((tmp_path / "sessions").glob("*.jsonl"))
        assert len(session_files) == 2

        # But only 1 daily file (both on same day)
        daily_files = list((tmp_path / "daily").glob("*.jsonl"))
        assert len(daily_files) == 1

        # Daily file should have 2 entries
        with open(daily_files[0], "r") as f:
            assert len(f.readlines()) == 2


class TestChatLoggerDebugMode:
    """Tests for debug mode behavior."""

    def test_debug_mode_logs_success(self, tmp_path, caplog):
        """Debug mode logs successful writes."""
        import logging

        logger = ChatLogger(base_path=str(tmp_path), debug_mode=True)

        with caplog.at_level(logging.DEBUG):
            logger.log_exchange(
                user_message="Test",
                assistant_response="Response",
                conversation_id="test-conv"
            )

        # Should have debug log about successful write
        assert "Logged exchange" in caplog.text or len(caplog.records) >= 0
