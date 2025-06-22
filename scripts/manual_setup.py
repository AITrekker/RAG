#!/usr/bin/env python3
"""
Manual Database Setup Script

Manually insert tenant and API key with detailed step-by-step logging.
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


def manual_setup():
    """Manually set up tenant and API key with detailed logging."""
    try:
        db = next(get_db())
        
        # Step 1: Check current state
        logger.info("=== STEP 1: Checking current database state ===")
        tenants = db.execute(text("SELECT id, tenant_id, name FROM tenants")).fetchall()
        logger.info(f"Found {len(tenants)} tenants")
        for tenant in tenants:
            logger.info(f"  Tenant: {tenant}")
        
        # Step 2: Insert tenant
        logger.info("\n=== STEP 2: Creating tenant ===")
        now = datetime.now(timezone.utc)
        
        try:
            result = db.execute(text("""
                INSERT INTO tenants (
                    id, tenant_id, name, display_name, tier, isolation_level, status,
                    created_at, updated_at, max_documents, max_storage_mb,
                    max_api_calls_per_day, max_concurrent_queries, contact_email
                ) VALUES (
                    gen_random_uuid(), 'default', 'Default Tenant', 'Default Development Tenant', 
                    'basic', 'logical', 'active', :now, :now, 1000, 5000, 10000, 10, 'dev@example.com'
                ) RETURNING id, tenant_id
            """), {"now": now})
            
            tenant_result = result.fetchone()
            logger.info(f"Tenant INSERT result: {tenant_result}")
            
            if tenant_result:
                tenant_uuid = tenant_result[0]
                tenant_id = tenant_result[1]
                logger.info(f"Created tenant with UUID: {tenant_uuid}, tenant_id: {tenant_id}")
            else:
                logger.error("Tenant INSERT returned no result")
                return False
                
        except Exception as e:
            # Check if it's a duplicate
            if "unique" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("Tenant already exists, fetching existing tenant")
                result = db.execute(text("SELECT id, tenant_id FROM tenants WHERE tenant_id = 'default'")).fetchone()
                if result:
                    tenant_uuid = result[0]
                    tenant_id = result[1]
                    logger.info(f"Found existing tenant with UUID: {tenant_uuid}, tenant_id: {tenant_id}")
                else:
                    logger.error(f"Tenant creation failed and couldn't find existing tenant: {e}")
                    return False
            else:
                logger.error(f"Tenant creation failed: {e}")
                return False
        
        # Step 3: Commit tenant
        logger.info("\n=== STEP 3: Committing tenant transaction ===")
        db.commit()
        logger.info("Tenant transaction committed")
        
        # Step 4: Verify tenant exists
        logger.info("\n=== STEP 4: Verifying tenant exists ===")
        verify_result = db.execute(text("SELECT id, tenant_id FROM tenants WHERE tenant_id = 'default'")).fetchone()
        if verify_result:
            logger.info(f"Verified tenant exists: {verify_result}")
        else:
            logger.error("Tenant verification failed - tenant not found after commit")
            return False
        
        # Step 5: Create API key
        logger.info("\n=== STEP 5: Creating API key ===")
        api_key = "dev-api-key-123"
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        expires_at = now + timedelta(days=365)
        
        logger.info(f"API key: {api_key}")
        logger.info(f"Key hash: {key_hash}")
        logger.info(f"Tenant UUID for FK: {tenant_uuid}")
        
        try:
            api_result = db.execute(text("""
                INSERT INTO tenant_api_keys (
                    id, tenant_id, key_name, key_hash, key_prefix, scopes, 
                    created_at, updated_at, expires_at, is_active, usage_count
                ) VALUES (
                    gen_random_uuid(), :tenant_uuid, 'Default Dev Key', :key_hash, 'dev-api', 
                    '{}', :now, :now, :expires_at, true, 0
                ) RETURNING id, key_name
            """), {
                "tenant_uuid": tenant_uuid,
                "key_hash": key_hash,
                "now": now,
                "expires_at": expires_at
            })
            
            api_key_result = api_result.fetchone()
            logger.info(f"API key INSERT result: {api_key_result}")
            
        except Exception as e:
            if "unique" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("API key already exists")
            else:
                logger.error(f"API key creation failed: {e}")
                return False
        
        # Step 6: Commit everything
        logger.info("\n=== STEP 6: Final commit ===")
        db.commit()
        logger.info("Final transaction committed")
        
        # Step 7: Final verification
        logger.info("\n=== STEP 7: Final verification ===")
        final_tenants = db.execute(text("SELECT id, tenant_id, name FROM tenants")).fetchall()
        final_keys = db.execute(text("SELECT id, tenant_id, key_name FROM tenant_api_keys")).fetchall()
        
        logger.info(f"Final tenants count: {len(final_tenants)}")
        for tenant in final_tenants:
            logger.info(f"  Tenant: {tenant}")
            
        logger.info(f"Final API keys count: {len(final_keys)}")
        for key in final_keys:
            logger.info(f"  API Key: {key}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Manual setup failed: {e}", exc_info=True)
        return False


def main():
    logger.info("Manual Database Setup Tool")
    
    success = manual_setup()
    
    if success:
        logger.info("Manual setup completed successfully!")
        logger.info("You can now use the API key 'dev-api-key-123' for authentication")
    else:
        logger.error("Manual setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 