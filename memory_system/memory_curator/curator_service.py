#!/usr/bin/env python3
"""
Memory Curator Agent - Prototype Service
Hardware-flexible memory validation with group chat capabilities
"""
from flask import Flask, request, jsonify, g
import logging
import os
import uuid
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from collections import deque
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class MemoryCurator:
    """
    Memory Curator Agent - Prototype Implementation
    Starts with basic conversation and validation, expandable with hardware
    """
    
    def __init__(self):
        self.service_id = str(uuid.uuid4())
        self.start_time = datetime.now(timezone.utc)
        
        # Configuration
        self.config = {
            'model_size': os.getenv('CURATOR_MODEL_SIZE', '1.5B'),
            'enable_embedding': os.getenv('CURATOR_ENABLE_EMBEDDING', 'false').lower() == 'true',
            'enable_rerank': os.getenv('CURATOR_ENABLE_RERANK', 'false').lower() == 'true',
            'enable_statistical': os.getenv('CURATOR_ENABLE_STATISTICAL', 'false').lower() == 'true',
            'working_memory_url': os.getenv('WORKING_MEMORY_URL', 'http://localhost:8002'),
            'max_conversation_history': int(os.getenv('CURATOR_MAX_HISTORY', '50'))
        }
        
        # Validation metrics
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'contradictions_found': 0,
            'uncertainty_flags': 0,
            'cross_validations': 0,
            'group_chat_sessions': 0
        }
        
        # Group chat conversation storage
        self.conversation_history = deque(maxlen=self.config['max_conversation_history'])
        self.active_validations = {}  # validation_id -> validation_context
        
        # Thread lock for thread-safety
        self.lock = threading.Lock()
        
        # Available models (hardware dependent)
        self.available_models = {
            'linguistic': True,  # Always available
            'embedding': self.config['enable_embedding'],
            'rerank': self.config['enable_rerank'],
            'statistical': self.config['enable_statistical']
        }
        
        logger.info(f"Memory Curator initialized - Service ID: {self.service_id}")
        logger.info(f"Configuration: {self.config}")
        logger.info(f"Available models: {self.available_models}")
    
    def validate_memory_exchange(self, exchange_data: Dict, validation_type: str = "basic") -> Dict:
        """
        Validate a memory exchange for accuracy and consistency
        """
        validation_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        with self.lock:
            self.validation_stats['total_validations'] += 1
        
        # Basic validation using linguistic model (prompt-based)
        validation_result = self._perform_linguistic_validation(exchange_data, validation_type)
        
        # Enhanced validation if models available
        if self.available_models['embedding']:
            embedding_result = self._perform_embedding_validation(exchange_data)
            validation_result['embedding_analysis'] = embedding_result
        
        if self.available_models['statistical']:
            statistical_result = self._perform_statistical_validation(exchange_data)
            validation_result['statistical_analysis'] = statistical_result
        
        # Store validation context
        validation_context = {
            'validation_id': validation_id,
            'timestamp': timestamp.isoformat(),
            'exchange_data': exchange_data,
            'validation_type': validation_type,
            'result': validation_result,
            'status': 'completed'
        }
        
        self.active_validations[validation_id] = validation_context
        
        # Update stats
        with self.lock:
            if validation_result.get('is_valid', True):
                self.validation_stats['successful_validations'] += 1
            if validation_result.get('contradictions_detected', 0) > 0:
                self.validation_stats['contradictions_found'] += 1
            if validation_result.get('uncertainty_level', 0) > 0.5:
                self.validation_stats['uncertainty_flags'] += 1
        
        return validation_context
    
    def _perform_linguistic_validation(self, exchange_data: Dict, validation_type: str) -> Dict:
        """
        Basic validation using 1.5B linguistic model (simulated for prototype)
        In real implementation, this would call the actual LLM
        """
        # Simulate validation logic - replace with actual LLM calls
        user_message = exchange_data.get('user_message', '')
        assistant_response = exchange_data.get('assistant_response', '')
        
        # Basic contradiction detection via keyword analysis (placeholder)
        contradiction_keywords = ['never', 'always', 'impossible', 'definitely', 'certainly']
        contradictions = []
        
        for keyword in contradiction_keywords:
            if keyword in user_message.lower() and keyword in assistant_response.lower():
                contradictions.append(f"Potential contradiction around '{keyword}'")
        
        # Basic uncertainty detection
        uncertainty_keywords = ['maybe', 'possibly', 'might', 'could be', 'not sure']
        uncertainty_level = sum(1 for keyword in uncertainty_keywords 
                              if keyword in assistant_response.lower()) / len(uncertainty_keywords)
        
        # Simulated validation result
        validation_result = {
            'is_valid': len(contradictions) == 0,
            'confidence_score': max(0.1, 1.0 - (len(contradictions) * 0.3) - (uncertainty_level * 0.2)),
            'contradictions_detected': len(contradictions),
            'contradiction_details': contradictions,
            'uncertainty_level': uncertainty_level,
            'validation_method': 'linguistic_analysis',
            'model_used': f"{self.config['model_size']}_linguistic"
        }
        
        return validation_result
    
    def _perform_embedding_validation(self, exchange_data: Dict) -> Dict:
        """
        Semantic similarity validation using embedding model (if available)
        """
        if not self.available_models['embedding']:
            return {'status': 'unavailable', 'reason': 'embedding_model_disabled'}
        
        # Placeholder for embedding analysis
        return {
            'semantic_similarity': 0.85,
            'context_alignment': 0.92,
            'method': 'embedding_similarity',
            'status': 'completed'
        }
    
    def _perform_statistical_validation(self, exchange_data: Dict) -> Dict:
        """
        Statistical pattern validation (if available)
        """
        if not self.available_models['statistical']:
            return {'status': 'unavailable', 'reason': 'statistical_model_disabled'}
        
        # Placeholder for statistical analysis
        return {
            'pattern_consistency': 0.88,
            'anomaly_score': 0.12,
            'method': 'statistical_analysis',
            'status': 'completed'
        }
    
    def start_group_chat_validation(self, exchange_data: Dict, participants: List[str]) -> Dict:
        """
        Start a group chat validation session
        """
        chat_session_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        with self.lock:
            self.validation_stats['group_chat_sessions'] += 1
        
        # Initialize group chat session
        chat_session = {
            'session_id': chat_session_id,
            'started_at': timestamp.isoformat(),
            'participants': participants,
            'exchange_under_review': exchange_data,
            'conversation_log': [],
            'status': 'active',
            'validation_result': None
        }
        
        # Add curator introduction message
        intro_message = {
            'timestamp': timestamp.isoformat(),
            'speaker': 'memory_curator',
            'message': f"Starting validation session for exchange {exchange_data.get('exchange_id', 'unknown')}. Participants: {', '.join(participants)}. Let's review this memory for accuracy.",
            'message_type': 'system'
        }
        
        chat_session['conversation_log'].append(intro_message)
        self.active_validations[chat_session_id] = chat_session
        
        return chat_session
    
    def add_chat_message(self, session_id: str, speaker: str, message: str, message_type: str = "user") -> Dict:
        """
        Add a message to a group chat validation session
        """
        if session_id not in self.active_validations:
            return {'error': 'Session not found'}
        
        timestamp = datetime.now(timezone.utc)
        
        chat_message = {
            'timestamp': timestamp.isoformat(),
            'speaker': speaker,
            'message': message,
            'message_type': message_type
        }
        
        with self.lock:
            self.active_validations[session_id]['conversation_log'].append(chat_message)
        
        # If it's a curator response, generate a validation response
        if speaker == 'memory_curator':
            # This would call the actual LLM for response generation
            # For now, simulate a basic response
            pass
        
        return {'status': 'message_added', 'message': chat_message}
    
    def get_validation_status(self, validation_id: str) -> Optional[Dict]:
        """
        Get the status of a validation request
        """
        return self.active_validations.get(validation_id)
    
    def get_curator_stats(self) -> Dict:
        """
        Get curator service statistics
        """
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        return {
            'service_id': self.service_id,
            'uptime_seconds': uptime,
            'uptime_hours': round(uptime / 3600, 2),
            'configuration': self.config,
            'available_models': self.available_models,
            'validation_stats': self.validation_stats.copy(),
            'active_validations': len(self.active_validations),
            'total_conversation_history': len(self.conversation_history)
        }

# Global curator instance
curator = MemoryCurator()

# Request ID middleware
@app.before_request
def before_request():
    g.request_id = str(uuid.uuid4())
    g.start_time = datetime.utcnow()

@app.after_request
def after_request(response):
    duration = (datetime.utcnow() - g.start_time).total_seconds()
    logger.info(f"REQUEST_COMPLETED: {request.method} {request.path} - {response.status_code} - {duration:.3f}s")
    return response

# API Endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "memory_curator",
        "timestamp": datetime.utcnow().isoformat(),
        "service_id": curator.service_id,
        "available_models": curator.available_models,
        "request_id": g.request_id
    })

@app.route('/validate', methods=['POST'])
def validate_memory():
    """Validate a memory exchange"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No JSON data provided",
                "request_id": g.request_id
            }), 400
        
        exchange_data = data.get('exchange_data', {})
        validation_type = data.get('validation_type', 'basic')
        
        if not exchange_data:
            return jsonify({
                "status": "error",
                "message": "exchange_data is required",
                "request_id": g.request_id
            }), 400
        
        validation_result = curator.validate_memory_exchange(exchange_data, validation_type)
        
        return jsonify({
            "status": "success",
            "validation": validation_result,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error in memory validation (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/group-chat/start', methods=['POST'])
def start_group_chat():
    """Start a group chat validation session"""
    try:
        data = request.get_json()
        
        exchange_data = data.get('exchange_data', {})
        participants = data.get('participants', [])
        
        if not exchange_data or not participants:
            return jsonify({
                "status": "error",
                "message": "exchange_data and participants are required",
                "request_id": g.request_id
            }), 400
        
        chat_session = curator.start_group_chat_validation(exchange_data, participants)
        
        return jsonify({
            "status": "success",
            "chat_session": chat_session,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error starting group chat (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/group-chat/<session_id>/message', methods=['POST'])
def add_chat_message(session_id):
    """Add a message to group chat session"""
    try:
        data = request.get_json()
        
        speaker = data.get('speaker', '')
        message = data.get('message', '')
        message_type = data.get('message_type', 'user')
        
        if not speaker or not message:
            return jsonify({
                "status": "error",
                "message": "speaker and message are required",
                "request_id": g.request_id
            }), 400
        
        result = curator.add_chat_message(session_id, speaker, message, message_type)
        
        if 'error' in result:
            return jsonify({
                "status": "error",
                "message": result['error'],
                "request_id": g.request_id
            }), 404
        
        return jsonify({
            "status": "success",
            "result": result,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error adding chat message (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/group-chat/<session_id>', methods=['GET'])
def get_chat_session(session_id):
    """Get group chat session details"""
    try:
        session = curator.get_validation_status(session_id)
        
        if not session:
            return jsonify({
                "status": "error",
                "message": "Session not found",
                "request_id": g.request_id
            }), 404
        
        return jsonify({
            "status": "success",
            "session": session,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting chat session (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/validation/<validation_id>', methods=['GET'])
def get_validation_status(validation_id):
    """Get validation status"""
    try:
        validation = curator.get_validation_status(validation_id)
        
        if not validation:
            return jsonify({
                "status": "error",
                "message": "Validation not found",
                "request_id": g.request_id
            }), 404
        
        return jsonify({
            "status": "success",
            "validation": validation,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting validation status (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/stats', methods=['GET'])
def get_curator_stats():
    """Get curator service statistics"""
    try:
        stats = curator.get_curator_stats()
        
        return jsonify({
            "status": "success",
            "stats": stats,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting curator stats (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('CURATOR_PORT', 8004))
    logger.info(f"Starting Memory Curator service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)