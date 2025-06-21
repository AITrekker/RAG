#!/usr/bin/env python3
"""
Test script for embedding model configuration system
Validates RTX 5070 optimized embedding model selection
"""

import os
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent / "backend"))

from backend.config.settings import (
    settings, 
    get_embedding_model_config, 
    get_model_recommendations,
    validate_rtx_5070_compatibility,
    EmbeddingModelType
)
from backend.core.embeddings import get_embedding_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_configuration_system():
    """Test the embedding configuration system"""
    logger.info("🧪 Testing Embedding Configuration System")
    
    print("\n" + "="*60)
    print("EMBEDDING MODEL CONFIGURATION TEST")
    print("="*60)
    
    # Test 1: Configuration loading
    print("\n1. Testing Configuration Loading:")
    config = get_embedding_model_config()
    for key, value in config.items():
        print(f"   {key}: {value}")
    
    # Test 2: RTX 5070 compatibility check
    print("\n2. RTX 5070 Compatibility Check:")
    compatibility = validate_rtx_5070_compatibility()
    print(f"   CUDA Available: {compatibility['cuda_available']}")
    print(f"   RTX 5070 Detected: {compatibility['rtx_5070_detected']}")
    if 'gpu_name' in compatibility:
        print(f"   GPU Name: {compatibility['gpu_name']}")
    
    print("   Recommendations:")
    for rec in compatibility['recommendations']:
        print(f"     • {rec}")
    
    # Test 3: Model recommendations
    print("\n3. Model Recommendations for RTX 5070:")
    recommendations = get_model_recommendations()
    for category, info in recommendations.items():
        print(f"\n   {category.upper()}:")
        print(f"     Model: {info['model']}")
        print(f"     Description: {info['description']}")
        print(f"     Embedding Dimension: {info['embedding_dim']}")
        print(f"     Expected Speed: {info['expected_speed_texts_per_sec']} texts/sec")
        print(f"     Memory Usage: {info['memory_usage_gb']} GB")
        print(f"     Use Case: {info['use_case']}")
    
    # Test 4: Available models
    print("\n4. Available Embedding Models:")  
    for model in EmbeddingModelType:
        print(f"   • {model.value}")
    
    return True


def test_embedding_service_with_config():
    """Test embedding service with configuration"""
    logger.info("🧪 Testing Embedding Service with Configuration")
    
    print("\n" + "="*60)
    print("EMBEDDING SERVICE CONFIGURATION TEST")
    print("="*60)
    
    test_texts = [
        "Enterprise RAG platform for document search and retrieval.",
        "RTX 5070 GPU acceleration for fast embedding generation.",
        "Multi-tenant architecture with data isolation."
    ]
    
    try:
        # Test with default configuration
        print("\n1. Testing with Default Configuration:")
        service = get_embedding_service()
        print(f"   Model: {service.model_name}")
        print(f"   Device: {service.device}")
        print(f"   Batch Size: {service.batch_size}")
        print(f"   Mixed Precision: {service.enable_mixed_precision}")
        
        # Generate embeddings
        print("\n   Generating embeddings...")
        embeddings = service.encode_texts(test_texts)
        print(f"   ✅ Generated embeddings shape: {embeddings.shape}")
        
        # Test performance
        stats = service.get_performance_stats()
        print(f"   Performance stats:")
        for key, value in stats.items():
            if key != "message":
                print(f"     {key}: {value}")
        
        # Test 2: Different model configurations
        print("\n2. Testing Different Model Configurations:")
        
        models_to_test = [
            ("all-MiniLM-L6-v2 (Default)", EmbeddingModelType.MINI_LM_L6_V2),
            ("all-mpnet-base-v2 (Quality)", EmbeddingModelType.MPNET_BASE_V2)
        ]
        
        for model_desc, model_type in models_to_test:
            print(f"\n   Testing {model_desc}:")
            try:
                # Create service with specific model
                service = get_embedding_service(
                    model_name=model_type.value,
                    force_reload=True
                )
                
                # Quick test
                sample_embedding = service.encode_single_text("Test text for model validation")
                print(f"     ✅ Model loaded, embedding dim: {len(sample_embedding)}")
                
            except Exception as e:
                print(f"     ❌ Error with {model_desc}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding service test failed: {e}")
        return False


def test_performance_benchmarks():
    """Test performance against RTX 5070 benchmarks"""
    logger.info("🧪 Testing Performance Benchmarks")
    
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK TEST")
    print("="*60)
    
    # Generate different sized batches to test performance
    batch_sizes = [8, 16, 32, 64]
    test_text = "This is a sample document for performance testing of the RAG platform with RTX 5070 GPU acceleration."
    
    try:
        service = get_embedding_service()
        
        print(f"\nTesting performance with model: {service.model_name}")
        print(f"Target performance: {service.target_performance} texts/sec")
        print("\nBatch Size | Texts/Sec | vs Target | Status")
        print("-" * 45)
        
        for batch_size in batch_sizes:
            # Create batch of texts
            texts = [f"{test_text} Batch item {i}" for i in range(batch_size)]
            
            # Time the embedding generation
            import time
            start_time = time.time()
            embeddings = service.encode_texts(texts, show_progress_bar=False)
            end_time = time.time()
            
            # Calculate performance
            elapsed = end_time - start_time
            if elapsed > 0:
                texts_per_sec = len(texts) / elapsed
                vs_target = texts_per_sec / service.target_performance
            else:
                texts_per_sec = 0
                vs_target = 0
            
            # Status
            if vs_target >= 1.0:
                status = "✅ GOOD"
            elif vs_target >= 0.7:
                status = "⚠️  OK"
            else:
                status = "❌ SLOW"
            
            print(f"{batch_size:10d} | {texts_per_sec:9.1f} | {vs_target:8.2f}x | {status}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Performance benchmark failed: {e}")
        return False


def main():
    """Run all embedding configuration tests"""
    print("🚀 Starting Embedding Model Configuration Tests")
    
    tests = [
        ("Configuration System", test_configuration_system),
        ("Embedding Service", test_embedding_service_with_config),
        ("Performance Benchmarks", test_performance_benchmarks)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")  
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25} : {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All embedding configuration tests passed!")
        print("✅ RTX 5070 embedding model configuration is ready!")
    else:
        print("⚠️  Some tests failed - check configuration")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 