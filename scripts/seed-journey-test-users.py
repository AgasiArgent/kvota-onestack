#!/usr/bin/env python3
"""
Journey Test User Seed (Task 25 — Customer Journey Map).

Creates one QA test user per active role for the nightly Playwright
screenshots pipeline (Req 10.3, 10.4). Idempotent: safe to re-run —
existing users are detected and only missing role rows are inserted.

Email pattern:   qa-{role_slug}@kvotaflow.ru
Password source: env var JOURNEY_TEST_USERS_PASSWORD (required)
Org target:      first active kvota.organizations row

Usage (staging / prod, not local dev):
    export SUPABASE_URL=...
    export SUPABASE_SERVICE_ROLE_KEY=...
    export JOURNEY_TEST_USERS_PASSWORD=...
    python scripts/seed-journey-test-users.py

Note: this script is NOT run by CI. It is a one-time staging/prod
bootstrap invoked manually by an admin. Re-runs are safe.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.client import ClientOptions

load_dotenv()

# Brief-aligned list: 13 active role slugs (see CLAUDE.md memory + access-control.md).
# Requirements doc §10.4 says "12 test users" — stale; `procurement_senior` was
# added after the requirements were written. We seed 13.
ROLE_SLUGS: tuple[str, ...] = (
    "admin",
    "sales",
    "procurement",
    "procurement_senior",
    "logistics",
    "customs",
    "quote_controller",
    "spec_controller",
    "finance",
    "top_manager",
    "head_of_sales",
    "head_of_procurement",
    "head_of_logistics",
)


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _get_supabase() -> Client:
    url = _env("SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key, options=ClientOptions(schema="kvota"))


def _find_user_by_email(sb: Client, email: str) -> str | None:
    """Look up an existing auth.users id by email.

    Supabase admin list_users pages — fine for our small org.
    """
    try:
        page = 1
        while True:
            resp = sb.auth.admin.list_users(page=page, per_page=1000)
            users = resp if isinstance(resp, list) else getattr(resp, "users", [])
            if not users:
                return None
            for u in users:
                u_email = getattr(u, "email", None)
                if u_email and u_email.lower() == email.lower():
                    return str(u.id)
            if len(users) < 1000:
                return None
            page += 1
    except Exception as exc:  # pragma: no cover — diagnostic path
        print(f"  ! list_users lookup failed for {email}: {exc}")
        return None


def _ensure_user(sb: Client, email: str, password: str) -> str:
    """Create the auth user if missing; return user_id either way."""
    existing_id = _find_user_by_email(sb, email)
    if existing_id:
        print(f"  auth user exists: {existing_id[:8]}…")
        return existing_id

    resp = sb.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    user_id = str(resp.user.id)
    print(f"  auth user created: {user_id[:8]}…")
    return user_id


def _ensure_org_member(sb: Client, user_id: str, org_id: str) -> None:
    existing = (
        sb.table("organization_members")
        .select("id")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if existing.data:
        return
    sb.table("organization_members").insert(
        {
            "user_id": user_id,
            "organization_id": org_id,
            "status": "active",
            "is_owner": False,
        }
    ).execute()
    print("  org membership: inserted")


def _ensure_role_assignment(
    sb: Client, user_id: str, org_id: str, role_id: str, role_slug: str
) -> None:
    existing = (
        sb.table("user_roles")
        .select("id")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .eq("role_id", role_id)
        .execute()
    )
    if existing.data:
        print(f"  role {role_slug}: already assigned")
        return
    sb.table("user_roles").insert(
        {
            "user_id": user_id,
            "organization_id": org_id,
            "role_id": role_id,
        }
    ).execute()
    print(f"  role {role_slug}: assigned")


def _load_role_map(sb: Client, needed: Iterable[str]) -> dict[str, str]:
    roles = sb.table("roles").select("id, slug").execute().data
    role_map = {r["slug"]: r["id"] for r in roles}
    missing = sorted(set(needed) - role_map.keys())
    if missing:
        raise SystemExit(
            f"Role slugs not present in kvota.roles: {missing!r}. "
            "Apply role migrations before seeding."
        )
    return role_map


def _pick_org_id(sb: Client) -> str:
    # Prefer the oldest active org — stable choice across re-runs.
    resp = (
        sb.table("organizations")
        .select("id, name, is_active, created_at")
        .eq("is_active", True)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise SystemExit("No active kvota.organizations row found.")
    org = resp.data[0]
    print(f"Target org: {org['name']} ({org['id']})")
    return org["id"]


def main() -> None:
    password = _env("JOURNEY_TEST_USERS_PASSWORD")
    sb = _get_supabase()

    print("=" * 60)
    print("Journey QA test user seed")
    print("=" * 60)

    org_id = _pick_org_id(sb)
    role_map = _load_role_map(sb, ROLE_SLUGS)

    for slug in ROLE_SLUGS:
        email = f"qa-{slug}@kvotaflow.ru"
        print(f"\n--- {email} ---")
        try:
            user_id = _ensure_user(sb, email, password)
            _ensure_org_member(sb, user_id, org_id)
            _ensure_role_assignment(sb, user_id, org_id, role_map[slug], slug)
        except Exception as exc:
            # Don't bail — try the rest, report at end.
            print(f"  ! error: {exc}")

    print("\n" + "=" * 60)
    print(f"Seed complete. {len(ROLE_SLUGS)} roles processed against org {org_id}.")
    print("=" * 60)


if __name__ == "__main__":
    main()
