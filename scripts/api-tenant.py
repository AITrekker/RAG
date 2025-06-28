#!/usr/bin/env python3
"""
Tenant Management Admin API Script

This script provides command-line access to tenant management admin endpoints.
All operations require admin API key authentication.

Usage:
    python api-tenant.py --list
    python api-tenant.py --create --name "New Company" --description "New tenant"
    python api-tenant.py --get --tenant-id "tenant_123"
    python api-tenant.py --update --tenant-id "tenant_123" --name "Updated Name"
    python api-tenant.py --delete --tenant-id "tenant_123"
    python api-tenant.py --create-key --tenant-id "tenant_123" --key-name "Production Key"
    python api-tenant.py --list-keys --tenant-id "tenant_123"
    python api-tenant.py --delete-key --tenant-id "tenant_123" --key-id "key_456"
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

def list_tenants(page: int = 1, page_size: int = 20, include_api_keys: bool = False, demo_only: bool = False):
    """List all tenants."""
    params = {
        "page": page,
        "page_size": page_size,
        "include_api_keys": include_api_keys,
        "demo_only": demo_only
    }
    
    result = make_request("GET", "/tenants", params=params)
    print("Tenants:")
    print(json.dumps(result, indent=2))

def create_tenant(name: str, description: str = "", auto_sync: bool = True, sync_interval: int = 60):
    """Create a new tenant."""
    data = {
        "name": name,
        "description": description,
        "auto_sync": auto_sync,
        "sync_interval": sync_interval
    }
    
    result = make_request("POST", "/tenants", data=data)
    print("Created tenant:")
    print(json.dumps(result, indent=2))
    return result

def get_tenant(tenant_id: str):
    """Get tenant details."""
    result = make_request("GET", f"/tenants/{tenant_id}")
    print("Tenant details:")
    print(json.dumps(result, indent=2))

def update_tenant(tenant_id: str, name: Optional[str] = None, description: Optional[str] = None, 
                 auto_sync: Optional[bool] = None, sync_interval: Optional[int] = None):
    """Update tenant details."""
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if auto_sync is not None:
        data["auto_sync"] = auto_sync
    if sync_interval is not None:
        data["sync_interval"] = sync_interval
    
    if not data:
        print("No update data provided")
        return
    
    result = make_request("PUT", f"/tenants/{tenant_id}", data=data)
    print("Updated tenant:")
    print(json.dumps(result, indent=2))

def delete_tenant(tenant_id: str):
    """Delete a tenant."""
    result = make_request("DELETE", f"/tenants/{tenant_id}")
    print(f"Tenant {tenant_id} deleted successfully")

def create_api_key(tenant_id: str, name: str, description: str = ""):
    """Create API key for tenant."""
    data = {
        "name": name,
        "description": description
    }
    
    result = make_request("POST", f"/tenants/{tenant_id}/api-keys", data=data)
    print("Created API key:")
    print(json.dumps(result, indent=2))

def list_api_keys(tenant_id: str):
    """List API keys for tenant."""
    result = make_request("GET", f"/tenants/{tenant_id}/api-keys")
    print("API keys:")
    print(json.dumps(result, indent=2))

def delete_api_key(tenant_id: str, key_id: str):
    """Delete API key for tenant."""
    result = make_request("DELETE", f"/tenants/{tenant_id}/api-keys/{key_id}")
    print(f"API key {key_id} deleted successfully")

def main():
    parser = argparse.ArgumentParser(description="Tenant Management Admin API")
    parser.add_argument("--list", action="store_true", help="List all tenants")
    parser.add_argument("--create", action="store_true", help="Create a new tenant")
    parser.add_argument("--get", action="store_true", help="Get tenant details")
    parser.add_argument("--update", action="store_true", help="Update tenant")
    parser.add_argument("--delete", action="store_true", help="Delete tenant")
    parser.add_argument("--create-key", action="store_true", help="Create API key for tenant")
    parser.add_argument("--list-keys", action="store_true", help="List API keys for tenant")
    parser.add_argument("--delete-key", action="store_true", help="Delete API key for tenant")
    
    # Tenant parameters
    parser.add_argument("--tenant-id", help="Tenant ID")
    parser.add_argument("--name", help="Tenant name")
    parser.add_argument("--description", help="Tenant description")
    parser.add_argument("--auto-sync", type=bool, help="Auto sync enabled")
    parser.add_argument("--sync-interval", type=int, help="Sync interval in seconds")
    
    # API key parameters
    parser.add_argument("--key-name", help="API key name")
    parser.add_argument("--key-id", help="API key ID")
    
    # List parameters
    parser.add_argument("--page", type=int, default=1, help="Page number")
    parser.add_argument("--page-size", type=int, default=20, help="Page size")
    parser.add_argument("--include-api-keys", action="store_true", help="Include API keys in response")
    parser.add_argument("--demo-only", action="store_true", help="Show only demo tenants")
    
    args = parser.parse_args()
    
    # API key validation is handled by config.py
    
    if args.list:
        list_tenants(args.page, args.page_size, args.include_api_keys, args.demo_only)
    elif args.create:
        if not args.name:
            print("ERROR: --name is required for creating a tenant")
            sys.exit(1)
        create_tenant(args.name, args.description or "", 
                     True if args.auto_sync is None else args.auto_sync, 
                     60 if args.sync_interval is None else args.sync_interval)
    elif args.get:
        if not args.tenant_id:
            print("ERROR: --tenant-id is required for getting tenant details")
            sys.exit(1)
        get_tenant(args.tenant_id)
    elif args.update:
        if not args.tenant_id:
            print("ERROR: --tenant-id is required for updating tenant")
            sys.exit(1)
        update_tenant(args.tenant_id, args.name, args.description, args.auto_sync, args.sync_interval)
    elif args.delete:
        if not args.tenant_id:
            print("ERROR: --tenant-id is required for deleting tenant")
            sys.exit(1)
        delete_tenant(args.tenant_id)
    elif args.create_key:
        if not args.tenant_id or not args.key_name:
            print("ERROR: --tenant-id and --key-name are required for creating API key")
            sys.exit(1)
        create_api_key(args.tenant_id, args.key_name, args.description or "")
    elif args.list_keys:
        if not args.tenant_id:
            print("ERROR: --tenant-id is required for listing API keys")
            sys.exit(1)
        list_api_keys(args.tenant_id)
    elif args.delete_key:
        if not args.tenant_id or not args.key_id:
            print("ERROR: --tenant-id and --key-id are required for deleting API key")
            sys.exit(1)
        delete_api_key(args.tenant_id, args.key_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 