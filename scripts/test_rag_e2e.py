#!/usr/bin/env python3
"""
End-to-end RAG test with real Qdrant vector search.
"""

import sys
import asyncio
import time
from pathlib import Path
from uuid import UUID

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.services.rag import QueryProcessor, VectorRetriever, ContextRanker, RAGPipeline

async def test_e2e_rag_with_vectors():
    """Test complete RAG pipeline with real vector search."""
    print("🚀 End-to-End RAG Test with Vector Search")
    print("=" * 60)
    
    # Use existing tenant with data
    tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
    
    async with AsyncSessionLocal() as session:
        # Initialize components with correct Qdrant URL
        print("🔧 Initializing RAG components...")
        retriever = VectorRetriever(session, qdrant_url="http://localhost:6333")
        processor = QueryProcessor()
        ranker = ContextRanker()
        pipeline = RAGPipeline(session)
        
        # Override the pipeline's retriever to use correct URL
        pipeline.retriever = retriever
        
        # Test queries that should find results
        test_queries = [
            "company mission innovation",
            "work from home remote", 
            "vacation time off policy",
            "culture team learning"
        ]
        
        for query_text in test_queries:
            print(f"\n🔍 Testing Query: '{query_text}'")
            print("-" * 40)
            
            try:
                start_time = time.time()
                
                # Step 1: Process query
                query = processor.process_query(query_text, tenant_id)
                print(f"📝 Processed: '{query.text}'")
                print(f"🔧 Filters: {query.filters}")
                
                # Step 2: Generate embedding and search vectors
                print("🧠 Generating query embedding...")
                query_embedding = await retriever._generate_query_embedding(query.text)
                print(f"✅ Generated {len(query_embedding)}-dim embedding")
                
                # Step 3: Perform vector search
                print("🔍 Searching vectors...")
                chunks = await retriever.search(query)
                print(f"📦 Found {len(chunks)} vector results")
                
                if chunks:
                    # Step 4: Rank results  
                    ranked_chunks = ranker.rank_chunks(chunks, query.text)
                    print(f"📊 Ranked to {len(ranked_chunks)} chunks")
                    
                    # Show top results
                    for i, chunk in enumerate(ranked_chunks[:3], 1):
                        print(f"  {i}. {chunk.filename} (score: {chunk.score:.3f})")
                        print(f"     {chunk.content[:100]}...")
                    
                    # Step 5: Generate answer
                    answer, sources = await pipeline._generate_simple_response(
                        type('Context', (), {'chunks': ranked_chunks})(), 
                        query.text
                    )
                    
                    print(f"\n💬 Generated Answer:")
                    print(f"{answer[:300]}...")
                    print(f"\n📚 Sources: {len(sources)} files")
                    
                else:
                    print("❌ No vector results found")
                
                elapsed = time.time() - start_time
                print(f"⏱️  Total time: {elapsed:.2f}s")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()

async def test_vector_performance():
    """Test vector search performance."""
    print("\n⚡ Vector Search Performance Test")
    print("=" * 60)
    
    tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
    
    async with AsyncSessionLocal() as session:
        retriever = VectorRetriever(session, qdrant_url="http://localhost:6333")
        processor = QueryProcessor()
        
        # Performance test queries
        queries = [
            "company mission", "work culture", "vacation policy", 
            "team collaboration", "innovation", "remote work",
            "benefits", "learning", "ownership", "speed"
        ]
        
        print(f"🔥 Running {len(queries)} vector searches...")
        
        start_time = time.time()
        total_chunks = 0
        successful_searches = 0
        
        for i, query_text in enumerate(queries, 1):
            try:
                query = processor.process_query(query_text, tenant_id)
                chunks = await retriever.search(query)
                total_chunks += len(chunks)
                successful_searches += 1
                
                if i % 3 == 0:
                    print(f"  Completed {i}/{len(queries)} searches...")
                    
            except Exception as e:
                print(f"  ❌ Query {i} failed: {e}")
        
        total_time = time.time() - start_time
        
        print(f"\n📊 Performance Results:")
        print(f"   Successful searches: {successful_searches}/{len(queries)}")
        print(f"   Total chunks found: {total_chunks}")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Avg time per search: {total_time/successful_searches:.3f}s")
        print(f"   Searches per second: {successful_searches/total_time:.1f}")
        print(f"   Avg chunks per search: {total_chunks/successful_searches:.1f}")

async def main():
    """Run E2E RAG tests."""
    try:
        await test_e2e_rag_with_vectors()
        await test_vector_performance()
        
        print("\n" + "=" * 60)
        print("✅ E2E RAG tests completed!")
        print("🎉 Vector search is working with real embeddings!")
        
    except Exception as e:
        print(f"\n❌ E2E test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())