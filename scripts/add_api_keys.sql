-- Add API key fields to tenants table
-- Run this migration to add API key authentication support

-- Add API key columns to tenants table
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS api_key VARCHAR(64) UNIQUE;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS api_key_name VARCHAR(100);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS api_key_expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS api_key_last_used TIMESTAMP WITH TIME ZONE;

-- Create index for fast API key lookups
CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key) WHERE api_key IS NOT NULL;

-- Generate API keys for existing demo tenants
UPDATE tenants SET 
    api_key = 'tenant_' || slug || '_' || encode(gen_random_bytes(16), 'hex'),
    api_key_name = 'Development Key'
WHERE api_key IS NULL;

-- Show the generated API keys for reference
SELECT name, slug, api_key, api_key_name FROM tenants WHERE api_key IS NOT NULL;