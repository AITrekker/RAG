"""
Basic database initialization container.
"""

import os
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Initialize database with basic tables."""
    logger.info("🚀 Starting database initialization...")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        return False
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            
            # Create tenants table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tenants (
                    slug VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    api_key VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create files table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS files (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_slug VARCHAR(255) REFERENCES tenants(slug) ON DELETE CASCADE,
                    filename VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    file_size BIGINT,
                    file_hash VARCHAR(64),
                    sync_status VARCHAR(50) DEFAULT 'pending',
                    sync_error TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    sync_completed_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(tenant_slug, file_path)
                )
            """))
            
            # Create embedding_chunks table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS embedding_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
                    tenant_slug VARCHAR(255) REFERENCES tenants(slug) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding vector(384),
                    embedding_model VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(file_id, chunk_index)
                )
            """))
            
            conn.commit()
            logger.info("✅ Database tables created successfully")
            
        # Create admin tenant
        admin_slug = os.getenv("ADMIN_TENANT_SLUG", "admin")
        admin_api_key = os.getenv("ADMIN_API_KEY")
        
        if admin_api_key:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT slug FROM tenants WHERE slug = :slug
                """), {"slug": admin_slug})
                
                if not result.fetchone():
                    conn.execute(text("""
                        INSERT INTO tenants (slug, name, api_key)
                        VALUES (:slug, :name, :api_key)
                    """), {
                        "slug": admin_slug,
                        "name": "Admin Tenant",
                        "api_key": admin_api_key
                    })
                    conn.commit()
                    logger.info(f"✅ Created admin tenant: {admin_slug}")
                else:
                    logger.info(f"✅ Admin tenant already exists: {admin_slug}")
        
        logger.info("🎉 Database initialization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)