#!/usr/bin/env python3
"""
Episodic Memory Coordinator
Single point for all episodic memory access - prevents conflicts between
rich_chat and recovery_thread when both need to write to episodic memory
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import logging
from pathlib import Path

coordinator_logger = logging.getLogger('episodic_coordinator')


class EpisodicMemoryCoordinator:
    """
    Coordinates all access to episodic memory service
    Prevents conflicts between multiple writers (rich_chat, recovery_thread)
    Provides fallback to backup system when episodic memory is unavailable
    """
    
    def __init__(self, episodic_url: str = 'http://localhost:8005', backup_system=None, error_handler=None):
        """
        Initialize coordinator

        Args:
            episodic_url: URL of episodic memory service
            backup_system: EmergencyBackupSystem instance for fallback
            error_handler: ErrorHandler instance for proper error routing
        """
        self.episodic_url = episodic_url.rstrip('/')
        self.backup_system = backup_system
        self.error_handler = error_handler
        
        # Request tracking
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_health_check = None
        self.service_healthy = True
        
        # Request queue for retry logic
        self.retry_queue = []
        self.max_retries = 3
        
    def archive_exchange(self, exchange_data: Dict, source: str = 'unknown') -> Dict[str, Any]:
        """
        Archive exchange to episodic memory with fallback to backup
        
        Args:
            exchange_data: Exchange data to archive
            source: Source of request ('chat', 'recovery', etc.)
            
        Returns:
            Result dict with success status and details
        """
        self.request_count += 1
        
        try:
            # Transform exchange data to episodic memory format
            # Handle both single exchange and conversation data formats
            if 'conversation_id' in exchange_data and 'exchanges' in exchange_data:
                # Already in episodic memory format (from rich_chat)
                enriched_data = exchange_data.copy()
                enriched_data['coordinator_metadata'] = {
                    'source': source,
                    'timestamp': datetime.now().isoformat(),
                    'request_id': self.request_count
                }
            else:
                # Single exchange format - transform to conversation format
                enriched_data = {
                    'conversation_id': exchange_data.get('conversation_id', f'coordinator_{self.request_count}'),
                    'exchanges': [exchange_data],
                    'participant_info': {
                        'user_id': f'{source}_user',
                        'assistant_id': f'{source}_assistant'
                    },
                    'coordinator_metadata': {
                        'source': source,
                        'timestamp': datetime.now().isoformat(),
                        'request_id': self.request_count
                    }
                }
            
            # Attempt to send to episodic memory
            # Wrap in conversation_data as expected by episodic service
            response = requests.post(
                f"{self.episodic_url}/archive",
                json={"conversation_data": enriched_data},
                timeout=10
            )
            
            if response.status_code == 200:
                self.success_count += 1
                self.service_healthy = True
                
                return {
                    'success': True,
                    'source': source,
                    'method': 'episodic_direct',
                    'request_id': self.request_count,
                    'response_time_ms': response.elapsed.total_seconds() * 1000
                }
            else:
                # Server error - capture error details and try backup
                try:
                    error_details = response.json().get('message', response.text)
                except:
                    error_details = response.text[:200] if response.text else 'No error details'

                error_reason = f"HTTP {response.status_code}: {error_details}"
                return self._fallback_to_backup(enriched_data, error_reason, source)
                
        except requests.exceptions.ConnectionError:
            return self._fallback_to_backup(exchange_data, "Connection failed", source)
        except requests.exceptions.Timeout:
            return self._fallback_to_backup(exchange_data, "Request timeout", source)
        except Exception as e:
            return self._fallback_to_backup(exchange_data, str(e), source)
    
    def _fallback_to_backup(self, exchange_data: Dict, error_reason: str, source: str) -> Dict[str, Any]:
        """
        Fall back to backup system when episodic memory fails
        
        Args:
            exchange_data: Data to backup
            error_reason: Why episodic memory failed
            source: Original source of request
            
        Returns:
            Result dict indicating backup fallback
        """
        self.failure_count += 1
        self.service_healthy = False
        
        if self.backup_system:
            try:
                # Use backup system to queue for later recovery
                exchange_id = exchange_data.get('exchange_id', f"coord_{self.request_count}")
                
                # Queue in backup system's pending directory
                pending_dir = self.backup_system.backup_root / 'pending'
                pending_dir.mkdir(exist_ok=True)
                
                pending_file = pending_dir / f"{exchange_id}.json"
                with open(pending_file, 'w') as f:
                    json.dump(exchange_data, f, indent=2, default=str)
                
                # Route through ErrorHandler if available, otherwise use logger
                warning_msg = f"Episodic memory failed ({error_reason}), queued for recovery: {exchange_id}"
                if self.error_handler:
                    from error_handler import ErrorCategory, ErrorSeverity
                    self.error_handler._route_error(warning_msg, ErrorCategory.EPISODIC_MEMORY, ErrorSeverity.MEDIUM_ALERT)
                else:
                    coordinator_logger.warning(warning_msg)
                
                return {
                    'success': True,  # Success from user perspective
                    'source': source,
                    'method': 'backup_queued',
                    'error_reason': error_reason,
                    'queued_for_recovery': True,
                    'exchange_id': exchange_id
                }
                
            except Exception as backup_error:
                coordinator_logger.error(f"Both episodic memory and backup failed: {backup_error}")
                
                return {
                    'success': False,
                    'source': source,
                    'method': 'total_failure',
                    'episodic_error': error_reason,
                    'backup_error': str(backup_error)
                }
        else:
            coordinator_logger.error(f"Episodic memory failed and no backup system available: {error_reason}")
            
            return {
                'success': False,
                'source': source,
                'method': 'no_backup_available',
                'error': error_reason
            }
    
    def retrieve_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Retrieve conversation from episodic memory
        
        Args:
            conversation_id: ID of conversation to retrieve
            
        Returns:
            Conversation data or error info
        """
        try:
            response = requests.get(
                f"{self.episodic_url}/conversation/{conversation_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'conversation': response.json(),
                    'method': 'episodic_direct'
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Conversation not found',
                    'method': 'episodic_direct'
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'method': 'episodic_direct'
                }
                
        except Exception as e:
            coordinator_logger.error(f"Failed to retrieve conversation {conversation_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': 'connection_failed'
            }
    
    def list_conversations(self, limit: int = 50) -> Dict[str, Any]:
        """
        List conversations from episodic memory
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversations or error info
        """
        try:
            response = requests.get(
                f"{self.episodic_url}/conversations",
                params={'limit': limit},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'conversations': response.json().get('conversations', []),
                    'method': 'episodic_direct'
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'method': 'episodic_direct'
                }
                
        except Exception as e:
            coordinator_logger.error(f"Failed to list conversations: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': 'connection_failed'
            }
    
    def verify_exchange(self, exchange_id: str) -> Dict[str, Any]:
        """
        Verify that an exchange exists in episodic memory
        Used by recovery thread for verification
        
        Args:
            exchange_id: ID of exchange to verify
            
        Returns:
            Verification result
        """
        try:
            response = requests.get(
                f"{self.episodic_url}/exchange/{exchange_id}",
                timeout=5
            )
            
            return {
                'success': response.status_code == 200,
                'verified': response.status_code == 200,
                'exchange_exists': response.status_code == 200,
                'method': 'episodic_direct',
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'success': False,
                'verified': False,
                'exchange_exists': False,
                'method': 'connection_failed',
                'error': str(e)
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check episodic memory service health
        
        Returns:
            Health status with details
        """
        try:
            start_time = datetime.now()
            response = requests.get(
                f"{self.episodic_url}/health",
                timeout=5
            )
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self.last_health_check = datetime.now()
            
            if response.status_code == 200:
                self.service_healthy = True
                return {
                    'healthy': True,
                    'status': 'online',
                    'response_time_ms': response_time,
                    'last_check': self.last_health_check.isoformat()
                }
            else:
                self.service_healthy = False
                return {
                    'healthy': False,
                    'status': f'http_error_{response.status_code}',
                    'response_time_ms': response_time,
                    'last_check': self.last_health_check.isoformat()
                }
                
        except Exception as e:
            self.service_healthy = False
            self.last_health_check = datetime.now()
            
            return {
                'healthy': False,
                'status': 'connection_failed',
                'error': str(e),
                'last_check': self.last_health_check.isoformat()
            }
    
    def get_coordinator_stats(self) -> Dict[str, Any]:
        """
        Get coordinator performance statistics
        
        Returns:
            Statistics about coordinator performance
        """
        success_rate = self.success_count / max(self.request_count, 1)
        
        return {
            'total_requests': self.request_count,
            'successful_requests': self.success_count,
            'failed_requests': self.failure_count,
            'success_rate': success_rate,
            'service_healthy': self.service_healthy,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'backup_system_available': self.backup_system is not None
        }
    
    def force_retry_failed(self) -> Dict[str, Any]:
        """
        Force retry of any queued requests
        This would be called by recovery thread or manual command
        
        Returns:
            Results of retry attempts
        """
        if not self.retry_queue:
            return {'retried': 0, 'message': 'No requests to retry'}
        
        retried = 0
        successful = 0
        
        # Process retry queue
        while self.retry_queue and retried < 10:  # Limit retries per call
            request_data = self.retry_queue.pop(0)
            result = self.archive_exchange(request_data['data'], request_data['source'])
            
            retried += 1
            if result['success'] and result['method'] == 'episodic_direct':
                successful += 1
            else:
                # Put back in queue if still failing
                self.retry_queue.append(request_data)
        
        return {
            'retried': retried,
            'successful': successful,
            'still_queued': len(self.retry_queue)
        }


# Example usage
if __name__ == "__main__":
    # Test coordinator without backup system
    coordinator = EpisodicMemoryCoordinator()
    
    # Test health check
    health = coordinator.health_check()
    print(f"Episodic memory health: {health}")
    
    # Test archive (this would normally come from rich_chat or recovery)
    test_exchange = {
        'exchange_id': 'test_coord_001',
        'user': 'Test message',
        'assistant': 'Test response',
        'conversation_id': 'test_conversation'
    }
    
    result = coordinator.archive_exchange(test_exchange, source='test')
    print(f"Archive result: {result}")
    
    # Show stats
    stats = coordinator.get_coordinator_stats()
    print(f"Coordinator stats: {stats}")