/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QueryHistory } from '../models/QueryHistory';
import type { QueryRequest } from '../models/QueryRequest';
import type { QueryResponse } from '../models/QueryResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class QueryService {
    /**
     * Process Query
     * Processes a natural language query through the RAG pipeline.
     * @param requestBody
     * @returns QueryResponse Successful Response
     * @throws ApiError
     */
    public static processQueryApiV1QueryPost(
        requestBody: QueryRequest,
    ): CancelablePromise<QueryResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/query',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Query History
     * Get query history for the current tenant.
     *
     * Returns paginated list of recent queries and their responses.
     * @param page
     * @param pageSize
     * @returns QueryHistory Successful Response
     * @throws ApiError
     */
    public static getQueryHistoryApiV1QueryHistoryGet(
        page: number = 1,
        pageSize: number = 20,
    ): CancelablePromise<QueryHistory> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/query/history',
            query: {
                'page': page,
                'page_size': pageSize,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Query Result
     * Get a specific query result by ID.
     *
     * Returns the query result with all associated metadata and sources.
     * @param queryId
     * @returns QueryResponse Successful Response
     * @throws ApiError
     */
    public static getQueryResultApiV1QueryQueryIdGet(
        queryId: string,
    ): CancelablePromise<QueryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/query/{query_id}',
            path: {
                'query_id': queryId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Query Result
     * Delete a specific query result.
     *
     * Removes the query result from history (if implemented).
     * @param queryId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteQueryResultApiV1QueryQueryIdDelete(
        queryId: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/query/{query_id}',
            path: {
                'query_id': queryId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
