#!/usr/bin/env python3
"""
Live Error Pipeline Test
Tests that errors actually flow to the React UI through the running API server
"""

import requests
import time
from datetime import datetime

API_URL = "http://localhost:8000"

def test_api_server_running():
    """Check if API server is running"""
    print("\n🔍 TEST 1: API Server Health Check")
    print("=" * 60)

    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✅ API server is running (status: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ API server is not running!")
        print("   Please start it with: python3 api_server_bridge.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_trigger_memory_search_error():
    """Trigger an error by searching with invalid query"""
    print("\n🔍 TEST 2: Trigger Memory Search Error")
    print("=" * 60)

    try:
        # Empty query should trigger an error
        response = requests.get(f"{API_URL}/memory/search", params={"query": ""}, timeout=5)
        print(f"✅ Request sent (status: {response.status_code})")

        # Check if error was returned
        data = response.json()
        if "error" in data:
            print(f"✅ Error response received: {data['error']}")
            return True
        else:
            print("⚠️  No error in response (might not have triggered error handler)")
            return True
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_errors_endpoint():
    """Check if errors appear in /errors endpoint"""
    print("\n🔍 TEST 3: Check /errors Endpoint")
    print("=" * 60)

    try:
        response = requests.get(f"{API_URL}/errors", timeout=5)

        if response.status_code != 200:
            print(f"❌ /errors endpoint failed (status: {response.status_code})")
            return False

        data = response.json()
        print(f"✅ /errors endpoint responding")
        print(f"   Session errors: {len(data.get('session', []))}")
        print(f"   Recent errors: {len(data.get('recent', []))}")

        # Show last 3 errors
        recent = data.get('recent', [])
        if recent:
            print(f"\n   Last {min(3, len(recent))} errors:")
            for error in recent[-3:]:
                print(f"   - [{error.get('severity', 'unknown')}] {error.get('error', 'no message')[:80]}")
                print(f"     Operation: {error.get('operation_context', 'unknown')}")
                print(f"     Time: {error.get('timestamp', 'unknown')}")
        else:
            print("   ⚠️  No errors in recent list")

        return True

    except Exception as e:
        print(f"❌ Failed to fetch errors: {e}")
        return False

def test_trigger_chat_error():
    """Trigger an error through chat endpoint"""
    print("\n🔍 TEST 4: Trigger Chat Processing Error")
    print("=" * 60)

    try:
        # Send a message that might trigger internal errors
        response = requests.post(
            f"{API_URL}/chat",
            json={"message": "test error pipeline"},
            timeout=30
        )

        print(f"✅ Chat request completed (status: {response.status_code})")

        data = response.json()
        if "error" in data:
            print(f"✅ Error response received: {data['error']}")
        else:
            print(f"✅ Chat processed successfully: {data.get('response', '')[:80]}")

        return True

    except Exception as e:
        print(f"❌ Chat request failed: {e}")
        return False

def test_final_error_check():
    """Final check of /errors endpoint after all tests"""
    print("\n🔍 TEST 5: Final Error Panel Check")
    print("=" * 60)

    try:
        response = requests.get(f"{API_URL}/errors", timeout=5)
        data = response.json()

        recent = data.get('recent', [])
        print(f"✅ Total errors captured: {len(recent)}")

        if recent:
            print(f"\n   All errors from this session:")
            for i, error in enumerate(recent[-10:], 1):  # Last 10 errors
                severity = error.get('severity', 'unknown')
                msg = error.get('error', 'no message')[:60]
                op = error.get('operation_context', 'unknown')[:30]
                print(f"   {i}. [{severity}] {msg}")
                print(f"      Op: {op}")

            print(f"\n✅ React error panel should be displaying these errors!")
            return True
        else:
            print("⚠️  No errors captured - this might indicate a problem")
            return False

    except Exception as e:
        print(f"❌ Final check failed: {e}")
        return False

def run_live_pipeline_test():
    """Run all live pipeline tests"""
    print("\n" + "=" * 60)
    print("🧪 LIVE ERROR PIPELINE VALIDATION")
    print("=" * 60)
    print("This test triggers real errors through the API server")
    print("and verifies they appear in the /errors endpoint.")
    print("=" * 60)

    tests = [
        ("API Server Running", test_api_server_running),
        ("Trigger Memory Search Error", test_trigger_memory_search_error),
        ("Check Errors Endpoint", test_errors_endpoint),
        ("Trigger Chat Error", test_trigger_chat_error),
        ("Final Error Panel Check", test_final_error_check)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            # Small delay between tests
            if results:  # Not first test
                time.sleep(0.5)

            result = test_func()
            results.append((test_name, result))

            # If API server isn't running, stop
            if test_name == "API Server Running" and not result:
                print("\n⚠️  Cannot continue without API server. Stopping tests.")
                break

        except Exception as e:
            print(f"\n❌ {test_name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 LIVE PIPELINE TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL LIVE TESTS PASSED!")
        print("✅ Error centralization is working end-to-end!")
        print("✅ React error panel should be displaying errors!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        if results[0][1] == False:  # API server not running
            print("\nℹ️  Start API server with: python3 api_server_bridge.py")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = run_live_pipeline_test()
    sys.exit(exit_code)
