"""Initial production schema with indexes and constraints

Revision ID: 001_initial_production_schema
Revises: 
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_production_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial production-ready database schema."""
    
    # Create enum types
    op.execute("CREATE TYPE tenant_status AS ENUM ('active', 'inactive', 'suspended', 'pending')")
    op.execute("CREATE TYPE document_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'archived')")
    op.execute("CREATE TYPE sync_status AS ENUM ('pending', 'in_progress', 'completed', 'failed')")
    
    # Create tenants table
    op.create_table('tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('tier', sa.String(length=20), nullable=False),
        sa.Column('isolation_level', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_documents', sa.Integer(), nullable=False),
        sa.Column('max_storage_mb', sa.Integer(), nullable=False),
        sa.Column('max_api_calls_per_day', sa.Integer(), nullable=False),
        sa.Column('max_concurrent_queries', sa.Integer(), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('billing_email', sa.String(length=255), nullable=True),
        sa.Column('custom_config', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id')
    )
    
    # Create indexes for tenants
    op.create_index('ix_tenants_tenant_id', 'tenants', ['tenant_id'])
    op.create_index('ix_tenants_status', 'tenants', ['status'])
    op.create_index('ix_tenants_tier', 'tenants', ['tier'])
    op.create_index('ix_tenants_created_at', 'tenants', ['created_at'])
    
    # Create tenant_usage_stats table
    op.create_table('tenant_usage_stats',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('documents_processed', sa.Integer(), nullable=False),
        sa.Column('api_calls_made', sa.Integer(), nullable=False),
        sa.Column('storage_used_mb', sa.Float(), nullable=False),
        sa.Column('queries_executed', sa.Integer(), nullable=False),
        sa.Column('avg_query_time_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for usage stats
    op.create_index('ix_tenant_usage_stats_tenant_id', 'tenant_usage_stats', ['tenant_id'])
    op.create_index('ix_tenant_usage_stats_period', 'tenant_usage_stats', ['period_start', 'period_end'])
    
    # Create tenant_api_keys table
    op.create_table('tenant_api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_name', sa.String(length=255), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=8), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    
    # Create indexes for API keys
    op.create_index('ix_tenant_api_keys_tenant_id', 'tenant_api_keys', ['tenant_id'])
    op.create_index('ix_tenant_api_keys_key_prefix', 'tenant_api_keys', ['key_prefix'])
    op.create_index('ix_tenant_api_keys_is_active', 'tenant_api_keys', ['is_active'])
    
    # Create documents table
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('mime_type', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('processing_metadata', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'file_path', 'version', name='uq_tenant_file_version')
    )
    
    # Create indexes for documents
    op.create_index('ix_documents_tenant_id', 'documents', ['tenant_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_file_hash', 'documents', ['file_hash'])
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])
    op.create_index('ix_documents_tenant_status', 'documents', ['tenant_id', 'status'])
    
    # Create document_chunks table
    op.create_table('document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('embedding_vector', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunk_index')
    )
    
    # Create indexes for chunks
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('ix_document_chunks_tenant_id', 'document_chunks', ['tenant_id'])
    op.create_index('ix_document_chunks_token_count', 'document_chunks', ['token_count'])
    
    # Create sync_events table
    op.create_table('sync_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_run_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for sync events
    op.create_index('ix_sync_events_id', 'sync_events', ['id'])
    op.create_index('ix_sync_events_sync_run_id', 'sync_events', ['sync_run_id'])
    op.create_index('ix_sync_events_tenant_id', 'sync_events', ['tenant_id'])
    op.create_index('ix_sync_events_timestamp', 'sync_events', ['timestamp'])
    op.create_index('ix_sync_events_tenant_status', 'sync_events', ['tenant_id', 'status'])
    
    # Create performance optimization indexes
    op.create_index('ix_documents_tenant_updated', 'documents', ['tenant_id', 'updated_at'])
    op.create_index('ix_chunks_tenant_created', 'document_chunks', ['tenant_id', 'created_at'])
    
    # Create partial indexes for active records
    op.execute("CREATE INDEX ix_tenants_active ON tenants (tenant_id, status) WHERE status = 'active'")
    op.execute("CREATE INDEX ix_documents_processing ON documents (tenant_id, created_at) WHERE status IN ('pending', 'processing')")
    
    # Add table partitioning preparation (for future scaling)
    op.execute("ALTER TABLE sync_events ADD CONSTRAINT check_tenant_id_length CHECK (length(tenant_id) > 0)")
    op.execute("ALTER TABLE documents ADD CONSTRAINT check_file_size_positive CHECK (file_size > 0)")
    op.execute("ALTER TABLE document_chunks ADD CONSTRAINT check_token_count_positive CHECK (token_count > 0)")
    

def downgrade() -> None:
    """Drop all tables and types."""
    op.drop_table('sync_events')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('tenant_api_keys')
    op.drop_table('tenant_usage_stats')
    op.drop_table('tenants')
    
    op.execute("DROP TYPE IF EXISTS sync_status")
    op.execute("DROP TYPE IF EXISTS document_status") 
    op.execute("DROP TYPE IF EXISTS tenant_status") 