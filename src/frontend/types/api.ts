/**
 * Centralized TypeScript type definitions for the RAG Platform API.
 *
 * This file contains all the shared interfaces and enums used for
 * API requests and responses across the frontend application.
 */

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