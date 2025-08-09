"""
Working Memory Buffer - Core Logic Only
Handles the basic conversation buffer with FIFO behavior
"""
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from collections import deque
import uuid


class WorkingMemoryBuffer:
    """
    Simple FIFO buffer for storing recent conversation exchanges.
    No persistence, no HTTP - just pure memory management.
    """
    
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.created_at = datetime.now(timezone.utc)
        
    def add_exchange(self, user_message: str, assistant_response: str, 
                    context_used: List[str] = None) -> Dict:
        """
        Add a new conversation exchange to the buffer.
        Returns the exchange object that was stored.
        """
        exchange = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exchange_id": str(uuid.uuid4()),
            "user_message": user_message,
            "assistant_response": assistant_response,
            "annotations": {
                "context_sources": context_used or [],
                "memory_type": "working_memory",
                "buffer_position": len(self.buffer)
            }
        }
        
        # Add to buffer (automatically removes oldest if at max_size)
        self.buffer.append(exchange)
        return exchange
    
    def get_recent_context(self, num_exchanges: Optional[int] = None) -> List[Dict]:
        """
        Get recent exchanges for context injection.
        Returns list from oldest to newest.
        """
        if num_exchanges is None:
            return list(self.buffer)
        
        # Get the last N exchanges
        return list(self.buffer)[-num_exchanges:]
    
    def get_current_size(self) -> int:
        """Return current number of exchanges in buffer."""
        return len(self.buffer)
    
    def is_full(self) -> bool:
        """Check if buffer is at maximum capacity."""
        return len(self.buffer) >= self.max_size
    
    def clear(self) -> int:
        """Clear all exchanges. Returns number of exchanges cleared."""
        cleared_count = len(self.buffer)
        self.buffer.clear()
        return cleared_count
    
    def get_summary(self) -> Dict:
        """Get buffer status summary."""
        return {
            "current_size": len(self.buffer),
            "max_size": self.max_size,
            "is_full": self.is_full(),
            "created_at": self.created_at.isoformat(),
            "oldest_exchange": self.buffer[0]["timestamp"] if self.buffer else None,
            "newest_exchange": self.buffer[-1]["timestamp"] if self.buffer else None
        }