#!/bin/bash

# Docker Run Script for takedown.email
# This script builds and runs the takedown.email application in Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 takedown.email Docker Deployment Script${NC}"
echo "============================================"

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

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_warning "Docker Compose is not installed. Installing docker-compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create data directory
print_status "Creating data directory..."
mkdir -p data

# Copy environment example if .env doesn't exist
if [ ! -f .env ]; then
    print_status "Creating .env file from example..."
    cp env.example .env
    print_warning "Please edit .env file with your configuration before running in production!"
fi

# Build the Docker image
print_status "Building Docker image..."
docker build -t takedown-email:latest .

# Check if build was successful
if [ $? -eq 0 ]; then
    print_status "Docker image built successfully!"
else
    print_error "Docker build failed!"
    exit 1
fi

# Run the container
print_status "Starting takedown.email container..."

# Stop existing container if running
docker stop takedown-email-app 2>/dev/null || true
docker rm takedown-email-app 2>/dev/null || true

# Run new container
docker run -d \
    --name takedown-email-app \
    --restart unless-stopped \
    -p 5000:5000 \
    -v "$(pwd)/data:/app/data" \
    --env-file .env \
    takedown-email:latest

# Check if container is running
sleep 5
if docker ps | grep -q takedown-email-app; then
    print_status "Container started successfully!"
    echo ""
    echo -e "${GREEN}🎉 takedown.email is now running!${NC}"
    echo -e "${BLUE}📍 Access the application at: http://localhost:5000${NC}"
    echo -e "${BLUE}🔧 Admin Panel: http://localhost:5000/security-dashboard-x9k2m8p7q4w1${NC}"
    echo ""
    echo "Useful commands:"
    echo "  View logs:     docker logs -f takedown-email-app"
    echo "  Stop app:      docker stop takedown-email-app"
    echo "  Restart app:   docker restart takedown-email-app"
    echo "  Remove app:    docker rm -f takedown-email-app"
else
    print_error "Container failed to start!"
    echo "Check logs with: docker logs takedown-email-app"
    exit 1
fi
