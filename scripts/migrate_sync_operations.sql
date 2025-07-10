-- Migration script to add heartbeat and progress tracking to sync_operations table
-- Run this script to upgrade existing database schema

BEGIN;

-- Add new columns for heartbeat and progress tracking
ALTER TABLE sync_operations 
ADD COLUMN heartbeat_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN expected_duration_seconds INTEGER,
ADD COLUMN progress_stage VARCHAR(50),
ADD COLUMN progress_percentage FLOAT,
ADD COLUMN total_files_to_process INTEGER,
ADD COLUMN current_file_index INTEGER;

-- Add constraints for the new columns
ALTER TABLE sync_operations 
ADD CONSTRAINT check_progress_range CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
ADD CONSTRAINT check_current_file_index CHECK (current_file_index >= 0),
ADD CONSTRAINT check_total_files CHECK (total_files_to_process >= 0);

-- Create new indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_sync_operations_heartbeat ON sync_operations(status, heartbeat_at);
CREATE INDEX IF NOT EXISTS idx_sync_operations_progress ON sync_operations(tenant_id, status, progress_stage);

-- Update existing running operations to have an initial heartbeat
UPDATE sync_operations 
SET heartbeat_at = started_at,
    progress_stage = 'running',
    progress_percentage = 0.0
WHERE status = 'running' AND heartbeat_at IS NULL;

COMMIT;

-- Verification queries
-- Check that new columns were added successfully
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'sync_operations' 
AND column_name IN ('heartbeat_at', 'expected_duration_seconds', 'progress_stage', 'progress_percentage', 'total_files_to_process', 'current_file_index');

-- Check that constraints were added
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'sync_operations' 
AND constraint_name IN ('check_progress_range', 'check_current_file_index', 'check_total_files');

-- Check that indexes were created
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'sync_operations' 
AND indexname IN ('idx_sync_operations_heartbeat', 'idx_sync_operations_progress'); 