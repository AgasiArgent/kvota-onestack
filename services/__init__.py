"""
OneStack Services

Export and versioning services for quote management.
Role management services for workflow system.
Workflow service for quote status management.
Telegram bot service for notifications and approvals.
"""

from .database import get_supabase, get_anon_client
from .export_data_mapper import fetch_export_data, ExportData
from .specification_export import (
    generate_specification_pdf,
    # Feature #70: Enhanced PDF generation from specifications table
    SpecificationData,
    fetch_specification_data,
    generate_spec_pdf_html,
    generate_spec_pdf_from_spec_id,
)
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
    # Convenience functions (Features #31, #32)
    get_procurement_manager,
    get_assigned_brands,
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
from .approval_service import (
    # Data classes
    Approval,
    ApprovalRequestResult,
    ApprovalDecisionResult,
    # Create operations
    create_approval,
    create_approvals_for_role,
    # Read operations
    get_approval,
    get_approval_by_quote,
    get_approvals_for_quote,
    get_pending_approval_for_quote,
    get_pending_approvals_for_user,
    get_approvals_requested_by,
    get_approvals_with_details,
    count_pending_approvals,
    # Update operations
    update_approval_status,
    approve_quote_approval,
    reject_quote_approval,
    # Delete operations
    cancel_pending_approvals_for_quote,
    # Utility functions
    has_pending_approval,
    get_latest_approval_decision,
    get_approval_stats_for_user,
    # High-level workflow functions (Feature #65, #66)
    request_approval,
    process_approval_decision,
)
from .specification_service import (
    # Data class
    Specification,
    CreateSpecFromQuoteResult,
    # Constants
    SPEC_STATUSES,
    SPEC_STATUS_NAMES,
    SPEC_STATUS_COLORS,
    SPEC_TRANSITIONS,
    # Status helpers
    get_spec_status_name,
    get_spec_status_color,
    can_transition_spec,
    get_allowed_spec_transitions,
    # Create operations
    create_specification,
    create_specification_from_quote,  # Feature #74
    # Read operations
    get_specification,
    get_specification_by_quote,
    get_specifications_by_status,
    get_all_specifications,
    get_specifications_with_details,
    count_specifications_by_status,
    specification_exists_for_quote,
    # Update operations
    update_specification,
    update_specification_status,
    set_signed_scan_url,
    # Delete operations
    delete_specification,
    # Utility functions
    generate_specification_number,
    get_specification_stats,
    get_specifications_for_signing,
    get_recently_signed_specifications,
)
from .deal_service import (
    # Data class
    Deal,
    CreateDealFromSpecResult,  # Feature #76
    # Constants
    DEAL_STATUSES,
    DEAL_STATUS_NAMES,
    DEAL_STATUS_COLORS,
    DEAL_TRANSITIONS,
    # Status helpers
    get_deal_status_name,
    get_deal_status_color,
    can_transition_deal,
    get_allowed_deal_transitions,
    is_deal_terminal,
    # Create operations
    create_deal,
    create_deal_from_specification,  # Feature #76
    # Read operations
    get_deal,
    get_deal_by_specification,
    get_deal_by_quote,
    get_deals_by_status,
    get_all_deals,
    get_deals_with_details,
    count_deals_by_status,
    deal_exists_for_specification,
    deal_exists_for_quote,
    # Update operations
    update_deal,
    update_deal_status,
    complete_deal,
    cancel_deal,
    update_deal_amount,
    # Delete operations
    delete_deal,
    # Utility functions
    generate_deal_number,
    get_deal_stats,
    get_active_deals,
    get_recent_deals,
    get_deals_by_date_range,
    search_deals,
)
from .plan_fact_service import (
    # Data classes
    PlanFactCategory,
    PlanFactItem,
    GeneratePlanFactResult,  # Feature #82
    # Category functions
    get_all_categories,
    get_category,
    get_category_by_code,
    get_income_categories,
    get_expense_categories,
    # Create operations
    create_plan_fact_item,
    create_plan_fact_item_with_category_code,
    bulk_create_plan_fact_items,
    # Read operations
    get_plan_fact_item,
    get_plan_fact_items_for_deal,
    get_plan_fact_items_by_category,
    get_unpaid_items_for_deal,
    get_paid_items_for_deal,
    get_overdue_items_for_deal,
    count_items_for_deal,
    # Update operations
    update_plan_fact_item,
    record_actual_payment,
    clear_actual_payment,
    update_planned_payment,
    # Delete operations
    delete_plan_fact_item,
    delete_all_items_for_deal,
    # Summary and statistics
    get_deal_plan_fact_summary,
    get_items_grouped_by_category,
    get_upcoming_payments,
    get_payments_for_period,
    # Validation
    validate_item_for_payment,
    validate_deal_plan_fact,
    # Auto-generation functions (Feature #82)
    generate_plan_fact_from_deal,
    regenerate_plan_fact_for_deal,
    get_plan_fact_generation_preview,
)
from .idn_service import (
    # Data classes (Feature #IDN-001, #IDN-002)
    ParsedQuoteIDN,
    ParsedItemIDN,
    IDNGenerationResult,
    # Parsing functions
    parse_quote_idn,
    parse_item_idn,
    # Validation functions
    is_valid_quote_idn,
    is_valid_item_idn,
    validate_seller_code,
    validate_inn,
    # Quote IDN generation (Feature #IDN-001)
    generate_quote_idn,
    assign_idn_to_quote,
    get_quote_idn,
    get_quote_by_idn,
    # Item IDN generation (Feature #IDN-002)
    generate_item_idn,
    regenerate_item_idns_for_quote,
    get_item_idn,
    get_item_by_idn,
    # Utility functions
    extract_quote_idn_from_item_idn,
    format_item_position,
    get_year_from_idn,
    get_customer_inn_from_idn,
    get_seller_code_from_idn,
    get_next_expected_sequence,
)
from .supplier_service import (
    # Data class (Feature #API-001)
    Supplier,
    # Validation functions
    validate_supplier_code,
    validate_inn as validate_supplier_inn,
    validate_kpp,
    # Create operations
    create_supplier,
    # Read operations
    get_supplier,
    get_supplier_by_code,
    get_all_suppliers,
    get_suppliers_by_country,
    count_suppliers,
    search_suppliers,
    get_active_suppliers,
    supplier_exists,
    # Update operations
    update_supplier,
    activate_supplier,
    deactivate_supplier,
    # Delete operations
    delete_supplier,
    # Utility functions
    get_unique_countries,
    get_supplier_stats,
    get_supplier_display_name,
    format_supplier_for_dropdown,
    get_suppliers_for_dropdown,
)
from .telegram_service import (
    # Configuration
    is_bot_configured,
    get_bot,
    # Notification types
    NotificationType,
    NotificationPayload,
    # Message functions
    format_notification,
    send_message,
    send_notification,
    send_approval_request,
    edit_message,
    # Keyboard builders
    build_approval_keyboard,
    build_open_quote_keyboard,
    # Webhook management
    setup_webhook,
    delete_webhook,
    get_webhook_info,
    # Bot info
    get_bot_info,
    # Callback data
    CallbackData,
    parse_callback_data,
    # Webhook processing (Feature #53)
    WebhookResult,
    parse_telegram_update,
    process_webhook_update,
    respond_to_command,
    # Account verification (Feature #55)
    VerificationResult,
    verify_telegram_account,
    get_telegram_user,
    is_telegram_linked,
    # Verification code UI (Feature #56)
    TelegramStatus,
    get_user_telegram_status,
    request_verification_code,
    unlink_telegram_account,
    # Status command (Feature #57)
    UserTask,
    get_user_tasks,
    handle_status_command,
    # Task assigned notification (Feature #58)
    TaskAssignedNotification,
    get_user_telegram_id,
    record_notification,
    send_task_assigned_notification,
    notify_users_of_task_assignment,
    notify_role_users_of_task,
    # Approval required notification (Feature #59)
    ApprovalRequiredNotification,
    send_approval_required_notification,
    send_approval_notification_for_quote,
    # Approve callback handler (Feature #60)
    ApprovalCallbackResult,
    handle_approve_callback,
    send_callback_response,
    # Reject callback handler (Feature #61)
    handle_reject_callback,
    # Status changed notification (Feature #62)
    StatusChangedNotification,
    send_status_changed_notification,
    notify_quote_creator_of_status_change,
    notify_assigned_users_of_status_change,
    # Returned for revision notification (Feature #63)
    ReturnedForRevisionNotification,
    send_returned_for_revision_notification,
    notify_creator_of_return,
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
    "get_procurement_manager",
    "get_assigned_brands",
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
    # Telegram bot (Feature #52)
    "is_bot_configured",
    "get_bot",
    "NotificationType",
    "NotificationPayload",
    "format_notification",
    "send_message",
    "send_notification",
    "send_approval_request",
    "edit_message",
    "build_approval_keyboard",
    "build_open_quote_keyboard",
    "setup_webhook",
    "delete_webhook",
    "get_webhook_info",
    "get_bot_info",
    "CallbackData",
    "parse_callback_data",
    # Webhook processing (Feature #53)
    "WebhookResult",
    "parse_telegram_update",
    "process_webhook_update",
    "respond_to_command",
    # Account verification (Feature #55)
    "VerificationResult",
    "verify_telegram_account",
    "get_telegram_user",
    "is_telegram_linked",
    # Verification code UI (Feature #56)
    "TelegramStatus",
    "get_user_telegram_status",
    "request_verification_code",
    "unlink_telegram_account",
    # Status command (Feature #57)
    "UserTask",
    "get_user_tasks",
    "handle_status_command",
    # Task assigned notification (Feature #58)
    "TaskAssignedNotification",
    "get_user_telegram_id",
    "record_notification",
    "send_task_assigned_notification",
    "notify_users_of_task_assignment",
    "notify_role_users_of_task",
    # Approval required notification (Feature #59)
    "ApprovalRequiredNotification",
    "send_approval_required_notification",
    "send_approval_notification_for_quote",
    # Approve callback handler (Feature #60)
    "ApprovalCallbackResult",
    "handle_approve_callback",
    "send_callback_response",
    # Reject callback handler (Feature #61)
    "handle_reject_callback",
    # Status changed notification (Feature #62)
    "StatusChangedNotification",
    "send_status_changed_notification",
    "notify_quote_creator_of_status_change",
    "notify_assigned_users_of_status_change",
    # Returned for revision notification (Feature #63)
    "ReturnedForRevisionNotification",
    "send_returned_for_revision_notification",
    "notify_creator_of_return",
    # Approval service (Feature #64)
    "Approval",
    "create_approval",
    "create_approvals_for_role",
    "get_approval",
    "get_approval_by_quote",
    "get_approvals_for_quote",
    "get_pending_approval_for_quote",
    "get_pending_approvals_for_user",
    "get_approvals_requested_by",
    "get_approvals_with_details",
    "count_pending_approvals",
    "update_approval_status",
    "approve_quote_approval",
    "reject_quote_approval",
    "cancel_pending_approvals_for_quote",
    "has_pending_approval",
    "get_latest_approval_decision",
    "get_approval_stats_for_user",
    # High-level workflow functions (Feature #65, #66)
    "ApprovalRequestResult",
    "request_approval",
    "ApprovalDecisionResult",
    "process_approval_decision",
    # Specification service (Feature #73)
    "Specification",
    "SPEC_STATUSES",
    "SPEC_STATUS_NAMES",
    "SPEC_STATUS_COLORS",
    "SPEC_TRANSITIONS",
    "get_spec_status_name",
    "get_spec_status_color",
    "can_transition_spec",
    "get_allowed_spec_transitions",
    "create_specification",
    "get_specification",
    "get_specification_by_quote",
    "get_specifications_by_status",
    "get_all_specifications",
    "get_specifications_with_details",
    "count_specifications_by_status",
    "specification_exists_for_quote",
    "update_specification",
    "update_specification_status",
    "set_signed_scan_url",
    "delete_specification",
    "generate_specification_number",
    "get_specification_stats",
    "get_specifications_for_signing",
    "get_recently_signed_specifications",
    # Create from quote (Feature #74)
    "CreateSpecFromQuoteResult",
    "create_specification_from_quote",
    # Deal service (Feature #75)
    "Deal",
    "DEAL_STATUSES",
    "DEAL_STATUS_NAMES",
    "DEAL_STATUS_COLORS",
    "DEAL_TRANSITIONS",
    "get_deal_status_name",
    "get_deal_status_color",
    "can_transition_deal",
    "get_allowed_deal_transitions",
    "is_deal_terminal",
    "create_deal",
    "get_deal",
    "get_deal_by_specification",
    "get_deal_by_quote",
    "get_deals_by_status",
    "get_all_deals",
    "get_deals_with_details",
    "count_deals_by_status",
    "deal_exists_for_specification",
    "deal_exists_for_quote",
    "update_deal",
    "update_deal_status",
    "complete_deal",
    "cancel_deal",
    "update_deal_amount",
    "delete_deal",
    "generate_deal_number",
    "get_deal_stats",
    "get_active_deals",
    "get_recent_deals",
    "get_deals_by_date_range",
    "search_deals",
    # Create deal from spec (Feature #76)
    "CreateDealFromSpecResult",
    "create_deal_from_specification",
    # Plan-fact service (Feature #81)
    "PlanFactCategory",
    "PlanFactItem",
    # Category functions
    "get_all_categories",
    "get_category",
    "get_category_by_code",
    "get_income_categories",
    "get_expense_categories",
    # Plan-fact create operations
    "create_plan_fact_item",
    "create_plan_fact_item_with_category_code",
    "bulk_create_plan_fact_items",
    # Plan-fact read operations
    "get_plan_fact_item",
    "get_plan_fact_items_for_deal",
    "get_plan_fact_items_by_category",
    "get_unpaid_items_for_deal",
    "get_paid_items_for_deal",
    "get_overdue_items_for_deal",
    "count_items_for_deal",
    # Plan-fact update operations
    "update_plan_fact_item",
    "record_actual_payment",
    "clear_actual_payment",
    "update_planned_payment",
    # Plan-fact delete operations
    "delete_plan_fact_item",
    "delete_all_items_for_deal",
    # Plan-fact summary and statistics
    "get_deal_plan_fact_summary",
    "get_items_grouped_by_category",
    "get_upcoming_payments",
    "get_payments_for_period",
    # Plan-fact validation
    "validate_item_for_payment",
    "validate_deal_plan_fact",
    # Auto-generation functions (Feature #82)
    "GeneratePlanFactResult",
    "generate_plan_fact_from_deal",
    "regenerate_plan_fact_for_deal",
    "get_plan_fact_generation_preview",
    # IDN service (Feature #IDN-001, #IDN-002)
    "ParsedQuoteIDN",
    "ParsedItemIDN",
    "IDNGenerationResult",
    "parse_quote_idn",
    "parse_item_idn",
    "is_valid_quote_idn",
    "is_valid_item_idn",
    "validate_seller_code",
    "validate_inn",
    "generate_quote_idn",
    "assign_idn_to_quote",
    "get_quote_idn",
    "get_quote_by_idn",
    "generate_item_idn",
    "regenerate_item_idns_for_quote",
    "get_item_idn",
    "get_item_by_idn",
    "extract_quote_idn_from_item_idn",
    "format_item_position",
    "get_year_from_idn",
    "get_customer_inn_from_idn",
    "get_seller_code_from_idn",
    "get_next_expected_sequence",
    # Supplier service (Feature #API-001)
    "Supplier",
    "validate_supplier_code",
    "validate_supplier_inn",
    "validate_kpp",
    "create_supplier",
    "get_supplier",
    "get_supplier_by_code",
    "get_all_suppliers",
    "get_suppliers_by_country",
    "count_suppliers",
    "search_suppliers",
    "get_active_suppliers",
    "supplier_exists",
    "update_supplier",
    "activate_supplier",
    "deactivate_supplier",
    "delete_supplier",
    "get_unique_countries",
    "get_supplier_stats",
    "get_supplier_display_name",
    "format_supplier_for_dropdown",
    "get_suppliers_for_dropdown",
]
