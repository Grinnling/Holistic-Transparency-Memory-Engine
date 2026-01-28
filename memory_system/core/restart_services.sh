#!/bin/bash

# Memory System Cluster Restart Script
# Cleanly stops all services, waits for ports to free, then restarts
# Used by: admin panel cluster restart, manual restart

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "Memory System Cluster Restart"
echo "============================================"
echo ""

# Stop all services
echo ">>> Stopping all services..."
"$SCRIPT_DIR/stop_services.sh"

echo ""
echo ">>> Waiting for cleanup..."
sleep 2

# Verify all ports are free before starting
echo ">>> Verifying ports are free..."
ports_busy=false
for port in 3000 8000 5001 8004 8001 8005; do
    if lsof -ti:$port >/dev/null 2>&1; then
        echo "  Port $port still busy, waiting..."
        ports_busy=true
    fi
done

if [ "$ports_busy" = true ]; then
    echo ">>> Some ports still busy, waiting 5 more seconds..."
    sleep 5
fi

echo ""
echo ">>> Starting all services..."
"$SCRIPT_DIR/start_services_tmux.sh"

echo ""
echo "============================================"
echo "Cluster restart complete"
echo "============================================"
