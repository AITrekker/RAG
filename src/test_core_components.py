#!/usr/bin/env python3
"""
Simplified Test for Core RAG Components
Tests the fundamental functionality without complex import dependencies
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def print_section(title: str):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_test(test_name: str):
    """Print test name"""
    print(f"\n📋 Testing: {test_name}")

def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")

def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")

def print_info(message: str):
    """Print info message"""
    print(f"ℹ️  {message}")

def test_basic_imports():
    """Test that core components can be imported"""
    print_section("Core Component Import Test")
    
    try:
        print_test("Configuration and settings")
        from backend.config.settings import settings
        print_success("Settings loaded successfully")
        print_info(f"Embedding model: {settings.embedding.model}")
        print_info(f"Device: {settings.embedding.device}")
        
        print_test("Embedding service")
        from backend.core.embeddings import get_embedding_service
        embedding_service = get_embedding_service()
        print_success("Embedding service imported and initialized")
        
        print_test("Vector store utilities")
        from backend.utils.vector_store import get_chroma_manager
        chroma_manager = get_chroma_manager()
        print_success("Vector store utilities working")
        
        print_test("Monitoring system")
        from backend.core.monitoring import get_performance_monitor
        monitor = get_performance_monitor()
        print_success("Performance monitoring system working")
        
        return True
        
    except Exception as e:
        print_error(f"Import test failed: {e}")
        return False

def test_embedding_functionality():
    """Test basic embedding functionality"""
    print_section("Embedding Functionality Test")
    
    try:
        from backend.core.embeddings import get_embedding_service
        
        print_test("Embedding service initialization")
        embedding_service = get_embedding_service()
        print_success(f"Service initialized with model: {embedding_service.model_name}")
        
        print_test("Single text encoding")
        test_text = "This is a test sentence for embedding generation."
        start_time = time.time()
        embedding = embedding_service.encode_single_text(test_text)
        duration = time.time() - start_time
        
        print_success(f"Generated embedding with {len(embedding)} dimensions")
        print_info(f"Processing time: {duration:.3f} seconds")
        
        print_test("Batch text encoding")
        test_texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence."
        ]
        
        start_time = time.time()
        embeddings = embedding_service.encode_batch_texts(test_texts)
        batch_duration = time.time() - start_time
        
        print_success(f"Generated {len(embeddings)} embeddings")
        print_info(f"Batch processing time: {batch_duration:.3f} seconds")
        print_info(f"Average per text: {batch_duration/len(test_texts):.3f} seconds")
        
        print_test("Performance statistics")
        stats = embedding_service.get_performance_stats()
        print_success(f"Performance tracking working")
        print_info(f"Total texts processed: {stats['total_texts']}")
        
        return True
        
    except Exception as e:
        print_error(f"Embedding test failed: {e}")
        return False

def test_vector_store():
    """Test vector store functionality"""
    print_section("Vector Store Test")
    
    try:
        from backend.utils.vector_store import get_chroma_manager
        from backend.core.embeddings import get_embedding_service
        
        print_test("Chroma manager initialization")
        chroma_manager = get_chroma_manager()
        embedding_service = get_embedding_service()
        print_success("Chroma manager initialized")
        
        print_test("Collection creation")
        test_tenant = "test_vector_store"
        collection = chroma_manager.get_collection_for_tenant(test_tenant)
        print_success(f"Collection created for tenant: {test_tenant}")
        
        print_test("Document storage")
        test_doc = {
            "id": "test_doc_1",
            "text": "This is a test document for vector storage.",
            "metadata": {"tenant_id": test_tenant, "type": "test"}
        }
        
        # Generate embedding
        embedding = embedding_service.encode_single_text(test_doc["text"])
        
        # Store in collection
        collection.add(
            ids=[test_doc["id"]],
            documents=[test_doc["text"]],
            embeddings=[embedding.tolist()],
            metadatas=[test_doc["metadata"]]
        )
        print_success("Document stored in vector database")
        
        print_test("Similarity search")
        query_text = "test document"
        query_embedding = embedding_service.encode_single_text(query_text)
        
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=1,
            where={"tenant_id": test_tenant}
        )
        
        if results["documents"] and results["documents"][0]:
            print_success("Similarity search working")
            print_info(f"Found document: {results['documents'][0][0][:50]}...")
        else:
            print_error("No documents found in similarity search")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Vector store test failed: {e}")
        return False

def test_monitoring():
    """Test monitoring functionality"""
    print_section("Monitoring System Test")
    
    try:
        from backend.utils.monitoring import get_performance_monitor
        import time

        monitor = get_performance_monitor(force_reload=True)
        
        print_test("Monitor initialization")
        print_success("Performance monitor initialized")
        
        print_test("Metric recording")
        # Record some test metrics
        monitor.record_metric(
            component="test_component",
            operation="test_operation",
            duration=1.5,
            metadata={"test": True}
        )
        
        record_embedding_time(0.5, "test_model")
        print_success("Metrics recorded successfully")
        
        print_test("Statistics retrieval")
        stats = monitor.get_overall_stats()
        print_success("Statistics generated")
        print_info(f"Total operations: {stats['total_operations']}")
        print_info(f"Success rate: {stats['success_rate']:.1%}")
        
        # Test convenience functions
        print_test("Convenience functions")
        from backend.utils.monitoring import record_embedding_time
        record_embedding_time(0.5, "test_model")
        stats = monitor.get_overall_stats()
        assert stats["total_operations"] == 3
        
        return True
        
    except Exception as e:
        print_error(f"Monitoring test failed: {e}")
        return False

def test_end_to_end_simple():
    """Simple end-to-end test without complex dependencies"""
    print_section("Simple End-to-End Test")
    
    try:
        from backend.core.embeddings import get_embedding_service
        from backend.utils.vector_store import get_chroma_manager
        from backend.core.monitoring import get_performance_monitor
        
        print_test("Component initialization")
        embedding_service = get_embedding_service()
        chroma_manager = get_chroma_manager()
        monitor = get_performance_monitor()
        print_success("All components initialized")
        
        print_test("Document processing simulation")
        tenant_id = "e2e_test"
        collection = chroma_manager.get_collection_for_tenant(tenant_id)
        
        # Add some test documents
        test_docs = [
            "Python is a versatile programming language for data science and AI.",
            "Machine learning models can automatically learn patterns from data.",
            "Vector databases enable fast similarity search for AI applications."
        ]
        
        start_time = time.time()
        
        for i, doc_text in enumerate(test_docs):
            doc_id = f"e2e_doc_{i}"
            
            # Generate embedding
            embedding = embedding_service.encode_single_text(doc_text)
            
            # Store in vector database
            collection.add(
                ids=[doc_id],
                documents=[doc_text],
                embeddings=[embedding.tolist()],
                metadatas=[{"tenant_id": tenant_id, "doc_id": doc_id}]
            )
        
        indexing_time = time.time() - start_time
        print_success(f"Indexed {len(test_docs)} documents in {indexing_time:.3f}s")
        
        print_test("Query processing simulation")
        query = "What is Python used for?"
        
        start_time = time.time()
        
        # Generate query embedding
        query_embedding = embedding_service.encode_single_text(query)
        
        # Search for similar documents
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=2,
            where={"tenant_id": tenant_id}
        )
        
        query_time = time.time() - start_time
        
        # Record performance metric
        monitor.record_metric(
            component="e2e_test",
            operation="query_processing",
            duration=query_time,
            metadata={"query": query, "results_found": len(results["documents"][0]) if results["documents"] else 0}
        )
        
        if results["documents"] and results["documents"][0]:
            print_success(f"Query processed in {query_time:.3f}s")
            print_info(f"Found {len(results['documents'][0])} relevant documents")
            print_info(f"Top result: {results['documents'][0][0][:80]}...")
        else:
            print_error("No results found for query")
            return False
        
        print_test("Performance validation")
        stats = monitor.get_overall_stats()
        avg_time = stats['average_duration']
        
        if avg_time < 5.0:  # Less than 5 seconds average
            print_success(f"Performance target met: {avg_time:.3f}s average")
        else:
            print_info(f"Performance: {avg_time:.3f}s average (target: <5s)")
        
        return True
        
    except Exception as e:
        print_error(f"End-to-end test failed: {e}")
        return False

def main():
    """Run simplified test suite"""
    print_section("🚀 Core RAG Components - Simplified Test Suite")
    
    tests = [
        ("Core Imports", test_basic_imports),
        ("Embedding Functionality", test_embedding_functionality), 
        ("Vector Store", test_vector_store),
        ("Monitoring System", test_monitoring),
        ("End-to-End Simple", test_end_to_end_simple)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            print_error(f"{test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print_section("📊 Test Results Summary")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for test_name in results:
        status = "✅ PASS" if results[test_name] else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total:.1%})")
    
    if passed == total:
        print_success("🎉 All core components working correctly!")
        print_info("✨ Section 2.0 Core RAG Pipeline is functional!")
    else:
        print_error(f"⚠️  {total-passed} components need attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 