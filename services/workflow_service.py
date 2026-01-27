"""
Workflow Service - Quote workflow status management

This module provides:
- WorkflowStatus enum with all 15 workflow statuses
- Status transition rules (who can transition from what status to what)
- Human-readable status names in Russian
- Helper functions for workflow management

Based on app_spec.xml workflow_statuses section.
"""

from enum import Enum
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass


class WorkflowStatus(str, Enum):
    """
    Quote workflow status enum.

    Values are strings matching the database workflow_status field.
    Using str Enum for easy JSON serialization and database compatibility.
    """
    # Initial/Draft
    DRAFT = "draft"

    # Evaluation stages
    PENDING_PROCUREMENT = "pending_procurement"
    PENDING_LOGISTICS = "pending_logistics"
    PENDING_CUSTOMS = "pending_customs"
    PENDING_LOGISTICS_AND_CUSTOMS = "pending_logistics_and_customs"  # Parallel logistics+customs stage

    # Sales review after evaluation
    PENDING_SALES_REVIEW = "pending_sales_review"

    # Control and approval
    PENDING_QUOTE_CONTROL = "pending_quote_control"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"

    # Client interaction
    SENT_TO_CLIENT = "sent_to_client"
    CLIENT_NEGOTIATION = "client_negotiation"

    # Specification process
    PENDING_SPEC_CONTROL = "pending_spec_control"
    PENDING_SIGNATURE = "pending_signature"

    # Final states
    DEAL = "deal"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# Human-readable status names in Russian
STATUS_NAMES: Dict[WorkflowStatus, str] = {
    WorkflowStatus.DRAFT: "Черновик",
    WorkflowStatus.PENDING_PROCUREMENT: "Ожидает оценки закупок",
    WorkflowStatus.PENDING_LOGISTICS: "Ожидает логистики",
    WorkflowStatus.PENDING_CUSTOMS: "Ожидает таможни",
    WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS: "Ожидает логистики и таможни",
    WorkflowStatus.PENDING_SALES_REVIEW: "Ожидает менеджера продаж",
    WorkflowStatus.PENDING_QUOTE_CONTROL: "Ожидает проверки КП",
    WorkflowStatus.PENDING_APPROVAL: "Ожидает согласования",
    WorkflowStatus.APPROVED: "Одобрено",
    WorkflowStatus.SENT_TO_CLIENT: "Отправлено клиенту",
    WorkflowStatus.CLIENT_NEGOTIATION: "Торги с клиентом",
    WorkflowStatus.PENDING_SPEC_CONTROL: "Ожидает проверки спецификации",
    WorkflowStatus.PENDING_SIGNATURE: "Ожидает подписания",
    WorkflowStatus.DEAL: "Сделка",
    WorkflowStatus.REJECTED: "Отклонено",
    WorkflowStatus.CANCELLED: "Отменено",
}


# Short status names for compact display
STATUS_NAMES_SHORT: Dict[WorkflowStatus, str] = {
    WorkflowStatus.DRAFT: "Черновик",
    WorkflowStatus.PENDING_PROCUREMENT: "Закупки",
    WorkflowStatus.PENDING_LOGISTICS: "Логистика",
    WorkflowStatus.PENDING_CUSTOMS: "Таможня",
    WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS: "Логистика+Таможня",
    WorkflowStatus.PENDING_SALES_REVIEW: "Продажи",
    WorkflowStatus.PENDING_QUOTE_CONTROL: "Контроль КП",
    WorkflowStatus.PENDING_APPROVAL: "Согласование",
    WorkflowStatus.APPROVED: "Одобрено",
    WorkflowStatus.SENT_TO_CLIENT: "Отправлено",
    WorkflowStatus.CLIENT_NEGOTIATION: "Торги",
    WorkflowStatus.PENDING_SPEC_CONTROL: "Спецификация",
    WorkflowStatus.PENDING_SIGNATURE: "Подписание",
    WorkflowStatus.DEAL: "Сделка",
    WorkflowStatus.REJECTED: "Отклонено",
    WorkflowStatus.CANCELLED: "Отменено",
}


# Status colors for UI badges (Tailwind CSS classes)
STATUS_COLORS: Dict[WorkflowStatus, str] = {
    WorkflowStatus.DRAFT: "bg-gray-100 text-gray-800",
    WorkflowStatus.PENDING_PROCUREMENT: "bg-yellow-100 text-yellow-800",
    WorkflowStatus.PENDING_LOGISTICS: "bg-blue-100 text-blue-800",
    WorkflowStatus.PENDING_CUSTOMS: "bg-purple-100 text-purple-800",
    WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS: "bg-teal-100 text-teal-800",  # Parallel stage
    WorkflowStatus.PENDING_SALES_REVIEW: "bg-orange-100 text-orange-800",
    WorkflowStatus.PENDING_QUOTE_CONTROL: "bg-pink-100 text-pink-800",
    WorkflowStatus.PENDING_APPROVAL: "bg-amber-100 text-amber-800",
    WorkflowStatus.APPROVED: "bg-green-100 text-green-800",
    WorkflowStatus.SENT_TO_CLIENT: "bg-cyan-100 text-cyan-800",
    WorkflowStatus.CLIENT_NEGOTIATION: "bg-teal-100 text-teal-800",
    WorkflowStatus.PENDING_SPEC_CONTROL: "bg-indigo-100 text-indigo-800",
    WorkflowStatus.PENDING_SIGNATURE: "bg-violet-100 text-violet-800",
    WorkflowStatus.DEAL: "bg-emerald-100 text-emerald-800",
    WorkflowStatus.REJECTED: "bg-red-100 text-red-800",
    WorkflowStatus.CANCELLED: "bg-stone-100 text-stone-800",
}


# Statuses that indicate "in progress" (not final, not draft)
IN_PROGRESS_STATUSES: Set[WorkflowStatus] = {
    WorkflowStatus.PENDING_PROCUREMENT,
    WorkflowStatus.PENDING_LOGISTICS,
    WorkflowStatus.PENDING_CUSTOMS,
    WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS,
    WorkflowStatus.PENDING_SALES_REVIEW,
    WorkflowStatus.PENDING_QUOTE_CONTROL,
    WorkflowStatus.PENDING_APPROVAL,
    WorkflowStatus.APPROVED,
    WorkflowStatus.SENT_TO_CLIENT,
    WorkflowStatus.CLIENT_NEGOTIATION,
    WorkflowStatus.PENDING_SPEC_CONTROL,
    WorkflowStatus.PENDING_SIGNATURE,
}


# Final statuses (workflow is complete)
FINAL_STATUSES: Set[WorkflowStatus] = {
    WorkflowStatus.DEAL,
    WorkflowStatus.REJECTED,
    WorkflowStatus.CANCELLED,
}


@dataclass
class StatusTransition:
    """
    Represents a valid status transition.

    Attributes:
        from_status: Current status
        to_status: Target status
        allowed_roles: Roles that can perform this transition
        requires_comment: Whether a comment is required
        auto_transition: Whether this happens automatically
    """
    from_status: WorkflowStatus
    to_status: WorkflowStatus
    allowed_roles: List[str]
    requires_comment: bool = False
    auto_transition: bool = False


# =============================================================================
# ALLOWED TRANSITIONS MATRIX
# =============================================================================
# This defines who can transition from what status to what status
# Format: (from_status, to_status): [allowed_roles]

ALLOWED_TRANSITIONS: List[StatusTransition] = [
    # From DRAFT
    StatusTransition(
        WorkflowStatus.DRAFT,
        WorkflowStatus.PENDING_PROCUREMENT,
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.DRAFT,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),

    # From PENDING_PROCUREMENT
    # Note: Procurement completion triggers PENDING_LOGISTICS + PENDING_CUSTOMS
    # This is handled by auto-transition when all brands are evaluated
    StatusTransition(
        WorkflowStatus.PENDING_PROCUREMENT,
        WorkflowStatus.PENDING_LOGISTICS,
        ["procurement", "admin"],
        auto_transition=True  # Triggered when all procurement is complete
    ),
    StatusTransition(
        WorkflowStatus.PENDING_PROCUREMENT,
        WorkflowStatus.PENDING_CUSTOMS,
        ["procurement", "admin"],
        auto_transition=True  # Triggered when all procurement is complete
    ),
    StatusTransition(
        WorkflowStatus.PENDING_PROCUREMENT,
        WorkflowStatus.DRAFT,  # Return to draft
        ["sales", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_PROCUREMENT,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),
    # Return to quote control after revision (Feature: multi-department return)
    StatusTransition(
        WorkflowStatus.PENDING_PROCUREMENT,
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        ["procurement", "admin"],
        requires_comment=True  # Must explain what was fixed
    ),

    # From PENDING_LOGISTICS
    StatusTransition(
        WorkflowStatus.PENDING_LOGISTICS,
        WorkflowStatus.PENDING_SALES_REVIEW,
        ["logistics", "admin"],
        auto_transition=True  # Auto when both logistics + customs are done
    ),
    StatusTransition(
        WorkflowStatus.PENDING_LOGISTICS,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),
    # Return to quote control after revision (Feature: multi-department return)
    StatusTransition(
        WorkflowStatus.PENDING_LOGISTICS,
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        ["logistics", "admin"],
        requires_comment=True  # Must explain what was fixed
    ),

    # From PENDING_CUSTOMS
    StatusTransition(
        WorkflowStatus.PENDING_CUSTOMS,
        WorkflowStatus.PENDING_SALES_REVIEW,
        ["customs", "admin"],
        auto_transition=True  # Auto when both logistics + customs are done
    ),
    StatusTransition(
        WorkflowStatus.PENDING_CUSTOMS,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),
    # Return to quote control after revision (Feature: multi-department return)
    StatusTransition(
        WorkflowStatus.PENDING_CUSTOMS,
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        ["customs", "admin"],
        requires_comment=True  # Must explain what was fixed
    ),

    # From PENDING_SALES_REVIEW
    StatusTransition(
        WorkflowStatus.PENDING_SALES_REVIEW,
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.PENDING_SALES_REVIEW,
        WorkflowStatus.DRAFT,  # Return to draft for re-evaluation
        ["sales", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_SALES_REVIEW,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),
    # Feature: Approval justification workflow - sales can submit with justification directly to pending_approval
    StatusTransition(
        WorkflowStatus.PENDING_SALES_REVIEW,
        WorkflowStatus.PENDING_APPROVAL,  # Submit with justification (when needs_justification=true)
        ["sales", "sales_manager", "admin"],
        requires_comment=True  # Justification is required
    ),

    # From PENDING_QUOTE_CONTROL (Zhanna's review)
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.PENDING_APPROVAL,  # Request top manager approval
        ["quote_controller", "admin"],
        requires_comment=True  # Reason for approval request
    ),
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.APPROVED,  # Direct approval (no top manager needed)
        ["quote_controller", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.PENDING_SALES_REVIEW,  # Return for revision to sales
        ["quote_controller", "admin"],
        requires_comment=True  # Must explain what needs to be fixed
    ),
    # Return for revision to other departments (Feature: multi-department return)
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.PENDING_PROCUREMENT,  # Return for revision to procurement
        ["quote_controller", "admin"],
        requires_comment=True  # Must explain what needs to be fixed
    ),
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.PENDING_LOGISTICS,  # Return for revision to logistics
        ["quote_controller", "admin"],
        requires_comment=True  # Must explain what needs to be fixed
    ),
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.PENDING_CUSTOMS,  # Return for revision to customs
        ["quote_controller", "admin"],
        requires_comment=True  # Must explain what needs to be fixed
    ),
    StatusTransition(
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.CANCELLED,
        ["quote_controller", "admin"],
        requires_comment=True
    ),

    # From PENDING_APPROVAL (Top manager approval via Telegram)
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.APPROVED,
        ["top_manager", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.REJECTED,
        ["top_manager", "admin"],
        requires_comment=True  # Must explain rejection
    ),
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.PENDING_QUOTE_CONTROL,  # Return for revision
        ["top_manager", "admin"],
        requires_comment=True
    ),
    # Feature: Multi-department return from top_manager (same as quote_controller)
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.PENDING_SALES_REVIEW,  # Return for revision to sales
        ["top_manager", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.PENDING_PROCUREMENT,  # Return for revision to procurement
        ["top_manager", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.PENDING_LOGISTICS,  # Return for revision to logistics
        ["top_manager", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.PENDING_CUSTOMS,  # Return for revision to customs
        ["top_manager", "admin"],
        requires_comment=True
    ),

    # From APPROVED
    StatusTransition(
        WorkflowStatus.APPROVED,
        WorkflowStatus.SENT_TO_CLIENT,
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.APPROVED,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),

    # From SENT_TO_CLIENT
    StatusTransition(
        WorkflowStatus.SENT_TO_CLIENT,
        WorkflowStatus.CLIENT_NEGOTIATION,
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.SENT_TO_CLIENT,
        WorkflowStatus.PENDING_SPEC_CONTROL,  # Client accepted immediately
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.SENT_TO_CLIENT,
        WorkflowStatus.REJECTED,  # Client rejected
        ["sales", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.SENT_TO_CLIENT,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),

    # From CLIENT_NEGOTIATION
    StatusTransition(
        WorkflowStatus.CLIENT_NEGOTIATION,
        WorkflowStatus.PENDING_SPEC_CONTROL,  # Client accepted version
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.CLIENT_NEGOTIATION,
        WorkflowStatus.PENDING_QUOTE_CONTROL,  # New version needs re-review
        ["sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.CLIENT_NEGOTIATION,
        WorkflowStatus.REJECTED,  # Client rejected
        ["sales", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.CLIENT_NEGOTIATION,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),

    # From PENDING_SPEC_CONTROL
    StatusTransition(
        WorkflowStatus.PENDING_SPEC_CONTROL,
        WorkflowStatus.PENDING_SIGNATURE,
        ["spec_controller", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.PENDING_SPEC_CONTROL,
        WorkflowStatus.CLIENT_NEGOTIATION,  # Return for changes
        ["spec_controller", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_SPEC_CONTROL,
        WorkflowStatus.CANCELLED,
        ["spec_controller", "admin"],
        requires_comment=True
    ),

    # From PENDING_SIGNATURE
    StatusTransition(
        WorkflowStatus.PENDING_SIGNATURE,
        WorkflowStatus.DEAL,  # Signature confirmed
        ["spec_controller", "sales", "admin"],
        requires_comment=False
    ),
    StatusTransition(
        WorkflowStatus.PENDING_SIGNATURE,
        WorkflowStatus.PENDING_SPEC_CONTROL,  # Changes needed
        ["spec_controller", "sales", "admin"],
        requires_comment=True
    ),
    StatusTransition(
        WorkflowStatus.PENDING_SIGNATURE,
        WorkflowStatus.CANCELLED,
        ["sales", "admin"],
        requires_comment=True
    ),
]


# Build transition lookup dictionary for O(1) access
_TRANSITIONS_BY_STATUS: Dict[WorkflowStatus, List[StatusTransition]] = {}
for t in ALLOWED_TRANSITIONS:
    if t.from_status not in _TRANSITIONS_BY_STATUS:
        _TRANSITIONS_BY_STATUS[t.from_status] = []
    _TRANSITIONS_BY_STATUS[t.from_status].append(t)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_status_name(status: WorkflowStatus | str) -> str:
    """
    Get human-readable status name in Russian.

    Args:
        status: WorkflowStatus enum value or string status code

    Returns:
        Human-readable status name
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return status  # Return as-is if not valid enum
    return STATUS_NAMES.get(status, str(status))


def get_status_name_short(status: WorkflowStatus | str) -> str:
    """
    Get short status name for compact display.

    Args:
        status: WorkflowStatus enum value or string status code

    Returns:
        Short status name
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return status
    return STATUS_NAMES_SHORT.get(status, str(status))


def get_status_color(status: WorkflowStatus | str) -> str:
    """
    Get Tailwind CSS color classes for status badge.

    Args:
        status: WorkflowStatus enum value or string status code

    Returns:
        Tailwind CSS classes for background and text color
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return "bg-gray-100 text-gray-800"
    return STATUS_COLORS.get(status, "bg-gray-100 text-gray-800")


def get_allowed_transitions(
    current_status: WorkflowStatus | str,
    user_roles: List[str]
) -> List[StatusTransition]:
    """
    Get list of allowed transitions from current status for given user roles.

    This is the main function for determining what actions a user can take.

    Args:
        current_status: Current workflow status
        user_roles: List of role codes the user has

    Returns:
        List of StatusTransition objects the user can perform

    Example:
        >>> transitions = get_allowed_transitions('draft', ['sales'])
        >>> for t in transitions:
        ...     print(f"Can move to: {t.to_status.value}")
    """
    if isinstance(current_status, str):
        try:
            current_status = WorkflowStatus(current_status)
        except ValueError:
            return []

    available = _TRANSITIONS_BY_STATUS.get(current_status, [])

    # Filter by user roles (don't include auto-transitions in user-available list)
    result = []
    for transition in available:
        if transition.auto_transition:
            continue  # Auto-transitions are handled by system, not user
        if any(role in transition.allowed_roles for role in user_roles):
            result.append(transition)

    return result


def get_allowed_target_statuses(
    current_status: WorkflowStatus | str,
    user_roles: List[str]
) -> List[WorkflowStatus]:
    """
    Get list of target statuses user can transition to.

    Convenience function that returns just the target statuses.

    Args:
        current_status: Current workflow status
        user_roles: List of role codes the user has

    Returns:
        List of WorkflowStatus values user can transition to
    """
    transitions = get_allowed_transitions(current_status, user_roles)
    return [t.to_status for t in transitions]


def can_transition(
    current_status: WorkflowStatus | str,
    target_status: WorkflowStatus | str,
    user_roles: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Check if a transition is allowed for given user roles.

    Args:
        current_status: Current workflow status
        target_status: Target workflow status
        user_roles: List of role codes the user has

    Returns:
        Tuple of (allowed: bool, error_message: Optional[str])
        If allowed, error_message is None
        If not allowed, error_message explains why

    Example:
        >>> allowed, error = can_transition('draft', 'pending_procurement', ['sales'])
        >>> if allowed:
        ...     # Perform transition
        ... else:
        ...     print(f"Cannot transition: {error}")
    """
    # Convert strings to enums
    if isinstance(current_status, str):
        try:
            current_status = WorkflowStatus(current_status)
        except ValueError:
            return False, f"Invalid current status: {current_status}"

    if isinstance(target_status, str):
        try:
            target_status = WorkflowStatus(target_status)
        except ValueError:
            return False, f"Invalid target status: {target_status}"

    # Check if current status is final
    if current_status in FINAL_STATUSES:
        return False, f"Cannot transition from final status: {get_status_name(current_status)}"

    # Find matching transition
    available = _TRANSITIONS_BY_STATUS.get(current_status, [])
    matching = None
    for t in available:
        if t.to_status == target_status:
            matching = t
            break

    if not matching:
        return False, f"Transition from {get_status_name(current_status)} to {get_status_name(target_status)} is not allowed"

    # Check if user has required role
    if not any(role in matching.allowed_roles for role in user_roles):
        return False, f"You don't have permission to perform this transition. Required roles: {', '.join(matching.allowed_roles)}"

    return True, None


def is_final_status(status: WorkflowStatus | str) -> bool:
    """
    Check if status is a final status (workflow complete).

    Args:
        status: Status to check

    Returns:
        True if status is final (deal, rejected, cancelled)
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return False
    return status in FINAL_STATUSES


def is_in_progress(status: WorkflowStatus | str) -> bool:
    """
    Check if status indicates work in progress.

    Args:
        status: Status to check

    Returns:
        True if status is in progress (not draft, not final)
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return False
    return status in IN_PROGRESS_STATUSES


def get_workflow_order() -> List[WorkflowStatus]:
    """
    Get the typical workflow order for display purposes.

    Returns:
        List of statuses in typical workflow progression order
    """
    return [
        WorkflowStatus.DRAFT,
        WorkflowStatus.PENDING_PROCUREMENT,
        WorkflowStatus.PENDING_LOGISTICS,
        WorkflowStatus.PENDING_CUSTOMS,
        WorkflowStatus.PENDING_SALES_REVIEW,
        WorkflowStatus.PENDING_QUOTE_CONTROL,
        WorkflowStatus.PENDING_APPROVAL,
        WorkflowStatus.APPROVED,
        WorkflowStatus.SENT_TO_CLIENT,
        WorkflowStatus.CLIENT_NEGOTIATION,
        WorkflowStatus.PENDING_SPEC_CONTROL,
        WorkflowStatus.PENDING_SIGNATURE,
        WorkflowStatus.DEAL,
    ]


def get_workflow_stage(status: WorkflowStatus | str) -> int:
    """
    Get numeric stage for progress bar calculation.

    Args:
        status: Current status

    Returns:
        Stage number (0-12) for progress visualization
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return 0

    # Special cases for final statuses
    if status == WorkflowStatus.DEAL:
        return 12  # Final stage
    if status in (WorkflowStatus.REJECTED, WorkflowStatus.CANCELLED):
        return -1  # Workflow ended early

    # Map status to stage number
    order = get_workflow_order()
    try:
        return order.index(status)
    except ValueError:
        return 0


def get_all_statuses() -> List[Dict[str, str]]:
    """
    Get all statuses with their names for UI dropdowns.

    Returns:
        List of dicts with 'code' and 'name' keys
    """
    return [
        {"code": status.value, "name": STATUS_NAMES[status]}
        for status in WorkflowStatus
    ]


# =============================================================================
# PERMISSION MATRIX FUNCTIONS (Feature #24)
# =============================================================================

def get_transition_requirements(
    from_status: WorkflowStatus | str,
    to_status: WorkflowStatus | str
) -> Optional[StatusTransition]:
    """
    Get the transition requirements for a specific status change.

    Args:
        from_status: Source workflow status
        to_status: Target workflow status

    Returns:
        StatusTransition with requirements, or None if transition not allowed

    Example:
        >>> req = get_transition_requirements('draft', 'pending_procurement')
        >>> if req:
        ...     print(f"Allowed roles: {req.allowed_roles}")
        ...     print(f"Comment required: {req.requires_comment}")
    """
    # Convert strings to enums
    if isinstance(from_status, str):
        try:
            from_status = WorkflowStatus(from_status)
        except ValueError:
            return None

    if isinstance(to_status, str):
        try:
            to_status = WorkflowStatus(to_status)
        except ValueError:
            return None

    # Find matching transition
    available = _TRANSITIONS_BY_STATUS.get(from_status, [])
    for transition in available:
        if transition.to_status == to_status:
            return transition

    return None


def get_roles_for_transition(
    from_status: WorkflowStatus | str,
    to_status: WorkflowStatus | str
) -> List[str]:
    """
    Get list of roles that can perform a specific transition.

    Args:
        from_status: Source workflow status
        to_status: Target workflow status

    Returns:
        List of role codes, or empty list if transition not allowed

    Example:
        >>> roles = get_roles_for_transition('draft', 'pending_procurement')
        >>> print(roles)  # ['sales', 'admin']
    """
    transition = get_transition_requirements(from_status, to_status)
    if transition:
        return transition.allowed_roles
    return []


def get_transitions_by_role(role_code: str) -> List[Dict]:
    """
    Get all transitions that a specific role can perform.

    Args:
        role_code: Role code (e.g., 'sales', 'procurement', 'admin')

    Returns:
        List of dicts with transition details:
        - from_status: Source status code
        - from_status_name: Source status name
        - to_status: Target status code
        - to_status_name: Target status name
        - requires_comment: Whether comment is required
        - auto_transition: Whether this is automatic

    Example:
        >>> sales_transitions = get_transitions_by_role('sales')
        >>> for t in sales_transitions:
        ...     print(f"{t['from_status_name']} → {t['to_status_name']}")
    """
    result = []
    for transition in ALLOWED_TRANSITIONS:
        if role_code in transition.allowed_roles:
            result.append({
                "from_status": transition.from_status.value,
                "from_status_name": STATUS_NAMES[transition.from_status],
                "to_status": transition.to_status.value,
                "to_status_name": STATUS_NAMES[transition.to_status],
                "requires_comment": transition.requires_comment,
                "auto_transition": transition.auto_transition
            })
    return result


def get_permission_matrix() -> Dict[str, Dict[str, List[str]]]:
    """
    Get the complete permission matrix for UI display.

    Returns:
        Nested dict: {from_status: {to_status: [allowed_roles]}}

    Example:
        >>> matrix = get_permission_matrix()
        >>> print(matrix['draft']['pending_procurement'])  # ['sales', 'admin']
    """
    matrix: Dict[str, Dict[str, List[str]]] = {}

    for transition in ALLOWED_TRANSITIONS:
        from_key = transition.from_status.value
        to_key = transition.to_status.value

        if from_key not in matrix:
            matrix[from_key] = {}

        matrix[from_key][to_key] = transition.allowed_roles

    return matrix


def get_permission_matrix_detailed() -> List[Dict]:
    """
    Get detailed permission matrix as a list for table display.

    Returns:
        List of dicts with full transition details:
        - from_status, from_status_name
        - to_status, to_status_name
        - allowed_roles: list of role codes
        - allowed_roles_names: list of role names
        - requires_comment: bool
        - auto_transition: bool

    Example:
        >>> for row in get_permission_matrix_detailed():
        ...     print(f"{row['from_status_name']} → {row['to_status_name']}: {row['allowed_roles']}")
    """
    # Role names for display
    ROLE_NAMES = {
        "sales": "Менеджер по продажам",
        "procurement": "Менеджер по закупкам",
        "logistics": "Логист",
        "customs": "Менеджер ТО",
        "quote_controller": "Контроллер КП",
        "spec_controller": "Контроллер спецификаций",
        "finance": "Финансовый менеджер",
        "top_manager": "Топ-менеджер",
        "admin": "Администратор"
    }

    result = []
    for transition in ALLOWED_TRANSITIONS:
        result.append({
            "from_status": transition.from_status.value,
            "from_status_name": STATUS_NAMES[transition.from_status],
            "to_status": transition.to_status.value,
            "to_status_name": STATUS_NAMES[transition.to_status],
            "allowed_roles": transition.allowed_roles,
            "allowed_roles_names": [ROLE_NAMES.get(r, r) for r in transition.allowed_roles],
            "requires_comment": transition.requires_comment,
            "auto_transition": transition.auto_transition
        })
    return result


def get_outgoing_transitions(status: WorkflowStatus | str) -> List[Dict]:
    """
    Get all possible outgoing transitions from a status (regardless of role).

    Args:
        status: Source workflow status

    Returns:
        List of dicts with transition details

    Example:
        >>> transitions = get_outgoing_transitions('draft')
        >>> for t in transitions:
        ...     print(f"Can go to: {t['to_status_name']}")
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return []

    available = _TRANSITIONS_BY_STATUS.get(status, [])
    result = []
    for transition in available:
        result.append({
            "to_status": transition.to_status.value,
            "to_status_name": STATUS_NAMES[transition.to_status],
            "allowed_roles": transition.allowed_roles,
            "requires_comment": transition.requires_comment,
            "auto_transition": transition.auto_transition
        })
    return result


def get_incoming_transitions(status: WorkflowStatus | str) -> List[Dict]:
    """
    Get all possible incoming transitions to a status (regardless of role).

    Args:
        status: Target workflow status

    Returns:
        List of dicts with transition details

    Example:
        >>> transitions = get_incoming_transitions('approved')
        >>> for t in transitions:
        ...     print(f"Can come from: {t['from_status_name']}")
    """
    if isinstance(status, str):
        try:
            status = WorkflowStatus(status)
        except ValueError:
            return []

    result = []
    for transition in ALLOWED_TRANSITIONS:
        if transition.to_status == status:
            result.append({
                "from_status": transition.from_status.value,
                "from_status_name": STATUS_NAMES[transition.from_status],
                "allowed_roles": transition.allowed_roles,
                "requires_comment": transition.requires_comment,
                "auto_transition": transition.auto_transition
            })
    return result


def is_comment_required(
    from_status: WorkflowStatus | str,
    to_status: WorkflowStatus | str
) -> bool:
    """
    Check if a comment is required for this transition.

    Args:
        from_status: Source workflow status
        to_status: Target workflow status

    Returns:
        True if comment is required, False otherwise

    Example:
        >>> if is_comment_required('pending_quote_control', 'pending_sales_review'):
        ...     # Return to revision requires comment
        ...     comment = input("Please explain: ")
    """
    transition = get_transition_requirements(from_status, to_status)
    if transition:
        return transition.requires_comment
    return False


def is_auto_transition(
    from_status: WorkflowStatus | str,
    to_status: WorkflowStatus | str
) -> bool:
    """
    Check if this transition is automatic (triggered by system, not user).

    Args:
        from_status: Source workflow status
        to_status: Target workflow status

    Returns:
        True if automatic, False otherwise

    Example:
        >>> if is_auto_transition('pending_procurement', 'pending_logistics'):
        ...     # This happens automatically when procurement completes
        ...     pass
    """
    transition = get_transition_requirements(from_status, to_status)
    if transition:
        return transition.auto_transition
    return False


# =============================================================================
# TRANSITION EXECUTION FUNCTIONS (Feature #25)
# =============================================================================

from .database import get_supabase
from datetime import datetime, timezone


@dataclass
class TransitionResult:
    """
    Result of a status transition attempt.

    Attributes:
        success: Whether the transition was successful
        error_message: Error message if failed, None if success
        quote_id: The quote ID that was transitioned
        from_status: Previous status
        to_status: New status
        transition_id: UUID of the workflow_transitions record created
    """
    success: bool
    error_message: Optional[str] = None
    quote_id: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    transition_id: Optional[str] = None


def transition_quote_status(
    quote_id: str,
    to_status: WorkflowStatus | str,
    actor_id: str,
    actor_roles: List[str],
    comment: Optional[str] = None,
    skip_validation: bool = False
) -> TransitionResult:
    """
    Transition a quote to a new workflow status.

    This is the main function for executing workflow transitions.
    It performs the following steps:
    1. Fetches the quote's current status
    2. Validates the transition is allowed for the actor's roles
    3. Checks if comment is required and provided
    4. Updates the quote's workflow_status
    5. Creates a record in workflow_transitions for audit
    6. Returns success or error

    Args:
        quote_id: UUID of the quote to transition
        to_status: Target workflow status (enum or string)
        actor_id: UUID of the user performing the transition
        actor_roles: List of role codes the actor has (e.g., ['sales', 'admin'])
        comment: Optional comment explaining the transition (required for some transitions)
        skip_validation: If True, skip role/transition validation (for auto-transitions)

    Returns:
        TransitionResult with success status and details

    Example:
        >>> result = transition_quote_status(
        ...     quote_id="quote-uuid",
        ...     to_status="pending_procurement",
        ...     actor_id="user-uuid",
        ...     actor_roles=["sales"],
        ...     comment=None
        ... )
        >>> if result.success:
        ...     print(f"Transitioned to {result.to_status}")
        ... else:
        ...     print(f"Failed: {result.error_message}")
    """
    supabase = get_supabase()

    # Convert string to enum if needed
    if isinstance(to_status, str):
        try:
            to_status_enum = WorkflowStatus(to_status)
        except ValueError:
            return TransitionResult(
                success=False,
                error_message=f"Invalid target status: {to_status}",
                quote_id=quote_id
            )
    else:
        to_status_enum = to_status

    # Step 1: Fetch current quote status
    try:
        quote_response = supabase.table("quotes") \
            .select("id, workflow_status, organization_id") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    quote = quote_response.data
    if not quote:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    current_status = quote.get("workflow_status", "draft")
    organization_id = quote.get("organization_id")

    # Convert current status to enum
    try:
        current_status_enum = WorkflowStatus(current_status)
    except ValueError:
        # If current status is invalid, treat as draft
        current_status_enum = WorkflowStatus.DRAFT

    # Step 2: Validate transition (unless skipped for auto-transitions)
    if not skip_validation:
        allowed, error = can_transition(current_status_enum, to_status_enum, actor_roles)
        if not allowed:
            return TransitionResult(
                success=False,
                error_message=error,
                quote_id=quote_id,
                from_status=current_status
            )

    # Step 3: Check if comment is required
    if is_comment_required(current_status_enum, to_status_enum):
        if not comment or not comment.strip():
            return TransitionResult(
                success=False,
                error_message=f"Comment is required for transition from {get_status_name(current_status_enum)} to {get_status_name(to_status_enum)}",
                quote_id=quote_id,
                from_status=current_status
            )

    # Step 4: Update the quote's workflow_status
    try:
        update_response = supabase.table("quotes") \
            .update({"workflow_status": to_status_enum.value}) \
            .eq("id", quote_id) \
            .execute()

        if not update_response.data:
            return TransitionResult(
                success=False,
                error_message="Failed to update quote status",
                quote_id=quote_id,
                from_status=current_status
            )
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Database error updating quote: {str(e)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Step 5: Log the transition in workflow_transitions
    # Determine actor's primary role for this transition
    transition_req = get_transition_requirements(current_status_enum, to_status_enum)
    actor_role_for_log = None
    if transition_req and actor_roles:
        # Find the role that authorized this transition
        for role in actor_roles:
            if role in transition_req.allowed_roles:
                actor_role_for_log = role
                break
    if not actor_role_for_log and actor_roles:
        actor_role_for_log = actor_roles[0]  # Fallback to first role

    try:
        transition_data = {
            "quote_id": quote_id,
            "from_status": current_status,
            "to_status": to_status_enum.value,
            "actor_id": actor_id,
            "actor_role": actor_role_for_log,
            "comment": comment.strip() if comment else None
        }

        log_response = supabase.table("workflow_transitions") \
            .insert(transition_data) \
            .execute()

        transition_id = None
        if log_response.data and len(log_response.data) > 0:
            transition_id = log_response.data[0].get("id")

    except Exception as e:
        # Transition succeeded but logging failed - still return success
        # but note the logging failure (in production, you'd want to handle this better)
        return TransitionResult(
            success=True,
            error_message=f"Warning: Transition succeeded but audit log failed: {str(e)}",
            quote_id=quote_id,
            from_status=current_status,
            to_status=to_status_enum.value,
            transition_id=None
        )

    return TransitionResult(
        success=True,
        error_message=None,
        quote_id=quote_id,
        from_status=current_status,
        to_status=to_status_enum.value,
        transition_id=transition_id
    )


def get_quote_workflow_status(quote_id: str) -> Optional[WorkflowStatus]:
    """
    Get the current workflow status of a quote.

    Args:
        quote_id: UUID of the quote

    Returns:
        WorkflowStatus enum value, or None if quote not found

    Example:
        >>> status = get_quote_workflow_status("quote-uuid")
        >>> if status == WorkflowStatus.DRAFT:
        ...     print("Quote is still in draft")
    """
    supabase = get_supabase()

    try:
        response = supabase.table("quotes") \
            .select("workflow_status") \
            .eq("id", quote_id) \
            .single() \
            .execute()

        if response.data:
            status_str = response.data.get("workflow_status", "draft")
            try:
                return WorkflowStatus(status_str)
            except ValueError:
                return WorkflowStatus.DRAFT
    except Exception:
        return None

    return None


def get_quote_transition_history(quote_id: str, limit: int = 50) -> List[Dict]:
    """
    Get the workflow transition history for a quote.

    Args:
        quote_id: UUID of the quote
        limit: Maximum number of records to return (default 50)

    Returns:
        List of transition records, ordered by created_at DESC (most recent first)
        Each record contains:
        - id: Transition record UUID
        - from_status: Previous status code
        - from_status_name: Previous status name
        - to_status: New status code
        - to_status_name: New status name
        - actor_id: User who made the transition
        - actor_role: Role used for the transition
        - comment: Comment/reason for transition
        - created_at: When the transition occurred

    Example:
        >>> history = get_quote_transition_history("quote-uuid")
        >>> for record in history:
        ...     print(f"{record['from_status_name']} → {record['to_status_name']}")
    """
    supabase = get_supabase()

    try:
        response = supabase.table("workflow_transitions") \
            .select("*") \
            .eq("quote_id", quote_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        result = []
        for record in response.data:
            result.append({
                "id": record.get("id"),
                "from_status": record.get("from_status"),
                "from_status_name": get_status_name(record.get("from_status", "")),
                "to_status": record.get("to_status"),
                "to_status_name": get_status_name(record.get("to_status", "")),
                "actor_id": record.get("actor_id"),
                "actor_role": record.get("actor_role"),
                "comment": record.get("comment"),
                "created_at": record.get("created_at")
            })

        return result
    except Exception:
        return []


def get_available_transitions_for_quote(
    quote_id: str,
    user_roles: List[str]
) -> List[Dict]:
    """
    Get available status transitions for a specific quote and user.

    Combines get_quote_workflow_status and get_allowed_transitions
    for convenience.

    Args:
        quote_id: UUID of the quote
        user_roles: List of role codes the user has

    Returns:
        List of available transitions, each containing:
        - to_status: Target status code
        - to_status_name: Target status name
        - requires_comment: Whether comment is required
        - allowed_roles: Roles that can perform this transition

    Example:
        >>> transitions = get_available_transitions_for_quote("quote-uuid", ["sales"])
        >>> for t in transitions:
        ...     print(f"Can move to: {t['to_status_name']}")
    """
    current_status = get_quote_workflow_status(quote_id)
    if current_status is None:
        return []

    allowed = get_allowed_transitions(current_status, user_roles)
    result = []
    for transition in allowed:
        result.append({
            "to_status": transition.to_status.value,
            "to_status_name": STATUS_NAMES[transition.to_status],
            "requires_comment": transition.requires_comment,
            "allowed_roles": transition.allowed_roles
        })

    return result


# =============================================================================
# AUTO-TRANSITION FUNCTIONS (Feature #28)
# =============================================================================
# Handles automatic status transitions when certain conditions are met
# Specifically: logistics + customs → sales_review


def check_and_auto_transition_to_sales_review(
    quote_id: str,
    actor_id: str
) -> Optional[TransitionResult]:
    """
    Check if both logistics and customs are complete, and auto-transition to sales_review.

    This function should be called after logistics or customs marks their work complete.
    It checks if both `logistics_completed_at` and `customs_completed_at` are set,
    and if so, automatically transitions the quote to `pending_sales_review`.

    Args:
        quote_id: UUID of the quote to check
        actor_id: UUID of the user who triggered this check (for audit log)

    Returns:
        TransitionResult if auto-transition was performed, None if conditions not met

    Example:
        >>> # Called after logistics completes
        >>> result = check_and_auto_transition_to_sales_review(quote_id, user_id)
        >>> if result and result.success:
        ...     print("Auto-transitioned to sales review!")
    """
    supabase = get_supabase()

    # Fetch quote with completion timestamps
    try:
        response = supabase.table("quotes") \
            .select("id, workflow_status, logistics_completed_at, customs_completed_at") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception as e:
        return None

    if not response.data:
        return None

    quote = response.data
    current_status = quote.get("workflow_status")
    logistics_completed = quote.get("logistics_completed_at")
    customs_completed = quote.get("customs_completed_at")

    # Check if current status allows auto-transition
    # Auto-transition should only happen from pending_logistics or pending_customs
    allowed_statuses = [
        WorkflowStatus.PENDING_LOGISTICS.value,
        WorkflowStatus.PENDING_CUSTOMS.value,
        "pending_logistics_and_customs"  # Parallel logistics+customs stage
    ]

    if current_status not in allowed_statuses:
        return None

    # Check if both stages are complete
    if not logistics_completed or not customs_completed:
        return None

    # Both complete! Perform auto-transition to sales_review
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_SALES_REVIEW,
        actor_id=actor_id,
        actor_roles=["system"],  # System-initiated transition
        comment="Автоматический переход: логистика и таможня завершены",
        skip_validation=True  # Skip role validation for auto-transitions
    )

    return result


def complete_logistics(
    quote_id: str,
    actor_id: str,
    actor_roles: List[str]
) -> TransitionResult:
    """
    Mark logistics work as complete and check for auto-transition.

    This function:
    1. Validates the user has logistics or admin role
    2. Sets logistics_completed_at timestamp
    3. Checks if customs is also complete
    4. If both complete, auto-transitions to pending_sales_review

    Args:
        quote_id: UUID of the quote
        actor_id: UUID of the user completing logistics
        actor_roles: List of role codes the user has

    Returns:
        TransitionResult indicating success or failure

    Example:
        >>> result = complete_logistics(quote_id, user_id, ["logistics"])
        >>> if result.success:
        ...     print(f"Logistics complete! New status: {result.to_status}")
    """
    supabase = get_supabase()

    # Validate role
    if not any(role in ["logistics", "admin"] for role in actor_roles):
        return TransitionResult(
            success=False,
            error_message="Only logistics or admin can complete logistics",
            quote_id=quote_id
        )

    # Get current quote status
    try:
        response = supabase.table("quotes") \
            .select("id, workflow_status, logistics_completed_at") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    if not response.data:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    quote = response.data
    current_status = quote.get("workflow_status")

    # Validate current status - must be pending_logistics or pending_customs or parallel stage
    # (logistics can be completed in parallel with customs)
    if current_status not in [
        WorkflowStatus.PENDING_LOGISTICS.value,
        WorkflowStatus.PENDING_CUSTOMS.value,
        WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value
    ]:
        return TransitionResult(
            success=False,
            error_message=f"Cannot complete logistics from status: {get_status_name(current_status)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Check if already completed
    if quote.get("logistics_completed_at"):
        return TransitionResult(
            success=False,
            error_message="Logistics already completed",
            quote_id=quote_id,
            from_status=current_status
        )

    # Set logistics_completed_at
    try:
        update_response = supabase.table("quotes") \
            .update({"logistics_completed_at": datetime.now(timezone.utc).isoformat()}) \
            .eq("id", quote_id) \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Failed to update logistics completion: {str(e)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Log the completion in workflow_transitions
    try:
        actor_role = "logistics" if "logistics" in actor_roles else "admin"
        transition_data = {
            "quote_id": quote_id,
            "from_status": current_status,
            "to_status": current_status,  # Status might not change yet
            "actor_id": actor_id,
            "actor_role": actor_role,
            "comment": "Логистика завершена"
        }
        supabase.table("workflow_transitions").insert(transition_data).execute()
    except Exception:
        pass  # Non-critical, continue

    # Check for auto-transition
    auto_result = check_and_auto_transition_to_sales_review(quote_id, actor_id)

    if auto_result and auto_result.success:
        # Auto-transition happened
        return TransitionResult(
            success=True,
            error_message=None,
            quote_id=quote_id,
            from_status=current_status,
            to_status=WorkflowStatus.PENDING_SALES_REVIEW.value,
            transition_id=auto_result.transition_id
        )
    else:
        # Logistics complete, but waiting for customs
        return TransitionResult(
            success=True,
            error_message=None,
            quote_id=quote_id,
            from_status=current_status,
            to_status=current_status  # Status unchanged, waiting for customs
        )


def complete_customs(
    quote_id: str,
    actor_id: str,
    actor_roles: List[str]
) -> TransitionResult:
    """
    Mark customs work as complete and check for auto-transition.

    This function:
    1. Validates the user has customs or admin role
    2. Sets customs_completed_at timestamp
    3. Checks if logistics is also complete
    4. If both complete, auto-transitions to pending_sales_review

    Args:
        quote_id: UUID of the quote
        actor_id: UUID of the user completing customs
        actor_roles: List of role codes the user has

    Returns:
        TransitionResult indicating success or failure

    Example:
        >>> result = complete_customs(quote_id, user_id, ["customs"])
        >>> if result.success:
        ...     print(f"Customs complete! New status: {result.to_status}")
    """
    supabase = get_supabase()

    # Validate role
    if not any(role in ["customs", "admin"] for role in actor_roles):
        return TransitionResult(
            success=False,
            error_message="Only customs or admin can complete customs",
            quote_id=quote_id
        )

    # Get current quote status
    try:
        response = supabase.table("quotes") \
            .select("id, workflow_status, customs_completed_at") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    if not response.data:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    quote = response.data
    current_status = quote.get("workflow_status")

    # Validate current status - must be pending_logistics or pending_customs or parallel stage
    if current_status not in [
        WorkflowStatus.PENDING_LOGISTICS.value,
        WorkflowStatus.PENDING_CUSTOMS.value,
        WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value
    ]:
        return TransitionResult(
            success=False,
            error_message=f"Cannot complete customs from status: {get_status_name(current_status)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Check if already completed
    if quote.get("customs_completed_at"):
        return TransitionResult(
            success=False,
            error_message="Customs already completed",
            quote_id=quote_id,
            from_status=current_status
        )

    # Set customs_completed_at
    try:
        update_response = supabase.table("quotes") \
            .update({"customs_completed_at": datetime.now(timezone.utc).isoformat()}) \
            .eq("id", quote_id) \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Failed to update customs completion: {str(e)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Log the completion in workflow_transitions
    try:
        actor_role = "customs" if "customs" in actor_roles else "admin"
        transition_data = {
            "quote_id": quote_id,
            "from_status": current_status,
            "to_status": current_status,  # Status might not change yet
            "actor_id": actor_id,
            "actor_role": actor_role,
            "comment": "Таможня завершена"
        }
        supabase.table("workflow_transitions").insert(transition_data).execute()
    except Exception:
        pass  # Non-critical, continue

    # Check for auto-transition
    auto_result = check_and_auto_transition_to_sales_review(quote_id, actor_id)

    if auto_result and auto_result.success:
        # Auto-transition happened
        return TransitionResult(
            success=True,
            error_message=None,
            quote_id=quote_id,
            from_status=current_status,
            to_status=WorkflowStatus.PENDING_SALES_REVIEW.value,
            transition_id=auto_result.transition_id
        )
    else:
        # Customs complete, but waiting for logistics
        return TransitionResult(
            success=True,
            error_message=None,
            quote_id=quote_id,
            from_status=current_status,
            to_status=current_status  # Status unchanged, waiting for logistics
        )


def get_parallel_stages_status(quote_id: str) -> Dict:
    """
    Get the completion status of parallel stages (logistics and customs).

    Useful for UI to show progress during parallel evaluation.

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict with:
        - logistics_completed: bool
        - logistics_completed_at: datetime or None
        - customs_completed: bool
        - customs_completed_at: datetime or None
        - both_completed: bool
        - current_status: str

    Example:
        >>> status = get_parallel_stages_status(quote_id)
        >>> if status["both_completed"]:
        ...     print("Both stages done!")
        >>> else:
        ...     if not status["logistics_completed"]:
        ...         print("Waiting for logistics")
        ...     if not status["customs_completed"]:
        ...         print("Waiting for customs")
    """
    supabase = get_supabase()

    try:
        response = supabase.table("quotes") \
            .select("workflow_status, logistics_completed_at, customs_completed_at") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception:
        return {
            "logistics_completed": False,
            "logistics_completed_at": None,
            "customs_completed": False,
            "customs_completed_at": None,
            "both_completed": False,
            "current_status": None
        }

    if not response.data:
        return {
            "logistics_completed": False,
            "logistics_completed_at": None,
            "customs_completed": False,
            "customs_completed_at": None,
            "both_completed": False,
            "current_status": None
        }

    quote = response.data
    logistics_completed_at = quote.get("logistics_completed_at")
    customs_completed_at = quote.get("customs_completed_at")

    return {
        "logistics_completed": logistics_completed_at is not None,
        "logistics_completed_at": logistics_completed_at,
        "customs_completed": customs_completed_at is not None,
        "customs_completed_at": customs_completed_at,
        "both_completed": logistics_completed_at is not None and customs_completed_at is not None,
        "current_status": quote.get("workflow_status")
    }


# =============================================================================
# PROCUREMENT ASSIGNMENT FUNCTIONS (Feature #29)
# =============================================================================
# Auto-assign procurement users when transitioning to pending_procurement
# Based on brand assignments in the brand_assignments table


def get_procurement_users_for_quote(quote_id: str) -> Dict[str, str]:
    """
    Get procurement users assigned to brands in a quote.

    This function:
    1. Gets all unique brands from quote_items
    2. Looks up procurement managers assigned to each brand
    3. Returns a mapping of brand -> user_id

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict mapping brand names to assigned user IDs
        Only includes brands that have assigned procurement managers

    Example:
        >>> brand_users = get_procurement_users_for_quote(quote_id)
        >>> print(brand_users)
        {'Siemens': 'user-uuid-1', 'ABB': 'user-uuid-2'}
    """
    supabase = get_supabase()

    # Get quote's organization_id and unique brands from items
    try:
        # First get the organization_id from the quote
        quote_response = supabase.table("quotes") \
            .select("organization_id") \
            .eq("id", quote_id) \
            .single() \
            .execute()

        if not quote_response.data:
            return {}

        org_id = quote_response.data.get("organization_id")
        if not org_id:
            return {}

        # Get all unique brands from quote items
        items_response = supabase.table("quote_items") \
            .select("brand") \
            .eq("quote_id", quote_id) \
            .execute()

        if not items_response.data:
            return {}

        # Extract unique brands (case-insensitive)
        brands = set()
        for item in items_response.data:
            brand = item.get("brand")
            if brand:
                brands.add(brand.strip())

        if not brands:
            return {}

        # Get brand assignments for these brands
        assignments_response = supabase.table("brand_assignments") \
            .select("brand, user_id") \
            .eq("organization_id", org_id) \
            .execute()

        if not assignments_response.data:
            return {}

        # Build mapping (case-insensitive match)
        brand_to_user = {}
        for assignment in assignments_response.data:
            assigned_brand = assignment.get("brand", "").strip().lower()
            user_id = assignment.get("user_id")
            for brand in brands:
                if brand.lower() == assigned_brand:
                    brand_to_user[brand] = user_id

        return brand_to_user

    except Exception as e:
        return {}


def assign_procurement_users_to_quote(quote_id: str) -> Dict:
    """
    Auto-assign procurement users to a quote based on brands.

    This function:
    1. Gets all brands from quote_items
    2. Looks up procurement managers for each brand
    3. Assigns users to individual quote_items
    4. Collects unique user IDs for quote-level assignment
    5. Updates quote.assigned_procurement_users array

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict with:
        - success: bool
        - assigned_users: list of user IDs assigned
        - assigned_items: count of items with assignments
        - unassigned_brands: list of brands without managers
        - error_message: error if failed

    Example:
        >>> result = assign_procurement_users_to_quote(quote_id)
        >>> if result["success"]:
        ...     print(f"Assigned {len(result['assigned_users'])} procurement managers")
    """
    supabase = get_supabase()

    try:
        # Get quote info
        quote_response = supabase.table("quotes") \
            .select("id, organization_id") \
            .eq("id", quote_id) \
            .single() \
            .execute()

        if not quote_response.data:
            return {
                "success": False,
                "error_message": f"Quote not found: {quote_id}",
                "assigned_users": [],
                "assigned_items": 0,
                "unassigned_brands": []
            }

        org_id = quote_response.data.get("organization_id")

        # Get quote items with their brands
        items_response = supabase.table("quote_items") \
            .select("id, brand") \
            .eq("quote_id", quote_id) \
            .execute()

        if not items_response.data:
            return {
                "success": True,
                "error_message": None,
                "assigned_users": [],
                "assigned_items": 0,
                "unassigned_brands": []
            }

        # Get all brand assignments for this org
        assignments_response = supabase.table("brand_assignments") \
            .select("brand, user_id") \
            .eq("organization_id", org_id) \
            .execute()

        # Build case-insensitive brand -> user mapping
        brand_to_user = {}
        if assignments_response.data:
            for a in assignments_response.data:
                brand = (a.get("brand") or "").strip().lower()
                if brand:  # Only add non-empty brands
                    brand_to_user[brand] = a.get("user_id")

        # Assign users to items and collect stats
        assigned_user_ids = set()
        assigned_items_count = 0
        unassigned_brands = set()

        for item in items_response.data:
            item_id = item.get("id")
            brand = (item.get("brand") or "").strip()

            if not brand:
                continue

            user_id = brand_to_user.get(brand.lower())

            if user_id:
                # Update the item with assigned procurement user
                supabase.table("quote_items") \
                    .update({
                        "assigned_procurement_user": user_id,
                        "procurement_status": "pending"
                    }) \
                    .eq("id", item_id) \
                    .execute()

                assigned_user_ids.add(user_id)
                assigned_items_count += 1
            else:
                unassigned_brands.add(brand)

        # Update quote with array of assigned procurement users
        assigned_users_list = list(assigned_user_ids)

        if assigned_users_list:
            supabase.table("quotes") \
                .update({"assigned_procurement_users": assigned_users_list}) \
                .eq("id", quote_id) \
                .execute()

        return {
            "success": True,
            "error_message": None,
            "assigned_users": assigned_users_list,
            "assigned_items": assigned_items_count,
            "unassigned_brands": list(unassigned_brands)
        }

    except Exception as e:
        return {
            "success": False,
            "error_message": str(e),
            "assigned_users": [],
            "assigned_items": 0,
            "unassigned_brands": []
        }


def transition_to_pending_procurement(
    quote_id: str,
    actor_id: str,
    actor_roles: List[str],
    comment: Optional[str] = None
) -> TransitionResult:
    """
    Transition a quote to pending_procurement status with auto-assignment.

    This is a specialized transition function that:
    1. Validates the transition is allowed
    2. Auto-assigns procurement users based on brands
    3. Updates quote status to pending_procurement
    4. Logs the transition

    This should be called instead of generic transition_quote_status() when
    moving to pending_procurement to ensure procurement users are assigned.

    Args:
        quote_id: UUID of the quote
        actor_id: UUID of the user performing the transition
        actor_roles: List of role codes the actor has
        comment: Optional comment for the transition

    Returns:
        TransitionResult with additional info about assignments

    Example:
        >>> result = transition_to_pending_procurement(
        ...     quote_id="quote-uuid",
        ...     actor_id="user-uuid",
        ...     actor_roles=["sales"]
        ... )
        >>> if result.success:
        ...     print("Transitioned to pending_procurement")
    """
    supabase = get_supabase()

    # First, get current status and validate
    try:
        quote_response = supabase.table("quotes") \
            .select("id, workflow_status, organization_id") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    if not quote_response.data:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    current_status = quote_response.data.get("workflow_status", "draft")

    # Validate the transition
    allowed, error = can_transition(
        current_status,
        WorkflowStatus.PENDING_PROCUREMENT,
        actor_roles
    )

    if not allowed:
        return TransitionResult(
            success=False,
            error_message=error,
            quote_id=quote_id,
            from_status=current_status
        )

    # Auto-assign procurement users BEFORE transitioning
    assignment_result = assign_procurement_users_to_quote(quote_id)

    if not assignment_result["success"]:
        return TransitionResult(
            success=False,
            error_message=f"Failed to assign procurement users: {assignment_result['error_message']}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Build comment with assignment info
    auto_comment_parts = []
    if assignment_result["assigned_users"]:
        auto_comment_parts.append(
            f"Назначено {len(assignment_result['assigned_users'])} менеджеров по закупкам"
        )
    if assignment_result["unassigned_brands"]:
        auto_comment_parts.append(
            f"Бренды без назначения: {', '.join(assignment_result['unassigned_brands'])}"
        )

    auto_comment = ". ".join(auto_comment_parts)
    full_comment = f"{comment}. {auto_comment}" if comment else auto_comment

    # Now perform the actual status transition
    try:
        update_response = supabase.table("quotes") \
            .update({
                # Note: Don't update legacy "status" field - it has different valid values
                # Only update workflow_status which tracks the actual workflow state
                "workflow_status": WorkflowStatus.PENDING_PROCUREMENT.value,
                "procurement_completed_at": None  # Reset in case of re-evaluation
            }) \
            .eq("id", quote_id) \
            .execute()

        if not update_response.data:
            return TransitionResult(
                success=False,
                error_message="Failed to update quote status",
                quote_id=quote_id,
                from_status=current_status
            )
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Database error: {str(e)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Log the transition
    actor_role = "sales" if "sales" in actor_roles else "admin"
    try:
        transition_data = {
            "quote_id": quote_id,
            "from_status": current_status,
            "to_status": WorkflowStatus.PENDING_PROCUREMENT.value,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "comment": full_comment if full_comment else None
        }

        log_response = supabase.table("workflow_transitions") \
            .insert(transition_data) \
            .execute()

        transition_id = None
        if log_response.data and len(log_response.data) > 0:
            transition_id = log_response.data[0].get("id")

    except Exception:
        transition_id = None  # Non-critical

    return TransitionResult(
        success=True,
        error_message=None,
        quote_id=quote_id,
        from_status=current_status,
        to_status=WorkflowStatus.PENDING_PROCUREMENT.value,
        transition_id=transition_id
    )


def get_quote_procurement_status(quote_id: str) -> Dict:
    """
    Get detailed procurement status for a quote.

    Returns information about:
    - Assigned procurement users
    - Items by brand and their status
    - Overall completion percentage

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict with procurement status details

    Example:
        >>> status = get_quote_procurement_status(quote_id)
        >>> print(f"Completion: {status['completion_percent']}%")
    """
    supabase = get_supabase()

    try:
        # Get quote info
        quote_response = supabase.table("quotes") \
            .select("assigned_procurement_users, procurement_completed_at, workflow_status") \
            .eq("id", quote_id) \
            .single() \
            .execute()

        if not quote_response.data:
            return {"error": "Quote not found"}

        quote = quote_response.data

        # Get items with procurement status
        items_response = supabase.table("quote_items") \
            .select("id, brand, assigned_procurement_user, procurement_status") \
            .eq("quote_id", quote_id) \
            .execute()

        items = items_response.data or []

        # Calculate stats
        total_items = len(items)
        completed_items = sum(1 for i in items if i.get("procurement_status") == "completed")
        pending_items = sum(1 for i in items if i.get("procurement_status") == "pending")
        in_progress_items = sum(1 for i in items if i.get("procurement_status") == "in_progress")

        # Group by brand
        brands_status = {}
        for item in items:
            brand = item.get("brand", "Unknown")
            if brand not in brands_status:
                brands_status[brand] = {
                    "total": 0,
                    "completed": 0,
                    "pending": 0,
                    "assigned_user": item.get("assigned_procurement_user")
                }
            brands_status[brand]["total"] += 1
            status = item.get("procurement_status", "pending")
            if status == "completed":
                brands_status[brand]["completed"] += 1
            else:
                brands_status[brand]["pending"] += 1

        completion_percent = round(completed_items / total_items * 100, 1) if total_items > 0 else 0

        return {
            "quote_id": quote_id,
            "workflow_status": quote.get("workflow_status"),
            "assigned_procurement_users": quote.get("assigned_procurement_users", []),
            "procurement_completed_at": quote.get("procurement_completed_at"),
            "total_items": total_items,
            "completed_items": completed_items,
            "pending_items": pending_items,
            "in_progress_items": in_progress_items,
            "completion_percent": completion_percent,
            "is_complete": completed_items == total_items and total_items > 0,
            "brands_status": brands_status
        }

    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# PROCUREMENT COMPLETION FUNCTIONS (Feature #37)
# =============================================================================
# Handles checking if all procurement is complete and auto-transitioning


def check_all_procurement_complete(quote_id: str) -> Dict:
    """
    Check if all procurement items for a quote are complete.

    This function checks if ALL quote_items (not just one user's brands)
    have procurement_status = 'completed'.

    Args:
        quote_id: UUID of the quote

    Returns:
        Dict with:
        - is_complete: bool - True if all items are complete
        - total_items: int - Total number of items
        - completed_items: int - Number of completed items
        - pending_items: int - Number of pending items

    Example:
        >>> status = check_all_procurement_complete(quote_id)
        >>> if status["is_complete"]:
        ...     print("All procurement complete!")
    """
    supabase = get_supabase()

    try:
        # Get all items for this quote
        items_response = supabase.table("quote_items") \
            .select("id, procurement_status") \
            .eq("quote_id", quote_id) \
            .execute()

        items = items_response.data or []

        total_items = len(items)
        completed_items = sum(1 for i in items if i.get("procurement_status") == "completed")
        pending_items = total_items - completed_items

        return {
            "is_complete": completed_items == total_items and total_items > 0,
            "total_items": total_items,
            "completed_items": completed_items,
            "pending_items": pending_items
        }

    except Exception as e:
        return {
            "is_complete": False,
            "total_items": 0,
            "completed_items": 0,
            "pending_items": 0,
            "error": str(e)
        }


def complete_procurement(
    quote_id: str,
    actor_id: str,
    actor_roles: List[str]
) -> TransitionResult:
    """
    Complete the procurement phase for a quote and trigger auto-transition.

    This function:
    1. Validates the user has procurement or admin role
    2. Checks if ALL procurement items are complete
    3. If complete, sets procurement_completed_at timestamp
    4. Transitions quote to pending_logistics_and_customs (parallel stage)

    Note: The workflow handles logistics and customs as parallel stages.
    When procurement completes, the quote goes to pending_logistics_and_customs status
    where both departments can work simultaneously.

    Args:
        quote_id: UUID of the quote
        actor_id: UUID of the user completing procurement
        actor_roles: List of role codes the user has

    Returns:
        TransitionResult indicating success or failure

    Example:
        >>> result = complete_procurement(quote_id, user_id, ["procurement"])
        >>> if result.success:
        ...     print(f"Procurement complete! New status: {result.to_status}")
    """
    supabase = get_supabase()

    # Validate role
    if not any(role in ["procurement", "admin"] for role in actor_roles):
        return TransitionResult(
            success=False,
            error_message="Only procurement or admin can complete procurement",
            quote_id=quote_id
        )

    # Get current quote status
    try:
        response = supabase.table("quotes") \
            .select("id, workflow_status, procurement_completed_at") \
            .eq("id", quote_id) \
            .single() \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    if not response.data:
        return TransitionResult(
            success=False,
            error_message=f"Quote not found: {quote_id}",
            quote_id=quote_id
        )

    quote = response.data
    current_status = quote.get("workflow_status")

    # Validate current status - must be pending_procurement
    if current_status != WorkflowStatus.PENDING_PROCUREMENT.value:
        return TransitionResult(
            success=False,
            error_message=f"Cannot complete procurement from status: {get_status_name(current_status)}. Quote must be in 'Ожидает оценки закупок' status.",
            quote_id=quote_id,
            from_status=current_status
        )

    # Check if already completed
    if quote.get("procurement_completed_at"):
        return TransitionResult(
            success=False,
            error_message="Procurement already completed for this quote",
            quote_id=quote_id,
            from_status=current_status
        )

    # Check if ALL procurement items are complete
    completion_status = check_all_procurement_complete(quote_id)

    if not completion_status["is_complete"]:
        pending = completion_status["pending_items"]
        total = completion_status["total_items"]
        return TransitionResult(
            success=False,
            error_message=f"Not all procurement items are complete. {pending} of {total} items still pending.",
            quote_id=quote_id,
            from_status=current_status
        )

    # All items complete! Set procurement_completed_at and transition to parallel stage
    try:
        update_response = supabase.table("quotes") \
            .update({
                "procurement_completed_at": datetime.now(timezone.utc).isoformat(),
                "workflow_status": WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value
            }) \
            .eq("id", quote_id) \
            .execute()
    except Exception as e:
        return TransitionResult(
            success=False,
            error_message=f"Failed to update quote: {str(e)}",
            quote_id=quote_id,
            from_status=current_status
        )

    # Log the transition in workflow_transitions
    try:
        actor_role = "procurement" if "procurement" in actor_roles else "admin"
        transition_data = {
            "quote_id": quote_id,
            "from_status": current_status,
            "to_status": WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "comment": "Оценка закупок завершена. Все позиции оценены. Переход в параллельную стадию (логистика + таможня)."
        }
        log_response = supabase.table("workflow_transitions").insert(transition_data).execute()
        transition_id = log_response.data[0].get("id") if log_response.data else None
    except Exception:
        transition_id = None  # Non-critical, continue

    return TransitionResult(
        success=True,
        error_message=None,
        quote_id=quote_id,
        from_status=current_status,
        to_status=WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value,
        transition_id=transition_id
    )
