#!/usr/bin/env python3
"""
Memory Request Router for MCP Memory Logger
Routes memory operations to appropriate services

This module handles the "traffic cop" functionality, determining which
memory service should handle each request and managing the communication.
"""

import logging
import requests
import time
from typing import Dict, Any, Optional, Tuple
from enum import Enum
import os
from dataclasses import dataclass

# Import our logging
from auth import MemoryLogger

# Create router logger
router_logger = MemoryLogger("memory_router")

class MemoryType(Enum):
    """Supported memory types"""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    CITATION = "citation"
    META = "meta"
    PROSPECTIVE = "prospective"  # Pass-through to scheduler

class RouterError(Exception):
    """Router-specific errors"""
    pass

@dataclass
class ServiceConfig:
    """Configuration for a memory service"""
    name: str
    url: str
    enabled: bool = True
    timeout: int = 30
    retry_count: int = 3

class MemoryRouter:
    """Routes memory requests to appropriate services"""
    
    def __init__(self):
        self.services = self._load_service_config()
        router_logger.log_info("ROUTER_INIT", "Memory router initialized", {
            "services_configured": len(self.services),
            "enabled_services": len([s for s in self.services.values() if s.enabled])
        })
    
    def _load_service_config(self) -> Dict[MemoryType, ServiceConfig]:
        """Load configuration for memory services"""
        base_url = os.getenv('MEMORY_SERVICES_BASE_URL', 'http://localhost')
        
        return {
            MemoryType.WORKING: ServiceConfig(
                name="Working Memory Service",
                url=f"{base_url}:8002",
                enabled=os.getenv('WORKING_MEMORY_ENABLED', 'true').lower() == 'true'
            ),
            MemoryType.EPISODIC: ServiceConfig(
                name="Episodic Memory Service", 
                url=f"{base_url}:8003",
                enabled=os.getenv('EPISODIC_MEMORY_ENABLED', 'true').lower() == 'true'
            ),
            MemoryType.SEMANTIC: ServiceConfig(
                name="Semantic Memory Service",
                url=f"{base_url}:8004",
                enabled=os.getenv('SEMANTIC_MEMORY_ENABLED', 'false').lower() == 'true'
            ),
            MemoryType.PROCEDURAL: ServiceConfig(
                name="Procedural Memory Service",
                url=f"{base_url}:8005", 
                enabled=os.getenv('PROCEDURAL_MEMORY_ENABLED', 'false').lower() == 'true'
            ),
            MemoryType.CITATION: ServiceConfig(
                name="Citation Memory Service",
                url=f"{base_url}:8006",
                enabled=os.getenv('CITATION_MEMORY_ENABLED', 'false').lower() == 'true'
            ),
            MemoryType.META: ServiceConfig(
                name="Meta Memory Service",
                url=f"{base_url}:8007",
                enabled=os.getenv('META_MEMORY_ENABLED', 'false').lower() == 'true'
            ),
            MemoryType.PROSPECTIVE: ServiceConfig(
                name="Prospective Memory Scheduler",
                url=f"{base_url}:8008",
                enabled=os.getenv('PROSPECTIVE_SCHEDULER_ENABLED', 'true').lower() == 'true'
            )
        }
    
    def _determine_memory_type(self, request_data: Dict[str, Any]) -> MemoryType:
        """Determine which memory type should handle this request"""
        memory_type_str = request_data.get('type', '').lower()
        
        try:
            return MemoryType(memory_type_str)
        except ValueError:
            router_logger.log_warning("UNKNOWN_MEMORY_TYPE", f"Unknown memory type: {memory_type_str}")
            # Default to working memory for unknown types
            return MemoryType.WORKING
    
    def _make_service_request(self, service: ServiceConfig, endpoint: str, 
                            method: str = 'POST', data: Dict = None, 
                            params: Dict = None) -> Tuple[bool, Dict]:
        """Make request to a memory service with retry logic"""
        url = f"{service.url}/{endpoint.lstrip('/')}"
        
        for attempt in range(service.retry_count):
            try:
                start_time = time.time()
                
                if method.upper() == 'POST':
                    response = requests.post(url, json=data, timeout=service.timeout)
                elif method.upper() == 'GET':
                    response = requests.get(url, params=params, timeout=service.timeout)
                else:
                    raise RouterError(f"Unsupported HTTP method: {method}")
                
                end_time = time.time()
                duration = end_time - start_time
                
                router_logger.log_info("SERVICE_REQUEST", f"Request to {service.name}", {
                    "url": url,
                    "method": method,
                    "status_code": response.status_code,
                    "duration": f"{duration:.3f}s",
                    "attempt": attempt + 1
                })
                
                if response.status_code == 200:
                    return True, response.json()
                else:
                    router_logger.log_warning("SERVICE_ERROR", f"Service returned {response.status_code}", {
                        "service": service.name,
                        "response": response.text[:500]  # Truncate long responses
                    })
                    return False, {"error": f"Service returned {response.status_code}", "details": response.text}
                    
            except requests.exceptions.Timeout:
                router_logger.log_warning("SERVICE_TIMEOUT", f"Timeout on attempt {attempt + 1}", {
                    "service": service.name,
                    "timeout": service.timeout
                })
                if attempt == service.retry_count - 1:  # Last attempt
                    return False, {"error": "Service timeout", "service": service.name}
                    
            except requests.exceptions.ConnectionError:
                router_logger.log_warning("SERVICE_UNAVAILABLE", f"Connection failed on attempt {attempt + 1}", {
                    "service": service.name,
                    "url": url
                })
                if attempt == service.retry_count - 1:  # Last attempt
                    return False, {"error": "Service unavailable", "service": service.name}
                    
            except Exception as e:
                router_logger.log_error("SERVICE_EXCEPTION", f"Unexpected error: {e}", {
                    "service": service.name,
                    "exception": str(e)
                })
                return False, {"error": "Service error", "details": str(e)}
        
        return False, {"error": "Max retries exceeded"}
    
    def _sanitize_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize request data for AI safety"""
        # Remove any system-level instructions that could be prompt injections
        dangerous_keys = ['system', 'system_prompt', 'jailbreak', 'ignore_previous']
        
        sanitized = {}
        for key, value in data.items():
            if key.lower() not in dangerous_keys:
                if isinstance(value, str):
                    # Basic prompt injection prevention
                    if any(phrase in value.lower() for phrase in ['ignore previous', 'disregard instructions', 'new system prompt']):
                        router_logger.log_warning("PROMPT_INJECTION_ATTEMPT", f"Potential prompt injection in {key}", {
                            "key": key,
                            "value_snippet": value[:50] + "..."
                        })
                        continue
                sanitized[key] = value
        
        return sanitized
    
    def route_store_request(self, request_data: Dict[str, Any]) -> Tuple[bool, Dict]:
        """Route a memory store request"""
        # Sanitize for AI safety
        request_data = self._sanitize_request_data(request_data)
        
        memory_type = self._determine_memory_type(request_data)
        service = self.services.get(memory_type)
        
        if not service:
            router_logger.log_error("SERVICE_NOT_CONFIGURED", f"No service configured for {memory_type}")
            return False, {"error": f"Service not configured for memory type: {memory_type.value}"}
        
        if not service.enabled:
            router_logger.log_warning("SERVICE_DISABLED", f"Service disabled: {service.name}")
            return False, {"error": f"Service disabled: {service.name}"}
        
        router_logger.log_info("ROUTING_STORE", f"Routing store request to {service.name}", {
            "memory_type": memory_type.value,
            "service_url": service.url
        })
        
        return self._make_service_request(service, "store", "POST", request_data)
    
    def route_recall_request(self, request_data: Dict[str, Any]) -> Tuple[bool, Dict]:
        """Route a memory recall request"""
        memory_type = self._determine_memory_type(request_data)
        service = self.services.get(memory_type)
        
        if not service:
            return False, {"error": f"Service not configured for memory type: {memory_type.value}"}
        
        if not service.enabled:
            return False, {"error": f"Service disabled: {service.name}"}
        
        router_logger.log_info("ROUTING_RECALL", f"Routing recall request to {service.name}", {
            "memory_type": memory_type.value,
            "service_url": service.url
        })
        
        # Recall can be GET or POST depending on the service
        if request_data:
            return self._make_service_request(service, "recall", "POST", request_data)
        else:
            return self._make_service_request(service, "recall", "GET")
    
    def route_search_request(self, request_data: Dict[str, Any]) -> Tuple[bool, Dict]:
        """Route a memory search request"""
        search_type = request_data.get('type', 'all').lower()
        
        if search_type == 'all':
            # Multi-service search - query all enabled services
            return self._route_multi_service_search(request_data)
        else:
            # Single service search
            try:
                memory_type = MemoryType(search_type)
                service = self.services.get(memory_type)
                
                if not service or not service.enabled:
                    return False, {"error": f"Service not available for search type: {search_type}"}
                
                router_logger.log_info("ROUTING_SEARCH", f"Routing search to {service.name}", {
                    "search_type": search_type,
                    "service_url": service.url
                })
                
                return self._make_service_request(service, "search", "POST", request_data)
                
            except ValueError:
                return False, {"error": f"Unknown search type: {search_type}"}
    
    def _route_multi_service_search(self, request_data: Dict[str, Any]) -> Tuple[bool, Dict]:
        """Search across multiple memory services"""
        router_logger.log_info("MULTI_SERVICE_SEARCH", "Starting multi-service search", {
            "query": request_data.get('query', 'No query')
        })
        
        results = {}
        errors = {}
        
        for memory_type, service in self.services.items():
            if not service.enabled:
                continue
                
            success, response = self._make_service_request(service, "search", "POST", request_data)
            
            if success:
                results[memory_type.value] = response
            else:
                errors[memory_type.value] = response
        
        if results:
            return True, {
                "results": results,
                "errors": errors if errors else None,
                "searched_services": list(results.keys())
            }
        else:
            return False, {
                "error": "No services returned results", 
                "errors": errors
            }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all configured services"""
        status = {}
        
        for memory_type, service in self.services.items():
            if not service.enabled:
                status[memory_type.value] = {"status": "disabled"}
                continue
                
            try:
                # Try a health check
                success, response = self._make_service_request(service, "health", "GET")
                status[memory_type.value] = {
                    "status": "healthy" if success else "unhealthy",
                    "service_name": service.name,
                    "url": service.url,
                    "response": response
                }
            except Exception as e:
                status[memory_type.value] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return status
    
    def route_prospective_request(self, request_data: Dict[str, Any]) -> Tuple[bool, Dict]:
        """Route prospective memory request to scheduler with metadata trace"""
        from flask import g  # Import here to avoid circular imports
        
        request_id = getattr(g, 'request_id', 'unknown')
        
        # Log the pass-through with full metadata
        router_logger.log_info("ROUTING_PROSPECTIVE", "Routing to scheduler with metadata trace", {
            "request_id": request_id,
            "trigger_time": request_data.get('trigger_time'),
            "trigger_type": request_data.get('trigger_type', 'unknown'),
            "original_context": request_data.get('context'),
            "created_from_memory_type": request_data.get('source_memory_type'),
            "user_context": request_data.get('user_id', 'unknown')
        })
        
        # Store trace for later verification
        self._store_router_trace(request_id, {
            "action": "prospective_create",
            "timestamp": time.time(),
            "request_data": request_data,
            "routed_to": "scheduler"
        })
        
        service = self.services.get(MemoryType.PROSPECTIVE)
        
        if not service:
            router_logger.log_error("SCHEDULER_NOT_CONFIGURED", "Prospective scheduler not configured")
            return False, {"error": "Prospective memory scheduler not configured"}
        
        if not service.enabled:
            router_logger.log_warning("SCHEDULER_DISABLED", "Prospective scheduler disabled")
            return False, {"error": "Prospective memory scheduler disabled"}
        
        # Add router metadata to request
        enhanced_request = {
            **request_data,
            "router_metadata": {
                "request_id": request_id,
                "routed_at": time.time(),
                "router_version": "1.0.0",
                "trace_verification_enabled": True
            }
        }
        
        success, response = self._make_service_request(service, "create_trigger", "POST", enhanced_request)
        
        if success:
            # Schedule trace verification
            scheduler_task_id = response.get('task_id')
            if scheduler_task_id:
                self._schedule_trace_verification(request_id, scheduler_task_id)
        
        return success, response
    
    def _store_router_trace(self, request_id: str, trace_data: Dict[str, Any]):
        """Store router trace for later verification"""
        # Simple in-memory storage for now - could be database/redis in production
        if not hasattr(self, '_router_traces'):
            self._router_traces = {}
        
        self._router_traces[request_id] = trace_data
        
        router_logger.log_info("TRACE_STORED", f"Router trace stored for {request_id}", {
            "request_id": request_id,
            "action": trace_data.get('action')
        })
    
    def _schedule_trace_verification(self, request_id: str, scheduler_task_id: str):
        """Schedule verification of router vs scheduler traces"""
        # Store the mapping for later verification
        if not hasattr(self, '_pending_verifications'):
            self._pending_verifications = {}
        
        self._pending_verifications[request_id] = {
            "scheduler_task_id": scheduler_task_id,
            "scheduled_at": time.time(),
            "verification_attempts": 0
        }
        
        router_logger.log_info("VERIFICATION_SCHEDULED", f"Trace verification scheduled", {
            "request_id": request_id,
            "scheduler_task_id": scheduler_task_id
        })
    
    def verify_scheduler_trace(self, request_id: str) -> Tuple[bool, Dict]:
        """Compare router trace with scheduler execution log"""
        if not hasattr(self, '_router_traces') or request_id not in self._router_traces:
            return False, {"error": "No router trace found for request"}
        
        router_trace = self._router_traces[request_id]
        
        # Query scheduler for execution confirmation
        service = self.services.get(MemoryType.PROSPECTIVE)
        if not service or not service.enabled:
            return False, {"error": "Scheduler service not available for verification"}
        
        verification_data = {"request_id": request_id}
        success, scheduler_response = self._make_service_request(
            service, "get_trace", "POST", verification_data
        )
        
        if not success:
            router_logger.log_warning("TRACE_VERIFICATION_FAILED", 
                                    f"Could not retrieve scheduler trace for {request_id}")
            return False, {"error": "Could not retrieve scheduler trace"}
        
        scheduler_trace = scheduler_response.get('trace', {})
        
        # Compare traces
        verification_result = self._compare_traces(router_trace, scheduler_trace)
        
        if verification_result['match']:
            router_logger.log_info("TRACE_VERIFIED", f"Traces match for {request_id}", {
                "request_id": request_id,
                "verification_timestamp": time.time()
            })
        else:
            router_logger.log_error("TRACE_MISMATCH", f"Traces don't match for {request_id}", {
                "request_id": request_id,
                "router_trace": router_trace,
                "scheduler_trace": scheduler_trace,
                "discrepancies": verification_result['discrepancies']
            })
        
        return verification_result['match'], verification_result
    
    def _compare_traces(self, router_trace: Dict, scheduler_trace: Dict) -> Dict:
        """Compare router and scheduler traces for discrepancies"""
        discrepancies = []
        
        # Check key fields
        key_fields = ['action', 'request_data', 'timestamp']
        
        for field in key_fields:
            router_value = router_trace.get(field)
            scheduler_value = scheduler_trace.get(field)
            
            if field == 'timestamp':
                # Allow small timestamp differences (up to 5 seconds)
                if abs(float(router_value or 0) - float(scheduler_value or 0)) > 5:
                    discrepancies.append({
                        "field": field,
                        "router_value": router_value,
                        "scheduler_value": scheduler_value,
                        "issue": "timestamp_mismatch"
                    })
            elif router_value != scheduler_value:
                discrepancies.append({
                    "field": field,
                    "router_value": router_value,
                    "scheduler_value": scheduler_value,
                    "issue": "value_mismatch"
                })
        
        return {
            "match": len(discrepancies) == 0,
            "discrepancies": discrepancies,
            "verified_at": time.time()
        }
    
    def run_pending_verifications(self) -> Dict[str, Any]:
        """Run all pending trace verifications"""
        if not hasattr(self, '_pending_verifications'):
            return {"message": "No pending verifications"}
        
        results = {
            "verified": [],
            "failed": [],
            "total_pending": len(self._pending_verifications)
        }
        
        # Copy keys to avoid modifying dict during iteration
        pending_requests = list(self._pending_verifications.keys())
        
        for request_id in pending_requests:
            verification_info = self._pending_verifications[request_id]
            
            # Skip if too recent (give scheduler time to process)
            if time.time() - verification_info['scheduled_at'] < 30:  # 30 second grace period
                continue
            
            success, result = self.verify_scheduler_trace(request_id)
            
            if success:
                results["verified"].append(request_id)
                # Remove from pending
                del self._pending_verifications[request_id]
            else:
                results["failed"].append({
                    "request_id": request_id,
                    "error": result.get("error", "Unknown error")  
                })
                
                # Increment attempt counter
                verification_info['verification_attempts'] += 1
                
                # Remove after 3 failed attempts
                if verification_info['verification_attempts'] >= 3:
                    del self._pending_verifications[request_id]
        
        router_logger.log_info("BATCH_VERIFICATION", "Batch verification completed", results)
        
        return results