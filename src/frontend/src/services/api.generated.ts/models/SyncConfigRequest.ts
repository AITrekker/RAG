/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WebhookConfigRequest } from './WebhookConfigRequest';
/**
 * Request model for sync configuration.
 */
export type SyncConfigRequest = {
    /**
     * Sync interval in minutes
     */
    sync_interval_minutes: number;
    /**
     * Whether auto sync is enabled
     */
    auto_sync_enabled: boolean;
    /**
     * File patterns to ignore
     */
    ignore_patterns?: (Array<string> | null);
    /**
     * Webhook configurations
     */
    webhooks?: (Array<WebhookConfigRequest> | null);
};

