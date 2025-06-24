/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Information about a synchronized document.
 */
export type DocumentSyncInfo = {
    /**
     * Document filename
     */
    filename: string;
    /**
     * Full file path
     */
    file_path: string;
    /**
     * File size in bytes
     */
    file_size: number;
    /**
     * Last modification timestamp
     */
    last_modified: string;
    /**
     * Processing status
     */
    status: string;
    /**
     * Number of chunks created
     */
    chunks_created?: (number | null);
    /**
     * Processing time in seconds
     */
    processing_time?: (number | null);
    /**
     * Error message if failed
     */
    error_message?: (string | null);
};

