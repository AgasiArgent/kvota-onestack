#!/usr/bin/env python3
"""
Test User Creation Script for E2E Testing

Creates 10 test users with different roles for comprehensive testing.
Run with --cleanup flag to remove test users after testing.

Usage:
    python scripts/create_test_users.py          # Create test users
    python scripts/create_test_users.py --cleanup # Remove test users
"""

import os
import sys
import argparse
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Test user definitions
TEST_USERS = [
    {"email": "sales@test.kvota.ru", "password": "Test123!", "roles": ["sales"]},
    {"email": "procurement@test.kvota.ru", "password": "Test123!", "roles": ["procurement"]},
    {"email": "logistics@test.kvota.ru", "password": "Test123!", "roles": ["logistics"]},
    {"email": "customs@test.kvota.ru", "password": "Test123!", "roles": ["customs"]},
    {"email": "quote-control@test.kvota.ru", "password": "Test123!", "roles": ["quote_controller"]},
    {"email": "spec-control@test.kvota.ru", "password": "Test123!", "roles": ["spec_controller"]},
    {"email": "finance@test.kvota.ru", "password": "Test123!", "roles": ["finance"]},
    {"email": "top-manager@test.kvota.ru", "password": "Test123!", "roles": ["top_manager"]},
    {"email": "admin@test.kvota.ru", "password": "Test123!", "roles": ["admin"]},
    {"email": "multi-role@test.kvota.ru", "password": "Test123!", "roles": ["sales", "procurement", "logistics"]},
]

# Brands to assign to procurement user
PROCUREMENT_BRANDS = ["SKF", "TIMKEN", "FAG"]


def get_supabase() -> Client:
    """Get Supabase client with service role key."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def get_existing_org_id(supabase: Client) -> Optional[str]:
    """Get organization ID from existing user (andrey@masterbearingsales.ru)."""
    result = supabase.table("organization_members") \
        .select("organization_id") \
        .limit(1) \
        .execute()

    if result.data:
        return result.data[0]["organization_id"]
    return None


def get_role_map(supabase: Client) -> dict:
    """Get mapping of role codes to role IDs from the roles table."""
    # Query all roles - existing DB uses 'slug' column
    result = supabase.table("roles") \
        .select("id, slug") \
        .execute()
    role_map = {row["slug"]: row["id"] for row in result.data}

    return role_map


def create_test_users(supabase: Client, org_id: str, role_map: dict):
    """Create test users with their roles."""
    created_users = []

    for user_def in TEST_USERS:
        email = user_def["email"]
        password = user_def["password"]
        roles = user_def["roles"]

        print(f"\nCreating user: {email}")

        try:
            # Create user via Supabase Auth Admin API
            user_response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True  # Skip email confirmation
            })

            user_id = user_response.user.id
            print(f"  User created: {user_id}")

            # Add to organization_members (required for org access)
            supabase.table("organization_members").insert({
                "user_id": str(user_id),
                "organization_id": org_id,
                "status": "active",
                "is_owner": False
            }).execute()
            print(f"  Added to organization")

            # Assign roles via user_roles table (supports multi-role)
            for role_code in roles:
                role_id = role_map.get(role_code)
                if role_id:
                    try:
                        supabase.table("user_roles").insert({
                            "user_id": str(user_id),
                            "organization_id": org_id,
                            "role_id": role_id
                        }).execute()
                        print(f"  Role assigned: {role_code}")
                    except Exception as e:
                        print(f"  Warning: Could not assign role {role_code}: {e}")
                else:
                    print(f"  Warning: Role '{role_code}' not found in database")

            # Assign brands for procurement user
            if "procurement" in roles:
                try:
                    for brand in PROCUREMENT_BRANDS:
                        supabase.table("brand_assignments").insert({
                            "organization_id": org_id,
                            "brand": brand,
                            "user_id": str(user_id)
                        }).execute()
                        print(f"  Brand assigned: {brand}")
                except Exception as e:
                    print(f"  Brand assignments skipped: {e}")

            created_users.append({"email": email, "user_id": str(user_id)})

        except Exception as e:
            if "already been registered" in str(e) or "already exists" in str(e).lower():
                print(f"  User already exists, skipping...")
            else:
                print(f"  ERROR: {e}")

    return created_users


def cleanup_test_users(supabase: Client):
    """Remove all test users."""
    print("\nCleaning up test users...")

    for user_def in TEST_USERS:
        email = user_def["email"]
        print(f"\nRemoving user: {email}")

        try:
            # Find user by email
            users_response = supabase.auth.admin.list_users()
            user_id = None
            for user in users_response:
                if user.email == email:
                    user_id = user.id
                    break

            if not user_id:
                print(f"  User not found, skipping...")
                continue

            # Remove brand assignments (if table exists)
            try:
                supabase.table("brand_assignments") \
                    .delete() \
                    .eq("user_id", str(user_id)) \
                    .execute()
                print(f"  Brand assignments removed")
            except:
                pass  # Table may not exist

            # Remove from user_roles (role assignments)
            try:
                supabase.table("user_roles") \
                    .delete() \
                    .eq("user_id", str(user_id)) \
                    .execute()
                print(f"  Role assignments removed")
            except:
                pass  # Table may not exist

            # Remove from organization_members
            supabase.table("organization_members") \
                .delete() \
                .eq("user_id", str(user_id)) \
                .execute()
            print(f"  Removed from organization")

            # Delete user from auth
            supabase.auth.admin.delete_user(user_id)
            print(f"  User deleted")

        except Exception as e:
            print(f"  ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(description="Create or cleanup test users for E2E testing")
    parser.add_argument("--cleanup", action="store_true", help="Remove test users instead of creating them")
    args = parser.parse_args()

    print("=" * 60)
    print("OneStack Test User Management")
    print("=" * 60)

    supabase = get_supabase()

    if args.cleanup:
        cleanup_test_users(supabase)
        print("\n" + "=" * 60)
        print("Cleanup complete!")
    else:
        # Get organization ID
        org_id = get_existing_org_id(supabase)
        if not org_id:
            print("ERROR: No organization found. Please ensure at least one user exists.")
            sys.exit(1)
        print(f"Using organization: {org_id}")

        # Get role mapping
        role_map = get_role_map(supabase)
        print(f"Found roles: {list(role_map.keys())}")

        # Create users
        created = create_test_users(supabase, org_id, role_map)

        print("\n" + "=" * 60)
        print("Test users created successfully!")
        print("=" * 60)
        print("\nTest Accounts:")
        print("-" * 60)
        for user_def in TEST_USERS:
            print(f"  {user_def['email']}")
            print(f"    Password: {user_def['password']}")
            print(f"    Roles: {', '.join(user_def['roles'])}")
            print()


if __name__ == "__main__":
    main()
