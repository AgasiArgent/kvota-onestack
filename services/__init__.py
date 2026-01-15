"""
OneStack Services

Export and versioning services for quote management.
Role management services for workflow system.
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
]
