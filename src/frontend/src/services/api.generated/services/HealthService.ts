/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HealthService {
    /**
     * Basic Health Check
     * Basic health check endpoint.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static basicHealthCheckApiV1HealthGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/',
        });
    }
    /**
     * Detailed Health Check
     * Detailed health check with service status.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static detailedHealthCheckApiV1HealthDetailedGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/detailed',
        });
    }
    /**
     * Prometheus Metrics
     * Prometheus-compatible metrics endpoint.
     *
     * Returns metrics in Prometheus format for monitoring and alerting.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static prometheusMetricsApiV1HealthMetricsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/metrics',
        });
    }
    /**
     * Performance Metrics
     * Get detailed performance metrics.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static performanceMetricsApiV1HealthPerformanceGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/performance',
        });
    }
    /**
     * Error Statistics
     * Get error statistics and recent errors.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static errorStatisticsApiV1HealthErrorsGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/errors',
        });
    }
    /**
     * Resource Usage
     * Get detailed system resource usage.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static resourceUsageApiV1HealthResourcesGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/resources',
        });
    }
    /**
     * Set Performance Alert
     * Set or update a performance alert threshold.
     * @param metricName
     * @param threshold
     * @param enabled
     * @returns any Successful Response
     * @throws ApiError
     */
    public static setPerformanceAlertApiV1HealthPerformanceAlertMetricNamePost(
        metricName: string,
        threshold: number,
        enabled: boolean = true,
    ): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/health/performance/alert/{metric_name}',
            path: {
                'metric_name': metricName,
            },
            query: {
                'threshold': threshold,
                'enabled': enabled,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Service Status
     * Get overall service status and uptime.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static serviceStatusApiV1HealthStatusGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/status',
        });
    }
    /**
     * Liveness Check
     * Basic liveness check.
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
     * Readiness Check
     * Basic readiness check.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static readinessCheckApiV1HealthReadinessGet(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health/readiness',
        });
    }
}
