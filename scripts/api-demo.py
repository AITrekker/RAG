#!/usr/bin/env python3
"""
Demo Management Admin API Script

This script provides command-line access to demo management admin endpoints.
All operations require admin API key authentication.

Usage:
    python api-demo.py --setup --demo-tenants "tenant_1,tenant_2" --duration 24
    python api-demo.py --list
    python api-demo.py --cleanup
"""

import argparse
import json
import requests
import sys
from typing import List, Optional

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

def setup_demo_environment(demo_tenants: List[str], demo_duration_hours: int = 24, generate_api_keys: bool = True):
    """Setup demo environment with specified tenants."""
    data = {
        "demo_tenants": demo_tenants,
        "demo_duration_hours": demo_duration_hours,
        "generate_api_keys": generate_api_keys
    }
    
    result = make_request("POST", "/demo/setup", data=data)
    print("Demo environment setup:")
    print(json.dumps(result, indent=2))

def list_demo_tenants():
    """List all demo tenants."""
    result = make_request("GET", "/demo/tenants")
    print("Demo tenants:")
    print(json.dumps(result, indent=2))

def cleanup_demo_environment():
    """Cleanup demo environment."""
    result = make_request("DELETE", "/demo/cleanup")
    print("Demo environment cleanup:")
    print(json.dumps(result, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Demo Management Admin API")
    parser.add_argument("--setup", action="store_true", help="Setup demo environment")
    parser.add_argument("--list", action="store_true", help="List demo tenants")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup demo environment")
    
    # Setup parameters
    parser.add_argument("--demo-tenants", help="Comma-separated list of demo tenant IDs")
    parser.add_argument("--duration", type=int, default=24, help="Demo duration in hours")
    parser.add_argument("--generate-api-keys", action="store_true", default=True, help="Generate API keys for demo tenants")
    parser.add_argument("--no-api-keys", action="store_true", help="Don't generate API keys")
    
    args = parser.parse_args()
    
    if ADMIN_API_KEY == "YOUR_ADMIN_API_KEY_HERE":
        print("ERROR: Please update ADMIN_API_KEY in the script with your actual admin API key")
        sys.exit(1)
    
    if args.setup:
        if not args.demo_tenants:
            print("ERROR: --demo-tenants is required for setting up demo environment")
            sys.exit(1)
        
        demo_tenants = [tenant.strip() for tenant in args.demo_tenants.split(",")]
        generate_api_keys = not args.no_api_keys
        
        setup_demo_environment(demo_tenants, args.duration, generate_api_keys)
    elif args.list:
        list_demo_tenants()
    elif args.cleanup:
        cleanup_demo_environment()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 