# Quick Start Guide - Friday Demo

**Date**: 2025-10-01
**Status**: Ready for demo testing

---

## ✅ What's Working

1. **Semantic/Embedding Search** - FULLY FUNCTIONAL
   - BGE-M3 embeddings integrated
   - Hybrid FTS5 + vector similarity search
   - LLM successfully recalls episodic memories
   - Database in permanent storage: `/home/grinnling/Development/CODE_IMPLEMENTATION/data/episodic_memory.db`

2. **All Core Features**
   - Memory archival ✅
   - Memory recall ✅
   - UI integration ✅
   - Persistence across restarts ✅

---

## 🚀 Start Services for Demo

### Step 1: Start Episodic Memory Service
```bash
cd /home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/episodic_memory
nohup python3 service.py > /tmp/episodic_service.log 2>&1 &

# Verify it's running:
curl http://localhost:8005/health | grep database_path
# Should show: /home/grinnling/Development/CODE_IMPLEMENTATION/data/episodic_memory.db
```

### Step 2: Start API Server
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
nohup python3 api_server_bridge.py > /tmp/api_server.log 2>&1 &

# Verify:
curl http://localhost:8000/health
```

### Step 3: Start React UI
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
npm start > /tmp/react_ui.log 2>&1 &

# Access at: http://localhost:3000
```

### Step 4: Verify LM Studio is Running
- Open LM Studio
- Ensure model is loaded
- Check: `curl http://localhost:1234/v1/models`

---

## 🧪 Remaining Tests (15 minutes)

### TEST 7+9: Error Reporting & Graceful Degradation (~10 min)
```bash
# Stop episodic service
fuser -k 8005/tcp

# Send chat message via UI or:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Testing error handling"}'

# Check UI error panel - should show episodic connection error
# Chat should still work (graceful degradation)

# Restart episodic service
cd /home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/episodic_memory
python3 service.py &

# Verify recovery
```

### TEST 8: Performance Check (~3 min)
```bash
# Send a quick message, note response time
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}' -w "\nTime: %{time_total}s\n"

# Should be < 3 seconds total (memory adds ~500ms)
```

---

## 🎯 Demo Script

**Scenario**: Show AI with episodic memory recall

1. **Setup**: "I'm going to teach the AI something about myself"
   - Send: "My favorite color is green"
   - Wait for response

2. **Different Session**: Clear working memory or restart services
   - This proves long-term storage works

3. **The Magic**: "Does it remember?"
   - Ask: "What's my favorite color?"
   - **Expected**: AI recalls "green" from episodic memory
   - **Tech**: Hybrid search (keyword + semantic embeddings) retrieves past conversation

4. **Show Semantic Understanding**
   - Ask: "What color do I prefer?"
   - Ask: "Tell me about my color choices"
   - **Point**: Different phrasings, same semantic meaning, AI still recalls

5. **Bonus**: Show the UI
   - Memory stats showing episodic count
   - Working memory vs episodic storage
   - Error panel (if you ran error tests)

---

## 🔍 Troubleshooting

### Database Path Issues
```bash
# Verify database is in correct location:
curl http://localhost:8005/health | grep database_path

# Should show: /home/grinnling/Development/CODE_IMPLEMENTATION/data/episodic_memory.db
# If shows /tmp/ - we fixed this but need to restart service
```

### Service Won't Start
```bash
# Check if port is in use:
ss -tln | grep :8005

# Kill processes on port:
fuser -k 8005/tcp
```

### No Memory Recall
```bash
# Check if memories exist:
curl http://localhost:8005/stats

# Check if semantic search works:
curl "http://localhost:8005/search?query=color&limit=3"
```

---

## 📊 Test Sheet Status

**Location**: `/home/grinnling/Development/CODE_IMPLEMENTATION/FRIDAY_DEMO_TEST_SHEET.md`

- ✅ TEST 1-6: Completed
- ⏳ TEST 7+9: Error handling (10 min)
- ⏳ TEST 8: Performance (3 min)

**Total time to demo-ready**: ~15 minutes of testing

---

## 💾 Important Files

**Database**: `/home/grinnling/Development/CODE_IMPLEMENTATION/data/episodic_memory.db` (160KB)

**Services**:
- Episodic: `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/episodic_memory/service.py`
- API: `/home/grinnling/Development/CODE_IMPLEMENTATION/api_server_bridge.py`
- React UI: `/home/grinnling/Development/CODE_IMPLEMENTATION/`

**Logs**:
- Episodic: `/tmp/episodic_service.log`
- API: `/tmp/api_server.log`
- React: `/tmp/react_ui.log`

---

## 🎉 Ready to Demo!

Everything is in place. Just start services, run the 15 min of remaining tests, and you're ready to show off semantic memory recall!
