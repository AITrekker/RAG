/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncConfigRequest } from '../models/SyncConfigRequest';
import type { SyncHistoryResponse } from '../models/SyncHistoryResponse';
import type { SyncMetricsResponse } from '../models/SyncMetricsResponse';
import type { SyncResponse } from '../models/SyncResponse';
import type { SyncStatusResponse } from '../models/SyncStatusResponse';
import type { SyncTriggerRequest } from '../models/SyncTriggerRequest';
import type { WebhookConfigRequest } from '../models/WebhookConfigRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SynchronizationService {
    /**
     * Test Sync Endpoint
     * Simple test endpoint to verify sync routes are working.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static testSyncEndpointApiV1SyncTestGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/test',
        });
    }
    /**
     * Trigger Sync Simple
     * Simple POST endpoint at /sync root for frontend compatibility.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static triggerSyncSimpleApiV1SyncPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/sync/',
        });
    }
    /**
     * Trigger Manual Sync
     * Manually trigger synchronization for a tenant.
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
     * Get the current status of the synchronization service for the tenant.
     * @returns SyncStatusResponse Successful Response
     * @throws ApiError
     */
    public static getSyncStatusApiV1SyncStatusGet(): CancelablePromise<SyncStatusResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/status',
        });
    }
    /**
     * Get Sync Operation Direct
     * Get the status of a specific sync operation directly by sync ID.
     * @param syncId
     * @returns SyncResponse Successful Response
     * @throws ApiError
     */
    public static getSyncOperationDirectApiV1SyncSyncIdGet(
        syncId: string,
    ): CancelablePromise<SyncResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/{sync_id}',
            path: {
                'sync_id': syncId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Sync Operation
     * Get the status of a specific sync operation (alternative endpoint).
     * @param syncId
     * @returns SyncResponse Successful Response
     * @throws ApiError
     */
    public static getSyncOperationApiV1SyncOperationSyncIdGet(
        syncId: string,
    ): CancelablePromise<SyncResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/operation/{sync_id}',
            path: {
                'sync_id': syncId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Sync History
     * Get synchronization history for a tenant.
     * @param limit
     * @returns SyncHistoryResponse Successful Response
     * @throws ApiError
     */
    public static getSyncHistoryApiV1SyncHistoryGet(
        limit: number = 50,
    ): CancelablePromise<Array<SyncHistoryResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/history',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Sync Config
     * Get current synchronization configuration for a tenant.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getSyncConfigApiV1SyncConfigGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/config',
        });
    }
    /**
     * Update Sync Config
     * Update synchronization configuration for a tenant.
     * @param requestBody
     * @returns string Successful Response
     * @throws ApiError
     */
    public static updateSyncConfigApiV1SyncConfigPut(
        requestBody: SyncConfigRequest,
    ): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/sync/config',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Test Webhook
     * Test a webhook configuration by sending a test event.
     * @param requestBody
     * @returns string Successful Response
     * @throws ApiError
     */
    public static testWebhookApiV1SyncWebhooksTestPost(
        requestBody: WebhookConfigRequest,
    ): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/sync/webhooks/test',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Sync Metrics
     * Get synchronization metrics and analytics for a tenant.
     * @param days
     * @returns SyncMetricsResponse Successful Response
     * @throws ApiError
     */
    public static getSyncMetricsApiV1SyncMetricsGet(
        days: number = 7,
    ): CancelablePromise<SyncMetricsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sync/metrics',
            query: {
                'days': days,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Pause Sync
     * Pause automatic synchronization for a tenant.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static pauseSyncApiV1SyncPausePost(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/sync/pause',
        });
    }
    /**
     * Resume Sync
     * Resume automatic synchronization for a tenant.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static resumeSyncApiV1SyncResumePost(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/sync/resume',
        });
    }
}
