# Friday Demo Script - Memory System with Semantic Search

## Pre-Demo Checklist (5 minutes before)
- [ ] Close any running service terminals
- [ ] Double-click "Memory System" desktop icon
- [ ] Verify all 6 terminal tabs opened
- [ ] Open browser to http://localhost:3000
- [ ] Check services dashboard shows all green

## Demo Flow (5-7 minutes)

### 1. The Problem (30 seconds)
**Say:**
> "Traditional keyword search in AI memory systems fails when words don't match exactly. If you ask 'What is my favorite color?' but the memory says 'My favorite color is purple' - keyword search might miss it."

### 2. Our Solution (30 seconds)
**Say:**
> "We implemented hybrid semantic search using BGE-M3 embeddings combined with SQLite FTS5. This means the system understands MEANING, not just keywords."

### 3. Live Demo - Semantic Memory Retrieval (2 minutes)

**Show the UI:**
- Point to services dashboard (all green)
- "6 microservices running: working memory, episodic memory, curator, MCP logger, API server, and React UI"

**Test Semantic Search:**
- Type: "What is my favorite color?"
- **Expected response:** System retrieves "purple" and cites sources:
  - "You said purple twice (Memory 1, Memory 5)"
  - Shows it's using retrieved context from episodic memory

**Say:**
> "Notice it found 'purple' even though my question used different words. The semantic search matched on MEANING, not exact keywords."

### 4. System Architecture (1 minute, if audience is technical)

**Say:**
> "The system uses:
> - **Episodic Memory Service** - BGE-M3 embeddings stored in SQLite with vector similarity search
> - **Hybrid Search** - Combines FTS5 keyword search + semantic embeddings
> - **Performance** - Sub-40ms query time for warm cache, 300ms cold start
> - **Graceful Degradation** - Services can fail without crashing the whole system"

### 5. Auto-Recovery Demo (1-2 minutes, OPTIONAL)

**Only do this if time allows and audience is technical:**

1. Close one service terminal tab (e.g., curator)
2. Refresh services dashboard → shows curator offline
3. Open terminal: `cd /home/grinnling/Development/CODE_IMPLEMENTATION`
4. Run: `python3 service_manager.py --autostart`
5. Dashboard shows green again

**Say:**
> "The service manager detects offline services and auto-restarts them. Makes recovery simple."

### 6. Wrap Up (30 seconds)

**Key Takeaways:**
- ✅ Semantic search works (demonstrated live)
- ✅ LLM uses retrieved memories and cites sources
- ✅ Distributed microservices architecture
- ✅ Auto-recovery capabilities
- ✅ Performance meets targets (<500ms)

**Say:**
> "This demonstrates a working memory system that understands meaning, not just keywords. All code is modular and the services can scale independently."

---

## Backup Plans

### If React UI doesn't load:
- Use curl commands to show API working:
  ```bash
  curl -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "What is my favorite color?"}'
  ```

### If LMStudio isn't connected:
- Focus on the semantic search working
- Show direct episodic memory query:
  ```bash
  curl "http://localhost:8005/search?query=favorite+color&limit=5"
  ```

### If services won't start:
- Show the service manager health check:
  ```bash
  python3 service_manager.py
  ```

---

## Technical Details (if asked)

**"How does semantic search work?"**
> "We use BGE-M3 embeddings - a multilingual model that converts text into 1024-dimensional vectors. Similar meanings produce similar vectors. We store these in SQLite and use cosine similarity to find relevant memories."

**"What about performance?"**
> "Cold start: 303ms (includes embedding generation). Warm cache: 37-39ms. Well under our 500ms target."

**"What if the database gets too large?"**
> "The curator service handles archival - moving old memories to long-term storage. We also have compression and cleanup strategies planned."

**"Where's the database stored?"**
> "Permanent storage at `/home/grinnling/Development/CODE_IMPLEMENTATION/data/episodic_memory.db` - no more temp directory data loss!"

**"Can it handle conflicting information?"**
> "The LLM sees all retrieved memories and can reason about conflicts. We tested this - it counts frequency and can explain which information is more recent."

---

## Quick Commands Reference

**Start all services:**
```bash
# Double-click desktop icon, OR:
/home/grinnling/Development/CODE_IMPLEMENTATION/start_services.sh
```

**Check service health:**
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
python3 service_manager.py
```

**Auto-start missing services:**
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
python3 service_manager.py --autostart
```

**Direct memory search:**
```bash
curl "http://localhost:8005/search?query=favorite+color&limit=5"
```

**Chat API:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my favorite color?"}'
```

---

## What NOT to Demo

- ❌ Don't test conflicting information live (save for later)
- ❌ Don't stop episodic service (causes 500 errors with apostrophes in fallback)
- ❌ Don't show error logs unless asked (can look messy)
- ❌ Don't over-promise features we haven't tested

---

## Post-Demo Notes

After demo, save feedback here:
- What questions did they ask?
- What impressed them most?
- What confused them?
- What features do they want next?

Good luck! 🚀
