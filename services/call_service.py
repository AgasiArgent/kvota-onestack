"""
Call Service - CRUD operations for kvota.calls table (Журнал звонков)

Provides:
- Create/Update/Delete call records
- Query calls by customer for customer detail tab
- Query all calls for registry page (cross-joined with customers, user_profiles, contacts)
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timezone
import logging
import os

from supabase import create_client, ClientOptions


logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

CALL_TYPE_LABELS = {
    "call": "Звонок",
    "scheduled": "Запланировать звонок",
}

CALL_CATEGORY_LABELS = {
    "cold": "Холодный",
    "warm": "Тёплый",
    "incoming": "Входящий",
}


def _get_supabase():
    """Get Supabase client with service role key for admin operations - kvota schema."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY,
        options=ClientOptions(schema="kvota")
    )


@dataclass
class CallRecord:
    """Represents a call/scheduled meeting record."""
    id: str
    organization_id: str
    customer_id: str
    user_id: str            # МОП user id

    call_type: str          # 'call' | 'scheduled'
    call_category: Optional[str] = None   # 'cold' | 'warm' | 'incoming'
    scheduled_date: Optional[datetime] = None
    comment: Optional[str] = None
    customer_needs: Optional[str] = None
    meeting_notes: Optional[str] = None
    contact_person_id: Optional[str] = None

    # Denormalized (populated by join queries)
    customer_name: Optional[str] = None
    contact_name: Optional[str] = None
    user_name: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _parse_call(data: dict) -> CallRecord:
    """Parse database row into CallRecord object.

    Uses safe FK null pattern: (data.get("fk") or {}).get("field")
    """
    def _dt(val):
        if not val:
            return None
        if isinstance(val, str):
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        return val

    # Denormalized fields from joins - safe FK null pattern
    customer_name = (data.get("customers") or {}).get("name", "")
    contact_name = (data.get("customer_contacts") or {}).get("name")

    # User name: populated by two-step fetch (user_profiles table)
    # The "user_profiles" key is injected Python-side after batch-fetching from kvota.user_profiles
    user_profiles_data = data.get("user_profiles") or {}
    user_name = user_profiles_data.get("full_name")

    return CallRecord(
        id=data["id"],
        organization_id=data["organization_id"],
        customer_id=data["customer_id"],
        user_id=data["user_id"],
        call_type=data.get("call_type", "call"),
        call_category=data.get("call_category") or None,
        scheduled_date=_dt(data.get("scheduled_date")),
        comment=data.get("comment"),
        customer_needs=data.get("customer_needs"),
        meeting_notes=data.get("meeting_notes"),
        contact_person_id=data.get("contact_person_id") or None,
        customer_name=customer_name,
        contact_name=contact_name,
        user_name=user_name,
        created_at=_dt(data.get("created_at")),
        updated_at=_dt(data.get("updated_at")),
    )


def sort_calls(records: List[CallRecord]) -> List[CallRecord]:
    """Sort calls: scheduled (upcoming, nearest first), then completed (newest first).

    Sorting rules:
    1. Scheduled calls with future dates appear FIRST, sorted by nearest date
    2. Completed calls appear AFTER, sorted by newest created_at first
    3. Past scheduled calls (missed) sort with completed calls by date desc
    """
    now = datetime.now(timezone.utc)

    def sort_key(r):
        # Scheduled calls with future dates go first (group 0)
        if r.call_type == "scheduled" and r.scheduled_date:
            # Make scheduled_date timezone-aware if needed for comparison
            sd = r.scheduled_date
            if sd.tzinfo is None:
                sd = sd.replace(tzinfo=timezone.utc)
            if sd >= now:
                return (0, sd.timestamp())
        # Everything else goes to group 1, sorted by newest first (negative timestamp)
        ts = 0
        if r.call_type == "scheduled" and r.scheduled_date:
            sd = r.scheduled_date
            if sd.tzinfo is None:
                sd = sd.replace(tzinfo=timezone.utc)
            ts = sd.timestamp()
        elif r.created_at:
            ca = r.created_at
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            ts = ca.timestamp()
        return (1, -ts)

    return sorted(records, key=sort_key)


def _enrich_user_names(client, rows: list) -> list:
    """Batch-fetch user names from user_profiles and inject into rows.

    Two-step fetch pattern (same as main.py):
    1. Collect unique user_ids from call rows
    2. Batch-fetch full_name from kvota.user_profiles
    3. Inject {"user_profiles": {"full_name": ...}} into each row
    """
    if not rows:
        return rows

    user_ids = list({r["user_id"] for r in rows if r.get("user_id")})
    if not user_ids:
        return rows

    profiles_map = {}
    try:
        # Batch fetch - PostgREST in_ filter
        profiles_resp = (
            client.table("user_profiles")
            .select("user_id, full_name")
            .in_("user_id", user_ids)
            .execute()
        )
        for p in (profiles_resp.data or []):
            profiles_map[p["user_id"]] = p.get("full_name")
    except Exception as e:
        logger.warning(f"Could not fetch user_profiles: {e}")

    # Inject into rows
    for row in rows:
        uid = row.get("user_id")
        full_name = profiles_map.get(uid) if uid else None
        row["user_profiles"] = {"full_name": full_name}

    return rows


def get_calls_for_customer(customer_id: str, limit: int = 50) -> List[CallRecord]:
    """Get call records for a specific customer, sorted by sort_calls logic."""
    try:
        client = _get_supabase()
        resp = (
            client.table("calls")
            .select("*, customers!calls_customer_id_fkey(id, name), customer_contacts!calls_contact_person_id_fkey(id, name)")
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
        # Two-step fetch: batch-resolve user names from user_profiles
        rows = _enrich_user_names(client, rows)
        records = [_parse_call(r) for r in rows]
        return sort_calls(records)
    except Exception as e:
        logger.error(f"Error fetching calls for customer {customer_id}: {e}")
        return []


def get_calls_registry(org_id: str, q: str = "", call_type: str = "",
                       user_id: str = "", limit: int = 200) -> List[CallRecord]:
    """Get all calls for registry page with joins and filters."""
    try:
        client = _get_supabase()
        query = (
            client.table("calls")
            .select("*, customers!calls_customer_id_fkey(id, name), customer_contacts!calls_contact_person_id_fkey(id, name)")
            .eq("organization_id", org_id)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        if call_type:
            query = query.eq("call_type", call_type)

        resp = query.order("created_at", desc=True).limit(limit).execute()
        rows = resp.data or []
        # Two-step fetch: batch-resolve user names from user_profiles
        rows = _enrich_user_names(client, rows)
        records = [_parse_call(r) for r in rows]

        # Apply text search filter after fetch (customer name, contact, comment)
        if q and q.strip():
            q_lower = q.strip().lower()
            records = [r for r in records if
                       (r.customer_name and q_lower in r.customer_name.lower()) or
                       (r.comment and q_lower in r.comment.lower()) or
                       (r.contact_name and q_lower in r.contact_name.lower())]

        return sort_calls(records)
    except Exception as e:
        logger.error(f"Error fetching calls registry for org {org_id}: {e}")
        return []


def get_call(call_id: str) -> Optional[CallRecord]:
    """Get a single call record by ID."""
    try:
        client = _get_supabase()
        resp = (
            client.table("calls")
            .select("*, customers!calls_customer_id_fkey(id, name), customer_contacts!calls_contact_person_id_fkey(id, name)")
            .eq("id", call_id)
            .execute()
        )
        if resp.data:
            rows = _enrich_user_names(client, resp.data)
            return _parse_call(rows[0])
        return None
    except Exception as e:
        logger.error(f"Error fetching call {call_id}: {e}")
        return None


def create_call(organization_id: str, customer_id: str, user_id: str,
                call_type: str = "call", call_category: str = None,
                scheduled_date: str = None, comment: str = None,
                customer_needs: str = None, meeting_notes: str = None,
                contact_person_id: str = None) -> Optional[CallRecord]:
    """Create a new call record."""
    try:
        client = _get_supabase()
        data = {
            "organization_id": organization_id,
            "customer_id": customer_id,
            "user_id": user_id,
            "call_type": call_type,
        }
        if call_category:
            data["call_category"] = call_category
        if scheduled_date:
            data["scheduled_date"] = scheduled_date
        if comment:
            data["comment"] = comment
        if customer_needs:
            data["customer_needs"] = customer_needs
        if meeting_notes:
            data["meeting_notes"] = meeting_notes
        if contact_person_id:
            data["contact_person_id"] = contact_person_id

        resp = client.table("calls").insert(data).execute()
        if resp.data:
            return _parse_call(resp.data[0])
        return None
    except Exception as e:
        logger.error(f"Error creating call: {e}")
        return None


def update_call(call_id: str, call_type: str = None, call_category: str = None,
                scheduled_date: str = None, comment: str = None,
                customer_needs: str = None, meeting_notes: str = None,
                contact_person_id: str = None) -> Optional[CallRecord]:
    """Update an existing call record. Pass None to skip a field."""
    try:
        update_data = {}
        if call_type is not None:
            update_data["call_type"] = call_type
        if call_category is not None:
            update_data["call_category"] = call_category or None
        if scheduled_date is not None:
            update_data["scheduled_date"] = scheduled_date or None
        if comment is not None:
            update_data["comment"] = comment or None
        if customer_needs is not None:
            update_data["customer_needs"] = customer_needs or None
        if meeting_notes is not None:
            update_data["meeting_notes"] = meeting_notes or None
        if contact_person_id is not None:
            update_data["contact_person_id"] = contact_person_id or None

        if not update_data:
            return get_call(call_id)

        client = _get_supabase()
        resp = client.table("calls").update(update_data).eq("id", call_id).execute()
        if resp.data:
            return _parse_call(resp.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating call {call_id}: {e}")
        return None


def delete_call(call_id: str) -> bool:
    """Delete a call record by ID."""
    try:
        client = _get_supabase()
        client.table("calls").delete().eq("id", call_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting call {call_id}: {e}")
        return False
