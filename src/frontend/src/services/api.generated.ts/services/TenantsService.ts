/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TenantCreateRequest } from '../models/TenantCreateRequest';
import type { TenantListResponse } from '../models/TenantListResponse';
import type { TenantResponse } from '../models/TenantResponse';
import type { TenantStatsResponse } from '../models/TenantStatsResponse';
import type { TenantUpdateRequest } from '../models/TenantUpdateRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TenantsService {
    /**
     * Create Tenant
     * Create a new tenant.
     *
     * Creates a new tenant with the specified configuration and initializes
     * the necessary resources (database, vector store, file system).
     * @param requestBody
     * @returns TenantResponse Successful Response
     * @throws ApiError
     */
    public static createTenantApiV1TenantsPost(
        requestBody: TenantCreateRequest,
    ): CancelablePromise<TenantResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/tenants/',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Tenants
     * List all tenants with pagination and filtering.
     *
     * Returns a paginated list of tenants with optional status filtering.
     * @param page
     * @param pageSize
     * @param statusFilter
     * @returns TenantListResponse Successful Response
     * @throws ApiError
     */
    public static listTenantsApiV1TenantsGet(
        page: number = 1,
        pageSize: number = 20,
        statusFilter?: (string | null),
    ): CancelablePromise<TenantListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/tenants/',
            query: {
                'page': page,
                'page_size': pageSize,
                'status_filter': statusFilter,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Tenant
     * Get detailed information about a specific tenant.
     *
     * Returns comprehensive tenant information including statistics.
     * @param tenantId
     * @returns TenantResponse Successful Response
     * @throws ApiError
     */
    public static getTenantApiV1TenantsTenantIdGet(
        tenantId: string,
    ): CancelablePromise<TenantResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/tenants/{tenant_id}',
            path: {
                'tenant_id': tenantId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Tenant
     * Update tenant information and settings.
     *
     * Updates the specified tenant with new information and settings.
     * @param tenantId
     * @param requestBody
     * @returns TenantResponse Successful Response
     * @throws ApiError
     */
    public static updateTenantApiV1TenantsTenantIdPut(
        tenantId: string,
        requestBody: TenantUpdateRequest,
    ): CancelablePromise<TenantResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/tenants/{tenant_id}',
            path: {
                'tenant_id': tenantId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Tenant
     * Delete a tenant and all associated data.
     *
     * WARNING: This operation is irreversible and will delete all tenant data
     * including documents, embeddings, and query history.
     * @param tenantId
     * @returns void
     * @throws ApiError
     */
    public static deleteTenantApiV1TenantsTenantIdDelete(
        tenantId: string,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/tenants/{tenant_id}',
            path: {
                'tenant_id': tenantId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Tenant Stats
     * Get detailed statistics for a specific tenant.
     *
     * Returns comprehensive usage and performance statistics.
     * @param tenantId
     * @returns TenantStatsResponse Successful Response
     * @throws ApiError
     */
    public static getTenantStatsApiV1TenantsTenantIdStatsGet(
        tenantId: string,
    ): CancelablePromise<TenantStatsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/tenants/{tenant_id}/stats',
            path: {
                'tenant_id': tenantId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
