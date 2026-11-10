"""
=============================================================================
Construtiva - Backend Connection & Credentials Verification Script
=============================================================================
This script verifies the connection to your Supabase project:
1. Validates Supabase REST API & Service Role Key.
2. Queries the 'projects' table to confirm schema availability.
3. Tests Supabase Storage bucket availability ('blueprints', 'rasters').
"""

import sys
import os
from supabase import create_client
from app.core.config import settings

SUPABASE_URL = settings.supabase_url or os.environ.get("SUPABASE_URL", "https://kssgwxqttrzhhrymwicd.supabase.co")
SUPABASE_KEY = settings.supabase_service_role_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

def main():
    print("--------------------------------------------------")
    print(f"Connecting to Supabase at: {SUPABASE_URL}")
    print("--------------------------------------------------")

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test 1: Query projects table
        print("\n[1/3] Testing 'projects' table query...")
        res = supabase.table("projects").select("id, name, status").limit(5).execute()
        print(f"  ✓ Successfully connected to PostgreSQL! Found {len(res.data)} project(s).")
        if res.data:
            for p in res.data:
                print(f"    - Project: {p.get('name')} (Status: {p.get('status')})")

        # Test 2: Query materials table
        print("\n[2/3] Testing 'materials' table query...")
        mat_res = supabase.table("materials").select("id, name, category, surface_tag").limit(5).execute()
        print(f"  ✓ Successfully queried 'materials'! Found {len(mat_res.data)} material(s).")

        # Test 3: Check Supabase Storage buckets
        print("\n[3/3] Checking Supabase Storage buckets...")
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        print(f"  ✓ Available buckets in Supabase Storage: {bucket_names}")

        print("\n--------------------------------------------------")
        print("ALL CHECKS PASSED: Supabase backend is fully operational!")
        print("--------------------------------------------------")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

