-- =============================================
-- RAG Platform Database Schema
-- PostgreSQL + Qdrant Hybrid Architecture
-- =============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- TENANTS & USERS
-- =============================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL, -- URL-safe identifier
    plan_tier VARCHAR(50) NOT NULL DEFAULT 'free', -- free, pro, enterprise
    storage_limit_gb INTEGER DEFAULT 10,
    max_users INTEGER DEFAULT 5,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    
    -- Additional tenant fields
    description TEXT,
    auto_sync BOOLEAN DEFAULT true,
    sync_interval INTEGER DEFAULT 60,
    status VARCHAR(50) DEFAULT 'active',
    
    -- API Key Authentication
    api_key VARCHAR(64) UNIQUE,
    api_key_hash VARCHAR(64),
    api_key_name VARCHAR(100),
    api_key_expires_at TIMESTAMP WITH TIME ZONE,
    api_key_last_used TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE tenant_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member', -- owner, admin, member, viewer
    permissions JSONB DEFAULT '{}', -- granular permissions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, user_id)
);

-- =============================================
-- FILE MANAGEMENT & SYNC
-- =============================================

CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL, -- relative to tenant uploads directory
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for change detection
    content_hash VARCHAR(64), -- Hash of processed content (for text extraction changes)
    
    -- Sync Status
    sync_status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, synced, failed, deleted
    sync_started_at TIMESTAMP WITH TIME ZONE,
    sync_completed_at TIMESTAMP WITH TIME ZONE,
    sync_error TEXT,
    sync_retry_count INTEGER DEFAULT 0,
    
    -- File Metadata
    word_count INTEGER,
    page_count INTEGER,
    language VARCHAR(10),
    extraction_method VARCHAR(50), -- pdf, docx, plaintext, etc.
    
    -- Lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE, -- soft delete
    
    -- Constraints
    UNIQUE(tenant_id, file_path),
    CHECK (file_size > 0),
    CHECK (sync_status IN ('pending', 'processing', 'synced', 'failed', 'deleted'))
);

CREATE TABLE embedding_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Chunk Information
    chunk_index INTEGER NOT NULL, -- 0-based index within file
    chunk_content TEXT NOT NULL,
    chunk_hash VARCHAR(64) NOT NULL, -- SHA-256 of chunk content
    token_count INTEGER,
    
    -- Vector Store Reference
    qdrant_point_id UUID NOT NULL, -- References point in Qdrant
    collection_name VARCHAR(100) NOT NULL, -- tenant_{tenant_id}_documents
    
    -- Processing Metadata
    embedding_model VARCHAR(100) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(file_id, chunk_index),
    UNIQUE(qdrant_point_id),
    CHECK (chunk_index >= 0),
    CHECK (token_count > 0)
);

-- =============================================
-- ACCESS CONTROL & SHARING
-- =============================================

CREATE TABLE file_access_control (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- NULL = tenant-wide access
    access_type VARCHAR(20) NOT NULL DEFAULT 'read', -- read, write, admin
    granted_by UUID NOT NULL REFERENCES users(id),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(file_id, user_id)
);

CREATE TABLE file_sharing_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    share_token VARCHAR(64) UNIQUE NOT NULL,
    access_type VARCHAR(20) NOT NULL DEFAULT 'read',
    created_by UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMP WITH TIME ZONE,
    max_uses INTEGER,
    current_uses INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- =============================================
-- SYNC TRACKING & AUDIT
-- =============================================

CREATE TABLE sync_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    operation_type VARCHAR(20) NOT NULL, -- full_sync, delta_sync, file_sync
    triggered_by UUID REFERENCES users(id), -- NULL for automated syncs
    
    -- Operation Status
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- running, completed, failed, cancelled
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Statistics
    files_processed INTEGER DEFAULT 0,
    files_added INTEGER DEFAULT 0,
    files_updated INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    chunks_updated INTEGER DEFAULT 0,
    chunks_deleted INTEGER DEFAULT 0,
    
    -- Error Tracking
    error_message TEXT,
    error_details JSONB,
    
    CHECK (status IN ('running', 'completed', 'failed', 'cancelled'))
);

CREATE TABLE file_sync_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    sync_operation_id UUID REFERENCES sync_operations(id) ON DELETE SET NULL,
    
    -- Change Detection
    previous_hash VARCHAR(64),
    new_hash VARCHAR(64) NOT NULL,
    change_type VARCHAR(20) NOT NULL, -- created, updated, deleted, renamed
    
    -- Processing Results
    chunks_before INTEGER DEFAULT 0,
    chunks_after INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CHECK (change_type IN ('created', 'updated', 'deleted', 'renamed'))
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Tenant isolation (most critical)
CREATE INDEX idx_files_tenant_id ON files(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_chunks_tenant_id ON embedding_chunks(tenant_id);
CREATE INDEX idx_memberships_tenant_id ON tenant_memberships(tenant_id);

-- Delta sync performance
CREATE INDEX idx_files_sync_status ON files(sync_status, updated_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_files_hash_lookup ON files(tenant_id, file_hash) WHERE deleted_at IS NULL;
CREATE INDEX idx_files_path_lookup ON files(tenant_id, file_path) WHERE deleted_at IS NULL;

-- Access control queries
CREATE INDEX idx_file_access_user ON file_access_control(user_id, access_type);
CREATE INDEX idx_file_access_file ON file_access_control(file_id, access_type);

-- Query performance
CREATE INDEX idx_chunks_file_id ON embedding_chunks(file_id, chunk_index);
CREATE INDEX idx_qdrant_point_lookup ON embedding_chunks(qdrant_point_id);

-- Audit and monitoring
CREATE INDEX idx_sync_operations_tenant ON sync_operations(tenant_id, started_at DESC);
CREATE INDEX idx_sync_history_file ON file_sync_history(file_id, synced_at DESC);

-- User and tenant lookups
CREATE INDEX idx_users_email ON users(email) WHERE is_active = true;
CREATE INDEX idx_tenants_slug ON tenants(slug) WHERE is_active = true;

-- =============================================
-- INSERT DEMO DATA (for development)
-- =============================================

-- Insert sample tenants
INSERT INTO tenants (name, slug, plan_tier) VALUES 
    ('Acme Corp', 'acme-corp', 'pro'),
    ('Tech Startup', 'tech-startup', 'free'),
    ('Enterprise Client', 'enterprise-client', 'enterprise');

-- Insert sample users
INSERT INTO users (email, password_hash, full_name) VALUES 
    ('admin@acme.com', '$2b$12$dummy_hash_replace_in_production', 'Admin User'),
    ('user@techstartup.com', '$2b$12$dummy_hash_replace_in_production', 'Startup User'),
    ('manager@enterprise.com', '$2b$12$dummy_hash_replace_in_production', 'Enterprise Manager');

-- Create tenant memberships
INSERT INTO tenant_memberships (tenant_id, user_id, role) 
SELECT 
    t.id,
    u.id,
    CASE 
        WHEN u.email LIKE '%admin%' THEN 'owner'
        WHEN u.email LIKE '%manager%' THEN 'admin'
        ELSE 'member'
    END
FROM tenants t
CROSS JOIN users u
WHERE 
    (t.slug = 'acme-corp' AND u.email = 'admin@acme.com') OR
    (t.slug = 'tech-startup' AND u.email = 'user@techstartup.com') OR
    (t.slug = 'enterprise-client' AND u.email = 'manager@enterprise.com');