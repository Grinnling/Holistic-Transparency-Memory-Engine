#!/usr/bin/env python3
"""
Memory Curator - Terminal Interface
Interactive terminal application for memory validation and group chat
"""
import os
import sys
import json
import requests
import time
from datetime import datetime
from pathlib import Path
import argparse
import threading
from typing import Dict, List, Optional

class CuratorTerminal:
    def __init__(self, curator_url="http://localhost:8004"):
        self.curator_url = curator_url
        self.active_session = None
        self.running = True
        
        # Check if service is running
        if not self._check_service():
            print("❌ Memory Curator service not running")
            print("Start it with: python3 curator_service.py")
            sys.exit(1)
        
        print("🧠 Memory Curator - Terminal Interface")
        print("=" * 50)
        self._show_service_info()
    
    def _check_service(self):
        """Check if curator service is running"""
        try:
            response = requests.get(f"{self.curator_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _show_service_info(self):
        """Show service information"""
        try:
            response = requests.get(f"{self.curator_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Connected to Memory Curator")
                print(f"   Service ID: {data.get('service_id', 'unknown')[:8]}...")
                print(f"   Available Models: {list(data.get('available_models', {}).keys())}")
                
                # Get stats
                stats_response = requests.get(f"{self.curator_url}/stats")
                if stats_response.status_code == 200:
                    stats = stats_response.json().get('stats', {})
                    validation_stats = stats.get('validation_stats', {})
                    print(f"   Total Validations: {validation_stats.get('total_validations', 0)}")
                    print(f"   Group Chat Sessions: {validation_stats.get('group_chat_sessions', 0)}")
        except Exception as e:
            print(f"⚠️  Could not get service info: {e}")
    
    def run(self):
        """Main terminal loop"""
        print("\n📋 Commands:")
        print("  validate <text>     - Validate a memory/response")
        print("  chat                - Start group chat validation")
        print("  sessions            - List active sessions")
        print("  stats               - Show curator statistics")
        print("  help                - Show this help")
        print("  quit                - Exit")
        print()
        
        while self.running:
            try:
                command = input("curator> ").strip()
                if not command:
                    continue
                    
                self._handle_command(command)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                break
    
    def _handle_command(self, command: str):
        """Handle user commands"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in ['quit', 'exit', 'q']:
            self.running = False
        
        elif cmd == 'validate':
            if not args:
                print("❌ Usage: validate <text to validate>")
                return
            self._validate_text(args)
        
        elif cmd == 'chat':
            self._start_group_chat()
        
        elif cmd == 'sessions':
            self._list_sessions()
        
        elif cmd == 'stats':
            self._show_stats()
        
        elif cmd == 'help':
            self._show_help()
        
        else:
            print(f"❌ Unknown command: {cmd}")
            print("Type 'help' for available commands")
    
    def _validate_text(self, text: str):
        """Validate a piece of text"""
        print(f"🔍 Validating: {text[:50]}{'...' if len(text) > 50 else ''}")
        
        exchange_data = {
            "exchange_id": f"terminal_{int(time.time())}",
            "user_message": "User input for validation",
            "assistant_response": text,
            "timestamp": datetime.now().isoformat(),
            "context_used": ["terminal_input"]
        }
        
        try:
            response = requests.post(
                f"{self.curator_url}/validate",
                json={
                    "exchange_data": exchange_data,
                    "validation_type": "terminal_validation"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                validation = result.get('validation', {})
                validation_result = validation.get('result', {})
                
                print(f"✅ Validation Complete")
                print(f"   Valid: {'✅ Yes' if validation_result.get('is_valid') else '❌ No'}")
                print(f"   Confidence: {validation_result.get('confidence_score', 0):.3f}")
                print(f"   Contradictions: {validation_result.get('contradictions_detected', 0)}")
                print(f"   Uncertainty: {validation_result.get('uncertainty_level', 0):.3f}")
                
                if validation_result.get('contradiction_details'):
                    print("   Issues found:")
                    for issue in validation_result['contradiction_details']:
                        print(f"     - {issue}")
                
            else:
                print(f"❌ Validation failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _start_group_chat(self):
        """Start a group chat validation session"""
        print("💬 Starting Group Chat Validation")
        
        # Get text to validate
        text = input("Enter text to validate: ").strip()
        if not text:
            print("❌ No text provided")
            return
        
        # Get participants
        print("Enter participants (comma-separated):")
        print("  Suggestions: claude_primary, validation_expert, human_reviewer, domain_expert")
        participants_input = input("Participants: ").strip()
        
        if not participants_input:
            participants = ["claude_primary", "validation_expert", "human_reviewer"]
        else:
            participants = [p.strip() for p in participants_input.split(',')]
        
        exchange_data = {
            "exchange_id": f"chat_{int(time.time())}",
            "user_message": "Group chat validation request",
            "assistant_response": text,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                f"{self.curator_url}/group-chat/start",
                json={
                    "exchange_data": exchange_data,
                    "participants": participants
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                session = result.get('chat_session', {})
                session_id = session.get('session_id')
                
                print(f"✅ Chat Session Started: {session_id}")
                print(f"   Participants: {', '.join(participants)}")
                
                self.active_session = session_id
                self._run_chat_session(session_id)
                
            else:
                print(f"❌ Failed to start chat: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _run_chat_session(self, session_id: str):
        """Run interactive chat session"""
        print("\n💬 Group Chat Session Active")
        print("Commands: <speaker>: <message>, 'show' to see conversation, 'quit' to exit")
        print("Example: claude_primary: I think this response has issues...")
        print()
        
        while True:
            try:
                user_input = input("chat> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'quit':
                    break
                
                if user_input.lower() == 'show':
                    self._show_conversation(session_id)
                    continue
                
                # Parse speaker: message format
                if ':' not in user_input:
                    print("❌ Format: <speaker>: <message>")
                    continue
                
                speaker, message = user_input.split(':', 1)
                speaker = speaker.strip()
                message = message.strip()
                
                if not speaker or not message:
                    print("❌ Both speaker and message required")
                    continue
                
                # Send message
                response = requests.post(
                    f"{self.curator_url}/group-chat/{session_id}/message",
                    json={
                        "speaker": speaker,
                        "message": message,
                        "message_type": "discussion"
                    }
                )
                
                if response.status_code == 200:
                    print(f"✅ Message added from {speaker}")
                else:
                    print(f"❌ Failed to add message: {response.text}")
                    
            except KeyboardInterrupt:
                break
        
        self.active_session = None
        print("💬 Chat session ended")
    
    def _show_conversation(self, session_id: str):
        """Show conversation history"""
        try:
            response = requests.get(f"{self.curator_url}/group-chat/{session_id}")
            if response.status_code == 200:
                result = response.json()
                session = result.get('session', {})
                conversation = session.get('conversation_log', [])
                
                print("\n📜 Conversation History:")
                print("-" * 40)
                for msg in conversation:
                    speaker = msg.get('speaker', 'unknown')
                    message = msg.get('message', '')
                    timestamp = msg.get('timestamp', '')[:19]  # Remove microseconds
                    print(f"[{timestamp}] {speaker}:")
                    print(f"  {message}")
                    print()
                print("-" * 40)
            else:
                print(f"❌ Could not get conversation: {response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _list_sessions(self):
        """List active sessions (placeholder - would need API endpoint)"""
        try:
            response = requests.get(f"{self.curator_url}/stats")
            if response.status_code == 200:
                result = response.json()
                stats = result.get('stats', {})
                active = stats.get('active_validations', 0)
                print(f"📊 Active validations: {active}")
                
                if self.active_session:
                    print(f"🔄 Current session: {self.active_session}")
            else:
                print(f"❌ Could not get sessions: {response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _show_stats(self):
        """Show curator statistics"""
        try:
            response = requests.get(f"{self.curator_url}/stats")
            if response.status_code == 200:
                result = response.json()
                stats = result.get('stats', {})
                
                print("📊 Memory Curator Statistics")
                print("-" * 30)
                print(f"Uptime: {stats.get('uptime_hours', 0):.2f} hours")
                print(f"Configuration: {stats.get('configuration', {}).get('model_size', 'unknown')}")
                
                validation_stats = stats.get('validation_stats', {})
                print(f"\nValidation Stats:")
                for key, value in validation_stats.items():
                    print(f"  {key.replace('_', ' ').title()}: {value}")
                
                print(f"\nActive Sessions: {stats.get('active_validations', 0)}")
                
            else:
                print(f"❌ Could not get stats: {response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _show_help(self):
        """Show help information"""
        print("🧠 Memory Curator - Terminal Interface Help")
        print("=" * 50)
        print("Commands:")
        print("  validate <text>     - Validate a memory/response for accuracy")
        print("  chat                - Start interactive group chat validation")
        print("  sessions            - List active validation sessions")
        print("  stats               - Show curator service statistics")
        print("  help                - Show this help message")
        print("  quit/exit/q         - Exit the terminal interface")
        print()
        print("Group Chat Format:")
        print("  <speaker>: <message>")
        print("  show                - Display conversation history")
        print("  quit                - Exit chat session")
        print()
        print("Examples:")
        print("  validate The sky is always green and never blue")
        print("  claude_primary: This response seems overly absolute")
        print("  human_reviewer: I agree, needs more nuance")

def main():
    parser = argparse.ArgumentParser(description="Memory Curator Terminal Interface")
    parser.add_argument("--url", default="http://localhost:8004", 
                       help="Curator service URL (default: http://localhost:8004)")
    
    args = parser.parse_args()
    
    terminal = CuratorTerminal(args.url)
    terminal.run()

if __name__ == "__main__":
    main()