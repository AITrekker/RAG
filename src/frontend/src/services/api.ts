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

export interface SyncStatusResponse {
  tenant_id: string;
  sync_enabled: boolean;
  last_sync_time: string | null;
  last_sync_success: boolean | null;
  sync_interval_minutes: number;
  file_watcher_active: boolean;
  pending_changes: number;
  current_status: SyncStatus;
  active_sync_id?: string;
}

export enum SyncStatus {
  IDLE = "idle",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
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

export interface SyncMetrics {
  period_days: number;
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  success_rate: number;
  total_files_processed: number;
  total_files_added: number;
  total_files_modified: number;
  total_files_deleted: number;
  average_sync_time_seconds: number | null;
  last_sync_time: string | null;
}

export interface SyncConfig {
  auto_sync_enabled: boolean;
  sync_interval_minutes: number;
  ignore_patterns: string[];
  webhooks: Array<{
    url: string;
    events: string[];
    timeout: number;
    retry_count: number;
  }>;
}

export interface DocumentInfo {
  document_id: string;
  filename: string;
  upload_timestamp: string;
  file_size: number;
  status: string;
  chunks_count: number;
  content_type?: string;
  metadata: {
    document_type?: string;
    file_hash?: string;
    file_path?: string;
    embedding_model?: string;
    processed_at?: string;
    error_message?: string;
  };
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
        'Authorization': `Bearer ${API_KEY}`,
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
      let errorMessage = 'Server error';
      
      if (data.detail) {
        // Handle FastAPI validation errors
        if (Array.isArray(data.detail)) {
          // FastAPI validation error format
          const validationErrors = data.detail.map((err: any) => 
            `${err.loc?.join('.')} - ${err.msg || err.type}`
          ).join(', ');
          errorMessage = `Validation error: ${validationErrors}`;
        } else if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        }
      } else if (data.error) {
        errorMessage = data.error;
      }
      
      return {
        error: errorMessage,
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
    const response = await this.client.post<SyncResponse>('/sync/trigger', request);
    return response.data;
  }

  async getSyncStatus(): Promise<SyncStatusResponse> {
    const response = await this.client.get<SyncStatusResponse>('/sync/status');
    return response.data;
  }

  async getSyncOperation(syncId: string): Promise<SyncResponse> {
    const response = await this.client.get<SyncResponse>(`/sync/${syncId}`);
    return response.data;
  }

  async getSyncMetrics(days: number = 7): Promise<SyncMetrics> {
    const response = await this.client.get<SyncMetrics>('/sync/metrics', { params: { days } });
    return response.data;
  }

  async getSyncConfig(): Promise<SyncConfig> {
    const response = await this.client.get<SyncConfig>('/sync/config');
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

  // Document API methods
  async uploadDocument(file: File): Promise<{
    document_id: string;
    filename: string;
    status: string;
    chunks_created: number;
    processing_time?: number;
    file_size: number;
    upload_timestamp: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.client.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getDocuments(page: number = 1, pageSize: number = 20, search?: string): Promise<{
    documents: any[];
    total_count: number;
    page: number;
    page_size: number;
  }> {
    const response = await this.client.get('/documents', {
      params: { page, page_size: pageSize, search },
    });
    return response.data;
  }

  async getDocument(documentId: string): Promise<any> {
    const response = await this.client.get(`/documents/${documentId}`);
    return response.data;
  }

  async updateDocument(documentId: string, metadata: Record<string, any>): Promise<any> {
    const response = await this.client.put(`/documents/${documentId}`, { metadata });
    return response.data;
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.client.delete(`/documents/${documentId}`);
  }

  async clearAllDocuments(): Promise<void> {
    await this.client.delete('/documents');
  }

  async downloadDocument(documentId: string): Promise<Blob> {
    const response = await this.client.get(`/documents/${documentId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  }

  async getDocumentChunks(documentId: string, page: number = 1, pageSize: number = 20): Promise<{
    chunks: any[];
    total_count: number;
    page: number;
    page_size: number;
  }> {
    const response = await this.client.get(`/documents/${documentId}/chunks`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  // Tenant API methods
  async getTenants(page: number = 1, pageSize: number = 20): Promise<{
    tenants: any[];
    total_count: number;
    page: number;
    page_size: number;
  }> {
    const response = await this.client.get('/tenants', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  async createTenant(name: string, description?: string): Promise<any> {
    const response = await this.client.post('/tenants', { name, description });
    return response.data;
  }

  async getTenant(tenantId: string): Promise<any> {
    const response = await this.client.get(`/tenants/${tenantId}`);
    return response.data;
  }

  async updateTenant(tenantId: string, updates: { name?: string; description?: string }): Promise<any> {
    const response = await this.client.put(`/tenants/${tenantId}`, updates);
    return response.data;
  }

  async deleteTenant(tenantId: string): Promise<void> {
    await this.client.delete(`/tenants/${tenantId}`);
  }

  async getTenantStats(tenantId: string): Promise<{
    document_count: number;
    storage_used_mb: number;
    query_count: number;
    last_sync: string;
  }> {
    const response = await this.client.get(`/tenants/${tenantId}/stats`);
    return response.data;
  }

  // Audit API methods
  async getAuditEvents(page: number = 1, pageSize: number = 100): Promise<{
    events: any[]; // Replace 'any' with a proper SyncEvent model if available
    total_count: number;
    page: number;
    page_size: number;
  }> {
    const response = await this.client.get('/audit/events', {
      params: { offset: (page - 1) * pageSize, limit: pageSize },
    });
    // Assuming the API returns a list and we need to structure it for pagination
    return {
      events: response.data,
      total_count: response.headers['x-total-count'] || response.data.length, // Fallback
      page,
      page_size: pageSize,
    };
  }

  // Utility methods
  setApiKey(apiKey: string): void {
    this.client.defaults.headers['Authorization'] = `Bearer ${apiKey}`;
  }

  setTenantId(tenantId: string): void {
    // Set tenant ID in the request headers for backend processing (backend expects X-Tenant-Id)
    this.client.defaults.headers['X-Tenant-Id'] = tenantId;
    console.log(`API: Set tenant ID to ${tenantId}`);
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

// Export a singleton instance
export const api = new ApiClient();

// Export types and client
export default api; 