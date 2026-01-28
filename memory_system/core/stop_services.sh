#!/bin/bash

# Memory System Service Shutdown Script
# Graceful shutdown in reverse order with port verification
# Used by: manual shutdown, cluster restart from admin panel

# Validate dependencies
if ! command -v lsof &> /dev/null; then
    echo "ERROR: lsof is required but not installed"
    echo "Install with: sudo apt install lsof"
    exit 1
fi

echo "Stopping Memory System Services..."

# Function to stop a service by port and wait for it to release
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
                echo "    $name stopped gracefully"
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
        echo "    $name stopped"
    else
        echo "  $name not running (port $port free)"
    fi
}

# Function to wait for a port to be free
wait_for_port_free() {
    local port=$1
    local name=$2
    local max_wait=10
    local waited=0

    while [ $waited -lt $max_wait ]; do
        if ! lsof -ti:$port >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done

    echo "  WARNING: Port $port ($name) still in use after ${max_wait}s"
    return 1
}

echo ""
echo "Phase 1: Frontend"
stop_by_port 3000 "React UI"

echo ""
echo "Phase 2: API Server"
stop_by_port 8000 "API Server"

echo ""
echo "Phase 3: Memory Services"
stop_by_port 5001 "Working Memory"
stop_by_port 8004 "Memory Curator"
stop_by_port 8001 "MCP Logger"
stop_by_port 8005 "Episodic Memory"

echo ""
echo "Phase 4: Redis"
if docker ps --format '{{.Names}}' | grep -q 'redis-n8n'; then
    docker stop redis-n8n > /dev/null 2>&1 && echo "  Redis container stopped" || echo "  Failed to stop Redis"
else
    echo "  Redis container not running"
fi

echo ""
echo "Phase 5: Verifying ports are free..."
all_free=true
for port in 3000 8000 5001 8004 8001 8005; do
    if lsof -ti:$port >/dev/null 2>&1; then
        echo "  WARNING: Port $port still in use"
        all_free=false
    fi
done

if [ "$all_free" = true ]; then
    echo "  All ports free"
fi

# Kill tmux session if it exists (for tmux-based setup)
if tmux has-session -t memory-system 2>/dev/null; then
    echo ""
    echo "Phase 6: Killing tmux session..."
    tmux kill-session -t memory-system
    echo "  tmux session 'memory-system' killed"
fi

echo ""
echo "All services stopped"
