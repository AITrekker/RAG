"""Add default API key for development

Revision ID: 002_add_default_api_key
Revises: 5c355f70c792
Create Date: 2025-06-22 11:15:00.000000

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
    
    # First, create default tenant if it doesn't exist
    result = conn.execute(sa.text("SELECT tenant_id FROM tenants WHERE tenant_id = 'default'")).fetchone()
    if not result:
        # Create default tenant
        conn.execute(sa.text("""
            INSERT INTO tenants (
                id, tenant_id, name, display_name, tier, isolation_level, status,
                created_at, updated_at, max_documents, max_storage_mb,
                max_api_calls_per_day, max_concurrent_queries, contact_email
            ) VALUES (
                gen_random_uuid(), 'default', 'Default Tenant', 'Default Development Tenant', 
                'basic', 'logical', 'active', :now, :now, 1000, 5000, 10000, 10, 'dev@example.com'
            )
        """), {"now": now})
    
    # Check if API key already exists
    existing_key = conn.execute(sa.text("""
        SELECT id FROM tenant_api_keys 
        WHERE tenant_id = 'default'
    """)).fetchone()
    
    if not existing_key:
        # Insert the new API key
        conn.execute(sa.text("""
            INSERT INTO tenant_api_keys (
                id, tenant_id, key_name, key_hash, key_prefix, scopes, 
                created_at, updated_at, expires_at, is_active, usage_count
            ) VALUES (
                gen_random_uuid(), 'default', 'Default Dev Key', :key_hash, 'dev-api', 
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
    
    # Delete the API key
    conn.execute(sa.text("DELETE FROM tenant_api_keys WHERE key_name = 'Default Dev Key'"))
    
    # Optionally delete the default tenant if it was created by this migration
    # (commented out to be safe - you may want to keep the tenant)
    # conn.execute(sa.text("DELETE FROM tenants WHERE tenant_id = 'default'")) 