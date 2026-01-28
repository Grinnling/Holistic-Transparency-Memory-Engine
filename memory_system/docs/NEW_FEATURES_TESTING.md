# Testing Protocols for Latest Additions

## **Enhanced Skinflap Integration** ✅ UPDATED

### **Test SF1: Non-Blocking Skinflap Detection**
Ask: "Fix the bug" (previously would block)
**Expected:** 
- NO blocking panels anymore
- LLM receives skinflap detection info in system prompt
- Model should ask for clarification naturally: "Which bug specifically?"

### **Test SF2: Skinflap Context Integration**
1. Enable debug mode: `/debug`
2. Ask: "Make this better" 
3. Check debug output for skinflap detection info
**Expected:** System prompt includes "QUERY ANALYSIS INFO" with detected patterns

### **Test SF3: Silly Response Generation**
Ask: "Make this perfect, cheap, and instant"
**Expected:** Silly formatted response with rich panels (🎭 **Hark! The Impossible Triangle!**)

---

## **Enhanced LLM Connector** ✅ UPDATED

### **Test LLM1: Skinflap-Aware Generation**
1. Ask vague question: "Optimize it"
2. Check that response is contextually aware
**Expected:** LLM should reference conversation history to understand "it"

### **Test LLM2: Multi-Provider Skinflap Support**
Test with different LLM providers (if available):
- LM Studio
- TGI  
- Ollama
**Expected:** All providers receive skinflap detection context

---

## **Two-Stage Testing Protocol** (From CLAUDE.md)

### **Stage 1: Unit Logic Testing**
```python
# Test skinflap detection directly
result = chat.check_with_skinflap("Fix that bug")
assert result['needs_clarification'] == False  # Should not block
assert 'detection_info' in result

# Test search logic
matches = chat.search_conversations("memory")
assert len(matches) > 0  # If you have memory-related conversations
```

### **Stage 2: In-Field Simulation**
```bash
# Test full command flow
/search memory
/help
/history
```

---

## **Integration Testing**

### **Test INT1: Skinflap + Clarification Priority**
Ask: "Fix it" (triggers both systems)
**Expected:** 
1. Clarification shortcuts take priority (blue panel)
2. If no clarification triggered, skinflap info goes to LLM
3. LLM makes informed decision about asking for details

### **Test INT2: Debug Mode Visibility**
1. Enable debug: `/debug`
2. Ask ambiguous question
3. Check debug output shows:
   - Skinflap detection info
   - Context sent to LLM
   - Model's response reasoning

---

## **Episodic Memory Service Status**

Based on the directory structure I saw earlier, **episodic memory service exists** at:
`/home/grinnling/Development/docs/github/repo/memory_system/episodic_memory/service.py`

### **Test EM1: Episodic Memory Service Check**
```bash
# Check if episodic memory is running
curl http://localhost:8002/health  # (assuming port 8002)
```

### **Test EM2: Episodic Memory Integration**
1. Check if rich_chat connects to episodic memory
2. Look for episodic memory in service health check
**Expected:** Should show in startup health table if configured

---

## **Episodic Memory Integration** ✅ NEW

### **Test EM1: Episodic Memory Service Health**
```bash
curl http://localhost:8005/health
```
**Expected:** JSON response with "healthy" status and service details

### **Test EM2: Episodic Memory in Startup Health**
1. Start services: `bash start_services.sh`
2. Start chat: `python3 rich_chat.py --auto-start`
**Expected:** Health table shows episodic_memory as "✅ Online"

### **Test EM3: Automatic Archival**
1. Enable debug: `/debug`
2. Have a conversation (few exchanges)
3. Check debug output for archival attempts
**Expected:** No error messages (or debug info if episodic service is down)

### **Test EM4: Cross-Session Memory Integration**
1. Have conversation, then quit
2. Restart chat with `python3 rich_chat.py --auto-start`
3. Use `/memory` to view history
**Expected:** Should show restored exchanges from working memory + episodic context

### **Test EM5: Episodic Memory Failure Graceful**
1. Stop episodic memory service
2. Continue chatting normally
3. Enable `/debug` to see failure messages
**Expected:** Chat continues normally, debug shows episodic archive failures

---

## **Tier 2: Conversation Management** ✅ NEW

### **Test CM1: Start New Conversation**
1. Start chat, have a few exchanges
2. Run `/new`
3. Confirm old conversation shows exchange count
4. New conversation should have fresh UUID (first 8 chars shown)
**Expected:** Clean slate but memory services retain all data

### **Test CM2: List Conversations** 
1. Run `/list` 
2. Check conversation table shows recent conversations
3. Current conversation should be marked with "🔸 Current"
**Expected:** Table with ID, Started, Exchanges, Last Activity, Status columns

### **Test CM3: Switch Between Conversations**
1. Start conversation A, have exchanges
2. Run `/new` to start conversation B
3. Run `/list` to see both conversations  
4. Run `/switch <first-8-chars-of-A>`
5. Verify conversation A is restored with full history
**Expected:** Can switch between conversations and continue from where you left off

### **Test CM4: Conversation ID Completion**
1. Run `/switch abc` (partial ID)
2. Should work if only one match
3. Should warn if multiple matches
4. Should error if no matches
**Expected:** Smart partial ID matching with clear error messages

---

## **Quick Verification Checklist**

**New Behavior Verification:**
- [ ] Skinflap no longer blocks with panels
- [ ] Vague questions get natural clarification from LLM
- [ ] `/help` shows comprehensive guide
- [ ] `/search <term>` finds and highlights matches
- [ ] `/history` shows everything without pagination
- [ ] Debug mode shows skinflap detection context
- [ ] Episodic memory service shows "✅ Online" in health table
- [ ] Episodic memory archives exchanges (check with `/debug`)
- [ ] `/new` command creates fresh conversation with new UUID
- [ ] `/list` shows conversation history with current marked
- [ ] `/switch <id>` loads conversation from episodic memory
- [ ] Partial conversation ID matching works correctly

**Regression Testing:**
- [ ] All original Tier 1 features still work
- [ ] Memory distillation still triggers at 100+ exchanges
- [ ] Token counting still toggleable
- [ ] Confidence markers still work
- [ ] Ctrl+C interruption still graceful

**Time Required:** ~15 minutes for new features, ~10 minutes regression check