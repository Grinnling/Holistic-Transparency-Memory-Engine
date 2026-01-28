#!/bin/bash

# Memory System Service Startup Script
# Run this to start all services for Friday Demo

echo "🚀 Starting Memory System Services..."

BASE_PATH="/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system"

# Redis - Start first since other services depend on it
echo "Starting Redis..."
docker start redis-n8n > /dev/null 2>&1 || echo "⚠️  Redis container not found or failed to start"
sleep 1  # Give Redis a moment to accept connections

# Terminal 1 - Working Memory
gnome-terminal --tab --title="Working Memory" -- bash -c "cd $BASE_PATH/working_memory && python3 service.py; exec bash" &

# Terminal 2 - Memory Curator
gnome-terminal --tab --title="Memory Curator" -- bash -c "cd $BASE_PATH/memory_curator && python3 curator_service.py; exec bash" &

# Terminal 3 - MCP Logger
gnome-terminal --tab --title="MCP Logger" -- bash -c "cd $BASE_PATH/mcp_logger && python3 server.py; exec bash" &

# Terminal 4 - Episodic Memory
gnome-terminal --tab --title="Episodic Memory" -- bash -c "cd $BASE_PATH/episodic_memory && python3 service.py; exec bash" &

# Terminal 5 - API Server Bridge
gnome-terminal --tab --title="API Server" -- bash -c "cd /home/grinnling/Development/CODE_IMPLEMENTATION && python3 api_server_bridge.py; exec bash" &

# Terminal 6 - React UI
gnome-terminal --tab --title="React UI" -- bash -c "export PATH=/home/grinnling/.nvm/versions/node/v22.17.1/bin:\$PATH && cd /home/grinnling/Development/CODE_IMPLEMENTATION && npm start; exec bash" &

sleep 2  # Give terminals time to open

echo "✅ Services starting in separate terminals..."
echo ""
echo "Service URLs:"
echo "  Redis:            localhost:6379"
echo "  React UI:         http://localhost:3000"
echo "  API Server:       http://localhost:8000"
echo "  Working Memory:   http://localhost:5001"
echo "  Memory Curator:   http://localhost:8004"
echo "  MCP Logger:       http://localhost:8001"
echo "  Episodic Memory:  http://localhost:8005"
echo ""
echo "All services launched! Check the terminal tabs above."
echo "Press Enter to close this window..."
read