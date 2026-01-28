# Recovery Thread Phase 2 - Testing Requirements
**Component:** Smart Recovery Logic  
**Date:** August 31, 2025

---

## 🎯 **Phase 2 Enhancements**
Building on Phase 1, adding:
- **Batch processing** (5-10 files per cycle)
- **3-strike failure rule** → failed directory
- **Data integrity verification** before cleanup
- **Advanced failure classification** (network/data/auth/server errors)

---

## 📦 **Batch Processing Tests**

### **Test RT2-1: Batch Size Calculation**
1. Test batch size with different queue sizes:
```python
# Small queue
assert recovery._calculate_batch_size(3) == 3

# Medium queue  
assert recovery._calculate_batch_size(15) == 5

# Large queue
assert recovery._calculate_batch_size(35) == 8

# Huge backlog
assert recovery._calculate_batch_size(100) == 12
```
**Expected:** Appropriate batch sizes prevent overwhelming episodic memory

### **Test RT2-2: Batch Processing Execution**
1. Create 10 pending files
2. Start episodic memory service
3. Run recovery cycle
4. Verify batch processed (not one-at-a-time like Phase 1)
5. Check logs show "X/Y succeeded" format
**Expected:** Multiple files processed in single cycle

### **Test RT2-3: Batch Processing with Mixed Success**
1. Create 8 pending files - 5 valid, 3 corrupted JSON
2. Run recovery cycle  
3. Verify 5 files processed successfully
4. Verify 3 files tracked for retry (not moved to failed yet)
**Expected:** Batch handles mix of success/failure gracefully

---

## 🔒 **Data Verification Tests**

### **Test RT2-4: Verification Success Path**
1. Create valid pending file
2. Mock episodic memory to accept POST and respond to GET
3. Run `_process_single_file_with_verification()`
4. Verify:
   - File sent to episodic memory
   - Verification GET request made
   - File removed from pending only after verification
**Expected:** File only removed after confirmed storage

### **Test RT2-5: Verification Failure Handling**
1. Create valid pending file
2. Mock episodic memory to accept POST but 404 on GET
3. Run verification process
4. Verify:
   - File remains in pending (not removed)
   - Error logged as 'verification_failure'
   - Will be retried in next cycle
**Expected:** Verification failure prevents data loss

### **Test RT2-6: Verification Timeout**
1. Create valid pending file
2. Mock episodic memory with slow verification endpoint (6+ second delay)
3. Run verification process
4. Verify graceful timeout handling
**Expected:** Doesn't hang on slow verification

---

## ⚡ **3-Strike Failure Rule Tests**

### **Test RT2-7: Strike Tracking**
1. Create pending file that will fail (corrupt data)
2. Run recovery cycle 3 times
3. Check failure tracking after each attempt:
   - Attempt 1: `attempt_count: 1`, file in pending
   - Attempt 2: `attempt_count: 2`, file in pending  
   - Attempt 3: `attempt_count: 3`, file moved to failed
**Expected:** Accurate strike counting, moves after 3rd failure

### **Test RT2-8: Failed Directory Organization**
1. Create files that fail with different error types:
   - Network timeout
   - Bad JSON
   - Server error
2. Run recovery until all moved to failed
3. Verify directory structure:
```
~/.memory_backup/failed/
  ├── network_timeout/
  │   └── exchange_abc_20250831_143022.json
  ├── data_corruption/
  │   └── exchange_def_20250831_143025.json  
  └── server_error/
      └── exchange_ghi_20250831_143028.json
```
**Expected:** Failed files organized by error type

### **Test RT2-9: Failed Files Summary**
1. Create failed files in multiple error type directories
2. Call `recovery.get_failed_files_summary()`
3. Verify returns:
   - `total_failed`: Accurate count
   - `by_error_type`: Breakdown by category
   - Timestamps for oldest/newest
**Expected:** Comprehensive failed files reporting

---

## 🏷️ **Error Classification Tests**

### **Test RT2-10: HTTP Error Classification**
1. Test various HTTP status codes:
```python
assert recovery._classify_http_error(400) == 'bad_request'
assert recovery._classify_http_error(401) == 'auth_failure' 
assert recovery._classify_http_error(500) == 'server_error'
assert recovery._classify_http_error(429) == 'rate_limited'
```
**Expected:** Accurate error type classification

### **Test RT2-11: Network Error Classification**
1. Mock different network failures:
   - Connection refused
   - Timeout
   - DNS failure
2. Run processing and verify error types assigned correctly
**Expected:** Network errors properly categorized

### **Test RT2-12: Data Corruption Detection**
1. Create files with various data issues:
   - Invalid JSON
   - Missing required fields
   - Corrupted file content
2. Process and verify classified as 'data_corruption'
**Expected:** Data issues identified and categorized

---

## 📊 **Enhanced Status Reporting Tests**

### **Test RT2-13: Comprehensive Queue Status**
1. Create mix of pending files and failed files
2. Get recovery status
3. Verify new fields present:
   - `retry_tracking`: Files being retried
   - `permanently_failed`: Total in failed directory
   - Batch size calculations
**Expected:** Complete queue visibility

### **Test RT2-14: Performance Metrics with Verification**
1. Process files with verification enabled
2. Check performance includes verification timing
3. Verify success/failure rates accurate with new logic
**Expected:** Metrics account for verification overhead

---

## 🔄 **Integration Tests**

### **Test RT2-15: Full Recovery Workflow**
1. Create 20 pending files (15 good, 5 problematic)
2. Start recovery thread
3. Let run for several cycles
4. Verify end state:
   - 15 files successfully processed and verified
   - 5 files moved to appropriate failed directories
   - No files left in pending
   - Accurate statistics
**Expected:** Complete processing with proper error handling

### **Test RT2-16: Recovery Under Load**
1. Create 100 pending files
2. Start recovery thread
3. Monitor processing over 5+ minutes
4. Verify:
   - Batch processing handles large queues
   - No memory leaks or performance degradation  
   - All files eventually processed or failed appropriately
**Expected:** Stable operation under high load

### **Test RT2-17: Manual Failed File Recovery**
1. Move some files to failed directory
2. Manually move them back to pending
3. Verify they get reprocessed (strike count reset)
**Expected:** Manual recovery workflow functional

---

## 🚨 **Edge Case Tests**

### **Test RT2-18: Episodic Memory Partial Outage**
1. Start processing batch of files
2. Stop episodic memory service mid-batch
3. Verify:
   - Processed files before outage are verified/cleaned
   - Remaining files properly handled as failures
   - No corruption or lost files
**Expected:** Graceful handling of mid-processing outage

### **Test RT2-19: Disk Space Exhaustion**
1. Fill up disk space (or mock filesystem full)
2. Try to move files to failed directory
3. Verify graceful degradation
**Expected:** Handles filesystem issues without crashing

---

## ✅ **Success Criteria for Phase 2**

**Batch Processing:**
- ✅ Calculates appropriate batch sizes
- ✅ Processes multiple files per cycle efficiently  
- ✅ Handles mixed success/failure in batches

**Data Integrity:**
- ✅ Verifies successful storage before cleanup
- ✅ Retries when verification fails
- ✅ No data loss under any failure scenario

**Failure Management:**
- ✅ Accurate 3-strike tracking per file
- ✅ Failed files organized by error type
- ✅ Comprehensive failure classification

**Error Classification:**
- ✅ Distinguishes network, data, auth, server errors
- ✅ Provides actionable error categories
- ✅ Enables targeted debugging

**Monitoring:**
- ✅ Enhanced status with batch and failure info
- ✅ Failed files summary and statistics
- ✅ Performance metrics include verification

---

## 🔧 **Manual Testing Commands**

```bash
# 1. Test batch processing with real files
python3 -c "
from recovery_thread import RecoveryThread
from emergency_backup import EmergencyBackupSystem
import json
from pathlib import Path

# Create test files
backup = EmergencyBackupSystem()
pending_dir = backup.backup_root / 'pending'
pending_dir.mkdir(exist_ok=True)

# Create 10 test files
for i in range(10):
    test_data = {
        'exchange_id': f'test_{i}',
        'user': f'Question {i}',
        'assistant': f'Answer {i}',
        'conversation_id': 'test_conv'
    }
    with open(pending_dir / f'test_{i}.json', 'w') as f:
        json.dump(test_data, f)

recovery = RecoveryThread(backup, interval=5)
recovery.start_recovery_thread()
print('Started with 10 pending files')
"

# 2. Test 3-strike rule
# Create a file with bad data, watch it fail 3 times and move to failed

# 3. Check failed files summary
python3 -c "
from recovery_thread import RecoveryThread
from emergency_backup import EmergencyBackupSystem
backup = EmergencyBackupSystem()
recovery = RecoveryThread(backup)
print('Failed files:', recovery.get_failed_files_summary())
"
```

---

## 🔄 **Next: Phase 3 Preparation**

Once Phase 2 tests pass:
- ✅ Batch processing working efficiently
- ✅ Data integrity verification preventing loss
- ✅ 3-strike rule managing permanent failures  
- ✅ Error classification enabling targeted fixes
- **Ready for Phase 3:** Monitoring integration, performance optimization, advanced controls