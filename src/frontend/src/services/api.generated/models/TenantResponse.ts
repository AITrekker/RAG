/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ApiKeyInfo } from './ApiKeyInfo';
export type TenantResponse = {
    tenant_id: string;
    name: string;
    description?: (string | null);
    status: string;
    created_at: string;
    api_keys: Array<ApiKeyInfo>;
};

