# Recovery Thread Phase 1 - Testing Requirements
**Component:** Core Threading Infrastructure  
**Date:** August 31, 2025

---

## 🎯 **Phase 1 Scope**
Basic RecoveryThread class with:
- Thread lifecycle management (start/stop/pause)
- Health checking with exponential backoff
- Simple recovery cycle (one file at a time)
- Status reporting and manual controls

---

## 🧪 **Core Threading Tests**

### **Test RT1: Thread Lifecycle Management**
1. Create RecoveryThread instance:
```python
from recovery_thread import RecoveryThread
from emergency_backup import EmergencyBackupSystem

backup = EmergencyBackupSystem()
recovery = RecoveryThread(backup, interval=5)  # Fast for testing
```
2. Check initial state: `recovery.get_recovery_status()`
3. Start thread: `recovery.start_recovery_thread()`
4. Verify running: `status['thread_status'] == 'running'`
5. Stop thread: `recovery.stop_recovery_thread()`
6. Verify stopped: `status['thread_status'] == 'stopped'`
**Expected:** Clean start/stop cycle, daemon thread dies with main program

### **Test RT2: Duplicate Start Protection**
1. Start recovery thread
2. Try to start again: `recovery.start_recovery_thread()`
3. Should return `False` and log warning
4. Verify only one thread running
**Expected:** Prevents multiple recovery threads

### **Test RT3: Pause/Resume Functionality**
1. Start recovery thread
2. Pause for 1 minute: `recovery.pause_recovery(minutes=1)`
3. Check status: `is_paused` should be `True`
4. Resume manually: `recovery.resume_recovery()`
5. Check status: `is_paused` should be `False`
**Expected:** Recovery respects pause state, auto-resumes after timeout

---

## 🏥 **Health Check Tests**

### **Test RT4: Health Check with Episodic Memory Up**
1. Start episodic memory service (port 8005)
2. Call `recovery._check_episodic_health()`
3. Verify returns:
   - `'healthy': True`
   - `'reason': 'service_responding'`
   - Response time in milliseconds
**Expected:** Detects healthy service correctly

### **Test RT5: Health Check with Episodic Memory Down**
1. Stop episodic memory service
2. Call `recovery._check_episodic_health()`
3. Verify returns:
   - `'healthy': False`  
   - `'reason': 'connection_failed: ...'`
   - `'next_check_in'`: backoff seconds
**Expected:** Handles service downtime gracefully

### **Test RT6: Exponential Backoff**
1. Stop episodic memory service
2. Call health check multiple times
3. Verify backoff increases: 30s → 60s → 120s → 240s → 300s (max)
4. Start episodic memory service
5. Call health check once more
6. Verify backoff resets to 30s
**Expected:** Smart backoff prevents spam, resets on recovery

---

## 🔄 **Recovery Cycle Tests**

### **Test RT7: Empty Queue Handling**
1. Ensure pending directory is empty
2. Call `recovery._recovery_cycle()`
3. Verify no errors, quick completion
4. Check logs for "No pending exchanges" message
**Expected:** Handles empty queue gracefully

### **Test RT8: Single File Processing Success**
1. Create test pending file:
```json
{
  "exchange_id": "test_123",
  "user": "test question",
  "assistant": "test response",
  "conversation_id": "test_conv"
}
```
2. Place in `~/.memory_backup/pending/test_123.json`
3. Start episodic memory service
4. Call `recovery._recovery_cycle()`
5. Verify file removed from pending
6. Check episodic memory received the data
**Expected:** Successful processing removes file

### **Test RT9: Single File Processing Failure**
1. Create test pending file (same as RT8)
2. Stop episodic memory service
3. Call `recovery._recovery_cycle()`
4. Verify file remains in pending
5. Check failure tracking in `recovery.failure_reasons`
**Expected:** Failure leaves file for retry, tracks error

---

## 📊 **Status Reporting Tests**

### **Test RT10: Comprehensive Status**
1. Start recovery thread with some test data
2. Get status: `status = recovery.get_recovery_status()`
3. Verify all required fields present:
   - `thread_status`, `is_paused`, `episodic_health`
   - `queue_info`, `performance`, `timing`
4. Verify data types and reasonable values
**Expected:** Complete status information for monitoring

### **Test RT11: Performance Tracking**
1. Process several files (success and failure mix)
2. Check performance metrics:
   - `total_processed`, `total_succeeded`, `total_failed`
   - `success_rate` calculation accuracy
   - `uptime_seconds` increases over time
**Expected:** Accurate performance statistics

---

## 🎛️ **Manual Control Tests**

### **Test RT12: Force Recovery**
1. Create pending files
2. Start recovery thread with long interval (60s)
3. Call `recovery.force_recovery_now()`
4. Verify immediate processing without waiting for interval
5. Check return data shows processed count
**Expected:** Manual trigger bypasses normal timing

### **Test RT13: Adaptive Interval**
1. Test with empty queue: `_calculate_next_interval()` → 60s
2. Test with normal queue (10 files): → 30s (base interval)
3. Test with large queue (60 files): → 10s
**Expected:** Interval adapts to workload

---

## 🚨 **Error Handling Tests**

### **Test RT14: Corrupted Pending File**
1. Create invalid JSON in pending directory
2. Run recovery cycle
3. Verify thread doesn't crash
4. Check error logged appropriately
5. File should be tracked in failure reasons
**Expected:** Graceful error handling, no crashes

### **Test RT15: Thread Safety**
1. Start recovery thread
2. Rapidly call multiple manual controls:
   - `force_recovery_now()`
   - `pause_recovery()`
   - `get_recovery_status()`
3. Verify no race conditions or crashes
**Expected:** Thread-safe operation under concurrent access

---

## 📝 **Integration Tests**

### **Test RT16: Integration with EmergencyBackupSystem**
1. Create real EmergencyBackupSystem instance
2. Initialize RecoveryThread with it
3. Create pending files using backup system
4. Start recovery and verify integration works
**Expected:** Seamless integration, uses correct paths

### **Test RT17: Extended Operation**
1. Run recovery thread for 2+ minutes
2. Process mix of successful and failed exchanges
3. Monitor memory usage, CPU usage
4. Verify no resource leaks
**Expected:** Stable long-running operation

---

## ✅ **Success Criteria for Phase 1**

**Core Functionality:**
- ✅ Thread starts, runs, and stops cleanly
- ✅ Pause/resume works correctly
- ✅ Health checks with smart backoff
- ✅ Processes pending files one at a time
- ✅ Tracks failures and statistics

**Error Handling:**
- ✅ Handles service outages gracefully
- ✅ Corrupted files don't crash thread
- ✅ Exponential backoff prevents spam
- ✅ Thread-safe operation

**Monitoring:**
- ✅ Comprehensive status reporting
- ✅ Performance statistics tracking
- ✅ Manual control commands work

---

## 🔧 **Manual Testing Commands**

```bash
# 1. Test basic functionality
python3 recovery_thread.py

# 2. Test with real backup system
python3 -c "
from recovery_thread import RecoveryThread
from emergency_backup import EmergencyBackupSystem
backup = EmergencyBackupSystem()
recovery = RecoveryThread(backup, interval=10)
print('Starting recovery...')
recovery.start_recovery_thread()
import time; time.sleep(30)
print('Status:', recovery.get_recovery_status())
recovery.stop_recovery_thread()
print('Stopped cleanly')
"

# 3. Test episodic memory health check
# Start episodic memory service first
python3 -c "
from recovery_thread import RecoveryThread
from emergency_backup import EmergencyBackupSystem
backup = EmergencyBackupSystem()
recovery = RecoveryThread(backup)
print('Health check:', recovery._check_episodic_health())
"
```

---

## 🔄 **Next: Phase 2 Preparation**

Once Phase 1 tests pass:
- ✅ Basic threading infrastructure solid
- ✅ Health checking and backoff working  
- ✅ Simple recovery cycle functional
- **Ready for Phase 2:** Batch processing, failure management, data verification

**Phase 2 will add:**
- Batch processing (5-10 files per cycle)
- 3-strike failure rule with failed directory
- Data integrity verification
- Advanced failure classification