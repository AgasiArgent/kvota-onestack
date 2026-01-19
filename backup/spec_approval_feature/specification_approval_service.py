"""
Specification Multi-Department Approval Service

Handles department-level approval workflow for specifications.
Feature: Bug #8 follow-up - Granular approval tracking

Workflow:
  procurement → (logistics + customs parallel) → sales → control → approved status

Rules:
  - All 5 departments must approve
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
        approvals: Current approvals dict from specification
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
    spec_id: str,
    organization_id: str,
    department: str,
    user_id: str,
    comments: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Approve specification for a specific department.

    Workflow:
    1. Validates department and prerequisites
    2. Updates approval record for department
    3. If all 5 departments approved → changes status to 'approved'

    Args:
        spec_id: UUID of specification
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
        # 1. Get current specification
        result = supabase.table('specifications').select('id, status, approvals') \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return False, "Specification not found"

        spec = result.data[0]
        status = spec.get('status')
        approvals = spec.get('approvals', {})

        # 2. Check status is pending_review
        if status not in ['pending_review', 'draft']:
            return False, f"Cannot approve specification with status: {status}"

        # 3. Check if already approved by this department
        if approvals.get(department, {}).get('approved', False):
            return False, f"{DEPARTMENT_NAMES[department]} уже одобрило спецификацию"

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
            # All approved! Change status to 'approved'
            update_data['status'] = 'approved'
            message = f"{DEPARTMENT_NAMES[department]} одобрило. Спецификация полностью согласована!"
        else:
            message = f"{DEPARTMENT_NAMES[department]} одобрило спецификацию"

        # 7. Save to database
        supabase.table('specifications').update(update_data) \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        return True, message

    except Exception as e:
        print(f"Error approving department: {e}")
        return False, f"Database error: {str(e)}"


def reject_department(
    spec_id: str,
    organization_id: str,
    department: str,
    user_id: str,
    reason: str
) -> Tuple[bool, str]:
    """
    Reject specification from a department and rollback dependent approvals.

    Rollback rules:
    - procurement reject → clears logistics, customs, sales, control
    - logistics/customs reject → clears sales, control
    - sales reject → clears control
    - control reject → clears only control

    Args:
        spec_id: UUID of specification
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
        # 1. Get current specification
        result = supabase.table('specifications').select('id, status, approvals') \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return False, "Specification not found"

        spec = result.data[0]
        approvals = spec.get('approvals', {})

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

        # 4. If spec was "approved", revert to "pending_review"
        update_data = {'approvals': approvals, 'updated_at': datetime.now().isoformat()}
        if spec.get('status') == 'approved':
            update_data['status'] = 'pending_review'

        # 5. Save to database
        supabase.table('specifications').update(update_data) \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if dependents:
            dependent_names = [DEPARTMENT_NAMES[d] for d in dependents]
            message = f"{DEPARTMENT_NAMES[department]} отклонило. Сброшены одобрения: {', '.join(dependent_names)}"
        else:
            message = f"{DEPARTMENT_NAMES[department]} отклонило спецификацию"

        return True, message

    except Exception as e:
        print(f"Error rejecting department: {e}")
        return False, f"Database error: {str(e)}"


# ============================================================================
# Query Operations
# ============================================================================

def get_approval_status(spec_id: str, organization_id: str) -> Optional[Dict]:
    """
    Get detailed approval status for UI display.

    Args:
        spec_id: UUID of specification
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
        # Get specification with approvals
        result = supabase.table('specifications').select('id, status, approvals') \
            .eq('id', spec_id) \
            .eq('organization_id', organization_id) \
            .execute()

        if not result.data:
            return None

        spec = result.data[0]
        approvals = spec.get('approvals', {})

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


def get_specs_pending_approval(
    organization_id: str,
    department: str,
    limit: int = 50
) -> List[Dict]:
    """
    Get specifications awaiting approval from a specific department.

    Args:
        organization_id: UUID of organization
        department: Department name
        limit: Maximum results

    Returns:
        List of specification dicts with quote details

    Filtering:
        - status = 'pending_review'
        - can_department_approve(approvals, department) = true
    """
    if department not in DEPARTMENTS:
        return []

    supabase = get_supabase()

    try:
        # Get all pending_review specs with quote details
        result = supabase.table('specifications').select(
            '*, quotes(id, idn_quote, customer_name, total_amount, currency)'
        ).eq('organization_id', organization_id) \
          .eq('status', 'pending_review') \
          .order('created_at', desc=False) \
          .limit(limit) \
          .execute()

        if not result.data:
            return []

        # Filter by workflow rules
        pending_specs = []
        for spec in result.data:
            approvals = spec.get('approvals', {})
            if can_department_approve(approvals, department):
                # Add department-specific metadata
                spec['department'] = department
                spec['department_name'] = DEPARTMENT_NAMES[department]
                pending_specs.append(spec)

        return pending_specs

    except Exception as e:
        print(f"Error getting pending specs: {e}")
        return []


def get_spec_approval_history(spec_id: str, organization_id: str) -> List[Dict]:
    """
    Get chronological approval history for a specification.

    Args:
        spec_id: UUID of specification
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
        result = supabase.table('specifications').select('approvals') \
            .eq('id', spec_id) \
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
