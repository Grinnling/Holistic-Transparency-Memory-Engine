#!/usr/bin/env python3
"""
Rich Chat Interface - Better UI with Rich library
Fancy terminal interface with proper formatting, panels, and input handling
"""

try:
    from rich.console import Console
    from rich.panel import Panel  
    from rich.text import Text
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.table import Table
    from rich.progress import track
    from rich.markdown import Markdown
    from rich.layout import Layout
    from rich.align import Align
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

import requests
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List
import sys
import os
import signal
import threading

# Import our modules
from llm_connector import SmartLLMSelector, LLMConnector
from skinflap_stupidity_detection import CollaborativeQueryReformer
from memory_distillation import MemoryDistillationEngine
from episodic_memory_coordinator import EpisodicMemoryCoordinator
from emergency_backup import EmergencyBackupSystem
from recovery_thread import RecoveryThread
from recovery_monitoring import RecoveryMonitor
from recovery_chat_commands import RecoveryChatInterface
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
from service_manager import ServiceManager
from memory_handler import MemoryHandler

class RichMemoryChat:
    def __init__(self, debug_mode=False, auto_start_services=False):
        """Initialize chat with optional debug mode and auto-start
        
        Args:
            debug_mode: Show debug info (prompts, context, etc.)
            auto_start_services: Automatically start memory services if not running
        """
        if not RICH_AVAILABLE:
            print("❌ Rich library not available. Install with: pip install rich")
            print("Falling back to basic chat interface...")
            return None
            
        # Configure console to prevent readline conflicts
        self.console = Console(
            force_terminal=True,
            width=None,  # Auto-detect but don't override readline
            legacy_windows=False
        )
        self.debug_mode = debug_mode
        self.show_tokens = False  # Toggle for token display
        self.show_confidence = True  # Toggle for uncertainty markers
        self.episodic_archival_failures = 0  # Track archival health
        self.fuck_it_we_ball_mode = False  # Debug mode for critical operations
        
        # Initialize ErrorHandler FIRST (before anything that might error)
        self.error_handler = ErrorHandler(
            console=self.console,
            debug_mode=debug_mode,
            fuck_it_we_ball_mode=self.fuck_it_we_ball_mode
        )
        
        # UI state
        self.status_messages = []  # Queue for status messages
        # self.alert_messages removed - now using error_handler.alert_queue
        self.show_error_panel = False  # Toggle for simple error panel

        # Initialize ServiceManager - now handles all service operations
        self.service_manager = ServiceManager(
            console=self.console,
            error_handler=self.error_handler,
            debug_mode=self.debug_mode
        )

        # Initialize MemoryHandler - now handles memory archival and display
        self.memory_handler = MemoryHandler(
            console=self.console,
            error_handler=self.error_handler,
            debug_mode=self.debug_mode
        )

        # Auto-start services if requested
        if auto_start_services:
            self.service_manager.auto_start_services()
        
        # Initialize emergency backup and recovery systems
        try:
            self.backup_system = EmergencyBackupSystem()
            self.recovery_thread = RecoveryThread(
                self.backup_system,
                error_handler=self.error_handler,
                interval=30
            )
            self.recovery_monitor = RecoveryMonitor(self.recovery_thread, error_handler=self.error_handler)
            self.recovery_chat = RecoveryChatInterface(self.recovery_thread, self.recovery_monitor)
            self.episodic_coordinator = EpisodicMemoryCoordinator(
                backup_system=self.backup_system,
                error_handler=self.error_handler
            )
            
            # Start recovery thread in background
            self.recovery_thread.start_recovery_thread()
            
            if self.debug_mode:
                self.success_message(
                    "✅ Emergency backup and recovery systems initialized", 
                    ErrorCategory.BACKUP_SYSTEM
                )
        except Exception as e:
            self.warning_message(
                f"⚠️ Backup system not available: {e}",
                ErrorCategory.BACKUP_SYSTEM
            )
            self.backup_system = None
            self.episodic_coordinator = None
            self.recovery_chat = None
        
        # Initialize components
        self.conversation_id = str(uuid.uuid4())
        self.conversation_history = []
        
        # Try to restore previous conversation
        self.restore_conversation_history()
        
        # Initialize LLM, Skinflap, and Memory Distillation
        with self.console.status("[bold blue]Initializing systems..."):
            self.llm = SmartLLMSelector.find_available_llm(debug_mode=self.debug_mode)
            self.skinflap = CollaborativeQueryReformer()
            self.distillation_engine = MemoryDistillationEngine()
            self.memory_buffer_limit = 100  # Trigger distillation at 100 exchanges
            self.generation_interrupted = False  # Flag for stopping generation
            # Check service health with extras (LLM, Skinflap)
            extras = {
                "LLM": ("✅ Connected" if self.llm else "⚠️ Fallback",
                       f"{self.llm.provider.value}" if self.llm else "No LLM service found"),
                "Skinflap": ("✅ Ready", "Query quality detector")
            }
            self.services_healthy = self.service_manager.check_services(show_table=True, include_extras=extras)

            # Inject dependencies into MemoryHandler
            self.memory_handler.inject_dependencies(
                conversation_history=self.conversation_history,
                conversation_id=self.conversation_id,
                services=self.service_manager.services,
                episodic_coordinator=self.episodic_coordinator,
                show_confidence=self.show_confidence,
                show_tokens=self.show_tokens,
                fuck_it_we_ball_mode=self.fuck_it_we_ball_mode,
                recovery_chat=self.recovery_chat
            )

        # Set up signal handler for graceful interruption
        signal.signal(signal.SIGINT, self.signal_handler)
    
    # Service management methods removed - now handled by ServiceManager
    
    def restore_conversation_history(self):
        """Restore recent conversation history from working memory and episodic memory"""
        try:
            # First try working memory for recent exchanges
            response = requests.get(
                f"{self.services['working_memory']}/working-memory",
                params={"limit": 30},  # Reduced to leave room for episodic
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                exchanges = data.get('context', [])
                
                for exchange in exchanges:
                    self.conversation_history.append({
                        'user': exchange.get('user_message', ''),
                        'assistant': exchange.get('assistant_response', ''),
                        'exchange_id': exchange.get('exchange_id', ''),
                        'timestamp': exchange.get('created_at', ''),
                        'restored': True,
                        'source': 'working_memory'
                    })
                
                working_count = len(exchanges)
            else:
                working_count = 0
                
            # Try episodic memory for additional context
            try:
                episodic_response = requests.get(
                    f"{self.services['episodic_memory']}/recent",
                    params={"limit": 20},  # Additional recent conversations
                    timeout=5
                )
                if episodic_response.status_code == 200:
                    episodic_data = episodic_response.json()
                    conversations = episodic_data.get('conversations', [])
                    
                    # Add episodic conversations (avoid duplicates by checking timestamps)
                    existing_timestamps = {ex.get('timestamp', '') for ex in self.conversation_history}
                    
                    episodic_count = 0
                    for conv in conversations:
                        # Extract key exchanges from conversation
                        exchanges = conv.get('exchanges', [])
                        for exchange in exchanges[-2:]:  # Last 2 from each conversation
                            timestamp = exchange.get('timestamp', '')
                            if timestamp not in existing_timestamps:
                                self.conversation_history.append({
                                    'user': exchange.get('user_input', ''),
                                    'assistant': exchange.get('assistant_response', ''),
                                    'exchange_id': exchange.get('exchange_id', ''),
                                    'timestamp': timestamp,
                                    'restored': True,
                                    'source': 'episodic_memory'
                                })
                                episodic_count += 1
                                
                    if episodic_count > 0:
                        self.debug_message(f"Added {episodic_count} exchanges from episodic memory", ErrorCategory.HISTORY_RESTORATION)
            except Exception as e:
                self.error_handler.handle_error(
                    e,
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.LOW_DEBUG,
                    context="Loading episodic memory for history restoration",
                    operation="episodic_history_fallback"
                )
                
            total_restored = working_count + episodic_count if 'episodic_count' in locals() else working_count
            if total_restored > 0:
                self.debug_message(f"Restored {total_restored} total exchanges ({working_count} working + {episodic_count if 'episodic_count' in locals() else 0} episodic)", ErrorCategory.HISTORY_RESTORATION)
                        
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.HISTORY_RESTORATION,
                ErrorSeverity.LOW_DEBUG,
                context="Restoring conversation history",
                operation="restore_conversation_history"
            )
    
    def process_message(self, user_message: str) -> Dict:
        """Process message with rich progress indicators"""
        result = {}

        try:
            with self.console.status("[bold blue]Processing message...") as status:
                # Step 1: Skinflap check (now includes clarity detection)
                status.update("[bold yellow]🔍 Checking query quality...")
                skinflap_result = self.check_with_skinflap(user_message)

                # Step 2: Retrieve relevant episodic memories
                status.update("[bold cyan]🧠 Retrieving relevant memories...")
                relevant_memories = self.memory_handler.retrieve_relevant_memories(user_message, top_k=5)

                # Step 3: Generate response with skinflap detection info and memories (interruptible)
                status.update("[bold green]🤖 Generating response...")
                self.generation_interrupted = False  # Reset flag
                # Restore signal handler
                signal.signal(signal.SIGINT, self.signal_handler)

                # Pass the detection info directly - the LLM connector expects detected_issues at the top level
                detection_info = skinflap_result.get('detection_info', {})
                assistant_response = self.generate_response_interruptible(
                    user_message,
                    skinflap_detection=detection_info,
                    relevant_memories=relevant_memories
                )

                # Check if generation was interrupted
                if self.generation_interrupted:
                    return {
                        'response': "[yellow]⚠️  Response generation was interrupted.[/yellow]",
                        'type': 'interrupted',
                        'partial_response': assistant_response
                    }

                # Step 4: Store in memory
                status.update("[bold cyan]💾 Storing in memory...")
                exchange_id = self.store_exchange(user_message, assistant_response)

                # Step 5: Validate
                status.update("[bold magenta]✅ Validating response...")
                validation = self.validate_with_curator(user_message, assistant_response)

            # Add confidence markers if enabled
            enhanced_response = self.add_confidence_markers(assistant_response, user_message)

            # Add to history
            self.conversation_history.append({
                'user': user_message,
                'assistant': enhanced_response,
                'exchange_id': exchange_id,
                'validation': validation,
                'timestamp': datetime.now().isoformat(),
                'source': 'current'
            })

            # Archive to episodic memory (async, non-blocking)
            self.memory_handler.archive_to_episodic_memory(user_message, enhanced_response, exchange_id)

            result_dict = {
                'response': enhanced_response,
                'type': 'normal',
                'validation': validation
            }
            print(f"DEBUG: About to return result_dict: {type(result_dict)}, keys: {result_dict.keys()}")
            return result_dict
        except Exception as e:
            # Let exception bubble up to API layer for centralized error tracking
            raise
    
    def check_with_skinflap(self, user_message: str) -> Dict:
        """Check with skinflap detector and return detection info"""
        result = self.skinflap.process_query(user_message, [])
        
        # Instead of blocking, return detection info for the model to consider
        return {
            'needs_clarification': False,  # Never block - let model decide
            'detection_info': {
                'detected_issues': result.detected_issues,
                'ready_for_processing': result.ready_for_processing,
                'has_serious_issues': len(result.detected_issues) >= 2,
                'has_serious_patterns': any(
                    issue['pattern'] in ['impossible_request', 'scope_creep_tracker', 'wrong_problem_solver'] 
                    for issue in result.detected_issues
                )
            }
        }
    
    def generate_silly_response(self, issues: List[Dict]) -> str:
        """Generate silly responses with rich formatting"""
        primary_patterns = [issue['pattern'] for issue in issues]
        
        if 'impossible_request' in primary_patterns:
            return """🎭 **Hark! The Impossible Triangle!**
            
*adjusts ruff collar dramatically*

Thou dost ask for what mortals call the "impossible triangle" - 
that a thing be **PERFECT**, **SWIFT**, and of **NO COST** all at once!

Choose thee wisely, noble patron:
• Perfect and Swift (but costly as dragon's gold) 💰
• Swift and Cheap (but rough as peasant's bread) ⚡  
• Perfect and Cheap (but slow as winter's end) 🐌

*bows with flourish*"""
        
        elif 'scope_creep_tracker' in primary_patterns:
            return """🏴‍☠️ **Ahoy! Scope Creep Detected!**
            
*brandishes cutlass*

Ye be addin' more cargo to this here ship than she can handle!
That request be growin' like barnacles on a hull!

Started with **one thing**, now ye want the whole **Spanish treasure fleet**!

How about we chart a course for yer **MAIN objective** first, 
then we can plunder the rest later, savvy? 

*tips tricorn hat with style* ⚓"""
        
        else:
            return """🤖 **BEEP BOOP - QUERY ANALYSIS ERROR**
            
*mechanical whirring*

INSUFFICIENT DATA FOR OPTIMAL PROCESSING.
PLEASE PROVIDE MORE SPECIFIC PARAMETERS.

*LED lights blinking frantically* 💡"""
    
    def store_exchange(self, user_message: str, assistant_response: str):
        """Store in working memory"""
        with self.error_handler.create_context_manager(
            ErrorCategory.WORKING_MEMORY,
            ErrorSeverity.HIGH_DEGRADE,  # Data loss is serious!
            operation="store_exchange",
            context=f"Storing {len(user_message)} char message"
        ):
            response = requests.post(
                f"{self.services['working_memory']}/working-memory",
                json={
                    "user_message": user_message,
                    "assistant_response": assistant_response,
                    "context_used": ["rich_chat"]
                },
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get('exchange', {}).get('exchange_id', 'unknown')
            else:
                # Raise exception so error handler catches it
                raise Exception(f"Working memory returned {response.status_code}")
        return None
    
    def validate_with_curator(self, user_message: str, assistant_response: str):
        """Validate with curator"""
        try:
            response = requests.post(
                f"{self.services['curator']}/validate",
                json={
                    "exchange_data": {
                        "user_message": user_message,
                        "assistant_response": assistant_response
                    }
                },
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get('validation', {}).get('result', {})
        except:
            pass
        return None

    # Memory archival methods removed - now handled by MemoryHandler

    def generate_response(self, user_message: str, skinflap_detection=None) -> str:
        """Generate response using LLM or fallback"""
        if self.llm:
            try:
                return self.llm.generate_response(user_message, self.conversation_history, skinflap_detection=skinflap_detection)
            except:
                pass
        
        return f"I understand you're asking: '{user_message}'. Let me help with that."
    
    def generate_response_interruptible(self, user_message: str, skinflap_detection=None, relevant_memories=None) -> str:
        """Generate response with interruption support and optional skinflap detection info"""
        if not self.llm:
            return f"I understand you're asking: '{user_message}'. Let me help with that."

        try:
            # Use a thread for generation so we can monitor interruption
            result = {'response': None, 'error': None}

            def generate_in_thread():
                try:
                    result['response'] = self.llm.generate_response(
                        user_message,
                        self.conversation_history,
                        skinflap_detection=skinflap_detection,
                        relevant_memories=relevant_memories
                    )
                except Exception as e:
                    self.error_handler.handle_error(
                        e,
                        ErrorCategory.LLM_COMMUNICATION,
                        ErrorSeverity.MEDIUM_ALERT,
                        context=f"Generating response for: {user_message[:50]}...",
                        operation="generate_response_thread"
                    )
                    result['error'] = str(e)
            
            generation_thread = threading.Thread(target=generate_in_thread)
            generation_thread.daemon = True
            generation_thread.start()
            
            # Monitor for interruption while generation runs
            while generation_thread.is_alive():
                if self.generation_interrupted:
                    # Can't actually stop the HTTP request, but can abandon it
                    return "[yellow]Generation interrupted - response may be incomplete.[/yellow]"
                generation_thread.join(timeout=0.1)  # Check every 100ms

            if result['error']:
                # Error already logged in generate_in_thread, just return user message
                return f"Error generating response: {result['error']}"
            
            return result['response'] if result['response'] else "No response generated."
            
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.CHAT_PROCESSING,
                ErrorSeverity.MEDIUM_ALERT,
                context=f"Interruptible generation outer handler: {user_message[:50]}...",
                operation="generate_response_interruptible_outer"
            )
            return f"I understand you're asking: '{user_message}'. (Generation error: {str(e)})"
    
    def show_status(self):
        """Show fancy status panel"""
        status_table = Table(title="📊 System Status")
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="green")
        
        status_table.add_row("Conversation ID", self.conversation_id[:12] + "...")
        status_table.add_row("Messages", str(len(self.conversation_history)))
        status_table.add_row("Services", "✅ Healthy" if self.services_healthy else "⚠️ Issues")
        status_table.add_row("LLM", "✅ Connected" if self.llm else "⚠️ Fallback")
        
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
    
    # Memory display methods removed - now handled by MemoryHandler
    
    def show_help(self):
        """Show comprehensive help with command explanations"""
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
        stats = self.get_memory_stats()
        status_text = f"""
Current Session: {stats['current_session_count']} exchanges | Restored: {stats['restored_count']} | Pressure: {stats['pressure']:.0%}
Debug: {'ON' if self.debug_mode else 'OFF'} | Tokens: {'ON' if self.show_tokens else 'OFF'} | Confidence: {'ON' if self.show_confidence else 'OFF'}
        """
        
        self.console.print(Panel(status_text.strip(), title="🔧 Current Settings", border_style="yellow"))
    
    def show_context_preview(self):
        """Show what context would be sent to LLM"""
        if not self.conversation_history:
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
        
        for exchange in self.conversation_history[-5:]:
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
        if self.show_tokens:
            estimated_tokens = self.estimate_tokens(total_chars)
            token_color = "red" if estimated_tokens > 1500 else "yellow" if estimated_tokens > 1000 else "green"
            stats_table.add_row("Estimated Tokens", f"[{token_color}]{estimated_tokens}[/{token_color}]", f"~{estimated_tokens/2000:.0%} of model limit")
            stats_table.add_row("Token Efficiency", f"{estimated_tokens/(row_num-1):.0f}" if row_num > 1 else "0", "avg tokens per message")
        
        stats_table.add_row("Context Strategy", "Last 5 exchanges + system")
        stats_table.add_row("Restored Count", str(sum(1 for ex in self.conversation_history if ex.get('restored'))))
        stats_table.add_row("Current Count", str(sum(1 for ex in self.conversation_history if not ex.get('restored'))))
        
        self.console.print(Panel(context_table, border_style="blue"))
        self.console.print(Panel(stats_table, border_style="yellow"))
    
    def toggle_debug_mode(self):
        """Toggle debug mode on/off"""
        self.debug_mode = not self.debug_mode
        self.llm.debug_mode = self.debug_mode  # Update LLM debug mode too
        
        status = "ON 🔍" if self.debug_mode else "OFF 🔕"
        color = "yellow" if self.debug_mode else "green"
        
        self.console.print(Panel(
            f"Debug mode is now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, you'll see:\n"
            f"• Exact prompts sent to LLM\n"
            f"• Model responses\n"
            f"• Context management details",
            title="🐛 Debug Mode",
            border_style=color
        ))
    
    def check_memory_pressure(self):
        """Check if memory buffer needs distillation"""
        current_count = len(self.conversation_history)
        
        # Trigger distillation if we're at or above limit
        if current_count >= self.memory_buffer_limit:
            self.warning_message(f"Memory buffer full ({current_count}/{self.memory_buffer_limit}) - Time for distillation!", ErrorCategory.MEMORY_DISTILLATION)
            
            # Run distillation audit
            filtered_history = self.distillation_engine.show_distillation_audit(
                self.conversation_history, 
                buffer_limit=50  # Keep 50 after distillation
            )
            
            # Update conversation history with filtered/compressed version
            self.conversation_history = filtered_history
            
            self.success_message(f"Memory distilled! Kept {len(filtered_history)} exchanges", ErrorCategory.MEMORY_DISTILLATION)
        
        # Show memory pressure indicator if getting close
        elif current_count >= self.memory_buffer_limit * 0.8:  # 80% threshold
            pressure = current_count / self.memory_buffer_limit
            self.info_message(f"Memory pressure: {pressure:.0%} ({current_count}/{self.memory_buffer_limit})", ErrorCategory.MEMORY_DISTILLATION)
    
    def get_memory_stats(self) -> Dict:
        """Get current memory statistics"""
        current_count = len(self.conversation_history)
        restored_count = sum(1 for ex in self.conversation_history if ex.get('restored', False))
        
        return {
            'current_exchanges': current_count,
            'buffer_limit': self.memory_buffer_limit,
            'pressure': current_count / self.memory_buffer_limit,
            'restored_count': restored_count,
            'current_session_count': current_count - restored_count
        }
    
    def estimate_tokens(self, text_or_char_count) -> int:
        """Estimate token count from text or character count"""
        if isinstance(text_or_char_count, str):
            char_count = len(text_or_char_count)
        else:
            char_count = text_or_char_count
            
        # More accurate token estimation
        # Average: 1 token ≈ 3.5-4 characters for English
        return int(char_count / 3.7)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully during generation"""
        if signum == signal.SIGINT:
            self.generation_interrupted = True
            self.warning_message("Generation interrupted. Press Ctrl+C again to exit chat.", ErrorCategory.UI_INPUT)
            # Reset signal handler to default for second Ctrl+C
            signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    def toggle_token_display(self):
        """Toggle token display on/off"""
        self.show_tokens = not self.show_tokens
        
        status = "ON 📊" if self.show_tokens else "OFF 🔕"
        color = "cyan" if self.show_tokens else "green"
        
        self.console.print(Panel(
            f"Token display is now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, you'll see:\n"
            f"• Token counts in /context\n"
            f"• Token efficiency in /stats\n"
            f"• Model limit percentages",
            title="📊 Token Display",
            border_style=color
        ))
    
    def toggle_confidence_display(self):
        """Toggle confidence/uncertainty markers on/off"""
        self.show_confidence = not self.show_confidence
        
        status = "ON 🤔" if self.show_confidence else "OFF 😐"
        color = "yellow" if self.show_confidence else "green"
        
        self.console.print(Panel(
            f"Confidence markers are now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, I'll show:\n"
            f"• Uncertainty indicators (\"I'm not sure...\")\n"
            f"• Confidence levels in responses\n"
            f"• Areas where I might be guessing\n"
            f"• Suggestions to clarify ambiguous requests",
            title="🤔 Confidence Display",
            border_style=color
        ))
    
    def add_confidence_markers(self, response: str, user_message: str) -> str:
        """Add confidence markers to response if enabled"""
        if not self.show_confidence:
            return response
            
        # Detect uncertainty patterns and add markers
        uncertainty_triggers = [
            ("current", "I don't have access to current/real-time information"),
            ("weather", "I can't check current weather conditions"),
            ("stock", "I don't have access to current market data"),
            ("breaking news", "I can't access current news"),
            ("specific person", "I may not have current information about specific individuals"),
            ("exact number", "This number might not be completely accurate"),
            ("recent events", "My information might be outdated for recent events")
        ]
        
        user_lower = user_message.lower()
        confidence_note = ""
        
        for trigger, note in uncertainty_triggers:
            if trigger in user_lower:
                confidence_note = f"\n\n🤔 **Confidence Note:** {note}"
                break
        
        # Add general uncertainty markers for vague questions
        vague_patterns = ["make it better", "fix this", "help me", "what should i do"]
        if any(pattern in user_lower for pattern in vague_patterns):
            if not confidence_note:
                confidence_note = "\n\n🤔 **Confidence Note:** This seems like a broad request - I might need more specifics to give you the most helpful response."
        
        return response + confidence_note
    
    def check_for_clarification_needed(self, user_message: str) -> Dict:
        """Check if user message needs clarification and provide shortcuts"""
        user_lower = user_message.lower().strip()
        
        # Patterns that need clarification
        clarification_patterns = {
            "vague_references": [
                ("that", "I see you mentioned 'that' - could you specify what you're referring to?"),
                ("it", "When you say 'it', what specifically are you talking about?"),
                ("this thing", "What specific thing are you referring to?"),
                ("the bug", "Which bug specifically? I'd need more details to help."),
                ("the feature", "Which feature are you thinking of?"),
                ("the problem", "What problem exactly are you experiencing?")
            ],
            "action_without_context": [
                ("make it better", "What specifically would you like me to improve? Performance, functionality, or something else?"),
                ("fix it", "What needs to be fixed? Could you describe the issue you're seeing?"),
                ("optimize", "What aspect should I optimize - speed, memory usage, code clarity?"),
                ("improve", "What kind of improvement are you looking for?"),
                ("enhance", "What specific enhancement did you have in mind?"),
                ("update", "What should be updated and how?")
            ],
            "missing_specifics": [
                ("add that feature", "Which feature specifically? I'd be happy to help once I know what you need."),
                ("use the library", "Which library are you referring to?"),
                ("run the script", "Which script should I help you with?"),
                ("check the logs", "Which logs would you like me to look at?"),
                ("test the function", "Which function needs testing?")
            ]
        }
        
        # Check for patterns
        for category, patterns in clarification_patterns.items():
            for pattern, clarification in patterns:
                if pattern in user_lower:
                    # Try to provide context-aware clarification
                    context_hint = self.get_recent_context_hint()
                    
                    if context_hint:
                        enhanced_clarification = f"{clarification}\n\nBased on our recent conversation, you might be referring to: {context_hint}"
                    else:
                        enhanced_clarification = clarification
                    
                    return {
                        'needs_clarification': True,
                        'clarification_message': f"🤔 **Need clarification:** {enhanced_clarification}",
                        'pattern_type': category,
                        'original_pattern': pattern
                    }
        
        return {'needs_clarification': False}
    
    def get_recent_context_hint(self) -> str:
        """Get hints from recent conversation for better clarification"""
        if len(self.conversation_history) < 2:
            return ""
            
        # Look at last few exchanges for context clues
        recent_topics = []
        for exchange in self.conversation_history[-3:]:
            user_msg = exchange.get('user', '').lower()
            
            # Extract potential topics (nouns that might be referenced)
            topic_keywords = ['bug', 'feature', 'function', 'error', 'issue', 'code', 'script', 'library']
            for keyword in topic_keywords:
                if keyword in user_msg:
                    # Try to extract more context around the keyword
                    words = user_msg.split()
                    for i, word in enumerate(words):
                        if keyword in word:
                            # Get surrounding context
                            start = max(0, i-2)
                            end = min(len(words), i+3)
                            context = ' '.join(words[start:end])
                            recent_topics.append(context)
                            break
        
        if recent_topics:
            return ', '.join(recent_topics[-2:])  # Last 2 topics
        return ""
    
    def show_memory_stats(self):
        """Show detailed memory statistics and distillation info"""
        stats = self.get_memory_stats()

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
        if self.show_tokens:
            total_context_chars = sum(len(ex.get('user', '') + ex.get('assistant', '')) for ex in self.conversation_history)
            estimated_context_tokens = self.estimate_tokens(total_context_chars)
            token_color = "red" if estimated_context_tokens > 1500 else "yellow" if estimated_context_tokens > 1000 else "green"

            memory_table.add_row(
                "Context Tokens",
                f"[{token_color}]{estimated_context_tokens}[/{token_color}]",
                f"~{estimated_context_tokens/2000:.0%} of model limit"
            )

        self.console.print(Panel(memory_table, border_style="blue"))

        # Show distillation learning progress
        self.distillation_engine.show_learning_progress()

    def start_new_conversation(self):
        """Start a fresh conversation (keeps memory, resets context)"""
        old_id = self.conversation_id[:8]
        
        # Generate new conversation ID
        import uuid
        self.conversation_id = str(uuid.uuid4())
        
        # Clear current conversation history (but memory services keep their data)
        old_count = len(self.conversation_history)
        self.conversation_history = []
        
        # Reset failure counters
        self.episodic_archival_failures = 0
        
        self.console.print(Panel(
            f"🆕 **New Conversation Started**\n\n"
            f"• Previous: `{old_id}...` ({old_count} exchanges)\n"
            f"• Current: `{self.conversation_id[:8]}...`\n"
            f"• Memory services retain all data\n"
            f"• Fresh context for new topic",
            title="New Conversation",
            border_style="cyan"
        ))
    
    def list_conversations(self):
        """List previous conversations from episodic memory"""
        try:
            # Get conversation list from episodic memory
            response = requests.get(
                f"{self.services['episodic_memory']}/conversations",
                timeout=5
            )
            
            if response.status_code == 200:
                conversations = response.json().get('conversations', [])
                
                if not conversations:
                    self.console.print(Panel(
                        "No previous conversations found in episodic memory.",
                        title="📝 Conversation History",
                        border_style="blue"
                    ))
                    return
                
                # Build conversation table
                from rich.table import Table
                conv_table = Table(show_header=True, header_style="bold blue")
                conv_table.add_column("ID", style="cyan", width=12)
                conv_table.add_column("Started", style="green", width=19)
                conv_table.add_column("Exchanges", justify="right", style="yellow")
                conv_table.add_column("Last Activity", style="magenta", width=19)
                conv_table.add_column("Status", width=8)
                
                for conv in conversations[-10:]:  # Show last 10
                    conv_id = conv.get('conversation_id', 'unknown')[:8] + '...'
                    started = conv.get('start_time', 'unknown')[:19] if conv.get('start_time') else 'unknown'
                    exchange_count = str(conv.get('exchange_count', 0))
                    last_activity = conv.get('last_activity', 'unknown')[:19] if conv.get('last_activity') else 'unknown'
                    
                    # Mark current conversation
                    status = "🔸 Current" if conv.get('conversation_id') == self.conversation_id else ""
                    
                    conv_table.add_row(conv_id, started, exchange_count, last_activity, status)
                
                self.console.print(Panel(
                    conv_table,
                    title=f"📝 Recent Conversations (showing {len(conversations[-10:])}/{len(conversations)})",
                    border_style="blue"
                ))
                
                if len(conversations) > 10:
                    self.console.print(f"[dim]Showing most recent 10 of {len(conversations)} total conversations[/dim]")
            else:
                self.warning_message("Could not retrieve conversation list from episodic memory", ErrorCategory.EPISODIC_MEMORY)
                
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.EPISODIC_MEMORY,
                ErrorSeverity.HIGH_DEGRADE,
                context="Accessing conversation list",
                operation="list_conversations"
            )
    
    def switch_conversation(self, target_id: str):
        """Switch to a different conversation by ID"""
        try:
            # Expand partial ID if needed (user might type first 8 chars)
            if len(target_id) < 36:  # Not a full UUID
                # Get conversation list and find match
                response = requests.get(
                    f"{self.services['episodic_memory']}/conversations",
                    timeout=5
                )
                
                if response.status_code == 200:
                    conversations = response.json().get('conversations', [])
                    matches = [conv for conv in conversations if conv.get('conversation_id', '').startswith(target_id)]
                    
                    if len(matches) == 0:
                        self.warning_message(f"No conversation found starting with '{target_id}'", ErrorCategory.EPISODIC_MEMORY)
                        return
                    elif len(matches) > 1:
                        self.warning_message(f"Multiple conversations match '{target_id}'. Be more specific.", ErrorCategory.UI_INPUT)
                        return
                    else:
                        target_id = matches[0]['conversation_id']
            
            # Save current conversation to episodic memory if it has exchanges
            if self.conversation_history:
                self.console.print("[dim]Saving current conversation...[/dim]")
            
            # Load target conversation from episodic memory
            response = requests.get(
                f"{self.services['episodic_memory']}/conversation/{target_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                conv_data = response.json().get('conversation', {})
                exchanges = conv_data.get('exchanges', [])
                
                old_id = self.conversation_id[:8]
                old_count = len(self.conversation_history)
                
                # Switch to new conversation
                self.conversation_id = target_id
                self.conversation_history = []
                
                # Load exchanges into conversation history
                for exchange in exchanges:
                    self.conversation_history.append({
                        'user': exchange.get('user_input', ''),
                        'assistant': exchange.get('assistant_response', ''),
                        'timestamp': exchange.get('timestamp'),
                        'restored': True  # Mark as restored
                    })
                
                self.console.print(Panel(
                    f"🔄 **Conversation Switched**\n\n"
                    f"• From: `{old_id}...` ({old_count} exchanges)\n"
                    f"• To: `{target_id[:8]}...` ({len(exchanges)} exchanges)\n"
                    f"• Loaded {len(exchanges)} exchanges from episodic memory\n"
                    f"• Ready to continue conversation",
                    title="Conversation Switched",
                    border_style="cyan"
                ))
            else:
                self.error_handler.handle_error(
                    Exception(f"Could not load conversation '{target_id[:8]}...' from episodic memory"),
                    ErrorCategory.EPISODIC_MEMORY,
                    ErrorSeverity.HIGH_DEGRADE,
                    context=f"Loading conversation {target_id[:8]}",
                    operation="switch_conversation"
                )
                
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.EPISODIC_MEMORY,
                ErrorSeverity.HIGH_DEGRADE,
                context=f"Switching to conversation {target_id[:8]}",
                operation="switch_conversation"
            )
    
    def cleanup_services(self):
        """Clean up auto-started services on exit"""
        # Debug: Show what we have (using warning_message to ensure visibility)
        import time
        timestamp = int(time.time()) % 1000
        if hasattr(self, 'service_processes'):
            self.warning_message(f"[{timestamp}] STOP-DEBUG: Found service_processes: {list(self.service_processes.keys()) if self.service_processes else 'empty'}", ErrorCategory.SERVICE_MANAGEMENT)
        else:
            self.warning_message(f"[{timestamp}] STOP-DEBUG: No service_processes attribute found", ErrorCategory.SERVICE_MANAGEMENT)

        if hasattr(self, 'service_processes') and self.service_processes:
            self.info_message("Stopping auto-started services...", ErrorCategory.SERVICE_MANAGEMENT)
            for service, process in self.service_processes.items():
                if process.poll() is None:  # Still running
                    try:
                        process.terminate()
                        self.debug_message(f"Stopped {service} (PID: {process.pid})", ErrorCategory.SERVICE_MANAGEMENT)
                    except:
                        pass
        else:
            self.info_message("No auto-started services to stop", ErrorCategory.SERVICE_MANAGEMENT)
            # Give processes time to terminate gracefully
            import time
            time.sleep(1)
    
    def run(self):
        """Main chat loop with rich interface"""
        if not RICH_AVAILABLE:
            self.console.print("❌ Rich not available")
            return

        # Check if we should use the new panel layout
        use_panel_layout = os.environ.get('RICH_PANEL_UI', 'false').lower() == 'true'

        if use_panel_layout:
            self.run_panel_ui()
        else:
            # Direct to legacy UI (now the only UI)
            self.run_legacy_ui()
    
    def run_panel_ui(self):
        """New panel-based UI with better layout management - simplified approach"""
        # For now, fall back to legacy UI with a note
        self.console.print(Panel(
            "[yellow]Panel UI is under development. Using standard UI for now.[/yellow]\n\n"
            "The panel UI will provide:\n"
            "• Fixed input area at bottom (solves visibility issue)\n"
            "• Status bar showing service health\n"
            "• Side panel for errors\n"
            "• Better queue management display",
            title="🚧 Panel UI Preview",
            border_style="yellow"
        ))

        # Use legacy UI for now
        self.run_legacy_ui()
        return

        # TODO: Implement proper panel UI
        # The issue is that Rich's Live display doesn't work well with input()
        # We need either:
        # 1. A custom input handler that works with Live
        # 2. A different approach using alternate screen buffer
        # 3. Simpler panel updates between prompts

        try:
                while True:
                    # Update layout components
                    self._update_status_bar(layout)
                    self._update_chat_panel(layout)
                    self._update_input_panel(layout)
                    if self.show_error_panel:
                        self._update_error_panel(layout)

                    # Manual refresh for controlled updates
                    live.refresh()

                    # Stop live display temporarily for input
                    live.stop()

                    # Get user input with better handling
                    try:
                        import readline
                        # Show input prompt
                        self.console.print("[bold blue]You:[/bold blue] ", end="")
                        user_input = input("")

                        if not user_input:
                            live.start()
                            continue

                        # Add to chat history
                        self.chat_history.append({
                            'role': 'user',
                            'content': user_input
                        })

                        # Handle commands
                        if user_input.lower() in ['/quit', 'exit']:
                            self.chat_history.append({
                                'role': 'system',
                                'content': "👋 Goodbye!"
                            })
                            break

                        # Restart live display
                        live.start()

                        # Process other commands
                        result = self._process_command_panel_ui(user_input)
                        if result:
                            continue

                        # Process regular chat
                        self.queue_count += 1
                        self._update_input_panel(layout)
                        live.refresh()

                        # Get AI response
                        response = self.process_message(user_input)

                        self.queue_count = max(0, self.queue_count - 1)

                        # Add response to chat
                        self.chat_history.append({
                            'role': 'assistant',
                            'content': response['response']
                        })

                        # Keep chat history reasonable size
                        if len(self.chat_history) > 50:
                            self.chat_history = self.chat_history[-40:]

                    except KeyboardInterrupt:
                        self.chat_history.append({
                            'role': 'system',
                            'content': "👋 Interrupted - Goodbye!"
                        })
                        live.update(layout)
                        break
                    except Exception as e:
                        self.error_handler.handle_error(
                            e,
                            ErrorCategory.UI_INPUT,
                            ErrorSeverity.MEDIUM_ALERT,
                            context="Panel UI processing"
                        )

        finally:
            # Cleanup
            if hasattr(self, 'recovery_thread') and self.recovery_thread:
                self.recovery_thread.stop_recovery_thread()
            if hasattr(self, 'service_processes'):
                self.cleanup_services()

    def _update_status_bar(self, layout):
        """Update the status bar with current state"""
        status_parts = []

        # Service status
        if self.services_healthy:
            status_parts.append("[green]● Services OK[/green]")
        else:
            status_parts.append("[red]● Services Down[/red]")

        # Model info
        if hasattr(self.llm, 'model_name'):
            status_parts.append(f"[cyan]Model: {self.llm.model_name}[/cyan]")

        # Debug mode
        if self.debug_mode:
            status_parts.append("[yellow]🐛 Debug ON[/yellow]")

        # Token display
        if self.show_tokens:
            status_parts.append("[magenta]🔢 Tokens ON[/magenta]")

        # Error panel
        if self.show_error_panel:
            status_parts.append("[orange1]📋 Errors ON[/orange1]")

        # Ball mode
        if self.fuck_it_we_ball_mode:
            status_parts.append("[red]🎱 BALL MODE[/red]")

        status_text = " | ".join(status_parts)
        layout["status"].update(Panel(status_text, style="on grey23", box=box.SIMPLE))

    def _update_chat_panel(self, layout):
        """Update the chat display panel"""
        # Format chat history
        chat_content = []
        for msg in self.chat_history[-20:]:  # Show last 20 messages
            if msg['role'] == 'user':
                chat_content.append(f"[bold blue]You:[/bold blue] {msg['content']}")
            elif msg['role'] == 'assistant':
                chat_content.append(f"[bold green]AI:[/bold green] {msg['content']}")
            elif msg['role'] == 'system':
                chat_content.append(f"[bold yellow]System:[/bold yellow] {msg['content']}")

        chat_text = "\n\n".join(chat_content) if chat_content else "[dim]No messages yet...[/dim]"
        layout["chat"].update(Panel(chat_text, title="💬 Chat", border_style="blue"))

    def _update_input_panel(self, layout):
        """Update the input panel with queue status"""
        input_content = []

        # Show queue count if any
        if self.queue_count > 0:
            input_content.append(f"[yellow]⏳ Queue: {self.queue_count} messages processing...[/yellow]")

        # Show current input prompt
        input_content.append("[bold blue]You:[/bold blue] _")

        # Add help hint
        input_content.append("[dim]Type /help for commands | /quit to exit[/dim]")

        input_text = "\n".join(input_content)
        layout["input"].update(Panel(input_text, title="✍️ Input", border_style="green"))

    def _update_error_panel(self, layout):
        """Update the error panel if visible"""
        if not self.show_error_panel:
            layout["errors"].visible = False
            return

        layout["errors"].visible = True

        # Get alerts from error handler
        current_alerts = self.error_handler.peek_alerts_for_ui(max_alerts=8)

        if not current_alerts:
            error_content = "[dim]No recent errors[/dim]"
        else:
            error_content = "\n".join(current_alerts)

        # Add error summary in debug mode
        if self.debug_mode:
            error_summary = self.error_handler.get_error_summary()
            if error_summary['total_errors'] > 0:
                error_content += f"\n\n[dim]Total: {error_summary['total_errors']} | Suppressed: {error_summary['suppressed_count']}[/dim]"

        layout["errors"].update(Panel(error_content, title="🚨 Errors", border_style="yellow"))

    def _process_command_panel_ui(self, user_input):
        """Process commands in panel UI mode"""
        if user_input == '/help':
            self.chat_history.append({
                'role': 'system',
                'content': self._get_help_text()
            })
            return True

        if user_input == '/errors':
            self.toggle_error_panel()
            self.chat_history.append({
                'role': 'system',
                'content': f"Error panel: {'ON' if self.show_error_panel else 'OFF'}"
            })
            return True

        if user_input == '/debug':
            self.debug_mode = not self.debug_mode
            self.chat_history.append({
                'role': 'system',
                'content': f"Debug mode: {'ON' if self.debug_mode else 'OFF'}"
            })
            return True

        if user_input == '/tokens':
            self.show_tokens = not self.show_tokens
            self.chat_history.append({
                'role': 'system',
                'content': f"Token display: {'ON' if self.show_tokens else 'OFF'}"
            })
            return True

        if user_input == '/ball':
            self.toggle_fuck_it_we_ball_mode()
            return True

        # Add other commands as needed
        return False

    def _get_help_text(self):
        """Get help text for panel UI"""
        return """**Available Commands:**

• `/help` - Show this help
• `/errors` - Toggle error panel
• `/debug` - Toggle debug mode
• `/tokens` - Toggle token display
• `/ball` - Toggle FUCK IT WE BALL mode
• `/memory` - Show memory status
• `/services` - Check service health
• `/quit` - Exit chat

**Tips:**
• Error panel shows system alerts
• Status bar shows current state
• Queue counter shows pending messages"""

    def run_legacy_ui(self):
        """Legacy UI for fallback compatibility"""
        # Welcome screen
        welcome = Panel.fit(
            """🧠 **Enhanced Memory Chat**
            
💬 Real LLM responses
🔍 Skinflap query detection  
💾 Memory system integration
✅ Curator validation

Commands: `/help` `/memory` `/history` `/search` `/stats` `/debug` `/new` `/list` `/quit`
💡 Pro tips: `/memory` = recent 15 | `/history` = all conversations | `/new` = fresh topic | `/list` = browse conversations""",
            title="Welcome",
            border_style="green"
        )
        
        self.console.print(welcome)
        
        try:
            # Main chat loop
            while True:
                try:
                    # Show error panel if enabled (semi-persistent display)
                    self.display_error_panel_if_enabled()

                    # Get user input with full readline support
                    try:
                        # Use raw input with readline for proper terminal behavior
                        import readline
                        import sys

                        # Ensure Rich output is completely flushed before readline takes over
                        self.console.file.flush()
                        sys.stdout.flush()
                        sys.stderr.flush()

                        self.console.print("\n[bold blue]You[/bold blue]", end="")
                        user_input = input(": ")
                    except (EOFError, KeyboardInterrupt):
                        self.console.print("\n👋 [bold yellow]Goodbye![/bold yellow]")
                        break
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.lower() in ['/quit', 'exit']:
                        self.console.print("👋 [bold yellow]Goodbye![/bold yellow]")
                        break
                    
                    if user_input == '/help':
                        self.show_help()
                        continue
                    
                    if user_input == '/status':
                        self.show_status()
                        continue
                    
                    if user_input == '/memory':
                        self.memory_handler.show_memory()
                        continue
                    
                    if user_input == '/history':
                        self.memory_handler.show_full_history()
                        continue
                    
                    if user_input.startswith('/search'):
                        search_term = user_input[7:].strip()  # Remove '/search '
                        if search_term:
                            self.memory_handler.search_conversations(search_term)
                        else:
                            self.warning_message("Usage: /search <term> - Search your conversation history", ErrorCategory.UI_INPUT)
                        continue
                    
                    if user_input == '/context':
                        self.show_context_preview()
                        continue
                    
                    if user_input == '/debug':
                        self.toggle_debug_mode()
                        continue
                    
                    if user_input == '/stats':
                        self.show_memory_stats()
                        continue
                    
                    if user_input == '/tokens':
                        self.toggle_token_display()
                        continue
                    
                    if user_input == '/confidence':
                        self.toggle_confidence_display()
                        continue
                    
                    if user_input == '/new':
                        self.start_new_conversation()
                        continue
                    
                    if user_input == '/list':
                        self.list_conversations()
                        continue
                    
                    if user_input.startswith('/switch'):
                        parts = user_input.split()
                        if len(parts) > 1:
                            self.switch_conversation(parts[1])
                        else:
                            self.warning_message("Usage: /switch <conversation_id>", ErrorCategory.UI_INPUT)
                        continue
                    
                    if user_input == '/services':
                        self.check_services()
                        continue
                    
                    if user_input == '/start-services':
                        self.auto_start_services()
                        continue
                    
                    if user_input == '/stop-services':
                        # Debug: Direct console output to bypass routing
                        self.console.print("[red]DEBUG: /stop-services command triggered[/red]")

                        self.cleanup_services()
                        self.success_message("Services stopped", ErrorCategory.SERVICE_MANAGEMENT)
                        continue
                    
                    # Handle recovery system commands
                    if user_input.startswith('/recovery'):
                        if self.recovery_chat:
                            result = self.recovery_chat.process_command(user_input)
                            self._display_recovery_result(result)
                        else:
                            self.warning_message("Recovery system not available", ErrorCategory.RECOVERY_SYSTEM)
                        continue
                    
                    # Handle FUCK IT WE BALL mode toggle
                    if user_input == '/ball':
                        self.toggle_fuck_it_we_ball_mode()
                        continue
                    
                    # Handle error panel toggle (what you originally wanted!)
                    if user_input == '/errors':
                        self.toggle_error_panel()
                        continue
                    
                    # Check memory pressure before processing
                    self.check_memory_pressure()
                
                    # Process message
                    result = self.process_message(user_input)
                    
                    # Display response (now always normal since we removed blocking)
                    response_panel = Panel(
                        result['response'],
                        title="🤖 Assistant",
                        border_style="green"
                    )
                    self.console.print(response_panel)
                    
                    # Show validation info if available
                    if result.get('validation'):
                        confidence = result['validation'].get('confidence_score', 0)
                        if confidence < 0.7:
                            self.console.print(f"⚠️ [dim]Confidence: {confidence:.2f}[/dim]")

                    # Error panel already shown at top of loop, no need to duplicate

                except KeyboardInterrupt:
                    self.console.print("\n👋 [bold yellow]Goodbye![/bold yellow]")
                    break
                except Exception as e:
                    self.error_handler.handle_error(
                        e,
                        ErrorCategory.UI_INPUT,
                        ErrorSeverity.MEDIUM_ALERT,
                        context="Processing user input",
                        operation="main_loop"
                    )
        finally:
            # Clean up auto-started services and recovery thread
            if hasattr(self, 'recovery_thread') and self.recovery_thread:
                self.recovery_thread.stop_recovery_thread()
            if hasattr(self, 'service_processes'):
                self.cleanup_services()
    
    def toggle_fuck_it_we_ball_mode(self):
        """Toggle FUCK IT WE BALL debug mode"""
        self.fuck_it_we_ball_mode = not self.fuck_it_we_ball_mode
        
        status = "ON 🎱" if self.fuck_it_we_ball_mode else "OFF 🔇"
        color = "red" if self.fuck_it_we_ball_mode else "green"
        
        self.console.print(Panel(
            f"FUCK IT WE BALL mode is now [bold {color}]{status}[/bold {color}]\n\n"
            f"When ON, you'll see:\n"
            f"• Full error stack traces and debug details\n"
            f"• Complete failure information from backup system\n"
            f"• Recovery thread internal state\n"
            f"• Episodic coordinator detailed responses\n"
            f"• Emergency backup file operations\n\n"
            f"[dim]This is maximum transparency mode for critical debugging[/dim]",
            title="🎱 FUCK IT WE BALL Mode",
            border_style=color
        ))
    
    def _display_recovery_result(self, result: dict):
        """Display recovery command results with appropriate formatting"""
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
        if self.fuck_it_we_ball_mode:
            self.console.print(f"[dim]FIWB: Raw result: {result}[/dim]")
    
    def add_alert_message(self, message: str):
        """Add message to alert queue - now routes through ErrorHandler"""
        # Parse the message to determine severity based on color/content
        if "[red]" in message or "🚨" in message or "💥" in message:
            severity = ErrorSeverity.HIGH_DEGRADE
        elif "[yellow]" in message or "⚠️" in message or "📦" in message:
            severity = ErrorSeverity.MEDIUM_ALERT
        elif "[green]" in message or "✅" in message:
            severity = ErrorSeverity.LOW_DEBUG
        else:
            severity = ErrorSeverity.MEDIUM_ALERT
            
        # Determine category from message content
        if "episodic" in message.lower() or "archive" in message.lower():
            category = ErrorCategory.EPISODIC_MEMORY
        elif "backup" in message.lower() or "queue" in message.lower():
            category = ErrorCategory.BACKUP_SYSTEM
        elif "recovery" in message.lower():
            category = ErrorCategory.RECOVERY_SYSTEM
        elif "coordinator" in message.lower():
            category = ErrorCategory.EPISODIC_MEMORY
        else:
            category = ErrorCategory.GENERAL
            
        # Route through error handler (will handle UI display)
        self.error_handler._route_error(message, category, severity)
        
        # Show error panel if enabled and this is a serious error
        if severity in [ErrorSeverity.HIGH_DEGRADE, ErrorSeverity.MEDIUM_ALERT]:
            # Auto-enable error panel for serious errors if not set
            if not hasattr(self, 'show_error_panel'):
                self.show_error_panel = True
            self.display_error_panel_if_enabled()
    
    # Helper methods for organized message routing
    def info_message(self, message: str, category: ErrorCategory = ErrorCategory.GENERAL):
        """For non-error information (service status, progress)"""
        self.error_handler._route_error(message, category, ErrorSeverity.LOW_DEBUG)
    
    def success_message(self, message: str, category: ErrorCategory = ErrorCategory.GENERAL):
        """For positive confirmations (service started successfully)"""  
        self.error_handler._route_error(message, category, ErrorSeverity.LOW_DEBUG)
    
    def warning_message(self, message: str, category: ErrorCategory = ErrorCategory.GENERAL):
        """For things user should know but aren't errors (service may be down)"""
        self.error_handler._route_error(message, category, ErrorSeverity.MEDIUM_ALERT)
    
    def debug_message(self, message: str, category: ErrorCategory = ErrorCategory.GENERAL):
        """For debug-only information"""
        self.error_handler._route_error(message, category, ErrorSeverity.TRACE_FIWB)
    
    def display_error_panel_if_enabled(self):
        """Show simple error panel at bottom if enabled - always show when ON"""
        if not getattr(self, 'show_error_panel', False):
            return

        # Get alerts from error handler (reuse the good logic!)
        current_alerts = self.error_handler.get_alerts_for_ui(max_alerts=5)

        # Always show panel when enabled, even if empty
        if not current_alerts:
            alerts_content = "[dim]No recent errors - panel ready for new alerts[/dim]"
        else:
            alerts_content = "\n".join(current_alerts)
            
        # Add error summary in debug mode
        if self.debug_mode:
            error_summary = self.error_handler.get_error_summary()
            if error_summary['total_errors'] > 0:
                alerts_content += f"\n\n[dim]Errors: {error_summary['total_errors']} | Suppressed: {error_summary['suppressed_count']}[/dim]"
                
        # Add recovery status if available
        if self.recovery_chat:
            try:
                dashboard_status = self.recovery_chat.get_status_for_dashboard()
                alerts_content = f"{dashboard_status}\n\n{alerts_content}"
            except:
                pass
                
        # Show simple panel at bottom
        error_panel = Panel(alerts_content, border_style="yellow", title="🚨 Recent Errors")
        self.console.print(error_panel)
    
    def toggle_error_panel(self):
        """Toggle error panel on/off - what you originally wanted!"""
        self.show_error_panel = getattr(self, 'show_error_panel', False)
        self.show_error_panel = not self.show_error_panel

        status = "ON" if self.show_error_panel else "OFF"
        self.console.print(f"[cyan]Error panel: {status}[/cyan]")

        # Don't show panel here - the main loop handles display
    

def main():
    """Run the rich chat interface with optional arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Rich Memory Chat Interface')
    parser.add_argument('--debug', '-d', action='store_true', 
                       help='Enable debug mode (show prompts, context, etc.)')
    parser.add_argument('--auto-start', '-a', action='store_true',
                       help='Automatically start memory services if not running')
    parser.add_argument('--normal', '-n', action='store_true',
                       help='Normal mode (no debug, same as not using --debug)')
    
    args = parser.parse_args()
    
    if not RICH_AVAILABLE:
        print("Rich library not available. Install with:")
        print("  pip install rich")
        print("\nFalling back to basic chat...")
        # Could import and run enhanced_chat.py here
        return
    
    # If --normal is specified, force debug to False
    debug_mode = False if args.normal else args.debug
    
    chat = RichMemoryChat(
        debug_mode=debug_mode,
        auto_start_services=args.auto_start
    )
    if chat:
        chat.run()

if __name__ == "__main__":
    main()