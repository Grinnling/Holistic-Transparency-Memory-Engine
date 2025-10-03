# memory_handler.py
"""
MemoryHandler - Centralized memory operations and archival management
Extracted from RichMemoryChat for cleaner separation of concerns
"""

import requests
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity


class MemoryHandler:
    """Handles memory archival, display, and search operations"""

    def __init__(self, console: Console = None, error_handler: ErrorHandler = None, debug_mode: bool = False):
        self.console = console or Console()
        self.error_handler = error_handler or ErrorHandler(debug_mode=debug_mode)
        self.debug_mode = debug_mode
        self.episodic_archival_failures = 0

        # Will be injected by the main chat class
        self.conversation_history = []
        self.conversation_id = ""
        self.services = {}
        self.episodic_coordinator = None
        self.show_confidence = False
        self.show_tokens = False
        self.fuck_it_we_ball_mode = False
        self.recovery_chat = None

    def inject_dependencies(self, **kwargs):
        """Inject dependencies from the main chat class"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def archive_to_episodic_memory(self, user_message: str, assistant_response: str, exchange_id: str):
        """Archive exchange using EpisodicMemoryCoordinator with backup fallback"""
        if not self.episodic_coordinator:
            # Fallback to old direct method if coordinator not available
            self._archive_direct_fallback(user_message, assistant_response, exchange_id)
            return

        try:
            # Prepare enhanced archive data with AI-centric metadata
            timing_info = {
                'processing_start': datetime.now().isoformat(),
                'user_input_length': len(user_message),
                'response_length': len(assistant_response)
            }

            ai_context = {
                'confidence_enabled': self.show_confidence,
                'debug_mode': self.debug_mode,
                'session_type': 'rich_chat',
                'tokens_shown': self.show_tokens,
                'conversation_length': len(self.conversation_history),
                'fuck_it_we_ball_mode': self.fuck_it_we_ball_mode
            }

            archive_data = {
                'conversation_id': self.conversation_id,
                'exchange_id': exchange_id or f"rich_{int(datetime.now().timestamp())}",
                'user_input': user_message,
                'assistant_response': assistant_response,
                'timestamp': datetime.now().isoformat(),
                'metadata': {
                    'session_type': 'rich_chat',
                    'has_confidence_markers': self.show_confidence,
                    'debug_mode': self.debug_mode,
                    'timing_info': timing_info,
                    'ai_context': ai_context
                }
            }

            # Use coordinator for archival with automatic backup fallback
            result = self.episodic_coordinator.archive_exchange(archive_data, source='rich_chat')

            # Show passive notification based on result
            if result['success']:
                if result['method'] == 'episodic_direct':
                    if self.debug_mode:
                        self._debug_message(f"Exchange archived (direct, {result.get('response_time_ms', 0):.0f}ms)", ErrorCategory.EPISODIC_MEMORY)
                elif result['method'] == 'backup_queued':
                    error_reason = result.get('error_reason', 'Unknown reason')
                    self._info_message(f"Exchange queued for backup recovery ({error_reason})", ErrorCategory.BACKUP_SYSTEM)
                    # Also send to error panel so user knows episodic archival is failing
                    self.error_handler.handle_error(
                        Exception(f"Episodic archival failed: {error_reason}"),
                        ErrorCategory.EPISODIC_MEMORY,
                        ErrorSeverity.MEDIUM_DEGRADE,
                        context="Falling back to backup system",
                        operation="archive_to_episodic_fallback"
                    )
                    if self.fuck_it_we_ball_mode:
                        self._debug_message(f"FIWB: Queued as {result['exchange_id']} for recovery thread", ErrorCategory.BACKUP_SYSTEM)
            else:
                self.episodic_archival_failures += 1
                self.error_handler.handle_error(
                    Exception(f"Archive failed: {result.get('error', 'Unknown error')}"),
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.HIGH_DEGRADE,
                    context="Coordinator archive result",
                    operation="archive_to_episodic_coordinator"
                )
                if self.fuck_it_we_ball_mode:
                    self._debug_message(f"FIWB: Full failure details: {result}", ErrorCategory.EPISODIC_MEMORY)

        except Exception as e:
            self.episodic_archival_failures += 1
            self.error_handler.handle_error(
                e,
                ErrorCategory.EPISODIC_MEMORY,
                ErrorSeverity.HIGH_DEGRADE,
                context="Archiving through coordinator",
                operation="archive_to_episodic_coordinator"
            )
            if self.fuck_it_we_ball_mode:
                import traceback
                self._debug_message(f"FIWB Traceback: {traceback.format_exc()}", ErrorCategory.EPISODIC_MEMORY)

            # Fallback to direct method
            self._archive_direct_fallback(user_message, assistant_response, exchange_id)

    def _archive_direct_fallback(self, user_message: str, assistant_response: str, exchange_id: str):
        """Fallback direct archival when coordinator not available"""
        try:
            # Prepare archive data
            archive_data = {
                'conversation_id': self.conversation_id,
                'exchanges': [{
                    'exchange_id': exchange_id,
                    'user_input': user_message,
                    'assistant_response': assistant_response,
                    'timestamp': datetime.now().isoformat(),
                    'metadata': {
                        'session_type': 'rich_chat_fallback',
                        'has_confidence_markers': self.show_confidence,
                        'debug_mode': self.debug_mode
                    }
                }],
                'participant_info': {
                    'user_id': 'rich_chat_user',
                    'assistant_id': 'rich_chat_assistant'
                }
            }

            # Send to episodic memory (with feedback on failure)
            response = requests.post(
                f"{self.services['episodic_memory']}/archive",
                json=archive_data,
                timeout=2  # Short timeout since it's background
            )

            if self.debug_mode and response.status_code == 200:
                self._debug_message("Exchange archived via fallback", ErrorCategory.EPISODIC_MEMORY)

        except Exception as e:
            # Track failures and show warning - user should know their memories aren't being saved
            self.episodic_archival_failures += 1
            self._warning_message(f"Episodic memory archive failed: {str(e)[:50]}...", ErrorCategory.EPISODIC_MEMORY)
            if self.debug_mode:
                self._debug_message(f"Full error: {e}", ErrorCategory.EPISODIC_MEMORY)

            # Alert after multiple failures
            if self.episodic_archival_failures >= 3:
                self.error_handler.handle_error(
                    Exception("Multiple episodic memory failures! Long-term memories not being saved."),
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.HIGH_DEGRADE,
                    context="Check episodic memory service status or use recovery commands",
                    operation="episodic_archival_tracking"
                )

    def show_status(self):
        """Show fancy status panel"""
        status_table = Table(title="📊 System Status")
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="green")

        status_table.add_row("Conversation ID", self.conversation_id[:12] + "...")
        status_table.add_row("Messages", str(len(self.conversation_history)))
        status_table.add_row("Services", "✅ Healthy" if self._services_healthy() else "⚠️ Issues")
        status_table.add_row("LLM", "✅ Connected" if self._llm_available() else "⚠️ Fallback")

        # Add recovery system status if available
        if self.recovery_chat:
            recovery_status = self.recovery_chat.get_status_for_dashboard()
            status_table.add_row("Recovery", recovery_status)

        if self.conversation_history:
            last = self.conversation_history[-1]
            validation = last.get('validation', {})
            confidence = validation.get('confidence_score', 'N/A')
            status_table.add_row("Last Confidence", str(confidence))

        self.console.print(Panel(status_table, title="System Status", border_style="blue"))

    def show_memory(self):
        """Show conversation memory in nice format"""
        if not self.conversation_history:
            self.console.print(Panel("No conversation history yet", title="📚 Memory"))
            return

        # Show more history - last 15 exchanges instead of just 5
        memory_panel = Table(title="📚 Recent Conversation Memory")
        memory_panel.add_column("#", width=3)
        memory_panel.add_column("You said", style="blue")
        memory_panel.add_column("I said", style="green")
        memory_panel.add_column("Source", width=8)
        memory_panel.add_column("Confidence", width=10)

        recent_exchanges = self.conversation_history[-15:]  # Show last 15
        for i, exchange in enumerate(recent_exchanges, 1):
            user_msg = exchange['user'][:40] + "..." if len(exchange['user']) > 40 else exchange['user']
            asst_msg = exchange['assistant'][:40] + "..." if len(exchange['assistant']) > 40 else exchange['assistant']
            confidence = exchange.get('validation', {}).get('confidence_score', 'N/A')
            source = "restored" if exchange.get('restored', False) else "current"

            # Mark restored conversations
            row_style = "dim" if exchange.get('restored', False) else None
            memory_panel.add_row(str(i), user_msg, asst_msg, source, str(confidence), style=row_style)

        self.console.print(Panel(memory_panel, border_style="cyan"))

        # Add summary info about memory system
        total_count = len(self.conversation_history)
        restored_count = sum(1 for ex in self.conversation_history if ex.get('restored'))
        current_count = total_count - restored_count

        summary_text = f"💾 Total in memory: {total_count} exchanges | Restored: {restored_count} | Current session: {current_count}\n"
        summary_text += f"📋 Use '/history' to see all conversations | Use '/stats' for distillation info"

        self.console.print(Panel(summary_text, title="Memory Summary", border_style="dim"))

    def show_full_history(self):
        """Show ALL conversation history with pagination"""
        if not self.conversation_history:
            self.console.print(Panel("No conversation history yet", title="📚 Full History"))
            return

        total = len(self.conversation_history)
        self.console.print(f"[bold]📚 Full Conversation History ({total} exchanges)[/bold]\n")

        # Show all exchanges in one scrollable table (no pagination)
        history_table = Table(title=f"📚 Complete Conversation History ({total} exchanges)")
        history_table.add_column("#", width=4)
        history_table.add_column("You", style="blue")
        history_table.add_column("Assistant", style="green")
        history_table.add_column("Source", width=8)
        history_table.add_column("Time", width=10)

        for i, exchange in enumerate(self.conversation_history):
            user_msg = exchange['user'][:50] + "..." if len(exchange['user']) > 50 else exchange['user']
            asst_msg = exchange['assistant'][:50] + "..." if len(exchange['assistant']) > 50 else exchange['assistant']
            source = "restored" if exchange.get('restored', False) else "current"
            timestamp = exchange.get('timestamp', '')[:10] if exchange.get('timestamp') else 'N/A'

            row_style = "dim" if exchange.get('restored', False) else None
            history_table.add_row(str(i + 1), user_msg, asst_msg, source, timestamp, style=row_style)

        self.console.print(Panel(history_table, border_style="blue"))

        # Add helpful tip about scrolling
        self.console.print(Panel(
            "💡 Use your terminal's scroll to browse through history | Use /search <term> to find specific topics",
            title="Navigation Tip",
            border_style="dim"
        ))

    def search_conversations(self, search_term: str):
        """Search conversation history for specific terms"""
        if not self.conversation_history:
            self.console.print(Panel("No conversation history to search", title="🔍 Search Results"))
            return

        search_lower = search_term.lower()
        matches = []

        # Search through all exchanges
        for i, exchange in enumerate(self.conversation_history):
            user_msg = exchange.get('user', '')
            asst_msg = exchange.get('assistant', '')

            # Check if search term appears in either message
            if (search_lower in user_msg.lower() or
                search_lower in asst_msg.lower()):
                matches.append((i + 1, exchange))

        if not matches:
            self.console.print(Panel(
                f"No conversations found containing '{search_term}'",
                title="🔍 Search Results",
                border_style="yellow"
            ))
            return

        # Show results
        results_table = Table(title=f"🔍 Search Results for '{search_term}' ({len(matches)} found)")
        results_table.add_column("#", width=4)
        results_table.add_column("You", style="blue")
        results_table.add_column("Assistant", style="green")
        results_table.add_column("Source", width=8)
        results_table.add_column("Match", style="yellow")

        for exchange_num, exchange in matches:
            user_msg = exchange['user']
            asst_msg = exchange['assistant']
            source = "restored" if exchange.get('restored', False) else "current"

            # Highlight matches and truncate
            user_snippet = self._highlight_and_truncate(user_msg, search_term, 40)
            asst_snippet = self._highlight_and_truncate(asst_msg, search_term, 40)

            # Determine which part matched
            match_in = []
            if search_lower in user_msg.lower():
                match_in.append("You")
            if search_lower in asst_msg.lower():
                match_in.append("AI")
            match_location = " + ".join(match_in)

            row_style = "dim" if exchange.get('restored', False) else None
            results_table.add_row(
                str(exchange_num),
                user_snippet,
                asst_snippet,
                source,
                match_location,
                style=row_style
            )

        self.console.print(Panel(results_table, border_style="green"))

        # Show search tips
        tips = f"💡 Found {len(matches)} matches | Try more specific terms for better results"
        self.console.print(Panel(tips, title="Search Tips", border_style="dim"))

    def _highlight_and_truncate(self, text: str, search_term: str, max_len: int) -> str:
        """Highlight search term in text and truncate smartly"""
        text_lower = text.lower()
        search_lower = search_term.lower()

        if search_lower not in text_lower:
            # No match, just truncate
            return text[:max_len] + "..." if len(text) > max_len else text

        # Find match position
        match_pos = text_lower.find(search_lower)

        # Try to center the match in the snippet
        start = max(0, match_pos - max_len // 2)
        end = min(len(text), start + max_len)

        # Adjust start if we hit the end
        if end == len(text):
            start = max(0, end - max_len)

        snippet = text[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        # Simple highlighting (Rich will render this)
        highlighted = snippet.replace(
            search_term,
            f"[yellow bold]{search_term}[/yellow bold]"
        )

        return highlighted

    def reset_archival_failures(self):
        """Reset archival failure counter - useful after service recovery"""
        self.episodic_archival_failures = 0

    def get_archival_status(self):
        """Get current archival health status"""
        return {
            'failures': self.episodic_archival_failures,
            'healthy': self.episodic_archival_failures < 3,
            'coordinator_available': self.episodic_coordinator is not None
        }

    def retrieve_relevant_memories(self, query: str, top_k: int = 5):
        """Retrieve most relevant memories for a query using semantic search

        Args:
            query: The user's current message to search for relevant context
            top_k: Number of most relevant memories to retrieve

        Returns:
            List of relevant memory exchanges with metadata
        """
        try:
            # Check if episodic memory service is available
            if not self.services or 'episodic_memory' not in self.services:
                if self.debug_mode:
                    self._debug_message("Episodic memory service not configured", ErrorCategory.EPISODIC_MEMORY)
                return []

            # Call episodic memory service for semantic search
            # Service uses REST GET with query params (not POST with JSON body)
            response = requests.get(
                f"{self.services['episodic_memory']}/search",
                params={"query": query, "limit": top_k},
                timeout=5
            )

            if response.ok:
                results = response.json().get('results', [])
                if self.debug_mode and results:
                    self._debug_message(f"Retrieved {len(results)} relevant memories", ErrorCategory.EPISODIC_MEMORY)
                return results
            else:
                self._warning_message(
                    f"Failed to retrieve memories: {response.status_code}",
                    ErrorCategory.EPISODIC_MEMORY
                )
                return []

        except requests.exceptions.Timeout:
            self._warning_message("Memory retrieval timeout - continuing without context", ErrorCategory.EPISODIC_MEMORY)
            return []
        except Exception as e:
            self._warning_message(
                f"Error retrieving memories: {str(e)}",
                ErrorCategory.EPISODIC_MEMORY
            )
            return []

    def get_memory_count(self):
        """Get total count of episodic memories stored

        Returns:
            int: Number of stored conversations/exchanges, or 0 if unavailable
        """
        try:
            if not self.services or 'episodic_memory' not in self.services:
                return 0

            response = requests.get(
                f"{self.services['episodic_memory']}/stats",
                timeout=5
            )

            if response.ok:
                data = response.json()
                # Navigate nested stats structure from episodic service
                # Use database_stats.total_episodes (actual DB count that persists across restarts)
                # Not service_stats.total_exchanges_archived (session counter that resets)
                if 'stats' in data:
                    database_stats = data['stats'].get('database_stats', {})
                    return database_stats.get('total_episodes', 0)
                # Fallback for simpler formats
                return data.get('total_exchanges', data.get('count', 0))
            else:
                return 0

        except Exception as e:
            if self.debug_mode:
                self._debug_message(f"Error getting memory count: {str(e)}", ErrorCategory.EPISODIC_MEMORY)
            return 0

    def search_memories(self, query: str):
        """Search episodic memories (wrapper for retrieve_relevant_memories with formatted output)

        Args:
            query: Search query string

        Returns:
            List of search results with metadata
        """
        # This is just a wrapper that returns the raw results
        # retrieve_relevant_memories already does the heavy lifting
        return self.retrieve_relevant_memories(query, top_k=10)

    def clear_all_memories(self):
        """Clear all episodic memories - INTENTIONALLY NOT IMPLEMENTED

        This operation is too dangerous to expose. Accidentally clearing years of
        conversation history would be catastrophic and ethically questionable.

        BETTER DESIGN (Post-Demo Implementation):
        Instead of deleting memories, implement snapshot-based barriers:

        1. Create snapshot marker at current timestamp
        2. Future queries only search memories AFTER the marker (soft barrier)
        3. Old memories preserved but "archived" behind the barrier
        4. Rollback = delete the barrier marker, memories instantly accessible again

        Benefits:
        - No data loss ever (memories are precious)
        - Fast "reset" for testing (just add marker)
        - Trivial rollback (remove marker)
        - Multiple named snapshots ("before_demo", "production_baseline")
        - Ethically sound - we don't destroy episodic memory

        Example:
            snapshot_id = create_snapshot("demo_baseline")
            # Search now only returns memories after snapshot
            # But old data still exists, just archived
            rollback_snapshot(snapshot_id)  # Restore access to old memories

        For now (testing only):
        - Contact operator for manual DB reset if absolutely necessary
        - This requires deliberate action, preventing accidents

        Returns:
            bool: Always False (operation not supported)
        """
        self._warning_message(
            "⚠️  Memory clear not supported - prevents accidental data loss.\n"
            "   Post-demo: Snapshot-based barriers planned (safe 'reset' without deletion).\n"
            "   For urgent testing needs, contact operator for manual assistance.",
            ErrorCategory.EPISODIC_MEMORY
        )
        return False

    # Helper methods for messaging (to be connected to main UI messaging system)
    def _debug_message(self, message: str, category: ErrorCategory):
        """Debug message output - override in subclass or connect to main UI"""
        if self.debug_mode:
            self.console.print(f"[dim]DEBUG: {message}[/dim]")

    def _info_message(self, message: str, category: ErrorCategory):
        """Info message output - override in subclass or connect to main UI"""
        self.console.print(f"[blue]INFO: {message}[/blue]")

    def _warning_message(self, message: str, category: ErrorCategory):
        """Warning message output - uses centralized error handler"""
        self.console.print(f"[yellow]WARNING: {message}[/yellow]")

        # Push to centralized error handler for UI visibility
        self.error_handler.handle_error(
            Exception(message),
            category,
            ErrorSeverity.MEDIUM_ALERT,
            context="Memory operation warning",
            operation="memory_handler"
        )

    def _services_healthy(self):
        """Check if services are healthy - to be connected to ServiceManager"""
        # This will be connected to the ServiceManager in the main class
        return True  # Placeholder

    def _llm_available(self):
        """Check if LLM is available - to be connected to main chat system"""
        # This will be connected to the main chat system
        return True  # Placeholder