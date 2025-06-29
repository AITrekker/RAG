@echo off
echo [DELTA SYNC]
echo Checking containers...

docker ps | findstr "rag_backend" >nul
if errorlevel 1 (
    echo ERROR: Backend container not running
    echo TIP: Run docker-compose up -d
    pause
    exit /b 1
)

echo Running sync...
docker exec rag_backend python scripts/delta-sync.py

echo.
echo Done!
pause