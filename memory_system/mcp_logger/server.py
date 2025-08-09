#!/usr/bin/env python3
"""
MCP Memory Logger - Traffic Cop for Memory Operations
Basic JSON-RPC server skeleton using Flask

This component acts as the central router for all memory operations,
providing security, audit logging, and request routing to appropriate
memory services (working, episodic, semantic, etc.)
"""

from flask import Flask, request, jsonify, g
import json
import logging
import time
from functools import wraps
import uuid
from dotenv import load_dotenv
import os

# Import our security and routing modules
from auth import init_security, require_auth, MemoryAuth, audit_logger
from router import MemoryRouter

# Initialize router
memory_router = MemoryRouter()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp_memory_logger')

app = Flask(__name__)

# Configuration from environment
CONFIG = {
    'version': '1.0.0',
    'name': 'MCP Memory Logger',
    'port': int(os.getenv('MEMORY_PORT', '8001')),
    'host': os.getenv('MEMORY_HOST', '0.0.0.0'),
    'debug': os.getenv('MEMORY_DEBUG', 'false').lower() == 'true'
}

# Initialize security
app = init_security(app)

def log_request(f):
    """Decorator to log all memory requests for audit trail"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_id = str(uuid.uuid4())
        g.request_id = request_id
        
        # Log incoming request
        logger.info(f"Memory Request {request_id}: {request.method} {request.path}")
        logger.info(f"Request {request_id} Data: {request.get_json() if request.is_json else 'No JSON data'}")
        
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        
        # Log response
        logger.info(f"Memory Response {request_id}: Duration {end_time - start_time:.3f}s")
        
        return result
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': CONFIG['name'],
        'version': CONFIG['version'],
        'timestamp': time.time()
    })

@app.route('/info', methods=['GET'])
def service_info():
    """Service information endpoint"""
    return jsonify({
        'name': CONFIG['name'],
        'version': CONFIG['version'],
        'description': 'Traffic cop for AI memory operations',
        'endpoints': {
            '/health': 'Health check',
            '/info': 'Service information',
            '/memory/store': 'Store memory (TODO)',
            '/memory/recall': 'Recall memory (TODO)',
            '/memory/search': 'Search memory (TODO)'
        }
    })

@app.route('/memory/store', methods=['POST'])
@require_auth
@log_request
def store_memory():
    """Store memory endpoint with routing"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'error': 'No JSON data provided',
            'request_id': g.request_id
        }), 400
    
    # Route the request
    success, result = memory_router.route_store_request(data)
    
    if success:
        return jsonify({
            'status': 'success',
            'request_id': g.request_id,
            'result': result
        })
    else:
        return jsonify({
            'status': 'error',
            'request_id': g.request_id,
            'error': result
        }), 500

@app.route('/memory/recall', methods=['GET', 'POST'])
@require_auth
@log_request
def recall_memory():
    """Recall memory endpoint with routing"""
    if request.method == 'POST':
        data = request.get_json()
    else:
        data = request.args.to_dict()
    
    # Route the request
    success, result = memory_router.route_recall_request(data)
    
    if success:
        return jsonify({
            'status': 'success',
            'request_id': g.request_id,
            'result': result
        })
    else:
        return jsonify({
            'status': 'error',
            'request_id': g.request_id,
            'error': result
        }), 500

@app.route('/memory/search', methods=['POST'])
@require_auth
@log_request
def search_memory():
    """Search memory endpoint with routing"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'error': 'No JSON data provided',
            'request_id': g.request_id
        }), 400
    
    # Route the request
    success, result = memory_router.route_search_request(data)
    
    if success:
        return jsonify({
            'status': 'success',
            'request_id': g.request_id,
            'result': result
        })
    else:
        return jsonify({
            'status': 'error',
            'request_id': g.request_id,
            'error': result
        }), 500

@app.route('/memory/services/status', methods=['GET'])
def service_status():
    """Get status of all memory services"""
    status = memory_router.get_service_status()
    return jsonify({
        'status': 'success',
        'services': status,
        'timestamp': time.time()
    })

@app.route('/memory/verify_traces', methods=['POST'])
@require_auth
def verify_traces():
    """Run pending trace verifications"""
    results = memory_router.run_pending_verifications()
    return jsonify({
        'status': 'success',
        'verification_results': results,
        'timestamp': time.time()
    })

@app.route('/memory/verify_trace/<request_id>', methods=['GET'])
@require_auth
def verify_single_trace(request_id):
    """Verify a specific trace by request ID"""
    success, result = memory_router.verify_scheduler_trace(request_id)
    
    if success:
        return jsonify({
            'status': 'success',
            'request_id': request_id,
            'verification': result
        })
    else:
        return jsonify({
            'status': 'error',
            'request_id': request_id,
            'error': result
        }), 400

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'Use /info to see available endpoints'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'Check server logs for details'
    }), 500

if __name__ == '__main__':
    logger.info(f"Starting {CONFIG['name']} v{CONFIG['version']}")
    logger.info(f"Listening on {CONFIG['host']}:{CONFIG['port']}")
    
    app.run(
        host=CONFIG['host'],
        port=CONFIG['port'],
        debug=CONFIG['debug']
    )