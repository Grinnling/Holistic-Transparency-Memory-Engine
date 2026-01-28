#!/usr/bin/env python3
"""
Simple Chat Interface for Memory System
Interactive chat that uses your memory services
"""

import requests
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List
import readline  # For better input experience

class MemoryChatInterface:
    def __init__(self):
        self.services = {
            'working_memory': 'http://localhost:5001',
            'curator': 'http://localhost:8004',
            'mcp_logger': 'http://localhost:8001'
        }
        
        self.conversation_id = str(uuid.uuid4())
        self.conversation_history = []
        self.current_session_id = None
        self.services_healthy = False
        
        # Colors for terminal output
        self.colors = {
            'user': '\033[94m',      # Blue
            'assistant': '\033[92m',  # Green
            'system': '\033[93m',     # Yellow
            'error': '\033[91m',      # Red
            'reset': '\033[0m'        # Reset
        }
    
    def print_colored(self, text, color_key='reset'):
        """Print colored text to terminal"""
        print(f"{self.colors[color_key]}{text}{self.colors['reset']}")
    
    def check_services(self):
        """Check if all services are running"""
        self.print_colored("\n🔍 Checking services...", 'system')
        
        all_healthy = True
        for service_name, url in self.services.items():
            try:
                response = requests.get(f"{url}/health", timeout=2)
                if response.status_code == 200:
                    print(f"  ✅ {service_name}: Online")
                else:
                    print(f"  ❌ {service_name}: Error")
                    all_healthy = False
            except:
                print(f"  ❌ {service_name}: Offline")
                all_healthy = False
        
        self.services_healthy = all_healthy
        return all_healthy
    
    def store_exchange(self, user_message: str, assistant_response: str):
        """Store conversation exchange in working memory"""
        try:
            response = requests.post(
                f"{self.services['working_memory']}/working-memory",
                json={
                    "user_message": user_message,
                    "assistant_response": assistant_response,
                    "context_used": ["chat_interface"]
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                exchange_id = result.get('exchange', {}).get('exchange_id', 'unknown')
                return exchange_id
            
        except Exception as e:
            self.print_colored(f"Failed to store in memory: {e}", 'error')
        
        return None
    
    def validate_exchange(self, user_message: str, assistant_response: str):
        """Validate exchange with curator"""
        try:
            response = requests.post(
                f"{self.services['curator']}/validate",
                json={
                    "exchange_data": {
                        "user_message": user_message,
                        "assistant_response": assistant_response,
                        "exchange_id": str(uuid.uuid4())
                    },
                    "validation_type": "basic"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                validation = result.get('validation', {}).get('result', {})
                return validation
                
        except Exception as e:
            self.print_colored(f"Validation failed: {e}", 'error')
        
        return None
    
    def start_group_chat(self, topic: str):
        """Start a group chat validation session"""
        try:
            response = requests.post(
                f"{self.services['curator']}/group-chat/start",
                json={
                    "exchange_data": {
                        "user_message": topic,
                        "assistant_response": "Let's discuss this together."
                    },
                    "participants": ["user", "assistant", "curator"]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get('chat_session', {}).get('session_id')
                self.current_session_id = session_id
                return session_id
                
        except Exception as e:
            self.print_colored(f"Group chat failed: {e}", 'error')
        
        return None
    
    def add_to_group_chat(self, message: str, speaker: str = "user"):
        """Add message to current group chat"""
        if not self.current_session_id:
            return None
        
        try:
            response = requests.post(
                f"{self.services['curator']}/group-chat/{self.current_session_id}/message",
                json={
                    "speaker": speaker,
                    "message": message,
                    "message_type": "user"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            self.print_colored(f"Failed to add to group chat: {e}", 'error')
        
        return None
    
    def process_message(self, user_message: str) -> str:
        """Process user message through the system"""
        # For now, simulate AI response (later integrate with actual LLM)
        assistant_response = self.generate_simulated_response(user_message)
        
        # Store in working memory
        exchange_id = self.store_exchange(user_message, assistant_response)
        
        # Validate with curator
        validation = self.validate_exchange(user_message, assistant_response)
        
        # Add to history
        self.conversation_history.append({
            'user': user_message,
            'assistant': assistant_response,
            'exchange_id': exchange_id,
            'validation': validation,
            'timestamp': datetime.now().isoformat()
        })
        
        # Check validation results
        if validation:
            confidence = validation.get('confidence_score', 0)
            contradictions = validation.get('contradictions_detected', 0)
            
            if confidence < 0.5 or contradictions > 0:
                self.print_colored(
                    f"⚠️  Low confidence ({confidence:.2f}) or contradictions ({contradictions})",
                    'system'
                )
        
        return assistant_response
    
    def generate_simulated_response(self, user_message: str) -> str:
        """Generate simulated assistant response"""
        # Simple rule-based responses for testing
        responses = {
            'hello': "Hello! I'm your memory-enabled assistant. How can I help you today?",
            'test': "Testing the memory system. This exchange will be stored and validated.",
            'memory': "I can remember our conversations using the working memory service.",
            'help': "Commands: /memory (show history), /group (start group chat), /validate (check last exchange), /clear (clear memory), /quit (exit)",
            'complex': "This seems like a complex query that might need orchestration. Let me think about this step by step.",
        }
        
        # Check for keywords
        message_lower = user_message.lower()
        for keyword, response in responses.items():
            if keyword in message_lower:
                return response
        
        # Default response
        return f"I understand you said: '{user_message}'. This has been stored in my memory system."
    
    def show_memory(self):
        """Show conversation memory"""
        try:
            response = requests.get(
                f"{self.services['working_memory']}/working-memory",
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                context = result.get('context', [])
                
                self.print_colored("\n📚 Conversation Memory:", 'system')
                for i, exchange in enumerate(context[-5:], 1):  # Last 5 exchanges
                    print(f"\n  Exchange {i}:")
                    print(f"    User: {exchange.get('user_message', 'N/A')[:50]}...")
                    print(f"    Assistant: {exchange.get('assistant_response', 'N/A')[:50]}...")
                    print(f"    Time: {exchange.get('timestamp', 'N/A')}")
                
                summary = result.get('summary', {})
                print(f"\n  Buffer: {summary.get('current_size', 0)}/{summary.get('max_size', 0)}")
                
        except Exception as e:
            self.print_colored(f"Failed to retrieve memory: {e}", 'error')
    
    def handle_command(self, command: str):
        """Handle special commands"""
        if command == '/memory':
            self.show_memory()
        
        elif command == '/group':
            topic = input("Group chat topic: ")
            session_id = self.start_group_chat(topic)
            if session_id:
                self.print_colored(f"Started group chat: {session_id[:8]}...", 'system')
                self.print_colored("Messages will now go to group chat. Use /endgroup to stop.", 'system')
        
        elif command == '/endgroup':
            self.current_session_id = None
            self.print_colored("Ended group chat mode", 'system')
        
        elif command == '/validate':
            if self.conversation_history:
                last = self.conversation_history[-1]
                validation = last.get('validation', {})
                self.print_colored("\n🔍 Last Exchange Validation:", 'system')
                print(f"  Valid: {validation.get('is_valid', 'N/A')}")
                print(f"  Confidence: {validation.get('confidence_score', 'N/A')}")
                print(f"  Contradictions: {validation.get('contradictions_detected', 'N/A')}")
                print(f"  Uncertainty: {validation.get('uncertainty_level', 'N/A')}")
        
        elif command == '/clear':
            response = requests.delete(f"{self.services['working_memory']}/working-memory")
            self.print_colored("Cleared working memory", 'system')
        
        elif command == '/help':
            self.print_colored("\n📋 Available Commands:", 'system')
            print("  /memory   - Show conversation memory")
            print("  /group    - Start group chat mode")
            print("  /endgroup - End group chat mode")
            print("  /validate - Show last validation results")
            print("  /clear    - Clear working memory")
            print("  /quit     - Exit chat")
        
        else:
            self.print_colored(f"Unknown command: {command}", 'error')
    
    def run(self):
        """Main chat loop"""
        print("\n" + "="*60)
        self.print_colored("🧠 Memory-Enabled Chat Interface", 'system')
        print("="*60)
        
        # Check services
        if not self.check_services():
            self.print_colored("\n⚠️  Warning: Some services are offline!", 'error')
            print("The chat will work but some features may be unavailable.")
            print("\nTo start services:")
            print("  Terminal 1: python working_memory/service.py")
            print("  Terminal 2: python memory_curator/curator_service.py")
            print("  Terminal 3: python mcp_logger/server.py")
        else:
            self.print_colored("\n✅ All services online!", 'system')
        
        print("\nType /help for commands, /quit to exit")
        print("-"*60)
        
        # Main loop
        while True:
            try:
                # Get user input
                user_input = input(f"\n{self.colors['user']}You > {self.colors['reset']}")
                
                # Check for exit
                if user_input.lower() in ['/quit', 'exit', 'quit']:
                    self.print_colored("\n👋 Goodbye!", 'system')
                    break
                
                # Check for commands
                if user_input.startswith('/'):
                    self.handle_command(user_input)
                    continue
                
                # Process in group chat mode
                if self.current_session_id:
                    self.add_to_group_chat(user_input)
                    self.print_colored("Added to group chat", 'system')
                    continue
                
                # Process normal message
                response = self.process_message(user_input)
                
                # Display response
                print(f"{self.colors['assistant']}Assistant > {self.colors['reset']}{response}")
                
            except KeyboardInterrupt:
                self.print_colored("\n\n👋 Goodbye!", 'system')
                break
            except Exception as e:
                self.print_colored(f"\nError: {e}", 'error')
                continue
    
    def run_test_conversation(self):
        """Run a test conversation to demo the system"""
        self.print_colored("\n🎮 Running test conversation...", 'system')
        
        test_messages = [
            "Hello! How are you?",
            "Can you remember what I just said?",
            "This is a test of the memory system",
            "Make this perfect, fast, and cheap!",  # Should trigger validation issues
            "What is 2+2?",
        ]
        
        for message in test_messages:
            print(f"\n{self.colors['user']}Test > {self.colors['reset']}{message}")
            response = self.process_message(message)
            print(f"{self.colors['assistant']}Assistant > {self.colors['reset']}{response}")
            
            # Show validation
            if self.conversation_history:
                validation = self.conversation_history[-1].get('validation', {})
                confidence = validation.get('confidence_score', 0)
                if confidence < 0.7:
                    self.print_colored(f"  [Confidence: {confidence:.2f}]", 'system')
        
        self.print_colored("\n✅ Test complete!", 'system')

def main():
    """Main entry point"""
    import sys
    
    chat = MemoryChatInterface()
    
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        chat.run_test_conversation()
    else:
        chat.run()

if __name__ == "__main__":
    main()