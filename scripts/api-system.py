#!/usr/bin/env python3
"""
System Monitoring & Maintenance Admin API Script

This script provides command-line access to system monitoring and maintenance admin endpoints.
All operations require admin API key authentication.

Usage:
    python api-system.py --status
    python api-system.py --metrics
    python api-system.py --clear-embeddings-stats
    python api-system.py --clear-llm-stats
    python api-system.py --clear-llm-cache
    python api-system.py --maintenance
"""

import argparse
import json
import requests
import sys
from typing import Optional

# Import centralized configuration
from config import get_admin_api_key, get_admin_base_url

# Configuration loaded automatically from .env or environment
ADMIN_API_KEY = get_admin_api_key()
BASE_URL = get_admin_base_url()

def make_request(method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    """Make HTTP request to the API."""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {ADMIN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        sys.exit(1)

def get_system_status():
    """Get system status."""
    result = make_request("GET", "/system/status")
    print("System Status:")
    print(json.dumps(result, indent=2))

def get_system_metrics():
    """Get system metrics."""
    result = make_request("GET", "/system/metrics")
    print("System Metrics:")
    print(json.dumps(result, indent=2))

def clear_embedding_statistics():
    """Clear embedding statistics."""
    result = make_request("DELETE", "/system/embeddings/stats")
    print("Embedding statistics cleared:")
    print(json.dumps(result, indent=2))

def clear_llm_statistics():
    """Clear LLM statistics."""
    result = make_request("DELETE", "/system/llm/stats")
    print("LLM statistics cleared:")
    print(json.dumps(result, indent=2))

def clear_llm_cache():
    """Clear LLM cache."""
    result = make_request("DELETE", "/system/llm/cache")
    print("LLM cache cleared:")
    print(json.dumps(result, indent=2))

def trigger_maintenance_mode():
    """Trigger maintenance mode."""
    result = make_request("PUT", "/system/maintenance", {"enabled": True})
    print("Maintenance mode triggered:")
    print(json.dumps(result, indent=2))

def main():
    parser = argparse.ArgumentParser(description="System Monitoring & Maintenance Admin API")
    parser.add_argument("--status", action="store_true", help="Get system status")
    parser.add_argument("--metrics", action="store_true", help="Get system metrics")
    parser.add_argument("--clear-embeddings-stats", action="store_true", help="Clear embedding statistics")
    parser.add_argument("--clear-llm-stats", action="store_true", help="Clear LLM statistics")
    parser.add_argument("--clear-llm-cache", action="store_true", help="Clear LLM cache")
    parser.add_argument("--maintenance", action="store_true", help="Trigger maintenance mode")
    
    args = parser.parse_args()
    
    # API key validation is handled by config.py
    
    if args.status:
        get_system_status()
    elif args.metrics:
        get_system_metrics()
    elif args.clear_embeddings_stats:
        clear_embedding_statistics()
    elif args.clear_llm_stats:
        clear_llm_statistics()
    elif args.clear_llm_cache:
        clear_llm_cache()
    elif args.maintenance:
        trigger_maintenance_mode()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 