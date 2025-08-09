#!/usr/bin/env python3
"""
Test script for MCP Memory Logger server
Tests basic functionality of the skeleton server
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8001"

def test_health_check():
    """Test health check endpoint"""
    print("Testing health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data['status']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Connection failed - is the server running?")
        return False

def test_service_info():
    """Test service info endpoint"""
    print("Testing service info...")
    
    try:
        response = requests.get(f"{BASE_URL}/info")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service info: {data['name']} v{data['version']}")
            return True
        else:
            print(f"❌ Service info failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Connection failed")
        return False

def test_memory_endpoints():
    """Test memory endpoints (skeleton functionality)"""
    print("Testing memory endpoints...")
    
    # Test store endpoint
    store_data = {
        "type": "working",
        "content": "Test conversation exchange",
        "timestamp": time.time()
    }
    
    try:
        response = requests.post(f"{BASE_URL}/memory/store", json=store_data)
        if response.status_code == 200:
            print("✅ Memory store endpoint responding")
        else:
            print(f"❌ Memory store failed: {response.status_code}")
            
        # Test recall endpoint
        response = requests.get(f"{BASE_URL}/memory/recall?type=working&limit=5")
        if response.status_code == 200:
            print("✅ Memory recall endpoint responding")
        else:
            print(f"❌ Memory recall failed: {response.status_code}")
            
        # Test search endpoint
        search_data = {"query": "test conversation", "type": "all"}
        response = requests.post(f"{BASE_URL}/memory/search", json=search_data)
        if response.status_code == 200:
            print("✅ Memory search endpoint responding")
            return True
        else:
            print(f"❌ Memory search failed: {response.status_code}")
            return False
            
    except requests.ConnectionError:
        print("❌ Connection failed")
        return False

def run_tests():
    """Run all tests"""
    print("🧪 Testing MCP Memory Logger Server")
    print("=" * 40)
    
    tests = [
        test_health_check,
        test_service_info,
        test_memory_endpoints
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Server skeleton is working.")
    else:
        print("⚠️  Some tests failed. Check server status.")

if __name__ == "__main__":
    run_tests()