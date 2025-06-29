# PowerShell script for delta sync
# Usage: .\scripts\run-delta-sync.ps1

Write-Host "[DELTA SYNC]" -ForegroundColor Cyan

# Check if Docker containers are running
$backendRunning = docker ps --format "table {{.Names}}" | Select-String "rag_backend"
if (-not $backendRunning) {
    Write-Host "ERROR: Backend container not running" -ForegroundColor Red
    Write-Host "TIP: Run docker-compose up -d" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Run the delta sync script
Write-Host "Processing..." -ForegroundColor Yellow

$output = docker exec rag_backend python scripts/delta-sync.py 2>$null
$cleanOutput = $output | Where-Object { $_ -match "tenants processed|Files processed|Complete|ERROR|SUCCESS|Found.*directories|valid tenants" }

$cleanOutput | ForEach-Object {
    if ($_ -match "ERROR|Failed") {
        Write-Host $_ -ForegroundColor Red
    } elseif ($_ -match "SUCCESS|Complete|Found") {
        Write-Host $_ -ForegroundColor Green
    } elseif ($_ -match "WARNING") {
        Write-Host $_ -ForegroundColor Yellow
    } else {
        Write-Host $_
    }
}

Write-Host "Complete!" -ForegroundColor Green
Read-Host "Press Enter to continue"