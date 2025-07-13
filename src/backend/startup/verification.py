"""
System requirements verification for backend startup.

Verifies that the system is properly configured before starting
the main application.
"""

import os
import logging
from typing import Tuple
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def verify_database_schema() -> Tuple[bool, str]:
    """Verify that database tables exist."""
    logger.info("Verifying database schema...")
    
    try:
        from sqlalchemy import create_engine, text
        
        # Use environment-specific database URL
        environment = os.getenv("RAG_ENVIRONMENT", "development")
        database_url = os.getenv(f"DATABASE_URL_{environment.upper()}")
        
        # Fallback to old DATABASE_URL for backwards compatibility
        if not database_url:
            database_url = os.getenv("DATABASE_URL")
            
        if not database_url:
            return False, "DATABASE_URL environment variable not set"
        
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Check if tenants table exists
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
    """Verify that admin tenant exists and is properly configured."""
    logger.info("Verifying admin tenant...")
    
    try:
        # Import here to avoid circular imports
        from src.backend.database import get_async_db
        from src.backend.services.tenant_service import TenantService
        
        # Load environment variables
        load_dotenv()
        
        # Check if .env has admin credentials first (no async needed)
        env_tenant_id = os.getenv("ADMIN_TENANT_ID")
        env_api_key = os.getenv("ADMIN_API_KEY")
        
        if not env_tenant_id or not env_api_key:
            return False, "Admin credentials not found in .env file"
        
        # Simple database check using sync connection for verification
        from sqlalchemy import create_engine, text
        
        # Use environment-specific database URL
        environment = os.getenv("RAG_ENVIRONMENT", "development")
        database_url = os.getenv(f"DATABASE_URL_{environment.upper()}")
        
        # Fallback to old DATABASE_URL for backwards compatibility
        if not database_url:
            database_url = os.getenv("DATABASE_URL")
            
        if not database_url:
            return False, "DATABASE_URL environment variable not set"
        
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Check if admin tenant exists with matching ID
            result = conn.execute(text("""
                SELECT id, slug FROM tenants 
                WHERE slug = 'admin'
            """))
            
            admin_row = result.fetchone()
            if not admin_row:
                return False, "Admin tenant not found in database"
            
            # Verify credentials match
            if str(admin_row.id) != env_tenant_id:
                return False, "Admin tenant ID mismatch between database and .env"
        
        success, message = True, "Admin tenant verified successfully"
        
        if success:
            logger.info(f"✅ {message}")
            return True, ""
        else:
            logger.error(f"❌ {message}")
            logger.error("   Setup required. Run admin setup before starting backend.")
            return False, message
        
    except Exception as e:
        error_msg = f"Failed to verify admin tenant: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error("   Setup may be required. Run admin setup before starting backend.")
        return False, error_msg


def verify_environment_config() -> Tuple[bool, str]:
    """Verify that required environment variables are set."""
    logger.info("Verifying environment configuration...")
    
    # Load environment variables
    load_dotenv()
    
    required_vars = [
        "DATABASE_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
    
    logger.info("✅ Environment configuration verified!")
    return True, ""


def verify_system_requirements() -> Tuple[bool, str]:
    """
    Verify all system requirements are met.
    
    Returns:
        Tuple[bool, str]: (success, error_message)
    """
    logger.info("🔍 Verifying system requirements...")
    
    # Verify environment configuration
    success, error = verify_environment_config()
    if not success:
        return False, f"Environment verification failed: {error}"
    
    # Verify database schema exists
    success, error = verify_database_schema()
    if not success:
        return False, f"Database schema verification failed: {error}"
    
    # Verify admin tenant is configured
    success, error = verify_admin_tenant()
    if not success:
        return False, f"Admin tenant verification failed: {error}"
    
    logger.info("✅ All system requirements verified!")
    return True, ""