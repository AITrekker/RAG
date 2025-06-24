/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncEventResponse } from '../models/SyncEventResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuditService {
    /**
     * Get Audit Events
     * Retrieve audit events for the current tenant.
     * @param limit
     * @param offset
     * @returns SyncEventResponse Successful Response
     * @throws ApiError
     */
    public static getAuditEventsApiV1AuditEventsGet(
        limit: number = 100,
        offset?: number,
    ): CancelablePromise<Array<SyncEventResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/audit/events',
            query: {
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
