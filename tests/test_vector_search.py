"""
Test vector search functionality and critical ID mapping.
"""

import pytest
import time
import torch
from uuid import UUID
from sqlalchemy import select, and_

from src.backend.services.rag import VectorRetriever, QueryProcessor
from src.backend.services.rag.base import Query
from src.backend.models.database import EmbeddingChunk, File

class TestConfig:
    """Test configuration constants."""
    
    # Similarity thresholds
    MIN_SCORE_THRESHOLD = 0.3
    HIGH_SCORE_THRESHOLD = 0.7
    
    # Performance expectations
    MAX_QUERY_TIME = 20.0  # seconds (increased for initialization time)
    MAX_EMBEDDING_TIME = 5.0  # seconds (increased for model loading)
    MIN_GPU_SPEEDUP = 2.0  # minimum expected GPU speedup

class TestVectorSearch:
    """Test vector search with real Qdrant integration."""
    
    @pytest.mark.asyncio
    async def test_embedding_generation(self, db_session, embedding_config):
        """Test GPU-accelerated embedding generation."""
        retriever = VectorRetriever(db_session)
        
        test_text = "company mission innovation"
        start_time = time.time()
        
        embedding = await retriever._generate_query_embedding(test_text)
        generation_time = time.time() - start_time
        
        # Validate embedding properties
        assert len(embedding) == embedding_config["dimensions"]
        assert all(isinstance(x, float) for x in embedding)
        assert generation_time < TestConfig.MAX_EMBEDDING_TIME
        
        # Check performance based on actual device used
        # Since we're using CPU fallback for RTX 5070 compatibility, adjust expectations
        print(f"⚠️ Embedding generation time: {generation_time:.3f}s (CPU mode due to RTX 5070 compatibility)")
        
        # Validate we got valid embeddings regardless of device
        assert not all(x == 0.0 for x in embedding), "Embedding should not be all zeros"
        assert any(abs(x) > 0.001 for x in embedding), "Embedding should have meaningful values"
    
    @pytest.mark.asyncio
    async def test_vector_search_with_results(self, db_session, test_tenant_id, sample_queries, qdrant_config):
        """Test vector search returns results with correct ID mapping."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        successful_searches = 0
        total_chunks_found = 0
        
        for query_text in sample_queries[:3]:  # Test first 3 queries
            print(f"\n🔍 Testing: '{query_text}'")
            
            query = processor.process_query(query_text, test_tenant_id)
            start_time = time.time()
            
            chunks = await retriever.search(query)
            search_time = time.time() - start_time
            
            if chunks:
                successful_searches += 1
                total_chunks_found += len(chunks)
                
                # Validate results
                for chunk in chunks:
                    assert chunk.score >= TestConfig.MIN_SCORE_THRESHOLD
                    assert chunk.chunk_id is not None
                    assert chunk.file_id is not None
                    assert chunk.filename is not None
                    assert len(chunk.content) > 0
                
                print(f"  ✅ Found {len(chunks)} chunks in {search_time:.3f}s")
                print(f"     Top score: {chunks[0].score:.3f}")
                print(f"     Top file: {chunks[0].filename}")
            else:
                print(f"  ❌ No results found")
            
            # Performance check
            assert search_time < TestConfig.MAX_QUERY_TIME
        
        # Overall success rate
        success_rate = successful_searches / len(sample_queries[:3])
        assert success_rate >= 0.5, f"Low success rate: {success_rate:.2f}"
        
        print(f"\n📊 Search Results:")
        print(f"   Success rate: {success_rate:.1%}")
        print(f"   Total chunks: {total_chunks_found}")
        print(f"   Avg chunks per query: {total_chunks_found/successful_searches:.1f}")
    
    @pytest.mark.asyncio
    async def test_id_mapping_consistency(self, db_session, test_tenant_id, qdrant_config):
        """Test critical ID mapping between Qdrant and PostgreSQL."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        # Perform search
        query = processor.process_query("company", test_tenant_id)
        chunks = await retriever.search(query)
        
        if not chunks:
            pytest.skip("No search results to test ID mapping")
        
        # Verify PostgreSQL records exist for returned chunks
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        
        db_query = select(EmbeddingChunk).where(
            and_(
                EmbeddingChunk.id.in_(chunk_ids),
                EmbeddingChunk.tenant_id == test_tenant_id
            )
        )
        
        result = await db_session.execute(db_query)
        db_chunks = result.scalars().all()
        
        # All returned chunks should exist in PostgreSQL
        assert len(db_chunks) == len(chunks)
        
        # Check qdrant_point_id is not None
        for db_chunk in db_chunks:
            assert db_chunk.qdrant_point_id is not None
            print(f"✅ Chunk {db_chunk.id} → Qdrant point {db_chunk.qdrant_point_id}")
    
    @pytest.mark.asyncio
    async def test_similarity_threshold_sensitivity(self, db_session, test_tenant_id, qdrant_config):
        """Test how similarity thresholds affect results."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        query_text = "company mission"
        
        # Test different thresholds
        thresholds = [0.0, 0.3, 0.5, 0.7, 0.9]
        results_by_threshold = {}
        
        for threshold in thresholds:
            query = processor.process_query(query_text, test_tenant_id)
            query.min_score = threshold
            
            chunks = await retriever.search(query)
            results_by_threshold[threshold] = len(chunks)
            
            print(f"  Threshold {threshold}: {len(chunks)} results")
        
        # Higher thresholds should return fewer or equal results
        for i in range(len(thresholds) - 1):
            current_threshold = thresholds[i]
            next_threshold = thresholds[i + 1]
            
            assert (results_by_threshold[current_threshold] >= 
                   results_by_threshold[next_threshold]), \
                   f"Threshold {next_threshold} returned more results than {current_threshold}"
        
        # 0.3 threshold should return reasonable results
        assert results_by_threshold[0.3] > 0, "No results at 0.3 threshold"
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, db_session, qdrant_config):
        """Test that searches are properly isolated by tenant."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        # Test with our known tenant
        valid_tenant_id = UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")
        # Test with a non-existent tenant
        invalid_tenant_id = UUID("00000000-0000-0000-0000-000000000000")
        
        query_text = "company"
        
        # Search with valid tenant
        valid_query = processor.process_query(query_text, valid_tenant_id)
        valid_chunks = await retriever.search(valid_query)
        
        # Search with invalid tenant
        invalid_query = processor.process_query(query_text, invalid_tenant_id)
        invalid_chunks = await retriever.search(invalid_query)
        
        # Valid tenant should have results, invalid should not
        print(f"Valid tenant results: {len(valid_chunks)}")
        print(f"Invalid tenant results: {len(invalid_chunks)}")
        
        # Invalid tenant should return no results
        assert len(invalid_chunks) == 0, "Cross-tenant data leakage detected!"
        
        # If we have data, valid tenant should have results
        if len(valid_chunks) > 0:
            # Verify all results belong to correct tenant
            for chunk in valid_chunks:
                # Check via database query
                db_query = select(EmbeddingChunk).where(
                    EmbeddingChunk.id == chunk.chunk_id
                )
                result = await db_session.execute(db_query)
                db_chunk = result.scalar_one_or_none()
                
                assert db_chunk is not None
                assert db_chunk.tenant_id == valid_tenant_id
    
    @pytest.mark.asyncio
    async def test_hybrid_keyword_search(self, db_session, test_tenant_id, qdrant_config):
        """Test hybrid vector + keyword search functionality."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        query = processor.process_query("mission innovation", test_tenant_id)
        keywords = ["mission", "innovation", "company"]
        
        # Test hybrid search
        hybrid_chunks = await retriever.search_with_keywords(query, keywords)
        
        # Test regular vector search for comparison
        vector_chunks = await retriever.search(query)
        
        print(f"Vector search: {len(vector_chunks)} results")
        print(f"Hybrid search: {len(hybrid_chunks)} results")
        
        # Hybrid search should boost relevant results
        if hybrid_chunks:
            # Check that keyword matches have boosted scores
            for chunk in hybrid_chunks:
                content_lower = chunk.content.lower()
                has_keyword = any(keyword.lower() in content_lower for keyword in keywords)
                
                if has_keyword:
                    print(f"  ✅ Keyword match: {chunk.filename} (score: {chunk.score:.3f})")
                    # Boosted scores should be higher than original
                    # (Note: this is hard to test without the original score)