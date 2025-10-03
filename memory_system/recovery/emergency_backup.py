#!/usr/bin/env python3
"""
Emergency Backup System for Memory Chat
Ensures zero data loss even when memory services fail
"""

import json
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import time
import hashlib

class EmergencyBackupSystem:
    """
    Three-stage backup system:
    1. Active: Current conversations (readable JSONL)
    2. Pending: Awaiting episodic memory sync
    3. Archived: Successfully synced (compressed after 7 days)
    """
    
    def __init__(self, backup_root: Optional[Path] = None):
        """Initialize backup system with directory structure"""
        self.backup_root = backup_root or (Path.home() / '.memory_backup')
        self.conversation_id = None
        self.model_config = {}
        
        # Recovery features
        self.partial_exchange_buffer = {}
        self.last_checkpoint = None
        
        # Setup directory structure
        self._setup_directories()
        
        # Recovery thread will be started separately to allow testing
        self.recovery_thread = None
        self.recovery_enabled = True
        self.recovery_interval = 30  # seconds
        
    def _setup_directories(self):
        """Create backup directory structure"""
        dirs = [
            self.backup_root / 'active',
            self.backup_root / 'pending',
            self.backup_root / 'archived' / 'daily',
            self.backup_root / 'archived' / 'audit',
            self.backup_root / 'recovery',  # For partial exchanges
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            
    def set_conversation_context(self, conversation_id: str, model_config: Dict):
        """Set current conversation context for metadata"""
        self.conversation_id = conversation_id
        self.model_config = model_config
        
    def backup_exchange(self, exchange_data: Dict, timing_info: Optional[Dict] = None,
                       ai_context: Optional[Dict] = None) -> str:
        """
        Backup a complete exchange with rich metadata
        
        Args:
            exchange_data: Core exchange (user, assistant, timestamp)
            timing_info: Optional timing data (thinking_time, interrupted, etc)
            ai_context: AI-specific metadata for learning and recovery
            
        Returns:
            exchange_id for recovery reference
        """
        # Generate unique exchange ID
        exchange_id = self._generate_exchange_id(exchange_data)
        
        # Enrich with metadata
        enriched_data = {
            'exchange_id': exchange_id,
            'conversation_id': self.conversation_id,
            'timestamp': exchange_data.get('timestamp', datetime.now().isoformat()),
            'user': exchange_data.get('user', ''),
            'assistant': exchange_data.get('assistant', ''),
            'metadata': {
                'model_config': self.model_config.copy(),
                'backup_timestamp': datetime.now().isoformat(),
                'backup_version': '1.1',  # Updated for AI context
            }
        }
        
        # Add timing info if provided
        if timing_info:
            enriched_data['metadata'].update({
                'thinking_time_ms': timing_info.get('thinking_time_ms'),
                'was_interrupted': timing_info.get('was_interrupted', False),
                'token_counts': timing_info.get('token_counts', {}),
                'generation_attempts': timing_info.get('generation_attempts', 1),
            })
        
        # Add AI context if provided (all the helpful stuff I mentioned)
        if ai_context:
            enriched_data['ai_context'] = {
                # Context window tracking
                'context_usage': ai_context.get('context_usage', {
                    'current_tokens': 0,
                    'max_tokens': 4096,
                    'pressure': 0.0
                }),
                
                # Conversation flow markers
                'topic_shift': ai_context.get('topic_shift', False),
                'conversation_phase': ai_context.get('conversation_phase', 'unknown'),
                'requires_context': ai_context.get('requires_context', []),
                
                # Error context for recovery
                'previous_errors': ai_context.get('previous_errors', []),
                'recovery_hints': ai_context.get('recovery_hints', ''),
                
                # Learning signals (will be populated by implicit tracking later)
                'user_satisfaction': ai_context.get('user_satisfaction'),
                'required_clarifications': ai_context.get('required_clarifications', 0),
                'helpful_response': ai_context.get('helpful_response'),
                
                # Relationship tracking
                'references': ai_context.get('references', []),
                'referenced_by': ai_context.get('referenced_by', []),
                'invalidates': ai_context.get('invalidates', []),
                
                # Additional AI needs
                'ambiguities_detected': ai_context.get('ambiguities_detected', []),
                'confidence_per_statement': ai_context.get('confidence_per_statement', {}),
                'alternative_interpretations': ai_context.get('alternative_interpretations', [])
            }
        
        # Write to active backup (append-only JSONL)
        active_file = self.backup_root / 'active' / f'conversation_{self.conversation_id}.jsonl'
        with open(active_file, 'a') as f:
            f.write(json.dumps(enriched_data) + '\n')
        
        # Queue for episodic sync
        self._queue_for_sync(enriched_data)
        
        # Update last checkpoint
        self.last_checkpoint = exchange_id
        
        return exchange_id
    
    def backup_partial_exchange(self, partial_data: Dict, exchange_id: Optional[str] = None) -> str:
        """
        Backup partial exchange for crash recovery
        Useful when generation is interrupted or system crashes mid-response
        """
        if not exchange_id:
            exchange_id = self._generate_exchange_id(partial_data)
            
        partial_file = self.backup_root / 'recovery' / f'{exchange_id}_partial.json'
        
        # Store with recovery metadata
        recovery_data = {
            'exchange_id': exchange_id,
            'conversation_id': self.conversation_id,
            'partial_data': partial_data,
            'saved_at': datetime.now().isoformat(),
            'can_resume': True
        }
        
        with open(partial_file, 'w') as f:
            json.dump(recovery_data, f, indent=2)
            
        self.partial_exchange_buffer[exchange_id] = recovery_data
        return exchange_id
    
    def complete_partial_exchange(self, exchange_id: str, complete_data: Dict):
        """Complete a partial exchange and move to normal backup"""
        partial_file = self.backup_root / 'recovery' / f'{exchange_id}_partial.json'
        
        if partial_file.exists():
            # Mark partial as completed
            partial_file.unlink()
            
        # Remove from buffer
        self.partial_exchange_buffer.pop(exchange_id, None)
        
        # Backup as complete exchange
        return self.backup_exchange(complete_data)
    
    def manual_checkpoint(self, checkpoint_name: Optional[str] = None) -> str:
        """
        Create manual checkpoint of current conversation state
        Useful for important moments user wants to preserve
        """
        checkpoint_name = checkpoint_name or f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Copy current active file to checkpoint
        if self.conversation_id:
            active_file = self.backup_root / 'active' / f'conversation_{self.conversation_id}.jsonl'
            if active_file.exists():
                checkpoint_file = self.backup_root / 'archived' / 'audit' / f'checkpoint_{checkpoint_name}.jsonl'
                shutil.copy2(active_file, checkpoint_file)
                
                return f"Checkpoint saved: {checkpoint_name}"
        
        return "No active conversation to checkpoint"
    
    def _generate_exchange_id(self, exchange_data: Dict) -> str:
        """Generate unique ID for exchange"""
        # Use hash of content + timestamp for uniqueness
        content = f"{exchange_data.get('user', '')}{exchange_data.get('assistant', '')}{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _queue_for_sync(self, exchange_data: Dict):
        """Queue exchange for episodic memory sync"""
        pending_file = self.backup_root / 'pending' / f"{exchange_data['exchange_id']}.json"
        with open(pending_file, 'w') as f:
            json.dump(exchange_data, f, indent=2)
    
    def get_pending_count(self) -> int:
        """Get count of exchanges awaiting sync"""
        pending_dir = self.backup_root / 'pending'
        return len(list(pending_dir.glob('*.json')))
    
    def get_recovery_candidates(self) -> List[Dict]:
        """Get partial exchanges that can be recovered"""
        recovery_dir = self.backup_root / 'recovery'
        candidates = []
        
        for partial_file in recovery_dir.glob('*_partial.json'):
            with open(partial_file) as f:
                candidates.append(json.load(f))
                
        return candidates
    
    def compress_old_backups(self, days_to_keep_readable: int = 7):
        """
        Compress backups older than specified days
        Keeps recent backups readable for debugging
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep_readable)
        
        # Process active directory
        active_dir = self.backup_root / 'active'
        for jsonl_file in active_dir.glob('*.jsonl'):
            # Check file modification time
            file_mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                # Compress to daily archive
                date_str = file_mtime.strftime('%Y-%m-%d')
                archive_file = self.backup_root / 'archived' / 'daily' / f'{date_str}.jsonl.gz'
                
                # Append to daily archive (compressed)
                with open(jsonl_file, 'rb') as f_in:
                    with gzip.open(archive_file, 'ab') as f_out:
                        f_out.write(f_in.read())
                
                # Remove original
                jsonl_file.unlink()
    
    def read_compressed_archive(self, date_str: str) -> List[Dict]:
        """
        Read compressed archive for specific date
        Demonstrates that compression doesn't prevent access
        """
        archive_file = self.backup_root / 'archived' / 'daily' / f'{date_str}.jsonl.gz'
        
        if not archive_file.exists():
            return []
        
        exchanges = []
        with gzip.open(archive_file, 'rt') as f:
            for line in f:
                exchanges.append(json.loads(line))
                
        return exchanges
    
    def calculate_context_usage(self, conversation_history: List[Dict], max_tokens: int = 4096) -> Dict:
        """
        Calculate current context window usage
        Helper for AI context metadata
        """
        # Rough token estimation (1 token ≈ 3.7 characters)
        total_chars = sum(
            len(ex.get('user', '') + ex.get('assistant', ''))
            for ex in conversation_history
        )
        current_tokens = int(total_chars / 3.7)
        
        return {
            'current_tokens': current_tokens,
            'max_tokens': max_tokens,
            'pressure': current_tokens / max_tokens,
            'exchanges_before_limit': max((max_tokens - current_tokens) // 50, 0)  # Assuming ~50 tokens per exchange
        }
    
    def detect_topic_shift(self, current_message: str, previous_exchange: Dict) -> bool:
        """
        Simple topic shift detection
        Can be enhanced with better NLP later
        """
        if not previous_exchange:
            return False
            
        # Simple keyword overlap check
        current_words = set(current_message.lower().split())
        previous_words = set(previous_exchange.get('user', '').lower().split())
        previous_words.update(previous_exchange.get('assistant', '').lower().split())
        
        # Remove common words
        stop_words = {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but', 'in', 'with', 'to', 'for', 'of', 'as', 'by'}
        current_words -= stop_words
        previous_words -= stop_words
        
        # If less than 20% word overlap, likely topic shift
        if current_words and previous_words:
            overlap = len(current_words & previous_words) / len(current_words)
            return overlap < 0.2
        
        return False
    
    def get_backup_stats(self) -> Dict:
        """Get statistics about backup system"""
        stats = {
            'active_conversations': len(list((self.backup_root / 'active').glob('*.jsonl'))),
            'pending_sync': self.get_pending_count(),
            'partial_exchanges': len(self.get_recovery_candidates()),
            'archived_days': len(list((self.backup_root / 'archived' / 'daily').glob('*.jsonl.gz'))),
            'audit_checkpoints': len(list((self.backup_root / 'archived' / 'audit').glob('checkpoint_*.jsonl'))),
            'total_size_mb': sum(f.stat().st_size for f in self.backup_root.rglob('*') if f.is_file()) / (1024 * 1024)
        }
        return stats


# Example usage and testing helpers
if __name__ == "__main__":
    # Quick test of backup system with AI context
    backup = EmergencyBackupSystem()
    backup.set_conversation_context("test-conv-123", {"model": "gpt-4", "temperature": 0.7})
    
    # Test conversation history for context calculation
    conversation_history = [
        {'user': 'What is Python?', 'assistant': 'Python is a programming language...'},
        {'user': 'Tell me more', 'assistant': 'Python was created by Guido van Rossum...'}
    ]
    
    # Test normal backup with AI context
    exchange = {
        'user': 'Hello, how are you?',
        'assistant': 'I am doing well, thank you for asking!',
        'timestamp': datetime.now().isoformat()
    }
    
    timing = {
        'thinking_time_ms': 1250,
        'was_interrupted': False,
        'token_counts': {'input': 12, 'output': 15}
    }
    
    # Build AI context with all the helpful metadata
    ai_context = {
        'context_usage': backup.calculate_context_usage(conversation_history),
        'topic_shift': backup.detect_topic_shift('Hello, how are you?', conversation_history[-1] if conversation_history else None),
        'conversation_phase': 'greeting',
        'ambiguities_detected': [],
        'confidence_per_statement': {
            'I am doing well': 0.95,
            'thank you for asking': 0.99
        },
        'references': ['exchange_456'] if len(conversation_history) > 1 else [],
        'user_satisfaction': None,  # Will be tracked implicitly later
    }
    
    exchange_id = backup.backup_exchange(exchange, timing, ai_context)
    print(f"Backed up exchange with AI context: {exchange_id}")
    
    # Test partial backup (interrupted generation)
    partial = {
        'user': 'Tell me a long story',
        'assistant': 'Once upon a time, in a land far...'  # Interrupted
    }
    
    partial_id = backup.backup_partial_exchange(partial)
    print(f"Saved partial exchange: {partial_id}")
    
    # Show stats
    print(f"\nBackup stats: {json.dumps(backup.get_backup_stats(), indent=2)}")