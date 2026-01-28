#!/bin/bash

# Memory System External Services Restart Script
# Restarts all services EXCEPT the API server (which handles its own shutdown)
# Used by: cluster restart from admin panel
#
# The API server calls this script, then gracefully shuts itself down.
# This script waits for external services to stop, then starts them fresh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_PATH="/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system"
SESSION_NAME="memory-system"
NODE_PATH="/home/grinnling/.nvm/versions/node/v22.17.1/bin"

# Validate dependencies
if ! command -v lsof &> /dev/null; then
    echo "ERROR: lsof is required but not installed"
    echo "Install with: sudo apt install lsof"
    exit 1
fi

echo "============================================"
echo "Restarting External Services"
echo "(API will handle its own shutdown)"
echo "============================================"
echo ""

# Function to stop a service by port
stop_by_port() {
    local port=$1
    local name=$2
    local pid=$(lsof -ti:$port 2>/dev/null)

    if [ -n "$pid" ]; then
        echo "  Stopping $name (port $port, PID: $pid)..."
        kill -SIGTERM $pid 2>/dev/null

        # Wait up to 5 seconds for graceful shutdown
        local waited=0
        while [ $waited -lt 5 ]; do
            if ! kill -0 $pid 2>/dev/null; then
                echo "    $name stopped"
                return 0
            fi
            sleep 1
            waited=$((waited + 1))
        done

        # Force kill if still running
        if kill -0 $pid 2>/dev/null; then
            echo "    Force stopping $name..."
            kill -SIGKILL $pid 2>/dev/null
            sleep 1
        fi
    else
        echo "  $name not running (port $port free)"
    fi
}

echo "Phase 1: Stop React UI"
stop_by_port 3000 "React UI"

echo ""
echo "Phase 2: Stop Memory Services"
stop_by_port 5001 "Working Memory"
stop_by_port 8004 "Memory Curator"
stop_by_port 8001 "MCP Logger"
stop_by_port 8005 "Episodic Memory"

echo ""
echo "Phase 3: Restart Redis"
if docker ps --format '{{.Names}}' | grep -q 'redis-n8n'; then
    docker restart redis-n8n > /dev/null 2>&1 && echo "  Redis restarted" || echo "  Failed to restart Redis"
else
    docker start redis-n8n > /dev/null 2>&1 && echo "  Redis started" || echo "  Redis container not found"
fi
sleep 1

echo ""
echo "Phase 4: Kill existing tmux session if any"
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    tmux kill-session -t $SESSION_NAME
    echo "  Killed existing tmux session"
fi

echo ""
echo "Phase 5: Start services in new tmux session"

# Create new tmux session with first window for Working Memory
tmux new-session -d -s $SESSION_NAME -n "working-memory" -c "$BASE_PATH/working_memory"
tmux send-keys -t $SESSION_NAME:working-memory "python3 service.py" C-m

# Memory Curator
tmux new-window -t $SESSION_NAME -n "curator" -c "$BASE_PATH/memory_curator"
tmux send-keys -t $SESSION_NAME:curator "python3 curator_service.py" C-m

# MCP Logger
tmux new-window -t $SESSION_NAME -n "mcp-logger" -c "$BASE_PATH/mcp_logger"
tmux send-keys -t $SESSION_NAME:mcp-logger "python3 server.py" C-m

# Episodic Memory
tmux new-window -t $SESSION_NAME -n "episodic" -c "$BASE_PATH/episodic_memory"
tmux send-keys -t $SESSION_NAME:episodic "python3 service.py" C-m

echo "  Memory services starting in tmux..."

# Wait for memory services
sleep 3

# API Server window (will be started by start_api.sh or manually)
tmux new-window -t $SESSION_NAME -n "api-server" -c "$SCRIPT_DIR"
tmux send-keys -t $SESSION_NAME:api-server "echo 'Waiting for API to restart...'; sleep 2; python3 api_server_bridge.py" C-m

# React UI
tmux new-window -t $SESSION_NAME -n "react-ui" -c "$SCRIPT_DIR"
tmux send-keys -t $SESSION_NAME:react-ui "export PATH=$NODE_PATH:\$PATH && npm start" C-m

echo "  All services starting in tmux session '$SESSION_NAME'"

echo ""
echo "============================================"
echo "External services restart complete"
echo "API will restart in tmux"
echo "============================================"
echo ""
echo "Attach with: tmux attach -t $SESSION_NAME"
