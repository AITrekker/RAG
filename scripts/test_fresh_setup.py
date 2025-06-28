#!/usr/bin/env python3
"""
Test script to verify fresh clone setup process.
This simulates what a new user would experience after cloning the repository.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, description, check=True):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}")
    print(f"   Running: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Success")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
        else:
            print(f"   ❌ Failed")
            print(f"   Error: {result.stderr.strip()}")
            if check:
                return False
        return True
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        if check:
            return False
        return True

def check_file_exists(filepath, description):
    """Check if a file exists."""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} (missing)")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists."""
    if Path(dirpath).exists() and Path(dirpath).is_dir():
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ {description}: {dirpath} (missing)")
        return False

def main():
    """Test the complete setup process."""
    print("🧪 Testing Fresh Clone Setup Process")
    print("=" * 50)
    
    # Check current directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Check if we're in the right place
    if not (current_dir / "setup.py").exists():
        print("❌ Error: setup.py not found. Please run this from the project root.")
        sys.exit(1)
    
    # Step 1: Check prerequisites
    print("\n📋 Checking Prerequisites")
    print("-" * 30)
    
    prereqs_ok = True
    
    # Check Python version
    python_version = sys.version_info
    if python_version >= (3, 11):
        print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"❌ Python {python_version.major}.{python_version.minor}.{python_version.micro} (need 3.11+)")
        prereqs_ok = False
    
    # Check Docker
    if run_command("docker --version", "Docker", check=False):
        print("✅ Docker available")
    else:
        print("❌ Docker not available")
        prereqs_ok = False
    
    # Check Docker Compose
    if run_command("docker-compose --version", "Docker Compose", check=False):
        print("✅ Docker Compose available")
    else:
        print("❌ Docker Compose not available")
        prereqs_ok = False
    
    if not prereqs_ok:
        print("\n❌ Prerequisites not met. Please install missing components.")
        sys.exit(1)
    
    # Step 2: Check essential files
    print("\n📁 Checking Essential Files")
    print("-" * 30)
    
    essential_files = [
        ("setup.py", "Root setup script"),
        ("requirements.txt", "Python requirements"),
        ("requirements-base.txt", "Base requirements"),
        (".env.example", "Environment template"),
        ("docker-compose.yml", "Docker Compose config"),
        ("scripts/db-init.py", "Database initialization script"),
        ("scripts/run_backend.py", "Backend runner script"),
        ("src/backend/main.py", "Backend main file"),
    ]
    
    files_ok = True
    for filepath, description in essential_files:
        if not check_file_exists(filepath, description):
            files_ok = False
    
    if not files_ok:
        print("\n❌ Essential files missing. Repository may be incomplete.")
        sys.exit(1)
    
    # Step 3: Test virtual environment creation
    print("\n🐍 Testing Virtual Environment Setup")
    print("-" * 30)
    
    # Check if virtual environment exists
    venv_path = Path(".venv")
    if venv_path.exists():
        print("✅ Virtual environment already exists")
    else:
        print("ℹ️  Virtual environment will be created during setup")
    
    # Step 4: Test setup.py
    print("\n⚙️  Testing Setup Script")
    print("-" * 30)
    
    # Run setup.py (this will install dependencies and create .env)
    if not run_command("python setup.py", "Running setup.py"):
        print("❌ Setup failed")
        sys.exit(1)
    
    # Step 5: Verify setup results
    print("\n🔍 Verifying Setup Results")
    print("-" * 30)
    
    setup_ok = True
    
    # Check .env file
    if not check_file_exists(".env", "Environment file"):
        setup_ok = False
    
    # Check essential directories
    essential_dirs = [
        ("data/tenants", "Tenant data directory"),
        ("logs", "Logs directory"),
        ("cache/transformers", "Transformers cache"),
        ("cache/huggingface", "HuggingFace cache"),
    ]
    
    for dirpath, description in essential_dirs:
        if not check_directory_exists(dirpath, description):
            setup_ok = False
    
    # Step 6: Test Docker services
    print("\n🐳 Testing Docker Services")
    print("-" * 30)
    
    # Test Qdrant startup
    if run_command("docker-compose up -d qdrant", "Starting Qdrant"):
        print("✅ Qdrant started successfully")
        
        # Wait a moment for Qdrant to start
        import time
        time.sleep(3)
        
        # Test Qdrant health
        if run_command("docker-compose ps qdrant", "Checking Qdrant status"):
            print("✅ Qdrant is running")
        else:
            print("❌ Qdrant failed to start properly")
            setup_ok = False
    else:
        print("❌ Failed to start Qdrant")
        setup_ok = False
    
    # Step 7: Test database initialization
    print("\n🗄️  Testing Database Initialization")
    print("-" * 30)
    
    if run_command("python scripts/db-init.py", "Initializing database"):
        print("✅ Database initialized successfully")
    else:
        print("❌ Database initialization failed")
        setup_ok = False
    
    # Step 8: Test backend startup
    print("\n🚀 Testing Backend Startup")
    print("-" * 30)
    
    # Try to start backend in background
    try:
        backend_process = subprocess.Popen(
            ["python", "scripts/run_backend.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for startup
        import time
        time.sleep(5)
        
        # Check if process is still running
        if backend_process.poll() is None:
            print("✅ Backend started successfully")
            backend_process.terminate()
            backend_process.wait()
        else:
            stdout, stderr = backend_process.communicate()
            print("❌ Backend failed to start")
            print(f"   Error: {stderr}")
            setup_ok = False
            
    except Exception as e:
        print(f"❌ Failed to test backend startup: {e}")
        setup_ok = False
    
    # Step 9: Cleanup
    print("\n🧹 Cleanup")
    print("-" * 30)
    
    # Stop Qdrant
    run_command("docker-compose down", "Stopping Docker services", check=False)
    
    # Final summary
    print("\n" + "=" * 50)
    if setup_ok:
        print("🎉 FRESH CLONE SETUP TEST PASSED!")
        print("✅ All components are working correctly")
        print("\nNext steps for a real fresh clone:")
        print("1. git clone <repository-url>")
        print("2. cd RAG")
        print("3. python -m venv .venv")
        print("4. .venv\\Scripts\\activate  # Windows")
        print("5. python setup.py")
        print("6. docker-compose up -d qdrant")
        print("7. python scripts/db-init.py")
        print("8. python scripts/run_backend.py")
    else:
        print("❌ FRESH CLONE SETUP TEST FAILED!")
        print("Some components are not working correctly")
        print("Please check the errors above and fix them")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 