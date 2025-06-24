/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response model for sync status.
 */
export type SyncStatusResponse = {
    /**
     * Tenant identifier
     */
    tenant_id: string;
    /**
     * Whether sync is enabled
     */
    sync_enabled: boolean;
    /**
     * Last sync timestamp
     */
    last_sync_time?: (string | null);
    /**
     * Whether last sync was successful
     */
    last_sync_success?: (boolean | null);
    /**
     * Sync interval in minutes
     */
    sync_interval_minutes: number;
    /**
     * Whether file watcher is active
     */
    file_watcher_active: boolean;
    /**
     * Number of pending changes
     */
    pending_changes?: number;
    /**
     * Current sync status
     */
    current_status: string;
    /**
     * The ID of the currently active sync, if any
     */
    active_sync_id?: (string | null);
};

