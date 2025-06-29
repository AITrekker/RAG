#!/usr/bin/env python3
"""
debug-admin.py

A. Reactivate the admin tenant if it exists but is inactive.
B. If the admin tenant does not exist, run setup_demo_tenants.py to recreate it.

Usage:
    python scripts/debug-admin.py
"""
import subprocess
import sys

def run_psql(query):
    cmd = [
        'docker', 'compose', 'exec', 'postgres', 'psql',
        '-U', 'rag_user', '-d', 'rag_db', '-t', '-c', query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

def admin_status():
    query = "SELECT is_active FROM tenants WHERE slug = 'system_admin';"
    out = run_psql(query)
    if not out:
        return None
    return out.strip()

def reactivate_admin():
    print("[INFO] Reactivating admin tenant...")
    query = "UPDATE tenants SET is_active = true WHERE slug = 'system_admin';"
    run_psql(query)
    print("[SUCCESS] Admin tenant reactivated.")

def main():
    print("[DEBUG] Checking admin tenant status...")
    status = admin_status()
    if status is None:
        print("[WARN] Admin tenant does not exist. Running setup_demo_tenants.py to recreate it...")
        subprocess.run([sys.executable, 'scripts/setup_demo_tenants.py'])
        print("[SUCCESS] Admin tenant recreated.")
    elif status == 't':
        print("[INFO] Admin tenant is already active.")
    else:
        reactivate_admin()

if __name__ == "__main__":
    main() 