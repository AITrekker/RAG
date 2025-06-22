-- Create API key for default tenant
-- Run this with: docker exec -i rag_postgres psql -U rag_user -d rag_database < scripts/create_api_key.sql

-- First, let's see what we have
\echo 'Current tenants:'
SELECT id, tenant_id, name, status FROM tenants;

\echo 'Current API keys:'
SELECT id, tenant_id, key_name, key_prefix, is_active FROM tenant_api_keys;

-- Insert the API key for the default tenant
\echo 'Creating API key...'
INSERT INTO tenant_api_keys (
    id, tenant_id, key_name, key_hash, key_prefix, scopes, 
    created_at, updated_at, expires_at, is_active, usage_count
) VALUES (
    gen_random_uuid(), 
    (SELECT id FROM tenants WHERE tenant_id = 'default'), 
    'Default Dev Key', 
    '0e32c8eba3a7bb06c44ce30244e5bd72b28508c4ebba4f4fbc0e2e55c388afda', -- SHA256 of 'dev-api-key-123'
    'dev-api', 
    '{}', 
    NOW(), 
    NOW(), 
    NOW() + INTERVAL '1 year', 
    true, 
    0
) ON CONFLICT (key_hash) DO NOTHING;

\echo 'API key creation completed.'

-- Verify the result
\echo 'Final API keys:'
SELECT id, tenant_id, key_name, key_prefix, is_active FROM tenant_api_keys;

\echo 'You can now use the API key: dev-api-key-123' 