#!/usr/bin/env python3
"""
Test GPU vs CPU performance for realistic RAG workloads.
"""

import time
import torch
from sentence_transformers import SentenceTransformer

def test_realistic_workload():
    """Test with realistic RAG query sizes."""
    print("🚀 Realistic RAG Performance Test")
    print("=" * 50)
    
    # Realistic RAG queries and documents
    test_texts = [
        "What is our company's work from home policy and how does it affect employee productivity?",
        "Explain the vacation policy and time off benefits for full-time employees.",
        "How does our company culture promote innovation and team collaboration?",
        "What are the requirements for remote work and flexible scheduling arrangements?",
        "Describe the employee benefits package including health insurance and retirement plans.",
        "What is the process for requesting time off and coordinating with team members?",
        "How does the company support professional development and continuous learning?",
        "What are the guidelines for working from home equipment and technology setup?",
        "Explain the company's approach to work-life balance and employee wellbeing.",
        "What are the expectations for communication and collaboration in remote teams?"
    ] * 5  # 50 total queries
    
    print(f"📊 Testing with {len(test_texts)} realistic queries...")
    
    # CPU Test
    print("\n⚙️  CPU Performance Test")
    model_cpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')
    
    start = time.time()
    embeddings_cpu = model_cpu.encode(test_texts, show_progress_bar=False)
    cpu_time = time.time() - start
    
    print(f"   CPU Time: {cpu_time:.3f}s")
    print(f"   CPU Rate: {len(test_texts)/cpu_time:.1f} queries/sec")
    
    # GPU Test
    print("\n🔥 GPU Performance Test")
    model_gpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
    
    # Warmup
    model_gpu.encode(["warmup"], show_progress_bar=False)
    torch.cuda.synchronize()
    
    start = time.time()
    embeddings_gpu = model_gpu.encode(test_texts, show_progress_bar=False)
    torch.cuda.synchronize()
    gpu_time = time.time() - start
    
    print(f"   GPU Time: {gpu_time:.3f}s")
    print(f"   GPU Rate: {len(test_texts)/gpu_time:.1f} queries/sec")
    
    print(f"\n📈 Results:")
    print(f"   Speedup: {cpu_time/gpu_time:.1f}x")
    print(f"   Embeddings shape: {embeddings_gpu.shape}")
    
    # Memory usage
    memory_used = torch.cuda.memory_allocated() / 1024**3
    print(f"   GPU Memory: {memory_used:.1f} GB")

def test_batch_scaling():
    """Test how performance scales with batch size."""
    print("\n📊 Batch Size Scaling Test")
    print("=" * 50)
    
    base_query = "What is our company policy for remote work and flexible scheduling?"
    batch_sizes = [1, 5, 10, 25, 50, 100]
    
    model_gpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
    model_cpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')
    
    print("Batch Size | CPU Time | GPU Time | Speedup | GPU Queries/sec")
    print("-" * 60)
    
    for batch_size in batch_sizes:
        texts = [base_query] * batch_size
        
        # CPU
        start = time.time()
        cpu_embeddings = model_cpu.encode(texts, show_progress_bar=False)
        cpu_time = time.time() - start
        
        # GPU (with warmup)
        model_gpu.encode([base_query], show_progress_bar=False)
        torch.cuda.synchronize()
        
        start = time.time()
        gpu_embeddings = model_gpu.encode(texts, show_progress_bar=False)
        torch.cuda.synchronize()
        gpu_time = time.time() - start
        
        speedup = cpu_time / gpu_time if gpu_time > 0 else 0
        gpu_rate = batch_size / gpu_time if gpu_time > 0 else 0
        
        print(f"{batch_size:>9} | {cpu_time:>7.3f}s | {gpu_time:>7.3f}s | {speedup:>6.1f}x | {gpu_rate:>11.1f}")

def main():
    """Run performance tests."""
    if not torch.cuda.is_available():
        print("❌ CUDA not available")
        return
    
    test_realistic_workload()
    test_batch_scaling()
    
    print("\n🎯 Performance Summary:")
    print("• Small batches (1-5): CPU often faster due to GPU overhead")
    print("• Medium batches (10-25): GPU starts to show advantage") 
    print("• Large batches (50+): GPU significantly faster")
    print("• RAG systems: Use GPU for batch processing, CPU for single queries")

if __name__ == "__main__":
    main()