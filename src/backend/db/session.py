from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from ..config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

try:
    # Configure PostgreSQL-specific engine settings
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_recycle": 3600,  # Recycle connections every hour
        "echo": settings.debug,  # Log SQL queries in debug mode
    }
    
    engine = create_engine(settings.database_url, **engine_kwargs)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine and session created successfully.")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}", exc_info=True)
    # Exit or handle gracefully if the database is critical for startup
    # For now, we'll let it raise, so it's visible on startup
    raise

def get_db() -> Session:
    """
    FastAPI dependency that provides a SQLAlchemy database session.
    
    Ensures the session is always closed after the request, even if errors occur.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 