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
from uuid_extensions import uuid7
from datetime import datetime
from typing import Optional, Dict, List
import sys
import os
import signal
import threading
from contextvars import ContextVar

# Fallback request ID for standalone mode (when not running through api_server_bridge)
_standalone_request_id: ContextVar[str] = ContextVar('standalone_request_id', default=None)

def _get_or_create_standalone_id() -> str:
    """Get or create a request ID for standalone rich_chat usage."""
    current = _standalone_request_id.get()
    if current is None:
        current = str(uuid7())
        _standalone_request_id.set(current)
    return current

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
from command_handler import CommandHandler
from conversation_orchestrator import ConversationOrchestrator, get_orchestrator
from conversation_manager import ConversationManager
from datashapes import SidebarStatus
from chat_logger import ChatLogger
from response_enhancer import ResponseEnhancer

class RichMemoryChat:
    def __init__(self, debug_mode=False, auto_start_services=False, error_handler=None):
        """Initialize chat with optional debug mode and auto-start

        Args:
            debug_mode: Show debug info (prompts, context, etc.)
            auto_start_services: Automatically start memory services if not running
            error_handler: Optional shared ErrorHandler instance (creates new if None)
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
        # Use provided error_handler or create new one
        if error_handler is not None:
            self.error_handler = error_handler
        else:
            self.error_handler = ErrorHandler(
                console=self.console,
                debug_mode=debug_mode,
                fuck_it_we_ball_mode=self.fuck_it_we_ball_mode
            )

        # Initialize ChatLogger for raw exchange logging (lab notes layer)
        self.chat_logger = ChatLogger(
            error_handler=self.error_handler,
            debug_mode=debug_mode
        )

        # Initialize ResponseEnhancer for confidence analysis (OMNI-MODEL design)
        self.response_enhancer = ResponseEnhancer(
            error_handler=self.error_handler,
            show_confidence=self.show_confidence
        )

        # Initialize UIHandler for display operations
        from ui_handler import UIHandler
        self.ui_handler = UIHandler(console=self.console, error_handler=self.error_handler)

        # Initialize CommandHandler for command routing
        self.command_handler = CommandHandler(chat_instance=self, error_handler=self.error_handler)

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
        
        # Initialize ConversationManager (handles persistence + orchestrator + OZOLITH)
        self.orchestrator = get_orchestrator(error_handler=self.error_handler)
        self.conversation_manager = ConversationManager(
            service_manager=self.service_manager,
            error_handler=self.error_handler,
            orchestrator=self.orchestrator
        )

        # Start initial conversation (creates root context, logs to OZOLITH)
        self.conversation_manager.start_new_conversation(task_description="Main conversation")

        # Restore previous conversation history
        self.conversation_manager.restore_conversation_history()

        # Expose for backwards compatibility (other modules may reference these)
        # TODO: Migrate all references to use conversation_manager directly
        self.conversation_id = self.conversation_manager.conversation_id
        self.conversation_history = self.conversation_manager.conversation_history

        # [DEBUG-SYNC] Verify reference setup after init
        print(f"[DEBUG-SYNC] rich_chat.__init__ reference check:")
        print(f"[DEBUG-SYNC]   chat.conversation_history id: {id(self.conversation_history)}")
        print(f"[DEBUG-SYNC]   cm.conversation_history id: {id(self.conversation_manager.conversation_history)}")
        print(f"[DEBUG-SYNC]   Same object: {self.conversation_history is self.conversation_manager.conversation_history}")
        print(f"[DEBUG-SYNC]   Current length: {len(self.conversation_history)}")

        # Initialize LLM, Skinflap, and Memory Distillation
        with self.console.status("[bold blue]Initializing systems..."):
            self.llm = SmartLLMSelector.find_available_llm(debug_mode=self.debug_mode, error_handler=self.error_handler)
            self.skinflap = CollaborativeQueryReformer()
            self.distillation_engine = MemoryDistillationEngine(error_handler=self.error_handler)
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

    def _get_trace_headers(self, source_service: str = "rich_chat") -> dict:
        """
        Build headers for inter-service calls with request ID propagation.

        Tries to get request ID from api_server_bridge context first.
        Falls back to standalone ID if running outside API context.

        Args:
            source_service: Name of this service (for X-Source-Service header)

        Returns:
            dict: Headers to include in requests
        """
        # Try to get ID from shared request context module
        try:
            from request_context import get_request_id

            request_id = get_request_id()
            if request_id and request_id != "unknown":
                return {
                    "X-Request-ID": request_id,
                    "X-Source-Service": source_service
                }
        except ImportError:
            pass  # Shared module not available, use fallback
        except Exception:
            pass  # Unexpected error, use fallback

        # Fallback: generate/reuse standalone ID (for standalone rich_chat usage)
        fallback_id = _get_or_create_standalone_id()
        return {
            "X-Request-ID": fallback_id,
            "X-Source-Service": source_service
        }

    def restore_conversation_history(self):
        """Restore recent conversation history from working memory and episodic memory"""
        # Delegate to ConversationManager (handles working + episodic memory, OZOLITH logging)
        total_restored = self.conversation_manager.restore_conversation_history()

        # Update local reference for backwards compatibility
        self.conversation_history = self.conversation_manager.conversation_history

        if total_restored > 0:
            self.debug_message(f"Restored {total_restored} exchanges from memory services", ErrorCategory.HISTORY_RESTORATION)
    
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

                # Step 4: Validate
                status.update("[bold magenta]✅ Validating response...")
                validation = self.validate_with_curator(user_message, assistant_response)

            # Add confidence markers if enabled (using ResponseEnhancer)
            enhanced_response = self.response_enhancer.enhance_response(
                response=assistant_response,
                user_message=user_message,
                curator_validation=None  # Full CuratorValidation will come when curator becomes an agent
            )

            # Format retrieved memories for persistence (readable, not raw dicts)
            formatted_memories = [self._extract_memory_content(m) for m in relevant_memories[:3]] if relevant_memories else []

            # Step 5: Store in memory (SINGLE storage path - includes validation and retrieved_memories)
            exchange_id = self.store_exchange(
                user_message=user_message,
                assistant_response=enhanced_response,
                metadata={
                    'validation': validation,
                    'source': 'current',
                    'retrieved_memories': formatted_memories
                }
            )

            # NOTE: conversation_history append is handled by conversation_manager.store_exchange()
            # DO NOT append here - that causes duplicates since they share the same list reference

            # Archive to episodic memory (async, non-blocking)
            self.memory_handler.archive_to_episodic_memory(user_message, enhanced_response, exchange_id)

            # Log raw exchange to JSONL files (lab notes layer - always runs)
            self.chat_logger.log_exchange(
                user_message=user_message,
                assistant_response=assistant_response,
                conversation_id=self.conversation_id,
                exchange_id=exchange_id,
                request_id=self._get_trace_headers().get("X-Request-ID")
            )

            # Check for degraded state (storage failure)
            storage_warning = None
            if exchange_id is None:
                storage_warning = "⚠️ This exchange was NOT saved to memory (working_memory unavailable)"
                # Also log to error panel for visibility
                self.error_handler.handle_error(
                    error=Exception("Working memory storage failed - exchange not saved"),
                    category=ErrorCategory.WORKING_MEMORY,
                    severity=ErrorSeverity.HIGH_DEGRADE,
                    context=f"User message: {user_message[:50]}...",
                    operation="store_exchange_degraded",
                    attempt_recovery=False  # Don't retry, just log it
                )

            result_dict = {
                'response': enhanced_response,
                'type': 'normal',
                'validation': validation,
                'retrieved_context': [self._extract_memory_content(m) for m in relevant_memories[:3]],  # Debug: First 3 memories, formatted
                'storage_warning': storage_warning  # None if stored successfully, warning message if failed
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
    
    def store_exchange(self, user_message: str, assistant_response: str, metadata: dict = None):
        """Store exchange via ConversationManager (orchestrator + OZOLITH + working memory)"""
        # Delegate to ConversationManager - handles orchestrator, OZOLITH, and working memory
        exchange_id = self.conversation_manager.store_exchange(
            user_message=user_message,
            assistant_response=assistant_response,
            metadata=metadata
        )

        # Update local reference for backwards compatibility
        self.conversation_history = self.conversation_manager.conversation_history

        return exchange_id

    # log_raw_exchange() removed - now handled by ChatLogger (chat_logger.py)

    def validate_with_curator(self, user_message: str, assistant_response: str):
        """Validate with curator

        TODO: When curator becomes an AGENT (not a service):
        - This should NOT fail silently
        - Curator validation is critical for LLM quality feedback
        - Add error_handler with MEDIUM_ALERT severity
        - This is a gap {YOU} (LLMs) need - validation feedback improves responses
        - First agent to add per Phase 3 roadmap
        """
        try:
            response = requests.post(
                f"{self.service_manager.services['curator']}/validate",
                json={
                    "exchange_data": {
                        "user_message": user_message,
                        "assistant_response": assistant_response
                    }
                },
                headers=self._get_trace_headers(),
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get('validation', {}).get('result', {})
        except:
            # TEMPORARY: Fails silently until curator agent is connected
            # When curator is an agent, this MUST alert via error_handler
            pass
        return None

    # Memory archival methods removed - now handled by MemoryHandler

    def generate_response(self, user_message: str, skinflap_detection=None) -> str:
        """Generate response using LLM or fallback

        TODO: Multi-model error handling (when multiple LLMs running):
        - Different severity based on model purpose:
          * Security agent down = CRITICAL alert
          * Specialized models (math, code) = MEDIUM alert
          * General models = LOW_DEBUG (already shown in dashboard)
        - Consider model failover chain (try backup model before fallback)
        """
        if self.llm:
            try:
                return self.llm.generate_response(user_message, self.conversation_history, skinflap_detection=skinflap_detection)
            except Exception as e:
                self.error_handler.handle_error(
                    e,
                    ErrorCategory.LLM_COMMUNICATION,
                    ErrorSeverity.MEDIUM_ALERT,
                    context=f"Generating response for: {user_message[:50]}...",
                    operation="generate_response"
                )
                # Fall through to generic response below

        return f"I understand you're asking: '{user_message}'. Let me help with that."

    def _extract_memory_content(self, memory: dict) -> str:
        """Extract readable content from an episodic memory result.

        Episodic memories have structure:
        {
            '_semantic_score': 0.5,
            'conversation_id': '...',
            'full_conversation': [{
                'user_input': '...',
                'assistant_response': '...'
            }]
        }
        """
        score = memory.get('_semantic_score', 0)
        conv_id = memory.get('conversation_id', 'unknown')[:8]

        # Extract actual conversation content
        full_conv = memory.get('full_conversation', [])
        if full_conv and isinstance(full_conv, list) and len(full_conv) > 0:
            exchange = full_conv[0]
            user_q = exchange.get('user_input', '')[:80]
            asst_a = exchange.get('assistant_response', '')[:120]
            return f"[{score:.2f}|{conv_id}] Q: {user_q}... A: {asst_a}..."

        # Fallback for different structures
        if 'content' in memory:
            return f"[{score:.2f}] {memory['content'][:200]}"
        if 'text' in memory:
            return f"[{score:.2f}] {memory['text'][:200]}"

        return f"[{score:.2f}|{conv_id}] (memory structure unrecognized)"

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
        """Show fancy status panel - delegated to UIHandler"""
        recovery_status = self.recovery_chat.get_status_for_dashboard() if self.recovery_chat else None

        last_confidence = None
        if self.conversation_history:
            last = self.conversation_history[-1]
            validation = last.get('validation', {})
            last_confidence = validation.get('confidence_score')

        self.ui_handler.show_status(
            conversation_id=self.conversation_id,
            message_count=len(self.conversation_history),
            services_healthy=self.services_healthy,
            llm_available=bool(self.llm),
            recovery_status=recovery_status,
            last_confidence=last_confidence
        )
    
    # Memory display methods removed - now handled by MemoryHandler
    
    def show_help(self):
        """Show comprehensive help with command explanations - delegated to UIHandler"""
        stats = self.get_memory_stats()
        self.ui_handler.show_help(stats, self.debug_mode)
    
    
    def show_context_preview(self):
        """Show what context would be sent to LLM - delegated to UIHandler"""
        self.ui_handler.show_context_preview(
            self.conversation_history,
            self.show_tokens,
            self.estimate_tokens
        )
    
    def toggle_debug_mode(self):
        """Toggle debug mode on/off"""
        self.debug_mode = not self.debug_mode
        if self.llm:  # Only update LLM debug mode if LLM exists
            self.llm.debug_mode = self.debug_mode
        self.ui_handler.toggle_debug_display(self.debug_mode)
    
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
        """Toggle token display on/off - delegated to UIHandler"""
        self.show_tokens = not self.show_tokens
        self.ui_handler.toggle_token_display(self.show_tokens)
    
    def toggle_confidence_display(self):
        """Toggle confidence/uncertainty markers on/off - delegated to UIHandler"""
        self.show_confidence = not self.show_confidence
        self.ui_handler.toggle_confidence_display(self.show_confidence)
        self.response_enhancer.set_show_confidence(self.show_confidence)  # Keep in sync
    
    # add_confidence_markers() removed - now handled by ResponseEnhancer (response_enhancer.py)

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
        return self.conversation_manager.get_recent_context_hint()
    
    def show_memory_stats(self):
        """Show detailed memory statistics and distillation info - delegated to UIHandler"""
        stats = self.get_memory_stats()
        self.ui_handler.show_memory_stats(
            stats,
            self.show_tokens,
            self.estimate_tokens,
            self.conversation_history,
            self.distillation_engine
        )

    def start_new_conversation(self):
        """Start a fresh conversation (keeps memory, resets context)"""
        old_id = self.conversation_id[:8]
        old_count = len(self.conversation_history)

        # Delegate to ConversationManager (handles orchestrator + OZOLITH)
        self.conversation_manager.start_new_conversation(task_description="New conversation")

        # Update local references for backwards compatibility
        self.conversation_id = self.conversation_manager.conversation_id
        self.conversation_history = self.conversation_manager.conversation_history

        # Reset failure counters
        self.episodic_archival_failures = 0

        # UI display
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
        # Delegate data fetching to ConversationManager
        conversations = self.conversation_manager.list_conversations(limit=50)

        if not conversations:
            self.console.print(Panel(
                "No previous conversations found in episodic memory.\n"
                "(Service may be unavailable - use [cyan]/start-services[/cyan] to start)",
                title="📝 Conversation History",
                border_style="blue"
            ))
            return

        # Build conversation table (UI stays here)
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

    def switch_conversation(self, target_id: str):
        """Switch to a different conversation by ID"""
        old_id = self.conversation_id[:8]
        old_count = len(self.conversation_history)

        # Delegate to ConversationManager (handles ID expansion, loading, OZOLITH logging)
        success = self.conversation_manager.switch_conversation(target_id)

        if not success:
            self.console.print(Panel(
                f"[yellow]Could not switch to conversation '[cyan]{target_id}[/cyan]'.\n\n"
                f"Possible reasons:\n"
                f"• Conversation not found\n"
                f"• Multiple matches (be more specific)\n"
                f"• Episodic memory service unavailable[/yellow]",
                title="Switch Failed",
                border_style="yellow"
            ))
            return

        # Update local references for backwards compatibility
        self.conversation_id = self.conversation_manager.conversation_id
        self.conversation_history = self.conversation_manager.conversation_history

        # UI display
        self.console.print(Panel(
            f"🔄 **Conversation Switched**\n\n"
            f"• From: `{old_id}...` ({old_count} exchanges)\n"
            f"• To: `{self.conversation_id[:8]}...` ({len(self.conversation_history)} exchanges)\n"
            f"• Loaded from episodic memory\n"
            f"• Ready to continue conversation",
            title="Conversation Switched",
            border_style="cyan"
        ))

    # =========================================================================
    # SIDEBAR OPERATIONS
    # =========================================================================

    def spawn_sidebar(self, reason: str, inherit_last_n: int = 10):
        """
        Spawn a sidebar to investigate something.

        Usage: /sidebar <reason>
        Usage: /sidebar 20 <reason>  (inherit 20 exchanges instead of default 10)
        Example: /sidebar Investigate the auth bug
        Example: /sidebar 30 Need more context for complex auth flow

        Args:
            reason: Why we're branching (can be prefixed with number for inherit count)
            inherit_last_n: How many parent exchanges to inherit (default 10)
        """
        try:
            # Check if reason starts with a number (custom inherit count)
            parts = reason.split(maxsplit=1)
            if parts and parts[0].isdigit():
                inherit_last_n = int(parts[0])
                reason = parts[1] if len(parts) > 1 else "Investigation"

            current_id = self.orchestrator.get_active_context_id()
            if current_id is None:
                self.warning_message("No active context to branch from", ErrorCategory.UI_INPUT)
                return

            # Check how many exchanges parent actually has
            parent = self.orchestrator.get_context(current_id)
            available = len(parent.local_memory)
            actual_inherit = min(inherit_last_n, available)

            sidebar_id = self.orchestrator.spawn_sidebar(
                parent_id=current_id,
                reason=reason,
                inherit_last_n=inherit_last_n,
                created_by="human"
            )

            # Get the new context for display
            sidebar = self.orchestrator.get_context(sidebar_id)

            # Build inherited info with helpful hints
            inherited_count = len(sidebar.inherited_memory)
            inherited_info = f"• Inherited: {inherited_count} exchanges"
            if inherited_count < inherit_last_n:
                inherited_info += f" (requested {inherit_last_n}, parent only had {available})"
            elif inherit_last_n == 10:
                inherited_info += f"\n  [dim]Tip: /sidebar 30 <reason> to inherit more context[/dim]"

            self.console.print(Panel(
                f"🔀 **Sidebar Created: {sidebar_id}**\n\n"
                f"• Reason: {reason}\n"
                f"• Parent: {current_id} (now PAUSED)\n"
                f"{inherited_info}\n"
                f"• Status: {sidebar.status.value}\n\n"
                f"[dim]Use /merge to return findings to parent, or /back to return without merging[/dim]",
                title="Sidebar Spawned",
                border_style="cyan"
            ))

            # Automatically process the reason as the first message in the sidebar
            # This way the user doesn't have to retype their question
            self.console.print(f"\n[cyan]Processing your question in sidebar...[/cyan]\n")
            result = self.process_message(reason)

            # Display the response
            if result and result.get('response'):
                self.console.print(Panel(
                    result['response'],
                    title=f"🤖 Assistant [{sidebar_id}]",
                    border_style="green"
                ))

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.UI_INPUT,
                ErrorSeverity.MEDIUM_ALERT,
                context=f"Spawning sidebar: {reason}",
                operation="spawn_sidebar"
            )

    def merge_current_sidebar(self, summary: Optional[str] = None):
        """
        Merge current sidebar back to parent.

        Usage: /merge [optional summary]
        """
        try:
            current_id = self.orchestrator.get_active_context_id()
            if current_id is None:
                self.warning_message("No active context", ErrorCategory.UI_INPUT)
                return

            current = self.orchestrator.get_context(current_id)
            if current.parent_context_id is None:
                self.warning_message(
                    f"{current_id} is a root context - nothing to merge into.\n"
                    "Use /sidebar to create a sidebar first.",
                    ErrorCategory.UI_INPUT
                )
                return

            result = self.orchestrator.merge_sidebar(current_id, summary=summary)

            if result["success"]:
                self.console.print(Panel(
                    f"✅ **Sidebar Merged**\n\n"
                    f"• Merged: {result['sidebar_id']} → {result['parent_id']}\n"
                    f"• Exchanges: {result['exchanges_merged']}\n"
                    f"• Summary: {result['summary']}\n\n"
                    f"[dim]Now focused on {result['parent_id']}[/dim]",
                    title="Merge Complete",
                    border_style="green"
                ))
            else:
                self.warning_message(f"Merge failed: {result.get('error')}", ErrorCategory.UI_INPUT)

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.UI_INPUT,
                ErrorSeverity.MEDIUM_ALERT,
                context="Merging sidebar",
                operation="merge_current_sidebar"
            )

    def back_to_parent(self):
        """
        Go back to parent context without merging.

        Usage: /back
        """
        try:
            current_id = self.orchestrator.get_active_context_id()
            if current_id is None:
                self.warning_message("No active context", ErrorCategory.UI_INPUT)
                return

            current = self.orchestrator.get_context(current_id)
            if current.parent_context_id is None:
                self.warning_message(
                    f"{current_id} is a root context - no parent to go back to.",
                    ErrorCategory.UI_INPUT
                )
                return

            parent_id = current.parent_context_id

            # Pause current sidebar (not merging, just stepping away)
            self.orchestrator.pause_context(current_id, reason="User went back to parent")

            # Resume parent
            self.orchestrator.resume_context(parent_id)

            self.console.print(Panel(
                f"⬅️ **Back to Parent**\n\n"
                f"• Left: {current_id} (PAUSED)\n"
                f"• Now in: {parent_id}\n\n"
                f"[dim]Sidebar {current_id} is paused. Use /focus {current_id} to return.[/dim]",
                title="Context Switched",
                border_style="yellow"
            ))

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.UI_INPUT,
                ErrorSeverity.MEDIUM_ALERT,
                context="Going back to parent",
                operation="back_to_parent"
            )

    def focus_context(self, context_id: str):
        """
        Focus on a specific context.

        Usage: /focus <context_id>
        Example: /focus SB-2
        """
        try:
            if not self.orchestrator.get_context(context_id):
                self.warning_message(
                    f"Context '{context_id}' not found.\nUse /tree to see available contexts.",
                    ErrorCategory.UI_INPUT
                )
                return

            old_id = self.orchestrator.get_active_context_id()
            self.orchestrator.switch_focus(context_id)

            context = self.orchestrator.get_context(context_id)
            self.console.print(Panel(
                f"🎯 **Focus Changed**\n\n"
                f"• From: {old_id}\n"
                f"• To: {context_id}\n"
                f"• Status: {context.status.value}\n"
                f"• Task: {context.task_description or 'No description'}\n"
                f"• Local exchanges: {len(context.local_memory)}",
                title="Focus",
                border_style="blue"
            ))

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.UI_INPUT,
                ErrorSeverity.MEDIUM_ALERT,
                context=f"Focusing on {context_id}",
                operation="focus_context"
            )

    def pause_current_context(self):
        """
        Pause the current context.

        Usage: /pause
        """
        try:
            current_id = self.orchestrator.get_active_context_id()
            if current_id is None:
                self.warning_message("No active context to pause", ErrorCategory.UI_INPUT)
                return

            self.orchestrator.pause_context(current_id, reason="User paused")

            self.console.print(Panel(
                f"⏸️ **Context Paused**\n\n"
                f"• Context: {current_id}\n"
                f"• Status: PAUSED\n\n"
                f"[dim]Use /focus {current_id} to resume[/dim]",
                title="Paused",
                border_style="yellow"
            ))

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.UI_INPUT,
                ErrorSeverity.MEDIUM_ALERT,
                context="Pausing context",
                operation="pause_current_context"
            )

    def show_context_tree(self):
        """
        Show the context tree.

        Usage: /tree
        """
        try:
            from rich.tree import Tree

            tree_data = self.orchestrator.get_tree()
            active_id = self.orchestrator.get_active_context_id()

            def build_rich_tree(node: dict, parent_tree: Tree):
                """Recursively build Rich tree from node data."""
                node_id = node.get("id", "unknown")
                desc = node.get("description") or ""

                # Mark active context
                if node_id == active_id:
                    label = f"[bold green]{node_id}[/bold green] ← active"
                else:
                    # Get status from orchestrator
                    ctx = self.orchestrator.get_context(node_id)
                    status = ctx.status.value if ctx else "unknown"
                    status_color = {
                        "active": "green",
                        "paused": "yellow",
                        "merged": "blue",
                        "archived": "dim",
                    }.get(status, "white")
                    label = f"[{status_color}]{node_id}[/{status_color}] ({status})"

                if desc:
                    label += f" - {desc[:40]}"

                branch = parent_tree.add(label)

                for child in node.get("children", []):
                    build_rich_tree(child, branch)

            # Build the tree
            root_tree = Tree("📊 Context Tree")

            roots = tree_data.get("roots", [])
            if not roots:
                self.console.print("[dim]No contexts yet[/dim]")
                return

            for root in roots:
                build_rich_tree(root, root_tree)

            self.console.print(root_tree)

            # Show stats
            stats = self.orchestrator.stats()
            self.console.print(f"\n[dim]Total: {stats['total_contexts']} contexts | Active: {active_id}[/dim]")

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.UI_INPUT,
                ErrorSeverity.LOW_DEBUG,
                context="Showing context tree",
                operation="show_context_tree"
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
                    except Exception as e:
                        # Log shutdown failures to learn patterns
                        # TODO: After observing for weeks/months, adjust severity per service:
                        # - Critical services (working_memory) = HIGH severity
                        # - Optional services = LOW severity
                        # - Algorithmic approach: different failures, different reactions
                        self.error_handler.handle_error(
                            e,
                            ErrorCategory.SERVICE_MANAGEMENT,
                            ErrorSeverity.MEDIUM_ALERT,
                            operation="cleanup_service",
                            context=f"Failed to terminate {service} (PID: {process.pid})"
                        )
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
        """
        DEPRECATED: Panel UI with Rich Live display.

        Why deprecated:
        - Rich's Live display conflicts with Python's input() - they fight for terminal control
        - This led to developing the React UI instead (api_server_bridge.py)
        - React UI is now the primary interface with full panel support

        For CLI enthusiasts:
        - This method is preserved as a starting point if you want to experiment
        - The core challenge: Rich Live needs to own the terminal, but input() also needs it
        - Possible approaches: curses, textual (Rich's TUI framework), or async input handling
        - Original attempt preserved in: deprecated/DEPRECATED_panel_ui_attempt.py

        Currently just redirects to run_legacy_ui() which uses simple Rich panels + standard input.
        """
        self.run_legacy_ui()

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
                    
                    # Handle commands via CommandHandler
                    if user_input.lower() in ['/quit', 'exit']:
                        self.console.print("👋 [bold yellow]Goodbye![/bold yellow]")
                        break

                    # Route all commands through CommandHandler
                    cmd_result = self.command_handler.handle_command(user_input)
                    if cmd_result.get('handled'):
                        if cmd_result.get('quit'):
                            break
                        if cmd_result.get('should_continue'):
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
        """Display recovery command results - delegated to UIHandler"""
        self.ui_handler.display_recovery_result(result, self.fuck_it_we_ball_mode)
    
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
        """Show simple error panel at bottom if enabled - delegated to UIHandler"""
        self.ui_handler.display_error_panel_if_enabled(
            getattr(self, 'show_error_panel', False),
            self.error_handler,
            self.debug_mode,
            self.recovery_chat
        )
    
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