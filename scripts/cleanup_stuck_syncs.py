#!/usr/bin/env python3
"""
Cleanup script for stuck sync operations
"""
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def cleanup_stuck_syncs():
    """Mark stuck sync operations as failed"""
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', 'postgresql://rag_user:rag_password@localhost:5432/rag_db')
    
    # Create sync engine
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Find operations stuck in 'running' state for more than 1 hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        # Update stuck operations
        result = session.execute(
            text("""
            UPDATE sync_operations 
            SET status = 'failed',
                completed_at = NOW(),
                error_message = 'Operation timed out - marked as failed by cleanup script',
                updated_at = NOW()
            WHERE status = 'running' 
            AND started_at < :cutoff_time
            RETURNING id, started_at, tenant_id
            """),
            {"cutoff_time": cutoff_time}
        )
        
        updated_operations = result.fetchall()
        session.commit()
        
        print(f"🧹 Cleanup completed!")
        print(f"📊 Updated {len(updated_operations)} stuck operations:")
        
        for op in updated_operations:
            print(f"  - ID: {op[0]}")
            print(f"    Started: {op[1]}")
            print(f"    Tenant: {op[2]}")
            print()
        
        if not updated_operations:
            print("✅ No stuck operations found!")

if __name__ == "__main__":
    cleanup_stuck_syncs()