#!/usr/bin/env python3
"""
Simple test to debug embedding generation
"""

import asyncio
import sys
import os
sys.path.append('/app/src')

from src.backend.database import AsyncSessionLocal, init_database
from src.backend.services.embedding_service import EmbeddingService
from src.backend.models.database import File
from uuid import UUID

async def test_embedding():
    await init_database()
    
    async with AsyncSessionLocal() as session:
        # Create a test file record
        file_record = File(
            tenant_id=UUID("d188b61c-4380-4ec0-93be-98cf1e8a0c2c"),
            uploaded_by=UUID("02e757b0-7c17-4c15-853b-bcf99e8e3584"),
            filename="company_mission.txt",
            file_path="d188b61c-4380-4ec0-93be-98cf1e8a0c2c/company_mission.txt",
            file_size=335,
            file_hash="test",
            sync_status='pending'
        )
        
        # Test embedding service
        embedding_service = EmbeddingService(session)
        await embedding_service.initialize()
        
        print("🧠 Testing file processing...")
        try:
            chunks = await embedding_service.process_file(file_record)
            print(f"✅ Generated {len(chunks)} chunks")
            
            if chunks:
                print(f"📝 First chunk: {chunks[0].content[:100]}...")
                
                print("🔢 Testing embedding generation...")
                embeddings = await embedding_service.generate_embeddings(chunks)
                print(f"✅ Generated {len(embeddings)} embeddings")
                print(f"🔢 Embedding dimension: {len(embeddings[0].vector)}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_embedding())