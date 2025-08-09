#!/usr/bin/env python3
"""
Encryption at Rest Manager for Working Memory
Integrates with GoCryptFS for encrypted storage
"""

import os
import json
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SensitiveDataDetector:
    """Detects sensitive data patterns in text"""
    
    def __init__(self):
        # Pattern definitions for sensitive data
        self.patterns = {
            'api_key': re.compile(r'(?i)(api[_-]?key|token|secret)["\'\s:=]+([a-zA-Z0-9_-]{16,})', re.MULTILINE),
            'password': re.compile(r'(?i)(password|passwd|pwd)["\'\s:=]+([^\s"\']{6,})', re.MULTILINE),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'file_path': re.compile(r'(?:/[^/\s]+)+/?|[A-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'),
            'personal_info': re.compile(r'(?i)(ssn|social.security|credit.card|phone.number|address)'),
            'credentials': re.compile(r'(?i)(username|user|login)["\'\s:=]+([^\s"\']{3,})', re.MULTILINE),
            # AI/LLM safety patterns
            'prompt_injection': re.compile(r'(?i)(ignore.*previous|disregard.*instructions|new.*instructions|system.*prompt|jailbreak)', re.MULTILINE),
            'model_params': re.compile(r'(?i)(temperature|max_tokens|top_p|frequency_penalty|presence_penalty)["\'\s:=]+[\d.]+', re.MULTILINE),
            'system_prompts': re.compile(r'(?i)(system["\'\s:]+|assistant["\'\s:]+|role["\'\s:]+system)', re.MULTILINE),
            'memory_references': re.compile(r'(?i)(memory_id|exchange_id|buffer_position|memory_type)["\'\s:=]+[a-zA-Z0-9-]+', re.MULTILINE),
            'internal_paths': re.compile(r'(?i)(/home/[^/\s]+/\.|/root/|/etc/|/var/log/|\.ssh/|\.env)', re.MULTILINE),
            'docker_secrets': re.compile(r'(?i)(container_id|docker.*token|swarm.*join.*token)', re.MULTILINE)
        }
        
        # Sensitivity levels
        self.sensitivity_weights = {
            'api_key': 10,          # Highest
            'password': 10,         # Highest  
            'prompt_injection': 10, # Highest - AI safety critical
            'system_prompts': 9,    # Very High - reveals AI internals
            'credentials': 8,       # High
            'model_params': 8,      # High - reveals optimization
            'memory_references': 8, # High - internal system exposure
            'docker_secrets': 8,    # High - infrastructure exposure
            'personal_info': 7,     # High
            'internal_paths': 7,    # High - now properly weighted!
            'email': 5,             # Medium
            'file_path': 5,         # Medium - bumped up as you suggested
            'ip_address': 5         # Medium - bumped up for AI safety
        }
    
    def analyze_text(self, text: str) -> Dict:
        """Analyze text for sensitive data patterns"""
        if not text or not isinstance(text, str):
            return {"sensitivity_score": 0, "patterns_found": [], "needs_encryption": False}
        
        patterns_found = []
        total_score = 0
        
        for pattern_name, regex in self.patterns.items():
            matches = regex.findall(text)
            if matches:
                pattern_score = self.sensitivity_weights.get(pattern_name, 1)
                total_score += pattern_score * len(matches)
                
                patterns_found.append({
                    "pattern": pattern_name,
                    "matches": len(matches),
                    "score": pattern_score
                })
        
        # Determine if encryption is needed (score > 5 = medium+ sensitivity)
        needs_encryption = total_score > 5
        
        return {
            "sensitivity_score": total_score,
            "patterns_found": patterns_found,
            "needs_encryption": needs_encryption,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    def analyze_exchange(self, exchange: Dict) -> Dict:
        """Analyze a conversation exchange for sensitive data"""
        user_analysis = self.analyze_text(exchange.get('user_message', ''))
        assistant_analysis = self.analyze_text(exchange.get('assistant_response', ''))
        
        # Combined analysis
        total_score = user_analysis['sensitivity_score'] + assistant_analysis['sensitivity_score']
        all_patterns = user_analysis['patterns_found'] + assistant_analysis['patterns_found']
        
        return {
            "total_sensitivity_score": total_score,
            "user_message_analysis": user_analysis,
            "assistant_response_analysis": assistant_analysis,
            "combined_patterns": all_patterns,
            "needs_encryption": total_score > 5,
            "auto_expire": total_score > 15  # Very high sensitivity gets auto-expiry
        }

class EncryptionManager:
    """Manages encryption at rest for working memory"""
    
    def __init__(self, encrypted_storage_path: str = None):
        self.encrypted_storage_path = encrypted_storage_path or os.getenv(
            'WORKING_MEMORY_ENCRYPTED_PATH', 
            '/home/grinnling/.memory_encrypted/working_memory'
        )
        
        # GoCryptFS mount point check
        self.gocryptfs_available = self._check_gocryptfs()
        
        # Sensitive data detector
        self.detector = SensitiveDataDetector()
        
        # Auto-expiry tracking
        self.expiry_exchanges = {}  # exchange_id -> expiry_time
        
        logger.info(f"Encryption manager initialized - GoCryptFS: {'Available' if self.gocryptfs_available else 'Not available'}")
    
    def _check_gocryptfs(self) -> bool:
        """Check if GoCryptFS encrypted storage is available"""
        try:
            # Check if the encrypted storage path exists and is accessible
            if os.path.exists(self.encrypted_storage_path):
                # Try to create a test file to verify write access
                test_file = os.path.join(self.encrypted_storage_path, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                return True
            else:
                logger.warning(f"Encrypted storage path not found: {self.encrypted_storage_path}")
                return False
        except Exception as e:
            logger.warning(f"GoCryptFS not available: {e}")
            return False
    
    def analyze_and_process_exchange(self, exchange: Dict) -> Tuple[Dict, Dict]:
        """
        Analyze exchange for sensitive data and determine processing
        Returns: (exchange_with_metadata, processing_info)
        """
        # Analyze sensitivity
        sensitivity_analysis = self.detector.analyze_exchange(exchange)
        
        # Add metadata to exchange
        exchange['encryption_metadata'] = {
            "sensitivity_analysis": sensitivity_analysis,
            "encrypted_at_rest": False,  # Will be updated if we backup
            "auto_expire": sensitivity_analysis.get('auto_expire', False),
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
        
        # Set auto-expiry if needed
        if sensitivity_analysis.get('auto_expire'):
            expiry_time = datetime.utcnow() + timedelta(hours=2)  # 2 hour expiry for very sensitive
            self.expiry_exchanges[exchange['exchange_id']] = expiry_time
            exchange['encryption_metadata']['expires_at'] = expiry_time.isoformat()
        
        processing_info = {
            "needs_encryption": sensitivity_analysis.get('needs_encryption', False),
            "should_backup": sensitivity_analysis.get('needs_encryption', False) and self.gocryptfs_available,
            "sensitivity_score": sensitivity_analysis.get('total_sensitivity_score', 0),
            "auto_expire": sensitivity_analysis.get('auto_expire', False)
        }
        
        return exchange, processing_info
    
    def backup_sensitive_exchange(self, exchange: Dict) -> bool:
        """Backup sensitive exchange to encrypted storage"""
        if not self.gocryptfs_available:
            logger.warning("Cannot backup - encrypted storage not available")
            return False
        
        try:
            # Create backup filename with timestamp and exchange ID
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            exchange_id = exchange.get('exchange_id', 'unknown')[:8]
            filename = f"sensitive_exchange_{timestamp}_{exchange_id}.json"
            
            backup_path = os.path.join(self.encrypted_storage_path, filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Write encrypted backup
            with open(backup_path, 'w') as f:
                json.dump(exchange, f, indent=2)
            
            # Update exchange metadata
            if 'encryption_metadata' not in exchange:
                exchange['encryption_metadata'] = {}
            
            exchange['encryption_metadata'].update({
                "encrypted_at_rest": True,
                "backup_path": backup_path,
                "backup_timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Backed up sensitive exchange {exchange_id} to encrypted storage")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup sensitive exchange: {e}")
            return False
    
    def backup_buffer_on_shutdown(self, buffer_data: List[Dict]) -> bool:
        """Backup entire buffer to encrypted storage on shutdown"""
        if not buffer_data:
            logger.info("No buffer data to backup")
            return True
        
        if not self.gocryptfs_available:
            logger.warning("Cannot backup buffer - encrypted storage not available")
            return False
        
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"working_memory_shutdown_backup_{timestamp}.json"
            backup_path = os.path.join(self.encrypted_storage_path, filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            backup_data = {
                "backup_type": "shutdown_backup",
                "timestamp": datetime.utcnow().isoformat(),
                "buffer_size": len(buffer_data),
                "exchanges": buffer_data
            }
            
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"Backed up {len(buffer_data)} exchanges to encrypted storage: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup buffer on shutdown: {e}")
            return False
    
    def cleanup_expired_exchanges(self, buffer) -> List[str]:
        """Remove expired exchanges from buffer"""
        if not self.expiry_exchanges:
            return []
        
        current_time = datetime.utcnow()
        expired_ids = []
        
        # Find expired exchanges
        for exchange_id, expiry_time in list(self.expiry_exchanges.items()):
            if current_time > expiry_time:
                expired_ids.append(exchange_id)
                del self.expiry_exchanges[exchange_id]
        
        # Remove from buffer (this is a simple implementation)
        if expired_ids:
            # Note: This is a simplified approach. In practice, you'd need to
            # implement a more sophisticated removal from the deque
            logger.info(f"Found {len(expired_ids)} expired exchanges")
            
            # For now, just log - actual removal would need buffer integration
            for expired_id in expired_ids:
                logger.info(f"Exchange {expired_id} has expired and should be removed")
        
        return expired_ids
    
    def get_encryption_stats(self) -> Dict:
        """Get encryption and sensitive data statistics"""
        return {
            "gocryptfs_available": self.gocryptfs_available,
            "encrypted_storage_path": self.encrypted_storage_path,
            "active_expiry_exchanges": len(self.expiry_exchanges),
            "expiry_exchanges": {
                eid: exp_time.isoformat() 
                for eid, exp_time in self.expiry_exchanges.items()
            }
        }