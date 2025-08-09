#!/usr/bin/env python3
"""
Episodic Memory Database Layer
Handles SQLite operations for conversation episode storage and retrieval
"""
import sqlite3
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class EpisodicDatabase:
    """
    Database layer for episodic memory storage
    Handles conversation episodes with rich metadata and search capabilities
    """
    
    def __init__(self, db_path: str):
        """Initialize episodic database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_schema()
        logger.info(f"Episodic database initialized at {self.db_path}")
    
    def _init_schema(self):
        """Create database tables and indexes"""
        with self._get_connection() as conn:
            # Main episodes table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT UNIQUE NOT NULL,
                    start_timestamp DATETIME NOT NULL,
                    end_timestamp DATETIME NOT NULL,
                    participants TEXT NOT NULL,  -- JSON array
                    exchange_count INTEGER NOT NULL,
                    summary TEXT,
                    full_conversation TEXT NOT NULL,  -- Complete JSON
                    topics TEXT,  -- JSON array
                    trigger_reason TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Search optimization indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_start_timestamp ON episodes(start_timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_end_timestamp ON episodes(end_timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_participants ON episodes(participants)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_topics ON episodes(topics)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trigger_reason ON episodes(trigger_reason)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON episodes(created_at)')
            
            # Full-text search for conversation content
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
                    conversation_id,
                    summary,
                    full_conversation,
                    topics,
                    content='episodes',
                    content_rowid='id'
                )
            ''')
            
            # Triggers to keep FTS in sync
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS episodes_fts_insert AFTER INSERT ON episodes BEGIN
                    INSERT INTO episodes_fts(rowid, conversation_id, summary, full_conversation, topics)
                    VALUES (new.id, new.conversation_id, new.summary, new.full_conversation, new.topics);
                END
            ''')
            
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS episodes_fts_delete AFTER DELETE ON episodes BEGIN
                    DELETE FROM episodes_fts WHERE rowid = old.id;
                END
            ''')
            
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS episodes_fts_update AFTER UPDATE ON episodes BEGIN
                    DELETE FROM episodes_fts WHERE rowid = old.id;
                    INSERT INTO episodes_fts(rowid, conversation_id, summary, full_conversation, topics)
                    VALUES (new.id, new.conversation_id, new.summary, new.full_conversation, new.topics);
                END
            ''')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            conn.row_factory = sqlite3.Row
            # Enable foreign keys and WAL mode for better performance
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('PRAGMA journal_mode = WAL')
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def store_episode(
        self,
        conversation_id: str,
        start_timestamp: datetime,
        end_timestamp: datetime,
        participants: List[str],
        exchanges: List[Dict],
        trigger_reason: str,
        summary: Optional[str] = None,
        topics: Optional[List[str]] = None
    ) -> str:
        """
        Store a conversation episode
        
        Args:
            conversation_id: Unique identifier for this conversation
            start_timestamp: When conversation started
            end_timestamp: When conversation ended
            participants: List of participants (humans, agents, etc.)
            exchanges: List of conversation exchanges
            trigger_reason: Why this episode was archived
            summary: Optional conversation summary
            topics: Optional list of topics discussed
            
        Returns:
            conversation_id of stored episode
        """
        try:
            # Generate conversation_id if not provided
            if not conversation_id:
                conversation_id = f"episode_{uuid.uuid4()}"
            
            # Prepare data
            participants_json = json.dumps(participants)
            full_conversation_json = json.dumps(exchanges, indent=2)
            topics_json = json.dumps(topics or [])
            exchange_count = len(exchanges)
            
            # Auto-generate summary if not provided
            if not summary:
                summary = self._generate_summary(exchanges, participants)
            
            # Store in database
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO episodes (
                        conversation_id, start_timestamp, end_timestamp,
                        participants, exchange_count, summary,
                        full_conversation, topics, trigger_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    conversation_id, start_timestamp, end_timestamp,
                    participants_json, exchange_count, summary,
                    full_conversation_json, topics_json, trigger_reason
                ))
                conn.commit()
            
            logger.info(f"Stored episode {conversation_id} with {exchange_count} exchanges")
            return conversation_id
            
        except Exception as e:
            logger.error(f"Error storing episode: {e}")
            raise
    
    def _generate_summary(self, exchanges: List[Dict], participants: List[str]) -> str:
        """Generate a basic summary of the conversation"""
        if not exchanges:
            return "Empty conversation"
        
        participant_list = ", ".join(participants)
        first_exchange = exchanges[0].get('user_message', '')[:100]
        exchange_count = len(exchanges)
        
        summary = f"Conversation with {participant_list} ({exchange_count} exchanges). "
        if first_exchange:
            summary += f"Started with: {first_exchange}..."
        
        return summary
    
    def get_episode(self, conversation_id: str) -> Optional[Dict]:
        """Get a specific episode by conversation_id"""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    'SELECT * FROM episodes WHERE conversation_id = ?',
                    (conversation_id,)
                ).fetchone()
                
                if row:
                    return self._row_to_dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting episode {conversation_id}: {e}")
            raise
    
    def search_episodes(
        self,
        query: Optional[str] = None,
        participants: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        topics: Optional[List[str]] = None,
        trigger_reason: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Search episodes with various filters
        
        Args:
            query: Full-text search query
            participants: Filter by participants
            start_date: Episodes after this date
            end_date: Episodes before this date
            topics: Filter by topics
            trigger_reason: Filter by trigger reason
            limit: Maximum results to return
            offset: Number of results to skip
            
        Returns:
            List of matching episodes
        """
        try:
            conditions = []
            params = []
            
            # Build base query
            if query:
                # Use full-text search
                base_query = '''
                    SELECT episodes.* FROM episodes
                    JOIN episodes_fts ON episodes.id = episodes_fts.rowid
                    WHERE episodes_fts MATCH ?
                '''
                # Don't add to conditions again, already in WHERE clause
                params.append(query)
            else:
                base_query = 'SELECT * FROM episodes WHERE 1=1'
            
            # Add filters
            if participants:
                # Search for any of the participants
                participant_conditions = []
                for participant in participants:
                    participant_conditions.append("participants LIKE ?")
                    params.append(f'%"{participant}"%')
                conditions.append(f"({' OR '.join(participant_conditions)})")
            
            if start_date:
                conditions.append("start_timestamp >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("end_timestamp <= ?")
                params.append(end_date)
            
            if topics:
                # Search for any of the topics
                topic_conditions = []
                for topic in topics:
                    topic_conditions.append("topics LIKE ?")
                    params.append(f'%"{topic}"%')
                conditions.append(f"({' OR '.join(topic_conditions)})")
            
            if trigger_reason:
                conditions.append("trigger_reason = ?")
                params.append(trigger_reason)
            
            # Combine conditions
            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            
            # Add ordering and pagination
            base_query += " ORDER BY start_timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            with self._get_connection() as conn:
                rows = conn.execute(base_query, params).fetchall()
                return [self._row_to_dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error searching episodes: {e}")
            raise
    
    def get_recent_episodes(self, limit: int = 10) -> List[Dict]:
        """Get the most recent episodes"""
        return self.search_episodes(limit=limit)
    
    def get_episodes_by_timerange(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 50
    ) -> List[Dict]:
        """Get episodes within a specific time range"""
        return self.search_episodes(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self._get_connection() as conn:
                # Basic stats
                total_episodes = conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]
                
                # Participants stats
                participant_stats = conn.execute('''
                    SELECT participants, COUNT(*) as count
                    FROM episodes
                    GROUP BY participants
                    ORDER BY count DESC
                    LIMIT 10
                ''').fetchall()
                
                # Trigger reason stats
                trigger_stats = conn.execute('''
                    SELECT trigger_reason, COUNT(*) as count
                    FROM episodes
                    GROUP BY trigger_reason
                    ORDER BY count DESC
                ''').fetchall()
                
                # Exchange count stats
                exchange_stats = conn.execute('''
                    SELECT 
                        AVG(exchange_count) as avg_exchanges,
                        MIN(exchange_count) as min_exchanges,
                        MAX(exchange_count) as max_exchanges,
                        SUM(exchange_count) as total_exchanges
                    FROM episodes
                ''').fetchone()
                
                # Recent activity
                recent_activity = conn.execute('''
                    SELECT DATE(start_timestamp) as date, COUNT(*) as count
                    FROM episodes
                    WHERE start_timestamp >= date('now', '-30 days')
                    GROUP BY DATE(start_timestamp)
                    ORDER BY date DESC
                ''').fetchall()
                
                return {
                    'total_episodes': total_episodes,
                    'participant_distribution': [dict(row) for row in participant_stats],
                    'trigger_distribution': [dict(row) for row in trigger_stats],
                    'exchange_statistics': dict(exchange_stats) if exchange_stats else {},
                    'recent_activity': [dict(row) for row in recent_activity]
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise
    
    def delete_episode(self, conversation_id: str) -> bool:
        """Delete an episode (use with caution!)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'DELETE FROM episodes WHERE conversation_id = ?',
                    (conversation_id,)
                )
                conn.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted episode {conversation_id}")
                else:
                    logger.warning(f"Episode {conversation_id} not found for deletion")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Error deleting episode {conversation_id}: {e}")
            raise
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert database row to dictionary with JSON parsing"""
        episode = dict(row)
        
        # Parse JSON fields
        try:
            episode['participants'] = json.loads(episode['participants'])
        except (json.JSONDecodeError, TypeError):
            episode['participants'] = []
        
        try:
            episode['full_conversation'] = json.loads(episode['full_conversation'])
        except (json.JSONDecodeError, TypeError):
            episode['full_conversation'] = []
        
        try:
            episode['topics'] = json.loads(episode['topics'])
        except (json.JSONDecodeError, TypeError):
            episode['topics'] = []
        
        return episode
    
    def export_episode_text(self, conversation_id: str) -> Optional[str]:
        """Export episode as human-readable text"""
        episode = self.get_episode(conversation_id)
        if not episode:
            return None
        
        text_lines = []
        text_lines.append(f"=== Conversation Episode: {conversation_id} ===")
        text_lines.append(f"Started: {episode['start_timestamp']}")
        text_lines.append(f"Ended: {episode['end_timestamp']}")
        text_lines.append(f"Participants: {', '.join(episode['participants'])}")
        text_lines.append(f"Exchanges: {episode['exchange_count']}")
        text_lines.append(f"Trigger: {episode['trigger_reason']}")
        
        if episode['topics']:
            text_lines.append(f"Topics: {', '.join(episode['topics'])}")
        
        if episode['summary']:
            text_lines.append(f"Summary: {episode['summary']}")
        
        text_lines.append("\n" + "="*50 + "\n")
        
        # Format conversation exchanges
        for i, exchange in enumerate(episode['full_conversation'], 1):
            text_lines.append(f"Exchange {i}:")
            if 'user_message' in exchange:
                text_lines.append(f"User: {exchange['user_message']}")
            if 'assistant_response' in exchange:
                text_lines.append(f"Assistant: {exchange['assistant_response']}")
            if 'timestamp' in exchange:
                text_lines.append(f"Time: {exchange['timestamp']}")
            text_lines.append("")
        
        return "\n".join(text_lines)