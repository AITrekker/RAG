/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response model for sync metrics.
 */
export type SyncMetricsResponse = {
    /**
     * Tenant identifier
     */
    tenant_id: string;
    /**
     * Total number of syncs
     */
    total_syncs: number;
    /**
     * Number of successful syncs
     */
    successful_syncs: number;
    /**
     * Number of failed syncs
     */
    failed_syncs: number;
    /**
     * Average sync duration in seconds
     */
    average_duration: number;
    /**
     * Total files processed
     */
    total_files_processed: number;
    /**
     * Total number of errors
     */
    total_errors: number;
    /**
     * Last sync timestamp
     */
    last_sync_time?: (string | null);
    /**
     * Success rate percentage
     */
    success_rate: number;
};

