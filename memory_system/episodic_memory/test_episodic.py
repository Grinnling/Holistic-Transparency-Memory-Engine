#!/usr/bin/env python3
"""
Test script for Episodic Memory Service
"""
import requests
import json
import time
from datetime import datetime, timedelta

# Configuration
EPISODIC_URL = "http://localhost:8005"

def test_episodic_health():
    """Test episodic service health endpoint"""
    print("=== Testing Episodic Service Health ===")
    try:
        response = requests.get(f"{EPISODIC_URL}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"Service ID: {health_data.get('service_id')}")
            print(f"Database Path: {health_data.get('database_path')}")
            return True
    except requests.exceptions.ConnectionError:
        print("❌ Episodic service not running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_archive_conversation():
    """Test archiving a conversation"""
    print("\n=== Testing Conversation Archive ===")
    
    # Create test conversation data
    test_conversation = {
        "conversation_id": f"test_episode_{int(time.time())}",
        "exchanges": [
            {
                "user_message": "Hello, can you help me understand Python decorators?",
                "assistant_response": "Of course! Python decorators are a way to modify or enhance functions...",
                "timestamp": datetime.now().isoformat()
            },
            {
                "user_message": "Can you show me a simple example?",
                "assistant_response": "Here's a simple decorator example:\n```python\ndef timer_decorator(func):\n    def wrapper(*args, **kwargs):\n        start = time.time()\n        result = func(*args, **kwargs)\n        end = time.time()\n        print(f'{func.__name__} took {end-start} seconds')\n        return result\n    return wrapper\n```",
                "timestamp": (datetime.now() + timedelta(minutes=1)).isoformat()
            },
            {
                "user_message": "That's helpful! How do I use it?",
                "assistant_response": "You use it with the @ symbol before a function definition:\n```python\n@timer_decorator\ndef slow_function():\n    time.sleep(2)\n    return 'Done!'\n```",
                "timestamp": (datetime.now() + timedelta(minutes=2)).isoformat()
            }
        ],
        "participants": ["human", "claude"]
    }
    
    archive_request = {
        "conversation_data": test_conversation,
        "trigger_reason": "manual_test"
    }
    
    try:
        response = requests.post(f"{EPISODIC_URL}/archive", json=archive_request)
        print(f"Archive Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            conversation_id = result.get('conversation_id')
            print(f"✅ Archived conversation: {conversation_id}")
            return conversation_id
        else:
            print(f"❌ Archive failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_get_conversation(conversation_id):
    """Test retrieving a specific conversation"""
    print(f"\n=== Testing Get Conversation: {conversation_id} ===")
    
    try:
        response = requests.get(f"{EPISODIC_URL}/conversation/{conversation_id}")
        print(f"Get Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            conversation = result.get('conversation')
            print(f"✅ Retrieved conversation:")
            print(f"   Start: {conversation.get('start_timestamp')}")
            print(f"   End: {conversation.get('end_timestamp')}")
            print(f"   Exchanges: {conversation.get('exchange_count')}")
            print(f"   Participants: {conversation.get('participants')}")
            print(f"   Topics: {conversation.get('topics')}")
            print(f"   Summary: {conversation.get('summary')[:100]}...")
            return True
        else:
            print(f"❌ Get failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_search_conversations():
    """Test searching conversations"""
    print("\n=== Testing Conversation Search ===")
    
    test_searches = [
        {"query": "Python decorators", "description": "Full-text search"},
        {"participants": ["human"], "description": "Search by participant"},
        {"topics": ["python"], "description": "Search by topic"},
        {"start_date": (datetime.now() - timedelta(hours=1)).isoformat(), "description": "Recent conversations"}
    ]
    
    for search_params in test_searches:
        description = search_params.pop("description")
        print(f"\n  Testing: {description}")
        
        try:
            response = requests.get(f"{EPISODIC_URL}/search", params=search_params)
            
            if response.status_code == 200:
                result = response.json()
                conversations = result.get('results', [])
                print(f"  ✅ Found {len(conversations)} conversations")
                
                if conversations:
                    first = conversations[0]
                    print(f"     First result: {first.get('conversation_id')}")
                    print(f"     Summary: {first.get('summary', '')[:50]}...")
            else:
                print(f"  ❌ Search failed: {response.text}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_export_conversation(conversation_id):
    """Test exporting conversation as text"""
    print(f"\n=== Testing Export Conversation: {conversation_id} ===")
    
    try:
        response = requests.get(f"{EPISODIC_URL}/conversation/{conversation_id}/export")
        print(f"Export Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            text_export = result.get('text_export', '')
            print(f"✅ Exported conversation (first 500 chars):")
            print("-" * 50)
            print(text_export[:500] + "..." if len(text_export) > 500 else text_export)
            print("-" * 50)
            return True
        else:
            print(f"❌ Export failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_recent_conversations():
    """Test getting recent conversations"""
    print("\n=== Testing Get Recent Conversations ===")
    
    try:
        response = requests.get(f"{EPISODIC_URL}/recent", params={"limit": 5})
        print(f"Recent Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            conversations = result.get('conversations', [])
            print(f"✅ Found {len(conversations)} recent conversations:")
            
            for conv in conversations:
                print(f"   - {conv.get('conversation_id')}: {conv.get('summary', '')[:50]}...")
            
            return True
        else:
            print(f"❌ Recent failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_service_stats():
    """Test service statistics endpoint"""
    print("\n=== Testing Service Statistics ===")
    
    try:
        response = requests.get(f"{EPISODIC_URL}/stats")
        print(f"Stats Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            stats = result.get('stats', {})
            
            print(f"✅ Service Statistics:")
            print(f"   Uptime: {stats.get('uptime_hours', 0):.2f} hours")
            
            service_stats = stats.get('service_stats', {})
            print(f"   Episodes Stored: {service_stats.get('episodes_stored', 0)}")
            print(f"   Episodes Retrieved: {service_stats.get('episodes_retrieved', 0)}")
            print(f"   Searches Performed: {service_stats.get('searches_performed', 0)}")
            
            db_stats = stats.get('database_stats', {})
            print(f"   Total Episodes in DB: {db_stats.get('total_episodes', 0)}")
            
            return True
        else:
            print(f"❌ Stats failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_multiple_conversations():
    """Test archiving multiple conversations with different triggers"""
    print("\n=== Testing Multiple Conversation Archives ===")
    
    test_conversations = [
        {
            "data": {
                "conversation_id": f"buffer_full_test_{int(time.time())}",
                "exchanges": [{"user_message": f"Message {i}", "assistant_response": f"Response {i}", "timestamp": datetime.now().isoformat()} for i in range(20)],
                "participants": ["human", "assistant"]
            },
            "trigger": "buffer_full"
        },
        {
            "data": {
                "conversation_id": f"time_gap_test_{int(time.time())}",
                "exchanges": [{"user_message": "Last message before gap", "assistant_response": "Final response", "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()}],
                "participants": ["human", "assistant"]
            },
            "trigger": "time_gap"
        },
        {
            "data": {
                "conversation_id": f"system_restart_test_{int(time.time())}",
                "exchanges": [{"user_message": "System going down", "assistant_response": "Saving state...", "timestamp": datetime.now().isoformat()}],
                "participants": ["human", "assistant", "system"]
            },
            "trigger": "system_restart"
        }
    ]
    
    archived_ids = []
    
    for test_conv in test_conversations:
        print(f"\n  Archiving with trigger: {test_conv['trigger']}")
        
        try:
            response = requests.post(
                f"{EPISODIC_URL}/archive",
                json={
                    "conversation_data": test_conv["data"],
                    "trigger_reason": test_conv["trigger"]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                conv_id = result.get('conversation_id')
                print(f"  ✅ Archived: {conv_id}")
                archived_ids.append(conv_id)
            else:
                print(f"  ❌ Failed: {response.text}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    return archived_ids

def main():
    """Run all tests"""
    print("🧠 Episodic Memory Service - Test Suite")
    print("=" * 50)
    
    # Test sequence
    tests = [
        ("Service Health Check", test_episodic_health),
    ]
    
    results = {}
    
    # Run health check first
    health_ok = test_episodic_health()
    if not health_ok:
        print("\n❌ Service not running. Please start it with:")
        print("python3 /home/grinnling/Development/docker_agent_environment/memory_system/episodic_memory/service.py")
        return
    
    # Archive a test conversation
    conversation_id = test_archive_conversation()
    if conversation_id:
        # Run tests that need a conversation ID
        test_get_conversation(conversation_id)
        test_export_conversation(conversation_id)
    
    # Run other tests
    test_search_conversations()
    test_recent_conversations()
    test_service_stats()
    test_multiple_conversations()
    
    print("\n" + "=" * 50)
    print("✅ Test suite completed!")

if __name__ == "__main__":
    main()