#!/usr/bin/env python3
"""
UIHandler - Display Layer for RichMemoryChat
Extracted from rich_chat.py to separate UI concerns from business logic
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from typing import Dict, List, Any, Optional, Callable
import logging

ui_logger = logging.getLogger('ui_handler')


class UIHandler:
    """
    Handles all UI rendering, command parsing, and user interaction
    RichMemoryChat orchestrates logic, UIHandler displays results
    """

    def __init__(self, console: Console, error_handler=None):
        """
        Initialize UI handler

        Args:
            console: Rich Console instance for rendering
            error_handler: Optional ErrorHandler for UI errors
        """
        self.console = console
        self.error_handler = error_handler

        # UI preferences (display toggles)
        self.show_tokens = False
        self.show_confidence = True
        self.show_debug = False

        # State for progress tracking
        self.current_status = None

    # ===== Display Methods =====

    def show_welcome(self):
        """Display welcome banner"""
        # To be implemented - extract from rich_chat.py
        pass

    def show_status(self, conversation_id: str, message_count: int, services_healthy: bool,
                   llm_available: bool, recovery_status: Optional[str] = None,
                   last_confidence: Optional[float] = None):
        """
        Display system status table

        Args:
            conversation_id: Current conversation ID
            message_count: Number of messages in history
            services_healthy: Whether services are healthy
            llm_available: Whether LLM is connected
            recovery_status: Optional recovery system status
            last_confidence: Optional last confidence score
        """
        status_table = Table(title="📊 System Status")
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="green")

        status_table.add_row("Conversation ID", conversation_id[:12] + "...")
        status_table.add_row("Messages", str(message_count))
        status_table.add_row("Services", "✅ Healthy" if services_healthy else "⚠️ Issues")
        status_table.add_row("LLM", "✅ Connected" if llm_available else "⚠️ Fallback")

        # Add recovery system status if available
        if recovery_status:
            status_table.add_row("Recovery", recovery_status)

        if last_confidence is not None:
            status_table.add_row("Last Confidence", str(last_confidence))

        self.console.print(Panel(status_table, title="System Status", border_style="blue"))

    def show_help(self, memory_stats: Dict, debug_mode: bool):
        """
        Display help text with available commands

        Args:
            memory_stats: Current memory statistics
            debug_mode: Whether debug mode is enabled
        """
        help_table = Table(title="📖 Rich Memory Chat - Command Reference")
        help_table.add_column("Command", style="cyan", width=15)
        help_table.add_column("Description", style="white")
        help_table.add_column("Example", style="dim", width=20)

        commands = [
            ("/help", "Show this help screen", "/help"),
            ("/memory", "Show recent 15 exchanges with confidence scores", "/memory"),
            ("/history", "Show ALL conversation history (scrollable)", "/history"),
            ("/search <term>", "Search conversations for specific topics", "/search authentication"),
            ("/context", "Preview what context goes to LLM", "/context"),
            ("/stats", "Memory statistics & distillation learning", "/stats"),
            ("/debug", "Toggle debug mode (shows prompts/responses)", "/debug"),
            ("/tokens", "Toggle token counter display", "/tokens"),
            ("/confidence", "Toggle uncertainty markers in responses", "/confidence"),
            ("---", "--- Service Management ---", "---"),
            ("/services", "Check status of all memory services", "/services"),
            ("/start-services", "Manually start memory services", "/start-services"),
            ("/stop-services", "Stop auto-started services", "/stop-services"),
            ("---", "--- Conversation Management ---", "---"),
            ("/new", "Start a fresh conversation (keeps memory)", "/new"),
            ("/list", "List previous conversations from episodic memory", "/list"),
            ("/switch <id>", "Switch to different conversation by ID", "/switch abc123"),
            ("/quit", "Exit the chat", "/quit or exit"),
            ("---", "--- Debug Tools ---", "---"),
            ("/recovery", "Recovery system controls", "/recovery status"),
            ("/ball", "Toggle 'FUCK IT WE BALL' mode", "/ball"),
            ("/errors", "Toggle error panel display", "/errors")
        ]

        for cmd, desc, example in commands:
            help_table.add_row(cmd, desc, example)

        self.console.print(Panel(help_table, border_style="blue"))

        # Add memory system explanation
        memory_explanation = """
📚 **Memory System Guide:**
• **Restored** = Previous conversations loaded from working memory
• **Current** = This session's exchanges
• **Distillation** = Auto-triggered at 100+ exchanges to compress old context
• **Learning** = System learns your preferences from distillation corrections

🔍 **Search Tips:**
• Use specific terms: `/search token counter`
• Search works on both your messages and AI responses
• Results show which part matched (You, AI, or both)

🎛️ **Toggles:**
• `/debug` = See exactly what prompts are sent to LLM
• `/tokens` = Show/hide token counts and efficiency metrics
• `/confidence` = Enable/disable uncertainty indicators in responses
        """

        self.console.print(Panel(memory_explanation.strip(), title="💡 Pro Tips", border_style="green"))

        # Current system status
        status_text = f"""
Current Session: {memory_stats['current_session_count']} exchanges | Restored: {memory_stats['restored_count']} | Pressure: {memory_stats['pressure']:.0%}
Debug: {'ON' if debug_mode else 'OFF'} | Tokens: {'ON' if self.show_tokens else 'OFF'} | Confidence: {'ON' if self.show_confidence else 'OFF'}
        """

        self.console.print(Panel(status_text.strip(), title="⚙️  Current Settings", border_style="dim"))

    def show_context_preview(self, conversation_history: List[Dict], show_tokens: bool,
                             estimate_tokens_func: callable):
        """
        Display preview of context that will be sent to LLM

        Args:
            conversation_history: Full conversation history
            show_tokens: Whether to show token estimates
            estimate_tokens_func: Function to estimate tokens from char count
        """
        if not conversation_history:
            self.console.print(Panel("No conversation history to show", title="🔍 Context Preview"))
            return

        # Simulate what the LLM connector does
        context_table = Table(title="🔍 Context that will be sent to LLM")
        context_table.add_column("#", width=3)
        context_table.add_column("Role", width=10)
        context_table.add_column("Content", style="dim")
        context_table.add_column("Length", width=8)
        context_table.add_column("Source", width=12)

        # Add system prompt
        system_prompt = """You are a helpful AI assistant with memory capabilities.
                    You can remember previous conversations and help users with complex queries.
                    Be concise but thorough in your responses."""
        context_table.add_row("1", "system", system_prompt[:60] + "...", str(len(system_prompt)), "hardcoded")

        # Add last 5 exchanges (same logic as llm_connector.py)
        total_chars = len(system_prompt)
        row_num = 2

        for exchange in conversation_history[-5:]:
            if 'user' in exchange and exchange['user']:
                user_content = exchange['user']
                context_table.add_row(
                    str(row_num),
                    "user",
                    user_content[:60] + ("..." if len(user_content) > 60 else ""),
                    str(len(user_content)),
                    "restored" if exchange.get('restored') else "current"
                )
                total_chars += len(user_content)
                row_num += 1

            if 'assistant' in exchange and exchange['assistant']:
                asst_content = exchange['assistant']
                context_table.add_row(
                    str(row_num),
                    "assistant",
                    asst_content[:60] + ("..." if len(asst_content) > 60 else ""),
                    str(len(asst_content)),
                    "restored" if exchange.get('restored') else "current"
                )
                total_chars += len(asst_content)
                row_num += 1

        # Show context stats
        stats_table = Table(title="📊 Context Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")

        stats_table.add_row("Total Messages", str(row_num - 1))
        stats_table.add_row("Total Characters", str(total_chars))

        # Only show token info if enabled
        if show_tokens:
            estimated_tokens = estimate_tokens_func(total_chars)
            token_color = "red" if estimated_tokens > 1500 else "yellow" if estimated_tokens > 1000 else "green"
            stats_table.add_row("Estimated Tokens", f"[{token_color}]{estimated_tokens}[/{token_color}]", f"~{estimated_tokens/2000:.0%} of model limit")
            stats_table.add_row("Token Efficiency", f"{estimated_tokens/(row_num-1):.0f}" if row_num > 1 else "0", "avg tokens per message")

        stats_table.add_row("Context Strategy", "Last 5 exchanges + system")
        stats_table.add_row("Restored Count", str(sum(1 for ex in conversation_history if ex.get('restored'))))
        stats_table.add_row("Current Count", str(sum(1 for ex in conversation_history if not ex.get('restored'))))

        self.console.print(Panel(context_table, border_style="blue"))
        self.console.print(Panel(stats_table, border_style="yellow"))

    def show_memory_stats(self, stats: Dict, show_tokens: bool, estimate_tokens_func: callable,
                          conversation_history: List[Dict], distillation_engine):
        """
        Display detailed memory statistics and distillation info

        Args:
            stats: Memory statistics dictionary from get_memory_stats()
            show_tokens: Whether to show token estimates
            estimate_tokens_func: Function to estimate tokens from char count
            conversation_history: Full conversation history for token calculation
            distillation_engine: Distillation engine for learning progress display
        """
        # Memory stats table
        memory_table = Table(title="💾 Memory System Statistics")
        memory_table.add_column("Metric", style="cyan")
        memory_table.add_column("Value", style="green")
        memory_table.add_column("Details", style="dim")

        memory_table.add_row(
            "Buffer Usage",
            f"{stats['current_exchanges']}/{stats['buffer_limit']}",
            f"Pressure: {stats['pressure']:.0%}"
        )
        memory_table.add_row(
            "Current Session",
            str(stats['current_session_count']),
            "Exchanges this session"
        )
        memory_table.add_row(
            "Restored",
            str(stats['restored_count']),
            "From previous sessions"
        )

        pressure_color = "red" if stats['pressure'] > 0.8 else "yellow" if stats['pressure'] > 0.6 else "green"
        memory_table.add_row(
            "Next Distillation",
            f"{stats['buffer_limit'] - stats['current_exchanges']} exchanges",
            f"[{pressure_color}]{stats['pressure']:.0%} full[/{pressure_color}]"
        )

        # Add token information only if enabled
        if show_tokens:
            total_context_chars = sum(len(ex.get('user', '') + ex.get('assistant', '')) for ex in conversation_history)
            estimated_context_tokens = estimate_tokens_func(total_context_chars)
            token_color = "red" if estimated_context_tokens > 1500 else "yellow" if estimated_context_tokens > 1000 else "green"

            memory_table.add_row(
                "Context Tokens",
                f"[{token_color}]{estimated_context_tokens}[/{token_color}]",
                f"~{estimated_context_tokens/2000:.0%} of model limit"
            )

        self.console.print(Panel(memory_table, border_style="blue"))

        # Show distillation learning progress
        distillation_engine.show_learning_progress()

    # ===== Conversation UI Methods =====

    def show_new_conversation_panel(self, old_id: str, old_count: int, new_id: str):
        """
        Display new conversation started notification

        Args:
            old_id: Previous conversation ID (full)
            old_count: Number of exchanges in previous conversation
            new_id: New conversation ID (full)
        """
        self.console.print(Panel(
            f"🆕 **New Conversation Started**\n\n"
            f"• Previous: `{old_id[:8]}...` ({old_count} exchanges)\n"
            f"• Current: `{new_id[:8]}...`\n"
            f"• Memory services retain all data\n"
            f"• Fresh context for new topic",
            title="New Conversation",
            border_style="cyan"
        ))

    def show_conversation_list(self, conversations: List[Dict], current_id: str):
        """
        Display conversation list table

        Args:
            conversations: List of conversation dictionaries from episodic memory
            current_id: Current conversation ID for marking
        """
        if not conversations:
            self.console.print(Panel(
                "No previous conversations found in episodic memory.\n"
                "(Service may be unavailable - use [cyan]/start-services[/cyan] to start)",
                title="📝 Conversation History",
                border_style="blue"
            ))
            return

        # Build conversation table
        conv_table = Table(show_header=True, header_style="bold blue")
        conv_table.add_column("ID", style="cyan", width=12)
        conv_table.add_column("Started", style="green", width=19)
        conv_table.add_column("Exchanges", justify="right", style="yellow")
        conv_table.add_column("Last Activity", style="magenta", width=19)
        conv_table.add_column("Status", width=8)

        display_conversations = conversations[-10:]  # Show last 10
        for conv in display_conversations:
            conv_id = conv.get('conversation_id', 'unknown')[:8] + '...'
            started = conv.get('start_time', 'unknown')[:19] if conv.get('start_time') else 'unknown'
            exchange_count = str(conv.get('exchange_count', 0))
            last_activity = conv.get('last_activity', 'unknown')[:19] if conv.get('last_activity') else 'unknown'

            # Mark current conversation
            status = "🔸 Current" if conv.get('conversation_id') == current_id else ""

            conv_table.add_row(conv_id, started, exchange_count, last_activity, status)

        self.console.print(Panel(
            conv_table,
            title=f"📝 Recent Conversations (showing {len(display_conversations)}/{len(conversations)})",
            border_style="blue"
        ))

        if len(conversations) > 10:
            self.console.print(f"[dim]Showing most recent 10 of {len(conversations)} total conversations[/dim]")

    def show_conversation_not_found(self, target_id: str):
        """
        Display switch failed notification

        Args:
            target_id: The conversation ID that was not found
        """
        self.console.print(Panel(
            f"[yellow]Could not switch to conversation '[cyan]{target_id}[/cyan]'.\n\n"
            f"Possible reasons:\n"
            f"• Conversation not found\n"
            f"• Multiple matches (be more specific)\n"
            f"• Episodic memory service unavailable[/yellow]",
            title="Switch Failed",
            border_style="yellow"
        ))

    def show_conversation_switched(self, old_id: str, old_count: int, new_id: str, new_count: int):
        """
        Display conversation switch success

        Args:
            old_id: Previous conversation ID (full)
            old_count: Number of exchanges in previous conversation
            new_id: New conversation ID (full)
            new_count: Number of exchanges in new conversation
        """
        self.console.print(Panel(
            f"🔄 **Conversation Switched**\n\n"
            f"• From: `{old_id[:8]}...` ({old_count} exchanges)\n"
            f"• To: `{new_id[:8]}...` ({new_count} exchanges)\n"
            f"• Loaded from episodic memory\n"
            f"• Ready to continue conversation",
            title="Conversation Switched",
            border_style="cyan"
        ))

    def display_recovery_result(self, result: Dict, fiwb_mode: bool = False):
        """
        Display recovery command results with appropriate formatting

        Args:
            result: Recovery result dictionary with type, title, content, footer
            fiwb_mode: Whether "FUCK IT WE BALL" mode is enabled (shows raw debug)
        """
        result_type = result.get('type', 'info')
        title = result.get('title', 'Recovery System')
        content = result.get('content', str(result))
        footer = result.get('footer', '')

        # Choose colors based on result type
        color_map = {
            'success': 'green',
            'error': 'red',
            'warning': 'yellow',
            'info': 'blue',
            'help': 'cyan',
            'status': 'blue',
            'analytics': 'magenta'
        }

        border_color = color_map.get(result_type, 'blue')

        # Format content with footer if present
        display_content = content
        if footer:
            display_content += f"\n\n[dim]{footer}[/dim]"

        self.console.print(Panel(
            display_content,
            title=title,
            border_style=border_color
        ))

        # Show raw result in FIWB mode for debugging
        if fiwb_mode:
            self.console.print(f"[dim]FIWB: Raw result: {result}[/dim]")

    def display_error_panel_if_enabled(self, show_error_panel: bool, error_handler,
                                       debug_mode: bool, recovery_chat=None):
        """
        Display error panel at bottom if enabled

        Args:
            show_error_panel: Whether error panel is enabled
            error_handler: ErrorHandler instance for retrieving alerts
            debug_mode: Whether debug mode is enabled (shows error summary)
            recovery_chat: Optional RecoveryChat instance for status display
        """
        if not show_error_panel:
            return

        # Get alerts from error handler (reuse the good logic!)
        current_alerts = error_handler.get_alerts_for_ui(max_alerts=5)

        # Always show panel when enabled, even if empty
        if not current_alerts:
            alerts_content = "[dim]No recent errors - panel ready for new alerts[/dim]"
        else:
            alerts_content = "\n".join(current_alerts)

        # Add error summary in debug mode
        if debug_mode:
            error_summary = error_handler.get_error_summary()
            if error_summary['total_errors'] > 0:
                alerts_content += f"\n\n[dim]Errors: {error_summary['total_errors']} | Suppressed: {error_summary['suppressed_count']}[/dim]"

        # Add recovery status if available
        if recovery_chat:
            try:
                dashboard_status = recovery_chat.get_status_for_dashboard()
                alerts_content = f"{dashboard_status}\n\n{alerts_content}"
            except:
                pass

        # Show simple panel at bottom
        error_panel = Panel(alerts_content, border_style="yellow", title="🚨 Recent Errors")
        self.console.print(error_panel)

    # ===== Command Handlers =====

    def toggle_token_display(self, new_value: bool):
        """
        Display feedback for token display toggle

        Args:
            new_value: New state of token display (True = ON, False = OFF)
        """
        status = "ON 📊" if new_value else "OFF 🔕"
        color = "cyan" if new_value else "green"

        self.console.print(Panel(
            f"Token display is now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, you'll see:\n"
            f"• Token counts in /context\n"
            f"• Token efficiency in /stats\n"
            f"• Model limit percentages",
            title="📊 Token Display",
            border_style=color
        ))

    def toggle_confidence_display(self, new_value: bool):
        """
        Display feedback for confidence display toggle

        Args:
            new_value: New state of confidence display (True = ON, False = OFF)
        """
        status = "ON 🤔" if new_value else "OFF 😐"
        color = "yellow" if new_value else "green"

        self.console.print(Panel(
            f"Confidence markers are now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, you'll see uncertainty indicators like:\n"
            f"• '~possibly~' = Medium confidence\n"
            f"• '?maybe?' = Low confidence\n"
            f"• 'SPECULATION:' = Very uncertain\n\n"
            f"These help you know when I'm guessing vs. when I'm sure.",
            title="🤔 Confidence Markers",
            border_style=color
        ))

    def toggle_debug_display(self, new_value: bool):
        """
        Display feedback for debug mode toggle

        Args:
            new_value: New state of debug mode (True = ON, False = OFF)
        """
        status = "ON 🔍" if new_value else "OFF 🔕"
        color = "yellow" if new_value else "green"

        self.console.print(Panel(
            f"Debug mode is now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, you'll see:\n"
            f"• Exact prompts sent to LLM\n"
            f"• Model responses\n"
            f"• Context management details",
            title="🐛 Debug Mode",
            border_style=color
        ))

    # ===== Progress Indicators =====

    def show_progress(self, message: str, style: str = "bold blue"):
        """
        Show progress message

        Args:
            message: Progress message to display
            style: Rich style for message
        """
        self.console.print(f"[{style}]{message}[/{style}]")

    def update_status(self, message: str):
        """Update current status message"""
        self.current_status = message
        self.console.print(f"[dim]{message}[/dim]")

    # ===== Response Rendering =====

    def render_response(self, response: str, confidence_score: Optional[float] = None,
                       show_confidence: bool = True, show_tokens: bool = False,
                       token_count: Optional[int] = None):
        """
        Render assistant response with optional metadata

        Args:
            response: Response text to display
            confidence_score: Optional confidence score
            show_confidence: Whether to show confidence markers
            show_tokens: Whether to show token count
            token_count: Optional token count
        """
        # Basic rendering for now
        self.console.print(response)

        # Show metadata if enabled
        metadata_parts = []
        if show_confidence and confidence_score is not None:
            metadata_parts.append(f"Confidence: {confidence_score:.2f}")
        if show_tokens and token_count is not None:
            metadata_parts.append(f"Tokens: {token_count}")

        if metadata_parts:
            metadata = " | ".join(metadata_parts)
            self.console.print(f"[dim]{metadata}[/dim]")

    # ===== Command Parsing =====

    def parse_command(self, user_input: str) -> Optional[str]:
        """
        Parse user input for commands

        Args:
            user_input: Raw user input

        Returns:
            Command name if input is a command, None otherwise
        """
        if not user_input.startswith('/'):
            return None

        # Extract command (remove leading slash, split on space)
        command = user_input[1:].split()[0].lower()
        return command

    def is_command(self, user_input: str) -> bool:
        """Check if input is a command"""
        return user_input.startswith('/')

    # ===== Error Display =====

    def display_error(self, error_msg: str, severity: str = "error"):
        """
        Display error message

        Args:
            error_msg: Error message to display
            severity: Severity level (error, warning, info)
        """
        styles = {
            'error': 'bold red',
            'warning': 'bold yellow',
            'info': 'bold blue'
        }
        style = styles.get(severity, 'bold red')
        self.console.print(f"[{style}]{'ERROR' if severity == 'error' else severity.upper()}: {error_msg}[/{style}]")


# Example usage
if __name__ == "__main__":
    # Test basic functionality
    console = Console()
    ui = UIHandler(console)

    ui.show_progress("Testing UI Handler...")
    ui.render_response("This is a test response", confidence_score=0.95)
    ui.display_error("This is a test error", severity="warning")

    print("UIHandler basic test complete!")
