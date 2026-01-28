#!/usr/bin/env python3
"""
Test script to verify error tracking flows to the error panel
Run this and check the React error panel to see if errors appear
"""

import requests
import time

API_BASE = "http://localhost:8000"

def test_chat_with_empty_message():
    """Test 1: Empty message (should be handled gracefully)"""
    print("Test 1: Sending empty message...")
    try:
        response = requests.post(f"{API_BASE}/chat", json={"message": ""})
        print(f"  Response: {response.status_code}")
        if response.ok:
            print(f"  Data: {response.json()}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1)

def test_chat_with_very_long_message():
    """Test 2: Very long message (might trigger memory issues)"""
    print("\nTest 2: Sending very long message...")
    long_message = "test " * 10000  # 50k chars
    try:
        response = requests.post(f"{API_BASE}/chat", json={"message": long_message}, timeout=30)
        print(f"  Response: {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1)

def test_malformed_request():
    """Test 3: Malformed JSON (should trigger validation error)"""
    print("\nTest 3: Sending malformed request...")
    try:
        response = requests.post(f"{API_BASE}/chat", json={"wrong_field": "test"})
        print(f"  Response: {response.status_code}")
        if not response.ok:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1)

def test_normal_message():
    """Test 4: Normal message (should work fine, no errors)"""
    print("\nTest 4: Sending normal message...")
    try:
        response = requests.post(f"{API_BASE}/chat", json={"message": "Hello, this is a test"})
        print(f"  Response: {response.status_code}")
        if response.ok:
            data = response.json()
            print(f"  Response preview: {data.get('response', '')[:100]}...")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1)

def check_error_panel():
    """Check if errors are in the error panel"""
    print("\n" + "="*60)
    print("Checking error panel...")
    try:
        response = requests.get(f"{API_BASE}/errors")
        if response.ok:
            data = response.json()
            session_errors = data.get("session", [])
            recent_errors = data.get("recent", [])

            print(f"\nSession errors: {len(session_errors)}")
            for err in session_errors:
                print(f"  - [{err['severity']}] {err['error'][:80]}...")

            print(f"\nRecent errors: {len(recent_errors)}")
            for err in recent_errors:
                print(f"  - [{err['severity']}] {err['error'][:80]}...")

            if len(session_errors) == 0 and len(recent_errors) == 0:
                print("\n✅ No errors detected (this is good if tests passed)")
            else:
                print(f"\n⚠️ Total errors tracked: {len(session_errors) + len(recent_errors)}")
        else:
            print(f"Failed to fetch errors: {response.status_code}")
    except Exception as e:
        print(f"Error checking panel: {e}")

if __name__ == "__main__":
    print("="*60)
    print("Error Tracking Test Suite")
    print("="*60)
    print("\nMake sure:")
    print("1. API server is running (python3 api_server_bridge.py)")
    print("2. React UI is open in browser")
    print("3. You're watching the Error panel tab")
    print("\nStarting tests in 3 seconds...")
    time.sleep(3)

    test_normal_message()
    test_chat_with_empty_message()
    test_malformed_request()
    # test_chat_with_very_long_message()  # Commented out - takes a while

    check_error_panel()

    print("\n" + "="*60)
    print("Tests complete! Check the React error panel now.")
    print("="*60)
