"""
Test complete RAG pipeline functionality.
"""

import pytest
import time
from uuid import UUID

from src.backend.services.rag import RAGPipeline, QueryProcessor, VectorRetriever, ContextRanker
from src.backend.services.rag.base import Query, RAGResponse

class TestConfig:
    """Test configuration constants."""
    MIN_SCORE_THRESHOLD = 0.3
    MAX_QUERY_TIME = 2.0

class TestRAGPipeline:
    """Test complete RAG pipeline from query to response."""
    
    @pytest.mark.asyncio
    async def test_complete_rag_pipeline(self, db_session, test_tenant_id, sample_queries, qdrant_config):
        """Test end-to-end RAG pipeline."""
        pipeline = RAGPipeline(db_session)
        
        # Override retriever with correct Qdrant URL
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        successful_queries = 0
        total_processing_time = 0
        
        for query_text in sample_queries[:4]:  # Test first 4 queries
            print(f"\n🔍 Testing RAG Pipeline: '{query_text}'")
            
            start_time = time.time()
            
            try:
                response = await pipeline.process_query(query_text, test_tenant_id)
                processing_time = time.time() - start_time
                total_processing_time += processing_time
                
                # Validate response structure
                assert isinstance(response, RAGResponse)
                assert response.answer is not None
                assert len(response.answer) > 0
                assert isinstance(response.sources, list)
                assert response.confidence >= 0.0
                assert response.confidence <= 1.0
                assert response.processing_time > 0
                assert response.query == query_text
                assert response.tenant_id == test_tenant_id
                
                # Performance check
                assert processing_time < TestConfig.MAX_QUERY_TIME
                
                successful_queries += 1
                
                print(f"  ✅ Generated answer ({len(response.answer)} chars)")
                print(f"     Sources: {len(response.sources)}")
                print(f"     Confidence: {response.confidence:.3f}")
                print(f"     Time: {processing_time:.3f}s")
                print(f"     Answer preview: {response.answer[:100]}...")
                
            except Exception as e:
                print(f"  ❌ Pipeline failed: {e}")
        
        # Overall success rate
        success_rate = successful_queries / len(sample_queries[:4])
        avg_time = total_processing_time / successful_queries if successful_queries > 0 else 0
        
        print(f"\n📊 Pipeline Results:")
        print(f"   Success rate: {success_rate:.1%}")
        print(f"   Avg processing time: {avg_time:.3f}s")
        
        assert success_rate >= 0.5, f"Low RAG success rate: {success_rate:.2f}"
    
    @pytest.mark.asyncio
    async def test_query_processor_validation(self, test_tenant_id):
        """Test query processing and validation."""
        processor = QueryProcessor()
        
        # Test basic query processing
        query = processor.process_query("What is the company mission?", test_tenant_id)
        
        assert isinstance(query, Query)
        assert query.text == "What is the company mission?"
        assert query.tenant_id == test_tenant_id
        assert query.min_score == TestConfig.MIN_SCORE_THRESHOLD
        assert query.max_results > 0
        assert isinstance(query.filters, dict)
        
        # Test filter extraction
        filtered_text, filters = processor.extract_filters(
            "Show me recent PDF documents about vacation policy"
        )
        
        assert "recent" in filters or "temporal" in filters
        assert "pdf" in str(filters).lower() or "file_types" in filters
        
        print(f"✅ Filter extraction: {filters}")
    
    @pytest.mark.asyncio
    async def test_context_ranking(self, db_session, test_tenant_id, qdrant_config):
        """Test context ranking and deduplication."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        ranker = ContextRanker()
        processor = QueryProcessor()
        
        # Get some chunks to rank
        query = processor.process_query("company mission", test_tenant_id)
        chunks = await retriever.search(query)
        
        if not chunks:
            pytest.skip("No chunks available for ranking test")
        
        # Test ranking
        ranked_chunks = ranker.rank_chunks(chunks, query.text)
        
        # Should return same or fewer chunks
        assert len(ranked_chunks) <= len(chunks)
        
        # Should be sorted by score (descending)
        for i in range(len(ranked_chunks) - 1):
            assert ranked_chunks[i].score >= ranked_chunks[i + 1].score
        
        # Test deduplication
        deduplicated_chunks = ranker.filter_duplicates(chunks)
        
        # Should not increase the number of chunks
        assert len(deduplicated_chunks) <= len(chunks)
        
        print(f"✅ Ranking: {len(chunks)} → {len(ranked_chunks)} chunks")
        print(f"✅ Deduplication: {len(chunks)} → {len(deduplicated_chunks)} chunks")
    
    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, db_session, test_tenant_id):
        """Test RAG pipeline error handling."""
        # Test with invalid Qdrant URL
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url="http://invalid:6333")
        
        # Should handle gracefully
        response = await pipeline.process_query("test query", test_tenant_id)
        
        # Should return a valid response even with errors
        assert isinstance(response, RAGResponse)
        assert response.answer is not None
        assert len(response.sources) == 0  # No sources due to error
        assert response.confidence == 0.0  # Low confidence due to error
        
        print("✅ Error handling: Pipeline gracefully handles Qdrant failures")
    
    @pytest.mark.asyncio
    async def test_source_citation_accuracy(self, db_session, test_tenant_id, qdrant_config):
        """Test that source citations are accurate."""
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        response = await pipeline.process_query("company mission", test_tenant_id)
        
        if not response.sources:
            pytest.skip("No sources returned to test citations")
        
        # Validate source structure
        for source in response.sources:
            assert "filename" in source
            assert "file_id" in source
            assert "score" in source
            assert source["filename"] is not None
            assert source["file_id"] is not None
            assert isinstance(source["score"], (int, float))
            assert source["score"] >= 0
            
            print(f"✅ Source: {source['filename']} (score: {source['score']:.3f})")
        
        # Check source uniqueness
        filenames = [source["filename"] for source in response.sources]
        unique_filenames = set(filenames)
        
        print(f"✅ Source diversity: {len(unique_filenames)} unique files from {len(filenames)} sources")
    
    @pytest.mark.asyncio
    async def test_pipeline_performance_characteristics(self, db_session, test_tenant_id, qdrant_config):
        """Test performance characteristics of the pipeline."""
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        # Test queries of different lengths
        test_cases = [
            ("short", "mission"),
            ("medium", "company mission and values"),
            ("long", "What is the company mission and how does it relate to our values and culture?"),
            ("complex", "Show me information about remote work policies, vacation time, and team collaboration processes")
        ]
        
        results = {}
        
        for case_name, query_text in test_cases:
            print(f"\n🔍 Testing {case_name} query: '{query_text[:50]}...'")
            
            start_time = time.time()
            response = await pipeline.process_query(query_text, test_tenant_id)
            processing_time = time.time() - start_time
            
            results[case_name] = {
                "time": processing_time,
                "answer_length": len(response.answer),
                "source_count": len(response.sources),
                "confidence": response.confidence
            }
            
            print(f"  Time: {processing_time:.3f}s")
            print(f"  Answer: {len(response.answer)} chars")
            print(f"  Sources: {len(response.sources)}")
            print(f"  Confidence: {response.confidence:.3f}")
        
        # Performance assertions
        for case_name, metrics in results.items():
            assert metrics["time"] < TestConfig.MAX_QUERY_TIME, f"{case_name} query too slow"
            assert metrics["answer_length"] > 0, f"{case_name} query produced no answer"
        
        print(f"\n📊 Performance Summary:")
        for case_name, metrics in results.items():
            print(f"  {case_name}: {metrics['time']:.3f}s, {metrics['source_count']} sources")
    
    @pytest.mark.asyncio
    async def test_query_context_preservation(self, db_session, test_tenant_id, qdrant_config):
        """Test that query context is preserved through the pipeline."""
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        original_query = "What are the company core values and mission?"
        
        response = await pipeline.process_query(original_query, test_tenant_id)
        
        # Check that original query is preserved
        assert response.query == original_query
        assert response.tenant_id == test_tenant_id
        
        # Check that context is related to the query
        answer_lower = response.answer.lower()
        query_terms = ["company", "values", "mission"]
        
        relevance_score = sum(1 for term in query_terms if term in answer_lower)
        
        print(f"✅ Query relevance: {relevance_score}/{len(query_terms)} terms found in answer")
        
        # Should find at least some relevant terms
        assert relevance_score > 0, "Generated answer not relevant to query"