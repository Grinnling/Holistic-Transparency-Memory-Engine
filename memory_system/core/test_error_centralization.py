#!/usr/bin/env python3
"""
Error Centralization Validation Test
Tests that errors flow through the complete pipeline:
1. Component (memory_handler/coordinator) → error_handler
2. error_handler → recent_errors storage
3. Proper formatting and categorization
"""

import sys
from pathlib import Path

# Add CODE_IMPLEMENTATION to path
sys.path.insert(0, str(Path(__file__).parent))

from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
from memory_handler import MemoryHandler
from episodic_memory_coordinator import EpisodicMemoryCoordinator

def test_memory_handler_error_routing():
    """Test that memory_handler routes errors to error_handler"""
    print("\n🧪 TEST 1: Memory Handler Error Routing")
    print("=" * 60)

    # Create error handler
    error_handler = ErrorHandler(debug_mode=True)

    # Create memory handler with our error handler
    memory_handler = MemoryHandler(
        error_handler=error_handler,
        debug_mode=True
    )

    # Clear any existing errors
    error_handler.recent_errors = []

    # Trigger an info message (should route to error_handler now)
    memory_handler._info_message("Test info message", ErrorCategory.EPISODIC_MEMORY)

    # Check if error was recorded
    if len(error_handler.recent_errors) > 0:
        error = error_handler.recent_errors[-1]
        print(f"✅ Error captured!")
        print(f"   Category: {error['category']}")
        print(f"   Severity: {error['severity']}")
        print(f"   Message: {error['message']}")
        print(f"   Operation: {error['operation']}")

        # Validate format
        assert error['category'] == ErrorCategory.EPISODIC_MEMORY.value
        assert error['severity'] == ErrorSeverity.LOW_DEBUG.value
        assert 'Test info message' in error['message']
        print("✅ Format validation passed!")
        return True
    else:
        print("❌ No error captured in recent_errors!")
        return False

def test_coordinator_error_routing():
    """Test that coordinator routes errors to error_handler"""
    print("\n🧪 TEST 2: Coordinator Error Routing")
    print("=" * 60)

    # Create error handler
    error_handler = ErrorHandler(debug_mode=True)

    # Create coordinator with our error handler (invalid URL to trigger errors)
    coordinator = EpisodicMemoryCoordinator(
        episodic_url="http://invalid-test-url:9999",
        error_handler=error_handler
    )

    # Clear any existing errors
    error_handler.recent_errors = []

    # Trigger a health check (will fail with connection error)
    result = coordinator.health_check()

    # Check if error was recorded
    if len(error_handler.recent_errors) > 0:
        error = error_handler.recent_errors[-1]
        print(f"✅ Error captured!")
        print(f"   Category: {error['category']}")
        print(f"   Severity: {error['severity']}")
        print(f"   Message: {error['message']}")
        print(f"   Operation: {error['operation']}")

        # Validate it's a health check error
        assert error['operation'] == 'health_check'
        assert error['category'] == ErrorCategory.EPISODIC_MEMORY.value
        print("✅ Coordinator error routing works!")
        return True
    else:
        print("❌ No error captured from coordinator!")
        return False

def test_error_handler_storage():
    """Test that error_handler properly stores errors with metadata"""
    print("\n🧪 TEST 3: Error Handler Storage Format")
    print("=" * 60)

    error_handler = ErrorHandler(debug_mode=True)
    error_handler.recent_errors = []

    # Manually trigger an error through error_handler
    test_error = Exception("Test exception for validation")
    error_handler.handle_error(
        test_error,
        ErrorCategory.MEMORY_ARCHIVAL,
        ErrorSeverity.MEDIUM_ALERT,
        context="Testing error storage",
        operation="test_operation"
    )

    # Verify storage
    if len(error_handler.recent_errors) > 0:
        error = error_handler.recent_errors[-1]
        print(f"✅ Error stored!")
        print(f"   Required fields present:")

        required_fields = ['timestamp', 'category', 'severity', 'error_type',
                          'message', 'context', 'operation']

        for field in required_fields:
            if field in error:
                print(f"   ✅ {field}: {error[field]}")
            else:
                print(f"   ❌ {field}: MISSING!")
                return False

        print("✅ All required fields present!")
        return True
    else:
        print("❌ Error not stored!")
        return False

def test_severity_levels():
    """Test different severity levels are handled correctly"""
    print("\n🧪 TEST 4: Severity Level Handling")
    print("=" * 60)

    severities = [
        ErrorSeverity.CRITICAL_STOP,
        ErrorSeverity.HIGH_DEGRADE,
        ErrorSeverity.MEDIUM_ALERT,
        ErrorSeverity.LOW_DEBUG
    ]

    for severity in severities:
        # Create fresh error handler for each test to avoid state contamination
        error_handler = ErrorHandler(debug_mode=True)
        error_handler.handle_error(
            Exception(f"Test {severity.value}"),
            ErrorCategory.GENERAL,
            severity,
            context=f"Testing {severity.value}",
            operation=f"test_{severity.value}"
        )

        if len(error_handler.recent_errors) > 0:
            error = error_handler.recent_errors[-1]
            if error['severity'] == severity.value:
                print(f"   ✅ {severity.value}: Correctly stored")
            else:
                print(f"   ❌ {severity.value}: Wrong severity in storage")
                return False
        else:
            print(f"   ❌ {severity.value}: Not stored")
            return False

    print("✅ All severity levels handled correctly!")
    return True

def run_all_tests():
    """Run all validation tests"""
    print("\n" + "=" * 60)
    print("🧪 ERROR CENTRALIZATION VALIDATION TESTS")
    print("=" * 60)

    tests = [
        ("Memory Handler Error Routing", test_memory_handler_error_routing),
        ("Coordinator Error Routing", test_coordinator_error_routing),
        ("Error Handler Storage", test_error_handler_storage),
        ("Severity Level Handling", test_severity_levels)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Error centralization is working correctly!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review output above.")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
