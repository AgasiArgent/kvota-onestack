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
        WorkflowStatus.PENDING_SALES_REVIEW,  # Return for revision
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
