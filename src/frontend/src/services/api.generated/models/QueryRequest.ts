/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The request model for submitting a query.
 */
export type QueryRequest = {
    /**
     * The user's query.
     */
    query: string;
    /**
     * The tenant ID to scope the query to. If not provided, a default may be used based on context.
     */
    tenant_id?: (string | null);
};

