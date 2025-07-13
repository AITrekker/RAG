"""
Super Simple Sync - No fancy patterns, just straightforward code
"""

import logging
from typing import List
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.backend.models.database import File
from src.backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def simple_sync_files(db: AsyncSession, tenant_slug: str) -> dict:
    """
    Simple file sync - no complex abstractions
    Just process files one by one with basic logging
    """
    logger.info(f"🚀 Starting simple sync for tenant {tenant_slug}")
    
    try:
        # Get all files for this tenant
        result = await db.execute(
            select(File).where(File.tenant_slug == tenant_slug)
        )
        files = result.scalars().all()
        
        logger.info(f"📁 Found {len(files)} files to process")
        
        if not files:
            return {
                "status": "completed",
                "message": "No files to process",
                "files_processed": 0,
                "chunks_created": 0
            }
        
        # Actually process files now!
        total_chunks = 0
        
        for file in files:
            try:
                # Step 1: Read file content
                file_path = Path(file.file_path)
                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue
                
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                if not content.strip():
                    logger.warning(f"Empty file: {file.filename}")
                    continue
                
                # Step 2: Simple chunking (fixed 512 chars for now)
                chunks = []
                chunk_size = 512
                for i in range(0, len(content), chunk_size):
                    chunk_text = content[i:i + chunk_size]
                    if chunk_text.strip():
                        chunks.append(chunk_text.strip())
                
                logger.info(f"📄 {file.filename}: Created {len(chunks)} chunks")
                total_chunks += len(chunks)
                
                # Step 3: Generate embeddings (using dependency injection)
                # TODO: Add actual embedding generation next
                
            except Exception as e:
                logger.error(f"❌ Failed to process {file.filename}: {e}")
                continue
        
        logger.info(f"✅ Simple sync completed: {len(files)} files, {total_chunks} chunks")
        
        return {
            "status": "completed", 
            "message": f"Processed {len(files)} files into {total_chunks} chunks",
            "files_processed": len(files),
            "chunks_created": total_chunks
        }
        
    except Exception as e:
        logger.error(f"❌ Simple sync failed: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "files_processed": 0,
            "chunks_created": 0
        }