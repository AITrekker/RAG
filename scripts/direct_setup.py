#!/usr/bin/env python3
"""
Direct Database Setup Script

Creates the default tenant and API key directly in the database
without relying on alembic command-line tools.
"""

import sys
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.config.settings import get_settings
from src.backend.db.session import get_db
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


def create_default_tenant_and_api_key():
    """Create default tenant and API key directly in the database."""
    try:
        db = next(get_db())
        
        # Check if default tenant exists
        result = db.execute(text("SELECT id FROM tenants WHERE tenant_id = 'default'")).fetchone()
        
        if not result:
            logger.info("Creating default tenant...")
            now = datetime.now(timezone.utc)
            
            # Create default tenant
            db.execute(text("""
                INSERT INTO tenants (
                    id, tenant_id, name, display_name, tier, isolation_level, status,
                    created_at, updated_at, max_documents, max_storage_mb,
                    max_api_calls_per_day, max_concurrent_queries, contact_email
                ) VALUES (
                    gen_random_uuid(), 'default', 'Default Tenant', 'Default Development Tenant', 
                    'basic', 'logical', 'active', :now, :now, 1000, 5000, 10000, 10, 'dev@example.com'
                )
            """), {"now": now})
            
            # Commit the tenant creation first
            db.commit()
            
            # Get the newly created tenant
            result = db.execute(text("SELECT id FROM tenants WHERE tenant_id = 'default'")).fetchone()
            logger.info("Default tenant created successfully")
        else:
            logger.info("Default tenant already exists")
        
        if result:
            tenant_id = result[0]
            logger.info(f"Default tenant ID: {tenant_id}")
            
            # Try to create the API key directly, catch if it already exists
            try:
                logger.info("Creating default API key...")
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(days=365)
                
                # Hash the API key
                api_key = "dev-api-key-123"
                key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
                
                logger.info(f"API key: {api_key}")
                logger.info(f"API key hash: {key_hash}")
                
                # Insert the new API key
                db.execute(text("""
                    INSERT INTO tenant_api_keys (
                        id, tenant_id, key_name, key_hash, key_prefix, scopes, 
                        created_at, updated_at, expires_at, is_active, usage_count
                    ) VALUES (
                        gen_random_uuid(), :tenant_id, 'Default Dev Key', :key_hash, 'dev-api', 
                        '{}', :now, :now, :expires_at, true, 0
                    )
                """), {
                    "tenant_id": tenant_id,
                    "key_hash": key_hash,
                    "now": now,
                    "expires_at": expires_at
                })
                
                db.commit()
                logger.info("Default API key created successfully")
                
            except Exception as api_key_error:
                # Check if it's a duplicate key error
                if "unique constraint" in str(api_key_error).lower() or "already exists" in str(api_key_error).lower():
                    logger.info("Default API key already exists")
                else:
                    # Re-raise other errors
                    raise api_key_error
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create default tenant and API key: {e}", exc_info=True)
        return False


def check_database_connection():
    """Check database connectivity."""
    try:
        db = next(get_db())
        result = db.execute(text("SELECT 1")).fetchone()
        db.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def main():
    logger.info("Direct Database Setup Tool")
    
    # Check database connection first
    if not check_database_connection():
        logger.error("Cannot connect to database. Exiting.")
        sys.exit(1)
    
    # Create tenant and API key
    logger.info("Creating default tenant and API key...")
    success = create_default_tenant_and_api_key()
    
    if success:
        logger.info("Setup completed successfully!")
        logger.info("You can now use the API key 'dev-api-key-123' for authentication")
        sys.exit(0)
    else:
        logger.error("Setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 