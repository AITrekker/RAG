#!/usr/bin/env python3
"""
Setup Environment Databases

Creates the environment-specific databases that the new architecture requires.
Run this after containers start but before init container.
"""

import asyncpg
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ENVIRONMENTS = ["production", "staging", "test", "development"]

async def create_environment_databases():
    """Create all environment-specific databases."""
    print("🏗️ Setting up environment-specific databases...")
    
    # Get credentials
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    
    if not postgres_user or not postgres_password:
        print("❌ Missing POSTGRES_USER or POSTGRES_PASSWORD in .env")
        sys.exit(1)
    
    try:
        # Connect to default postgres database to create others
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user=postgres_user,
            password=postgres_password
        )
        
        print("✅ Connected to PostgreSQL")
        
        # Create each environment database
        for env in ENVIRONMENTS:
            db_name = f"rag_db_{env}"
            
            try:
                # Check if database exists
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1", db_name
                )
                
                if result:
                    print(f"  ✅ {db_name} already exists")
                else:
                    # Create database
                    await conn.execute(f'CREATE DATABASE {db_name} OWNER {postgres_user}')
                    print(f"  ✅ Created {db_name}")
                    
            except Exception as e:
                print(f"  ❌ Failed to create {db_name}: {e}")
        
        await conn.close()
        print("\n🎉 Environment databases setup complete!")
        print("\nNext steps:")
        print("1. Restart the init container: docker restart rag_init")
        print("2. Check init logs: docker logs rag_init")
        print("3. Start backend: docker start rag_backend")
        
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        print("Make sure PostgreSQL container is running: docker ps")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(create_environment_databases())