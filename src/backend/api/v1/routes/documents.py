"""
Document management API endpoints for the Enterprise RAG Platform.

Handles document upload, listing, and deletion using a Qdrant-based backend.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Security, status
from typing import List
import logging
import tempfile
import os
from pathlib import Path

from .....middleware.tenant_context import get_tenant_from_header
from .....core.document_ingestion import DocumentIngestionPipeline
from .....utils.vector_store import get_vector_store_manager
from .....models.api_models import (
    DocumentListResponse, DocumentUploadResponse, DocumentResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()

def get_ingestion_pipeline(
    tenant_id: str = Depends(get_tenant_from_header),
) -> DocumentIngestionPipeline:
    """Dependency to get the document ingestion pipeline for the current tenant."""
    return DocumentIngestionPipeline(
        tenant_id=tenant_id,
        vector_store_manager=get_vector_store_manager()
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_from_header),
    ingestion_pipeline: DocumentIngestionPipeline = Depends(get_ingestion_pipeline)
):
    """
    Uploads, processes, and indexes a document in one go.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")
        
    # Use a temporary file to handle the upload
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        
        logger.info(f"Temporarily saved uploaded file to {tmp_path}")

        doc_id, chunks = await ingestion_pipeline.ingest_document(file_path=tmp_path)

        return DocumentUploadResponse(
            document_id=doc_id,
            filename=file.filename,
            status="processed",
            chunks_created=len(chunks)
        )
    except Exception as e:
        logger.error(f"Failed to upload document for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload and process document: {e}"
        )
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    tenant_id: str = Depends(get_tenant_from_header),
    vector_store_manager = Depends(get_vector_store_manager)
):
    """
    Lists all documents for the current tenant by fetching metadata from Qdrant.
    NOTE: This can be inefficient and is intended for simple overviews.
    """
    try:
        collection_name = f"tenant_{tenant_id}_documents"
        
        # This is a simplified approach. For production, a more robust
        # metadata storage or a different query strategy would be needed.
        response, _ = vector_store_manager.client.scroll(
            collection_name=collection_name,
            limit=1000, # Adjust limit as needed
            with_payload=["document_id", "source"]
        )
        
        # Deduplicate documents based on document_id
        documents_map = {}
        for point in response:
            doc_id = point.payload.get("document_id")
            if doc_id and doc_id not in documents_map:
                documents_map[doc_id] = DocumentResponse(
                    document_id=doc_id,
                    filename=point.payload.get("source"),
                    status="processed"
                )

        doc_list = list(documents_map.values())

        return DocumentListResponse(
            documents=doc_list,
            total_count=len(doc_list)
        )
    except Exception as e:
        # This can happen if the collection doesn't exist yet
        if "not found" in str(e).lower():
            return DocumentListResponse(documents=[], total_count=0)
            
        logger.error(f"Failed to list documents for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve document list.")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    tenant_id: str = Depends(get_tenant_from_header),
    vector_store_manager = Depends(get_vector_store_manager)
):
    """
    Gets metadata for a specific document by its ID.
    """
    try:
        collection_name = f"tenant_{tenant_id}_documents"
        
        # Scroll to find one point related to this document_id to fetch metadata
        response, _ = vector_store_manager.client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
            ),
            limit=1,
            with_payload=True
        )

        if not response:
            raise HTTPException(status_code=404, detail="Document not found")

        payload = response[0].payload
        return DocumentResponse(
            document_id=document_id,
            filename=payload.get("source"),
            status="processed"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve document {document_id} for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve document information.")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    ingestion_pipeline: DocumentIngestionPipeline = Depends(get_ingestion_pipeline)
):
    """
    Deletes a document and all its associated chunks from the vector store.
    """
    try:
        logger.info(f"Deleting document {document_id} for tenant {ingestion_pipeline.tenant_id}")
        ingestion_pipeline.delete_document(document_id)
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete document.") 