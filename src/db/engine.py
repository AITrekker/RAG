"""
Database engine and connection management for Enterprise RAG Pipeline.

This module handles SQLAlchemy engine creation, session management,
and database initialization with tenant support.
"""

from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Optional, Generator
import logging
from contextlib import contextmanager

from ..config import get_settings
from .models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None

def create_database_engine() -> Engine:
    """
    Create and configure database engine based on settings.
    
    Returns:
        Configured SQLAlchemy engine
    """
    settings = get_settings()
    database_url = settings.database.database_url
    
    logger.info(f"Creating database engine for: {database_url.split('@')[0]}@***")
    
    # Engine configuration based on database type
    if settings.database.type == "sqlite":
        engine = create_engine(
            database_url,
            echo=settings.database.sqlite_echo,
            check_same_thread=settings.database.sqlite_check_same_thread,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
    elif settings.database.type == "postgresql":
        engine = create_engine(
            database_url,
            echo=settings.database.postgresql_echo,
            pool_size=settings.database.postgresql_pool_size,
            max_overflow=settings.database.postgresql_max_overflow,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections every hour
        )
    else:
        raise ValueError(f"Unsupported database type: {settings.database.type}")
    
    # Add event listeners for connection management
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set SQLite pragmas for better performance and reliability."""
        if settings.database.type == "sqlite":
            cursor = dbapi_connection.cursor()
            # Enable foreign key support
            cursor.execute("PRAGMA foreign_keys=ON")
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            # Set synchronous mode for better performance
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    
    @event.listens_for(engine, "before_cursor_execute")
    def log_sql_queries(conn, cursor, statement, parameters, context, executemany):
        """Log SQL queries in debug mode."""
        if settings.app.debug and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"SQL: {statement}")
            if parameters:
                logger.debug(f"Parameters: {parameters}")
    
    return engine

def get_engine() -> Engine:
    """
    Get or create the global database engine.
    
    Returns:
        Database engine instance
    """
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine

def get_session_factory() -> sessionmaker:
    """
    Get or create the global session factory.
    
    Returns:
        Session factory
    """
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    return _session_factory

def create_tables() -> None:
    """
    Create all database tables.
    """
    engine = get_engine()
    logger.info("Creating database tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

def drop_tables() -> None:
    """
    Drop all database tables.
    Warning: This will delete all data!
    """
    engine = get_engine()
    logger.warning("Dropping all database tables")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")

def reset_database() -> None:
    """
    Reset database by dropping and recreating all tables.
    Warning: This will delete all data!
    """
    logger.warning("Resetting database - all data will be lost")
    drop_tables()
    create_tables()
    logger.info("Database reset completed")

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Yields:
        Database session
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.
    
    Yields:
        Database session
    """
    with get_db_session() as session:
        yield session

class TenantAwareSession:
    """
    Wrapper for database session with tenant context.
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def query(self, model):
        """
        Create query with automatic tenant filtering.
        
        Args:
            model: SQLAlchemy model class
            
        Returns:
            Query with tenant filter applied
        """
        from .models import TenantMixin
        
        query = self.session.query(model)
        
        # Add tenant filter if model supports it
        if hasattr(model, 'tenant_id') and issubclass(model, TenantMixin):
            query = query.filter(model.tenant_id == self.tenant_id)
        
        return query
    
    def add(self, instance):
        """
        Add instance with tenant ID set.
        
        Args:
            instance: Model instance to add
        """
        from .models import TenantMixin
        
        # Set tenant ID if model supports it
        if hasattr(instance, 'tenant_id') and isinstance(instance, TenantMixin):
            instance.tenant_id = self.tenant_id
        
        self.session.add(instance)
    
    def commit(self):
        """Commit the session."""
        self.session.commit()
    
    def rollback(self):
        """Rollback the session."""
        self.session.rollback()
    
    def close(self):
        """Close the session."""
        self.session.close()

@contextmanager
def get_tenant_session(tenant_id: str) -> Generator[TenantAwareSession, None, None]:
    """
    Get tenant-aware database session.
    
    Args:
        tenant_id: Tenant identifier
        
    Yields:
        Tenant-aware session
    """
    with get_db_session() as session:
        tenant_session = TenantAwareSession(session, tenant_id)
        try:
            yield tenant_session
        except Exception as e:
            tenant_session.rollback()
            logger.error(f"Tenant session error for {tenant_id}: {e}")
            raise

def init_database() -> None:
    """
    Initialize database with tables and default data.
    """
    logger.info("Initializing database")
    
    # Create tables
    create_tables()
    
    # Create default tenant if none exists
    with get_db_session() as session:
        from .models import Tenant
        
        existing_tenant = session.query(Tenant).first()
        if not existing_tenant:
            logger.info("Creating default tenant")
            default_tenant = Tenant(
                id="tenant1",
                name="tenant1",
                display_name="Default Tenant",
                description="Default tenant for single-tenant deployment",
                source_folder_path="./data/master",
                processed_folder_path="./data/sync"
            )
            session.add(default_tenant)
            session.commit()
            logger.info("Default tenant created")
    
    logger.info("Database initialization completed")

def check_database_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        with get_db_session() as session:
            # Simple query to test connection
            session.execute("SELECT 1")
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def close_database_connections() -> None:
    """
    Close all database connections and clean up.
    """
    global _engine, _session_factory
    
    if _engine:
        logger.info("Closing database connections")
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")

# Export commonly used functions
__all__ = [
    "create_database_engine",
    "get_engine",
    "get_session_factory", 
    "create_tables",
    "drop_tables",
    "reset_database",
    "get_db_session",
    "get_db",
    "TenantAwareSession",
    "get_tenant_session",
    "init_database",
    "check_database_connection",
    "close_database_connections",
] 