/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Represents a single source document chunk used for an answer.
 */
export type SourceCitation = {
    /**
     * The unique ID of the document chunk.
     */
    id: string;
    /**
     * The text content of the chunk.
     */
    text: string;
    /**
     * The relevance score of the chunk.
     */
    score: number;
    /**
     * The name of the source document.
     */
    filename?: (string | null);
    /**
     * The page number in the source document.
     */
    page_number?: (number | null);
    /**
     * The index of the chunk within the document.
     */
    chunk_index?: (number | null);
};

