# Recovery Thread Phase 3 - Testing Requirements
**Component:** Monitoring, Control, and Chat Integration  
**Date:** August 31, 2025

---

## 🎯 **Phase 3 Enhancements**
Building on Phase 1 & 2, adding:
- **Advanced trend analysis** with pattern detection
- **Emergency handling** (backlog, cascade, memory, disk)
- **Chat interface integration** with recovery commands
- **Staged alerts** with frequency control
- **Smart auto-remediation** attempts

---

## 📊 **Trend Analysis Tests**

### **Test RT3-1: Failure Pattern Detection**
1. Create failures with patterns:
   - 5 failures at same hour (3pm)
   - 5 failures on same day (Tuesday)
   - 5 large file failures (>50KB)
2. Run `monitor.analyze_failure()` for each
3. Check insights include:
   - "Fails every day at 15:00"
   - "Fails every Tuesday"
   - "Large files failing more frequently"
**Expected:** Pattern detection identifies correlations

### **Test RT3-2: Cascade Precursor Detection**
1. Generate 6 rapid failures of same type within 60 seconds
2. Check `detect_cascade_precursor()` returns warning
3. Verify insight includes "CASCADE RISK"
**Expected:** Early warning before full cascade

### **Test RT3-3: System Correlation Analysis**
1. Simulate high memory usage (mock psutil returns 600MB)
2. Generate failures during high memory
3. Check insights include memory correlation
**Expected:** System state correlations detected

### **Test RT3-4: Analytics File Generation**
1. Process various failures
2. Check `~/.memory_backup/analytics/failure_trends.json`
3. Verify structure:
   - `by_reason` with counts and dates
   - `hotspots` with spike detection
   - `insights_log` with timestamped insights
**Expected:** Passive monitoring file updates correctly

---

## 🚨 **Emergency Handling Tests**

### **Test RT3-5: Backlog Explosion Detection**
1. Create 501 pending files
2. Call `monitor.check_emergency_conditions()`
3. Verify returns backlog_explosion emergency
4. Check recommended action increases batch size
**Expected:** Detects and responds to huge backlogs

### **Test RT3-6: Cascade Failure Handling**
1. Generate 10 consecutive identical failures
2. Check cascade failure detected
3. Verify debug package saved to analytics/
4. Check auto-remediation attempted based on error type
**Expected:** Cascade handled with debug capture and auto-fix attempt

### **Test RT3-7: Memory Pressure Response**
1. Mock recovery using 600MB memory
2. Check memory_pressure emergency triggered
3. Verify suggests throttling OTHER processes (not recovery)
**Expected:** Protects recovery thread during memory pressure

### **Test RT3-8: Staged Disk Alerts**
1. Test disk space at different levels:
   - 45GB free → info alert (once per day)
   - 15GB free → warning alert (once per hour)
   - 4GB free → critical alert (every 10 min)
   - 500MB free → emergency stop
2. Verify alert frequencies respected
3. Check emergency triggers compression
**Expected:** Staged alerts with appropriate frequencies

---

## 💬 **Chat Interface Tests**

### **Test RT3-9: Command Processing**
1. Test all commands:
```python
commands = [
    '/recovery',
    '/recovery status',
    '/recovery status verbose',
    '/recovery force',
    '/recovery failed',
    '/recovery failed network_timeout',
    '/recovery pause 60',
    '/recovery resume',
    '/recovery retry-failed test_123',
    '/recovery clear-old',
    '/recovery trends'
]
```
2. Verify each returns proper response dict
**Expected:** All commands work with correct output format

### **Test RT3-10: Status Display (Both Views)**
1. Call `/recovery status` → basic view
2. Call `/recovery status verbose` → detailed view
3. Verify basic shows:
   - Status line
   - Uptime and success rate
   - Active alerts
4. Verify verbose adds:
   - Performance metrics
   - Trends
   - System state
   - Recommendations
**Expected:** Two-tier status display as requested

### **Test RT3-11: Failed File Management**
1. Create failed files in different categories
2. Test `/recovery failed` → shows summary
3. Test `/recovery failed data_corruption` → shows specific files
4. Test `/recovery retry-failed all` → moves back to pending
**Expected:** Interactive failed file management

### **Test RT3-12: Dashboard Integration**
1. Call `get_status_for_dashboard()`
2. With no issues → "✅ Recovery: Running | 5 pending | 0 failed"
3. With warning → "⚠️ Recovery: High pending count"
4. With critical → "🚨 Recovery: Cascade failure detected"
**Expected:** One-line status for main chat display

---

## 📈 **Trend Analytics Tests**

### **Test RT3-13: Hotspot Detection**
1. Create 15 failures of same type
2. Create 5 recent failures (last hour)
3. Check hotspots detected in analytics
4. Verify "recent_spike" flagged
**Expected:** Identifies failure hotspots and spikes

### **Test RT3-14: Recommendation Generation**
1. Create various failure patterns
2. Check recommendations generated:
   - Cascade → "Consider pausing and investigating"
   - Memory correlation → "Free up memory"
   - Periodic → "Check scheduled maintenance"
**Expected:** Actionable recommendations based on patterns

### **Test RT3-15: Auto-Remediation Attempts**
1. Create cascade with "connection_refused" error
2. Verify attempts health check to episodic memory
3. Create cascade with "timeout" error
4. Verify suggests increasing timeouts
**Expected:** Smart remediation based on error type

---

## 🔄 **Integration Tests**

### **Test RT3-16: Full Emergency Response**
1. Fill disk to <1GB
2. Verify:
   - Emergency alert fires
   - Recovery stops
   - Compression attempted
   - Alert shows in chat
**Expected:** Complete emergency response workflow

### **Test RT3-17: Alert Frequency Control**
1. Trigger same alert multiple times rapidly
2. Verify respects frequency limits:
   - Info: Max once per day
   - Warning: Max once per hour
   - Critical: Max every 10 minutes
**Expected:** No alert spam

### **Test RT3-18: Performance Under Monitoring**
1. Run recovery with monitoring for 5+ minutes
2. Process mix of success/failure
3. Verify:
   - Trend analysis doesn't slow recovery
   - Memory usage stable
   - Analytics file size reasonable
**Expected:** Monitoring doesn't impact performance

---

## 🎮 **Manual Control Tests**

### **Test RT3-19: Force Recovery with Monitoring**
1. Use `/recovery force` during normal operation
2. Verify immediate execution
3. Check monitoring captures forced recovery
**Expected:** Manual control integrates with monitoring

### **Test RT3-20: Pause/Resume with State Preservation**
1. Pause recovery during active processing
2. Check state preserved
3. Resume and verify continues correctly
4. Check pause shown in status
**Expected:** Clean pause/resume with monitoring awareness

---

## ✅ **Success Criteria for Phase 3**

**Trend Analysis:**
- ✅ Detects periodic, size, and system correlations
- ✅ Identifies cascade precursors before failure
- ✅ Generates actionable insights and recommendations
- ✅ Passive analytics file for historical review

**Emergency Handling:**
- ✅ Handles 4 emergency types appropriately
- ✅ Auto-remediation attempts for common issues
- ✅ Staged disk alerts with frequency control
- ✅ Debug packages for cascade analysis

**Chat Integration:**
- ✅ All recovery commands functional
- ✅ Both basic and verbose status views
- ✅ Dashboard one-line status
- ✅ Interactive failed file management

**Monitoring:**
- ✅ No performance impact on recovery
- ✅ Alert frequency limits prevent spam
- ✅ Comprehensive status reporting
- ✅ Smart recommendations based on patterns

---

## 🔧 **Manual Testing Commands**

```bash
# 1. Test monitoring initialization
python3 -c "
from recovery_thread import RecoveryThread
from recovery_monitoring import RecoveryMonitor
from emergency_backup import EmergencyBackupSystem

backup = EmergencyBackupSystem()
recovery = RecoveryThread(backup)
monitor = RecoveryMonitor(recovery)

print('Monitor initialized')
print('Status:', monitor.get_comprehensive_status(verbose=True))
"

# 2. Test chat interface
python3 -c "
from recovery_chat_commands import RecoveryChatInterface
# ... initialize recovery and monitor ...
chat = RecoveryChatInterface(recovery, monitor)

# Test commands
print(chat.process_command('/recovery status'))
print(chat.process_command('/recovery trends'))
"

# 3. Simulate cascade failure
# Create 10 identical failures rapidly and check detection

# 4. Test emergency response
# Reduce disk space and verify alerts
```

---

## 🚀 **Phase 3 Completion = Chunk 2 DONE!**

With Phase 3 complete:
- ✅ Recovery thread has full production capabilities
- ✅ Self-healing through pattern detection
- ✅ User-friendly chat interface
- ✅ Comprehensive monitoring without performance impact

**Ready for Chunk 3:** Integration with rich_chat.py!