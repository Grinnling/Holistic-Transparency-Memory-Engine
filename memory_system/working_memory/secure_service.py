#!/usr/bin/env python3
"""
Enhanced Working Memory HTTP Service with Security & Audit
Integrates with MCP security framework
"""
from flask import Flask, request, jsonify, g
import logging
import os
import uuid
from buffer import WorkingMemoryBuffer
import threading
from datetime import datetime
from auth_integration import secure_memory_endpoint, working_memory_audit, MCP_AUTH_AVAILABLE
from encryption_manager import EncryptionManager
from lifecycle_manager import LifecycleManager
from retrieval_manager import SmartRetrieval
from observability_manager import ObservabilityManager
import atexit
import signal
import sys
import time

# Import archiving triggers for Phase 1 completion
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from episodic_memory.archiving_triggers import TriggerConfig, initialize_triggers, start_triggers_monitoring
    TRIGGERS_AVAILABLE = True
except ImportError:
    logger.warning("Archiving triggers not available - auto-archiving disabled")
    TRIGGERS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Global buffer instance (thread-safe with simple operations)
memory_buffer = WorkingMemoryBuffer(max_size=int(os.environ.get('MEMORY_WORKING_BUFFER_SIZE', 20)))
buffer_lock = threading.Lock()

# Global encryption manager
encryption_manager = EncryptionManager()

# Global lifecycle manager
lifecycle_manager = LifecycleManager()

# Global smart retrieval system
smart_retrieval = SmartRetrieval()

# Global observability manager
observability_manager = ObservabilityManager()

# Timing decorator for operations
def timed_operation(operation_name):
    """Decorator to time and record operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                observability_manager.record_operation(
                    operation_name,
                    duration,
                    success,
                    error,
                    metadata={'request_id': g.get('request_id')}
                )
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# Graceful shutdown handler
def shutdown_handler():
    """Backup buffer to encrypted storage on shutdown"""
    logger.info("Shutting down - backing up buffer to encrypted storage")
    with buffer_lock:
        buffer_data = list(memory_buffer.buffer)
    encryption_manager.backup_buffer_on_shutdown(buffer_data)
    logger.info("Shutdown backup complete")

# Register shutdown handlers
atexit.register(shutdown_handler)
signal.signal(signal.SIGTERM, lambda signum, frame: (shutdown_handler(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda signum, frame: (shutdown_handler(), sys.exit(0)))

# Request ID middleware for audit trail
@app.before_request
def before_request():
    g.request_id = str(uuid.uuid4())
    g.start_time = datetime.utcnow()

@app.after_request
def after_request(response):
    if working_memory_audit:
        duration = (datetime.utcnow() - g.start_time).total_seconds()
        working_memory_audit.log_info("REQUEST_COMPLETED", f"{request.method} {request.path}", {
            "request_id": g.request_id,
            "status_code": response.status_code,
            "duration": f"{duration:.3f}s"
        })
    return response

# API Endpoints with Security

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint (public)"""
    return jsonify({
        "status": "healthy",
        "service": "working_memory",
        "timestamp": datetime.utcnow().isoformat(),
        "buffer_summary": memory_buffer.get_summary(),
        "security_enabled": MCP_AUTH_AVAILABLE,
        "encryption_stats": encryption_manager.get_encryption_stats(),
        "request_id": g.request_id
    })

@app.route('/store', methods=['POST'])
@secure_memory_endpoint("memory_store")
@timed_operation("store_memory")
def store_memory():
    """
    Store new conversation exchange (MCP Router compatible)
    Expected JSON from router:
    {
        "type": "working",
        "user_message": "What GPU do I have?",
        "assistant_response": "RTX 4060 Ti with driver 550.144.03",
        "context_used": ["system_hardware_scan"],  // optional
        "router_metadata": {...}  // added by MCP router
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No JSON data provided",
                "request_id": g.request_id
            }), 400
        
        # Extract working memory specific data
        user_message = data.get('user_message') or data.get('content', {}).get('user_message')
        assistant_response = data.get('assistant_response') or data.get('content', {}).get('assistant_response')
        context_used = data.get('context_used', [])
        
        if not user_message or not assistant_response:
            return jsonify({
                "status": "error", 
                "message": "Both user_message and assistant_response are required",
                "request_id": g.request_id
            }), 400
        
        with buffer_lock:
            exchange = memory_buffer.add_exchange(
                user_message=user_message,
                assistant_response=assistant_response,
                context_used=context_used
            )
            
            # Process encryption and sensitive data handling
            exchange, processing_info = encryption_manager.analyze_and_process_exchange(exchange)
            
            # Backup sensitive exchanges to encrypted storage
            if processing_info.get('should_backup'):
                backup_success = encryption_manager.backup_sensitive_exchange(exchange)
                if backup_success:
                    logger.info(f"Backed up sensitive exchange {exchange['exchange_id']} (sensitivity: {processing_info['sensitivity_score']})")
            
            # Check for lifecycle archival (high significance exchanges)
            buffer_status = memory_buffer.get_summary()
            should_archive, archival_reason, archival_metadata = lifecycle_manager.should_archive_exchange(exchange, buffer_status)
            
            if should_archive:
                archive_success = lifecycle_manager.archive_exchange_to_episodic(exchange, archival_reason, archival_metadata)
                if archive_success:
                    logger.info(f"Archived exchange {exchange['exchange_id']} to episodic memory (reason: {archival_reason.value})")
                    processing_info['archived_to_episodic'] = True
            
            summary = memory_buffer.get_summary()
            
            # Record buffer operation for observability
            observability_manager.record_buffer_operation('add', summary)
        
        logger.info(f"Added exchange {exchange['exchange_id']} (request: {g.request_id}, sensitivity: {processing_info['sensitivity_score']})")
        
        response_data = {
            "status": "success",
            "exchange": exchange,
            "buffer_summary": summary,
            "processing_info": {
                "sensitivity_detected": processing_info['sensitivity_score'] > 0,
                "encryption_backup": processing_info.get('should_backup', False),
                "auto_expire": processing_info.get('auto_expire', False),
                "archived_to_episodic": processing_info.get('archived_to_episodic', False)
            },
            "request_id": g.request_id
        }
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Error adding exchange (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/recall', methods=['GET', 'POST'])
@secure_memory_endpoint("memory_recall")
def recall_memory():
    """
    Get current working memory context (MCP Router compatible)
    Query params (GET) or JSON (POST):
    - limit: number of recent exchanges to return (default: all)
    - type: memory type filter (should be "working")
    """
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            limit = data.get('limit')
        else:
            limit = request.args.get('limit', type=int)
        
        with buffer_lock:
            context = memory_buffer.get_recent_context(limit)
            summary = memory_buffer.get_summary()
        
        return jsonify({
            "status": "success",
            "context": context,
            "summary": summary,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting working memory (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/search', methods=['POST'])
@secure_memory_endpoint("memory_search")
def search_memory():
    """Search working memory with smart relevance ranking (MCP Router compatible)"""
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "status": "error",
                "message": "Query parameter required",
                "request_id": g.request_id
            }), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({
                "status": "error",
                "message": "Query cannot be empty",
                "request_id": g.request_id
            }), 400
        
        # Extract search parameters (support both new and legacy formats)
        context_filter = data.get('context_filter', [])
        max_results = min(data.get('max_results', data.get('limit', 10)), 50)  # Support legacy 'limit'
        min_relevance = data.get('min_relevance', 0.1)
        
        with buffer_lock:
            buffer_data = list(memory_buffer.buffer)
        
        # Perform smart search
        search_results = smart_retrieval.search_exchanges(
            query=query,
            exchanges=buffer_data,
            context_filter=context_filter,
            max_results=max_results,
            min_relevance=min_relevance
        )
        
        # Format results for response (support both new detailed and legacy simple formats)
        if data.get('detailed', True):
            # New detailed format
            formatted_results = []
            for result in search_results:
                formatted_results.append({
                    "exchange_id": result['exchange']['exchange_id'],
                    "relevance_score": round(result['relevance_score'], 3),
                    "text_similarity": round(result['text_similarity'], 3),
                    "context_similarity": round(result['context_similarity'], 3),
                    "temporal_relevance": round(result['temporal_relevance'], 3),
                    "significance_boost": round(result['significance_boost'], 3),
                    "matched_keywords": result['matched_keywords'],
                    "exchange": result['exchange']
                })
            
            return jsonify({
                "status": "success",
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results,
                "search_parameters": {
                    "context_filter": context_filter,
                    "max_results": max_results,
                    "min_relevance": min_relevance
                },
                "request_id": g.request_id
            })
        else:
            # Legacy simple format for backward compatibility
            simple_results = [result['exchange'] for result in search_results]
            return jsonify({
                "status": "success",
                "results": simple_results,
                "total_matches": len(simple_results),
                "query": query,
                "request_id": g.request_id
            })
    
    except Exception as e:
        logger.error(f"Error in memory search (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

# Legacy endpoints for backward compatibility
@app.route('/working-memory', methods=['GET'])
@secure_memory_endpoint("legacy_recall")
def get_working_memory():
    """Legacy endpoint - redirects to /recall"""
    return recall_memory()

@app.route('/working-memory', methods=['POST'])
@secure_memory_endpoint("legacy_store")
def add_exchange():
    """Legacy endpoint - redirects to /store"""
    return store_memory()

@app.route('/working-memory', methods=['DELETE'])
@secure_memory_endpoint("memory_clear")
def clear_working_memory():
    """Clear all exchanges from working memory"""
    try:
        with buffer_lock:
            cleared_count = memory_buffer.clear()
        
        logger.info(f"Cleared {cleared_count} exchanges from working memory (request: {g.request_id})")
        
        return jsonify({
            "status": "success",
            "message": f"Cleared {cleared_count} exchanges",
            "cleared_count": cleared_count,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error clearing working memory (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/working-memory/size', methods=['PUT'])
@secure_memory_endpoint("buffer_resize")
def update_buffer_size():
    """Update working memory buffer size"""
    try:
        data = request.get_json()
        new_size = data.get('size') if data else None
        
        if not isinstance(new_size, int) or new_size < 1:
            return jsonify({
                "status": "error",
                "message": "Size must be a positive integer",
                "request_id": g.request_id
            }), 400
        
        with buffer_lock:
            old_size = memory_buffer.max_size
            memory_buffer.max_size = new_size
            # If new size is smaller, deque will automatically trim
            if new_size < len(memory_buffer.buffer):
                # Recreate deque with new max length
                from collections import deque
                old_data = list(memory_buffer.buffer)
                memory_buffer.buffer = deque(old_data, maxlen=new_size)
        
        logger.info(f"Updated buffer size from {old_size} to {new_size} (request: {g.request_id})")
        
        return jsonify({
            "status": "success",
            "old_size": old_size,
            "new_size": new_size,
            "buffer_summary": memory_buffer.get_summary(),
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error updating buffer size (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error", 
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/encryption/cleanup', methods=['POST'])
@secure_memory_endpoint("encryption_cleanup")
def cleanup_expired():
    """Clean up expired sensitive exchanges"""
    try:
        expired_ids = encryption_manager.cleanup_expired_exchanges(memory_buffer)
        
        return jsonify({
            "status": "success",
            "expired_count": len(expired_ids),
            "expired_exchange_ids": expired_ids,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error during cleanup (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/encryption/stats', methods=['GET'])
@secure_memory_endpoint("encryption_stats")
def get_encryption_stats():
    """Get detailed encryption statistics"""
    try:
        stats = encryption_manager.get_encryption_stats()
        
        return jsonify({
            "status": "success",
            "encryption_stats": stats,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting encryption stats (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error", 
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/lifecycle/maintenance', methods=['POST'])
@secure_memory_endpoint("lifecycle_maintenance")
def perform_lifecycle_maintenance():
    """Perform lifecycle maintenance - archive qualifying exchanges"""
    try:
        with buffer_lock:
            buffer_data = list(memory_buffer.buffer)
            buffer_status = memory_buffer.get_summary()
        
        maintenance_results = lifecycle_manager.perform_lifecycle_maintenance(buffer_data, buffer_status)
        
        return jsonify({
            "status": "success",
            "maintenance_results": maintenance_results,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error during lifecycle maintenance (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/lifecycle/stats', methods=['GET'])
@secure_memory_endpoint("lifecycle_stats")
def get_lifecycle_stats():
    """Get lifecycle management statistics"""
    try:
        stats = lifecycle_manager.get_lifecycle_stats()
        
        return jsonify({
            "status": "success",
            "lifecycle_stats": stats,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting lifecycle stats (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/lifecycle/candidates', methods=['GET'])
@secure_memory_endpoint("lifecycle_candidates")
def get_archival_candidates():
    """Get list of exchanges that should be archived"""
    try:
        with buffer_lock:
            buffer_data = list(memory_buffer.buffer)
            buffer_status = memory_buffer.get_summary()
        
        candidates = lifecycle_manager.get_archival_candidates(buffer_data, buffer_status)
        
        # Format candidates for response
        candidate_info = []
        for exchange, reason, metadata in candidates:
            candidate_info.append({
                "exchange_id": exchange.get('exchange_id'),
                "archival_reason": reason.value,
                "significance_score": metadata.get('significance_analysis', {}).get('significance_score', 0),
                "significance_level": metadata.get('significance_analysis', {}).get('significance_level', 'unknown'),
                "timestamp": exchange.get('timestamp'),
                "priority": metadata.get('priority', 'medium')
            })
        
        return jsonify({
            "status": "success",
            "candidates_count": len(candidate_info),
            "candidates": candidate_info,
            "buffer_status": buffer_status,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting archival candidates (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/similar/<exchange_id>', methods=['GET'])
@secure_memory_endpoint("find_similar")
def find_similar_exchanges(exchange_id):
    """Find exchanges similar to a specific exchange"""
    try:
        with buffer_lock:
            buffer_data = list(memory_buffer.buffer)
        
        # Find the reference exchange
        reference_exchange = None
        for exchange in buffer_data:
            if exchange.get('exchange_id') == exchange_id:
                reference_exchange = exchange
                break
        
        if not reference_exchange:
            return jsonify({
                "status": "error",
                "message": f"Exchange {exchange_id} not found",
                "request_id": g.request_id
            }), 404
        
        # Get similar exchanges
        max_results = min(int(request.args.get('max_results', 5)), 20)
        min_similarity = float(request.args.get('min_similarity', 0.2))
        
        similar_results = smart_retrieval.find_similar_exchanges(
            reference_exchange=reference_exchange,
            exchanges=buffer_data,
            max_results=max_results,
            min_similarity=min_similarity
        )
        
        # Format results
        formatted_results = []
        for result in similar_results:
            formatted_results.append({
                "exchange_id": result['exchange']['exchange_id'],
                "similarity_score": round(result['similarity_score'], 3),
                "text_similarity": round(result['text_similarity'], 3),
                "context_similarity": round(result['context_similarity'], 3),
                "common_keywords": result['common_keywords'],
                "exchange": result['exchange']
            })
        
        return jsonify({
            "status": "success",
            "reference_exchange_id": exchange_id,
            "similar_count": len(formatted_results),
            "similar_exchanges": formatted_results,
            "request_id": g.request_id
        })
    
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": f"Invalid parameter: {e}",
            "request_id": g.request_id
        }), 400
    except Exception as e:
        logger.error(f"Error finding similar exchanges (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/keywords', methods=['GET'])
@secure_memory_endpoint("get_keywords")
def get_keyword_summary():
    """Get keyword summary of current working memory contents"""
    try:
        with buffer_lock:
            buffer_data = list(memory_buffer.buffer)
        
        top_keywords = min(int(request.args.get('top_keywords', 20)), 100)
        
        keyword_summary = smart_retrieval.get_keyword_summary(
            exchanges=buffer_data,
            top_keywords=top_keywords
        )
        
        return jsonify({
            "status": "success",
            "keyword_summary": keyword_summary,
            "request_id": g.request_id
        })
    
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": f"Invalid parameter: {e}",
            "request_id": g.request_id
        }), 400
    except Exception as e:
        logger.error(f"Error getting keyword summary (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/retrieval/stats', methods=['GET'])
@secure_memory_endpoint("retrieval_stats")
def get_retrieval_stats():
    """Get smart retrieval system statistics"""
    try:
        stats = smart_retrieval.get_retrieval_stats()
        
        return jsonify({
            "status": "success",
            "retrieval_stats": stats,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting retrieval stats (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/metrics', methods=['GET'])
@secure_memory_endpoint("get_metrics")
def get_metrics():
    """Get comprehensive observability metrics"""
    try:
        format_type = request.args.get('format', 'json')
        
        if format_type == 'prometheus':
            metrics_data = observability_manager.export_metrics('prometheus')
            return metrics_data, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        else:
            # JSON format (default)
            snapshot = observability_manager.take_metrics_snapshot()
            return jsonify({
                "status": "success",
                "metrics": snapshot,
                "request_id": g.request_id
            })
    
    except Exception as e:
        logger.error(f"Error getting metrics (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/metrics/performance', methods=['GET'])
@secure_memory_endpoint("get_performance")
def get_performance_metrics():
    """Get performance summary metrics"""
    try:
        performance_summary = observability_manager.get_performance_summary()
        
        return jsonify({
            "status": "success",
            "performance": performance_summary,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting performance metrics (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/metrics/buffer', methods=['GET'])
@secure_memory_endpoint("get_buffer_metrics")
def get_buffer_metrics():
    """Get detailed buffer analytics"""
    try:
        buffer_analytics = observability_manager.get_buffer_analytics()
        
        return jsonify({
            "status": "success",
            "buffer_analytics": buffer_analytics,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting buffer metrics (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/health/detailed', methods=['GET'])
@secure_memory_endpoint("detailed_health")
def get_detailed_health():
    """Get detailed health check with observability status"""
    try:
        # Take current metrics snapshot
        snapshot = observability_manager.take_metrics_snapshot()
        
        # Get observability system status
        observability_status = observability_manager.get_observability_status()
        
        # Enhanced health check
        health_data = {
            "status": snapshot['health']['status'],
            "timestamp": snapshot['timestamp'],
            "uptime_hours": round(snapshot['uptime_seconds'] / 3600, 2),
            "service_health": {
                "buffer_available": True,
                "encryption_available": encryption_manager.get_encryption_stats()['gocryptfs_available'],
                "lifecycle_available": True,
                "retrieval_available": True,
                "observability_available": True
            },
            "performance_indicators": {
                "total_operations": sum(op['count'] for op in snapshot['operations'].values()),
                "average_response_time_ms": sum(op['avg_duration_ms'] * op['count'] for op in snapshot['operations'].values()) / max(sum(op['count'] for op in snapshot['operations'].values()), 1),
                "error_rate_percent": sum(op['error_count'] for op in snapshot['operations'].values()) / max(sum(op['count'] for op in snapshot['operations'].values()), 1) * 100
            },
            "buffer_health": {
                "current_utilization": snapshot['buffer_metrics']['current_size'] / 20 * 100,
                "operations_per_hour": (snapshot['buffer_metrics']['total_adds'] + snapshot['buffer_metrics']['total_recalls']) / max(snapshot['uptime_seconds'] / 3600, 0.01)
            },
            "observability_status": observability_status,
            "issues": snapshot['health']['issues'],
            "warnings": snapshot['health']['warnings'],
            "request_id": g.request_id
        }
        
        # Determine HTTP status based on health
        if snapshot['health']['status'] == 'unhealthy':
            return jsonify(health_data), 503
        elif snapshot['health']['status'] == 'degraded':
            return jsonify(health_data), 200
        else:
            return jsonify(health_data), 200
    
    except Exception as e:
        logger.error(f"Error getting detailed health (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

# Memory Curator Integration Placeholders
@app.route('/memory/validate', methods=['POST'])
@secure_memory_endpoint("memory_validate")
def validate_memory():
    """Placeholder for Memory Curator validation requests"""
    try:
        data = request.get_json()
        
        # Record validation request for metrics
        observability_manager.record_memory_integrity_event('validation_request', {
            'request_id': g.request_id,
            'validation_type': data.get('validation_type', 'unknown')
        })
        
        # Placeholder response - Memory Curator will implement actual validation
        return jsonify({
            "status": "pending",
            "message": "Memory Curator integration pending",
            "request_id": g.request_id,
            "placeholder": True
        })
    
    except Exception as e:
        logger.error(f"Error in memory validation (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/memory/flag-uncertainty', methods=['POST'])
@secure_memory_endpoint("flag_uncertainty")
def flag_uncertainty():
    """Placeholder for flagging uncertain memories"""
    try:
        data = request.get_json()
        
        # Record uncertainty flag
        observability_manager.record_memory_integrity_event('uncertainty_flag', {
            'request_id': g.request_id,
            'exchange_id': data.get('exchange_id'),
            'uncertainty_type': data.get('uncertainty_type')
        })
        
        # Placeholder response
        return jsonify({
            "status": "flagged",
            "message": "Uncertainty flagged for Memory Curator review",
            "request_id": g.request_id,
            "placeholder": True
        })
    
    except Exception as e:
        logger.error(f"Error flagging uncertainty (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/memory/analyze-patterns', methods=['POST'])
@secure_memory_endpoint("analyze_patterns")
def analyze_memory_patterns():
    """Placeholder for memory pattern analysis requests"""
    try:
        data = request.get_json()
        
        # Placeholder response
        return jsonify({
            "status": "pending",
            "message": "Pattern analysis pending Memory Curator implementation",
            "request_id": g.request_id,
            "placeholder": True,
            "requested_pattern": data.get('pattern_type')
        })
    
    except Exception as e:
        logger.error(f"Error in pattern analysis (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/memory/archive-now', methods=['POST'])
@secure_memory_endpoint("memory_archive")
def archive_memory_now():
    """Manual archive trigger - 'This is gold' functionality"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'manual_archive')
        
        if TRIGGERS_AVAILABLE:
            from episodic_memory.archiving_triggers import archiving_triggers
            
            if archiving_triggers:
                success = archiving_triggers.trigger_manual_archiving(reason)
                
                if success:
                    # Record the manual archive in observability
                    observability_manager.record_memory_integrity_event('manual_archive', {
                        'request_id': g.request_id,
                        'reason': reason,
                        'buffer_size': buffer.current_size
                    })
                    
                    return jsonify({
                        "status": "success",
                        "message": "Memory archived successfully",
                        "reason": reason,
                        "request_id": g.request_id
                    })
                else:
                    return jsonify({
                        "status": "error", 
                        "message": "Failed to archive memory",
                        "request_id": g.request_id
                    }), 500
            else:
                return jsonify({
                    "status": "error",
                    "message": "Archiving triggers not initialized",
                    "request_id": g.request_id
                }), 503
        else:
            return jsonify({
                "status": "error", 
                "message": "Archiving triggers not available",
                "request_id": g.request_id
            }), 503
    
    except Exception as e:
        logger.error(f"Error in manual memory archive (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

if __name__ == '__main__':
    # For development - in production this will run via Docker
    port = int(os.environ.get('WORKING_MEMORY_PORT', 8002))
    logger.info(f"Starting Secure Working Memory service on port {port}")
    logger.info(f"MCP Security integration: {'Enabled' if MCP_AUTH_AVAILABLE else 'Disabled (Fallback mode)'}")
    
    # Initialize archiving triggers for Phase 1 auto-archiving
    if TRIGGERS_AVAILABLE:
        try:
            # Configure triggers
            trigger_config = TriggerConfig(
                max_buffer_size=int(os.environ.get('WORKING_MEMORY_MAX_SIZE', 20)),
                inactivity_timeout_minutes=int(os.environ.get('ARCHIVE_TIMEOUT_MINUTES', 60)),
                working_memory_url=f"http://localhost:{port}",
                episodic_memory_url=os.environ.get('EPISODIC_MEMORY_URL', 'http://localhost:8005')
            )
            
            # Initialize and start monitoring
            triggers = initialize_triggers(trigger_config)
            start_triggers_monitoring()
            logger.info("✅ Archiving triggers initialized - auto-archiving enabled")
            logger.info(f"   Buffer threshold: {trigger_config.max_buffer_size} exchanges")
            logger.info(f"   Inactivity timeout: {trigger_config.inactivity_timeout_minutes} minutes")
            
            # Cleanup on shutdown
            def cleanup_triggers():
                if triggers:
                    triggers.stop_monitoring()
                    logger.info("Archiving triggers stopped")
            
            atexit.register(cleanup_triggers)
            
        except Exception as e:
            logger.error(f"Failed to initialize archiving triggers: {e}")
            logger.warning("Auto-archiving disabled due to initialization failure")
    else:
        logger.warning("Archiving triggers not available - auto-archiving disabled")
    
    app.run(host='0.0.0.0', port=port, debug=True)