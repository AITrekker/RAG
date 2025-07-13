#!/usr/bin/env python3
"""
Init container script for environment-aware database and system setup.

This script runs as an init container before the main backend starts.
It handles:
1. Environment database creation (production, staging, test, development)
2. Database table creation in current environment
3. Admin tenant setup
4. Credential management in .env
5. Basic system configuration

This script should complete successfully before the main backend container starts.
"""

import os
import sys
import logging
import asyncpg
import asyncio
from pathlib import Path
from typing import Tuple, List

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENTS = ["production", "staging", "test", "development"]
CURRENT_ENVIRONMENT = os.getenv("RAG_ENVIRONMENT", "development")


async def create_environment_databases() -> bool:
    """Create all environment-specific databases."""
    logger.info("🏗️ Creating environment-specific databases...")
    
    try:
        # Get database credentials
        postgres_user = os.getenv("POSTGRES_USER")
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        
        if not postgres_user or not postgres_password:
            logger.error("❌ Missing POSTGRES_USER or POSTGRES_PASSWORD")
            return False
        
        # Connect to default postgres database
        conn = await asyncpg.connect(
            host="postgres",  # Docker service name
            port=5432,
            database="postgres",
            user=postgres_user,
            password=postgres_password
        )
        
        logger.info("✅ Connected to PostgreSQL for database creation")
        
        # Create each environment database
        for env in ENVIRONMENTS:
            db_name = f"rag_db_{env}"
            
            try:
                # Check if database exists
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1", db_name
                )
                
                if result:
                    logger.info(f"  ✅ {db_name} already exists")
                else:
                    # Create database
                    await conn.execute(f'CREATE DATABASE {db_name} OWNER {postgres_user}')
                    logger.info(f"  ✅ Created {db_name}")
                    
            except Exception as e:
                logger.error(f"  ❌ Failed to create {db_name}: {e}")
                await conn.close()
                return False
        
        await conn.close()
        logger.info("🎉 Environment databases setup complete!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create environment databases: {e}")
        return False

def wait_for_dependencies() -> bool:
    """Wait for dependencies to be available."""
    logger.info("🔍 Waiting for dependencies in init container...")
    
    try:
        from src.backend.startup.dependencies import wait_for_dependencies
        success, error = wait_for_dependencies()
        
        if not success:
            logger.error(f"❌ Dependencies not available: {error}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error waiting for dependencies: {e}")
        return False


def create_database_tables() -> bool:
    """Create database tables if they don't exist."""
    logger.info("🗄️ Creating database tables...")
    
    try:
        # First, enable pgvector extension
        logger.info("🔧 Enabling pgvector extension...")
        if not asyncio.run(enable_pgvector_extension()):
            logger.error("❌ Failed to enable pgvector extension")
            return False
        
        # Then create tables
        from src.backend.database import create_tables
        create_tables()
        logger.info("✅ Database tables created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        return False


async def enable_pgvector_extension() -> bool:
    """Enable pgvector extension in the current environment database."""
    try:
        import asyncpg
        
        # Get database credentials
        postgres_user = os.getenv("POSTGRES_USER")
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        current_db = f"rag_db_{CURRENT_ENVIRONMENT}"
        
        if not postgres_user or not postgres_password:
            logger.error("❌ Missing POSTGRES_USER or POSTGRES_PASSWORD")
            return False
        
        # Connect to the current environment database
        conn = await asyncpg.connect(
            host="postgres",  # Docker service name
            port=5432,
            database=current_db,
            user=postgres_user,
            password=postgres_password
        )
        
        logger.info(f"✅ Connected to {current_db} for pgvector extension setup")
        
        # Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("✅ pgvector extension enabled successfully!")
        
        # Verify extension is available
        result = await conn.fetchval("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
        if result:
            logger.info("✅ pgvector extension verified and ready")
        else:
            logger.error("❌ pgvector extension not found after installation")
            await conn.close()
            return False
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to enable pgvector extension: {e}")
        return False


def setup_admin_tenant() -> bool:
    """Setup admin tenant with always-fresh API key."""
    logger.info("👤 Setting up admin tenant...")
    
    try:
        # Always generate a new admin API key for security
        logger.info("🔑 Generating fresh admin API key...")
        import secrets
        new_admin_api_key = f"tenant_admin_{secrets.token_hex(20)}"
        
        # Check if admin tenant already exists in database
        from dotenv import load_dotenv
        load_dotenv()
        
        admin_tenant_id = os.getenv("ADMIN_TENANT_ID")
        logger.info(f"📋 Found existing ADMIN_TENANT_ID: {'Yes' if admin_tenant_id else 'No'}")
        
        if admin_tenant_id:
            # Admin tenant ID exists, just update the API key in env file
            logger.info(f"✅ Admin tenant ID found: {admin_tenant_id}")
            logger.info("🔄 Updating API key in environment file (skipping database update for now)...")
            update_env_file(admin_tenant_id, new_admin_api_key)
            logger.info("✅ Admin tenant API key updated in environment")
            return True
        
        # No admin tenant ID, create new admin tenant
        logger.info("🏗️ No existing admin tenant found, creating new admin tenant...")
        result = create_admin_tenant_with_fresh_key(new_admin_api_key)
        logger.info(f"🎯 Admin tenant creation result: {result}")
        return result
            
    except Exception as e:
        logger.error(f"❌ Failed to setup admin tenant: {e}")
        import traceback
        logger.error(f"🔥 Full traceback: {traceback.format_exc()}")
        return False


def verify_admin_tenant_exists(admin_tenant_id: str) -> bool:
    """Verify if admin tenant exists in database."""
    import asyncio
    
    async def async_verify():
        try:
            from src.backend.database import get_async_db
            from src.backend.services.tenant_service import TenantService
            
            async for db in get_async_db():
                tenant_service = TenantService(db)
                tenant = await tenant_service.get_tenant_by_id(admin_tenant_id)
                return tenant is not None
                
        except Exception as e:
            logger.error(f"Error verifying admin tenant: {e}")
            return False
    
    return asyncio.run(async_verify())


def create_admin_tenant_with_existing_credentials(admin_tenant_id: str, admin_api_key: str) -> bool:
    """Recreate admin tenant with existing credentials."""
    import asyncio
    
    async def async_recreate():
        try:
            from src.backend.database import get_async_db
            from src.backend.services.tenant_service import TenantService
            from src.backend.models.database import Tenant
            from uuid import UUID
            
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Create simplified tenant with the existing ID and API key
                tenant = Tenant(
                    id=UUID(admin_tenant_id),
                    name="admin",
                    slug="admin",
                    api_key=admin_api_key
                )
                
                # Add to database
                db.add(tenant)
                await db.commit()
                await db.refresh(tenant)
                
                logger.info(f"✅ Admin tenant recreated with existing credentials: {tenant.id}")
                return True
                
        except Exception as e:
            logger.error(f"Error recreating admin tenant: {e}")
            return False
    
    return asyncio.run(async_recreate())


def create_admin_tenant_inline() -> bool:
    """Create admin tenant using inline logic."""
    import asyncio
    import secrets
    import uuid
    
    async def async_create_admin():
        try:
            logger.info("🔧 Importing database and tenant service...")
            from src.backend.database import get_async_db
            from src.backend.services.tenant_service import TenantService
            
            logger.info("🔧 Getting database connection...")
            # Create admin tenant
            async for db in get_async_db():
                logger.info("🔧 Creating tenant service...")
                tenant_service = TenantService(db)
                
                logger.info("🔍 Checking if admin tenant already exists...")
                # Check if admin tenant already exists
                existing_admin = await tenant_service.get_tenant_by_slug("admin")
                if existing_admin:
                    logger.info(f"✅ Admin tenant already exists: {existing_admin.id}")
                    admin_tenant_id = str(existing_admin.id)
                    
                    # ALWAYS generate a fresh API key for security
                    logger.info("🔑 Generating fresh admin API key for security...")
                    import secrets
                    admin_api_key = f"tenant_admin_{secrets.token_hex(16)}"
                    
                    # Update the tenant with the new API key
                    await tenant_service.update_tenant_api_key(existing_admin.id, admin_api_key)
                    logger.info("🔐 Admin API key regenerated successfully")
                else:
                    logger.info("🏗️ Creating new admin tenant...")
                    # Create new admin tenant
                    tenant_result = await tenant_service.create_tenant(
                        name="admin",
                        description="System administrator tenant"
                    )
                    logger.info(f"🔧 Tenant creation result: {tenant_result}")
                    
                    logger.info("🔍 Retrieving created admin tenant details...")
                    # Get the created tenant details
                    admin_tenant = await tenant_service.get_tenant_by_slug("admin")
                    admin_tenant_id = str(admin_tenant.id)
                    admin_api_key = admin_tenant.api_key
                    
                    logger.info(f"✅ Admin tenant created: {admin_tenant_id}")
                
                logger.info("📝 Updating .env file with admin credentials...")
                # Update .env file with admin credentials
                update_env_file(admin_tenant_id, admin_api_key)
                logger.info("✅ .env file updated successfully")
                
                break  # Only need first session
                
            logger.info("🎉 Admin tenant setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating admin tenant: {e}")
            import traceback
            logger.error(f"🔥 Full traceback: {traceback.format_exc()}")
            return False
    
    # Run the async function
    try:
        logger.info("🚀 Starting async admin tenant creation...")
        result = asyncio.run(async_create_admin())
        logger.info(f"🎯 Async admin tenant creation result: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Error in async admin tenant creation: {e}")
        import traceback
        logger.error(f"🔥 Full traceback: {traceback.format_exc()}")
        return False


def update_admin_tenant_api_key(admin_tenant_id: str, new_api_key: str) -> bool:
    """Update existing admin tenant's API key in the database."""
    try:
        import asyncio
        from src.backend.database import AsyncSessionLocal
        from src.backend.models.database import Tenant
        from sqlalchemy import select
        from uuid import UUID
        
        async def update_key():
            session = None
            try:
                session = AsyncSessionLocal()
                # Find the admin tenant
                result = await session.execute(
                    select(Tenant).where(Tenant.id == UUID(admin_tenant_id))
                )
                tenant = result.scalar_one_or_none()
                
                if not tenant:
                    logger.error(f"❌ Admin tenant {admin_tenant_id} not found in database")
                    return False
                
                # Update the API key
                tenant.api_key = new_api_key
                await session.commit()
                logger.info(f"✅ Updated API key for admin tenant {admin_tenant_id}")
                return True
            except Exception as e:
                if session:
                    await session.rollback()
                raise e
            finally:
                if session:
                    await session.close()
        
        return asyncio.run(update_key())
        
    except Exception as e:
        logger.error(f"❌ Failed to update admin tenant API key: {e}")
        return False


def create_admin_tenant_with_new_key(admin_tenant_id: str, new_api_key: str) -> bool:
    """Create admin tenant with existing ID but new API key."""
    try:
        import asyncio
        from src.backend.database import AsyncSessionLocal
        from src.backend.models.database import Tenant
        from uuid import UUID
        
        async def create_tenant():
            async with AsyncSessionLocal() as session:
                # Create simplified admin tenant with existing ID
                admin_tenant = Tenant(
                    id=UUID(admin_tenant_id),
                    name="admin",
                    slug="admin",
                    api_key=new_api_key
                )
                
                session.add(admin_tenant)
                await session.commit()
                logger.info(f"✅ Created admin tenant with ID {admin_tenant_id}")
                return True
        
        result = asyncio.run(create_tenant())
        if result:
            update_env_file(admin_tenant_id, new_api_key)
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to create admin tenant with new key: {e}")
        return False


def create_admin_tenant_with_fresh_key(new_api_key: str) -> bool:
    """Create completely new admin tenant with fresh API key."""
    try:
        import asyncio
        from src.backend.database import AsyncSessionLocal
        from src.backend.models.database import Tenant
        from uuid import uuid4
        
        async def create_tenant():
            async with AsyncSessionLocal() as session:
                # Create simplified admin tenant with new ID
                new_tenant_id = uuid4()
                admin_tenant = Tenant(
                    id=new_tenant_id,
                    name="admin",
                    slug="admin",
                    api_key=new_api_key
                )
                
                session.add(admin_tenant)
                await session.commit()
                logger.info(f"✅ Created new admin tenant with ID {new_tenant_id}")
                return str(new_tenant_id)
        
        new_tenant_id = asyncio.run(create_tenant())
        if new_tenant_id:
            update_env_file(new_tenant_id, new_api_key)
            return True
        return False
        
    except Exception as e:
        logger.error(f"❌ Failed to create admin tenant with fresh key: {e}")
        return False


def update_env_file(admin_tenant_id: str, admin_api_key: str) -> None:
    """Update .env file with admin credentials and environment information."""
    env_file = Path(".env")
    
    if not env_file.exists():
        logger.error("❌ .env file not found")
        return
    
    # Read current .env content
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Remove existing admin credentials and environment info
    cleaned_lines = []
    skip_next_empty = False
    
    for line in lines:
        if (line.strip().startswith('ADMIN_TENANT_ID=') or 
            line.strip().startswith('ADMIN_API_KEY=') or
            line.strip().startswith('RAG_ENVIRONMENT=') or
            line.strip().startswith('DATABASE_URL_')):
            continue
        elif line.strip() in ['# Admin credentials (auto-generated)', '# Environment-specific database URLs']:
            skip_next_empty = True
            continue
        elif skip_next_empty and line.strip() == '':
            skip_next_empty = False
            continue
        else:
            cleaned_lines.append(line)
            skip_next_empty = False
    
    # Add new admin credentials and environment info at the end
    if cleaned_lines and not cleaned_lines[-1].endswith('\n'):
        cleaned_lines.append('\n')
    
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    
    cleaned_lines.extend([
        '# Admin credentials (auto-generated)\n',
        f'ADMIN_TENANT_ID={admin_tenant_id}\n',
        f'ADMIN_API_KEY={admin_api_key}\n',
        f'RAG_ENVIRONMENT={CURRENT_ENVIRONMENT}\n',
        '\n',
        '# Environment-specific database URLs\n',
        f'DATABASE_URL_PRODUCTION=postgresql://{postgres_user}:{postgres_password}@postgres:5432/rag_db_production\n',
        f'DATABASE_URL_STAGING=postgresql://{postgres_user}:{postgres_password}@postgres:5432/rag_db_staging\n',
        f'DATABASE_URL_TEST=postgresql://{postgres_user}:{postgres_password}@postgres:5432/rag_db_test\n',
        f'DATABASE_URL_DEVELOPMENT=postgresql://{postgres_user}:{postgres_password}@postgres:5432/rag_db_development\n'
    ])
    
    # Write updated content
    with open(env_file, 'w') as f:
        f.writelines(cleaned_lines)
    
    logger.info("✅ Admin credentials and environment URLs saved to .env file")
    
    # Also write admin key to JSON file for frontend access
    write_admin_config_json(admin_tenant_id, admin_api_key)


def write_admin_config_json(admin_tenant_id: str, admin_api_key: str) -> None:
    """Write admin configuration to JSON file for frontend access."""
    import json
    from datetime import datetime, timezone
    
    admin_config = {
        "admin_tenant_id": admin_tenant_id,
        "admin_api_key": admin_api_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "init_container"
    }
    
    config_file = Path("demo_admin_keys.json")
    
    try:
        with open(config_file, 'w') as f:
            json.dump(admin_config, f, indent=2)
        logger.info("✅ Admin configuration saved to demo_admin_keys.json")
    except Exception as e:
        logger.error(f"❌ Failed to write admin config JSON: {e}")


def verify_setup() -> bool:
    """Verify that setup was successful."""
    logger.info("🔍 Verifying setup...")
    
    try:
        from src.backend.startup.verification import verify_system_requirements
        success, error = verify_system_requirements()
        
        if success:
            logger.info("✅ Setup verification successful!")
            return True
        else:
            logger.error(f"❌ Setup verification failed: {error}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error during setup verification: {e}")
        return False


def main():
    """Main init container function with environment support."""
    logger.info("🚀 Starting environment-aware init container setup...")
    logger.info(f"🌍 Target environment: {CURRENT_ENVIRONMENT}")
    
    # Step 1: Wait for external dependencies
    if not wait_for_dependencies():
        logger.error("❌ Init container failed: dependencies not available")
        sys.exit(1)
    
    # Step 2: Create environment-specific databases
    if not asyncio.run(create_environment_databases()):
        logger.error("❌ Init container failed: environment database creation failed")
        sys.exit(1)
    
    # Step 3: Create database tables in current environment
    if not create_database_tables():
        logger.error("❌ Init container failed: database table creation failed")
        sys.exit(1)
    
    # Step 4: Setup admin tenant
    if not setup_admin_tenant():
        logger.error("❌ Init container failed: admin tenant setup failed")
        sys.exit(1)
    
    # Step 5: Verify setup
    if not verify_setup():
        logger.error("❌ Init container failed: setup verification failed")
        sys.exit(1)
    
    logger.info("🎉 Environment-aware init container setup completed successfully!")
    logger.info(f"💡 Backend container can now start safely in {CURRENT_ENVIRONMENT} environment")
    logger.info("📋 Environment databases created:")
    for env in ENVIRONMENTS:
        logger.info(f"  - rag_db_{env}")
    logger.info(f"🔑 Admin credentials and environment URLs written to .env")


if __name__ == "__main__":
    main()