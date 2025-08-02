#!/usr/bin/env python3
"""
Simple Context-Aware Chatbot Example
Shows how conversation context/memory actually works
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any

class SimpleContextChatbot:
    def __init__(self):
        # In-memory storage (resets when program ends)
        self.conversations = {}
        
    def create_session(self) -> str:
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        self.conversations[session_id] = {
            "created": datetime.now().isoformat(),
            "messages": []
        }
        return session_id
    
    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the conversation history"""
        if session_id not in self.conversations:
            raise ValueError(f"Session {session_id} not found")
            
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        self.conversations[session_id]["messages"].append(message)
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get the full conversation history for a session"""
        if session_id not in self.conversations:
            return []
        return self.conversations[session_id]["messages"]
    
    def format_context_for_model(self, session_id: str) -> str:
        """Format conversation history for sending to AI model"""
        history = self.get_conversation_history(session_id)
        
        # Convert to a format an AI model would expect
        formatted = "Conversation History:\n"
        for msg in history:
            formatted += f"{msg['role'].title()}: {msg['content']}\n"
        
        return formatted
    
    def simulate_ai_response(self, session_id: str, user_message: str) -> str:
        """Simulate an AI response (replace this with real model calls)"""
        # Add user message to history
        self.add_message(session_id, "user", user_message)
        
        # Get full context to send to AI model
        context = self.format_context_for_model(session_id)
        
        # SIMULATE AI MODEL CALL
        # In reality, you'd send 'context' to your AI model
        # For demo, we'll do simple pattern matching
        
        response = self._mock_ai_response(user_message, context)
        
        # Add AI response to history
        self.add_message(session_id, "assistant", response)
        
        return response
    
    def _mock_ai_response(self, current_message: str, full_context: str) -> str:
        """Mock AI response - replace with real model"""
        current_lower = current_message.lower()
        
        # Check if name was mentioned earlier in context
        if "my name is" in full_context.lower() and "what" in current_lower and "name" in current_lower:
            # Extract name from context
            lines = full_context.split('\n')
            for line in lines:
                if "my name is" in line.lower():
                    name = line.split("my name is")[-1].strip()
                    return f"Your name is {name}"
        
        # Other simple responses
        if "my name is" in current_lower:
            name = current_message.lower().split("my name is")[-1].strip()
            return f"Nice to meet you, {name}!"
        elif "hello" in current_lower or "hi" in current_lower:
            return "Hello! How can I help you today?"
        elif "how are you" in current_lower:
            return "I'm doing well, thank you for asking!"
        else:
            return "I understand. Can you tell me more about that?"
    
    def print_conversation(self, session_id: str):
        """Print the entire conversation history"""
        history = self.get_conversation_history(session_id)
        
        print(f"\n=== Conversation {session_id[:8]}... ===")
        for msg in history:
            role_display = "🧑 User" if msg["role"] == "user" else "🤖 Bot"
            print(f"{role_display}: {msg['content']}")
        print("=" * 40)

def demo_context_retention():
    """Demonstrate how context retention works"""
    
    print("🤖 Context Retention Demo")
    print("This shows how chatbots 'remember' previous messages\n")
    
    # Create chatbot and session
    bot = SimpleContextChatbot()
    session = bot.create_session()
    
    # Simulate a conversation
    conversations = [
        "Hello there!",
        "My name is Alice",
        "I'm a software developer",
        "What's my name?",
        "What do I do for work?"
    ]
    
    for user_msg in conversations:
        print(f"🧑 User: {user_msg}")
        response = bot.simulate_ai_response(session, user_msg)
        print(f"🤖 Bot: {response}")
        
        # Show what gets sent to AI model
        print(f"📝 Context sent to model:")
        context = bot.format_context_for_model(session)
        print(f"   {context.replace(chr(10), chr(10) + '   ')}")
        print("-" * 50)
    
    # Show final conversation
    bot.print_conversation(session)

def demo_multiple_sessions():
    """Show how different sessions maintain separate context"""
    
    print("\n🔄 Multiple Sessions Demo")
    print("Different conversations maintain separate context\n")
    
    bot = SimpleContextChatbot()
    
    # Session 1
    session1 = bot.create_session()
    bot.simulate_ai_response(session1, "My name is Bob")
    bot.simulate_ai_response(session1, "What's my name?")
    
    # Session 2
    session2 = bot.create_session()
    bot.simulate_ai_response(session2, "My name is Carol")
    bot.simulate_ai_response(session2, "What's my name?")
    
    # Show both conversations
    bot.print_conversation(session1)
    bot.print_conversation(session2)

if __name__ == "__main__":
    demo_context_retention()
    demo_multiple_sessions()
    
    print("\n💡 Key Takeaways:")
    print("1. Models don't 'remember' - they get full conversation history each time")
    print("2. Context is stored externally (memory, database, files)")
    print("3. Each request includes ALL previous messages")
    print("4. Different sessions maintain separate conversation histories")
    print("5. 'Memory' is just sending the right context to the model")
