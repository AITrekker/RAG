/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SourceCitation } from './SourceCitation';
/**
 * The response model for a RAG query.
 */
export type QueryResponse = {
    /**
     * The original query text.
     */
    query: string;
    /**
     * The generated answer from the LLM.
     */
    answer: string;
    /**
     * A list of source chunks that informed the answer.
     */
    sources: Array<SourceCitation>;
    /**
     * The calculated confidence score for the answer.
     */
    confidence: number;
    /**
     * The total time taken to process the query in seconds.
     */
    processing_time?: (number | null);
    /**
     * Metadata from the LLM, such as model name and token counts.
     */
    llm_metadata?: (Record<string, any> | null);
};

