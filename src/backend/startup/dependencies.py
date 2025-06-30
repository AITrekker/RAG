"""
Dependency verification for backend startup.

Waits for external dependencies to become available before
starting the main application.
"""

import os
import time
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def wait_for_postgres(max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for PostgreSQL to become available."""
    logger.info("Waiting for PostgreSQL to become available...")
    
    # Get database connection details from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        return False
    
    for attempt in range(max_retries):
        try:
            from sqlalchemy import create_engine, text
            
            # Create a test engine
            test_engine = create_engine(database_url, pool_pre_ping=True)
            
            # Test connection
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


def wait_for_qdrant(max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for Qdrant to become available."""
    logger.info("Waiting for Qdrant to become available...")
    
    # Get Qdrant connection details from environment
    qdrant_host = os.getenv("QDRANT_HOST", "qdrant")  # Default to service name for Docker
    qdrant_port = os.getenv("QDRANT_PORT", "6333")
    qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    
    logger.info(f"Connecting to Qdrant at: {qdrant_url}")
    
    for attempt in range(max_retries):
        try:
            import requests
            response = requests.get(f"{qdrant_url}/collections", timeout=5)
            if response.status_code == 200:
                collections = response.json()
                logger.info(f"✅ Qdrant is available! Found {len(collections.get('collections', []))} collections")
                return True
        except Exception as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: Qdrant not ready yet ({e})")
            if attempt < max_retries - 1:
                time.sleep(delay)
    
    logger.error("❌ Qdrant failed to become available within the expected time")
    return False


def wait_for_dependencies() -> Tuple[bool, str]:
    """
    Wait for all external dependencies to become available.
    
    Returns:
        Tuple[bool, str]: (success, error_message)
    """
    logger.info("🔍 Waiting for external dependencies...")
    
    # Wait for PostgreSQL
    if not wait_for_postgres():
        return False, "Failed to connect to PostgreSQL"
    
    # Wait for Qdrant
    if not wait_for_qdrant():
        return False, "Failed to connect to Qdrant"
    
    logger.info("✅ All external dependencies are available!")
    return True, ""