"""
Working Memory HTTP Service
Flask wrapper around the memory buffer with REST API endpoints
"""
from flask import Flask, request, jsonify
import logging
import os
from buffer import WorkingMemoryBuffer
import threading
from datetime import datetime

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

# API Endpoints

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "working_memory",
        "timestamp": datetime.utcnow().isoformat(),
        "buffer_summary": memory_buffer.get_summary()
    })

@app.route('/working-memory', methods=['GET'])
def get_working_memory():
    """
    Get current working memory context
    Query params:
    - limit: number of recent exchanges to return (default: all)
    """
    try:
        limit = request.args.get('limit', type=int)
        
        with buffer_lock:
            context = memory_buffer.get_recent_context(limit)
            summary = memory_buffer.get_summary()
        
        return jsonify({
            "status": "success",
            "context": context,
            "summary": summary
        })
    
    except Exception as e:
        logger.error(f"Error getting working memory: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/working-memory', methods=['POST'])
def add_exchange():
    """
    Add new conversation exchange to working memory
    Expected JSON:
    {
        "user_message": "What GPU do I have?",
        "assistant_response": "RTX 4060 Ti with driver 550.144.03",
        "context_used": ["system_hardware_scan"]  // optional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No JSON data provided"
            }), 400
        
        user_message = data.get('user_message')
        assistant_response = data.get('assistant_response')
        context_used = data.get('context_used', [])
        
        if not user_message or not assistant_response:
            return jsonify({
                "status": "error", 
                "message": "Both user_message and assistant_response are required"
            }), 400
        
        with buffer_lock:
            exchange = memory_buffer.add_exchange(
                user_message=user_message,
                assistant_response=assistant_response,
                context_used=context_used
            )
            summary = memory_buffer.get_summary()
        
        logger.info(f"Added exchange {exchange['exchange_id']}")
        
        return jsonify({
            "status": "success",
            "exchange": exchange,
            "buffer_summary": summary
        })
    
    except Exception as e:
        logger.error(f"Error adding exchange: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/working-memory', methods=['DELETE'])
def clear_working_memory():
    """Clear all exchanges from working memory"""
    try:
        with buffer_lock:
            cleared_count = memory_buffer.clear()
        
        logger.info(f"Cleared {cleared_count} exchanges from working memory")
        
        return jsonify({
            "status": "success",
            "message": f"Cleared {cleared_count} exchanges",
            "cleared_count": cleared_count
        })
    
    except Exception as e:
        logger.error(f"Error clearing working memory: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/working-memory/size', methods=['PUT'])
def update_buffer_size():
    """
    Update working memory buffer size
    Expected JSON: {"size": 25}
    """
    try:
        data = request.get_json()
        new_size = data.get('size')
        
        if not isinstance(new_size, int) or new_size < 1:
            return jsonify({
                "status": "error",
                "message": "Size must be a positive integer"
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
        
        logger.info(f"Updated buffer size from {old_size} to {new_size}")
        
        return jsonify({
            "status": "success",
            "old_size": old_size,
            "new_size": new_size,
            "buffer_summary": memory_buffer.get_summary()
        })
    
    except Exception as e:
        logger.error(f"Error updating buffer size: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

if __name__ == '__main__':
    # For development - in production this will run via Docker
    port = int(os.environ.get('WORKING_MEMORY_PORT', 5001))
    logger.info(f"Starting Working Memory service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)