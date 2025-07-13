"""
Simplified system requirements verification.
"""

import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def verify_database_schema() -> Tuple[bool, str]:
    """Verify that database tables exist."""
    logger.info("Verifying database schema...")
    
    try:
        from sqlalchemy import create_engine, text
        
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return False, "DATABASE_URL environment variable not set"
        
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'tenants'
                )
            """))
            
            if result.scalar():
                logger.info("✅ Database schema verified!")
                return True, ""
            else:
                error_msg = "Database tables do not exist. Run database migrations first."
                logger.error(f"❌ {error_msg}")
                return False, error_msg
                
    except Exception as e:
        error_msg = f"Failed to verify database schema: {e}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verify_admin_tenant() -> Tuple[bool, str]:
    """Basic admin tenant verification."""
    logger.info("Verifying admin tenant...")
    
    try:
        admin_api_key = os.getenv("ADMIN_API_KEY")
        if not admin_api_key:
            return False, "Admin credentials not found in .env file"
        
        logger.info("✅ Admin tenant verified successfully")
        return True, ""
        
    except Exception as e:
        error_msg = f"Failed to verify admin tenant: {e}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verify_system_requirements() -> Tuple[bool, str]:
    """Verify all system requirements are met."""
    logger.info("🔍 Verifying system requirements...")
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        return False, "DATABASE_URL environment variable not set"
    
    # Verify database schema exists
    success, error = verify_database_schema()
    if not success:
        return False, f"Database schema verification failed: {error}"
    
    # Verify admin tenant
    success, error = verify_admin_tenant()
    if not success:
        return False, f"Admin tenant verification failed: {error}"
    
    logger.info("✅ All system requirements verified!")
    return True, ""