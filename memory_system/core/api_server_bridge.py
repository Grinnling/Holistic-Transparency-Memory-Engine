# api_server.py - NEW FILE NEEDED
"""
FastAPI bridge to expose rich_chat functionality via REST/WebSocket
Port: 8000 (main project API)
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import asyncio
from typing import List, Dict, Any
import uuid
from datetime import datetime
import sys

# Add path to CODE_IMPLEMENTATION folder and import chat system
sys.path.append('/home/grinnling/Development/CODE_IMPLEMENTATION')
from rich_chat import RichMemoryChat
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
from service_manager import ServiceManager

app = FastAPI(title="Memory Chat API", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize chat system, error handler, and service manager
# debug_mode only affects logging visibility, not functionality
chat = RichMemoryChat(debug_mode=False, auto_start_services=True)
error_handler = ErrorHandler(debug_mode=True)
service_manager = ServiceManager(error_handler=error_handler, debug_mode=True)

# Pydantic models
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    confidence_score: float | None = None
    operation_context: str | None = None  # What operation triggered this
    error: str | None = None

class ErrorEvent(BaseModel):
    id: str
    timestamp: str
    error: str
    operation_context: str = None
    service: str = None
    severity: str = "normal"  # critical, warning, normal, debug
    attempted_fixes: List[str] = []
    fix_success: bool = None

# Legacy error_tracker removed - now using centralized ErrorHandler

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

async def broadcast_to_react(message: dict):
    """Send updates to all connected React clients"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            active_connections.remove(connection)

def track_error(error_msg: str, operation_context: str = None, service: str = "api_server", severity: str = "normal"):
    """Track errors using centralized ErrorHandler and broadcast to React"""

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

    # Create exception from error message
    error_exception = Exception(error_msg)

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
            operation_context=f"chat_message: {message.message[:50]}..."
        )
        
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
        track_error(error_msg, f"chat_message: {message.message[:50]}...", "chat_processor", "critical")
        
        return ChatResponse(
            response="Sorry, I encountered an error processing your message.",
            error=error_msg,
            operation_context=f"chat_message: {message.message[:50]}..."
        )

@app.get("/health")
async def health_check():
    """Check all service health using ServiceManager"""
    # Use ServiceManager for clean, centralized health checking
    return service_manager.check_services(show_table=False)

@app.get("/history")
async def get_history():
    """Get conversation history"""
    try:
        return {
            "history": chat.conversation_history,
            "conversation_id": chat.conversation_id
        }
    except Exception as e:
        track_error(f"History retrieval failed: {str(e)}", "get_history", "chat_processor", "warning")
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

            formatted_errors.append({
                "id": str(hash(f"{error_record['timestamp']}_{error_record['message']}")),
                "timestamp": error_record['timestamp'].isoformat(),
                "error": error_record['message'],
                "severity": severity_map.get(error_record['severity'], "normal"),
                "operation_context": error_record.get('operation', 'unknown'),
                "service": error_record.get('category', 'unknown'),
                "attempted_fixes": [],  # TODO: Add recovery tracking from ErrorHandler
                "fix_success": None
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
    """Mark error as acknowledged - TODO: Add acknowledgement tracking to ErrorHandler"""
    # For now, just return success since ErrorHandler doesn't have acknowledgement yet
    return {"status": "acknowledged", "note": "Acknowledgement tracking not yet implemented in ErrorHandler"}

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

    await broadcast_to_react({"type": "errors_cleared"})
    return {"status": "cleared"}

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
        track_error(f"Memory stats failed: {str(e)}", "get_memory_stats", "memory_system", "warning")
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
        track_error(f"Memory search failed: {str(e)}", f"search_query: {query}", "memory_system", "warning")
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
                track_error(f"WebSocket error: {str(e)}", "websocket_handling", "api_server", "warning")
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
                
    finally:
        active_connections.remove(websocket)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("🚀 Memory Chat API Server starting...")
    print("📡 WebSocket endpoint: ws://localhost:8000/ws")
    print("🌐 Chat endpoint: POST /chat")
    print("❤️  Health endpoint: GET /health")
    print("📚 History endpoint: GET /history")
    print("🚨 Errors endpoint: GET /errors")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)