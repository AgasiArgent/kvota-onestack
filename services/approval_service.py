"""
Approval Service

CRUD operations for the approvals table.
Handles approval requests from quote controllers to top managers.

Feature #64 from features.json
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from .database import get_supabase


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Approval:
    """Represents an approval request for a quote."""
    id: str
    quote_id: str
    requested_by: str
    approver_id: str
    approval_type: str
    reason: str
    status: str  # 'pending', 'approved', 'rejected'
    decision_comment: Optional[str]
    requested_at: datetime
    decided_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict) -> 'Approval':
        """Create an Approval instance from a dictionary."""
        return cls(
            id=data['id'],
            quote_id=data['quote_id'],
            requested_by=data['requested_by'],
            approver_id=data['approver_id'],
            approval_type=data.get('approval_type', 'top_manager'),
            reason=data['reason'],
            status=data['status'],
            decision_comment=data.get('decision_comment'),
            requested_at=datetime.fromisoformat(data['requested_at'].replace('Z', '+00:00')) if isinstance(data['requested_at'], str) else data['requested_at'],
            decided_at=datetime.fromisoformat(data['decided_at'].replace('Z', '+00:00')) if data.get('decided_at') and isinstance(data['decided_at'], str) else data.get('decided_at'),
        )


# ============================================================================
# CREATE Operations
# ============================================================================

def create_approval(
    quote_id: str,
    requested_by: str,
    approver_id: str,
    reason: str,
    approval_type: str = 'top_manager'
) -> Optional[Approval]:
    """
    Create a new approval request.

    Args:
        quote_id: ID of the quote requiring approval
        requested_by: User ID of who is requesting approval (usually quote_controller)
        approver_id: User ID of who should approve (usually top_manager)
        reason: Reason why approval is needed
        approval_type: Type of approval (default: 'top_manager')

    Returns:
        Approval object if created successfully, None on error

    Example:
        approval = create_approval(
            quote_id='abc-123',
            requested_by='user-456',
            approver_id='manager-789',
            reason='RUB currency, markup below minimum'
        )
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').insert({
            'quote_id': quote_id,
            'requested_by': requested_by,
            'approver_id': approver_id,
            'approval_type': approval_type,
            'reason': reason,
            'status': 'pending'
        }).execute()

        if result.data:
            return Approval.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error creating approval: {e}")
        return None


def create_approvals_for_role(
    quote_id: str,
    organization_id: str,
    requested_by: str,
    reason: str,
    role_codes: List[str] = ['top_manager', 'admin'],
    approval_type: str = 'top_manager'
) -> List[Approval]:
    """
    Create approval requests for all users with specified roles in the organization.

    Args:
        quote_id: ID of the quote requiring approval
        organization_id: ID of the organization
        requested_by: User ID of who is requesting approval
        reason: Reason why approval is needed
        role_codes: List of role codes to send approvals to (default: top_manager, admin)
        approval_type: Type of approval (default: 'top_manager')

    Returns:
        List of created Approval objects

    Example:
        approvals = create_approvals_for_role(
            quote_id='abc-123',
            organization_id='org-456',
            requested_by='user-789',
            reason='Markup below minimum threshold'
        )
    """
    from .role_service import get_users_by_any_role

    # Get all users with the specified roles
    users = get_users_by_any_role(organization_id, role_codes)

    created_approvals = []
    for user in users:
        user_id = user.get('user_id')
        # Don't create approval for the requester themselves
        if user_id and user_id != requested_by:
            approval = create_approval(
                quote_id=quote_id,
                requested_by=requested_by,
                approver_id=user_id,
                reason=reason,
                approval_type=approval_type
            )
            if approval:
                created_approvals.append(approval)

    return created_approvals


# ============================================================================
# READ Operations
# ============================================================================

def get_approval(approval_id: str) -> Optional[Approval]:
    """
    Get a single approval by ID.

    Args:
        approval_id: UUID of the approval

    Returns:
        Approval object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select('*').eq('id', approval_id).execute()

        if result.data:
            return Approval.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting approval: {e}")
        return None


def get_approval_by_quote(quote_id: str, status: Optional[str] = None) -> Optional[Approval]:
    """
    Get the most recent approval for a quote.

    Args:
        quote_id: UUID of the quote
        status: Optional status filter ('pending', 'approved', 'rejected')

    Returns:
        Most recent Approval object if found, None otherwise
    """
    supabase = get_supabase()

    try:
        query = supabase.table('approvals').select('*').eq('quote_id', quote_id)

        if status:
            query = query.eq('status', status)

        result = query.order('requested_at', desc=True).limit(1).execute()

        if result.data:
            return Approval.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error getting approval by quote: {e}")
        return None


def get_approvals_for_quote(quote_id: str) -> List[Approval]:
    """
    Get all approvals for a quote, ordered by requested_at descending.

    Args:
        quote_id: UUID of the quote

    Returns:
        List of Approval objects
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select('*').eq('quote_id', quote_id).order('requested_at', desc=True).execute()

        return [Approval.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting approvals for quote: {e}")
        return []


def get_pending_approval_for_quote(quote_id: str) -> Optional[Approval]:
    """
    Get the pending approval for a quote (if any).

    Args:
        quote_id: UUID of the quote

    Returns:
        Pending Approval object if found, None otherwise
    """
    return get_approval_by_quote(quote_id, status='pending')


def get_pending_approvals_for_user(user_id: str, limit: int = 50) -> List[Approval]:
    """
    Get all pending approvals for a user (approvals they need to review).

    Args:
        user_id: UUID of the approver
        limit: Maximum number of results (default: 50)

    Returns:
        List of Approval objects that the user needs to review
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select('*').eq('approver_id', user_id).eq('status', 'pending').order('requested_at', desc=True).limit(limit).execute()

        return [Approval.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting pending approvals for user: {e}")
        return []


def get_approvals_requested_by(user_id: str, limit: int = 50) -> List[Approval]:
    """
    Get all approvals requested by a user.

    Args:
        user_id: UUID of the requester
        limit: Maximum number of results (default: 50)

    Returns:
        List of Approval objects requested by the user
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select('*').eq('requested_by', user_id).order('requested_at', desc=True).limit(limit).execute()

        return [Approval.from_dict(row) for row in result.data]
    except Exception as e:
        print(f"Error getting approvals requested by user: {e}")
        return []


def get_approvals_with_details(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    Get pending approvals for a user with quote details.

    Args:
        user_id: UUID of the approver
        status: Optional status filter ('pending', 'approved', 'rejected')
        limit: Maximum number of results

    Returns:
        List of dicts with approval and quote details
    """
    supabase = get_supabase()

    try:
        query = supabase.table('approvals').select(
            '*, quotes(id, idn, customer_name, workflow_status, total_amount, currency, organization_id)'
        ).eq('approver_id', user_id)

        if status:
            query = query.eq('status', status)

        result = query.order('requested_at', desc=True).limit(limit).execute()

        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting approvals with details: {e}")
        return []


def count_pending_approvals(user_id: str) -> int:
    """
    Count pending approvals for a user.

    Args:
        user_id: UUID of the approver

    Returns:
        Number of pending approvals
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select('id', count='exact').eq('approver_id', user_id).eq('status', 'pending').execute()

        return result.count if result.count else 0
    except Exception as e:
        print(f"Error counting pending approvals: {e}")
        return 0


# ============================================================================
# UPDATE Operations
# ============================================================================

def update_approval_status(
    approval_id: str,
    status: str,
    decision_comment: Optional[str] = None
) -> Optional[Approval]:
    """
    Update the status of an approval (approve or reject).

    Note: The database trigger will automatically set decided_at when status changes
    from 'pending' to 'approved' or 'rejected'.

    Args:
        approval_id: UUID of the approval
        status: New status ('approved' or 'rejected')
        decision_comment: Optional comment from the approver

    Returns:
        Updated Approval object if successful, None on error
    """
    if status not in ('approved', 'rejected'):
        print(f"Invalid approval status: {status}. Must be 'approved' or 'rejected'")
        return None

    supabase = get_supabase()

    try:
        update_data = {'status': status}
        if decision_comment:
            update_data['decision_comment'] = decision_comment

        result = supabase.table('approvals').update(update_data).eq('id', approval_id).eq('status', 'pending').execute()

        if result.data:
            return Approval.from_dict(result.data[0])
        return None
    except Exception as e:
        print(f"Error updating approval status: {e}")
        return None


def approve_quote_approval(
    approval_id: str,
    comment: Optional[str] = None
) -> Optional[Approval]:
    """
    Approve an approval request.

    Args:
        approval_id: UUID of the approval
        comment: Optional approval comment

    Returns:
        Updated Approval object if successful, None on error
    """
    return update_approval_status(approval_id, 'approved', comment)


def reject_quote_approval(
    approval_id: str,
    comment: Optional[str] = None
) -> Optional[Approval]:
    """
    Reject an approval request.

    Args:
        approval_id: UUID of the approval
        comment: Optional rejection reason

    Returns:
        Updated Approval object if successful, None on error
    """
    return update_approval_status(approval_id, 'rejected', comment)


# ============================================================================
# DELETE Operations (Note: Approvals are typically immutable audit records)
# ============================================================================

def cancel_pending_approvals_for_quote(quote_id: str) -> int:
    """
    Cancel (delete) all pending approvals for a quote.
    This might be needed when a quote is edited or workflow is reset.

    Note: Only pending approvals are deleted. Decided approvals are kept for audit.

    Args:
        quote_id: UUID of the quote

    Returns:
        Number of approvals cancelled
    """
    supabase = get_supabase()

    try:
        # First get count of pending approvals
        count_result = supabase.table('approvals').select('id', count='exact').eq('quote_id', quote_id).eq('status', 'pending').execute()

        count = count_result.count if count_result.count else 0

        if count > 0:
            # Delete pending approvals
            supabase.table('approvals').delete().eq('quote_id', quote_id).eq('status', 'pending').execute()

        return count
    except Exception as e:
        print(f"Error cancelling pending approvals: {e}")
        return 0


# ============================================================================
# Utility Functions
# ============================================================================

def has_pending_approval(quote_id: str) -> bool:
    """
    Check if a quote has any pending approvals.

    Args:
        quote_id: UUID of the quote

    Returns:
        True if there are pending approvals, False otherwise
    """
    approval = get_pending_approval_for_quote(quote_id)
    return approval is not None


def get_latest_approval_decision(quote_id: str) -> Optional[dict]:
    """
    Get the latest approval decision (approved or rejected) for a quote.

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict with status, comment, decided_at if found, None otherwise
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select('status, decision_comment, decided_at').eq('quote_id', quote_id).neq('status', 'pending').order('decided_at', desc=True).limit(1).execute()

        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error getting latest approval decision: {e}")
        return None


def get_approval_stats_for_user(user_id: str) -> dict:
    """
    Get approval statistics for a user (as an approver).

    Args:
        user_id: UUID of the approver

    Returns:
        Dict with pending, approved, rejected counts
    """
    supabase = get_supabase()

    stats = {
        'pending': 0,
        'approved': 0,
        'rejected': 0,
        'total': 0
    }

    try:
        for status in ['pending', 'approved', 'rejected']:
            result = supabase.table('approvals').select('id', count='exact').eq('approver_id', user_id).eq('status', status).execute()
            stats[status] = result.count if result.count else 0

        stats['total'] = stats['pending'] + stats['approved'] + stats['rejected']
        return stats
    except Exception as e:
        print(f"Error getting approval stats: {e}")
        return stats


# ============================================================================
# High-Level Approval Request Function (Feature #65)
# ============================================================================

@dataclass
class ApprovalRequestResult:
    """Result of a request_approval operation."""
    success: bool
    quote_id: str
    approvals_created: int
    notifications_sent: int
    transition_success: bool
    error_message: Optional[str] = None


def request_approval(
    quote_id: str,
    requested_by: str,
    reason: str,
    organization_id: str,
    actor_roles: List[str],
    quote_idn: Optional[str] = None,
    customer_name: Optional[str] = None,
    total_amount: Optional[float] = None,
    markup_percent: Optional[float] = None,
    payment_terms: Optional[str] = None,
    send_notifications: bool = True
) -> ApprovalRequestResult:
    """
    Request approval for a quote from top managers.

    This function performs the complete approval request workflow:
    1. Validates the quote is in the correct status (pending_quote_control)
    2. Transitions the quote to pending_approval status
    3. Creates approval records for all top_manager/admin users
    4. Sends Telegram notifications to approvers (optional)

    Args:
        quote_id: ID of the quote requiring approval
        requested_by: User ID of who is requesting approval (usually quote_controller)
        reason: Reason why approval is needed (e.g., "RUB currency, markup below minimum")
        organization_id: ID of the organization
        actor_roles: Roles of the user making the request
        quote_idn: Quote identifier for notifications (optional, fetched if not provided)
        customer_name: Customer name for notifications (optional, fetched if not provided)
        total_amount: Total amount for notifications (optional)
        markup_percent: Markup percentage for notifications (optional)
        payment_terms: Payment terms for notifications (optional)
        send_notifications: Whether to send Telegram notifications (default: True)

    Returns:
        ApprovalRequestResult with success status and details

    Example:
        result = request_approval(
            quote_id='abc-123',
            requested_by='user-456',
            reason='RUB currency, markup below 15%',
            organization_id='org-789',
            actor_roles=['quote_controller'],
            quote_idn='KP-2025-001',
            customer_name='ООО Клиент'
        )
        if result.success:
            print(f"Created {result.approvals_created} approvals")
    """
    from .workflow_service import (
        transition_quote_status,
        WorkflowStatus,
        get_quote_workflow_status
    )
    from .telegram_service import send_approval_notification_for_quote

    supabase = get_supabase()

    # Step 1: Validate current quote status
    current_status = get_quote_workflow_status(quote_id)

    if current_status is None:
        return ApprovalRequestResult(
            success=False,
            quote_id=quote_id,
            approvals_created=0,
            notifications_sent=0,
            transition_success=False,
            error_message="КП не найдено"
        )

    if current_status != WorkflowStatus.PENDING_QUOTE_CONTROL:
        return ApprovalRequestResult(
            success=False,
            quote_id=quote_id,
            approvals_created=0,
            notifications_sent=0,
            transition_success=False,
            error_message=f"КП не в статусе проверки. Текущий статус: {current_status.value}"
        )

    # Step 2: Fetch quote details if not provided
    if not quote_idn or not customer_name:
        try:
            quote_result = supabase.table('quotes').select(
                'idn, customer_name, total_amount, currency'
            ).eq('id', quote_id).execute()

            if quote_result.data:
                quote_data = quote_result.data[0]
                quote_idn = quote_idn or quote_data.get('idn', 'N/A')
                customer_name = customer_name or quote_data.get('customer_name', 'Не указан')
                total_amount = total_amount or quote_data.get('total_amount')
        except Exception as e:
            print(f"Error fetching quote details: {e}")

    # Step 3: Transition quote to pending_approval
    transition_result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_APPROVAL,
        actor_id=requested_by,
        actor_roles=actor_roles,
        comment=reason
    )

    if not transition_result.success:
        return ApprovalRequestResult(
            success=False,
            quote_id=quote_id,
            approvals_created=0,
            notifications_sent=0,
            transition_success=False,
            error_message=f"Не удалось перевести КП в статус ожидания согласования: {transition_result.error_message}"
        )

    # Step 4: Create approval records for all top_manager/admin users
    approvals = create_approvals_for_role(
        quote_id=quote_id,
        organization_id=organization_id,
        requested_by=requested_by,
        reason=reason,
        role_codes=['top_manager', 'admin'],
        approval_type='top_manager'
    )

    approvals_created = len(approvals)

    # Step 5: Send Telegram notifications (optional)
    notifications_sent = 0
    if send_notifications and approvals_created > 0:
        import asyncio

        try:
            # Run async notification in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            notification_result = loop.run_until_complete(
                send_approval_notification_for_quote(
                    quote_id=quote_id,
                    approval_reason=reason,
                    requester_id=requested_by
                )
            )

            notifications_sent = notification_result.get('telegram_sent', 0)
        except Exception as e:
            print(f"Error sending approval notifications: {e}")
            # Continue - notification failure shouldn't fail the overall request

    return ApprovalRequestResult(
        success=True,
        quote_id=quote_id,
        approvals_created=approvals_created,
        notifications_sent=notifications_sent,
        transition_success=True,
        error_message=None
    )
