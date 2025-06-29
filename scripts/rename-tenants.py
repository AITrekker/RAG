#!/usr/bin/env python3
"""
Rename tenant upload directories to match database tenant IDs

This script:
1. Queries the database for actual tenant records (excluding admin/system tenants)
2. Renames the directories under /data/uploads/ to match tenant UUIDs
3. Preserves all files during the rename operation
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Tuple
from uuid import UUID

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import AsyncSessionLocal
from src.backend.models.database import Tenant


async def get_actual_tenants() -> List[Tuple[UUID, str, str]]:
    """
    Get actual tenant records from database (excluding admin/system tenants)
    
    Returns:
        List of tuples: (tenant_id, tenant_name, tenant_slug)
    """
    async with AsyncSessionLocal() as session:
        # Query for non-admin tenants with reasonable names
        result = await session.execute(
            select(Tenant.id, Tenant.name, Tenant.slug)
            .where(
                Tenant.is_active == True,
                ~Tenant.slug.in_(['system_admin', 'admin', 'test_tenant', 'test-tenant', 'test_company'])
            )
            .order_by(Tenant.created_at)
            .limit(10)  # Get up to 10 tenants to choose from
        )
        
        tenants = result.fetchall()
        return [(UUID(str(t.id)), t.name, t.slug) for t in tenants]


def get_upload_directories() -> List[str]:
    """
    Get current directory names under /data/uploads/
    
    Returns:
        List of directory names
    """
    uploads_path = Path("data/uploads")
    if not uploads_path.exists():
        return []
    
    return [d.name for d in uploads_path.iterdir() if d.is_dir()]


def backup_directory_mapping(tenants: List[Tuple[UUID, str, str]], directories: List[str]) -> None:
    """
    Create a backup mapping file of the rename operation
    """
    mapping_file = Path("data/tenant_directory_mapping.txt")
    
    with open(mapping_file, 'w') as f:
        f.write("# Tenant Directory Rename Mapping\n")
        f.write("# Generated by scripts/rename-tenants.py\n")
        f.write(f"# Date: {asyncio.get_event_loop().time()}\n\n")
        
        f.write("# Database Tenants:\n")
        for tenant_id, name, slug in tenants:
            f.write(f"# {tenant_id} -> {name} ({slug})\n")
        
        f.write(f"\n# Current Directories:\n")
        for directory in directories:
            f.write(f"# {directory}\n")
        
        f.write(f"\n# Planned Mapping:\n")
        for i, directory in enumerate(directories[:3]):
            if i < len(tenants):
                tenant_id, name, slug = tenants[i]
                f.write(f"{directory} -> {tenant_id} ({name})\n")


def rename_directories(tenants: List[Tuple[UUID, str, str]], directories: List[str]) -> List[Tuple[str, str, str]]:
    """
    Rename directories to match tenant UUIDs
    
    Returns:
        List of rename operations performed: (old_name, new_name, tenant_name)
    """
    uploads_path = Path("data/uploads")
    rename_operations = []
    
    print("🔄 Starting directory rename operations...")
    
    # Take up to 3 directories and 3 tenants
    directories_to_rename = directories[:3]
    target_tenants = tenants[:3]
    
    for i, old_dir in enumerate(directories_to_rename):
        if i >= len(target_tenants):
            break
            
        tenant_id, tenant_name, tenant_slug = target_tenants[i]
        old_path = uploads_path / old_dir
        new_path = uploads_path / str(tenant_id)
        
        if old_path.exists() and not new_path.exists():
            try:
                # Perform the rename
                old_path.rename(new_path)
                rename_operations.append((old_dir, str(tenant_id), tenant_name))
                print(f"  ✅ Renamed: {old_dir} -> {tenant_id} ({tenant_name})")
                
                # Verify files are still there
                file_count = len(list(new_path.rglob("*")))
                print(f"     📁 Verified {file_count} files in directory")
                
            except Exception as e:
                print(f"  ❌ Failed to rename {old_dir}: {e}")
        elif new_path.exists():
            print(f"  ⏩ Target directory {tenant_id} already exists, skipping {old_dir}")
        else:
            print(f"  ⚠️ Source directory {old_dir} not found")
    
    return rename_operations


async def main():
    """Main function to orchestrate the tenant directory rename"""
    print("🚀 Tenant Directory Rename Script")
    print("=" * 50)
    
    try:
        # 1. Get actual tenants from database
        print("\n📊 Querying database for tenant records...")
        tenants = await get_actual_tenants()
        
        if not tenants:
            print("❌ No suitable tenants found in database")
            return
        
        print(f"✅ Found {len(tenants)} tenants:")
        for i, (tenant_id, name, slug) in enumerate(tenants[:5]):  # Show first 5
            print(f"  {i+1}. {name} ({slug}) -> {tenant_id}")
        
        # 2. Get current upload directories
        print(f"\n📁 Scanning /data/uploads/ directory...")
        directories = get_upload_directories()
        
        if not directories:
            print("❌ No directories found in /data/uploads/")
            return
        
        print(f"✅ Found {len(directories)} directories:")
        for directory in directories:
            file_count = len(list(Path(f"data/uploads/{directory}").rglob("*")))
            print(f"  📂 {directory} ({file_count} files)")
        
        # 3. Create backup mapping
        print(f"\n💾 Creating backup mapping...")
        backup_directory_mapping(tenants, directories)
        print("✅ Backup mapping saved to data/tenant_directory_mapping.txt")
        
        # 4. Confirm operation
        print(f"\n⚠️  This will rename up to 3 directories to match tenant UUIDs:")
        for i in range(min(3, len(directories), len(tenants))):
            old_name = directories[i]
            tenant_id, tenant_name, _ = tenants[i]
            print(f"  {old_name} -> {tenant_id} ({tenant_name})")
        
        response = input(f"\nProceed with rename? (yes/no): ").lower().strip()
        if response not in ['yes', 'y']:
            print("❌ Operation cancelled")
            return
        
        # 5. Perform rename operations
        print(f"\n🔄 Performing rename operations...")
        rename_operations = rename_directories(tenants, directories)
        
        # 6. Summary
        print(f"\n🎉 Rename operations completed!")
        print(f"📊 Summary:")
        print(f"  🔄 Directories renamed: {len(rename_operations)}")
        print(f"  📁 Total tenants available: {len(tenants)}")
        
        if rename_operations:
            print(f"\n✅ Successfully renamed directories:")
            for old_name, new_name, tenant_name in rename_operations:
                print(f"  {old_name} -> {new_name} ({tenant_name})")
            
            print(f"\n🚀 Ready for delta sync! Run: python scripts/delta-sync.py")
        else:
            print(f"\n⚠️ No directories were renamed (they may already be correctly named)")
        
    except Exception as e:
        print(f"❌ Error during rename operation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())