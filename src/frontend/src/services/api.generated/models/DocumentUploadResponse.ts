/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response model for document upload.
 */
export type DocumentUploadResponse = {
    /**
     * Unique document identifier
     */
    document_id: string;
    /**
     * Original filename
     */
    filename: string;
    /**
     * Processing status
     */
    status: string;
    /**
     * Number of chunks created
     */
    chunks_created?: number;
    /**
     * Processing time in seconds
     */
    processing_time?: (number | null);
    /**
     * File size in bytes
     */
    file_size: number;
    /**
     * Upload timestamp
     */
    upload_timestamp: string;
};

