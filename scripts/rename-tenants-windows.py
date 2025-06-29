#!/usr/bin/env python3
"""
Windows-friendly tenant directory rename script (no emojis)
"""

import os
from pathlib import Path

def main():
    """Rename directories to match known tenant UUIDs"""
    print("TENANT DIRECTORY RENAME")
    
    uploads_path = Path("data/uploads")
    
    if not uploads_path.exists():
        print("ERROR: data/uploads directory not found")
        return
    
    # Known tenant mappings from your database
    known_mappings = {
        "d188b61c-4380-4ec0-93be-98cf1e8a0c2c": "Acme Corp",
        "110174a1-8e2f-47a1-af19-1478f1be07a8": "Tech Startup", 
        "fc246f18-5e94-41e3-9840-9f23e47aca4b": "Enterprise Client"
    }
    
    # Get current directories
    current_dirs = [d.name for d in uploads_path.iterdir() if d.is_dir()]
    print(f"Found {len(current_dirs)} directories")
    
    if len(current_dirs) != 3:
        print(f"WARNING: Expected 3 directories, found {len(current_dirs)}")
    
    # Map current directories to target UUIDs
    target_uuids = list(known_mappings.keys())
    renames = []
    
    for i, current_dir in enumerate(current_dirs[:3]):
        if i < len(target_uuids):
            target_uuid = target_uuids[i]
            target_name = known_mappings[target_uuid]
            
            if current_dir != target_uuid:
                renames.append((current_dir, target_uuid, target_name))
    
    if not renames:
        print("SUCCESS: Directories already correctly named")
        return
    
    print(f"Will rename {len(renames)} directories:")
    for old, new, name in renames:
        print(f"  -> {name}")
    
    try:
        response = input(f"\nProceed? (y/n): ").lower().strip()
        if response not in ['yes', 'y']:
            print("CANCELLED")
            return
    except (EOFError, KeyboardInterrupt):
        print("\nCANCELLED")
        return
    
    # Perform renames
    print(f"Renaming...")
    success_count = 0
    
    for old_name, new_name, tenant_name in renames:
        old_path = uploads_path / old_name
        new_path = uploads_path / new_name
        
        try:
            if old_path.exists() and not new_path.exists():
                old_path.rename(new_path)
                print(f"SUCCESS: {tenant_name}")
                success_count += 1
            else:
                print(f"SKIPPED: {tenant_name}")
        except Exception as e:
            print(f"ERROR: {tenant_name} - {e}")
    
    print(f"COMPLETE: {success_count} renamed")

if __name__ == "__main__":
    main()