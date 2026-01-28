# Environment Configuration System

**Created:** 2024-12-24
**Status:** Implemented

---

## Overview

Centralized environment configuration for all services. Provides a single "system map" that both humans and AI can read to understand the service topology.

## Files

| File | Purpose | Commit to Git? |
|------|---------|----------------|
| `.env.example` | Documents all services - the system map | Yes |
| `.env` | Actual config with your values | No |
| `check_services.py` | Health validation script | Yes |
| `.gitignore` | Prevents committing secrets | Yes |

---

## Service Topology

### Frontend (VITE_ prefix - exposed to browser)

| Variable | Default | Service |
|----------|---------|---------|
| `VITE_API_URL` | `http://localhost:8000` | Main API server |
| `VITE_WS_CHAT_URL` | `ws://localhost:8000/ws` | Chat WebSocket |
| `VITE_WS_EVENTS_URL` | `ws://localhost:8000/ws/events` | Visibility stream |
| `VITE_TERMINAL_WS_URL` | `ws://localhost:8765` | Terminal streaming |

### Backend Services (Python only)

| Variable | Default | Service |
|----------|---------|---------|
| `WORKING_MEMORY_URL` | `http://localhost:5001` | Short-term context |
| `CURATOR_URL` | `http://localhost:8004` | Memory curation |
| `MCP_LOGGER_URL` | `http://localhost:8001` | MCP logging |
| `EPISODIC_MEMORY_URL` | `http://localhost:8005` | Long-term storage |

### LLM Backends

| Variable | Default | Service |
|----------|---------|---------|
| `LLM_BACKEND` | `ollama` | Which backend to use |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama |
| `LMSTUDIO_URL` | `http://localhost:1234` | LM Studio |
| `TEXTGEN_URL` | `http://localhost:8080` | Text Gen WebUI |

### Optional

| Variable | Default | Service |
|----------|---------|---------|
| `REDIS_URL` | `redis://localhost:6379/0` | Context registry cache |

---

## Usage

### Check System Health

```bash
# Full check
python3 check_services.py

# Quick check (shorter timeouts)
python3 check_services.py --quick

# JSON output for scripting
python3 check_services.py --json
```

### For Docker/Production

Override variables in your environment:

```yaml
# docker-compose.yml
services:
  frontend:
    environment:
      - VITE_API_URL=http://api:8000
      - VITE_WS_EVENTS_URL=ws://api:8000/ws/events

  api:
    environment:
      - WORKING_MEMORY_URL=http://working-memory:5001
      - EPISODIC_MEMORY_URL=http://episodic:8005
```

---

## Files Updated

These files now read from environment variables with localhost defaults:

**React:**
- `src/App.tsx` - API_BASE
- `src/components/EventStreamPanel.tsx` - WebSocket URL
- `src/components/TerminalDisplay.tsx` - Terminal WebSocket

**Python:**
- `service_manager.py` - All service URLs
- `service_connector.py` - All service URLs
- `llm_connector.py` - LLM backend URLs
- `episodic_memory_coordinator.py` - Episodic memory URL

**Vite:**
- `vite.config.ts` - Proxy configuration

---

## For Claude/AI

Run `check_services.py` first thing to understand current system state. Read `.env.example` to understand the full service topology without grepping multiple files.
