#!/usr/bin/env python3
"""
Init container script for database and system setup.

This script runs as an init container before the main backend starts.
It handles:
1. Database table creation
2. Admin tenant setup
3. Basic system configuration

This script should complete successfully before the main backend container starts.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Tuple

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        from src.backend.database import create_tables
        create_tables()
        logger.info("✅ Database tables created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        return False


def setup_admin_tenant() -> bool:
    """Setup admin tenant if it doesn't exist."""
    logger.info("👤 Setting up admin tenant...")
    
    try:
        # Check if .env already has admin credentials
        from dotenv import load_dotenv
        load_dotenv()
        
        admin_tenant_id = os.getenv("ADMIN_TENANT_ID")
        admin_api_key = os.getenv("ADMIN_API_KEY")
        
        if admin_tenant_id and admin_api_key:
            logger.info("✅ Admin credentials already exist in .env file")
            return True
        
        # Create admin tenant directly
        return create_admin_tenant_inline()
            
    except Exception as e:
        logger.error(f"❌ Failed to setup admin tenant: {e}")
        return False


def create_admin_tenant_inline() -> bool:
    """Create admin tenant using inline logic."""
    import asyncio
    import secrets
    import uuid
    
    async def async_create_admin():
        try:
            from src.backend.database import get_async_db
            from src.backend.services.tenant_service import TenantService
            
            # Create admin tenant
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Check if admin tenant already exists
                existing_admin = await tenant_service.get_tenant_by_slug("admin")
                if existing_admin:
                    logger.info(f"✅ Admin tenant already exists: {existing_admin.id}")
                    admin_tenant_id = str(existing_admin.id)
                    admin_api_key = existing_admin.api_key
                else:
                    # Create new admin tenant
                    tenant_result = await tenant_service.create_tenant(
                        name="admin",
                        description="System administrator tenant"
                    )
                    
                    # Get the created tenant details
                    admin_tenant = await tenant_service.get_tenant_by_slug("admin")
                    admin_tenant_id = str(admin_tenant.id)
                    admin_api_key = admin_tenant.api_key
                    
                    logger.info(f"✅ Admin tenant created: {admin_tenant_id}")
                
                # Update .env file with admin credentials
                update_env_file(admin_tenant_id, admin_api_key)
                
                break  # Only need first session
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating admin tenant: {e}")
            return False
    
    # Run the async function
    return asyncio.run(async_create_admin())


def update_env_file(admin_tenant_id: str, admin_api_key: str) -> None:
    """Update .env file with admin credentials."""
    env_file = Path(".env")
    
    if not env_file.exists():
        logger.error("❌ .env file not found")
        return
    
    # Read current .env content
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Remove existing admin credentials
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
    
    # Add new admin credentials at the end
    if cleaned_lines and not cleaned_lines[-1].endswith('\n'):
        cleaned_lines.append('\n')
    
    cleaned_lines.extend([
        '# Admin credentials (auto-generated)\n',
        f'ADMIN_TENANT_ID={admin_tenant_id}\n',
        f'ADMIN_API_KEY={admin_api_key}\n'
    ])
    
    # Write updated content
    with open(env_file, 'w') as f:
        f.writelines(cleaned_lines)
    
    logger.info("✅ Admin credentials saved to .env file")


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
    """Main init container function."""
    logger.info("🚀 Starting init container setup...")
    
    # Step 1: Wait for external dependencies
    if not wait_for_dependencies():
        logger.error("❌ Init container failed: dependencies not available")
        sys.exit(1)
    
    # Step 2: Create database tables
    if not create_database_tables():
        logger.error("❌ Init container failed: database table creation failed")
        sys.exit(1)
    
    # Step 3: Setup admin tenant
    if not setup_admin_tenant():
        logger.error("❌ Init container failed: admin tenant setup failed")
        sys.exit(1)
    
    # Step 4: Verify setup
    if not verify_setup():
        logger.error("❌ Init container failed: setup verification failed")
        sys.exit(1)
    
    logger.info("🎉 Init container setup completed successfully!")
    logger.info("💡 Backend container can now start safely")


if __name__ == "__main__":
    main()