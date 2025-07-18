#!/bin/bash
cd ~/Development/docker_agent_environment

# 1. Backup first
cp docker-compose.yml docker-compose.yml.backup

# 2. Add the missing networks section
cat >> docker-compose.yml << 'EOF'

networks:
  agent-network:
    driver: bridge
EOF

# 3. Remove the obsolete version line (optional - just removes the warning)
sed -i '/^version:/d' docker-compose.yml

# 4. Test the fix
echo "Testing the fix..."
docker compose config >/dev/null && echo "✅ YAML is now valid!" || echo "❌ Still has issues"

# 5. Check what it looks like now
echo ""
echo "Checking current container status:"
docker compose ps