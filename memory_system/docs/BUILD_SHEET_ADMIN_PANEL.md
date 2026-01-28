# Build Sheet: Service Admin Panel

**Created:** 2026-01-26
**Completed:** 2026-01-26
**Status:** IMPLEMENTED

---

## Overview

Expanded the existing ServiceStatusPanel into a full Service Admin Panel with:
- Service health indicators (existing, enhanced)
- Individual service restart controls (new)
- LLM status display with model identification (new)
- LLM reconnect button (new)
- API shutdown control (new)
- Full cluster restart via tmux (new)
- Toast notification system (new)
- Auto-reconnect polling (new)

---

## Implementation Summary

### What Changed vs. Original Plan

| Original Plan | What We Built |
|---------------|---------------|
| `stop_services.sh` (basic) | `stop_services.sh` with lsof validation, graceful waits, port verification |
| `restart_services.sh` (not planned) | Added for full cluster restart |
| `start_services_tmux.sh` (not planned) | Added tmux-based startup (cleaner than gnome-terminal) |
| `restart_external_services.sh` (not planned) | Added for stable cluster restart (API handles own shutdown) |
| Simple `/services/status` | Enhanced `/llm/status` with model role detection |
| String-matching for models | Env var config (`LLM_CHAT_MODEL`, etc.) with fallback |
| No toast system | Full toast notification system with context/provider |
| No auto-reconnect | ServiceStatusPanel polls and reconnects automatically |

---

## Files Modified/Created

### Backend (Python)

**Modified:** `api_server_bridge.py`
- Added imports: `os`, `subprocess`, `requests`
- Added LLM model role env vars: `LLM_CHAT_MODEL`, `LLM_EMBEDDING_MODEL`, `LLM_RERANK_MODEL`
- Added endpoints:
  - `GET /llm/status` - Returns chat/embedding/rerank model status
  - `POST /llm/reconnect` - Re-run SmartLLMSelector
  - `POST /services/shutdown` - Graceful API shutdown with state save
  - `POST /services/cluster-restart` - Triggers external restart + self-shutdown

### Frontend (React)

**Modified:** `src/main.tsx`
- Wrapped App with ToastProvider

**Modified:** `src/App.tsx`
- Added `useToast` hook
- Updated `handleServiceAction` with toast notifications
- Updated error handlers (`acknowledgeError`, `clearErrors`, `reportFix`) with toasts

**Modified:** `src/components/ServiceStatusPanel.tsx`
- Added LLM Status Card (shows chat, embedding, rerank models)
- Added Admin Controls Card (Reconnect LLM, Shutdown API, Cluster Restart)
- Added connection status tracking with auto-reconnect polling
- Added reconnection banner when API disconnected
- Integrated toast notifications for all actions

**Created:** `src/components/ui/toast.tsx`
- Toast component with variants (success, error, warning, info)
- ToastContainer for positioning and stacking

**Created:** `src/contexts/ToastContext.tsx`
- Toast context and provider
- `useToast` hook with convenience methods

**Modified:** `tailwind.config.js`
- Added slide-in animation for toasts

**Modified:** `.env.example`
- Added LLM model role configuration section

### Scripts

**Created:** `stop_services.sh`
- lsof dependency validation
- Graceful shutdown with SIGTERM, fallback to SIGKILL
- Port verification after stop
- Kills tmux session if exists

**Created:** `start_services_tmux.sh`
- Creates tmux session "memory-system"
- Named windows for each service
- Cleaner than gnome-terminal tabs

**Created:** `restart_services.sh`
- Calls stop then start
- Used for manual restart

**Created:** `restart_external_services.sh`
- Restarts everything EXCEPT the API
- API handles its own shutdown
- Avoids parent-killing-child race condition

---

## Testing Checklist

- [x] `stop_services.sh` stops all services cleanly
- [x] `stop_services.sh` validates lsof dependency
- [x] `/llm/status` returns accurate model identification
- [x] `/llm/status` uses env vars when configured, falls back to pattern matching
- [x] `/llm/reconnect` works when LMStudio started after API
- [x] `/services/shutdown` saves state and exits cleanly
- [x] `/services/cluster-restart` triggers stable restart
- [x] Individual service restart buttons work
- [x] Toast notifications appear for all actions
- [x] Auto-reconnect polling works after API restart
- [x] Reconnection banner shows during disconnect

---

## Environment Variables Added

```bash
# LLM Model Role Configuration (optional - falls back to auto-detect)
LLM_CHAT_MODEL=qwen          # Partial match for chat model
LLM_EMBEDDING_MODEL=bge-m3   # Partial match for embedding model
LLM_RERANK_MODEL=            # Partial match for rerank model (empty = not configured)
```

---

## Architecture Decisions

### Cluster Restart Stability

**Problem:** Original plan had restart script killing the API while API was its parent process - potential race condition.

**Solution:** API handles its OWN shutdown:
1. API receives `/services/cluster-restart`
2. API spawns `restart_external_services.sh` (detached)
3. API returns response to client
4. API schedules self-shutdown after 1 second
5. External script restarts all other services
6. External script starts new API in tmux

### Toast System

**Design:**
- Context-based (ToastProvider wraps app)
- Type variants: success (grey), error (red), warning (yellow), info (blue)
- Auto-dismiss with configurable duration
- Max 3 visible, stacked bottom-right
- Convenience methods: `toast.success()`, `toast.error()`, etc.

### LLM Model Detection

**Priority:**
1. Environment variables (explicit configuration)
2. Pattern matching on model names (fallback)

---

## Known Limitations

1. **Rerank endpoint not implemented** - Model slot shows in UI but actual rerank functionality is stubbed in curator_service.py

2. **No new-error toast** - Toasts fire for user actions, but not automatically when new critical errors appear in the error panel

3. **tmux required** - Cluster restart uses tmux sessions; won't work without tmux installed

---

## Cleanup Notes

Multiple startup scripts exist:
- `start_services.sh` - gnome-terminal approach (original)
- `start_all_services.sh` - Python ServiceManager approach
- `start_services_tmux.sh` - tmux approach (recommended for cluster restart)

All three are valid for different use cases. Keep unless consolidation requested.

---

## Dependencies

Validated:
- `lsof` - Required for port-based process detection (validated at script start)
- `tmux` - Required for cluster restart

---

## Future Enhancements (Not Implemented)

1. **New critical error toast** - Fire toast when critical error arrives, with "Check Error Panel" action
2. **Copy message to clipboard toast** - Feedback when copying chat messages
3. **Sidebar spawn toast** - Feedback when creating new sidebars
