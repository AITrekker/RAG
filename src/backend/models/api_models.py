"""
Pydantic models for API request and response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class SyncStatus(str, Enum):
    """Sync operation status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncType(str, Enum):
    """Type of sync operation."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    AUTO = "auto"


class DocumentSyncInfo(BaseModel):
    """Information about a synchronized document."""
    filename: str = Field(..., description="Document filename")
    file_path: str = Field(..., description="Full file path")
    file_size: int = Field(..., description="File size in bytes")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    status: str = Field(..., description="Processing status")
    chunks_created: Optional[int] = Field(None, description="Number of chunks created")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class RAGSource(BaseModel):
    """Represents a single source document chunk used for an answer."""
    id: str = Field(..., description="The unique ID of the document chunk.")
    text: str = Field(..., description="The text content of the chunk.")
    score: float = Field(..., description="The relevance score of the chunk.")
    filename: Optional[str] = Field(None, description="The name of the source document.")
    page_number: Optional[int] = Field(None, description="The page number in the source document.")
    chunk_index: Optional[int] = Field(None, description="The index of the chunk within the document.")

class RAGResponse(BaseModel):
    """The response model for a RAG query."""
    query: str = Field(..., description="The original query text.")
    answer: str = Field(..., description="The generated answer from the LLM.")
    sources: List[RAGSource] = Field(..., description="A list of source chunks that informed the answer.")
    confidence: float = Field(..., description="The calculated confidence score for the answer.")
    processing_time: Optional[float] = Field(None, description="The total time taken to process the query in seconds.")
    llm_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata from the LLM, such as model name and token counts.")

class QueryRequest(BaseModel):
    """The request model for submitting a query."""
    query: str = Field(..., min_length=3, max_length=500, description="The user's query.")
    tenant_id: Optional[str] = Field(None, description="The tenant ID to scope the query to. If not provided, a default may be used based on context.")

class SourceCitation(BaseModel):
    """Represents a single source document chunk used for an answer."""
    id: str = Field(..., description="The unique ID of the document chunk.")
    text: str = Field(..., description="The text content of the chunk.")
    score: float = Field(..., description="The relevance score of the chunk.")
    filename: Optional[str] = Field(None, description="The name of the source document.")
    page_number: Optional[int] = Field(None, description="The page number in the source document.")
    chunk_index: Optional[int] = Field(None, description="The index of the chunk within the document.")
    
class QueryResponse(BaseModel):
    """The response model for a RAG query."""
    query: str = Field(..., description="The original query text.")
    answer: str = Field(..., description="The generated answer from the LLM.")
    sources: List[SourceCitation] = Field(..., description="A list of source chunks that informed the answer.")
    confidence: float = Field(..., description="The calculated confidence score for the answer.")
    processing_time: Optional[float] = Field(None, description="The total time taken to process the query in seconds.")
    llm_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata from the LLM, such as model name and token counts.")

class QueryHistory(BaseModel):
    """Represents a single entry in the query history."""
    id: UUID
    query: str
    response: QueryResponse
    timestamp: datetime
    tenant_id: str

# Models from tenants.py
class TenantCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class TenantResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    class Config:
        from_attributes = True

class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]

class TenantStatsResponse(BaseModel):
    document_count: int
    storage_used_mb: float

class SyncRequest(BaseModel):
    force_full_resync: Optional[bool] = False

class SyncResponse(BaseModel):
    """Response model for sync operations."""
    sync_id: str = Field(..., description="Unique sync operation identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    status: SyncStatus = Field(..., description="Current sync status")
    sync_type: SyncType = Field(..., description="Type of sync operation")
    started_at: datetime = Field(..., description="Sync start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Sync completion timestamp")
    total_files: int = Field(default=0, description="Total number of files to process")
    processed_files: int = Field(default=0, description="Number of files processed")
    successful_files: int = Field(default=0, description="Number of successfully processed files")
    failed_files: int = Field(default=0, description="Number of failed files")
    total_chunks: int = Field(default=0, description="Total number of chunks created")
    processing_time: Optional[float] = Field(None, description="Total processing time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    documents: List[DocumentSyncInfo] = Field(default_factory=list, description="Processed documents")

class SyncScheduleResponse(BaseModel):
    schedule_id: str
    tenant_id: str
    cron_expression: str
    next_run_time: Optional[datetime]
    is_active: bool

class SyncScheduleUpdateRequest(BaseModel):
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None

# Models from sync.py and audit.py
class SyncEventResponse(BaseModel):
    id: int
    sync_run_id: str
    tenant_id: str
    event_type: str
    status: str
    message: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class SyncHistoryResponse(BaseModel):
    """Response model for sync history."""
    syncs: List[SyncResponse] = Field(default_factory=list, description="List of sync operations")
    total_count: int = Field(..., description="Total number of sync operations")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of syncs per page")


# Document Management Models
class DocumentMetadata(BaseModel):
    """Document metadata model."""
    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    description: Optional[str] = Field(None, description="Document description")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")


class DocumentResponse(BaseModel):
    """Response model for document information."""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    upload_timestamp: datetime = Field(..., description="Upload timestamp")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Processing status (uploaded, processing, processed, failed)")
    chunks_count: int = Field(default=0, description="Number of chunks created")
    content_type: Optional[str] = Field(None, description="MIME content type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    file_size: int = Field(..., description="File size in bytes")
    upload_timestamp: datetime = Field(..., description="Upload timestamp")


class DocumentListResponse(BaseModel):
    """Response model for document listing."""
    documents: List[DocumentResponse] = Field(default_factory=list, description="List of documents")
    total_count: int = Field(..., description="Total number of documents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of documents per page")


class DocumentUpdateRequest(BaseModel):
    """Request model for updating document metadata."""
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    tags: Optional[List[str]] = Field(None, description="Updated tags") 