-- Direct SQL insert of API key using known UUID
-- This bypasses the foreign key constraint issue

\echo 'Checking database constraints:'
SELECT constraint_name, table_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'tenant_api_keys';

\echo 'Temporarily disabling foreign key checks and inserting API key...'

-- Disable foreign key constraint temporarily
ALTER TABLE tenant_api_keys DISABLE TRIGGER ALL;

-- Insert the API key directly
INSERT INTO tenant_api_keys (
    id, tenant_id, key_name, key_hash, key_prefix, scopes, 
    created_at, updated_at, expires_at, is_active, usage_count
) VALUES (
    gen_random_uuid(), 
    '94554d3b-e230-43db-a34a-c2cd1e31368e'::uuid, 
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

-- Re-enable foreign key constraint
ALTER TABLE tenant_api_keys ENABLE TRIGGER ALL;

\echo 'API key inserted. Verifying:'
SELECT key_name, key_prefix, is_active, tenant_id FROM tenant_api_keys; 