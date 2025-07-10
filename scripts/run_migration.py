#!/usr/bin/env python3
"""
Simple migration script to add missing columns to sync_operations table.
"""

import asyncio
import asyncpg
import os
from pathlib import Path

async def run_migration():
    """Add missing columns to sync_operations table."""
    
    # Get database connection details from docker-compose configuration
    postgres_user = "rag_user"
    postgres_password = "rag_password"
    postgres_host = "localhost"  # Since we're running from host
    postgres_port = 5432
    db_name = "rag_db"
    
    print(f"Connecting to {db_name} with user {postgres_user}")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=postgres_host,
            port=postgres_port,
            database=db_name,
            user=postgres_user,
            password=postgres_password
        )
        
        print(f"✅ Connected to {db_name}")
        
        # Check if columns already exist
        columns_to_add = [
            'heartbeat_at',
            'expected_duration_seconds', 
            'progress_stage',
            'progress_percentage',
            'total_files_to_process',
            'current_file_index'
        ]
        
        for column in columns_to_add:
            result = await conn.fetchval("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'sync_operations' AND column_name = $1
            """, column)
            
            if result:
                print(f"  ✅ {column} already exists")
            else:
                # Add the column
                if column == 'heartbeat_at':
                    await conn.execute("ALTER TABLE sync_operations ADD COLUMN heartbeat_at TIMESTAMP WITH TIME ZONE")
                elif column == 'expected_duration_seconds':
                    await conn.execute("ALTER TABLE sync_operations ADD COLUMN expected_duration_seconds INTEGER")
                elif column == 'progress_stage':
                    await conn.execute("ALTER TABLE sync_operations ADD COLUMN progress_stage VARCHAR(50)")
                elif column == 'progress_percentage':
                    await conn.execute("ALTER TABLE sync_operations ADD COLUMN progress_percentage FLOAT")
                elif column == 'total_files_to_process':
                    await conn.execute("ALTER TABLE sync_operations ADD COLUMN total_files_to_process INTEGER")
                elif column == 'current_file_index':
                    await conn.execute("ALTER TABLE sync_operations ADD COLUMN current_file_index INTEGER")
                
                print(f"  ✅ Added {column}")
        
        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_operations_heartbeat 
            ON sync_operations(status, heartbeat_at)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_operations_progress 
            ON sync_operations(tenant_id, status, progress_stage)
        """)
        
        print("  ✅ Created indexes")
        
        # Update existing running operations
        result = await conn.execute("""
            UPDATE sync_operations 
            SET heartbeat_at = started_at,
                progress_stage = 'running',
                progress_percentage = 0.0
            WHERE status = 'running' AND heartbeat_at IS NULL
        """)
        
        print("  ✅ Updated existing running operations")
        
        await conn.close()
        print("\n🎉 Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(run_migration()) 