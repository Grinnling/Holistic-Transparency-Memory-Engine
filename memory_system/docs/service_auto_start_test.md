# Service Auto-Start Testing Document

## Overview
This document outlines testing procedures for the service auto-start functionality added to rich_chat.py. The system can now automatically start memory services if they're not running.

## Service Configuration
The system manages these memory services:

| Service | Port | Path | File |
|---------|------|------|------|
| working_memory | 5001 | `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/working_memory` | `service.py` |
| curator | 8004 | `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/memory_curator` | `curator_service.py` |
| mcp_logger | 8001 | `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/mcp_logger` | `server.py` |
| episodic_memory | 8005 | `/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/episodic_memory` | `service.py` |

## Testing Procedures

### 1. Auto-Start on Launch Test

#### Test Case 1.1: All services offline
```bash
# 1. Ensure all services are stopped
sudo pkill -f "memory_service|curator_service|episodic_service"

# 2. Launch chat with auto-start
python3 rich_chat.py --auto-start

# Expected: 
# - Shows "🔍 Checking services..."
# - Shows "Starting X services..."
# - Shows "🚀 Starting [service] on port [port]..."
# - Shows "✅ Started [service] (PID: [pid])"
# - Shows "Waiting for services to initialize..."
# - Shows "✅ [service] started successfully" for each service
```

#### Test Case 1.2: Some services already running
```bash
# 1. Start working_memory manually
cd /home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/working_memory
python3 service.py &

# 2. Launch chat with auto-start
python3 rich_chat.py --auto-start

# Expected:
# - Shows "✅ working_memory already running"
# - Starts only the missing services (curator, mcp_logger, episodic_memory)
```

#### Test Case 1.3: All services already running
```bash
# 1. Start all services manually (or use previous test)
# 2. Launch chat with auto-start
python3 rich_chat.py --auto-start

# Expected:
# - Shows "✅ [service] already running" for all services
# - Shows "All services already running!"
```

### 2. Manual Service Control Tests

#### Test Case 2.1: Check service status
```bash
# In rich_chat.py interface:
/services

# Expected:
# - Shows table with service status
# - Shows ✅ Online or ❌ Offline for each service
# - Shows LLM and Skinflap status
```

#### Test Case 2.2: Manual start services
```bash
# 1. Stop all services
sudo pkill -f "memory_service|curator_service|episodic_service"

# 2. In rich_chat.py interface:
/start-services

# Expected:
# - Same behavior as auto-start
# - Services start successfully
```

#### Test Case 2.3: Manual stop services
```bash
# 1. Start services using /start-services
# 2. In rich_chat.py interface:
/stop-services

# Expected:
# - Shows "Stopping auto-started services..."
# - Shows "Stopped [service] (PID: [pid])" for each auto-started service
# - Shows "✅ Services stopped"
```

### 3. Debug Mode Testing

#### Test Case 3.1: Auto-start in debug mode
```bash
python3 rich_chat.py --auto-start --debug

# Expected additional output:
# - "DEBUG: Starting in [path]"
# - "DEBUG: Running [file]" 
# - "Logs: /tmp/rich_chat_services/[service]_stdout.log"
# - "Errors: /tmp/rich_chat_services/[service]_stderr.log"
```

#### Test Case 3.2: Service startup failure in debug mode
```bash
# 1. Break a service file (add syntax error)
# 2. Run with debug mode
python3 rich_chat.py --auto-start --debug

# Expected:
# - Shows detailed error information
# - Shows "Last error:" with log content
# - Shows full traceback for startup failures
```

### 4. Log File Testing

#### Test Case 4.1: Verify log files creation
```bash
# 1. Start services
python3 rich_chat.py --auto-start

# 2. Check log files
ls -la /tmp/rich_chat_services/

# Expected files:
# - working_memory_stdout.log
# - working_memory_stderr.log  
# - curator_stdout.log
# - curator_stderr.log
# - mcp_logger_stdout.log
# - mcp_logger_stderr.log
# - episodic_memory_stdout.log
# - episodic_memory_stderr.log
```

#### Test Case 4.2: Log file content
```bash
# Check log file content
cat /tmp/rich_chat_services/working_memory_stdout.log

# Expected:
# - Service startup messages
# - Flask app initialization
# - Health check endpoint setup
```

### 5. Process Management Testing

#### Test Case 5.1: Process persistence
```bash
# 1. Start services through rich_chat.py
# 2. Exit rich_chat.py normally (/quit)
# 3. Check if services are still running
ps aux | grep -E "memory_service|curator_service|episodic_service"

# Expected:
# - Services should be terminated when chat exits
# - No orphaned processes
```

#### Test Case 5.2: Ctrl+C handling
```bash
# 1. Start services through rich_chat.py  
# 2. Press Ctrl+C to interrupt
# 3. Check if services are cleaned up
ps aux | grep -E "memory_service|curator_service|episodic_service"

# Expected:
# - Services should be terminated
# - No orphaned processes
```

### 6. Error Handling Tests

#### Test Case 6.1: Service fails to start
```bash
# 1. Make service file unexecutable
chmod -x /home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system/working_memory/service.py

# 2. Try to start services
python3 rich_chat.py --auto-start

# Expected:
# - Shows "❌ Failed to start working_memory: [error]"
# - Continues with other services
# - Provides helpful error information
```

#### Test Case 6.2: Service starts but health check fails
```bash
# 1. Modify service to bind to wrong port
# 2. Start services
python3 rich_chat.py --auto-start

# Expected:
# - Service process starts
# - Health check fails with "⚠️ [service] may not be running properly"
# - Shows log file locations for debugging
```

### 7. Integration Tests

#### Test Case 7.1: Full chat workflow with auto-started services
```bash
# 1. Start with auto-start
python3 rich_chat.py --auto-start

# 2. Have a conversation to test memory integration
# 3. Use /memory to check working memory
# 4. Exit and restart
# 5. Verify conversation history is restored

# Expected:
# - All memory services work correctly
# - Conversation history is preserved
# - No service connectivity issues
```

## Test Results Template

### Test Run: [Date]
**Environment:**
- OS: [Linux version]
- Python: [version]
- Terminal: [terminal type]

**Results:**
- [ ] Test Case 1.1: Auto-start all services offline
- [ ] Test Case 1.2: Auto-start some services running  
- [ ] Test Case 1.3: Auto-start all services running
- [ ] Test Case 2.1: Check service status
- [ ] Test Case 2.2: Manual start services
- [ ] Test Case 2.3: Manual stop services
- [ ] Test Case 3.1: Debug mode auto-start
- [ ] Test Case 3.2: Debug mode with failures
- [ ] Test Case 4.1: Log files creation
- [ ] Test Case 4.2: Log file content
- [ ] Test Case 5.1: Process persistence
- [ ] Test Case 5.2: Ctrl+C handling
- [ ] Test Case 6.1: Service start failure
- [ ] Test Case 6.2: Health check failure
- [ ] Test Case 7.1: Full integration test

**Issues Found:**
[Document any issues or unexpected behavior]

**Notes:**
[Additional observations or recommendations]

## Command Reference for Testing

```bash
# Quick service cleanup
sudo pkill -f "memory_service|curator_service|episodic_service"

# Check running services
ps aux | grep -E "memory_service|curator_service|episodic_service"

# Check ports in use
netstat -tulpn | grep -E "5001|8001|8004|8005"

# Monitor log files in real-time
tail -f /tmp/rich_chat_services/*.log

# Check service health manually
curl http://localhost:5001/health
curl http://localhost:8001/health  
curl http://localhost:8004/health
curl http://localhost:8005/health
```

## Performance Considerations

**Service Startup Time:**
- Working Memory: ~2-3 seconds
- Curator: ~3-4 seconds  
- MCP Logger: ~1-2 seconds
- Episodic Memory: ~2-3 seconds
- Total: ~8-12 seconds for all services

**Memory Usage:**
Monitor memory usage of auto-started services to ensure they don't consume excessive resources.

**Log File Growth:**
Log files in `/tmp/rich_chat_services/` will grow over time. Consider log rotation for long-running instances.