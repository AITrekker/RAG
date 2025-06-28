/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CreateApiKeyRequest } from '../models/CreateApiKeyRequest';
import type { CreateApiKeyResponse } from '../models/CreateApiKeyResponse';
import type { TenantResponse } from '../models/TenantResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TenantsService {
    /**
     * Get Tenants
     * Get all tenants.
     * @returns TenantResponse Successful Response
     * @throws ApiError
     */
    public static getTenantsApiV1TenantsGet(): CancelablePromise<Array<TenantResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/tenants',
        });
    }
    /**
     * Create Api Key
     * Create an API key for a tenant.
     * @param requestBody
     * @returns CreateApiKeyResponse Successful Response
     * @throws ApiError
     */
    public static createApiKeyApiV1TenantsApiKeyPost(
        requestBody: CreateApiKeyRequest,
    ): CancelablePromise<CreateApiKeyResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/tenants/api-key',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
