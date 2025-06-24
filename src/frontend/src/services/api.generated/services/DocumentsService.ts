/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_upload_document_api_v1_documents_upload_post } from '../models/Body_upload_document_api_v1_documents_upload_post';
import type { DocumentListResponse } from '../models/DocumentListResponse';
import type { DocumentResponse } from '../models/DocumentResponse';
import type { DocumentUpdateRequest } from '../models/DocumentUpdateRequest';
import type { DocumentUploadResponse } from '../models/DocumentUploadResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DocumentsService {
    /**
     * Upload Document
     * Upload a document for processing and indexing.
     *
     * Accepts various file formats (PDF, DOCX, TXT, etc.) and processes them
     * through the document ingestion pipeline.
     * @param formData
     * @returns DocumentUploadResponse Successful Response
     * @throws ApiError
     */
    public static uploadDocumentApiV1DocumentsUploadPost(
        formData: Body_upload_document_api_v1_documents_upload_post,
    ): CancelablePromise<DocumentUploadResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/documents/upload',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Documents
     * List all documents for the current tenant.
     *
     * Returns paginated list of documents with optional search filtering.
     * @param page
     * @param pageSize
     * @param search
     * @returns DocumentListResponse Successful Response
     * @throws ApiError
     */
    public static listDocumentsApiV1DocumentsGet(
        page: number = 1,
        pageSize: number = 20,
        search?: (string | null),
    ): CancelablePromise<DocumentListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/',
            query: {
                'page': page,
                'page_size': pageSize,
                'search': search,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Document
     * Get detailed information about a specific document.
     *
     * Returns comprehensive document information including metadata and processing status.
     * @param documentId
     * @returns DocumentResponse Successful Response
     * @throws ApiError
     */
    public static getDocumentApiV1DocumentsDocumentIdGet(
        documentId: string,
    ): CancelablePromise<DocumentResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Document
     * Update document metadata.
     *
     * Allows updating document metadata such as tags, description, etc.
     * @param documentId
     * @param requestBody
     * @returns DocumentResponse Successful Response
     * @throws ApiError
     */
    public static updateDocumentApiV1DocumentsDocumentIdPut(
        documentId: string,
        requestBody: DocumentUpdateRequest,
    ): CancelablePromise<DocumentResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/documents/{document_id}',
            path: {
                'document_id': documentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Document
     * Delete a document and its associated data.
     *
     * This endpoint is now a thin wrapper around the DocumentService.
     * @param documentId
     * @returns void
     * @throws ApiError
     */
    public static deleteDocumentApiV1DocumentsDocumentIdDelete(
        documentId: string,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/documents/{document_id}',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Clear All Documents
     * Delete all documents for the current tenant.
     *
     * This endpoint is now a thin wrapper around the DocumentService.
     * @returns void
     * @throws ApiError
     */
    public static clearAllDocumentsApiV1DocumentsClearDelete(): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/documents/clear',
        });
    }
    /**
     * Download Document
     * Download the original document file.
     *
     * Returns the original uploaded file for download.
     * @param documentId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static downloadDocumentApiV1DocumentsDocumentIdDownloadGet(
        documentId: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}/download',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Document Chunks
     * Get chunks/segments of a specific document.
     *
     * Returns paginated list of document chunks with their embeddings metadata.
     * @param documentId
     * @param page
     * @param pageSize
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getDocumentChunksApiV1DocumentsDocumentIdChunksGet(
        documentId: string,
        page: number = 1,
        pageSize: number = 20,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/documents/{document_id}/chunks',
            path: {
                'document_id': documentId,
            },
            query: {
                'page': page,
                'page_size': pageSize,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
