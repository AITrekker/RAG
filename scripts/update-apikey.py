#!/usr/bin/env python3
"""
Update API Key Script

This script helps you update the admin API key in the .env file.
It can get the key from Docker logs or let you set it manually.

Usage:
    python update-apikey.py --from-docker    # Get from Docker logs
    python update-apikey.py --key "new_key"  # Set manually
    python update-apikey.py --show           # Show current key
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

def get_api_key_from_docker():
    """Extract API key from Docker container logs."""
    try:
        result = subprocess.run(
            ['docker', 'logs', 'rag_backend'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Look for the API key in logs
        pattern = r'Admin API Key:\s+([a-fA-F0-9]{64})'
        match = re.search(pattern, result.stdout)
        
        if match:
            return match.group(1)
        else:
            print("❌ API key not found in Docker logs")
            print("💡 Try restarting the backend: docker-compose restart backend")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error reading Docker logs: {e}")
        return None
    except FileNotFoundError:
        print("❌ Docker not found. Make sure Docker is installed and running.")
        return None

def update_env_file(api_key: str):
    """Update the .env file with the new API key."""
    project_root = Path(__file__).parent.parent
    env_file = project_root / '.env'
    
    if not env_file.exists():
        print(f"❌ .env file not found at {env_file}")
        return False
    
    # Read current content
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Update or add the API key
    if 'ADMIN_API_KEY=' in content:
        # Replace existing key
        content = re.sub(r'ADMIN_API_KEY=.*', f'ADMIN_API_KEY={api_key}', content)
    else:
        # Add new key
        content += f'\nADMIN_API_KEY={api_key}\n'
    
    # Write back to file
    with open(env_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated .env file with new API key")
    print(f"   Key: {api_key[:8]}...{api_key[-8:]}")
    return True

def show_current_key():
    """Show the current API key from .env file."""
    project_root = Path(__file__).parent.parent
    env_file = project_root / '.env'
    
    if not env_file.exists():
        print(f"❌ .env file not found at {env_file}")
        return
    
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip().startswith('ADMIN_API_KEY='):
                api_key = line.strip().split('=', 1)[1]
                if api_key:
                    print(f"🔑 Current API Key: {api_key[:8]}...{api_key[-8:]}")
                    print(f"    Full key: {api_key}")
                else:
                    print("❌ API key is empty in .env file")
                return
    
    print("❌ ADMIN_API_KEY not found in .env file")

def main():
    parser = argparse.ArgumentParser(description="Update Admin API Key")
    parser.add_argument("--from-docker", action="store_true", 
                       help="Get API key from Docker container logs")
    parser.add_argument("--key", type=str, 
                       help="Set API key manually")
    parser.add_argument("--show", action="store_true",
                       help="Show current API key")
    
    args = parser.parse_args()
    
    if args.show:
        show_current_key()
    elif args.from_docker:
        api_key = get_api_key_from_docker()
        if api_key:
            update_env_file(api_key)
        else:
            sys.exit(1)
    elif args.key:
        if len(args.key) != 64 or not re.match(r'^[a-fA-F0-9]+$', args.key):
            print("❌ Invalid API key format. Expected 64 hex characters.")
            sys.exit(1)
        update_env_file(args.key)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()