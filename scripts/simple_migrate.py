#!/usr/bin/env python3
"""
Simple Database Migration Script (No Backup Required)

This script runs database migrations without creating backups,
useful for development environments.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.config.settings import get_settings
from src.backend.db.session import engine
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


def check_database_connection() -> bool:
    """Check database connectivity."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def run_migrations(target_revision: str = "head") -> bool:
    """Run database migrations."""
    logger.info(f"Running migrations to {target_revision}")
    
    try:
        # Change to backend directory for alembic
        backend_dir = Path(__file__).parent.parent / "src" / "backend"
        
        cmd = [
            "python", "-m", "alembic", 
            "-c", "migrations/alembic.ini",
            "upgrade", target_revision
        ]
        
        result = subprocess.run(
            cmd, 
            cwd=backend_dir,
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Migrations completed successfully")
            if result.stdout:
                logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"Migration failed: {result.stderr}")
            if result.stdout:
                logger.error(f"Output: {result.stdout}")
            return False
            
    except Exception as e:
        logger.error(f"Migration failed with exception: {e}")
        return False


def main():
    logger.info("Simple Database Migration Tool")
    
    # Check database connection first
    if not check_database_connection():
        logger.error("Cannot connect to database. Exiting.")
        sys.exit(1)
    
    # Run migrations
    logger.info("Running database migrations...")
    success = run_migrations()
    
    if success:
        logger.info("Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 