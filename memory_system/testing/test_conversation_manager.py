"""
ConversationManager Tests (Layer 3: Memory Lifecycle)

Tests for ConversationManager covering:
- Unit tests (isolated logic)
- Integration tests (with mocked services)
- OZOLITH verification tests (memory event logging)
- Error handling tests (graceful degradation)

See TEST_CONVERSATION_MANAGER_REQUIREMENTS.md for test plan.
"""

import pytest
import sys
import uuid
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

sys.path.insert(0, '/home/grinnling/Development/CODE_IMPLEMENTATION')


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_service_manager():
    """ServiceManager that reports all services healthy."""
    manager = MagicMock()
    manager.check_service_health.return_value = True
    manager.services = {
        'working_memory': 'http://localhost:8001',
        'episodic_memory': 'http://localhost:8002'
    }
    return manager


@pytest.fixture
def mock_unhealthy_service_manager():
    """ServiceManager that reports all services unhealthy."""
    manager = MagicMock()
    manager.check_service_health.return_value = False
    manager.services = {
        'working_memory': 'http://localhost:8001',
        'episodic_memory': 'http://localhost:8002'
    }
    return manager


@pytest.fixture
def mock_error_handler():
    """ErrorHandler that tracks calls."""
    handler = MagicMock()
    handler.calls = []

    def track_error(error, category, severity, context=None, operation=None):
        handler.calls.append({
            'error': error,
            'category': category,
            'severity': severity,
            'context': context,
            'operation': operation
        })

    handler.handle_error.side_effect = track_error
    return handler


@pytest.fixture
def mock_orchestrator():
    """ConversationOrchestrator that tracks calls."""
    orch = MagicMock()
    orch.create_root_context.return_value = "CTX-test-123"
    orch.add_exchange.return_value = "EXCH-test-456"
    orch.get_active_context_id.return_value = "CTX-test-123"
    orch.get_context_for_llm.return_value = [
        {'user': 'Hello', 'assistant': 'Hi there!', 'exchange_id': 'EXCH-1', 'source': 'working_memory'},
        {'user': 'Help with code', 'assistant': 'Sure!', 'exchange_id': 'EXCH-2', 'source': 'current_session'}
    ]
    return orch


@pytest.fixture
def mock_ozolith():
    """Mock Ozolith that tracks append calls."""
    ozolith = MagicMock()
    ozolith.events = []

    def track_event(event_type, context_id, actor, payload):
        ozolith.events.append({
            'event_type': event_type,
            'context_id': context_id,
            'actor': actor,
            'payload': payload
        })

    ozolith.append.side_effect = track_event
    return ozolith


@pytest.fixture
def conversation_manager(mock_service_manager, mock_error_handler, mock_orchestrator):
    """Fresh ConversationManager with all dependencies mocked."""
    from conversation_manager import ConversationManager, reset_conversation_manager

    # Reset any global state
    reset_conversation_manager()

    manager = ConversationManager(
        service_manager=mock_service_manager,
        error_handler=mock_error_handler,
        orchestrator=mock_orchestrator
    )
    return manager


@pytest.fixture
def sample_episodic_conversations():
    """What episodic memory API returns for list."""
    return {
        'conversations': [
            {'conversation_id': 'conv-1-full-uuid-here', 'created_at': '2025-12-15T10:00:00Z', 'exchange_count': 5},
            {'conversation_id': 'conv-2-full-uuid-here', 'created_at': '2025-12-14T14:30:00Z', 'exchange_count': 12}
        ]
    }


@pytest.fixture
def sample_conversation_history():
    """What episodic memory returns for a specific conversation."""
    return {
        'conversation': {
            'exchanges': [
                {'exchange_id': 'EXCH-1', 'user_input': 'Hello', 'assistant_response': 'Hi there!', 'timestamp': '2025-12-15T10:00:00Z'},
                {'exchange_id': 'EXCH-2', 'user_input': 'Help with bug', 'assistant_response': 'What bug?', 'timestamp': '2025-12-15T10:01:00Z'}
            ]
        }
    }


# =============================================================================
# UNIT TESTS (Isolated Logic)
# =============================================================================

class TestConversationManagerUnit:
    """Unit tests for ConversationManager - no external service calls."""

    def test_init_requires_error_handler(self, mock_service_manager, mock_orchestrator):
        """Error handler is required - no silent errors."""
        from conversation_manager import ConversationManager

        with pytest.raises(ValueError, match="error_handler is required"):
            ConversationManager(
                service_manager=mock_service_manager,
                error_handler=None,
                orchestrator=mock_orchestrator
            )

    def test_init_generates_conversation_id(self, conversation_manager):
        """Conversation ID is a valid UUID on init."""
        conv_id = conversation_manager.conversation_id

        assert conv_id is not None
        # Should be a valid UUID
        uuid.UUID(conv_id)  # Raises if invalid

    def test_start_new_conversation_generates_new_uuid(self, conversation_manager):
        """Starting new conversation generates fresh UUID."""
        old_id = conversation_manager.conversation_id

        new_id = conversation_manager.start_new_conversation(task_description="Test task")

        assert new_id != old_id
        uuid.UUID(new_id)  # Validates UUID format

    def test_start_new_conversation_calls_orchestrator(self, conversation_manager, mock_orchestrator):
        """Starting new conversation creates root context via orchestrator."""
        conversation_manager.start_new_conversation(task_description="Test task")

        mock_orchestrator.create_root_context.assert_called_once()
        call_kwargs = mock_orchestrator.create_root_context.call_args[1]
        assert call_kwargs['task_description'] == "Test task"
        assert call_kwargs['created_by'] == "human"

    def test_start_new_conversation_clears_history(self, conversation_manager):
        """Starting new conversation clears local history."""
        # Add some history
        conversation_manager.conversation_history = [
            {'user': 'Old message', 'assistant': 'Old response'}
        ]

        conversation_manager.start_new_conversation()

        assert len(conversation_manager.conversation_history) == 0

    def test_get_recent_context_hint_empty_history(self, conversation_manager):
        """Returns empty string when < 2 exchanges."""
        conversation_manager.conversation_history = [
            {'user': 'Hello', 'assistant': 'Hi'}
        ]

        hint = conversation_manager.get_recent_context_hint()

        assert hint == ""

    def test_get_recent_context_hint_extracts_topics(self, conversation_manager):
        """Extracts bug/feature/error keywords from recent exchanges."""
        conversation_manager.conversation_history = [
            {'user': 'I found a bug in the login function', 'assistant': 'Tell me more'},
            {'user': 'The error message is unclear', 'assistant': 'I see'},
            {'user': 'Can you fix the code please', 'assistant': 'Sure'}
        ]

        hint = conversation_manager.get_recent_context_hint()

        # Should have extracted "bug" and/or "error" related context
        assert len(hint) > 0

    def test_store_exchange_adds_to_local_history(self, conversation_manager, mock_service_manager):
        """Store exchange adds to local conversation history."""
        mock_service_manager.check_service_health.return_value = False  # Disable external store

        conversation_manager.store_exchange(
            user_message="Test message",
            assistant_response="Test response"
        )

        assert len(conversation_manager.conversation_history) == 1
        assert conversation_manager.conversation_history[0]['user'] == "Test message"
        assert conversation_manager.conversation_history[0]['assistant'] == "Test response"

    def test_store_exchange_returns_exchange_id(self, conversation_manager, mock_orchestrator, mock_service_manager):
        """Store exchange returns ID from orchestrator."""
        mock_service_manager.check_service_health.return_value = False

        exchange_id = conversation_manager.store_exchange(
            user_message="Test",
            assistant_response="Response"
        )

        assert exchange_id == "EXCH-test-456"
        mock_orchestrator.add_exchange.assert_called_once()

    def test_get_conversation_id_returns_current(self, conversation_manager):
        """get_conversation_id returns current conversation ID."""
        expected = conversation_manager.conversation_id

        assert conversation_manager.get_conversation_id() == expected

    def test_get_history_count_correct(self, conversation_manager):
        """get_history_count returns correct count."""
        conversation_manager.conversation_history = [
            {'user': 'A', 'assistant': 'B'},
            {'user': 'C', 'assistant': 'D'},
            {'user': 'E', 'assistant': 'F'}
        ]

        assert conversation_manager.get_history_count() == 3

    def test_get_history_returns_copy(self, conversation_manager):
        """get_history returns a copy, not the internal list."""
        conversation_manager.conversation_history = [
            {'user': 'Original', 'assistant': 'Response'}
        ]

        history = conversation_manager.get_history()
        history.append({'user': 'Added', 'assistant': 'By caller'})

        # Internal list should be unchanged
        assert len(conversation_manager.conversation_history) == 1


# =============================================================================
# INTEGRATION TESTS (With Mocked HTTP Services)
# =============================================================================

class TestConversationManagerWithMockedServices:
    """Integration tests with mocked HTTP services."""

    def test_list_conversations_queries_episodic(self, conversation_manager, sample_episodic_conversations):
        """List conversations makes correct API call to episodic memory."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_episodic_conversations
            mock_get.return_value = mock_response

            result = conversation_manager.list_conversations(limit=50)

            assert len(result) == 2
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert '/recent' in call_args[0][0]
            assert call_args[1]['params']['limit'] == 50

    def test_list_conversations_returns_empty_when_unhealthy(
        self, mock_unhealthy_service_manager, mock_error_handler, mock_orchestrator
    ):
        """List conversations returns empty list when service unavailable."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_unhealthy_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )

        result = manager.list_conversations()

        assert result == []

    def test_switch_conversation_loads_history(
        self, conversation_manager, sample_conversation_history
    ):
        """Switch conversation loads history from episodic memory."""
        with patch('requests.get') as mock_get:
            # First call for expand_conversation_id (list), second for load
            list_response = Mock()
            list_response.status_code = 200
            list_response.json.return_value = {
                'conversations': [
                    {'conversation_id': 'target-uuid-full'}
                ]
            }

            load_response = Mock()
            load_response.status_code = 200
            load_response.json.return_value = sample_conversation_history

            mock_get.side_effect = [list_response, load_response]

            with patch('conversation_manager._get_ozolith', return_value=None):
                result = conversation_manager.switch_conversation("target")

            assert result is True
            assert len(conversation_manager.conversation_history) == 2
            assert conversation_manager.conversation_history[0]['user'] == 'Hello'

    def test_switch_conversation_returns_false_when_not_found(self, conversation_manager):
        """Switch returns False when conversation doesn't exist."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'conversations': []}  # No matches
            mock_get.return_value = mock_response

            result = conversation_manager.switch_conversation("nonexistent")

            assert result is False

    def test_store_exchange_persists_to_working_memory(
        self, conversation_manager, mock_ozolith
    ):
        """Store exchange makes POST to working memory service."""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.store_exchange(
                    user_message="Test",
                    assistant_response="Response"
                )

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert '/working-memory' in call_args[0][0]
            assert call_args[1]['json']['user_message'] == "Test"

    def test_restore_pulls_from_both_services(self, conversation_manager):
        """Restore queries both working memory and episodic memory."""
        with patch('requests.get') as mock_get:
            working_response = Mock()
            working_response.status_code = 200
            working_response.json.return_value = {
                'context': [
                    {'user_message': 'Working msg', 'assistant_response': 'Working resp', 'exchange_id': 'W1'}
                ]
            }

            episodic_response = Mock()
            episodic_response.status_code = 200
            episodic_response.json.return_value = {
                'conversations': [
                    {
                        'exchanges': [
                            {'user_input': 'Episodic msg', 'assistant_response': 'Episodic resp',
                             'timestamp': '2025-12-15T10:00:00Z', 'exchange_id': 'E1'}
                        ]
                    }
                ]
            }

            mock_get.side_effect = [working_response, episodic_response]

            with patch('conversation_manager._get_ozolith', return_value=None):
                count = conversation_manager.restore_conversation_history()

            # Should have pulled from both
            assert count >= 2
            assert mock_get.call_count == 2

    def test_archive_conversation_posts_to_episodic(self, conversation_manager, mock_ozolith):
        """Archive sends conversation to episodic memory."""
        # Add some history to archive
        conversation_manager.conversation_history = [
            {'user': 'Test', 'assistant': 'Response', 'exchange_id': 'E1',
             'timestamp': datetime.now().isoformat()}
        ]

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                result = conversation_manager.archive_conversation(reason="test")

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert '/archive' in call_args[0][0]
            assert call_args[1]['json']['trigger_reason'] == "test"

    def test_archive_returns_true_with_empty_history(self, conversation_manager):
        """Archive with no history returns True (nothing to do)."""
        conversation_manager.conversation_history = []

        result = conversation_manager.archive_conversation()

        assert result is True


# =============================================================================
# OZOLITH VERIFICATION TESTS
# =============================================================================

class TestConversationManagerOzolithLogging:
    """Tests verifying correct OZOLITH event logging."""

    def test_store_exchange_logs_memory_stored(self, conversation_manager, mock_ozolith):
        """MEMORY_STORED event logged with correct payload."""
        from datashapes import OzolithEventType

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.store_exchange(
                    user_message="Test",
                    assistant_response="Response",
                    metadata={'confidence': 0.85}
                )

        # Check MEMORY_STORED was logged
        stored_events = [e for e in mock_ozolith.events
                        if e['event_type'] == OzolithEventType.MEMORY_STORED]
        assert len(stored_events) == 1
        assert stored_events[0]['payload']['confidence'] == 0.85

    def test_get_context_logs_memory_retrieved(self, conversation_manager, mock_ozolith, mock_orchestrator):
        """MEMORY_RETRIEVED event logged with exchange IDs."""
        from datashapes import OzolithEventType

        # Set context_id so orchestrator is used
        conversation_manager._context_id = "CTX-test-123"

        with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
            conversation_manager.get_context_for_llm()

        # Check MEMORY_RETRIEVED was logged
        retrieved_events = [e for e in mock_ozolith.events
                          if e['event_type'] == OzolithEventType.MEMORY_RETRIEVED]
        assert len(retrieved_events) == 1
        assert 'EXCH-1' in retrieved_events[0]['payload']['retrieved_ids']

    def test_switch_conversation_logs_memory_recalled(
        self, conversation_manager, mock_ozolith, sample_conversation_history
    ):
        """MEMORY_RECALLED event logged on conversation load."""
        from datashapes import OzolithEventType

        with patch('requests.get') as mock_get:
            list_response = Mock()
            list_response.status_code = 200
            list_response.json.return_value = {
                'conversations': [{'conversation_id': 'target-uuid-full'}]
            }

            load_response = Mock()
            load_response.status_code = 200
            load_response.json.return_value = sample_conversation_history

            mock_get.side_effect = [list_response, load_response]

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.switch_conversation("target")

        # Check MEMORY_RECALLED was logged
        recalled_events = [e for e in mock_ozolith.events
                         if e['event_type'] == OzolithEventType.MEMORY_RECALLED]
        assert len(recalled_events) == 1
        assert 'EXCH-1' in recalled_events[0]['payload']['recalled_ids']
        assert recalled_events[0]['payload']['recall_reason'] == "switch_conversation"

    def test_archive_conversation_logs_memory_archived(self, conversation_manager, mock_ozolith):
        """MEMORY_ARCHIVED event logged for each exchange."""
        from datashapes import OzolithEventType

        conversation_manager.conversation_history = [
            {'user': 'A', 'assistant': 'B', 'exchange_id': 'E1',
             'timestamp': datetime.now().isoformat()},
            {'user': 'C', 'assistant': 'D', 'exchange_id': 'E2',
             'timestamp': datetime.now().isoformat()}
        ]

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.archive_conversation(reason="test_archive")

        # Check MEMORY_ARCHIVED was logged for each exchange
        archived_events = [e for e in mock_ozolith.events
                         if e['event_type'] == OzolithEventType.MEMORY_ARCHIVED]
        assert len(archived_events) == 2
        exchange_ids = [e['payload']['exchange_id'] for e in archived_events]
        assert 'E1' in exchange_ids
        assert 'E2' in exchange_ids

    def test_restore_logs_memory_recalled(self, conversation_manager, mock_ozolith):
        """MEMORY_RECALLED event logged on restore."""
        from datashapes import OzolithEventType

        with patch('requests.get') as mock_get:
            working_response = Mock()
            working_response.status_code = 200
            working_response.json.return_value = {
                'context': [
                    {'user_message': 'Test', 'assistant_response': 'Response',
                     'exchange_id': 'W1', 'created_at': '2025-12-15T10:00:00Z'}
                ]
            }

            episodic_response = Mock()
            episodic_response.status_code = 200
            episodic_response.json.return_value = {'conversations': []}

            mock_get.side_effect = [working_response, episodic_response]

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.restore_conversation_history()

        # Check MEMORY_RECALLED was logged
        recalled_events = [e for e in mock_ozolith.events
                         if e['event_type'] == OzolithEventType.MEMORY_RECALLED]
        assert len(recalled_events) == 1
        assert recalled_events[0]['payload']['recall_reason'] == "restore_conversation_history"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestConversationManagerErrorHandling:
    """Tests for graceful error handling."""

    def test_list_conversations_handles_service_down(
        self, mock_unhealthy_service_manager, mock_error_handler, mock_orchestrator
    ):
        """Returns empty list when episodic unavailable."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_unhealthy_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )

        result = manager.list_conversations()

        assert result == []

    def test_list_conversations_handles_http_error(self, conversation_manager, mock_error_handler):
        """Returns empty list and logs error on HTTP failure."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            result = conversation_manager.list_conversations()

        assert result == []
        assert len(mock_error_handler.calls) == 1
        assert 'episodic' in str(mock_error_handler.calls[0]['category']).lower()

    def test_switch_conversation_handles_not_found(self, conversation_manager):
        """Returns False when conversation doesn't exist."""
        with patch('requests.get') as mock_get:
            # No conversations match
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'conversations': []}
            mock_get.return_value = mock_response

            result = conversation_manager.switch_conversation("nonexistent")

        assert result is False

    def test_switch_conversation_handles_multiple_matches(self, conversation_manager):
        """Returns False when partial ID matches multiple conversations."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'conversations': [
                    {'conversation_id': 'abc-1-uuid'},
                    {'conversation_id': 'abc-2-uuid'}
                ]
            }
            mock_get.return_value = mock_response

            result = conversation_manager.switch_conversation("abc")

        assert result is False

    def test_store_exchange_continues_on_working_memory_failure(
        self, conversation_manager, mock_orchestrator, mock_error_handler
    ):
        """Exchange still stored to orchestrator if working memory fails."""
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Working memory down")

            exchange_id = conversation_manager.store_exchange(
                user_message="Test",
                assistant_response="Response"
            )

        # Exchange ID still returned (orchestrator succeeded)
        assert exchange_id == "EXCH-test-456"

        # Local history still updated
        assert len(conversation_manager.conversation_history) == 1

        # Error was logged
        assert len(mock_error_handler.calls) == 1

    def test_archive_handles_episodic_failure(
        self, conversation_manager, mock_error_handler
    ):
        """Archive returns False and logs error on HTTP failure."""
        import requests as req_module

        conversation_manager.conversation_history = [
            {'user': 'Test', 'assistant': 'Response', 'exchange_id': 'E1',
             'timestamp': datetime.now().isoformat()}
        ]

        with patch('requests.post') as mock_post:
            mock_post.side_effect = req_module.RequestException("Episodic memory down")

            result = conversation_manager.archive_conversation()

        assert result is False
        assert len(mock_error_handler.calls) == 1

    def test_archive_returns_false_when_service_unhealthy(
        self, mock_unhealthy_service_manager, mock_error_handler, mock_orchestrator
    ):
        """Archive returns False when episodic service unavailable."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_unhealthy_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )
        manager.conversation_history = [
            {'user': 'Test', 'assistant': 'Response'}
        ]

        result = manager.archive_conversation()

        assert result is False


# =============================================================================
# EXPAND CONVERSATION ID TESTS
# =============================================================================

class TestExpandConversationId:
    """Tests for partial conversation ID expansion."""

    def test_full_uuid_returned_as_is(self, conversation_manager):
        """Full UUID (36 chars) returned without API call."""
        full_uuid = str(uuid.uuid4())

        with patch('requests.get') as mock_get:
            result = conversation_manager._expand_conversation_id(full_uuid)

        assert result == full_uuid
        mock_get.assert_not_called()

    def test_partial_id_expands_to_match(self, conversation_manager):
        """Partial ID expands to matching full UUID."""
        full_uuid = "abc12345-full-uuid-value"

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'conversations': [{'conversation_id': full_uuid}]
            }
            mock_get.return_value = mock_response

            result = conversation_manager._expand_conversation_id("abc")

        assert result == full_uuid

    def test_no_match_returns_none(self, conversation_manager):
        """No matching conversation returns None."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'conversations': []}
            mock_get.return_value = mock_response

            result = conversation_manager._expand_conversation_id("xyz")

        assert result is None


# =============================================================================
# MODULE-LEVEL FUNCTION TESTS
# =============================================================================

class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_conversation_manager_requires_service_manager(self, mock_error_handler):
        """First call requires service_manager."""
        from conversation_manager import get_conversation_manager, reset_conversation_manager
        reset_conversation_manager()

        with pytest.raises(ValueError, match="service_manager required"):
            get_conversation_manager(error_handler=mock_error_handler)

    def test_get_conversation_manager_requires_error_handler(self, mock_service_manager):
        """First call requires error_handler."""
        from conversation_manager import get_conversation_manager, reset_conversation_manager
        reset_conversation_manager()

        with pytest.raises(ValueError, match="error_handler required"):
            get_conversation_manager(service_manager=mock_service_manager)

    def test_get_conversation_manager_returns_singleton(
        self, mock_service_manager, mock_error_handler
    ):
        """Subsequent calls return same instance."""
        from conversation_manager import get_conversation_manager, reset_conversation_manager
        reset_conversation_manager()

        manager1 = get_conversation_manager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler
        )
        manager2 = get_conversation_manager()

        assert manager1 is manager2

    def test_reset_clears_singleton(self, mock_service_manager, mock_error_handler):
        """reset_conversation_manager clears the global instance."""
        from conversation_manager import get_conversation_manager, reset_conversation_manager

        manager1 = get_conversation_manager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler
        )

        reset_conversation_manager()

        manager2 = get_conversation_manager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler
        )

        assert manager1 is not manager2


# =============================================================================
# EDGE CASE TESTS (Added after honest review)
# =============================================================================

class TestEdgeCases:
    """Edge cases identified during honest review of test coverage."""

    def test_get_context_id_returns_current(self, conversation_manager):
        """get_context_id returns the current orchestrator context ID."""
        # After start_new_conversation, _context_id should be set
        conversation_manager.start_new_conversation(task_description="Test")

        context_id = conversation_manager.get_context_id()

        assert context_id == "CTX-test-123"  # From mock_orchestrator fixture

    def test_get_context_id_none_before_start(
        self, mock_service_manager, mock_error_handler, mock_orchestrator
    ):
        """get_context_id returns None before start_new_conversation."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )

        # Before calling start_new_conversation
        assert manager.get_context_id() is None

    def test_store_exchange_fallback_when_no_context_id(
        self, mock_service_manager, mock_error_handler, mock_orchestrator
    ):
        """store_exchange uses orchestrator.get_active_context_id() when _context_id is None."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )
        mock_service_manager.check_service_health.return_value = False

        # Don't call start_new_conversation - _context_id stays None
        assert manager._context_id is None

        manager.store_exchange(
            user_message="Test without context",
            assistant_response="Response"
        )

        # Should have called get_active_context_id as fallback
        mock_orchestrator.get_active_context_id.assert_called()

    def test_restore_both_services_down_returns_zero(
        self, mock_unhealthy_service_manager, mock_error_handler, mock_orchestrator
    ):
        """restore_conversation_history returns 0 when both services are down."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_unhealthy_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )

        count = manager.restore_conversation_history()

        assert count == 0
        assert len(manager.conversation_history) == 0

    def test_get_context_for_llm_fallback_to_local_history(
        self, mock_service_manager, mock_error_handler, mock_orchestrator
    ):
        """get_context_for_llm falls back to local history when no context_id available."""
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        # Make orchestrator return None for active context too
        mock_orchestrator.get_active_context_id.return_value = None

        manager = ConversationManager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )

        # Add local history without starting conversation (no _context_id)
        manager.conversation_history = [
            {'user': 'Local msg', 'assistant': 'Local resp', 'exchange_id': 'LOCAL-1'}
        ]

        with patch('conversation_manager._get_ozolith', return_value=None):
            context = manager.get_context_for_llm()

        # Should return local history since both _context_id and get_active_context_id are None
        assert len(context) == 1
        assert context[0]['user'] == 'Local msg'


class TestOzolithPayloadVerification:
    """Deep verification of OZOLITH payload contents."""

    def test_memory_retrieved_counts_sources_correctly(
        self, mock_service_manager, mock_error_handler, mock_orchestrator, mock_ozolith
    ):
        """MEMORY_RETRIEVED payload has correct from_working and from_episodic counts."""
        from datashapes import OzolithEventType
        from conversation_manager import ConversationManager, reset_conversation_manager
        reset_conversation_manager()

        manager = ConversationManager(
            service_manager=mock_service_manager,
            error_handler=mock_error_handler,
            orchestrator=mock_orchestrator
        )
        manager._context_id = "CTX-test-123"

        # Mock orchestrator returns mixed sources
        mock_orchestrator.get_context_for_llm.return_value = [
            {'user': 'A', 'assistant': 'B', 'exchange_id': 'E1', 'source': 'working_memory'},
            {'user': 'C', 'assistant': 'D', 'exchange_id': 'E2', 'source': 'working_memory'},
            {'user': 'E', 'assistant': 'F', 'exchange_id': 'E3', 'source': 'episodic_memory'},
            {'user': 'G', 'assistant': 'H', 'exchange_id': 'E4', 'source': 'current_session'},
        ]

        with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
            manager.get_context_for_llm()

        # Find the MEMORY_RETRIEVED event
        retrieved_events = [e for e in mock_ozolith.events
                          if e['event_type'] == OzolithEventType.MEMORY_RETRIEVED]
        assert len(retrieved_events) == 1

        payload = retrieved_events[0]['payload']
        assert payload['from_working'] == 2  # E1, E2
        assert payload['from_episodic'] == 1  # E3
        # E4 is current_session, not counted in either

    def test_memory_archived_calculates_age_correctly(
        self, conversation_manager, mock_ozolith
    ):
        """MEMORY_ARCHIVED payload calculates age_at_archive_seconds correctly."""
        from datashapes import OzolithEventType
        from datetime import datetime, timedelta

        # Add history with known timestamp (5 minutes ago)
        five_minutes_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
        conversation_manager.conversation_history = [
            {'user': 'Test', 'assistant': 'Response', 'exchange_id': 'E1',
             'timestamp': five_minutes_ago}
        ]

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.archive_conversation(reason="test_age")

        # Find the MEMORY_ARCHIVED event
        archived_events = [e for e in mock_ozolith.events
                         if e['event_type'] == OzolithEventType.MEMORY_ARCHIVED]
        assert len(archived_events) == 1

        payload = archived_events[0]['payload']
        # Age should be approximately 300 seconds (5 minutes), allow some tolerance
        assert 290 <= payload['age_at_archive_seconds'] <= 310

    def test_memory_stored_includes_confidence(
        self, conversation_manager, mock_ozolith
    ):
        """MEMORY_STORED payload includes confidence from metadata."""
        from datashapes import OzolithEventType

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.store_exchange(
                    user_message="High confidence message",
                    assistant_response="Confident response",
                    metadata={'confidence': 0.95, 'other_data': 'ignored'}
                )

        stored_events = [e for e in mock_ozolith.events
                        if e['event_type'] == OzolithEventType.MEMORY_STORED]
        assert len(stored_events) == 1
        assert stored_events[0]['payload']['confidence'] == 0.95

    def test_memory_stored_zero_confidence_when_no_metadata(
        self, conversation_manager, mock_ozolith
    ):
        """MEMORY_STORED defaults to 0.0 confidence when no metadata provided."""
        from datashapes import OzolithEventType

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch('conversation_manager._get_ozolith', return_value=mock_ozolith):
                conversation_manager.store_exchange(
                    user_message="No metadata message",
                    assistant_response="Response",
                    metadata=None
                )

        stored_events = [e for e in mock_ozolith.events
                        if e['event_type'] == OzolithEventType.MEMORY_STORED]
        assert len(stored_events) == 1
        assert stored_events[0]['payload']['confidence'] == 0.0
