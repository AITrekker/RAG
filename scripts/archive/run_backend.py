#!/usr/bin/env python3
"""
Direct execution script for RAG Platform Backend
Runs FastAPI backend without Docker for debugging and development
"""

import os
import sys
import subprocess
import platform
import argparse
from pathlib import Path

def print_banner():
    """Print startup banner"""
    print("🚀 RAG Platform Backend - Direct Execution")
    print("=" * 45)

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import fastapi
        import uvicorn
        import pydantic_settings
        import dotenv
    except ImportError as e:
        print(f"❌ Missing critical dependency: {e.name}")
        print("   Please run 'pip install -r requirements.txt'")
        return False
    return True

def run_backend(project_root, debug=False, port=8000, host="127.0.0.1", log_level="info"):
    """Run the FastAPI backend using configuration from settings.py"""
    
    # Set environment variables based on arguments
    # This allows settings.py to pick them up
    os.environ['DEBUG'] = str(debug).lower()
    os.environ['LOG_LEVEL'] = log_level.upper()
    os.environ['RELOAD_ON_CHANGE'] = str(debug).lower()

    # Change to project root for proper imports
    os.chdir(project_root)

    cmd = [
        sys.executable, '-m', 'uvicorn',
        'src.backend.main:app',
        '--host', host,
        '--port', str(port),
    ]
    
    # Uvicorn handles its own log level and reloading from its CLI args
    if debug:
        cmd.append('--reload')
    
    cmd.extend(['--log-level', log_level.lower()])

    print(f"\n🚀 Starting backend server...")
    print(f"   Mode: {'Debug (reloading enabled)' if debug else 'Production'}")
    print(f"   URL: http://{host}:{port}")
    print("-" * 40)
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server failed: {e}")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Run the RAG Platform Backend directly.")
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--log-level', type=str, default='info', choices=['debug', 'info', 'warning', 'error', 'critical'], help='Set the log level')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with auto-reloading')
    args = parser.parse_args()

    print_banner()
    
    if not check_dependencies():
        sys.exit(1)
    
    project_root = Path(__file__).parent.parent.absolute()
    
    # Create necessary directories if they don't exist
    (project_root / 'cache').mkdir(exist_ok=True)
    (project_root / 'logs').mkdir(exist_ok=True)
    (project_root / 'documents').mkdir(exist_ok=True)
    
    print("\n✅ Initial checks complete. Launching server...")
    
    run_backend(
        project_root, 
        debug=args.debug, 
        port=args.port, 
        host=args.host, 
        log_level=args.log_level
    )

if __name__ == "__main__":
    main() 