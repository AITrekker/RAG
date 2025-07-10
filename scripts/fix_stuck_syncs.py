#!/usr/bin/env python3
"""
Fix stuck sync operations via API
"""
import requests
import json
from datetime import datetime, timedelta

def fix_stuck_syncs():
    """Fix stuck sync operations by calling API endpoints"""
    
    # API configuration
    base_url = "http://localhost:8000/api/v1"
    api_key = "tenant_tenant2_6f64c01dc83cd9b0fad463c99d7a6d50"
    headers = {"X-API-Key": api_key}
    
    # Get sync history
    print("🔍 Checking sync history...")
    response = requests.get(f"{base_url}/sync/history", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to get sync history: {response.status_code}")
        return
    
    history = response.json()
    
    # Find stuck operations
    stuck_ops = []
    for op in history["history"]:
        if op["status"] == "running" and op["completed_at"] is None:
            # Check if it's been running for more than 1 hour
            started_at = datetime.fromisoformat(op["started_at"].replace('Z', '+00:00'))
            if datetime.now(started_at.tzinfo) - started_at > timedelta(hours=1):
                stuck_ops.append(op)
    
    if not stuck_ops:
        print("✅ No stuck operations found!")
        return
    
    print(f"🔍 Found {len(stuck_ops)} stuck operations:")
    for op in stuck_ops:
        print(f"  - ID: {op['id']}")
        print(f"    Started: {op['started_at']}")
        print(f"    Status: {op['status']}")
        print()
    
    # The API doesn't have a direct way to mark operations as failed,
    # so let's try to trigger a new sync which should complete properly
    print("🔄 Triggering new sync to replace stuck operations...")
    
    response = requests.post(f"{base_url}/sync/trigger", headers=headers)
    
    if response.status_code == 200:
        print("✅ New sync triggered successfully!")
        print("💡 The new sync should complete properly and the frontend should stop polling.")
    else:
        print(f"❌ Failed to trigger new sync: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    fix_stuck_syncs()