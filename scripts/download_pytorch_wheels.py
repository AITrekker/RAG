#!/usr/bin/env python3
"""
Download PyTorch wheels locally for offline Docker builds.
This script downloads the specific PyTorch versions needed for RTX 5070 compatibility.
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path

# PyTorch packages and versions for RTX 5070 (CUDA 12.8)
PYTORCH_PACKAGES = [
    "torch",
    "torchvision", 
    "torchaudio"
]

# PyTorch index URL for CUDA 12.8
PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"

def download_wheel(package_name, target_dir):
    """Download a PyTorch wheel package."""
    print(f"Downloading {package_name}...")
    
    # Use pip download to get the wheel
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--index-url", PYTORCH_INDEX_URL,
        "--dest", target_dir,
        package_name
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Downloaded {package_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to download {package_name}: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    # Create cache directory for PyTorch wheels
    cache_dir = Path("cache/pytorch_wheels")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading PyTorch wheels to {cache_dir.absolute()}")
    print(f"Using PyTorch index: {PYTORCH_INDEX_URL}")
    print()
    
    success_count = 0
    for package in PYTORCH_PACKAGES:
        if download_wheel(package, str(cache_dir)):
            success_count += 1
    
    print()
    if success_count == len(PYTORCH_PACKAGES):
        print("✓ All PyTorch packages downloaded successfully!")
        print(f"Wheels saved to: {cache_dir.absolute()}")
        print()
        print("To use these wheels in Docker builds:")
        print("1. Use the Dockerfile.backend.local instead of Dockerfile.backend")
        print("2. Or copy the wheels to your Docker build context")
    else:
        print(f"✗ Only {success_count}/{len(PYTORCH_PACKAGES)} packages downloaded successfully")
        sys.exit(1)

if __name__ == "__main__":
    main() 