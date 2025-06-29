"""
Database configuration and connection management
"""

import os
from typing import AsyncGenerator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.backend.models.database import Base
from src.backend.config.settings import get_settings

settings = get_settings()

# =============================================
# DATABASE ENGINES
# =============================================

# Sync engine for migrations and admin tasks
sync_engine = create_engine(
    settings.database_url.replace("postgresql://", "postgresql://", 1),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    echo=settings.debug
)

# Async engine for application usage
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    echo=settings.debug
)

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# =============================================
# DATABASE UTILITIES
# =============================================

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=sync_engine)

def drop_tables():
    """Drop all database tables"""
    Base.metadata.drop_all(bind=sync_engine)

def get_sync_db() -> Session:
    """Get synchronous database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# =============================================
# DATABASE INITIALIZATION
# =============================================

async def init_database():
    """Initialize database with tables and initial data"""
    # Create tables if they don't exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database initialized successfully")

async def close_database():
    """Close database connections"""
    await async_engine.dispose()
    sync_engine.dispose()
    print("✅ Database connections closed")

# =============================================
# DATABASE HEALTH CHECK
# =============================================

async def check_database_health() -> bool:
    """Check if database is healthy"""
    try:
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"❌ Database health check failed: {e}")
        return False

# =============================================
# TRANSACTION HELPERS
# =============================================

async def run_in_transaction(func, *args, **kwargs):
    """Run function in database transaction"""
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                result = await func(session, *args, **kwargs)
                await session.commit()
                return result
        except Exception as e:
            await session.rollback()
            raise e

# =============================================
# DEVELOPMENT HELPERS
# =============================================

def reset_database():
    """Reset database for development (DANGEROUS!)"""
    if not settings.debug:
        raise ValueError("Database reset only allowed in debug mode")
    
    print("⚠️  Dropping all tables...")
    drop_tables()
    print("🔄 Creating tables...")
    create_tables()
    print("✅ Database reset complete")

# =============================================
# EVENT LISTENERS
# =============================================

@event.listens_for(sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance (if using SQLite)"""
    if 'sqlite' in settings.database_url:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# =============================================
# STARTUP CHECKS
# =============================================

async def startup_database_checks():
    """Perform startup database checks"""
    print("🔍 Running database startup checks...")
    
    # Check connection
    is_healthy = await check_database_health()
    if not is_healthy:
        raise RuntimeError("Database connection failed")
    
    # Initialize if needed
    await init_database()
    
    print("✅ Database startup checks completed")