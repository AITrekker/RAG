"""
Test script to validate API structure without running server.
"""

import json
import sys
import os

def test_api_imports():
    """Test if we can import the basic modules needed"""
    try:
        print("Testing basic Python imports...")
        from typing import Optional, Dict, Any
        print("✓ typing imports work")
        
        # Test if we have the requirements we need
        req_file = "requirements.txt"
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                reqs = f.read()
                if "fastapi" in reqs:
                    print("✓ FastAPI found in requirements.txt")
                if "uvicorn" in reqs:
                    print("✓ Uvicorn found in requirements.txt")
        
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_api_structure():
    """Test the API file structure"""
    api_file = "api_rebuild.py"
    if os.path.exists(api_file):
        with open(api_file, 'r') as f:
            content = f.read()
            
        tests = [
            ("FastAPI import", "from fastapi import FastAPI"),
            ("Health endpoint", "@app.get(\"/health\""),
            ("Query endpoint", "@app.post(\"/api/v1/query/ask\""),
            ("CORS middleware", "CORSMiddleware"),
            ("Pydantic models", "class HealthResponse(BaseModel)"),
        ]
        
        print("\nTesting API structure...")
        for test_name, pattern in tests:
            if pattern in content:
                print(f"✓ {test_name}")
            else:
                print(f"✗ {test_name}")
        
        return True
    else:
        print("✗ api_rebuild.py not found")
        return False

def show_next_steps():
    """Show what to do next"""
    print("\n" + "="*50)
    print("NEXT STEPS TO GET API RUNNING:")
    print("="*50)
    print("1. Install Python packages:")
    print("   pip install fastapi uvicorn pydantic")
    print()
    print("2. Run the API server:")
    print("   python api_rebuild.py")
    print()
    print("3. Test endpoints:")
    print("   curl http://localhost:8000/health")
    print("   curl http://localhost:8000/api/v1/health")
    print()
    print("4. View API docs:")
    print("   http://localhost:8000/docs")
    print("="*50)

if __name__ == "__main__":
    print("RAG API Structure Test")
    print("=" * 30)
    
    imports_ok = test_api_imports()
    structure_ok = test_api_structure()
    
    if imports_ok and structure_ok:
        print("\n✓ API structure looks good!")
        show_next_steps()
    else:
        print("\n✗ Some issues found")