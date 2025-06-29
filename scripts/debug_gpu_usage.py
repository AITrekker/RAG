#!/usr/bin/env python3
"""
Debug GPU usage for embedding generation.
"""

import sys
import torch
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_torch_setup():
    """Check PyTorch and CUDA setup."""
    print("🔍 PyTorch & CUDA Debug")
    print("=" * 50)
    
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU count: {torch.cuda.device_count()}")
        
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            print(f"GPU {i}: {props.name}")
            print(f"  Memory: {props.total_memory / 1024**3:.1f} GB")
            print(f"  Compute capability: {props.major}.{props.minor}")
        
        # Test GPU tensor
        try:
            x = torch.randn(1000, 1000).cuda()
            y = torch.mm(x, x)
            print("✅ GPU tensor operations working")
        except Exception as e:
            print(f"❌ GPU tensor test failed: {e}")
    else:
        print("❌ CUDA not available")

def check_sentence_transformers_gpu():
    """Check if sentence-transformers can use GPU."""
    print("\n🧠 Sentence Transformers GPU Debug")
    print("=" * 50)
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # Load model
        print("📦 Loading sentence-transformers model...")
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        print(f"Model device: {model.device}")
        print(f"Model modules on device:")
        for name, module in model.named_modules():
            if hasattr(module, 'weight') and hasattr(module.weight, 'device'):
                print(f"  {name}: {module.weight.device}")
                break
        
        # Test encoding with GPU
        test_texts = [
            "This is a test sentence for GPU encoding",
            "Another test sentence to check GPU utilization",
            "Final test sentence for embeddings"
        ]
        
        print("\n🔥 Testing embedding generation...")
        
        # CPU test
        if torch.cuda.is_available():
            print("Testing CPU encoding...")
            model_cpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')
            import time
            start = time.time()
            embeddings_cpu = model_cpu.encode(test_texts)
            cpu_time = time.time() - start
            print(f"CPU encoding time: {cpu_time:.3f}s")
            
            # GPU test
            print("Testing GPU encoding...")
            model_gpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
            start = time.time()
            embeddings_gpu = model_gpu.encode(test_texts)
            gpu_time = time.time() - start
            print(f"GPU encoding time: {gpu_time:.3f}s")
            print(f"Speedup: {cpu_time/gpu_time:.1f}x")
            
            print(f"Embeddings shape: {embeddings_gpu.shape}")
            print(f"GPU model device: {model_gpu.device}")
        else:
            print("⚠️  CUDA not available, testing CPU only...")
            embeddings = model.encode(test_texts)
            print(f"Embeddings shape: {embeddings.shape}")
            
    except Exception as e:
        print(f"❌ Sentence transformers test failed: {e}")
        import traceback
        traceback.print_exc()

def check_embedding_service():
    """Check our embedding service GPU usage."""
    print("\n🔧 RAG Embedding Service GPU Debug")
    print("=" * 50)
    
    try:
        import asyncio
        from src.backend.database import AsyncSessionLocal
        from src.backend.services.embedding_service import EmbeddingService
        
        async def test_embedding_service():
            async with AsyncSessionLocal() as session:
                service = EmbeddingService(session)
                
                # Check if service uses GPU
                print("🔍 Checking embedding service configuration...")
                
                # Generate embeddings
                test_text = "This is a test for our embedding service GPU usage"
                print(f"📝 Test text: {test_text}")
                
                # Check if we can force GPU in our service
                print("🔥 Testing embedding generation...")
                
                # This will call our service
                embedding = await service.generate_embedding(test_text)
                print(f"✅ Generated embedding: {len(embedding)} dimensions")
                
                # Check model device if accessible
                if hasattr(service, '_model') and service._model:
                    print(f"Service model device: {service._model.device}")
                
        asyncio.run(test_embedding_service())
        
    except Exception as e:
        print(f"❌ Embedding service test failed: {e}")
        import traceback
        traceback.print_exc()

def gpu_monitoring_test():
    """Test with GPU monitoring."""
    print("\n📊 GPU Monitoring Test")
    print("=" * 50)
    
    try:
        import GPUtil
        
        print("Initial GPU status:")
        gpus = GPUtil.getGPUs()
        for gpu in gpus:
            print(f"GPU {gpu.id}: {gpu.name}")
            print(f"  Memory: {gpu.memoryUsed}MB / {gpu.memoryTotal}MB")
            print(f"  Load: {gpu.load * 100:.1f}%")
        
        # Heavy GPU test
        if torch.cuda.is_available():
            print("\n🔥 Running heavy GPU workload...")
            
            # Large matrix multiplication
            x = torch.randn(5000, 5000).cuda()
            y = torch.randn(5000, 5000).cuda()
            
            for i in range(5):
                result = torch.mm(x, y)
                torch.cuda.synchronize()
                print(f"  Iteration {i+1}/5 completed")
            
            print("\nFinal GPU status:")
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                print(f"GPU {gpu.id}: {gpu.name}")
                print(f"  Memory: {gpu.memoryUsed}MB / {gpu.memoryTotal}MB")
                print(f"  Load: {gpu.load * 100:.1f}%")
        
    except Exception as e:
        print(f"❌ GPU monitoring failed: {e}")

def main():
    """Run all GPU debug tests."""
    check_torch_setup()
    check_sentence_transformers_gpu()
    check_embedding_service()
    gpu_monitoring_test()
    
    print("\n" + "=" * 50)
    print("🏁 GPU Debug Complete!")
    print("\nIf your GPU isn't being used, possible causes:")
    print("1. 🔧 Model not explicitly set to GPU device")
    print("2. 📦 sentence-transformers defaulting to CPU")
    print("3. 🚨 CUDA/PyTorch version mismatch")
    print("4. 💾 Insufficient GPU memory causing fallback")

if __name__ == "__main__":
    main()