# Chunk 2: Recovery Thread - Implementation Outline
**Component:** Background recovery system for emergency backup
**Date:** August 31, 2025

---

## 🎯 **Core Objective**
Implement a background daemon thread that automatically flushes pending exchanges to episodic memory when it becomes available again after failures.

---

## 📋 **Implementation Components**

### **Component 1: RecoveryThread Class**
```python
class RecoveryThread:
    """
    Background daemon thread for automatic recovery
    Runs independently of main chat flow
    """
    
    def __init__(self, backup_system, interval=30):
        self.backup_system = backup_system  # Reference to EmergencyBackupSystem
        self.interval = interval             # Base recovery interval (seconds)
        self.thread = None                  # Threading.Thread object
        self.stop_event = threading.Event() # Clean shutdown signal
        self.paused_until = None            # Manual pause timestamp
        
        # Health tracking
        self.last_health_check = None
        self.last_failure_time = None
        self.backoff_seconds = 30
        
        # Recovery tracking
        self.sync_attempts = {}           # {file_path: [attempt_timestamps]}
        self.failure_reasons = {}         # {file_path: error_reason}
        self.success_count_last_hour = 0
        self.failure_count_last_hour = 0
        self.current_processing_file = None
```

### **Component 2: Health Check with Smart Backoff**
```python
def is_episodic_memory_healthy(self) -> Dict:
    """
    Check episodic memory health with exponential backoff
    Returns detailed health status for monitoring
    """
    # Implementation:
    # 1. Check if we're in backoff period
    # 2. Attempt HTTP health check to localhost:8005/health
    # 3. Update backoff on failure (double up to 5 minutes max)
    # 4. Reset backoff on success
    # 5. Return detailed status dict
```

### **Component 3: Batch Recovery Process**
```python
def recovery_cycle(self):
    """
    One complete recovery attempt cycle
    Processes pending exchanges in batches
    """
    # Implementation:
    # 1. Check if paused or stopped
    # 2. Health check episodic memory
    # 3. Get pending files (oldest first)
    # 4. Process in batches of 5-10
    # 5. Verify successful sync before cleanup
    # 6. Handle failures appropriately
    # 7. Update statistics and status
```

### **Component 4: Failure Management**
```python
def handle_sync_failure(self, file_path, error):
    """
    Smart failure handling with classification
    """
    # Implementation:
    # 1. Classify error type (network, data, auth, etc.)
    # 2. Update attempt counter
    # 3. After 3 attempts, move to failed directory
    # 4. Track failure reasons for analysis
    # 5. Update failure statistics
```

### **Component 5: Data Integrity Verification**
```python
def verify_sync_success(self, exchange_id: str) -> bool:
    """
    Verify exchange was actually archived before cleanup
    Light verification to prevent data loss
    """
    # Implementation:
    # 1. Quick HTTP GET to episodic memory
    # 2. Verify exchange exists with matching ID
    # 3. Return success/failure for cleanup decision
```

### **Component 6: Adaptive Frequency Control**
```python
def calculate_next_interval(self) -> int:
    """
    Adapt recovery frequency based on backlog and success rate
    """
    # Implementation:
    # 1. Check pending queue size
    # 2. Large backlog (50+) → 10 seconds (aggressive)
    # 3. Normal operation → 30 seconds (standard)
    # 4. No backlog → 60 seconds (maintenance)
    # 5. Consider recent failure rate for adjustments
```

### **Component 7: Status and Monitoring**
```python
def get_recovery_status(self) -> Dict:
    """
    Comprehensive status for dashboard and debugging
    """
    return {
        'thread_status': 'running' | 'stopped' | 'paused',
        'episodic_health': {'status': bool, 'last_check': timestamp},
        'queue_info': {'pending': int, 'processing': str, 'failed': int},
        'performance': {
            'successes_last_hour': int,
            'failures_last_hour': int,
            'success_rate': float
        },
        'timing': {
            'next_cycle_in_seconds': int,
            'current_interval': int,
            'backoff_until': timestamp
        }
    }
```

### **Component 8: Manual Control Interface**
```python
def start_recovery_thread(self):
    """Start background recovery (if not already running)"""
    
def stop_recovery_thread(self, timeout=10):
    """Clean shutdown of recovery thread"""
    
def pause_recovery(self, minutes=30):
    """Temporarily pause recovery for maintenance"""
    
def force_recovery_now(self):
    """Manual trigger - bypass normal interval"""
    
def reset_failed_exchanges(self):
    """Move failed exchanges back to pending for retry"""
```

---

## 🔧 **Implementation Phases**

### **Phase 1: Core Threading Infrastructure**
- Basic RecoveryThread class with start/stop
- Simple recovery cycle (no batching yet)
- Health check integration
- Clean shutdown handling

### **Phase 2: Smart Recovery Logic**
- Batch processing implementation
- Failure classification and tracking
- Data integrity verification
- Adaptive frequency calculation

### **Phase 3: Monitoring and Control**
- Comprehensive status reporting
- Manual control commands
- Statistics tracking and performance metrics
- Integration with chat interface alerts

---

## 🎯 **Success Criteria**

### **Reliability:**
- ✅ Recovery thread runs continuously without crashes
- ✅ Clean shutdown when main program exits
- ✅ Zero data loss - all pending exchanges eventually sync or fail safely
- ✅ Handles episodic memory downtime gracefully

### **Performance:**
- ✅ Batch processing prevents overwhelming episodic memory
- ✅ Adaptive frequency reduces CPU usage during quiet periods
- ✅ Backoff prevents spam during extended outages

### **Monitoring:**
- ✅ Clear status reporting for dashboard integration
- ✅ Failure classification helps debug root causes
- ✅ Performance metrics track recovery effectiveness

### **User Experience:**
- ✅ Manual controls work reliably
- ✅ Recovery runs silently in background
- ✅ Alerts only when intervention needed

---

## 📊 **Testing Requirements**

### **Unit Tests:**
- Recovery thread lifecycle (start/stop/pause)
- Health check logic with various failure scenarios
- Batch processing with different queue sizes
- Failure handling for network, data, and auth errors
- Data integrity verification success/failure cases

### **Integration Tests:**
- Full recovery cycle with real episodic memory service
- Extended downtime simulation (hours of outage)
- Large backlog processing (100+ pending exchanges)
- Manual control during active recovery
- Performance under sustained load

### **Failure Tests:**
- Episodic memory service stops during recovery
- Network connectivity issues
- Corrupted pending files
- Resource exhaustion scenarios
- Thread safety under concurrent access

---

## 🔮 **Future Enhancements (Not Chunk 2)**

```python
# TODO: Network status listener for immediate recovery trigger
# TODO: Redis context stream integration for real-time monitoring  
# TODO: Soft emergency alerts for debug mode
# TODO: Compression of failed exchanges for long-term storage
# TODO: Machine learning for failure prediction and prevention
```

---

## 🛠️ **Implementation Order**

1. **RecoveryThread class foundation** (basic thread management)
2. **Health check with backoff** (smart episodic memory monitoring)
3. **Simple recovery cycle** (one file at a time processing)
4. **Batch processing upgrade** (5-10 files per cycle)
5. **Failure management** (3-strike rule, failed directory)
6. **Data verification** (integrity checks before cleanup)
7. **Adaptive frequency** (smart interval calculation)
8. **Status reporting** (comprehensive monitoring data)
9. **Manual controls** (user commands for pause/resume/force)
10. **Integration testing** (full system validation)

---

**Ready to start chiseling through Phase 1: Core Threading Infrastructure?**