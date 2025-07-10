#!/usr/bin/env python3
"""
Add missing heartbeat and progress tracking columns to sync_operations table
"""

import asyncio
from src.backend.database import async_engine
from sqlalchemy import text

async def add_sync_columns():
    """Add missing columns to sync_operations table"""
    
    async with async_engine.begin() as conn:
        print("🔍 Checking existing columns...")
        
        # Check what columns exist
        result = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'sync_operations'")
        )
        existing_columns = {row[0] for row in result.fetchall()}
        print(f"Existing columns: {existing_columns}")
        
        # Define columns to add
        new_columns = {
            'heartbeat_at': 'TIMESTAMP WITH TIME ZONE',
            'expected_duration_seconds': 'INTEGER',
            'progress_stage': 'VARCHAR(50)',
            'progress_percentage': 'FLOAT',
            'total_files_to_process': 'INTEGER',
            'current_file_index': 'INTEGER'
        }
        
        # Add missing columns
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                print(f"➕ Adding column: {column_name}")
                await conn.execute(
                    text(f"ALTER TABLE sync_operations ADD COLUMN {column_name} {column_type}")
                )
            else:
                print(f"✅ Column {column_name} already exists")
        
        # Add constraints
        print("🔒 Adding constraints...")
        try:
            await conn.execute(
                text("ALTER TABLE sync_operations ADD CONSTRAINT check_progress_range CHECK (progress_percentage >= 0 AND progress_percentage <= 100)")
            )
            print("✅ Added progress_range constraint")
        except Exception as e:
            if "already exists" in str(e):
                print("✅ progress_range constraint already exists")
            else:
                print(f"⚠️ Could not add progress_range constraint: {e}")
        
        try:
            await conn.execute(
                text("ALTER TABLE sync_operations ADD CONSTRAINT check_current_file_index CHECK (current_file_index >= 0)")
            )
            print("✅ Added current_file_index constraint")
        except Exception as e:
            if "already exists" in str(e):
                print("✅ current_file_index constraint already exists")
            else:
                print(f"⚠️ Could not add current_file_index constraint: {e}")
        
        try:
            await conn.execute(
                text("ALTER TABLE sync_operations ADD CONSTRAINT check_total_files CHECK (total_files_to_process >= 0)")
            )
            print("✅ Added total_files constraint")
        except Exception as e:
            if "already exists" in str(e):
                print("✅ total_files constraint already exists")
            else:
                print(f"⚠️ Could not add total_files constraint: {e}")
        
        # Add indexes
        print("📊 Adding indexes...")
        try:
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_sync_operations_heartbeat ON sync_operations(status, heartbeat_at)")
            )
            print("✅ Added heartbeat index")
        except Exception as e:
            print(f"⚠️ Could not add heartbeat index: {e}")
        
        try:
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_sync_operations_progress ON sync_operations(tenant_id, status, progress_stage)")
            )
            print("✅ Added progress index")
        except Exception as e:
            print(f"⚠️ Could not add progress index: {e}")
        
        # Update existing running operations
        print("🔄 Updating existing running operations...")
        result = await conn.execute(
            text("""
                UPDATE sync_operations 
                SET heartbeat_at = started_at,
                    progress_stage = 'running',
                    progress_percentage = 0.0
                WHERE status = 'running' AND heartbeat_at IS NULL
            """)
        )
        print(f"✅ Updated {result.rowcount} existing operations")
        
        print("🎉 Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(add_sync_columns())