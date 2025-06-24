/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncResponse } from './SyncResponse';
/**
 * Response model for sync history.
 */
export type SyncHistoryResponse = {
    /**
     * List of sync operations
     */
    syncs?: Array<SyncResponse>;
    /**
     * Total number of sync operations
     */
    total_count: number;
    /**
     * Current page number
     */
    page: number;
    /**
     * Number of syncs per page
     */
    page_size: number;
};

