"""
Performance and benchmark tests for RAG system.
"""

import pytest
import time
import asyncio
import statistics
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from src.backend.services.rag import RAGPipeline, VectorRetriever, QueryProcessor

class TestConfig:
    """Test configuration constants."""
    MAX_QUERY_TIME = 2.0
    MAX_EMBEDDING_TIME = 1.0
    MIN_GPU_SPEEDUP = 2.0
    MIN_SCORE_THRESHOLD = 0.3

class TestPerformance:
    """Performance and scalability tests."""
    
    @pytest.mark.asyncio
    async def test_embedding_generation_performance(self, db_session, embedding_config):
        """Test embedding generation performance and GPU acceleration."""
        retriever = VectorRetriever(db_session)
        
        test_texts = [
            "short query",
            "medium length query about company policies",
            "This is a longer query that contains more detailed information about the company's remote work policies, vacation time, and team collaboration processes.",
            "This is an even longer query that simulates a complex user question about multiple topics including company mission, values, culture, benefits, career development, performance reviews, and workplace policies that might be asked in a real-world scenario."
        ]
        
        times = []
        
        print("\n⚡ Embedding Generation Performance Test")
        print("=" * 60)
        
        for i, text in enumerate(test_texts, 1):
            length_category = ["Short", "Medium", "Long", "Very Long"][i-1]
            
            # Warm up (first call loads the model)
            if i == 1:
                await retriever._generate_query_embedding(text)
            
            # Actual measurement
            start_time = time.time()
            embedding = await retriever._generate_query_embedding(text)
            generation_time = time.time() - start_time
            
            times.append(generation_time)
            
            print(f"{length_category:10} ({len(text):3d} chars): {generation_time:.4f}s")
            
            # Validate embedding
            assert len(embedding) == embedding_config["dimensions"]
            assert generation_time < TestConfig.MAX_EMBEDDING_TIME
        
        avg_time = statistics.mean(times)
        std_time = statistics.stdev(times) if len(times) > 1 else 0
        
        print(f"\nPerformance Summary:")
        print(f"Average: {avg_time:.4f}s ± {std_time:.4f}s")
        print(f"Range: {min(times):.4f}s - {max(times):.4f}s")
        
        # GPU acceleration check
        import torch
        if torch.cuda.is_available():
            print(f"✅ GPU acceleration detected (CUDA available)")
            assert avg_time < 0.5, f"GPU should be faster: {avg_time:.4f}s"
        else:
            print(f"⚠️  CPU fallback mode")
    
    @pytest.mark.asyncio
    async def test_vector_search_throughput(self, db_session, test_tenant_id, qdrant_config, sample_queries):
        """Test vector search throughput and latency."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        # Prepare queries
        queries = [processor.process_query(q, test_tenant_id) for q in sample_queries]
        
        print(f"\n🔍 Vector Search Throughput Test ({len(queries)} queries)")
        print("=" * 60)
        
        # Sequential execution
        start_time = time.time()
        sequential_results = []
        
        for query in queries:
            search_start = time.time()
            chunks = await retriever.search(query)
            search_time = time.time() - search_start
            sequential_results.append((len(chunks), search_time))
        
        sequential_total_time = time.time() - start_time
        
        # Concurrent execution
        start_time = time.time()
        
        async def search_query(query):
            search_start = time.time()
            chunks = await retriever.search(query)
            search_time = time.time() - search_start
            return len(chunks), search_time
        
        concurrent_results = await asyncio.gather(*[search_query(q) for q in queries])
        concurrent_total_time = time.time() - start_time
        
        # Analysis
        sequential_times = [t for _, t in sequential_results]
        concurrent_times = [t for _, t in concurrent_results]
        
        seq_avg = statistics.mean(sequential_times)
        conc_avg = statistics.mean(concurrent_times)
        
        print(f"Sequential Execution:")
        print(f"  Total time: {sequential_total_time:.3f}s")
        print(f"  Avg per query: {seq_avg:.3f}s")
        print(f"  Throughput: {len(queries)/sequential_total_time:.1f} queries/sec")
        
        print(f"\nConcurrent Execution:")
        print(f"  Total time: {concurrent_total_time:.3f}s") 
        print(f"  Avg per query: {conc_avg:.3f}s")
        print(f"  Throughput: {len(queries)/concurrent_total_time:.1f} queries/sec")
        
        print(f"\nConcurrency Speedup: {sequential_total_time/concurrent_total_time:.2f}x")
        
        # Performance assertions
        assert seq_avg < TestConfig.MAX_QUERY_TIME
        assert conc_avg < TestConfig.MAX_QUERY_TIME
        assert concurrent_total_time < sequential_total_time  # Should be faster
    
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline_performance(self, db_session, test_tenant_id, qdrant_config):
        """Test complete RAG pipeline performance under load."""
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        test_queries = [
            "What is the company mission?",
            "Tell me about remote work policies",
            "What are the vacation benefits?",
            "How does the team collaboration work?",
            "What is the company culture like?"
        ]
        
        print(f"\n🚀 End-to-End Pipeline Performance Test")
        print("=" * 60)
        
        # Measure pipeline performance
        times = []
        responses = []
        
        for query in test_queries:
            start_time = time.time()
            response = await pipeline.process_query(query, test_tenant_id)
            total_time = time.time() - start_time
            
            times.append(total_time)
            responses.append(response)
            
            print(f"Query: '{query[:30]}...'")
            print(f"  Time: {total_time:.3f}s")
            print(f"  Answer length: {len(response.answer)} chars")
            print(f"  Sources: {len(response.sources)}")
        
        # Performance analysis
        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        print(f"\nPipeline Performance Summary:")
        print(f"  Average latency: {avg_time:.3f}s")
        print(f"  95th percentile: {p95_time:.3f}s")
        print(f"  Throughput: {len(test_queries)/sum(times):.1f} queries/sec")
        
        # Quality metrics
        avg_answer_length = statistics.mean(len(r.answer) for r in responses)
        avg_source_count = statistics.mean(len(r.sources) for r in responses)
        avg_confidence = statistics.mean(r.confidence for r in responses)
        
        print(f"\nResponse Quality:")
        print(f"  Avg answer length: {avg_answer_length:.0f} chars")
        print(f"  Avg sources: {avg_source_count:.1f}")
        print(f"  Avg confidence: {avg_confidence:.3f}")
        
        # Assertions
        assert avg_time < TestConfig.MAX_QUERY_TIME
        assert all(len(r.answer) > 0 for r in responses)
        assert avg_confidence > 0.0
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, db_session, test_tenant_id, qdrant_config):
        """Test memory usage remains stable under repeated queries."""
        import psutil
        import os
        
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"\n💾 Memory Stability Test")
        print("=" * 60)
        print(f"Initial memory: {initial_memory:.1f} MB")
        
        # Run many queries
        query_text = "company mission and values"
        memory_samples = [initial_memory]
        
        for i in range(20):  # 20 iterations
            response = await pipeline.process_query(query_text, test_tenant_id)
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)
            
            if i % 5 == 4:  # Every 5 iterations
                print(f"After {i+1} queries: {current_memory:.1f} MB")
        
        final_memory = memory_samples[-1]
        memory_growth = final_memory - initial_memory
        max_memory = max(memory_samples)
        
        print(f"\nMemory Usage Summary:")
        print(f"  Initial: {initial_memory:.1f} MB")
        print(f"  Final: {final_memory:.1f} MB")
        print(f"  Growth: {memory_growth:.1f} MB")
        print(f"  Peak: {max_memory:.1f} MB")
        
        # Memory leak check
        memory_growth_rate = memory_growth / 20  # MB per query
        print(f"  Growth rate: {memory_growth_rate:.3f} MB/query")
        
        # Reasonable memory bounds
        assert memory_growth < 500, f"Excessive memory growth: {memory_growth:.1f} MB"
        assert memory_growth_rate < 5, f"Memory leak detected: {memory_growth_rate:.3f} MB/query"
    
    @pytest.mark.asyncio
    async def test_similarity_search_accuracy(self, db_session, test_tenant_id, qdrant_config):
        """Test accuracy of similarity search with known good queries."""
        retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        processor = QueryProcessor()
        
        # Test cases with expected results
        test_cases = [
            {
                "query": "company mission",
                "expected_terms": ["mission", "company", "values", "purpose"],
                "min_results": 1,
                "min_score": 0.4
            },
            {
                "query": "remote work policy",
                "expected_terms": ["remote", "work", "policy", "home"],
                "min_results": 1,
                "min_score": 0.3
            },
            {
                "query": "vacation time benefits",
                "expected_terms": ["vacation", "time", "benefits", "leave"],
                "min_results": 1,
                "min_score": 0.3
            }
        ]
        
        print(f"\n🎯 Similarity Search Accuracy Test")
        print("=" * 60)
        
        accuracy_scores = []
        
        for i, test_case in enumerate(test_cases, 1):
            query = processor.process_query(test_case["query"], test_tenant_id)
            chunks = await retriever.search(query)
            
            print(f"\nTest {i}: '{test_case['query']}'")
            
            if not chunks:
                print("  ❌ No results found")
                accuracy_scores.append(0.0)
                continue
            
            # Check result count
            meets_count = len(chunks) >= test_case["min_results"]
            print(f"  Results: {len(chunks)} (min: {test_case['min_results']}) {'✅' if meets_count else '❌'}")
            
            # Check top score
            top_score = chunks[0].score
            meets_score = top_score >= test_case["min_score"] 
            print(f"  Top score: {top_score:.3f} (min: {test_case['min_score']}) {'✅' if meets_score else '❌'}")
            
            # Check term relevance
            relevant_chunks = 0
            for chunk in chunks[:5]:  # Check top 5
                content_lower = chunk.content.lower()
                has_terms = any(term.lower() in content_lower for term in test_case["expected_terms"])
                if has_terms:
                    relevant_chunks += 1
            
            relevance_rate = relevant_chunks / min(len(chunks), 5)
            meets_relevance = relevance_rate >= 0.5
            print(f"  Relevance: {relevance_rate:.1%} ({relevant_chunks}/{min(len(chunks), 5)}) {'✅' if meets_relevance else '❌'}")
            
            # Calculate accuracy score
            accuracy = (int(meets_count) + int(meets_score) + int(meets_relevance)) / 3
            accuracy_scores.append(accuracy)
            print(f"  Accuracy: {accuracy:.1%}")
        
        overall_accuracy = statistics.mean(accuracy_scores)
        
        print(f"\nOverall Accuracy: {overall_accuracy:.1%}")
        
        # Accuracy threshold
        assert overall_accuracy >= 0.6, f"Low search accuracy: {overall_accuracy:.1%}"
    
    @pytest.mark.asyncio 
    async def test_scalability_limits(self, db_session, test_tenant_id, qdrant_config):
        """Test system behavior at scalability limits."""
        pipeline = RAGPipeline(db_session)
        pipeline.retriever = VectorRetriever(db_session, qdrant_url=qdrant_config["url"])
        
        print(f"\n📈 Scalability Limits Test")
        print("=" * 60)
        
        # Test 1: Large number of concurrent queries
        concurrent_queries = 10
        query_text = "company information"
        
        print(f"Testing {concurrent_queries} concurrent queries...")
        
        async def stress_query():
            start_time = time.time()
            response = await pipeline.process_query(query_text, test_tenant_id)
            return time.time() - start_time, len(response.sources)
        
        start_time = time.time()
        results = await asyncio.gather(*[stress_query() for _ in range(concurrent_queries)])
        total_time = time.time() - start_time
        
        times, source_counts = zip(*results)
        
        print(f"Concurrent execution results:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Avg query time: {statistics.mean(times):.3f}s")
        print(f"  Max query time: {max(times):.3f}s")
        print(f"  Throughput: {concurrent_queries/total_time:.1f} queries/sec")
        
        # Test 2: Very long query
        long_query = " ".join(["company mission values culture"] * 50)  # ~200 words
        
        print(f"\nTesting very long query ({len(long_query)} chars)...")
        
        start_time = time.time()
        response = await pipeline.process_query(long_query, test_tenant_id)
        long_query_time = time.time() - start_time
        
        print(f"  Query time: {long_query_time:.3f}s")
        print(f"  Answer length: {len(response.answer)} chars")
        print(f"  Sources: {len(response.sources)}")
        
        # Assertions
        assert all(t < TestConfig.MAX_QUERY_TIME * 2 for t in times), "Some concurrent queries too slow"
        assert long_query_time < TestConfig.MAX_QUERY_TIME * 3, "Long query timeout"
        assert len(response.answer) > 0, "Long query produced no answer"