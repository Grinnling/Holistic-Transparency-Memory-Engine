#!/usr/bin/env python3
"""
Enhanced Chat Interface with Real LLM and Skinflap Detection
Combines memory system + real LLM + skinflap detection
"""

import requests
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List
import sys
import os
import readline
import textwrap

# Import our modules
from llm_connector import SmartLLMSelector, LLMConnector
from skinflap_stupidity_detection import CollaborativeQueryReformer

class EnhancedMemoryChat:
    def __init__(self):
        self.services = {
            'working_memory': 'http://localhost:5001',
            'curator': 'http://localhost:8004',
            'mcp_logger': 'http://localhost:8001'
        }
        
        # Initialize components
        self.conversation_id = str(uuid.uuid4())
        self.conversation_history = []
        
        # Configure readline for better input
        self.setup_readline()
        
        # Initialize LLM
        print("🤖 Initializing LLM connection...")
        self.llm = SmartLLMSelector.find_available_llm()
        
        # Initialize Skinflap detector
        print("🔍 Initializing Skinflap detector...")
        self.skinflap = CollaborativeQueryReformer()
        
        # Colors for terminal
        self.colors = {
            'user': '\033[94m',      # Blue
            'assistant': '\033[92m',  # Green
            'system': '\033[93m',     # Yellow
            'warning': '\033[95m',    # Magenta
            'error': '\033[91m',      # Red
            'reset': '\033[0m'        # Reset
        }
        
        self.services_healthy = self.check_services()
    
    def setup_readline(self):
        """Configure readline for better input experience"""
        try:
            # Enable command history
            readline.set_startup_hook(None)
            
            # Set up history
            history_file = os.path.expanduser("~/.chat_history")
            try:
                readline.read_history_file(history_file)
            except FileNotFoundError:
                pass
            
            # Save history on exit
            import atexit
            atexit.register(readline.write_history_file, history_file)
            
            # Configure readline behavior
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("set editing-mode emacs")
            readline.parse_and_bind("set show-all-if-ambiguous on")
            
            # Set history length
            readline.set_history_length(1000)
            
        except ImportError:
            # readline not available on this system
            pass
    
    def print_colored(self, text, color_key='reset'):
        """Print colored text to terminal with proper wrapping"""
        # Wrap long lines to fit terminal
        terminal_width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
        wrapped_lines = textwrap.fill(text, width=terminal_width - 4)  # Leave margin
        print(f"{self.colors[color_key]}{wrapped_lines}{self.colors['reset']}")
    
    def print_response(self, text, color_key='assistant'):
        """Print assistant responses with nice formatting"""
        terminal_width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
        
        # Wrap text nicely
        wrapped = textwrap.fill(text, width=terminal_width - 15, 
                               initial_indent="", subsequent_indent="  ")
        
        print(f"\n{self.colors[color_key]}Assistant > {self.colors['reset']}{wrapped}")
    
    def get_multiline_input(self, prompt="You > "):
        """Get input with support for multi-line editing"""
        try:
            # Use readline for better editing
            user_input = input(f"{self.colors['user']}{prompt}{self.colors['reset']}")
            return user_input
        except EOFError:
            return "/quit"
        except KeyboardInterrupt:
            return "/quit"
    
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
        
        if self.llm:
            print(f"  ✅ LLM: Connected ({self.llm.provider.value})")
        else:
            print(f"  ⚠️  LLM: Using fallback (no LLM connected)")
        
        print(f"  ✅ Skinflap: Ready")
        
        return all_healthy
    
    def check_with_skinflap(self, user_message: str) -> Dict:
        """Check user message with skinflap detector"""
        # Run skinflap detection
        result = self.skinflap.process_query(
            user_message, 
            [msg.get('user', '') for msg in self.conversation_history[-5:]]
        )
        
        if not result.ready_for_processing:
            return {
                'needs_clarification': True,
                'clarification_message': result.clarification_needed,
                'issues': result.detected_issues,
                'severity': 'high' if len(result.detected_issues) > 2 else 'medium'
            }
        
        return {
            'needs_clarification': False,
            'reformed_query': result.reformed_query,
            'issues': [],
            'severity': 'none'
        }
    
    def store_exchange(self, user_message: str, assistant_response: str, metadata: Dict = None):
        """Store conversation exchange in working memory"""
        try:
            exchange_data = {
                "user_message": user_message,
                "assistant_response": assistant_response,
                "context_used": ["enhanced_chat", "llm", "skinflap"]
            }
            
            if metadata:
                exchange_data['metadata'] = metadata
            
            response = requests.post(
                f"{self.services['working_memory']}/working-memory",
                json=exchange_data,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('exchange', {}).get('exchange_id', 'unknown')
                
        except Exception as e:
            self.print_colored(f"Failed to store in memory: {e}", 'error')
        
        return None
    
    def validate_with_curator(self, user_message: str, assistant_response: str, skinflap_result: Dict = None):
        """Validate exchange with curator (now with skinflap awareness)"""
        try:
            validation_data = {
                "exchange_data": {
                    "user_message": user_message,
                    "assistant_response": assistant_response,
                    "exchange_id": str(uuid.uuid4())
                },
                "validation_type": "enhanced"  # New type for skinflap-aware validation
            }
            
            # Add skinflap results if available
            if skinflap_result:
                validation_data['skinflap_analysis'] = skinflap_result
            
            response = requests.post(
                f"{self.services['curator']}/validate",
                json=validation_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('validation', {}).get('result', {})
                
        except Exception as e:
            self.print_colored(f"Validation failed: {e}", 'error')
        
        return None
    
    def generate_response(self, user_message: str) -> str:
        """Generate response using real LLM or fallback"""
        if self.llm:
            try:
                response = self.llm.generate_response(
                    user_message,
                    conversation_history=self.conversation_history,
                    system_prompt="""You are a helpful AI assistant with memory capabilities. 
                    You can remember previous conversations and help users with complex queries.
                    Be concise but thorough in your responses."""
                )
                return response
            except Exception as e:
                self.print_colored(f"LLM error, using fallback: {e}", 'warning')
        
        # Fallback response
        return f"I understand you're asking about: '{user_message}'. Let me help you with that."
    
    def process_message(self, user_message: str) -> Dict:
        """Process message through full pipeline"""
        
        # Step 1: Skinflap detection
        self.print_colored("  [Checking query quality...]", 'system')
        skinflap_result = self.check_with_skinflap(user_message)
        
        # Step 2: Handle problematic queries
        if skinflap_result['needs_clarification']:
            self.print_colored(f"\n⚠️  Query Issues Detected:", 'warning')
            self.print_colored(skinflap_result['clarification_message'], 'warning')
            
            # Store the problematic query anyway (for learning)
            self.store_exchange(
                user_message, 
                "Query needs clarification - see message above",
                {'skinflap_blocked': True, 'issues': skinflap_result['issues']}
            )
            
            return {
                'response': skinflap_result['clarification_message'],
                'type': 'clarification_needed',
                'skinflap_blocked': True
            }
        
        # Step 3: Generate LLM response
        self.print_colored("  [Generating response...]", 'system')
        
        # Use reformed query if available
        query_to_process = skinflap_result.get('reformed_query', user_message)
        if query_to_process != user_message:
            self.print_colored(f"  [Query reformed: {query_to_process[:50]}...]", 'system')
        
        assistant_response = self.generate_response(query_to_process)
        
        # Step 4: Store in memory
        self.print_colored("  [Storing in memory...]", 'system')
        exchange_id = self.store_exchange(user_message, assistant_response)
        
        # Step 5: Validate with curator
        self.print_colored("  [Validating response...]", 'system')
        validation = self.validate_with_curator(user_message, assistant_response, skinflap_result)
        
        # Step 6: Add to conversation history
        self.conversation_history.append({
            'user': user_message,
            'assistant': assistant_response,
            'exchange_id': exchange_id,
            'validation': validation,
            'skinflap': skinflap_result,
            'timestamp': datetime.now().isoformat()
        })
        
        # Step 7: Check validation results
        if validation:
            confidence = validation.get('confidence_score', 0)
            contradictions = validation.get('contradictions_detected', 0)
            
            if confidence < 0.5:
                self.print_colored(f"  ⚠️  Low confidence: {confidence:.2f}", 'warning')
            if contradictions > 0:
                self.print_colored(f"  ⚠️  Contradictions detected: {contradictions}", 'warning')
        
        return {
            'response': assistant_response,
            'type': 'normal',
            'validation': validation,
            'skinflap_result': skinflap_result
        }
    
    def show_status(self):
        """Show current system status"""
        print("\n" + "="*60)
        self.print_colored("📊 System Status", 'system')
        print("="*60)
        
        print(f"Conversation ID: {self.conversation_id[:8]}...")
        print(f"Messages in history: {len(self.conversation_history)}")
        print(f"Services healthy: {self.services_healthy}")
        print(f"LLM connected: {self.llm is not None}")
        print(f"Skinflap active: True")
        
        if self.conversation_history:
            last = self.conversation_history[-1]
            print(f"\nLast exchange:")
            print(f"  User: {last['user'][:50]}...")
            print(f"  Assistant: {last['assistant'][:50]}...")
            if last.get('validation'):
                print(f"  Confidence: {last['validation'].get('confidence_score', 'N/A')}")
    
    def run(self):
        """Main chat loop"""
        print("\n" + "="*60)
        self.print_colored("🧠 Enhanced Memory Chat with Skinflap + Real LLM", 'system')
        print("="*60)
        
        if not self.services_healthy:
            self.print_colored("\n⚠️  Some services are offline but chat will continue", 'warning')
        
        if not self.llm:
            self.print_colored("⚠️  No LLM connected - using fallback responses", 'warning')
        
        print("\nCommands: /status, /memory, /quit")
        print("-"*60)
        
        while True:
            try:
                # Get user input with better editing
                user_input = self.get_multiline_input("\nYou > ")
                
                # Handle commands
                if user_input.lower() in ['/quit', 'exit']:
                    self.print_colored("\n👋 Goodbye!", 'system')
                    break
                
                if user_input == '/status':
                    self.show_status()
                    continue
                
                if user_input == '/memory':
                    # Show last 3 exchanges
                    for exchange in self.conversation_history[-3:]:
                        print(f"\n  User: {exchange['user'][:100]}")
                        print(f"  Assistant: {exchange['assistant'][:100]}")
                    continue
                
                # Process message
                result = self.process_message(user_input)
                
                # Display response with better formatting
                if result['type'] == 'clarification_needed':
                    self.print_response(result['response'], 'warning')
                else:
                    self.print_response(result['response'], 'assistant')
                
            except KeyboardInterrupt:
                self.print_colored("\n\n👋 Goodbye!", 'system')
                break
            except Exception as e:
                self.print_colored(f"\nError: {e}", 'error')

def test_problematic_queries():
    """Test the system with problematic queries"""
    chat = EnhancedMemoryChat()
    
    test_queries = [
        "Hello, how are you?",  # Normal
        "Fix it",  # Vague
        "Make this perfect, fast, and cheap immediately",  # Impossible
        "Build me a todo app and also add user auth and make it scalable and add payment processing",  # Scope creep
        "What is 2+2?",  # Normal
    ]
    
    print("\n" + "="*60)
    print("🧪 Testing Problematic Query Detection")
    print("="*60)
    
    for query in test_queries:
        print(f"\n📝 Testing: {query}")
        result = chat.process_message(query)
        
        if result.get('skinflap_blocked'):
            print("  🚨 BLOCKED by Skinflap")
        else:
            print(f"  ✅ Processed normally")
            if result.get('validation'):
                confidence = result['validation'].get('confidence_score', 0)
                print(f"  📊 Confidence: {confidence:.2f}")

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        test_problematic_queries()
    else:
        chat = EnhancedMemoryChat()
        chat.run()

if __name__ == "__main__":
    main()