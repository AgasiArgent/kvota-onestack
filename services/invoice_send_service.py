"""
Invoice Send Service

Handles the invoice send lifecycle: drafting letters, committing sends
(both XLS download and letter draft paths), and tracking send history.

The commit_invoice_send function is the single atomic commit point —
it writes the letter_drafts audit row AND updates invoices.sent_at
in one logical operation.
"""

from datetime import datetime, timezone
from typing import Optional

from .database import get_supabase


# Roles that can edit a sent invoice without approval
_EDIT_OVERRIDE_ROLES = {"admin", "head_of_procurement"}


# ============================================================================
# Core: Atomic Commit
# ============================================================================

def commit_invoice_send(
    invoice_id: str,
    user_id: str,
    method: str,
    language: str = "ru",
    recipient_email: Optional[str] = None,
    subject: Optional[str] = None,
    body_text: Optional[str] = None,
) -> dict:
    """Atomic commit: insert letter_drafts row with sent_at + update invoices.sent_at.

    This is the single commit point for both XLS download and letter draft paths.

    Args:
        invoice_id: UUID of the invoice being sent.
        user_id: UUID of the user performing the send.
        method: 'xls_download' or 'letter_draft'.
        language: 'ru' or 'en' (default 'ru').
        recipient_email: Supplier email (for letter_draft method).
        subject: Email subject (for letter_draft method).
        body_text: Email body (for letter_draft method).

    Returns:
        The created invoice_letter_drafts row as a dict.
    """
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # 1. Insert letter_drafts row with sent_at set (marks as committed)
    draft_data = {
        "invoice_id": invoice_id,
        "created_by": user_id,
        "method": method,
        "language": language,
        "recipient_email": recipient_email,
        "subject": subject,
        "body_text": body_text,
        "sent_at": now,
    }
    result = sb.table("invoice_letter_drafts").insert(draft_data).execute()
    created_draft = result.data[0]

    # 2. Update invoices.sent_at (denormalized for fast filtering)
    sb.table("invoices").update({"sent_at": now}).eq("id", invoice_id).execute()

    return created_draft


# ============================================================================
# Draft CRUD
# ============================================================================

def save_draft(invoice_id: str, user_id: str, data: dict) -> dict:
    """Create or update the active (unsent) draft for an invoice.

    If an active draft exists (sent_at IS NULL), update it.
    If not, insert a new one.

    Args:
        invoice_id: UUID of the invoice.
        user_id: UUID of the acting user.
        data: Dict with draft fields: language, recipient_email, subject, body_text.

    Returns:
        The created or updated draft row.
    """
    sb = get_supabase()

    # Check for existing active draft
    existing = (
        sb.table("invoice_letter_drafts")
        .select("*")
        .eq("invoice_id", invoice_id)
        .is_("sent_at", "null")
        .execute()
    )

    update_fields = {
        "language": data.get("language", "ru"),
        "recipient_email": data.get("recipient_email"),
        "subject": data.get("subject"),
        "body_text": data.get("body_text"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing.data:
        # Update existing draft
        draft_id = existing.data[0]["id"]
        result = (
            sb.table("invoice_letter_drafts")
            .update(update_fields)
            .eq("id", draft_id)
            .execute()
        )
        return result.data[0]

    # Create new draft
    insert_data = {
        "invoice_id": invoice_id,
        "created_by": user_id,
        "method": "letter_draft",
        **update_fields,
    }
    result = sb.table("invoice_letter_drafts").insert(insert_data).execute()
    return result.data[0]


def get_active_draft(invoice_id: str) -> Optional[dict]:
    """Return the unsent draft for an invoice, or None.

    Args:
        invoice_id: UUID of the invoice.

    Returns:
        Draft row dict, or None if no active draft exists.
    """
    sb = get_supabase()
    result = (
        sb.table("invoice_letter_drafts")
        .select("*")
        .eq("invoice_id", invoice_id)
        .is_("sent_at", "null")
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


# ============================================================================
# Send History
# ============================================================================

def get_send_history(invoice_id: str) -> list[dict]:
    """Return all sent drafts for an invoice, ordered by sent_at DESC.

    Args:
        invoice_id: UUID of the invoice.

    Returns:
        List of sent draft rows (sent_at IS NOT NULL), newest first.
    """
    sb = get_supabase()
    result = (
        sb.table("invoice_letter_drafts")
        .select("*")
        .eq("invoice_id", invoice_id)
        .not_.is_("sent_at", "null")
        .order("sent_at", desc=True)
        .execute()
    )
    return result.data


# ============================================================================
# Status Checks
# ============================================================================

def is_invoice_procurement_locked(invoice_id: str) -> bool:
    """Return True iff the invoice itself has procurement_completed_at set.

    Per-invoice procurement closure (post PR #74): each КП (invoice) is
    locked independently when МОЗ clicks «Завершить закупку по КП». The
    legacy quote-level ``quotes.procurement_completed_at`` flag is no
    longer the source of truth — it stays NULL after the migration to the
    per-invoice model.

    Fail-open: a missing invoice row does not engage the lock.

    Args:
        invoice_id: UUID of the invoice.

    Returns:
        True if this invoice is procurement-locked, False otherwise.
    """
    sb = get_supabase()
    inv = (
        sb.table("invoices")
        .select("procurement_completed_at")
        .eq("id", invoice_id)
        .single()
        .execute()
    )
    if not inv.data:
        return False

    return inv.data.get("procurement_completed_at") is not None


# Phase 5c name retained as an alias so older imports keep compiling.
# The old quote-level lookup was removed in the per-invoice migration; new
# code should call ``is_invoice_procurement_locked`` directly.
is_quote_procurement_locked = is_invoice_procurement_locked


def check_edit_permission(invoice_id: str, user_roles: list[str]) -> bool:
    """Check if the user can edit an invoice.

    Phase 5c semantics: the gate fires when the parent quote's procurement
    stage has completed. Regular roles can edit freely during procurement
    (including after the "request for pricing" send). Once procurement is
    locked, only override roles (admin, head_of_procurement) can edit.

    Args:
        invoice_id: UUID of the invoice.
        user_roles: List of role slugs for the current user.

    Returns:
        True if edit is permitted.
    """
    if not is_invoice_procurement_locked(invoice_id):
        return True  # Procurement still active: anyone in roles can edit.

    # Procurement locked — only override roles can edit.
    return bool(set(user_roles) & _EDIT_OVERRIDE_ROLES)
