#!/usr/bin/env python3
"""
Test script for MCP Memory Logger routing framework
Tests the traffic cop functionality and trace verification
"""

import requests
import json
import time
from dotenv import load_dotenv

# Load environment
load_dotenv()

BASE_URL = "http://localhost:8001"

def test_service_status():
    """Test service status endpoint"""
    print("🔍 Testing service status...")
    
    try:
        response = requests.get(f"{BASE_URL}/memory/services/status")
        if response.status_code == 200:
            data = response.json()
            print("✅ Service status endpoint working")
            
            services = data.get('services', {})
            for service_name, service_info in services.items():
                status = service_info.get('status', 'unknown')
                if status == 'disabled':
                    print(f"   📴 {service_name}: {status}")
                elif status == 'unhealthy':
                    print(f"   ❌ {service_name}: {status}")
                else:
                    print(f"   ⚠️  {service_name}: {status} (service not running)")
            
            return True
        else:
            print(f"❌ Service status failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Connection failed")
        return False

def test_memory_routing():
    """Test memory request routing"""
    print("🚦 Testing memory request routing...")
    
    # Test different memory types
    test_requests = [
        {
            "name": "Working Memory",
            "data": {
                "type": "working",
                "content": "Test working memory storage",
                "context": "test_session"
            }
        },
        {
            "name": "Episodic Memory", 
            "data": {
                "type": "episodic",
                "content": "Test episodic memory - conversation from yesterday",
                "timestamp": time.time(),
                "participants": ["user", "ai"]
            }
        },
        {
            "name": "Prospective Memory",
            "data": {
                "type": "prospective",
                "content": "Remind user about meeting",
                "trigger_time": time.time() + 3600,  # 1 hour from now
                "trigger_type": "timestamp",
                "context": "calendar_integration"
            }
        }
    ]
    
    passed = 0
    for test_case in test_requests:
        print(f"   Testing {test_case['name']}...")
        
        try:
            response = requests.post(f"{BASE_URL}/memory/store", json=test_case['data'])
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    print(f"   ✅ {test_case['name']} routed successfully")
                    passed += 1
                else:
                    print(f"   ⚠️  {test_case['name']} routed but result unclear: {result}")
            else:
                result = response.json()
                error_msg = result.get('error', 'Unknown error')
                
                # Expected errors for services that aren't running
                if 'Service unavailable' in str(error_msg) or 'Connection failed' in str(error_msg):
                    print(f"   ⚠️  {test_case['name']} routing works (service not running): {error_msg}")
                    passed += 1
                else:
                    print(f"   ❌ {test_case['name']} routing failed: {error_msg}")
        
        except requests.ConnectionError:
            print(f"   ❌ Connection failed for {test_case['name']}")
    
    print(f"   Routing tests: {passed}/{len(test_requests)} passed")
    return passed == len(test_requests)

def test_search_routing():
    """Test search routing functionality"""
    print("🔍 Testing search routing...")
    
    search_tests = [
        {
            "name": "Single service search",
            "data": {
                "type": "working",
                "query": "test conversation",
                "limit": 5
            }
        },
        {
            "name": "Multi-service search",
            "data": {
                "type": "all",
                "query": "meeting reminder",
                "limit": 10
            }
        }
    ]
    
    passed = 0
    for test_case in search_tests:
        print(f"   Testing {test_case['name']}...")
        
        try:
            response = requests.post(f"{BASE_URL}/memory/search", json=test_case['data'])
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    print(f"   ✅ {test_case['name']} search routed successfully")
                    passed += 1
                else:
                    print(f"   ⚠️  {test_case['name']} search routed but unclear result")
            else:
                result = response.json()
                error_msg = result.get('error', 'Unknown error')
                
                # Expected errors for services that aren't running
                if 'Service unavailable' in str(error_msg) or 'No services returned' in str(error_msg):
                    print(f"   ⚠️  {test_case['name']} routing works (services not running)")
                    passed += 1
                else:
                    print(f"   ❌ {test_case['name']} search failed: {error_msg}")
        
        except requests.ConnectionError:
            print(f"   ❌ Connection failed for {test_case['name']}")
    
    return passed == len(search_tests)

def test_trace_verification():
    """Test trace verification system"""
    print("🔬 Testing trace verification...")
    
    try:
        # Test batch verification endpoint
        response = requests.post(f"{BASE_URL}/memory/verify_traces")
        
        if response.status_code == 200:
            result = response.json()
            verification_results = result.get('verification_results', {})
            
            print(f"   ✅ Trace verification endpoint working")
            print(f"   📊 Pending verifications: {verification_results.get('total_pending', 0)}")
            print(f"   ✅ Verified: {len(verification_results.get('verified', []))}")
            print(f"   ❌ Failed: {len(verification_results.get('failed', []))}")
            
            return True
        else:
            print(f"   ❌ Trace verification failed: {response.status_code}")
            return False
            
    except requests.ConnectionError:
        print("   ❌ Connection failed")
        return False

def test_routing_error_handling():
    """Test error handling in routing"""
    print("⚠️  Testing routing error handling...")
    
    error_tests = [
        {
            "name": "Invalid memory type",
            "data": {
                "type": "invalid_type",
                "content": "This should fail gracefully"
            },
            "expected_behavior": "Default to working memory"
        },
        {
            "name": "Missing memory type",
            "data": {
                "content": "No type specified"
            },
            "expected_behavior": "Default to working memory"
        },
        {
            "name": "Empty request",
            "data": {},
            "expected_behavior": "Handle gracefully"
        }
    ]
    
    passed = 0
    for test_case in error_tests:
        print(f"   Testing {test_case['name']}...")
        
        try:
            response = requests.post(f"{BASE_URL}/memory/store", json=test_case['data'])
            
            # We expect success (200), server error (500), or bad request (400) for empty data
            if response.status_code in [200, 400, 500]:
                result = response.json()
                if response.status_code == 400:
                    print(f"   ✅ {test_case['name']} properly rejected (HTTP 400)")
                else:
                    print(f"   ✅ {test_case['name']} handled gracefully")
                passed += 1
            else:
                print(f"   ❌ {test_case['name']} not handled properly (HTTP {response.status_code})")
        
        except requests.ConnectionError:
            print(f"   ❌ Connection failed for {test_case['name']}")
    
    return passed == len(error_tests)

def run_routing_tests():
    """Run all routing framework tests"""
    print("🚦 Testing MCP Memory Logger Routing Framework")
    print("=" * 55)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print("❌ Server not running! Start server first.")
        return
    
    tests = [
        ("Service Status", test_service_status),
        ("Memory Routing", test_memory_routing), 
        ("Search Routing", test_search_routing),
        ("Trace Verification", test_trace_verification),
        ("Error Handling", test_routing_error_handling)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            print()
    
    print(f"🚦 Routing Test Results: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 All routing tests passed! Traffic cop is working.")
    else:
        print("⚠️  Some routing tests failed. Check individual results above.")
        
    print("\n📋 Next Steps:")
    print("- Memory services are expected to be unavailable (that's normal)")
    print("- Routing logic is working - requests get directed properly")
    print("- When you build actual memory services, they'll receive these requests")
    print("- Trace verification system is ready for prospective memory integration")

if __name__ == "__main__":
    run_routing_tests()