"""
Test script for Working Memory HTTP Service
Tests the REST API endpoints
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:5001"

def test_http_service():
    """Test the Working Memory HTTP service"""
    print("=== Testing Working Memory HTTP Service ===")
    print("(Make sure to run: python service.py in another terminal first)")
    
    try:
        # Test health check
        print("\n--- Testing health check ---")
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health check status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test getting empty working memory
        print("\n--- Testing GET empty working memory ---")
        response = requests.get(f"{BASE_URL}/working-memory")
        print(f"GET status: {response.status_code}")
        data = response.json()
        print(f"Empty buffer size: {data['summary']['current_size']}")
        
        # Test adding exchanges
        print("\n--- Testing POST exchanges ---")
        
        exchanges = [
            {
                "user_message": "What GPU do I have?",
                "assistant_response": "You have an RTX 4060 Ti with driver 550.144.03",
                "context_used": ["system_hardware_scan"]
            },
            {
                "user_message": "How much memory?", 
                "assistant_response": "64GB DDR4, 45GB available"
            },
            {
                "user_message": "Is Docker running?",
                "assistant_response": "Yes, 2 containers are active"
            }
        ]
        
        for i, exchange in enumerate(exchanges, 1):
            response = requests.post(f"{BASE_URL}/working-memory", json=exchange)
            print(f"Exchange {i} status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Added: {data['exchange']['exchange_id']}")
                print(f"  Buffer size: {data['buffer_summary']['current_size']}")
        
        # Test getting populated working memory
        print("\n--- Testing GET populated working memory ---")
        response = requests.get(f"{BASE_URL}/working-memory")
        data = response.json()
        print(f"GET status: {response.status_code}")
        print(f"Buffer size: {data['summary']['current_size']}")
        print("Recent exchanges:")
        for i, exchange in enumerate(data['context'], 1):
            print(f"  {i}. User: {exchange['user_message'][:30]}...")
            print(f"     AI: {exchange['assistant_response'][:30]}...")
        
        # Test limit parameter
        print("\n--- Testing GET with limit ---")
        response = requests.get(f"{BASE_URL}/working-memory?limit=2")
        data = response.json()
        print(f"Limited GET status: {response.status_code}")
        print(f"Returned {len(data['context'])} exchanges (requested 2)")
        
        # Test buffer size update
        print("\n--- Testing PUT buffer size ---")
        response = requests.put(f"{BASE_URL}/working-memory/size", json={"size": 2})
        print(f"Size update status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Size changed from {data['old_size']} to {data['new_size']}")
            print(f"Buffer now has {data['buffer_summary']['current_size']} exchanges")
        
        # Test clear
        print("\n--- Testing DELETE (clear) ---")
        response = requests.delete(f"{BASE_URL}/working-memory")
        print(f"Clear status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Cleared {data['cleared_count']} exchanges")
        
        print("\n=== HTTP Service test complete ===")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to service.")
        print("Make sure to run 'python service.py' in another terminal first!")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_http_service()