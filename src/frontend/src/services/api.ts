/**
 * API client service for the Enterprise RAG Platform frontend.
 * 
 * Handles all communication with the backend API including authentication,
 * error handling, and request/response processing.
 */

import axios, { AxiosError } from 'axios';
import type { AxiosInstance, AxiosResponse } from 'axios';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const API_KEY = import.meta.env.VITE_API_KEY || 'dev-api-key-123';

// Types
export interface QueryRequest {
  query: string;
  max_sources?: number;
  include_metadata?: boolean;
  rerank?: boolean;
}

export interface SourceCitation {
  document_id: string;
  filename: string;
  chunk_text: string;
  page_number?: number;
  confidence_score: number;
  chunk_index: number;
  metadata?: Record<string, any>;
}

export interface QueryResponse {
  query_id: string;
  query: string;
  answer: string;
  sources: SourceCitation[];
  processing_time: number;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface SyncRequest {
  sync_type?: 'manual' | 'scheduled' | 'auto';
  force_full_sync?: boolean;
  include_patterns?: string[];
  exclude_patterns?: string[];
}

export interface SyncResponse {
  sync_id: string;
  tenant_id: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
  sync_type: 'manual' | 'scheduled' | 'auto';
  started_at: string;
  completed_at?: string;
  total_files: number;
  processed_files: number;
  successful_files: number;
  failed_files: number;
  total_chunks: number;
  processing_time?: number;
  error_message?: string;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  version: string;
  uptime_seconds: number;
}

export interface ApiError {
  error: string;
  status_code: number;
  request_id?: string;
}

// API Client Class
class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000, // 30 seconds
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('API Request Error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        console.log(`API Response: ${response.status} ${response.config.url}`);
        return response;
      },
      (error: AxiosError) => {
        console.error('API Response Error:', error);
        return Promise.reject(this.handleApiError(error));
      }
    );
  }

  private handleApiError(error: AxiosError): ApiError {
    if (error.response) {
      // Server responded with error status
      const data = error.response.data as any;
      return {
        error: data.error || data.detail || 'Server error',
        status_code: error.response.status,
        request_id: data.request_id,
      };
    } else if (error.request) {
      // Request was made but no response received
      return {
        error: 'Network error - unable to connect to server',
        status_code: 0,
      };
    } else {
      // Something else happened
      return {
        error: error.message || 'Unknown error',
        status_code: 0,
      };
    }
  }

  // Query API methods
  async processQuery(request: QueryRequest): Promise<QueryResponse> {
    const response = await this.client.post<QueryResponse>('/query', request);
    return response.data;
  }

  async getQueryHistory(page: number = 1, pageSize: number = 20): Promise<{
    queries: QueryResponse[];
    total_count: number;
    page: number;
    page_size: number;
  }> {
    const response = await this.client.get('/query/history', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  async getQueryResult(queryId: string): Promise<QueryResponse> {
    const response = await this.client.get<QueryResponse>(`/query/${queryId}`);
    return response.data;
  }

  async deleteQueryResult(queryId: string): Promise<void> {
    await this.client.delete(`/query/${queryId}`);
  }

  // Sync API methods
  async triggerSync(request: SyncRequest = {}): Promise<SyncResponse> {
    const response = await this.client.post<SyncResponse>('/sync', request);
    return response.data;
  }

  async getSyncStatus(): Promise<SyncResponse> {
    const response = await this.client.get<SyncResponse>('/sync/status');
    return response.data;
  }

  async getSyncOperation(syncId: string): Promise<SyncResponse> {
    const response = await this.client.get<SyncResponse>(`/sync/${syncId}`);
    return response.data;
  }

  async getSyncHistory(page: number = 1, pageSize: number = 20): Promise<{
    syncs: SyncResponse[];
    total_count: number;
    page: number;
    page_size: number;
  }> {
    const response = await this.client.get('/sync/history', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  async cancelSyncOperation(syncId: string): Promise<void> {
    await this.client.delete(`/sync/${syncId}`);
  }

  async getSyncSchedule(): Promise<{
    tenant_id: string;
    auto_sync_enabled: boolean;
    sync_interval_hours: number;
    next_scheduled_sync?: string;
    last_auto_sync?: string;
  }> {
    const response = await this.client.get('/sync/schedule');
    return response.data;
  }

  async updateSyncSchedule(
    autoSyncEnabled: boolean,
    syncIntervalHours: number
  ): Promise<void> {
    await this.client.put('/sync/schedule', {
      auto_sync_enabled: autoSyncEnabled,
      sync_interval_hours: syncIntervalHours,
    });
  }

  // Health API methods
  async getHealth(): Promise<HealthStatus> {
    const response = await this.client.get<HealthStatus>('/health');
    return response.data;
  }

  async getDetailedHealth(): Promise<{
    status: string;
    timestamp: string;
    version: string;
    uptime_seconds: number;
    components: Record<string, any>;
  }> {
    const response = await this.client.get('/health/detailed');
    return response.data;
  }

  async getSystemStatus(): Promise<{
    health: any;
    metrics: any;
    configuration: Record<string, any>;
  }> {
    const response = await this.client.get('/status');
    return response.data;
  }

  // Utility methods
  setApiKey(apiKey: string): void {
    this.client.defaults.headers['X-API-Key'] = apiKey;
  }

  setTenantId(tenantId: string): void {
    this.client.defaults.headers['X-Tenant-ID'] = tenantId;
  }

  // Test connection
  async testConnection(): Promise<boolean> {
    try {
      await this.getHealth();
      return true;
    } catch (error) {
      console.error('API connection test failed:', error);
      return false;
    }
  }
}

// Create and export singleton instance
export const apiClient = new ApiClient();

// Export types and client
export default apiClient; 