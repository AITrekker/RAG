#!/usr/bin/env python3
"""
Hard Delete Operations Test Suite for RAG System

Tests the hard delete functionality implemented to replace soft deletes.
Validates that files can be deleted and recreated without constraint violations.

Usage:
    python scripts/test_hard_delete.py
    python scripts/test_hard_delete.py --verbose
    python scripts/test_hard_delete.py --cleanup-only
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
from dataclasses import dataclass

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("⚠️ aiohttp not available, using requests fallback")
    import requests

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.utils import get_paths, ValidatedAPIClient
    paths = get_paths()
    validation_available = True
except ImportError:
    print("⚠️ Using fallback HTTP client (validation utilities not available)")
    paths = None
    validation_available = False

# Configuration
BASE_URL = "http://localhost:8000"
API_VERSION = "v1"

@dataclass
class TestFile:
    """Test file data structure"""
    name: str
    content: str
    expected_chunks: int = 1
    
    def __post_init__(self):
        # Estimate expected chunks based on content length
        # Using typical chunk size of ~500 characters
        self.expected_chunks = max(1, len(self.content) // 500)

class HardDeleteTester:
    """Comprehensive hard delete functionality tester"""
    
    def __init__(self, verbose: bool = False, cleanup_only: bool = False):
        self.verbose = verbose
        self.cleanup_only = cleanup_only
        self.base_url = BASE_URL
        self.api_client = ValidatedAPIClient(BASE_URL) if validation_available else None
        self.admin_api_key = self._load_admin_key()
        self.test_files = self._create_test_files()
        self.test_results = []
        self.temp_dir = None
        
    def _load_admin_key(self) -> str:
        """Load admin API key from environment"""
        # Try from .env file first
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith("ADMIN_API_KEY="):
                        return line.split("=", 1)[1].strip()
        
        # Fallback to environment variable
        api_key = os.getenv("ADMIN_API_KEY")
        if not api_key:
            print("❌ ADMIN_API_KEY not found in .env file or environment")
            sys.exit(1)
        
        return api_key
    
    def _create_test_files(self) -> List[TestFile]:
        """Create test files with various content sizes"""
        return [
            TestFile(
                name="small_test.txt",
                content="This is a small test file for hard delete validation.",
                expected_chunks=1
            ),
            TestFile(
                name="medium_test.txt", 
                content="This is a medium-sized test file. " * 50 + 
                       "It should create multiple chunks when processed. " * 30,
                expected_chunks=2
            ),
            TestFile(
                name="large_test.txt",
                content="This is a large test file for comprehensive testing. " * 100 + 
                       "It contains substantial content that will be split into multiple chunks. " * 50,
                expected_chunks=3
            ),
            TestFile(
                name="duplicate_name.txt",
                content="First version of duplicate file.",
                expected_chunks=1
            ),
            TestFile(
                name="special_chars_文件.txt",
                content="File with special characters: αβγ δεζ 中文 🔥 testing unicode support.",
                expected_chunks=1
            )
        ]
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with optional verbose output"""
        if level == "DEBUG" and not self.verbose:
            return
        
        emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }.get(level, "📝")
        
        print(f"{emoji} {message}")
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request with fallback support"""
        if self.api_client:
            try:
                if method.upper() == "GET":
                    return await self.api_client.get(endpoint, self.admin_api_key)
                elif method.upper() == "POST":
                    return await self.api_client.post(endpoint, self.admin_api_key, data)
                elif method.upper() == "DELETE":
                    return await self.api_client.delete(endpoint, self.admin_api_key)
            except Exception as e:
                self.log(f"Validated request failed, using fallback: {e}", "WARNING")
        
        # Fallback to manual request
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.admin_api_key}",
            "Content-Type": "application/json"
        }
        
        if AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers) as response:
                        return await response.json()
                elif method.upper() == "POST":
                    async with session.post(url, headers=headers, json=data or {}) as response:
                        return await response.json()
                elif method.upper() == "DELETE":
                    async with session.delete(url, headers=headers) as response:
                        return await response.json()
        else:
            # Synchronous fallback using requests
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
                return response.json()
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data or {})
                return response.json()
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
                return response.json()
    
    def _setup_test_files(self) -> str:
        """Create temporary directory with test files"""
        self.temp_dir = tempfile.mkdtemp(prefix="rag_hard_delete_test_")
        
        # Create test files
        for test_file in self.test_files:
            file_path = Path(self.temp_dir) / test_file.name
            file_path.write_text(test_file.content, encoding='utf-8')
        
        self.log(f"Created test files in: {self.temp_dir}", "DEBUG")
        return self.temp_dir
    
    def _cleanup_test_files(self):
        """Clean up temporary test files"""
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir)
            self.log(f"Cleaned up test files: {self.temp_dir}", "DEBUG")
    
    def _get_admin_tenant_id(self) -> str:
        """Extract admin tenant ID from API key or environment"""
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith("ADMIN_TENANT_ID="):
                        return line.split("=", 1)[1].strip()
        
        # Fallback to extracting from demo_admin_keys.json
        keys_file = Path(__file__).parent.parent / "demo_admin_keys.json"
        if keys_file.exists():
            with open(keys_file, 'r') as f:
                data = json.load(f)
                return data.get("admin_tenant_id", "")
        
        raise ValueError("Could not find admin tenant ID")
    
    def _copy_files_to_tenant_dir(self, tenant_id: str):
        """Copy test files to tenant upload directory"""
        tenant_dir = Path(__file__).parent.parent / "data" / "uploads" / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        for test_file in self.test_files:
            src_path = Path(self.temp_dir) / test_file.name
            dst_path = tenant_dir / test_file.name
            dst_path.write_text(src_path.read_text(encoding='utf-8'), encoding='utf-8')
        
        self.log(f"Copied test files to tenant directory: {tenant_dir}", "DEBUG")
        return tenant_dir
    
    async def test_basic_hard_delete(self) -> bool:
        """Test basic hard delete functionality"""
        self.log("Testing basic hard delete functionality...")
        
        try:
            # Setup
            tenant_id = self._get_admin_tenant_id()
            tenant_dir = self._copy_files_to_tenant_dir(tenant_id)
            
            # 1. Trigger initial sync to create files
            self.log("Triggering initial sync...", "DEBUG")
            sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if sync_result.get("status") != "completed":
                self.log(f"Initial sync failed: {sync_result}", "ERROR")
                return False
            
            # 2. Verify files were created
            files_processed = sync_result.get("files_processed", 0)
            expected_files = len(self.test_files)
            
            if files_processed != expected_files:
                self.log(f"Expected {expected_files} files, got {files_processed}", "ERROR")
                return False
            
            # 3. Delete some files from filesystem
            files_to_delete = self.test_files[:2]  # Delete first 2 files
            for test_file in files_to_delete:
                file_path = tenant_dir / test_file.name
                if file_path.exists():
                    file_path.unlink()
            
            self.log(f"Deleted {len(files_to_delete)} files from filesystem", "DEBUG")
            
            # 4. Trigger sync to process deletions
            self.log("Triggering sync to process deletions...", "DEBUG")
            delete_sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if delete_sync_result.get("status") != "completed":
                self.log(f"Delete sync failed: {delete_sync_result}", "ERROR")
                return False
            
            # 5. Verify sync history shows deletions
            history_result = await self._make_request("GET", "/api/v1/sync/history")
            
            if not history_result.get("history"):
                self.log("No sync history found", "ERROR")
                return False
            
            latest_sync = history_result["history"][0]
            files_deleted = latest_sync.get("files_deleted", 0)
            
            if files_deleted != len(files_to_delete):
                self.log(f"Expected {len(files_to_delete)} deleted files, got {files_deleted}", "ERROR")
                return False
            
            self.log(f"Successfully hard deleted {files_deleted} files", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Basic hard delete test failed: {e}", "ERROR")
            return False
    
    async def test_file_recreation(self) -> bool:
        """Test that deleted files can be recreated without constraint violations"""
        self.log("Testing file recreation after hard delete...")
        
        try:
            tenant_id = self._get_admin_tenant_id()
            tenant_dir = Path(__file__).parent.parent / "data" / "uploads" / tenant_id
            
            # 1. Create a test file
            test_file = TestFile(
                name="recreation_test.txt",
                content="Original content for recreation test."
            )
            
            file_path = tenant_dir / test_file.name
            file_path.write_text(test_file.content, encoding='utf-8')
            
            # 2. Sync to create the file record
            self.log("Creating initial file record...", "DEBUG")
            sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if sync_result.get("status") != "completed":
                self.log(f"Initial sync failed: {sync_result}", "ERROR")
                return False
            
            # 3. Delete the file
            file_path.unlink()
            
            # 4. Sync to delete the file record (hard delete)
            self.log("Hard deleting file record...", "DEBUG")
            delete_sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if delete_sync_result.get("status") != "completed":
                self.log(f"Delete sync failed: {delete_sync_result}", "ERROR")
                return False
            
            # 5. Recreate the file with different content
            new_content = "New content for recreation test - different from original."
            file_path.write_text(new_content, encoding='utf-8')
            
            # 6. Sync to recreate the file record (this should NOT fail with constraint violations)
            self.log("Recreating file record...", "DEBUG")
            recreate_sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if recreate_sync_result.get("status") != "completed":
                self.log(f"Recreation sync failed: {recreate_sync_result}", "ERROR")
                return False
            
            # 7. Verify the file was recreated
            history_result = await self._make_request("GET", "/api/v1/sync/history")
            latest_sync = history_result["history"][0]
            files_added = latest_sync.get("files_added", 0)
            
            if files_added != 1:
                self.log(f"Expected 1 file added, got {files_added}", "ERROR")
                return False
            
            self.log("File successfully recreated without constraint violations", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"File recreation test failed: {e}", "ERROR")
            return False
    
    async def test_batch_hard_delete(self) -> bool:
        """Test batch hard delete operations"""
        self.log("Testing batch hard delete operations...")
        
        try:
            tenant_id = self._get_admin_tenant_id()
            tenant_dir = self._copy_files_to_tenant_dir(tenant_id)
            
            # 1. Create multiple files
            self.log("Creating multiple test files...", "DEBUG")
            sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if sync_result.get("status") != "completed":
                self.log(f"Initial sync failed: {sync_result}", "ERROR")
                return False
            
            # 2. Delete all files at once
            self.log("Deleting all files simultaneously...", "DEBUG")
            for test_file in self.test_files:
                file_path = tenant_dir / test_file.name
                if file_path.exists():
                    file_path.unlink()
            
            # 3. Trigger batch deletion
            batch_delete_start = time.time()
            delete_sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            batch_delete_time = time.time() - batch_delete_start
            
            if delete_sync_result.get("status") != "completed":
                self.log(f"Batch delete sync failed: {delete_sync_result}", "ERROR")
                return False
            
            # 4. Verify all files were deleted
            history_result = await self._make_request("GET", "/api/v1/sync/history")
            latest_sync = history_result["history"][0]
            files_deleted = latest_sync.get("files_deleted", 0)
            chunks_deleted = latest_sync.get("chunks_deleted", 0)
            
            if files_deleted != len(self.test_files):
                self.log(f"Expected {len(self.test_files)} deleted files, got {files_deleted}", "ERROR")
                return False
            
            if chunks_deleted == 0:
                self.log("No embedding chunks were deleted", "WARNING")
            
            self.log(f"Batch deleted {files_deleted} files and {chunks_deleted} chunks in {batch_delete_time:.2f}s", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Batch hard delete test failed: {e}", "ERROR")
            return False
    
    async def test_embedding_cleanup(self) -> bool:
        """Test that embeddings are properly cleaned up during hard delete"""
        self.log("Testing embedding cleanup during hard delete...")
        
        try:
            tenant_id = self._get_admin_tenant_id()
            tenant_dir = self._copy_files_to_tenant_dir(tenant_id)
            
            # 1. Create files and embeddings
            self.log("Creating files and embeddings...", "DEBUG")
            sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if sync_result.get("status") != "completed":
                self.log(f"Initial sync failed: {sync_result}", "ERROR")
                return False
            
            initial_chunks = sync_result.get("files_processed", 0)  # This should be from history
            
            # 2. Delete files
            for test_file in self.test_files:
                file_path = tenant_dir / test_file.name
                if file_path.exists():
                    file_path.unlink()
            
            # 3. Trigger deletion and verify embedding cleanup
            delete_sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if delete_sync_result.get("status") != "completed":
                self.log(f"Delete sync failed: {delete_sync_result}", "ERROR")
                return False
            
            # 4. Check sync history for embedding metrics
            history_result = await self._make_request("GET", "/api/v1/sync/history")
            latest_sync = history_result["history"][0]
            
            chunks_deleted = latest_sync.get("chunks_deleted", 0)
            files_deleted = latest_sync.get("files_deleted", 0)
            
            if files_deleted == 0:
                self.log("No files were deleted", "ERROR")
                return False
            
            if chunks_deleted == 0:
                self.log("No embedding chunks were deleted - this may indicate a cleanup issue", "WARNING")
            
            self.log(f"Hard delete cleaned up {chunks_deleted} embedding chunks for {files_deleted} files", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Embedding cleanup test failed: {e}", "ERROR")
            return False
    
    async def test_concurrent_operations(self) -> bool:
        """Test hard delete behavior with concurrent operations"""
        self.log("Testing concurrent hard delete operations...")
        
        try:
            tenant_id = self._get_admin_tenant_id()
            tenant_dir = self._copy_files_to_tenant_dir(tenant_id)
            
            # 1. Create initial files
            sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if sync_result.get("status") != "completed":
                self.log(f"Initial sync failed: {sync_result}", "ERROR")
                return False
            
            # 2. Test concurrent sync operations
            # Delete some files
            files_to_delete = self.test_files[:2]
            for test_file in files_to_delete:
                file_path = tenant_dir / test_file.name
                if file_path.exists():
                    file_path.unlink()
            
            # Add new files
            new_files = [
                TestFile(name="concurrent_1.txt", content="Concurrent test file 1"),
                TestFile(name="concurrent_2.txt", content="Concurrent test file 2")
            ]
            
            for test_file in new_files:
                file_path = tenant_dir / test_file.name
                file_path.write_text(test_file.content, encoding='utf-8')
            
            # 3. Trigger sync with mixed operations
            self.log("Processing mixed add/delete operations...", "DEBUG")
            mixed_sync_result = await self._make_request("POST", "/api/v1/sync/trigger")
            
            if mixed_sync_result.get("status") != "completed":
                self.log(f"Mixed operations sync failed: {mixed_sync_result}", "ERROR")
                return False
            
            # 4. Verify results
            history_result = await self._make_request("GET", "/api/v1/sync/history")
            latest_sync = history_result["history"][0]
            
            files_added = latest_sync.get("files_added", 0)
            files_deleted = latest_sync.get("files_deleted", 0)
            
            if files_added != len(new_files) or files_deleted != len(files_to_delete):
                self.log(f"Expected {len(new_files)} added, {len(files_to_delete)} deleted; got {files_added} added, {files_deleted} deleted", "ERROR")
                return False
            
            self.log(f"Successfully processed concurrent operations: {files_added} added, {files_deleted} deleted", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Concurrent operations test failed: {e}", "ERROR")
            return False
    
    async def cleanup_tenant_data(self):
        """Clean up any test data from tenant directory"""
        try:
            tenant_id = self._get_admin_tenant_id()
            tenant_dir = Path(__file__).parent.parent / "data" / "uploads" / tenant_id
            
            if tenant_dir.exists():
                # Remove test files
                for test_file in self.test_files:
                    file_path = tenant_dir / test_file.name
                    if file_path.exists():
                        file_path.unlink()
                
                # Remove concurrent test files
                for concurrent_file in ["concurrent_1.txt", "concurrent_2.txt", "recreation_test.txt"]:
                    file_path = tenant_dir / concurrent_file
                    if file_path.exists():
                        file_path.unlink()
                
                # Trigger sync to clean up database
                await self._make_request("POST", "/api/v1/sync/trigger")
                
                self.log("Cleaned up tenant test data", "SUCCESS")
                
        except Exception as e:
            self.log(f"Cleanup failed: {e}", "WARNING")
    
    async def run_all_tests(self) -> bool:
        """Run all hard delete tests"""
        self.log("🧪 Starting Hard Delete Test Suite", "INFO")
        self.log("=" * 60, "INFO")
        
        # Setup
        self._setup_test_files()
        
        if self.cleanup_only:
            await self.cleanup_tenant_data()
            self._cleanup_test_files()
            return True
        
        # Test cases
        tests = [
            ("Basic Hard Delete", self.test_basic_hard_delete),
            ("File Recreation", self.test_file_recreation),
            ("Batch Hard Delete", self.test_batch_hard_delete),
            ("Embedding Cleanup", self.test_embedding_cleanup),
            ("Concurrent Operations", self.test_concurrent_operations)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.log(f"\n📋 Running: {test_name}", "INFO")
            try:
                result = await test_func()
                if result:
                    passed += 1
                    self.log(f"✅ PASSED: {test_name}", "SUCCESS")
                else:
                    failed += 1
                    self.log(f"❌ FAILED: {test_name}", "ERROR")
            except Exception as e:
                failed += 1
                self.log(f"❌ FAILED: {test_name} - {e}", "ERROR")
        
        # Cleanup
        await self.cleanup_tenant_data()
        self._cleanup_test_files()
        
        # Summary
        self.log("\n" + "=" * 60, "INFO")
        self.log(f"🏁 Test Suite Complete: {passed} passed, {failed} failed", "INFO")
        
        if failed == 0:
            self.log("🎉 All hard delete tests passed!", "SUCCESS")
            return True
        else:
            self.log(f"⚠️ {failed} tests failed", "ERROR")
            return False

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Hard Delete Test Suite for RAG System")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--cleanup-only", action="store_true", help="Only run cleanup, skip tests")
    args = parser.parse_args()
    
    tester = HardDeleteTester(verbose=args.verbose, cleanup_only=args.cleanup_only)
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test suite interrupted by user")
        await tester.cleanup_tenant_data()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())