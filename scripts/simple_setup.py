"""
DEAD SIMPLE tenant setup - no overengineering
Just create 3 tenants with API keys. That's it.
"""

import asyncio
import asyncpg
from uuid import uuid4
import secrets
import json
from pathlib import Path

# Simple tenant data
TENANTS = [
    {"name": "tenant1", "slug": "tenant1"},
    {"name": "tenant2", "slug": "tenant2"}, 
    {"name": "tenant3", "slug": "tenant3"}
]

async def setup_simple_tenants():
    """Create tenants directly in database. No fancy APIs."""
    
    # Connect directly to database
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        database="rag_db_development", 
        user="rag_user",
        password="rag_password"
    )
    
    tenant_keys = {}
    
    for tenant_data in TENANTS:
        # Generate simple data
        tenant_id = uuid4()
        api_key = f"tenant_{tenant_data['slug']}_{secrets.token_hex(16)}"
        
        print(f"Creating {tenant_data['name']}...")
        
        # Insert with required fields - no fancy ORM
        await conn.execute("""
            INSERT INTO tenants (
                id, name, slug, api_key, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (slug) DO UPDATE SET
                api_key = $4,
                updated_at = NOW()
        """, tenant_id, tenant_data['name'], tenant_data['slug'], api_key)
        
        tenant_keys[str(tenant_id)] = {
            "api_key": api_key,
            "slug": tenant_data['slug'],
            "description": f"Demo {tenant_data['name']} with company documents (development)"
        }
        
        print(f"✅ Created {tenant_data['name']} with key: {api_key}")
    
    await conn.close()
    
    # Write keys to file
    with open("demo_tenant_keys.json", "w") as f:
        json.dump(tenant_keys, f, indent=2)
    
    print(f"\n🎉 Done! Created {len(TENANTS)} tenants")
    print("Keys saved to demo_tenant_keys.json")

if __name__ == "__main__":
    asyncio.run(setup_simple_tenants())