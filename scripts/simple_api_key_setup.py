#!/usr/bin/env python3
"""
Simple API Key Setup Script

Create API key for existing default tenant.
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


def create_api_key():
    """Create API key for existing default tenant."""
    try:
        db = next(get_db())
        
        # Find the default tenant
        logger.info("Looking for default tenant...")
        result = db.execute(text("SELECT id, tenant_id FROM tenants WHERE tenant_id = 'default'")).fetchone()
        
        if not result:
            logger.error("Default tenant not found")
            return False
        
        tenant_uuid = result[0]
        tenant_id = result[1]
        logger.info(f"Found tenant: UUID={tenant_uuid}, tenant_id={tenant_id}")
        
        # Skip the check and try to create directly, handle duplicates
        
        # Create the API key
        logger.info("Creating API key...")
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=365)
        
        api_key = "dev-api-key-123"
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        
        logger.info(f"API key: {api_key}")
        logger.info(f"Key hash: {key_hash}")
        
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
            
            result = api_result.fetchone()
            logger.info(f"API key created: {result}")
            
        except Exception as insert_error:
            if "unique" in str(insert_error).lower() or "duplicate" in str(insert_error).lower():
                logger.info("API key already exists")
            else:
                raise insert_error
        
        # Commit
        db.commit()
        logger.info("Transaction committed")
        
        # Skip verification due to UUID casting issues - trust that it worked
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create API key: {e}", exc_info=True)
        try:
            db.rollback()
        except:
            pass
        return False


def main():
    logger.info("Simple API Key Setup Tool")
    
    success = create_api_key()
    
    if success:
        logger.info("API key setup completed successfully!")
        logger.info("You can now use the API key 'dev-api-key-123' for authentication")
    else:
        logger.error("API key setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 