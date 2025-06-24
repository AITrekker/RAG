/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocumentResponse } from './DocumentResponse';
/**
 * Response model for document listing.
 */
export type DocumentListResponse = {
    /**
     * List of documents
     */
    documents?: Array<DocumentResponse>;
    /**
     * Total number of documents
     */
    total_count: number;
    /**
     * Current page number
     */
    page: number;
    /**
     * Number of documents per page
     */
    page_size: number;
};

