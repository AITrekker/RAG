"""
GPU Test Configuration
Configuration to prefer GPU usage during tests for better performance validation.
"""

import os
import subprocess
import json

def check_gpu_availability():
    """Check if GPU is available for testing."""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            return {
                "available": True,
                "count": gpu_count,
                "memory_gb": gpu_memory,
                "device_name": torch.cuda.get_device_name(0)
            }
    except ImportError:
        pass
    
    return {"available": False}

def setup_gpu_test_environment():
    """Set up environment variables to prefer GPU usage during tests."""
    gpu_info = check_gpu_availability()
    
    if gpu_info["available"]:
        # Force GPU usage for embeddings
        os.environ["EMBEDDING_DEVICE"] = "cuda"
        os.environ["EMBEDDING_BATCH_SIZE"] = "64"  # Larger batch for GPU
        os.environ["TORCH_USE_CUDA_DSA"] = "1"     # Enable CUDA optimizations
        
        print(f"✅ GPU Test Environment: {gpu_info['device_name']} ({gpu_info['memory_gb']:.1f}GB)")
        return True
    else:
        # Fall back to CPU with smaller batches
        os.environ["EMBEDDING_DEVICE"] = "cpu"
        os.environ["EMBEDDING_BATCH_SIZE"] = "16"
        
        print("⚠️ GPU not available, falling back to CPU for tests")
        return False

def get_optimal_test_config():
    """Get optimal test configuration based on available hardware."""
    gpu_info = check_gpu_availability()
    
    if gpu_info["available"]:
        return {
            "embedding_device": "cuda",
            "batch_size": 64 if gpu_info["memory_gb"] > 8 else 32,
            "expected_speed": "fast",
            "timeout_multiplier": 1.0
        }
    else:
        return {
            "embedding_device": "cpu", 
            "batch_size": 16,
            "expected_speed": "slow",
            "timeout_multiplier": 2.0
        }

# Auto-setup when imported
_gpu_available = setup_gpu_test_environment()
TEST_CONFIG = get_optimal_test_config()

# Export for use in tests
__all__ = ["check_gpu_availability", "setup_gpu_test_environment", "TEST_CONFIG", "_gpu_available"]