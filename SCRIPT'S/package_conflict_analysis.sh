#!/bin/bash
# Package Conflict Detective Script
# Identifies the exact packages causing docker-compose urllib3 conflicts

echo "🔍 DOCKER-COMPOSE URLLIB3 CONFLICT ANALYSIS"
echo "=============================================="

# Make script executable and save to temp location for easy running
SCRIPT_PATH="/tmp/conflict_analysis.sh"

echo ""
echo "📦 CHECKING INSTALLED PACKAGE VERSIONS..."

# Check requests version
echo "Current requests version:"
python3 -c "import requests; print(f'  requests: {requests.__version__}')" 2>/dev/null || echo "  requests: NOT INSTALLED"

# Check urllib3 version  
echo "Current urllib3 version:"
python3 -c "import urllib3; print(f'  urllib3: {urllib3.__version__}')" 2>/dev/null || echo "  urllib3: NOT INSTALLED"

# Check docker-py version
echo "Current docker-py version:"
python3 -c "import docker; print(f'  docker: {docker.__version__}')" 2>/dev/null || echo "  docker: NOT INSTALLED"

# Check docker-compose version
echo "Current docker-compose version:"
docker-compose --version 2>/dev/null || echo "  docker-compose: NOT WORKING"

echo ""
echo "🎯 KNOWN PROBLEMATIC COMBINATIONS:"
echo "❌ requests >= 2.32.0 + docker-compose v1"
echo "❌ urllib3 >= 2.0.0 + docker-py < 7.1.0"
echo "❌ System urllib3 + pip urllib3 mixed installs"

echo ""
echo "✅ KNOWN WORKING COMBINATIONS:"
echo "✅ requests <= 2.31.0 + docker-compose v1"
echo "✅ docker-compose v2 (any recent requests version)"
echo "✅ docker-py >= 7.1.0 + urllib3 >= 2.0.0"

echo ""
echo "🔍 CHECKING YOUR SPECIFIC SITUATION..."

# Check if we have the known bad combination
REQUESTS_VERSION=$(python3 -c "import requests; print(requests.__version__)" 2>/dev/null || echo "unknown")
URLLIB3_VERSION=$(python3 -c "import urllib3; print(urllib3.__version__)" 2>/dev/null || echo "unknown")

if [[ $REQUESTS_VERSION == 2.32.* ]] || [[ $REQUESTS_VERSION > "2.31.9" ]]; then
    echo "⚠️  FOUND ISSUE: requests $REQUESTS_VERSION is >= 2.32.0"
    echo "   This breaks docker-compose v1"
fi

if [[ $URLLIB3_VERSION == 2.* ]]; then
    echo "⚠️  FOUND ISSUE: urllib3 $URLLIB3_VERSION is >= 2.0.0"
    echo "   This requires docker-py >= 7.1.0"
fi

echo ""
echo "📋 PACKAGE INSTALLATION SOURCES:"
pip3 show requests | grep -E "(Version|Location)" 2>/dev/null || echo "requests: Not via pip"
pip3 show urllib3 | grep -E "(Version|Location)" 2>/dev/null || echo "urllib3: Not via pip"
apt list --installed | grep -E "(python3-requests|python3-urllib3)" 2>/dev/null || echo "No system Python packages found"

echo ""
echo "🎯 RECOMMENDED FIXES:"
echo "1. UPGRADE TO DOCKER COMPOSE V2 (recommended)"
echo "   sudo apt remove docker-compose"
echo "   sudo apt install docker-compose-v2"
echo ""
echo "2. PIN REQUESTS VERSION (temporary fix)"
echo "   pip3 install 'requests==2.31.0'"
echo ""
echo "3. UPGRADE DOCKER-PY (if using docker-py directly)"
echo "   pip3 install 'docker>=7.1.0'"