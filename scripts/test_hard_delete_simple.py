#!/usr/bin/env python3
"""
Simple Hard Delete Test for RAG System

Tests the hard delete functionality using existing test patterns.
Validates that files can be deleted and recreated without constraint violations.

Usage:
    python scripts/test_hard_delete_simple.py
"""

import requests
import json
import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import time

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.utils import get_paths
    paths = get_paths()
    PROJECT_ROOT = paths.root
except ImportError:
    # Fallback to old method
    PROJECT_ROOT = Path(__file__).parent.parent

# Configuration
env_file = PROJECT_ROOT / ".env"
load_dotenv(env_file)

BACKEND_URL = "http://localhost:8000"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

if not ADMIN_API_KEY:
    print("❌ ADMIN_API_KEY not found in .env file")
    sys.exit(1)

# Headers
headers = {
    "Authorization": f"Bearer {ADMIN_API_KEY}",
    "Content-Type": "application/json"
}

def log(message, level="INFO"):
    """Simple logging function"""
    emoji = {
        "INFO": "ℹ️",
        "SUCCESS": "✅", 
        "WARNING": "⚠️",
        "ERROR": "❌"
    }.get(level, "📝")
    print(f"{emoji} {message}")

def get_admin_tenant_id():
    """Get admin tenant ID from demo keys"""
    keys_file = PROJECT_ROOT / "demo_admin_keys.json"
    if keys_file.exists():
        with open(keys_file, 'r') as f:
            data = json.load(f)
            return data.get("admin_tenant_id", "")
    
    # Fallback to environment
    return os.getenv("ADMIN_TENANT_ID", "")

def test_basic_hard_delete():
    """Test basic hard delete functionality"""
    log("Testing basic hard delete functionality...")
    
    try:
        # Get tenant ID
        tenant_id = get_admin_tenant_id()
        if not tenant_id:
            log("Could not find admin tenant ID", "ERROR")
            return False
        
        tenant_dir = PROJECT_ROOT / "data" / "uploads" / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test files
        test_files = [
            ("test_delete_1.txt", "Content for test file 1"),
            ("test_delete_2.txt", "Content for test file 2"),
        ]
        
        for filename, content in test_files:
            file_path = tenant_dir / filename
            file_path.write_text(content, encoding='utf-8')
        
        # 1. Initial sync to create files
        log("Creating files with initial sync...")
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        if response.status_code != 200:
            log(f"Initial sync failed: {response.text}", "ERROR")
            return False
        
        result = response.json()
        if result.get("status") != "completed":
            log(f"Initial sync not completed: {result}", "ERROR")
            return False
        
        # 2. Delete files from filesystem
        log("Deleting files from filesystem...")
        for filename, _ in test_files:
            file_path = tenant_dir / filename
            if file_path.exists():
                file_path.unlink()
        
        # 3. Sync to delete from database (hard delete)
        log("Syncing to hard delete from database...")
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        if response.status_code != 200:
            log(f"Delete sync failed: {response.text}", "ERROR")
            return False
        
        result = response.json()
        if result.get("status") != "completed":
            log(f"Delete sync not completed: {result}", "ERROR")
            return False
        
        # 4. Verify deletion in history
        log("Verifying deletion in sync history...")
        response = requests.get(f"{BACKEND_URL}/api/v1/sync/history", headers=headers)
        
        if response.status_code != 200:
            log(f"Failed to get sync history: {response.text}", "ERROR")
            return False
        
        history = response.json()
        if not history.get("history"):
            log("No sync history found", "ERROR")
            return False
        
        latest_sync = history["history"][0]
        files_deleted = latest_sync.get("files_deleted", 0)
        
        if files_deleted != len(test_files):
            log(f"Expected {len(test_files)} deleted files, got {files_deleted}", "ERROR")
            return False
        
        log(f"Successfully hard deleted {files_deleted} files", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"Basic hard delete test failed: {e}", "ERROR")
        return False

def test_file_recreation():
    """Test that deleted files can be recreated without constraint violations"""
    log("Testing file recreation after hard delete...")
    
    try:
        tenant_id = get_admin_tenant_id()
        if not tenant_id:
            log("Could not find admin tenant ID", "ERROR")
            return False
        
        tenant_dir = PROJECT_ROOT / "data" / "uploads" / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Test file
        test_file = "recreation_test.txt"
        original_content = "Original content for recreation test"
        new_content = "New content after recreation"
        
        file_path = tenant_dir / test_file
        
        # 1. Create file
        file_path.write_text(original_content, encoding='utf-8')
        
        # 2. Sync to create record
        log("Creating file record...")
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        if response.status_code != 200:
            log(f"Initial sync failed: {response.text}", "ERROR")
            return False
        
        # 3. Delete file
        log("Deleting file...")
        file_path.unlink()
        
        # 4. Sync to hard delete record
        log("Hard deleting file record...")
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        if response.status_code != 200:
            log(f"Delete sync failed: {response.text}", "ERROR")
            return False
        
        # 5. Recreate file with different content
        log("Recreating file with new content...")
        file_path.write_text(new_content, encoding='utf-8')
        
        # 6. Sync to recreate record (should NOT fail with constraint violations)
        log("Syncing to recreate file record...")
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        if response.status_code != 200:
            log(f"Recreation sync failed: {response.text}", "ERROR")
            return False
        
        result = response.json()
        if result.get("status") != "completed":
            log(f"Recreation sync not completed: {result}", "ERROR")
            return False
        
        # 7. Verify file was recreated
        response = requests.get(f"{BACKEND_URL}/api/v1/sync/history", headers=headers)
        
        if response.status_code != 200:
            log(f"Failed to get sync history: {response.text}", "ERROR")
            return False
        
        history = response.json()
        latest_sync = history["history"][0]
        files_added = latest_sync.get("files_added", 0)
        
        if files_added != 1:
            log(f"Expected 1 file added, got {files_added}", "ERROR")
            return False
        
        log("File successfully recreated without constraint violations", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"File recreation test failed: {e}", "ERROR")
        return False

def test_batch_operations():
    """Test batch hard delete operations"""
    log("Testing batch hard delete operations...")
    
    try:
        tenant_id = get_admin_tenant_id()
        if not tenant_id:
            log("Could not find admin tenant ID", "ERROR")
            return False
        
        tenant_dir = PROJECT_ROOT / "data" / "uploads" / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Create multiple test files
        test_files = [
            ("batch_test_1.txt", "Batch test content 1"),
            ("batch_test_2.txt", "Batch test content 2"),
            ("batch_test_3.txt", "Batch test content 3"),
            ("batch_test_4.txt", "Batch test content 4"),
        ]
        
        for filename, content in test_files:
            file_path = tenant_dir / filename
            file_path.write_text(content, encoding='utf-8')
        
        # 1. Create files
        log("Creating batch test files...")
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        if response.status_code != 200:
            log(f"Initial sync failed: {response.text}", "ERROR")
            return False
        
        # 2. Delete all files at once
        log("Deleting all files simultaneously...")
        for filename, _ in test_files:
            file_path = tenant_dir / filename
            if file_path.exists():
                file_path.unlink()
        
        # 3. Trigger batch deletion
        start_time = time.time()
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        batch_time = time.time() - start_time
        
        if response.status_code != 200:
            log(f"Batch delete sync failed: {response.text}", "ERROR")
            return False
        
        result = response.json()
        if result.get("status") != "completed":
            log(f"Batch delete sync not completed: {result}", "ERROR")
            return False
        
        # 4. Verify all files were deleted
        response = requests.get(f"{BACKEND_URL}/api/v1/sync/history", headers=headers)
        
        if response.status_code != 200:
            log(f"Failed to get sync history: {response.text}", "ERROR")
            return False
        
        history = response.json()
        latest_sync = history["history"][0]
        files_deleted = latest_sync.get("files_deleted", 0)
        chunks_deleted = latest_sync.get("chunks_deleted", 0)
        
        if files_deleted != len(test_files):
            log(f"Expected {len(test_files)} deleted files, got {files_deleted}", "ERROR")
            return False
        
        log(f"Batch deleted {files_deleted} files and {chunks_deleted} chunks in {batch_time:.2f}s", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"Batch hard delete test failed: {e}", "ERROR")
        return False

def cleanup_test_files():
    """Clean up test files"""
    try:
        tenant_id = get_admin_tenant_id()
        if not tenant_id:
            return
        
        tenant_dir = PROJECT_ROOT / "data" / "uploads" / tenant_id
        
        # Remove all test files
        test_patterns = [
            "test_delete_*.txt",
            "recreation_test.txt", 
            "batch_test_*.txt"
        ]
        
        for pattern in test_patterns:
            for file_path in tenant_dir.glob(pattern):
                if file_path.exists():
                    file_path.unlink()
        
        # Trigger sync to clean up database
        requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
        
        log("Cleaned up test files", "SUCCESS")
        
    except Exception as e:
        log(f"Cleanup failed: {e}", "WARNING")

def main():
    """Main test runner"""
    log("🧪 Starting Hard Delete Test Suite")
    log("=" * 50)
    
    # Test cases
    tests = [
        ("Basic Hard Delete", test_basic_hard_delete),
        ("File Recreation", test_file_recreation),
        ("Batch Operations", test_batch_operations)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        log(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            if result:
                passed += 1
                log(f"✅ PASSED: {test_name}", "SUCCESS")
            else:
                failed += 1
                log(f"❌ FAILED: {test_name}", "ERROR")
        except Exception as e:
            failed += 1
            log(f"❌ FAILED: {test_name} - {e}", "ERROR")
    
    # Cleanup
    cleanup_test_files()
    
    # Summary
    log("\n" + "=" * 50)
    log(f"🏁 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        log("🎉 All hard delete tests passed!", "SUCCESS")
        return True
    else:
        log(f"⚠️ {failed} tests failed", "ERROR")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        cleanup_test_files()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        sys.exit(1)