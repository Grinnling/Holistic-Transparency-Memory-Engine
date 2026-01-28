# Testing Sheet: Service Admin Panel

**Created:** 2026-01-26
**Related Build Sheet:** BUILD_SHEET_ADMIN_PANEL.md

---

## Prerequisites

Before testing, ensure:
- [ ] tmux is installed (`sudo apt install tmux` if not)
- [ ] lsof is installed (`sudo apt install lsof` if not)
- [ ] LM Studio is running with models loaded
- [ ] Redis container exists (`docker ps -a | grep redis-n8n`)

---

## Test Sequence

Run tests in order - some depend on previous steps.

---

## Phase 1: Script Validation

### Test 1.1: lsof Dependency Check
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
./stop_services.sh
```

**Expected:** Script runs OR shows "ERROR: lsof is required" if not installed

**Pass:** [ ] Script validates dependency before proceeding

---

### Test 1.2: Stop Services (Nothing Running)
```bash
./stop_services.sh
```

**Expected:** Each service shows "not running (port X free)"

**Pass:** [ ] Script handles no-services-running gracefully

---

### Test 1.3: Start Services (tmux)
```bash
./start_services_tmux.sh
```

**Expected:**
- Creates tmux session "memory-system"
- Shows service URLs
- Services start in background

**Verify:**
```bash
tmux list-sessions
tmux attach -t memory-system
# Ctrl+B then number to switch windows
# Ctrl+B then D to detach
```

**Pass:** [ ] tmux session created with all service windows

---

### Test 1.4: Stop Services (Running)
```bash
./stop_services.sh
```

**Expected:**
- Each service stops with PID shown
- "All ports free" at end
- tmux session killed

**Pass:** [ ] All services stopped cleanly

---

## Phase 2: React Build Verification

### Test 2.1: TypeScript Compilation
```bash
cd /home/grinnling/Development/CODE_IMPLEMENTATION
npm run build
```

**Expected:** Build completes without errors

**Watch for:**
- Import path errors (ToastContext)
- Type errors in new components
- Missing dependencies

**Pass:** [ ] Build succeeds

---

### Test 2.2: Dev Server Start
```bash
npm start
```

**Expected:** Vite dev server starts on localhost:3000

**Pass:** [ ] Dev server running

---

## Phase 3: UI Component Testing

Start all services first:
```bash
./start_services_tmux.sh
```

Open browser to http://localhost:3000

---

### Test 3.1: ServiceStatusPanel Loads
Navigate to Status tab in sidebar.

**Expected:**
- System Health card shows
- LLM Status card shows
- Admin Controls card shows
- Service Status list shows

**Pass:** [ ] All cards render without errors

---

### Test 3.2: LLM Status Display
Check LLM Status card.

**Expected:**
- Chat model shows with status (connected/offline)
- Embedding model shows with status
- Rerank shows "not_configured" or model name
- "LM Studio loaded models" list appears

**Pass:** [ ] Models correctly identified and displayed

---

### Test 3.3: Toast on Service Restart
1. Expand any service (click on it)
2. Click "Restart" button

**Expected:**
- Toast appears bottom-right
- Shows success or error message
- Auto-dismisses after ~3 seconds

**Pass:** [ ] Toast notification works

---

### Test 3.4: LLM Reconnect Button
1. In Admin Controls, click "Reconnect LLM"

**Expected:**
- Button shows "Reconnecting..."
- Toast shows result (success/failure)
- LLM Status card updates

**Pass:** [ ] Reconnect works and shows feedback

---

### Test 3.5: API Shutdown
1. Click "Shutdown API"
2. Confirm dialog

**Expected:**
- Toast shows "API shutting down..."
- Connection banner appears ("Reconnecting to API...")
- Reconnect attempts counter increments

**Pass:** [ ] Shutdown triggers, UI shows disconnected state

---

### Test 3.6: Auto-Reconnect
After API shutdown:
1. Restart API manually:
```bash
tmux attach -t memory-system
# Switch to api-server window (Ctrl+B then window number)
python3 api_server_bridge.py
# Ctrl+B then D to detach
```

**Expected:**
- Connection banner disappears
- Toast shows "API reconnected"
- Status refreshes automatically

**Pass:** [ ] Auto-reconnect works

---

### Test 3.7: Cluster Restart
1. Click "Full Cluster Restart"
2. Confirm dialog

**Expected:**
- Toast shows "Cluster restart initiated"
- UI disconnects (reconnecting banner)
- After ~10-15 seconds, UI reconnects
- All services healthy again

**Verify tmux:**
```bash
tmux attach -t memory-system
# Should show all services running in windows
```

**Pass:** [ ] Full cluster restart completes successfully

---

## Phase 4: Error Panel Integration

### Test 4.1: Clear Errors Toast
1. Switch to Errors tab
2. If errors exist, click "Clear All"

**Expected:**
- Toast shows "All errors cleared"

**Pass:** [ ] Error clear shows toast

---

### Test 4.2: Acknowledge Error Toast
1. If errors exist, click acknowledge on one

**Expected:**
- Toast shows "Error acknowledged"

**Pass:** [ ] Acknowledge shows toast

---

## Phase 5: Environment Variable Config

### Test 5.1: Model Config via Env Vars
1. Stop services
2. Set env vars:
```bash
export LLM_CHAT_MODEL=qwen
export LLM_EMBEDDING_MODEL=bge
```
3. Start API:
```bash
python3 api_server_bridge.py
```
4. Check http://localhost:8000/llm/status

**Expected:**
- Response includes `"config_source": "env_vars"`
- Models matched by env var patterns

**Pass:** [ ] Env var config works

---

## Phase 6: Edge Cases

### Test 6.1: LM Studio Not Running
1. Stop LM Studio
2. Check LLM Status card

**Expected:**
- Shows "lmstudio_error" in response
- Chat shows "disconnected"
- Embedding shows "offline"

**Pass:** [ ] Graceful handling when LM Studio down

---

### Test 6.2: Rapid Button Clicks
Click "Reconnect LLM" multiple times quickly.

**Expected:**
- Buttons disable during action (loading state)
- No duplicate toasts
- No console errors

**Pass:** [ ] Rate limiting works

---

### Test 6.3: Multiple Toasts
Trigger several actions quickly.

**Expected:**
- Max 3 toasts visible
- Older toasts auto-dismiss
- Stack from bottom

**Pass:** [ ] Toast stacking works correctly

---

## Phase 7: Frontend Error Reporting (Added 2026-01-27)

### Test 7.1: Error Endpoint Exists
```bash
curl -X POST http://localhost:8000/errors/report \
  -H "Content-Type: application/json" \
  -d '{"source":"test","operation":"curl_test","message":"Test error","severity":"low"}'
```

**Expected:**
- Returns `{"status":"reported","error_id":"...","category":"...","severity":"..."}`
- Error appears in GET /errors response

**Pass:** [ ] Endpoint accepts and routes frontend errors

---

### Test 7.2: Error Panel Shows Frontend Errors
1. Trigger a frontend error (e.g., stop API while sending a message)
2. Restart API
3. Check Error Panel

**Expected:**
- Error shows with source like `[Frontend:App]`
- Operation and context visible in error details

**Pass:** [ ] Frontend errors visible in Error Panel

---

### Test 7.3: Graceful Degradation
1. Stop the API completely
2. In browser console, watch for errors
3. Errors should log to console, not throw exceptions

**Expected:**
- `[errorReporter] Could not reach API: ...` in console
- No uncaught exceptions
- UI remains functional

**Pass:** [ ] Error reporter handles API-down gracefully

---

### Test 7.4: Recovery Reporting
1. Stop the API for ~30 seconds
2. Watch browser console for polling failures
3. Restart the API
4. Check Error Panel after reconnect

**Expected:**
- First disconnect: reported at medium severity
- Polling failures: logged at trace level (in log file, not flooding panel)
- On reconnect: recovery message with attempt count and duration
- Example: "Reconnected after 30s and 6 polling failures"

**Pass:** [ ] Recovery reports include attempt count and duration

---

### Test 7.5: Audit Trail (Log File)
```bash
cat /home/grinnling/Development/CODE_IMPLEMENTATION/logs/errors.log | tail -50
```

**Expected:**
- All trace-level polling errors present in log
- Timestamps for each failure
- Recovery events logged

**Pass:** [ ] Log file contains full audit trail including trace-level errors

---

## Results Summary (2026-01-26)

| Phase | Test | Pass/Fail | Notes |
|-------|------|-----------|-------|
| 1.1 | lsof check | PASS | |
| 1.2 | Stop (nothing) | PASS | |
| 1.3 | Start tmux | PASS | |
| 1.4 | Stop (running) | PASS | |
| 2.1 | TS build | PASS | |
| 2.2 | Dev server | PASS | |
| 3.1 | Panel loads | PASS | |
| 3.2 | LLM status | PASS | |
| 3.3 | Restart toast | PASS | |
| 3.4 | LLM reconnect | PASS | |
| 3.5 | API shutdown | PASS | |
| 3.6 | Auto-reconnect | FIXED | Was partial, now auto-resumes |
| 3.7 | Cluster restart | PASS | |
| 4.1 | Clear errors toast | PASS | |
| 4.2 | Acknowledge toast | SKIP | No errors to test |
| 5.1 | Env var config | PASS | |
| 6.1 | LM Studio down | FIXED | Chat/Rerank now show "offline" |
| 6.2 | Rapid clicks | FIXED | 1 second cooldown added |
| 6.3 | Toast stacking | PASS | |

**Overall: 14 PASS, 3 FIXED, 1 SKIP**

---

## Fixes Applied This Session

1. **Chat/Rerank status logic** (api_server_bridge.py:680-740)
   - Chat now shows "offline" when LM Studio is down (was showing "connected")
   - Rerank now shows "offline" when LM Studio down (was showing "not_configured")

2. **Rapid click rate limiting** (ServiceStatusPanel.tsx)
   - Added ref-based guard + 1 second cooldown between admin actions

3. **Toast history** (ToastContext.tsx)
   - Added `history` array and `clearHistory()` to context
   - Keeps last 50 toasts with timestamps

4. **Auto-resume after disconnect** (App.tsx)
   - Connection polling now triggers checkStartupState on reconnect
   - Shows "Waiting for API..." instead of "Start Fresh" when API is down
   - Session resumes automatically when API returns

5. **Frontend error reporting** (2026-01-27, recovered session)
   - Added `POST /errors/report` endpoint to api_server_bridge.py
   - Created `src/utils/errorReporter.tsx` with `reportError()` and `reportCaughtError()` helpers
   - Wired up catch blocks in:
     - `ServiceStatusPanel.tsx`: fetchLLMStatus, handleReconnectLLM
     - `SidebarsPanel.tsx`: bulk archive, alias/tags operations
     - `App.tsx`: sendMessage, spawnSidebar, focusSidebar, createRootContext, handleServiceAction, error panel operations
   - Frontend errors now appear in the Error Panel alongside backend errors
   - Graceful degradation: if API is down, errors log to console instead of throwing

---

## Remaining Work (TODO)

### HIGH PRIORITY - Service Stop Bug
**The Stop button in Service Status doesn't work!**

- `handleServiceAction` in App.tsx ignores the action parameter
- Always calls `/services/{service_name}/restart` regardless of action
- Backend has no `/services/{service_name}/stop` endpoint

**Fix needed:**
1. Add `POST /services/{service_name}/stop` to api_server_bridge.py
2. Fix handleServiceAction to call correct endpoint based on action
3. Consider adding `POST /services/{service_name}/start` too

### MEDIUM PRIORITY - API in Service Status
**Move API controls from Admin Controls to Service Status**

- Remove "Shutdown API" from Admin Controls
- Add "api_server" to service list with Stop/Restart buttons
- Special handling: API restart should call cluster-restart or similar

**Admin Controls should keep:**
- LLM Reconnect
- Cluster Restart

### LOW PRIORITY - UX Polish
1. **Admin message stuck after shutdown** - Clear adminMessage when connection restored
2. **Toast history UI** - Add way to view toast history (currently just stored, no UI)

---

## Known Issues to Watch For

1. **First load after restart** - LLM Status might show "Loading..." for a few seconds while first fetch completes

2. **tmux session name collision** - If "memory-system" session already exists from previous run, start_services_tmux.sh will fail. Run stop_services.sh first.

3. **Port still in use** - If a service didn't stop cleanly, the port might still be held. Wait a few seconds or check with `lsof -i:PORT`

---

## Debugging Commands

```bash
# Check what's running on a port
lsof -i:8000

# Check tmux sessions
tmux list-sessions

# Attach to tmux
tmux attach -t memory-system

# Kill stuck tmux session
tmux kill-session -t memory-system

# Check API health directly
curl http://localhost:8000/health

# Check LLM status directly
curl http://localhost:8000/llm/status | python3 -m json.tool
```
