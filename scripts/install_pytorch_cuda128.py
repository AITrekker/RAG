#!/usr/bin/env python3
"""
Install PyTorch with CUDA 12.8 support for RTX 5070.
This ensures we get the correct PyTorch version for optimal RTX 5070 performance.
"""

import subprocess
import sys
import importlib.util

def check_pytorch_version():
    """Check current PyTorch installation."""
    try:
        import torch
        print(f"Current PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"GPU count: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"  GPU {i}: {props.name}")
        return True
    except ImportError:
        print("PyTorch not installed")
        return False

def install_pytorch_cuda128():
    """Install PyTorch with CUDA 12.8 support."""
    print("\n🚀 Installing PyTorch with CUDA 12.8 for RTX 5070")
    print("=" * 60)
    
    # Commands to run
    commands = [
        # Uninstall existing PyTorch (if any)
        [sys.executable, "-m", "pip", "uninstall", "-y", "torch", "torchvision", "torchaudio"],
        
        # Install CUDA 12.8 version
        [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", 
         "--index-url", "https://download.pytorch.org/whl/cu128"]
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"\n📦 Step {i}/{len(commands)}: {' '.join(cmd[3:])}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(f"✅ Success!")
            else:
                print(f"⚠️  Command completed with warnings:")
                if result.stderr:
                    print(result.stderr[:500])
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    return True

def verify_installation():
    """Verify the installation worked."""
    print("\n🔍 Verifying Installation")
    print("=" * 60)
    
    try:
        # Force reload if already imported
        if 'torch' in sys.modules:
            print("Reloading PyTorch module...")
            del sys.modules['torch']
            if 'torchvision' in sys.modules:
                del sys.modules['torchvision']
        
        import torch
        import torchvision
        
        print(f"✅ PyTorch version: {torch.__version__}")
        print(f"✅ TorchVision version: {torchvision.__version__}")
        print(f"✅ CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"✅ CUDA version: {torch.version.cuda}")
            print(f"✅ GPU count: {torch.cuda.device_count()}")
            
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"✅ GPU {i}: {props.name} ({props.total_memory // 1024**3} GB)")
            
            # Test GPU tensor operations
            try:
                x = torch.randn(1000, 1000).cuda()
                y = torch.mm(x, x)
                print("✅ GPU tensor operations working!")
            except Exception as e:
                print(f"❌ GPU tensor test failed: {e}")
                return False
        else:
            print("❌ CUDA not available - check your installation")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def main():
    """Main installation process."""
    print("🔧 PyTorch CUDA 12.8 Installation for RTX 5070")
    print("=" * 60)
    
    print("📋 Current installation status:")
    has_pytorch = check_pytorch_version()
    
    if has_pytorch:
        import torch
        if torch.cuda.is_available() and "cu128" in torch.__version__:
            print("\n✅ Correct PyTorch CUDA 12.8 already installed!")
            return True
    
    print(f"\n⚡ Installing CUDA 12.8 PyTorch for RTX 5070 optimization...")
    print("   This may take a few minutes to download...")
    
    if install_pytorch_cuda128():
        print(f"\n🔍 Verifying installation...")
        if verify_installation():
            print(f"\n🎉 SUCCESS! PyTorch with CUDA 12.8 installed!")
            print(f"Your RTX 5070 is now ready for maximum performance!")
            return True
        else:
            print(f"\n❌ Installation verification failed")
            return False
    else:
        print(f"\n❌ Installation failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)