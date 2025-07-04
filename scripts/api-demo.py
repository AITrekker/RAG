#!/usr/bin/env python3
"""
Demo Management Admin API Script

This script provides command-line access to demo management admin endpoints.
All operations require admin API key authentication.

Usage:
    python api-demo.py --setup-default                                         # Setup tenant1, tenant2, tenant3
    python api-demo.py --setup --demo-tenants "tenant_1,tenant_2" --duration 24
    python api-demo.py --list
    python api-demo.py --cleanup
"""

import argparse
import json
import os
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

def save_api_keys(api_keys: dict):
    """Save API keys to a JSON file."""
    # Save to project root directory
    project_root = os.path.dirname(os.path.dirname(__file__))
    keys_file = os.path.join(project_root, "demo_tenant_keys.json")
    
    try:
        with open(keys_file, 'w') as f:
            json.dump(api_keys, f, indent=2)
        print(f"\nAPI keys saved to {keys_file}")
        print("Use these keys in other scripts to interact with the tenants:")
        for tenant, key in api_keys.items():
            print(f"  {tenant}: {key}")
    except Exception as e:
        print(f"Error saving API keys: {e}")

def create_tenant_via_api(name: str, description: str = "") -> str:
    """Create a new tenant using the admin API."""
    create_data = {
        "name": name,
        "description": description,
        "auto_sync": True,
        "sync_interval": 60
    }
    
    try:
        result = make_request("POST", "/tenants", data=create_data)
        tenant_id = result["id"]
        print(f"Created tenant: {name} (ID: {tenant_id})")
        return tenant_id
    except Exception as e:
        print(f"Failed to create tenant {name}: {e}")
        raise

def create_data_folder_tenants():
    """Create tenants that match the /data/uploads folder structure using API."""
    print("Creating tenants to match /data/uploads folder structure...")
    
    # First, get list of existing tenants to avoid duplicates
    print("Checking for existing tenants...")
    try:
        existing_tenants_result = make_request("GET", "/tenants")
        existing_tenant_names = {tenant["name"]: tenant["id"] for tenant in existing_tenants_result.get("tenants", [])}
    except Exception as e:
        print(f"⚠️  Could not retrieve existing tenants: {e}")
        existing_tenant_names = {}
    
    # Create tenants with names that match the uploads folders
    tenant_configs = [
        {"name": "tenant1", "description": "GlobalCorp Inc. - Global industry leader"},
        {"name": "tenant2", "description": "Regional Solutions - Local community partner"},
        {"name": "tenant3", "description": "Small Startup - Fiery new tech innovator"},
    ]
    
    tenant_ids = []
    for config in tenant_configs:
        tenant_name = config['name']
        
        # Check if tenant already exists
        if tenant_name in existing_tenant_names:
            tenant_id = existing_tenant_names[tenant_name]
            tenant_ids.append(tenant_id)
            print(f"  ✅ Tenant {tenant_name} already exists with ID: {tenant_id}")
            continue
        
        # Create new tenant via API
        print(f"Creating new tenant: {tenant_name}")
        try:
            tenant_id = create_tenant_via_api(tenant_name, config["description"])
            tenant_ids.append(tenant_id)
            print(f"  ✅ Created {tenant_name} with ID: {tenant_id}")
        except Exception as e:
            print(f"  ❌ Failed to create {tenant_name}: {e}")
            # Don't add to tenant_ids if creation failed
    
    return tenant_ids

def setup_default_tenants():
    """Setup default demo environment by creating tenants first, then setting up demo."""
    print("Setting up demo environment for uploads folder tenants...")
    
    # First create the tenants to match uploads folder structure
    tenant_ids = create_data_folder_tenants()
    
    if not tenant_ids:
        print("❌ No tenants were created or found!")
        return {"success": False, "message": "Failed to create tenants"}
    
    print(f"\n🎯 Setting up demo environment for {len(tenant_ids)} tenants...")
    return setup_demo_environment(tenant_ids, demo_duration_hours=24, generate_api_keys=True)

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
    
    # Save API keys to file if they were generated
    if generate_api_keys and result.get("demo_tenants"):
        api_keys = {}
        for demo_tenant in result["demo_tenants"]:
            tenant_name = demo_tenant["tenant_name"]
            if demo_tenant.get("api_keys"):
                api_keys[tenant_name] = demo_tenant["api_keys"][0]["api_key"]
        
        if api_keys:
            save_api_keys(api_keys)
    
    return result

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
    
    # Also remove the demo_tenant_keys.json file
    project_root = os.path.dirname(os.path.dirname(__file__))
    keys_file = os.path.join(project_root, "demo_tenant_keys.json")
    if os.path.exists(keys_file):
        try:
            os.remove(keys_file)
            print(f"\n✅ Removed {keys_file}")
        except Exception as e:
            print(f"⚠️  Could not remove {keys_file}: {e}")
    else:
        print(f"\nℹ️  {keys_file} not found (already removed or never created)")

def main():
    parser = argparse.ArgumentParser(description="Demo Management Admin API")
    parser.add_argument("--setup-default", action="store_true", help="Setup default demo environment (tenant1, tenant2, tenant3)")
    parser.add_argument("--setup", action="store_true", help="Setup custom demo environment")
    parser.add_argument("--list", action="store_true", help="List demo tenants")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup demo environment")
    
    # Setup parameters
    parser.add_argument("--demo-tenants", help="Comma-separated list of tenant IDs for demo")
    parser.add_argument("--duration", type=int, default=24, help="Demo duration in hours")
    parser.add_argument("--generate-api-keys", action="store_true", default=True, help="Generate API keys for demo tenants")
    
    args = parser.parse_args()
    
    # API key validation is handled by config.py
    
    if args.setup_default:
        setup_default_tenants()
    elif args.setup:
        if not args.demo_tenants:
            print("ERROR: --demo-tenants is required for custom setup")
            sys.exit(1)
        
        tenant_ids = [tid.strip() for tid in args.demo_tenants.split(",")]
        setup_demo_environment(tenant_ids, args.duration, args.generate_api_keys)
    elif args.list:
        list_demo_tenants()
    elif args.cleanup:
        cleanup_demo_environment()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 