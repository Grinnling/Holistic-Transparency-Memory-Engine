#!/usr/bin/env python3
"""
Test recovery thread message routing through ErrorHandler
"""

from rich_chat import RichMemoryChat
import time

print("=== Testing Recovery Thread Message Routing ===\n")

# Create chat with error handler
chat = RichMemoryChat(debug_mode=True)

print("1. Recovery thread should be initialized with error_handler")
print(f"   Recovery thread has error_handler: {chat.recovery_thread.error_handler is not None}")
print(f"   Error handler is the right one: {chat.recovery_thread.error_handler == chat.error_handler}")

print("\n2. Testing message routing (should NOT appear as raw logger output)")
print("   Triggering recovery cycle...")

# Force a recovery cycle to generate messages
chat.recovery_thread._log_info("TEST: Starting recovery cycle")
chat.recovery_thread._log_warning("TEST: Failed attempt 2/3")
chat.recovery_thread._log_error("TEST: Failed 3 times")

print("\n3. Check error panel for routed messages")
print("   Toggle error panel with /errors to see messages")

print("\n✅ If you don't see 'INFO:recovery_thread:' messages above, routing is working!")
print("   Messages should be in error panel instead of console spam.")