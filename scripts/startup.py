#!/usr/bin/env python3
"""
Startup script for the RAG backend.
This script runs before the main FastAPI application starts to:
1. Wait for Qdrant to be available
2. Check if the database is empty
3. Seed it with admin tenant and API key if needed
4. Write the admin API key to .env for later use
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def wait_for_qdrant(max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for Qdrant to become available."""
    logger.info("Waiting for Qdrant to become available...")
    
    # Get Qdrant connection details from environment
    # In Docker Compose, use the service name 'qdrant', otherwise use localhost
    qdrant_host = os.getenv("QDRANT_HOST", "qdrant")  # Default to service name for Docker
    qdrant_port = os.getenv("QDRANT_PORT", "6333")
    qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    
    logger.info(f"Connecting to Qdrant at: {qdrant_url}")
    
    for attempt in range(max_retries):
        try:
            import requests
            response = requests.get(f"{qdrant_url}/collections", timeout=5)
            if response.status_code == 200:
                collections = response.json()
                logger.info(f"✅ Qdrant is available! Found {len(collections.get('collections', []))} collections")
                return True
        except Exception as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: Qdrant not ready yet ({e})")
            if attempt < max_retries - 1:
                time.sleep(delay)
    
    logger.error("❌ Qdrant failed to become available within the expected time")
    return False

def wait_for_postgres(max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for PostgreSQL to become available."""
    logger.info("Waiting for PostgreSQL to become available...")
    
    # Get database connection details from environment
    database_url = os.getenv("DATABASE_URL", "postgresql://rag_user:rag_password@postgres:5432/rag_db")
    
    for attempt in range(max_retries):
        try:
            from sqlalchemy import create_engine, text
            
            # Create a test engine
            test_engine = create_engine(database_url, pool_pre_ping=True)
            
            # Test connection
            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    logger.info("✅ PostgreSQL is available!")
                    return True
                    
        except Exception as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: PostgreSQL not ready yet ({e})")
            if attempt < max_retries - 1:
                time.sleep(delay)
    
    logger.error("❌ PostgreSQL failed to become available within the expected time")
    return False

def is_database_empty() -> bool:
    """Check if the database is empty (no tenants)."""
    try:
        # Import here to avoid settings issues
        from src.backend.database import get_async_db
        from src.backend.services.tenant_service import TenantService
        
        # Use asyncio to run the async check
        import asyncio
        
        async def check_tenants():
            async for db in get_async_db():
                tenant_service = TenantService(db)
                tenants = await tenant_service.list_tenants()
                return len(tenants) == 0
        
        return asyncio.run(check_tenants())
        
    except Exception as e:
        logger.warning(f"Could not check database state: {e}")
        # Assume empty if we can't check
        return True

def seed_database() -> Optional[dict]:
    """Seed the database with admin tenant and API key."""
    logger.info("Seeding database with admin tenant...")
    
    try:
        # Import here to avoid settings issues
        from src.backend.database import get_async_db
        from src.backend.services.tenant_service import TenantService
        
        # Use asyncio to run the async operations
        import asyncio
        
        async def create_admin():
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Create admin tenant
                admin_result = await tenant_service.create_tenant(
                    name="System Admin",
                    description="System administrator tenant",
                    auto_sync=True,
                    sync_interval=60
                )
                
                # Get the created tenant
                admin_tenant = await tenant_service.get_tenant_by_slug("admin")
                
                # Generate API key
                api_key = await tenant_service.regenerate_api_key(admin_tenant.id)
                
                return {
                    "tenant_id": str(admin_tenant.id),
                    "api_key": api_key
                }
        
        result = asyncio.run(create_admin())
        
        logger.info(f"✅ Created admin tenant with ID: {result['tenant_id']}")
        logger.info(f"✅ Generated admin API key: {result['api_key']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to seed database: {e}")
        return None

def write_env_config(admin_tenant_id: str, admin_api_key: str) -> bool:
    """Write admin credentials to .env file."""
    env_file = Path(".env")
    
    try:
        # Read existing .env content
        existing_content = ""
        if env_file.exists():
            with open(env_file, "r") as f:
                existing_content = f.read()
        
        # Check if admin credentials already exist
        if f"ADMIN_API_KEY={admin_api_key}" in existing_content:
            logger.info("Admin credentials already exist in .env file")
            return True
        
        # Add admin credentials
        with open(env_file, "a") as f:
            f.write(f"\n# Admin credentials (auto-generated)\n")
            f.write(f"ADMIN_TENANT_ID={admin_tenant_id}\n")
            f.write(f"ADMIN_API_KEY={admin_api_key}\n")
        
        logger.info("✅ Admin credentials written to .env file")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to write to .env file: {e}")
        return False

def main():
    """Main startup function."""
    logger.info("🚀 Starting RAG backend initialization...")
    
    # Step 1: Wait for PostgreSQL
    if not wait_for_postgres():
        logger.error("Failed to connect to PostgreSQL. Exiting.")
        sys.exit(1)
    
    # Step 2: Wait for Qdrant
    if not wait_for_qdrant():
        logger.error("Failed to connect to Qdrant. Exiting.")
        sys.exit(1)
    
    # Step 3: Check if database is empty
    if is_database_empty():
        logger.info("Database is empty. Seeding with admin tenant...")
        
        # Step 4: Seed the database
        seed_result = seed_database()
        if seed_result:
            # Step 5: Write to .env
            write_env_config(
                seed_result['tenant_id'],
                seed_result['api_key']
            )
            
            logger.info("🎉 Database seeding completed successfully!")
            logger.info(f"Admin Tenant ID: {seed_result['tenant_id']}")
            logger.info(f"Admin API Key: {seed_result['api_key']}")
            logger.info("⚠️  IMPORTANT: Save this API key securely!")
        else:
            logger.error("❌ Database seeding failed!")
            sys.exit(1)
    else:
        logger.info("✅ Database already contains data. Skipping seeding.")
    
    logger.info("✅ Backend initialization completed successfully!")

if __name__ == "__main__":
    main() 