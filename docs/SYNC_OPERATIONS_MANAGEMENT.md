# Enterprise Sync Operations Management

## Overview

The new sync operations management system provides enterprise-level reliability and monitoring for file synchronization operations. It addresses the issue of sync operations getting stuck in a "running" state by implementing multiple layers of protection and monitoring.

## Key Features

### 1. Heartbeat Monitoring
- Each sync operation sends periodic heartbeats every 30 seconds
- Heartbeats indicate that the operation is actively progressing
- Stale heartbeats (>90 seconds old) indicate a stuck operation

### 2. Adaptive Timeouts
- Timeout calculation based on workload size: `base_timeout + (file_count * per_file_timeout)`
- Default: 5 minutes base + 10 seconds per file
- Configurable minimum (5 min) and maximum (2 hours) limits
- Prevents operations from running indefinitely

### 3. Progress Tracking
- Real-time progress updates with stages:
  - `initializing` - Setting up sync operation
  - `detecting_changes` - Scanning for file changes
  - `processing_files` - Processing individual files
  - `updating_embeddings` - Updating vector database
  - `finalizing` - Completing operation
- Progress percentage (0-100%)
- Current file index and total file count

### 4. Tenant-Level Locking
- Only one sync operation per tenant at a time
- Prevents concurrent operations that could cause data corruption
- Intelligent conflict resolution:
  - If existing sync is stuck → automatically clean up and start new sync
  - If existing sync is active → return conflict with progress information

### 5. Multi-Layer Cleanup System

#### Layer 1: In-Process Timeout
- Uses `asyncio.wait_for` with calculated timeout
- Immediate failure and cleanup on timeout

#### Layer 2: Background Heartbeat Monitor
- Checks every 5 minutes for operations with stale heartbeats
- Marks stuck operations as failed automatically

#### Layer 3: Manual Cleanup
- API endpoint `/api/v1/sync/cleanup` for manual cleanup
- Frontend "Cleanup Stuck Syncs" button
- Useful for troubleshooting and recovery

## API Changes

### Enhanced Status Response
```json
{
  "latest_sync": {
    "id": "uuid",
    "status": "running",
    "started_at": "2024-01-01T10:00:00Z",
    "completed_at": null,
    "files_processed": 5,
    "error_message": null,
    "progress": {
      "stage": "processing_files",
      "percentage": 45.2,
      "current_file": 9,
      "total_files": 20
    },
    "heartbeat_at": "2024-01-01T10:05:30Z",
    "expected_duration_seconds": 600
  },
  "file_status": {
    "pending": 2,
    "processing": 1,
    "failed": 0,
    "total": 25
  }
}
```

### New Sync Trigger Response
- Returns conflict information instead of rejecting concurrent requests
- Provides progress details for running operations

### New Cleanup Endpoint
```bash
POST /api/v1/sync/cleanup
```
Returns count of cleaned up operations.

## Database Schema Changes

New columns added to `sync_operations` table:
- `heartbeat_at` - Last heartbeat timestamp
- `expected_duration_seconds` - Calculated timeout for this operation
- `progress_stage` - Current stage of sync operation
- `progress_percentage` - Progress percentage (0-100)
- `total_files_to_process` - Total files to be processed
- `current_file_index` - Current file being processed

## Frontend Enhancements

### Enhanced Sync Dashboard
- Real-time progress bar with percentage
- Stage indicator (initializing, processing files, etc.)
- File progress (5 of 20 files)
- Heartbeat timestamp
- Expected duration display
- Cleanup button for stuck operations

### Improved User Experience
- No more mysterious "stuck" syncs
- Clear progress indication
- Automatic conflict resolution
- Manual cleanup option

## Configuration

Environment variables for tuning:
```bash
# Sync operation timeouts
SYNC_BASE_TIMEOUT_SECONDS=300        # 5 minutes base
SYNC_PER_FILE_TIMEOUT_SECONDS=10     # 10 seconds per file
SYNC_MAX_TIMEOUT_SECONDS=7200        # 2 hours maximum
SYNC_MIN_TIMEOUT_SECONDS=300         # 5 minutes minimum

# Heartbeat and cleanup intervals
SYNC_HEARTBEAT_INTERVAL_SECONDS=30   # Heartbeat every 30 seconds
SYNC_CLEANUP_INTERVAL_SECONDS=300    # Cleanup check every 5 minutes
```

## Migration

1. **Database Migration**: Run `scripts/migrate_sync_operations.sql` to add new columns
2. **Application Restart**: Restart the backend to enable new sync management
3. **Background Tasks**: Background cleanup tasks start automatically

## Monitoring and Troubleshooting

### Health Checks
- Background tasks status available in logs
- System health monitoring includes sync operation tracking
- Performance metrics track sync operation duration and success rates

### Troubleshooting Stuck Syncs
1. Check frontend sync dashboard for real-time status
2. Look at heartbeat timestamp - if >90 seconds old, operation is stuck
3. Use "Cleanup Stuck Syncs" button to manually resolve
4. Check logs for error messages and timeout information

### Key Log Messages
- `Started sync {sync_id} for tenant {tenant_id} (timeout: {duration}s)` - Sync started
- `Sync {sync_id} completed successfully` - Sync completed
- `Sync {sync_id} timed out` - Sync exceeded calculated timeout
- `Cleaned up {count} stuck sync operations` - Background cleanup ran

## Benefits

1. **Reliability**: No more permanently stuck sync operations
2. **Transparency**: Full visibility into sync progress and health
3. **User Experience**: Clear progress indication and automatic conflict resolution
4. **Enterprise-Grade**: Configurable timeouts, monitoring, and automatic cleanup
5. **Data Integrity**: Tenant-level locking prevents concurrent modifications
6. **Scalability**: Adaptive timeouts handle varying workload sizes

This system ensures that sync operations are robust, transparent, and self-healing, providing an enterprise-level solution for file synchronization management. 