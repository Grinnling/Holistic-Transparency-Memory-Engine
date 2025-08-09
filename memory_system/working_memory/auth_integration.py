#!/usr/bin/env python3
"""
Security and Audit Integration for Working Memory Service
Integrates with existing MCP auth system
"""

import os
import sys
import logging
from functools import wraps
from flask import request, jsonify, g
import time
import uuid

# Add MCP logger auth path to system path
mcp_auth_path = os.path.join(os.path.dirname(__file__), '..', 'mcp_logger')
sys.path.append(mcp_auth_path)

try:
    # Import from your existing MCP auth system
    from auth import MemoryLogger, require_auth
    MCP_AUTH_AVAILABLE = True
except ImportError:
    # Fallback if MCP auth not available
    MCP_AUTH_AVAILABLE = False
    print("Warning: MCP auth system not available, using fallback")

# Create working memory specific loggers
working_memory_audit = MemoryLogger("working_memory_audit") if MCP_AUTH_AVAILABLE else None
working_memory_security = MemoryLogger("working_memory_security") if MCP_AUTH_AVAILABLE else None

class WorkingMemoryAuth:
    """Authentication and audit for working memory operations"""
    
    def __init__(self):
        self.request_counts = {}  # Simple rate limiting
        self.rate_limit = int(os.getenv('WORKING_MEMORY_RATE_LIMIT', '60'))  # 60 requests per minute
        self.rate_window = 60  # 1 minute window
        
    def validate_exchange_data(self, data):
        """Validate and sanitize exchange data"""
        if not isinstance(data, dict):
            return False, "Data must be a JSON object"
        
        user_message = data.get('user_message', '').strip()
        assistant_response = data.get('assistant_response', '').strip()
        
        # Basic validation
        if not user_message or not assistant_response:
            return False, "Both user_message and assistant_response are required"
        
        # Length limits (prevent memory spam AND context overflow attacks)
        if len(user_message) > 10000:
            return False, "User message too long (max 10,000 characters)"
        
        if len(assistant_response) > 50000:
            return False, "Assistant response too long (max 50,000 characters)"
        
        # AI Safety: Check for repeated patterns (context stuffing attack)
        user_stuffing = self._detect_pattern_stuffing(user_message)
        assistant_stuffing = self._detect_pattern_stuffing(assistant_response)
        
        if user_stuffing or assistant_stuffing:
            # Don't reject immediately - validate the content
            validation_result = self._validate_suspicious_content(
                user_message if user_stuffing else assistant_response,
                "user" if user_stuffing else "assistant"
            )
            
            if validation_result['action'] == 'reject':
                return False, f"Content validation failed: {validation_result['reason']}"
            elif validation_result['action'] == 'compress':
                # Compress/summarize the content instead of rejecting
                if user_stuffing:
                    data['user_message'] = validation_result['processed_content']
                    data['original_length'] = len(user_message)
                else:
                    data['assistant_response'] = validation_result['processed_content']
                    data['original_length'] = len(assistant_response)
                
                if working_memory_security:
                    working_memory_security.log_info("CONTENT_COMPRESSED", 
                        f"Large {validation_result['content_type']} content compressed", {
                        "original_length": validation_result.get('original_length', 0),
                        "compressed_length": len(validation_result['processed_content']),
                        "pattern_type": validation_result.get('pattern_type', 'unknown')
                    })
        
        # Sanitize (basic - could be enhanced)
        data['user_message'] = self._sanitize_text(user_message)
        data['assistant_response'] = self._sanitize_text(assistant_response)
        
        return True, "Valid"
    
    def _sanitize_text(self, text):
        """Basic text sanitization"""
        # Remove control characters except newlines and tabs
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        return sanitized.strip()
    
    def _detect_pattern_stuffing(self, text):
        """Detect repeated patterns that could be context stuffing attacks"""
        if len(text) < 100:
            return False
        
        # Check for excessive repetition of short patterns
        chunks = [text[i:i+20] for i in range(0, len(text)-20, 10)]
        chunk_counts = {}
        for chunk in chunks:
            chunk_counts[chunk] = chunk_counts.get(chunk, 0) + 1
        
        # If any 20-char pattern repeats more than 10 times, it's suspicious
        max_repetitions = max(chunk_counts.values()) if chunk_counts else 0
        return max_repetitions > 10
    
    def _validate_suspicious_content(self, content, content_type):
        """Smart validation for suspicious content instead of just rejecting"""
        
        # Quick heuristics to differentiate legitimate docs from attacks
        legitimate_indicators = [
            # Technical documentation patterns
            content.count('\n') > 20,  # Multi-line document
            any(word in content.lower() for word in ['documentation', 'reference', 'specification', 'manual', 'guide']),
            content.count('.') > 50,   # Sentences/structured content
            content.count(' ') / len(content) > 0.15,  # Normal word spacing
            # Code/config patterns
            any(pattern in content for pattern in ['{', '}', '[]', '()', 'def ', 'class ', 'function']),
        ]
        
        attack_indicators = [
            # Malicious patterns
            content.count('ignore') > 5,
            content.count('system') > 10 and len(content) < 1000,  # Short but lots of "system"
            len(set(content.split()[:100])) < 10,  # Very low vocabulary diversity
            content.lower().count('jailbreak') > 0,
        ]
        
        legitimate_score = sum(legitimate_indicators)
        attack_score = sum(attack_indicators)
        
        if attack_score > legitimate_score:
            return {
                'action': 'reject',
                'reason': 'Content appears to be malicious',
                'attack_score': attack_score,
                'legitimate_score': legitimate_score
            }
        elif len(content) > 25000 and legitimate_score >= 2:  # Large but seems legit
            # Compress/summarize instead of rejecting
            compressed = self._compress_large_content(content)
            return {
                'action': 'compress',
                'processed_content': compressed,
                'original_length': len(content),
                'content_type': content_type,
                'pattern_type': 'large_document'
            }
        else:
            # Allow through but flag for monitoring
            return {
                'action': 'allow',
                'reason': 'Content appears legitimate but flagged for review'
            }
    
    def _compress_large_content(self, content):
        """Simple compression for large legitimate content"""
        lines = content.split('\n')
        
        # Keep first 20 lines, sample middle, keep last 10 lines
        if len(lines) > 50:
            compressed_lines = (
                lines[:20] + 
                [f"... [COMPRESSED: {len(lines) - 30} lines omitted] ..."] +
                lines[-10:]
            )
            return '\n'.join(compressed_lines)
        
        # If not line-based, do character truncation with summary
        if len(content) > 10000:
            return (
                content[:5000] + 
                f"\n\n... [COMPRESSED: {len(content) - 7000} characters omitted] ...\n\n" +
                content[-2000:]
            )
        
        return content
    
    def check_rate_limit(self, client_ip):
        """Simple rate limiting check"""
        current_time = int(time.time())
        window_start = current_time - self.rate_window
        
        # Clean old entries
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                timestamp for timestamp in self.request_counts[client_ip]
                if timestamp > window_start
            ]
        else:
            self.request_counts[client_ip] = []
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.rate_limit:
            return False
        
        # Add current request
        self.request_counts[client_ip].append(current_time)
        return True

# Global auth instance
working_memory_auth = WorkingMemoryAuth()

def audit_memory_operation(operation_type):
    """Decorator to audit memory operations"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not MCP_AUTH_AVAILABLE or not working_memory_audit:
                return f(*args, **kwargs)
            
            request_id = getattr(g, 'request_id', str(uuid.uuid4()))
            client_ip = request.remote_addr
            start_time = time.time()
            
            # Pre-operation audit
            working_memory_audit.log_info("MEMORY_OPERATION_START", f"Starting {operation_type}", {
                "request_id": request_id,
                "client_ip": client_ip,
                "operation": operation_type,
                "timestamp": start_time
            })
            
            try:
                result = f(*args, **kwargs)
                end_time = time.time()
                
                # Success audit
                working_memory_audit.log_info("MEMORY_OPERATION_SUCCESS", f"Completed {operation_type}", {
                    "request_id": request_id,
                    "operation": operation_type,
                    "duration": f"{end_time - start_time:.3f}s",
                    "status": "success"
                })
                
                return result
                
            except Exception as e:
                end_time = time.time()
                
                # Error audit
                working_memory_audit.log_error("MEMORY_OPERATION_ERROR", f"Failed {operation_type}", {
                    "request_id": request_id,
                    "operation": operation_type,
                    "duration": f"{end_time - start_time:.3f}s",
                    "error": str(e),
                    "status": "error"
                })
                
                raise
        
        return decorated_function
    return decorator

def working_memory_security_check(f):
    """Security check decorator for working memory"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        
        # Rate limiting
        if not working_memory_auth.check_rate_limit(client_ip):
            if working_memory_security:
                working_memory_security.log_warning("RATE_LIMIT_EXCEEDED", f"Rate limit exceeded for {client_ip}")
            
            return jsonify({
                'status': 'error',
                'error': 'Rate limit exceeded',
                'code': 'RATE_LIMIT_EXCEEDED'
            }), 429
        
        # Validate request data for POST requests
        if request.method == 'POST':
            data = request.get_json()
            if data:
                valid, message = working_memory_auth.validate_exchange_data(data)
                if not valid:
                    if working_memory_security:
                        working_memory_security.log_warning("INVALID_REQUEST_DATA", f"Invalid data from {client_ip}: {message}")
                    
                    return jsonify({
                        'status': 'error',
                        'error': f'Invalid request data: {message}',
                        'code': 'INVALID_DATA'
                    }), 400
        
        return f(*args, **kwargs)
    
    return decorated_function

# Convenience decorator that combines auth, security, and audit
def secure_memory_endpoint(operation_type):
    """Combined decorator for secure memory endpoints"""
    def decorator(f):
        if MCP_AUTH_AVAILABLE:
            # Use MCP auth system
            @require_auth
            @working_memory_security_check
            @audit_memory_operation(operation_type)
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
        else:
            # Fallback without MCP auth
            @working_memory_security_check
            @audit_memory_operation(operation_type)
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator