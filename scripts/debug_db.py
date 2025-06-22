#!/usr/bin/env python3
"""
Debug Database Script

Check what tenants and API keys exist in the database.
"""

import sys
import logging
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


def check_database():
    """Check what's in the database."""
    try:
        db = next(get_db())
        
        # Check tenants
        logger.info("=== TENANTS ===")
        tenants = db.execute(text("SELECT id, tenant_id, name, status FROM tenants")).fetchall()
        for tenant in tenants:
            logger.info(f"Tenant: {tenant}")
        
        if not tenants:
            logger.info("No tenants found")
        
        # Check API keys
        logger.info("\n=== API KEYS ===")
        api_keys = db.execute(text("SELECT id, tenant_id, key_name, key_prefix, is_active FROM tenant_api_keys")).fetchall()
        for key in api_keys:
            logger.info(f"API Key: {key}")
        
        if not api_keys:
            logger.info("No API keys found")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to check database: {e}", exc_info=True)
        return False


def main():
    logger.info("Database Debug Tool")
    
    success = check_database()
    
    if success:
        logger.info("Database check completed")
    else:
        logger.error("Database check failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 