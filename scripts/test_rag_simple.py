#!/usr/bin/env python3
"""
Simple RAG test using PostgreSQL keyword search (fallback when Qdrant unavailable).
"""

import sys
import asyncio
from pathlib import Path
from uuid import UUID

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.models.database import EmbeddingChunk, File
from sqlalchemy import select, and_, or_, func

async def simple_keyword_search(query: str, tenant_id: UUID, limit: int = 5):
    """Simple keyword-based search using PostgreSQL."""
    async with AsyncSessionLocal() as session:
        # Split query into keywords
        keywords = [word.lower().strip() for word in query.split() if len(word) > 2]
        
        if not keywords:
            return []
        
        # Build ILIKE conditions for keyword search
        search_conditions = []
        for keyword in keywords:
            search_conditions.append(
                EmbeddingChunk.chunk_content.ilike(f'%{keyword}%')
            )
        
        # Query with joins
        query_stmt = select(EmbeddingChunk, File).join(
            File, EmbeddingChunk.file_id == File.id
        ).where(
            and_(
                EmbeddingChunk.tenant_id == tenant_id,
                File.deleted_at.is_(None),
                or_(*search_conditions)  # Match any keyword
            )
        ).order_by(
            EmbeddingChunk.chunk_index
        ).limit(limit)
        
        result = await session.execute(query_stmt)
        chunks_data = result.all()
        
        results = []
        for chunk, file in chunks_data:
            # Calculate simple relevance score based on keyword matches
            content_lower = chunk.chunk_content.lower()
            matches = sum(1 for keyword in keywords if keyword in content_lower)
            score = matches / len(keywords)
            
            results.append({
                'content': chunk.chunk_content,
                'filename': file.filename,
                'chunk_index': chunk.chunk_index,
                'score': score,
                'file_size': file.file_size
            })
        
        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

async def generate_simple_answer(chunks, query: str):
    """Generate simple answer from chunks."""
    if not chunks:
        return "I couldn't find any relevant information to answer your question."
    
    # Build answer from top chunks
    answer_parts = [f"Based on the information I found:\n"]
    
    for i, chunk in enumerate(chunks[:3], 1):
        content = chunk['content'][:300]
        if len(chunk['content']) > 300:
            content += "..."
        
        answer_parts.append(f"\n{i}. From {chunk['filename']}:")
        answer_parts.append(f"   {content}")
    
    # Add sources summary
    unique_files = list(set(chunk['filename'] for chunk in chunks))
    answer_parts.append(f"\n\nSources: {', '.join(unique_files[:3])}")
    if len(unique_files) > 3:
        answer_parts.append(f" and {len(unique_files) - 3} more")
    
    return "".join(answer_parts)

async def test_simple_rag():
    """Test simple RAG system."""
    print("🚀 Simple RAG Test (PostgreSQL keyword search)")
    print("=" * 60)
    
    # Use existing tenant with data
    tenant_id = UUID('110174a1-8e2f-47a1-af19-1478f1be07a8')
    
    test_queries = [
        "company mission",
        "work culture", 
        "innovation",
        "team collaboration",
        "vacation policy"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        print("-" * 40)
        
        try:
            # Search for relevant chunks
            chunks = await simple_keyword_search(query, tenant_id)
            
            print(f"📦 Found {len(chunks)} relevant chunks")
            
            if chunks:
                # Show top matches
                for i, chunk in enumerate(chunks[:3], 1):
                    print(f"  {i}. {chunk['filename']} (score: {chunk['score']:.2f})")
                    preview = chunk['content'][:100]
                    if len(chunk['content']) > 100:
                        preview += "..."
                    print(f"     {preview}")
                
                # Generate answer
                answer = await generate_simple_answer(chunks, query)
                print(f"\n💬 Answer:")
                print(answer)
            else:
                print("   No relevant content found")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

async def check_data_availability():
    """Check what data is available for testing."""
    print("📊 Data Availability Check")
    print("=" * 60)
    
    tenant_id = UUID('110174a1-8e2f-47a1-af19-1478f1be07a8')
    
    async with AsyncSessionLocal() as session:
        # Check total chunks
        result = await session.execute(
            select(func.count(EmbeddingChunk.id))
            .where(EmbeddingChunk.tenant_id == tenant_id)
        )
        total_chunks = result.scalar()
        print(f"Total chunks for tenant: {total_chunks}")
        
        # Check files
        result = await session.execute(
            select(File.filename, func.count(EmbeddingChunk.id))
            .join(EmbeddingChunk, File.id == EmbeddingChunk.file_id)
            .where(
                and_(
                    File.tenant_id == tenant_id,
                    File.deleted_at.is_(None)
                )
            )
            .group_by(File.filename)
        )
        files_data = result.all()
        
        print(f"\nFiles and chunk counts:")
        for filename, chunk_count in files_data:
            print(f"  {filename}: {chunk_count} chunks")
        
        # Show sample content
        result = await session.execute(
            select(EmbeddingChunk.chunk_content)
            .where(EmbeddingChunk.tenant_id == tenant_id)
            .limit(3)
        )
        sample_chunks = result.scalars().all()
        
        print(f"\nSample content:")
        for i, content in enumerate(sample_chunks, 1):
            preview = content[:150]
            if len(content) > 150:
                preview += "..."
            print(f"  {i}. {preview}")

async def main():
    """Run simple RAG tests."""
    try:
        await check_data_availability()
        print("\n")
        await test_simple_rag()
        
        print("\n" + "=" * 60)
        print("✅ Simple RAG test completed!")
        print("Note: This is a PostgreSQL-only fallback. Full RAG requires Qdrant.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())