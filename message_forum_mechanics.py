#!/usr/bin/env python3
"""
Message Forum Structure for AI Sidebar Collaboration
Core mechanics for sequential messaging, citations, and shared context
"""

import json
import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from uuid import uuid4

@dataclass
class Citation:
    """Knowledge artifact that can be referenced by any model"""
    id: str
    content: str
    source_model: str
    source_context: str
    created_at: datetime
    referenced_by: List[str] = field(default_factory=list)
    
    def add_reference(self, message_id: str):
        """Track which messages reference this citation"""
        if message_id not in self.referenced_by:
            self.referenced_by.append(message_id)

@dataclass 
class Message:
    """Single message in the collaboration forum"""
    id: str
    sequence_number: int
    model_id: str
    content: str
    citations: List[str]  # Citation IDs referenced in this message
    timestamp: datetime
    message_type: str = "conversation"  # conversation, question, answer, insight
    parent_message: Optional[str] = None  # For threaded responses
    
@dataclass
class Participant:
    """Model or human participating in sidebar"""
    id: str
    type: str  # "model" or "human"
    capabilities: List[str]
    status: str = "active"  # active, thinking, away
    join_time: datetime = field(default_factory=datetime.now)

class SidebarForum:
    """
    Core forum structure for AI collaboration
    Handles sequential messaging, citations, and context sharing
    """
    
    def __init__(self, problem_context: Dict[str, Any], sidebar_id: str = None):
        self.sidebar_id = sidebar_id or str(uuid4())
        self.immutable_source = problem_context.copy()  # Never changes
        self.messages: List[Message] = []
        self.citations: Dict[str, Citation] = {}
        self.participants: Dict[str, Participant] = {}
        self.sequence_counter = 0
        self.lock = threading.Lock()  # Thread safety for concurrent access
        self.created_at = datetime.now()
        
    def add_participant(self, model_id: str, model_type: str, capabilities: List[str]):
        """Add model or human to the sidebar conversation"""
        participant = Participant(
            id=model_id,
            type=model_type,
            capabilities=capabilities
        )
        self.participants[model_id] = participant
        
        # Log the join
        self._add_system_message(f"{model_id} joined the sidebar")
        return participant
    
    def add_message(self, model_id: str, content: str, citations: List[str] = None, 
                   message_type: str = "conversation", parent_message: str = None) -> str:
        """
        Add message to the forum with automatic sequencing
        Thread-safe operation with sequential numbering
        """
        with self.lock:
            self.sequence_counter += 1
            
            message = Message(
                id=f"MSG-{self.sequence_counter:04d}",
                sequence_number=self.sequence_counter,
                model_id=model_id,
                content=content,
                citations=citations or [],
                timestamp=datetime.now(),
                message_type=message_type,