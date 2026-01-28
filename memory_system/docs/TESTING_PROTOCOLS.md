# Rich Memory Chat - Testing Protocols

## **Task 3: Memory Distillation Engine** ✅ COMPLETED

### **Test A: Memory Pressure Warning (80% threshold)**
```bash
python3 rich_chat.py --debug
```
**To Trigger:** Have ~80 exchanges (need to simulate or have long conversation)  
**Expected:** Yellow warning: `💾 Memory pressure: 80% (80/100)`

### **Test B: Full Distillation Trigger (100 exchanges)**
**To Trigger:** Reach 100+ exchanges total  
**Expected:** 
- Skinflap alert: "Blimey! My brain's fuller than a hoarder's attic!"
- Visual audit with green/yellow/red decisions
- Option to correct my reasoning
- Buffer reduced to ~50 exchanges

### **Test C: Stats Command**
```bash
/stats
```
**Expected:** Memory statistics table + learning progress display

---

## **Task 4: Token Counter Display** 

### **Test A: Context Token Display**
```bash
/context
```
**Expected:** Token count with color coding (green<1000, yellow<1500, red>1500) - ONLY when `/tokens` is ON

### **Test B: Token Toggle**
```bash
/tokens
```
**Expected:** Toggle on/off message, affects `/context` and `/stats` displays

### **Test C: Memory Stats Token Info**  
```bash
/stats
```
**Expected:** Token efficiency metrics in memory table - ONLY when `/tokens` is ON

---

## **Task 5: Stop Generation Handler** 

### **Test A: Interrupt Long Response**
1. Ask for something long: "Write a detailed essay about AI"
2. **While it's generating:** Press `Ctrl+C`
**Expected:** 
- Yellow warning: "⚠️ Generation interrupted. Press Ctrl+C again to exit chat."
- Generation stops gracefully, chat continues working

### **Test B: Multiple Interrupts**
1. Start generation
2. Ctrl+C to stop  
3. Ask new question immediately  
**Expected:** No broken state, new response works normally

### **Test C: Double Ctrl+C Exit**
1. Start generation
2. Ctrl+C to interrupt  
3. Ctrl+C again to exit
**Expected:** Clean exit from chat

---

## **Task 6: Uncertainty Markers (LLM-Friendly)** 

### **Test A: Confidence Toggle**
```bash
/confidence
```
**Expected:** Toggle on/off message with explanation

### **Test B: Automatic Uncertainty Detection**
**Confidence ON:** Ask: "What's the current weather in Tokyo?"  
**Expected:** Response includes: "🤔 **Confidence Note:** I can't check current weather conditions"

**Confidence OFF:** Same question  
**Expected:** No confidence markers in response

### **Test C: Vague Request Detection**
**Confidence ON:** Ask: "Make it better"  
**Expected:** Response includes: "🤔 **Confidence Note:** This seems like a broad request - I might need more specifics..."

### **Test D: Various Uncertainty Triggers**
Test these phrases with `/confidence` ON:
- "current stock prices" → market data warning
- "recent breaking news" → news access warning  
- "help me" → vague request warning

---

## **Task 7: Clarification Shortcuts (LLM-Friendly)** 

### **Test A: Vague Reference Detection**
Ask: "Fix that bug"  
**Expected:** Blue panel "🤔 Need More Details: Which bug specifically? I'd need more details to help."

### **Test B: Action Without Context**
Ask: "Make it better"  
**Expected:** Blue panel asking "What specifically would you like me to improve? Performance, functionality, or something else?"

### **Test C: Context-Aware Clarification** 
1. Discuss "authentication feature" 
2. Then ask: "Add that feature"  
**Expected:** Clarification mentions recent context about authentication

### **Test D: Missing Specifics**
Ask: "Run the script"  
**Expected:** Blue panel "Which script should I help you with?"

### **Test E: Pattern Priority**
Ask: "Fix it" (triggers both skinflap AND clarification)  
**Expected:** Clarification takes priority, shows blue panel first

---

## **Integration Tests**

### **Test I1: All Systems Working Together**
1. Start chat with: `python3 rich_chat.py --debug --auto-start`
2. Toggle: `/tokens` (on), `/confidence` (on)  
3. Have ~10 exchanges
4. Use `/context`, `/stats`, `/memory`
5. Ask vague question, interrupt response with Ctrl+C

**Expected:** All features work together without conflicts

### **Test I2: Memory Persistence + New Features**
1. Have conversation, quit
2. Restart chat  
3. Check `/memory` shows restored exchanges
4. Verify token counts and confidence markers still work
5. Test distillation if near 100 exchanges

**Expected:** All data persists, features continue working across sessions

---

## **Quick Smoke Test Checklist**

Run this minimal test suite to verify basic functionality:

- [ ] Chat starts successfully
- [ ] `/tokens` toggles token display  
- [ ] `/confidence` toggles uncertainty markers
- [ ] `/stats` shows memory + token info (if enabled)
- [ ] `/context` shows what goes to LLM
- [ ] Ctrl+C interrupts generation gracefully
- [ ] Memory persistence works across restart
- [ ] Ask vague question → get confidence note (if enabled)
- [ ] All services show online in startup health check

**Time Required:** ~5-10 minutes for smoke test, ~30 minutes for full protocol