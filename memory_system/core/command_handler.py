"""
Command Handler - Routing and validation for CLI commands

Separates command routing logic from business logic and UI rendering.
This class handles:
- Command validation (is this a valid command?)
- Command parsing (extract arguments from command string)
- Command routing (call the right method based on command)
- Command execution (execute the command with proper error handling)

Design principles:
- CommandHandler ROUTES commands, doesn't implement them
- Business logic stays in RichMemoryChat
- UI rendering delegated to UIHandler
- Dependency injection for testability
"""

from typing import Dict, Optional, Callable
from error_handler import ErrorCategory, ErrorSeverity


class CommandHandler:
    """Handles command parsing, validation, and routing"""

    # Valid commands organized by category
    VALID_COMMANDS = {
        'display': ['/help', '/status', '/context', '/stats', '/tree'],
        'toggle': ['/debug', '/tokens', '/confidence', '/errors', '/ball'],
        'memory': ['/memory', '/history', '/search'],
        'conversation': ['/new', '/list', '/switch'],
        'sidebar': ['/sidebar', '/merge', '/back', '/focus', '/pause'],
        'services': ['/services', '/start-services', '/stop-services'],
        'system': ['/recovery', '/quit']
    }

    def __init__(self, chat_instance, error_handler):
        """
        Initialize command handler

        Args:
            chat_instance: RichMemoryChat instance (for calling business logic)
            error_handler: ErrorHandler instance (for error reporting)
        """
        self.chat = chat_instance
        self.error_handler = error_handler

        # Build flat command list for validation
        self.all_commands = []
        for category_commands in self.VALID_COMMANDS.values():
            self.all_commands.extend(category_commands)

    def is_command(self, user_input: str) -> bool:
        """Check if input is a command"""
        return user_input.strip().startswith('/')

    def is_valid_command(self, user_input: str) -> bool:
        """
        Validate if command exists

        Args:
            user_input: Raw user input string

        Returns:
            True if command is valid, False otherwise
        """
        if not self.is_command(user_input):
            return True  # Not a command, so "valid" for non-command processing

        command = self.extract_command(user_input)

        # Handle special cases with arguments
        commands_with_args = ['/search', '/switch', '/recovery', '/sidebar', '/focus']
        if any(command.startswith(cmd) for cmd in commands_with_args):
            base_command = '/' + command.split()[0].lstrip('/')
            return base_command in self.all_commands

        return command in self.all_commands

    def extract_command(self, user_input: str) -> str:
        """
        Extract command from user input

        Args:
            user_input: Raw user input string

        Returns:
            Command string (e.g., '/help')
        """
        return user_input.split()[0] if user_input.strip() else ''

    def extract_args(self, user_input: str) -> str:
        """
        Extract arguments from command

        Args:
            user_input: Raw user input string (e.g., '/search hello world')

        Returns:
            Arguments string (e.g., 'hello world')
        """
        parts = user_input.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ''

    def handle_command(self, user_input: str) -> Dict:
        """
        Main command routing logic

        Args:
            user_input: Raw user input string

        Returns:
            Dict with:
                - handled: bool (was this a command that was handled?)
                - should_continue: bool (should main loop continue without processing?)
                - result: any (optional result from command execution)
        """
        if not self.is_command(user_input):
            return {'handled': False, 'should_continue': False}

        # Validate command
        if not self.is_valid_command(user_input):
            command = self.extract_command(user_input)
            self.chat.warning_message(
                f"Unknown command: {command}\nType /help for a list of valid commands",
                ErrorCategory.UI_INPUT
            )
            return {'handled': True, 'should_continue': True}

        command = self.extract_command(user_input)
        args = self.extract_args(user_input)

        # Route to appropriate handler
        return self._route_command(command, args)

    def _route_command(self, command: str, args: str) -> Dict:
        """
        Route command to appropriate handler method

        Args:
            command: Command string (e.g., '/help')
            args: Arguments string (e.g., 'search term')

        Returns:
            Command result dict
        """
        # Display commands
        if command == '/help':
            self.chat.show_help()
            return {'handled': True, 'should_continue': True}

        if command == '/status':
            self.chat.show_status()
            return {'handled': True, 'should_continue': True}

        if command == '/context':
            self.chat.show_context_preview()
            return {'handled': True, 'should_continue': True}

        if command == '/stats':
            self.chat.show_memory_stats()
            return {'handled': True, 'should_continue': True}

        # Toggle commands
        if command == '/debug':
            self.chat.toggle_debug_mode()
            return {'handled': True, 'should_continue': True}

        if command == '/tokens':
            self.chat.toggle_token_display()
            return {'handled': True, 'should_continue': True}

        if command == '/confidence':
            self.chat.toggle_confidence_display()
            return {'handled': True, 'should_continue': True}

        if command == '/errors':
            self.chat.toggle_error_panel()
            return {'handled': True, 'should_continue': True}

        if command == '/ball':
            self.chat.toggle_fuck_it_we_ball_mode()
            return {'handled': True, 'should_continue': True}

        # Memory commands
        if command == '/memory':
            self.chat.memory_handler.show_memory()
            return {'handled': True, 'should_continue': True}

        if command == '/history':
            self.chat.memory_handler.show_full_history()
            return {'handled': True, 'should_continue': True}

        if command == '/search':
            if args:
                self.chat.memory_handler.search_conversations(args)
            else:
                self.chat.warning_message(
                    "Usage: /search <term> - Search your conversation history",
                    ErrorCategory.UI_INPUT
                )
            return {'handled': True, 'should_continue': True}

        # Conversation commands
        if command == '/new':
            self.chat.start_new_conversation()
            return {'handled': True, 'should_continue': True}

        if command == '/list':
            self.chat.list_conversations()
            return {'handled': True, 'should_continue': True}

        if command == '/switch':
            if args:
                self.chat.switch_conversation(args)
            else:
                self.chat.warning_message(
                    "Usage: /switch <conversation_id>",
                    ErrorCategory.UI_INPUT
                )
            return {'handled': True, 'should_continue': True}

        # Sidebar commands
        if command == '/sidebar':
            if args:
                self.chat.spawn_sidebar(args)
            else:
                self.chat.warning_message(
                    "Usage: /sidebar <reason>\nExample: /sidebar Investigate the auth bug",
                    ErrorCategory.UI_INPUT
                )
            return {'handled': True, 'should_continue': True}

        if command == '/merge':
            self.chat.merge_current_sidebar(args if args else None)
            return {'handled': True, 'should_continue': True}

        if command == '/back':
            self.chat.back_to_parent()
            return {'handled': True, 'should_continue': True}

        if command == '/focus':
            if args:
                self.chat.focus_context(args)
            else:
                self.chat.warning_message(
                    "Usage: /focus <context_id>\nExample: /focus SB-1",
                    ErrorCategory.UI_INPUT
                )
            return {'handled': True, 'should_continue': True}

        if command == '/pause':
            self.chat.pause_current_context()
            return {'handled': True, 'should_continue': True}

        if command == '/tree':
            self.chat.show_context_tree()
            return {'handled': True, 'should_continue': True}

        # Service management commands
        if command == '/services':
            self.chat.service_manager.check_services(show_table=True)
            return {'handled': True, 'should_continue': True}

        if command == '/start-services':
            self.chat.service_manager.auto_start_services()
            return {'handled': True, 'should_continue': True}

        if command == '/stop-services':
            # Confirm before force-stopping (nuclear option)
            from rich.panel import Panel
            self.chat.console.print(Panel(
                "[yellow]⚠️  WARNING: This will force-stop ALL services on ports 5001, 8004, 8001, 8005\n"
                "This includes services started externally (not just by this chat).\n\n"
                "Are you sure? (y/n)[/yellow]",
                title="Confirm Force Stop",
                border_style="yellow"
            ))

            confirm = input("").strip().lower()
            if confirm == 'y':
                self.chat.service_manager.force_stop_all_services()
            else:
                self.chat.info_message("Service stop cancelled", ErrorCategory.SERVICE_MANAGEMENT)
            return {'handled': True, 'should_continue': True}

        # System commands
        if command == '/recovery':
            if self.chat.recovery_chat:
                # Reconstruct full command for recovery system
                full_command = f"{command} {args}".strip()
                result = self.chat.recovery_chat.process_command(full_command)
                self.chat._display_recovery_result(result)
            else:
                self.chat.warning_message(
                    "Recovery system not available",
                    ErrorCategory.RECOVERY_SYSTEM
                )
            return {'handled': True, 'should_continue': True}

        if command == '/quit':
            return {'handled': True, 'should_continue': False, 'quit': True}

        # Fallback (should never reach here if validation worked)
        return {'handled': False, 'should_continue': False}

    def get_help_text(self) -> str:
        """
        Get help text for commands (used by API bridge)

        Returns:
            Formatted help text string
        """
        return """Available Commands:

Display Commands:
  /help      - Show this help message
  /status    - Show system status
  /context   - Preview what context will be sent to LLM
  /stats     - Show memory statistics

Toggle Commands:
  /debug     - Toggle debug mode (show prompts/responses)
  /tokens    - Toggle token counter display
  /confidence - Toggle confidence markers
  /errors    - Toggle error panel display
  /ball      - Toggle FUCK IT WE BALL mode (max debug)

Memory Commands:
  /memory    - Show current working memory
  /history   - Show full conversation history
  /search <term> - Search conversation history

Conversation Commands:
  /new       - Start new conversation
  /list      - List previous conversations
  /switch <id> - Switch to previous conversation

Sidebar Commands:
  /sidebar <reason> - Spawn sidebar to investigate something
  /merge [summary]  - Merge current sidebar back to parent
  /back             - Go back to parent context
  /focus <id>       - Focus on a specific context (e.g., SB-1)
  /pause            - Pause current context
  /tree             - Show context tree

Service Commands:
  /services  - Check service health
  /start-services - Start memory services
  /stop-services - Stop memory services

System Commands:
  /recovery [cmd] - Recovery system commands
  /quit      - Exit the chat
"""


# Standalone test
if __name__ == "__main__":
    print("CommandHandler basic test...")

    # Mock objects for testing
    class MockChat:
        def __init__(self):
            self.show_help_called = False

        def show_help(self):
            self.show_help_called = True
            print("show_help() called")

    class MockErrorHandler:
        pass

    chat = MockChat()
    error_handler = MockErrorHandler()
    cmd_handler = CommandHandler(chat, error_handler)

    # Test command detection
    assert cmd_handler.is_command('/help') == True
    assert cmd_handler.is_command('hello') == False
    print("✅ Command detection works")

    # Test command extraction
    assert cmd_handler.extract_command('/help') == '/help'
    assert cmd_handler.extract_command('/search hello world') == '/search'
    print("✅ Command extraction works")

    # Test argument extraction
    assert cmd_handler.extract_args('/search hello world') == 'hello world'
    assert cmd_handler.extract_args('/help') == ''
    print("✅ Argument extraction works")

    # Test validation
    assert cmd_handler.is_valid_command('/help') == True
    assert cmd_handler.is_valid_command('/invalid') == False
    assert cmd_handler.is_valid_command('/search test') == True
    print("✅ Command validation works")

    print("\nCommandHandler basic test complete!")
