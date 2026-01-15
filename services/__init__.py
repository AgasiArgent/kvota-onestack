"""
OneStack Services

Export and versioning services for quote management.
Role management services for workflow system.
Workflow service for quote status management.
"""

from .database import get_supabase, get_anon_client
from .export_data_mapper import fetch_export_data, ExportData
from .specification_export import generate_specification_pdf
from .invoice_export import generate_invoice_pdf
from .validation_export import create_validation_excel
from .quote_version_service import create_quote_version, list_quote_versions, get_quote_version
from .role_service import (
    Role,
    UserRole,
    get_user_roles,
    get_user_role_codes,
    has_role,
    has_any_role,
    has_all_roles,
    assign_role,
    remove_role,
    get_all_roles,
    get_role_by_code,
    get_users_by_role,
    get_users_by_any_role,
    # Route protection middleware
    require_role,
    require_any_role,
    require_all_roles,
    get_session_user_roles,
)
from .brand_service import (
    # Data class
    BrandAssignment,
    # Create operations
    create_brand_assignment,
    upsert_brand_assignment,
    bulk_create_assignments,
    # Read operations
    get_brand_assignment,
    get_brand_assignment_by_brand,
    get_all_brand_assignments,
    get_user_brand_assignments,
    get_assignments_with_user_details,
    # Update operations
    update_brand_assignment,
    reassign_brand,
    # Delete operations
    delete_brand_assignment,
    delete_brand_assignment_by_brand,
    delete_all_user_assignments,
    # Utility functions
    get_unique_brands_in_org,
    get_unassigned_brands,
    get_brand_manager_mapping,
    count_assignments_by_user,
    is_brand_assigned,
)
from .workflow_service import (
    # Enum and data classes
    WorkflowStatus,
    StatusTransition,
    TransitionResult,
    # Status metadata
    STATUS_NAMES,
    STATUS_NAMES_SHORT,
    STATUS_COLORS,
    IN_PROGRESS_STATUSES,
    FINAL_STATUSES,
    ALLOWED_TRANSITIONS,
    # Helper functions
    get_status_name,
    get_status_name_short,
    get_status_color,
    get_allowed_transitions,
    get_allowed_target_statuses,
    can_transition,
    is_final_status,
    is_in_progress,
    get_workflow_order,
    get_workflow_stage,
    get_all_statuses,
    # Permission matrix functions (Feature #24)
    get_transition_requirements,
    get_roles_for_transition,
    get_transitions_by_role,
    get_permission_matrix,
    get_permission_matrix_detailed,
    get_outgoing_transitions,
    get_incoming_transitions,
    is_comment_required,
    is_auto_transition,
    # Transition execution functions (Feature #25)
    transition_quote_status,
    get_quote_workflow_status,
    get_quote_transition_history,
    get_available_transitions_for_quote,
    # Auto-transition functions (Feature #28)
    check_and_auto_transition_to_sales_review,
    complete_logistics,
    complete_customs,
    get_parallel_stages_status,
    # Procurement assignment functions (Feature #29)
    get_procurement_users_for_quote,
    assign_procurement_users_to_quote,
    transition_to_pending_procurement,
    get_quote_procurement_status,
)

__all__ = [
    # Database
    "get_supabase",
    "get_anon_client",
    # Export
    "fetch_export_data",
    "ExportData",
    "generate_specification_pdf",
    "generate_invoice_pdf",
    "create_validation_excel",
    # Versioning
    "create_quote_version",
    "list_quote_versions",
    "get_quote_version",
    # Roles
    "Role",
    "UserRole",
    "get_user_roles",
    "get_user_role_codes",
    "has_role",
    "has_any_role",
    "has_all_roles",
    "assign_role",
    "remove_role",
    "get_all_roles",
    "get_role_by_code",
    "get_users_by_role",
    "get_users_by_any_role",
    # Route protection middleware
    "require_role",
    "require_any_role",
    "require_all_roles",
    "get_session_user_roles",
    # Brand assignments (Feature #30)
    "BrandAssignment",
    "create_brand_assignment",
    "upsert_brand_assignment",
    "bulk_create_assignments",
    "get_brand_assignment",
    "get_brand_assignment_by_brand",
    "get_all_brand_assignments",
    "get_user_brand_assignments",
    "get_assignments_with_user_details",
    "update_brand_assignment",
    "reassign_brand",
    "delete_brand_assignment",
    "delete_brand_assignment_by_brand",
    "delete_all_user_assignments",
    "get_unique_brands_in_org",
    "get_unassigned_brands",
    "get_brand_manager_mapping",
    "count_assignments_by_user",
    "is_brand_assigned",
    # Workflow
    "WorkflowStatus",
    "StatusTransition",
    "TransitionResult",
    "STATUS_NAMES",
    "STATUS_NAMES_SHORT",
    "STATUS_COLORS",
    "IN_PROGRESS_STATUSES",
    "FINAL_STATUSES",
    "ALLOWED_TRANSITIONS",
    "get_status_name",
    "get_status_name_short",
    "get_status_color",
    "get_allowed_transitions",
    "get_allowed_target_statuses",
    "can_transition",
    "is_final_status",
    "is_in_progress",
    "get_workflow_order",
    "get_workflow_stage",
    "get_all_statuses",
    # Permission matrix functions (Feature #24)
    "get_transition_requirements",
    "get_roles_for_transition",
    "get_transitions_by_role",
    "get_permission_matrix",
    "get_permission_matrix_detailed",
    "get_outgoing_transitions",
    "get_incoming_transitions",
    "is_comment_required",
    "is_auto_transition",
    # Transition execution functions (Feature #25)
    "transition_quote_status",
    "get_quote_workflow_status",
    "get_quote_transition_history",
    "get_available_transitions_for_quote",
    # Auto-transition functions (Feature #28)
    "check_and_auto_transition_to_sales_review",
    "complete_logistics",
    "complete_customs",
    "get_parallel_stages_status",
    # Procurement assignment functions (Feature #29)
    "get_procurement_users_for_quote",
    "assign_procurement_users_to_quote",
    "transition_to_pending_procurement",
    "get_quote_procurement_status",
]
