#!/usr/bin/env python3
"""
Test script for MCP Memory Logger authentication
Tests both authenticated and unauthenticated requests
"""

import requests
import json
import time
import hashlib
import hmac
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

BASE_URL = "http://localhost:8001"
AUTH_KEY = os.getenv('MEMORY_AUTH_KEY', 'development_key_change_in_production')

def generate_auth_header(data: str = "") -> str:
    """Generate authentication header matching server logic"""
    timestamp = str(int(time.time()))
    message = f"{data}:{timestamp}"
    signature = hmac.new(
        AUTH_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{signature}:{timestamp}"

def test_unauthenticated_access():
    """Test endpoints without authentication (should work in dev mode)"""
    print("🔓 Testing unauthenticated access (dev mode)...")
    
    # Test health (public endpoint)
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print("✅ Health check works without auth")
    else:
        print(f"❌ Health check failed: {response.status_code}")
    
    # Test memory endpoints without auth
    test_data = {"type": "working", "content": "Test without auth"}
    response = requests.post(f"{BASE_URL}/memory/store", json=test_data)
    
    if response.status_code == 200:
        print("✅ Memory endpoints work without auth (dev mode)")
        return True
    elif response.status_code == 401:
        print("🔒 Auth required - production mode enabled")
        return False
    else:
        print(f"❌ Unexpected response: {response.status_code}")
        return False

def test_authenticated_access():
    """Test endpoints with proper authentication"""
    print("🔐 Testing authenticated access...")
    
    test_data = {"type": "working", "content": "Test with auth"}
    data_string = json.dumps(test_data)
    auth_header = generate_auth_header(data_string)
    
    headers = {
        'X-Memory-Auth': auth_header,
        'Content-Type': 'application/json'
    }
    
    # Test store with auth
    response = requests.post(f"{BASE_URL}/memory/store", json=test_data, headers=headers)
    if response.status_code == 200:
        print("✅ Authenticated store request successful")
    else:
        print(f"❌ Authenticated store failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    # Test recall with auth
    recall_data = {"type": "working", "limit": 5}
    data_string = json.dumps(recall_data)
    auth_header = generate_auth_header(data_string)
    headers['X-Memory-Auth'] = auth_header
    
    response = requests.post(f"{BASE_URL}/memory/recall", json=recall_data, headers=headers)
    if response.status_code == 200:
        print("✅ Authenticated recall request successful")
        return True
    else:
        print(f"❌ Authenticated recall failed: {response.status_code}")
        return False

def test_invalid_auth():
    """Test with invalid authentication"""
    print("❌ Testing invalid authentication...")
    
    test_data = {"type": "working", "content": "Test with bad auth"}
    headers = {
        'X-Memory-Auth': 'invalid_token_here',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(f"{BASE_URL}/memory/store", json=test_data, headers=headers)
    if response.status_code == 401:
        print("✅ Invalid auth properly rejected")
        return True
    else:
        print(f"❌ Invalid auth not rejected: {response.status_code}")
        return False

def test_security_headers():
    """Test security headers are present"""
    print("🛡️  Testing security headers...")
    
    response = requests.get(f"{BASE_URL}/health")
    headers = response.headers
    
    security_headers = [
        'X-Content-Type-Options',
        'X-Frame-Options', 
        'X-XSS-Protection'
    ]
    
    passed = 0
    for header in security_headers:
        if header in headers:
            print(f"✅ {header}: {headers[header]}")
            passed += 1
        else:
            print(f"❌ Missing security header: {header}")
    
    return passed == len(security_headers)

def run_auth_tests():
    """Run all authentication tests"""
    print("🔐 Testing MCP Memory Logger Authentication")
    print("=" * 50)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print("❌ Server not running! Start server first.")
        return
    
    tests = [
        test_unauthenticated_access,
        test_security_headers,
        # Only test auth if it's enabled
        test_authenticated_access if os.getenv('MEMORY_AUTH_ENABLED', 'false') == 'true' else lambda: True,
        test_invalid_auth if os.getenv('MEMORY_AUTH_ENABLED', 'false') == 'true' else lambda: True
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            print()
    
    print(f"Security Test Results: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 All security tests passed!")
    else:
        print("⚠️  Some security tests failed.")

if __name__ == "__main__":
    run_auth_tests()