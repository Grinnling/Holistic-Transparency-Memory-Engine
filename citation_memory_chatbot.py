#!/usr/bin/env python3
"""
Citation-Based Memory Chatbot
Test platform for biological-style memory with citations
"""

import json
import uuid
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import gradio as gr

class CitationMemorySystem:
    def __init__(self, db_path="chat_memory.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for persistent memory"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                title TEXT,
                summary TEXT
            )
        ''')
        
        # Working memory (recent messages)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS working_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                importance_score REAL,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        ''')
        
        # Citations (long-term important information)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS citations (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                content TEXT,
                citation_type TEXT,
                confidence REAL,
                created_at TEXT,
                created_by TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        ''')
        
        # Citation relationships (what citations are related)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS citation_relationships (
                citation_a TEXT,
                citation_b TEXT,
                relationship_type TEXT,
                strength REAL,
                FOREIGN KEY (citation_a) REFERENCES citations (id),
                FOREIGN KEY (citation_b) REFERENCES citations (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_conversation(self, title: str = None) -> str:
        """Create new conversation session"""
        conv_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO conversations (id, created_at, title)
            VALUES (?, ?, ?)
        ''', (conv_id, datetime.now().isoformat(), title or "New Conversation"))
        
        conn.commit()
        conn.close()
        return conv_id
    
    def add_to_working_memory(self, conv_id: str, role: str, content: str, importance: float = 0.5):
        """Add message to working memory with importance assessment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO working_memory (conversation_id, role, content, timestamp, importance_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (conv_id, role, content, datetime.now().isoformat(), importance))
        
        conn.commit()
        conn.close()
        
        # Keep working memory manageable (last 20 messages)
        self.trim_working_memory(conv_id, keep_last=20)
    
    def trim_working_memory(self, conv_id: str, keep_last: int = 20):
        """Keep working memory focused on recent exchanges"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM working_memory 
            WHERE conversation_id = ? 
            AND id NOT IN (
                SELECT id FROM working_memory 
                WHERE conversation_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            )
        ''', (conv_id, conv_id, keep_last))
        
        conn.commit()
        conn.close()
    
    def create_citation(self, conv_id: str, content: str, citation_type: str = "FACT", confidence: float = 0.8) -> str:
        """Create a new citation for important information"""
        citation_id = f"CITE-{len(self.get_citations(conv_id)) + 1}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO citations (id, conversation_id, content, citation_type, confidence, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (citation_id, conv_id, content, citation_type, confidence, datetime.now().isoformat(), "system"))
        
        conn.commit()
        conn.close()
        return citation_id
    
    def get_working_memory(self, conv_id: str, last_n: int = 10) -> List[Dict]:
        """Get recent working memory for context"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content, timestamp, importance_score
            FROM working_memory 
            WHERE conversation_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (conv_id, last_n))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"role": r[0], "content": r[1], "timestamp": r[2], "importance": r[3]} 
                for r in reversed(results)]
    
    def get_citations(self, conv_id: str) -> List[Dict]:
        """Get all citations for a conversation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, content, citation_type, confidence, created_at, usage_count
            FROM citations 
            WHERE conversation_id = ? 
            ORDER BY usage_count DESC, created_at DESC
        ''', (conv_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"id": r[0], "content": r[1], "type": r[2], "confidence": r[3], 
                "created": r[4], "usage": r[5]} for r in results]
    
    def find_relevant_citations(self, conv_id: str, query: str, limit: int = 5) -> List[Dict]:
        """Find citations relevant to current query (simple keyword matching for now)"""
        citations = self.get_citations(conv_id)
        query_lower = query.lower()
        
        # Simple relevance scoring based on keyword overlap
        relevant = []
        for citation in citations:
            content_lower = citation["content"].lower()
            
            # Count keyword matches
            query_words = set(query_lower.split())
            citation_words = set(content_lower.split())
            overlap = len(query_words.intersection(citation_words))
            
            if overlap > 0:
                relevance_score = overlap / len(query_words)
                citation["relevance"] = relevance_score
                relevant.append(citation)
        
        # Sort by relevance and usage
        relevant.sort(key=lambda x: (x["relevance"], x["usage"]), reverse=True)
        return relevant[:limit]
    
    def update_citation_usage(self, citation_id: str):
        """Track citation usage for importance assessment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE citations 
            SET usage_count = usage_count + 1, last_used = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), citation_id))
        
        conn.commit()
        conn.close()

class BiologicalMemoryChatbot:
    def __init__(self):
        self.memory = CitationMemorySystem()
        self.current_conversation = None
    
    def assess_importance(self, message: str, role: str) -> float:
        """Assess importance of a message for memory retention"""
        importance = 0.5  # Default
        
        # Simple heuristics for importance
        message_lower = message.lower()
        
        # Higher importance indicators
        if any(word in message_lower for word in ["name", "important", "remember", "goal", "problem"]):
            importance += 0.2
        if any(word in message_lower for word in ["error", "failed", "broken", "issue"]):
            importance += 0.3
        if any(word in message_lower for word in ["solution", "fixed", "works", "success"]):
            importance += 0.3
        if role == "user" and ("my" in message_lower or "i" in message_lower):
            importance += 0.1
        
        return min(importance, 1.0)
    
    def should_create_citation(self, message: str, role: str, importance: float) -> tuple:
        """Determine if message should become a citation"""
        message_lower = message.lower()
        
        # Citation triggers
        if importance > 0.7:
            if any(word in message_lower for word in ["name", "goal", "requirement"]):
                return True, "FACT"
            elif any(word in message_lower for word in ["error", "failed", "broken"]):
                return True, "FAILURE"
            elif any(word in message_lower for word in ["solution", "works", "fixed"]):
                return True, "SUCCESS"
            elif any(word in message_lower for word in ["important", "remember", "constraint"]):
                return True, "CONSTRAINT"
        
        return False, None
    
    def build_smart_context(self, conv_id: str, current_message: str) -> str:
        """Build context using biological memory approach"""
        context_parts = []
        
        # 1. Working memory (recent exchanges)
        working_memory = self.memory.get_working_memory(conv_id, last_n=8)
        if working_memory:
            context_parts.append("=== Recent Conversation ===")
            for msg in working_memory:
                context_parts.append(f"{msg['role'].title()}: {msg['content']}")
        
        # 2. Relevant citations (targeted retrieval)
        relevant_citations = self.memory.find_relevant_citations(conv_id, current_message, limit=3)
        if relevant_citations:
            context_parts.append("\n=== Relevant Background ===")
            for citation in relevant_citations:
                context_parts.append(f"[{citation['id']}] {citation['content']} (Type: {citation['type']})")
                # Track usage
                self.memory.update_citation_usage(citation['id'])
        
        # 3. Current message
        context_parts.append(f"\n=== Current Message ===")
        context_parts.append(f"User: {current_message}")
        
        return "\n".join(context_parts)
    
    def generate_response(self, message: str, conv_id: str) -> str:
        """Generate response using biological memory approach"""
        # Assess importance of user message
        importance = self.assess_importance(message, "user")
        
        # Add to working memory
        self.memory.add_to_working_memory(conv_id, "user", message, importance)
        
        # Check if should create citation
        should_cite, cite_type = self.should_create_citation(message, "user", importance)
        if should_cite:
            citation_id = self.memory.create_citation(conv_id, message, cite_type)
        
        # Build smart context (not everything!)
        context = self.build_smart_context(conv_id, message)
        
        # Simple response generation (replace with real model)
        response = self.mock_ai_response(context, message)
        
        # Assess response importance
        response_importance = self.assess_importance(response, "assistant")
        
        # Add response to working memory
        self.memory.add_to_working_memory(conv_id, "assistant", response, response_importance)
        
        # Check if response should be cited
        should_cite_response, cite_type_response = self.should_create_citation(response, "assistant", response_importance)
        if should_cite_response:
            self.memory.create_citation(conv_id, response, cite_type_response)
        
        return response
    
    def mock_ai_response(self, context: str, message: str) -> str:
        """Mock AI response - replace with real model integration"""
        message_lower = message.lower()
        
        # Check for memory-related queries
        if "what" in message_lower and ("name" in message_lower or "called" in message_lower):
            if "name" in context.lower():
                # Extract name from context
                lines = context.split('\n')
                for line in lines:
                    if "name" in line.lower() and ("my name is" in line.lower() or "i'm" in line.lower()):
                        name_part = line.split("my name is")[-1] if "my name is" in line.lower() else line.split("i'm")[-1]
                        name = name_part.strip().split()[0]
                        return f"Your name is {name}. I found this in [CITE-1] which I reference frequently."
                
        # Check for goal/purpose queries
        elif "goal" in message_lower or "purpose" in message_lower or "doing" in message_lower:
            if "goal" in context.lower() or "project" in context.lower():
                return "Based on our conversation history and citations, I can see we're working on AI agent development with citation-based memory systems."
        
        # Pattern recognition responses
        elif "remember" in message_lower:
            citations = self.memory.get_citations(self.current_conversation)
            if citations:
                return f"I have {len(citations)} citations stored about our conversation, including facts, constraints, and solutions we've discovered."
            else:
                return "I'm building up memory as we talk. Important information gets stored as citations for easy reference."
        
        # Default responses
        if "hello" in message_lower or "hi" in message_lower:
            return "Hello! I'm testing biological-style memory with citations. Tell me something important about yourself or our project!"
        elif "my name is" in message_lower:
            name = message_lower.split("my name is")[-1].strip()
            return f"Nice to meet you, {name}! I'll remember that in my citation system."
        else:
            return "I understand. I'm processing this with my citation-based memory system - important information gets stored for future reference, while routine exchanges stay in working memory."

def create_chatbot_interface():
    """Create Gradio interface for testing citation memory"""
    
    chatbot = BiologicalMemoryChatbot()
    
    def chat_response(message, history, conversation_dropdown):
        # Create new conversation if needed
        if not conversation_dropdown or conversation_dropdown == "Select Conversation":
            conv_id = chatbot.memory.create_conversation(f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            chatbot.current_conversation = conv_id
        else:
            chatbot.current_conversation = conversation_dropdown
        
        # Generate response
        response = chatbot.generate_response(message, chatbot.current_conversation)
        
        # Update history
        if history is None:
            history = []
        history.append([message, response])
        
        return "", history
    
    def get_memory_info(conversation_dropdown):
        """Display current memory state"""
        if not conversation_dropdown or conversation_dropdown == "Select Conversation":
            return "No conversation selected", "No conversation selected"
        
        # Working memory
        working_memory = chatbot.memory.get_working_memory(conversation_dropdown, last_n=10)
        working_text = "=== Working Memory (Recent Exchanges) ===\n"
        for msg in working_memory:
            working_text += f"{msg['role'].title()}: {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}\n"
            working_text += f"   Importance: {msg['importance']:.2f}\n\n"
        
        # Citations
        citations = chatbot.memory.get_citations(conversation_dropdown)
        citation_text = "=== Citations (Long-term Memory) ===\n"
        for cite in citations:
            citation_text += f"[{cite['id']}] {cite['content']}\n"
            citation_text += f"   Type: {cite['type']} | Confidence: {cite['confidence']:.2f} | Used: {cite['usage']} times\n\n"
        
        return working_text, citation_text
    
    def get_conversation_list():
        """Get list of conversations for dropdown"""
        conn = sqlite3.connect(chatbot.memory.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, title FROM conversations ORDER BY created_at DESC')
        convs = cursor.fetchall()
        conn.close()
        
        return [f"{conv[1]} ({conv[0][:8]}...)" for conv in convs] if convs else ["Select Conversation"]
    
    with gr.Blocks(title="Citation Memory Chatbot") as demo:
        gr.Markdown("# 🧠 Citation-Based Memory Chatbot\nTesting biological-style memory with working memory + citations")
        
        with gr.Row():
            with gr.Column(scale=2):
                conversation_dropdown = gr.Dropdown(
                    choices=get_conversation_list(),
                    value="Select Conversation",
                    label="Conversation",
                    interactive=True
                )
                
                chatbot_interface = gr.Chatbot(
                    height=400,
                    label="Chat (with Citation Memory)"
                )
                
                msg_input = gr.Textbox(
                    placeholder="Try: 'My name is John' then later 'What's my name?'",
                    label="Message"
                )
                
                with gr.Row():
                    submit_btn = gr.Button("Send", variant="primary")
                    clear_btn = gr.Button("Clear")
                    refresh_btn = gr.Button("Refresh Conversations")
            
            with gr.Column(scale=1):
                gr.Markdown("### 🧠 Memory State")
                
                working_memory_display = gr.Textbox(
                    label="Working Memory",
                    lines=8,
                    max_lines=8
                )
                
                citations_display = gr.Textbox(
                    label="Citations",
                    lines=8,
                    max_lines=8
                )
                
                memory_refresh_btn = gr.Button("Refresh Memory View")
        
        # Event handlers
        submit_btn.click(
            chat_response,
            inputs=[msg_input, chatbot_interface, conversation_dropdown],
            outputs=[msg_input, chatbot_interface]
        ).then(
            get_memory_info,
            inputs=[conversation_dropdown],
            outputs=[working_memory_display, citations_display]
        )
        
        msg_input.submit(
            chat_response,
            inputs=[msg_input, chatbot_interface, conversation_dropdown],
            outputs=[msg_input, chatbot_interface]
        ).then(
            get_memory_info,
            inputs=[conversation_dropdown],
            outputs=[working_memory_display, citations_display]
        )
        
        memory_refresh_btn.click(
            get_memory_info,
            inputs=[conversation_dropdown],
            outputs=[working_memory_display, citations_display]
        )
        
        refresh_btn.click(
            lambda: gr.Dropdown(choices=get_conversation_list()),
            outputs=[conversation_dropdown]
        )
        
        clear_btn.click(
            lambda: (None, ""),
            outputs=[chatbot_interface, msg_input]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_chatbot_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
