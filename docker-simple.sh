#!/bin/bash

# Simple Docker Test Script
echo "🐳 Simple Docker Test for takedown.email"
echo "========================================"

# Stop and remove existing container
echo "Stopping existing container..."
docker stop takedown-email-app 2>/dev/null || true
docker rm takedown-email-app 2>/dev/null || true

# Create data directory
echo "Creating data directory..."
mkdir -p data
chmod 777 data

# Build image
echo "Building Docker image..."
docker build -t takedown-email:latest . --no-cache

# Run container
echo "Starting container..."
docker run -d \
    --name takedown-email-app \
    --restart unless-stopped \
    -p 5000:5000 \
    -v "$(pwd)/data:/app/data" \
    -e DATABASE_PATH=/app/data/takedown_logs.db \
    -e FLASK_ENV=production \
    -e FLASK_DEBUG=0 \
    takedown-email:latest

echo "Waiting for container to start..."
sleep 15

# Check logs
echo "Checking logs..."
docker logs takedown-email-app

# Test if running
echo "Testing application..."
if curl -s http://localhost:5000/ | grep -q "takedown.email"; then
    echo "✅ SUCCESS: Application is running!"
    echo "🌐 Access: http://localhost:5000"
    echo "🔧 Admin: http://localhost:5000/security-dashboard-x9k2m8p7q4w1"
else
    echo "❌ FAILED: Application not responding"
fi

echo ""
echo "Container status:"
docker ps | grep takedown-email-app || echo "Container not running"
