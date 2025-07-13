"""
Dependency verification for backend startup.
"""

import os
import time
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def wait_for_postgres(max_retries: int = 10, delay: int = 1) -> bool:
    """Wait for PostgreSQL to become available."""
    logger.info("Waiting for PostgreSQL to become available...")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        return False
    
    for attempt in range(max_retries):
        try:
            from sqlalchemy import create_engine, text
            
            test_engine = create_engine(database_url, pool_pre_ping=True)
            
            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    logger.info("✅ PostgreSQL is available!")
                    return True
                    
        except Exception as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: PostgreSQL not ready yet ({e})")
            if attempt < max_retries - 1:
                time.sleep(delay)
    
    logger.error("❌ PostgreSQL failed to become available within the expected time")
    return False


def wait_for_dependencies() -> Tuple[bool, str]:
    """Wait for all external dependencies to become available."""
    logger.info("🔍 Waiting for external dependencies...")
    
    if not wait_for_postgres():
        return False, "Failed to connect to PostgreSQL"
    
    logger.info("✅ All external dependencies are available!")
    return True, ""