#!/usr/bin/env python3
"""
Get Admin API Key Script

This script extracts the admin API key from the backend Docker container.
It reads the .env file inside the container and displays the admin credentials.

Usage:
    python get-apikey.py
    python get-apikey.py --json
    python get-apikey.py --env
"""

import argparse
import json
import subprocess
import sys
import os
from typing import Dict, Optional

def run_docker_command(command: str) -> str:
    """Run a Docker command and return the output."""
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running Docker command: {e}")
        print(f"Command: {command}")
        print(f"Error output: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Docker is not installed or not in PATH")
        sys.exit(1)

def get_container_env() -> Dict[str, str]:
    """Get the .env file contents from the backend container."""
    print("Reading admin credentials from backend container...")
    
    # Check if container is running
    try:
        containers = run_docker_command("docker ps --filter name=rag_backend --format '{{.Names}}'")
        if not containers or 'rag_backend' not in containers:
            print("Error: Backend container 'rag_backend' is not running")
            print("Please start the backend with: docker-compose up backend -d")
            sys.exit(1)
    except Exception as e:
        print(f"Error checking container status: {e}")
        sys.exit(1)
    
    # Read .env file from container
    env_content = run_docker_command("docker exec -it rag_backend cat .env")
    
    # Parse .env file
    env_vars = {}
    for line in env_content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key] = value
    
    return env_vars

def display_credentials(env_vars: Dict[str, str], output_format: str = "text"):
    """Display the admin credentials in the specified format."""
    
    admin_tenant_id = env_vars.get('ADMIN_TENANT_ID', 'Not found')
    admin_api_key = env_vars.get('ADMIN_API_KEY', 'Not found')
    
    if output_format == "json":
        credentials = {
            "admin_tenant_id": admin_tenant_id,
            "admin_api_key": admin_api_key,
            "base_url": "http://localhost:8000/api/v1"
        }
        print(json.dumps(credentials, indent=2))
    
    elif output_format == "env":
        print(f"ADMIN_TENANT_ID={admin_tenant_id}")
        print(f"ADMIN_API_KEY={admin_api_key}")
        print("BASE_URL=http://localhost:8000/api/v1")
    
    else:  # text format
        print("=" * 60)
        print("🔑 ADMIN CREDENTIALS")
        print("=" * 60)
        print(f"Admin Tenant ID: {admin_tenant_id}")
        print(f"Admin API Key:   {admin_api_key}")
        print(f"Base URL:        http://localhost:8000/api/v1")
        print("=" * 60)
        print()
        print("📝 Usage Examples:")
        print("=" * 60)
        print("# Update your API scripts with this key:")
        print(f'ADMIN_API_KEY = "{admin_api_key}"')
        print()
        print("# Test with curl:")
        print(f'curl -X GET "http://localhost:8000/api/v1/admin/tenants" \\')
        print(f'  -H "Authorization: Bearer {admin_api_key}"')
        print()
        print("# Test with Python scripts:")
        print("python scripts/api-tenant.py --list")
        print("python scripts/api-system.py --status")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Get Admin API Key from Docker Container")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--env", action="store_true", help="Output in .env format")
    
    args = parser.parse_args()
    
    # Determine output format
    output_format = "text"
    if args.json:
        output_format = "json"
    elif args.env:
        output_format = "env"
    
    try:
        # Get environment variables from container
        env_vars = get_container_env()
        
        # Display credentials
        display_credentials(env_vars, output_format)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 