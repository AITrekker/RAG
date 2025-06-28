/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncResponse } from '../models/SyncResponse';
import type { SyncTriggerRequest } from '../models/SyncTriggerRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SyncService {
    /**
     * Trigger Manual Sync
     * Manually triggers a delta synchronization for the current tenant.
     *
     * This process will run in the background and perform the following steps:
     * 1. Scan the tenant's data source.
     * 2. Compare the current state with the last known state from Qdrant.
     * 3. Process new, modified, and deleted files.
     * @param requestBody
     * @returns SyncResponse Successful Response
     * @throws ApiError
     */
    public static triggerManualSyncApiV1SyncTriggerPost(
        requestBody: SyncTriggerRequest,
    ): CancelablePromise<SyncResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/sync/trigger',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Sync Status
     * Retrieves the status of a specific synchronization operation.
     * @param syncId
     * @returns SyncResponse Successful Response
     * @throws ApiError
     */
    public static getSyncStatusApiV1SyncStatusSyncIdGet(
        syncId: string,
    ): CancelablePromise<SyncResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/status/{sync_id}',
            path: {
                'sync_id': syncId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
