#!/usr/bin/env python3
"""
Startup script for the Enterprise RAG Platform backend.
"""

import sys
import os
import uvicorn
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Run the FastAPI application."""
    print("🚀 Starting Enterprise RAG Platform Backend...")
    print("📍 API will be available at: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔍 Health Check: http://localhost:8000/api/v1/health")
    print("\n" + "="*50)
    
    try:
        # Import and run the FastAPI app
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure you're in the correct directory and all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 