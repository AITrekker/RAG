#!/usr/bin/env python3
"""
Test RAG query functionality

Tests RAG queries against the demo tenant data.
Requires sync to be completed first (run test_sync.py).

Since tenant API keys are hidden for existing tenants, this script
will attempt to use the admin key initially and provide guidance
for getting tenant-specific keys.

Usage:
    python scripts/test_query.py
    python scripts/test_query.py --query "What are the product specifications?"
"""

import requests
import json
import os
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.utils import get_paths
    paths = get_paths()
    PROJECT_ROOT = paths.root
except ImportError:
    # Fallback to old method
    PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
env_file = PROJECT_ROOT / ".env"
load_dotenv(env_file)

BACKEND_URL = "http://localhost:8000"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

def get_tenant_api_key():
    """Try to get tenant API key from demo file, fallback to admin key."""
    if 'paths' in locals():
        tenant_keys_file = paths.demo_keys_file
    else:
        tenant_keys_file = PROJECT_ROOT / "demo_tenant_keys.json"
    
    if tenant_keys_file.exists():
        try:
            with open(tenant_keys_file, 'r') as f:
                tenant_keys = json.load(f)
            
            # Get first tenant's API key
            for tenant_name, tenant_info in tenant_keys.items():
                api_key = tenant_info.get("api_key")
                if api_key and api_key != "N/A" and "HIDDEN" not in api_key:
                    print(f"🔑 Using tenant API key from demo_tenant_keys.json")
                    return api_key
            
        except Exception as e:
            print(f"⚠️ Could not parse demo_tenant_keys.json: {e}")
    
    # Fallback to admin key
    print("🔑 Using admin API key (tenant keys not available)")
    return ADMIN_API_KEY

def main():
    parser = argparse.ArgumentParser(description='Test RAG query functionality')
    parser.add_argument('--query', '-q', 
                       default="What is mentioned in the company overview document?",
                       help='The query to test')
    
    args = parser.parse_args()
    
    if not ADMIN_API_KEY:
        print("❌ ADMIN_API_KEY not found in .env file")
        return
    
    # Get API key
    api_key = get_tenant_api_key()
    
    # Headers
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Request body
    body = {
        "query": args.query,
        "max_sources": 5,
        "confidence_threshold": 0.5
    }
    
    print("🤖 Testing RAG Query")
    print("=" * 50)
    print(f"Query: {args.query}")
    
    try:
        # Send query
        query_url = f"{BACKEND_URL}/api/v1/query"
        print(f"\n📡 Calling: POST {query_url}")
        
        response = requests.post(query_url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        print("\n✅ Query successful!")
        print(f"\n📝 Answer:")
        print(result['answer'])
        
        print(f"\n📚 Sources:")
        for source in result['sources']:
            filename = source.get('filename', source.get('document_name', 'Unknown Document'))
            print(f"  • {filename} (Score: {source['score']:.3f})")
            if source.get('page_number'):
                print(f"    Page: {source['page_number']}")
            text_content = source.get('content', source.get('text', ''))
            text_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
            print(f"    Text: {text_preview}")
            print()
        
        print(f"📊 Query Stats:")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Processing Time: {result['processing_time']:.3f}s")
        if result.get('tokens_used'):
            print(f"  Tokens Used: {result['tokens_used']}")
        if result.get('model_used'):
            print(f"  Model: {result['model_used']}")
        
    except requests.exceptions.RequestException as e:
        print("\n❌ Query failed!")
        print(f"Error: {e}")
        
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status Code: {e.response.status_code}")
            
            try:
                error_content = e.response.json()
                print(f"Error Details: {json.dumps(error_content, indent=2)}")
            except:
                print("Could not parse error response")
        
        print("\n🔧 Troubleshooting:")
        print("- Ensure sync completed successfully (run test_sync.py first)")
        print("- Check if embeddings exist in Qdrant UI: http://localhost:6333/dashboard")
        print("- Check backend logs: docker-compose logs backend")
        print("- Verify API key has access to tenant data")
    
    print("\n🧪 Try more queries:")
    print("python scripts/test_query.py --query 'What are the financial highlights?'")
    print("python scripts/test_query.py --query 'Tell me about the marketing strategy'")
    print("python scripts/test_query.py --query 'What is in the technical documentation?'")

if __name__ == "__main__":
    main()