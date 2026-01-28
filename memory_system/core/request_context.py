"""
Shared Request Context Module

This module holds the request_id ContextVar that needs to be shared
between api_server_bridge and rich_chat without circular import issues.

Both modules should import from HERE, not from each other.
"""
from contextvars import ContextVar
from uuid_extensions import uuid7

# Single source of truth for request ID tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)

def get_request_id() -> str:
    """Get the current request ID from context (returns 'unknown' if not in request context)"""
    return request_id_var.get() or "unknown"

def set_request_id(request_id: str = None) -> str:
    """Set the request ID in context. If none provided, generates UUID7."""
    if request_id is None:
        request_id = str(uuid7())
    request_id_var.set(request_id)
    return request_id

# Debug helper
def get_contextvar_id() -> int:
    """Get the id of the ContextVar object (for debugging)"""
    return id(request_id_var)
