@echo off
REM Shortcut to run delta sync in Docker container (Windows)

echo [DELTA SYNC]

REM Check if Docker containers are running
docker ps | findstr "rag_backend" >nul
if errorlevel 1 (
    echo ERROR: Backend container not running
    echo TIP: Run docker-compose up -d first
    pause
    exit /b 1
)

REM Run the delta sync script with clean output
echo Processing...
docker exec rag_backend python scripts/delta-sync.py 2>nul | findstr /C:"tenants processed" /C:"Files processed" /C:"Complete" /C:"ERROR" /C:"SUCCESS"

echo Complete!
pause