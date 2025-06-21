#!/usr/bin/env python3
"""
Direct execution script for RAG Platform Backend
Runs FastAPI backend without Docker for debugging and development
"""

import os
import sys
import subprocess
import platform
import json
from pathlib import Path

def print_banner():
    """Print startup banner"""
    print("🚀 RAG Platform Backend - Direct Execution")
    print("=" * 45)
    print()

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_virtual_environment():
    """Check if virtual environment is activated"""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment is active")
        return True
    else:
        print("⚠️  Virtual environment not detected")
        print("   Recommendation: Activate your virtual environment first")
        response = input("   Continue anyway? (y/N): ").strip().lower()
        return response == 'y'

def check_cuda_availability():
    """Check CUDA availability for GPU acceleration"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
            print(f"✅ CUDA available - {gpu_count} GPU(s) detected")
            print(f"   Primary GPU: {gpu_name}")
            return True
        else:
            print("⚠️  CUDA not available - will run on CPU")
            return False
    except ImportError:
        print("⚠️  PyTorch not installed - CUDA check skipped")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    # Map of package names to their import names
    package_imports = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'transformers': 'transformers',
        'llama-index': 'llama_index',
        'sqlalchemy': 'sqlalchemy',
        'chromadb': 'chromadb',
        'python-dotenv': 'dotenv'
    }
    
    missing_packages = []
    for package, import_name in package_imports.items():
        try:
            __import__(import_name)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("   Install with: pip install -r requirements.txt")
        return False
    
    return True

def setup_environment():
    """Set up environment variables"""
    # Get project root (parent of scripts directory)
    project_root = Path(__file__).parent.parent.absolute()
    
    # Default environment variables
    env_vars = {
        'PYTHONPATH': str(project_root / 'src' / 'backend'),
        'DATABASE_URL': 'sqlite:///./data/rag_dev.db',
        'CHROMA_PERSIST_DIRECTORY': str(project_root / 'data' / 'chroma'),
        'UPLOAD_DIRECTORY': str(project_root / 'data' / 'uploads'),
        'TRANSFORMERS_CACHE': str(project_root / 'cache' / 'transformers'),
        'LOG_LEVEL': 'DEBUG',
        'DEBUG': 'true',
        'CORS_ORIGINS': '["http://localhost:3000", "http://127.0.0.1:3000"]'
    }
    
    # Load .env file if it exists
    env_file = project_root / '.env'
    if env_file.exists():
        print(f"✅ Loading environment from {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    # Set environment variables
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
            print(f"🔧 Set {key}={value}")
    
    # Create necessary directories
    directories = [
        project_root / 'data',
        project_root / 'data' / 'uploads',
        project_root / 'data' / 'chroma',
        project_root / 'cache',
        project_root / 'cache' / 'transformers',
        project_root / 'logs'
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    
    print("✅ Environment setup complete")
    return project_root

def run_backend(project_root, debug=False, port=8000, host="127.0.0.1"):
    """Run the FastAPI backend"""
    backend_path = project_root / 'src' / 'backend'
    
    # Check if main.py exists
    main_file = backend_path / 'main.py'
    if not main_file.exists():
        print(f"❌ Backend main.py not found at {main_file}")
        print("   This will be created in subsequent tasks")
        return False
    
    # Prepare uvicorn command
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'src.backend.main:app',
        '--host', host,
        '--port', str(port),
        '--reload' if debug else '--no-reload',
        '--log-level', 'debug' if debug else 'info'
    ]
    
    if debug:
        cmd.extend(['--reload-dir', str(backend_path)])
    
    print(f"🚀 Starting backend server...")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Debug: {debug}")
    print(f"   URL: http://{host}:{port}")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        # Change to project root for proper imports
        os.chdir(project_root)
        subprocess.run(cmd, check=True)
        return True
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Server failed to start: {e}")
        return False
    except FileNotFoundError:
        print("❌ uvicorn not found. Install with: pip install uvicorn")
        return False

def main():
    """Main execution function"""
    print_banner()
    
    # Pre-flight checks
    if not check_python_version():
        sys.exit(1)
    
    if not check_virtual_environment():
        sys.exit(1)
    
    print("\n📦 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    
    print("\n🔧 Setting up environment...")
    project_root = setup_environment()
    
    print("\n🖥️  System information:")
    print(f"   OS: {platform.system()} {platform.release()}")
    print(f"   Python: {sys.executable}")
    print(f"   Working directory: {project_root}")
    
    print("\n🎮 GPU Information:")
    check_cuda_availability()
    
    # Parse command line arguments
    debug = '--debug' in sys.argv or '-d' in sys.argv
    
    # Get port from arguments
    port = 8000
    if '--port' in sys.argv:
        try:
            port_idx = sys.argv.index('--port')
            port = int(sys.argv[port_idx + 1])
        except (IndexError, ValueError):
            print("⚠️  Invalid port specified, using default 8000")
    
    # Get host from arguments
    host = "127.0.0.1"
    if '--host' in sys.argv:
        try:
            host_idx = sys.argv.index('--host')
            host = sys.argv[host_idx + 1]
        except IndexError:
            print("⚠️  Invalid host specified, using default 127.0.0.1")
    
    print(f"\n🚀 Starting RAG Platform Backend...")
    success = run_backend(project_root, debug=debug, port=port, host=host)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    # Help message
    if '--help' in sys.argv or '-h' in sys.argv:
        print("RAG Platform Backend - Direct Execution Script")
        print()
        print("Usage: python scripts/run_backend.py [options]")
        print()
        print("Options:")
        print("  --debug, -d     Enable debug mode with auto-reload")
        print("  --port PORT     Specify port (default: 8000)")
        print("  --host HOST     Specify host (default: 127.0.0.1)")
        print("  --help, -h      Show this help message")
        print()
        print("Examples:")
        print("  python scripts/run_backend.py")
        print("  python scripts/run_backend.py --debug --port 8080")
        print("  python scripts/run_backend.py --host 0.0.0.0")
        sys.exit(0)
    
    main() 