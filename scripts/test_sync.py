#!/usr/bin/env python3
"""
Trigger sync/embedding generation for demo tenants

Uses admin API key to trigger sync operations that will:
- Scan tenant upload directories
- Process demo files (txt files)
- Generate embeddings using sentence transformers
- Store vectors in Qdrant collections
- Update PostgreSQL with sync status

Usage:
    python scripts/test_sync.py
"""

import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
env_file = PROJECT_ROOT / ".env"
load_dotenv(env_file)

BACKEND_URL = "http://localhost:8000"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

if not ADMIN_API_KEY:
    print("❌ ADMIN_API_KEY not found in .env file")
    exit(1)

# Headers
headers = {
    "X-API-Key": ADMIN_API_KEY,
    "Content-Type": "application/json"
}

def main():
    print("🚀 Triggering Sync/Embedding Generation")
    print("=" * 50)
    
    try:
        # Trigger sync
        sync_url = f"{BACKEND_URL}/api/v1/sync/trigger"
        print(f"📡 Calling: POST {sync_url}")
        
        response = requests.post(sync_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        print("✅ Sync triggered successfully!")
        print(f"Sync ID: {result['sync_id']}")
        print(f"Status: {result['status']}")
        print(f"Started: {result['started_at']}")
        print(f"Message: {result['message']}")
        
        print("\n🔍 Next Steps:")
        print("1. Check Qdrant UI: http://localhost:6333/dashboard")
        print("2. Wait for sync to complete (watch container logs)")
        print("3. Run query test: python scripts/test_query.py")
        
    except requests.exceptions.RequestException as e:
        print("❌ Sync failed!")
        print(f"Error: {e}")
        
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status Code: {e.response.status_code}")
            
            try:
                error_content = e.response.json()
                print(f"Error Details: {json.dumps(error_content, indent=2)}")
            except:
                print("Could not parse error response")
        
        print("\n🔧 Troubleshooting:")
        print("- Check if backend container is running: docker-compose ps")
        print("- Check backend logs: docker-compose logs backend")
        print("- Verify admin API key in .env file")

if __name__ == "__main__":
    main()