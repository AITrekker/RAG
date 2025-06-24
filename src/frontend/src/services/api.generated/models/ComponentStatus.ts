/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Health status of an individual component.
 */
export type ComponentStatus = {
    /**
     * Component name
     */
    name: string;
    /**
     * Component status ('healthy' or 'unhealthy')
     */
    status: string;
    /**
     * Additional component details
     */
    details?: (Record<string, any> | null);
};

