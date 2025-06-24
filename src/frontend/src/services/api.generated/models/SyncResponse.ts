/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocumentSyncInfo } from './DocumentSyncInfo';
import type { SyncStatus } from './SyncStatus';
import type { SyncType } from './SyncType';
/**
 * Response model for sync operations.
 */
export type SyncResponse = {
    /**
     * Unique sync operation identifier
     */
    sync_id: string;
    /**
     * Tenant identifier
     */
    tenant_id: string;
    /**
     * Current sync status
     */
    status: SyncStatus;
    /**
     * Type of sync operation
     */
    sync_type: SyncType;
    /**
     * Sync start timestamp
     */
    started_at: string;
    /**
     * Sync completion timestamp
     */
    completed_at?: (string | null);
    /**
     * Total number of files to process
     */
    total_files?: number;
    /**
     * Number of files processed
     */
    processed_files?: number;
    /**
     * Number of successfully processed files
     */
    successful_files?: number;
    /**
     * Number of failed files
     */
    failed_files?: number;
    /**
     * Total number of chunks created
     */
    total_chunks?: number;
    /**
     * Total processing time
     */
    processing_time?: (number | null);
    /**
     * Error message if failed
     */
    error_message?: (string | null);
    /**
     * Processed documents
     */
    documents?: Array<DocumentSyncInfo>;
};

