#!/usr/bin/env python3
"""
Create a definite error by temporarily breaking the code
This is a proof-of-concept test
"""

import requests
import time

API_BASE = "http://localhost:8000"

print("""
============================================================
MANUAL ERROR INJECTION TEST
============================================================

To test error tracking, we need to temporarily break something.

INSTRUCTIONS:
1. Open rich_chat.py
2. Find the process_message function (around line 254)
3. Add this line right after the function starts:

   raise ValueError("TEST ERROR - Delete this line after testing")

4. Save the file
5. Press Enter here to run the test
6. Watch the React error panel - you should see the error appear
7. Remove the test line when done

Press Enter when ready (or Ctrl+C to cancel)...
""")

input()

print("\nSending test message that will trigger the error...")
try:
    response = requests.post(
        f"{API_BASE}/chat",
        json={"message": "test"},
        timeout=5
    )
    print(f"Response: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Data: {data}")
    else:
        print(f"Error response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")

print("\nWaiting 2 seconds...")
time.sleep(2)

print("\nChecking error panel...")
response = requests.get(f"{API_BASE}/errors")
if response.ok:
    data = response.json()
    all_errors = data.get("session", []) + data.get("recent", [])

    if len(all_errors) > 0:
        print(f"\n✅ SUCCESS! Found {len(all_errors)} error(s) in panel:")
        for err in all_errors:
            print(f"  - [{err['severity']}] {err['error']}")
        print("\n✅ Error tracking is working!")
    else:
        print("\n❌ No errors in panel - tracking might not be connected")

print("\n⚠️ Don't forget to remove the test error line from rich_chat.py!")
