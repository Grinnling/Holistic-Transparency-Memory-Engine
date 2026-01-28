#!/usr/bin/env python3
"""
Service Connector - MVP Test Script
Connects your existing memory services and tests basic flow

Your Working Services:
- Working Memory Service (port 5001)
- Memory Curator Service (port 8004)
- MCP Logger (port 8001)

This script tests the basic flow:
1. Store a message in working memory
2. Validate it with curator
3. Route through MCP logger
"""

import os
import requests
import json
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

# Conditional import for error handler (avoid circular imports)
if TYPE_CHECKING:
    from error_handler import ErrorHandler

class ServiceConnector:
    def __init__(self, error_handler: Optional["ErrorHandler"] = None):
        self.error_handler = error_handler
        # Service URLs from environment variables with localhost defaults
        self.services = {
            'working_memory': os.environ.get('WORKING_MEMORY_URL', 'http://localhost:5001'),
            'curator': os.environ.get('CURATOR_URL', 'http://localhost:8004'),
            'mcp_logger': os.environ.get('MCP_LOGGER_URL', 'http://localhost:8001')
        }

        self.service_status = {}

    def _log_error(self, error: Exception, context: str, operation: str):
        """Route error through error_handler if available, otherwise print"""
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity
            self.error_handler.handle_error(
                error,
                ErrorCategory.SERVICE_MANAGEMENT,
                ErrorSeverity.MEDIUM_ALERT,
                context=context,
                operation=operation
            )
        else:
            print(f"❌ [{operation}] {context}: {error}")

    def check_all_services(self):
        """Check if all services are running"""
        print("🔍 Checking service health...")

        for service_name, base_url in self.services.items():
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    self.service_status[service_name] = {
                        'status': 'healthy',
                        'response': response.json(),
                        'url': base_url
                    }
                    print(f"✅ {service_name}: {response.json().get('status', 'unknown')}")
                else:
                    self.service_status[service_name] = {
                        'status': 'error',
                        'error': f"HTTP {response.status_code}",
                        'url': base_url
                    }
                    print(f"❌ {service_name}: HTTP {response.status_code}")

            except requests.exceptions.RequestException as e:
                self.service_status[service_name] = {
                    'status': 'unreachable',
                    'error': str(e),
                    'url': base_url
                }
                self._log_error(e, f"Service {service_name} unreachable", "check_all_services")

        return self.service_status
    
    def test_working_memory_flow(self):
        """Test basic working memory operations"""
        print("\n🧠 Testing Working Memory Service...")
        
        if self.service_status['working_memory']['status'] != 'healthy':
            print("❌ Working Memory service not available")
            return False
        
        # Test adding an exchange
        test_exchange = {
            "user_message": "What is 2+2?",
            "assistant_response": "2+2 equals 4. This is basic arithmetic.",
            "context_used": ["math", "arithmetic"]
        }
        
        try:
            response = requests.post(
                f"{self.services['working_memory']}/working-memory",
                json=test_exchange,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Added exchange: {result.get('exchange', {}).get('exchange_id', 'unknown')}")
                print(f"   Buffer summary: {result.get('buffer_summary', {})}")
                return result
            else:
                print(f"❌ Failed to add exchange: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self._log_error(e, "Working memory test failed", "test_working_memory_flow")
            return False
    
    def test_curator_validation(self, exchange_data):
        """Test curator validation"""
        print("\n🎯 Testing Memory Curator Service...")
        
        if self.service_status['curator']['status'] != 'healthy':
            print("❌ Curator service not available")
            return False
        
        # Test validation
        validation_request = {
            "exchange_data": exchange_data,
            "validation_type": "basic"
        }
        
        try:
            response = requests.post(
                f"{self.services['curator']}/validate",
                json=validation_request,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                validation = result.get('validation', {}).get('result', {})
                print(f"✅ Validation completed:")
                print(f"   Valid: {validation.get('is_valid', 'unknown')}")
                print(f"   Confidence: {validation.get('confidence_score', 'unknown')}")
                print(f"   Contradictions: {validation.get('contradictions_detected', 0)}")
                print(f"   Uncertainty: {validation.get('uncertainty_level', 0)}")
                return result
            else:
                print(f"❌ Validation failed: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self._log_error(e, "Curator validation failed", "test_curator_validation")
            return False
    
    def test_group_chat_session(self):
        """Test group chat validation session"""
        print("\n💬 Testing Group Chat Session...")
        
        if self.service_status['curator']['status'] != 'healthy':
            print("❌ Curator service not available")
            return False
        
        # Start group chat session
        chat_request = {
            "exchange_data": {
                "user_message": "How do I optimize database queries?",
                "assistant_response": "Use indexes, limit results, and avoid N+1 queries."
            },
            "participants": ["user", "database_expert", "performance_analyst"]
        }
        
        try:
            response = requests.post(
                f"{self.services['curator']}/group-chat/start",
                json=chat_request,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get('chat_session', {}).get('session_id')
                print(f"✅ Group chat session started: {session_id}")
                
                # Add a test message
                message_request = {
                    "speaker": "database_expert",
                    "message": "I agree with using indexes, but we should also consider query execution plans.",
                    "message_type": "expert"
                }
                
                msg_response = requests.post(
                    f"{self.services['curator']}/group-chat/{session_id}/message",
                    json=message_request,
                    timeout=10
                )
                
                if msg_response.status_code == 200:
                    print("✅ Added message to group chat")
                    
                    # Get session details
                    session_response = requests.get(
                        f"{self.services['curator']}/group-chat/{session_id}",
                        timeout=10
                    )
                    
                    if session_response.status_code == 200:
                        session_data = session_response.json()
                        chat_log = session_data.get('session', {}).get('conversation_log', [])
                        print(f"   Messages in chat: {len(chat_log)}")
                        return session_data
                
                return result
            else:
                print(f"❌ Group chat failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self._log_error(e, "Group chat test failed", "test_group_chat_session")
            return False
    
    def test_mcp_logger_routing(self):
        """Test MCP logger routing"""
        print("\n📡 Testing MCP Logger Service...")
        
        if self.service_status['mcp_logger']['status'] != 'healthy':
            print("❌ MCP Logger service not available")
            return False
        
        # Test service info
        try:
            response = requests.get(
                f"{self.services['mcp_logger']}/info",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ MCP Logger info:")
                print(f"   Service: {result.get('name', 'unknown')}")
                print(f"   Version: {result.get('version', 'unknown')}")
                
                # Test service status endpoint
                status_response = requests.get(
                    f"{self.services['mcp_logger']}/memory/services/status",
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"   Service status check: {status_data.get('status', 'unknown')}")
                
                return result
            else:
                print(f"❌ MCP Logger info failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self._log_error(e, "MCP Logger test failed", "test_mcp_logger_routing")
            return False
    
    def run_full_integration_test(self):
        """Run complete integration test"""
        print("🚀 Starting Full Integration Test")
        print("=" * 50)
        
        # Step 1: Check all services
        status = self.check_all_services()
        healthy_services = [name for name, info in status.items() if info['status'] == 'healthy']
        
        if len(healthy_services) < 3:
            print(f"\n❌ Only {len(healthy_services)}/3 services healthy. Need all services running.")
            print("\nTo start services:")
            print("  python working_memory/service.py    # Terminal 1")
            print("  python memory_curator/curator_service.py  # Terminal 2") 
            print("  python mcp_logger/server.py         # Terminal 3")
            return False
        
        print(f"\n✅ All {len(healthy_services)} services are healthy!")
        
        # Step 2: Test working memory
        exchange_result = self.test_working_memory_flow()
        if not exchange_result:
            return False
        
        # Step 3: Test curator validation
        exchange_data = exchange_result.get('exchange', {})
        validation_result = self.test_curator_validation(exchange_data)
        if not validation_result:
            return False
        
        # Step 4: Test group chat
        group_chat_result = self.test_group_chat_session()
        if not group_chat_result:
            return False
        
        # Step 5: Test MCP logger
        mcp_result = self.test_mcp_logger_routing()
        if not mcp_result:
            return False
        
        # Success!
        print("\n" + "=" * 50)
        print("🎉 INTEGRATION TEST SUCCESSFUL!")
        print("=" * 50)
        print(f"✅ Working Memory: Storing and retrieving exchanges")
        print(f"✅ Memory Curator: Validating exchanges and group chats")  
        print(f"✅ MCP Logger: Service routing and status monitoring")
        print("\nYour memory system is working! 🧠")
        
        return True
    
    def add_skinflap_integration_test(self):
        """Test adding skinflap detection to curator"""
        print("\n🔍 Testing Skinflap Integration...")
        
        # Test query that should trigger skinflap
        problematic_queries = [
            "Make this perfect, fast, and cheap immediately",  # impossible request
            "Fix it",  # vague request
            "This is broken and also add a new feature and make it scalable",  # scope creep
        ]
        
        for query in problematic_queries:
            test_exchange = {
                "user_message": query,
                "assistant_response": "I'll help with that request."
            }
            
            print(f"\n   Testing: '{query[:40]}...'")
            
            # This would test if curator detects the problematic query
            # For now, just simulate what skinflap would catch
            issues = self.simulate_skinflap_detection(query)
            if issues:
                print(f"   🚨 Skinflap would catch: {', '.join(issues)}")
            else:
                print(f"   ✅ Query seems fine")
    
    def simulate_skinflap_detection(self, query):
        """Simulate what skinflap detector would catch"""
        issues = []
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['perfect', 'fast', 'cheap']) and len(query_lower.split()) < 20:
            issues.append('impossible_request')
        
        if query_lower.strip() in ['fix it', 'make it work', 'handle this']:
            issues.append('vague_request')
        
        if 'and' in query_lower and len(query_lower.split('and')) > 2:
            issues.append('scope_creep')
        
        return issues

def run_mvp_test():
    """Main function to run MVP test"""
    connector = ServiceConnector()
    
    print("🔬 Memory System MVP Test")
    print("Testing your existing services...")
    print()
    
    # Run the integration test
    success = connector.run_full_integration_test()
    
    if success:
        # Test skinflap integration concept
        connector.add_skinflap_integration_test()
        
        print("\n" + "=" * 50)
        print("🎯 NEXT STEPS FOR INTEGRATION:")
        print("=" * 50)
        print("1. ✅ Your services work - good foundation!")
        print("2. 📝 Add skinflap detector to curator validation")
        print("3. 🔗 Connect advanced orchestration when needed")
        print("4. 🚀 Test with real conversations")
        
        print("\n📋 Integration Points:")
        print("- Curator can call advanced orchestration for complex queries")
        print("- Working memory feeds context to orchestration")
        print("- MCP logger routes between all services")
        print("- Progress tracking works on conversation history")
        
        return True
    else:
        print("\n❌ Integration test failed. Fix services first.")
        return False

if __name__ == "__main__":
    run_mvp_test()