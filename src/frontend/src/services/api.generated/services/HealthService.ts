/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DetailedHealthResponse } from '../models/DetailedHealthResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HealthService {
    /**
     * Basic Liveness Check
     * Confirms the API is running and can respond to requests.
     * Does not check dependencies.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static livenessCheckApiV1HealthLivenessGet(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/liveness',
        });
    }
    /**
     * Basic Liveness Check
     * Confirms the API is running and can respond to requests.
     * Does not check dependencies.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static livenessCheckApiV1HealthLivenessGet1(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/liveness',
        });
    }
    /**
     * Detailed Readiness Check
     * Checks the health of the API and its critical dependencies (Qdrant, Embedding Model).
     * @param kwargs
     * @param forceReload
     * @returns DetailedHealthResponse Successful Response
     * @throws ApiError
     */
    public static readinessCheckApiV1HealthReadinessGet(
        kwargs: any,
        forceReload: boolean = false,
    ): CancelablePromise<DetailedHealthResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/readiness',
            query: {
                'force_reload': forceReload,
                'kwargs': kwargs,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Detailed Readiness Check
     * Checks the health of the API and its critical dependencies (Qdrant, Embedding Model).
     * @param kwargs
     * @param forceReload
     * @returns DetailedHealthResponse Successful Response
     * @throws ApiError
     */
    public static readinessCheckApiV1HealthReadinessGet1(
        kwargs: any,
        forceReload: boolean = false,
    ): CancelablePromise<DetailedHealthResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/readiness',
            query: {
                'force_reload': forceReload,
                'kwargs': kwargs,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
