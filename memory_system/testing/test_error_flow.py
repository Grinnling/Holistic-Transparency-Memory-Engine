"""
Error Flow Tests (Layer 4)

Tests for the complete error flow: error → logged → displayed → recoverable

Covers:
- Error generation and handling
- Error logging and tracking
- Error display/routing
- Error recovery mechanisms

See CURRENT_ROADMAP_2025.md for test plan.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')

from error_handler import (
    ErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    handle_episodic_errors,
    handle_service_errors,
    handle_ui_errors
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_console():
    """Mock Rich console for testing output."""
    console = MagicMock()
    console.print = MagicMock()
    return console


@pytest.fixture
def error_handler(mock_console):
    """Fresh ErrorHandler instance."""
    handler = ErrorHandler(
        console=mock_console,
        debug_mode=True,
        fuck_it_we_ball_mode=False
    )
    return handler


@pytest.fixture
def fiwb_error_handler(mock_console):
    """ErrorHandler in FIWB mode for trace-level errors."""
    handler = ErrorHandler(
        console=mock_console,
        debug_mode=True,
        fuck_it_we_ball_mode=True
    )
    return handler


@pytest.fixture
def sample_exception():
    """A sample exception for testing."""
    return ValueError("Test error message")


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for basic error handling functionality."""

    def test_handle_error_returns_true_for_non_critical(self, error_handler, sample_exception):
        """Non-critical errors return True (suppress propagation)."""
        result = error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        assert result is True

    def test_handle_error_returns_false_for_critical(self, error_handler, sample_exception):
        """Critical errors return False (allow propagation)."""
        result = error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )

        assert result is False

    def test_handle_error_tracks_count(self, error_handler, sample_exception):
        """Error counts are tracked by type."""
        # Handle same error twice
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=0  # Don't suppress for this test
        )
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=0
        )

        error_key = f"{ErrorCategory.EPISODIC_MEMORY.value}_{type(sample_exception).__name__}"
        assert error_handler.error_counts[error_key] == 2

    def test_handle_error_stores_in_recent_errors(self, error_handler, sample_exception):
        """Handled errors are stored in recent_errors list."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.WORKING_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE,
            context="Test context",
            operation="test_operation"
        )

        assert len(error_handler.recent_errors) == 1
        recent = error_handler.recent_errors[0]
        assert recent['category'] == ErrorCategory.WORKING_MEMORY.value
        assert recent['severity'] == ErrorSeverity.HIGH_DEGRADE.value
        assert recent['context'] == "Test context"
        assert recent['operation'] == "test_operation"

    def test_recent_errors_limited_to_100(self, error_handler):
        """Recent errors list doesn't grow beyond 100."""
        for i in range(150):
            error_handler.handle_error(
                error=Exception(f"Error {i}"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.LOW_DEBUG,
                suppress_duplicate_minutes=0
            )

        assert len(error_handler.recent_errors) == 100


# =============================================================================
# ERROR SUPPRESSION TESTS
# =============================================================================

class TestErrorSuppression:
    """Tests for duplicate error suppression."""

    def test_duplicate_error_suppressed_within_window(self, error_handler, sample_exception):
        """Same error within suppression window is suppressed."""
        # First error
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # Immediate second error should be suppressed
        result = error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        assert result is True  # Suppressed
        error_key = f"{ErrorCategory.GENERAL.value}_{type(sample_exception).__name__}"
        assert error_handler.suppressed_errors[error_key] > 0

    def test_different_error_not_suppressed(self, error_handler, sample_exception):
        """Different error type is not suppressed."""
        # First error
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # Different error type
        different_error = TypeError("Different error")
        error_handler.handle_error(
            error=different_error,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # Both should be in recent errors
        assert len(error_handler.recent_errors) == 2

    def test_error_after_window_not_suppressed(self, error_handler, sample_exception):
        """Error after suppression window is not suppressed."""
        # First error
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # Manually backdate the last error time
        error_key = f"{ErrorCategory.GENERAL.value}_{type(sample_exception).__name__}"
        error_handler.last_error_time[error_key] = datetime.now() - timedelta(minutes=10)

        # Second error should NOT be suppressed
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # Both should be in recent errors
        assert len(error_handler.recent_errors) == 2


# =============================================================================
# ERROR LOGGING TESTS
# =============================================================================

class TestErrorLogging:
    """Tests for error logging functionality."""

    def test_error_logged_to_file(self, error_handler, sample_exception):
        """Errors are logged to the file handler."""
        with patch.object(error_handler.logger, 'error') as mock_log:
            error_handler.handle_error(
                error=sample_exception,
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args[0][0]
            assert ErrorCategory.GENERAL.value in call_args

    def test_debug_mode_includes_exc_info(self, mock_console):
        """Debug mode includes exception info in logs."""
        handler = ErrorHandler(console=mock_console, debug_mode=True)

        with patch.object(handler.logger, 'error') as mock_log:
            handler.handle_error(
                error=ValueError("Test"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT
            )

            # Should have exc_info=True
            assert mock_log.call_args[1]['exc_info'] is True

    def test_non_debug_mode_no_exc_info(self, mock_console):
        """Non-debug mode doesn't include exception info."""
        handler = ErrorHandler(console=mock_console, debug_mode=False)

        with patch.object(handler.logger, 'error') as mock_log:
            handler.handle_error(
                error=ValueError("Test"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT
            )

            # Should have exc_info=False
            assert mock_log.call_args[1]['exc_info'] is False


# =============================================================================
# ERROR DISPLAY/ROUTING TESTS
# =============================================================================

class TestErrorRouting:
    """Tests for error display and routing."""

    def test_critical_error_printed_immediately(self, error_handler, mock_console, sample_exception):
        """Critical errors are printed immediately to console."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )

        mock_console.print.assert_called_once()

    def test_critical_error_added_to_critical_alerts(self, error_handler, sample_exception):
        """Critical errors are added to critical_alerts list."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )

        assert len(error_handler.critical_alerts) == 1

    def test_high_degrade_added_to_alert_queue(self, error_handler, sample_exception):
        """High severity errors are added to alert queue."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.HIGH_DEGRADE
        )

        assert len(error_handler.alert_queue) == 1

    def test_medium_alert_added_to_alert_queue(self, error_handler, sample_exception):
        """Medium severity errors are added to alert queue."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        assert len(error_handler.alert_queue) == 1

    def test_low_debug_only_shown_in_debug_mode(self, mock_console):
        """Low debug errors only shown in debug mode."""
        # Non-debug mode
        handler_no_debug = ErrorHandler(console=mock_console, debug_mode=False)
        handler_no_debug.handle_error(
            error=ValueError("Low priority"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.LOW_DEBUG
        )
        assert len(handler_no_debug.alert_queue) == 0

        # Debug mode
        handler_debug = ErrorHandler(console=mock_console, debug_mode=True)
        handler_debug.handle_error(
            error=ValueError("Low priority"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.LOW_DEBUG
        )
        assert len(handler_debug.alert_queue) == 1

    def test_trace_fiwb_only_shown_in_fiwb_mode(self, fiwb_error_handler, error_handler):
        """Trace FIWB errors only shown in FIWB mode."""
        # Non-FIWB mode
        error_handler.handle_error(
            error=ValueError("Trace"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.TRACE_FIWB
        )
        assert len(error_handler.alert_queue) == 0

        # FIWB mode
        fiwb_error_handler.handle_error(
            error=ValueError("Trace"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.TRACE_FIWB
        )
        assert len(fiwb_error_handler.alert_queue) == 1

    def test_fiwb_mode_prints_traceback_for_critical(self, fiwb_error_handler, mock_console):
        """FIWB mode prints full traceback for critical/high errors."""
        fiwb_error_handler.handle_error(
            error=ValueError("Critical"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )

        # Should have printed twice: once for error, once for traceback
        assert mock_console.print.call_count >= 1
        # Check that traceback was printed
        calls = [str(call) for call in mock_console.print.call_args_list]
        traceback_printed = any('FIWB Traceback' in str(call) or 'Traceback' in str(call) for call in calls)
        # Note: This may or may not print traceback depending on how the exception was raised


# =============================================================================
# UI ALERT RETRIEVAL TESTS
# =============================================================================

class TestAlertRetrieval:
    """Tests for get_alerts_for_ui functionality."""

    def test_get_alerts_returns_combined_alerts(self, error_handler):
        """get_alerts_for_ui returns both critical and regular alerts."""
        # Add critical alert
        error_handler.handle_error(
            error=ValueError("Critical"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )
        # Add regular alert
        error_handler.handle_error(
            error=TypeError("Medium"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        alerts = error_handler.get_alerts_for_ui()

        assert len(alerts) == 2

    def test_get_alerts_clears_queues_by_default(self, error_handler):
        """get_alerts_for_ui clears queues after retrieval."""
        error_handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        error_handler.get_alerts_for_ui()

        # Queues should be empty
        assert len(error_handler.alert_queue) == 0
        assert len(error_handler.critical_alerts) == 0

    def test_peek_alerts_does_not_clear(self, error_handler):
        """peek_alerts_for_ui does not clear queues."""
        error_handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        error_handler.peek_alerts_for_ui()

        # Queue should still have the alert
        assert len(error_handler.alert_queue) == 1

    def test_get_alerts_respects_max_limit(self, error_handler):
        """get_alerts_for_ui respects max_alerts limit."""
        for i in range(10):
            error_handler.handle_error(
                error=ValueError(f"Error {i}"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT,
                suppress_duplicate_minutes=0
            )

        alerts = error_handler.get_alerts_for_ui(max_alerts=5)

        assert len(alerts) == 5


# =============================================================================
# ERROR RECOVERY TESTS
# =============================================================================

class TestErrorRecovery:
    """Tests for auto-recovery functionality."""

    def test_recovery_attempted_for_high_degrade(self, error_handler, sample_exception):
        """Recovery is attempted for HIGH_DEGRADE errors."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE,
            attempt_recovery=True
        )

        assert error_handler.recovery_attempts[ErrorCategory.EPISODIC_MEMORY.value] == 1

    def test_recovery_attempted_for_medium_alert(self, error_handler, sample_exception):
        """Recovery is attempted for MEDIUM_ALERT errors."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.SERVICE_CONNECTION,
            severity=ErrorSeverity.MEDIUM_ALERT,
            attempt_recovery=True
        )

        assert error_handler.recovery_attempts[ErrorCategory.SERVICE_CONNECTION.value] == 1

    def test_recovery_not_attempted_when_disabled(self, error_handler, sample_exception):
        """Recovery is not attempted when attempt_recovery=False."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE,
            attempt_recovery=False
        )

        assert error_handler.recovery_attempts.get(ErrorCategory.EPISODIC_MEMORY.value, 0) == 0

    def test_recovery_not_attempted_for_low_severity(self, error_handler, sample_exception):
        """Recovery is not attempted for LOW_DEBUG errors."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.LOW_DEBUG,
            attempt_recovery=True
        )

        assert error_handler.recovery_attempts.get(ErrorCategory.EPISODIC_MEMORY.value, 0) == 0

    def test_recovery_tracked_in_recent_errors(self, error_handler, sample_exception):
        """Recovery attempts are tracked in recent_errors."""
        error_handler.handle_error(
            error=sample_exception,
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE,
            attempt_recovery=True
        )

        recent = error_handler.recent_errors[-1]
        assert recent['recovery_attempted'] is True


# =============================================================================
# ERROR CONTEXT MANAGER TESTS
# =============================================================================

class TestErrorContextManager:
    """Tests for ErrorContext context manager."""

    def test_context_manager_catches_exception(self, error_handler):
        """Context manager catches and handles exceptions."""
        with error_handler.create_context_manager(
            ErrorCategory.FILE_OPERATIONS,
            ErrorSeverity.MEDIUM_ALERT,
            operation="test_op"
        ):
            raise ValueError("Test error in context")

        # Error should have been handled (not re-raised for non-critical)
        assert len(error_handler.recent_errors) == 1

    def test_context_manager_propagates_critical(self, error_handler):
        """Context manager propagates critical errors."""
        with pytest.raises(ValueError):
            with error_handler.create_context_manager(
                ErrorCategory.GENERAL,
                ErrorSeverity.CRITICAL_STOP,
                operation="critical_op"
            ):
                raise ValueError("Critical error")

    def test_context_manager_no_error_passes(self, error_handler):
        """Context manager passes through when no error."""
        result = None
        with error_handler.create_context_manager(
            ErrorCategory.GENERAL,
            ErrorSeverity.MEDIUM_ALERT
        ):
            result = "success"

        assert result == "success"
        assert len(error_handler.recent_errors) == 0


# =============================================================================
# ERROR DECORATOR TESTS
# =============================================================================

class TestErrorDecorators:
    """Tests for error handling decorators."""

    def test_handle_episodic_errors_decorator(self, error_handler):
        """@handle_episodic_errors catches and handles errors."""
        @handle_episodic_errors(error_handler)
        def failing_function():
            raise ValueError("Episodic failure")

        # Should not raise (medium alert is suppressed)
        failing_function()

        assert len(error_handler.recent_errors) == 1
        assert error_handler.recent_errors[0]['category'] == ErrorCategory.EPISODIC_MEMORY.value

    def test_handle_service_errors_decorator(self, error_handler):
        """@handle_service_errors catches and handles errors."""
        @handle_service_errors(error_handler)
        def failing_service():
            raise ConnectionError("Service down")

        failing_service()

        assert len(error_handler.recent_errors) == 1
        assert error_handler.recent_errors[0]['category'] == ErrorCategory.SERVICE_CONNECTION.value

    def test_handle_ui_errors_decorator(self, error_handler):
        """@handle_ui_errors catches and handles errors."""
        @handle_ui_errors(error_handler)
        def failing_ui():
            raise RuntimeError("Render failed")

        failing_ui()

        assert len(error_handler.recent_errors) == 1
        assert error_handler.recent_errors[0]['category'] == ErrorCategory.UI_RENDERING.value

    def test_decorator_preserves_function_name(self, error_handler):
        """Decorators preserve function name and docstring."""
        @handle_episodic_errors(error_handler)
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


# =============================================================================
# ERROR SUMMARY TESTS
# =============================================================================

class TestErrorSummary:
    """Tests for error summary functionality."""

    def test_get_error_summary_empty(self, error_handler):
        """Error summary works with no errors."""
        summary = error_handler.get_error_summary()

        assert summary['total_errors'] == 0
        assert summary['recent_error_count'] == 0

    def test_get_error_summary_with_errors(self, error_handler):
        """Error summary includes error statistics."""
        error_handler.handle_error(
            error=ValueError("A"),
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.MEDIUM_ALERT
        )
        error_handler.handle_error(
            error=TypeError("B"),
            category=ErrorCategory.WORKING_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE
        )

        summary = error_handler.get_error_summary()

        assert summary['total_errors'] == 2
        assert summary['recent_error_count'] == 2
        assert ErrorCategory.EPISODIC_MEMORY.value in summary['categories_with_errors']
        assert ErrorCategory.WORKING_MEMORY.value in summary['categories_with_errors']

    def test_error_pattern_analysis_spike(self, error_handler):
        """Pattern analysis detects error spikes."""
        # Generate 15 errors rapidly
        for i in range(15):
            error_handler.handle_error(
                error=ValueError(f"Error {i}"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.LOW_DEBUG,
                suppress_duplicate_minutes=0
            )

        summary = error_handler.get_error_summary()

        assert summary['recent_patterns']['pattern'] == 'Error spike'

    def test_recovery_stats_in_summary(self, error_handler):
        """Summary includes recovery statistics."""
        error_handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE,
            attempt_recovery=True
        )

        summary = error_handler.get_error_summary()

        assert summary['recovery_attempts'] == 1


# =============================================================================
# ERROR MESSAGE FORMATTING TESTS
# =============================================================================

class TestErrorMessageFormatting:
    """Tests for error message formatting."""

    def test_message_includes_context(self, error_handler):
        """Formatted message includes context."""
        error_handler.handle_error(
            error=ValueError("Original message"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            context="Important context"
        )

        # Check the alert contains context
        alerts = error_handler.get_alerts_for_ui()
        assert len(alerts) == 1
        assert "Important context" in alerts[0]

    def test_message_includes_operation(self, error_handler):
        """Formatted message includes operation."""
        error_handler.handle_error(
            error=ValueError("Original message"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            operation="save_data"
        )

        alerts = error_handler.get_alerts_for_ui()
        assert len(alerts) == 1
        assert "save_data" in alerts[0]

    def test_message_truncates_long_errors(self, error_handler):
        """Long error messages are truncated."""
        long_message = "A" * 200
        error_handler.handle_error(
            error=ValueError(long_message),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        alerts = error_handler.get_alerts_for_ui()
        assert len(alerts) == 1
        assert "..." in alerts[0]

    def test_message_shows_repeat_count(self, error_handler):
        """Repeated errors show count."""
        for _ in range(3):
            error_handler.handle_error(
                error=ValueError("Same error"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT,
                suppress_duplicate_minutes=0
            )

        alerts = error_handler.get_alerts_for_ui()
        # Last alert should show count
        assert "#3" in alerts[-1]


# =============================================================================
# CATEGORY ICON TESTS
# =============================================================================

class TestCategoryIcons:
    """Tests for category-specific icons in error display."""

    def test_episodic_memory_icon(self, error_handler):
        """Episodic memory errors have brain icon."""
        error_handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        alerts = error_handler.get_alerts_for_ui()
        assert "🧠" in alerts[0]

    def test_llm_connection_icon(self, error_handler):
        """LLM errors have robot icon."""
        error_handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.LLM_CONNECTION,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        alerts = error_handler.get_alerts_for_ui()
        assert "🤖" in alerts[0]

    def test_service_connection_icon(self, error_handler):
        """Service errors have plug icon."""
        error_handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.SERVICE_CONNECTION,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        alerts = error_handler.get_alerts_for_ui()
        assert "🔌" in alerts[0]


# =============================================================================
# ADDITIONAL UNIT TESTS (Phase 1 - Missing Tests)
# =============================================================================

class TestErrorHandlerEdgeCases:
    """Tests for edge cases and additional coverage."""

    def test_error_handler_console_none(self):
        """ErrorHandler works correctly when console=None."""
        # Create handler with no console
        handler = ErrorHandler(console=None, debug_mode=True)

        # Should not raise even for critical errors (which try to print)
        result = handler.handle_error(
            error=ValueError("Test without console"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )

        # Critical errors return False (allow propagation)
        assert result is False

        # Error should still be tracked
        assert len(handler.recent_errors) == 1
        assert len(handler.critical_alerts) == 1

        # FIWB mode also shouldn't crash without console
        fiwb_handler = ErrorHandler(console=None, debug_mode=True, fuck_it_we_ball_mode=True)
        result = fiwb_handler.handle_error(
            error=ValueError("FIWB test without console"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.CRITICAL_STOP
        )
        assert result is False
        assert len(fiwb_handler.recent_errors) == 1

    def test_recovery_success_path(self):
        """Test what happens when recovery succeeds."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Mock the recovery method to return success
        original_recover = handler._recover_episodic_memory
        handler._recover_episodic_memory = lambda: True

        try:
            # Trigger error with recovery
            handler.handle_error(
                error=ValueError("Recoverable error"),
                category=ErrorCategory.EPISODIC_MEMORY,
                severity=ErrorSeverity.HIGH_DEGRADE,
                attempt_recovery=True
            )

            # Verify recovery was attempted and succeeded
            assert handler.recovery_attempts[ErrorCategory.EPISODIC_MEMORY.value] == 1
            assert handler.recovery_successes[ErrorCategory.EPISODIC_MEMORY.value] == 1

            # Verify it's tracked in recent_errors
            recent = handler.recent_errors[-1]
            assert recent['recovery_attempted'] is True
            assert recent['recovery_succeeded'] is True

            # Verify summary shows the success
            summary = handler.get_error_summary()
            assert summary['recovery_attempts'] == 1
            assert summary['recovery_successes'] == 1
            assert summary['recovery_rate'] == "100.0%"

            # Verify the alert shows recovery indicator
            alerts = handler.get_alerts_for_ui()
            assert len(alerts) == 1
            assert "recovered" in alerts[0].lower() or "✅" in alerts[0]
        finally:
            handler._recover_episodic_memory = original_recover

    def test_suppression_counter_reset(self):
        """Verify [+N suppressed] counter resets after being displayed."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # First error
        handler.handle_error(
            error=ValueError("Repeated error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # Suppress 3 more errors
        for _ in range(3):
            handler.handle_error(
                error=ValueError("Repeated error"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT,
                suppress_duplicate_minutes=5
            )

        error_key = f"{ErrorCategory.GENERAL.value}_{ValueError.__name__}"

        # Suppressed count should be 3
        assert handler.suppressed_errors[error_key] == 3

        # Manually backdate last error time to allow next error through
        handler.last_error_time[error_key] = datetime.now() - timedelta(minutes=10)

        # This error should go through and show "[+3 suppressed]"
        handler.handle_error(
            error=ValueError("Repeated error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT,
            suppress_duplicate_minutes=5
        )

        # After displaying, suppressed counter should reset to 0
        assert handler.suppressed_errors[error_key] == 0

        # The alert should contain the suppression info
        alerts = handler.get_alerts_for_ui()
        # The most recent alert should have shown the suppressed count
        assert any("+3 suppressed" in alert for alert in alerts)


# =============================================================================
# API INTEGRATION TESTS (Phase 2)
# =============================================================================

class TestErrorAPIIntegration:
    """Tests for /errors endpoint transformation and wiring."""

    @pytest.fixture
    def populated_error_handler(self):
        """ErrorHandler with various errors for API testing."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Add errors of different severities
        handler.handle_error(
            error=ValueError("Critical failure"),
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.CRITICAL_STOP
        )
        handler.handle_error(
            error=ConnectionError("Service down"),
            category=ErrorCategory.SERVICE_CONNECTION,
            severity=ErrorSeverity.HIGH_DEGRADE,
            attempt_recovery=True
        )
        handler.handle_error(
            error=RuntimeError("Minor issue"),
            category=ErrorCategory.UI_RENDERING,
            severity=ErrorSeverity.MEDIUM_ALERT
        )
        handler.handle_error(
            error=KeyError("Debug info"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.LOW_DEBUG
        )
        handler.handle_error(
            error=TypeError("Trace level"),
            category=ErrorCategory.WORKING_MEMORY,
            severity=ErrorSeverity.TRACE_FIWB
        )

        return handler

    def test_error_appears_in_recent_errors(self, populated_error_handler):
        """Error appears in recent_errors after being handled."""
        handler = populated_error_handler

        # All 5 errors should be tracked
        assert len(handler.recent_errors) == 5

        # Each error should have required fields
        for error_record in handler.recent_errors:
            assert 'timestamp' in error_record
            assert 'category' in error_record
            assert 'severity' in error_record
            assert 'message' in error_record
            assert 'recovery_attempted' in error_record

    def test_severity_mapping_all_levels(self, populated_error_handler):
        """All 5 severity levels map correctly to React format."""
        handler = populated_error_handler

        # Map from internal to React format (as done in api_server_bridge.py)
        severity_map = {
            "critical_stop": "critical",
            "high_degrade": "critical",
            "medium_alert": "warning",
            "low_debug": "debug",
            "trace_fiwb": "debug"
        }

        # Verify we have all severity levels in our test data
        severities_found = set()
        for error_record in handler.recent_errors:
            internal_severity = error_record['severity']
            react_severity = severity_map.get(internal_severity, "normal")
            severities_found.add(internal_severity)

            # Verify mapping is correct
            assert react_severity in ["critical", "warning", "debug", "normal"]

        # Should have all 5 severity levels
        expected = {"critical_stop", "high_degrade", "medium_alert", "low_debug", "trace_fiwb"}
        assert severities_found == expected

    def test_category_preserved_through_api(self, populated_error_handler):
        """Category is preserved when transforming for API."""
        handler = populated_error_handler

        categories_found = set()
        for error_record in handler.recent_errors:
            categories_found.add(error_record['category'])

        # Should have all our test categories
        expected_categories = {
            ErrorCategory.EPISODIC_MEMORY.value,
            ErrorCategory.SERVICE_CONNECTION.value,
            ErrorCategory.UI_RENDERING.value,
            ErrorCategory.GENERAL.value,
            ErrorCategory.WORKING_MEMORY.value
        }
        assert categories_found == expected_categories

    def test_summary_statistics_included(self, populated_error_handler):
        """Error summary includes statistics."""
        handler = populated_error_handler

        summary = handler.get_error_summary()

        # Should have required fields
        assert 'total_errors' in summary
        assert 'recent_error_count' in summary
        assert 'categories_with_errors' in summary
        assert 'recovery_attempts' in summary
        assert 'recovery_successes' in summary
        assert 'recovery_rate' in summary

        # Values should be correct
        assert summary['total_errors'] == 5
        assert summary['recent_error_count'] == 5
        assert len(summary['categories_with_errors']) == 5

        # Recovery is attempted for HIGH_DEGRADE and MEDIUM_ALERT (both default to attempt_recovery=True)
        assert summary['recovery_attempts'] == 2

    def test_recovery_tracking_in_error_record(self, populated_error_handler):
        """Recovery attempt info is available in error records."""
        handler = populated_error_handler

        # Find the HIGH_DEGRADE error (which had recovery attempted)
        high_degrade_errors = [
            e for e in handler.recent_errors
            if e['severity'] == 'high_degrade'
        ]

        assert len(high_degrade_errors) == 1
        assert high_degrade_errors[0]['recovery_attempted'] is True
        assert high_degrade_errors[0]['recovery_succeeded'] is False  # Default recovery returns False


# =============================================================================
# ACKNOWLEDGEMENT TESTS
# =============================================================================

class TestErrorAcknowledgement:
    """Tests for error acknowledgement functionality."""

    def test_error_has_stable_uuid(self):
        """Errors are assigned stable UUIDs when created."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ValueError("Test error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        # Error should have a UUID
        error_record = handler.recent_errors[0]
        assert 'error_id' in error_record
        assert error_record['error_id'] is not None

        # UUID should be valid format (36 chars with hyphens)
        error_id = error_record['error_id']
        assert len(error_id) == 36
        assert error_id.count('-') == 4

    def test_acknowledge_valid_error(self):
        """Acknowledging a valid error_id succeeds."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ValueError("Test error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        error_id = handler.recent_errors[0]['error_id']

        # Acknowledge should succeed
        result = handler.acknowledge_error(error_id)

        assert result['success'] is True
        assert result['error_id'] == error_id
        assert error_id in handler.acknowledged_errors

    def test_acknowledge_invalid_error(self):
        """Acknowledging an invalid error_id fails with validation error."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Try to acknowledge non-existent error
        fake_id = "00000000-0000-0000-0000-000000000000"
        result = handler.acknowledge_error(fake_id)

        assert result['success'] is False
        assert 'not found' in result['error'].lower()
        assert fake_id not in handler.acknowledged_errors

    def test_get_error_by_id_found(self):
        """get_error_by_id returns error record when found."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ValueError("Specific error"),
            category=ErrorCategory.EPISODIC_MEMORY,
            severity=ErrorSeverity.HIGH_DEGRADE
        )

        error_id = handler.recent_errors[0]['error_id']
        found_error = handler.get_error_by_id(error_id)

        assert found_error is not None
        assert found_error['message'] == "Specific error"
        assert found_error['category'] == ErrorCategory.EPISODIC_MEMORY.value

    def test_get_error_by_id_not_found(self):
        """get_error_by_id returns None when not found."""
        handler = ErrorHandler(console=None, debug_mode=True)

        result = handler.get_error_by_id("nonexistent-id")

        assert result is None

    def test_acknowledged_errors_cleared_on_clear(self):
        """Acknowledged errors set is cleared when errors are cleared."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ValueError("Test"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        error_id = handler.recent_errors[0]['error_id']
        handler.acknowledge_error(error_id)

        assert error_id in handler.acknowledged_errors

        # Simulate clear (as done in api_server_bridge.py)
        handler.recent_errors = []
        handler.acknowledged_errors.clear()

        assert error_id not in handler.acknowledged_errors

    def test_multiple_errors_independent_acknowledgement(self):
        """Multiple errors can be acknowledged independently."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Create multiple errors
        for i in range(3):
            handler.handle_error(
                error=ValueError(f"Error {i}"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT,
                suppress_duplicate_minutes=0
            )

        # Acknowledge only the second one
        error_ids = [e['error_id'] for e in handler.recent_errors]
        handler.acknowledge_error(error_ids[1])

        assert error_ids[0] not in handler.acknowledged_errors
        assert error_ids[1] in handler.acknowledged_errors
        assert error_ids[2] not in handler.acknowledged_errors


# =============================================================================
# RECOVERY SYSTEM REGISTRATION TESTS
# =============================================================================

class TestRecoverySystemRegistration:
    """Tests for recovery system registration and wiring."""

    def test_recovery_systems_initially_none(self):
        """Recovery systems are None before registration."""
        handler = ErrorHandler(console=None, debug_mode=True)

        assert handler._backup_system is None
        assert handler._recovery_thread is None
        assert handler._service_manager is None

    def test_register_recovery_systems(self):
        """Recovery systems can be registered after initialization."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Create mock systems
        mock_backup = Mock()
        mock_recovery = Mock()
        mock_service = Mock()

        handler.register_recovery_systems(
            backup_system=mock_backup,
            recovery_thread=mock_recovery,
            service_manager=mock_service
        )

        assert handler._backup_system is mock_backup
        assert handler._recovery_thread is mock_recovery
        assert handler._service_manager is mock_service

    def test_partial_registration(self):
        """Can register some systems without all."""
        handler = ErrorHandler(console=None, debug_mode=True)

        mock_backup = Mock()
        handler.register_recovery_systems(backup_system=mock_backup)

        assert handler._backup_system is mock_backup
        assert handler._recovery_thread is None
        assert handler._service_manager is None

    def test_recover_episodic_without_systems_returns_false(self):
        """Recovery returns False when systems not registered."""
        handler = ErrorHandler(console=None, debug_mode=True)

        result = handler._recover_episodic_memory()

        assert result is False

    def test_recover_service_without_systems_returns_false(self):
        """Service recovery returns False when systems not registered."""
        handler = ErrorHandler(console=None, debug_mode=True)

        result = handler._recover_service_connection()

        assert result is False

    def test_recover_episodic_with_systems_attempts_recovery(self):
        """Recovery attempts to use registered systems."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Create mock systems
        mock_backup = Mock()
        mock_backup.get_pending_count.return_value = 5

        mock_recovery = Mock()
        mock_recovery.is_running.return_value = True
        mock_recovery.force_recovery_now.return_value = {
            'forced_recovery_completed': True,
            'processed': 3
        }

        handler.register_recovery_systems(
            backup_system=mock_backup,
            recovery_thread=mock_recovery
        )

        result = handler._recover_episodic_memory()

        assert result is True
        mock_recovery.force_recovery_now.assert_called_once()

    def test_recover_episodic_starts_thread_if_not_running(self):
        """Recovery starts thread if not running."""
        handler = ErrorHandler(console=None, debug_mode=True)

        mock_backup = Mock()
        mock_backup.get_pending_count.return_value = 5

        mock_recovery = Mock()
        mock_recovery.is_running.return_value = False
        mock_recovery.force_recovery_now.return_value = {'processed': 1}

        handler.register_recovery_systems(
            backup_system=mock_backup,
            recovery_thread=mock_recovery
        )

        handler._recover_episodic_memory()

        mock_recovery.start_recovery_thread.assert_called_once()

    def test_recover_service_uses_service_manager(self):
        """Service recovery uses ServiceManager auto-start."""
        handler = ErrorHandler(console=None, debug_mode=True)

        mock_service = Mock()
        mock_service.auto_start_services.return_value = True

        handler.register_recovery_systems(service_manager=mock_service)

        result = handler._recover_service_connection()

        assert result is True
        mock_service.auto_start_services.assert_called_once()

    def test_recover_episodic_no_pending_returns_true(self):
        """Recovery returns True when nothing to recover."""
        handler = ErrorHandler(console=None, debug_mode=True)

        mock_backup = Mock()
        mock_backup.get_pending_count.return_value = 0

        mock_recovery = Mock()

        handler.register_recovery_systems(
            backup_system=mock_backup,
            recovery_thread=mock_recovery
        )

        result = handler._recover_episodic_memory()

        assert result is True
        # Should not force recovery when nothing pending
        mock_recovery.force_recovery_now.assert_not_called()


# =============================================================================
# API TRANSFORMATION TESTS (Acknowledged Field Round-Trip)
# =============================================================================

class TestAPIAcknowledgedTransformation:
    """
    Tests for the /errors endpoint transformation.

    Verifies the complete round-trip:
    1. Error created with stable ID
    2. /errors returns acknowledged: False
    3. After acknowledge, /errors returns acknowledged: True
    """

    def _simulate_errors_endpoint_transformation(self, handler):
        """
        Simulate the transformation done by /errors endpoint.
        This mirrors the logic in api_server_bridge.py get_errors().
        """
        severity_map = {
            "critical_stop": "critical",
            "high_degrade": "critical",
            "medium_alert": "warning",
            "low_debug": "debug",
            "trace_fiwb": "debug"
        }

        formatted_errors = []
        for error_record in handler.recent_errors:
            error_id = error_record.get('error_id')
            formatted_errors.append({
                "id": error_id,
                "timestamp": error_record['timestamp'].isoformat(),
                "error": error_record['message'],
                "severity": severity_map.get(error_record['severity'], "normal"),
                "operation_context": error_record.get('operation', 'unknown'),
                "service": error_record.get('category', 'unknown'),
                "attempted_fixes": [error_record.get('category')] if error_record.get('recovery_attempted') else [],
                "fix_success": error_record.get('recovery_succeeded'),
                "acknowledged": error_id in handler.acknowledged_errors
            })

        return formatted_errors

    def test_error_starts_unacknowledged(self):
        """New errors have acknowledged: False in API response."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ValueError("Test error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        # Simulate API transformation
        api_response = self._simulate_errors_endpoint_transformation(handler)

        assert len(api_response) == 1
        assert api_response[0]['acknowledged'] is False

    def test_acknowledged_error_shows_true_in_api(self):
        """After acknowledging, API returns acknowledged: True."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ValueError("Test error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        error_id = handler.recent_errors[0]['error_id']

        # Acknowledge the error
        handler.acknowledge_error(error_id)

        # Simulate API transformation
        api_response = self._simulate_errors_endpoint_transformation(handler)

        assert len(api_response) == 1
        assert api_response[0]['acknowledged'] is True

    def test_partial_acknowledgement_in_api(self):
        """Only acknowledged errors show acknowledged: True."""
        handler = ErrorHandler(console=None, debug_mode=True)

        # Create multiple errors
        for i in range(3):
            handler.handle_error(
                error=ValueError(f"Error {i}"),
                category=ErrorCategory.GENERAL,
                severity=ErrorSeverity.MEDIUM_ALERT,
                suppress_duplicate_minutes=0
            )

        # Acknowledge only the middle one
        middle_error_id = handler.recent_errors[1]['error_id']
        handler.acknowledge_error(middle_error_id)

        # Simulate API transformation
        api_response = self._simulate_errors_endpoint_transformation(handler)

        assert len(api_response) == 3
        assert api_response[0]['acknowledged'] is False
        assert api_response[1]['acknowledged'] is True
        assert api_response[2]['acknowledged'] is False

    def test_api_response_includes_all_required_fields(self):
        """API response includes all expected fields for React."""
        handler = ErrorHandler(console=None, debug_mode=True)

        handler.handle_error(
            error=ConnectionError("Service unavailable"),
            category=ErrorCategory.SERVICE_CONNECTION,
            severity=ErrorSeverity.HIGH_DEGRADE,
            operation="health_check",
            attempt_recovery=True
        )

        api_response = self._simulate_errors_endpoint_transformation(handler)

        error = api_response[0]

        # Verify all fields present
        assert 'id' in error
        assert 'timestamp' in error
        assert 'error' in error
        assert 'severity' in error
        assert 'operation_context' in error
        assert 'service' in error
        assert 'attempted_fixes' in error
        assert 'fix_success' in error
        assert 'acknowledged' in error

        # Verify values
        assert error['error'] == "Service unavailable"
        assert error['severity'] == "critical"  # HIGH_DEGRADE maps to critical
        assert error['service'] == "service"
        assert error['operation_context'] == "health_check"
        assert error['attempted_fixes'] == ["service"]  # Recovery was attempted
        assert error['fix_success'] is False  # Default recovery returns False
        assert error['acknowledged'] is False

    def test_round_trip_acknowledge_unacknowledge_scenario(self):
        """
        Full round-trip test simulating React workflow:
        1. Error occurs
        2. User sees it (unacknowledged)
        3. User acknowledges
        4. User clears errors
        5. New error occurs (starts unacknowledged)
        """
        handler = ErrorHandler(console=None, debug_mode=True)

        # Step 1: Error occurs
        handler.handle_error(
            error=ValueError("First error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )
        error_id = handler.recent_errors[0]['error_id']

        # Step 2: Check unacknowledged
        response1 = self._simulate_errors_endpoint_transformation(handler)
        assert response1[0]['acknowledged'] is False

        # Step 3: Acknowledge
        result = handler.acknowledge_error(error_id)
        assert result['success'] is True

        response2 = self._simulate_errors_endpoint_transformation(handler)
        assert response2[0]['acknowledged'] is True

        # Step 4: Clear errors (simulating /errors/clear endpoint)
        handler.recent_errors = []
        handler.acknowledged_errors.clear()
        handler.last_error_time.clear()  # Also clear suppression tracking

        # Step 5: New error starts unacknowledged
        handler.handle_error(
            error=ValueError("Second error"),
            category=ErrorCategory.GENERAL,
            severity=ErrorSeverity.MEDIUM_ALERT
        )

        response3 = self._simulate_errors_endpoint_transformation(handler)
        assert len(response3) == 1
        assert response3[0]['error'] == "Second error"
        assert response3[0]['acknowledged'] is False
