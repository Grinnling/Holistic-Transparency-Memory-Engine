# Refactor Test Sheet - Phase 3: Command Handler
**Test Date:** October 5, 2025
**What Changed:** Extracted command routing from rich_chat.py to command_handler.py
**Lines Removed:** 82 lines from rich_chat.py (1517 → 1435)
**New File:** command_handler.py (338 lines)

---

## 🎯 What We're Testing

We moved ALL command routing logic to CommandHandler:
- Command validation (is `/foo` a valid command?)
- Command parsing (extract `/search` from `/search hello world`)
- Argument extraction (extract `hello world` from `/search hello world`)
- Command routing (call the right method based on command)

**Risk Areas:**
- Commands might not route correctly
- Arguments might not be extracted properly
- Validation might fail on edge cases
- Integration with existing command methods

---

## 🧪 Tests to Run

### **Test 1: Import Check**
**What:** Make sure nothing broke on import
**Command:**
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
python3 -c "from rich_chat import RichMemoryChat; print('✅ Import successful')"
python3 -c "from command_handler import CommandHandler; print('✅ CommandHandler import successful')"
```
**Expected:** Both imports succeed
**Pass/Fail:** _____

---

### **Test 2: CommandHandler Standalone Test**
**What:** Test command handler logic independently
**Command:**
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
python3 command_handler.py
```
**Expected:**
```
CommandHandler basic test...
✅ Command detection works
✅ Command extraction works
✅ Argument extraction works
✅ Command validation works

CommandHandler basic test complete!
```
**Pass/Fail:** _____

---

### **Test 3: Simple Commands (no arguments)**
**What:** Test basic command routing
**Steps:**
1. Run: `python3 rich_chat.py`
2. Test each command:
   - `/help` → should show help table
   - `/status` → should show system status
   - `/context` → should show LLM context preview
   - `/stats` → should show memory statistics
   - `/debug` → should toggle debug mode
   - `/tokens` → should toggle token display
   - `/confidence` → should toggle confidence markers
   - `/errors` → should toggle error panel

**Expected Results:**
- ✅ Each command routes to correct method
- ✅ Display output looks correct
- ✅ No errors in terminal
- ✅ Commands execute immediately (no delay)

**Pass/Fail:** _____

---

### **Test 4: Commands with Arguments**
**What:** Test argument extraction and passing
**Steps:**
1. In chat, type: `/search test`
2. Should search for "test" in conversation history
3. Type: `/switch abc123`
4. Should attempt to switch to conversation "abc123"

**Expected Results:**
- ✅ `/search test` → searches for "test" (not empty search)
- ✅ `/search` (no args) → shows usage message
- ✅ `/switch abc123` → passes "abc123" to switch method
- ✅ `/switch` (no args) → shows usage message
- ✅ Arguments extracted correctly

**Pass/Fail:** _____

**Notes:** _____

---

### **Test 5: Recovery Command (complex arguments)**
**What:** Test commands that pass full user_input
**Steps:**
1. Type: `/recovery status`
2. Type: `/recovery help`

**Expected Results:**
- ✅ Full command string passed to recovery system
- ✅ Recovery system processes command correctly
- ✅ Result displayed properly
- ✅ No argument truncation

**Pass/Fail:** _____

---

### **Test 6: Invalid Command Validation**
**What:** Test unknown command handling
**Steps:**
1. Type: `/invalid`
2. Type: `/notacommand`
3. Type: `/help123`

**Expected Results:**
- ✅ Shows error: "Unknown command: /invalid"
- ✅ Shows message: "Type /help for a list of valid commands"
- ✅ Doesn't crash
- ✅ Returns to prompt for next input

**Pass/Fail:** _____

---

### **Test 7: Service Management Commands**
**What:** Test service commands work
**Steps:**
1. Type: `/services` → check service status
2. Type: `/start-services` → start services
3. Type: `/stop-services` → stop services

**Expected Results:**
- ✅ `/services` shows service health
- ✅ `/start-services` starts services (if not running)
- ✅ `/stop-services` shows debug message then stops services
- ✅ Success/error messages display correctly

**Pass/Fail:** ✅ PASSED (with emergency stop enhancement)

**Notes:**
- ⚠️ **Zombie Services Issue**: Discovered leftover services from previous rich-chat sessions causing multiple PIDs per port. This leakage between sessions broke the initial per-PID force-stop implementation (hung on second PID). Refactored to batch-kill approach: collect all PIDs, send SIGTERM to all, wait once, force-kill survivors. Successfully cleaned up 7 zombie processes across 4 services.
- Enhancement: Added confirmation prompt for `/stop-services` (nuclear option warning)
- Enhancement: Implemented `force_stop_all_services()` for emergency shutdown regardless of how services were started
- Fixed: `/services` and `/start-services` were calling non-existent chat methods instead of `service_manager` methods

---

### **Test 8: Memory Commands**
**What:** Test memory-related commands
**Steps:**
1. Type: `/memory` → show working memory
2. Type: `/history` → show full history
3. Type: `/search hello` → search for "hello"

**Expected Results:**
- ✅ `/memory` delegates to memory_handler.show_memory()
- ✅ `/history` delegates to memory_handler.show_full_history()
- ✅ `/search hello` delegates to memory_handler.search_conversations("hello")
- ✅ No routing errors

**Pass/Fail:** ✅ PASSED

---

### **Test 9: Conversation Commands**
**What:** Test conversation management
**Steps:**
1. Type: `/new` → start new conversation
2. Type: `/list` → list conversations
3. Type: `/switch <id>` → switch conversation (use real ID from /list)

**Expected Results:**
- ✅ `/new` creates new conversation (shows new ID)
- ✅ `/list` shows conversation list from episodic memory
- ✅ `/switch <id>` attempts to switch (may fail if ID invalid, but routing works)

**Pass/Fail:** ✅ PASSED (with bug fixes)

**Notes:**
- **Bug 1**: `/list` and `/switch` were calling non-existent `/conversations` endpoint. Fixed to use `/recent?limit=50` endpoint.
- **Bug 2**: `warning_message()` only routes to error panel (invisible without panel enabled). Fixed to use `console.print(Panel(...))` for user-visible feedback.
- `/new` works (would conflict with Claude Code's /new command in that UI)
- `/list` now shows "No previous conversations found" (none stored yet)
- `/switch test123` now shows clear "Not Found" panel instead of silence

---

### **Test 10: Toggle Commands State Management**
**What:** Verify toggles actually change state
**Steps:**
1. Type: `/debug` → should turn ON
2. Type: `/debug` → should turn OFF
3. Type: `/tokens` → should turn ON
4. Type: `/tokens` → should turn OFF

**Expected Results:**
- ✅ First toggle shows ON state
- ✅ Second toggle shows OFF state
- ✅ State persists between toggles
- ✅ Debug mode affects LLM (check self.llm.debug_mode)

**Pass/Fail:** _____

---

### **Test 11: /quit Command**
**What:** Test quit functionality
**Steps:**
1. Type: `/quit`
2. Should exit cleanly

**Expected Results:**
- ✅ Shows "👋 Goodbye!" message
- ✅ Exits chat
- ✅ No errors on exit
- ✅ Services cleaned up properly

**Pass/Fail:** _____

**Alternative Test:**
- Type: `exit` → should also quit
- ✅ Both `/quit` and `exit` work

---

### **Test 12: API Bridge Integration**
**What:** Verify API still works with new command routing
**Command:**
```bash
# Terminal 1:
python3 api_server_bridge.py

# Terminal 2:
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message": "hello"}'
```
**Expected:** Returns JSON response, no errors
**Pass/Fail:** _____

---

### **Test 13: /help Command in React**
**What:** Verify React UI still intercepts /help
**Steps:**
1. Open React UI (http://localhost:3000)
2. Type: `/help`

**Expected Results:**
- ✅ Shows help text (not sent to LLM)
- ✅ Help text properly formatted
- ✅ No errors in console
- ✅ API bridge command interception still works

**Pass/Fail:** _____

---

### **Test 14: Command Handler get_help_text() Method**
**What:** Test API fallback for help text
**Command:**
```bash
python3 -c "
from command_handler import CommandHandler
handler = CommandHandler(None, None)
help_text = handler.get_help_text()
print(help_text)
"
```
**Expected:** Prints formatted help text with all commands listed
**Pass/Fail:** _____

---

### **Test 15: Edge Case - Empty Input**
**What:** Test command handler with empty/whitespace input
**Steps:**
1. In chat, press Enter (empty input)
2. Type: `   ` (spaces only)
3. Type: `/` (slash only)

**Expected Results:**
- ✅ Empty input → continues to next prompt (no crash)
- ✅ Whitespace → continues to next prompt
- ✅ Slash only → shows invalid command error or continues

**Pass/Fail:** _____

---

### **Test 16: /ball Command (FIWB Mode)**
**What:** Test FUCK IT WE BALL mode toggle
**Steps:**
1. Type: `/ball` → should enable FIWB mode
2. Type: `/ball` → should disable FIWB mode

**Expected Results:**
- ✅ First toggle shows ON with red panel
- ✅ Shows what FIWB mode displays (stack traces, etc.)
- ✅ Second toggle shows OFF
- ✅ State managed in rich_chat.py

**Pass/Fail:** _____

---

### **Test 17: Line Count Verification**
**What:** Verify we reduced lines
**Command:**
```bash
wc -l /home/grinnling/Development/CODE_IMPLEMENTATION/rich_chat.py
wc -l /home/grinnling/Development/CODE_IMPLEMENTATION/command_handler.py
```
**Expected:**
- rich_chat.py: ~1435 lines (down from 1517)
- command_handler.py: ~338 lines

**Pass/Fail:** _____

---

## 📊 What I'm Looking For (AI Transparency)

As the AI, here's what I'm worried about with command routing:

1. **Argument Passing:**
   - Does `/search hello world` pass "hello world" (not "hello")?
   - Does `/switch abc123` pass "abc123" correctly?
   - Does `/recovery status` pass full "recovery status" string?

2. **Command Validation:**
   - Will `/searc` (typo) show invalid command error?
   - Will `/help123` be caught as invalid?
   - Will `/` alone cause a crash?

3. **State Management:**
   - Do toggles update state BEFORE returning?
   - Does `/debug` still update self.llm.debug_mode?
   - Does `/quit` properly break the loop?

4. **Integration Points:**
   - Does memory_handler still receive correct method calls?
   - Does recovery_chat still process commands properly?
   - Does API bridge still intercept commands?

5. **Edge Cases:**
   - What if command has trailing spaces? (`/help   `)
   - What if command has mixed case? (`/HeLp`)
   - What if user types `exit` vs `/quit`?

**If any of these fail, I want to know EXACTLY which test and the error message.**

---

## 📋 Summary

**Tests Passed:** _____ / 17
**Tests Failed:** _____ / 17

**Issues Found:**
- [ ] None (all tests passed!)
- [ ] Issue 1: _____________________________
- [ ] Issue 2: _____________________________
- [ ] Issue 3: _____________________________

**Notes:**


---

## ✅ Sign-Off

If all 17 tests pass:
- ✅ Phase 3 command extraction is working correctly
- ✅ All commands properly routed through CommandHandler
- ✅ Safe to continue to Phase 4 (dependency cleanup)

If any tests fail:
- ❌ Stop and review what broke
- ❌ Check command routing logic
- ❌ Debug before continuing to Phase 4

**Tested By:** _____________________
**Date:** October 5, 2025
**Ready to Continue to Phase 4:** YES / NO (circle one)

---

## 🔍 Debugging Reference

If tests fail, here's what to check:

**Test 3-5 failures (command routing):**
- Check `command_handler.handle_command()` return value
- Check `cmd_result.get('handled')` and `cmd_result.get('should_continue')`
- Verify command method exists in RichMemoryChat

**Test 4 failures (arguments):**
- Check `extract_args()` method in command_handler.py
- Verify args are passed to the right methods
- Check for off-by-one errors in string slicing

**Test 6 failures (validation):**
- Check `is_valid_command()` logic
- Verify `VALID_COMMANDS` dict has all commands
- Check command extraction logic

**Test 10 failures (state):**
- Check toggles update state before calling UIHandler
- Verify self.debug_mode, self.show_tokens, etc. are updated
- Check LLM integration (self.llm.debug_mode)

**Test 11 failures (quit):**
- Check `/quit` returns `{'handled': True, 'quit': True}`
- Verify main loop checks for `cmd_result.get('quit')`
- Check cleanup happens before exit

**Test 12-13 failures (API):**
- Check api_server_bridge.py still has command interception
- Verify `get_help_text()` method exists
- Check React UI command handling
