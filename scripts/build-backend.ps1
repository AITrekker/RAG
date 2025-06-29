# Build backend container with cache mounts
Write-Host "Building backend container with cache mounts..." -ForegroundColor Green

docker build -f docker/Dockerfile.backend.cached . --tag rag-backend:latest

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backend build completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Backend build failed!" -ForegroundColor Red
    exit 1
} 