"""Add default API key for development

Revision ID: 002_add_default_api_key
Revises: 5c355f70c792
Create Date: 2025-06-22 11:15:00.000000

# ==============================================================================
# IMPORTANT: This migration seeds essential data for development environments.
#
# It creates:
# 1. Two default tenants: 'tenant1' and 'tenant2'.
# 2. A default, non-expiring API key for 'tenant1'.
#
# NOTE: This script *only* creates tenant records and an API key. It does *not*
# seed any documents or document metadata in the database. This is why health
# checks should verify tenant existence rather than document existence to
# confirm that migrations have run successfully.
# ==============================================================================

"""
from alembic import op
import sqlalchemy as sa
import hashlib
from datetime import datetime, timedelta, timezone

# revision identifiers, used by Alembic.
revision = '002_add_default_api_key'
down_revision = '5c355f70c792'
branch_labels = None
depends_on = None

def upgrade():
    # Get the current time and expiration time
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=365)
    
    # Hash the API key
    api_key = "dev-api-key-123"
    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    # Get connection
    conn = op.get_bind()
    
    # Create tenant1 if it doesn't exist
    result_t1 = conn.execute(sa.text("SELECT id FROM tenants WHERE tenant_id = 'tenant1'")).fetchone()
    if not result_t1:
        conn.execute(sa.text("""
            INSERT INTO tenants (
                id, tenant_id, name, display_name, created_at, updated_at, tier, 
                isolation_level, status, max_documents, max_storage_mb, 
                max_api_calls_per_day, max_concurrent_queries
            ) 
            VALUES (
                gen_random_uuid(), 'tenant1', 'Tenant 1', 'Development Tenant 1', 
                :now, :now, 'basic', 'logical', 'active', 1000, 5000, 10000, 10
            )
        """), {'now': now})

    # Create tenant2 if it doesn't exist
    result_t2 = conn.execute(sa.text("SELECT id FROM tenants WHERE tenant_id = 'tenant2'")).fetchone()
    if not result_t2:
        conn.execute(sa.text("""
            INSERT INTO tenants (
                id, tenant_id, name, display_name, created_at, updated_at, tier, 
                isolation_level, status, max_documents, max_storage_mb, 
                max_api_calls_per_day, max_concurrent_queries
            ) 
            VALUES (
                gen_random_uuid(), 'tenant2', 'Tenant 2', 'Development Tenant 2', 
                :now, :now, 'basic', 'logical', 'active', 1000, 5000, 10000, 10
            )
        """), {'now': now})
    
    # Check if API key already exists for tenant1
    existing_key = conn.execute(sa.text("""
        SELECT id FROM tenant_api_keys 
        WHERE tenant_id = 'tenant1' AND key_name = 'Default Dev Key'
    """)).fetchone()
    
    if not existing_key:
        # Insert the new API key for tenant1
        conn.execute(sa.text("""
            INSERT INTO tenant_api_keys (
                id, tenant_id, key_name, key_hash, key_prefix, scopes, 
                created_at, updated_at, expires_at, is_active, usage_count
            ) VALUES (
                gen_random_uuid(), 'tenant1', 'Default Dev Key', :key_hash, 'dev-api', 
                '{}', :now, :now, :expires_at, true, 0
            )
        """), {
            "key_hash": key_hash,
            "now": now,
            "expires_at": expires_at
        })

def downgrade():
    # Get connection
    conn = op.get_bind()

    # First, delete the API key associated with tenant1
    conn.execute(sa.text("""
        DELETE FROM tenant_api_keys 
        WHERE tenant_id = 'tenant1' AND key_name = 'Default Dev Key'
    """))

    # Now, it's safe to delete the tenants
    conn.execute(sa.text("DELETE FROM tenants WHERE tenant_id IN ('tenant1', 'tenant2')")) 