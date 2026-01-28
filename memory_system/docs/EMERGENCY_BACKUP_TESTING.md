# Emergency Backup System - Testing Requirements
**Component:** Chunk 1 - Backup Writer with Rich Metadata
**Date:** August 31, 2025

---

## 🎯 **Core Functionality Tests**

### **Test EB1: Directory Structure Creation**
1. Import and initialize EmergencyBackupSystem
2. Check that all directories exist:
   - `~/.memory_backup/active/`
   - `~/.memory_backup/pending/`
   - `~/.memory_backup/archived/daily/`
   - `~/.memory_backup/archived/audit/`
   - `~/.memory_backup/recovery/`
**Expected:** All directories created automatically on init

### **Test EB2: Normal Exchange Backup**
1. Set conversation context: `backup.set_conversation_context("test-001", {"model": "gpt-4"})`
2. Create test exchange:
```python
exchange = {
    'user': 'What is Python?',
    'assistant': 'Python is a programming language',
    'timestamp': '2025-08-31T10:00:00'
}
timing = {
    'thinking_time_ms': 1250,
    'was_interrupted': False,
    'token_counts': {'input': 4, 'output': 6}
}
```
3. Backup: `exchange_id = backup.backup_exchange(exchange, timing)`
4. Verify file exists: `~/.memory_backup/active/conversation_test-001.jsonl`
5. Verify pending sync: `~/.memory_backup/pending/{exchange_id}.json`
**Expected:** Exchange saved to both active and pending, returns valid exchange_id

### **Test EB3: Partial Exchange Recovery**
1. Start partial exchange (simulating Ctrl+C interrupt):
```python
partial = {
    'user': 'Tell me a long story',
    'assistant': 'Once upon a time in a...'  # Interrupted
}
partial_id = backup.backup_partial_exchange(partial)
```
2. Check recovery file exists: `~/.memory_backup/recovery/{partial_id}_partial.json`
3. Complete the exchange:
```python
complete = {
    'user': 'Tell me a long story',
    'assistant': 'Once upon a time in a distant land, there lived a wise owl who loved to share stories with travelers.',
}
backup.complete_partial_exchange(partial_id, complete)
```
4. Verify partial file removed, complete exchange in active
**Expected:** Smooth transition from partial to complete, no data loss

### **Test EB4: Manual Checkpoint**
1. Have a conversation with 3-5 exchanges
2. Create checkpoint: `backup.manual_checkpoint("important_discovery")`
3. Check file: `~/.memory_backup/archived/audit/checkpoint_important_discovery.jsonl`
**Expected:** Complete conversation snapshot saved with custom name

### **Test EB5: Rich Metadata Capture**
1. Backup exchange with full timing info:
```python
timing = {
    'thinking_time_ms': 2500,
    'was_interrupted': True,
    'token_counts': {'input': 150, 'output': 200},
    'generation_attempts': 3
}
```
2. Read the saved file and verify all metadata present:
   - model_config (model name, temperature)
   - thinking_time_ms
   - was_interrupted flag
   - token_counts
   - generation_attempts
   - backup_timestamp
   - backup_version
**Expected:** All metadata preserved in backup

---

## 🤖 **AI Context Tests** ✅ NEW

### **Test AI1: Context Usage Tracking**
1. Create conversation with 5+ exchanges
2. Call `context_usage = backup.calculate_context_usage(conversation_history)`
3. Verify returns:
   - `current_tokens`: Accurate count
   - `max_tokens`: 4096 (or configured)
   - `pressure`: Between 0.0 and 1.0
   - `exchanges_before_limit`: Reasonable estimate
**Expected:** Accurate context window tracking for AI awareness

### **Test AI2: Topic Shift Detection**
1. Have conversation about Python
2. Switch to talking about weather
3. Call `is_shift = backup.detect_topic_shift('What is the weather?', prev_exchange)`
**Expected:** Returns True when topic changes significantly

### **Test AI3: AI Context in Backup**
1. Create exchange with full AI context:
```python
ai_context = {
    'context_usage': {'current_tokens': 500, 'max_tokens': 4096, 'pressure': 0.12},
    'topic_shift': True,
    'conversation_phase': 'exploration',
    'confidence_per_statement': {'Answer 1': 0.95, 'Answer 2': 0.60},
    'ambiguities_detected': [{'term': 'it', 'interpreted_as': 'backup system'}],
    'references': ['exchange_123'],
}
backup.backup_exchange(exchange, timing, ai_context)
```
2. Read back from file and verify all AI context preserved
**Expected:** Complete AI metadata available for learning and recovery

### **Test AI4: Error Context Preservation**
1. Simulate failed generation with error context:
```python
ai_context = {
    'previous_errors': [
        {'type': 'timeout', 'attempt': 1},
        {'type': 'confusion', 'attempt': 2, 'reason': 'ambiguous_pronoun'}
    ],
    'recovery_hints': 'User clarified "it" means the backup system'
}
```
2. Backup and verify error history preserved
**Expected:** AI can learn from failures and recover better

---

## 🔥 **Failure Scenario Tests**

### **Test EB6: Multiple Conversation Handling**
1. Set context for conversation A, backup 2 exchanges
2. Switch context to conversation B, backup 3 exchanges
3. Switch back to A, backup 1 more exchange
4. Verify separate files:
   - `conversation_A.jsonl` has 3 exchanges
   - `conversation_B.jsonl` has 3 exchanges
**Expected:** Conversations remain separate, no cross-contamination

### **Test EB7: Pending Queue Management**
1. Backup 10 exchanges
2. Check `backup.get_pending_count()` returns 10
3. Verify all 10 files in pending directory
**Expected:** Accurate pending count, all exchanges queued

### **Test EB8: Recovery Candidates**
1. Create 3 partial exchanges (simulating 3 crashes)
2. Call `candidates = backup.get_recovery_candidates()`
3. Verify returns list of 3 recoverable exchanges
4. Each should have `can_resume: true`
**Expected:** All partial exchanges discoverable for recovery

---

## 📊 **Statistics & Monitoring Tests**

### **Test EB9: Backup Statistics**
1. Create mixed data:
   - 2 complete exchanges
   - 1 partial exchange
   - 1 manual checkpoint
2. Get stats: `stats = backup.get_backup_stats()`
3. Verify:
   - `active_conversations`: 1
   - `pending_sync`: 2
   - `partial_exchanges`: 1
   - `audit_checkpoints`: 1
   - `total_size_mb`: > 0
**Expected:** Accurate statistics for monitoring backup health

### **Test EB10: Compression Readiness**
1. Verify `compress_old_backups()` method exists
2. Verify `read_compressed_archive()` method exists
3. Create test data, compress it, read it back
**Expected:** Compression preserves data integrity

---

## 🚨 **Edge Cases**

### **Test EB11: Empty/Missing Data Handling**
1. Try backing up exchange with empty user message
2. Try backing up exchange with missing assistant response
3. Try backing up with no timing info
**Expected:** Graceful handling, defaults applied, no crashes

### **Test EB12: Concurrent Access**
1. Rapidly backup 20 exchanges (simulating fast conversation)
2. Verify all 20 saved correctly
3. No file corruption, all JSONs valid
**Expected:** Thread-safe operation, no data loss

---

## ✅ **Integration Verification**

### **Test EB13: Integration with rich_chat.py**
1. Import emergency_backup in rich_chat.py
2. Initialize backup system on chat startup
3. Backup each exchange after successful generation
4. On episodic memory failure, verify backup continues
**Expected:** Seamless integration, automatic failover

### **Test EB14: Startup Recovery Check**
1. Create some partial exchanges
2. Restart system
3. On startup, system should detect and offer to recover partials
**Expected:** "Found 3 partial exchanges, recover? [y/n]"

---

## 🎯 **Success Criteria**

**All tests pass when:**
- ✅ Zero data loss under any failure scenario
- ✅ All metadata properly captured and preserved
- ✅ Partial exchanges recoverable after crash
- ✅ Manual checkpoints work on demand
- ✅ Statistics accurately reflect backup state
- ✅ Compression doesn't break data access
- ✅ System handles edge cases gracefully

**Performance Targets:**
- Backup operation < 50ms
- Pending queue can handle 1000+ items
- Compression reduces size by >70%
- Recovery scan < 100ms

---

## 📝 **Manual Testing Checklist**

```bash
# 1. Initialize and check directories
python3 -c "from emergency_backup import EmergencyBackupSystem; b = EmergencyBackupSystem(); print(b.get_backup_stats())"

# 2. Test backup
python3 emergency_backup.py

# 3. Check files created
ls -la ~/.memory_backup/active/
ls -la ~/.memory_backup/pending/
ls -la ~/.memory_backup/recovery/

# 4. Simulate episodic memory failure
# Stop episodic memory service, continue chatting, verify backups accumulate
```

---

## 🔄 **Next Steps After Testing**

Once Chunk 1 tests pass:
1. **Chunk 2:** Recovery thread implementation
2. **Chunk 3:** Integration with rich_chat.py
3. **Chunk 4:** Failure simulation testing