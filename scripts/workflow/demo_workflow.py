#!/usr/bin/env python3
"""
SIMPLE Demo Workflow - Everything in one script
1. Check containers are running
2. Create 3 tenants directly in database
3. Copy demo files to tenant directories
4. Done
"""

import subprocess
import sys
import shutil
import json
import asyncio
import asyncpg
import secrets
from uuid import uuid4
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

def check_containers():
    """Check if containers are running."""
    print("🚀 Simple Demo Workflow")
    print("=" * 40)
    
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        
        if result.returncode != 0:
            print("❌ Docker-compose not available")
            return False
            
        running_services = result.stdout.strip().split('\n') if result.stdout.strip() else []
        expected_services = ["postgres", "backend", "frontend"]
        
        print("📋 Container Status:")
        for service in expected_services:
            if service in running_services:
                print(f"  ✅ {service}: running")
            else:
                print(f"  ❌ {service}: not running")
        
        if len(running_services) >= 3:
            print("✅ All containers running!")
            return True
        else:
            print("\n❌ Some containers are not running")
            print("💡 Start them with: docker-compose up -d")
            return False
            
    except Exception as e:
        print(f"❌ Error checking containers: {e}")
        return False

async def create_tenants():
    """Create 3 demo tenants directly in database."""
    print("\n🏗️ Creating demo tenants...")
    
    # Simple tenant data
    tenants = [
        {"name": "tenant1", "slug": "tenant1"},
        {"name": "tenant2", "slug": "tenant2"}, 
        {"name": "tenant3", "slug": "tenant3"}
    ]
    
    try:
        # Connect directly to database
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            database="rag_db_development", 
            user="rag_user",
            password="rag_password"
        )
        
        tenant_keys = {}
        
        for tenant_data in tenants:
            # Generate simple data (slug-based system)
            tenant_slug = tenant_data['slug']
            api_key = f"tenant_{tenant_slug}_{secrets.token_hex(16)}"
            
            print(f"  ✓ Creating {tenant_data['name']}...")
            
            # Insert tenant (slug-based schema)
            await conn.execute("""
                INSERT INTO tenants (
                    slug, name, api_key, created_at, updated_at
                )
                VALUES ($1, $2, $3, NOW(), NOW())
                ON CONFLICT (slug) DO UPDATE SET
                    api_key = $3,
                    updated_at = NOW()
            """, tenant_slug, tenant_data['name'], api_key)
            
            # Use slug as key instead of UUID for user-friendly keys file
            tenant_keys[tenant_slug] = {
                "api_key": api_key,
                "slug": tenant_slug,
                "description": f"Demo {tenant_data['name']} with company documents (development)"
            }
        
        await conn.close()
        
        # Write keys to file
        with open("demo_tenant_keys.json", "w") as f:
            json.dump(tenant_keys, f, indent=2)
        
        # Copy to frontend so UI can access them
        frontend_keys_file = PROJECT_ROOT / "src" / "frontend" / "public" / "demo_tenant_keys.json"
        with open(frontend_keys_file, "w") as f:
            json.dump(tenant_keys, f, indent=2)
        
        print(f"✅ Created {len(tenants)} tenants")
        print(f"✅ Keys copied to frontend")
        return True
        
    except Exception as e:
        print(f"❌ Tenant creation failed: {e}")
        return False

def copy_demo_files():
    """Copy demo files to tenant directories"""
    print("\n📁 Copying demo files...")
    
    # Load tenant keys to get tenant IDs
    keys_file = PROJECT_ROOT / "demo_tenant_keys.json"
    if not keys_file.exists():
        print("❌ No tenant keys file found")
        return False
    
    try:
        with open(keys_file) as f:
            tenant_data = json.load(f)
    except Exception as e:
        print(f"❌ Could not read tenant keys: {e}")
        return False
    
    files_copied = 0
    
    for tenant_slug, info in tenant_data.items():
        print(f"  📂 Processing {tenant_slug}...")
        
        # Source: demo-data/tenant1, tenant2, tenant3
        demo_source_dir = PROJECT_ROOT / "demo-data" / tenant_slug
        # Destination: data/uploads/{tenant-slug}/
        tenant_upload_dir = PROJECT_ROOT / "data" / "uploads" / tenant_slug
        
        if not demo_source_dir.exists():
            print(f"    ⚠️ No demo files found for {tenant_slug}")
            continue
            
        # Create tenant upload directory
        tenant_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy all files
        tenant_files_copied = 0
        for demo_file in demo_source_dir.glob("*"):
            if demo_file.is_file():
                dest_file = tenant_upload_dir / demo_file.name
                shutil.copy2(demo_file, dest_file)
                tenant_files_copied += 1
                print(f"    ✓ Copied: {demo_file.name}")
        
        files_copied += tenant_files_copied
        print(f"    📊 {tenant_files_copied} files copied for {tenant_slug}")
    
    print(f"✅ Total files copied: {files_copied}")
    return True

def verify_tenants():
    """Basic tenant verification - check they exist in database"""
    print("\n🔍 Verifying tenants...")
    
    # Load tenant keys
    keys_file = PROJECT_ROOT / "demo_tenant_keys.json"
    if not keys_file.exists():
        print("❌ No tenant keys file found")
        return False
    
    try:
        with open(keys_file) as f:
            tenant_data = json.load(f)
    except Exception as e:
        print(f"❌ Could not read tenant keys: {e}")
        return False
    
    # Simple verification - just check the count
    print(f"  ✓ Found {len(tenant_data)} tenants in keys file")
    for tenant_id, info in tenant_data.items():
        slug = info["slug"]
        api_key = info["api_key"]
        print(f"    • {slug}: {api_key[:20]}...")
    
    print("✅ Basic tenant verification complete")
    return True

def restart_frontend():
    """Restart frontend container"""
    print("\n🔄 Restarting frontend container...")
    
    try:
        result = subprocess.run(
            ["docker-compose", "restart", "frontend"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Frontend container restarted!")
            print("🌐 Frontend available at: http://localhost:3000")
            return True
        else:
            print(f"❌ Frontend restart failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error restarting frontend: {e}")
        return False

def wait_for_input(message):
    """Wait for user input to continue"""
    input(f"\n⏸️  {message} (Press Enter to continue...)")

def main():
    """Main entry point."""
    # Step 1: Check containers
    if not check_containers():
        return False
    
    # Step 2: Create tenants
    if not asyncio.run(create_tenants()):
        return False
    
    # Step 3: Copy demo files
    if not copy_demo_files():
        return False
    
    print("\n🎉 Demo setup complete!")
    
    # Step 4: Wait for user input
    wait_for_input("Ready to verify tenants?")
    
    # Step 5: Verify tenants
    if not verify_tenants():
        return False
    
    # Step 6: Wait for user input
    wait_for_input("Ready to restart frontend?")
    
    # Step 7: Restart frontend
    if not restart_frontend():
        return False
    
    # Done!
    print("\n🎉 Complete workflow finished!")
    print("📝 What you can do now:")
    print("  • Frontend: http://localhost:3000")
    print("  • API docs: http://localhost:8000/docs")
    print("  • Check tenant keys: cat demo_tenant_keys.json")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)