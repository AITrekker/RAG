/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QueryResponse } from './QueryResponse';
/**
 * Represents a single entry in the query history.
 */
export type QueryHistory = {
    id: string;
    query: string;
    response: QueryResponse;
    timestamp: string;
    tenant_id: string;
};

