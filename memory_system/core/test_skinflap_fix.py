#!/usr/bin/env python3
"""
Quick test to verify skinflap detector no longer blocks normal conversation
"""

from rich_chat import RichMemoryChat
from unittest.mock import Mock

def test_skinflap_flow():
    """Test that skinflap detection info gets passed to model instead of blocking"""
    
    # Create chat instance (no auto-start to avoid services)
    chat = RichMemoryChat(debug_mode=True, auto_start_services=False)
    
    if not chat:
        print("❌ Rich not available")
        return
    
    # Mock the LLM to avoid actual calls
    chat.llm = Mock()
    chat.llm.generate_response = Mock(return_value="This is a test response")
    
    # Test the problematic patterns that were previously blocking
    test_messages = [
        "it works great",  # Should NOT block - "it" with context
        "fix it",          # SHOULD trigger detection but let model decide
        "make it better",  # SHOULD trigger detection but let model decide
        "hello there"      # Should NOT trigger anything
    ]
    
    for msg in test_messages:
        print(f"\n🧪 Testing: '{msg}'")
        
        # Test skinflap detection
        skinflap_result = chat.check_with_skinflap(msg)
        print(f"   Skinflap blocks: {skinflap_result['needs_clarification']}")
        
        detection_info = skinflap_result.get('detection_info', {})
        if detection_info.get('detected_issues'):
            print(f"   Issues detected: {len(detection_info['detected_issues'])}")
            patterns = [issue.get('pattern') for issue in detection_info['detected_issues']]
            print(f"   Patterns: {patterns}")
        else:
            print(f"   No issues detected")
    
    print(f"\n✅ Test complete - skinflap should never block, just provide detection info")

if __name__ == "__main__":
    test_skinflap_flow()