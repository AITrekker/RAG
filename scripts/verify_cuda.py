#!/usr/bin/env python3
"""
CUDA and RTX 5070 Verification Script for RAG Platform
Comprehensive testing of GPU capabilities and transformers integration
"""

import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def print_banner():
    """Print verification banner"""
    print("🎮 RTX 5070 CUDA Verification for RAG Platform")
    print("=" * 50)
    print()

def print_section(title: str):
    """Print section header"""
    print(f"\n{'='*15} {title} {'='*15}")

def print_test(test_name: str, status: str = "INFO", details: str = ""):
    """Print test result with status"""
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅", 
        "WARNING": "⚠️",
        "ERROR": "❌",
        "RUNNING": "🔄"
    }
    icon = icons.get(status, "ℹ️")
    if details:
        print(f"{icon} {test_name}: {details}")
    else:
        print(f"{icon} {test_name}")

def check_cuda_installation() -> Dict[str, any]:
    """Check CUDA installation and drivers"""
    print_section("CUDA INSTALLATION CHECK")
    
    cuda_info = {
        "nvidia_smi": False,
        "cuda_version": None,
        "driver_version": None,
        "gpu_count": 0,
        "gpus": []
    }
    
    # Check nvidia-smi
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=True)
        cuda_info["nvidia_smi"] = True
        print_test("nvidia-smi command", "SUCCESS")
        
        # Parse nvidia-smi output for basic info
        lines = result.stdout.split('\n')
        for line in lines:
            if "Driver Version:" in line:
                parts = line.split()
                driver_idx = parts.index("Driver") + 2
                cuda_idx = parts.index("CUDA") + 2 if "CUDA" in parts else None
                
                cuda_info["driver_version"] = parts[driver_idx]
                if cuda_idx and cuda_idx < len(parts):
                    cuda_info["cuda_version"] = parts[cuda_idx]
                
                print_test("NVIDIA Driver", "SUCCESS", f"Version {cuda_info['driver_version']}")
                if cuda_info["cuda_version"]:
                    print_test("CUDA Runtime", "SUCCESS", f"Version {cuda_info['cuda_version']}")
                break
    
    except subprocess.CalledProcessError:
        print_test("nvidia-smi command", "ERROR", "Failed to run nvidia-smi")
    except FileNotFoundError:
        print_test("nvidia-smi command", "ERROR", "nvidia-smi not found - NVIDIA drivers not installed")
    except Exception as e:
        print_test("nvidia-smi command", "ERROR", f"Unexpected error: {e}")
    
    return cuda_info

def check_pytorch_cuda() -> Dict[str, any]:
    """Check PyTorch CUDA integration"""
    print_section("PYTORCH CUDA INTEGRATION")
    
    pytorch_info = {
        "installed": False,
        "cuda_available": False,
        "cuda_version": None,
        "cudnn_version": None,
        "gpu_count": 0,
        "gpu_names": [],
        "memory_info": []
    }
    
    try:
        import torch
        pytorch_info["installed"] = True
        print_test("PyTorch installation", "SUCCESS", f"Version {torch.__version__}")
        
        # Check CUDA availability
        if torch.cuda.is_available():
            pytorch_info["cuda_available"] = True
            pytorch_info["cuda_version"] = torch.version.cuda
            pytorch_info["gpu_count"] = torch.cuda.device_count()
            
            print_test("PyTorch CUDA support", "SUCCESS", f"CUDA {pytorch_info['cuda_version']}")
            print_test("GPU count", "SUCCESS", str(pytorch_info["gpu_count"]))
            
            # Check cuDNN
            if torch.backends.cudnn.enabled:
                pytorch_info["cudnn_version"] = torch.backends.cudnn.version()
                print_test("cuDNN support", "SUCCESS", f"Version {pytorch_info['cudnn_version']}")
            else:
                print_test("cuDNN support", "WARNING", "Not enabled")
            
            # Get GPU information
            for i in range(pytorch_info["gpu_count"]):
                gpu_name = torch.cuda.get_device_name(i)
                pytorch_info["gpu_names"].append(gpu_name)
                
                # Memory info
                memory_allocated = torch.cuda.memory_allocated(i) / 1024**3  # GB
                memory_reserved = torch.cuda.memory_reserved(i) / 1024**3    # GB
                memory_total = torch.cuda.get_device_properties(i).total_memory / 1024**3  # GB
                
                pytorch_info["memory_info"].append({
                    "allocated": memory_allocated,
                    "reserved": memory_reserved,
                    "total": memory_total
                })
                
                print_test(f"GPU {i}", "SUCCESS", f"{gpu_name}")
                print_test(f"GPU {i} Memory", "INFO", f"{memory_total:.1f} GB total")
                
                # Check if it's RTX 5070
                if "RTX 5070" in gpu_name:
                    print_test("RTX 5070 Detection", "SUCCESS", "Target GPU found!")
                elif "RTX" in gpu_name:
                    print_test("RTX GPU Detection", "SUCCESS", f"RTX GPU found: {gpu_name}")
        else:
            pytorch_info["cuda_available"] = False
            print_test("PyTorch CUDA support", "ERROR", "CUDA not available")
            
    except ImportError:
        print_test("PyTorch installation", "ERROR", "PyTorch not installed")
    except Exception as e:
        print_test("PyTorch check", "ERROR", f"Unexpected error: {e}")
    
    return pytorch_info

def test_basic_gpu_operations() -> bool:
    """Test basic GPU tensor operations"""
    print_section("BASIC GPU OPERATIONS TEST")
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print_test("GPU Operations", "ERROR", "CUDA not available")
            return False
        
        # Test tensor creation
        print_test("Creating GPU tensors", "RUNNING")
        device = torch.device('cuda:0')
        
        # Create tensors on GPU
        x = torch.randn(1000, 1000, device=device)
        y = torch.randn(1000, 1000, device=device)
        print_test("GPU tensor creation", "SUCCESS", f"Shape: {x.shape}")
        
        # Test basic operations
        print_test("Matrix multiplication", "RUNNING")
        start_time = time.time()
        z = torch.matmul(x, y)
        gpu_time = time.time() - start_time
        print_test("GPU matrix multiplication", "SUCCESS", f"{gpu_time:.4f} seconds")
        
        # Test CPU comparison
        print_test("CPU comparison", "RUNNING")
        x_cpu = x.cpu()
        y_cpu = y.cpu()
        start_time = time.time()
        z_cpu = torch.matmul(x_cpu, y_cpu)
        cpu_time = time.time() - start_time
        print_test("CPU matrix multiplication", "INFO", f"{cpu_time:.4f} seconds")
        
        speedup = cpu_time / gpu_time
        print_test("GPU Speedup", "SUCCESS", f"{speedup:.2f}x faster than CPU")
        
        # Test memory transfer
        print_test("GPU-CPU memory transfer", "RUNNING")
        result_cpu = z.cpu()
        result_gpu = result_cpu.cuda()
        print_test("Memory transfer", "SUCCESS", "GPU ↔ CPU transfer working")
        
        return True
        
    except Exception as e:
        print_test("GPU Operations", "ERROR", f"Failed: {e}")
        traceback.print_exc()
        return False

def test_transformers_gpu() -> bool:
    """Test Transformers library GPU integration"""
    print_section("TRANSFORMERS GPU INTEGRATION")
    
    try:
        from transformers import AutoTokenizer, AutoModel
        import torch
        
        if not torch.cuda.is_available():
            print_test("Transformers GPU test", "ERROR", "CUDA not available")
            return False
        
        print_test("Loading transformers model", "RUNNING")
        
        # Use a small model for testing
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        
        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        
        print_test("Model loading", "SUCCESS", f"Loaded {model_name}")
        
        # Move model to GPU
        device = torch.device('cuda:0')
        model = model.to(device)
        print_test("Model on GPU", "SUCCESS", f"Moved to {device}")
        
        # Test inference
        print_test("GPU inference test", "RUNNING")
        test_text = "This is a test sentence for GPU inference."
        
        # Tokenize
        inputs = tokenizer(test_text, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Forward pass
        start_time = time.time()
        with torch.no_grad():
            outputs = model(**inputs)
        inference_time = time.time() - start_time
        
        print_test("GPU inference", "SUCCESS", f"{inference_time:.4f} seconds")
        
        # Check output shape
        embeddings = outputs.last_hidden_state
        print_test("Output embeddings", "SUCCESS", f"Shape: {embeddings.shape}")
        
        # Test batch processing
        print_test("Batch processing test", "RUNNING")
        batch_texts = [
            "First test sentence for batch processing.",
            "Second test sentence for batch processing.",
            "Third test sentence for batch processing."
        ]
        
        batch_inputs = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True)
        batch_inputs = {k: v.to(device) for k, v in batch_inputs.items()}
        
        start_time = time.time()
        with torch.no_grad():
            batch_outputs = model(**batch_inputs)
        batch_time = time.time() - start_time
        
        print_test("Batch inference", "SUCCESS", f"{batch_time:.4f} seconds for {len(batch_texts)} sentences")
        
        return True
        
    except ImportError as e:
        print_test("Transformers library", "ERROR", f"Not installed: {e}")
        return False
    except Exception as e:
        print_test("Transformers GPU test", "ERROR", f"Failed: {e}")
        traceback.print_exc()
        return False

def test_memory_stress() -> bool:
    """Test GPU memory handling under stress"""
    print_section("GPU MEMORY STRESS TEST")
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print_test("Memory stress test", "ERROR", "CUDA not available")
            return False
        
        device = torch.device('cuda:0')
        initial_memory = torch.cuda.memory_allocated(device) / 1024**3
        print_test("Initial GPU memory", "INFO", f"{initial_memory:.2f} GB")
        
        # Gradually increase tensor size to test memory limits
        sizes = [100, 500, 1000, 2000, 3000]
        successful_sizes = []
        
        for size in sizes:
            try:
                print_test(f"Testing {size}x{size} tensors", "RUNNING")
                
                # Create large tensors
                x = torch.randn(size, size, device=device)
                y = torch.randn(size, size, device=device)
                
                # Perform operation
                z = torch.matmul(x, y)
                
                current_memory = torch.cuda.memory_allocated(device) / 1024**3
                print_test(f"Size {size}x{size}", "SUCCESS", f"Memory: {current_memory:.2f} GB")
                successful_sizes.append(size)
                
                # Clean up
                del x, y, z
                torch.cuda.empty_cache()
                
            except torch.cuda.OutOfMemoryError:
                print_test(f"Size {size}x{size}", "WARNING", "Out of memory - reached limit")
                break
            except Exception as e:
                print_test(f"Size {size}x{size}", "ERROR", f"Failed: {e}")
                break
        
        if successful_sizes:
            max_size = max(successful_sizes)
            print_test("Memory stress test", "SUCCESS", f"Max tensor size: {max_size}x{max_size}")
            
            # Estimate maximum model size
            elements_per_gb = (max_size * max_size) / (torch.cuda.memory_allocated(device) / 1024**3)
            print_test("Estimated capacity", "INFO", f"~{elements_per_gb/1e6:.1f}M parameters per GB")
        
        return True
        
    except Exception as e:
        print_test("Memory stress test", "ERROR", f"Failed: {e}")
        return False

def test_mixed_precision() -> bool:
    """Test mixed precision (FP16) capabilities"""
    print_section("MIXED PRECISION TEST")
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print_test("Mixed precision test", "ERROR", "CUDA not available")
            return False
        
        device = torch.device('cuda:0')
        
        # Test FP32 operations
        print_test("FP32 baseline test", "RUNNING")
        x_fp32 = torch.randn(1000, 1000, device=device, dtype=torch.float32)
        y_fp32 = torch.randn(1000, 1000, device=device, dtype=torch.float32)
        
        start_time = time.time()
        z_fp32 = torch.matmul(x_fp32, y_fp32)
        fp32_time = time.time() - start_time
        fp32_memory = torch.cuda.memory_allocated(device) / 1024**3
        
        print_test("FP32 operations", "SUCCESS", f"{fp32_time:.4f}s, {fp32_memory:.2f} GB")
        
        # Clear memory
        del x_fp32, y_fp32, z_fp32
        torch.cuda.empty_cache()
        
        # Test FP16 operations
        print_test("FP16 mixed precision test", "RUNNING")
        x_fp16 = torch.randn(1000, 1000, device=device, dtype=torch.float16)
        y_fp16 = torch.randn(1000, 1000, device=device, dtype=torch.float16)
        
        start_time = time.time()
        z_fp16 = torch.matmul(x_fp16, y_fp16)
        fp16_time = time.time() - start_time
        fp16_memory = torch.cuda.memory_allocated(device) / 1024**3
        
        print_test("FP16 operations", "SUCCESS", f"{fp16_time:.4f}s, {fp16_memory:.2f} GB")
        
        # Calculate improvements
        speed_improvement = fp32_time / fp16_time
        memory_savings = (fp32_memory - fp16_memory) / fp32_memory * 100
        
        print_test("Speed improvement", "SUCCESS", f"{speed_improvement:.2f}x faster")
        print_test("Memory savings", "SUCCESS", f"{memory_savings:.1f}% less memory")
        
        # Test automatic mixed precision (AMP)
        try:
            from torch.cuda.amp import autocast, GradScaler
            
            print_test("Automatic Mixed Precision (AMP)", "RUNNING")
            
            # Simple AMP test
            x = torch.randn(500, 500, device=device, requires_grad=True)
            y = torch.randn(500, 500, device=device, requires_grad=True)
            
            scaler = GradScaler()
            
            with autocast():
                z = torch.matmul(x, y)
                loss = z.sum()
            
            scaler.scale(loss).backward()
            scaler.step(torch.optim.SGD([x, y], lr=0.01))
            scaler.update()
            
            print_test("AMP training simulation", "SUCCESS", "Autocast and gradient scaling working")
            
        except ImportError:
            print_test("AMP support", "WARNING", "torch.cuda.amp not available")
        
        return True
        
    except Exception as e:
        print_test("Mixed precision test", "ERROR", f"Failed: {e}")
        traceback.print_exc()
        return False

def generate_performance_report(cuda_info: Dict, pytorch_info: Dict) -> str:
    """Generate a performance report"""
    report = []
    report.append("=" * 60)
    report.append("RTX 5070 CUDA VERIFICATION REPORT")
    report.append("=" * 60)
    report.append("")
    
    # System Information
    report.append("SYSTEM INFORMATION:")
    report.append(f"  NVIDIA Driver: {cuda_info.get('driver_version', 'Unknown')}")
    report.append(f"  CUDA Runtime: {cuda_info.get('cuda_version', 'Unknown')}")
    report.append(f"  PyTorch Version: {pytorch_info.get('pytorch_version', 'Unknown')}")
    report.append("")
    
    # GPU Information
    if pytorch_info.get("gpu_count", 0) > 0:
        report.append("GPU INFORMATION:")
        for i, gpu_name in enumerate(pytorch_info.get("gpu_names", [])):
            report.append(f"  GPU {i}: {gpu_name}")
            if i < len(pytorch_info.get("memory_info", [])):
                memory = pytorch_info["memory_info"][i]
                report.append(f"    Memory: {memory['total']:.1f} GB")
        report.append("")
    
    # Recommendations
    report.append("RECOMMENDATIONS:")
    
    if pytorch_info.get("cuda_available", False):
        report.append("  ✅ GPU acceleration is ready for RAG platform")
        report.append("  ✅ Use mixed precision (FP16) to save memory")
        report.append("  ✅ Batch processing recommended for efficiency")
    else:
        report.append("  ❌ GPU acceleration not available")
        report.append("  🔧 Install CUDA drivers and PyTorch with CUDA support")
    
    # Model recommendations
    if pytorch_info.get("memory_info"):
        total_memory = pytorch_info["memory_info"][0]["total"]
        if total_memory >= 12:
            report.append("  📊 Suitable for large language models (7B+ parameters)")
        elif total_memory >= 8:
            report.append("  📊 Suitable for medium models (3-7B parameters)")
        else:
            report.append("  📊 Suitable for small models (<3B parameters)")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """Main verification function"""
    print_banner()
    
    # Run all verification tests
    cuda_info = check_cuda_installation()
    pytorch_info = check_pytorch_cuda()
    
    # Only run advanced tests if basic CUDA is working
    if pytorch_info.get("cuda_available", False):
        basic_ops_success = test_basic_gpu_operations()
        transformers_success = test_transformers_gpu()
        memory_success = test_memory_stress()
        precision_success = test_mixed_precision()
        
        # Overall success check
        all_tests_passed = all([
            basic_ops_success,
            transformers_success,
            memory_success,
            precision_success
        ])
    else:
        all_tests_passed = False
    
    # Generate and print report
    print_section("PERFORMANCE REPORT")
    report = generate_performance_report(cuda_info, pytorch_info)
    print(report)
    
    # Save report to file
    report_file = Path("logs") / "cuda_verification_report.txt"
    report_file.parent.mkdir(exist_ok=True)
    
    try:
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save report: {e}")
    
    # Exit with appropriate code
    if all_tests_passed:
        print("\n🎉 All CUDA verification tests passed!")
        print("🚀 RTX 5070 is ready for RAG platform development!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed or CUDA is not available")
        print("📝 Check the report above for recommendations")
        sys.exit(1)

if __name__ == "__main__":
    main() 