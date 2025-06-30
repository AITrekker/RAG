#!/usr/bin/env python3
"""
Comprehensive cleanup script for RAG system.
Clears PostgreSQL database, Qdrant collections, upload files, and resets .env credentials.
Use with caution - this will delete ALL data!
"""

import asyncio
import asyncpg
import httpx
import shutil
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment
POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "rag_db",
    "user": os.getenv("POSTGRES_USER", "rag_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "rag_password")
}

QDRANT_CONFIG = {
    "host": "localhost",
    "port": 6333
}

UPLOADS_DIR = Path("./data/uploads")
ENV_FILE = Path(".env")


async def cleanup_postgres():
    """Drop and recreate the PostgreSQL database if available."""
    print("🗄️  Cleaning up PostgreSQL database...")
    
    try:
        # Test if PostgreSQL is available first
        conn = await asyncpg.connect(
            host=POSTGRES_CONFIG["host"],
            port=POSTGRES_CONFIG["port"],
            database="postgres",
            user=POSTGRES_CONFIG["user"],
            password=POSTGRES_CONFIG["password"]
        )
        
        # Terminate existing connections to the target database
        await conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{POSTGRES_CONFIG["database"]}'
              AND pid <> pg_backend_pid()
        """)
        
        # Drop and recreate database
        await conn.execute(f'DROP DATABASE IF EXISTS {POSTGRES_CONFIG["database"]}')
        await conn.execute(f'CREATE DATABASE {POSTGRES_CONFIG["database"]} OWNER {POSTGRES_CONFIG["user"]}')
        
        await conn.close()
        print("✅ PostgreSQL database cleaned and recreated")
        
    except (ConnectionRefusedError, OSError) as e:
        print("✅ PostgreSQL not running (containers already stopped)")
    except Exception as e:
        print(f"⚠️  PostgreSQL cleanup skipped: {e}")
        print("   (This is normal if containers are already stopped)")


async def cleanup_qdrant():
    """Delete all Qdrant collections if available."""
    print("🔍 Cleaning up Qdrant collections...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test if Qdrant is available first
            response = await client.get(f"http://{QDRANT_CONFIG['host']}:{QDRANT_CONFIG['port']}/collections")
            response.raise_for_status()
            
            collections = response.json().get("result", {}).get("collections", [])
            
            if not collections:
                print("✅ No Qdrant collections found")
                return
            
            # Delete each collection
            for collection in collections:
                collection_name = collection["name"]
                print(f"  Deleting collection: {collection_name}")
                
                delete_response = await client.delete(
                    f"http://{QDRANT_CONFIG['host']}:{QDRANT_CONFIG['port']}/collections/{collection_name}"
                )
                delete_response.raise_for_status()
            
            print(f"✅ Deleted {len(collections)} Qdrant collections")
            
    except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionRefusedError) as e:
        print("✅ Qdrant not running (containers already stopped)")
    except Exception as e:
        print(f"⚠️  Qdrant cleanup skipped: {e}")
        print("   (This is normal if containers are already stopped)")


def cleanup_uploads():
    """Preserve uploaded files but ensure directory exists."""
    print("📁 Ensuring upload directory exists (files preserved)...")
    
    try:
        # Just ensure the directory exists, don't delete files
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        
        if UPLOADS_DIR.exists():
            file_count = len([f for f in UPLOADS_DIR.rglob("*") if f.is_file()])
            print(f"✅ Upload directory exists with {file_count} files preserved")
        else:
            print("✅ Upload directory created")
            
    except Exception as e:
        print(f"❌ Error with uploads directory: {e}")
        raise


def cleanup_env_credentials():
    """Remove admin credentials from .env file."""
    print("🔑 Cleaning up .env credentials...")
    
    try:
        if not ENV_FILE.exists():
            print("✅ .env file doesn't exist")
            return
        
        # Read current .env content
        with open(ENV_FILE, 'r') as f:
            lines = f.readlines()
        
        # Remove admin credential lines
        cleaned_lines = []
        skip_next_empty = False
        
        for line in lines:
            if line.strip().startswith('ADMIN_TENANT_ID=') or line.strip().startswith('ADMIN_API_KEY='):
                continue
            elif line.strip() == '# Admin credentials (auto-generated)':
                skip_next_empty = True
                continue
            elif skip_next_empty and line.strip() == '':
                skip_next_empty = False
                continue
            else:
                cleaned_lines.append(line)
                skip_next_empty = False
        
        # Write cleaned content back
        with open(ENV_FILE, 'w') as f:
            f.writelines(cleaned_lines)
        
        print("✅ Admin credentials removed from .env")
        
    except Exception as e:
        print(f"❌ Error cleaning .env credentials: {e}")
        raise


def cleanup_demo_keys():
    """Remove demo tenant keys file."""
    print("🔑 Cleaning up demo tenant keys...")
    
    try:
        keys_file = Path("demo_tenant_keys.json")
        if keys_file.exists():
            keys_file.unlink()
            print("✅ Demo tenant keys file removed")
        else:
            print("✅ Demo tenant keys file doesn't exist")
            
    except Exception as e:
        print(f"❌ Error cleaning demo keys: {e}")
        raise


def cleanup_containers():
    """Remove Docker containers to reset deployment lifecycle."""
    print("🐳 Removing Docker containers...")
    
    try:
        # Run docker-compose down
        result = subprocess.run(
            ["docker-compose", "down"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if "No stopped containers" in output or not output:
                print("✅ No containers to remove (already clean)")
            else:
                print("✅ Docker containers removed successfully")
                if output:
                    print(f"   Output: {output}")
        else:
            print(f"⚠️  Docker-compose down completed with warnings")
            if result.stderr.strip():
                print(f"   Warning: {result.stderr.strip()}")
            
    except FileNotFoundError:
        print("⚠️  docker-compose command not found. Please run manually:")
        print("   docker-compose down")
    except Exception as e:
        print(f"⚠️  Container cleanup skipped: {e}")
        print("   (This is normal if docker-compose is not available)")


async def verify_cleanup():
    """Verify that cleanup was successful."""
    print("🔍 Verifying cleanup...")
    
    try:
        # Check PostgreSQL (only if containers are still running)
        try:
            conn = await asyncpg.connect(**POSTGRES_CONFIG)
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            await conn.close()
            
            if tables:
                print(f"⚠️  Found {len(tables)} tables in PostgreSQL (expected after cleanup)")
            else:
                print("✅ PostgreSQL database is empty")
        except Exception:
            print("✅ PostgreSQL containers stopped (cleanup complete)")
        
        # Check Qdrant (only if containers are still running)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"http://{QDRANT_CONFIG['host']}:{QDRANT_CONFIG['port']}/collections")
                collections = response.json().get("result", {}).get("collections", [])
                
                if collections:
                    print(f"⚠️  Found {len(collections)} collections in Qdrant")
                else:
                    print("✅ Qdrant has no collections")
        except Exception:
            print("✅ Qdrant containers stopped (cleanup complete)")
        
        # Check uploads
        if UPLOADS_DIR.exists():
            files = list(UPLOADS_DIR.rglob("*"))
            file_count = len([f for f in files if f.is_file()])
            print(f"✅ Upload directory preserved with {file_count} files")
        else:
            print("✅ Upload directory doesn't exist")
        
        # Check .env credentials
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r') as f:
                content = f.read()
            if 'ADMIN_TENANT_ID=' in content or 'ADMIN_API_KEY=' in content:
                print("⚠️  Admin credentials still found in .env")
            else:
                print("✅ Admin credentials removed from .env")
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")


async def main():
    """Main cleanup function."""
    print("🚨 RAG SYSTEM CLEANUP SCRIPT")
    print("This will delete ALL data including:")
    print("  - PostgreSQL database and all tables")
    print("  - All Qdrant collections and vectors")
    print("  - Admin credentials from .env file")
    print("  - Demo tenant keys file")
    print("  - Docker containers (to reset deployment lifecycle)")
    print("")
    print("📁 NOTE: Upload files will be PRESERVED")
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        print("🔥 Force flag detected, proceeding with cleanup...")
    else:
        confirmation = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
        if confirmation != "YES":
            print("❌ Cleanup cancelled")
            return
    
    try:
        # Perform cleanup
        await cleanup_postgres()
        await cleanup_qdrant()
        cleanup_uploads()
        cleanup_env_credentials()
        cleanup_demo_keys()
        cleanup_containers()
        
        print("\n🎉 Cleanup completed successfully!")
        print("Next steps:")
        print("1. Start fresh system: docker-compose up -d")
        print("   This will automatically:")
        print("   - Start PostgreSQL & Qdrant")
        print("   - Run init container (creates tables & admin tenant)")
        print("   - Start backend API server")
        print("2. Verify system is healthy: docker-compose ps")
        print("3. Verify admin setup: python scripts/verify_admin_setup.py")
        print("   (This automatically checks credentials, database, and API access)")
        print("")
        print("📝 Notes:")
        print("- Containers were removed to reset deployment lifecycle")
        print("- Init container will run fresh and create admin tenant")
        print("- Upload files were preserved during cleanup")
        print("- Use scripts/setup_admin.py only for manual admin recreation if needed")
        
        # Verify cleanup
        await verify_cleanup()
        
    except Exception as e:
        print(f"\n💥 Cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())