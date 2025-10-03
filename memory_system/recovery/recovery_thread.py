#!/usr/bin/env python3
"""
Recovery Thread for Emergency Backup System
Automatically flushes pending exchanges to episodic memory
"""

import threading
import time
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Configure logging for recovery thread
# logging.basicConfig(level=logging.INFO)  # Disabled - using ErrorHandler instead
recovery_logger = logging.getLogger('recovery_thread')


class RecoveryThread:
    """
    Background daemon thread for automatic recovery of failed exchanges
    
    Runs continuously in background, checking pending queue and flushing
    to episodic memory when available. Handles failures gracefully with
    exponential backoff and detailed tracking.
    """
    
    def __init__(self, backup_system, error_handler=None, interval: int = 30):
        """
        Initialize recovery thread

        Args:
            backup_system: Reference to EmergencyBackupSystem instance
            error_handler: Optional ErrorHandler for routing messages (falls back to logger)
            interval: Base recovery interval in seconds (default 30)
        """
        self.backup_system = backup_system
        self.error_handler = error_handler
        self.base_interval = interval
        self.current_interval = interval
        
        # Threading control
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.paused_until: Optional[datetime] = None
        self.running = False
        
        # Health tracking
        self.last_health_check: Optional[datetime] = None
        self.last_health_result = False
        self.last_failure_time: Optional[datetime] = None
        self.backoff_seconds = 30
        self.max_backoff = 300  # 5 minutes max
        
        # Recovery tracking and statistics
        self.sync_attempts = {}  # {file_path: [attempt_timestamps]}
        self.failure_reasons = {}  # {file_path: error_reason}
        self.success_count_last_hour = 0
        self.failure_count_last_hour = 0
        self.current_processing_file: Optional[str] = None
        
        # Performance tracking
        self.stats_reset_time = datetime.now()
        self.total_processed = 0
        self.total_succeeded = 0
        self.total_failed = 0

    def _log_info(self, message: str):
        """
        Route info messages through error_handler or logger

        Severity Mapping:
        - "Starting recovery cycle" → LOW_DEBUG (routine operation)
        - "Cycle completed: 1/1 succeeded" → LOW_DEBUG (success is quiet)
        - "Cycle completed: 0/1 succeeded" → Gets escalated to MEDIUM_ALERT in _log_error
        """
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            self.error_handler._route_error(
                message,
                ErrorCategory.RECOVERY_THREAD,
                ErrorSeverity.LOW_DEBUG,
                recovery_succeeded=False
            )
        else:
            self._log_info(message)

    def _log_warning(self, message: str):
        """
        Route warning messages through error_handler or logger

        Severity Mapping:
        - "Failed attempt 2/3" → MEDIUM_ALERT (concerning, need visibility)
        - "Service unavailable" → MEDIUM_ALERT (degraded but running)
        """
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            self.error_handler._route_error(
                message,
                ErrorCategory.RECOVERY_THREAD,
                ErrorSeverity.MEDIUM_ALERT,
                recovery_succeeded=False
            )
        else:
            self._log_warning(message)

    def _log_error(self, message: str, exception: Optional[Exception] = None):
        """
        Route error messages through error_handler or logger

        Severity Mapping:
        - "Failed 3 times, moved to failed/" → HIGH_DEGRADE (data needs manual intervention)
        - "Failed directory critical: 300MB" → CRITICAL_STOP (system failing)
        """
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            # Use _route_error instead of handle_error to avoid double-logging
            self.error_handler._route_error(
                message,
                ErrorCategory.RECOVERY_THREAD,
                ErrorSeverity.HIGH_DEGRADE
            )
        else:
            # Fallback to logger (avoid recursion)
            recovery_logger.error(message)

    def start_recovery_thread(self) -> bool:
        """
        Start the background recovery thread
        
        Returns:
            True if started successfully, False if already running
        """
        if self.is_running():
            self._log_warning("Recovery thread already running")
            return False
        
        # Create and start daemon thread
        self.thread = threading.Thread(
            target=self._recovery_loop,
            name="MemoryRecoveryThread",
            daemon=True  # Dies when main program exits
        )
        
        self.stop_event.clear()
        self.running = True
        self.thread.start()
        
        self._log_info(f"Recovery thread started with {self.base_interval}s interval")
        return True
    
    def stop_recovery_thread(self, timeout: int = 10) -> bool:
        """
        Stop the recovery thread cleanly
        
        Args:
            timeout: Seconds to wait for clean shutdown
            
        Returns:
            True if stopped cleanly, False if timeout
        """
        if not self.is_running():
            return True
        
        self._log_info("Stopping recovery thread...")
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                self._log_error(f"Recovery thread failed to stop within {timeout}s")
                return False
        
        self._log_info("Recovery thread stopped cleanly")
        return True
    
    def pause_recovery(self, minutes: int = 30) -> None:
        """
        Temporarily pause recovery for maintenance
        
        Args:
            minutes: How long to pause (default 30 minutes)
        """
        self.paused_until = datetime.now() + timedelta(minutes=minutes)
        self._log_info(f"Recovery paused for {minutes} minutes until {self.paused_until}")
    
    def resume_recovery(self) -> None:
        """Resume recovery immediately (cancel pause)"""
        self.paused_until = None
        self._log_info("Recovery resumed manually")
    
    def is_running(self) -> bool:
        """Check if recovery thread is active"""
        return self.running and self.thread and self.thread.is_alive()
    
    def is_paused(self) -> bool:
        """Check if recovery is currently paused"""
        if not self.paused_until:
            return False
        
        if datetime.now() >= self.paused_until:
            self.paused_until = None  # Auto-resume
            return False
        
        return True
    
    def _recovery_loop(self) -> None:
        """
        Main recovery loop - runs continuously until stopped
        This is the core background process
        """
        self._log_info("Recovery loop started")
        
        while not self.stop_event.is_set():
            try:
                # Check if paused
                if self.is_paused():
                    time.sleep(5)  # Check pause status every 5 seconds
                    continue
                
                # Perform one recovery cycle
                self._recovery_cycle()
                
                # Calculate next interval (adaptive)
                self.current_interval = self._calculate_next_interval()
                
                # Sleep until next cycle (or until stop signal)
                self.stop_event.wait(self.current_interval)
                
            except Exception as e:
                self._log_error(f"Error in recovery loop: {e}")
                # Sleep briefly before retrying to prevent tight error loop
                time.sleep(10)
        
        self._log_info("Recovery loop ended")
    
    def _recovery_cycle(self) -> None:
        """
        Perform one recovery cycle
        This is where the actual work happens
        """
        cycle_start = datetime.now()
        
        # Step 1: Check episodic memory health
        health_status = self._check_episodic_health()
        if not health_status['healthy']:
            self._log_info(f"Episodic memory not healthy: {health_status['reason']}")
            return
        
        # Step 2: Get pending files to process
        pending_files = self._get_pending_files()
        if not pending_files:
            self._log_info("No pending exchanges to process")
            return
        
        self._log_info(f"Starting recovery cycle: {len(pending_files)} pending exchanges")
        
        # Step 3: Process files in batches (Phase 2 upgrade)
        batch_size = self._calculate_batch_size(len(pending_files))
        batch = pending_files[:batch_size]
        
        processed_count = 0
        success_count = 0
        
        for file_path in batch:
            if self.stop_event.is_set():
                break
            
            self.current_processing_file = str(file_path)
            result = self._process_single_file_with_verification(file_path)
            
            if result['success']:
                success_count += 1
                self.total_succeeded += 1
            else:
                self._handle_processing_failure(file_path, result['error'], result['error_type'])
                self.total_failed += 1
            
            processed_count += 1
            self.total_processed += 1
        
        self.current_processing_file = None
        
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        self._log_info(f"Recovery cycle completed: {success_count}/{processed_count} succeeded in {cycle_duration:.2f}s")
    
    def _check_episodic_health(self) -> Dict[str, Any]:
        """
        Check if episodic memory is healthy with smart backoff
        
        Returns:
            Dict with health status and details
        """
        now = datetime.now()
        
        # Check if we're in backoff period
        if self.last_failure_time:
            time_since_failure = (now - self.last_failure_time).total_seconds()
            if time_since_failure < self.backoff_seconds:
                return {
                    'healthy': False,
                    'reason': f'in_backoff_for_{self.backoff_seconds - int(time_since_failure)}s',
                    'last_check': self.last_health_check
                }
        
        # Perform actual health check
        try:
            response = requests.get(
                'http://localhost:8005/health',
                timeout=3  # Quick timeout for health check
            )
            
            if response.status_code == 200:
                # Success - reset backoff
                self.last_failure_time = None
                self.backoff_seconds = 30
                self.last_health_result = True
                self.last_health_check = now
                
                return {
                    'healthy': True,
                    'reason': 'service_responding',
                    'last_check': now,
                    'response_time_ms': response.elapsed.total_seconds() * 1000
                }
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            # Failure - increase backoff
            self.last_failure_time = now
            self.backoff_seconds = min(self.backoff_seconds * 2, self.max_backoff)
            self.last_health_result = False
            self.last_health_check = now
            
            return {
                'healthy': False,
                'reason': f'connection_failed: {str(e)[:50]}',
                'last_check': now,
                'next_check_in': self.backoff_seconds
            }
    
    def _get_pending_files(self) -> List[Path]:
        """
        Get list of pending files to process, sorted by age (oldest first)
        
        Returns:
            List of Path objects for pending exchange files
        """
        pending_dir = self.backup_system.backup_root / 'pending'
        
        if not pending_dir.exists():
            return []
        
        # Get all .json files, sort by modification time (oldest first)
        pending_files = list(pending_dir.glob('*.json'))
        pending_files.sort(key=lambda f: f.stat().st_mtime)
        
        return pending_files
    
    def _process_single_file(self, file_path: Path) -> bool:
        """
        Process a single pending exchange file
        
        Args:
            file_path: Path to pending exchange JSON file
            
        Returns:
            True if successfully processed, False if failed
        """
        try:
            # Load exchange data from backup format
            with open(file_path, 'r') as f:
                backup_data = json.load(f)
            
            # Transform backup format to episodic memory format
            episodic_data = {
                'exchange_id': backup_data['exchange_id'],
                'conversation_id': backup_data['conversation_id'],
                'conversation_data': {
                    'user': backup_data['user'],
                    'assistant': backup_data['assistant'],
                    'timestamp': backup_data['timestamp']
                }
            }
            
            # Include metadata if present
            if 'metadata' in backup_data:
                episodic_data['conversation_data']['metadata'] = backup_data['metadata']
            
            # Include AI context if present
            if 'ai_context' in backup_data:
                episodic_data['conversation_data']['ai_context'] = backup_data['ai_context']
            
            # Attempt to send to episodic memory
            response = requests.post(
                'http://localhost:8005/archive',
                json=episodic_data,
                timeout=10
            )
            
            if response.status_code == 200:
                # Success - remove from pending
                file_path.unlink()  # Delete the file
                self._log_info(f"Successfully processed {file_path.name}")
                return True
            else:
                # Server error - track failure
                self._track_failure(file_path, f"HTTP_{response.status_code}")
                self._log_warning(f"Failed to process {file_path.name}: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            # Processing error - track failure
            self._track_failure(file_path, str(e))
            self._log_error(f"Error processing {file_path.name}: {e}")
            return False
    
    def _track_failure(self, file_path: Path, error_reason: str) -> None:
        """
        Track processing failure for statistics and retry logic
        
        Args:
            file_path: Path to failed file
            error_reason: Description of failure
        """
        file_key = str(file_path)
        now = datetime.now()
        
        # Track attempt times
        if file_key not in self.sync_attempts:
            self.sync_attempts[file_key] = []
        self.sync_attempts[file_key].append(now)
        
        # Track failure reason
        self.failure_reasons[file_key] = error_reason
        
        # TODO: Implement 3-strike rule in later phase
        # For now, just log the failure
        attempt_count = len(self.sync_attempts[file_key])
        self._log_warning(f"File {file_path.name} failed {attempt_count} times: {error_reason}")
    
    def _calculate_next_interval(self) -> int:
        """
        Calculate adaptive interval based on queue size and recent performance
        
        Returns:
            Seconds to wait before next recovery cycle
        """
        pending_count = len(self._get_pending_files())
        
        if pending_count == 0:
            return 60  # Maintenance mode - check less frequently
        elif pending_count > 50:
            return 10  # Aggressive mode - large backlog
        else:
            return self.base_interval  # Normal mode
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status for monitoring and debugging
        
        Returns:
            Dictionary with detailed recovery thread status
        """
        now = datetime.now()
        uptime = (now - self.stats_reset_time).total_seconds()
        
        return {
            'thread_status': 'running' if self.is_running() else 'stopped',
            'is_paused': self.is_paused(),
            'paused_until': self.paused_until.isoformat() if self.paused_until else None,
            
            'episodic_health': {
                'status': self.last_health_result,
                'last_check': self.last_health_check.isoformat() if self.last_health_check else None,
                'backoff_seconds': self.backoff_seconds if self.last_failure_time else 0
            },
            
            'queue_info': {
                'pending_count': len(self._get_pending_files()),
                'currently_processing': self.current_processing_file,
                'retry_tracking': len(self.failure_reasons),
                'permanently_failed': self.get_failed_files_summary()['total_failed']
            },
            
            'performance': {
                'total_processed': self.total_processed,
                'total_succeeded': self.total_succeeded,
                'total_failed': self.total_failed,
                'success_rate': self.total_succeeded / max(self.total_processed, 1),
                'uptime_seconds': uptime
            },
            
            'timing': {
                'current_interval': self.current_interval,
                'base_interval': self.base_interval,
                'thread_alive': self.thread.is_alive() if self.thread else False
            }
        }
    
    def force_recovery_now(self) -> Dict[str, Any]:
        """
        Trigger immediate recovery cycle (bypass normal interval)
        
        Returns:
            Results of the forced recovery cycle
        """
        if not self.is_running():
            return {'error': 'Recovery thread not running'}
        
        self._log_info("Forcing immediate recovery cycle")
        
        # Run one cycle immediately
        start_time = datetime.now()
        pending_before = len(self._get_pending_files())
        
        self._recovery_cycle()
        
        pending_after = len(self._get_pending_files())
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'forced_recovery_completed': True,
            'pending_before': pending_before,
            'pending_after': pending_after,
            'processed': pending_before - pending_after,
            'duration_seconds': duration
        }
    
    # ==================== PHASE 2: SMART RECOVERY LOGIC ====================
    
    def _calculate_batch_size(self, total_pending: int) -> int:
        """
        Calculate optimal batch size based on pending queue and recent performance
        
        Args:
            total_pending: Number of pending files
            
        Returns:
            Batch size (1-15 files)
        """
        if total_pending == 0:
            return 0
        elif total_pending <= 5:
            return total_pending  # Process all if small queue
        elif total_pending <= 20:
            return 5  # Small batches for medium queues
        elif total_pending <= 50:
            return 8  # Medium batches for large queues
        else:
            return 12  # Large batches for huge backlogs (but not overwhelming)
    
    def _process_single_file_with_verification(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single pending exchange file with integrity verification
        
        Args:
            file_path: Path to pending exchange JSON file
            
        Returns:
            Dict with success status, error info, and verification details
        """
        try:
            # Load exchange data
            with open(file_path, 'r') as f:
                exchange_data = json.load(f)
                
            exchange_id = exchange_data.get('exchange_id')
            if not exchange_id:
                return {
                    'success': False,
                    'error': 'Missing exchange_id in file',
                    'error_type': 'data_corruption'
                }
            
            # Attempt to send to episodic memory
            response = requests.post(
                'http://localhost:8005/archive',
                json=exchange_data,
                timeout=10
            )
            
            if response.status_code == 200:
                # Verify the exchange was actually stored
                verification_result = self._verify_exchange_stored(exchange_id)
                
                if verification_result['verified']:
                    # Success and verified - safe to remove from pending
                    file_path.unlink()
                    self._log_info(f"Successfully processed and verified {file_path.name}")
                    return {
                        'success': True,
                        'verified': True,
                        'verification_time_ms': verification_result.get('response_time_ms', 0)
                    }
                else:
                    # Posted but verification failed - keep file for retry
                    self._log_warning(f"Posted {file_path.name} but verification failed: {verification_result['error']}")
                    return {
                        'success': False,
                        'error': f"Verification failed: {verification_result['error']}",
                        'error_type': 'verification_failure'
                    }
            else:
                # Server error - classify error type
                error_type = self._classify_http_error(response.status_code)
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text[:100]}",
                    'error_type': error_type
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'error_type': 'network_timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False, 
                'error': 'Connection failed',
                'error_type': 'network_connection'
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Invalid JSON: {str(e)[:50]}',
                'error_type': 'data_corruption'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:100],
                'error_type': 'unknown_error'
            }
    
    def _verify_exchange_stored(self, exchange_id: str) -> Dict[str, Any]:
        """
        Verify that an exchange was properly stored in episodic memory
        
        Args:
            exchange_id: ID of exchange to verify
            
        Returns:
            Dict with verification result
        """
        try:
            start_time = datetime.now()
            response = requests.get(
                f'http://localhost:8005/exchange/{exchange_id}',
                timeout=5
            )
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                # Exchange exists - verification successful
                return {
                    'verified': True,
                    'response_time_ms': response_time
                }
            elif response.status_code == 404:
                # Exchange not found - verification failed
                return {
                    'verified': False,
                    'error': 'Exchange not found in episodic memory',
                    'response_time_ms': response_time
                }
            else:
                # Server error during verification
                return {
                    'verified': False,
                    'error': f'Verification request failed: HTTP {response.status_code}',
                    'response_time_ms': response_time
                }
                
        except Exception as e:
            return {
                'verified': False,
                'error': f'Verification error: {str(e)[:50]}',
                'response_time_ms': 0
            }
    
    def _classify_http_error(self, status_code: int) -> str:
        """
        Classify HTTP errors for better failure tracking
        
        Args:
            status_code: HTTP status code
            
        Returns:
            Error type classification
        """
        if status_code == 400:
            return 'bad_request'
        elif status_code == 401:
            return 'auth_failure'
        elif status_code == 403:
            return 'permission_denied'
        elif status_code == 404:
            return 'endpoint_not_found'
        elif status_code == 413:
            return 'payload_too_large'
        elif status_code == 429:
            return 'rate_limited'
        elif 500 <= status_code < 600:
            return 'server_error'
        else:
            return 'http_error'
    
    def _handle_processing_failure(self, file_path: Path, error: str, error_type: str) -> None:
        """
        Handle processing failure with 3-strike rule and failure classification
        
        Args:
            file_path: Path to failed file
            error: Error description
            error_type: Classification of error
        """
        file_key = str(file_path)
        now = datetime.now()
        
        # Track attempt times
        if file_key not in self.sync_attempts:
            self.sync_attempts[file_key] = []
        self.sync_attempts[file_key].append(now)
        
        # Track failure reason and type
        self.failure_reasons[file_key] = {
            'error': error,
            'error_type': error_type,
            'attempt_count': len(self.sync_attempts[file_key]),
            'last_attempt': now.isoformat()
        }
        
        attempt_count = len(self.sync_attempts[file_key])
        
        # 3-strike rule: Move to failed directory after 3 attempts
        if attempt_count >= 3:
            self._move_to_failed_directory(file_path, error_type)
            self._log_error(f"File {file_path.name} failed 3 times, moved to failed directory: {error}")
            
            # Clean up tracking data
            del self.sync_attempts[file_key]
            del self.failure_reasons[file_key]
        else:
            self._log_warning(f"File {file_path.name} failed attempt {attempt_count}/3 ({error_type}): {error}")
    
    def _move_to_failed_directory(self, file_path: Path, error_type: str) -> None:
        """
        Move permanently failed file to failed directory for manual review
        
        Args:
            file_path: Path to file that permanently failed
            error_type: Type of error that caused permanent failure
        """
        failed_dir = self.backup_system.backup_root / 'failed'
        failed_dir.mkdir(exist_ok=True)
        
        # Create subdirectory by error type for organization
        error_subdir = failed_dir / error_type
        error_subdir.mkdir(exist_ok=True)
        
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_name = file_path.stem
        failed_filename = f"{original_name}_{timestamp}.json"
        failed_path = error_subdir / failed_filename
        
        # Move file to failed directory
        try:
            file_path.rename(failed_path)
            self._log_info(f"Moved failed file to: {failed_path}")
        except Exception as e:
            self._log_error(f"Failed to move {file_path} to failed directory: {e}")
            # If move fails, at least remove from pending so we don't keep retrying
            try:
                file_path.unlink()
                self._log_warning(f"Deleted {file_path} after failed move")
            except Exception as e2:
                self._log_error(f"Failed to delete {file_path}: {e2}")
    
    def get_failed_files_summary(self) -> Dict[str, Any]:
        """
        Get summary of files that have permanently failed
        
        Returns:
            Summary of failed files by error type
        """
        failed_dir = self.backup_system.backup_root / 'failed'
        
        if not failed_dir.exists():
            return {'total_failed': 0, 'by_error_type': {}}
        
        summary = {'total_failed': 0, 'by_error_type': {}}
        
        for error_type_dir in failed_dir.iterdir():
            if error_type_dir.is_dir():
                failed_files = list(error_type_dir.glob('*.json'))
                if failed_files:
                    summary['by_error_type'][error_type_dir.name] = {
                        'count': len(failed_files),
                        'oldest': min(f.stat().st_mtime for f in failed_files),
                        'newest': max(f.stat().st_mtime for f in failed_files)
                    }
                    summary['total_failed'] += len(failed_files)
        
        return summary


# Example usage and integration helper
if __name__ == "__main__":
    # This would normally be integrated with EmergencyBackupSystem
    print("RecoveryThread - Phase 1 Implementation")
    print("Ready for integration with EmergencyBackupSystem")
    
    # Basic functionality test
    class MockBackupSystem:
        def __init__(self):
            self.backup_root = Path.home() / '.memory_backup'
    
    mock_backup = MockBackupSystem()
    recovery = RecoveryThread(mock_backup, interval=5)  # Fast interval for testing
    
    print(f"Initial status: {recovery.get_recovery_status()}")
    
    # Test start/stop
    print("Starting recovery thread...")
    recovery.start_recovery_thread()
    
    time.sleep(2)
    print(f"Running status: {recovery.get_recovery_status()}")
    
    print("Stopping recovery thread...")
    recovery.stop_recovery_thread()
    
    print("Phase 1 implementation complete!")