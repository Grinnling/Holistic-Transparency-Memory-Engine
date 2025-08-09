#!/usr/bin/env python3
"""
Archiving Triggers System
Monitors working memory and triggers archiving based on various conditions
"""
import time
import threading
import logging
import requests
import os
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TriggerType(Enum):
    """Types of archiving triggers"""
    BUFFER_FULL = "buffer_full"
    TIME_GAP = "time_gap"
    MANUAL = "manual"
    SYSTEM_RESTART = "system_restart"
    TOPIC_SHIFT = "topic_shift"

@dataclass
class TriggerConfig:
    """Configuration for archiving triggers"""
    # Buffer-based triggers
    max_buffer_size: int = 20
    
    # Time-based triggers
    inactivity_timeout_minutes: int = 60
    max_conversation_duration_hours: int = 24
    
    # Topic shift detection
    enable_topic_shift_detection: bool = False
    topic_shift_threshold: float = 0.7
    
    # Service URLs
    working_memory_url: str = "http://localhost:8002"
    episodic_memory_url: str = "http://localhost:8005"
    
    # Monitoring intervals
    check_interval_seconds: int = 30

class ArchivingTriggers:
    """
    Monitors working memory and triggers archiving when conditions are met
    """
    
    def __init__(self, config: TriggerConfig):
        self.config = config
        self.is_running = False
        self.monitor_thread = None
        self.last_check_time = datetime.now(timezone.utc)
        self.last_activity_time = datetime.now(timezone.utc)
        self.previous_conversation_state = None
        
        # Authentication for working memory service
        self.auth_key = os.getenv('MEMORY_AUTH_KEY', 'development_key_change_in_production')
        self.auth_enabled = os.getenv('MEMORY_AUTH_ENABLED', 'true').lower() == 'true'
        
        # Statistics
        self.trigger_stats = {
            TriggerType.BUFFER_FULL: 0,
            TriggerType.TIME_GAP: 0,
            TriggerType.MANUAL: 0,
            TriggerType.SYSTEM_RESTART: 0,
            TriggerType.TOPIC_SHIFT: 0
        }
        
        # Thread lock for thread-safety
        self.lock = threading.Lock()
        
        logger.info(f"Archiving triggers system initialized (auth: {'enabled' if self.auth_enabled else 'disabled'})")
    
    def _generate_auth_token(self, data: str) -> str:
        """Generate HMAC token for authenticated requests to working memory"""
        if not self.auth_enabled:
            return ""
        
        timestamp = str(int(time.time()))
        message = f"{data}:{timestamp}"
        signature = hmac.new(
            self.auth_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{signature}:{timestamp}"
    
    def _make_authenticated_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make an authenticated request to working memory service"""
        print(f"[archiving_triggers.py:96] Making {method} request to {url}")
        headers = kwargs.get('headers', {})
        
        # Only add Content-Type for requests that actually have bodies
        if method.upper() in ['POST', 'PUT', 'PATCH'] and 'json' in kwargs:
            headers['Content-Type'] = 'application/json'
            print(f"[archiving_triggers.py:101] Added Content-Type header for {method}")
        
        if self.auth_enabled:
            # Get request data for token generation
            request_data = ""
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                if 'json' in kwargs:
                    import json
                    request_data = json.dumps(kwargs['json'], sort_keys=True)
                elif 'data' in kwargs:
                    request_data = str(kwargs['data'])
            # GET/DELETE have no body, use empty string for HMAC
            
            # Generate auth token
            auth_token = self._generate_auth_token(request_data)
            
            # Add auth header
            headers['X-Memory-Auth'] = auth_token
        
        kwargs['headers'] = headers
        
        # Make the request
        return requests.request(method, url, **kwargs)
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self.is_running:
            logger.warning("Monitoring already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Started archiving triggers monitoring")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Stopped archiving triggers monitoring")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                self._check_triggers()
                time.sleep(self.config.check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.config.check_interval_seconds)
    
    def _check_triggers(self):
        """Check all trigger conditions"""
        try:
            # Get current working memory state
            current_state = self._get_working_memory_state()
            if not current_state:
                return
            
            # Check each trigger type
            triggered_reasons = []
            
            # Buffer size trigger
            if self._check_buffer_size_trigger(current_state):
                triggered_reasons.append(TriggerType.BUFFER_FULL)
            
            # Time-based triggers
            time_trigger = self._check_time_triggers(current_state)
            if time_trigger:
                triggered_reasons.append(time_trigger)
            
            # Topic shift trigger (if enabled)
            if (self.config.enable_topic_shift_detection and 
                self._check_topic_shift_trigger(current_state)):
                triggered_reasons.append(TriggerType.TOPIC_SHIFT)
            
            # Execute archiving if any triggers fired
            if triggered_reasons:
                self._execute_archiving(current_state, triggered_reasons)
            
            # Update tracking state
            self.previous_conversation_state = current_state
            self.last_check_time = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error checking triggers: {e}")
    
    def _get_working_memory_state(self) -> Optional[Dict]:
        """Get current state of working memory"""
        print(f"[archiving_triggers.py:190] Fetching working memory state")
        try:
            response = self._make_authenticated_request(
                'GET',
                f"{self.config.working_memory_url}/recall",
                timeout=5
            )
            
            print(f"[archiving_triggers.py:197] Response status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                # Update last activity time if there are exchanges
                context = data.get('context', [])
                if context:
                    self.last_activity_time = datetime.now(timezone.utc)
                
                return {
                    'buffer': {
                        'exchanges': context,
                        'current_size': len(context)
                    }
                }
            else:
                logger.warning(f"Working memory service returned {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting working memory state: {e}")
            return None
    
    def _check_buffer_size_trigger(self, current_state: Dict) -> bool:
        """Check if buffer size trigger should fire"""
        try:
            buffer_data = current_state.get('buffer', {})
            current_size = buffer_data.get('current_size', 0)
            
            return current_size >= self.config.max_buffer_size
            
        except Exception as e:
            logger.error(f"Error checking buffer size trigger: {e}")
            return False
    
    def _check_time_triggers(self, current_state: Dict) -> Optional[TriggerType]:
        """Check time-based triggers"""
        try:
            now = datetime.now(timezone.utc)
            
            # Check inactivity timeout
            inactivity_duration = now - self.last_activity_time
            if inactivity_duration.total_seconds() > (self.config.inactivity_timeout_minutes * 60):
                buffer_data = current_state.get('buffer', {})
                if buffer_data.get('current_size', 0) > 0:  # Only if there's content to archive
                    return TriggerType.TIME_GAP
            
            # Check maximum conversation duration
            buffer_data = current_state.get('buffer', {})
            exchanges = buffer_data.get('exchanges', [])
            
            if exchanges:
                # Get timestamp of first exchange
                first_exchange = exchanges[0]
                first_timestamp_str = first_exchange.get('timestamp')
                
                if first_timestamp_str:
                    try:
                        first_timestamp = datetime.fromisoformat(
                            first_timestamp_str.replace('Z', '+00:00')
                        )
                        conversation_duration = now - first_timestamp
                        
                        if conversation_duration.total_seconds() > (self.config.max_conversation_duration_hours * 3600):
                            return TriggerType.TIME_GAP
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse timestamp: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking time triggers: {e}")
            return None
    
    def _check_topic_shift_trigger(self, current_state: Dict) -> bool:
        """Check if conversation topic has shifted significantly"""
        # This is a placeholder for topic shift detection
        # Would require semantic analysis of conversation content
        # For now, return False (disabled)
        return False
    
    def _execute_archiving(self, current_state: Dict, trigger_reasons: List[TriggerType]):
        """Execute the archiving process"""
        try:
            # Prepare conversation data for archiving
            buffer_data = current_state.get('buffer', {})
            exchanges = buffer_data.get('exchanges', [])
            
            if not exchanges:
                logger.info("No exchanges to archive")
                return
            
            # Create conversation data structure
            conversation_data = {
                'conversation_id': f"auto_archive_{int(time.time())}",
                'exchanges': exchanges,
                'participants': self._extract_participants(exchanges),
                'archived_at': datetime.now(timezone.utc).isoformat(),
                'buffer_info': buffer_data
            }
            
            # Determine primary trigger reason
            primary_trigger = trigger_reasons[0].value
            
            # Send to episodic memory service
            archive_response = requests.post(
                f"{self.config.episodic_memory_url}/archive",
                json={
                    'conversation_data': conversation_data,
                    'trigger_reason': primary_trigger
                },
                timeout=10
            )
            
            if archive_response.status_code == 200:
                # Successfully archived, now clear working memory
                archive_result = archive_response.json()
                conversation_id = archive_result.get('conversation_id')
                
                clear_response = self._make_authenticated_request(
                    'DELETE',
                    f"{self.config.working_memory_url}/working-memory",
                    timeout=5
                )
                
                if clear_response.status_code == 200:
                    logger.info(f"Successfully archived conversation {conversation_id} and cleared working memory")
                    logger.info(f"Trigger reasons: {[t.value for t in trigger_reasons]}")
                    
                    # Update statistics
                    with self.lock:
                        for trigger in trigger_reasons:
                            self.trigger_stats[trigger] += 1
                else:
                    logger.error(f"Failed to clear working memory after archiving: {clear_response.status_code}")
            else:
                logger.error(f"Failed to archive conversation: {archive_response.status_code} - {archive_response.text}")
                
        except Exception as e:
            logger.error(f"Error executing archiving: {e}")
    
    def _extract_participants(self, exchanges: List[Dict]) -> List[str]:
        """Extract participants from exchanges"""
        participants = set()
        
        for exchange in exchanges:
            # Look for user/assistant patterns
            if 'user_message' in exchange:
                participants.add('human')
            if 'assistant_response' in exchange:
                participants.add('assistant')
            
            # Look for explicit participant information
            if 'participant' in exchange:
                participants.add(exchange['participant'])
        
        return list(participants) if participants else ['human', 'assistant']
    
    def trigger_manual_archiving(self, reason: str = "manual") -> bool:
        """Manually trigger archiving"""
        try:
            current_state = self._get_working_memory_state()
            if not current_state:
                logger.error("Could not get working memory state for manual archiving")
                return False
            
            self._execute_archiving(current_state, [TriggerType.MANUAL])
            return True
            
        except Exception as e:
            logger.error(f"Error in manual archiving: {e}")
            return False
    
    def get_trigger_stats(self) -> Dict[str, Any]:
        """Get trigger statistics"""
        with self.lock:
            return {
                'trigger_counts': {k.value: v for k, v in self.trigger_stats.items()},
                'total_triggers': sum(self.trigger_stats.values()),
                'last_check_time': self.last_check_time.isoformat(),
                'last_activity_time': self.last_activity_time.isoformat(),
                'is_monitoring': self.is_running,
                'config': {
                    'max_buffer_size': self.config.max_buffer_size,
                    'inactivity_timeout_minutes': self.config.inactivity_timeout_minutes,
                    'check_interval_seconds': self.config.check_interval_seconds
                }
            }

# Global triggers instance (will be initialized when service starts)
archiving_triggers = None

def initialize_triggers(config: Optional[TriggerConfig] = None) -> ArchivingTriggers:
    """Initialize the global triggers instance"""
    global archiving_triggers
    
    if not config:
        config = TriggerConfig()
    
    archiving_triggers = ArchivingTriggers(config)
    return archiving_triggers

def start_triggers_monitoring():
    """Start the triggers monitoring"""
    global archiving_triggers
    
    if not archiving_triggers:
        archiving_triggers = initialize_triggers()
    
    archiving_triggers.start_monitoring()

def stop_triggers_monitoring():
    """Stop the triggers monitoring"""
    global archiving_triggers
    
    if archiving_triggers:
        archiving_triggers.stop_monitoring()