#!/bin/bash
# Enhanced Package Review Checklist with Cross-Contamination Detection
# Based on lessons learned from requests 2.32.0 + docker-compose conflict

PACKAGE_NAME="${1:-}"
if [ -z "$PACKAGE_NAME" ]; then
    echo "Usage: $0 <package_name>"
    exit 1
fi

echo "🔍 ENHANCED PACKAGE REVIEW: $PACKAGE_NAME"
echo "=========================================="

# Step 1: Basic Package Information
echo ""
echo "📦 STEP 1: BASIC PACKAGE INFO"
echo "Package: $PACKAGE_NAME"
if command -v apt &> /dev/null; then
    apt show "$PACKAGE_NAME" 2>/dev/null | grep -E "(Version|Depends|Conflicts)" || echo "Not in apt repositories"
fi

if command -v pip3 &> /dev/null; then
    pip3 show "$PACKAGE_NAME" 2>/dev/null | grep -E "(Version|Requires|Required-by)" || echo "Not installed via pip"
fi

# Step 2: Dependency Conflict Detection
echo ""
echo "⚠️  STEP 2: DEPENDENCY CONFLICT ANALYSIS"

# Check for known problematic packages
KNOWN_CONFLICT_PACKAGES=("requests" "urllib3" "docker" "docker-compose" "numpy" "tensorflow" "pytorch")

echo "Checking if $PACKAGE_NAME affects known conflict-prone packages..."
for conflict_pkg in "${KNOWN_CONFLICT_PACKAGES[@]}"; do
    if pip3 show "$PACKAGE_NAME" 2>/dev/null | grep -q "$conflict_pkg"; then
        echo "⚠️  POTENTIAL CONFLICT: $PACKAGE_NAME depends on $conflict_pkg"
        echo "   Action needed: Check version compatibility"
    fi
done

# Step 3: Version Compatibility Matrix Check
echo ""
echo "🔄 STEP 3: VERSION COMPATIBILITY CHECK"

case "$PACKAGE_NAME" in
    "requests")
        echo "📋 REQUESTS VERSION COMPATIBILITY:"
        echo "   ✅ requests <= 2.31.x: Compatible with docker-compose v1"
        echo "   ❌ requests >= 2.32.0: BREAKS docker-compose v1"
        echo "   🎯 Current system compatibility:"
        docker-compose --version 2>/dev/null && echo "      docker-compose v1 detected - AVOID requests >= 2.32.0"
        docker compose version 2>/dev/null && echo "      docker-compose v2 detected - Any requests version OK"
        ;;
    "urllib3")
        echo "📋 URLLIB3 VERSION COMPATIBILITY:"
        echo "   ✅ urllib3 < 2.0: Compatible with older docker-py"
        echo "   ❌ urllib3 >= 2.0: Requires docker-py >= 7.1.0"
        echo "   🎯 Current system compatibility:"
        python3 -c "import docker; print(f'      docker-py: {docker.__version__}')" 2>/dev/null || echo "      docker-py: NOT INSTALLED"
        ;;
    "docker"|"docker-py")
        echo "📋 DOCKER-PY VERSION COMPATIBILITY:"
        echo "   ❌ docker-py < 7.1.0: BREAKS with urllib3 >= 2.0"
        echo "   ✅ docker-py >= 7.1.0: Compatible with urllib3 >= 2.0"
        ;;
    *)
        echo "No specific compatibility matrix for $PACKAGE_NAME"
        echo "Checking general dependency conflicts..."
        ;;
esac

# Step 4: Cross-Contamination Risk Assessment
echo ""
echo "🧪 STEP 4: CROSS-CONTAMINATION RISK ASSESSMENT"

echo "Checking for mixed installation sources..."
SYSTEM_PACKAGES=$(apt list --installed 2>/dev/null | grep -E "python3-$PACKAGE_NAME|python-$PACKAGE_NAME" | wc -l)
PIP_PACKAGES=$(pip3 list 2>/dev/null | grep -i "$PACKAGE_NAME" | wc -l)

if [ "$SYSTEM_PACKAGES" -gt 0 ] && [ "$PIP_PACKAGES" -gt 0 ]; then
    echo "🚨 HIGH RISK: Both system and pip installations detected"
    echo "   System packages: $SYSTEM_PACKAGES"
    echo "   Pip packages: $PIP_PACKAGES"
    echo "   Recommendation: Choose ONE installation method"
elif [ "$SYSTEM_PACKAGES" -gt 0 ]; then
    echo "✅ LOW RISK: Only system packages detected"
elif [ "$PIP_PACKAGES" -gt 0 ]; then
    echo "✅ LOW RISK: Only pip packages detected"
else
    echo "ℹ️  Package not currently installed"
fi

# Step 5: Installation Impact Simulation
echo ""
echo "🎮 STEP 5: INSTALLATION IMPACT SIMULATION"
echo "Simulating installation impact..."

if command -v pip3 &> /dev/null; then
    echo "Dependencies that would be installed/upgraded:"
    pip3 install --dry-run "$PACKAGE_NAME" 2>/dev/null | grep -E "(Would install|Would upgrade)" || echo "No pip simulation available"
fi

# Step 6: Recommendations
echo ""
echo "✅ STEP 6: RECOMMENDATIONS"

echo "Based on analysis:"
echo "1. Review dependency conflicts above"
echo "2. Test in virtual environment first"
echo "3. Document any version pins needed"
echo "4. Add to package compatibility matrix"
echo "5. Update conflict detection rules if needed"

# Step 7: Testing Commands
echo ""
echo "🧪 STEP 7: POST-INSTALLATION TESTING COMMANDS"
echo "After installation, run these tests:"

case "$PACKAGE_NAME" in
    "requests"|"urllib3")
        echo "   docker-compose --version"
        echo "   python3 -c 'import docker; docker.from_env().ping()'"
        ;;
    "docker"|"docker-py")
        echo "   docker version"
        echo "   python3 -c 'import docker; print(docker.__version__)'"
        ;;
    *)
        echo "   python3 -c 'import $PACKAGE_NAME; print(\"Import successful\")'"
        ;;
esac

echo ""
echo "📝 PACKAGE REVIEW COMPLETE"
echo "Document findings in: ~/security_docs/package_reviews/$PACKAGE_NAME-$(date +%Y%m%d).md"