#!/usr/bin/env python3
"""
Memory Lifecycle Manager for Working Memory
Handles archival to episodic memory based on significance and age
"""

import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import requests

logger = logging.getLogger(__name__)

class ArchivalReason(Enum):
    """Reasons for archiving exchanges"""
    BUFFER_FULL = "buffer_full"
    SIGNIFICANCE_HIGH = "significance_high"  
    MANUAL_ARCHIVE = "manual_archive"
    SENSITIVITY_EXPIRY = "sensitivity_expiry"
    TIME_BASED = "time_based"

class SignificanceAnalyzer:
    """Analyzes conversation significance for archival decisions"""
    
    def __init__(self):
        # Significance indicators with weights
        self.significance_patterns = {
            # High significance patterns
            'decision_making': {
                'patterns': ['decided', 'conclusion', 'resolved', 'agreed', 'determined'],
                'weight': 8
            },
            'problem_solving': {
                'patterns': ['solution', 'fixed', 'solved', 'resolved', 'error', 'bug', 'issue'],
                'weight': 7
            },
            'learning_insights': {
                'patterns': ['learned', 'discovered', 'insight', 'understanding', 'realization'],
                'weight': 6
            },
            'code_implementation': {
                'patterns': ['implemented', 'created', 'built', 'deployed', 'function', 'class'],
                'weight': 6
            },
            'important_info': {
                'patterns': ['important', 'critical', 'key', 'essential', 'crucial'],
                'weight': 5
            },
            # Medium significance
            'configuration': {
                'patterns': ['config', 'setting', 'parameter', 'environment', 'variable'],
                'weight': 4
            },
            'documentation': {
                'patterns': ['documented', 'explained', 'described', 'outlined'],
                'weight': 3
            },
            # Lower significance
            'routine_tasks': {
                'patterns': ['checked', 'listed', 'viewed', 'showed', 'displayed'],
                'weight': 2
            },
            # Consequence impact patterns
            'production_impact': {
                'patterns': ['production', 'live', 'users affected', 'outage', 'downtime', 'service down'],
                'weight': 9  # Very high - affects real users
            },
            'security_consequence': {
                'patterns': ['vulnerability', 'exposed', 'unauthorized', 'breach', 'compromised', 'leaked'],
                'weight': 9  # Very high - security critical
            },
            'data_consequence': {
                'patterns': ['lost', 'corrupted', 'deleted', 'missing', 'destroyed', 'wiped'],
                'weight': 8  # High - data loss is serious
            },
            'system_failure': {
                'patterns': ['crashed', 'failed', 'broken', 'not working', 'dead', 'unresponsive'],
                'weight': 7  # High - system reliability
            },
            # Time invested indicators
            'debugging_session': {
                'patterns': ['debugging', 'troubleshooting', 'still not working', 'tried again', 'another approach'],
                'weight': 6  # High - indicates significant time investment
            },
            'research_intensive': {
                'patterns': ['researching', 'looking into', 'investigating', 'need to find out', 'digging deeper'],
                'weight': 5  # Medium-high - research takes time
            },
            'iterative_work': {
                'patterns': ['iteration', 'attempt', 'trying different', 'version', 'round'],
                'weight': 4  # Medium - multiple attempts = time invested
            },
            # Learning curve difficulty indicators
            'confusion_struggle': {
                'patterns': ['confused', 'not sure', 'don\'t understand', 'unclear', 'lost', 'stuck'],
                'weight': 5  # Medium-high - difficulty learning indicates importance
            },
            'breakthrough_learning': {
                'patterns': ['oh!', 'i see', 'that makes sense', 'got it', 'now i understand', 'finally'],
                'weight': 6  # High - breakthrough moments are memorable
            },
            'complex_explanation': {
                'patterns': ['complex', 'complicated', 'intricate', 'detailed explanation', 'step by step'],
                'weight': 4  # Medium - complexity indicates learning curve
            }
        }
        
        # Context-based significance multipliers
        self.context_multipliers = {
            'first_time': 1.5,      # First mention of a topic
            'complex_task': 1.3,    # Multi-step processes
            'error_resolution': 1.4, # Bug fixes and troubleshooting
            'system_config': 1.2,   # System configuration changes
            'high_consequence': 1.6, # Production/security impact amplifies everything
            'learning_breakthrough': 1.3, # Breakthrough moments are extra memorable
        }
    
    def analyze_exchange_significance(self, exchange: Dict) -> Dict:
        """Analyze the significance of a conversation exchange"""
        user_message = exchange.get('user_message', '').lower()
        assistant_response = exchange.get('assistant_response', '').lower()
        context_used = exchange.get('context_used', [])
        
        total_score = 0
        matched_patterns = []
        
        # Analyze both messages for significance patterns
        combined_text = f"{user_message} {assistant_response}"
        
        for category, config in self.significance_patterns.items():
            pattern_matches = 0
            for pattern in config['patterns']:
                pattern_matches += combined_text.count(pattern)
            
            if pattern_matches > 0:
                category_score = pattern_matches * config['weight']
                total_score += category_score
                matched_patterns.append({
                    'category': category,
                    'matches': pattern_matches,
                    'score': category_score
                })
        
        # Apply context multipliers
        multiplier = 1.0
        applied_multipliers = []
        
        # Check for first-time topics (simple heuristic)
        if any(word in combined_text for word in ['first', 'initial', 'new', 'start']):
            multiplier *= self.context_multipliers['first_time']
            applied_multipliers.append('first_time')
        
        # Check for complex tasks (multi-step indicators)
        if combined_text.count('then') > 2 or combined_text.count('next') > 2:
            multiplier *= self.context_multipliers['complex_task']
            applied_multipliers.append('complex_task')
        
        # Check for error resolution
        if any(word in combined_text for word in ['error', 'failed', 'fix', 'debug']):
            multiplier *= self.context_multipliers['error_resolution']
            applied_multipliers.append('error_resolution')
        
        # Check for system configuration
        if any(word in combined_text for word in ['config', 'setup', 'install', 'deploy']):
            multiplier *= self.context_multipliers['system_config']
            applied_multipliers.append('system_config')
        
        # Check for high consequence situations
        if any(word in combined_text for word in ['production', 'live', 'vulnerability', 'breach', 'outage', 'lost', 'corrupted']):
            multiplier *= self.context_multipliers['high_consequence']
            applied_multipliers.append('high_consequence')
        
        # Check for learning breakthroughs
        if any(word in combined_text for word in ['oh!', 'i see', 'got it', 'finally', 'breakthrough', 'understand']):
            multiplier *= self.context_multipliers['learning_breakthrough']
            applied_multipliers.append('learning_breakthrough')
        
        final_score = total_score * multiplier
        
        # Determine significance level
        if final_score >= 20:
            significance_level = "very_high"
        elif final_score >= 10:
            significance_level = "high"
        elif final_score >= 5:
            significance_level = "medium"
        else:
            significance_level = "low"
        
        return {
            'significance_score': final_score,
            'significance_level': significance_level,
            'base_score': total_score,
            'multiplier': multiplier,
            'matched_patterns': matched_patterns,
            'applied_multipliers': applied_multipliers,
            'analysis_timestamp': datetime.utcnow().isoformat()
        }

class LifecycleManager:
    """Manages working memory lifecycle and archival to episodic memory"""
    
    def __init__(self, episodic_service_url: str = None):
        self.episodic_service_url = episodic_service_url or os.getenv(
            'EPISODIC_MEMORY_URL', 
            'http://localhost:8003'
        )
        
        # Archival thresholds
        self.archival_config = {
            'significance_threshold': float(os.getenv('ARCHIVAL_SIGNIFICANCE_THRESHOLD', '10.0')),
            'max_age_hours': int(os.getenv('ARCHIVAL_MAX_AGE_HOURS', '24')),
            'buffer_full_threshold': float(os.getenv('ARCHIVAL_BUFFER_THRESHOLD', '0.9')),  # 90% full
        }
        
        self.significance_analyzer = SignificanceAnalyzer()
        
        # Track archival statistics
        self.archival_stats = {
            'total_archived': 0,
            'by_reason': {},
            'by_significance': {},
            'last_archival': None
        }
        
        logger.info(f"Lifecycle manager initialized - Episodic service: {self.episodic_service_url}")
    
    def should_archive_exchange(self, exchange: Dict, buffer_status: Dict) -> Tuple[bool, ArchivalReason, Dict]:
        """Determine if an exchange should be archived"""
        
        # Analyze significance
        significance_analysis = self.significance_analyzer.analyze_exchange_significance(exchange)
        
        # Check archival conditions
        archival_decision = {
            'should_archive': False,
            'reason': None,
            'significance_analysis': significance_analysis,
            'buffer_utilization': buffer_status.get('current_size', 0) / buffer_status.get('max_size', 1)
        }
        
        # High significance exchanges get archived immediately
        if significance_analysis['significance_score'] >= self.archival_config['significance_threshold']:
            archival_decision.update({
                'should_archive': True,
                'reason': ArchivalReason.SIGNIFICANCE_HIGH,
                'priority': 'high'
            })
            return True, ArchivalReason.SIGNIFICANCE_HIGH, archival_decision
        
        # Buffer nearly full - archive older, less significant items
        if archival_decision['buffer_utilization'] >= self.archival_config['buffer_full_threshold']:
            archival_decision.update({
                'should_archive': True,
                'reason': ArchivalReason.BUFFER_FULL,
                'priority': 'medium'
            })
            return True, ArchivalReason.BUFFER_FULL, archival_decision
        
        # Check age-based archival
        exchange_time = datetime.fromisoformat(exchange.get('timestamp', datetime.utcnow().isoformat()))
        age_hours = (datetime.now(timezone.utc) - exchange_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        
        if age_hours > self.archival_config['max_age_hours']:
            archival_decision.update({
                'should_archive': True,
                'reason': ArchivalReason.TIME_BASED,
                'priority': 'low',
                'age_hours': age_hours
            })
            return True, ArchivalReason.TIME_BASED, archival_decision
        
        return False, None, archival_decision
    
    def archive_exchange_to_episodic(self, exchange: Dict, reason: ArchivalReason, metadata: Dict = None) -> bool:
        """Archive an exchange to episodic memory"""
        
        try:
            # Prepare archival payload
            archival_payload = {
                'type': 'episodic',
                'source': 'working_memory',
                'archival_reason': reason.value,
                'archival_timestamp': datetime.utcnow().isoformat(),
                'exchange': exchange,
                'metadata': metadata or {}
            }
            
            # Add lifecycle metadata
            archival_payload['metadata'].update({
                'working_memory_position': exchange.get('annotations', {}).get('buffer_position'),
                'working_memory_timestamp': exchange.get('timestamp'),
                'archival_priority': metadata.get('priority', 'medium') if metadata else 'medium'
            })
            
            # Send to episodic memory service
            response = requests.post(
                f"{self.episodic_service_url}/store",
                json=archival_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                # Update statistics
                self.archival_stats['total_archived'] += 1
                self.archival_stats['by_reason'][reason.value] = self.archival_stats['by_reason'].get(reason.value, 0) + 1
                self.archival_stats['last_archival'] = datetime.utcnow().isoformat()
                
                if metadata and 'significance_analysis' in metadata:
                    sig_level = metadata['significance_analysis'].get('significance_level', 'unknown')
                    self.archival_stats['by_significance'][sig_level] = self.archival_stats['by_significance'].get(sig_level, 0) + 1
                
                logger.info(f"Successfully archived exchange {exchange.get('exchange_id', 'unknown')} to episodic memory", extra={
                    'reason': reason.value,
                    'significance_score': metadata.get('significance_analysis', {}).get('significance_score', 0) if metadata else 0
                })
                
                return True
            else:
                logger.error(f"Failed to archive exchange - Episodic service returned {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.warning("Cannot archive exchange - Episodic memory service unavailable")
            return False
        except Exception as e:
            logger.error(f"Error archiving exchange to episodic memory: {e}")
            return False
    
    def get_archival_candidates(self, buffer_exchanges: List[Dict], buffer_status: Dict) -> List[Tuple[Dict, ArchivalReason, Dict]]:
        """Get list of exchanges that should be archived"""
        candidates = []
        
        for exchange in buffer_exchanges:
            should_archive, reason, metadata = self.should_archive_exchange(exchange, buffer_status)
            if should_archive:
                candidates.append((exchange, reason, metadata))
        
        # Sort by priority: high significance first, then buffer management, then age-based
        priority_order = {
            ArchivalReason.SIGNIFICANCE_HIGH: 1,
            ArchivalReason.SENSITIVITY_EXPIRY: 2,
            ArchivalReason.BUFFER_FULL: 3,
            ArchivalReason.TIME_BASED: 4,
            ArchivalReason.MANUAL_ARCHIVE: 5
        }
        
        candidates.sort(key=lambda x: priority_order.get(x[1], 10))
        return candidates
    
    def perform_lifecycle_maintenance(self, buffer_exchanges: List[Dict], buffer_status: Dict) -> Dict:
        """Perform routine lifecycle maintenance"""
        maintenance_results = {
            'archived_count': 0,
            'archived_exchanges': [],
            'failed_archives': [],
            'maintenance_timestamp': datetime.utcnow().isoformat()
        }
        
        # Get archival candidates
        candidates = self.get_archival_candidates(buffer_exchanges, buffer_status)
        
        if not candidates:
            logger.info("No exchanges require archival")
            return maintenance_results
        
        logger.info(f"Found {len(candidates)} exchanges for archival")
        
        # Archive each candidate
        for exchange, reason, metadata in candidates:
            success = self.archive_exchange_to_episodic(exchange, reason, metadata)
            
            if success:
                maintenance_results['archived_count'] += 1
                maintenance_results['archived_exchanges'].append({
                    'exchange_id': exchange.get('exchange_id'),
                    'reason': reason.value,
                    'significance_score': metadata.get('significance_analysis', {}).get('significance_score', 0)
                })
            else:
                maintenance_results['failed_archives'].append({
                    'exchange_id': exchange.get('exchange_id'),
                    'reason': reason.value
                })
        
        return maintenance_results
    
    def get_lifecycle_stats(self) -> Dict:
        """Get lifecycle management statistics"""
        return {
            'archival_stats': self.archival_stats,
            'archival_config': self.archival_config,
            'episodic_service_url': self.episodic_service_url,
            'service_status': self._check_episodic_service_health()
        }
    
    def _check_episodic_service_health(self) -> Dict:
        """Check if episodic memory service is available"""
        try:
            response = requests.get(f"{self.episodic_service_url}/health", timeout=5)
            return {
                'available': response.status_code == 200,
                'status_code': response.status_code,
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }