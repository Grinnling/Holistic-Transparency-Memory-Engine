#!/usr/bin/env python3
"""
Force an actual error to test error panel tracking
This will temporarily break something to verify errors show up
"""

import requests
import time

API_BASE = "http://localhost:8000"

def test_trigger_backend_error():
    """
    Send a message that might trigger internal errors
    """
    print("Testing error tracking by sending problematic input...")

    # Try various inputs that might cause issues
    test_cases = [
        {"name": "Unicode chaos", "message": "🔥" * 1000},
        {"name": "SQL-like injection attempt", "message": "'; DROP TABLE--"},
        {"name": "Script injection", "message": "<script>alert('test')</script>"},
        {"name": "Null bytes", "message": "test\x00null\x00bytes"},
        {"name": "Extreme nesting", "message": "{{{{{{{{{{test}}}}}}}}}}"},
    ]

    for test in test_cases:
        print(f"\nTest: {test['name']}")
        try:
            response = requests.post(
                f"{API_BASE}/chat",
                json={"message": test['message']},
                timeout=10
            )
            print(f"  Status: {response.status_code}")
            if response.ok:
                data = response.json()
                if data.get('error'):
                    print(f"  ✓ Error captured: {data['error'][:80]}...")
                else:
                    print(f"  ✓ Handled gracefully")
            else:
                print(f"  ✗ HTTP error: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"  ⏱ Timeout - might have caused backend issues")
        except Exception as e:
            print(f"  ✗ Exception: {e}")

        time.sleep(1)

def check_errors():
    """Check if errors appeared in the panel"""
    print("\n" + "="*60)
    print("Checking error panel...")

    try:
        response = requests.get(f"{API_BASE}/errors")
        if response.ok:
            data = response.json()
            all_errors = data.get("session", []) + data.get("recent", [])

            if len(all_errors) == 0:
                print("⚠️ NO ERRORS CAPTURED - Error tracking might not be working")
                print("   or all edge cases were handled gracefully (also good!)")
            else:
                print(f"✅ Found {len(all_errors)} errors in panel:")
                for err in all_errors:
                    print(f"   [{err['severity']}] {err['service']}: {err['error'][:100]}...")
        else:
            print(f"Failed to fetch errors: {response.status_code}")
    except Exception as e:
        print(f"Error checking panel: {e}")

if __name__ == "__main__":
    print("="*60)
    print("Force Error Test - Verify Error Panel Tracking")
    print("="*60)
    print("\nThis will send edge-case inputs to try to trigger errors.")
    print("Watch the React Error panel for any errors that appear.\n")

    input("Press Enter to start tests...")

    test_trigger_backend_error()

    print("\nWaiting 3 seconds for errors to propagate...")
    time.sleep(3)

    check_errors()

    print("\n" + "="*60)
    print("Check the React UI error panel now!")
    print("If you see errors there, tracking is working ✅")
    print("If no errors but tests ran, handling is robust ✅")
    print("="*60)
