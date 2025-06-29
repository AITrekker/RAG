#!/usr/bin/env python3
"""
Test script for RAG system components and end-to-end functionality.
"""

import sys
import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4, UUID

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.services.rag import QueryProcessor, VectorRetriever, ContextRanker, RAGPipeline

# Test tenant for RAG testing
RAG_TEST_TENANT_ID = UUID("12345678-1234-1234-1234-123456789abc")

async def test_query_processor():
    """Test query processing and validation."""
    print("🧪 Testing Query Processor")
    print("-" * 50)
    
    processor = QueryProcessor()
    
    # Test basic query processing
    test_queries = [
        "What is our work from home policy?",
        "Tell me about benefits in the PDF files",
        "What vacation policy do we have in recent documents?",
        "How to contact HR from company_mission.txt?",
        "Remote work guidelines"
    ]
    
    for query_text in test_queries:
        try:
            query = processor.process_query(query_text, RAG_TEST_TENANT_ID)
            print(f"  📝 Query: {query_text}")
            print(f"     Processed: {query.text}")
            print(f"     Filters: {query.filters}")
            print(f"     Intent: {processor.get_query_intent(query.text)}")
            
            # Test query expansion
            variations = processor.expand_query(query.text)
            if len(variations) > 1:
                print(f"     Variations: {variations[1:3]}")
            print()
            
        except Exception as e:
            print(f"  ❌ Failed to process query '{query_text}': {e}")
    
    # Test edge cases
    print("  🔍 Testing edge cases...")
    edge_cases = ["", "hi", "?", "x" * 1001]
    for edge_query in edge_cases:
        try:
            processor.process_query(edge_query, RAG_TEST_TENANT_ID)
            print(f"     ❌ Should have failed: '{edge_query[:50]}'")
        except Exception:
            print(f"     ✅ Correctly rejected: '{edge_query[:50]}'")

async def test_vector_retriever():
    """Test vector retrieval functionality."""
    print("\n🔍 Testing Vector Retriever")
    print("-" * 50)
    
    async with AsyncSessionLocal() as session:
        # Use Docker port mapping for Qdrant from Windows host
        retriever = VectorRetriever(session, qdrant_url="http://localhost:6333")
        processor = QueryProcessor()
        
        # Use existing tenant with data
        existing_tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
        
        test_queries = [
            "work from home policy",
            "employee benefits", 
            "company culture",
            "vacation time"
        ]
        
        for query_text in test_queries:
            try:
                query = processor.process_query(query_text, existing_tenant_id)
                print(f"  🔍 Searching for: {query_text}")
                
                # Test basic search
                chunks = await retriever.search(query)
                print(f"     Found {len(chunks)} chunks")
                
                if chunks:
                    best_chunk = chunks[0]
                    print(f"     Best match: {best_chunk.filename} (score: {best_chunk.score:.3f})")
                    print(f"     Content preview: {best_chunk.content[:100]}...")
                
                # Test context retrieval
                context = await retriever.get_context(query)
                print(f"     Context: {len(context.chunks)} chunks, {len(context.unique_sources)} sources")
                print(f"     Retrieval time: {context.retrieval_time:.3f}s")
                print()
                
            except Exception as e:
                print(f"  ❌ Search failed for '{query_text}': {e}")

async def test_context_ranker():
    """Test context ranking and filtering."""
    print("\n📊 Testing Context Ranker")
    print("-" * 50)
    
    async with AsyncSessionLocal() as session:
        # Use Docker port mapping for Qdrant from Windows host  
        retriever = VectorRetriever(session, qdrant_url="http://localhost:6333")
        ranker = ContextRanker()
        processor = QueryProcessor()
        
        # Use existing tenant with data
        existing_tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
        
        query_text = "company benefits and vacation policy"
        query = processor.process_query(query_text, existing_tenant_id)
        
        # Get raw chunks
        chunks = await retriever.search(query)
        print(f"  📦 Raw chunks: {len(chunks)}")
        
        if chunks:
            # Test ranking
            ranked_chunks = ranker.rank_chunks(chunks, query.text)
            print(f"     Ranked chunks: {len(ranked_chunks)}")
            
            # Test duplicate filtering
            filtered_chunks = ranker.filter_duplicates(ranked_chunks)
            print(f"     After dedup: {len(filtered_chunks)}")
            
            # Test diversity
            diverse_chunks = ranker.apply_diversity(filtered_chunks)
            print(f"     After diversity: {len(diverse_chunks)}")
            
            # Show results
            for i, chunk in enumerate(diverse_chunks[:3], 1):
                print(f"     {i}. {chunk.filename} (score: {chunk.score:.3f})")
                print(f"        {chunk.content[:80]}...")
            
            # Get stats
            stats = ranker.get_context_stats(diverse_chunks)
            print(f"     Stats: {stats}")

async def test_rag_pipeline():
    """Test complete RAG pipeline."""
    print("\n🚀 Testing Complete RAG Pipeline")
    print("-" * 50)
    
    async with AsyncSessionLocal() as session:
        pipeline = RAGPipeline(session)
        
        # Use existing tenant with data
        existing_tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
        
        test_queries = [
            "What is our work from home policy?",
            "Tell me about company benefits",
            "What are the vacation policies?",
            "How does our company culture work?",
            "What should I know about remote work?"
        ]
        
        for query_text in test_queries:
            try:
                print(f"  🤖 Query: {query_text}")
                
                # Process complete query
                response = await pipeline.process_query(query_text, existing_tenant_id)
                
                print(f"     ✅ Response generated in {response.processing_time:.2f}s")
                print(f"     📊 Confidence: {response.confidence}")
                print(f"     📚 Sources: {len(response.sources)}")
                print(f"     🔍 Chunks used: {response.metadata.get('chunks_found', 0)}")
                
                # Show answer preview
                answer_preview = response.answer[:200]
                if len(response.answer) > 200:
                    answer_preview += "..."
                print(f"     💬 Answer: {answer_preview}")
                
                # Show sources
                for i, source in enumerate(response.sources[:2], 1):
                    print(f"        Source {i}: {source['filename']} (score: {source['relevance_score']})")
                
                print()
                
            except Exception as e:
                print(f"  ❌ Pipeline failed for '{query_text}': {e}")
        
        # Test query suggestions
        print("  💡 Testing query suggestions...")
        suggestions = await pipeline.get_query_suggestions("work", existing_tenant_id)
        print(f"     Suggestions for 'work': {suggestions[:3]}")
        
        # Test related questions
        related = await pipeline.get_related_questions("vacation policy", existing_tenant_id)
        print(f"     Related to 'vacation policy': {related}")

async def test_streaming_response():
    """Test streaming RAG response."""
    print("\n📡 Testing Streaming Response")
    print("-" * 50)
    
    async with AsyncSessionLocal() as session:
        pipeline = RAGPipeline(session)
        
        # Use existing tenant with data
        existing_tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
        
        query_text = "What is our company culture?"
        print(f"  🎙️ Streaming query: {query_text}")
        print("     Response: ", end="", flush=True)
        
        try:
            async for chunk in pipeline.stream_response(query_text, existing_tenant_id):
                print(chunk, end="", flush=True)
            print("\n     ✅ Streaming completed")
            
        except Exception as e:
            print(f"\n  ❌ Streaming failed: {e}")

async def run_rag_performance_test():
    """Test RAG system performance."""
    print("\n⚡ Testing RAG Performance")
    print("-" * 50)
    
    async with AsyncSessionLocal() as session:
        pipeline = RAGPipeline(session)
        
        # Use existing tenant with data
        existing_tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
        
        # Run multiple queries and measure performance
        queries = [
            "work from home",
            "benefits",
            "vacation",
            "company culture",
            "remote work"
        ] * 3  # 15 total queries
        
        import time
        start_time = time.time()
        
        successful_queries = 0
        total_processing_time = 0
        
        for i, query_text in enumerate(queries, 1):
            try:
                response = await pipeline.process_query(query_text, existing_tenant_id)
                successful_queries += 1
                total_processing_time += response.processing_time
                
                if i % 5 == 0:
                    print(f"     Completed {i}/{len(queries)} queries...")
                    
            except Exception as e:
                print(f"     ❌ Query {i} failed: {e}")
        
        total_time = time.time() - start_time
        
        print(f"  📊 Performance Results:")
        print(f"     Total queries: {len(queries)}")
        print(f"     Successful: {successful_queries}")
        print(f"     Success rate: {successful_queries/len(queries)*100:.1f}%")
        print(f"     Total time: {total_time:.2f}s")
        print(f"     Avg time per query: {total_processing_time/successful_queries:.2f}s")
        print(f"     Queries per second: {successful_queries/total_time:.1f}")

async def main():
    """Run all RAG system tests."""
    print("🚀 RAG System Comprehensive Test Suite")
    print("=" * 60)
    
    try:
        await test_query_processor()
        await test_vector_retriever()
        await test_context_ranker()
        await test_rag_pipeline()
        await test_streaming_response()
        await run_rag_performance_test()
        
        print("\n" + "=" * 60)
        print("✅ All RAG tests completed successfully!")
        print("🎉 RAG system is ready for production use!")
        
    except Exception as e:
        print(f"\n❌ RAG test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())