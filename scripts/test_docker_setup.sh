#!/bin/bash

# Test Docker Compose Setup for RAG Platform
# This script verifies that all services are working correctly

echo "🐋 Testing RAG Platform Docker Setup..."
echo "======================================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

# Check for NVIDIA Docker support (for GPU)
if command -v nvidia-docker >/dev/null 2>&1; then
    echo "✅ NVIDIA Docker support detected"
else
    echo "⚠️  NVIDIA Docker not found. GPU acceleration may not work."
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up --build -d

# Wait for services to start
echo "⏳ Waiting for services to initialize..."
sleep 30

# Check service health
echo "🔍 Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U rag_user >/dev/null 2>&1; then
    echo "✅ PostgreSQL is healthy"
else
    echo "❌ PostgreSQL is not responding"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis is healthy"
else
    echo "❌ Redis is not responding"
fi

# Check Chroma (may take longer to start)
sleep 10
if curl -s http://localhost:8001/api/v1/heartbeat >/dev/null 2>&1; then
    echo "✅ Chroma is healthy"
else
    echo "⚠️  Chroma may still be starting..."
fi

# Check backend health endpoint (will be created later)
echo "⚠️  Backend health check will be available after implementing the health endpoint"

# Check frontend (will be available after implementing)
echo "⚠️  Frontend check will be available after implementing the React app"

# Check Nginx
if curl -s http://localhost >/dev/null 2>&1; then
    echo "✅ Nginx is responding"
else
    echo "❌ Nginx is not responding"
fi

echo ""
echo "📊 Service Status Summary:"
echo "========================="
docker-compose ps

echo ""
echo "🌐 Access URLs:"
echo "==============="
echo "Frontend:     http://localhost"
echo "Backend API:  http://localhost/api/"
echo "Nginx:        http://localhost"
echo "Chroma DB:    http://localhost:8001"
echo "PostgreSQL:   localhost:5432"
echo "Redis:        localhost:6379"

echo ""
echo "📝 Next Steps:"
echo "=============="
echo "1. Implement backend FastAPI application"
echo "2. Implement frontend React application"
echo "3. Test end-to-end functionality"
echo ""
echo "To view logs: docker-compose logs -f [service_name]"
echo "To stop:      docker-compose down" 