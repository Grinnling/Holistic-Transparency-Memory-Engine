#!/usr/bin/env python3
"""
Episodic Memory Service
Handles long-term conversation storage and retrieval
"""
import os
import sys
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify, g
import threading

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from episodic_memory.database import EpisodicDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class EpisodicMemoryService:
    """
    Episodic Memory Service
    Manages long-term storage and retrieval of conversation episodes
    """
    
    def __init__(self, db_path: str = "/tmp/episodic_memory.db"):
        """Initialize the episodic memory service"""
        self.service_id = str(uuid.uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.db_path = db_path
        
        # Initialize database
        self.database = EpisodicDatabase(db_path)
        
        # Service statistics
        self.stats = {
            'episodes_stored': 0,
            'episodes_retrieved': 0,
            'searches_performed': 0,
            'total_exchanges_archived': 0
        }
        
        # Thread lock for thread-safety
        self.lock = threading.Lock()
        
        logger.info(f"Episodic Memory Service initialized - Service ID: {self.service_id}")
        logger.info(f"Database path: {db_path}")
    
    def archive_conversation(
        self,
        conversation_data: Dict,
        trigger_reason: str = "manual"
    ) -> str:
        """
        Archive a conversation from working memory
        
        Args:
            conversation_data: Conversation data from working memory
            trigger_reason: Why this conversation was archived
            
        Returns:
            conversation_id of archived episode
        """
        try:
            # Extract conversation details
            exchanges = conversation_data.get('exchanges', [])
            participants = conversation_data.get('participants', ['human', 'assistant'])
            conversation_id = conversation_data.get('conversation_id') or f"episode_{uuid.uuid4()}"
            
            # Determine timestamps
            start_timestamp = None
            end_timestamp = None
            
            if exchanges:
                # Get timestamps from first and last exchanges
                first_exchange = exchanges[0]
                last_exchange = exchanges[-1]
                
                start_timestamp = self._parse_timestamp(first_exchange.get('timestamp'))
                end_timestamp = self._parse_timestamp(last_exchange.get('timestamp'))
            
            if not start_timestamp:
                start_timestamp = datetime.now(timezone.utc)
            if not end_timestamp:
                end_timestamp = datetime.now(timezone.utc)
            
            # Extract topics (basic keyword extraction for now)
            topics = self._extract_topics(exchanges)
            
            # Generate summary
            summary = self._generate_conversation_summary(exchanges, participants)
            
            # Store in database
            stored_id = self.database.store_episode(
                conversation_id=conversation_id,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                participants=participants,
                exchanges=exchanges,
                trigger_reason=trigger_reason,
                summary=summary,
                topics=topics
            )
            
            # Update statistics
            with self.lock:
                self.stats['episodes_stored'] += 1
                self.stats['total_exchanges_archived'] += len(exchanges)
            
            logger.info(f"Archived conversation {stored_id} with {len(exchanges)} exchanges")
            return stored_id
            
        except Exception as e:
            logger.error(f"Error archiving conversation: {e}")
            raise
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string into datetime object"""
        if not timestamp_str:
            return None
        
        try:
            # Try ISO format first
            if 'T' in timestamp_str:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Try other common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(timestamp_str, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        except Exception as e:
            logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
        
        return None
    
    def _extract_topics(self, exchanges: List[Dict]) -> List[str]:
        """Extract topics from conversation exchanges (basic implementation)"""
        topics = set()
        
        # Simple keyword-based topic extraction
        topic_keywords = {
            'python': ['python', 'py', 'pip', 'django', 'flask'],
            'security': ['security', 'encryption', 'auth', 'vulnerability', 'secure'],
            'memory': ['memory', 'remember', 'recall', 'conversation', 'context'],
            'coding': ['code', 'programming', 'function', 'class', 'variable'],
            'database': ['database', 'sql', 'query', 'table', 'db'],
            'docker': ['docker', 'container', 'compose', 'image'],
            'ai': ['ai', 'model', 'agent', 'llm', 'assistant'],
            'testing': ['test', 'testing', 'unit', 'integration', 'debug'],
        }
        
        for exchange in exchanges:
            text_content = ""
            if 'user_message' in exchange:
                text_content += exchange['user_message'].lower()
            if 'assistant_response' in exchange:
                text_content += " " + exchange['assistant_response'].lower()
            
            for topic, keywords in topic_keywords.items():
                if any(keyword in text_content for keyword in keywords):
                    topics.add(topic)
        
        return list(topics)
    
    def _generate_conversation_summary(
        self, 
        exchanges: List[Dict], 
        participants: List[str]
    ) -> str:
        """Generate a summary of the conversation"""
        if not exchanges:
            return "Empty conversation"
        
        participant_str = ", ".join(participants)
        exchange_count = len(exchanges)
        
        # Get first user message for context
        first_message = ""
        for exchange in exchanges:
            if 'user_message' in exchange and exchange['user_message']:
                first_message = exchange['user_message'][:100]
                break
        
        summary = f"Conversation between {participant_str} ({exchange_count} exchanges)"
        if first_message:
            summary += f". Started with: {first_message}..."
        
        return summary
    
    def search_conversations(
        self,
        query: Optional[str] = None,
        participants: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        topics: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search for conversations"""
        try:
            # Parse date strings
            start_dt = None
            end_dt = None
            
            if start_date:
                start_dt = self._parse_timestamp(start_date)
            if end_date:
                end_dt = self._parse_timestamp(end_date)
            
            # Perform search
            results = self.database.search_episodes(
                query=query,
                participants=participants,
                start_date=start_dt,
                end_date=end_dt,
                topics=topics,
                limit=limit
            )
            
            # Update statistics
            with self.lock:
                self.stats['searches_performed'] += 1
                self.stats['episodes_retrieved'] += len(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching conversations: {e}")
            raise
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a specific conversation by ID"""
        try:
            result = self.database.get_episode(conversation_id)
            
            if result:
                with self.lock:
                    self.stats['episodes_retrieved'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            raise
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """Get recent conversations"""
        try:
            results = self.database.get_recent_episodes(limit)
            
            with self.lock:
                self.stats['episodes_retrieved'] += len(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting recent conversations: {e}")
            raise
    
    def export_conversation_text(self, conversation_id: str) -> Optional[str]:
        """Export conversation as human-readable text"""
        try:
            return self.database.export_episode_text(conversation_id)
        except Exception as e:
            logger.error(f"Error exporting conversation {conversation_id}: {e}")
            raise
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        try:
            # Get database statistics
            db_stats = self.database.get_statistics()
            
            # Service uptime
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            
            return {
                'service_id': self.service_id,
                'uptime_seconds': uptime,
                'uptime_hours': round(uptime / 3600, 2),
                'database_path': str(self.db_path),
                'service_stats': self.stats.copy(),
                'database_stats': db_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting service stats: {e}")
            raise

# Global service instance
episodic_service = EpisodicMemoryService(
    db_path=os.getenv('EPISODIC_DB_PATH', '/tmp/episodic_memory.db')
)

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
        "service": "episodic_memory",
        "timestamp": datetime.utcnow().isoformat(),
        "service_id": episodic_service.service_id,
        "database_path": str(episodic_service.db_path),
        "request_id": g.request_id
    })

@app.route('/archive', methods=['POST'])
def archive_conversation():
    """Archive a conversation from working memory"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No JSON data provided",
                "request_id": g.request_id
            }), 400
        
        conversation_data = data.get('conversation_data', {})
        trigger_reason = data.get('trigger_reason', 'manual')
        
        if not conversation_data:
            return jsonify({
                "status": "error",
                "message": "conversation_data is required",
                "request_id": g.request_id
            }), 400
        
        conversation_id = episodic_service.archive_conversation(
            conversation_data, trigger_reason
        )
        
        return jsonify({
            "status": "success",
            "conversation_id": conversation_id,
            "message": f"Conversation archived successfully",
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error in archive endpoint (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/search', methods=['GET'])
def search_conversations():
    """Search for conversations"""
    try:
        # Get query parameters
        query = request.args.get('query')
        participants = request.args.getlist('participants')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        topics = request.args.getlist('topics')
        limit = int(request.args.get('limit', 20))
        
        results = episodic_service.search_conversations(
            query=query,
            participants=participants if participants else None,
            start_date=start_date,
            end_date=end_date,
            topics=topics if topics else None,
            limit=limit
        )
        
        return jsonify({
            "status": "success",
            "results": results,
            "count": len(results),
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error in search endpoint (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get a specific conversation"""
    try:
        result = episodic_service.get_conversation(conversation_id)
        
        if not result:
            return jsonify({
                "status": "error",
                "message": "Conversation not found",
                "request_id": g.request_id
            }), 404
        
        return jsonify({
            "status": "success",
            "conversation": result,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting conversation (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/conversation/<conversation_id>/export', methods=['GET'])
def export_conversation(conversation_id):
    """Export conversation as text"""
    try:
        text_export = episodic_service.export_conversation_text(conversation_id)
        
        if not text_export:
            return jsonify({
                "status": "error",
                "message": "Conversation not found",
                "request_id": g.request_id
            }), 404
        
        return jsonify({
            "status": "success",
            "conversation_id": conversation_id,
            "text_export": text_export,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error exporting conversation (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/recent', methods=['GET'])
def get_recent_conversations():
    """Get recent conversations"""
    try:
        limit = int(request.args.get('limit', 10))
        results = episodic_service.get_recent_conversations(limit)
        
        return jsonify({
            "status": "success",
            "conversations": results,
            "count": len(results),
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting recent conversations (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

@app.route('/stats', methods=['GET'])
def get_service_stats():
    """Get service statistics"""
    try:
        stats = episodic_service.get_service_stats()
        
        return jsonify({
            "status": "success",
            "stats": stats,
            "request_id": g.request_id
        })
    
    except Exception as e:
        logger.error(f"Error getting service stats (request: {g.request_id}): {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": g.request_id
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('EPISODIC_PORT', 8005))
    logger.info(f"Starting Episodic Memory service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)