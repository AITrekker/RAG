#!/usr/bin/env python3
"""
Database Inspection Script - View RAG system data
"""

import os
import sys
import socket
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Set NLTK data path for Docker environment
os.environ['NLTK_DATA'] = '/tmp/nltk_data'

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def setup_database_url():
    """Setup DATABASE_URL for current environment (Docker vs local)"""
    load_dotenv()
    
    # Get credentials from .env
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD") 
    postgres_db = "rag_db"
    
    if not postgres_user or not postgres_password:
        print("❌ Missing database credentials in .env file")
        print("   Required: POSTGRES_USER, POSTGRES_PASSWORD")
        sys.exit(1)
    
    # Detect environment
    if is_running_in_docker():
        # Use Docker network hostname
        database_url = f"postgresql://{postgres_user}:{postgres_password}@postgres:5432/{postgres_db}"
        print("🐳 Detected Docker environment")
    else:
        # Use localhost for local execution
        database_url = f"postgresql://{postgres_user}:{postgres_password}@localhost:5432/{postgres_db}"
        print("💻 Detected local environment")
    
    # Set the environment variable for database connections
    os.environ["DATABASE_URL"] = database_url
    print(f"📡 Database URL: {database_url}")

def is_running_in_docker() -> bool:
    """Detect if we're running inside a Docker container"""
    try:
        # Check for Docker-specific files/environments
        if os.path.exists("/.dockerenv"):
            return True
        
        # Check if hostname resolves to postgres (Docker network)
        try:
            socket.gethostbyname("postgres")
            return True
        except socket.gaierror:
            return False
            
    except Exception:
        return False

# Setup database URL BEFORE importing backend modules
setup_database_url()

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.backend.database import AsyncSessionLocal

async def show_overview():
    """Show database overview"""
    print("\n📊 DATABASE OVERVIEW")
    print("=" * 50)
    
    async with AsyncSessionLocal() as session:
        # Get counts
        file_count = await session.scalar(text("SELECT COUNT(*) FROM files WHERE deleted_at IS NULL"))
        chunk_count = await session.scalar(text("SELECT COUNT(*) FROM embedding_chunks"))
        tenant_count = await session.scalar(text("SELECT COUNT(*) FROM tenants WHERE is_active = true"))
        user_count = await session.scalar(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
        
        print(f"🏢 Active Tenants: {tenant_count}")
        print(f"👥 Active Users: {user_count}")
        print(f"📁 Files: {file_count}")
        print(f"🧩 Embedding Chunks: {chunk_count}")

async def show_tenants():
    """Show tenant details with file counts"""
    print("\n🏢 TENANTS & FILES")
    print("=" * 50)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT 
                t.name,
                t.id,
                t.plan_tier,
                COUNT(f.id) as file_count,
                COALESCE(SUM(f.file_size), 0) as total_size,
                COUNT(DISTINCT f.id) FILTER (WHERE f.sync_status = 'synced') as synced_files
            FROM tenants t 
            LEFT JOIN files f ON t.id = f.tenant_id AND f.deleted_at IS NULL
            WHERE t.is_active = true
            GROUP BY t.id, t.name, t.plan_tier
            ORDER BY t.name
        """))
        
        for row in result:
            size_mb = row.total_size / (1024 * 1024) if row.total_size else 0
            print(f"  📂 {row.name}")
            print(f"     ID: {row.id}")
            print(f"     Plan: {row.plan_tier}")
            print(f"     Files: {row.file_count} ({row.synced_files} synced)")
            print(f"     Size: {size_mb:.1f} MB")
            print()

async def show_files():
    """Show file details"""
    print("\n📁 FILES")
    print("=" * 50)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT 
                f.filename,
                t.name as tenant_name,
                f.file_size,
                f.word_count,
                f.sync_status,
                COUNT(c.id) as chunks,
                f.created_at
            FROM files f
            JOIN tenants t ON f.tenant_id = t.id
            LEFT JOIN embedding_chunks c ON f.id = c.file_id
            WHERE f.deleted_at IS NULL
            GROUP BY f.id, f.filename, t.name, f.file_size, f.word_count, f.sync_status, f.created_at
            ORDER BY t.name, f.filename
            LIMIT 20
        """))
        
        for row in result:
            size_kb = row.file_size / 1024 if row.file_size else 0
            status_emoji = {
                'synced': '✅',
                'pending': '⏳',
                'processing': '🔄',
                'failed': '❌'
            }.get(row.sync_status, '❓')
            
            print(f"  {status_emoji} {row.filename}")
            print(f"     Tenant: {row.tenant_name}")
            print(f"     Size: {size_kb:.1f} KB")
            print(f"     Words: {row.word_count or 'N/A'}")
            print(f"     Chunks: {row.chunks}")
            print(f"     Status: {row.sync_status}")
            print()

async def show_chunks():
    """Show embedding chunk statistics"""
    print("\n🧩 EMBEDDING CHUNKS")
    print("=" * 50)
    
    async with AsyncSessionLocal() as session:
        # Chunk stats by tenant
        result = await session.execute(text("""
            SELECT 
                t.name as tenant_name,
                COUNT(c.id) as chunk_count,
                AVG(c.token_count) as avg_tokens,
                SUM(c.token_count) as total_tokens
            FROM embedding_chunks c
            JOIN tenants t ON c.tenant_id = t.id
            GROUP BY t.id, t.name
            ORDER BY chunk_count DESC
        """))
        
        print("By Tenant:")
        for row in result:
            print(f"  📊 {row.tenant_name}")
            print(f"     Chunks: {row.chunk_count}")
            print(f"     Avg Tokens: {row.avg_tokens:.1f}")
            print(f"     Total Tokens: {row.total_tokens}")
            print()
        
        # Overall stats
        stats = await session.execute(text("""
            SELECT 
                COUNT(*) as total_chunks,
                AVG(token_count) as avg_tokens,
                MIN(token_count) as min_tokens,
                MAX(token_count) as max_tokens,
                COUNT(DISTINCT embedding_model) as model_count
            FROM embedding_chunks
        """))
        
        row = stats.first()
        print("Overall Statistics:")
        print(f"  📈 Total Chunks: {row.total_chunks}")
        print(f"  📊 Avg Tokens: {row.avg_tokens:.1f}")
        print(f"  📉 Token Range: {row.min_tokens} - {row.max_tokens}")
        print(f"  🤖 Models Used: {row.model_count}")

async def show_recent_activity():
    """Show recent sync activity"""
    print("\n⚡ RECENT ACTIVITY")
    print("=" * 50)
    
    async with AsyncSessionLocal() as session:
        # Recent files
        result = await session.execute(text("""
            SELECT 
                f.filename,
                t.name as tenant_name,
                f.sync_status,
                f.created_at,
                f.updated_at
            FROM files f
            JOIN tenants t ON f.tenant_id = t.id
            WHERE f.deleted_at IS NULL
            ORDER BY f.updated_at DESC
            LIMIT 10
        """))
        
        print("Recently Updated Files:")
        for row in result:
            status_emoji = {
                'synced': '✅',
                'pending': '⏳',
                'processing': '🔄',
                'failed': '❌'
            }.get(row.sync_status, '❓')
            
            print(f"  {status_emoji} {row.filename}")
            print(f"     Tenant: {row.tenant_name}")
            print(f"     Updated: {row.updated_at}")
            print()

async def test_connection():
    """Test database connection"""
    print("\n🔍 CONNECTION TEST")
    print("=" * 50)
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Connection successful")
            print(f"📡 PostgreSQL Version: {version}")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

async def main():
    """Main inspection function"""
    print("🔍 RAG Database Inspector")
    print("=" * 50)
    
    # Test connection first
    if not await test_connection():
        print("\n💡 Troubleshooting:")
        print("  • Make sure PostgreSQL is running (docker-compose up -d)")
        print("  • Check .env file has correct POSTGRES_USER/POSTGRES_PASSWORD")
        print("  • Verify you're in the correct directory")
        return
    
    try:
        await show_overview()
        await show_tenants()
        await show_files()
        await show_chunks()
        await show_recent_activity()
        
        print("\n🎉 Inspection Complete!")
        print("💡 Your RAG system is ready for queries!")
        
    except Exception as e:
        print(f"❌ Error during inspection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())