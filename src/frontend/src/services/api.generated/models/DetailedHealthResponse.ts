/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ComponentStatus } from './ComponentStatus';
/**
 * Detailed health check response with component status.
 */
export type DetailedHealthResponse = {
    /**
     * Overall system status
     */
    overall_status: string;
    /**
     * Health check timestamp
     */
    timestamp: string;
    /**
     * List of component health statuses
     */
    components: Array<ComponentStatus>;
};

