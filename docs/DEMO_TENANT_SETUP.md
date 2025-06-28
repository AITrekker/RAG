# Demo Tenant Setup Guide

This guide explains how to create and manage demo tenants for the Enterprise RAG Platform.

## Overview

Demo tenants are pre-configured tenant environments designed for testing, demonstrations, and development purposes. They can be created with sample data, API keys, and configured to match your `/data/tenants` folder structure.

## Quick Start

### Option 1: Default Demo Setup (Recommended)

The fastest way to create demo tenants that match your data folder structure:

```bash
# Creates tenant1, tenant2, tenant3 with API keys
python scripts/api-demo.py --setup-default
```

This command will:
- Create tenants named `tenant1`, `tenant2`, `tenant3`
- Generate API keys for each tenant
- Save API keys to `demo_tenant_keys.json`
- Set up document collections in Qdrant
- Configure 24-hour demo duration

### Option 2: Custom Demo Setup

For custom tenant configurations:

```bash
# Custom demo tenants with specific duration
python scripts/api-demo.py --setup --demo-tenants "custom1,custom2" --duration 48

# Setup without API keys
python scripts/api-demo.py --setup --demo-tenants "tenant1,tenant2" --no-api-keys
```

## Available Scripts

### Primary Demo Management Script

**`scripts/api-demo.py`** - Main demo tenant management tool

#### Commands:

```bash
# Setup default demo tenants (tenant1, tenant2, tenant3)
python scripts/api-demo.py --setup-default

# Setup custom demo tenants
python scripts/api-demo.py --setup --demo-tenants "tenant_1,tenant_2" --duration 24

# List all demo tenants
python scripts/api-demo.py --list

# Cleanup demo environment
python scripts/api-demo.py --cleanup
```

#### Parameters:

- `--demo-tenants`: Comma-separated list of tenant names
- `--duration`: Demo duration in hours (default: 24)
- `--generate-api-keys`: Generate API keys (default: true)
- `--no-api-keys`: Skip API key generation

### Individual Tenant Management

**`scripts/api-tenant.py`** - Individual tenant operations

```bash
# Create individual tenant
python scripts/api-tenant.py --create --name "Demo Company" --description "Demo tenant"

# Create API key for existing tenant
python scripts/api-tenant.py --create-key --tenant-id "tenant_123" --key-name "Demo Key"

# List all tenants (including demo tenants)
python scripts/api-tenant.py --list

# List only demo tenants
python scripts/api-tenant.py --list --demo-only

# Get tenant details
python scripts/api-tenant.py --get --tenant-id "tenant_123"

# Delete tenant
python scripts/api-tenant.py --delete --tenant-id "tenant_123"
```

### Direct Database Creation

**`scripts/db-create-tenant.py`** - Direct database tenant creation

```bash
# Create tenant directly in database
python scripts/db-create-tenant.py "Demo Company" "Demo description"
```

## Configuration

### API Keys

All demo management scripts require admin API key authentication. The API key is automatically loaded from:

1. Environment variable `ADMIN_API_KEY`
2. `.env` file in project root
3. Configuration through `scripts/config.py`

### Default Tenant Structure

The `--setup-default` command creates tenants that match the `/data/tenants` folder structure:

- **tenant1**: "GlobalCorp Inc. - Global industry leader"
- **tenant2**: "Regional Solutions - Local community partner"  
- **tenant3**: "Tenant 3 - Third demo tenant"

## API Key Management

### Automatic API Key Generation

When creating demo tenants with API keys enabled, keys are automatically:

- Generated for each tenant
- Saved to `demo_tenant_keys.json`
- Displayed in console output
- Associated with the tenant in the database

### Using Generated API Keys

After demo setup, use the generated keys:

```bash
# Keys are saved to demo_tenant_keys.json
cat demo_tenant_keys.json

# Example output:
{
  "tenant1": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
  "tenant2": "def456ghi789jkl012mno345pqr678stu901vwx234yz567ab",
  "tenant3": "ghi789jkl012mno345pqr678stu901vwx234yz567abcde012"
}
```

### Manual API Key Creation

For existing tenants without API keys:

```bash
# Create API key for specific tenant
python scripts/api-tenant.py --create-key --tenant-id "tenant_123" --key-name "Production Key"

# List all API keys for tenant
python scripts/api-tenant.py --list-keys --tenant-id "tenant_123"
```

## Demo Environment Features

### Automatic Cleanup

Demo tenants can be configured with automatic cleanup:

- Default duration: 24 hours
- Configurable duration via `--duration` parameter
- Manual cleanup via `--cleanup` command

### Document Collections

Each demo tenant automatically gets:

- Dedicated Qdrant collection for documents
- Collection naming: `tenant_{tenant_id}_documents`
- Vector embeddings configured for 384 dimensions
- Ready for document upload and querying

### Integration with Data Folders

Demo tenants created with `--setup-default` are designed to work with:

- `/data/tenants/tenant1/` folder structure
- `/data/tenants/tenant2/` folder structure  
- `/data/tenants/tenant3/` folder structure

## Common Workflows

### Complete Demo Setup

```bash
# 1. Setup demo environment
python scripts/api-demo.py --setup-default

# 2. Verify tenants were created
python scripts/api-demo.py --list

# 3. Start backend server
python scripts/run_backend.py

# 4. Use API keys from demo_tenant_keys.json in your frontend
```

### Development Testing

```bash
# 1. Create test tenants
python scripts/api-demo.py --setup --demo-tenants "test1,test2" --duration 2

# 2. Run your tests

# 3. Cleanup when done
python scripts/api-demo.py --cleanup
```

### Production Demo Environment

```bash
# 1. Create demo tenants with longer duration
python scripts/api-demo.py --setup --demo-tenants "demo_client1,demo_client2" --duration 168

# 2. Upload sample documents for each tenant

# 3. Configure frontend with demo API keys

# 4. Cleanup after demo period
python scripts/api-demo.py --cleanup
```

## Troubleshooting

### Common Issues

1. **"Please update ADMIN_API_KEY"**
   - Ensure admin API key is set in environment or `.env` file
   - Verify API key has admin privileges

2. **"Tenant already exists"**
   - Use `--list` to see existing tenants
   - Use existing tenant ID for API key creation
   - Or delete existing tenant and recreate

3. **"Connection refused"**
   - Ensure backend server is running on `http://localhost:8000`
   - Check Docker containers are running
   - Verify database connections

4. **API keys not saved**
   - Check file permissions in project directory
   - Verify `demo_tenant_keys.json` is created
   - Check console output for generation confirmation

### Debug Mode

Enable detailed logging by modifying the request functions in the scripts to include debug output.

### Verification Steps

```bash
# Verify demo setup
python scripts/api-demo.py --list

# Check tenant details
python scripts/api-tenant.py --get --tenant-id "your_tenant_id"

# Test API key
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/v1/health

# Check Qdrant collections
curl http://localhost:6333/collections
```

## Security Notes

- Demo tenants should only be used for development and testing
- API keys are stored in plaintext in `demo_tenant_keys.json`
- Remove demo tenants from production environments
- Rotate API keys regularly
- Use `--cleanup` to remove demo data when no longer needed

## Integration with Other Scripts

Demo tenants work seamlessly with other platform scripts:

- **Document Upload**: Use generated API keys with document upload scripts
- **Health Checks**: `python scripts/health_check.py` includes demo tenant validation
- **System Monitoring**: Demo tenants appear in system metrics and audit logs
- **Database Migrations**: Demo tenants are preserved during database migrations

## Next Steps

After creating demo tenants:

1. **Upload Documents**: Add sample documents to each tenant's collection
2. **Configure Frontend**: Use generated API keys in your frontend configuration
3. **Test Queries**: Verify search and retrieval functionality
4. **Monitor Usage**: Check audit logs and system metrics
5. **Schedule Cleanup**: Set up automated cleanup for expired demo tenants