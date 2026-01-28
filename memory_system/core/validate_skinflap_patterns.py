#!/usr/bin/env python3
"""
Validate skinflap detection patterns work as expected
"""

from skinflap_stupidity_detection import CollaborativeQueryReformer

def test_pattern_detection():
    """Test specific patterns that should/shouldn't trigger"""
    
    reformer = CollaborativeQueryReformer()
    
    # Test cases that SHOULD trigger vague_request
    should_trigger = [
        "fix it",
        "better",
        "improve", 
        "make it work",
        "optimize",
        "handle this",
        "deal with"
    ]
    
    # Test cases that should NOT trigger (because they don't start with vague words)
    should_not_trigger = [
        "make it better",  # Doesn't start with "better"
        "can you fix it",  # Doesn't start with "fix it"
        "please improve",  # Doesn't start with "improve" 
        "i need to optimize", # Doesn't start with "optimize"
        "it works great",  # Normal conversation
        "hello there"      # Greeting
    ]
    
    print("🧪 Testing patterns that SHOULD trigger vague_request detection:")
    for query in should_trigger:
        result = reformer.process_query(query, [])
        vague_detected = any(issue['pattern'] == 'vague_request' for issue in result.detected_issues)
        status = "✅" if vague_detected else "❌"
        print(f"  {status} '{query}' → vague_request: {vague_detected}")
    
    print("\n🧪 Testing patterns that should NOT trigger:")
    for query in should_not_trigger:
        result = reformer.process_query(query, [])
        vague_detected = any(issue['pattern'] == 'vague_request' for issue in result.detected_issues)
        status = "✅" if not vague_detected else "❌"
        print(f"  {status} '{query}' → vague_request: {vague_detected}")
        
        # Show what WAS detected if anything
        if result.detected_issues:
            patterns = [issue['pattern'] for issue in result.detected_issues]
            print(f"      (detected: {patterns})")

if __name__ == "__main__":
    test_pattern_detection()