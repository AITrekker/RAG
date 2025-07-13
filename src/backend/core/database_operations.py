"""
Database Operations - Simple CRUD for Files and Embeddings
Clean database interactions without complex service layers
"""

from typing import List, Optional
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload

from src.backend.models.database import File, EmbeddingChunk
from src.backend.core.document_discovery import FileInfo
from src.backend.core.embedding_engine import EmbeddedChunk


async def create_file_record(
    db: AsyncSession,
    tenant_slug: str,
    file_info: FileInfo,
    status: str = "processing"
) -> File:
    """Create a new file record in database"""
    file_record = File(
        tenant_slug=tenant_slug,
        filename=file_info.name,
        file_path=file_info.path,
        file_size=file_info.size,
        file_hash=file_info.hash,
        sync_status=status
    )
    
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)
    return file_record


async def update_file_record(
    db: AsyncSession,
    file_record: File,
    file_info: FileInfo,
    status: str = "processing"
) -> File:
    """Update existing file record"""
    file_record.file_hash = file_info.hash
    file_record.file_size = file_info.size
    file_record.sync_status = status
    
    await db.commit()
    await db.refresh(file_record)
    return file_record


async def delete_file_record(db: AsyncSession, file_record: File) -> None:
    """Delete file record and all its embeddings"""
    # Delete embeddings first
    await db.execute(
        delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_record.id)
    )
    
    # Delete file record
    await db.delete(file_record)
    await db.commit()


async def set_file_status(
    db: AsyncSession,
    file_record: File,
    status: str,
    error_message: Optional[str] = None
) -> None:
    """Update file sync status"""
    file_record.sync_status = status
    if error_message:
        file_record.sync_error = error_message
    
    await db.commit()


async def save_embeddings(
    db: AsyncSession,
    file_record: File,
    embedded_chunks
) -> int:
    """Save embeddings to database (supports both old and new format)"""
    if not embedded_chunks:
        return 0
    
    # Delete existing embeddings for this file
    await db.execute(
        delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_record.id)
    )
    
    # Create new embedding records
    embedding_records = []
    
    # Handle both old EmbeddedChunk objects and new simple dict format
    for i, embedded_chunk in enumerate(embedded_chunks):
        if isinstance(embedded_chunk, dict):
            # New simple format from simple_embedder
            import hashlib
            chunk_text = embedded_chunk["text"]
            chunk_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            
            embedding_record = EmbeddingChunk(
                file_id=file_record.id,
                tenant_slug=file_record.tenant_slug,
                chunk_index=embedded_chunk["index"],
                chunk_content=chunk_text,
                chunk_hash=chunk_hash,
                token_count=len(chunk_text.split()),
                embedding=embedded_chunk["embedding"],
                embedding_model=embedded_chunk["model"]
            )
        else:
            # Old EmbeddedChunk object format (for backward compatibility)
            chunk = embedded_chunk.chunk
            embedding_record = EmbeddingChunk(
                file_id=file_record.id,
                tenant_slug=file_record.tenant_slug,
                chunk_index=chunk.index,
                text=chunk.text,
                token_count=getattr(chunk, 'token_count', None),
                start_char=getattr(chunk, 'start_char', None),
                end_char=getattr(chunk, 'end_char', None),
                embedding=embedded_chunk.embedding,
                embedding_model=embedded_chunk.embedding_model
            )
        embedding_records.append(embedding_record)
    
    # Bulk insert
    db.add_all(embedding_records)
    await db.commit()
    
    return len(embedding_records)


async def get_file_by_path(db: AsyncSession, tenant_slug: str, file_path: str) -> Optional[File]:
    """Get file record by path"""
    result = await db.execute(
        select(File).where(
            File.tenant_slug == tenant_slug,
            File.file_path == file_path
        )
    )
    return result.scalar_one_or_none()


async def get_files_for_tenant(db: AsyncSession, tenant_slug: str) -> List[File]:
    """Get all files for a tenant"""
    result = await db.execute(
        select(File).where(File.tenant_slug == tenant_slug)
    )
    return result.scalars().all()


async def get_embeddings_for_file(db: AsyncSession, file_id) -> List[EmbeddingChunk]:
    """Get all embeddings for a file"""
    result = await db.execute(
        select(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
        .order_by(EmbeddingChunk.chunk_index)
    )
    return result.scalars().all()


async def search_embeddings(
    db: AsyncSession,
    tenant_slug: str,
    query_embedding: List[float],
    limit: int = 10,
    similarity_threshold: float = 0.0
) -> List[EmbeddingChunk]:
    """Search for similar embeddings using cosine similarity"""
    # Convert query embedding to pgvector format
    query_vector = f"[{','.join(map(str, query_embedding))}]"
    
    # Use pgvector cosine similarity
    result = await db.execute(
        select(EmbeddingChunk)
        .where(EmbeddingChunk.tenant_slug == tenant_slug)
        .order_by(EmbeddingChunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    
    embeddings = result.scalars().all()
    
    # Filter by threshold if specified
    if similarity_threshold > 0.0:
        # Note: cosine_distance returns distance (lower is better)
        # You might want to calculate actual similarity and filter
        pass
    
    return embeddings


async def get_tenant_stats(db: AsyncSession, tenant_slug: str) -> dict:
    """Get statistics for a tenant"""
    # Count files
    file_result = await db.execute(
        select(File).where(File.tenant_slug == tenant_slug)
    )
    files = file_result.scalars().all()
    
    # Count embeddings
    embedding_result = await db.execute(
        select(EmbeddingChunk).where(EmbeddingChunk.tenant_slug == tenant_slug)
    )
    embeddings = embedding_result.scalars().all()
    
    # Status breakdown
    status_counts = {}
    for file in files:
        status = file.sync_status
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "total_files": len(files),
        "total_chunks": len(embeddings),
        "status_breakdown": status_counts,
        "files_by_status": {
            "completed": [f for f in files if f.sync_status == "completed"],
            "processing": [f for f in files if f.sync_status == "processing"],
            "failed": [f for f in files if f.sync_status == "failed"],
            "pending": [f for f in files if f.sync_status == "pending"]
        }
    }


async def cleanup_orphaned_embeddings(db: AsyncSession) -> int:
    """Clean up embeddings that don't have corresponding file records"""
    # Find embeddings without files
    result = await db.execute(
        select(EmbeddingChunk)
        .outerjoin(File, EmbeddingChunk.file_id == File.id)
        .where(File.id.is_(None))
    )
    orphaned = result.scalars().all()
    
    if orphaned:
        # Delete orphaned embeddings
        orphaned_ids = [e.id for e in orphaned]
        await db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.id.in_(orphaned_ids))
        )
        await db.commit()
    
    return len(orphaned)


async def reset_failed_files(db: AsyncSession, tenant_slug: str) -> int:
    """Reset failed files to pending for retry"""
    result = await db.execute(
        update(File)
        .where(
            File.tenant_slug == tenant_slug,
            File.sync_status == "failed"
        )
        .values(sync_status="pending", sync_error=None)
    )
    await db.commit()
    return result.rowcount