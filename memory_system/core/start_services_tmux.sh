#!/bin/bash

# Memory System Service Startup Script (tmux version)
# Creates a tmux session with each service in its own window
# Used by: manual startup, cluster restart from admin panel

SESSION_NAME="memory-system"
BASE_PATH="/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system"
CODE_PATH="/home/grinnling/Development/CODE_IMPLEMENTATION"
NODE_PATH="/home/grinnling/.nvm/versions/node/v22.17.1/bin"

echo "Starting Memory System Services (tmux)..."

# Check if session already exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists. Kill it first with: tmux kill-session -t $SESSION_NAME"
    echo "Or run: ./stop_services.sh"
    exit 1
fi

# Start Redis first (in docker, not tmux)
echo "Starting Redis..."
docker start redis-n8n > /dev/null 2>&1 || echo "WARNING: Redis container not found or failed to start"
sleep 1

# Create new tmux session with first window for Working Memory
echo "Creating tmux session..."
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

# Wait for backend services to start
echo "Waiting for memory services to initialize..."
sleep 3

# API Server
tmux new-window -t $SESSION_NAME -n "api-server" -c "$CODE_PATH"
tmux send-keys -t $SESSION_NAME:api-server "python3 api_server_bridge.py" C-m

# React UI (needs node in path)
tmux new-window -t $SESSION_NAME -n "react-ui" -c "$CODE_PATH"
tmux send-keys -t $SESSION_NAME:react-ui "export PATH=$NODE_PATH:\$PATH && npm start" C-m

# Select the api-server window by default
tmux select-window -t $SESSION_NAME:api-server

echo ""
echo "Services starting in tmux session '$SESSION_NAME'"
echo ""
echo "Service URLs:"
echo "  Redis:            localhost:6379"
echo "  Working Memory:   http://localhost:5001"
echo "  Memory Curator:   http://localhost:8004"
echo "  MCP Logger:       http://localhost:8001"
echo "  Episodic Memory:  http://localhost:8005"
echo "  API Server:       http://localhost:8000"
echo "  React UI:         http://localhost:3000"
echo ""
echo "tmux commands:"
echo "  Attach to session:  tmux attach -t $SESSION_NAME"
echo "  List windows:       tmux list-windows -t $SESSION_NAME"
echo "  Switch window:      Ctrl+B then window number (0-5)"
echo "  Detach:             Ctrl+B then D"
echo "  Kill session:       tmux kill-session -t $SESSION_NAME"
echo ""
echo "Or use: ./stop_services.sh to cleanly shut down everything"
