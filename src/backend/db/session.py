from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from ..config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

try:
    # Get production-ready database configuration
    db_config = settings.get_database_config()
    
    # Configure PostgreSQL-specific engine settings
    engine_kwargs = {
        "pool_pre_ping": db_config["pool_pre_ping"],
        "pool_size": db_config["pool_size"],
        "max_overflow": db_config["max_overflow"],
        "pool_recycle": db_config["pool_recycle"],
        "pool_timeout": db_config["pool_timeout"],
        "connect_args": db_config["connect_args"],
        "echo": settings.debug,  # Log SQL queries in debug mode
    }
    
    engine = create_engine(db_config["url"], **engine_kwargs)
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