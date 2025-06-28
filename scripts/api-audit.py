#!/usr/bin/env python3
"""
Audit Events Admin API Script

This script provides command-line access to audit events admin endpoints.
All operations require admin API key authentication.

Usage:
    python api-audit.py --list
    python api-audit.py --list --tenant-id "tenant_123"
    python api-audit.py --list --limit 50 --offset 10
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

def list_audit_events(tenant_id: Optional[str] = None, limit: int = 100, offset: int = 0):
    """List audit events with optional filtering."""
    params = {
        "limit": limit,
        "offset": offset
    }
    
    if tenant_id:
        params["tenant_id"] = tenant_id
    
    result = make_request("GET", "/audit/events", params=params)
    print("Audit Events:")
    print(json.dumps(result, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Audit Events Admin API")
    parser.add_argument("--list", action="store_true", help="List audit events")
    
    # Filter parameters
    parser.add_argument("--tenant-id", help="Filter by tenant ID")
    parser.add_argument("--limit", type=int, default=100, help="Number of events to return (max 100)")
    parser.add_argument("--offset", type=int, default=0, help="Number of events to skip")
    
    args = parser.parse_args()
    
    if ADMIN_API_KEY == "YOUR_ADMIN_API_KEY_HERE":
        print("ERROR: Please update ADMIN_API_KEY in the script with your actual admin API key")
        sys.exit(1)
    
    if args.list:
        list_audit_events(args.tenant_id, args.limit, args.offset)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 