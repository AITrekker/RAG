from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from ..config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

try:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
    )
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