"""
Quote Multi-Department Approval Service

Handles department-level approval workflow for quotes.
Feature: Bug #8 follow-up - Granular approval tracking

Workflow:
  procurement → (logistics + customs parallel) → sales → control → pending_spec_control status

Rules:
  - All 5 departments must approve before spec controller can create specification
  - Sequential with parallel section for logistics/customs
  - Any department can reject and rollback dependent approvals
  - Admin can override and approve any department
"""

from datetime import datetime
from typing import Optional, Tuple, Dict, List
from .database import get_supabase


# Department workflow configuration
DEPARTMENTS = ['procurement', 'logistics', 'customs', 'sales', 'control']

# Department display names (Russian)
DEPARTMENT_NAMES = {
    'procurement': 'Закупки',
    'logistics': 'Логистика',
    'customs': 'Таможня',
    'sales': 'Продажи',
    'control': 'Контроль'
}

# Role requirements for each department
DEPARTMENT_ROLES = {
    'procurement': ['procurement_specialist', 'admin'],
    'logistics': ['logistics_specialist', 'admin'],
    'customs': ['customs_specialist', 'admin'],
    'sales': ['sales_manager', 'quote_controller', 'admin'],
    'control': ['spec_controller', 'admin']
}


# ============================================================================
# Workflow Logic
# ============================================================================

def can_department_approve(approvals: dict, department: str) -> bool:
    """
    Check if a department can approve based on workflow prerequisites.

    Workflow rules:
    - procurement: Always can approve (first step)
    - logistics/customs: Require procurement approval
    - sales: Require BOTH logistics AND customs approval
    - control: Require sales approval

    Args:
        approvals: Current approvals dict from quote
        department: Department name ('procurement', 'logistics', etc.)

    Returns:
        True if department can approve now, False otherwise
    """
    if department not in DEPARTMENTS:
        return False

    # Procurement is always the first step
    if department == 'procurement':
        return True

    # Logistics and Customs require procurement approval
    elif department in ['logistics', 'customs']:
        return approvals.get('procurement', {}).get('approved', False)

    # Sales requires BOTH logistics AND customs approval
    elif department == 'sales':
        logistics_ok = approvals.get('logistics', {}).get('approved', False)
        customs_ok = approvals.get('customs', {}).get('approved', False)
        return logistics_ok and customs_ok

    # Control requires sales approval
    elif department == 'control':
        return approvals.get('sales', {}).get('approved', False)

    return False


def get_blocking_departments(approvals: dict, department: str) -> List[str]:
    """
    Get list of departments that are blocking this department from approving.

    Args:
        approvals: Current approvals dict
        department: Department to check

    Returns:
        List of department names that must approve first
    """
    blocking = []

    if department in ['logistics', 'customs']:
        if not approvals.get('procurement', {}).get('approved', False):
            blocking.append('procurement')

    elif department == 'sales':
        if not approvals.get('logistics', {}).get('approved', False):
            blocking.append('logistics')
        if not approvals.get('customs', {}).get('approved', False):
            blocking.append('customs')

    elif department == 'control':
        if not approvals.get('sales', {}).get('approved', False):
            blocking.append('sales')

    return blocking


def get_dependent_departments(department: str) -> List[str]:
    """
    Get departments that depend on this department's approval.
    Used for rollback when rejecting.

    Args:
        department: Department that is rejecting

    Returns:
        List of department names that should be rolled back
    """
    if department == 'procurement':
        # Rolling back procurement clears everything
        return ['logistics', 'customs', 'sales', 'control']

    elif department in ['logistics', 'customs']:
        # Rolling back logistics or customs clears sales and control
        return ['sales', 'control']

    elif department == 'sales':
        # Rolling back sales only clears control
        return ['control']

    elif department == 'control':
        # Rolling back control has no dependents
        return []

    return []


def are_all_departments_approved(approvals: dict) -> bool:
    """
    Check if all 5 departments have approved.

    Args:
        approvals: Current approvals dict

    Returns:
        True if all departments approved, False otherwise
    """
    for dept in DEPARTMENTS:
        if not approvals.get(dept, {}).get('approved', False):
            return False
    return True


def get_next_departments(approvals: dict) -> List[str]:
    """
    Get list of departments that can approve next.

    Args:
        approvals: Current approvals dict

    Returns:
        List of department names that can currently approve
    """
    next_depts = []
    for dept in DEPARTMENTS:
        if not approvals.get(dept, {}).get('approved', False):
            if can_department_approve(approvals, dept):
                next_depts.append(dept)
    return next_depts


# ============================================================================
# Approval Operations
# ============================================================================

def approve_department(
    quote_id: str,
    organization_id: str,
    department: str,
    user_id: str,
    comments: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Approve quote for a specific department.

    Workflow:
    1. Validates department and prerequisites
    2. Updates approval record for department
    3. If all 5 departments approved → changes status to 'pending_spec_control'
       (ready for spec controller to create specification)

    Args:
        quote_id: UUID of quote
        organization_id: UUID of organization (security check)
        department: Department name
        user_id: ID of user approving
        comments: Optional comments/notes

    Returns:
        (success: bool, message: str)
    """
    if department not in DEPARTMENTS:
        return False, f"Invalid department: {department}"

    supabase = get_supabase()

    try:
        # 1. Get current quote
        result = supabase.table('quotes').select('id, status, workflow_status, approvals') \
            .eq('id', quote_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return False, "Quote not found"

        quote = result.data[0]
        status = quote.get('workflow_status') or quote.get('status', 'draft')
        approvals = quote.get('approvals', {})

        # 2. Check status allows approval (not yet approved by spec controller)
        if status not in ['draft', 'pending_review', 'pending_procurement', 'pending_logistics',
                          'pending_customs', 'pending_sales', 'pending_control']:
            return False, f"Cannot approve quote with status: {status}"

        # 3. Check if already approved by this department
        if approvals.get(department, {}).get('approved', False):
            return False, f"{DEPARTMENT_NAMES[department]} уже одобрило КП"

        # 4. Check workflow prerequisites
        if not can_department_approve(approvals, department):
            blocking = get_blocking_departments(approvals, department)
            blocking_names = [DEPARTMENT_NAMES[d] for d in blocking]
            return False, f"Требуется одобрение: {', '.join(blocking_names)}"

        # 5. Update approval for this department
        approvals[department] = {
            'approved': True,
            'approved_by': user_id,
            'approved_at': datetime.now().isoformat(),
            'comments': comments
        }

        # 6. Check if all departments have approved
        update_data = {'approvals': approvals, 'updated_at': datetime.now().isoformat()}

        if are_all_departments_approved(approvals):
            # All approved! Change status to 'pending_spec_control'
            # This signals to spec controller that they can create the specification
            update_data['workflow_status'] = 'pending_spec_control'
            message = f"{DEPARTMENT_NAMES[department]} одобрило. КП готово к созданию спецификации!"
        else:
            message = f"{DEPARTMENT_NAMES[department]} одобрило КП"

        # 7. Save to database
        supabase.table('quotes').update(update_data) \
            .eq('id', quote_id) \
            .eq('organization_id', organization_id) \
            .execute()

        return True, message

    except Exception as e:
        print(f"Error approving department: {e}")
        return False, f"Database error: {str(e)}"


def reject_department(
    quote_id: str,
    organization_id: str,
    department: str,
    user_id: str,
    reason: str
) -> Tuple[bool, str]:
    """
    Reject quote from a department and rollback dependent approvals.

    Rollback rules:
    - procurement reject → clears logistics, customs, sales, control
    - logistics/customs reject → clears sales, control
    - sales reject → clears control
    - control reject → clears only control

    Args:
        quote_id: UUID of quote
        organization_id: UUID of organization
        department: Department rejecting
        user_id: ID of user rejecting
        reason: Required reason for rejection

    Returns:
        (success: bool, message: str)
    """
    if department not in DEPARTMENTS:
        return False, f"Invalid department: {department}"

    if not reason or len(reason.strip()) == 0:
        return False, "Причина отклонения обязательна"

    supabase = get_supabase()

    try:
        # 1. Get current quote
        result = supabase.table('quotes').select('id, status, workflow_status, approvals') \
            .eq('id', quote_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return False, "Quote not found"

        quote = result.data[0]
        approvals = quote.get('approvals', {})

        # 2. Clear approval for this department
        approvals[department] = {
            'approved': False,
            'approved_by': user_id,
            'approved_at': datetime.now().isoformat(),
            'comments': f"ОТКЛОНЕНО: {reason}"
        }

        # 3. Rollback dependent departments
        dependents = get_dependent_departments(department)
        for dept in dependents:
            approvals[dept] = {
                'approved': False,
                'approved_by': None,
                'approved_at': None,
                'comments': f"Сброшено из-за отклонения: {DEPARTMENT_NAMES[department]}"
            }

        # 4. If quote was "pending_spec_control", revert to "pending_review"
        update_data = {'approvals': approvals, 'updated_at': datetime.now().isoformat()}
        status = quote.get('workflow_status') or quote.get('status', 'draft')
        if status == 'pending_spec_control':
            update_data['workflow_status'] = 'pending_review'

        # 5. Save to database
        supabase.table('quotes').update(update_data) \
            .eq('id', quote_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if dependents:
            dependent_names = [DEPARTMENT_NAMES[d] for d in dependents]
            message = f"{DEPARTMENT_NAMES[department]} отклонило. Сброшены одобрения: {', '.join(dependent_names)}"
        else:
            message = f"{DEPARTMENT_NAMES[department]} отклонило КП"

        return True, message

    except Exception as e:
        print(f"Error rejecting department: {e}")
        return False, f"Database error: {str(e)}"


# ============================================================================
# Query Operations
# ============================================================================

def get_approval_status(quote_id: str, organization_id: str) -> Optional[Dict]:
    """
    Get detailed approval status for UI display.

    Args:
        quote_id: UUID of quote
        organization_id: UUID of organization

    Returns:
        Dict with approval status for all departments, or None if not found

    Example return:
        {
          'procurement': {
            'approved': True,
            'can_approve': False,
            'approved_by': 'user-123',
            'approved_by_name': 'Иван Петров',
            'approved_at': '2025-01-15T14:30:00',
            'comments': 'Цены согласованы',
            'blocking_departments': []
          },
          'logistics': {...},
          ... (for each department),
          'all_approved': False,
          'next_departments': ['logistics', 'customs'],
          'progress_percentage': 20  # (1/5 approved)
        }
    """
    supabase = get_supabase()

    try:
        # Get quote with approvals
        result = supabase.table('quotes').select('id, status, workflow_status, approvals') \
            .eq('id', quote_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return None

        quote = result.data[0]
        approvals = quote.get('approvals', {})

        # Build status dict for each department
        status_dict = {}
        approved_count = 0

        for dept in DEPARTMENTS:
            dept_approval = approvals.get(dept, {})
            is_approved = dept_approval.get('approved', False)

            if is_approved:
                approved_count += 1

            dept_status = {
                'approved': is_approved,
                'can_approve': can_department_approve(approvals, dept) and not is_approved,
                'approved_by': dept_approval.get('approved_by'),
                'approved_by_name': None,  # TODO: Fetch from users table if needed
                'approved_at': dept_approval.get('approved_at'),
                'comments': dept_approval.get('comments'),
                'blocking_departments': get_blocking_departments(approvals, dept) if not is_approved else []
            }

            status_dict[dept] = dept_status

        # Add summary info
        status_dict['all_approved'] = are_all_departments_approved(approvals)
        status_dict['next_departments'] = get_next_departments(approvals)
        status_dict['progress_percentage'] = int((approved_count / len(DEPARTMENTS)) * 100)
        status_dict['approved_count'] = approved_count
        status_dict['total_count'] = len(DEPARTMENTS)

        return status_dict

    except Exception as e:
        print(f"Error getting approval status: {e}")
        return None


def get_quotes_pending_approval(
    organization_id: str,
    department: str,
    limit: int = 50
) -> List[Dict]:
    """
    Get quotes awaiting approval from a specific department.

    Args:
        organization_id: UUID of organization
        department: Department name
        limit: Maximum results

    Returns:
        List of quote dicts

    Filtering:
        - status = in active workflow (not won/lost/cancelled)
        - can_department_approve(approvals, department) = true
    """
    if department not in DEPARTMENTS:
        return []

    supabase = get_supabase()

    try:
        # Get all quotes in workflow stages
        result = supabase.table('quotes').select(
            'id, idn_quote, customer_name, total_amount, currency, status, approvals, created_at'
        ).eq('organization_id', organization_id) \
          .in_('status', ['draft', 'pending_review', 'pending_procurement', 'pending_logistics',
                          'pending_customs', 'pending_sales', 'pending_control']) \
          .order('created_at', desc=False) \
          .limit(limit) \
          .execute()

        if not result.data:
            return []

        # Filter by workflow rules
        pending_quotes = []
        for quote in result.data:
            approvals = quote.get('approvals', {})
            if can_department_approve(approvals, department):
                # Add department-specific metadata
                quote['department'] = department
                quote['department_name'] = DEPARTMENT_NAMES[department]
                pending_quotes.append(quote)

        return pending_quotes

    except Exception as e:
        print(f"Error getting pending quotes: {e}")
        return []


def get_quote_approval_history(quote_id: str, organization_id: str) -> List[Dict]:
    """
    Get chronological approval history for a quote.

    Args:
        quote_id: UUID of quote
        organization_id: UUID of organization

    Returns:
        List of approval events sorted by timestamp

    Example:
        [
          {
            'department': 'procurement',
            'department_name': 'Закупки',
            'approved': True,
            'approved_by': 'user-123',
            'approved_at': '2025-01-15T14:30:00',
            'comments': 'Цены согласованы'
          },
          ...
        ]
    """
    supabase = get_supabase()

    try:
        result = supabase.table('quotes').select('approvals') \
            .eq('id', quote_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return []

        approvals = result.data[0].get('approvals', {})
        history = []

        for dept in DEPARTMENTS:
            dept_approval = approvals.get(dept, {})
            if dept_approval.get('approved_at'):  # Only include if there's a timestamp
                history.append({
                    'department': dept,
                    'department_name': DEPARTMENT_NAMES[dept],
                    'approved': dept_approval.get('approved', False),
                    'approved_by': dept_approval.get('approved_by'),
                    'approved_at': dept_approval.get('approved_at'),
                    'comments': dept_approval.get('comments')
                })

        # Sort by timestamp
        history.sort(key=lambda x: x['approved_at'] or '')

        return history

    except Exception as e:
        print(f"Error getting approval history: {e}")
        return []


# ============================================================================
# Permission Checks
# ============================================================================

def user_can_approve_department(session: dict, department: str) -> bool:
    """
    Check if user has permission to approve for a department.

    Args:
        session: User session dict with roles
        department: Department name

    Returns:
        True if user has required role
    """
    if department not in DEPARTMENT_ROLES:
        return False

    user_roles = session.get('user', {}).get('roles', [])
    required_roles = DEPARTMENT_ROLES[department]

    # Check if user has any of the required roles
    return any(role in required_roles for role in user_roles)
