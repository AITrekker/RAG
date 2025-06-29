#!/usr/bin/env python3
"""
Setup script to install dependencies for running scripts locally
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies for local script execution"""
    
    # Core dependencies needed for the scripts
    dependencies = [
        "asyncpg",
        "sqlalchemy[asyncio]",
        "python-dotenv"
    ]
    
    print("🔧 Installing dependencies for local script execution...")
    
    for dep in dependencies:
        print(f"  📦 Installing {dep}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"  ✅ {dep} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Failed to install {dep}: {e}")
            return False
    
    print("\n✅ All dependencies installed!")
    print("\n🚀 You can now run scripts locally:")
    print("  python scripts/rename-tenants.py")
    print("  python scripts/delta-sync.py")
    
    return True

if __name__ == "__main__":
    success = install_dependencies()
    if not success:
        sys.exit(1)