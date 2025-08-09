"""
Simple test script for Working Memory Buffer
Run this to verify the basic functionality works
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from buffer import WorkingMemoryBuffer
import json


def test_basic_functionality():
    """Test basic buffer operations"""
    print("=== Testing Working Memory Buffer ===")
    
    # Create buffer with small size for easy testing
    buffer = WorkingMemoryBuffer(max_size=3)
    print(f"Created buffer with max_size=3")
    print(f"Initial summary: {json.dumps(buffer.get_summary(), indent=2)}")
    
    # Test adding exchanges
    print("\n--- Adding exchanges ---")
    
    exchange1 = buffer.add_exchange(
        "What GPU do I have?", 
        "You have an RTX 4060 Ti",
        ["system_hardware_scan"]
    )
    print(f"Added exchange 1: {exchange1['exchange_id']}")
    
    exchange2 = buffer.add_exchange(
        "How much memory?",
        "64GB DDR4, 45GB available"
    )
    print(f"Added exchange 2: {exchange2['exchange_id']}")
    
    exchange3 = buffer.add_exchange(
        "Is Docker running?",
        "Yes, 2 containers active"
    )
    print(f"Added exchange 3: {exchange3['exchange_id']}")
    
    print(f"Buffer size: {buffer.get_current_size()}")
    print(f"Is full: {buffer.is_full()}")
    
    # Test FIFO behavior - add one more to force oldest out
    print("\n--- Testing FIFO behavior ---")
    exchange4 = buffer.add_exchange(
        "What OS am I running?",
        "Ubuntu 22.04.3 LTS"
    )
    print(f"Added exchange 4: {exchange4['exchange_id']}")
    print(f"Buffer size after overflow: {buffer.get_current_size()}")
    
    # Check what's in the buffer now
    recent = buffer.get_recent_context()
    print(f"Exchanges in buffer: {len(recent)}")
    for i, exchange in enumerate(recent):
        print(f"  {i+1}. {exchange['user_message'][:20]}...")
    
    print(f"\nFinal summary: {json.dumps(buffer.get_summary(), indent=2)}")
    
    print("\n=== Basic test complete ===")


if __name__ == "__main__":
    test_basic_functionality()