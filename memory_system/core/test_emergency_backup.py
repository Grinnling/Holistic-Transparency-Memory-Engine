#!/usr/bin/env python3
"""
Test harness for Emergency Backup System
Tests all backup writer functionality
"""

import json
import time
import shutil
from pathlib import Path
from datetime import datetime
import tempfile
import unittest
from emergency_backup import EmergencyBackupSystem


class TestEmergencyBackup(unittest.TestCase):
    """Test suite for emergency backup system"""
    
    def setUp(self):
        """Create temp directory for testing"""
        self.test_dir = Path(tempfile.mkdtemp()) / 'test_backup'
        self.backup = EmergencyBackupSystem(backup_root=self.test_dir)
        self.backup.set_conversation_context("test-conv-001", {
            "model": "test-model",
            "temperature": 0.7
        })
        
    def tearDown(self):
        """Clean up test directory"""
        if self.test_dir.parent.exists():
            shutil.rmtree(self.test_dir.parent)
    
    def test_directory_structure_creation(self):
        """Test that all required directories are created"""
        expected_dirs = [
            'active',
            'pending', 
            'archived/daily',
            'archived/audit',
            'recovery'
        ]
        
        for dir_name in expected_dirs:
            dir_path = self.test_dir / dir_name
            self.assertTrue(dir_path.exists(), f"Directory {dir_name} not created")
    
    def test_normal_exchange_backup(self):
        """Test backing up a normal exchange"""
        exchange = {
            'user': 'Test question',
            'assistant': 'Test response',
            'timestamp': datetime.now().isoformat()
        }
        
        timing = {
            'thinking_time_ms': 500,
            'was_interrupted': False,
            'token_counts': {'input': 10, 'output': 20}
        }
        
        exchange_id = self.backup.backup_exchange(exchange, timing)
        
        # Verify exchange was written to active
        active_file = self.test_dir / 'active' / 'conversation_test-conv-001.jsonl'
        self.assertTrue(active_file.exists())
        
        # Verify content
        with open(active_file) as f:
            saved_data = json.loads(f.readline())
            
        self.assertEqual(saved_data['exchange_id'], exchange_id)
        self.assertEqual(saved_data['user'], 'Test question')
        self.assertEqual(saved_data['assistant'], 'Test response')
        self.assertEqual(saved_data['metadata']['thinking_time_ms'], 500)
        
        # Verify queued for sync
        pending_file = self.test_dir / 'pending' / f'{exchange_id}.json'
        self.assertTrue(pending_file.exists())
    
    def test_partial_exchange_backup(self):
        """Test backing up partial/interrupted exchange"""
        partial = {
            'user': 'Tell me about Python',
            'assistant': 'Python is a high-level programming...'  # Interrupted
        }
        
        partial_id = self.backup.backup_partial_exchange(partial)
        
        # Verify partial was saved
        recovery_file = self.test_dir / 'recovery' / f'{partial_id}_partial.json'
        self.assertTrue(recovery_file.exists())
        
        # Verify content
        with open(recovery_file) as f:
            saved_data = json.load(f)
            
        self.assertEqual(saved_data['exchange_id'], partial_id)
        self.assertTrue(saved_data['can_resume'])
        self.assertEqual(saved_data['partial_data']['user'], 'Tell me about Python')
        
        # Test completing the partial
        complete_data = {
            'user': 'Tell me about Python',
            'assistant': 'Python is a high-level programming language known for its simplicity and readability.',
            'timestamp': datetime.now().isoformat()
        }
        
        complete_id = self.backup.complete_partial_exchange(partial_id, complete_data)
        
        # Verify partial was removed
        self.assertFalse(recovery_file.exists())
        
        # Verify complete exchange was backed up
        active_file = self.test_dir / 'active' / 'conversation_test-conv-001.jsonl'
        with open(active_file) as f:
            lines = f.readlines()
            last_exchange = json.loads(lines[-1])
            
        self.assertEqual(last_exchange['exchange_id'], complete_id)
        self.assertEqual(last_exchange['assistant'], complete_data['assistant'])
    
    def test_manual_checkpoint(self):
        """Test manual checkpoint creation"""
        # Add some exchanges first
        for i in range(3):
            exchange = {
                'user': f'Question {i}',
                'assistant': f'Answer {i}',
                'timestamp': datetime.now().isoformat()
            }
            self.backup.backup_exchange(exchange)
        
        # Create manual checkpoint
        result = self.backup.manual_checkpoint("important_moment")
        
        self.assertIn("Checkpoint saved", result)
        
        # Verify checkpoint file exists
        checkpoint_file = self.test_dir / 'archived' / 'audit' / 'checkpoint_important_moment.jsonl'
        self.assertTrue(checkpoint_file.exists())
        
        # Verify it contains all exchanges
        with open(checkpoint_file) as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 3)
    
    def test_metadata_enrichment(self):
        """Test that metadata is properly added"""
        exchange = {
            'user': 'What is the weather?',
            'assistant': 'I cannot check current weather.',
        }
        
        timing = {
            'thinking_time_ms': 750,
            'was_interrupted': True,
            'token_counts': {'input': 5, 'output': 8},
            'generation_attempts': 2
        }
        
        exchange_id = self.backup.backup_exchange(exchange, timing)
        
        # Read back and verify metadata
        active_file = self.test_dir / 'active' / 'conversation_test-conv-001.jsonl'
        with open(active_file) as f:
            saved_data = json.loads(f.readline())
        
        metadata = saved_data['metadata']
        self.assertEqual(metadata['model_config']['model'], 'test-model')
        self.assertEqual(metadata['thinking_time_ms'], 750)
        self.assertTrue(metadata['was_interrupted'])
        self.assertEqual(metadata['generation_attempts'], 2)
        self.assertIn('backup_timestamp', metadata)
        self.assertEqual(metadata['backup_version'], '1.0')
    
    def test_pending_count(self):
        """Test counting pending sync items"""
        self.assertEqual(self.backup.get_pending_count(), 0)
        
        # Add exchanges
        for i in range(5):
            exchange = {'user': f'Q{i}', 'assistant': f'A{i}'}
            self.backup.backup_exchange(exchange)
        
        self.assertEqual(self.backup.get_pending_count(), 5)
    
    def test_recovery_candidates(self):
        """Test getting recoverable partial exchanges"""
        # Add some partials
        for i in range(3):
            partial = {'user': f'Partial {i}', 'assistant': f'Incomplete...'}
            self.backup.backup_partial_exchange(partial)
        
        candidates = self.backup.get_recovery_candidates()
        self.assertEqual(len(candidates), 3)
        self.assertTrue(all(c['can_resume'] for c in candidates))
    
    def test_backup_stats(self):
        """Test backup statistics"""
        # Add various data
        self.backup.backup_exchange({'user': 'Q1', 'assistant': 'A1'})
        self.backup.backup_partial_exchange({'user': 'Q2', 'assistant': 'A2...'})
        self.backup.manual_checkpoint("test_checkpoint")
        
        stats = self.backup.get_backup_stats()
        
        self.assertEqual(stats['active_conversations'], 1)
        self.assertEqual(stats['pending_sync'], 1)
        self.assertEqual(stats['partial_exchanges'], 1)
        self.assertEqual(stats['audit_checkpoints'], 1)
        self.assertGreater(stats['total_size_mb'], 0)
    
    def test_compression_readability(self):
        """Test that compressed archives remain readable"""
        # This would need actual compression testing
        # For now, verify the read_compressed_archive method exists
        self.assertTrue(hasattr(self.backup, 'read_compressed_archive'))


def run_comprehensive_test():
    """Run all tests with detailed output"""
    print("=" * 60)
    print("Emergency Backup System - Comprehensive Test")
    print("=" * 60)
    
    # Run unit tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestEmergencyBackup)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ {len(result.failures)} tests failed")
        for test, traceback in result.failures:
            print(f"\nFailed: {test}")
            print(traceback)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_comprehensive_test()
    exit(0 if success else 1)