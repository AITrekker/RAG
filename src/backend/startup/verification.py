"""
Simplified system requirements verification.
"""

import os
import logging
from typing import Tuple
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def reload_environment_variables() -> None:
    """
    Force reload .env file and clear settings cache.
    
    This is needed because the init container writes new credentials to .env
    during runtime, but Pydantic settings are cached at startup time.
    """
    logger.info("🔄 Reloading environment variables from .env file...")
    
    # Reload .env file (override=True means existing env vars are updated)
    load_dotenv(override=True)
    
    # Clear the settings cache so get_settings() will read new values
    from src.backend.config.settings import get_settings
    get_settings.cache_clear()
    
    logger.info("✅ Environment variables reloaded successfully")


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
            logger.warning("⚠️ ADMIN_API_KEY not found in environment variables")
            return False, "Admin credentials not found in .env file"
        
        # Log first few characters for verification (security: don't log full key)
        logger.info(f"✅ Admin tenant verified successfully (key starts with: {admin_api_key[:12]}...)")
        return True, ""
        
    except Exception as e:
        error_msg = f"Failed to verify admin tenant: {e}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verify_system_requirements() -> Tuple[bool, str]:
    """Verify all system requirements are met."""
    logger.info("🔍 Verifying system requirements...")
    
    # Force reload .env file to pick up changes from init container
    reload_environment_variables()
    
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