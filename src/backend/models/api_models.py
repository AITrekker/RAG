"""
Pydantic models for the redesigned RAG Platform API.

This module defines all request and response models for the new API structure:
- Setup & Initialization
- Admin Operations (Admin-only)
- Document Sync (Per-tenant)
- Query Processing (Per-tenant)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

# =============================================================================
# SETUP & INITIALIZATION MODELS
# =============================================================================

class SetupStatus(str, Enum):
    """System initialization status."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    ERROR = "error"

class SetupCheckResponse(BaseModel):
    """Response for system initialization check."""
    initialized: bool = Field(..., description="Whether system is initialized")
    message: str = Field(..., description="Status message")
    admin_tenant_exists: bool = Field(False, description="Whether admin tenant exists")
    total_tenants: int = Field(0, description="Total number of tenants")

class SetupInitializeRequest(BaseModel):
    """Request to initialize the system."""
    admin_tenant_name: str = Field(..., description="Name for the admin tenant")
    admin_tenant_description: Optional[str] = Field(None, description="Admin tenant description")

class SetupInitializeResponse(BaseModel):
    """Response after system initialization."""
    success: bool = Field(..., description="Whether initialization was successful")
    admin_tenant_id: str = Field(..., description="Admin tenant ID")
    admin_api_key: str = Field(..., description="Admin API key (save this securely)")
    message: str = Field(..., description="Initialization message")
    config_written: bool = Field(..., description="Whether config was written to .env")

# =============================================================================
# ADMIN OPERATIONS MODELS
# =============================================================================

class TenantStatus(str, Enum):
    """Tenant status enumeration."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class TenantCreateRequest(BaseModel):
    """Request to create a new tenant."""
    name: str = Field(..., min_length=1, max_length=100, description="Tenant name")
    description: Optional[str] = Field(None, max_length=500, description="Tenant description")
    auto_sync: bool = Field(True, description="Enable automatic document sync")
    sync_interval: int = Field(60, ge=1, le=1440, description="Sync interval in minutes")

class TenantUpdateRequest(BaseModel):
    """Request to update tenant details."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Tenant name")
    description: Optional[str] = Field(None, max_length=500, description="Tenant description")
    status: Optional[TenantStatus] = Field(None, description="Tenant status")
    auto_sync: Optional[bool] = Field(None, description="Enable automatic document sync")
    sync_interval: Optional[int] = Field(None, ge=1, le=1440, description="Sync interval in minutes")

class ApiKeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="API key name")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")

class ApiKeyResponse(BaseModel):
    """API key information (without the actual key)."""
    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key_prefix: str = Field(..., description="Key prefix for identification")
    is_active: bool = Field(..., description="Whether key is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")

class ApiKeyCreateResponse(BaseModel):
    """Response when creating a new API key."""
    api_key: str = Field(..., description="The full API key (save this securely)")
    key_info: ApiKeyResponse = Field(..., description="Key metadata")

class TenantResponse(BaseModel):
    """Tenant information."""
    id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    status: TenantStatus = Field(..., description="Tenant status")
    created_at: datetime = Field(..., description="Creation timestamp")
    auto_sync: bool = Field(..., description="Automatic sync enabled")
    sync_interval: int = Field(..., description="Sync interval in minutes")
    api_keys: List[ApiKeyResponse] = Field(default_factory=list, description="API keys")
    document_count: int = Field(0, description="Number of documents")
    storage_used_mb: float = Field(0.0, description="Storage used in MB")

class TenantListResponse(BaseModel):
    """Response for listing tenants."""
    tenants: List[TenantResponse] = Field(..., description="List of tenants")
    total_count: int = Field(..., description="Total number of tenants")

class SystemStatusResponse(BaseModel):
    """System status information."""
    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="System version")
    uptime_seconds: float = Field(..., description="System uptime")
    total_tenants: int = Field(..., description="Total number of tenants")
    total_documents: int = Field(..., description="Total documents across all tenants")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component statuses")

class SystemMetricsResponse(BaseModel):
    """System performance metrics."""
    timestamp: datetime = Field(..., description="Metrics timestamp")
    cpu_usage_percent: float = Field(..., description="CPU usage")
    memory_usage_percent: float = Field(..., description="Memory usage")
    disk_usage_percent: float = Field(..., description="Disk usage")
    active_connections: int = Field(..., description="Active connections")
    queries_per_minute: float = Field(..., description="Queries per minute")
    sync_operations: int = Field(..., description="Active sync operations")

# =============================================================================
# DOCUMENT SYNC MODELS
# =============================================================================

class SyncStatus(str, Enum):
    """Sync operation status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SyncTriggerRequest(BaseModel):
    """Request to trigger document sync."""
    force_full_sync: bool = Field(False, description="Force full resync")
    document_paths: Optional[List[str]] = Field(None, description="Specific paths to sync")

class SyncResponse(BaseModel):
    """Sync operation response."""
    sync_id: str = Field(..., description="Unique sync operation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    status: SyncStatus = Field(..., description="Sync status")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    progress: Dict[str, Any] = Field(default_factory=dict, description="Progress information")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class SyncHistoryResponse(BaseModel):
    """Sync history response."""
    syncs: List[SyncResponse] = Field(..., description="List of sync operations")
    total_count: int = Field(..., description="Total number of syncs")

class SyncConfigRequest(BaseModel):
    """Sync configuration request."""
    auto_sync: bool = Field(..., description="Enable automatic sync")
    sync_interval: int = Field(..., ge=1, le=1440, description="Sync interval in minutes")
    document_paths: List[str] = Field(default_factory=list, description="Document paths to monitor")
    file_types: List[str] = Field(default_factory=list, description="File types to process")
    chunk_size: int = Field(512, ge=100, le=2000, description="Document chunk size")
    chunk_overlap: int = Field(50, ge=0, le=500, description="Chunk overlap")

class SyncConfigResponse(BaseModel):
    """Sync configuration response."""
    tenant_id: str = Field(..., description="Tenant ID")
    auto_sync: bool = Field(..., description="Automatic sync enabled")
    sync_interval: int = Field(..., description="Sync interval in minutes")
    document_paths: List[str] = Field(..., description="Document paths")
    file_types: List[str] = Field(..., description="File types")
    chunk_size: int = Field(..., description="Chunk size")
    chunk_overlap: int = Field(..., description="Chunk overlap")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    next_sync: Optional[datetime] = Field(None, description="Next scheduled sync")

# =============================================================================
# QUERY PROCESSING MODELS
# =============================================================================

class MetadataFilters(BaseModel):
    """Metadata filters for query processing."""
    author: Optional[str] = Field(None, description="Filter by author")
    date_from: Optional[str] = Field(None, description="Filter by date from (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter by date to (YYYY-MM-DD)")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    title: Optional[str] = Field(None, description="Filter by document title")
    category: Optional[str] = Field(None, description="Filter by document category")

class QueryRequest(BaseModel):
    """RAG query request with metadata filtering."""
    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    max_sources: int = Field(5, ge=1, le=20, description="Maximum number of sources")
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Confidence threshold")
    metadata_filters: Optional[MetadataFilters] = Field(None, description="Metadata filters")

class SourceCitation(BaseModel):
    """Source document citation with metadata."""
    id: str = Field(..., description="Source ID")
    text: str = Field(..., description="Source text content")
    score: float = Field(..., description="Relevance score")
    document_id: str = Field(..., description="Document ID")
    document_name: str = Field(..., description="Document name")
    page_number: Optional[int] = Field(None, description="Page number")
    chunk_index: Optional[int] = Field(None, description="Chunk index")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Document metadata")
    
class QueryResponse(BaseModel):
    """RAG query response."""
    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Generated answer")
    sources: List[SourceCitation] = Field(..., description="Source citations")
    confidence: float = Field(..., description="Confidence score")
    processing_time: float = Field(..., description="Processing time in seconds")
    tokens_used: Optional[int] = Field(None, description="Tokens used")
    model_used: Optional[str] = Field(None, description="Model used for generation")

class QueryBatchRequest(BaseModel):
    """Batch query request with metadata filtering."""
    queries: List[str] = Field(..., min_items=1, max_items=10, description="List of queries")
    max_sources: int = Field(5, ge=1, le=20, description="Maximum sources per query")
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Confidence threshold")
    metadata_filters: Optional[MetadataFilters] = Field(None, description="Metadata filters")

class QueryBatchResponse(BaseModel):
    """Batch query response."""
    results: List[QueryResponse] = Field(..., description="Query results")
    total_processing_time: float = Field(..., description="Total processing time")
    successful_queries: int = Field(..., description="Number of successful queries")
    failed_queries: int = Field(..., description="Number of failed queries")

class QueryHistoryResponse(BaseModel):
    """Query history response."""
    queries: List[Dict[str, Any]] = Field(..., description="Query history")
    total_count: int = Field(..., description="Total number of queries")

class QueryFeedbackRequest(BaseModel):
    """Query feedback request."""
    query_id: str = Field(..., description="Query ID")
    rating: int = Field(..., ge=1, le=5, description="Rating (1-5)")
    feedback: Optional[str] = Field(None, description="Feedback text")
    helpful: bool = Field(..., description="Whether answer was helpful")

class QueryFeedbackResponse(BaseModel):
    """Query feedback response."""
    success: bool = Field(..., description="Whether feedback was saved")
    message: str = Field(..., description="Feedback message")

# =============================================================================
# DOCUMENT MANAGEMENT MODELS
# =============================================================================

class DocumentMetadata(BaseModel):
    """Document metadata."""
    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    date_created: Optional[str] = Field(None, description="Creation date")
    date_modified: Optional[str] = Field(None, description="Last modified date")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    category: Optional[str] = Field(None, description="Document category")
    summary: Optional[str] = Field(None, description="Document summary")
    language: Optional[str] = Field(None, description="Document language")
    page_count: Optional[int] = Field(None, description="Number of pages")
    word_count: Optional[int] = Field(None, description="Word count")
    file_hash: Optional[str] = Field(None, description="File hash for delta sync")

class DocumentResponse(BaseModel):
    """Document information with metadata."""
    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    file_path: str = Field(..., description="File path")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="Content type")
    upload_timestamp: datetime = Field(..., description="Upload timestamp")
    last_modified: datetime = Field(..., description="Last modification")
    chunk_count: int = Field(..., description="Number of chunks")
    status: str = Field(..., description="Processing status")
    metadata: Optional[DocumentMetadata] = Field(None, description="Document metadata")
    embedding_count: int = Field(0, description="Number of embeddings")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")

class DocumentListResponse(BaseModel):
    """Document list response."""
    documents: List[DocumentResponse] = Field(..., description="List of documents")
    total_count: int = Field(..., description="Total number of documents")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")

class DocumentUploadResponse(BaseModel):
    """Document upload response."""
    document_id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    status: str = Field(..., description="Upload status")
    message: str = Field(..., description="Status message")

# =============================================================================
# EMBEDDING MANAGEMENT MODELS
# =============================================================================

class EmbeddingRequest(BaseModel):
    """Request to generate embeddings for a single text."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to embed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    doc_id: Optional[str] = Field(None, description="Document ID")

class BatchEmbeddingRequest(BaseModel):
    """Request to generate embeddings for multiple texts."""
    texts: List[str] = Field(..., min_items=1, max_items=100, description="Texts to embed")
    metadata: Optional[List[Dict[str, Any]]] = Field(None, description="Optional metadata for each text")
    doc_ids: Optional[List[str]] = Field(None, description="Document IDs for each text")
    priority: int = Field(0, ge=0, le=10, description="Processing priority (0-10)")

class EmbeddingResponse(BaseModel):
    """Response for single embedding generation."""
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    text: str = Field(..., description="Original text")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")
    doc_id: Optional[str] = Field(None, description="Document ID")
    processing_time: float = Field(..., description="Processing time in seconds")
    embedding_dimension: int = Field(..., description="Embedding dimension")

class BatchEmbeddingResponse(BaseModel):
    """Response for batch embedding generation."""
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    texts: List[str] = Field(..., description="Original texts")
    metadata: Optional[List[Dict[str, Any]]] = Field(None, description="Metadata")
    doc_ids: Optional[List[str]] = Field(None, description="Document IDs")
    processing_time: float = Field(..., description="Processing time in seconds")
    embedding_dimension: int = Field(..., description="Embedding dimension")
    batch_size: int = Field(..., description="Number of texts processed")

class EmbeddingServiceInfo(BaseModel):
    """Information about the embedding service."""
    model_name: str = Field(..., description="Model name")
    model_path: str = Field(..., description="Model path")
    embedding_dimension: int = Field(..., description="Embedding dimension")
    max_sequence_length: int = Field(..., description="Maximum sequence length")
    device: str = Field(..., description="Computing device")
    is_loaded: bool = Field(..., description="Whether model is loaded")
    supports_normalization: bool = Field(..., description="Supports embedding normalization")

class EmbeddingStatsResponse(BaseModel):
    """Embedding generation statistics."""
    processed_requests: int = Field(..., description="Total processed requests")
    total_texts_processed: int = Field(..., description="Total texts processed")
    total_processing_time: float = Field(..., description="Total processing time")
    error_count: int = Field(..., description="Number of errors")
    average_processing_time: float = Field(..., description="Average processing time")
    requests_per_second: float = Field(..., description="Requests per second")
    worker_threads: int = Field(..., description="Number of worker threads")
    queue_size: int = Field(..., description="Current queue size")
    pipeline_stats: Dict[str, Any] = Field(default_factory=dict, description="Pipeline statistics")

# =============================================================================
# LLM SERVICE MODELS
# =============================================================================

class LLMGenerateRequest(BaseModel):
    """Request to generate text using LLM."""
    prompt: str = Field(..., min_length=1, max_length=10000, description="Input prompt")
    context: Optional[List[str]] = Field(None, description="Additional context")
    max_new_tokens: Optional[int] = Field(None, ge=1, le=2048, description="Maximum new tokens")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Generation temperature")
    do_sample: bool = Field(True, description="Enable sampling")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p sampling")
    top_k: int = Field(50, ge=1, le=1000, description="Top-k sampling")
    repetition_penalty: float = Field(1.1, ge=1.0, le=2.0, description="Repetition penalty")

class LLMGenerateResponse(BaseModel):
    """Response from LLM text generation."""
    text: str = Field(..., description="Generated text")
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    completion_tokens: int = Field(..., description="Number of completion tokens")
    total_tokens: int = Field(..., description="Total tokens")
    generation_time: float = Field(..., description="Generation time in seconds")
    model_name: str = Field(..., description="Model used")
    temperature: float = Field(..., description="Temperature used")

class LLMServiceInfo(BaseModel):
    """Information about the LLM service."""
    model_name: str = Field(..., description="Model name")
    max_length: int = Field(..., description="Maximum length")
    temperature: float = Field(..., description="Default temperature")
    device: str = Field(..., description="Computing device")
    is_loaded: bool = Field(..., description="Whether model is loaded")
    quantization_enabled: bool = Field(..., description="Whether quantization is enabled")

class LLMStatsResponse(BaseModel):
    """LLM service statistics."""
    generation_times: List[float] = Field(..., description="Recent generation times")
    total_tokens_generated: int = Field(..., description="Total tokens generated")
    average_generation_time: float = Field(..., description="Average generation time")
    model_name: str = Field(..., description="Model name")
    device: str = Field(..., description="Device used")

# =============================================================================
# SYSTEM MONITORING MODELS
# =============================================================================

class SystemMetricsDetailResponse(BaseModel):
    """Detailed system metrics."""
    timestamp: datetime = Field(..., description="Metrics timestamp")
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    disk_usage_percent: float = Field(..., description="Disk usage percentage")
    gpu_utilization: Optional[float] = Field(None, description="GPU utilization")
    gpu_memory_percent: Optional[float] = Field(None, description="GPU memory usage")
    active_connections: int = Field(..., description="Active connections")
    network_io: Dict[str, float] = Field(..., description="Network I/O statistics")
    disk_io: Dict[str, float] = Field(..., description="Disk I/O statistics")

class PerformanceMetricsResponse(BaseModel):
    """Performance metrics for the system."""
    timestamp: datetime = Field(..., description="Metrics timestamp")
    queries_per_minute: float = Field(..., description="Queries per minute")
    average_query_time: float = Field(..., description="Average query time")
    embedding_requests_per_minute: float = Field(..., description="Embedding requests per minute")
    sync_operations_per_minute: float = Field(..., description="Sync operations per minute")
    error_rate: float = Field(..., description="Error rate percentage")
    active_tenants: int = Field(..., description="Number of active tenants")

class ErrorLogResponse(BaseModel):
    """Error log entry."""
    timestamp: datetime = Field(..., description="Error timestamp")
    error_type: str = Field(..., description="Error type")
    error_message: str = Field(..., description="Error message")
    severity: str = Field(..., description="Error severity")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")
    endpoint: Optional[str] = Field(None, description="API endpoint")

class ErrorLogListResponse(BaseModel):
    """List of error log entries."""
    errors: List[ErrorLogResponse] = Field(..., description="Error log entries")
    total_count: int = Field(..., description="Total number of errors")
    error_types: Dict[str, int] = Field(..., description="Error type counts")

# =============================================================================
# ERROR RESPONSE
# =============================================================================

class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

# =============================================================================
# TENANT CONTEXT & DEMO MANAGEMENT MODELS
# =============================================================================

class TenantContextResponse(BaseModel):
    """Current tenant context information."""
    tenant_id: str = Field(..., description="Current tenant ID")
    tenant_name: str = Field(..., description="Current tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    status: TenantStatus = Field(..., description="Tenant status")
    permissions: List[str] = Field(default_factory=list, description="Tenant permissions")
    api_keys: List[ApiKeyResponse] = Field(default_factory=list, description="Tenant's API keys")
    created_at: datetime = Field(..., description="Creation timestamp")
    auto_sync: bool = Field(..., description="Automatic sync enabled")
    sync_interval: int = Field(..., description="Sync interval in minutes")

class TenantSwitchRequest(BaseModel):
    """Request to switch tenant context."""
    tenant_id: str = Field(..., description="Target tenant ID")
    api_key: str = Field(..., description="API key for target tenant")

class TenantSwitchResponse(BaseModel):
    """Response after tenant context switch."""
    success: bool = Field(..., description="Switch successful")
    tenant_context: TenantContextResponse = Field(..., description="New tenant context")
    message: str = Field(..., description="Switch message")

class DemoSetupRequest(BaseModel):
    """Request to setup demo environment."""
    demo_tenants: List[str] = Field(..., description="List of tenant IDs for demo")
    demo_duration_hours: int = Field(24, ge=1, le=168, description="Demo duration in hours")
    generate_api_keys: bool = Field(True, description="Generate API keys for demo tenants")

class DemoTenantInfo(BaseModel):
    """Demo tenant information with API keys."""
    tenant_id: str = Field(..., description="Tenant ID")
    tenant_name: str = Field(..., description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    api_keys: List[ApiKeyCreateResponse] = Field(default_factory=list, description="Generated API keys")
    demo_expires_at: datetime = Field(..., description="Demo expiration")
    created_at: datetime = Field(..., description="Demo creation timestamp")

class DemoSetupResponse(BaseModel):
    """Response after demo setup."""
    success: bool = Field(..., description="Setup successful")
    demo_tenants: List[DemoTenantInfo] = Field(..., description="Demo tenant information")
    admin_api_key: str = Field(..., description="Admin API key for demo management")
    message: str = Field(..., description="Setup message")
    total_tenants: int = Field(..., description="Total demo tenants created")

class DemoCleanupResponse(BaseModel):
    """Response after demo cleanup."""
    success: bool = Field(..., description="Cleanup successful")
    cleaned_tenants: int = Field(..., description="Number of tenants cleaned up")
    expired_keys: int = Field(..., description="Number of expired API keys")
    message: str = Field(..., description="Cleanup message")

# =============================================================================
# ENHANCED TENANT OPERATIONS MODELS
# =============================================================================

class TenantDocumentListRequest(BaseModel):
    """Request to list tenant documents with filtering."""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Page size")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    status: Optional[str] = Field(None, description="Filter by document status")

class TenantSyncStatusRequest(BaseModel):
    """Request to get tenant sync status."""
    include_history: bool = Field(False, description="Include sync history")
    limit: int = Field(10, ge=1, le=50, description="Number of history entries")

class TenantApiKeyManagementRequest(BaseModel):
    """Request for tenant API key management."""
    key_name: str = Field(..., min_length=1, max_length=100, description="API key name")
    description: Optional[str] = Field(None, max_length=500, description="Key description")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    permissions: List[str] = Field(default_factory=list, description="Key permissions")

# =============================================================================
# AUDIT & MONITORING MODELS
# =============================================================================

class SyncEventResponse(BaseModel):
    """Audit event response for sync operations."""
    event_id: str = Field(..., description="Event ID")
    tenant_id: str = Field(..., description="Tenant ID")
    event_type: str = Field(..., description="Event type")
    status: str = Field(..., description="Event status")
    timestamp: datetime = Field(..., description="Event timestamp")
    message: Optional[str] = Field(None, description="Event message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Event metadata")

# =============================================================================
# RAG PIPELINE MODELS
# =============================================================================

class RAGSource(BaseModel):
    """Source document information for RAG responses."""
    id: str = Field(..., description="Source ID")
    text: str = Field(..., description="Source text content")
    score: float = Field(..., description="Relevance score")
    document_id: str = Field(..., description="Document ID")
    document_name: str = Field(..., description="Document name")
    page_number: Optional[int] = Field(None, description="Page number")
    chunk_index: Optional[int] = Field(None, description="Chunk index")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Document metadata")

class RAGResponse(BaseModel):
    """Response from RAG pipeline."""
    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Generated answer")
    sources: List[RAGSource] = Field(..., description="Source citations")
    confidence: float = Field(..., description="Confidence score")
    processing_time: float = Field(..., description="Processing time in seconds")
    tokens_used: Optional[int] = Field(None, description="Tokens used")
    model_used: Optional[str] = Field(None, description="Model used for generation")


# =============================================================================
# NEW SERVICE LAYER MODELS
# =============================================================================

class FileResponse(BaseModel):
    """File response model for new service layer"""
    id: str = Field(..., description="File ID")
    filename: str = Field(..., description="File name")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    sync_status: str = Field(..., description="Sync status")
    word_count: Optional[int] = Field(None, description="Word count")
    page_count: Optional[int] = Field(None, description="Page count")
    language: Optional[str] = Field(None, description="Detected language")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Update timestamp")


class FileListResponse(BaseModel):
    """File list response model"""
    files: List[FileResponse] = Field(..., description="List of files")
    total_count: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")


class UploadResponse(BaseModel):
    """File upload response model"""
    file_id: str = Field(..., description="File ID")
    filename: str = Field(..., description="File name")
    file_size: int = Field(..., description="File size")
    sync_status: str = Field(..., description="Sync status")
    message: str = Field(..., description="Upload message") 