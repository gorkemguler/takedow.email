#!/bin/bash

# Docker Fix Script for takedown.email
# This script fixes the Docker container and rebuilds it

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 takedown.email Docker Fix Script${NC}"
echo "=========================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Stop and remove existing container
print_status "Stopping existing container..."
docker stop takedown-email-app 2>/dev/null || true
docker rm takedown-email-app 2>/dev/null || true

# Remove old image
print_status "Removing old image..."
docker rmi takedown-email:latest 2>/dev/null || true

# Build new image with fix
print_status "Building new Docker image..."
docker build -t takedown-email:latest . --no-cache

# Check if build was successful
if [ $? -eq 0 ]; then
    print_status "Docker image built successfully!"
else
    print_error "Docker build failed!"
    exit 1
fi

# Create data directory with proper permissions
mkdir -p data
chmod 755 data
echo "Created data directory with proper permissions"

# Create environment file if not exists
if [ ! -f .env ]; then
    print_status "Creating .env file..."
    cat > .env << EOF
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=takedown-email-super-secret-key-$(date +%s)
DATABASE_PATH=/app/data/takedown_logs.db
ADMIN_USERNAME=secadmin
ADMIN_PASSWORD=admin123
ADMIN_URL_PATH=security-dashboard-x9k2m8p7q4w1
HOST=0.0.0.0
PORT=5000
EOF
fi

# Run the container
print_status "Starting takedown.email container..."
docker run -d \
    --name takedown-email-app \
    --restart unless-stopped \
    -p 5000:5000 \
    -v "$(pwd)/data:/app/data" \
    --env-file .env \
    takedown-email:latest

# Wait for container to start
print_status "Waiting for container to start..."
sleep 10

# Check if container is running
if docker ps | grep -q takedown-email-app; then
    print_status "Container started successfully!"
    
    # Test the application
    print_status "Testing application..."
    sleep 5
    
    if curl -s http://localhost:5000/ | grep -q "takedown.email"; then
        echo ""
        echo -e "${GREEN}✅ takedown.email is working perfectly!${NC}"
        echo -e "${BLUE}📍 Access: http://localhost:5000${NC}"
        echo -e "${BLUE}🔧 Admin: http://localhost:5000/security-dashboard-x9k2m8p7q4w1${NC}"
        echo -e "${BLUE}👤 Credentials: secadmin / admin123${NC}"
    else
        print_warning "Application started but may not be fully functional"
        echo "Check logs with: docker logs takedown-email-app"
    fi
else
    print_error "Container failed to start!"
    echo "Check logs with: docker logs takedown-email-app"
    exit 1
fi

echo ""
echo "Useful commands:"
echo "  View logs:     docker logs -f takedown-email-app"
echo "  Stop app:      docker stop takedown-email-app"
echo "  Restart app:   docker restart takedown-email-app"
echo "  Remove app:    docker rm -f takedown-email-app"
