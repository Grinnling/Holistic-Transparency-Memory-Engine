# FRIDAY DEMO - EPISODIC MEMORY TEST SHEET
**Created:** 2025-09-30
**Purpose:** Manual testing checklist for episodic memory integration
**Target:** Demo-ready functionality verification

---

## PRE-TEST SETUP CHECKLIST

### Environment Preparation
- [ ] **Working Directory:** `/home/grinnling/Development/CODE_IMPLEMENTATION`
- [ ] **LLM Service Running:** LM Studio with model loaded (or TGI/Ollama)
- [ ] **Episodic Memory Service:** Running and healthy
- [ ] **Working Memory Service:** Running and healthy
- [ ] **Curator Service:** Running (optional but recommended)
- [ ] **API Server:** `python3 api_server_bridge.py` running on port 8000
- [ ] **React UI:** `npm run dev` in separate terminal, accessible at http://localhost:3000

### Quick Health Check
```bash
# Check all services are up
curl http://localhost:8000/health
# Should return JSON with service status

# Check memory stats endpoint exists
curl http://localhost:8000/memory/stats
# Should return episodic_count, working_memory_count, conversation_id

# CRITICAL: Verify database is NOT in /tmp (permanent storage)
curl -s http://localhost:8005/health | grep database_path
# Should show: /home/grinnling/Development/CODE_IMPLEMENTATION/data/episodic_memory.db
# ❌ FAIL if shows: /tmp/episodic_memory.db (memories will be lost!)
```

**If any service is down:** Use `/start-services` in rich_chat.py or start manually

---

## TEST 1: CLEAN SLATE - Starting Fresh
**Priority:** MEDIUM (Optional for demo - can test with existing memories)
**Purpose:** Test with clean state if desired

### Steps:
1. **Option A: Test with existing memories (Recommended)**
   - Skip clean slate
   - Use whatever memories are already in the system
   - Tests that retrieval works with real data

2. **Option B: Fresh start (if needed)**
   - Contact operator for manual DB reset
   - Requires deliberate action to prevent accidents
   - **Note:** We intentionally removed deletion capability - memories are precious!
   - **Post-demo:** Snapshot-based barriers will enable safe "reset" without data loss

3. **Verify Current Stats:**
   ```bash
   curl http://localhost:8000/memory/stats
   ```
   **Expected:** Shows current episodic memory count

3. **Check React UI:**
   - Open http://localhost:3000
   - Click "Status" tab in sidebar
   - Scroll to "Memory System" section

   **Expected:**
   - Episodic Memories: 0
   - Working Memory: 0 messages (or however many restored)
   - Archival Healthy: ✅ (green indicator)

### ✅ Pass Criteria:
- Memory cleared successfully
- Stats reflect 0 episodic memories
- UI updates within 5 seconds

### ❌ Failure Scenarios:
- Can't find DB file → Check episodic service logs for actual DB path
- Stats don't update → Check episodic service `/stats` endpoint format
- UI doesn't refresh → Check browser console for errors

---

## TEST 2: MEMORY ARCHIVAL - Store Personal Info
**Priority:** CRITICAL
**Purpose:** Verify memories are being saved to episodic storage

### Steps:
1. **Send Test Messages via React UI:**
   - Message 1: "My favorite color is blue"
   - Wait for response
   - Message 2: "I work as a software engineer"
   - Wait for response
   - Message 3: "I have a dog named Max"
   - Wait for response

2. **Check Immediate Stats:**
   ```bash
   curl http://localhost:8000/memory/stats
   ```
   **Expected:** `episodic_count: 3` (or at least 2-3)

3. **Check React UI Memory Stats:**
   - Status tab → Memory System section

   **Expected:**
   - Episodic Memories: 3
   - Working Memory: 6 messages (3 user + 3 assistant)
   - Archival Healthy: ✅ green

### ✅ Pass Criteria:
- All 3 messages archived successfully
- Stats endpoint reflects new memories
- UI updates automatically (within 5 seconds)
- No archival failures shown

### ❌ Failure Scenarios:
- Episodic count stays at 0 → Check:
  - `memory_handler.archive_to_episodic_memory()` being called
  - Episodic service `/archive` endpoint working
  - Check API logs for errors
- Archival Healthy shows red → Check error panel in React UI
- Working memory updates but episodic doesn't → Archive is failing silently

### Debug Commands:
```bash
# Check episodic service directly
curl http://localhost:YOUR_EPISODIC_PORT/conversations
# Should show your conversation with 3 exchanges

# Check working memory
curl http://localhost:8000/history
# Should show 6 messages (3 exchanges)
```

---

## TEST 3: MEMORY SEARCH - Direct API Test
**Priority:** HIGH
**Purpose:** Verify semantic search returns relevant memories

### Steps:
1. **Search for "color":**
   ```bash
   curl "http://localhost:8000/memory/search?query=color"
   ```
   **Expected:**
   - JSON response with `results` array
   - At least 1 result mentioning "blue" or "favorite color"
   - `count: 1` or more

2. **Search for "work":**
   ```bash
   curl "http://localhost:8000/memory/search?query=work"
   ```
   **Expected:**
   - Results mentioning "software engineer"
   - Relevant context included

3. **Search for "dog":**
   ```bash
   curl "http://localhost:8000/memory/search?query=dog"
   ```
   **Expected:**
   - Results mentioning "Max" or "dog"

### ✅ Pass Criteria:
- All searches return relevant results
- Results include both user input and assistant response
- Response format is valid JSON

### ❌ Failure Scenarios:
- Empty results → Check episodic service `/search` endpoint
- 404 error → API endpoint not registered properly
- Wrong results → Semantic search quality issue (episodic service problem)

---

## TEST 4: MEMORY RETRIEVAL IN CHAT - The Big One! 🎯
**Priority:** CRITICAL (MAIN DEMO FEATURE)
**Purpose:** Prove episodic memory enhances LLM responses

### Steps:
1. **Ask about favorite color:**
   - In React UI chat, type: "What's my favorite color?"
   - Send message

   **Expected:**
   - LLM response mentions "blue"
   - Response shows understanding of previous conversation
   - Example: "Your favorite color is blue" or "You mentioned earlier that your favorite color is blue"

2. **Ask about job:**
   - Type: "What do I do for work?"
   - Send message

   **Expected:**
   - LLM mentions "software engineer"
   - Shows it retrieved from memory

3. **Ask about pet:**
   - Type: "What's my dog's name?"
   - Send message

   **Expected:**
   - LLM says "Max"
   - References earlier conversation

### Debug This Test:
If LLM doesn't recall, check:

```bash
# 1. Check if retrieval is happening (look for this in API logs)
# You should see: "Retrieved X relevant memories" in debug output

# 2. Manually verify search works
curl "http://localhost:8000/memory/search?query=What's my favorite color?"

# 3. Check LLM is getting memory context
# Enable debug mode: python3 rich_chat.py --debug
# Send "What's my favorite color?"
# Look for "Memory X from [timestamp]" in LLM prompt
```

### ✅ Pass Criteria:
- LLM correctly recalls all 3 facts
- Responses feel natural (not robotic)
- No errors in UI or console

### ❌ Failure Scenarios:
- LLM says "I don't know" → Memory retrieval failed, check:
  - `retrieve_relevant_memories()` returning empty list
  - Episodic service `/search` endpoint failing
  - LLM prompt not including memory context

- LLM recalls wrong info → Semantic search returned wrong memories

- Errors in UI → Check browser console and API logs

---

## TEST 5: PERSISTENCE ACROSS RESTARTS - The Clincher! 🔄
**Priority:** CRITICAL
**Purpose:** Prove episodic memory survives server restarts (working memory doesn't)

### Steps:
1. **Check Current State:**
   ```bash
   curl http://localhost:8000/memory/stats
   ```
   **Record:** `episodic_count: X, working_memory_count: Y`

2. **STOP API Server:**
   - Press `Ctrl+C` in terminal running `api_server_bridge.py`
   - Wait for clean shutdown

3. **START API Server:**
   ```bash
   python3 api_server_bridge.py
   ```
   - Wait for "Memory Chat API Server starting..." message

4. **Check Stats After Restart:**
   ```bash
   curl http://localhost:8000/memory/stats
   ```

   **Expected:**
   - `episodic_count: X` (SAME as before restart) ✅
   - `working_memory_count: 0` (or very low - working memory cleared) ✅
   - `conversation_id: <new_uuid>` (different from before)

5. **Test Recall Still Works:**
   - In React UI: "What's my favorite color?"

   **Expected:**
   - LLM STILL recalls "blue" from episodic memory
   - Even though working memory was cleared!

### ✅ Pass Criteria:
- Episodic count unchanged after restart
- Working memory reset to 0
- LLM can still recall facts from episodic memory
- **This proves long-term memory works!**

### ❌ Failure Scenarios:
- Episodic count = 0 after restart → Episodic service not persisting
- LLM can't recall after restart → Memory retrieval broken
- Working memory still full → restore_conversation_history() loading too much

---

## TEST 6: UI INTEGRATION - Polish Check
**Priority:** MEDIUM
**Purpose:** Verify UI updates and displays correctly

### Steps:
1. **Memory Stats Display:**
   - Open React UI at http://localhost:3000
   - Click "Status" tab
   - Observe "Memory System" section

   **Expected:**
   - Shows episodic count
   - Shows working memory count
   - Shows archival health status
   - Updates every 5 seconds (watch the numbers)

2. **Conversation History Display:**
   - Check main chat area
   - Scroll up to see history

   **Expected:**
   - Past messages loaded on page load
   - User messages on left (blue)
   - Assistant messages on right (green)
   - Timestamps visible

3. **Loading States:**
   - Send a message

   **Expected:**
   - Input shows "Processing..."
   - Send button shows "Sending..."
   - Button disabled while processing

4. **Service Status Panel:**
   - Check all services show green dots
   - Memory System shows healthy status

### ✅ Pass Criteria:
- All UI elements display correctly
- Auto-refresh works (5s interval)
- Loading states prevent double-send

### ❌ Failure Scenarios:
- Stats don't update → Check browser console for fetch errors
- History doesn't load → Check `/history` endpoint
- No loading indicator → Missing state updates

---

## TEST 7: ERROR HANDLING - Break Things Intentionally
**Priority:** MEDIUM
**Purpose:** Verify graceful degradation

### Steps:
1. **Stop Episodic Service:**
   - Intentionally stop the episodic memory service
   - Send a chat message: "Testing without episodic memory"

   **Expected:**
   - Chat still works!
   - Message sent and response received
   - Memory stats show error or 0 count
   - Archival Healthy: ❌ red (after 3 failures)
   - No crash, no hang

2. **Check Error Panel:**
   - Click "Errors" tab in React UI

   **Expected:**
   - Shows episodic memory connection errors
   - Error severity indicated
   - Errors don't prevent chat

3. **Restart Episodic Service:**
   - Start episodic service again
   - Send another message

   **Expected:**
   - System recovers automatically
   - Archival starts working again
   - Stats update correctly

### ✅ Pass Criteria:
- System doesn't crash when episodic service is down
- Errors logged and displayed
- Automatic recovery when service comes back

### ❌ Failure Scenarios:
- Chat hangs → Timeout not working (should be 5s max)
- No error indication → Error handling not reporting properly
- Doesn't recover → Need to restart API server (not acceptable)

---

## TEST 8: PERFORMANCE CHECK - Speed Test
**Priority:** LOW
**Purpose:** Ensure memory retrieval doesn't slow things down

### Steps:
1. **Measure Response Time:**
   - Send message: "Hello"
   - Note response time

2. **Add 20 more memories:**
   - Send 10 unique messages with facts
   - Build up episodic memory

3. **Measure Response Time Again:**
   - Send message: "Hello again"
   - Compare to earlier time

   **Expected:**
   - Response time similar (within 1-2 seconds)
   - No noticeable degradation

### ✅ Pass Criteria:
- Memory retrieval adds < 500ms to response time
- No timeout errors
- UI feels responsive

### ❌ Failure Scenarios:
- Slow responses → Episodic service search is slow
- Timeouts → Reduce top_k from 5 to 3 memories

---

## TEST 9: ERROR REPORTING VALIDATION - Critical for AI Debugging
**Priority:** HIGH
**Purpose:** Verify all service failures are visible and actionable in error panel

### Why This Test Matters:
When the AI (Claude) encounters issues, it needs clear visibility into what failed and why. Silent failures or missing error details create blind spots that prevent effective troubleshooting. This test ensures every failure mode surfaces properly.

### Test Each Service Independently:

#### 1. **Episodic Memory Service Errors**
```bash
# Stop episodic service
kill $(lsof -t -i:8005)

# Trigger archival through chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message during episodic failure"}'

# Check error panel in React UI
```

**Expected in Error Panel:**
- Error message: "Episodic archival failed: Connection refused" (or similar)
- Category: EPISODIC_MEMORY
- Severity: MEDIUM_DEGRADE
- Context: "Falling back to backup system"
- Operation: "archive_to_episodic_fallback"

**Pass Criteria:**
- ✅ Error appears in panel within 5 seconds
- ✅ Error message is clear and actionable
- ✅ Shows what operation failed and why
- ✅ Error persists until acknowledged

#### 2. **Working Memory Service Errors**
```bash
# Stop working memory service
kill $(lsof -t -i:5001)

# Trigger operation that needs working memory
curl http://localhost:8000/history
```

**Expected:**
- Clear error about working memory unavailable
- Appropriate severity level
- Graceful degradation (system doesn't crash)

#### 3. **Curator Service Errors**
```bash
# Stop curator service
kill $(lsof -t -i:8004)

# Send message (curator validates responses)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test during curator failure"}'
```

**Expected:**
- Error about curator validation failure
- Chat still works (curator is optional)
- Warning level error, not critical

#### 4. **LLM Service Errors**
```bash
# Stop LM Studio or disconnect LLM

# Try to send message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test during LLM failure"}'
```

**Expected:**
- Critical error about LLM unavailable
- Clear message to user
- System doesn't hang

### Special Error Cases to Test:

#### A. **HTTP 400 Errors (Data Format Issues)**
This was the bug we just fixed - test it still reports properly:
```bash
# This should now work, but if we break the format again, error should be clear
# The fix: coordinator wraps data in conversation_data
# Test by temporarily removing the wrapper and checking error visibility
```

**Expected:**
- Error shows HTTP status code (400)
- Error shows actual message from service ("conversation_data is required")
- Not just "HTTP 400" - needs details!

#### B. **Timeout Errors**
```bash
# Simulate slow episodic service (if possible)
# Or set very short timeout in coordinator
```

**Expected:**
- Error: "Request timeout after Xs"
- Falls back to backup gracefully
- Error panel shows timeout occurred

#### C. **Network Connection Errors**
```bash
# Configure wrong port for service
# Or block network access temporarily
```

**Expected:**
- Error: "Connection refused" or "Connection failed"
- Not generic "Archive failed"

#### D. **Malformed Response Errors**
```bash
# Service returns non-JSON or unexpected format
```

**Expected:**
- Error explaining what went wrong with parsing
- Shows what was expected vs what was received

### Error Panel UI Validation:

**Check error panel displays:**
1. ✅ Timestamp of error
2. ✅ Error severity indicator (color-coded)
3. ✅ Service/category that failed
4. ✅ Clear error message
5. ✅ Operation context (what was being attempted)
6. ✅ Acknowledge button works
7. ✅ Errors don't disappear until acknowledged
8. ✅ Multiple errors can stack (show all recent failures)

### Error Routing Validation:

**Verify errors go to correct categories:**
- `ErrorCategory.EPISODIC_MEMORY` → Archival, retrieval failures
- `ErrorCategory.BACKUP_SYSTEM` → Recovery thread, backup queue
- `ErrorCategory.WORKING_MEMORY` → Working memory service issues
- `ErrorCategory.LLM` → LLM connection, generation failures
- `ErrorCategory.CURATOR` → Validation service issues

### Recovery Validation:

**After fixing each service:**
1. Restart the service
2. Send another message
3. Verify error clears or new success message appears
4. Verify system recovers automatically (no API restart needed)

### ✅ Pass Criteria Summary:
- All service failures surface to error panel
- Error messages include HTTP codes and details
- Errors show operation context (what was being attempted)
- Errors persist until acknowledged
- System degrades gracefully (doesn't crash)
- Recovery is automatic when service comes back

### ❌ Failure Scenarios:
- Error never appears in panel (silent failure)
- Error message is generic ("Archive failed" with no details)
- Error disappears before user can see it
- Wrong severity level (critical marked as warning)
- System hangs or crashes instead of showing error
- No indication of which service failed

### Debug Commands:
```bash
# Check error handler logs
tail -f /tmp/api_server.log | grep -i error

# Check error endpoint directly
curl http://localhost:8000/errors | python3 -m json.tool

# Check service health
curl http://localhost:8000/services/dashboard

# Trigger error acknowledgment
curl -X POST http://localhost:8000/errors/{error_id}/acknowledge

# Clear all errors
curl -X POST http://localhost:8000/errors/clear
```

### Why This Test Is Critical:
**For the AI (Claude):** Without clear error visibility, I can't help you debug issues. I need to see:
- WHAT failed (which service)
- WHY it failed (error details)
- WHERE it failed (operation context)

**For the human:** You need to know when the memory system is degraded so you can fix it before data loss occurs.

**For the demo:** Showing robust error handling demonstrates production-readiness, not just happy-path functionality.

---

## DEMO REHEARSAL CHECKLIST (DO THIS BEFORE FRIDAY!)

### Pre-Demo Setup (30 minutes before):
- [ ] **Start all services** in this order:
  1. LM Studio (load model, wait for ready)
  2. Episodic Memory Service
  3. Working Memory Service
  4. Curator Service (optional)
  5. API Server (`python3 api_server_bridge.py`)
  6. React UI (`npm run dev`)

- [ ] **Clear all memories:**
  ```bash
  curl -X POST http://localhost:8000/memory/clear
  ```

- [ ] **Verify health:**
  ```bash
  curl http://localhost:8000/health
  ```
  All services should be "healthy"

- [ ] **Test one message:**
  - Open React UI
  - Send "Hello, this is a test"
  - Verify response received
  - Check memory stats updated

### Demo Script (5 minutes):

**Act 1 - Store Personal Info (1 min):**
```
User: "My favorite color is teal"
User: "I work as a machine learning engineer"
User: "I'm learning about memory systems"
```

**Show:** Memory stats updating in UI (3 episodic memories)

**Act 2 - Immediate Recall (1 min):**
```
User: "What's my favorite color?"
User: "What do I do for work?"
```

**Show:** LLM recalling correctly from episodic memory

**Act 3 - The Big Demo - Restart Test (2 min):**
```
1. Show memory stats: "3 episodic, 6 working"
2. Stop API server (Ctrl+C)
3. Restart API server
4. Show memory stats: "3 episodic, 0 working"
   ^ THIS IS THE MAGIC MOMENT
5. Ask: "What's my favorite color?"
6. LLM recalls "teal" even though working memory cleared!
```

**Narration:**
"Even though we restarted the server and working memory was cleared, the episodic memory system retrieved the relevant context and the LLM still knows my favorite color. This is true long-term memory!"

**Act 4 - Show UI Features (1 min):**
```
- Memory stats panel
- Service health indicators
- Conversation history
- Error panel (if any)
```

### Demo Don'ts:
- ❌ Don't restart LLM during demo (takes too long)
- ❌ Don't ask super complex questions (keep it simple)
- ❌ Don't demo with broken services (test beforehand!)
- ❌ Don't skip the restart test (it's the coolest part!)

---

## TROUBLESHOOTING GUIDE

### Problem: Episodic count stays at 0
**Diagnosis:**
```bash
# Check if archive endpoint works
curl -X POST http://localhost:YOUR_EPISODIC_PORT/archive \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "test", "exchanges": [{"user_input": "test", "assistant_response": "test"}]}'
```

**Fix Options:**
1. Check episodic service is running: `ps aux | grep episodic`
2. Check episodic service logs for errors
3. Verify endpoint URL in `service_manager.py`
4. Test with curl directly to isolate issue

### Problem: Memory search returns empty
**Diagnosis:**
```bash
# Test search endpoint directly
curl -X POST http://localhost:YOUR_EPISODIC_PORT/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

**Fix Options:**
1. Check episodic service `/search` endpoint exists
2. Verify request format matches what service expects
3. Check if memories are actually stored (query `/conversations`)
4. May need to adjust MemoryHandler.retrieve_relevant_memories() format

### Problem: LLM doesn't recall memories
**Diagnosis:**
```bash
# Enable debug mode
python3 rich_chat.py --debug

# Send a message and look for:
# - "Retrieved X relevant memories"
# - "Memory context parts:" followed by memory snippets
# - LLM prompt should include "[Memory 1 from timestamp]"
```

**Fix Options:**
1. Verify retrieval is happening (check debug logs)
2. Check memory context is in LLM prompt
3. Try more obvious question: "What did I just tell you about my favorite color?"
4. Check LLM model is capable of using context (some models ignore it)

### Problem: UI doesn't update
**Check:**
```bash
# Browser console (F12)
# Look for fetch errors or CORS issues

# Check React dev server logs
# Look for build errors or warnings
```

**Fix Options:**
1. Hard refresh browser (Ctrl+Shift+R)
2. Check CORS settings in api_server_bridge.py
3. Verify API_BASE in App.tsx matches server port
4. Check network tab in browser dev tools

### Problem: Service won't start
**Check:**
```bash
# Port already in use?
lsof -i :8000  # For API server
lsof -i :3000  # For React

# Kill if needed
kill -9 <PID>
```

---

## SUCCESS CRITERIA SUMMARY

### Must Have (Critical for Demo):
- ✅ Memories stored to episodic (TEST 2)
- ✅ Memories retrieved in chat (TEST 4)
- ✅ Persistence across restarts (TEST 5)
- ✅ UI displays memory stats (TEST 6)

### Should Have (Nice for Demo):
- ✅ Memory search API works (TEST 3)
- ✅ Graceful error handling (TEST 7)
- ✅ UI looks polished (TEST 6)

### Could Have (Not Critical):
- ⚠️ Performance optimizations (TEST 8)
- ⚠️ Advanced search features
- ⚠️ Memory visualization

---

## POST-TEST NOTES SECTION

**Date Tested:** _________________
**Tester:** _________________

**Passing Tests:**
- [ ] TEST 1 - Clean Slate
- [ ] TEST 2 - Memory Archival
- [ ] TEST 3 - Memory Search
- [ ] TEST 4 - Memory Retrieval in Chat
- [ ] TEST 5 - Persistence Across Restarts
- [ ] TEST 6 - UI Integration
- [ ] TEST 7 - Error Handling
- [ ] TEST 8 - Performance

**Issues Found:**

1. _____________________________________________
   - Severity: [ ] Critical [ ] High [ ] Medium [ ] Low
   - Workaround: _________________________________

2. _____________________________________________
   - Severity: [ ] Critical [ ] High [ ] Medium [ ] Low
   - Workaround: _________________________________

**Notes for Demo:**
_____________________________________________________
_____________________________________________________
_____________________________________________________

**Demo Ready?** [ ] YES [ ] NO [ ] NEEDS WORK

---

## QUICK REFERENCE - Essential Commands

```bash
# Start API server
cd /home/grinnling/Development/CODE_IMPLEMENTATION
python3 api_server_bridge.py

# Start React UI (separate terminal)
cd /home/grinnling/Development/CODE_IMPLEMENTATION
npm run dev

# Clear memories
curl -X POST http://localhost:8000/memory/clear

# Check stats
curl http://localhost:8000/memory/stats

# Search memories
curl "http://localhost:8000/memory/search?query=YOUR_QUERY"

# Check health
curl http://localhost:8000/health

# Debug mode chat
python3 rich_chat.py --debug
```

---

**Remember:** The goal is to demonstrate **EPISODIC MEMORY THAT PERSISTS ACROSS RESTARTS**. That's the killer feature. Everything else is supporting cast.

**Good luck with testing! 🚀**
