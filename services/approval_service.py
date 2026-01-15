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
    modifications: Optional[dict] = None  # v3.0: JSON with modifications made by approver

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
            modifications=data.get('modifications'),
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
            '*, quotes(id, idn_quote, workflow_status, total_amount, currency, organization_id, customers(name))'
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
# High-Level Approval Decision Function (Feature #66)
# ============================================================================

@dataclass
class ApprovalDecisionResult:
    """Result of a process_approval_decision operation."""
    success: bool
    approval_id: str
    quote_id: Optional[str]
    quote_idn: Optional[str]
    decision: str  # 'approved' or 'rejected'
    new_status: Optional[str]
    other_approvals_cancelled: int
    notifications_sent: int
    error_message: Optional[str] = None


def process_approval_decision(
    approval_id: str,
    decision: str,
    comment: Optional[str] = None,
    decider_id: Optional[str] = None,
    decider_roles: Optional[List[str]] = None,
    send_notifications: bool = True
) -> ApprovalDecisionResult:
    """
    Process an approval decision (approve or reject) from a top manager.

    This function performs the complete approval decision workflow:
    1. Validates the approval exists and is pending
    2. Updates the approval record with the decision
    3. Transitions the quote to the appropriate status (approved or rejected)
    4. Cancels any other pending approvals for the same quote
    5. Sends notifications to the quote creator (optional)

    Args:
        approval_id: ID of the approval to process
        decision: Decision ('approved' or 'rejected')
        comment: Optional comment from the approver
        decider_id: ID of the user making the decision (for audit trail)
        decider_roles: Roles of the user making the decision
        send_notifications: Whether to send notifications (default: True)

    Returns:
        ApprovalDecisionResult with success status and details

    Example:
        result = process_approval_decision(
            approval_id='abc-123',
            decision='approved',
            comment='Одобрено. Хорошая сделка.',
            decider_id='user-456',
            decider_roles=['top_manager']
        )
        if result.success:
            print(f"Quote {result.quote_idn} is now {result.new_status}")
    """
    from .workflow_service import (
        transition_quote_status,
        WorkflowStatus,
        get_quote_workflow_status
    )

    supabase = get_supabase()

    # Validate decision value
    if decision not in ('approved', 'rejected'):
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=None,
            quote_idn=None,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message=f"Недопустимое решение: {decision}. Должно быть 'approved' или 'rejected'"
        )

    # Step 1: Get and validate the approval
    approval = get_approval(approval_id)

    if approval is None:
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=None,
            quote_idn=None,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message="Запрос на согласование не найден"
        )

    if approval.status != 'pending':
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=approval.quote_id,
            quote_idn=None,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message=f"Запрос уже обработан. Текущий статус: {approval.status}"
        )

    quote_id = approval.quote_id

    # Step 2: Verify quote is in pending_approval status
    current_status = get_quote_workflow_status(quote_id)

    if current_status is None:
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            quote_idn=None,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message="КП не найдено"
        )

    if current_status != WorkflowStatus.PENDING_APPROVAL:
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            quote_idn=None,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message=f"КП не в статусе ожидания согласования. Текущий статус: {current_status.value}"
        )

    # Step 3: Fetch quote details for notifications
    quote_idn = None
    customer_name = None
    quote_creator_id = None

    try:
        quote_result = supabase.table('quotes').select(
            'idn, customer_name, created_by'
        ).eq('id', quote_id).execute()

        if quote_result.data:
            quote_data = quote_result.data[0]
            quote_idn = quote_data.get('idn', 'N/A')
            customer_name = quote_data.get('customer_name', 'Не указан')
            quote_creator_id = quote_data.get('created_by')
    except Exception as e:
        print(f"Error fetching quote details: {e}")

    # Step 4: Update the approval record
    updated_approval = update_approval_status(approval_id, decision, comment)

    if updated_approval is None:
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            quote_idn=quote_idn,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message="Не удалось обновить статус согласования"
        )

    # Step 5: Transition quote to appropriate status
    target_status = WorkflowStatus.APPROVED if decision == 'approved' else WorkflowStatus.REJECTED

    # Get actor info
    actor_id = decider_id or approval.approver_id
    actor_roles = decider_roles or ['top_manager']

    # Generate default comment if none provided
    transition_comment = comment or (
        "Одобрено топ-менеджером" if decision == 'approved'
        else "Отклонено топ-менеджером"
    )

    transition_result = transition_quote_status(
        quote_id=quote_id,
        to_status=target_status,
        actor_id=actor_id,
        actor_roles=actor_roles,
        comment=transition_comment
    )

    if not transition_result.success:
        # Rollback approval status (try to revert to pending)
        # Note: This is best effort - the approval may already be marked as decided
        print(f"Warning: Could not transition quote after approval decision: {transition_result.error_message}")
        return ApprovalDecisionResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            quote_idn=quote_idn,
            decision=decision,
            new_status=None,
            other_approvals_cancelled=0,
            notifications_sent=0,
            error_message=f"Не удалось изменить статус КП: {transition_result.error_message}"
        )

    new_status = target_status.value

    # Step 6: Cancel other pending approvals for this quote
    # (Since one manager made a decision, others don't need to)
    other_approvals_cancelled = 0
    try:
        # Count other pending approvals (excluding the one we just processed)
        count_result = supabase.table('approvals').select(
            'id', count='exact'
        ).eq('quote_id', quote_id).eq('status', 'pending').neq('id', approval_id).execute()

        other_pending = count_result.count if count_result.count else 0

        if other_pending > 0:
            # Update other pending approvals to 'cancelled' status (if we want to keep them)
            # Or delete them entirely
            # For now, let's delete them to keep the data clean
            supabase.table('approvals').delete().eq(
                'quote_id', quote_id
            ).eq('status', 'pending').neq('id', approval_id).execute()

            other_approvals_cancelled = other_pending
    except Exception as e:
        print(f"Error cancelling other approvals: {e}")
        # Continue - this is not critical

    # Step 7: Send notifications (optional)
    notifications_sent = 0
    if send_notifications and quote_creator_id:
        import asyncio
        from .telegram_service import send_status_changed_notification

        try:
            # Get decider name for notification
            decider_name = "Топ-менеджер"
            if actor_id:
                try:
                    user_result = supabase.table('profiles').select('name').eq('id', actor_id).execute()
                    if user_result.data:
                        decider_name = user_result.data[0].get('name', 'Топ-менеджер')
                except Exception:
                    pass

            # Run async notification in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            notification_result = loop.run_until_complete(
                send_status_changed_notification(
                    user_id=quote_creator_id,
                    quote_id=quote_id,
                    quote_idn=quote_idn or 'N/A',
                    customer_name=customer_name or 'Не указан',
                    old_status='pending_approval',
                    new_status=new_status,
                    actor_name=decider_name,
                    comment=comment
                )
            )

            if notification_result.get('success'):
                notifications_sent = 1

            # Also notify the requester if different from creator
            if approval.requested_by != quote_creator_id:
                notification_result = loop.run_until_complete(
                    send_status_changed_notification(
                        user_id=approval.requested_by,
                        quote_id=quote_id,
                        quote_idn=quote_idn or 'N/A',
                        customer_name=customer_name or 'Не указан',
                        old_status='pending_approval',
                        new_status=new_status,
                        actor_name=decider_name,
                        comment=comment
                    )
                )
                if notification_result.get('success'):
                    notifications_sent += 1

        except Exception as e:
            print(f"Error sending approval decision notifications: {e}")
            # Continue - notification failure shouldn't fail the overall process

    return ApprovalDecisionResult(
        success=True,
        approval_id=approval_id,
        quote_id=quote_id,
        quote_idn=quote_idn,
        decision=decision,
        new_status=new_status,
        other_approvals_cancelled=other_approvals_cancelled,
        notifications_sent=notifications_sent,
        error_message=None
    )


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


# ============================================================================
# WF-005: Approval with Modifications (v3.0)
# ============================================================================

# Allowed modification fields for quote-level changes
ALLOWED_QUOTE_MODIFICATIONS = [
    'margin_percent',       # Изменение маржи
    'payment_terms',        # Условия оплаты
    'currency',             # Валюта (редко)
    'notes',                # Примечания к согласованию
    'delivery_terms',       # Условия доставки
]

# Allowed modification fields for item-level changes
ALLOWED_ITEM_MODIFICATIONS = [
    'sale_price',           # Продажная цена
    'purchase_price',       # Закупочная цена
    'quantity',             # Количество
    'notes',                # Примечания к позиции
]


@dataclass
class ModificationValidationResult:
    """Result of modifications validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sanitized_modifications: Optional[dict] = None


def validate_modifications(modifications: dict) -> ModificationValidationResult:
    """
    Validate modifications structure for approval.

    Allowed structure:
    {
        "margin_percent": 15,              # Quote-level numeric
        "payment_terms": "50% advance",     # Quote-level string
        "notes": "Approved with changes",   # Quote-level string
        "items": [                          # Item-level array (optional)
            {
                "item_id": "uuid-here",
                "sale_price": 1500.00,
                "notes": "Reduced price"
            }
        ]
    }

    Args:
        modifications: Dict with proposed modifications

    Returns:
        ModificationValidationResult with validation status
    """
    errors = []
    warnings = []
    sanitized = {}

    if not isinstance(modifications, dict):
        return ModificationValidationResult(
            is_valid=False,
            errors=["Modifications must be a dictionary"],
            warnings=[],
            sanitized_modifications=None
        )

    # Validate quote-level modifications
    for key, value in modifications.items():
        if key == 'items':
            # Handle items array separately
            continue

        if key not in ALLOWED_QUOTE_MODIFICATIONS:
            warnings.append(f"Unknown modification field: {key} (will be ignored)")
            continue

        # Type validation for known fields
        if key == 'margin_percent':
            if not isinstance(value, (int, float)):
                errors.append(f"margin_percent must be a number, got {type(value).__name__}")
            elif value < 0 or value > 100:
                errors.append(f"margin_percent must be between 0 and 100, got {value}")
            else:
                sanitized[key] = float(value)
        elif key in ('payment_terms', 'notes', 'delivery_terms', 'currency'):
            if not isinstance(value, str):
                errors.append(f"{key} must be a string, got {type(value).__name__}")
            elif len(value) > 1000:
                errors.append(f"{key} too long (max 1000 chars)")
            else:
                sanitized[key] = value.strip()

    # Validate item-level modifications
    items = modifications.get('items', [])
    if items:
        if not isinstance(items, list):
            errors.append("items must be an array")
        else:
            sanitized_items = []
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"items[{i}] must be a dictionary")
                    continue

                if 'item_id' not in item:
                    errors.append(f"items[{i}] missing required field: item_id")
                    continue

                sanitized_item = {'item_id': item['item_id']}

                for key, value in item.items():
                    if key == 'item_id':
                        continue

                    if key not in ALLOWED_ITEM_MODIFICATIONS:
                        warnings.append(f"items[{i}].{key}: unknown field (will be ignored)")
                        continue

                    # Type validation
                    if key in ('sale_price', 'purchase_price'):
                        if not isinstance(value, (int, float)):
                            errors.append(f"items[{i}].{key} must be a number")
                        elif value < 0:
                            errors.append(f"items[{i}].{key} must be non-negative")
                        else:
                            sanitized_item[key] = float(value)
                    elif key == 'quantity':
                        if not isinstance(value, (int, float)):
                            errors.append(f"items[{i}].quantity must be a number")
                        elif value <= 0:
                            errors.append(f"items[{i}].quantity must be positive")
                        else:
                            sanitized_item[key] = int(value)
                    elif key == 'notes':
                        if not isinstance(value, str):
                            errors.append(f"items[{i}].notes must be a string")
                        else:
                            sanitized_item[key] = value.strip()

                if len(sanitized_item) > 1:  # More than just item_id
                    sanitized_items.append(sanitized_item)

            if sanitized_items:
                sanitized['items'] = sanitized_items

    return ModificationValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        sanitized_modifications=sanitized if sanitized else None
    )


@dataclass
class ApprovalWithModificationsResult:
    """Result of approve_with_modifications operation."""
    success: bool
    approval_id: str
    quote_id: Optional[str]
    modifications_applied: bool
    items_modified: int
    new_status: Optional[str]
    error_message: Optional[str] = None


def approve_with_modifications(
    approval_id: str,
    modifications: dict,
    comment: Optional[str] = None,
    decider_id: Optional[str] = None,
    decider_roles: Optional[List[str]] = None,
    apply_immediately: bool = True,
    send_notifications: bool = True
) -> ApprovalWithModificationsResult:
    """
    Approve a quote with modifications (v3.0 feature WF-005).

    This function allows a top_manager to approve a quote while making
    modifications to quote or item values. The modifications are stored
    in the approval record and optionally applied to the quote.

    Args:
        approval_id: ID of the approval to process
        modifications: Dict with modifications to apply
        comment: Optional approval comment
        decider_id: ID of the user making the decision
        decider_roles: Roles of the user making the decision
        apply_immediately: If True, apply modifications to quote (default: True)
        send_notifications: Whether to send notifications (default: True)

    Returns:
        ApprovalWithModificationsResult with status and details

    Example:
        result = approve_with_modifications(
            approval_id='abc-123',
            modifications={
                'margin_percent': 12,
                'payment_terms': '50% advance, 50% upon delivery',
                'items': [
                    {'item_id': 'item-uuid', 'sale_price': 1500.00}
                ]
            },
            comment='Approved with adjusted margin'
        )
    """
    from .workflow_service import (
        transition_quote_status,
        WorkflowStatus,
        get_quote_workflow_status
    )

    supabase = get_supabase()

    # Step 1: Validate modifications structure
    validation = validate_modifications(modifications)
    if not validation.is_valid:
        return ApprovalWithModificationsResult(
            success=False,
            approval_id=approval_id,
            quote_id=None,
            modifications_applied=False,
            items_modified=0,
            new_status=None,
            error_message=f"Invalid modifications: {'; '.join(validation.errors)}"
        )

    # Use sanitized modifications
    clean_modifications = validation.sanitized_modifications or {}

    # Step 2: Validate approval exists and is pending
    approval = get_approval(approval_id)

    if approval is None:
        return ApprovalWithModificationsResult(
            success=False,
            approval_id=approval_id,
            quote_id=None,
            modifications_applied=False,
            items_modified=0,
            new_status=None,
            error_message="Запрос на согласование не найден"
        )

    if approval.status != 'pending':
        return ApprovalWithModificationsResult(
            success=False,
            approval_id=approval_id,
            quote_id=approval.quote_id,
            modifications_applied=False,
            items_modified=0,
            new_status=None,
            error_message=f"Запрос уже обработан. Статус: {approval.status}"
        )

    quote_id = approval.quote_id

    # Step 3: Verify quote is in pending_approval status
    current_status = get_quote_workflow_status(quote_id)

    if current_status != WorkflowStatus.PENDING_APPROVAL:
        return ApprovalWithModificationsResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            modifications_applied=False,
            items_modified=0,
            new_status=None,
            error_message=f"КП не в статусе согласования. Текущий статус: {current_status.value if current_status else 'unknown'}"
        )

    # Step 4: Update approval with modifications and approve
    try:
        update_data = {
            'status': 'approved',
            'modifications': clean_modifications if clean_modifications else None
        }
        if comment:
            update_data['decision_comment'] = comment

        result = supabase.table('approvals').update(
            update_data
        ).eq('id', approval_id).eq('status', 'pending').execute()

        if not result.data:
            return ApprovalWithModificationsResult(
                success=False,
                approval_id=approval_id,
                quote_id=quote_id,
                modifications_applied=False,
                items_modified=0,
                new_status=None,
                error_message="Не удалось обновить запрос на согласование"
            )
    except Exception as e:
        return ApprovalWithModificationsResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            modifications_applied=False,
            items_modified=0,
            new_status=None,
            error_message=f"Database error: {str(e)}"
        )

    # Step 5: Apply modifications to quote (if requested)
    items_modified = 0
    modifications_applied = False

    if apply_immediately and clean_modifications:
        apply_result = apply_modifications_to_quote(quote_id, clean_modifications)
        modifications_applied = apply_result.success
        items_modified = apply_result.items_modified

    # Step 6: Transition quote to approved status
    actor_id = decider_id or approval.approver_id
    actor_roles = decider_roles or ['top_manager']

    transition_comment = comment or "Одобрено топ-менеджером"
    if clean_modifications:
        transition_comment += f" (с изменениями: {len(clean_modifications)} полей)"

    transition_result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.APPROVED,
        actor_id=actor_id,
        actor_roles=actor_roles,
        comment=transition_comment
    )

    if not transition_result.success:
        return ApprovalWithModificationsResult(
            success=False,
            approval_id=approval_id,
            quote_id=quote_id,
            modifications_applied=modifications_applied,
            items_modified=items_modified,
            new_status=None,
            error_message=f"Не удалось перевести КП в статус одобрено: {transition_result.error_message}"
        )

    # Step 7: Cancel other pending approvals
    try:
        supabase.table('approvals').delete().eq(
            'quote_id', quote_id
        ).eq('status', 'pending').neq('id', approval_id).execute()
    except Exception:
        pass  # Non-critical

    # Step 8: Send notifications
    if send_notifications:
        # Notification sending similar to process_approval_decision
        pass  # Notifications already handled by workflow transition

    return ApprovalWithModificationsResult(
        success=True,
        approval_id=approval_id,
        quote_id=quote_id,
        modifications_applied=modifications_applied,
        items_modified=items_modified,
        new_status='approved',
        error_message=None
    )


@dataclass
class ApplyModificationsResult:
    """Result of apply_modifications_to_quote operation."""
    success: bool
    quote_id: str
    fields_updated: List[str]
    items_modified: int
    errors: List[str]


def apply_modifications_to_quote(
    quote_id: str,
    modifications: dict
) -> ApplyModificationsResult:
    """
    Apply approved modifications to a quote.

    This function updates the quote and its items based on the
    modifications approved by the top_manager.

    Args:
        quote_id: ID of the quote to modify
        modifications: Dict with modifications from approval

    Returns:
        ApplyModificationsResult with status

    Example:
        result = apply_modifications_to_quote(
            quote_id='quote-uuid',
            modifications={
                'margin_percent': 12,
                'items': [
                    {'item_id': 'item-uuid', 'sale_price': 1500.00}
                ]
            }
        )
    """
    supabase = get_supabase()
    fields_updated = []
    items_modified = 0
    errors = []

    if not modifications:
        return ApplyModificationsResult(
            success=True,
            quote_id=quote_id,
            fields_updated=[],
            items_modified=0,
            errors=[]
        )

    # Step 1: Apply quote-level modifications
    quote_updates = {}

    # Note: The actual field mapping depends on the quotes table structure
    # These are the fields that can be modified:
    field_mapping = {
        'payment_terms': 'payment_terms',        # Direct mapping
        'delivery_terms': 'delivery_terms',      # Direct mapping
        'currency': 'currency',                  # Direct mapping
        # margin_percent typically affects calculation, handled separately
    }

    for mod_field, quote_field in field_mapping.items():
        if mod_field in modifications:
            quote_updates[quote_field] = modifications[mod_field]
            fields_updated.append(mod_field)

    # Handle margin_percent - typically stored in variables JSONB
    if 'margin_percent' in modifications:
        # We'll update the variables JSON field
        try:
            quote_result = supabase.table('quotes').select('variables').eq('id', quote_id).execute()
            if quote_result.data:
                variables = quote_result.data[0].get('variables', {}) or {}
                variables['margin_percent'] = modifications['margin_percent']
                variables['manager_modified'] = True
                quote_updates['variables'] = variables
                fields_updated.append('margin_percent')
        except Exception as e:
            errors.append(f"Failed to update margin_percent: {str(e)}")

    # Apply quote updates
    if quote_updates:
        try:
            supabase.table('quotes').update(quote_updates).eq('id', quote_id).execute()
        except Exception as e:
            errors.append(f"Failed to update quote: {str(e)}")

    # Step 2: Apply item-level modifications
    items = modifications.get('items', [])
    for item in items:
        item_id = item.get('item_id')
        if not item_id:
            continue

        item_updates = {}
        item_field_mapping = {
            'sale_price': 'sale_price',
            'purchase_price': 'purchase_price',
            'quantity': 'quantity',
        }

        for mod_field, db_field in item_field_mapping.items():
            if mod_field in item:
                item_updates[db_field] = item[mod_field]

        if item_updates:
            try:
                result = supabase.table('quote_items').update(
                    item_updates
                ).eq('id', item_id).eq('quote_id', quote_id).execute()

                if result.data:
                    items_modified += 1
            except Exception as e:
                errors.append(f"Failed to update item {item_id}: {str(e)}")

    # Add notes to quote if provided
    if 'notes' in modifications:
        try:
            # Append approval notes to quote notes
            quote_result = supabase.table('quotes').select('notes').eq('id', quote_id).execute()
            if quote_result.data:
                existing_notes = quote_result.data[0].get('notes', '') or ''
                approval_note = f"\n[Согласование] {modifications['notes']}"
                new_notes = existing_notes + approval_note
                supabase.table('quotes').update({'notes': new_notes}).eq('id', quote_id).execute()
                fields_updated.append('notes')
        except Exception:
            pass  # Non-critical

    return ApplyModificationsResult(
        success=len(errors) == 0,
        quote_id=quote_id,
        fields_updated=fields_updated,
        items_modified=items_modified,
        errors=errors
    )


def get_approval_modifications(approval_id: str) -> Optional[dict]:
    """
    Get modifications from an approval record.

    Args:
        approval_id: ID of the approval

    Returns:
        Dict with modifications or None if not found/no modifications
    """
    approval = get_approval(approval_id)
    if approval and approval.modifications:
        return approval.modifications
    return None


def get_modifications_summary(modifications: dict) -> str:
    """
    Get a human-readable summary of modifications.

    Args:
        modifications: Dict with modifications

    Returns:
        Summary string in Russian

    Example:
        >>> get_modifications_summary({'margin_percent': 12, 'items': [{'item_id': 'x', 'sale_price': 1000}]})
        "Изменено: маржа (12%), 1 позиция"
    """
    if not modifications:
        return "Без изменений"

    parts = []

    if 'margin_percent' in modifications:
        parts.append(f"маржа ({modifications['margin_percent']}%)")

    if 'payment_terms' in modifications:
        parts.append("условия оплаты")

    if 'delivery_terms' in modifications:
        parts.append("условия доставки")

    if 'currency' in modifications:
        parts.append(f"валюта ({modifications['currency']})")

    items = modifications.get('items', [])
    if items:
        item_count = len(items)
        item_word = "позиция" if item_count == 1 else "позиций" if item_count > 4 else "позиции"
        parts.append(f"{item_count} {item_word}")

    if not parts:
        if 'notes' in modifications:
            return f"Примечание: {modifications['notes'][:50]}..."
        return "Без существенных изменений"

    return f"Изменено: {', '.join(parts)}"


def get_approvals_with_modifications(
    organization_id: str,
    limit: int = 50
) -> List[dict]:
    """
    Get recent approvals that have modifications.

    Args:
        organization_id: Organization ID filter
        limit: Max results

    Returns:
        List of approvals with modification summaries
    """
    supabase = get_supabase()

    try:
        result = supabase.table('approvals').select(
            '*, quotes(id, idn, organization_id, customer_name)'
        ).not_.is_('modifications', 'null').eq(
            'status', 'approved'
        ).order('decided_at', desc=True).limit(limit).execute()

        if not result.data:
            return []

        # Filter by organization and add summary
        approvals = []
        for row in result.data:
            quote_data = row.get('quotes', {})
            if quote_data and quote_data.get('organization_id') == organization_id:
                row['modifications_summary'] = get_modifications_summary(row.get('modifications', {}))
                approvals.append(row)

        return approvals
    except Exception as e:
        print(f"Error getting approvals with modifications: {e}")
        return []
