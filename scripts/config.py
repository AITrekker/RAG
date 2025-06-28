#!/usr/bin/env python3
"""
Centralized Configuration for API Scripts

This module provides centralized configuration management for all API scripts.
The admin API key is automatically loaded from:
1. Environment variable ADMIN_API_KEY
2. .env file ADMIN_API_KEY
3. Docker container .env file (if running in Docker)

Usage:
    from config import get_admin_api_key, get_base_url
    
    api_key = get_admin_api_key()
    base_url = get_base_url()
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from typing import Optional

def load_env_file(file_path: str) -> dict:
    """Load environment variables from a .env file."""
    env_vars = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

def get_admin_api_key() -> str:
    """
    Get the admin API key from various sources in order of priority:
    1. Environment variable ADMIN_API_KEY
    2. .env file in project root
    3. Docker container .env file
    """
    # 1. Check environment variable
    api_key = os.getenv('ADMIN_API_KEY')
    if api_key:
        return api_key
    
    # 2. Check .env file in project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / '.env'
    env_vars = load_env_file(str(env_file))
    api_key = env_vars.get('ADMIN_API_KEY')
    if api_key:
        return api_key
    
    # 3. Try to get from Docker container
    try:
        result = subprocess.run(
            ['docker', 'exec', 'rag_backend', 'cat', '.env'],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('ADMIN_API_KEY='):
                api_key = line.split('=', 1)[1]
                if api_key:
                    return api_key
                    
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # 4. If all else fails, show helpful error
    print("❌ ERROR: Admin API key not found!")
    print()
    print("💡 Solutions:")
    print("1. Run: python scripts/get-apikey.py")
    print("2. Set environment variable: export ADMIN_API_KEY='your_key'")
    print("3. Add to .env file: ADMIN_API_KEY=your_key")
    print("4. Ensure Docker backend is running: docker-compose up -d backend")
    sys.exit(1)

def get_base_url() -> str:
    """Get the base URL for API requests."""
    return os.getenv('BASE_URL', 'http://localhost:8000/api/v1')

def get_admin_base_url() -> str:
    """Get the admin base URL for API requests."""
    return f"{get_base_url()}/admin"

def get_demo_api_keys() -> dict:
    """
    Load demo tenant API keys from the demo_tenant_keys.json file.
    
    Returns:
        dict: Dictionary mapping tenant names to API keys
    """
    project_root = Path(__file__).parent.parent
    keys_file = project_root / 'demo_tenant_keys.json'
    
    if not keys_file.exists():
        print("❌ Demo tenant keys file not found!")
        print("💡 Run: python scripts/api-demo.py --setup-default")
        return {}
    
    try:
        with open(keys_file, 'r') as f:
            keys = json.load(f)
        return keys
    except Exception as e:
        print(f"❌ Error loading demo keys: {e}")
        return {}

def print_demo_keys():
    """Print available demo tenant API keys."""
    keys = get_demo_api_keys()
    if keys:
        print("🔑 Available Demo Tenant API Keys:")
        for tenant_name, api_key in keys.items():
            print(f"  {tenant_name}: {api_key[:8]}...{api_key[-8:]}")
    else:
        print("❌ No demo tenant keys available")

def print_config_info():
    """Print current configuration for debugging."""
    try:
        api_key = get_admin_api_key()
        print("✅ Configuration loaded successfully:")
        print(f"   Admin API Key: {api_key[:8]}...{api_key[-8:] if len(api_key) > 16 else api_key}")
        print(f"   Base URL: {get_base_url()}")
        print()
        print_demo_keys()
    except SystemExit:
        print("❌ Configuration failed to load")

if __name__ == "__main__":
    print_config_info()