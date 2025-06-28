#!/usr/bin/env python3
"""
Demo Query Example Script

Shows how to easily use demo tenant API keys for testing queries.
This script demonstrates how other scripts can pick up the saved API keys
without having to type them manually.

Usage:
    python scripts/demo-query-example.py "What is the meaning of life?"
    python scripts/demo-query-example.py --tenant "Demo Tenant 1" "How does AI work?"
"""

import argparse
import json
import requests
import sys
from typing import Optional

# Import our centralized configuration
from config import get_base_url, get_demo_api_keys

def make_tenant_request(method: str, endpoint: str, api_key: str, data: Optional[dict] = None) -> dict:
    """Make a request using a tenant API key."""
    url = f"{get_base_url()}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        sys.exit(1)

def query_with_tenant(tenant_name: str, query: str):
    """Send a query using a specific tenant's API key."""
    demo_keys = get_demo_api_keys()
    
    if not demo_keys:
        print("No demo tenant keys available. Run: python scripts/api-demo.py --setup-default")
        sys.exit(1)
    
    if tenant_name not in demo_keys:
        print(f"Tenant '{tenant_name}' not found. Available tenants:")
        for name in demo_keys.keys():
            print(f"  - {name}")
        sys.exit(1)
    
    api_key = demo_keys[tenant_name]
    print(f"🔍 Querying with {tenant_name}...")
    print(f"   API Key: {api_key[:8]}...{api_key[-8:]}")
    print(f"   Query: {query}")
    print()
    
    # Example query to the RAG endpoint (adjust endpoint as needed)
    query_data = {
        "query": query,
        "max_sources": 5,
        "confidence_threshold": 0.7
    }
    
    try:
        result = make_tenant_request("POST", "/queries", api_key, query_data)
        print("📝 Query Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"❌ Query failed: {e}")
        print("💡 This is expected if the query endpoint isn't implemented yet")

def main():
    parser = argparse.ArgumentParser(description="Demo Query Example")
    parser.add_argument("query", nargs="?", help="Query to send")
    parser.add_argument("--tenant", default="Demo Tenant 1", 
                       help="Tenant name to use for query (default: Demo Tenant 1)")
    parser.add_argument("--list-tenants", action="store_true", 
                       help="List available demo tenants and exit")
    
    args = parser.parse_args()
    
    if not args.list_tenants and not args.query:
        parser.error("Query is required unless --list-tenants is specified")
    
    if args.list_tenants:
        demo_keys = get_demo_api_keys()
        if demo_keys:
            print("🔑 Available Demo Tenants:")
            for tenant_name, api_key in demo_keys.items():
                print(f"  - {tenant_name} (key: {api_key[:8]}...{api_key[-8:]})")
        else:
            print("❌ No demo tenants available")
            print("💡 Run: python scripts/api-demo.py --setup-default")
        return
    
    query_with_tenant(args.tenant, args.query)

if __name__ == "__main__":
    main()