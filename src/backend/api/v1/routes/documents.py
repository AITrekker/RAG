"""
Document management API endpoints for the Enterprise RAG Platform.

Handles document upload, listing, and deletion using a Qdrant-based backend.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from typing import List, Optional
import logging
import tempfile
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone

from src.backend.middleware.auth import require_authentication
from src.backend.core.document_service import DocumentService
from src.backend.models.api_models import (
    DocumentListResponse, DocumentUploadResponse, DocumentResponse,
    DocumentUpdateRequest
)
from src.backend.api.v1.providers import get_document_service
from src.backend.utils.vector_store import get_vector_store_manager
from src.backend.core.embeddings import get_embedding_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(require_authentication)
):
    """
    Accepts a document upload and places it in the tenant's directory for asynchronous processing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")

    try:
        # Define the path to the tenant's upload directory
        # This path should be consistent with what DeltaSync scans
        tenant_uploads_path = Path(f"data/tenants/{tenant_id}/uploads")
        tenant_uploads_path.mkdir(parents=True, exist_ok=True)
        
        # Save the file
        file_path = tenant_uploads_path / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Successfully saved uploaded file to {file_path} for tenant {tenant_id}")

        return DocumentUploadResponse(
            filename=file.filename,
            status="accepted_for_processing"
        )
    except Exception as e:
        logger.error(f"Failed to upload document for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save document for processing: {e}"
        )

@router.get("/", response_model=DocumentListResponse, dependencies=[Depends(require_authentication)])
async def list_documents(
    tenant_id: str = Depends(require_authentication),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    Lists all documents for the current tenant.
    """
    try:
        vector_manager = get_vector_store_manager()
        collection_name = vector_manager.get_collection_name_for_tenant(tenant_id)
        
        # Get total count
        try:
            count_result = vector_manager.client.count(collection_name, exact=True)
            total_count = count_result.count
        except Exception:
            total_count = 0
        
        # Get documents with pagination
        offset = (page - 1) * page_size
        documents = []
        
        if total_count > 0:
            try:
                points, _ = vector_manager.client.scroll(
                    collection_name=collection_name,
                    limit=page_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                # Group by file path to get unique documents
                document_map = {}
                for point in points:
                    payload = point.payload or {}
                    file_path = payload.get("metadata", {}).get("file_path")
                    
                    if file_path and file_path not in document_map:
                        document_map[file_path] = {
                            "document_id": point.id,
                            "filename": Path(file_path).name,
                            "upload_timestamp": datetime.fromtimestamp(
                                payload.get("metadata", {}).get("modified_at", 0), 
                                tz=timezone.utc
                            ),
                            "file_size": payload.get("metadata", {}).get("file_size", 0),
                            "status": "processed",
                            "chunks_count": 1,  # This would need to be calculated properly
                            "content_type": payload.get("metadata", {}).get("content_type"),
                            "metadata": payload.get("metadata", {})
                        }
                
                documents = list(document_map.values())
                
            except Exception as e:
                logger.error(f"Error retrieving documents: {e}")
        
        return DocumentListResponse(
            documents=documents,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing documents for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")

@router.get("/{document_id}", response_model=DocumentResponse, dependencies=[Depends(require_authentication)])
async def get_document(
    document_id: str,
    tenant_id: str = Depends(require_authentication),
):
    """
    Gets metadata for a specific document.
    """
    try:
        vector_manager = get_vector_store_manager()
        collection_name = vector_manager.get_collection_name_for_tenant(tenant_id)
        
        # Get the specific point
        points = vector_manager.client.retrieve(
            collection_name=collection_name,
            ids=[document_id],
            with_payload=True
        )
        
        if not points:
            raise HTTPException(status_code=404, detail="Document not found")
        
        point = points[0]
        payload = point.payload or {}
        metadata = payload.get("metadata", {})
        
        # Count chunks for this document
        file_path = metadata.get("file_path")
        chunks_count = 0
        if file_path:
            try:
                # Count points with same file_path
                all_points, _ = vector_manager.client.scroll(
                    collection_name=collection_name,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                chunks_count = sum(1 for p in all_points if p.payload.get("metadata", {}).get("file_path") == file_path)
            except Exception:
                chunks_count = 1
        
        return DocumentResponse(
            document_id=point.id,
            filename=Path(file_path).name if file_path else "Unknown",
            upload_timestamp=datetime.fromtimestamp(
                metadata.get("modified_at", 0), 
                tz=timezone.utc
            ),
            file_size=metadata.get("file_size", 0),
            status="processed",
            chunks_count=chunks_count,
            content_type=metadata.get("content_type"),
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id} for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document")

@router.put("/{document_id}", response_model=DocumentResponse, dependencies=[Depends(require_authentication)])
async def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    tenant_id: str = Depends(require_authentication),
):
    """
    Update document metadata.
    """
    # This would need to be implemented in DocumentService
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Document update not yet implemented"
    )

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_authentication)])
async def delete_document(
    document_id: str,
    tenant_id: str = Depends(require_authentication),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Deletes a document.
    """
    try:
        document_service.delete_document(document_id)
    except ValueError as e:
        # This occurs if the document_id is not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting document {document_id} for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete document.")

@router.get("/search/semantic", dependencies=[Depends(require_authentication)])
async def search_documents(
    query: str = Query(..., min_length=1, description="Search query"),
    tenant_id: str = Depends(require_authentication),
    top_k: int = Query(10, ge=1, le=50, description="Number of results to return")
):
    """
    Perform semantic search across documents.
    """
    try:
        embedding_service = get_embedding_service()
        vector_manager = get_vector_store_manager()
        
        # Generate query embedding
        query_embedding = embedding_service.encode_texts([query])[0]
        
        # Search in vector store
        search_results = vector_manager.similarity_search(
            tenant_id=tenant_id,
            query_embedding=query_embedding,
            top_k=top_k
        )
        
        # Format results
        results = []
        for point in search_results:
            payload = point.payload or {}
            metadata = payload.get("metadata", {})
            
            results.append({
                "id": point.id,
                "score": point.score,
                "text": payload.get("content", "")[:200] + "...",  # Truncate for preview
                "filename": Path(metadata.get("file_path", "")).name,
                "file_path": metadata.get("file_path"),
                "page_number": metadata.get("page_number"),
                "chunk_index": metadata.get("chunk_index")
            })
        
        return {
            "query": query,
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error searching documents for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search documents") 