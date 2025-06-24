/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request model for webhook configuration.
 */
export type WebhookConfigRequest = {
    /**
     * Webhook URL
     */
    url: string;
    /**
     * Webhook secret
     */
    secret?: (string | null);
    /**
     * Events to subscribe to
     */
    events: Array<string>;
    /**
     * Timeout in seconds
     */
    timeout?: number;
    /**
     * Number of retries
     */
    retry_count?: number;
};

