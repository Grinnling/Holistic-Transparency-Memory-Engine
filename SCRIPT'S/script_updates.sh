#!/bin/bash
# Docker Compose V2 Script Updates
# These are the exact changes needed for your scripts

echo "🔧 UPDATING SCRIPTS FOR DOCKER COMPOSE V2"
echo "=========================================="

cd ~/Development/docker_agent_environment/scripts

echo "📝 Backing up original scripts..."
cp start_environment.sh start_environment.sh.backup
cp stop_environment.sh stop_environment.sh.backup

echo "✏️  Updating start_environment.sh..."
cat > start_environment.sh << 'EOF'
#!/bin/bash
# Script to start the Docker environment with original model files
cd "$(dirname "$0")"
echo "Starting Docker environment using original model files..."
echo "NOTE: The encrypted storage is NOT being used due to compatibility issues."
docker compose up -d
echo "Docker environment started successfully."
echo "You can view the logs with: docker compose logs -f"
echo "To stop the environment, use: docker compose down"
EOF

echo "✏️  Updating stop_environment.sh..."
cat > stop_environment.sh << 'EOF'
#!/bin/bash

# Script to stop the Docker environment and unmount encrypted storage

# Change to the project directory
cd "$(dirname "$0")"

# Stop the Docker environment
echo "Stopping Docker environment..."
docker compose down

# Check if Docker was stopped successfully
if [ $? -ne 0 ]; then
    echo "Failed to stop Docker environment properly. Continue with caution."
else
    echo "Docker environment stopped successfully."
fi

# Ask if user wants to unmount the encrypted container
read -p "Do you want to unmount the encrypted model container? (y/n): " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    echo "Unmounting encrypted model container..."
    ./unmount_encrypted_model.sh
    echo "Cleanup complete."
else
    echo "Encrypted model container remains mounted."
    echo "You can unmount it later with: ./unmount_encrypted_model.sh"
fi
EOF

echo "🔧 Making scripts executable..."
chmod +x start_environment.sh
chmod +x stop_environment.sh

echo "✅ SCRIPT UPDATES COMPLETED!"
echo ""
echo "📋 Changes made:"
echo "   start_environment.sh: docker-compose → docker compose"
echo "   stop_environment.sh:  docker-compose → docker compose"
echo ""
echo "📁 Backups saved as:"
echo "   start_environment.sh.backup"
echo "   stop_environment.sh.backup"
echo ""
echo "🎯 Ready for Docker Compose V2 upgrade!"