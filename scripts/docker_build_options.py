#!/usr/bin/env python3
"""
Docker build options for avoiding PyTorch downloads when using --no-cache.
This script helps you choose the best approach for your situation.
"""

import subprocess
import sys
from pathlib import Path

def check_docker_version():
    """Check if Docker supports cache mounts."""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        version = result.stdout.strip()
        print(f"Docker version: {version}")
        
        # Extract version number
        version_parts = version.split()
        if len(version_parts) >= 3:
            version_num = version_parts[2].split('.')
            major = int(version_num[0])
            minor = int(version_num[1])
            
            # Docker 18.09+ supports cache mounts, but 20.10+ is more reliable
            if major >= 20 or (major == 18 and minor >= 9):
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        print(f"Could not check Docker version: {e}")
        return False

def main():
    print("=== Docker Build Options for PyTorch ===")
    print()
    
    docker_supports_cache = check_docker_version()
    
    print("Available options to avoid PyTorch downloads with --no-cache:")
    print()
    
    print("1. 🚀 RECOMMENDED: Use Docker Cache Mounts")
    print("   - Use Dockerfile.backend.cached")
    print("   - PyTorch downloads are cached between builds")
    print("   - Works with --no-cache for other layers")
    print("   - No manual download needed")
    print()
    
    if docker_supports_cache:
        print("   ✓ Your Docker version supports cache mounts")
        print("   Command: docker build -f docker/Dockerfile.backend.cached .")
    else:
        print("   ⚠ Your Docker version may not support cache mounts")
        print("   Consider upgrading Docker or using option 2")
    print()
    
    print("2. 📦 Local PyTorch Wheels")
    print("   - Download PyTorch wheels locally first")
    print("   - Use Dockerfile.backend.local")
    print("   - Works offline after initial download")
    print("   - Requires manual download step")
    print()
    print("   Steps:")
    print("   1. Run: python scripts/download_pytorch_wheels.py")
    print("   2. Build: docker build -f docker/Dockerfile.backend.local .")
    print()
    
    print("3. 🔄 Hybrid Approach")
    print("   - Use cache mounts for most packages")
    print("   - Keep PyTorch installation separate")
    print("   - Best of both worlds")
    print()
    
    print("4. 💾 Preserve Base Image")
    print("   - Don't use --no-cache on the base image layer")
    print("   - Only use --no-cache for application layers")
    print("   - PyTorch stays cached in base image")
    print()
    
    print("=== Quick Commands ===")
    print()
    print("# Option 1 (Recommended):")
    print("docker build -f docker/Dockerfile.backend.cached .")
    print()
    print("# Option 2 (Local wheels):")
    print("python scripts/download_pytorch_wheels.py")
    print("docker build -f docker/Dockerfile.backend.local .")
    print()
    print("# Option 4 (Preserve base):")
    print("docker build --target pytorch-base -f docker/Dockerfile.backend .")
    print("docker build --no-cache --target final -f docker/Dockerfile.backend .")
    print()
    
    print("=== Current Setup ===")
    print(f"Your current Dockerfile: docker/Dockerfile.backend")
    print(f"Cache directory: {Path('cache').absolute()}")
    
    if Path('cache/pytorch_wheels').exists():
        wheel_count = len(list(Path('cache/pytorch_wheels').glob('*.whl')))
        print(f"Local PyTorch wheels: {wheel_count} found")
    else:
        print("Local PyTorch wheels: None found")

if __name__ == "__main__":
    main() 