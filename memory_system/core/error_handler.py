#!/usr/bin/env python3
"""
ErrorHandler - Centralized exception handling to fix silent failures
Phase 1 of rich_chat.py refactoring to stop alert flooding
Amalgamated from parallel development and session work
"""

import traceback
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from collections import defaultdict

class ErrorSeverity(Enum):
    """Error severity levels with clear action mappings"""
    CRITICAL_STOP = "critical_stop"       # Stop everything, human intervention needed
    HIGH_DEGRADE = "high_degrade"         # Feature broken, continue with degraded functionality  
    MEDIUM_ALERT = "medium_alert"         # User should know, show in alerts panel
    LOW_DEBUG = "low_debug"               # Background issue, show only in debug mode
    TRACE_FIWB = "trace_fiwb"             # Deep debugging, show only in FIWB mode

class ErrorCategory(Enum):
    """Complete error categories covering all services"""
    # Memory System (Core Brain Functions)
    EPISODIC_MEMORY = "episodic"              # Long-term memory storage
    WORKING_MEMORY = "working"                # Short-term active memory  
    MEMORY_DISTILLATION = "distillation"     # Memory processing/compression
    MEMORY_ARCHIVAL = "archival"             # Moving between memory types
    
    # Communication & Logging
    MCP_LOGGER = "mcp_logger"                # Message logging service
    CURATOR = "curator"                      # Content validation/curation
    
    # AI/LLM System
    LLM_CONNECTION = "llm"                   # LLM service connection
    LLM_GENERATION = "llm_generation"        # Response generation
    SKINFLAP_DETECTION = "skinflap"          # Query stupidity detection
    QUERY_REFORMING = "query_reform"         # Query improvement
    
    # Recovery & Backup Systems
    RECOVERY_SYSTEM = "recovery"             # Overall recovery process health
    RECOVERY_THREAD = "recovery_thread"      # Individual thread lifecycle management
    BACKUP_SYSTEM = "backup"                 # Regular backup operations
    EMERGENCY_BACKUP = "emergency_backup"    # Critical backup operations
    
    # Infrastructure & Services
    SERVICE_CONNECTION = "service"           # General service connectivity
    SERVICE_HEALTH = "service_health"        # Service health monitoring
    AUTO_START = "auto_start"               # Service auto-start system
    
    # User Interface
    UI_RENDERING = "ui"                     # UI display/rendering
    UI_INPUT = "ui_input"                   # User input processing
    UI_LAYOUT = "ui_layout"                 # Layout management
    
    # Message Processing
    MESSAGE_PROCESSING = "processing"        # Core message processing
    MESSAGE_VALIDATION = "validation"       # Message validation
    CONVERSATION_FLOW = "conversation"       # Conversation management
    
    # File & Data Operations
    FILE_OPERATIONS = "file_ops"            # File read/write operations
    DATA_SERIALIZATION = "serialization"    # JSON/data serialization
    HISTORY_RESTORATION = "history"         # Conversation history operations
    
    # Threading & Concurrency
    THREADING = "threading"                  # General thread management/creation
    SIGNAL_HANDLING = "signals"             # Signal handling (Ctrl+C, etc)
    
    # Catch-all
    GENERAL = "general"                     # Uncategorized errors
    UNKNOWN = "unknown"                     # When category can't be determined

class ErrorHandler:
    """Centralized error handling to replace scattered try/except blocks"""
    
    def __init__(self, console=None, debug_mode=False, fuck_it_we_ball_mode=False):
        self.console = console
        self.debug_mode = debug_mode
        self.fuck_it_we_ball_mode = fuck_it_we_ball_mode
        
        # Error tracking with better organization
        self.error_counts = defaultdict(int)  # category -> count
        self.recent_errors = []  # Recent errors for pattern analysis
        self.suppressed_errors = defaultdict(int)  # category -> count of suppressed
        self.last_error_time = {}  # error_key -> last occurrence time
        
        # Alert routing with priorities
        self.alert_queue = []
        self.critical_alerts = []
        
        # Auto-recovery tracking
        self.recovery_attempts = defaultdict(int)
        self.recovery_successes = defaultdict(int)

        # Acknowledgement tracking
        self.acknowledged_errors: set = set()

        # Recovery systems (late-bound after initialization)
        self._backup_system = None
        self._recovery_thread = None
        self._service_manager = None

        # Configure logging
        self.logger = logging.getLogger('rich_chat_errors')
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

        # Add file handler for persistent error logging
        if not self.logger.handlers:
            handler = logging.FileHandler('/home/grinnling/Development/CODE_IMPLEMENTATION/logs/errors.log')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)

    def get_error_by_id(self, error_id: str) -> Optional[Dict[str, Any]]:
        """
        Find an error record by its ID.

        Args:
            error_id: The UUID of the error to find

        Returns:
            The error record if found, None otherwise
        """
        for error in self.recent_errors:
            if error.get('error_id') == error_id:
                return error
        return None

    def acknowledge_error(self, error_id: str) -> Dict[str, Any]:
        """
        Acknowledge an error by ID with validation.

        Args:
            error_id: The UUID of the error to acknowledge

        Returns:
            Dict with status and error info
        """
        error_record = self.get_error_by_id(error_id)
        if error_record is None:
            return {
                'success': False,
                'error': f'Error ID not found: {error_id}',
                'error_id': error_id
            }

        self.acknowledged_errors.add(error_id)
        return {
            'success': True,
            'error_id': error_id,
            'error_category': error_record.get('category'),
            'error_message': error_record.get('message')
        }
    
    def handle_error(self, 
                    error: Exception, 
                    category: ErrorCategory, 
                    severity: ErrorSeverity,
                    context: str = "",
                    operation: str = "",
                    suppress_duplicate_minutes: int = 5,
                    attempt_recovery: bool = True) -> bool:
        """
        Central error handling method with recovery attempts
        
        Args:
            error: The exception that occurred
            category: What type of error this is
            severity: How severe this error is
            context: Additional context about what was happening
            operation: What operation was being performed
            suppress_duplicate_minutes: Suppress similar errors for this many minutes
            attempt_recovery: Whether to attempt auto-recovery
            
        Returns:
            bool: True if error was handled and should not propagate, False to re-raise
        """
        
        error_key = f"{category.value}_{type(error).__name__}"
        current_time = datetime.now()
        
        # Track error frequency
        self.error_counts[error_key] += 1
        
        # Check if we should suppress this error
        if self._should_suppress_error(error_key, current_time, suppress_duplicate_minutes):
            self.suppressed_errors[error_key] += 1
            return True  # Suppress error
        
        # Update last error time
        self.last_error_time[error_key] = current_time
        
        # Format error message
        error_message = self._format_error_message(error, category, severity, context, operation)
        
        # Attempt auto-recovery if enabled
        recovery_succeeded = False
        if attempt_recovery and severity in [ErrorSeverity.HIGH_DEGRADE, ErrorSeverity.MEDIUM_ALERT]:
            recovery_succeeded = self.attempt_auto_recovery(category, error)
        
        # Route error to appropriate destination
        self._route_error(error_message, category, severity, recovery_succeeded)
        
        # Store for pattern analysis with stable UUID for acknowledgement
        error_id = str(uuid.uuid4())
        self.recent_errors.append({
            'error_id': error_id,
            'timestamp': current_time,
            'category': category.value,
            'severity': severity.value,
            'error_type': type(error).__name__,
            'message': str(error),
            'context': context,
            'operation': operation,
            'recovery_attempted': attempt_recovery,
            'recovery_succeeded': recovery_succeeded
        })
        
        # Keep only recent errors (last 100)
        if len(self.recent_errors) > 100:
            self.recent_errors.pop(0)
        
        # Show full traceback in FIWB mode for critical/high errors
        if self.fuck_it_we_ball_mode and severity in [ErrorSeverity.CRITICAL_STOP, ErrorSeverity.HIGH_DEGRADE]:
            if self.console:
                self.console.print(f"[red dim]FIWB Traceback:\n{traceback.format_exc()}[/red dim]")
        
        # Log the error
        self.logger.error(f"{category.value}: {error_message}", exc_info=self.debug_mode)
        
        # Return whether to suppress exception propagation
        return severity != ErrorSeverity.CRITICAL_STOP  # Only re-raise critical errors
    
    def attempt_auto_recovery(self, category: ErrorCategory, error: Exception) -> bool:
        """
        Attempt automatic recovery based on error category
        
        Returns:
            bool: True if recovery succeeded
        """
        self.recovery_attempts[category.value] += 1
        recovery_succeeded = False
        
        # Category-specific recovery logic
        if category == ErrorCategory.EPISODIC_MEMORY:
            # Could trigger backup system or coordinator fallback
            recovery_succeeded = self._recover_episodic_memory()
        elif category == ErrorCategory.SERVICE_CONNECTION:
            # Could attempt service restart
            recovery_succeeded = self._recover_service_connection()
        elif category == ErrorCategory.LLM_CONNECTION:
            # Could fallback to local model
            recovery_succeeded = self._recover_llm_connection()
        
        if recovery_succeeded:
            self.recovery_successes[category.value] += 1
            
        return recovery_succeeded
    
    def register_recovery_systems(self, backup_system=None, recovery_thread=None, service_manager=None):
        """
        Register recovery systems for automatic error recovery.

        Called after ErrorHandler is initialized and other systems are ready.
        This allows late-binding since ErrorHandler is created first.

        Args:
            backup_system: EmergencyBackupSystem instance for disk-based recovery
            recovery_thread: RecoveryThread instance for automatic sync
            service_manager: ServiceManager instance for service health checks
        """
        if backup_system:
            self._backup_system = backup_system
            self.logger.info("Registered backup_system for episodic recovery")
        if recovery_thread:
            self._recovery_thread = recovery_thread
            self.logger.info("Registered recovery_thread for automatic sync")
        if service_manager:
            self._service_manager = service_manager
            self.logger.info("Registered service_manager for service recovery")

    def _recover_episodic_memory(self) -> bool:
        """
        Attempt to recover episodic memory service.

        Recovery strategy:
        1. Check if recovery thread is running, start if not
        2. Force immediate recovery cycle
        3. Check pending count before/after to verify progress
        """
        if not self._backup_system or not self._recovery_thread:
            self.logger.debug("Recovery systems not registered, cannot recover episodic memory")
            return False

        try:
            # Check pending count before recovery
            pending_before = self._backup_system.get_pending_count()

            if pending_before == 0:
                # Nothing to recover
                return True

            # Ensure recovery thread is running
            if not self._recovery_thread.is_running():
                self._recovery_thread.start_recovery_thread()
                self.logger.info("Started recovery thread during error recovery")

            # Force immediate recovery cycle
            result = self._recovery_thread.force_recovery_now()

            if result.get('error'):
                self.logger.warning(f"Recovery cycle failed: {result['error']}")
                return False

            # Check if we made progress
            processed = result.get('processed', 0)
            if processed > 0:
                self.logger.info(f"Episodic recovery: processed {processed} pending exchanges")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Exception during episodic recovery: {e}")
            return False

    def _recover_service_connection(self) -> bool:
        """
        Attempt to recover service connection.

        Uses ServiceManager's smart_recovery if available.
        """
        if not self._service_manager:
            self.logger.debug("ServiceManager not registered, cannot recover service")
            return False

        try:
            # Try to auto-start missing services
            success = self._service_manager.auto_start_services()
            if success:
                self.logger.info("Service auto-start succeeded during error recovery")
            return success

        except Exception as e:
            self.logger.error(f"Exception during service recovery: {e}")
            return False

    def _recover_llm_connection(self) -> bool:
        """
        Attempt to recover LLM connection.

        KNOWN LIMITATION: This is currently a stub that always returns False.
        LLM recovery requires integration with the LLM service layer which
        is not yet wired to the ErrorHandler.

        Future implementation options:
        - Switch to local/fallback model (e.g., ollama)
        - Retry with exponential backoff
        - Try alternative API endpoints
        - Queue messages for later retry

        To implement:
        1. Add _llm_service attribute
        2. Add register method for LLM service
        3. Implement fallback logic based on error type
        """
        # LLM recovery would need LLM service reference
        # For now, return False as we don't have fallback configured
        self.logger.debug("LLM recovery not implemented - stub returns False")
        return False
    
    def _should_suppress_error(self, error_key: str, current_time: datetime, suppress_minutes: int) -> bool:
        """Check if this error should be suppressed due to recent similar errors"""
        if error_key not in self.last_error_time:
            return False
            
        last_occurrence = self.last_error_time[error_key]
        time_since_last = (current_time - last_occurrence).total_seconds()
        
        # Suppress if we've seen this error within the window
        return time_since_last < (suppress_minutes * 60)
    
    def _format_error_message(self, error: Exception, category: ErrorCategory, 
                             severity: ErrorSeverity, context: str, operation: str) -> str:
        """Format error message consistently with all metadata"""
        
        # Base message
        base_msg = str(error)
        if len(base_msg) > 100:
            base_msg = base_msg[:100] + "..."
        
        # Add context if provided
        if context:
            base_msg = f"{context}: {base_msg}"
        
        # Add operation if provided
        if operation:
            base_msg = f"During {operation} - {base_msg}"
        
        # Add error count if this is a repeat
        error_key = f"{category.value}_{type(error).__name__}"
        count = self.error_counts.get(error_key, 1)
        if count > 1:
            base_msg += f" (#{count})"
        
        # Add suppression info if applicable
        suppressed_count = self.suppressed_errors.get(error_key, 0)
        if suppressed_count > 0:
            base_msg += f" [+{suppressed_count} suppressed]"
            self.suppressed_errors[error_key] = 0  # Reset after showing
        
        return base_msg
    
    def _route_error(self, message: str, category: ErrorCategory, severity: ErrorSeverity, 
                    recovery_succeeded: bool = False):
        """Route error to appropriate display location with recovery status"""
        
        # Choose color based on severity
        color_map = {
            ErrorSeverity.CRITICAL_STOP: "red bold",
            ErrorSeverity.HIGH_DEGRADE: "red",
            ErrorSeverity.MEDIUM_ALERT: "yellow",
            ErrorSeverity.LOW_DEBUG: "dim yellow",
            ErrorSeverity.TRACE_FIWB: "dim"
        }
        
        # Choose icon based on category
        icon_map = {
            ErrorCategory.EPISODIC_MEMORY: "🧠",
            ErrorCategory.WORKING_MEMORY: "🧠",
            ErrorCategory.MEMORY_DISTILLATION: "🔄",
            ErrorCategory.MEMORY_ARCHIVAL: "📦",
            ErrorCategory.MCP_LOGGER: "📝",
            ErrorCategory.CURATOR: "✅",
            ErrorCategory.LLM_CONNECTION: "🤖",
            ErrorCategory.LLM_GENERATION: "💬",
            ErrorCategory.SKINFLAP_DETECTION: "🎭",
            ErrorCategory.QUERY_REFORMING: "✨",
            ErrorCategory.RECOVERY_SYSTEM: "🔄",
            ErrorCategory.RECOVERY_THREAD: "🧵",
            ErrorCategory.BACKUP_SYSTEM: "💾",
            ErrorCategory.EMERGENCY_BACKUP: "🚨",
            ErrorCategory.SERVICE_CONNECTION: "🔌",
            ErrorCategory.SERVICE_HEALTH: "❤️",
            ErrorCategory.AUTO_START: "🚀",
            ErrorCategory.UI_RENDERING: "🖥️",
            ErrorCategory.UI_INPUT: "⌨️",
            ErrorCategory.UI_LAYOUT: "📐",
            ErrorCategory.MESSAGE_PROCESSING: "⚡",
            ErrorCategory.MESSAGE_VALIDATION: "✔️",
            ErrorCategory.CONVERSATION_FLOW: "💭",
            ErrorCategory.FILE_OPERATIONS: "📁",
            ErrorCategory.DATA_SERIALIZATION: "📊",
            ErrorCategory.HISTORY_RESTORATION: "📚",
            ErrorCategory.THREADING: "🧵",
            ErrorCategory.SIGNAL_HANDLING: "🚦",
            ErrorCategory.GENERAL: "⚠️",
            ErrorCategory.UNKNOWN: "❓"
        }
        
        color = color_map.get(severity, "dim")
        icon = icon_map.get(category, "⚠️")
        
        # Add recovery indicator if applicable
        recovery_indicator = " ✅ [recovered]" if recovery_succeeded else ""
        
        formatted_message = f"[{color}]{icon} {message}{recovery_indicator}[/{color}]"
        
        # Route based on severity
        if severity == ErrorSeverity.CRITICAL_STOP:
            self.critical_alerts.append(formatted_message)
            # Also print immediately for critical errors if console available
            if self.console:
                self.console.print(formatted_message)
        elif severity in [ErrorSeverity.HIGH_DEGRADE, ErrorSeverity.MEDIUM_ALERT]:
            self.alert_queue.append(formatted_message)
        elif severity == ErrorSeverity.LOW_DEBUG and self.debug_mode:
            self.alert_queue.append(formatted_message)
        elif severity == ErrorSeverity.TRACE_FIWB and self.fuck_it_we_ball_mode:
            self.alert_queue.append(formatted_message)
    
    def get_alerts_for_ui(self, max_alerts: int = 8, clear_after: bool = True) -> List[str]:
        """Get alerts for UI display"""
        # Combine critical and regular alerts
        all_alerts = self.critical_alerts + self.alert_queue

        # Return most recent alerts
        alerts = all_alerts[-max_alerts:] if len(all_alerts) > max_alerts else all_alerts

        # Clear the queues after retrieving (unless specified not to)
        if clear_after:
            self.critical_alerts = []
            self.alert_queue = []

        return alerts

    def peek_alerts_for_ui(self, max_alerts: int = 8) -> List[str]:
        """Peek at alerts without clearing them"""
        return self.get_alerts_for_ui(max_alerts, clear_after=False)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of error patterns for debugging"""
        total_errors = sum(self.error_counts.values())
        total_suppressed = sum(self.suppressed_errors.values())
        total_recoveries = sum(self.recovery_attempts.values())
        successful_recoveries = sum(self.recovery_successes.values())
        
        return {
            'total_errors': total_errors,
            'error_counts_by_type': dict(self.error_counts),
            'recent_error_count': len(self.recent_errors),
            'suppressed_count': total_suppressed,
            'suppression_rate': f"{(total_suppressed / max(total_errors, 1)) * 100:.1f}%",
            'categories_with_errors': list(set(e['category'] for e in self.recent_errors)),
            'most_common_errors': sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            'recovery_attempts': total_recoveries,
            'recovery_successes': successful_recoveries,
            'recovery_rate': f"{(successful_recoveries / max(total_recoveries, 1)) * 100:.1f}%",
            'recent_patterns': self._analyze_error_patterns()
        }
    
    def _analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze recent error patterns for insights"""
        if not self.recent_errors:
            return {'pattern': 'No errors yet'}
        
        # Time-based patterns
        recent_10min = [e for e in self.recent_errors 
                       if (datetime.now() - e['timestamp']).total_seconds() < 600]
        
        if len(recent_10min) > 10:
            return {'pattern': 'Error spike', 'count_10min': len(recent_10min)}
        
        # Category patterns
        category_counts = defaultdict(int)
        for error in self.recent_errors[-20:]:  # Last 20 errors
            category_counts[error['category']] += 1
        
        if category_counts:
            worst_category = max(category_counts.items(), key=lambda x: x[1])
            if worst_category[1] > 5:
                return {'pattern': 'Repeated category', 'category': worst_category[0], 'count': worst_category[1]}
        
        return {'pattern': 'Normal', 'error_rate': 'Low'}
    
    def create_context_manager(self, category: ErrorCategory, severity: ErrorSeverity, 
                              operation: str = "", context: str = ""):
        """Create a context manager for wrapping risky operations"""
        return ErrorContext(self, category, severity, operation, context)

class ErrorContext:
    """Context manager for handling errors in specific operations"""
    
    def __init__(self, error_handler: ErrorHandler, category: ErrorCategory, 
                 severity: ErrorSeverity, operation: str = "", context: str = ""):
        self.error_handler = error_handler
        self.category = category
        self.severity = severity
        self.operation = operation
        self.context = context
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Handle the error
            suppress = self.error_handler.handle_error(
                error=exc_val,
                category=self.category,
                severity=self.severity,
                context=self.context,
                operation=self.operation
            )
            return suppress  # Suppress exception if error handler says to
        return False

# Convenience decorators for common error patterns
def handle_episodic_errors(error_handler: ErrorHandler, severity: ErrorSeverity = ErrorSeverity.MEDIUM_ALERT):
    """Decorator for episodic memory operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with error_handler.create_context_manager(
                ErrorCategory.EPISODIC_MEMORY, 
                severity, 
                operation=func.__name__
            ):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator

def handle_service_errors(error_handler: ErrorHandler, severity: ErrorSeverity = ErrorSeverity.LOW_DEBUG):
    """Decorator for service connection operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with error_handler.create_context_manager(
                ErrorCategory.SERVICE_CONNECTION, 
                severity, 
                operation=func.__name__
            ):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator

def handle_ui_errors(error_handler: ErrorHandler, severity: ErrorSeverity = ErrorSeverity.MEDIUM_ALERT):
    """Decorator for UI operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with error_handler.create_context_manager(
                ErrorCategory.UI_RENDERING, 
                severity, 
                operation=func.__name__
            ):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator