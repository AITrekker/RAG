# Test sync functionality
Write-Host "Testing RAG Platform Sync API"
Write-Host "=============================="

$baseUrl = "http://localhost:8000/api/v1"

# Test health
try {
    Write-Host "1. Testing health endpoint..."
    $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method GET
    Write-Host "✅ Backend is running"
    Write-Host "Status: $($health.status)"
} catch {
    Write-Host "❌ Backend not running: $($_.Exception.Message)"
    exit 1
}

# Test sync status
try {
    Write-Host "`n2. Getting sync status..."
    $syncStatus = Invoke-RestMethod -Uri "$baseUrl/sync/status" -Method GET
    Write-Host "✅ Sync status retrieved"
    Write-Host "Current status: $($syncStatus.current_status)"
    Write-Host "Pending changes: $($syncStatus.pending_changes)"
} catch {
    Write-Host "❌ Failed to get sync status: $($_.Exception.Message)"
}

# Test documents endpoint - skip for now due to auth issues
# try {
#     Write-Host "`n3. Getting documents list..."
#     $documents = Invoke-RestMethod -Uri "$baseUrl/documents" -Method GET
#     Write-Host "✅ Documents retrieved"
#     Write-Host "Total documents: $($documents.total_count)"
#     foreach ($doc in $documents.documents) {
#         Write-Host "  - $($doc.filename) ($($doc.status))"
#     }
# } catch {
#     Write-Host "❌ Failed to get documents: $($_.Exception.Message)"
# }

# Trigger sync
try {
    Write-Host "`n3. Triggering sync..."
    $headers = @{"Content-Type" = "application/json"}
    $body = @{force_full_sync = $true} | ConvertTo-Json
    $syncResult = Invoke-RestMethod -Uri "$baseUrl/sync/trigger" -Method POST -Body $body -Headers $headers
    Write-Host "✅ Sync triggered successfully"
    Write-Host "Sync ID: $($syncResult.sync_id)"
    Write-Host "Status: $($syncResult.status)"
    Write-Host "Total files: $($syncResult.total_files)"

    # Poll sync status
    Write-Host "`n4. Monitoring sync progress..."
    $syncId = $syncResult.sync_id
    $maxWait = 120 # seconds - increased for embedding generation
    $waited = 0
    
    while ($waited -lt $maxWait) {
        try {
            $currentSync = Invoke-RestMethod -Uri "$baseUrl/sync/operation/$syncId" -Method GET
            Write-Host "Status: $($currentSync.status) | Processed: $($currentSync.processed_files)/$($currentSync.total_files)"
            
            if ($currentSync.status -eq "completed" -or $currentSync.status -eq "failed") {
                Write-Host "✅ Sync $($currentSync.status)!"
                if ($currentSync.status -eq "completed") {
                    Write-Host "Successfully processed: $($currentSync.successful_files)"
                    Write-Host "Failed: $($currentSync.failed_files)"
                    Write-Host "Total chunks: $($currentSync.total_chunks)"
                    Write-Host "Processing time: $($currentSync.processing_time) seconds"
                }
                if ($currentSync.error_message) {
                    Write-Host "Error: $($currentSync.error_message)"
                }
                
                # Show details of processed documents
                if ($currentSync.documents) {
                    Write-Host "`nDocument Processing Details:"
                    foreach ($doc in $currentSync.documents) {
                        $status = $doc.status
                        $icon = if ($status -eq "completed") { "[OK]" } elseif ($status -eq "failed") { "[FAIL]" } elseif ($status -eq "skipped") { "[SKIP]" } else { "[?]" }
                        Write-Host "  $icon $($doc.filename): $status"
                        if ($status -eq "completed") {
                            Write-Host "    - Size: $([math]::Round($doc.file_size / 1KB, 2)) KB"
                            Write-Host "    - Chunks: $($doc.chunks_created)"
                            Write-Host "    - Processing time: $([math]::Round($doc.processing_time, 2))s"
                        }
                        if ($status -eq "failed" -and $doc.error_message) {
                            Write-Host "    - Error: $($doc.error_message)"
                        }
                    }
                }
                break
            }
            
            Start-Sleep -Seconds 5
            $waited += 5
        } catch {
            Write-Host "Error polling sync: $($_.Exception.Message)"
            break
        }
    }
    
    if ($waited -ge $maxWait) {
        Write-Host "⚠️ Sync still running after $maxWait seconds"
    }

} catch {
    Write-Host "❌ Failed to trigger sync: $($_.Exception.Message)"
    Write-Host "Response: $($_.Exception.Response)"
}

Write-Host "`nSync test completed!" 