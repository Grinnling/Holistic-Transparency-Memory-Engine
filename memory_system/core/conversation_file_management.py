# conversation_manager.py - Conversation and file management
"""
Define conversation management and file storage systems
(Implement basic now, expand to branching later)
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import os
import json
import uuid
from pathlib import Path

# Conditional import for error handler (avoid circular imports)
if TYPE_CHECKING:
    from error_handler import ErrorHandler

class ConversationStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    BRANCHED = "branched"  # Future: for conversation branching

class FileType(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"  # PDF, DOCX, TXT, MD
    IMAGE = "image"
    CODE = "code"         # Source code files
    DATA = "data"         # CSV, JSON, XML
    ARCHIVE = "archive"   # ZIP, TAR, etc.
    OTHER = "other"

@dataclass
class ConversationMessage:
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    timestamp: datetime
    confidence_score: Optional[float] = None
    citations: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)  # File paths
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Conversation:
    id: str
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    message_count: int
    messages: List[ConversationMessage] = field(default_factory=list)
    
    # Future: branching support
    parent_id: Optional[str] = None
    branch_point: Optional[int] = None  # Message index where branch occurred
    child_conversations: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    total_tokens: Optional[int] = None
    
@dataclass 
class AttachedFile:
    id: str
    original_name: str
    stored_path: str
    file_type: FileType
    size_bytes: int
    mime_type: str
    uploaded_at: datetime
    conversation_id: str
    message_index: Optional[int] = None  # Which message it's attached to
    
    # Processing metadata
    processing_status: str = "pending"  # pending, processing, complete, failed
    thumbnail_path: Optional[str] = None
    extracted_text: Optional[str] = None  # For searchable content
    metadata: Dict[str, Any] = field(default_factory=dict)

class ConversationManager:
    def __init__(self, storage_path: str = "./data/conversations", error_handler: Optional["ErrorHandler"] = None):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.error_handler = error_handler

        self.conversations: Dict[str, Conversation] = {}
        self.active_conversation_id: Optional[str] = None

        # Load existing conversations
        self._load_conversations()

    def _log_error(self, error: Exception, context: str, operation: str):
        """Route error through error_handler if available, otherwise print"""
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            self.error_handler.handle_error(
                error,
                ErrorCategory.HISTORY_RESTORATION,  # File-based conversation history
                ErrorSeverity.MEDIUM_ALERT,
                context=context,
                operation=operation
            )
        else:
            print(f"❌ [{operation}] {context}: {error}")
    
    def create_conversation(self, title: Optional[str] = None) -> Conversation:
        """Create new conversation"""
        conv_id = str(uuid.uuid4())
        now = datetime.now()
        
        if not title:
            title = f"Chat {now.strftime('%Y-%m-%d %H:%M')}"
        
        conversation = Conversation(
            id=conv_id,
            title=title,
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            message_count=0
        )
        
        self.conversations[conv_id] = conversation
        self.active_conversation_id = conv_id
        self._save_conversation(conversation)
        
        return conversation
    
    def get_active_conversation(self) -> Optional[Conversation]:
        """Get currently active conversation"""
        if self.active_conversation_id:
            return self.conversations.get(self.active_conversation_id)
        return None
    
    def switch_conversation(self, conversation_id: str) -> bool:
        """Switch to different conversation"""
        if conversation_id in self.conversations:
            self.active_conversation_id = conversation_id
            return True
        return False
    
    def add_message(self, role: str, content: str, 
                   confidence_score: Optional[float] = None,
                   attachments: List[str] = None) -> bool:
        """Add message to active conversation"""
        conversation = self.get_active_conversation()
        if not conversation:
            return False
        
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            confidence_score=confidence_score,
            attachments=attachments or []
        )
        
        conversation.messages.append(message)
        conversation.message_count += 1
        conversation.updated_at = datetime.now()
        
        self._save_conversation(conversation)
        return True
    
    def get_conversation_history(self, conversation_id: Optional[str] = None,
                               limit: Optional[int] = None) -> List[ConversationMessage]:
        """Get conversation history"""
        conv_id = conversation_id or self.active_conversation_id
        if not conv_id or conv_id not in self.conversations:
            return []
        
        messages = self.conversations[conv_id].messages
        if limit:
            return messages[-limit:]
        return messages
    
    def list_conversations(self, status: Optional[ConversationStatus] = None) -> List[Conversation]:
        """List conversations, optionally filtered by status"""
        conversations = list(self.conversations.values())
        
        if status:
            conversations = [c for c in conversations if c.status == status]
        
        # Sort by most recent first
        conversations.sort(key=lambda c: c.updated_at, reverse=True)
        return conversations
    
    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].status = ConversationStatus.ARCHIVED
            self._save_conversation(self.conversations[conversation_id])
            
            # If this was active, clear active
            if self.active_conversation_id == conversation_id:
                self.active_conversation_id = None
                
            return True
        return False
    
    # Future: Conversation branching
    # def branch_conversation(self, conversation_id: str,
    #                       at_message_index: int,
    #                       new_title: Optional[str] = None) -> Optional[str]:
    #     """Branch conversation at specific message (implement later)"""
    #     # TODO: Implement conversation branching
    #     # 1. Create new conversation as child
    #     # 2. Copy messages up to branch point
    #     # 3. Update parent/child relationships
    #     # 4. Return new conversation ID
    #     pass

    # def merge_conversation_branch(self, child_id: str, parent_id: str) -> bool:
    #     """Merge branch back to parent (implement later)"""
    #     # TODO: Implement branch merging
    #     pass
    
    def _load_conversations(self):
        """Load conversations from disk"""
        for conv_file in self.storage_path.glob("*.json"):
            try:
                with open(conv_file, 'r') as f:
                    data = json.load(f)
                    # Convert dict back to Conversation object
                    conversation = self._dict_to_conversation(data)
                    self.conversations[conversation.id] = conversation
            except Exception as e:
                self._log_error(e, f"Loading conversation {conv_file}", "_load_conversations")

    def _save_conversation(self, conversation: Conversation):
        """Save conversation to disk"""
        file_path = self.storage_path / f"{conversation.id}.json"
        try:
            with open(file_path, 'w') as f:
                json.dump(self._conversation_to_dict(conversation), f, indent=2, default=str)
        except Exception as e:
            self._log_error(e, f"Saving conversation {conversation.id}", "_save_conversation")
    
    def _conversation_to_dict(self, conv: Conversation) -> dict:
        """Convert Conversation to dict for JSON storage"""
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status.value,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": conv.message_count,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "confidence_score": m.confidence_score,
                    "citations": m.citations,
                    "attachments": m.attachments,
                    "metadata": m.metadata
                }
                for m in conv.messages
            ],
            "parent_id": conv.parent_id,
            "branch_point": conv.branch_point,
            "child_conversations": conv.child_conversations,
            "tags": conv.tags,
            "summary": conv.summary,
            "total_tokens": conv.total_tokens
        }
    
    def _dict_to_conversation(self, data: dict) -> Conversation:
        """Convert dict to Conversation object"""
        messages = [
            ConversationMessage(
                role=m["role"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
                confidence_score=m.get("confidence_score"),
                citations=m.get("citations", []),
                attachments=m.get("attachments", []),
                metadata=m.get("metadata", {})
            )
            for m in data.get("messages", [])
        ]
        
        return Conversation(
            id=data["id"],
            title=data["title"],
            status=ConversationStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            message_count=data["message_count"],
            messages=messages,
            parent_id=data.get("parent_id"),
            branch_point=data.get("branch_point"),
            child_conversations=data.get("child_conversations", []),
            tags=data.get("tags", []),
            summary=data.get("summary"),
            total_tokens=data.get("total_tokens")
        )

class FileManager:
    def __init__(self, upload_path: str = "./data/uploads", error_handler: Optional["ErrorHandler"] = None):
        self.upload_path = Path(upload_path)
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.error_handler = error_handler

        # Organize by type for easier management
        self.type_paths = {
            FileType.VIDEO: self.upload_path / "videos",
            FileType.AUDIO: self.upload_path / "audio",
            FileType.DOCUMENT: self.upload_path / "documents",
            FileType.IMAGE: self.upload_path / "images",
            FileType.CODE: self.upload_path / "code",
            FileType.DATA: self.upload_path / "data",
            FileType.ARCHIVE: self.upload_path / "archives",
            FileType.OTHER: self.upload_path / "other"
        }

        # Create type directories
        for path in self.type_paths.values():
            path.mkdir(exist_ok=True)

        self.files: Dict[str, AttachedFile] = {}

        self._load_file_index()

    def _log_error(self, error: Exception, context: str, operation: str):
        """Route error through error_handler if available, otherwise print"""
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            self.error_handler.handle_error(
                error,
                ErrorCategory.GENERAL,  # File operations
                ErrorSeverity.MEDIUM_ALERT,
                context=context,
                operation=operation
            )
        else:
            print(f"❌ [{operation}] {context}: {error}")
    
    def detect_file_type(self, filename: str, mime_type: str) -> FileType:
        """Detect file type from filename and MIME type"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Video files
        if ext in ['mp4', 'avi', 'mkv', 'mov', 'webm', 'flv'] or mime_type.startswith('video/'):
            return FileType.VIDEO
            
        # Audio files  
        if ext in ['mp3', 'wav', 'flac', 'ogg', 'aac', 'm4a'] or mime_type.startswith('audio/'):
            return FileType.AUDIO
            
        # Document files
        if ext in ['pdf', 'docx', 'doc', 'txt', 'md', 'rtf', 'odt']:
            return FileType.DOCUMENT
            
        # Image files
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'] or mime_type.startswith('image/'):
            return FileType.IMAGE
            
        # Code files
        if ext in ['py', 'js', 'ts', 'html', 'css', 'cpp', 'c', 'java', 'go', 'rs', 'php']:
            return FileType.CODE
            
        # Data files
        if ext in ['json', 'csv', 'xml', 'yaml', 'yml', 'sql']:
            return FileType.DATA
            
        # Archive files
        if ext in ['zip', 'tar', 'gz', 'rar', '7z', 'bz2']:
            return FileType.ARCHIVE
            
        return FileType.OTHER
    
    def store_file(self, file_data: bytes, original_name: str, 
                  mime_type: str, conversation_id: str) -> AttachedFile:
        """Store uploaded file and return metadata"""
        file_id = str(uuid.uuid4())
        file_type = self.detect_file_type(original_name, mime_type)
        
        # Generate unique filename
        ext = original_name.split('.')[-1] if '.' in original_name else ''
        stored_name = f"{file_id}.{ext}" if ext else file_id
        stored_path = self.type_paths[file_type] / stored_name
        
        # Write file to disk
        with open(stored_path, 'wb') as f:
            f.write(file_data)
        
        # Create file record
        attached_file = AttachedFile(
            id=file_id,
            original_name=original_name,
            stored_path=str(stored_path),
            file_type=file_type,
            size_bytes=len(file_data),
            mime_type=mime_type,
            uploaded_at=datetime.now(),
            conversation_id=conversation_id
        )
        
        self.files[file_id] = attached_file
        self._save_file_index()
        
        return attached_file
    
    def get_file(self, file_id: str) -> Optional[AttachedFile]:
        """Get file metadata"""
        return self.files.get(file_id)
    
    def get_conversation_files(self, conversation_id: str) -> List[AttachedFile]:
        """Get all files for a conversation"""
        return [f for f in self.files.values() if f.conversation_id == conversation_id]
    
    def _load_file_index(self):
        """Load file index from disk"""
        index_path = self.upload_path / "file_index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                    for file_data in data:
                        file_obj = AttachedFile(
                            id=file_data["id"],
                            original_name=file_data["original_name"],
                            stored_path=file_data["stored_path"],
                            file_type=FileType(file_data["file_type"]),
                            size_bytes=file_data["size_bytes"],
                            mime_type=file_data["mime_type"],
                            uploaded_at=datetime.fromisoformat(file_data["uploaded_at"]),
                            conversation_id=file_data["conversation_id"],
                            message_index=file_data.get("message_index"),
                            processing_status=file_data.get("processing_status", "pending"),
                            thumbnail_path=file_data.get("thumbnail_path"),
                            extracted_text=file_data.get("extracted_text"),
                            metadata=file_data.get("metadata", {})
                        )
                        self.files[file_obj.id] = file_obj
            except Exception as e:
                self._log_error(e, "Loading file index", "_load_file_index")
    
    def _save_file_index(self):
        """Save file index to disk"""
        index_path = self.upload_path / "file_index.json"
        file_list = [
            {
                "id": f.id,
                "original_name": f.original_name,
                "stored_path": f.stored_path,
                "file_type": f.file_type.value,
                "size_bytes": f.size_bytes,
                "mime_type": f.mime_type,
                "uploaded_at": f.uploaded_at.isoformat(),
                "conversation_id": f.conversation_id,
                "message_index": f.message_index,
                "processing_status": f.processing_status,
                "thumbnail_path": f.thumbnail_path,
                "extracted_text": f.extracted_text,
                "metadata": f.metadata
            }
            for f in self.files.values()
        ]

        try:
            with open(index_path, 'w') as f:
                json.dump(file_list, f, indent=2)
        except Exception as e:
            self._log_error(e, "Saving file index", "_save_file_index")

# Example usage and testing
if __name__ == "__main__":
    # Test conversation management
    conv_manager = ConversationManager()
    
    # Create test conversation
    conv = conv_manager.create_conversation("Test Chat")
    print(f"Created conversation: {conv.id} - {conv.title}")
    
    # Add messages
    conv_manager.add_message("user", "Hello, how are you?")
    conv_manager.add_message("assistant", "I'm doing well, thank you!", confidence_score=0.95)
    
    # List conversations
    conversations = conv_manager.list_conversations()
    print(f"Total conversations: {len(conversations)}")
    
    # Test file management
    file_manager = FileManager()
    
    # Simulate file upload
    test_file_data = b"This is test file content"
    attached_file = file_manager.store_file(
        file_data=test_file_data,
        original_name="test_document.txt",
        mime_type="text/plain",
        conversation_id=conv.id
    )
    
    print(f"Stored file: {attached_file.id} - {attached_file.original_name}")
    print(f"File type: {attached_file.file_type}")
    print(f"Storage path: {attached_file.stored_path}")
