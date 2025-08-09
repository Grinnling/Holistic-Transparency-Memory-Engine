#!/usr/bin/env python3
"""
Authentication and Security module for MCP Memory Logger
Integrates with existing middleware security framework
"""

import logging
import os
import time
import hashlib
import hmac
from functools import wraps
from flask import request, jsonify, g
from enum import Enum, auto
from typing import Dict, Any, Optional

class MemoryErrorCodes(Enum):
    """Error codes for memory operations"""
    AUTH_FAILED = auto()
    INVALID_TOKEN = auto()
    RATE_LIMIT_EXCEEDED = auto()
    SECURITY_VIOLATION = auto()
    UNAUTHORIZED_ACCESS = auto()
    PROMPT_INJECTION = auto()
    CONTEXT_OVERFLOW = auto()
    SYSTEM_BOUNDARY_VIOLATION = auto()

class MemoryLogger:
    """Custom logger for memory operations (matches your existing pattern)"""
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Add console handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_error(self, code: str, message: str, context: Dict[str, Any] = None):
        """Log an error with context"""
        self.logger.error(f"{code}: {message}", extra={"context": context})
    
    def log_info(self, code: str, message: str, context: Dict[str, Any] = None):
        """Log an informational message with context"""
        self.logger.info(f"{code}: {message}", extra={"context": context})
    
    def log_warning(self, code: str, message: str, context: Dict[str, Any] = None):
        """Log a warning with context"""
        self.logger.warning(f"{code}: {message}", extra={"context": context})

# Create specialized loggers (matching your pattern)
auth_logger = MemoryLogger("memory_auth")
security_logger = MemoryLogger("memory_security")
audit_logger = MemoryLogger("memory_audit")

class MemoryAuth:
    """Authentication handler for memory operations"""
    
    def __init__(self):
        # Load from environment (following your pattern)
        self.auth_key = os.getenv('MEMORY_AUTH_KEY', 'development_key_change_in_production')
        self.enable_auth = os.getenv('MEMORY_AUTH_ENABLED', 'true').lower() == 'true'
        self.audit_enabled = os.getenv('MEMORY_AUDIT_ENABLED', 'true').lower() == 'true'
        
        # Rate limiting (simple implementation for now)
        self.rate_limit_requests = int(os.getenv('MEMORY_RATE_LIMIT', '100'))
        self.rate_limit_window = int(os.getenv('MEMORY_RATE_WINDOW', '3600'))  # 1 hour
        self.request_counts = {}
        
        auth_logger.log_info("AUTH_INIT", "Memory authentication initialized", {
            "auth_enabled": self.enable_auth,
            "audit_enabled": self.audit_enabled,
            "rate_limit": f"{self.rate_limit_requests}/{self.rate_limit_window}s"
        })
    
    def generate_token(self, data: str) -> str:
        """Generate HMAC token for request validation"""
        timestamp = str(int(time.time()))
        message = f"{data}:{timestamp}"
        signature = hmac.new(
            self.auth_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{signature}:{timestamp}"
    
    def validate_token(self, token: str, data: str, max_age: int = 300) -> bool:
        """Validate HMAC token (5 minute window by default)"""
        print(f"[auth.py:93] Validating token, data length: {len(data)}, token: {token[:20]}...")
        try:
            signature, timestamp = token.split(':')
            request_time = int(timestamp)
            current_time = int(time.time())
            
            # Check if token is too old
            age = current_time - request_time
            print(f"[auth.py:100] Token age: {age}s (max: {max_age}s)")
            if age > max_age:
                auth_logger.log_warning("TOKEN_EXPIRED", f"Token expired: {age}s old")
                return False
            
            # Recreate expected signature
            message = f"{data}:{timestamp}"
            expected_signature = hmac.new(
                self.auth_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison
            is_valid = hmac.compare_digest(signature, expected_signature)
            print(f"[auth.py:115] Token validation result: {is_valid}")
            return is_valid
            
        except (ValueError, TypeError) as e:
            auth_logger.log_error("TOKEN_INVALID", f"Token validation failed: {e}")
            return False
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Simple rate limiting check"""
        current_time = int(time.time())
        window_start = current_time - self.rate_limit_window
        
        # Clean old entries
        self.request_counts = {
            ip: [(timestamp, count) for timestamp, count in requests if timestamp > window_start]
            for ip, requests in self.request_counts.items()
        }
        
        # Count requests in current window
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        current_requests = sum(count for _, count in self.request_counts[client_ip])
        
        if current_requests >= self.rate_limit_requests:
            security_logger.log_warning("RATE_LIMIT_EXCEEDED", f"Rate limit exceeded for {client_ip}")
            return False
        
        # Add current request
        self.request_counts[client_ip].append((current_time, 1))
        return True
    
    def audit_request(self, endpoint: str, data: Any = None, result: str = "SUCCESS"):
        """Audit log for memory operations"""
        if not self.audit_enabled:
            return
            
        client_ip = request.remote_addr if request else "unknown"
        request_id = getattr(g, 'request_id', 'unknown')
        
        audit_logger.log_info("MEMORY_AUDIT", f"Operation: {endpoint}", {
            "request_id": request_id,
            "client_ip": client_ip,
            "endpoint": endpoint,
            "result": result,
            "timestamp": time.time(),
            "data_present": data is not None
        })

def require_auth(f):
    """Decorator to require authentication on memory endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = MemoryAuth()
        
        # Skip auth if disabled (development mode)
        if not auth.enable_auth:
            print(f"[auth.py:168] Auth disabled, skipping check for {request.method} {request.path}")
            return f(*args, **kwargs)
        
        client_ip = request.remote_addr
        print(f"[auth.py:172] Auth check for {request.method} {request.path} from {client_ip}")
        
        # Rate limiting check
        if not auth.check_rate_limit(client_ip):
            print(f"[auth.py:176] Rate limit exceeded for {client_ip}")
            auth.audit_request(request.endpoint, None, "RATE_LIMITED")
            return jsonify({
                'error': 'Rate limit exceeded',
                'code': MemoryErrorCodes.RATE_LIMIT_EXCEEDED.name
            }), 429
        
        # Check for auth header
        auth_header = request.headers.get('X-Memory-Auth')
        print(f"[auth.py:184] Auth header present: {bool(auth_header)}, Content-Type: {request.content_type}")
        if not auth_header:
            auth.audit_request(request.endpoint, None, "NO_AUTH_HEADER")
            return jsonify({
                'error': 'Authentication required',
                'code': MemoryErrorCodes.AUTH_FAILED.name
            }), 401
        
        # Validate token
        # Only get request data for requests that actually have bodies
        if request.method in ['POST', 'PUT', 'PATCH']:
            request_data = request.get_data(as_text=True) or ""
            print(f"[auth.py:196] Got request data for {request.method}, length: {len(request_data)}")
        else:
            request_data = ""  # GET/DELETE/HEAD have no body
            print(f"[auth.py:199] No request body for {request.method}, using empty string for HMAC")
        
        print(f"[auth.py:201] Validating token...")
        if not auth.validate_token(auth_header, request_data):
            print(f"[auth.py:203] Token validation failed")
            auth.audit_request(request.endpoint, None, "INVALID_TOKEN")
            return jsonify({
                'error': 'Invalid authentication token',
                'code': MemoryErrorCodes.INVALID_TOKEN.name
            }), 401
        
        # Authentication successful
        # Only get JSON for requests that actually have bodies
        audit_data = None
        if request.method in ['POST', 'PUT', 'PATCH'] and request.is_json:
            audit_data = request.get_json()
        auth.audit_request(request.endpoint, audit_data, "SUCCESS")
        return f(*args, **kwargs)
    
    return decorated_function

def init_security(app):
    """Initialize security for Flask app (following your Talisman pattern)"""
    
    # Add security headers (simplified version of your Talisman setup)
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
    
    # Error handlers for security-related errors
    @app.errorhandler(401)
    def unauthorized(error):
        security_logger.log_warning("UNAUTHORIZED_ACCESS", f"401 error: {error}")
        return jsonify({
            'error': 'Unauthorized access',
            'code': MemoryErrorCodes.UNAUTHORIZED_ACCESS.name
        }), 401
    
    @app.errorhandler(429)
    def rate_limited(error):
        security_logger.log_warning("RATE_LIMITED", f"429 error: {error}")
        return jsonify({
            'error': 'Rate limit exceeded',
            'code': MemoryErrorCodes.RATE_LIMIT_EXCEEDED.name
        }), 429
    
    security_logger.log_info("SECURITY_INIT", "Memory security initialized")
    
    return app