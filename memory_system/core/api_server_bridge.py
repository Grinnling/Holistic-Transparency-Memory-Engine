# api_server.py - NEW FILE NEEDED
"""
FastAPI bridge to expose rich_chat functionality via REST/WebSocket
Port: 8000 (main project API)
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import asyncio
from typing import List, Dict, Any, Set, Optional
import uuid
from uuid_extensions import uuid7
from datetime import datetime
import sys
import os
import subprocess
import requests

# Import EventEmitter for visibility stream
from event_emitter import EventEmitter, EventTier, get_emitter, VisibilityEvent

# Add path to CODE_IMPLEMENTATION folder and import chat system
sys.path.append('/home/grinnling/Development/CODE_IMPLEMENTATION')

# IMPORTANT: Import shared request context BEFORE rich_chat to avoid circular import issues
from request_context import request_id_var, get_request_id, set_request_id

from rich_chat import RichMemoryChat
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
from service_manager import ServiceManager
from conversation_orchestrator import ConversationOrchestrator, _get_ozolith

app = FastAPI(title="Memory Chat API", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Add unique request ID to each request for distributed tracing.

    SECURITY: Always generate fresh ID at entry point.
    Never trust incoming X-Request-ID from external users.
    Uses UUID7 for chronological sorting.
    """
    # Use shared request context module
    request_id = set_request_id()  # Generates UUID7 and sets it

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Initialize error handler FIRST (shared instance for all components)
error_handler = ErrorHandler(debug_mode=True)

# Initialize chat system and service manager with shared error_handler
# debug_mode only affects logging visibility, not functionality
chat = RichMemoryChat(debug_mode=False, auto_start_services=True, error_handler=error_handler)
service_manager = ServiceManager(error_handler=error_handler, debug_mode=True)

# Initialize conversation orchestrator for sidebar management
orchestrator = ConversationOrchestrator(error_handler=error_handler)

# Register recovery systems with error handler for automatic recovery
# This late-binding allows error_handler to be created first, then wired to systems
if hasattr(chat, 'backup_system') and chat.backup_system:
    error_handler.register_recovery_systems(
        backup_system=chat.backup_system,
        recovery_thread=getattr(chat, 'recovery_thread', None),
        service_manager=service_manager
    )

# Pydantic models
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    confidence_score: float | None = None
    operation_context: str | None = None  # What operation triggered this
    error: str | None = None
    retrieved_context: list[str] | None = None  # Debug: Retrieved memories
    request_id: str | None = None  # For distributed tracing
    storage_warning: str | None = None  # Warning if exchange wasn't saved (degraded state)

class ErrorEvent(BaseModel):
    id: str
    timestamp: str
    error: str
    operation_context: str = None
    service: str = None
    severity: str = "normal"  # critical, warning, normal, debug
    attempted_fixes: List[str] = []
    fix_success: bool = None

class FrontendErrorReport(BaseModel):
    """Error report from React frontend - routes to centralized ErrorHandler"""
    source: str                      # Component name: ServiceStatusPanel, App, SidebarsPanel
    operation: str                   # What was attempted: fetchLLMStatus, sendMessage, spawnSidebar
    message: str                     # The actual error message
    context: Optional[str] = None    # Additional context: service name, sidebar ID, etc.
    severity: str = "medium"         # Maps to ErrorSeverity: critical, high, medium, low, trace

# Sidebar management models
class SpawnSidebarRequest(BaseModel):
    parent_id: str
    reason: str
    inherit_last_n: int | None = None  # None = inherit all exchanges

class MergeSidebarRequest(BaseModel):
    summary: str | None = None  # Manual summary of findings
    auto_summarize: bool = False  # Let LLM generate summary

class SidebarResponse(BaseModel):
    """Standard response for sidebar operations"""
    id: str
    status: str
    parent_id: str | None = None
    reason: str | None = None
    created_at: str | None = None
    message: str | None = None  # Human-readable status message

class CreateRootRequest(BaseModel):
    """Request to create a new root conversation context"""
    task_description: str = "Main conversation"
    created_by: str = "human"

# Legacy error_tracker removed - now using centralized ErrorHandler

# Helper function to get current request ID
def get_request_id() -> str:
    """Get the current request ID from context (returns 'unknown' if not in request context)"""
    return request_id_var.get() or "unknown"

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

# Separate WebSocket connections for event stream (per PRD: Option B - separate socket)
# This provides better siloing - event stream is its own concern
event_connections: List[WebSocket] = []

async def broadcast_to_react(message: dict):
    """Send updates to all connected React clients (chat channel)"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            active_connections.remove(connection)


async def broadcast_event_to_react(event: VisibilityEvent):
    """
    Send visibility event to all connected event stream clients.

    Per VISIBILITY_STREAM_PRD.md:
    - Separate WebSocket for events (Option B)
    - Events already tiered by EventEmitter
    - React receives events and displays based on tier
    """
    event_dict = event.to_dict()
    event_dict["channel"] = "visibility_stream"  # Identify the channel

    disconnected = []
    for connection in event_connections:
        try:
            await connection.send_json(event_dict)
        except Exception:
            disconnected.append(connection)

    # Clean up disconnected clients
    for conn in disconnected:
        if conn in event_connections:
            event_connections.remove(conn)

def track_error(error_msg: str, operation_context: str = None, service: str = "api_server", severity: str = "normal", original_exception: Exception = None):
    """Track errors using centralized ErrorHandler and broadcast to React

    Args:
        error_msg: Human-readable error message
        operation_context: Context of the operation that failed
        service: Service name for error categorization
        severity: Error severity level (critical, warning, normal, debug)
        original_exception: Optional original exception to preserve stack trace
    """

    # Map string severity to ErrorSeverity enum
    severity_map = {
        "critical": ErrorSeverity.CRITICAL_STOP,
        "warning": ErrorSeverity.MEDIUM_ALERT,
        "normal": ErrorSeverity.MEDIUM_ALERT,
        "debug": ErrorSeverity.LOW_DEBUG
    }
    error_severity = severity_map.get(severity, ErrorSeverity.MEDIUM_ALERT)

    # Map service to ErrorCategory
    category_map = {
        "chat_processor": ErrorCategory.MESSAGE_PROCESSING,
        "api_server": ErrorCategory.SERVICE_CONNECTION,
        "websocket": ErrorCategory.SERVICE_CONNECTION,
        "memory_system": ErrorCategory.WORKING_MEMORY
    }
    error_category = category_map.get(service, ErrorCategory.GENERAL)

    # Use original exception if provided, otherwise create from message
    # This preserves stack traces and exception types for better debugging
    error_exception = original_exception if original_exception is not None else Exception(error_msg)

    # Use centralized error handler
    error_handler.handle_error(
        error_exception,
        error_category,
        error_severity,
        context=operation_context or "API operation",
        operation=service or "api_request"
    )

    # Broadcast to React for real-time updates
    error_event = ErrorEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        error=error_msg,
        operation_context=operation_context,
        service=service,
        severity=severity
    )

    asyncio.create_task(broadcast_to_react({
        "type": "error_update",
        "error": error_event.dict()
    }))

# REST Endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """Main chat endpoint - processes message through your existing system"""
    try:
        print(f"[API DEBUG] Received message: {message.message}")
        print(f"[API DEBUG] Memory handler services: {chat.memory_handler.services}")

        # Check for commands first (React interface command handling)
        if message.message == '/help':
            help_text = chat._get_help_text()
            return ChatResponse(
                response=help_text,
                operation_context="help_command",
                request_id=get_request_id()
            )

        # Handle toggle commands
        if message.message == '/tokens':
            chat.toggle_token_display()
            status = "ON" if chat.show_tokens else "OFF"
            return ChatResponse(
                response=f"✅ Token display is now {status}",
                operation_context="toggle_command"
            )

        if message.message == '/confidence':
            chat.toggle_confidence_display()
            status = "ON" if chat.show_confidence else "OFF"
            return ChatResponse(
                response=f"✅ Confidence markers are now {status}",
                operation_context="toggle_command"
            )

        if message.message == '/debug':
            chat.toggle_debug_mode()
            status = "ON" if chat.debug_mode else "OFF"
            return ChatResponse(
                response=f"✅ Debug mode is now {status}",
                operation_context="toggle_command"
            )

        if message.message == '/errors':
            chat.toggle_error_panel()
            status = "ON" if chat.show_error_panel else "OFF"
            return ChatResponse(
                response=f"✅ Error panel is now {status}",
                operation_context="toggle_command"
            )

        # Handle display commands (Note: These display to CLI console, not React UI yet)
        if message.message == '/status':
            chat.show_status()
            return ChatResponse(
                response="📊 System status displayed in server console (React UI display coming soon)",
                operation_context="status_command"
            )

        if message.message == '/context':
            chat.show_context_preview()
            return ChatResponse(
                response="🔍 Context preview displayed in server console (React UI display coming soon)",
                operation_context="context_command"
            )

        if message.message == '/stats':
            chat.show_memory_stats()
            return ChatResponse(
                response="💾 Memory stats displayed in server console (React UI display coming soon)",
                operation_context="stats_command"
            )

        # Validate slash commands before sending to LLM
        if message.message.startswith('/'):
            valid_commands = [
                '/quit', '/help', '/status', '/memory', '/history', '/search',
                '/context', '/debug', '/stats', '/tokens', '/confidence',
                '/new', '/list', '/switch', '/services', '/start-services',
                '/stop-services', '/recovery', '/ball', '/errors'
            ]
            command = message.message.split()[0]  # Get first word (the command)
            if command not in valid_commands:
                return ChatResponse(
                    response=f"❌ Unknown command: {command}\nType /help for a list of valid commands",
                    operation_context="invalid_command",
                    request_id=get_request_id()
                )

        # Process through your existing rich_chat system
        result = chat.process_message(message.message)

        # Check if result is None (indicates internal error)
        if result is None:
            raise ValueError("process_message returned None - internal processing failed")

        # Extract response and metadata
        validation_data = result.get('validation') or {}
        response = ChatResponse(
            response=result.get('response', 'No response generated'),
            confidence_score=validation_data.get('confidence_score'),
            operation_context=f"chat_message: {message.message[:50]}...",
            retrieved_context=result.get('retrieved_context'),  # Debug: Pass through retrieved memories
            request_id=get_request_id(),
            storage_warning=result.get('storage_warning')  # Surface degraded state to user
        )
        
        # NOTE: Exchange storage is handled by rich_chat.process_message() via orchestrator.add_exchange()
        # DO NOT duplicate storage here - that causes double-write bugs
        # Just persist the context to ensure it's saved
        active_id = orchestrator.get_active_context_id()
        if active_id:
            active_ctx = orchestrator.get_context(active_id)
            if active_ctx:
                orchestrator._persist_context(active_ctx)

        # Broadcast to React
        await broadcast_to_react({
            "type": "chat_update",
            "message": {
                "role": "user",
                "content": message.message,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        await broadcast_to_react({
            "type": "chat_update", 
            "message": {
                "role": "assistant",
                "content": response.response,
                "timestamp": datetime.now().isoformat(),
                "confidence_score": response.confidence_score
            }
        })
        
        return response
        
    except Exception as e:
        error_msg = f"Chat processing failed: {str(e)}"
        track_error(error_msg, f"chat_message: {message.message[:50]}...", "chat_processor", "critical", original_exception=e)
        
        return ChatResponse(
            response="Sorry, I encountered an error processing your message.",
            error=error_msg,
            operation_context=f"chat_message: {message.message[:50]}...",
            request_id=get_request_id()
        )

@app.get("/health")
async def health_check():
    """Check all service health using ServiceManager"""
    # Use ServiceManager for clean, centralized health checking
    return {
        "status": "healthy",
        "service": "api_server_bridge",
        "request_id": get_request_id(),
        "downstream_services": service_manager.check_services(show_table=False)
    }

@app.get("/history")
async def get_history():
    """Get conversation history"""
    try:
        return {
            "history": chat.conversation_history,
            "conversation_id": chat.conversation_id
        }
    except Exception as e:
        track_error(f"History retrieval failed: {str(e)}", "get_history", "chat_processor", "warning", original_exception=e)
        return {"error": "Could not retrieve history", "history": []}

@app.get("/errors")
async def get_errors():
    """Get error log for React error panel - using centralized ErrorHandler"""
    try:
        # Get errors from the centralized error handler
        error_summary = error_handler.get_error_summary()
        recent_error_data = error_handler.recent_errors  # Direct access to structured error data

        # Convert to format expected by React frontend
        formatted_errors = []
        for error_record in recent_error_data:
            # Map ErrorSeverity to React severity levels
            severity_map = {
                "critical_stop": "critical",
                "high_degrade": "critical",
                "medium_alert": "warning",
                "low_debug": "debug",
                "trace_fiwb": "debug"
            }

            error_id = error_record.get('error_id', str(uuid.uuid4()))  # Use stored ID or generate fallback
            formatted_errors.append({
                "id": error_id,
                "timestamp": error_record['timestamp'].isoformat(),
                "error": error_record['message'],
                "severity": severity_map.get(error_record['severity'], "normal"),
                "operation_context": error_record.get('operation', 'unknown'),
                "service": error_record.get('category', 'unknown'),
                "attempted_fixes": [error_record.get('category')] if error_record.get('recovery_attempted') else [],
                "fix_success": error_record.get('recovery_succeeded'),
                "acknowledged": error_id in error_handler.acknowledged_errors
            })

        return {
            "session": formatted_errors,
            "recent": formatted_errors,  # Same as session for now
            "summary": error_summary
        }

    except Exception as e:
        # Fallback error handling
        return {
            "session": [],
            "recent": [],
            "summary": {"error": f"Error handler failed: {str(e)}"}
        }

@app.post("/errors/{error_id}/acknowledge")
async def acknowledge_error(error_id: str):
    """Mark error as acknowledged using centralized ErrorHandler with validation"""
    result = error_handler.acknowledge_error(error_id)

    if not result['success']:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "error": result['error'], "error_id": error_id}
        )

    return {
        "status": "acknowledged",
        "error_id": error_id,
        "error_category": result.get('error_category'),
        "error_message": result.get('error_message')
    }

@app.post("/errors/clear")
async def clear_errors():
    """Clear all errors from centralized ErrorHandler"""
    # Clear error handler's error tracking
    error_handler.recent_errors = []
    error_handler.error_counts.clear()
    error_handler.suppressed_errors.clear()
    error_handler.last_error_time.clear()
    error_handler.alert_queue = []
    error_handler.critical_alerts = []
    error_handler.acknowledged_errors.clear()

    await broadcast_to_react({"type": "errors_cleared"})
    return {"status": "cleared"}

@app.post("/errors/report")
async def report_frontend_error(report: FrontendErrorReport):
    """
    Receive error reports from React frontend and route to centralized ErrorHandler.

    This bridges the gap: frontend errors now go to the same place as backend errors,
    giving full visibility in the Error Panel.
    """
    import uuid
    from datetime import datetime

    # Map severity string to ErrorSeverity enum
    severity_map = {
        "critical": ErrorSeverity.CRITICAL_STOP,
        "high": ErrorSeverity.HIGH_DEGRADE,
        "medium": ErrorSeverity.MEDIUM_ALERT,
        "low": ErrorSeverity.LOW_DEBUG,
        "trace": ErrorSeverity.TRACE_FIWB
    }
    severity = severity_map.get(report.severity, ErrorSeverity.MEDIUM_ALERT)

    # Map source to ErrorCategory - frontend sources get UI category
    category_map = {
        "ServiceStatusPanel": ErrorCategory.SERVICE_HEALTH,
        "App": ErrorCategory.UI_RENDERING,
        "SidebarsPanel": ErrorCategory.CONVERSATION_FLOW,
        "ErrorPanel": ErrorCategory.UI_RENDERING,
        "TerminalDisplay": ErrorCategory.UI_RENDERING
    }
    category = category_map.get(report.source, ErrorCategory.UI_RENDERING)

    # Create a synthetic exception for the ErrorHandler
    frontend_error = Exception(report.message)

    # Build context string
    context_parts = [f"[Frontend:{report.source}]"]
    if report.context:
        context_parts.append(report.context)
    context_str = " ".join(context_parts)

    # Route through centralized ErrorHandler
    error_handler.handle_error(
        error=frontend_error,
        category=category,
        severity=severity,
        context=context_str,
        operation=report.operation,
        suppress_duplicate_minutes=1,  # Shorter suppression for frontend errors
        attempt_recovery=False  # Frontend can't auto-recover via backend
    )

    # Get the error_id from the most recent error (just added)
    error_id = error_handler.recent_errors[-1]['error_id'] if error_handler.recent_errors else str(uuid.uuid4())

    # Broadcast to React so ErrorPanel updates
    await broadcast_to_react({
        "type": "frontend_error_reported",
        "error_id": error_id,
        "source": report.source,
        "operation": report.operation
    })

    return {
        "status": "reported",
        "error_id": error_id,
        "category": category.value,
        "severity": severity.value
    }

# Memory System Endpoints (Task 2)
@app.get("/memory/stats")
async def get_memory_stats():
    """Get memory statistics for dashboard"""
    try:
        episodic_count = chat.memory_handler.get_memory_count()
        working_memory_count = len(chat.conversation_history)

        return {
            "episodic_count": episodic_count,
            "working_memory_count": working_memory_count,
            "conversation_id": chat.conversation_id,
            "archival_failures": chat.memory_handler.episodic_archival_failures,
            "archival_healthy": chat.memory_handler.episodic_archival_failures < 3
        }
    except Exception as e:
        track_error(f"Memory stats failed: {str(e)}", "get_memory_stats", "memory_system", "warning", original_exception=e)
        return {
            "episodic_count": 0,
            "working_memory_count": 0,
            "conversation_id": chat.conversation_id,
            "error": str(e)
        }

@app.get("/memory/search")
async def search_memories(query: str):
    """Search episodic memories"""
    try:
        if not query or query.strip() == "":
            return {"error": "Query parameter required", "results": []}

        results = chat.memory_handler.search_memories(query)
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        track_error(f"Memory search failed: {str(e)}", f"search_query: {query}", "memory_system", "warning", original_exception=e)
        return {
            "error": str(e),
            "results": []
        }

@app.post("/memory/clear")
async def clear_episodic():
    """Clear episodic storage - INTENTIONALLY DISABLED

    This operation is too dangerous for production use.
    Deleting episodic memories is ethically questionable and risks catastrophic data loss.

    Post-demo feature: Snapshot-based barriers (safe reset without deletion)
    """
    return {
        "status": "not_supported",
        "message": "Memory clear intentionally disabled to prevent accidental data loss.",
        "future_design": {
            "approach": "snapshot_based_barriers",
            "description": "Create timestamp markers that act as soft barriers for search queries",
            "benefits": [
                "No data loss - memories preserved behind barrier",
                "Fast reset - just add a marker",
                "Easy rollback - remove the marker",
                "Multiple named snapshots supported",
                "Ethically sound - we don't destroy memories"
            ],
            "example": "snapshot_id = create_snapshot('demo_baseline')"
        },
        "for_testing": "Contact operator if urgent DB reset needed (requires deliberate action)"
    }

# ServiceManager endpoints for React frontend flexibility

@app.get("/services/dashboard")
async def get_service_dashboard():
    """Get comprehensive service data for React dashboard"""
    return service_manager.get_dashboard_data()

@app.get("/services/{service_name}/health")
async def get_service_health(service_name: str):
    """Get detailed health info for a specific service"""
    return service_manager.get_service_health_detailed(service_name)

@app.post("/services/{service_name}/restart")
async def restart_service(service_name: str):
    """Smart restart of a specific service"""
    try:
        success = service_manager.smart_recovery(service_name)
        return {
            "status": "success" if success else "failed",
            "service": service_name,
            "message": f"Service {service_name} {'restarted successfully' if success else 'restart failed'}"
        }
    except Exception as e:
        error_handler.handle_error(
            e,
            ErrorCategory.SERVICE_HEALTH,
            ErrorSeverity.MEDIUM_ALERT,
            context=f"API restart request for {service_name}",
            operation="service_restart_api"
        )
        return {
            "status": "error",
            "service": service_name,
            "message": f"Error restarting {service_name}: {str(e)}"
        }

# Service port mapping for stop/start by port
SERVICE_PORTS = {
    'working_memory': 5001,
    'curator': 8004,
    'mcp_logger': 8001,
    'episodic_memory': 8005,
}

def stop_service_by_port(port: int, service_name: str) -> dict:
    """Stop a service by finding and killing the process on its port (like stop_services.sh)"""
    import subprocess
    import signal

    try:
        # Find PID using lsof
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0 or not result.stdout.strip():
            return {"success": True, "message": f"{service_name} not running (port {port} free)", "was_running": False}

        pids = result.stdout.strip().split('\n')

        for pid in pids:
            pid = pid.strip()
            if pid:
                try:
                    pid_int = int(pid)
                    # Try graceful SIGTERM first
                    os.kill(pid_int, signal.SIGTERM)
                except (ValueError, ProcessLookupError):
                    continue

        # Wait up to 5 seconds for graceful shutdown
        import time
        for _ in range(5):
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.returncode != 0 or not result.stdout.strip():
                return {"success": True, "message": f"{service_name} stopped gracefully", "was_running": True}
            time.sleep(1)

        # Force kill if still running
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        if result.stdout.strip():
            for pid in result.stdout.strip().split('\n'):
                try:
                    os.kill(int(pid.strip()), signal.SIGKILL)
                except:
                    pass

        return {"success": True, "message": f"{service_name} force stopped", "was_running": True}

    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"Timeout checking port {port}"}
    except Exception as e:
        return {"success": False, "message": f"Error stopping {service_name}: {str(e)}"}

@app.post("/services/{service_name}/stop")
async def stop_service(service_name: str):
    """Stop a specific service by killing its process"""
    if service_name not in SERVICE_PORTS:
        return {
            "status": "error",
            "service": service_name,
            "message": f"Unknown service: {service_name}. Valid services: {list(SERVICE_PORTS.keys())}"
        }

    port = SERVICE_PORTS[service_name]
    result = stop_service_by_port(port, service_name)

    return {
        "status": "success" if result["success"] else "error",
        "service": service_name,
        "port": port,
        "message": result["message"],
        "was_running": result.get("was_running", False)
    }

@app.post("/services/{service_name}/start")
async def start_service(service_name: str):
    """Start a specific service"""
    if service_name not in SERVICE_PORTS:
        return {
            "status": "error",
            "service": service_name,
            "message": f"Unknown service: {service_name}. Valid services: {list(SERVICE_PORTS.keys())}"
        }

    try:
        # Use ServiceManager's internal start method
        success = service_manager._start_service(service_name)
        return {
            "status": "success" if success else "failed",
            "service": service_name,
            "message": f"Service {service_name} {'started successfully' if success else 'failed to start'}"
        }
    except Exception as e:
        return {
            "status": "error",
            "service": service_name,
            "message": f"Error starting {service_name}: {str(e)}"
        }

@app.post("/services/group/{group_name}/start")
async def start_service_group(group_name: str):
    """Start a group of services (e.g., 'memory_system', 'all')"""
    try:
        success = service_manager.start_group(group_name)
        return {
            "status": "success" if success else "partial",
            "group": group_name,
            "message": f"Service group {group_name} {'started successfully' if success else 'partially started'}"
        }
    except Exception as e:
        error_handler.handle_error(
            e,
            ErrorCategory.SERVICE_HEALTH,
            ErrorSeverity.MEDIUM_ALERT,
            context=f"API group start request for {group_name}",
            operation="service_group_start_api"
        )
        return {
            "status": "error",
            "group": group_name,
            "message": f"Error starting group {group_name}: {str(e)}"
        }

@app.post("/services/autostart")
async def autostart_services():
    """Auto-start all missing services"""
    try:
        success = service_manager.auto_start_services()
        return {
            "status": "success" if success else "partial",
            "message": "Auto-start completed" if success else "Some services failed to start"
        }
    except Exception as e:
        error_handler.handle_error(
            e,
            ErrorCategory.AUTO_START,
            ErrorSeverity.MEDIUM_ALERT,
            context="API auto-start request",
            operation="autostart_api"
        )
        return {
            "status": "error",
            "message": f"Auto-start failed: {str(e)}"
        }


# =============================================================================
# LLM Status and Admin Control Endpoints
# =============================================================================

# LLM Model Role Configuration (environment-based)
# These allow explicit mapping of model names to roles instead of string guessing
LLM_CHAT_MODEL = os.environ.get('LLM_CHAT_MODEL', '')
LLM_EMBEDDING_MODEL = os.environ.get('LLM_EMBEDDING_MODEL', '')
LLM_RERANK_MODEL = os.environ.get('LLM_RERANK_MODEL', '')


@app.get("/llm/status")
async def get_llm_status():
    """
    Get status of all LLM connections (chat, embedding, rerank).
    Queries LM Studio /v1/models to see what's loaded.
    Uses LLM_CHAT_MODEL, LLM_EMBEDDING_MODEL, LLM_RERANK_MODEL env vars for explicit mapping.
    Falls back to pattern matching if env vars not set.
    """
    result = {
        "chat": {
            "status": "offline",
            "provider": None,
            "model": None,
            "configured_model": LLM_CHAT_MODEL or None
        },
        "embedding": {
            "status": "offline",
            "model": None,
            "endpoint": "http://localhost:1234/v1/embeddings",
            "configured_model": LLM_EMBEDDING_MODEL or None
        },
        "rerank": {
            "status": "not_configured",
            "model": None,
            "note": "Rerank endpoint not yet implemented" if not LLM_RERANK_MODEL else None,
            "configured_model": LLM_RERANK_MODEL or None
        },
        "lmstudio_models": [],
        "config_source": "env_vars" if (LLM_CHAT_MODEL or LLM_EMBEDDING_MODEL or LLM_RERANK_MODEL) else "auto_detect"
    }

    # Track provider info from internal connector (but don't trust connection status yet)
    if chat and chat.llm:
        result["chat"]["provider"] = chat.llm.provider.value if hasattr(chat.llm, 'provider') else "unknown"

    # Query LM Studio for loaded models - this is the source of truth for connection status
    lmstudio_responding = False
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=3)
        if response.ok:
            lmstudio_responding = True
            models_data = response.json().get('data', [])
            model_ids = [m.get('id', 'unknown') for m in models_data]
            result["lmstudio_models"] = model_ids

            # If env vars are configured, use them for matching
            if LLM_CHAT_MODEL:
                for model_id in model_ids:
                    if LLM_CHAT_MODEL.lower() in model_id.lower() or model_id.lower() in LLM_CHAT_MODEL.lower():
                        result["chat"]["model"] = model_id
                        result["chat"]["status"] = "connected"
                        break
            else:
                # Fallback: first non-embedding model
                for model_id in model_ids:
                    if 'embed' not in model_id.lower() and 'bge' not in model_id.lower() and 'rerank' not in model_id.lower():
                        result["chat"]["model"] = model_id
                        result["chat"]["status"] = "connected"
                        break

            if LLM_EMBEDDING_MODEL:
                for model_id in model_ids:
                    if LLM_EMBEDDING_MODEL.lower() in model_id.lower() or model_id.lower() in LLM_EMBEDDING_MODEL.lower():
                        result["embedding"]["status"] = "available"
                        result["embedding"]["model"] = model_id
                        break
            else:
                # Fallback: first embedding-like model (not rerank)
                for model_id in model_ids:
                    if ('embed' in model_id.lower() or 'bge' in model_id.lower()) and 'rerank' not in model_id.lower():
                        result["embedding"]["status"] = "available"
                        result["embedding"]["model"] = model_id
                        break

            if LLM_RERANK_MODEL:
                for model_id in model_ids:
                    if LLM_RERANK_MODEL.lower() in model_id.lower() or model_id.lower() in LLM_RERANK_MODEL.lower():
                        result["rerank"]["status"] = "available"
                        result["rerank"]["model"] = model_id
                        result["rerank"]["note"] = None
                        break
            else:
                # Fallback: model with rerank in name
                for model_id in model_ids:
                    if 'rerank' in model_id.lower():
                        result["rerank"]["status"] = "available"
                        result["rerank"]["model"] = model_id
                        result["rerank"]["note"] = None
                        break

            # If LM Studio responded but no rerank model found, it's not configured (not offline)
            # rerank stays at default "not_configured"

    except Exception as e:
        result["lmstudio_error"] = str(e)
        # LM Studio not responding - all models are offline
        result["chat"]["status"] = "offline"
        result["embedding"]["status"] = "offline"
        result["rerank"]["status"] = "offline"
        result["rerank"]["note"] = "LM Studio not responding"

    return result


@app.post("/llm/reconnect")
async def reconnect_llm():
    """
    Attempt to reconnect to LLM without full restart.
    Re-runs SmartLLMSelector.find_available_llm().
    """
    global chat
    try:
        from llm_connector import SmartLLMSelector

        new_llm = SmartLLMSelector.find_available_llm(
            debug_mode=chat.debug_mode if chat else False,
            error_handler=chat.error_handler if chat else None
        )

        if new_llm:
            chat.llm = new_llm
            provider = new_llm.provider.value if hasattr(new_llm, 'provider') else "unknown"
            return {
                "success": True,
                "provider": provider,
                "message": f"LLM reconnected successfully via {provider}"
            }
        else:
            return {
                "success": False,
                "message": "No LLM provider found. Is LM Studio running?"
            }
    except Exception as e:
        error_handler.handle_error(
            e,
            ErrorCategory.LLM_COMMUNICATION,
            ErrorSeverity.MEDIUM_ALERT,
            context="LLM reconnect request",
            operation="llm_reconnect_api"
        )
        return {
            "success": False,
            "message": f"Reconnect failed: {str(e)}"
        }


@app.post("/services/shutdown")
async def shutdown_api():
    """
    Graceful API shutdown - saves state before exit.
    Called by admin panel for controlled shutdown.
    """
    try:
        # Save all contexts to SQLite
        if orchestrator:
            orchestrator.save_all_contexts()
            print("Saved all contexts before shutdown")

        # Log shutdown to OZOLITH if available
        oz = _get_ozolith()
        if oz:
            from datashapes import OzolithEventType
            oz.append(
                event_type=OzolithEventType.SESSION_END,
                context_id=orchestrator.get_active_context_id() if orchestrator else "unknown",
                actor="system",
                payload={"reason": "graceful_shutdown", "initiated_by": "admin_panel"}
            )

        # Schedule actual shutdown after response is sent
        async def delayed_shutdown():
            await asyncio.sleep(0.5)
            os._exit(0)

        asyncio.create_task(delayed_shutdown())

        return {"success": True, "message": "Shutdown initiated - API will stop in 0.5s"}

    except Exception as e:
        error_handler.handle_error(
            e,
            ErrorCategory.SERVICE_MANAGEMENT,
            ErrorSeverity.HIGH_ALERT,
            context="API shutdown request",
            operation="shutdown_api"
        )
        return {"success": False, "message": f"Shutdown failed: {str(e)}"}


@app.post("/services/cluster-restart")
async def cluster_restart():
    """
    Trigger full cluster restart.

    Flow:
    1. Save all state (contexts, conversations)
    2. Spawn external restart script (handles memory services, React, Redis)
    3. API gracefully shuts itself down after response is sent
    4. External script starts new API in tmux

    This avoids the race condition of a child process killing its parent.
    """
    try:
        # First do graceful state save
        if orchestrator:
            orchestrator.save_all_contexts()
            print("Saved all contexts before cluster restart")

        script_dir = "/home/grinnling/Development/CODE_IMPLEMENTATION"
        restart_script = f"{script_dir}/restart_external_services.sh"

        # Check script exists
        if not os.path.exists(restart_script):
            return {
                "success": False,
                "message": f"Restart script not found: {restart_script}"
            }

        # Spawn external restart script in detached process
        # This handles everything EXCEPT killing the API
        subprocess.Popen(
            ["bash", restart_script],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Schedule API self-shutdown after response is sent
        # The external script will start a new API instance in tmux
        async def delayed_self_shutdown():
            await asyncio.sleep(1.0)  # Give time for response to be sent
            print("API shutting down for cluster restart...")
            os._exit(0)

        asyncio.create_task(delayed_self_shutdown())

        return {
            "success": True,
            "message": "Cluster restart initiated - API will restart in ~5 seconds"
        }

    except Exception as e:
        error_handler.handle_error(
            e,
            ErrorCategory.SERVICE_MANAGEMENT,
            ErrorSeverity.HIGH_ALERT,
            context="Cluster restart request",
            operation="cluster_restart_api"
        )
        return {"success": False, "message": f"Restart failed: {str(e)}"}


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates to React"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send current state on connect
        await websocket.send_json({
            "type": "connection_established",
            "conversation_id": chat.conversation_id,
            "message_count": len(chat.conversation_history)
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle different message types from React
                if message_data["type"] == "ping":
                    await websocket.send_json({"type": "pong"})
                    
                elif message_data["type"] == "chat_message":
                    # Process message and broadcast response
                    result = chat.process_message(message_data["message"])
                    await websocket.send_json({
                        "type": "chat_response",
                        "response": result
                    })
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                track_error(f"WebSocket error: {str(e)}", "websocket_handling", "api_server", "warning", original_exception=e)
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
                
    finally:
        active_connections.remove(websocket)


# Separate WebSocket endpoint for visibility/event stream
# Per VISIBILITY_STREAM_PRD.md: Option B - separate socket for better siloing
@app.websocket("/ws/events")
async def events_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for visibility event stream to React.

    Separate from main chat WebSocket for:
    - Independent reconnection (events don't drop if chat hiccups)
    - Different retention policies possible
    - Cleaner React message handling
    - Better siloing - event stream is its own concern

    Events include: context_loaded, memory_retrieved, validation_result,
    error_occurred, sidebar_lifecycle, memory_pressure, etc.
    """
    await websocket.accept()
    event_connections.append(websocket)

    # Get the global emitter and wire up the broadcast
    emitter = get_emitter()

    try:
        # Send connection established event
        await websocket.send_json({
            "type": "event_stream_connected",
            "channel": "visibility_stream",
            "stream_tiers": [t.name.lower() for t in emitter._stream_tiers],
            "event_types": emitter.get_event_types(),
            "buffer_size": len(emitter._event_buffer)
        })

        # Send recent events from buffer (catch-up)
        recent = emitter.get_recent_events(50)
        if recent:
            await websocket.send_json({
                "type": "event_history",
                "events": [e.to_dict() for e in recent]
            })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                # Handle different message types from React
                if message_data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                elif message_data.get("type") == "set_stream_tiers":
                    # Allow React to configure which tiers to stream
                    tier_names = message_data.get("tiers", ["critical"])
                    tiers = set()
                    for name in tier_names:
                        try:
                            tiers.add(EventTier[name.upper()])
                        except KeyError:
                            pass
                    emitter.set_stream_tiers(tiers)
                    await websocket.send_json({
                        "type": "tiers_updated",
                        "stream_tiers": [t.name.lower() for t in emitter._stream_tiers]
                    })

                elif message_data.get("type") == "get_stats":
                    # Return emitter statistics
                    await websocket.send_json({
                        "type": "emitter_stats",
                        "stats": emitter.stats()
                    })

                elif message_data.get("type") == "get_history":
                    # Get more history from buffer
                    count = message_data.get("count", 100)
                    tier_filter = message_data.get("tier")
                    type_filter = message_data.get("event_type")

                    tier = EventTier[tier_filter.upper()] if tier_filter else None
                    events = emitter.get_recent_events(count, tier=tier, event_type=type_filter)
                    await websocket.send_json({
                        "type": "event_history",
                        "events": [e.to_dict() for e in events]
                    })

            except WebSocketDisconnect:
                break
            except Exception as e:
                track_error(f"Events WebSocket error: {str(e)}", "events_websocket", "api_server", "warning", original_exception=e)
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })

    finally:
        if websocket in event_connections:
            event_connections.remove(websocket)


# REST endpoint for event stream stats and history
@app.get("/events/stats")
async def get_event_stats():
    """Get visibility event stream statistics"""
    emitter = get_emitter()
    return emitter.stats()


@app.get("/events/history")
async def get_event_history(count: int = 100, tier: str = None, event_type: str = None):
    """
    Get recent events from buffer.

    Query params:
    - count: Number of events (default 100)
    - tier: Filter by tier (critical, system, debug)
    - event_type: Filter by event type
    """
    emitter = get_emitter()
    tier_enum = EventTier[tier.upper()] if tier else None
    events = emitter.get_recent_events(count, tier=tier_enum, event_type=event_type)
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "filters": {"tier": tier, "event_type": event_type}
    }


@app.get("/events/types")
async def get_event_types():
    """Get all known event types and their tier classifications"""
    emitter = get_emitter()
    return {
        "event_types": emitter.get_event_types(),
        "tiers": ["critical", "system", "debug"],
        "tier_descriptions": {
            "critical": "Poison detection - context, memory, validation, errors",
            "system": "System visibility - OZOLITH, sidebars, memory pressure",
            "debug": "Deep dive - LLM prompts, tool invocations, file ops"
        }
    }


# =============================================================================
# SIDEBAR MANAGEMENT ENDPOINTS
# Expose ConversationOrchestrator to React UI
# =============================================================================

@app.get("/sidebars")
async def list_sidebars(
    status: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "last_activity",
    sort_order: str = "desc",
    search: str | None = None,
    actor: str = "human"
):
    """
    List conversation contexts with pagination, sorting, and search.

    Query params:
    - status: Filter by status (active, paused, merged, archived, etc.)
    - include_archived: Include archived contexts (default False)
    - limit: Max results to return (default 50, max 200)
    - offset: Skip this many results (for pagination)
    - sort_by: Sort field (last_activity, created_at, task_description, exchange_count)
    - sort_order: asc or desc (default desc)
    - search: Fuzzy search on task_description
    - actor: Who is viewing (for alias resolution, default "human")
    """
    try:
        # Convert status string to enum if provided
        status_filter = None
        if status:
            from datashapes import SidebarStatus
            try:
                status_filter = SidebarStatus[status.upper()]
            except KeyError:
                return {"error": f"Unknown status: {status}", "valid_statuses": [s.name.lower() for s in SidebarStatus]}

        contexts = orchestrator.list_contexts(status=status_filter, include_archived=include_archived)
        total_count = len(contexts)

        # Fuzzy search on task_description and actor's alias
        if search:
            search_lower = search.lower()
            contexts = [
                ctx for ctx in contexts
                if (ctx.task_description and search_lower in ctx.task_description.lower())
                or (resolve_display_name(ctx, actor) and search_lower in resolve_display_name(ctx, actor).lower())
            ]

        # Sorting
        sort_key_map = {
            "last_activity": lambda c: c.last_activity or c.created_at,
            "created_at": lambda c: c.created_at,
            "task_description": lambda c: (c.task_description or "").lower(),
            "exchange_count": lambda c: len(c.local_memory),
        }
        sort_key = sort_key_map.get(sort_by, sort_key_map["last_activity"])
        reverse = sort_order.lower() != "asc"
        contexts = sorted(contexts, key=sort_key, reverse=reverse)

        # Pagination
        limit = min(limit, 200)  # Cap at 200
        paginated = contexts[offset:offset + limit]

        # Convert to JSON-serializable format
        return {
            "contexts": [
                {
                    "id": ctx.sidebar_id,
                    "parent_id": ctx.parent_context_id,
                    "status": ctx.status.name.lower(),
                    "reason": ctx.task_description,
                    "display_name": resolve_display_name(ctx, actor),
                    "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
                    "last_activity": ctx.last_activity.isoformat() if ctx.last_activity else None,
                    "created_by": ctx.participants[0] if ctx.participants else "unknown",
                    "priority": ctx.priority.name.lower() if ctx.priority else None,
                    "exchange_count": len(ctx.local_memory),
                    "inherited_count": len(ctx.inherited_memory),
                    "tags": ctx.tags if hasattr(ctx, 'tags') else []
                }
                for ctx in paginated
            ],
            "count": len(paginated),
            "total": total_count,
            "filtered": len(contexts) if search else total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < (len(contexts) if search else total_count)
        }
    except Exception as e:
        track_error(f"List sidebars failed: {str(e)}", "list_sidebars", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "contexts": []}


@app.get("/sidebars/startup-state")
async def get_startup_state():
    """
    Get startup state for React UI initialization.

    Returns info needed for the UI to decide what to show:
    - If contexts exist: proceed to chat
    - If no contexts: show "Start Fresh" dialog

    This replaces the old auto-create stopgap with explicit user choice.
    """
    try:
        contexts = orchestrator.list_contexts(include_archived=False)
        active_id = orchestrator.get_active_context_id()
        stats = orchestrator.stats()

        return {
            "has_contexts": len(contexts) > 0,
            "context_count": len(contexts),
            "active_context_id": active_id,
            "needs_initialization": len(contexts) == 0,
            "stats": stats
        }
    except Exception as e:
        track_error(f"Get startup state failed: {str(e)}", "startup_state", "orchestrator", "warning", original_exception=e)
        return {
            "has_contexts": False,
            "context_count": 0,
            "active_context_id": None,
            "needs_initialization": True,
            "error": str(e)
        }


@app.post("/sidebars/create-root")
async def create_root_context(request: CreateRootRequest):
    """
    Create a new root conversation context.

    Used by React UI for "Start Fresh" action when no contexts exist.
    This is the entry point for a new conversation tree.
    """
    try:
        root_id = orchestrator.create_root_context(
            task_description=request.task_description,
            created_by=request.created_by
        )

        ctx = orchestrator.get_context(root_id)

        # Broadcast to any connected React clients
        await broadcast_to_react({
            "type": "root_created",
            "context": {
                "id": root_id,
                "task_description": request.task_description,
                "status": "active"
            }
        })

        return SidebarResponse(
            id=root_id,
            status="active",
            parent_id=None,
            reason=request.task_description,
            created_at=ctx.created_at.isoformat() if ctx and ctx.created_at else None,
            message=f"Created root context: {request.task_description}"
        )
    except Exception as e:
        track_error(f"Create root failed: {str(e)}", "create_root", "orchestrator", "critical", original_exception=e)
        return {"error": str(e), "id": None}


@app.get("/sidebars/tree")
async def get_sidebar_tree(
    root_id: str | None = None,
    actor: str = "human",
    sort_by: str = "last_activity",
    sort_order: str = "desc"
):
    """
    Get tree structure for visualization.

    Returns nested hierarchy showing parent-child relationships.
    Useful for breadcrumb navigation and tree view components.

    Query params:
    - root_id: Starting point (None = all roots)
    - actor: Who is viewing (for alias resolution, default "human")
    - sort_by: Sort field for roots (last_activity, created_at, task_description, exchange_count)
    - sort_order: asc or desc (default desc)
    """
    def augment_tree_node(node):
        """Add display_name, status, reason, and tags from context for the requesting actor."""
        if node is None:
            return None
        ctx = orchestrator._contexts.get(node.get('id'))
        if ctx:
            name = resolve_display_name(ctx, actor)
            if name:
                node['display_name'] = name
            node['status'] = ctx.status.name.lower() if hasattr(ctx.status, 'name') else str(ctx.status)
            # Provide reason as alias for description (React component uses reason)
            node['reason'] = node.get('description', ctx.task_description)
            # Include tags for tree rendering
            node['tags'] = ctx.tags if hasattr(ctx, 'tags') and ctx.tags else []
        if 'children' in node and node['children']:
            node['children'] = [augment_tree_node(child) for child in node['children']]
        return node

    def get_sort_key(node):
        """Get sort key for a root node based on its context."""
        ctx = orchestrator._contexts.get(node.get('id'))
        if not ctx:
            return None
        sort_key_map = {
            "last_activity": ctx.last_activity or ctx.created_at,
            "created_at": ctx.created_at,
            "task_description": (ctx.task_description or "").lower(),
            "exchange_count": len(ctx.local_memory),
        }
        return sort_key_map.get(sort_by, sort_key_map["last_activity"])

    try:
        tree = orchestrator.get_tree(root_id=root_id)
        if tree and 'roots' in tree:
            # Sort roots before augmenting
            reverse = sort_order.lower() != "asc"
            tree['roots'] = sorted(tree['roots'], key=get_sort_key, reverse=reverse)
            tree['roots'] = [augment_tree_node(root) for root in tree['roots']]
        elif tree:
            tree = augment_tree_node(tree)
        return {"tree": tree}
    except Exception as e:
        track_error(f"Get tree failed: {str(e)}", "get_tree", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "tree": None}


@app.get("/sidebars/active")
async def get_active_sidebar():
    """
    Get the currently focused/active context.

    This is where new messages will be routed.
    """
    try:
        active_id = orchestrator.get_active_context_id()
        if not active_id:
            return {"active": None, "message": "No active context"}

        ctx = orchestrator.get_context(active_id)
        if not ctx:
            return {"active": None, "message": "Active context not found"}

        return {
            "active": {
                "id": ctx.sidebar_id,
                "parent_id": ctx.parent_context_id,
                "status": ctx.status.name.lower(),
                "reason": ctx.task_description,
                "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
                "exchange_count": len(ctx.local_memory),
                "inherited_count": len(ctx.inherited_memory)
            }
        }
    except Exception as e:
        track_error(f"Get active failed: {str(e)}", "get_active", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "active": None}


@app.get("/sidebars/archived")
async def list_archived_sidebars(
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    actor: str = "human"
):
    """
    List archived contexts for browsing/restore.

    Query params:
    - search: Filter by task_description or actor's alias
    - limit: Max results (default 50)
    - offset: Pagination offset
    - actor: Who is viewing (for alias resolution, default "human")
    """
    try:
        # Get archived contexts
        contexts = orchestrator.list_contexts(include_archived=True)
        from datashapes import SidebarStatus
        archived = [ctx for ctx in contexts if ctx.status == SidebarStatus.ARCHIVED]

        # Apply search filter (searches task_description and actor's alias)
        if search:
            search_lower = search.lower()
            archived = [
                ctx for ctx in archived
                if (ctx.task_description and search_lower in ctx.task_description.lower())
                or (resolve_display_name(ctx, actor) and search_lower in resolve_display_name(ctx, actor).lower())
            ]

        total = len(archived)

        # Sort by last_activity (most recent first)
        archived.sort(key=lambda c: c.last_activity or c.created_at, reverse=True)

        # Paginate
        paginated = archived[offset:offset + limit]

        return {
            "contexts": [
                {
                    "id": ctx.sidebar_id,
                    "reason": ctx.task_description,
                    "display_name": resolve_display_name(ctx, actor),
                    "archived_at": ctx.last_activity.isoformat() if ctx.last_activity else None,
                    "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
                    "exchange_count": len(ctx.local_memory),
                    "tags": ctx.tags if hasattr(ctx, 'tags') else []
                }
                for ctx in paginated
            ],
            "count": len(paginated),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    except Exception as e:
        track_error(f"List archived failed: {str(e)}", "list_archived", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "contexts": []}


@app.get("/sidebars/{sidebar_id}")
async def get_sidebar_details(sidebar_id: str):
    """Get detailed information about a specific context."""
    try:
        ctx = orchestrator.get_context(sidebar_id)
        if not ctx:
            return {"error": f"Context {sidebar_id} not found", "context": None}

        return {
            "context": {
                "id": ctx.sidebar_id,
                "parent_id": ctx.parent_context_id,
                "status": ctx.status.name.lower(),
                "reason": ctx.task_description,
                "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
                "created_by": ctx.participants[0] if ctx.participants else "unknown",
                "priority": ctx.priority.name.lower() if ctx.priority else None,
                "exchange_count": len(ctx.local_memory),
                "inherited_count": len(ctx.inherited_memory),
                "local_memory": ctx.local_memory,  # Full conversation for this sidebar
                "scratchpad": getattr(ctx, 'scratchpad', None).__dict__ if getattr(ctx, 'scratchpad', None) else None
            }
        }
    except Exception as e:
        track_error(f"Get sidebar details failed: {str(e)}", f"get_sidebar:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "context": None}


@app.post("/sidebars/spawn")
async def spawn_sidebar(request: SpawnSidebarRequest):
    """
    Spawn a new sidebar from a parent context.

    This is the "Fork" action - creates a branch to explore a tangent.
    The new sidebar inherits context from the parent at the branch point.
    """
    try:
        new_id = orchestrator.spawn_sidebar(
            parent_id=request.parent_id,
            reason=request.reason,
            inherit_last_n=request.inherit_last_n
        )

        # Get the newly created context for full details
        ctx = orchestrator.get_context(new_id)

        # Broadcast to React clients
        await broadcast_to_react({
            "type": "sidebar_spawned",
            "sidebar": {
                "id": new_id,
                "parent_id": request.parent_id,
                "reason": request.reason,
                "status": "active"
            }
        })

        return SidebarResponse(
            id=new_id,
            status="active",
            parent_id=request.parent_id,
            reason=request.reason,
            created_at=ctx.created_at.isoformat() if ctx and ctx.created_at else None,
            message=f"Sidebar spawned: {request.reason}"
        )
    except Exception as e:
        track_error(f"Spawn sidebar failed: {str(e)}", f"spawn:{request.reason}", "orchestrator", "critical", original_exception=e)
        return {"error": str(e), "id": None}


@app.post("/sidebars/{sidebar_id}/focus")
async def focus_sidebar(sidebar_id: str):
    """
    Switch focus to a specific context.

    After this, new messages will be routed to this context.
    """
    try:
        success = orchestrator.switch_focus(sidebar_id)
        if not success:
            return {"error": f"Could not switch to {sidebar_id}", "success": False}

        ctx = orchestrator.get_context(sidebar_id)

        # Swap chat's conversation_history to match the new context
        if ctx:
            chat.conversation_history = [
                {"user": ex["content"], "assistant": ctx.local_memory[i+1]["content"]}
                for i, ex in enumerate(ctx.local_memory)
                if ex.get("role") == "user" and i+1 < len(ctx.local_memory) and ctx.local_memory[i+1].get("role") == "assistant"
            ]

        # Broadcast focus change
        await broadcast_to_react({
            "type": "focus_changed",
            "active_id": sidebar_id,
            "reason": ctx.task_description if ctx else None
        })

        return {
            "success": True,
            "active_id": sidebar_id,
            "message": f"Now focused on: {ctx.task_description if ctx else sidebar_id}"
        }
    except Exception as e:
        track_error(f"Focus switch failed: {str(e)}", f"focus:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/pause")
async def pause_sidebar(sidebar_id: str, reason: str = ""):
    """
    Pause a context (step away without abandoning).

    Useful when you need to check something in another context
    but want to come back to this one.
    """
    try:
        success = orchestrator.pause_context(sidebar_id, reason=reason)
        if not success:
            return {"error": f"Could not pause {sidebar_id}", "success": False}

        await broadcast_to_react({
            "type": "sidebar_paused",
            "sidebar_id": sidebar_id,
            "reason": reason
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "status": "paused",
            "message": f"Context paused{': ' + reason if reason else ''}"
        }
    except Exception as e:
        track_error(f"Pause failed: {str(e)}", f"pause:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/resume")
async def resume_sidebar(sidebar_id: str):
    """Resume a paused context."""
    try:
        success = orchestrator.resume_context(sidebar_id)
        if not success:
            return {"error": f"Could not resume {sidebar_id}", "success": False}

        await broadcast_to_react({
            "type": "sidebar_resumed",
            "sidebar_id": sidebar_id
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "status": "active",
            "message": "Context resumed"
        }
    except Exception as e:
        track_error(f"Resume failed: {str(e)}", f"resume:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/merge")
async def merge_sidebar(sidebar_id: str, request: MergeSidebarRequest):
    """
    Merge sidebar findings back into parent.

    This consolidates what was learned in the sidebar and injects
    a summary into the parent context. The sidebar is then marked as merged.
    """
    try:
        result = orchestrator.merge_sidebar(
            sidebar_id=sidebar_id,
            summary=request.summary,
            auto_summarize=request.auto_summarize
        )

        if result.get("error"):
            return {"error": result["error"], "success": False}

        await broadcast_to_react({
            "type": "sidebar_merged",
            "sidebar_id": sidebar_id,
            "parent_id": result.get("parent_id"),
            "summary": result.get("summary_used")
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "parent_id": result.get("parent_id"),
            "summary": result.get("summary_used"),
            "message": "Sidebar merged into parent"
        }
    except Exception as e:
        track_error(f"Merge failed: {str(e)}", f"merge:{sidebar_id}", "orchestrator", "critical", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/archive")
async def archive_sidebar(sidebar_id: str, reason: str = "manual"):
    """
    Archive a context (soft delete).

    Archived contexts are hidden by default but not deleted.
    Useful for cleanup without losing history.
    """
    try:
        success = orchestrator.archive_context(sidebar_id, reason=reason)
        if not success:
            return {"error": f"Could not archive {sidebar_id}", "success": False}

        await broadcast_to_react({
            "type": "sidebar_archived",
            "sidebar_id": sidebar_id,
            "reason": reason
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "status": "archived",
            "message": f"Context archived: {reason}"
        }
    except Exception as e:
        track_error(f"Archive failed: {str(e)}", f"archive:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


class BulkArchiveRequest(BaseModel):
    """Request to bulk archive contexts matching criteria"""
    # Filter criteria (all optional, combined with AND)
    reason_contains: str | None = None  # Search term for name/description matching
    search_mode: str = "alias_preferred"  # How to search: alias_preferred, alias_only, description_only, both, both_required
    exchange_count_max: int | None = None  # Archive if exchange_count <= this (e.g., 0 for empty)
    status: str | None = None  # Archive only contexts with this status
    created_before: str | None = None  # ISO date string - archive if created before this
    # Safety
    dry_run: bool = True  # If True, just return what WOULD be archived
    archive_reason: str = "bulk_cleanup"  # Reason to log for archived contexts


@app.post("/sidebars/archive-bulk")
async def bulk_archive_sidebars(request: BulkArchiveRequest):
    """
    Bulk archive contexts matching criteria.

    Useful for cleaning up test data without manually archiving one by one.
    Use dry_run=True first to see what would be affected.
    """
    try:
        from datashapes import SidebarStatus

        # Get all non-archived contexts
        all_contexts = orchestrator.list_contexts(include_archived=False)

        # Apply filters
        matching = []
        for ctx in all_contexts:
            # Filter by name/description based on search_mode
            if request.reason_contains:
                search_lower = request.reason_contains.lower()
                desc = (ctx.task_description or "").lower()
                alias = resolve_display_name(ctx, "human") or ""
                alias_lower = alias.lower()
                has_alias = bool(alias)

                match = False
                mode = request.search_mode.lower()

                if mode == "alias_only":
                    # Only search aliases
                    match = search_lower in alias_lower
                elif mode == "description_only":
                    # Only search task_description
                    match = search_lower in desc
                elif mode == "both":
                    # OR logic: match if in either
                    match = search_lower in desc or search_lower in alias_lower
                elif mode == "both_required":
                    # AND logic: both must match (if both exist)
                    if has_alias:
                        match = search_lower in desc and search_lower in alias_lower
                    else:
                        # Only description exists, check that
                        match = search_lower in desc
                else:  # alias_preferred (default)
                    # If alias exists, search alias only; otherwise search description
                    if has_alias:
                        match = search_lower in alias_lower
                    else:
                        match = search_lower in desc

                if not match:
                    continue

            # Filter by exchange count
            if request.exchange_count_max is not None:
                if len(ctx.local_memory) > request.exchange_count_max:
                    continue

            # Filter by status
            if request.status:
                if ctx.status.name.lower() != request.status.lower():
                    continue

            # Filter by created date
            if request.created_before:
                from datetime import datetime
                try:
                    cutoff = datetime.fromisoformat(request.created_before.replace('Z', '+00:00'))
                    if ctx.created_at and ctx.created_at > cutoff:
                        continue
                except ValueError:
                    pass  # Skip date filter if invalid

            matching.append(ctx)

        if request.dry_run:
            return {
                "dry_run": True,
                "would_archive": len(matching),
                "matching_ids": [ctx.sidebar_id for ctx in matching[:100]],  # Limit preview
                "truncated": len(matching) > 100,
                "message": f"Would archive {len(matching)} contexts. Set dry_run=false to execute."
            }

        # Generate batch_id for tracking
        from datashapes import generate_id, OzolithEventType, OzolithPayloadBatchOperation, payload_to_dict
        from datetime import datetime
        batch_id = generate_id("BATCH")

        # Capture pre-operation states for undo capability
        pre_operation_states = {ctx.sidebar_id: ctx.status.name.lower() for ctx in matching}
        affected_ids = [ctx.sidebar_id for ctx in matching]

        # Build criteria dict for audit
        criteria_used = {
            "reason_contains": request.reason_contains,
            "search_mode": request.search_mode,
            "exchange_count_max": request.exchange_count_max,
            "status": request.status,
            "created_before": request.created_before
        }

        # Actually archive
        archived_count = 0
        failed_ids = []
        for ctx in matching:
            try:
                success = orchestrator.archive_context(ctx.sidebar_id, reason=request.archive_reason)
                if success:
                    archived_count += 1
                else:
                    failed_ids.append(ctx.sidebar_id)
            except Exception as e:
                failed_ids.append(ctx.sidebar_id)

        # Log batch operation to Ozolith
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadBatchOperation(
                batch_id=batch_id,
                operation_type="bulk_archive",
                affected_count=archived_count,
                criteria=criteria_used,
                affected_ids_sample=affected_ids[:50],  # Sample, not all
                executed_by="human",  # Could be parameterized later
                reason=request.archive_reason,
                status="completed" if not failed_ids else "partial",
                pre_operation_states_sample={k: v for k, v in list(pre_operation_states.items())[:50]}
            )
            oz.append(
                event_type=OzolithEventType.BATCH_OPERATION,
                context_id=batch_id,  # Use batch_id as context
                actor="human",
                payload=payload_to_dict(payload)
            )

        await broadcast_to_react({
            "type": "bulk_archive_complete",
            "batch_id": batch_id,
            "archived_count": archived_count,
            "failed_count": len(failed_ids)
        })

        return {
            "success": True,
            "batch_id": batch_id,
            "archived_count": archived_count,
            "failed_count": len(failed_ids),
            "failed_ids": failed_ids[:20] if failed_ids else [],
            "pre_operation_states": pre_operation_states,  # For undo
            "message": f"Archived {archived_count} contexts (batch: {batch_id})"
        }
    except Exception as e:
        track_error(f"Bulk archive failed: {str(e)}", "bulk_archive", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


# =============================================================================
# BATCH OPERATIONS - View and undo bulk operations
# =============================================================================

@app.get("/batches")
async def list_batches(
    limit: int = 20,
    offset: int = 0,
    operation_type: str | None = None
):
    """
    List batch operations with pagination.

    Query params:
    - limit: Max results (default 20, max 100)
    - offset: Skip this many results
    - operation_type: Filter by type ("bulk_archive", "bulk_restore")
    """
    try:
        oz = _get_ozolith()
        if not oz:
            return {"batches": [], "count": 0, "total": 0, "message": "Ozolith not available"}

        # Query batch operations from Ozolith
        from datashapes import OzolithEventType
        entries = (oz.query()
            .by_type(OzolithEventType.BATCH_OPERATION)
            .execute())

        # Filter by operation_type if specified
        if operation_type:
            entries = [e for e in entries if (e.payload if hasattr(e, 'payload') else {}).get("operation_type") == operation_type]

        total = len(entries)

        # Apply pagination
        paginated = entries[offset:offset + limit]

        # Format for response
        batches = []
        for entry in paginated:
            payload = entry.payload if hasattr(entry, 'payload') else {}
            batches.append({
                "batch_id": payload.get("batch_id"),
                "operation_type": payload.get("operation_type"),
                "affected_count": payload.get("affected_count", 0),
                "status": payload.get("status", "unknown"),
                "executed_by": payload.get("executed_by", "unknown"),
                "reason": payload.get("reason", ""),
                "timestamp": entry.timestamp if hasattr(entry, 'timestamp') else None,
                "criteria": payload.get("criteria", {}),
                "affected_ids_sample": payload.get("affected_ids_sample", [])[:10]
            })

        return {
            "batches": batches,
            "count": len(batches),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    except Exception as e:
        track_error(f"List batches failed: {str(e)}", "list_batches", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "batches": []}


@app.get("/batches/{batch_id}")
async def get_batch(batch_id: str):
    """
    Get full details of a specific batch operation.
    """
    try:
        oz = _get_ozolith()
        if not oz:
            return {"error": "Ozolith not available", "batch": None}

        # Find the batch operation
        from datashapes import OzolithEventType
        all_batches = (oz.query()
            .by_type(OzolithEventType.BATCH_OPERATION)
            .execute())
        entries = [e for e in all_batches
                   if (e.payload if hasattr(e, 'payload') else {}).get("batch_id") == batch_id]

        if not entries:
            return {"error": f"Batch {batch_id} not found", "batch": None}

        entry = entries[0]
        payload = entry.payload if hasattr(entry, 'payload') else {}

        return {
            "success": True,
            "batch": {
                "batch_id": payload.get("batch_id"),
                "operation_type": payload.get("operation_type"),
                "affected_count": payload.get("affected_count", 0),
                "status": payload.get("status"),
                "executed_by": payload.get("executed_by"),
                "reason": payload.get("reason"),
                "timestamp": entry.timestamp if hasattr(entry, 'timestamp') else None,
                "criteria": payload.get("criteria", {}),
                "affected_ids_sample": payload.get("affected_ids_sample", []),
                "pre_operation_states_sample": payload.get("pre_operation_states_sample", {})
            }
        }
    except Exception as e:
        track_error(f"Get batch failed: {str(e)}", f"batch:{batch_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "batch": None}


class RestoreRequest(BaseModel):
    """Request to restore an archived context"""
    restore_to_status: str = "paused"  # What status to restore to
    reason: str = ""                    # Why restoring


@app.post("/sidebars/{sidebar_id}/restore")
async def restore_sidebar(sidebar_id: str, request: RestoreRequest):
    """
    Restore an archived context.

    Sets status from ARCHIVED back to the specified status (default: paused).
    """
    try:
        from datashapes import SidebarStatus, OzolithEventType, OzolithPayloadBatchOperation, payload_to_dict, generate_id

        context = orchestrator._contexts.get(sidebar_id)
        if context is None:
            return {"error": f"Context {sidebar_id} not found", "success": False}

        if context.status != SidebarStatus.ARCHIVED:
            return {"error": f"Context {sidebar_id} is not archived (status: {context.status.name})", "success": False}

        # Map status string to enum
        try:
            new_status = SidebarStatus[request.restore_to_status.upper()]
        except KeyError:
            return {"error": f"Invalid status: {request.restore_to_status}", "success": False}

        old_status = context.status.name.lower()

        # Restore
        context.status = new_status
        context.last_activity = datetime.now()
        orchestrator._persist_context(context)

        # Log as single-item batch for consistency
        batch_id = generate_id("BATCH")
        oz = _get_ozolith()
        if oz:
            payload = OzolithPayloadBatchOperation(
                batch_id=batch_id,
                operation_type="single_restore",
                affected_count=1,
                affected_ids_sample=[sidebar_id],
                executed_by="human",
                reason=request.reason,
                status="completed",
                pre_operation_states_sample={sidebar_id: old_status}
            )
            oz.append(
                event_type=OzolithEventType.BATCH_OPERATION,
                context_id=sidebar_id,
                actor="human",
                payload=payload_to_dict(payload)
            )

        await broadcast_to_react({
            "type": "sidebar_restored",
            "sidebar_id": sidebar_id,
            "new_status": new_status.name.lower()
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "old_status": old_status,
            "new_status": new_status.name.lower(),
            "message": f"Restored {sidebar_id} to {new_status.name.lower()}"
        }
    except Exception as e:
        track_error(f"Restore failed: {str(e)}", f"restore:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


class BatchRestoreRequest(BaseModel):
    """Request to restore an entire batch"""
    dry_run: bool = True
    restore_to_original: bool = True  # Restore to pre-archive status if available
    fallback_status: str = "paused"   # If original not available
    reason: str = ""


@app.post("/batches/{batch_id}/restore")
async def restore_batch(batch_id: str, request: BatchRestoreRequest):
    """
    Restore all contexts from a batch operation.

    Use dry_run=true first to preview what would be restored.
    If restore_to_original=true, uses pre_operation_states from the batch.
    """
    try:
        from datashapes import SidebarStatus, OzolithEventType, OzolithPayloadBatchOperation, payload_to_dict, generate_id
        from datetime import datetime

        # Find the original batch
        oz = _get_ozolith()
        if not oz:
            return {"error": "Ozolith not available", "success": False}

        entries = oz.query().by_type(OzolithEventType.BATCH_OPERATION).by_context(batch_id).execute()

        if not entries:
            return {"error": f"Batch {batch_id} not found", "success": False}

        original_batch = entries[0].payload if hasattr(entries[0], 'payload') else {}

        if original_batch.get("operation_type") != "bulk_archive":
            return {"error": f"Batch {batch_id} is not a bulk_archive operation", "success": False}

        # Get affected IDs and their pre-archive states
        affected_ids = original_batch.get("affected_ids_sample", [])
        pre_states = original_batch.get("pre_operation_states_sample", {})

        # Find which ones are still archived
        restorable = []
        for sid in affected_ids:
            ctx = orchestrator._contexts.get(sid)
            if ctx and ctx.status == SidebarStatus.ARCHIVED:
                target_status = pre_states.get(sid, request.fallback_status) if request.restore_to_original else request.fallback_status
                restorable.append({"id": sid, "target_status": target_status})

        if request.dry_run:
            return {
                "dry_run": True,
                "would_restore": len(restorable),
                "restorable": restorable[:50],
                "original_batch_affected": original_batch.get("affected_count", 0),
                "message": f"Would restore {len(restorable)} contexts. Set dry_run=false to execute."
            }

        # Execute restore
        restore_batch_id = generate_id("BATCH")
        restored_count = 0
        failed_ids = []
        pre_operation_states = {}

        for item in restorable:
            try:
                ctx = orchestrator._contexts.get(item["id"])
                if ctx:
                    pre_operation_states[item["id"]] = ctx.status.name.lower()
                    try:
                        new_status = SidebarStatus[item["target_status"].upper()]
                    except KeyError:
                        new_status = SidebarStatus.PAUSED

                    ctx.status = new_status
                    ctx.last_activity = datetime.now()
                    orchestrator._persist_context(ctx)
                    restored_count += 1
            except Exception:
                failed_ids.append(item["id"])

        # Log the restore batch
        if oz:
            payload = OzolithPayloadBatchOperation(
                batch_id=restore_batch_id,
                operation_type="bulk_restore",
                affected_count=restored_count,
                criteria={"original_batch_id": batch_id},
                affected_ids_sample=[item["id"] for item in restorable[:50]],
                executed_by="human",
                reason=request.reason or f"Restoring batch {batch_id}",
                status="completed" if not failed_ids else "partial",
                pre_operation_states_sample={k: v for k, v in list(pre_operation_states.items())[:50]}
            )
            oz.append(
                event_type=OzolithEventType.BATCH_OPERATION,
                context_id=restore_batch_id,
                actor="human",
                payload=payload_to_dict(payload)
            )

        await broadcast_to_react({
            "type": "batch_restore_complete",
            "batch_id": restore_batch_id,
            "original_batch_id": batch_id,
            "restored_count": restored_count
        })

        return {
            "success": True,
            "batch_id": restore_batch_id,
            "original_batch_id": batch_id,
            "restored_count": restored_count,
            "failed_count": len(failed_ids),
            "failed_ids": failed_ids[:20] if failed_ids else [],
            "message": f"Restored {restored_count} contexts (batch: {restore_batch_id})"
        }
    except Exception as e:
        track_error(f"Batch restore failed: {str(e)}", f"batch_restore:{batch_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


# =============================================================================
# ALIAS AND TAGS ENDPOINTS
# Display name management and categorization
# =============================================================================

def resolve_display_name(ctx, actor: str = "human") -> str | None:
    """
    Resolve display name for a given actor from the per-actor alias cache.
    Returns the actor's alias, or None if no alias set for that actor.
    """
    if hasattr(ctx, 'display_names') and isinstance(ctx.display_names, dict):
        return ctx.display_names.get(actor)
    return None


class AliasRequest(BaseModel):
    """Request to add/update a context alias (display name)"""
    alias: str                    # The display name
    confidence: float = 1.0       # How strongly this name fits (0.0-1.0)
    reason: str = ""              # Why this name (learning signal)
    cited_by: str = "human"       # Who assigned this alias


class TagsUpdateRequest(BaseModel):
    """Request to update context tags"""
    tags: list[str]               # New complete tag list (replaces existing)
    reason: str = ""              # Why this categorization
    confidence: float = 1.0       # How confident in this categorization
    updated_by: str = "human"     # Who made the change


@app.post("/sidebars/{sidebar_id}/alias")
async def set_sidebar_alias(sidebar_id: str, request: AliasRequest):
    """
    Set a display name alias for a context.

    Creates a CONTEXT_ALIAS citation logged to Ozolith.
    Each actor maintains their own alias independently (parallel symlink model).
    Same actor updating = supersession (new citation references old via extra.supersedes).
    Different actor = independent parallel alias, no conflict.
    """
    try:
        from datashapes import CitationType, create_citation, OzolithEventType, OzolithPayloadCitation, payload_to_dict

        context = orchestrator._contexts.get(sidebar_id)
        if context is None:
            return {"error": f"Context {sidebar_id} not found", "success": False}

        # Check if this actor already has an alias for this context (for supersession)
        superseded_citation_id = None
        oz = _get_ozolith()
        if oz:
            from datashapes import OzolithEventType
            entries = (oz.query()
                .by_type(OzolithEventType.CITATION_CREATED)
                .by_context(sidebar_id)
                .by_actor(request.cited_by)
                .execute())
            # Find the most recent non-superseded alias by this actor
            for entry in reversed(entries):
                payload = entry.payload if hasattr(entry, 'payload') else {}
                if payload.get("citation_type") == "context_alias":
                    superseded_citation_id = payload.get("citation_id")
                    break

        # Create the citation with supersession tracking if applicable
        extra = {}
        if superseded_citation_id:
            extra["supersedes"] = superseded_citation_id

        citation = create_citation(
            citation_type=CitationType.CONTEXT_ALIAS,
            target_id=sidebar_id,
            target_type="sidebar",
            cited_by=request.cited_by,
            relevance_note=request.alias,  # The alias text lives here
            confidence_at_citation=request.confidence,
            cited_from_context=sidebar_id,
            extra=extra
        )

        # Update per-actor alias cache
        if not hasattr(context, 'display_names') or not isinstance(context.display_names, dict):
            context.display_names = {}
        context.display_names[request.cited_by] = request.alias
        orchestrator._persist_context(context)

        # Log to Ozolith
        if oz:
            payload_data = OzolithPayloadCitation(
                citation_id=citation.citation_id,
                citation_type=CitationType.CONTEXT_ALIAS.value,
                target_id=sidebar_id,
                target_type="sidebar",
                cited_from_context=sidebar_id,
                relevance_note=request.alias,
                confidence_at_citation=request.confidence
            )
            oz_payload = payload_to_dict(payload_data)
            if superseded_citation_id:
                oz_payload["supersedes"] = superseded_citation_id
            oz.append(
                event_type=OzolithEventType.CITATION_CREATED,
                context_id=sidebar_id,
                actor=request.cited_by,
                payload=oz_payload
            )

        await broadcast_to_react({
            "type": "sidebar_alias_updated",
            "sidebar_id": sidebar_id,
            "alias": request.alias,
            "cited_by": request.cited_by,
            "supersedes": superseded_citation_id
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "alias": request.alias,
            "cited_by": request.cited_by,
            "citation_id": citation.citation_id,
            "supersedes": superseded_citation_id,
            "message": f"Alias set for {request.cited_by}: {request.alias}"
        }
    except Exception as e:
        track_error(f"Set alias failed: {str(e)}", f"alias:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/tags")
async def update_sidebar_tags(sidebar_id: str, request: TagsUpdateRequest):
    """
    Update tags for a context (categorization).

    Logs TAGS_UPDATED event to Ozolith with full provenance.
    Tags are simple labels for filtering/organization.
    """
    try:
        from datashapes import OzolithEventType, OzolithPayloadTagsUpdated, payload_to_dict

        context = orchestrator._contexts.get(sidebar_id)
        if context is None:
            return {"error": f"Context {sidebar_id} not found", "success": False}

        old_tags = list(context.tags) if hasattr(context, 'tags') else []
        new_tags = list(request.tags)

        # Compute what changed
        tags_added = [t for t in new_tags if t not in old_tags]
        tags_removed = [t for t in old_tags if t not in new_tags]

        # Determine action
        if tags_added and tags_removed:
            action = "replace"
        elif tags_added:
            action = "add"
        elif tags_removed:
            action = "remove"
        else:
            action = "no_change"

        # Update the context
        context.tags = new_tags
        orchestrator._persist_context(context)

        # Log to Ozolith
        oz = _get_ozolith()
        if oz and action != "no_change":
            payload = OzolithPayloadTagsUpdated(
                context_id=sidebar_id,
                action=action,
                tags_added=tags_added,
                tags_removed=tags_removed,
                old_tags=old_tags,
                new_tags=new_tags,
                updated_by=request.updated_by,
                reason=request.reason,
                confidence=request.confidence
            )
            oz.append(
                event_type=OzolithEventType.TAGS_UPDATED,
                context_id=sidebar_id,
                actor=request.updated_by,
                payload=payload_to_dict(payload)
            )

        await broadcast_to_react({
            "type": "sidebar_tags_updated",
            "sidebar_id": sidebar_id,
            "tags": new_tags,
            "updated_by": request.updated_by
        })

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "tags": new_tags,
            "action": action,
            "tags_added": tags_added,
            "tags_removed": tags_removed,
            "message": f"Tags updated: {action}"
        }
    except Exception as e:
        track_error(f"Update tags failed: {str(e)}", f"tags:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.get("/sidebars/{sidebar_id}/aliases")
async def get_sidebar_aliases(sidebar_id: str):
    """
    Get all aliases for a context, grouped by actor.

    Returns per-actor alias history with supersession chains.
    Each actor's "current" alias is the most recent non-superseded one.
    """
    try:
        from datashapes import OzolithEventType
        oz = _get_ozolith()
        # Raw list of all alias citations for this context
        raw_aliases = []

        if oz:
            entries = (oz.query()
                .by_type(OzolithEventType.CITATION_CREATED)
                .by_context(sidebar_id)
                .execute())

            for entry in entries:
                payload = entry.payload if hasattr(entry, 'payload') else {}
                if payload.get("citation_type") == "context_alias":
                    raw_aliases.append({
                        "alias": payload.get("relevance_note", ""),
                        "cited_by": entry.actor if hasattr(entry, 'actor') else "unknown",
                        "confidence": payload.get("confidence_at_citation", 0.0),
                        "citation_id": payload.get("citation_id", ""),
                        "supersedes": payload.get("supersedes"),
                        "created_at": entry.timestamp if hasattr(entry, 'timestamp') else ""
                    })

        # Group by actor with history and current resolution
        by_actor = {}
        superseded_ids = {a["supersedes"] for a in raw_aliases if a.get("supersedes")}

        for alias_entry in raw_aliases:
            actor = alias_entry["cited_by"]
            if actor not in by_actor:
                by_actor[actor] = {"current": None, "history": []}
            by_actor[actor]["history"].append({
                "alias": alias_entry["alias"],
                "citation_id": alias_entry["citation_id"],
                "confidence": alias_entry["confidence"],
                "supersedes": alias_entry.get("supersedes"),
                "created_at": alias_entry["created_at"],
                "is_current": alias_entry["citation_id"] not in superseded_ids
            })

        # Set current for each actor (most recent non-superseded)
        for actor, data in by_actor.items():
            current_entries = [h for h in data["history"] if h["is_current"]]
            if current_entries:
                # Most recent non-superseded entry
                data["current"] = current_entries[-1]["alias"]

        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "by_actor": by_actor,
            "actors": list(by_actor.keys()),
            "total_aliases": len(raw_aliases)
        }
    except Exception as e:
        track_error(f"Get aliases failed: {str(e)}", f"aliases:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False, "by_actor": {}}


@app.get("/sidebars/{sidebar_id}/alias")
async def get_sidebar_alias_for_actor(sidebar_id: str, actor: str = "human"):
    """
    Get a specific actor's current alias for a context.

    Fast path for UI rendering - returns just the actor's current alias
    without downloading full alias history.

    Query params:
    - actor: Whose alias to retrieve (default "human")
    """
    try:
        context = orchestrator._contexts.get(sidebar_id)
        if context is None:
            return {"error": f"Context {sidebar_id} not found", "success": False}

        alias = resolve_display_name(context, actor)
        return {
            "success": True,
            "sidebar_id": sidebar_id,
            "actor": actor,
            "alias": alias,
            "has_alias": alias is not None
        }
    except Exception as e:
        track_error(f"Get alias failed: {str(e)}", f"alias:{sidebar_id}:{actor}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


# =============================================================================
# REPARENTING AND CROSS-REFERENCE ENDPOINTS (Phase 4)
# These enable context reorganization and relationship tracking
# =============================================================================

class ReparentRequest(BaseModel):
    """Request to reparent a context"""
    new_parent_id: str | None = None  # None = become root
    reason: str
    confidence: float = 0.0  # Model's confidence when suggesting
    suggested_by_model: bool = False  # Did a model suggest this?
    pattern_detected: str = ""  # What pattern triggered suggestion


class CrossRefRequest(BaseModel):
    """Request to add a cross-reference between contexts"""
    target_context_id: str
    ref_type: str = "related_to"  # "cites", "related_to", "derived_from", "contradicts"
    reason: str = ""
    confidence: float = 0.0  # How confident in the connection
    discovery_method: str = "explicit"  # How found: "explicit_mention", "semantic_similarity", etc.
    strength: str = "normal"  # "weak", "normal", "strong", "definitive"
    bidirectional: bool = True  # Auto-create reverse reference
    validation_priority: str = "normal"  # "urgent" if actively citing, "normal" otherwise


@app.post("/sidebars/{sidebar_id}/reparent")
async def reparent_context(sidebar_id: str, request: ReparentRequest):
    """
    Change a context's parent in the tree.

    Use cases:
    - Unify multiple roots under umbrella context
    - Move sidebar to different parent
    - Promote sidebar to root (new_parent_id=None)

    The learning signals (confidence, suggested_by_model, pattern_detected)
    support future model autonomy - tracking suggestions for calibration.
    """
    try:
        result = orchestrator.reparent_context(
            context_id=sidebar_id,
            new_parent_id=request.new_parent_id,
            reason=request.reason,
            confidence=request.confidence,
            suggested_by_model=request.suggested_by_model,
            pattern_detected=request.pattern_detected
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        await broadcast_to_react({
            "type": "context_reparented",
            "context_id": sidebar_id,
            "old_parent_id": result.get("old_parent_id"),
            "new_parent_id": result.get("new_parent_id"),
            "children_moved": result.get("children_moved", []),
            "reason": request.reason
        })

        return {
            "success": True,
            "context_id": sidebar_id,
            "old_parent_id": result.get("old_parent_id"),
            "new_parent_id": result.get("new_parent_id"),
            "children_moved": result.get("children_moved", []),
            "message": f"Reparented: {request.reason}"
        }
    except Exception as e:
        track_error(f"Reparent failed: {str(e)}", f"reparent:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/cross-ref")
async def add_cross_reference(sidebar_id: str, request: CrossRefRequest):
    """
    Add a cross-reference from this context to another.

    Cross-references create the "stumble upon related work" capability.
    By default, bidirectional - so you can query from either side.

    Learning signals track how connections are discovered for future
    calibration of semantic similarity detection.
    """
    try:
        result = orchestrator.add_cross_ref(
            source_context_id=sidebar_id,
            target_context_id=request.target_context_id,
            ref_type=request.ref_type,
            reason=request.reason,
            confidence=request.confidence,
            discovery_method=request.discovery_method,
            strength=request.strength,
            bidirectional=request.bidirectional,
            validation_priority=request.validation_priority
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        await broadcast_to_react({
            "type": "cross_ref_added",
            "source_context_id": sidebar_id,
            "target_context_id": request.target_context_id,
            "ref_type": request.ref_type,
            "bidirectional": request.bidirectional
        })

        return {
            "success": True,
            "source_context_id": sidebar_id,
            "target_context_id": request.target_context_id,
            "ref_type": request.ref_type,
            "bidirectional": request.bidirectional,
            "message": f"Cross-reference added: {request.ref_type}"
        }
    except Exception as e:
        track_error(f"Cross-ref failed: {str(e)}", f"cross-ref:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.get("/sidebars/{sidebar_id}/cross-refs")
async def get_cross_references(
    sidebar_id: str,
    ref_type: str | None = None,
    min_strength: str | None = None
):
    """
    Get cross-references for a context, with optional filtering.

    Query Parameters:
        ref_type: Filter by relationship type (cites, related_to, derived_from,
                  contradicts, supersedes, obsoletes, implements)
        min_strength: Minimum strength level (speculative, weak, normal, strong, definitive)
                      Returns refs at this level or higher.

    Returns context IDs that this context references (matching filters if provided).
    """
    try:
        refs = orchestrator.get_cross_refs(
            context_id=sidebar_id,
            ref_type=ref_type,
            min_strength=min_strength
        )
        return {
            "context_id": sidebar_id,
            "cross_refs": refs,
            "count": len(refs),
            "filters_applied": {
                "ref_type": ref_type,
                "min_strength": min_strength
            }
        }
    except Exception as e:
        track_error(f"Get cross-refs failed: {str(e)}", f"get-cross-refs:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "cross_refs": []}


class RevokeCrossRefRequest(BaseModel):
    """Request to revoke a cross-reference"""
    reason: str
    revoked_by: str = "human"  # "human" or "model"
    replacement_refs: list[str] | None = None  # Correct contexts if this was wrong
    corrected_understanding: str = ""  # Why the original was wrong


@app.post("/sidebars/{sidebar_id}/cross-refs/{target_id}/revoke")
async def revoke_cross_reference(sidebar_id: str, target_id: str, request: RevokeCrossRefRequest):
    """
    Revoke a cross-reference between contexts.

    This is an append-only pattern: the original CROSS_REF_ADDED event is preserved,
    and a new CROSS_REF_REVOKED event marks it as no longer valid.

    Use cases:
    - Model made a wrong connection, human corrects it
    - Relationship was valid but is now obsolete
    - Redirect to correct connections via replacement_refs
    """
    try:
        result = orchestrator.revoke_cross_ref(
            source_context_id=sidebar_id,
            target_context_id=target_id,
            reason=request.reason,
            revoked_by=request.revoked_by,
            replacement_refs=request.replacement_refs,
            corrected_understanding=request.corrected_understanding
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        await broadcast_to_react({
            "type": "cross_ref_revoked",
            "source_context_id": sidebar_id,
            "target_context_id": target_id,
            "reason": request.reason,
            "replacement_refs": request.replacement_refs or []
        })

        return {
            "success": True,
            "source_context_id": sidebar_id,
            "target_context_id": target_id,
            "reason": request.reason,
            "replacement_refs": request.replacement_refs or [],
            "message": f"Cross-reference revoked: {request.reason}"
        }
    except Exception as e:
        track_error(f"Revoke cross-ref failed: {str(e)}", f"revoke-cross-ref:{sidebar_id}->{target_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


class UpdateCrossRefRequest(BaseModel):
    """Request to update a cross-reference's metadata"""
    reason: str
    new_strength: str | None = None  # "speculative", "weak", "normal", "strong", "definitive"
    new_confidence: float | None = None  # 0.0-1.0
    new_ref_type: str | None = None  # "cites", "related_to", etc.
    new_validation_priority: str | None = None  # "normal", "urgent"
    updated_by: str = "human"  # "human" or "model"


@app.patch("/sidebars/{sidebar_id}/cross-refs/{target_id}")
async def update_cross_reference(sidebar_id: str, target_id: str, request: UpdateCrossRefRequest):
    """
    Update metadata on an existing cross-reference.

    Cleaner than revoke + re-add when you just need to change strength,
    confidence, ref_type, or validation_priority. Full audit trail via
    CROSS_REF_UPDATED event.
    """
    try:
        result = orchestrator.update_cross_ref(
            source_context_id=sidebar_id,
            target_context_id=target_id,
            reason=request.reason,
            new_strength=request.new_strength,
            new_confidence=request.new_confidence,
            new_ref_type=request.new_ref_type,
            new_validation_priority=request.new_validation_priority,
            updated_by=request.updated_by
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        await broadcast_to_react({
            "type": "cross_ref_updated",
            "source_context_id": sidebar_id,
            "target_context_id": target_id,
            "changes": result.get("changes")
        })

        return {
            "success": True,
            "source_context_id": sidebar_id,
            "target_context_id": target_id,
            "changes": result.get("changes"),
            "message": f"Cross-reference updated: {request.reason}"
        }
    except Exception as e:
        track_error(f"Update cross-ref failed: {str(e)}", f"update-cross-ref:{sidebar_id}->{target_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


class ValidateCrossRefRequest(BaseModel):
    """Request to validate a cross-reference (human feedback)"""
    state: str  # "true", "false", "not_sure"
    notes: str | None = None  # Optional feedback text
    chase_after: str | None = None  # ISO datetime for per-ref follow-up override


@app.post("/sidebars/{sidebar_id}/cross-refs/{target_id}/validate")
async def validate_cross_reference(sidebar_id: str, target_id: str, request: ValidateCrossRefRequest):
    """
    Validate a cross-reference (human confirms/rejects/unsure).

    Captures human feedback on model-detected connections for calibration.
    Snapshots model's confidence at validation time for learning.

    Body:
        state: "true" | "false" | "not_sure"
        notes: Optional feedback text
        chase_after: Optional ISO datetime for "check again Friday"
    """
    try:
        # Get current active context for validation_context_id
        active_context = orchestrator.get_active_context()
        validation_context_id = active_context.sidebar_id if active_context else None

        result = orchestrator.validate_cross_ref(
            source_context_id=sidebar_id,
            target_context_id=target_id,
            validation_state=request.state,
            validated_by="human",
            validation_notes=request.notes,
            chase_after=request.chase_after,
            validation_context_id=validation_context_id
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        await broadcast_to_react({
            "type": "cross_ref_validated",
            "source_context_id": sidebar_id,
            "target_context_id": target_id,
            "validation_state": request.state,
            "is_flip": result.get("is_flip", False)
        })

        return {
            "success": True,
            "source_context_id": sidebar_id,
            "target_context_id": target_id,
            "validation_state": request.state,
            "previous_state": result.get("previous_state"),
            "confidence_at_validation": result.get("confidence_at_validation"),
            "is_flip": result.get("is_flip", False),
            "message": f"Cross-reference validated: {request.state}"
        }
    except Exception as e:
        track_error(f"Validate cross-ref failed: {str(e)}", f"validate-cross-ref:{sidebar_id}->{target_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.get("/cross-refs/pending-validations")
async def get_pending_validations():
    """
    Get all cross-refs awaiting human validation.

    Returns refs where human_validated is None across all contexts.
    Useful for batch review: "show me everything I haven't looked at yet."

    Sorted by priority (urgent first), then by created_at.
    """
    try:
        pending = orchestrator.get_pending_validations()
        return {
            "pending_validations": pending,
            "count": len(pending),
            "urgent_count": sum(1 for p in pending if p.get("validation_priority") == "urgent")
        }
    except Exception as e:
        track_error(f"Get pending validations failed: {str(e)}", "pending-validations", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "pending_validations": [], "count": 0}


@app.get("/cross-refs/clustered")
async def get_clustered_refs(context_id: Optional[str] = None, include_validated: bool = False):
    """
    Get cross-refs that have been cluster-flagged (3+ sources suggested same ref).

    These are high-confidence validation candidates - multiple independent sources
    noticed the same connection, which is a strong signal it's real.

    Args:
        context_id: Limit to specific context, or omit for all contexts
        include_validated: Include refs already validated (default: False)

    Returns:
        Flagged refs sorted by source count (highest first)
    """
    try:
        result = orchestrator.get_cluster_flagged_refs(
            context_id=context_id,
            include_validated=include_validated
        )
        return result
    except Exception as e:
        track_error(f"Get clustered refs failed: {str(e)}", "clustered-refs", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "flagged_refs": [], "total_count": 0}


# =============================================================================
# YARN BOARD ENDPOINTS
# =============================================================================
# Yarn board is a VIEW layer over OZOLITH + Redis + cross-refs.
# These endpoints manage layout persistence and hot state.
# See SIDEBAR_PERSISTENCE_IMPLEMENTATION.md Section 9.

class YarnLayoutRequest(BaseModel):
    """Request to save yarn board layout"""
    point_positions: dict | None = None  # {point_id: {x, y, collapsed}}
    zoom_level: float | None = None
    focus_point: str | None = None
    show_archived: bool | None = None
    filter_by_priority: str | None = None
    filter_by_type: str | None = None


class PointPositionRequest(BaseModel):
    """Request to update a single point's position"""
    x: float
    y: float
    collapsed: bool = False


class GrabPointRequest(BaseModel):
    """Request to grab or release a point"""
    grabbed: bool
    agent_id: str = "operator"  # Who is grabbing (for collision detection)


@app.get("/sidebars/{sidebar_id}/yarn-board")
async def get_yarn_board_layout(sidebar_id: str):
    """
    Get the yarn board layout for a context.

    Returns visual layout (point positions, zoom, filters) for rendering.
    If no layout exists, returns sensible defaults.
    """
    try:
        result = orchestrator.get_yarn_layout(sidebar_id)
        if not result.get("success"):
            return {"error": result.get("error"), "success": False}
        return result
    except Exception as e:
        track_error(f"Get yarn layout failed: {str(e)}", f"yarn-board:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.put("/sidebars/{sidebar_id}/yarn-board")
async def save_yarn_board_layout(sidebar_id: str, request: YarnLayoutRequest):
    """
    Save or update the yarn board layout for a context.

    Only updates fields that are provided (not None).
    Persists so the board can "grow over time" between sessions.
    """
    try:
        result = orchestrator.save_yarn_layout(
            context_id=sidebar_id,
            point_positions=request.point_positions,
            zoom_level=request.zoom_level,
            focus_point=request.focus_point,
            show_archived=request.show_archived,
            filter_by_priority=request.filter_by_priority,
            filter_by_type=request.filter_by_type
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        # Broadcast to React
        await broadcast_to_react({
            "type": "yarn_board_layout_updated",
            "context_id": sidebar_id,
            "layout": result.get("layout")
        })

        return result
    except Exception as e:
        track_error(f"Save yarn layout failed: {str(e)}", f"yarn-board:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.patch("/sidebars/{sidebar_id}/yarn-board/points/{point_id}")
async def update_point_position(sidebar_id: str, point_id: str, request: PointPositionRequest):
    """
    Update a single point's position on the yarn board.

    Convenience endpoint for drag-and-drop without sending entire layout.
    """
    try:
        result = orchestrator.update_point_position(
            context_id=sidebar_id,
            point_id=point_id,
            x=request.x,
            y=request.y,
            collapsed=request.collapsed
        )

        if not result.get("success"):
            return {"error": result.get("error"), "success": False}

        # Broadcast to React (lightweight update)
        await broadcast_to_react({
            "type": "yarn_point_moved",
            "context_id": sidebar_id,
            "point_id": point_id,
            "position": result.get("position")
        })

        return result
    except Exception as e:
        track_error(f"Update point position failed: {str(e)}", f"yarn-point:{sidebar_id}:{point_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.get("/sidebars/{sidebar_id}/yarn-board/state")
async def get_yarn_board_state(sidebar_id: str):
    """
    Get the hot state for a yarn board (what's currently grabbed).

    NOTE: Returns default empty state until Redis is implemented.
    When Redis is online, returns cached grabbed points and priority overrides.
    """
    try:
        result = orchestrator.get_yarn_state(sidebar_id)
        return result
    except Exception as e:
        track_error(f"Get yarn state failed: {str(e)}", f"yarn-state:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


@app.post("/sidebars/{sidebar_id}/yarn-board/points/{point_id}/grab")
async def grab_yarn_point(sidebar_id: str, point_id: str, request: GrabPointRequest):
    """
    Mark a point as grabbed (focused) or released.

    Grabbed points are the "current focus" - what matters RIGHT NOW.
    If another agent has the point grabbed, spawns a coordination sidebar
    for both agents to sync up (collision = coordination signal).

    NOTE: Gracefully degrades until Redis is implemented.
    """
    try:
        result = orchestrator.set_grabbed(
            context_id=sidebar_id,
            point_id=point_id,
            grabbed=request.grabbed,
            agent_id=request.agent_id
        )

        # Broadcast grab event to React
        await broadcast_to_react({
            "type": "yarn_point_grabbed" if request.grabbed else "yarn_point_released",
            "context_id": sidebar_id,
            "point_id": point_id,
            "agent_id": request.agent_id,
            "persisted": result.get("persisted", False)
        })

        # If coordination sidebar was spawned, broadcast that too
        if result.get("coordination"):
            coord = result["coordination"]
            await broadcast_to_react({
                "type": "coordination_sidebar_spawned",
                "context_id": sidebar_id,
                "sidebar_id": coord.get("sidebar_id"),
                "agents": coord.get("agents", []),
                "point_id": point_id,
                "reason": coord.get("reason", "grab_collision")
            })

        return result
    except Exception as e:
        track_error(f"Grab point failed: {str(e)}", f"yarn-grab:{sidebar_id}:{point_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


class RenderYarnBoardRequest(BaseModel):
    """Options for yarn board rendering."""
    highlights: list[str] | None = None
    expanded: bool = False  # If True, include detail dicts with rich metadata


@app.post("/sidebars/{sidebar_id}/yarn-board/render")
async def render_yarn_board(sidebar_id: str, request: RenderYarnBoardRequest | None = None):
    """
    Render the yarn board as a minimal minimap structure.

    Returns points (dots), connections (strings), cushion (unstaged items),
    and highlights (model suggestions). This is a VIEW - all rich data lives
    in OZOLITH/SQLite/cross-refs.

    Point ID convention:
    - context:{sidebar_id} - e.g., context:SB-1
    - crossref:{sorted_a}:{sorted_b} - e.g., crossref:SB-1:SB-2
    - finding:{entry_id} - e.g., finding:ENTRY-001

    When expanded=True, each point and connection includes a 'detail' dict:
    - Context points: task_description, status, findings_count, questions_count
    - Crossref points: ref_type, strength, confidence, validation_state, reason
    - Connections: ref_type, strength, validation_state (same as crossref detail)
    """
    try:
        highlights = request.highlights if request else None
        expanded = request.expanded if request else False
        result = orchestrator.render_yarn_board(
            context_id=sidebar_id,
            highlights=highlights,
            expanded=expanded
        )
        return result
    except Exception as e:
        track_error(f"Render yarn board failed: {str(e)}", f"yarn-render:{sidebar_id}", "orchestrator", "warning", original_exception=e)
        return {"error": str(e), "success": False}


# Startup event
@app.get("/redis/health")
async def redis_health():
    """Check Redis connection health."""
    try:
        from redis_client import get_redis_client
        client = get_redis_client()
        return client.health_check()
    except ImportError:
        return {"connected": False, "status": "redis_client not available"}
    except Exception as e:
        return {"connected": False, "status": f"error: {e}"}


# =============================================================================
# QUEUE ROUTING ENDPOINTS (Phase 5 - Scratchpad routing through curator)
# =============================================================================

class QueueRouteRequest(BaseModel):
    """Request to route a scratchpad entry through validation pipeline."""
    entry: Dict  # ScratchpadEntry as dict
    context_id: str
    explicit_route_to: Optional[str] = None  # Override auto-routing


class QueueApprovalRequest(BaseModel):
    """Request for curator to approve/reject an entry."""
    entry_id: str
    context_id: str
    approved: bool
    rejection_reason: Optional[str] = None


@app.post("/queue/route")
async def route_scratchpad_entry(request: QueueRouteRequest):
    """
    Route a scratchpad entry through the validation/delivery pipeline.

    Flow:
    1. quick_note with no route → just store
    2. Everything else → queue for curator validation
    3. After validation → infer destination or use explicit_route_to
    4. Queue for destination agent
    """
    try:
        result = orchestrator.route_scratchpad_entry(
            entry=request.entry,
            context_id=request.context_id,
            explicit_route_to=request.explicit_route_to
        )
        return result
    except Exception as e:
        track_error(f"Queue routing failed: {str(e)}", "queue-route", "orchestrator", "warning", original_exception=e)
        return {"success": False, "error": str(e)}


@app.post("/queue/approve")
async def curator_approve_entry(request: QueueApprovalRequest):
    """
    Curator approves or rejects an entry, then routes to destination.

    Called by curator agent after validation review.
    """
    try:
        result = orchestrator.curator_approve_entry(
            entry_id=request.entry_id,
            context_id=request.context_id,
            approved=request.approved,
            rejection_reason=request.rejection_reason
        )
        return result
    except Exception as e:
        track_error(f"Curator approval failed: {str(e)}", "queue-approve", "orchestrator", "warning", original_exception=e)
        return {"success": False, "error": str(e)}


@app.get("/queue/{agent_id}")
async def get_agent_queue(agent_id: str, limit: int = 100):
    """
    Get queued messages for an agent (peek, doesn't remove).

    Args:
        agent_id: Agent to get queue for (e.g., "AGENT-curator", "AGENT-librarian")
        limit: Max messages to return (default 100)
    """
    try:
        from redis_client import get_redis_client
        client = get_redis_client()

        if not client.is_connected():
            return {"messages": [], "count": 0, "redis_available": False}

        messages = client.get_agent_queue(agent_id, limit)
        return {
            "agent_id": agent_id,
            "messages": messages,
            "count": len(messages),
            "redis_available": True
        }
    except ImportError:
        return {"messages": [], "count": 0, "redis_available": False, "error": "redis_client not available"}
    except Exception as e:
        return {"messages": [], "count": 0, "redis_available": False, "error": str(e)}


@app.get("/queue/{agent_id}/length")
async def get_agent_queue_length(agent_id: str):
    """Get number of messages in an agent's queue."""
    try:
        from redis_client import get_redis_client
        client = get_redis_client()

        if not client.is_connected():
            return {"agent_id": agent_id, "length": 0, "redis_available": False}

        length = client.get_queue_length(agent_id)
        return {
            "agent_id": agent_id,
            "length": length,
            "redis_available": True
        }
    except ImportError:
        return {"agent_id": agent_id, "length": 0, "redis_available": False, "error": "redis_client not available"}
    except Exception as e:
        return {"agent_id": agent_id, "length": 0, "redis_available": False, "error": str(e)}


@app.post("/queue/{agent_id}/pop")
async def pop_agent_queue(agent_id: str):
    """Pop oldest message from agent's queue (FIFO). Used by agents to consume messages."""
    try:
        from redis_client import get_redis_client
        client = get_redis_client()

        if not client.is_connected():
            return {"message": None, "redis_available": False}

        message = client.pop_agent_queue(agent_id)
        return {
            "agent_id": agent_id,
            "message": message,
            "redis_available": True
        }
    except ImportError:
        return {"message": None, "redis_available": False, "error": "redis_client not available"}
    except Exception as e:
        return {"message": None, "redis_available": False, "error": str(e)}


@app.delete("/queue/{agent_id}")
async def clear_agent_queue(agent_id: str):
    """Clear all messages from an agent's queue."""
    try:
        from redis_client import get_redis_client
        client = get_redis_client()

        if not client.is_connected():
            return {"success": False, "redis_available": False}

        success = client.clear_agent_queue(agent_id)
        return {
            "agent_id": agent_id,
            "success": success,
            "redis_available": True
        }
    except ImportError:
        return {"success": False, "redis_available": False, "error": "redis_client not available"}
    except Exception as e:
        return {"success": False, "redis_available": False, "error": str(e)}


@app.get("/queue/agents/status")
async def get_all_agent_status():
    """Get status of all registered agents."""
    try:
        from redis_client import get_redis_client
        client = get_redis_client()

        # Get registered agent IDs from orchestrator
        agent_ids = list(orchestrator._agent_registry.keys()) if hasattr(orchestrator, '_agent_registry') else []

        if not client.is_connected():
            return {
                "agents": {aid: {"status": "unknown", "redis_available": False} for aid in agent_ids},
                "redis_available": False
            }

        statuses = {}
        for agent_id in agent_ids:
            status = client.get_agent_status(agent_id)
            queue_length = client.get_queue_length(agent_id)
            statuses[agent_id] = {
                "status": status if status else {"busy": False, "current_task": None},
                "queue_length": queue_length
            }

        return {
            "agents": statuses,
            "redis_available": True
        }
    except ImportError:
        return {"agents": {}, "redis_available": False, "error": "redis_client not available"}
    except Exception as e:
        return {"agents": {}, "redis_available": False, "error": str(e)}


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("🚀 Memory Chat API Server starting...")
    print("📡 WebSocket (chat): ws://localhost:8000/ws")
    print("👁️  WebSocket (events): ws://localhost:8000/ws/events")
    print("🌐 Chat endpoint: POST /chat")
    print("📊 Events endpoint: GET /events/stats, /events/history, /events/types")

    # Initialize Redis (replaces stub with real implementation if available)
    try:
        from redis_client import initialize_redis
        redis_connected = initialize_redis()
        if redis_connected:
            print("🔴 Redis: Connected and active")
        else:
            print("🔴 Redis: Not available (using stub mode)")
    except ImportError:
        print("🔴 Redis: redis_client module not found (using stub mode)")
    except Exception as e:
        print(f"🔴 Redis: Initialization error - {e} (using stub mode)")

    # Wire up EventEmitter to broadcast to WebSocket clients
    emitter = get_emitter()
    emitter.add_async_listener(broadcast_event_to_react)
    print("✅ EventEmitter wired to visibility stream")
    print("❤️  Health endpoint: GET /health")
    print("📚 History endpoint: GET /history")
    print("🚨 Errors endpoint: GET /errors")
    print("🌿 Sidebar endpoints: GET/POST /sidebars/*")
    print("🔗 Reparent/Cross-ref: POST /sidebars/{id}/reparent, /cross-ref, GET /cross-refs/clustered")
    print("🧶 Yarn Board: GET/PUT /sidebars/{id}/yarn-board, /yarn-board/state, /yarn-board/points/{id}, /yarn-board/render")
    print("🔴 Redis: GET /redis/health")
    print("📬 Queue: POST /queue/route, /queue/approve, GET /queue/{agent_id}, /queue/agents/status")

    # Report startup state - React UI handles "no contexts" case
    try:
        contexts = orchestrator.list_contexts()
        if contexts:
            active = orchestrator.get_active_context_id()
            print(f"🌳 Restored {len(contexts)} context(s) from persistence, active: {active}")

            # Load active context's local_memory into chat.conversation_history
            if active:
                active_ctx = orchestrator.get_context(active)

                # [DEBUG-SYNC] Log state BEFORE restoration attempt
                print(f"[DEBUG-SYNC] api_server_bridge startup - BEFORE restoration:")
                print(f"[DEBUG-SYNC]   chat.conversation_history id: {id(chat.conversation_history)}")
                print(f"[DEBUG-SYNC]   chat.cm.conversation_history id: {id(chat.conversation_manager.conversation_history)}")
                print(f"[DEBUG-SYNC]   Same object BEFORE: {chat.conversation_history is chat.conversation_manager.conversation_history}")
                print(f"[DEBUG-SYNC]   chat.conversation_history length: {len(chat.conversation_history)}")

                # [DEBUG-SYNC] Check WHY we might skip restoration
                print(f"[DEBUG-SYNC] Restoration gate check:")
                print(f"[DEBUG-SYNC]   active_ctx exists: {active_ctx is not None}")
                if active_ctx:
                    print(f"[DEBUG-SYNC]   active_ctx.sidebar_id: {active_ctx.sidebar_id}")
                    print(f"[DEBUG-SYNC]   active_ctx.local_memory is not None: {active_ctx.local_memory is not None}")
                    print(f"[DEBUG-SYNC]   active_ctx.local_memory length: {len(active_ctx.local_memory) if active_ctx.local_memory else 0}")
                    print(f"[DEBUG-SYNC]   active_ctx.local_memory truthy: {bool(active_ctx.local_memory)}")
                else:
                    print(f"[DEBUG-SYNC]   ⚠️ active_ctx is None! Context {active} not found in orchestrator")

                if active_ctx and active_ctx.local_memory:
                    # [DEBUG-SYNC] Log what's actually in local_memory
                    print(f"[DEBUG-SYNC] local_memory inspection:")
                    print(f"[DEBUG-SYNC]   local_memory length: {len(active_ctx.local_memory)}")
                    if active_ctx.local_memory:
                        first_ex = active_ctx.local_memory[0]
                        print(f"[DEBUG-SYNC]   First exchange keys: {list(first_ex.keys())}")
                        print(f"[DEBUG-SYNC]   Has 'role' key: {'role' in first_ex}")
                        print(f"[DEBUG-SYNC]   Has 'user' key: {'user' in first_ex}")
                        print(f"[DEBUG-SYNC]   Has 'retrieved_memories': {'retrieved_memories' in first_ex}")

                    restored = []
                    for i, ex in enumerate(active_ctx.local_memory):
                        if ex.get("role") == "user" and i+1 < len(active_ctx.local_memory) and active_ctx.local_memory[i+1].get("role") == "assistant":
                            restored.append({
                                "user": ex["content"],
                                "assistant": active_ctx.local_memory[i+1]["content"],
                                "timestamp": ex.get("timestamp"),
                                "source": "restored"
                            })

                    # [DEBUG-SYNC] Log what restoration found
                    print(f"[DEBUG-SYNC] Restoration result:")
                    print(f"[DEBUG-SYNC]   restored list length: {len(restored)}")
                    print(f"[DEBUG-SYNC]   (Looking for role='user' format, found {len(restored)} matches)")

                    if restored:
                        chat.conversation_history = restored
                        print(f"💬 Restored {len(restored)} exchanges from active context {active}")

                        # [DEBUG-SYNC] Log state AFTER restoration
                        print(f"[DEBUG-SYNC] api_server_bridge startup - AFTER restoration:")
                        print(f"[DEBUG-SYNC]   chat.conversation_history id: {id(chat.conversation_history)}")
                        print(f"[DEBUG-SYNC]   chat.cm.conversation_history id: {id(chat.conversation_manager.conversation_history)}")
                        print(f"[DEBUG-SYNC]   Same object AFTER: {chat.conversation_history is chat.conversation_manager.conversation_history}")
                        print(f"[DEBUG-SYNC]   ⚠️  REFERENCE BROKEN: {chat.conversation_history is not chat.conversation_manager.conversation_history}")
                    else:
                        print(f"[DEBUG-SYNC] No exchanges matched role='user' format - restored list is EMPTY")
        else:
            print(f"🌳 No persisted contexts - UI will offer choice to start fresh")
    except Exception as e:
        print(f"⚠️  Context state check error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)