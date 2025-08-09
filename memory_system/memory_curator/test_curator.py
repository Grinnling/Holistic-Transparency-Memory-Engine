#!/usr/bin/env python3
"""
Test script for Memory Curator Agent prototype
"""
import requests
import json
import time
from datetime import datetime

# Configuration
CURATOR_URL = "http://localhost:8004"
WORKING_MEMORY_URL = "http://localhost:8002"

def test_curator_health():
    """Test curator health endpoint"""
    print("=== Testing Curator Health ===")
    try:
        response = requests.get(f"{CURATOR_URL}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"Service ID: {health_data.get('service_id')}")
            print(f"Available Models: {health_data.get('available_models')}")
            return True
    except requests.exceptions.ConnectionError:
        print("❌ Curator service not running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_memory_validation():
    """Test basic memory validation"""
    print("\n=== Testing Memory Validation ===")
    
    # Sample exchange to validate
    test_exchange = {
        "exchange_id": "test_001",
        "user_message": "What GPU do I have?",
        "assistant_response": "You have an RTX 4060 Ti with driver 550.144.03",
        "timestamp": datetime.now().isoformat(),
        "context_used": ["system_hardware_scan"]
    }
    
    validation_request = {
        "exchange_data": test_exchange,
        "validation_type": "basic"
    }
    
    try:
        response = requests.post(f"{CURATOR_URL}/validate", json=validation_request)
        print(f"Validation Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            validation = result.get('validation', {})
            validation_result = validation.get('result', {})
            
            print(f"✅ Validation ID: {validation.get('validation_id')}")
            print(f"   Is Valid: {validation_result.get('is_valid')}")
            print(f"   Confidence: {validation_result.get('confidence_score', 0):.3f}")
            print(f"   Contradictions: {validation_result.get('contradictions_detected', 0)}")
            print(f"   Uncertainty Level: {validation_result.get('uncertainty_level', 0):.3f}")
            print(f"   Model Used: {validation_result.get('model_used')}")
            
            return validation.get('validation_id')
        else:
            print(f"❌ Validation failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_group_chat_validation():
    """Test group chat validation feature"""
    print("\n=== Testing Group Chat Validation ===")
    
    # Sample exchange with potential issues
    test_exchange = {
        "exchange_id": "test_002",
        "user_message": "Is Python always faster than JavaScript?",
        "assistant_response": "Python is definitely always faster than JavaScript in all scenarios.",
        "timestamp": datetime.now().isoformat(),
        "context_used": []
    }
    
    chat_request = {
        "exchange_data": test_exchange,
        "participants": ["primary_ai", "validation_ai", "human_reviewer"]
    }
    
    try:
        # Start group chat session
        response = requests.post(f"{CURATOR_URL}/group-chat/start", json=chat_request)
        print(f"Group Chat Start Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            session = result.get('chat_session', {})
            session_id = session.get('session_id')
            
            print(f"✅ Chat Session ID: {session_id}")
            print(f"   Participants: {session.get('participants')}")
            print(f"   Started At: {session.get('started_at')}")
            
            # Add some test messages to the conversation
            test_messages = [
                {
                    "speaker": "primary_ai",
                    "message": "I'm concerned about my response - saying 'always faster' seems too absolute.",
                    "message_type": "concern"
                },
                {
                    "speaker": "validation_ai", 
                    "message": "I agree. Performance depends on the specific use case, implementation, and runtime environment.",
                    "message_type": "analysis"
                },
                {
                    "speaker": "human_reviewer",
                    "message": "This is a good catch. The original response needs to be more nuanced.",
                    "message_type": "feedback"
                }
            ]
            
            # Add messages to conversation
            for msg in test_messages:
                msg_response = requests.post(
                    f"{CURATOR_URL}/group-chat/{session_id}/message",
                    json=msg
                )
                if msg_response.status_code == 200:
                    print(f"   ✅ Added message from {msg['speaker']}")
                else:
                    print(f"   ❌ Failed to add message from {msg['speaker']}")
            
            # Get updated session
            session_response = requests.get(f"{CURATOR_URL}/group-chat/{session_id}")
            if session_response.status_code == 200:
                updated_session = session_response.json().get('session', {})
                conversation_log = updated_session.get('conversation_log', [])
                print(f"   Total messages in conversation: {len(conversation_log)}")
                
                # Show conversation excerpt
                print("   Recent conversation:")
                for msg in conversation_log[-3:]:
                    speaker = msg.get('speaker', 'unknown')
                    message = msg.get('message', '')[:50] + "..." if len(msg.get('message', '')) > 50 else msg.get('message', '')
                    print(f"     {speaker}: {message}")
            
            return session_id
        else:
            print(f"❌ Group chat failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_curator_stats():
    """Test curator statistics endpoint"""
    print("\n=== Testing Curator Statistics ===")
    
    try:
        response = requests.get(f"{CURATOR_URL}/stats")
        print(f"Stats Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            stats = result.get('stats', {})
            
            print(f"✅ Service Uptime: {stats.get('uptime_hours', 0):.2f} hours")
            print(f"   Configuration: {stats.get('configuration', {}).get('model_size')}")
            print(f"   Available Models: {list(stats.get('available_models', {}).keys())}")
            
            validation_stats = stats.get('validation_stats', {})
            print(f"   Total Validations: {validation_stats.get('total_validations', 0)}")
            print(f"   Successful Validations: {validation_stats.get('successful_validations', 0)}")
            print(f"   Contradictions Found: {validation_stats.get('contradictions_found', 0)}")
            print(f"   Group Chat Sessions: {validation_stats.get('group_chat_sessions', 0)}")
            print(f"   Active Validations: {stats.get('active_validations', 0)}")
            
            return True
        else:
            print(f"❌ Stats failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_integration_with_working_memory():
    """Test integration with working memory service"""
    print("\n=== Testing Working Memory Integration ===")
    
    try:
        # Check if working memory service is available
        response = requests.get(f"{WORKING_MEMORY_URL}/health")
        if response.status_code != 200:
            print("❌ Working memory service not available")
            return False
        
        print("✅ Working memory service is available")
        
        # Test the placeholder endpoint we created
        validation_request = {
            "validation_type": "integration_test",
            "exchange_id": "test_integration_001"
        }
        
        response = requests.post(f"{WORKING_MEMORY_URL}/memory/validate", json=validation_request)
        print(f"Working Memory Validation Endpoint Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {result.get('message')}")
            print("✅ Integration endpoint is working (placeholder)")
            return True
        else:
            print(f"❌ Integration endpoint failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧠 Memory Curator Agent - Test Suite")
    print("=" * 50)
    
    # Test sequence
    tests = [
        ("Curator Health Check", test_curator_health),
        ("Memory Validation", test_memory_validation),
        ("Group Chat Validation", test_group_chat_validation),
        ("Curator Statistics", test_curator_stats),
        ("Working Memory Integration", test_integration_with_working_memory)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔬 Running: {test_name}")
        try:
            result = test_func()
            results[test_name] = "✅ PASS" if result else "❌ FAIL"
        except Exception as e:
            results[test_name] = f"❌ ERROR: {e}"
        
        time.sleep(1)  # Small delay between tests
    
    # Test summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        print(f"{result} - {test_name}")
        if "✅" in result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Memory Curator is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    main()