"""
Init container script for database setup and admin tenant seeding.
Handles database tables, admin tenant creation, and credential management.
"""

import os
import sys
import json
import logging
import secrets
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_database_tables(engine) -> bool:
    """Create database tables if they don't exist."""
    logger.info("🗄️ Creating database tables...")
    
    try:
        with engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            
            # Create tenants table (simplified slug-based schema)
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
                    UNIQUE(tenant_slug, file_path),
                    CHECK(sync_status IN ('pending', 'processing', 'synced', 'failed', 'deleted'))
                )
            """))
            
            # Create embedding_chunks table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS embedding_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
                    tenant_slug VARCHAR(255) REFERENCES tenants(slug) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    chunk_content TEXT NOT NULL,
                    chunk_hash VARCHAR(64) NOT NULL,
                    token_count INTEGER,
                    embedding vector(384),
                    embedding_model VARCHAR(255) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
                    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(file_id, chunk_index)
                )
            """))
            
            # Create index on embeddings for fast search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_embedding_chunks_embedding 
                ON embedding_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """))
            
            conn.commit()
            logger.info("✅ Database tables created successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        return False


def setup_admin_tenant(engine) -> bool:
    """Setup admin tenant with fresh API key and credential management."""
    logger.info("👤 Setting up admin tenant...")
    
    try:
        admin_slug = "admin"
        
        # Always generate a fresh admin API key for security
        logger.info("🔑 Generating fresh admin API key...")
        admin_api_key = f"tenant_admin_{secrets.token_hex(20)}"
        
        with engine.connect() as conn:
            # Check if admin tenant exists
            result = conn.execute(text("""
                SELECT slug, api_key FROM tenants WHERE slug = :slug
            """), {"slug": admin_slug})
            
            existing_admin = result.fetchone()
            
            if existing_admin:
                # Update existing admin tenant with new API key
                logger.info("🔄 Updating existing admin tenant with fresh API key...")
                conn.execute(text("""
                    UPDATE tenants 
                    SET api_key = :api_key, updated_at = NOW()
                    WHERE slug = :slug
                """), {
                    "slug": admin_slug,
                    "api_key": admin_api_key
                })
                logger.info("✅ Admin tenant API key updated")
            else:
                # Create new admin tenant
                logger.info("🏗️ Creating new admin tenant...")
                conn.execute(text("""
                    INSERT INTO tenants (slug, name, api_key)
                    VALUES (:slug, :name, :api_key)
                """), {
                    "slug": admin_slug,
                    "name": "Admin Tenant",
                    "api_key": admin_api_key
                })
                logger.info("✅ Admin tenant created")
            
            conn.commit()
        
        # Update .env file with admin credentials
        update_env_file(admin_slug, admin_api_key)
        
        # Write admin config JSON for frontend
        write_admin_config_json(admin_slug, admin_api_key)
        
        logger.info("🎉 Admin tenant setup completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to setup admin tenant: {e}")
        return False


def update_env_file(admin_slug: str, admin_api_key: str) -> None:
    """Update .env file with admin credentials."""
    env_file = Path(".env")
    
    if not env_file.exists():
        logger.warning("⚠️ .env file not found, skipping credential update")
        return
    
    try:
        # Read current .env content
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Remove existing admin credentials
        cleaned_lines = []
        skip_next_empty = False
        
        for line in lines:
            if (line.strip().startswith('ADMIN_TENANT_SLUG=') or 
                line.strip().startswith('ADMIN_API_KEY=') or
                line.strip().startswith('RAG_ENVIRONMENT=')):
                continue
            elif line.strip() == '# Admin credentials (auto-generated)':
                skip_next_empty = True
                continue
            elif skip_next_empty and line.strip() == '':
                skip_next_empty = False
                continue
            else:
                cleaned_lines.append(line)
                skip_next_empty = False
        
        # Add new admin credentials at the end
        if cleaned_lines and not cleaned_lines[-1].endswith('\n'):
            cleaned_lines.append('\n')
        
        environment = os.getenv("RAG_ENVIRONMENT", "development")
        
        cleaned_lines.extend([
            '# Admin credentials (auto-generated)\n',
            f'ADMIN_TENANT_SLUG={admin_slug}\n',
            f'ADMIN_API_KEY={admin_api_key}\n',
            f'RAG_ENVIRONMENT={environment}\n'
        ])
        
        # Write updated content
        with open(env_file, 'w') as f:
            f.writelines(cleaned_lines)
        
        logger.info("✅ Admin credentials saved to .env file")
        
    except Exception as e:
        logger.error(f"❌ Failed to update .env file: {e}")


def write_admin_config_json(admin_slug: str, admin_api_key: str) -> None:
    """Write admin configuration to JSON file for frontend access."""
    admin_config = {
        "admin_tenant_slug": admin_slug,
        "admin_api_key": admin_api_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "init_container"
    }
    
    config_file = Path("demo_admin_keys.json")
    
    try:
        with open(config_file, 'w') as f:
            json.dump(admin_config, f, indent=2)
        logger.info("✅ Admin configuration saved to demo_admin_keys.json")
        
        # Simple approach - just log that we wrote to project root
        logger.info("✅ Admin configuration will be available via volume mount")
            
    except Exception as e:
        logger.error(f"❌ Failed to write admin config JSON: {e}")


def setup_demo_tenants(engine) -> bool:
    """Setup demo tenants for development."""
    logger.info("🏢 Setting up demo tenants...")
    
    # Demo tenant configurations
    demo_tenants = {
        "tenant1": {"name": "tenant1 with company documents (development)"},
        "tenant2": {"name": "tenant2 with company documents (development)"},
        "tenant3": {"name": "tenant3 with company documents (development)"}
    }
    
    tenant_keys = {}
    
    try:
        with engine.connect() as conn:
            for tenant_slug, tenant_data in demo_tenants.items():
                # Generate API key for this tenant
                api_key = f"tenant_{tenant_slug}_{secrets.token_hex(16)}"
                
                # Check if tenant exists
                result = conn.execute(text("""
                    SELECT slug FROM tenants WHERE slug = :slug
                """), {"slug": tenant_slug})
                
                existing_tenant = result.fetchone()
                
                if existing_tenant:
                    # Update existing tenant with new API key
                    logger.info(f"🔄 Updating demo tenant: {tenant_slug}")
                    conn.execute(text("""
                        UPDATE tenants 
                        SET api_key = :api_key, updated_at = NOW()
                        WHERE slug = :slug
                    """), {
                        "slug": tenant_slug,
                        "api_key": api_key
                    })
                else:
                    # Create new tenant
                    logger.info(f"🏗️ Creating demo tenant: {tenant_slug}")
                    conn.execute(text("""
                        INSERT INTO tenants (slug, name, api_key)
                        VALUES (:slug, :name, :api_key)
                    """), {
                        "slug": tenant_slug,
                        "name": tenant_data["name"],
                        "api_key": api_key
                    })
                
                # Store for keys file
                tenant_keys[tenant_slug] = {
                    "api_key": api_key,
                    "slug": tenant_slug,
                    "description": f"Demo {tenant_data['name']}"
                }
            
            conn.commit()
        
        # Write tenant keys to JSON file
        write_demo_tenant_keys(tenant_keys)
        
        logger.info(f"✅ Setup {len(demo_tenants)} demo tenants successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to setup demo tenants: {e}")
        return False


def write_demo_tenant_keys(tenant_keys: dict) -> None:
    """Write demo tenant keys to JSON file for frontend access."""
    config_file = Path("demo_tenant_keys.json")
    
    try:
        with open(config_file, 'w') as f:
            json.dump(tenant_keys, f, indent=2)
        logger.info("✅ Demo tenant keys saved to demo_tenant_keys.json")
        
        # Simple approach - just log that we wrote to project root  
        logger.info("✅ Demo tenant keys will be available via volume mount")
            
    except Exception as e:
        logger.error(f"❌ Failed to write demo tenant keys: {e}")


def main():
    """Main init container function."""
    logger.info("🚀 Starting database and admin tenant initialization...")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL not set")
        sys.exit(1)
    
    try:
        # Create database engine
        engine = create_engine(database_url)
        
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
        
        # Step 1: Create database tables
        if not create_database_tables(engine):
            logger.error("❌ Database table creation failed")
            sys.exit(1)
        
        # Step 2: Setup admin tenant
        if not setup_admin_tenant(engine):
            logger.error("❌ Admin tenant setup failed")
            sys.exit(1)
        
        # Step 3: Setup demo tenants for development
        if not setup_demo_tenants(engine):
            logger.error("❌ Demo tenant setup failed")
            sys.exit(1)
        
        logger.info("🎉 Init container completed successfully!")
        logger.info("💡 Backend container can now start safely")
        
    except Exception as e:
        logger.error(f"❌ Init container failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()