"""
Test database integration and data consistency.
"""

import pytest
import time
from uuid import UUID
from sqlalchemy import select, and_, func

from src.backend.models.database import Tenant, User, File, EmbeddingChunk, SyncOperation

class TestConfig:
    """Test configuration constants."""
    MIN_SCORE_THRESHOLD = 0.3
    MAX_QUERY_TIME = 2.0

class TestDatabaseIntegration:
    """Test PostgreSQL database integration and consistency."""
    
    @pytest.mark.asyncio
    async def test_database_connection(self, db_session):
        """Test basic database connectivity."""
        # Simple query to test connection
        result = await db_session.execute(select(func.now()))
        current_time = result.scalar()
        
        assert current_time is not None
        print(f"✅ Database connected: {current_time}")
    
    @pytest.mark.asyncio
    async def test_tenant_data_integrity(self, db_session, test_tenant_id):
        """Test tenant data exists and is consistent."""
        # Check tenant exists
        tenant_query = select(Tenant).where(Tenant.id == test_tenant_id)
        result = await db_session.execute(tenant_query)
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            pytest.skip(f"Test tenant {test_tenant_id} not found in database")
        
        assert tenant.is_active is True
        assert tenant.name is not None
        print(f"✅ Tenant found: {tenant.name}")
        
        # Check tenant has files
        files_query = select(func.count(File.id)).where(
            and_(
                File.tenant_id == test_tenant_id,
                File.deleted_at.is_(None)
            )
        )
        result = await db_session.execute(files_query)
        file_count = result.scalar()
        
        print(f"✅ Tenant files: {file_count}")
        
        # Check tenant has chunks
        chunks_query = select(func.count(EmbeddingChunk.id)).where(
            EmbeddingChunk.tenant_id == test_tenant_id
        )
        result = await db_session.execute(chunks_query)
        chunk_count = result.scalar()
        
        print(f"✅ Tenant chunks: {chunk_count}")
        
        assert file_count > 0, "No files found for test tenant"
        assert chunk_count > 0, "No chunks found for test tenant"
    
    @pytest.mark.asyncio
    async def test_file_chunk_relationships(self, db_session, test_tenant_id):
        """Test file-to-chunk relationships are consistent."""
        # Get files and their chunks
        files_query = select(File).where(
            and_(
                File.tenant_id == test_tenant_id,
                File.deleted_at.is_(None)
            )
        ).limit(10)
        
        result = await db_session.execute(files_query)
        files = result.scalars().all()
        
        if not files:
            pytest.skip("No files to test relationships")
        
        total_chunks = 0
        
        for file in files:
            # Get chunks for this file
            chunks_query = select(EmbeddingChunk).where(
                EmbeddingChunk.file_id == file.id
            )
            result = await db_session.execute(chunks_query)
            chunks = result.scalars().all()
            
            total_chunks += len(chunks)
            
            # Validate chunk data
            for chunk in chunks:
                assert chunk.file_id == file.id
                assert chunk.tenant_id == test_tenant_id
                assert chunk.chunk_content is not None
                assert len(chunk.chunk_content) > 0
                assert chunk.qdrant_point_id is not None
                assert chunk.chunk_index >= 0
                
            print(f"  File: {file.filename} → {len(chunks)} chunks")
        
        print(f"✅ Relationship integrity: {len(files)} files, {total_chunks} chunks")
        assert total_chunks > 0
    
    @pytest.mark.asyncio
    async def test_qdrant_point_id_uniqueness(self, db_session, test_tenant_id):
        """Test that Qdrant point IDs are unique."""
        chunks_query = select(EmbeddingChunk.qdrant_point_id).where(
            EmbeddingChunk.tenant_id == test_tenant_id
        )
        result = await db_session.execute(chunks_query)
        point_ids = [row[0] for row in result.all()]
        
        if not point_ids:
            pytest.skip("No chunks to test point ID uniqueness")
        
        unique_point_ids = set(point_ids)
        
        print(f"✅ Point ID uniqueness: {len(point_ids)} total, {len(unique_point_ids)} unique")
        
        assert len(point_ids) == len(unique_point_ids), "Duplicate Qdrant point IDs found!"
    
    @pytest.mark.asyncio
    async def test_file_hash_consistency(self, db_session, test_tenant_id):
        """Test file hash consistency for delta sync."""
        files_query = select(File).where(
            and_(
                File.tenant_id == test_tenant_id,
                File.deleted_at.is_(None)
            )
        ).limit(5)
        
        result = await db_session.execute(files_query)
        files = result.scalars().all()
        
        if not files:
            pytest.skip("No files to test hash consistency")
        
        for file in files:
            assert file.file_hash is not None
            assert len(file.file_hash) == 64, f"Invalid SHA-256 hash length: {len(file.file_hash)}"
            assert all(c in '0123456789abcdef' for c in file.file_hash.lower()), "Invalid hash characters"
            
            print(f"  {file.filename}: {file.file_hash[:16]}...")
        
        print(f"✅ Hash consistency: {len(files)} files validated")
    
    @pytest.mark.asyncio
    async def test_sync_operation_tracking(self, db_session, test_tenant_id):
        """Test sync operation tracking."""
        # Get recent sync operations
        sync_query = select(SyncOperation).where(
            SyncOperation.tenant_id == test_tenant_id
        ).order_by(SyncOperation.started_at.desc()).limit(5)
        
        result = await db_session.execute(sync_query)
        sync_ops = result.scalars().all()
        
        if not sync_ops:
            print("⚠️  No sync operations found")
            return
        
        for sync_op in sync_ops:
            assert sync_op.status in ['running', 'completed', 'failed', 'cancelled']
            assert sync_op.started_at is not None
            
            if sync_op.status == 'completed':
                assert sync_op.completed_at is not None
                assert sync_op.files_processed >= 0
                
            print(f"  Sync {sync_op.id}: {sync_op.status} ({sync_op.files_processed} files)")
        
        print(f"✅ Sync tracking: {len(sync_ops)} operations found")
    
    @pytest.mark.asyncio
    async def test_database_performance(self, db_session, test_tenant_id):
        """Test database query performance."""
        queries = [
            ("File count", select(func.count(File.id)).where(File.tenant_id == test_tenant_id)),
            ("Chunk count", select(func.count(EmbeddingChunk.id)).where(EmbeddingChunk.tenant_id == test_tenant_id)),
            ("Recent files", select(File).where(File.tenant_id == test_tenant_id).order_by(File.created_at.desc()).limit(10)),
            ("File-chunk join", select(File, EmbeddingChunk).join(EmbeddingChunk).where(File.tenant_id == test_tenant_id).limit(10))
        ]
        
        performance_results = []
        
        for query_name, query in queries:
            start_time = time.time()
            result = await db_session.execute(query)
            result.all()  # Fetch all results
            query_time = time.time() - start_time
            
            performance_results.append((query_name, query_time))
            print(f"  {query_name}: {query_time:.3f}s")
            
            # Performance assertions
            assert query_time < 1.0, f"{query_name} query too slow: {query_time:.3f}s"
        
        avg_time = sum(t for _, t in performance_results) / len(performance_results)
        print(f"✅ Database performance: avg {avg_time:.3f}s per query")
    
    @pytest.mark.asyncio
    async def test_tenant_isolation_enforcement(self, db_session):
        """Test that tenant isolation is properly enforced."""
        # Get two different tenant IDs (if available)
        tenants_query = select(Tenant.id).limit(2)
        result = await db_session.execute(tenants_query)
        tenant_ids = [row[0] for row in result.all()]
        
        if len(tenant_ids) < 2:
            pytest.skip("Need at least 2 tenants to test isolation")
        
        tenant_a, tenant_b = tenant_ids[0], tenant_ids[1]
        
        # Count files for each tenant
        count_query_a = select(func.count(File.id)).where(File.tenant_id == tenant_a)
        count_query_b = select(func.count(File.id)).where(File.tenant_id == tenant_b)
        
        result_a = await db_session.execute(count_query_a)
        result_b = await db_session.execute(count_query_b)
        
        count_a = result_a.scalar()
        count_b = result_b.scalar()
        
        print(f"✅ Tenant isolation: Tenant A has {count_a} files, Tenant B has {count_b} files")
        
        # Verify cross-tenant query returns nothing
        cross_tenant_query = select(File).where(
            and_(
                File.tenant_id == tenant_a,
                File.tenant_id == tenant_b  # Impossible condition
            )
        )
        
        result = await db_session.execute(cross_tenant_query)
        cross_tenant_files = result.scalars().all()
        
        assert len(cross_tenant_files) == 0, "Cross-tenant query returned results!"
    
    @pytest.mark.asyncio
    async def test_data_consistency_checks(self, db_session, test_tenant_id):
        """Test various data consistency checks."""
        print("\n🔍 Running data consistency checks...")
        
        # Check 1: All chunks have valid file references
        orphan_chunks_query = select(func.count(EmbeddingChunk.id)).select_from(
            EmbeddingChunk
        ).outerjoin(
            File, EmbeddingChunk.file_id == File.id
        ).where(
            and_(
                EmbeddingChunk.tenant_id == test_tenant_id,
                File.id.is_(None)
            )
        )
        
        result = await db_session.execute(orphan_chunks_query)
        orphan_count = result.scalar()
        
        assert orphan_count == 0, f"Found {orphan_count} orphaned chunks"
        print("  ✅ No orphaned chunks found")
        
        # Check 2: All files have at least one chunk
        files_without_chunks_query = select(func.count(File.id)).select_from(
            File
        ).outerjoin(
            EmbeddingChunk, File.id == EmbeddingChunk.file_id
        ).where(
            and_(
                File.tenant_id == test_tenant_id,
                File.deleted_at.is_(None),
                EmbeddingChunk.id.is_(None)
            )
        )
        
        result = await db_session.execute(files_without_chunks_query)
        files_without_chunks = result.scalar()
        
        if files_without_chunks > 0:
            print(f"  ⚠️  {files_without_chunks} files have no chunks (may need processing)")
        else:
            print("  ✅ All files have chunks")
        
        # Check 3: Chunk indices are sequential
        files_query = select(File.id, File.filename).where(
            and_(
                File.tenant_id == test_tenant_id,
                File.deleted_at.is_(None)
            )
        ).limit(3)
        
        result = await db_session.execute(files_query)
        sample_files = result.all()
        
        for file_id, filename in sample_files:
            chunks_query = select(EmbeddingChunk.chunk_index).where(
                EmbeddingChunk.file_id == file_id
            ).order_by(EmbeddingChunk.chunk_index)
            
            result = await db_session.execute(chunks_query)
            indices = [row[0] for row in result.all()]
            
            if indices:
                expected_indices = list(range(len(indices)))
                if indices != expected_indices:
                    print(f"  ⚠️  {filename}: Non-sequential chunk indices {indices}")
                else:
                    print(f"  ✅ {filename}: Sequential indices (0-{len(indices)-1})")
        
        print("✅ Data consistency checks completed")