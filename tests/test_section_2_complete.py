#!/usr/bin/env python3
"""
Comprehensive Test Suite for Section 2.0 Core RAG Pipeline Implementation
Tests all completed tasks: 2.1-2.9
"""

import sys
import os
import asyncio
import time
from typing import List, Dict, Any

# Update the path to ensure 'src' is in our import path
# This allows us to import modules from the 'src' directory as if we were running from the root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Test imports
from src.backend.config.settings import settings
from src.backend.core.embeddings import get_embedding_service
from src.backend.core.rag_pipeline import get_rag_pipeline, create_documents_from_texts
from src.backend.utils.vector_store import get_chroma_manager
from src.backend.core.embedding_pipeline import get_embedding_pipeline
from src.backend.core.query_processor import get_query_processor
from src.backend.core.llm_service import get_llm_service, get_model_recommendations
from src.backend.core.response_generator import get_response_generator, CitationStyle
from src.backend.utils.monitoring import get_performance_monitor, record_query_time
from src.backend.core.tenant_manager import get_tenant_manager
from src.backend.core.document_ingestion import DocumentIngestionPipeline
from src.backend.utils.vector_store import get_vector_store_manager
from src.backend.config.settings import get_settings
from src.backend.db.session import get_db
from src.backend.db.base import Base
from src.backend.models.tenant import Tenant
from src.backend.models.document import Document, DocumentChunk
from src.backend.core.document_processor import DocumentProcessor
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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

def test_task_2_1_huggingface_integration():
    """Test Task 2.1: Hugging Face transformers integration"""
    print_section("Task 2.1: Hugging Face Transformers Integration")
    
    try:
        print_test("Embedding service initialization")
        embedding_service = get_embedding_service()
        print_success(f"Embedding service initialized with model: {embedding_service.model_name}")
        print_info(f"Device: {embedding_service.device}")
        
        print_test("Single text encoding")
        sample_text = "Machine learning is transforming technology."
        embedding = embedding_service.encode_single_text(sample_text)
        print_success(f"Generated embedding with dimension: {len(embedding)}")
        
        print_test("Batch text encoding")
        sample_texts = [
            "Artificial intelligence is advancing rapidly.",
            "Natural language processing enables better human-computer interaction.",
            "Deep learning models require significant computational resources."
        ]
        embeddings = embedding_service.encode_batch_texts(sample_texts)
        print_success(f"Generated {len(embeddings)} embeddings for batch processing")
        
        print_test("Performance statistics")
        stats = embedding_service.get_performance_stats()
        print_success(f"Avg processing time: {stats['avg_processing_time']:.3f}s")
        print_success(f"Total texts processed: {stats['total_texts']}")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.1 failed: {e}")
        return False

def test_task_2_2_embedding_model_config():
    """Test Task 2.2: Embedding model configuration for RTX 5070"""
    print_section("Task 2.2: Embedding Model Configuration (RTX 5070)")
    
    try:
        print_test("Configuration validation")
        print_success(f"Model: {settings.embedding.model}")
        print_success(f"Batch size: {settings.embedding.batch_size}")
        print_success(f"Device: {settings.embedding.device}")
        
        print_test("RTX 5070 optimization check")
        embedding_service = get_embedding_service()
        if "RTX 5070" in str(embedding_service.device_info):
            print_success("RTX 5070 detected and optimized")
        else:
            print_info("RTX 5070 not detected, using available device")
        
        print_test("Performance benchmark")
        start_time = time.time()
        test_texts = ["Sample text for performance testing"] * 50
        embeddings = embedding_service.encode_batch_texts(test_texts)
        duration = time.time() - start_time
        throughput = len(test_texts) / duration
        
        print_success(f"Throughput: {throughput:.1f} texts/second")
        
        # Check if meeting target performance
        target_throughput = 16.3  # texts/second for RTX 5070
        if throughput >= target_throughput:
            print_success(f"Performance target exceeded! ({throughput/target_throughput:.1f}x)")
        else:
            print_info(f"Performance: {throughput/target_throughput:.1f}x of target")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.2 failed: {e}")
        return False

def test_task_2_3_llamaindex_service():
    """Test Task 2.3: LlamaIndex service manager"""
    print_section("Task 2.3: LlamaIndex Service Manager")
    
    try:
        print_test("RAG pipeline initialization")
        rag_pipeline = get_rag_pipeline(tenant_id="test_tenant")
        print_success(f"RAG pipeline initialized for tenant: {rag_pipeline.tenant_id}")
        
        print_test("Document creation and indexing")
        sample_docs = [
            "Python is a versatile programming language used in data science.",
            "FastAPI is a modern web framework for building APIs with Python.",
            "Vector databases enable efficient similarity search for embeddings.",
            "RAG systems combine retrieval and generation for better AI responses.",
            "Machine learning models can be deployed using various cloud platforms."
        ]
        
        documents = create_documents_from_texts(
            sample_docs,
            metadatas=[{"source": f"doc_{i}", "topic": "AI"} for i in range(len(sample_docs))]
        )
        
        # Create index
        index = rag_pipeline.create_index(documents)
        print_success(f"Index created with {len(documents)} documents")
        
        print_test("Query execution")
        query_result = rag_pipeline.query(
            "What is Python used for?",
            top_k=3,
            include_metadata=True
        )
        
        print_success(f"Query executed successfully")
        print_info(f"Response: {query_result['response'][:100]}...")
        print_info(f"Found {len(query_result['sources'])} sources")
        print_info(f"Query time: {query_result['query_time']:.3f}s")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.3 failed: {e}")
        return False

def test_task_2_4_chroma_vector_db():
    """Test Task 2.4: Chroma vector database setup"""
    print_section("Task 2.4: Chroma Vector Database Setup")
    
    try:
        print_test("Chroma manager initialization")
        chroma_manager = get_chroma_manager()
        print_success("Chroma manager initialized")
        
        print_test("Collection creation and management")
        test_tenant = "test_tenant_vectordb"
        collection = chroma_manager.get_collection_for_tenant(test_tenant)
        print_success(f"Collection created for tenant: {test_tenant}")
        
        print_test("Document storage and retrieval")
        # Add some test documents
        test_docs = [
            {"id": "doc1", "text": "Vector databases store high-dimensional data efficiently."},
            {"id": "doc2", "text": "Chroma is an open-source vector database for AI applications."},
            {"id": "doc3", "text": "Similarity search finds related documents using embeddings."}
        ]
        
        embedding_service = get_embedding_service()
        
        for doc in test_docs:
            embedding = embedding_service.encode_single_text(doc["text"])
            collection.add(
                ids=[doc["id"]],
                documents=[doc["text"]],
                embeddings=[embedding.tolist()],
                metadatas=[{"tenant_id": test_tenant, "source": doc["id"]}]
            )
        
        print_success(f"Added {len(test_docs)} documents to collection")
        
        print_test("Similarity search")
        query_text = "What are vector databases?"
        query_embedding = embedding_service.encode_single_text(query_text)
        
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=2,
            where={"tenant_id": test_tenant}
        )
        
        print_success(f"Found {len(results['documents'][0])} similar documents")
        
        print_test("Database statistics")
        stats = chroma_manager.get_database_stats()
        print_success(f"Total collections: {stats['total_collections']}")
        print_success(f"Database path: {stats['database_path']}")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.4 failed: {e}")
        return False

def test_task_2_5_embedding_pipeline():
    """Test Task 2.5: Embedding generation pipeline"""
    print_section("Task 2.5: Embedding Generation Pipeline")
    
    try:
        print_test("Embedding pipeline initialization")
        pipeline = get_embedding_pipeline()
        print_success("Embedding pipeline initialized")
        
        print_test("Single document processing")
        doc_request = {
            "id": "test_doc_1",
            "text": "This is a test document for the embedding pipeline.",
            "metadata": {"source": "test", "type": "document"}
        }
        
        result = pipeline.process_single(doc_request)
        print_success(f"Processed document: {result.doc_id}")
        print_info(f"Embedding dimension: {len(result.embedding)}")
        print_info(f"Processing time: {result.processing_time:.3f}s")
        
        print_test("Batch processing")
        batch_docs = [
            {"id": f"batch_doc_{i}", "text": f"Batch document {i} for testing.", "metadata": {"batch": True}}
            for i in range(5)
        ]
        
        batch_results = pipeline.process_batch(batch_docs)
        print_success(f"Processed batch of {len(batch_results)} documents")
        
        print_test("Performance statistics")
        stats = pipeline.get_stats()
        print_success(f"Documents processed: {stats['documents_processed']}")
        print_success(f"Average processing time: {stats['average_processing_time']:.3f}s")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.5 failed: {e}")
        return False

def test_task_2_6_query_processing():
    """Test Task 2.6: Basic query processing with vector similarity search"""
    print_section("Task 2.6: Query Processing with Vector Search")
    
    try:
        print_test("Query processor initialization")
        query_processor = get_query_processor(tenant_id="test_query_processor")
        print_success("Query processor initialized")
        
        # First, let's add some test documents to search against
        print_test("Setting up test data")
        embedding_pipeline = get_embedding_pipeline()
        
        test_documents = [
            {
                "id": "search_doc_1",
                "text": "Python is excellent for data science and machine learning applications.",
                "metadata": {"topic": "programming", "language": "python"}
            },
            {
                "id": "search_doc_2", 
                "text": "Vector databases enable fast similarity search for AI applications.",
                "metadata": {"topic": "databases", "type": "vector"}
            },
            {
                "id": "search_doc_3",
                "text": "RAG systems combine retrieval and generation for better AI responses.",
                "metadata": {"topic": "ai", "system": "rag"}
            }
        ]
        
        # Process documents through pipeline
        for doc in test_documents:
            embedding_pipeline.process_single(doc)
        
        print_success(f"Added {len(test_documents)} test documents")
        
        print_test("Similarity search")
        query = "What programming languages are good for machine learning?"
        search_results = query_processor.similarity_search(query, top_k=3)
        print_success(f"Found {len(search_results)} relevant documents")
        
        for i, result in enumerate(search_results):
            print_info(f"Result {i+1}: Score {result['score']:.3f} - {result['text'][:50]}...")
        
        print_test("Complete query processing")
        query_result = query_processor.process_query(query, top_k=2)
        print_success(f"Query processed successfully")
        print_info(f"Response: {query_result.response[:100]}...")
        print_info(f"Processing time: {query_result.processing_time:.3f}s")
        print_info(f"Sources found: {query_result.embeddings_used}")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.6 failed: {e}")
        return False

def test_task_2_7_local_llm():
    """Test Task 2.7: Local LLM inference using Hugging Face transformers"""
    print_section("Task 2.7: Local LLM Inference")
    
    try:
        print_test("LLM service initialization")
        llm_service = get_llm_service()
        print_success(f"LLM service initialized with model: {llm_service.model_name}")
        print_info(f"Device: {llm_service.device}")
        
        print_test("Model recommendations")
        recommendations = get_model_recommendations()
        print_success(f"Available model configurations: {len(recommendations)}")
        for name, config in recommendations.items():
            print_info(f"  {name}: {config['model']} ({config['parameters']})")
        
        print_test("Simple text generation")
        prompt = "What is machine learning?"
        response = llm_service.generate_response(
            prompt,
            max_new_tokens=50,
            temperature=0.7
        )
        
        if response.success:
            print_success("Text generation successful")
            print_info(f"Response: {response.text[:100]}...")
            print_info(f"Generation time: {response.generation_time:.3f}s")
            print_info(f"Tokens: {response.prompt_tokens} + {response.completion_tokens} = {response.total_tokens}")
        else:
            print_error(f"Text generation failed: {response.error}")
            return False
        
        print_test("RAG response generation")
        sources = [
            {"text": "Python is a popular programming language for AI and data science."},
            {"text": "Machine learning algorithms can learn patterns from data automatically."}
        ]
        
        rag_response = llm_service.generate_rag_response(
            "What makes Python good for machine learning?",
            sources,
            max_new_tokens=80
        )
        
        if rag_response.success:
            print_success("RAG response generation successful")
            print_info(f"Response: {rag_response.text[:100]}...")
        else:
            print_error(f"RAG response failed: {rag_response.error}")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.7 failed: {e}")
        return False

def test_task_2_8_response_generation():
    """Test Task 2.8: Response generation pipeline with source citation tracking"""
    print_section("Task 2.8: Response Generation with Citations")
    
    try:
        print_test("Response generator initialization")
        response_generator = get_response_generator(
            citation_style=CitationStyle.NUMBERED,
            max_sources=3
        )
        print_success("Response generator initialized")
        
        print_test("Citation formatting")
        sample_sources = [
            {
                "text": "Python is widely used in data science due to its extensive libraries like pandas and scikit-learn.",
                "score": 0.85,
                "metadata": {"title": "Python for Data Science", "author": "Data Scientist"}
            },
            {
                "text": "Machine learning models require careful feature engineering and hyperparameter tuning.",
                "score": 0.78,
                "metadata": {"title": "ML Best Practices", "source": "AI Research"}
            },
            {
                "text": "Deep learning frameworks like TensorFlow and PyTorch have revolutionized AI development.",
                "score": 0.72,
                "metadata": {"title": "Deep Learning Frameworks", "url": "https://example.com"}
            }
        ]
        
        query = "How is Python used in machine learning?"
        generated_response = response_generator.generate_response(
            query,
            sample_sources,
            temperature=0.7,
            max_tokens=150
        )
        
        if generated_response.success:
            print_success("Response generated with citations")
            print_info(f"Response: {generated_response.response_text[:200]}...")
            print_info(f"Citations: {len(generated_response.citations)}")
            print_info(f"Quality score: {generated_response.quality_score:.2f}")
            print_info(f"Confidence score: {generated_response.confidence_score:.2f}")
            print_info(f"Generation time: {generated_response.generation_time:.3f}s")
        else:
            print_error(f"Response generation failed: {generated_response.error}")
            return False
        
        print_test("Different citation styles")
        for style in [CitationStyle.BRACKETED, CitationStyle.FOOTNOTE]:
            style_generator = get_response_generator(citation_style=style, force_reload=True)
            style_response = style_generator.generate_response(query, sample_sources[:2])
            if style_response.success:
                print_success(f"{style.value} citations working")
            else:
                print_error(f"{style.value} citations failed")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.8 failed: {e}")
        return False

def test_task_2_9_monitoring():
    """Test Task 2.9: Basic response time monitoring"""
    print_section("Task 2.9: Response Time Monitoring")
    
    try:
        print_test("Performance monitor initialization")
        monitor = get_performance_monitor()
        print_success("Performance monitor initialized")
        
        print_test("Recording metrics")
        # Simulate some operations
        record_query_time(1.2, sources_found=3)
        record_query_time(0.8, sources_found=5)
        record_query_time(2.1, sources_found=2)
        
        # Record embedding metrics
        monitor.record_metric(
            component="embedding_service",
            operation="encode_batch",
            duration=0.5,
            metadata={"batch_size": 10}
        )
        
        # Record LLM metrics
        monitor.record_metric(
            component="llm_service", 
            operation="generate_response",
            duration=3.2,
            metadata={"tokens": 150}
        )
        
        print_success("Metrics recorded successfully")
        
        print_test("Performance statistics")
        stats = monitor.get_overall_stats()
        print_success(f"Total operations: {stats['total_operations']}")
        print_success(f"Success rate: {stats['success_rate']:.1%}")
        print_success(f"Average duration: {stats['average_duration']:.3f}s")
        
        if stats['total_operations'] > 0:
            print_info(f"Min duration: {stats['min_duration']:.3f}s")
            print_info(f"Max duration: {stats['max_duration']:.3f}s")
            print_info(f"Median duration: {stats['median_duration']:.3f}s")
        
        return True
        
    except Exception as e:
        print_error(f"Task 2.9 failed: {e}")
        return False

def test_integration():
    """Test end-to-end integration of all components"""
    print_section("End-to-End Integration Test")
    
    try:
        print_test("Full RAG pipeline integration")
        
        # 1. Set up components
        tenant_id = "integration_test"
        embedding_pipeline = get_embedding_pipeline()
        query_processor = get_query_processor(tenant_id=tenant_id)
        response_generator = get_response_generator()
        monitor = get_performance_monitor()
        
        # 2. Add knowledge base
        knowledge_docs = [
            {
                "id": "kb_1",
                "text": "Python is a high-level programming language known for its simplicity and readability. It's widely used in web development, data science, artificial intelligence, and scientific computing.",
                "metadata": {"topic": "python", "type": "programming"}
            },
            {
                "id": "kb_2", 
                "text": "Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed for every task.",
                "metadata": {"topic": "ml", "type": "concept"}
            },
            {
                "id": "kb_3",
                "text": "Vector databases store and index high-dimensional vectors, enabling fast similarity search. They're essential for AI applications like recommendation systems and RAG.",
                "metadata": {"topic": "vectordb", "type": "technology"}
            }
        ]
        
        # Process documents
        for doc in knowledge_docs:
            embedding_pipeline.process_single(doc)
        
        print_success(f"Knowledge base created with {len(knowledge_docs)} documents")
        
        # 3. Test complete query flow
        start_time = time.time()
        
        user_query = "How is Python used in machine learning?"
        
        # Query processing with similarity search
        query_result = query_processor.process_query(
            user_query,
            top_k=3,
            include_metadata=True
        )
        
        # Generate response with citations
        if query_result.success and query_result.sources:
            final_response = response_generator.generate_response(
                user_query,
                query_result.sources
            )
            
            total_time = time.time() - start_time
            
            # Record performance
            monitor.record_metric(
                component="integration_test",
                operation="full_rag_pipeline", 
                duration=total_time
            )
            
            print_success("Full integration test completed!")
            print_info(f"Query: {user_query}")
            print_info(f"Response: {final_response.response_text[:150]}...")
            print_info(f"Sources used: {len(query_result.sources)}")
            print_info(f"Total time: {total_time:.3f}s")
            print_info(f"Quality score: {final_response.quality_score:.2f}")
            
        else:
            print_error("Query processing failed in integration test")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Integration test failed: {e}")
        return False

def main():
    """Run all tests for Section 2.0"""
    print_section("🚀 Section 2.0 Core RAG Pipeline Implementation - Full Test Suite")
    
    tests = [
        ("2.1", "Hugging Face Transformers Integration", test_task_2_1_huggingface_integration),
        ("2.2", "Embedding Model Configuration (RTX 5070)", test_task_2_2_embedding_model_config),
        ("2.3", "LlamaIndex Service Manager", test_task_2_3_llamaindex_service),
        ("2.4", "Chroma Vector Database Setup", test_task_2_4_chroma_vector_db),
        ("2.5", "Embedding Generation Pipeline", test_task_2_5_embedding_pipeline),
        ("2.6", "Query Processing with Vector Search", test_task_2_6_query_processing),
        ("2.7", "Local LLM Inference", test_task_2_7_local_llm),
        ("2.8", "Response Generation with Citations", test_task_2_8_response_generation),
        ("2.9", "Response Time Monitoring", test_task_2_9_monitoring),
        ("INT", "End-to-End Integration", test_integration)
    ]
    
    results = {}
    
    for task_id, task_name, test_func in tests:
        try:
            success = test_func()
            results[task_id] = success
        except Exception as e:
            print_error(f"Task {task_id} test crashed: {e}")
            results[task_id] = False
    
    # Summary
    print_section("📊 Test Results Summary")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for task_id, task_name, _ in tests:
        status = "✅ PASS" if results[task_id] else "❌ FAIL"
        print(f"Task {task_id}: {status} - {task_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total:.1%})")
    
    if passed == total:
        print_success("🎉 All Section 2.0 tasks completed successfully!")
        print_info("Core RAG Pipeline Implementation is ready for production!")
    else:
        print_error(f"⚠️  {total-passed} tasks need attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 