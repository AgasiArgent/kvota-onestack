#!/usr/bin/env python3
"""Fix passwords for non-working test accounts."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Non-working accounts that need password reset
NON_WORKING_ACCOUNTS = [
    "sales@test.kvota.ru",
    "procurement@test.kvota.ru",
    "quote-control@test.kvota.ru",
    "spec-control@test.kvota.ru",
    "top-manager@test.kvota.ru",
]

PASSWORD = "Test123!"

def get_supabase():
    """Get Supabase client with service role key."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)

def main():
    print("=" * 60)
    print("Fixing Test User Passwords")
    print("=" * 60)

    supabase = get_supabase()

    # Get all users
    users_response = supabase.auth.admin.list_users()

    for user in users_response:
        if user.email in NON_WORKING_ACCOUNTS:
            print(f"\nUpdating password for: {user.email}")
            try:
                supabase.auth.admin.update_user_by_id(
                    user.id,
                    {"password": PASSWORD}
                )
                print(f"  ✓ Password updated successfully")
            except Exception as e:
                print(f"  ✗ Error: {e}")

    print("\n" + "=" * 60)
    print("Password reset complete!")
    print("=" * 60)
    print(f"\nAll accounts should now work with password: {PASSWORD}")

if __name__ == "__main__":
    main()
