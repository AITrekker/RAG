/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response model for document information.
 */
export type DocumentResponse = {
    /**
     * Unique document identifier
     */
    document_id: string;
    /**
     * Original filename
     */
    filename: string;
    /**
     * Upload timestamp
     */
    upload_timestamp: string;
    /**
     * File size in bytes
     */
    file_size: number;
    /**
     * Processing status (uploaded, processing, processed, failed)
     */
    status: string;
    /**
     * Number of chunks created
     */
    chunks_count?: number;
    /**
     * MIME content type
     */
    content_type?: (string | null);
    /**
     * Document metadata
     */
    metadata?: Record<string, any>;
};

