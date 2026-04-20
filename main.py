"""
Kvota OneStack - FastHTML + Supabase

A single-language (Python) quotation platform.
Run with: python main.py
"""

from fasthtml.common import *
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, cast
import os
import json
import html as html_mod
from starlette.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# Initialize Sentry for error tracking (must be before app creation)
import sentry_sdk

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=1.0,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production" if not os.getenv("DEBUG") else "development"),
    )

from services.database import get_supabase, get_anon_client

# Import export services
from services.export_data_mapper import fetch_export_data, format_date_russian
from services.specification_export import generate_specification_pdf, generate_spec_pdf_from_spec_id
from services.invoice_export import generate_invoice_pdf
from services.export_validation_service import create_validation_excel
from services.procurement_export import create_procurement_excel

# Import version service
from services.quote_version_service import (
    create_quote_version, list_quote_versions, get_quote_version,
    get_current_quote_version, can_update_version, update_quote_version
)

# Import role service
from services.role_service import get_user_role_codes, get_session_user_roles, require_role, require_any_role

# Import brand service for procurement
from services.brand_service import get_assigned_brands

# Import workflow service for status display
from services.workflow_service import (
    WorkflowStatus, STATUS_NAMES, STATUS_NAMES_SHORT, STATUS_COLORS,
    check_all_procurement_complete, complete_procurement,
    transition_quote_status, get_quote_transition_history, transition_to_pending_procurement,
    show_validation_excel, show_quote_pdf, show_invoice_and_spec
)

# Import approval service (Feature #65, #86)
from services.approval_service import count_pending_approvals

# Import composition service (Phase 5b — multi-supplier quote composition adapter).
# Replaces the three quote_items reads that feed build_calculation_inputs() with
# a single helper that overlays prices from invoice_item_prices when a
# composition pointer is set on the item. Falls back to legacy quote_items
# values when no composition exists, so pre-Phase-5b quotes compute identically.
from services.composition_service import get_composed_items, is_procurement_complete

from services.logistics_service import (
    get_stages_for_deal, get_stage_summary, stage_allows_expenses,
    STAGE_NAMES,
)
from services.plan_fact_service import get_categories_for_role

# Import quote approval service (Bug #8 follow-up - Multi-department approval)
from services.quote_approval_service import (
    get_approval_status as get_quote_approval_status,
    approve_department as approve_quote_department,
    reject_department as reject_quote_department,
    user_can_approve_department as user_can_approve_quote_department,
    DEPARTMENT_NAMES as QUOTE_DEPARTMENT_NAMES,
    DEPARTMENTS as QUOTE_DEPARTMENTS
)

# Import calculation engine
from calculation_engine import calculate_multiproduct_quote
from calculation_mapper import map_variables_to_calculation_input, safe_decimal, safe_int
from calculation_models import (
    QuoteCalculationInput, Currency, SupplierCountry, SellerCompany,
    OfferSaleType, Incoterms, DMFeeType
)

# Import currency service for multi-currency logistics
from services.currency_service import convert_to_usd

# Import CBR rates service for exchange rates on Svodka tab
from services.cbr_rates_service import get_usd_rub_rate

# Import document service for file uploads
from services.document_service import (
    upload_document, get_document, get_documents_for_entity,
    get_download_url, delete_document, update_document,
    get_document_type_label, get_file_icon, format_file_size,
    get_allowed_document_types_for_entity, count_documents_for_entity,
    get_all_documents_for_quote, count_all_documents_for_quote,
    get_required_sub_entity_type, get_entity_type_label,
    DOCUMENT_TYPE_LABELS, INVOICE_DOCUMENT_TYPES, ITEM_DOCUMENT_TYPES
)

# ============================================================================
# SHARED ROLE LABELS (used by impersonation banner, sidebar, activity log)
# ============================================================================

ROLE_LABELS_RU = {
    "sales": "Продажи", "sales_manager": "Менеджер", "procurement": "Закупки",
    "logistics": "Логистика", "customs": "Таможня", "admin": "Админ",
    "quote_controller": "Контроль КП", "spec_controller": "Контроль спецификаций",
    "top_manager": "Руководитель", "finance": "Финансы", "system": "Система",
    "head_of_sales": "Нач. продаж", "head_of_procurement": "Нач. закупок",
    "head_of_logistics": "Нач. логистики",
    "training_manager": "Менеджер обучения",
    "currency_controller": "Контроль валютных инвойсов",
}

# ============================================================================
# APP SETUP
# ============================================================================

app, rt = fast_app(
    secret_key=os.getenv("APP_SECRET", "dev-secret-change-in-production"),
    live=True,
)

# JWT auth middleware for /api/* endpoints (Next.js frontend)
from api.auth import ApiAuthMiddleware
app.add_middleware(ApiAuthMiddleware)

# NOTE: FastAPI sub-app for /api/* is mounted at the bottom of this file,
# AFTER all legacy @rt("/api/...") handlers are registered. Starlette routes
# in declaration order, so specific @rt routes resolve first and unmatched
# /api/* paths fall through to the mount. Moving the mount above @rt blocks
# every legacy endpoint (Mount takes full ownership of its prefix).

# ============================================================================
# STYLES
# ============================================================================

# Modern, attractive styles with smooth animations and depth
# Built on top of PicoCSS + DaisyUI + Tailwind for maximum visual appeal
# Supports light (default) and dark themes via CSS variables
APP_STYLES = """
/* ========== Theme Variables ========== */
/* Light theme (default) - inspired by Behance CRM reference */
:root {
    /* Page background */
    --bg-page: #f5f7fa;
    --bg-page-alt: #eef1f5;

    /* Sidebar/Nav */
    --bg-sidebar: #ffffff;
    --bg-sidebar-hover: #f1f5f9;
    --bg-sidebar-active: rgba(59, 130, 246, 0.1);
    --sidebar-border: #e5e7eb;
    --sidebar-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);

    /* Cards */
    --bg-card: #ffffff;
    --bg-card-hover: #ffffff;
    --card-border: #e2e8f0;
    --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    --card-shadow-hover: 0 12px 24px rgba(59, 130, 246, 0.12);

    /* Text colors (slate palette) */
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
    --text-on-accent: #ffffff;

    /* Accent colors */
    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --accent-light: rgba(59, 130, 246, 0.1);
    --accent-gradient: #3b82f6;

    /* Borders (slate palette) */
    --border-color: #e2e8f0;
    --border-color-light: #f1f5f9;

    /* Status colors */
    --status-success: #10b981;
    --status-warning: #f59e0b;
    --status-error: #ef4444;
    --status-info: #3b82f6;

    /* Table */
    --table-header-bg: #f8fafc;
    --table-row-hover: rgba(59, 130, 246, 0.06);
    --table-stripe: rgba(59, 130, 246, 0.02);

    /* Forms */
    --input-bg: #ffffff;
    --input-border: #e2e8f0;
    --input-focus-border: #3b82f6;
    --input-focus-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

    /* ========== Button System Variables ========== */
    /* Primary (blue - main action) */
    --btn-primary-bg: #3b82f6;
    --btn-primary-hover: #2563eb;
    --btn-primary-text: white;

    /* Secondary (white + gray border) */
    --btn-secondary-bg: white;
    --btn-secondary-border: #d1d5db;
    --btn-secondary-text: #374151;
    --btn-secondary-hover-bg: #f9fafb;

    /* Success (outline: white + green border, green fill on hover) */
    --btn-success-bg: white;
    --btn-success-border: #10b981;
    --btn-success-text: #059669;
    --btn-success-hover-bg: #10b981;
    --btn-success-hover-text: white;

    /* Danger (outline: white + red border, red fill on hover) */
    --btn-danger-bg: white;
    --btn-danger-border: #ef4444;
    --btn-danger-text: #dc2626;
    --btn-danger-hover-bg: #ef4444;
    --btn-danger-hover-text: white;

    /* Ghost (transparent background) */
    --btn-ghost-bg: transparent;
    --btn-ghost-text: #374151;
    --btn-ghost-hover-bg: #f3f4f6;

    /* Button sizing */
    --btn-padding: 0.625rem 1.25rem;
    --btn-padding-sm: 0.4rem 0.875rem;
    --btn-padding-lg: 0.875rem 1.75rem;
    --btn-radius: 0.5rem;
    --btn-gap: 0.5rem;
    --btn-font-size: 0.875rem;
    --btn-font-size-sm: 0.8125rem;
    --btn-font-size-lg: 1rem;

    /* ========== Compact Spacing (logistics-style) ========== */
    --spacing-tight: 8px;
    --spacing-compact: 12px;
    --spacing-normal: 16px;

    /* Compact Label Typography */
    --label-size: 11px;
    --label-weight: 600;
    --label-color: #94a3b8;
    --label-transform: uppercase;
    --label-spacing: 0.05em;

    /* Compact Inputs */
    --input-height-compact: 36px;
    --input-padding-compact: 8px 10px;
    --input-bg-compact: #f8fafc;
    --input-border-compact: #e2e8f0;

    /* Elevated Card Backgrounds */
    --bg-card-elevated: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
    --bg-card-success: linear-gradient(90deg, #f0fdf4 0%, #fafbfc 100%);

    /* Badge Colors (flat) */
    --badge-pending: #fef3c7;
    --badge-active: #d1fae5;
    --badge-complete: #dbeafe;
    --badge-purple: #ede9fe;
    --badge-neutral: #f3f4f6;
    --badge-error: #fee2e2;

    /* Subtle Shadows */
    --shadow-subtle: 0 1px 4px rgba(0,0,0,0.06);
    --shadow-card-v2: 0 2px 8px rgba(0,0,0,0.04);

    /* Transition */
    --transition-smooth: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

/* Dark theme */
[data-theme="dark"] {
    /* Page background */
    --bg-page: #0f0f1a;
    --bg-page-alt: #1a1a2e;

    /* Sidebar/Nav */
    --bg-sidebar: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    --bg-sidebar-hover: rgba(255, 255, 255, 0.1);
    --bg-sidebar-active: rgba(99, 102, 241, 0.15);
    --sidebar-border: rgba(255, 255, 255, 0.1);
    --sidebar-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);

    /* Cards */
    --bg-card: linear-gradient(135deg, #2d2d44 0%, #1e1e2f 100%);
    --bg-card-hover: linear-gradient(135deg, #353550 0%, #262638 100%);
    --card-border: rgba(255, 255, 255, 0.05);
    --card-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
    --card-shadow-hover: 0 20px 40px rgba(99, 102, 241, 0.3);

    /* Text colors */
    --text-primary: #ffffff;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --text-on-accent: #ffffff;

    /* Accent colors */
    --accent: #6366f1;
    --accent-hover: #4f46e5;
    --accent-light: rgba(99, 102, 241, 0.15);
    --accent-gradient: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);

    /* Borders */
    --border-color: rgba(255, 255, 255, 0.1);
    --border-color-light: rgba(255, 255, 255, 0.05);

    /* Status colors (same) */
    --status-success: #10b981;
    --status-warning: #f59e0b;
    --status-error: #ef4444;
    --status-info: #3b82f6;

    /* Table */
    --table-header-bg: rgba(99, 102, 241, 0.1);
    --table-row-hover: rgba(99, 102, 241, 0.12);
    --table-stripe: rgba(99, 102, 241, 0.03);

    /* Forms */
    --input-bg: #1e1e2f;
    --input-border: rgba(255, 255, 255, 0.15);
    --input-focus-border: #6366f1;
    --input-focus-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);

    /* ========== Button System Variables (Dark Theme) ========== */
    /* Primary (blue - main action) */
    --btn-primary-bg: #3b82f6;
    --btn-primary-hover: #60a5fa;
    --btn-primary-text: white;

    /* Secondary (dark + lighter border) */
    --btn-secondary-bg: #2d2d44;
    --btn-secondary-border: rgba(255, 255, 255, 0.15);
    --btn-secondary-text: #e5e7eb;
    --btn-secondary-hover-bg: #3d3d5c;

    /* Success (outline: dark + green border, green fill on hover) */
    --btn-success-bg: #2d2d44;
    --btn-success-border: #10b981;
    --btn-success-text: #34d399;
    --btn-success-hover-bg: #10b981;
    --btn-success-hover-text: white;

    /* Danger (outline: dark + red border, red fill on hover) */
    --btn-danger-bg: #2d2d44;
    --btn-danger-border: #ef4444;
    --btn-danger-text: #f87171;
    --btn-danger-hover-bg: #ef4444;
    --btn-danger-hover-text: white;

    /* Ghost (transparent background) */
    --btn-ghost-bg: transparent;
    --btn-ghost-text: #e5e7eb;
    --btn-ghost-hover-bg: rgba(255, 255, 255, 0.1);

    /* ========== Compact Spacing (Dark Theme) ========== */
    --label-color: #94a3b8;
    --input-bg-compact: #1e1e2f;
    --input-border-compact: rgba(255, 255, 255, 0.15);
    --bg-card-elevated: linear-gradient(135deg, #2d2d44 0%, #252538 100%);
    --bg-card-success: linear-gradient(90deg, rgba(22, 163, 74, 0.15) 0%, #2d2d44 100%);

    /* Badge Colors (Dark Theme, flat) */
    --badge-pending: rgba(217, 119, 6, 0.2);
    --badge-active: rgba(22, 163, 74, 0.2);
    --badge-complete: rgba(37, 99, 235, 0.2);
    --badge-purple: rgba(124, 58, 237, 0.2);
    --badge-neutral: rgba(107, 114, 128, 0.2);
    --badge-error: rgba(220, 38, 38, 0.2);
}

/* ========== Global Enhancements ========== */
/* Opt-in transitions only (no global * transition — performance) */
.transition-colors { transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease; }
.transition-opacity { transition: opacity 0.15s ease; }
.transition-shadow { transition: box-shadow 0.15s ease; }

html, body, h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

body {
    line-height: 1.6;
    background: var(--bg-page);
    color: var(--text-primary);
    font-size: 14px;
}

h1 {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 1.5rem;
    color: var(--text-primary);
    letter-spacing: -0.02em;
}

h2 {
    font-size: 1.5rem;
    font-weight: 600;
    line-height: 1.3;
    margin-bottom: 1rem;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}

h3 {
    font-size: 1.125rem;
    font-weight: 600;
    line-height: 1.4;
    margin-bottom: 0.75rem;
    color: var(--text-primary);
}

/* ========== Unified Header System ========== */
/*
 * 3-level hierarchy:
 * 1. .page-header (H1) - Page title with icon
 * 2. .section-header (H2) - Section on page
 * 3. .card-header (H3) - Card/form header
 */

/* Page Header - Main page title */
.page-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid var(--border-color-light);
}

.page-header svg {
    flex-shrink: 0;
    color: var(--accent);
}

/* Section Header - Major section on page */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 2rem 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color-light);
}

.section-header svg {
    flex-shrink: 0;
    color: var(--text-secondary);
}

/* Card Header - Inside cards/forms */
.card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color-light);
}

.card-header svg {
    flex-shrink: 0;
    color: var(--text-muted);
}

/* Card Header with accent color (for dashboard task cards) */
.card-header--accent {
    font-size: 1.125rem;
    font-weight: 600;
    padding: 0;
    margin-bottom: 1rem;
    border-bottom: none;
}

.card-header--accent svg {
    width: 24px;
    height: 24px;
}

/* Accent color variants */
.card-header--orange { color: #b45309; }
.card-header--orange svg { color: #b45309; }

.card-header--amber { color: #92400e; }
.card-header--amber svg { color: #92400e; }

.card-header--blue { color: #1e40af; }
.card-header--blue svg { color: #1e40af; }

.card-header--purple { color: #6b21a8; }
.card-header--purple svg { color: #6b21a8; }

.card-header--pink { color: #9d174d; }
.card-header--pink svg { color: #9d174d; }

.card-header--indigo { color: #4338ca; }
.card-header--indigo svg { color: #4338ca; }

.card-header--green { color: #059669; }
.card-header--green svg { color: #059669; }

.card-header--red { color: #9a3412; }
.card-header--red svg { color: #9a3412; }

/* Subsection header - smaller, no border */
.subsection-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 1.5rem 0 0.75rem 0;
}

.subsection-header svg {
    flex-shrink: 0;
    color: var(--text-muted);
}

/* ========== Navigation Bar ========== */
nav {
    background: var(--bg-sidebar);
    color: var(--text-primary);
    padding: 1rem 0;
    margin-bottom: 0;
    box-shadow: var(--sidebar-shadow);
    overflow-x: auto;
}

nav .nav-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
}

nav ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
}

nav a {
    color: var(--text-secondary);
    text-decoration: none;
    padding: 0.5rem 0.75rem;
    border-radius: 0.375rem;
    white-space: nowrap;
    font-size: 0.9375rem;
}

nav a:hover {
    color: var(--accent);
    background: var(--accent-light);
}

nav strong {
    color: var(--text-primary);
    font-size: 1.1rem;
    font-weight: 700;
}

/* ========== Cards with Hover Effects ========== */
.card,
[style*="border-left"],
.stat-card,
div[style*="max-width"][style*="margin"] {
    background: var(--bg-card) !important;
    border-radius: 0.75rem !important;
    box-shadow: var(--card-shadow) !important;
    padding: 1.5rem !important;
    border: 1px solid var(--card-border) !important;
}

/* Cards are static containers — no hover lift or border glow */

/* ========== Enhanced Buttons ========== */
button, [role="button"], .button, a[role="button"] {
    padding: 0.625rem 1.25rem;
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.875rem;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
    border: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    text-decoration: none;
}

/* Primary button (default) - Override ALL button colors including Pico CSS */
/* IMPORTANT: Exclude .btn class elements - they use BEM system */
button:not(.secondary):not(.ghost):not(.sidebar-toggle-btn):not(.theme-toggle):not(.btn),
[role="button"]:not(.secondary):not(.ghost):not(.btn),
button[type="submit"]:not(.btn),
a[href*="/new"]:not(.sidebar-item):not(.btn) {
    background: var(--accent) !important;
    color: var(--text-on-accent) !important;
    box-shadow: 0 1px 3px rgba(59, 130, 246, 0.2) !important;
    border-color: transparent !important;
}

button:not(.secondary):not(.ghost):not(.sidebar-toggle-btn):not(.theme-toggle):not(.btn):hover,
[role="button"]:not(.secondary):not(.ghost):not(.btn):hover,
button[type="submit"]:not(.btn):hover,
a[href*="/new"]:not(.sidebar-item):not(.btn):hover {
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25) !important;
    background: var(--accent-hover) !important;
}

/* Secondary button (legacy - exclude .btn) */
button.secondary:not(.btn),
[role="button"].secondary:not(.btn),
.button.secondary:not(.btn) {
    background: var(--bg-card);
    color: var(--accent);
    border: 1.5px solid var(--accent);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

button.secondary:not(.btn):hover,
[role="button"].secondary:not(.btn):hover,
.button.secondary:not(.btn):hover {
    background: var(--accent-light);
}

/* Ghost button (legacy - exclude .btn) */
button.ghost:not(.btn),
[role="button"].ghost:not(.btn),
.button.ghost:not(.btn) {
    background: transparent;
    color: var(--accent);
    border: none;
}

button.ghost:not(.btn):hover,
[role="button"].ghost:not(.btn):hover,
.button.ghost:not(.btn):hover {
    background: var(--accent-light);
}

/* Success button (legacy - exclude .btn) */
button.success:not(.btn),
[role="button"].success:not(.btn) {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25);
}

button.success:not(.btn):hover,
[role="button"].success:not(.btn):hover {
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25);
}

/* Danger button (legacy - exclude .btn) */
button.danger:not(.btn),
[role="button"].danger:not(.btn) {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.25);
}

button.danger:not(.btn):hover,
[role="button"].danger:not(.btn):hover {
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.25);
}

/* Disabled state */
button:disabled,
[role="button"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
}

/* Small button variant (legacy - exclude .btn) */
button.btn-sm:not(.btn),
[role="button"].btn-sm:not(.btn) {
    padding: 0.4rem 0.875rem;
    font-size: 0.875rem;
}

/* ========== BEM Button System ========== */
/*
 * Standardized button classes using BEM methodology.
 * Use Python helpers: btn(), btn_link(), btn_icon()
 *
 * Variants:
 *   .btn--primary   - Gray fill, main actions (Передать, Сохранить)
 *   .btn--secondary - White + gray border, secondary actions
 *   .btn--success   - White + green border, confirmations (Одобрить)
 *   .btn--danger    - White + red border, destructive (Удалить, Отклонить)
 *   .btn--ghost     - Transparent, toolbar buttons (Добавить, Загрузить)
 *
 * Modifiers:
 *   .btn--sm        - Small size
 *   .btn--lg        - Large size
 *   .btn--full      - Full width
 *   .btn--icon-only - Square button for icons only
 */

/* Base button reset - highest specificity with .btn class */
/* Note: width: auto !important overrides PicoCSS full-width form buttons */
.btn {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    gap: var(--btn-gap);
    padding: var(--btn-padding);
    border-radius: var(--btn-radius);
    font-size: var(--btn-font-size);
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    border: 1px solid transparent;
    text-decoration: none;
    background: none;
    box-shadow: none;
    width: auto !important;
}

/* Primary - Gray fill (main actions) */
.btn.btn--primary {
    background: var(--btn-primary-bg);
    color: var(--btn-primary-text);
    border-color: var(--btn-primary-bg);
}

.btn.btn--primary:hover {
    background: var(--btn-primary-hover);
    border-color: var(--btn-primary-hover);
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
}

/* Secondary - White/gray outline */
.btn.btn--secondary {
    background: var(--btn-secondary-bg);
    color: var(--btn-secondary-text);
    border-color: var(--btn-secondary-border);
}

.btn.btn--secondary:hover {
    background: var(--btn-secondary-hover-bg);
    border-color: var(--btn-secondary-text);
}

/* Success - White + green border, green fill on hover */
.btn.btn--success {
    background: var(--btn-success-bg);
    color: var(--btn-success-text);
    border-color: var(--btn-success-border);
}

.btn.btn--success:hover {
    background: var(--btn-success-hover-bg);
    color: var(--btn-success-hover-text);
    border-color: var(--btn-success-hover-bg);
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25);
}

/* Danger - White + red border, red fill on hover */
.btn.btn--danger {
    background: var(--btn-danger-bg);
    color: var(--btn-danger-text);
    border-color: var(--btn-danger-border);
}

.btn.btn--danger:hover {
    background: var(--btn-danger-hover-bg);
    color: var(--btn-danger-hover-text);
    border-color: var(--btn-danger-hover-bg);
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.25);
}

/* Ghost - Transparent, for toolbar actions */
.btn.btn--ghost {
    background: var(--btn-ghost-bg);
    color: var(--btn-ghost-text);
    border-color: transparent;
}

.btn.btn--ghost:hover {
    background: var(--btn-ghost-hover-bg);
}

/* Size modifiers */
.btn.btn--sm {
    padding: var(--btn-padding-sm);
    font-size: var(--btn-font-size-sm);
}

.btn.btn--lg {
    padding: var(--btn-padding-lg);
    font-size: var(--btn-font-size-lg);
}

/* Full width */
.btn.btn--full {
    width: 100%;
}

/* Icon only (square) */
.btn.btn--icon-only {
    padding: 0.5rem;
    width: 2.25rem;
    height: 2.25rem;
}

.btn.btn--icon-only.btn--sm {
    padding: 0.375rem;
    width: 1.75rem;
    height: 1.75rem;
}

/* Disabled state */
.btn:disabled,
.btn[disabled],
.btn.btn--disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
    transform: none;
}

/* Focus state for accessibility */
.btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}

/* Loading state */
.btn.btn--loading {
    position: relative;
    color: transparent;
    pointer-events: none;
}

.btn.btn--loading::after {
    content: '';
    position: absolute;
    width: 1rem;
    height: 1rem;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: btn-spin 0.6s linear infinite;
}

@keyframes btn-spin {
    to { transform: rotate(360deg); }
}

/* ========== Status Colors — flat backgrounds, dark text ========== */
.status-draft {
    background: #fef3c7;
    color: #92400e;
}

.status-sent {
    background: #dbeafe;
    color: #1e40af;
}

.status-approved {
    background: #d1fae5;
    color: #065f46;
}

.status-rejected {
    background: #fee2e2;
    color: #991b1b;
}

.status-pending {
    background: #fef3c7;
    color: #92400e;
}

.status-progress {
    background: #cffafe;
    color: #155e75;
}

.status-cancelled {
    background: #f3f4f6;
    color: #4b5563;
}

/* ========== Enhanced Stats Cards ========== */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.25rem;
    margin-bottom: 2rem;
}

.stat-card {
    text-align: center;
    padding: 1.5rem;
    background: var(--bg-card) !important;
    border-radius: 12px;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--card-border);
}

/* stat-card hover: subtle bg only, no lift */

.stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    line-height: 1.2;
}

.stat-label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin-top: 0.5rem;
}

/* ========== Tables with Zebra Stripes & Hover ========== */
table {
    border-collapse: collapse;
    width: 100%;
    border-radius: 0.5rem;
    overflow: hidden;
    box-shadow: var(--card-shadow);
    background: var(--bg-card);
}

table tbody tr {
    transition: background-color 0.15s ease;
}

/* Zebra striping - alternating row colors */
table tbody tr:nth-child(even) {
    background: var(--table-stripe);
}

table tbody tr:hover {
    background: var(--table-row-hover) !important;
    cursor: pointer;
}

/* Table headers */
table thead {
    background: var(--table-header-bg);
}

table thead th {
    font-weight: 700;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.075em;
    padding: 1rem 0.75rem;
    border-bottom: 2px solid var(--border-color);
    color: var(--accent);
    text-align: left;
}

/* Table cells */
table tbody td {
    padding: 0.875rem 0.75rem;
    border-bottom: 1px solid var(--border-color-light);
    font-size: 0.9375rem;
    color: var(--text-primary);
}

/* First and last columns padding */
table thead th:first-child,
table tbody td:first-child {
    padding-left: 1.25rem;
}

table thead th:last-child,
table tbody td:last-child {
    padding-right: 1.25rem;
}
/* ========== Unified Table Design System (Livento CRM Style) ========== */
/* Reference: https://www.behance.net/gallery/239045803/CRM-Dashboard-UI-UX-Branding-Case-Study */

/* Table Container - adds shadow and rounded corners */
.table-container {
    background: var(--bg-card);
    border-radius: 12px;
    border: 1px solid var(--border-color);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    margin: 1.5rem;  /* Fixed spacing from edges */
    margin-top: 1rem;
}

/* Table Header Bar - search, filters, actions */
.table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-card);
    gap: 1rem;
    flex-wrap: wrap;
}

.table-header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.table-header-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Search Input in Table Header */
.table-search {
    min-width: 250px;
    padding: 0.5rem 1rem !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 8px !important;
    font-size: 0.875rem;
    background: var(--bg-primary) !important;
    margin: 0 !important;
}

.table-search:focus {
    outline: none;
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
}

/* Unified Table Base Styles */
.unified-table {
    width: 100%;
    min-width: 800px;  /* Minimum width for readability, enables horizontal scroll */
    border-collapse: collapse;
    font-size: 0.875rem;
    box-shadow: none;
}

/* Unified Table Header */
.unified-table thead {
    background: #f8fafc;
    border-bottom: 1px solid var(--border-color);
}

[data-theme="dark"] .unified-table thead {
    background: rgba(255, 255, 255, 0.05);
}

.unified-table th {
    padding: 0.875rem 1rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    white-space: nowrap;
    border-bottom: none;
}

/* Right-align numeric columns */
.unified-table th.col-number,
.unified-table td.col-number,
.unified-table th.col-money,
.unified-table td.col-money {
    text-align: right;
}

/* Center-align action columns */
.unified-table th.col-actions,
.unified-table td.col-actions {
    text-align: center;
    width: 100px;
}

/* Unified Table Body */
.unified-table tbody tr {
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.15s;
}

.unified-table tbody tr:last-child {
    border-bottom: none;
}

.unified-table tbody tr:hover {
    background: #f8fafc;
}

[data-theme="dark"] .unified-table tbody tr:hover {
    background: rgba(255, 255, 255, 0.05);
}

.unified-table td {
    padding: 0.875rem 1rem;
    color: var(--text-primary);
    vertical-align: middle;
    border-bottom: none;
}

/* Compact table variant — smaller font for dense data */
.unified-table.compact-table td,
.unified-table.compact-table th {
    font-size: 13px;
    padding: 0.625rem 0.75rem;
}

/* Clickable row - global (works in all table types) */
tr.clickable-row {
    cursor: pointer;
}

tr.clickable-row:hover {
    background: rgba(59, 130, 246, 0.08) !important;
}

/* Status Badges - Unified Color Palette */
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.625rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    white-space: nowrap;
}

.status-success { background: #dcfce7; color: #166534; }
.status-warning { background: #fef3c7; color: #92400e; }
.status-error { background: #fee2e2; color: #991b1b; }
.status-info { background: #dbeafe; color: #1e40af; }
.status-neutral { background: #f3f4f6; color: #4b5563; }
.status-new { background: #eff6ff; color: #2563eb; }
.status-progress { background: #f3e8ff; color: #7c3aed; }

[data-theme="dark"] .status-success { background: rgba(22, 163, 74, 0.2); color: #86efac; }
[data-theme="dark"] .status-warning { background: rgba(217, 119, 6, 0.2); color: #fcd34d; }
[data-theme="dark"] .status-error { background: rgba(220, 38, 38, 0.2); color: #fca5a5; }
[data-theme="dark"] .status-info { background: rgba(37, 99, 235, 0.2); color: #93c5fd; }
[data-theme="dark"] .status-neutral { background: rgba(107, 114, 128, 0.2); color: #d1d5db; }
[data-theme="dark"] .status-new { background: rgba(37, 99, 235, 0.15); color: #93c5fd; }
[data-theme="dark"] .status-progress { background: rgba(124, 58, 237, 0.2); color: #c4b5fd; }

/* Table Footer - pagination */
.table-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.875rem 1.25rem;
    border-top: 1px solid var(--border-color);
    background: #f8fafc;
    font-size: 0.875rem;
}

[data-theme="dark"] .table-footer {
    background: rgba(255, 255, 255, 0.02);
}

.table-pagination {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.table-pagination button {
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-card);
    cursor: pointer;
    font-size: 0.875rem;
}

.table-pagination button:hover:not(:disabled) {
    background: #f3f4f6;
}

.table-pagination button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.table-pagination .current-page {
    padding: 0.375rem 0.75rem;
    background: var(--accent);
    color: white;
    border-radius: 6px;
    font-weight: 500;
}

/* Empty State */
.table-empty {
    padding: 3rem 1rem;
    text-align: center;
    color: var(--text-muted);
}

.table-empty-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
    opacity: 0.5;
}

.table-empty-text {
    font-size: 0.9375rem;
}

/* Action Buttons */
.table-action-btn {
    padding: 0.375rem;
    border: none;
    background: transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: background-color 0.15s ease, color 0.15s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.table-action-btn:hover {
    background: #f3f4f6;
    color: var(--text-primary);
}

[data-theme="dark"] .table-action-btn:hover {
    background: rgba(255, 255, 255, 0.1);
}

.table-action-btn.danger:hover {
    background: #fee2e2;
    color: #dc2626;
}

[data-theme="dark"] .table-action-btn.danger:hover {
    background: rgba(220, 38, 38, 0.2);
    color: #fca5a5;
}

/* Responsive Table Wrapper */
.table-responsive {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

@media (max-width: 768px) {
    .table-header {
        flex-direction: column;
        align-items: stretch;
    }

    .table-search {
        min-width: 100%;
    }

    .unified-table th,
    .unified-table td {
        padding: 0.625rem 0.75rem;
    }
}


/* ========== Forms with Enhanced Styling ========== */
.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.form-actions {
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
    justify-content: flex-start;
}

/* Labels */
label {
    font-weight: 500;
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
    display: block;
    color: var(--text-primary);
}

/* Input fields */
input[type="text"],
input[type="email"],
input[type="password"],
input[type="number"],
input[type="date"],
input[type="tel"],
select,
textarea {
    width: 100%;
    padding: 0.625rem 0.875rem;
    border: 1.5px solid var(--input-border);
    border-radius: 0.5rem;
    font-size: 0.9375rem;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
    background: var(--input-bg);
    color: var(--text-primary);
}

input[type="text"]:hover,
input[type="email"]:hover,
input[type="password"]:hover,
input[type="number"]:hover,
input[type="date"]:hover,
input[type="tel"]:hover,
select:hover,
textarea:hover {
    border-color: var(--accent);
}

input[type="text"]:focus,
input[type="email"]:focus,
input[type="password"]:focus,
input[type="number"]:focus,
input[type="date"]:focus,
input[type="tel"]:focus,
select:focus,
textarea:focus {
    outline: none;
    border-color: var(--input-focus-border);
    box-shadow: var(--input-focus-shadow);
}

/* Disabled state */
input:disabled,
select:disabled,
textarea:disabled {
    background: var(--bg-page-alt);
    cursor: not-allowed;
    opacity: 0.6;
}

/* Textarea specific */
textarea {
    min-height: 100px;
    resize: vertical;
}

/* ========== Enhanced Alerts ========== */
.alert {
    padding: 1rem 1.25rem;
    border-radius: 0.75rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    font-size: 0.9375rem;
    line-height: 1.6;
    position: relative;
    overflow: hidden;
}

.alert::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 5px;
}

.alert-success {
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    color: #065f46;
    border: 1px solid rgba(16, 185, 129, 0.2);
}

.alert-success::before {
    background: linear-gradient(180deg, #10b981 0%, #059669 100%);
}

.alert-error {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    color: #991b1b;
    border: 1px solid rgba(239, 68, 68, 0.2);
}

.alert-error::before {
    background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%);
}

.alert-info {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    color: #1e40af;
    border: 1px solid rgba(59, 130, 246, 0.2);
}

.alert-info::before {
    background: #3b82f6;
}

.alert-warning {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    color: #92400e;
    border: 1px solid rgba(245, 158, 11, 0.2);
}

.alert-warning::before {
    background: linear-gradient(180deg, #f59e0b 0%, #d97706 100%);
}

/* ========== Enhanced Links ========== */
a {
    color: var(--accent);
    text-decoration: none;
    transition: color 0.15s ease;
    font-weight: 500;
}

a:hover {
    color: var(--accent-hover);
    text-decoration: underline;
}

a:active {
    color: var(--accent-hover);
}

/* ========== DaisyUI Stats Component Support ========== */
.stats {
    display: grid;
    grid-auto-flow: column;
    gap: 0;
    border-radius: 1rem;
    box-shadow: var(--card-shadow);
    overflow: hidden;
    background: var(--bg-card);
}

.stat {
    padding: 1.5rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    border-right: 1px solid var(--border-color-light);
}

.stat:last-child {
    border-right: none;
}

.stat-title {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Note: .stat-value is defined in main stat-card section above */

.stat-desc {
    font-size: 0.875rem;
    color: var(--text-secondary);
    font-weight: 400;
}

/* ========== Additional Polish ========== */
/* Better spacing for headings with emojis */
h2:first-line,
h3:first-line {
    line-height: 1.4;
}

/* Smooth scrolling */
html {
    scroll-behavior: smooth;
}

/* ========== Form Layout Improvements ========== */
/* Align form fields properly */
form {
    max-width: 100%;
}

/* Grid layout for form fields */
form .form-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
}

/* Stack labels and inputs vertically */
form .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

/* Consistent form field widths */
form input[type="text"],
form input[type="email"],
form input[type="password"],
form input[type="number"],
form input[type="date"],
form input[type="tel"],
form select,
form textarea {
    width: 100%;
}

/* Search field containers (fix alignment issues) */
.search-container,
form[method="get"] {
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
    flex-wrap: wrap;
}

.search-container input,
form[method="get"] input {
    flex: 1;
    min-width: 250px;
}

.search-container button,
form[method="get"] button {
    flex-shrink: 0;
}

/* ========== Legacy Button Overrides ========== */
/*
 * NOTE: These overrides exist for backward compatibility with old button styles.
 * For NEW buttons, use the BEM system: .btn, .btn--primary, .btn--success, etc.
 * See Python helpers: btn(), btn_link(), btn_icon()
 *
 * Legacy classes being phased out:
 * - .btn-outline → use .btn.btn--secondary
 * - .btn-danger → use .btn.btn--danger
 * - .secondary, .ghost, .success, .danger → use .btn.btn--{variant}
 */

/* Legacy .btn-outline - map to secondary style */
button.btn-outline:not(.btn),
a.btn-outline:not(.btn) {
    background: var(--btn-secondary-bg);
    color: var(--btn-secondary-text);
    border: 1px solid var(--btn-secondary-border);
    box-shadow: none;
    padding: 0.5rem 1rem;
}
button.btn-outline:not(.btn):hover,
a.btn-outline:not(.btn):hover {
    background: var(--btn-secondary-hover-bg);
    border-color: var(--btn-secondary-text);
}

/* Legacy .btn-danger (old style) - map to danger style */
button.btn-danger:not(.btn) {
    background: var(--btn-danger-bg);
    color: var(--btn-danger-text);
    border: 1px solid var(--btn-danger-border);
    box-shadow: none;
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
}
button.btn-danger:not(.btn):hover {
    background: var(--btn-danger-hover-bg);
    color: var(--btn-danger-hover-text);
    border-color: var(--btn-danger-hover-bg);
}

/* Legacy old-style variants (without .btn class) */
button.secondary:not(.btn),
[role="button"].secondary:not(.btn) {
    background: var(--btn-secondary-bg);
    color: var(--accent);
    border: 1.5px solid var(--accent);
}

button.ghost:not(.btn),
[role="button"].ghost:not(.btn) {
    background: transparent;
    color: var(--accent);
    border: none;
    box-shadow: none;
}

button.success:not(.btn),
[role="button"].success:not(.btn) {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
}

button.danger:not(.btn),
[role="button"].danger:not(.btn) {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
}

/* Selection styling */
::selection {
    background: rgba(99, 102, 241, 0.2);
    color: #1e293b;
}

/* Focus visible for accessibility */
*:focus-visible {
    outline: 2px solid #6366f1;
    outline-offset: 2px;
}

/* ========== Responsive Design ========== */
@media (max-width: 768px) {
    .form-row {
        grid-template-columns: 1fr;
    }

    h1 { font-size: 1.5rem; }
    h2 { font-size: 1.25rem; }
    h3 { font-size: 1.1rem; }

    nav .nav-container {
        flex-direction: column;
        gap: 1rem;
    }

    nav ul {
        flex-wrap: wrap;
        justify-content: center;
        gap: 0.5rem;
    }
}

/* ========== Enhanced Tabs with "Folder Tab" Effect ========== */
.tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 0;
    padding-left: 0.5rem;
}

.tab {
    padding: 0.75rem 1.5rem;
    border-radius: 0.5rem 0.5rem 0 0;
    background: var(--accent-light);
    color: var(--text-secondary);
    font-weight: 500;
    font-size: 0.9375rem;
    border: 1px solid var(--border-color);
    border-bottom: none;
    position: relative;
    transition: background-color 0.15s ease, color 0.15s ease;
    cursor: pointer;
    margin-bottom: -1px;
}

.tab:hover {
    background: var(--bg-sidebar-hover);
    color: var(--text-primary);
}

.tab-active {
    background: var(--bg-card) !important;
    color: var(--accent) !important;
    font-weight: 600;
    border-color: var(--accent);
    z-index: 10;
}

.tab-active::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--accent-gradient);
    border-radius: 0.5rem 0.5rem 0 0;
}

/* Remove DaisyUI tab-lifted corner decorations (black corners) */
.tabs-lifted > .tab::before,
.tabs-lifted > .tab::after,
.tabs-lifted > .tab-active::after {
    display: none !important;
}

/* Also hide any corner elements from daisyUI tabs-lifted */
.tabs-lifted::before,
.tabs-lifted::after {
    display: none !important;
}

/* ========== Enhanced Stat Cards with Gradients ========== */
.stats {
    display: grid;
    grid-auto-flow: column;
    gap: 1rem;
    border-radius: 1rem;
    box-shadow: none;
    overflow: visible;
    background: transparent;
}

.stat {
    padding: 1.75rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    background: var(--bg-card);
    border-radius: 0.75rem;
    border: 1px solid var(--card-border);
    box-shadow: var(--card-shadow);
    position: relative;
    overflow: hidden;
}

.stat::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--accent-gradient);
}

/* stat:hover removed — cards are static containers */

/* Note: stat-title, stat-value, stat-desc are defined earlier in stat-card section */

/* ========== Sidebar Navigation ========== */
.app-layout {
    display: flex;
    min-height: 100vh;
    background: var(--bg-page);
}

.sidebar {
    width: 240px;
    min-width: 240px;
    background: var(--bg-sidebar);
    display: flex;
    flex-direction: column;
    transition: width 0.2s ease;
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    overflow-y: auto;
    overflow-x: hidden;
    border-right: 1px solid var(--sidebar-border);
    box-shadow: var(--sidebar-shadow);
}

.sidebar.collapsed {
    width: 60px;
    min-width: 60px;
}

.sidebar-header {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--sidebar-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 56px;
    gap: 0.5rem;
}

.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
    color: var(--text-primary);
}

.sidebar-logo-text {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--accent);
    white-space: nowrap;
}

.sidebar.collapsed .sidebar-logo-text {
    display: none;
}

.sidebar-toggle-btn {
    width: 32px;
    height: 32px;
    min-width: 32px;
    background: var(--bg-sidebar-hover) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 0.375rem !important;
    cursor: pointer;
    display: flex !important;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    color: var(--text-secondary) !important;
    transition: background-color 0.15s ease, color 0.15s ease;
    padding: 0 !important;
    box-shadow: none !important;
    transform: none !important;
}

.sidebar-toggle-btn:hover {
    background: var(--accent-light) !important;
    color: var(--accent) !important;
    transform: none !important;
    box-shadow: none !important;
}

.sidebar.collapsed .sidebar-header {
    justify-content: center;
}

.sidebar.collapsed .sidebar-toggle-btn {
    width: 36px;
    height: 36px;
}

.sidebar-nav {
    flex: 1;
    padding: 0.5rem 0;
    overflow-y: auto;
    overflow-x: hidden;
}

.sidebar-section {
    margin-bottom: 0.25rem;
}

/* Clickable section header (accordion toggle) */
.sidebar-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 1rem;
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
    user-select: none;
}

.sidebar-section-header:hover {
    color: var(--text-secondary);
    background: var(--bg-sidebar-hover);
}

.sidebar-section-arrow {
    font-size: 0.5rem;
    transition: transform 0.2s ease;
}

.sidebar-section.collapsed .sidebar-section-arrow {
    transform: rotate(-90deg);
}

.sidebar-section-items {
    overflow: hidden;
    transition: max-height 0.3s ease;
    max-height: 500px;
}

.sidebar-section.collapsed .sidebar-section-items {
    max-height: 0;
}

.sidebar.collapsed .sidebar-section-header {
    display: none;
}

.sidebar-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 1rem;
    color: var(--text-secondary);
    text-decoration: none;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    border-left: 3px solid transparent;
    cursor: pointer;
}

.sidebar-item:hover {
    background: var(--bg-sidebar-hover);
    color: var(--text-primary);
    border-left-color: var(--accent);
}

.sidebar-item.active {
    background: var(--bg-sidebar-active);
    color: var(--accent);
    border-left-color: var(--accent);
    font-weight: 500;
}

.sidebar-item-icon {
    width: 20px;
    height: 20px;
    min-width: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

/* Lucide icons inherit current color */
.lucide-icon,
.lucide-icon svg {
    stroke: currentColor;
    fill: none;
}

.sidebar-item-icon svg {
    stroke: currentColor;
    width: 20px;
    height: 20px;
}

.sidebar-item-text {
    font-size: 0.85rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.sidebar.collapsed .sidebar-item-text {
    display: none;
}

.sidebar.collapsed .sidebar-badge {
    display: none;
}

.sidebar.collapsed .sidebar-item {
    justify-content: center;
    padding: 0.6rem;
    border-left: none;
}

/* User section at bottom */
.sidebar-footer {
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--sidebar-border);
    margin-top: auto;
}

.sidebar-user {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    color: var(--text-secondary);
    font-size: 0.8rem;
    text-decoration: none;
    padding: 0.5rem;
    border-radius: 0.5rem;
    transition: background-color 0.15s ease;
}

.sidebar-user:hover {
    background: var(--bg-sidebar-hover);
}

.sidebar-user-avatar {
    width: 32px;
    height: 32px;
    min-width: 32px;
    background: var(--accent-gradient);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-on-accent);
    font-weight: 600;
    font-size: 0.85rem;
}

.sidebar-user-info {
    overflow: hidden;
}

.sidebar-user-email {
    font-weight: 500;
    color: var(--text-primary);
    font-size: 0.8rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 140px;
}

.sidebar-user-logout {
    font-size: 0.7rem;
    color: var(--text-muted);
}

/* ========== Theme Toggle (icon-only in header) ========== */
/* High specificity to override button:not(...) rules */
.sidebar-header-buttons > button.theme-toggle,
button.theme-toggle.theme-toggle {
    width: 32px;
    height: 32px;
    min-width: 32px;
    display: flex !important;
    align-items: center;
    justify-content: center;
    padding: 0 !important;
    background: var(--bg-sidebar-hover) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 0.375rem !important;
    color: var(--text-secondary) !important;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
    box-shadow: none !important;
    transform: none !important;
}

.sidebar-header-buttons > button.theme-toggle:hover,
button.theme-toggle.theme-toggle:hover {
    background: var(--border-color) !important;
    color: var(--text-primary) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* Theme toggle icons - show/hide based on current theme */
.theme-icon-moon,
.theme-icon-sun {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
}

/* Light theme (default): show moon icon, hide sun */
.theme-icon-sun {
    display: none;
}

/* Dark theme: show sun icon, hide moon */
[data-theme="dark"] .theme-icon-moon {
    display: none;
}

[data-theme="dark"] .theme-icon-sun {
    display: inline-flex;
}

/* Header buttons container */
.sidebar-header-buttons {
    display: flex;
    gap: 0.4rem;
    align-items: center;
}

/* When collapsed, stack buttons vertically */
.sidebar.collapsed .sidebar-header-buttons {
    flex-direction: column;
    gap: 0.3rem;
}

.sidebar.collapsed .sidebar-user-info {
    display: none;
}

.sidebar.collapsed .sidebar-user {
    justify-content: center;
}

/* Main content area */
.main-content {
    flex: 1;
    margin-left: 240px;
    transition: margin-left 0.3s ease;
    min-height: 100vh;
}

.sidebar.collapsed + .main-content,
.main-content.sidebar-collapsed {
    margin-left: 60px;
}

/* Remove old nav styles when sidebar is used (except sidebar-nav) */
.app-layout nav:not(.sidebar-nav) {
    display: none;
}

/* ========== Design System V2: Status Badge System ========== */
/* Reference: Logistics page compact design */

.status-badge-v2 {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
}

.status-badge-v2--pending {
    background: var(--badge-pending);
    color: #92400e;
}

.status-badge-v2--active,
.status-badge-v2--success {
    background: var(--badge-active);
    color: #065f46;
}

.status-badge-v2--complete,
.status-badge-v2--info {
    background: var(--badge-complete);
    color: #1e40af;
}

.status-badge-v2--purple {
    background: var(--badge-purple);
    color: #6b21a8;
}

.status-badge-v2--neutral {
    background: var(--badge-neutral);
    color: #4b5563;
}

.status-badge-v2--error {
    background: var(--badge-error);
    color: #991b1b;
}

.status-badge-v2--warning {
    background: var(--badge-pending);
    color: #92400e;
}

/* Dark theme overrides */
[data-theme="dark"] .status-badge-v2--pending { color: #fcd34d; }
[data-theme="dark"] .status-badge-v2--active,
[data-theme="dark"] .status-badge-v2--success { color: #86efac; }
[data-theme="dark"] .status-badge-v2--complete,
[data-theme="dark"] .status-badge-v2--info { color: #93c5fd; }
[data-theme="dark"] .status-badge-v2--purple { color: #c4b5fd; }
[data-theme="dark"] .status-badge-v2--neutral { color: #d1d5db; }
[data-theme="dark"] .status-badge-v2--error { color: #fca5a5; }
[data-theme="dark"] .status-badge-v2--warning { color: #fcd34d; }

/* ========== Design System V2: Elevated Cards ========== */

.card-elevated {
    background: var(--bg-card-elevated);
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: var(--shadow-card-v2);
    overflow: hidden;
}

/* card-elevated:hover removed — cards are static containers */

.card-elevated-static {
    background: var(--bg-card-elevated);
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: var(--shadow-card-v2);
}

[data-theme="dark"] .card-elevated,
[data-theme="dark"] .card-elevated-static {
    border-color: rgba(255, 255, 255, 0.1);
}

/* ========== Design System V2: Compact Labels ========== */

.label-compact {
    font-size: var(--label-size);
    font-weight: var(--label-weight);
    color: var(--label-color);
    text-transform: var(--label-transform);
    letter-spacing: var(--label-spacing);
    margin-bottom: 4px;
}

/* ========== Design System V2: Enhanced Tables ========== */

.table-enhanced {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    background: var(--bg-card);
}

/* Table Container with rounded corners */
.table-enhanced-container {
    border-radius: 12px;
    overflow: hidden;
    box-shadow: var(--shadow-card-v2);
    border: 1px solid #e2e8f0;
}

[data-theme="dark"] .table-enhanced-container {
    border-color: rgba(255, 255, 255, 0.1);
}

/* Header Row */
.table-enhanced thead {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

[data-theme="dark"] .table-enhanced thead {
    background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.04) 100%);
}

.table-enhanced thead th {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
    padding: 12px 16px;
    border-bottom: 2px solid #e2e8f0;
    text-align: left;
    white-space: nowrap;
}

[data-theme="dark"] .table-enhanced thead th {
    color: #94a3b8;
    border-bottom-color: rgba(255, 255, 255, 0.1);
}

/* Body Rows */
.table-enhanced tbody tr {
    transition: background-color 0.15s ease;
    border-bottom: 1px solid #f1f5f9;
}

[data-theme="dark"] .table-enhanced tbody tr {
    border-bottom-color: rgba(255, 255, 255, 0.05);
}

.table-enhanced tbody tr:last-child {
    border-bottom: none;
}

/* Zebra Striping */
.table-enhanced tbody tr:nth-child(even) {
    background: rgba(59, 130, 246, 0.02);
}

[data-theme="dark"] .table-enhanced tbody tr:nth-child(even) {
    background: rgba(99, 102, 241, 0.04);
}

/* Hover Effect */
.table-enhanced tbody tr:hover {
    background: rgba(59, 130, 246, 0.06);
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.1);
}

[data-theme="dark"] .table-enhanced tbody tr:hover {
    background: rgba(99, 102, 241, 0.1);
    box-shadow: inset 0 0 0 1px rgba(99, 102, 241, 0.15);
}

/* Cell Styling */
.table-enhanced td {
    padding: 14px 16px;
    font-size: 14px;
    vertical-align: middle;
}

/* Link Styling in Tables */
.table-enhanced a {
    color: #3b82f6;
    font-weight: 500;
}

[data-theme="dark"] .table-enhanced a {
    color: #93c5fd;
}

/* Right-align numeric columns */
.table-enhanced th.col-number,
.table-enhanced td.col-number,
.table-enhanced th.col-money,
.table-enhanced td.col-money {
    text-align: right;
}

/* Center-align action columns */
.table-enhanced th.col-actions,
.table-enhanced td.col-actions {
    text-align: center;
    width: 100px;
}

/* ========== Design System V2: Handsontable Overrides ========== */

/* Handsontable Container */
.handsontable-container {
    border-radius: 12px;
    overflow: hidden;
    box-shadow: var(--shadow-card-v2);
    border: 1px solid #e2e8f0;
}

[data-theme="dark"] .handsontable-container {
    border-color: rgba(255, 255, 255, 0.1);
}

/* Header Row - Match design system */
.handsontable-container .handsontable thead th,
.handsontable thead th.htNoFrame {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #64748b !important;
    border-bottom: 2px solid #e2e8f0 !important;
    padding: 10px 12px !important;
}

[data-theme="dark"] .handsontable-container .handsontable thead th,
[data-theme="dark"] .handsontable thead th.htNoFrame {
    background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.04) 100%) !important;
    color: #94a3b8 !important;
    border-bottom-color: rgba(255, 255, 255, 0.1) !important;
}

/* Body Cells */
.handsontable-container .handsontable td {
    border-color: #f1f5f9 !important;
    font-size: 14px !important;
    padding: 8px 12px !important;
}

[data-theme="dark"] .handsontable-container .handsontable td {
    border-color: rgba(255, 255, 255, 0.05) !important;
}

/* Zebra Striping */
.handsontable-container .handsontable tbody tr:nth-child(even) td {
    background: rgba(59, 130, 246, 0.02) !important;
}

[data-theme="dark"] .handsontable-container .handsontable tbody tr:nth-child(even) td {
    background: rgba(99, 102, 241, 0.04) !important;
}

/* Hover Effect */
.handsontable-container .handsontable tbody tr:hover td {
    background: rgba(59, 130, 246, 0.06) !important;
}

[data-theme="dark"] .handsontable-container .handsontable tbody tr:hover td {
    background: rgba(99, 102, 241, 0.1) !important;
}

/* Read-only Cells - Subtle gray background */
.handsontable-container .handsontable td.htDimmed {
    background: #f9fafb !important;
    color: #64748b !important;
}

[data-theme="dark"] .handsontable-container .handsontable td.htDimmed {
    background: rgba(255, 255, 255, 0.03) !important;
    color: #94a3b8 !important;
}

/* Editable Cells - White background */
.handsontable-container .handsontable td:not(.htDimmed) {
    background: #ffffff !important;
}

[data-theme="dark"] .handsontable-container .handsontable td:not(.htDimmed) {
    background: #1e1e2f !important;
}

/* Selected Cell */
.handsontable-container .handsontable td.current,
.handsontable-container .handsontable td.area {
    border: 2px solid #3b82f6 !important;
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.2) !important;
}

[data-theme="dark"] .handsontable-container .handsontable td.current,
[data-theme="dark"] .handsontable-container .handsontable td.area {
    border-color: #6366f1 !important;
    box-shadow: inset 0 0 0 1px rgba(99, 102, 241, 0.3) !important;
}

/* Input in Cell */
.handsontable-container .handsontable .handsontableInput {
    font-size: 14px !important;
    padding: 6px 10px !important;
    border: 1px solid #3b82f6 !important;
    border-radius: 4px !important;
}

/* Checkbox Cells */
.handsontable-container .handsontable td.htCheckboxRendererInput {
    text-align: center !important;
}

/* Row headers styling */
.handsontable-container .handsontable th.ht_clone_left {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
    font-size: 12px !important;
    color: #64748b !important;
}

[data-theme="dark"] .handsontable-container .handsontable th.ht_clone_left {
    background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.04) 100%) !important;
    color: #94a3b8 !important;
}

/* ========== Design System V2: Animations ========== */

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.animate-fade-in-up {
    animation: fadeInUp 0.4s ease forwards;
}

.animate-fade-in {
    animation: fadeIn 0.3s ease forwards;
}

/* Staggered delays for card grids */
.stagger-1 { animation-delay: 0.05s; opacity: 0; }
.stagger-2 { animation-delay: 0.1s; opacity: 0; }
.stagger-3 { animation-delay: 0.15s; opacity: 0; }
.stagger-4 { animation-delay: 0.2s; opacity: 0; }
.stagger-5 { animation-delay: 0.25s; opacity: 0; }

/* ========== Design System V2: Compact Utilities ========== */

.p-tight { padding: var(--spacing-tight); }
.p-compact { padding: var(--spacing-compact); }
.p-normal { padding: var(--spacing-normal); }

.gap-tight { gap: var(--spacing-tight); }
.gap-compact { gap: var(--spacing-compact); }
.gap-normal { gap: var(--spacing-normal); }

.mb-tight { margin-bottom: var(--spacing-tight); }
.mb-compact { margin-bottom: var(--spacing-compact); }
.mb-normal { margin-bottom: var(--spacing-normal); }
"""

# ============================================================================
# LAYOUT HELPERS
# ============================================================================

def nav_bar(session):
    """Navigation bar component with role-based links"""
    user = session.get("user")
    if user:
        roles = user.get("roles", [])

        # Check if user is procurement-only (no access to sales features)
        is_procurement_only = "procurement" in roles and not any(
            role in roles for role in ["admin", "sales", "sales_manager", "quote_controller"]
        )

        # Base navigation items (hidden from procurement-only users)
        nav_items = [Li(A("Dashboard", href="/dashboard"))]

        # Hide Quotes/Customers/New Quote from procurement-only users
        if not is_procurement_only:
            nav_items.extend([
                Li(A("Quotes", href="/quotes")),
                Li(A("Customers", href="/customers")),
                Li(A("New Quote", href="/quotes/new")),
            ])

        # Role-specific navigation items
        if "procurement" in roles or "admin" in roles:
            nav_items.append(Li(A("Закупки", href="/procurement")))

        if "logistics" in roles or "admin" in roles:
            nav_items.append(Li(A("Логистика", href="/logistics")))

        if "customs" in roles or "admin" in roles:
            nav_items.append(Li(A("Таможня", href="/customs")))

        if "quote_controller" in roles or "admin" in roles:
            nav_items.append(Li(A("Контроль КП", href="/quote-control")))

        if "top_manager" in roles or "admin" in roles:
            nav_items.append(Li(A("Согласования", href="/approvals")))

        if "spec_controller" in roles or "admin" in roles:
            nav_items.append(Li(A("Спецификации", href="/spec-control")))

        if "finance" in roles or "admin" in roles:
            nav_items.append(Li(A("Финансы", href="/finance")))

        # Supply chain navigation (procurement + admin)
        if "procurement" in roles or "admin" in roles:
            nav_items.append(Li(A("Поставщики", href="/suppliers")))

        # Admin-only navigation
        if "admin" in roles:
            nav_items.append(Li(A("Админ", href="/admin")))
            nav_items.append(Li(A("Settings", href="/settings")))

        # Add profile and logout at the end
        nav_items.extend([
            Li(A("Профиль", href="/profile")),
            Li(A(f"Logout ({user.get('email', 'User')})", href="/logout")),
        ])

        return Nav(
            Div(
                Ul(Li(Strong("Kvota OneStack"))),
                Ul(*nav_items),
                cls="nav-container"
            )
        )
    return Nav(
        Div(
            Ul(Li(Strong("Kvota OneStack"))),
            Ul(Li(A("Login", href="/login"))),
            cls="nav-container"
        )
    )


def sidebar(session, current_path: str = ""):
    """
    Collapsible sidebar navigation with role-based menu items.

    Args:
        session: User session with roles
        current_path: Current URL path to highlight active item
    """
    user = session.get("user")

    if not user:
        # Not logged in - show minimal sidebar with login
        return Aside(
            Div(
                A(
                    Span("Kvota", cls="sidebar-logo-text"),
                    href="/",
                    cls="sidebar-logo"
                ),
                Button(
                    Div("☰", cls="sidebar-toggle-icon", id="toggle-icon"),
                    cls="sidebar-toggle-btn",
                    onclick="toggleSidebar()",
                    type="button"
                ),
                cls="sidebar-header"
            ),
            Nav(
                Div(
                    A(
                        Span("🔑", cls="sidebar-item-icon"),
                        Span("Войти", cls="sidebar-item-text"),
                        href="/login",
                        cls="sidebar-item"
                    ),
                    cls="sidebar-section"
                ),
                cls="sidebar-nav"
            ),
            # Footer with theme toggle
            Div(
                Button(
                    icon("moon", size=18, cls="theme-icon-moon"),
                    icon("sun", size=18, cls="theme-icon-sun"),
                    cls="theme-toggle",
                    onclick="toggleTheme()",
                    type="button",
                    title="Переключить тему"
                ),
                cls="sidebar-footer",
                style="padding: 0.5rem; display: flex; justify-content: center;"
            ),
            cls="sidebar",
            id="sidebar"
        )

    real_roles = user.get("roles", [])
    is_real_admin = "admin" in real_roles
    is_training_manager = "training_manager" in real_roles
    can_impersonate = is_real_admin or is_training_manager

    # Use impersonated role for menu visibility if active
    impersonated_role = session.get("impersonated_role")
    if impersonated_role:
        roles = [impersonated_role]
        is_admin = (impersonated_role == "admin")
    else:
        roles = real_roles
        is_admin = is_real_admin or is_training_manager

    user_id = user.get("id")

    # Role impersonation dropdown (admins and training managers)
    impersonation_select = None
    if can_impersonate:
        active_roles = ["sales", "procurement", "logistics", "customs", "finance",
                        "quote_controller", "spec_controller", "top_manager",
                        "head_of_sales", "head_of_procurement", "head_of_logistics",
                        "currency_controller"]
        current_impersonation = session.get("impersonated_role", "")
        default_label = "Менеджер обучения (все разделы)" if is_training_manager and not is_real_admin else "Администратор (все права)"
        options = [Option(default_label, value="", selected=not current_impersonation)]
        for r in active_roles:
            options.append(Option(ROLE_LABELS_RU.get(r, r), value=r, selected=(current_impersonation == r)))
        impersonation_select = Div(
            Select(*options,
                   onchange="window.location.href='/admin/impersonate?role=' + encodeURIComponent(this.value)",
                   style="font-size: 11px; padding: 4px 8px; border-radius: 6px; border: 1px solid #e2e8f0; width: 100%; background: #fef3c7;"),
            style="padding: 4px 12px; margin-bottom: 4px;",
            cls="sidebar-section"
        )

    # Get pending approvals count for badge (top_manager/admin only)
    pending_approvals_count = 0
    if user_id and (is_admin or "top_manager" in roles):
        try:
            pending_approvals_count = count_pending_approvals(user_id)
        except Exception:
            pending_approvals_count = 0

    # Get changelog unread count for badge (all users)
    changelog_unread_count = 0
    if user_id:
        try:
            from services.changelog_service import count_unread_entries
            changelog_unread_count = count_unread_entries(user_id)
        except Exception:
            changelog_unread_count = 0

    # Define menu structure with role requirements
    menu_sections = []

    # === MAIN SECTION ===
    main_items = [
        {"icon": "inbox", "label": "Мои задачи", "href": "/tasks", "roles": None},  # All users - primary entry point
        {"icon": "play-circle", "label": "Обучение", "href": "/training", "roles": None},  # All users - training videos
        {"icon": "newspaper", "label": "Обновления", "href": "/changelog", "roles": None, "badge": changelog_unread_count if changelog_unread_count > 0 else None},
        {"icon": "send", "label": "Уведомления", "href": "/telegram", "roles": None},
    ]
    # Add "Новый КП" button for sales/admin
    if is_admin or any(r in roles for r in ["sales", "sales_manager"]):
        main_items.append({"icon": "plus-circle", "label": "Новый КП", "href": "/quotes/new", "roles": ["sales", "sales_manager", "admin"]})
    # Add "Обзор" (analytics) for all department roles
    if is_admin or any(r in roles for r in ["top_manager", "sales", "sales_manager", "head_of_sales", "procurement", "logistics", "head_of_logistics", "customs", "head_of_customs", "quote_controller", "spec_controller", "finance"]):
        main_items.append({"icon": "bar-chart-3", "label": "Обзор", "href": "/dashboard?tab=overview", "roles": None})
    # Add "Согласования" (approvals workspace) for top_manager/admin with badge
    if is_admin or "top_manager" in roles:
        main_items.append({
            "icon": "clock",
            "label": "Согласования",
            "href": "/approvals",
            "roles": ["admin", "top_manager"],
            "badge": pending_approvals_count if pending_approvals_count > 0 else None
        })

    menu_sections.append({"title": "Главное", "items": main_items})

    # === REGISTRIES SECTION (reference data) ===
    registries_items = []

    # Customers - for sales roles, heads, and admins
    if is_admin or any(r in roles for r in ["sales", "sales_manager", "top_manager", "head_of_sales"]):
        registries_items.append({"icon": "users", "label": "Клиенты", "href": "/customers", "roles": ["sales", "sales_manager", "admin", "top_manager", "head_of_sales"]})

    # Quotes registry - visible to ALL authenticated roles
    registries_items.append({"icon": "file-text", "label": "Коммерческие предложения", "href": "/quotes", "roles": None})

    # Suppliers - for procurement
    if is_admin or "procurement" in roles:
        registries_items.append({"icon": "building-2", "label": "Поставщики", "href": "/suppliers", "roles": ["procurement", "admin"]})


    # Customs declarations registry - for customs, finance, admin
    if is_admin or any(r in roles for r in ["customs", "finance"]):
        registries_items.append({"icon": "file-text", "label": "Таможенные декларации", "href": "/customs/declarations", "roles": ["customs", "finance", "admin"]})

    # Calls journal - for sales and admin
    if is_admin or any(r in roles for r in ["sales", "sales_manager", "top_manager"]):
        registries_items.append({"icon": "phone", "label": "Журнал звонков", "href": "/calls", "roles": ["sales", "sales_manager", "top_manager", "admin"]})

    # Company registries - for admin (not training_manager)
    if is_real_admin:
        registries_items.append({"icon": "building", "label": "Юрлица", "href": "/companies", "roles": ["admin"]})

    if registries_items:
        menu_sections.append({"title": "Реестры", "items": registries_items})

    # === FINANCE SECTION (for finance roles) ===
    if is_admin or any(r in roles for r in ["finance", "top_manager", "currency_controller"]):
        finance_items = [
            {"icon": "file-text", "label": "Контроль платежей", "href": "/finance?tab=erps", "roles": ["finance", "top_manager", "admin"]},
            {"icon": "calendar", "label": "Календарь", "href": "/payments/calendar", "roles": ["finance", "top_manager", "admin"]},
        ]
        # Currency invoices registry for admin and currency_controller
        if is_admin or "currency_controller" in roles:
            finance_items.append({"icon": "file-text", "label": "Валютные инвойсы", "href": "/currency-invoices", "roles": ["currency_controller", "admin"]})
        menu_sections.append({"title": "Финансы", "items": finance_items})

    # === ADMIN SECTION ===
    if is_real_admin:
        _feedback_href = "/admin" + "/feedback"
        admin_items = [
            {"icon": "user", "label": "Пользователи", "href": "/admin", "roles": ["admin"]},
            {"icon": "message-square", "label": "Обращения", "href": _feedback_href, "roles": ["admin"]},
            {"icon": "git-branch", "label": "Маршрутизация закупок", "href": "/admin/procurement-groups", "roles": ["admin"]},
            {"icon": "settings", "label": "Настройки", "href": "/settings", "roles": ["admin"]},
        ]
        menu_sections.append({"title": "Администрирование", "items": admin_items})

    # Build sidebar sections with collapsible headers
    nav_sections = []
    for idx, section in enumerate(menu_sections):
        section_items = []
        has_active = False

        for item in section["items"]:
            # Check if user has required role
            if item["roles"] is None or is_admin or any(r in roles for r in item["roles"]):
                is_active = current_path == item["href"] or (item["href"] != "/" and current_path.startswith(item["href"]))
                if is_active:
                    has_active = True

                # Build item content with optional badge
                item_content = [
                    icon(item["icon"], size=20, cls="sidebar-item-icon"),
                    Span(item["label"], cls="sidebar-item-text"),
                ]
                # Add badge if present (e.g., pending approvals count)
                if item.get("badge"):
                    item_content.append(
                        Span(
                            str(item["badge"]),
                            cls="sidebar-badge",
                            style="background: #ef4444; color: white; font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; margin-left: auto; min-width: 18px; text-align: center;"
                        )
                    )

                section_items.append(
                    A(
                        *item_content,
                        href=item["href"],
                        cls=f"sidebar-item {'active' if is_active else ''}"
                    )
                )

        if section_items:
            section_id = f"section-{idx}"
            nav_sections.append(
                Div(
                    # Clickable section header
                    Div(
                        Span(section["title"]),
                        Span("▼", cls="sidebar-section-arrow"),
                        cls="sidebar-section-header",
                        onclick=f"toggleSection('{section_id}')"
                    ),
                    # Collapsible items container
                    Div(
                        *section_items,
                        cls="sidebar-section-items",
                        id=section_id
                    ),
                    cls="sidebar-section",
                    data_has_active="true" if has_active else "false"
                )
            )

    # User info
    email = user.get("email", "User")
    initials = email[0].upper() if email else "U"

    return Aside(
        # Header with logo and separate toggle button
        Div(
            A(
                Span("Kvota", cls="sidebar-logo-text"),
                href="/dashboard",
                cls="sidebar-logo"
            ),
            Div(
                Button(
                    icon("moon", size=18, cls="theme-icon-moon"),
                    icon("sun", size=18, cls="theme-icon-sun"),
                    cls="theme-toggle",
                    onclick="toggleTheme()",
                    type="button",
                    title="Переключить тему"
                ),
                Button(
                    Div("☰", cls="sidebar-toggle-icon", id="toggle-icon"),
                    cls="sidebar-toggle-btn",
                    onclick="toggleSidebar()",
                    type="button",
                    title="Свернуть панель"
                ),
                cls="sidebar-header-buttons"
            ),
            cls="sidebar-header"
        ),
        # Impersonation dropdown (admin only)
        *([impersonation_select] if impersonation_select else []),
        # Navigation sections
        Nav(*nav_sections, cls="sidebar-nav"),
        # Footer with user info
        Div(
            A(
                Div(initials, cls="sidebar-user-avatar"),
                Div(
                    Div(email, cls="sidebar-user-email"),
                    Div("Профиль", cls="sidebar-user-logout", style="color: #3b82f6;"),
                    cls="sidebar-user-info"
                ),
                href="/profile",
                cls="sidebar-user"
            ),
            A(
                icon("log-out", size=16),
                Span("Выйти", cls="sidebar-item-text", style="font-size: 12px; color: #94a3b8;"),
                href="/logout",
                cls="sidebar-item",
                style="padding: 4px 12px; gap: 8px; opacity: 0.7;",
                title="Выйти из системы"
            ),
            cls="sidebar-footer"
        ),
        cls="sidebar",
        id="sidebar"
    )


# JavaScript for sidebar toggle and section accordion
SIDEBAR_JS = """
<script>
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    const toggleIcon = document.getElementById('toggle-icon');

    sidebar.classList.toggle('collapsed');
    if (mainContent) {
        mainContent.classList.toggle('sidebar-collapsed');
    }

    // Update toggle icon
    const isCollapsed = sidebar.classList.contains('collapsed');
    if (toggleIcon) {
        toggleIcon.textContent = isCollapsed ? '▶' : '☰';
    }

    // Save state to localStorage
    localStorage.setItem('sidebarCollapsed', isCollapsed);
}

function toggleSection(sectionId) {
    const sidebar = document.getElementById('sidebar');
    // Don't toggle sections when sidebar is collapsed
    if (sidebar.classList.contains('collapsed')) return;

    const section = document.getElementById(sectionId);
    if (section) {
        const parent = section.closest('.sidebar-section');
        parent.classList.toggle('collapsed');

        // Save section states
        saveSectionStates();
    }
}

function saveSectionStates() {
    const sections = document.querySelectorAll('.sidebar-section');
    const states = {};
    sections.forEach((section, idx) => {
        states[idx] = section.classList.contains('collapsed');
    });
    localStorage.setItem('sidebarSections', JSON.stringify(states));
}

// Restore sidebar and section states on page load
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    const toggleIcon = document.getElementById('toggle-icon');

    // Restore sidebar collapsed state
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (isCollapsed) {
        if (sidebar) sidebar.classList.add('collapsed');
        if (mainContent) mainContent.classList.add('sidebar-collapsed');
        if (toggleIcon) toggleIcon.textContent = '▶';
    }

    // Restore section states - collapse all by default, expand only those with active items
    const savedStates = localStorage.getItem('sidebarSections');
    const sections = document.querySelectorAll('.sidebar-section');

    if (savedStates) {
        // Restore from saved state
        const states = JSON.parse(savedStates);
        sections.forEach((section, idx) => {
            if (states[idx]) {
                section.classList.add('collapsed');
            }
        });
    } else {
        // First visit: collapse all sections except those with active items
        sections.forEach(section => {
            const hasActive = section.getAttribute('data-has-active') === 'true';
            if (!hasActive) {
                section.classList.add('collapsed');
            }
        });
    }
});

// Tab switching - update active class
function switchTab(clickedTab) {
    // Find all tabs in the same tablist
    const tablist = clickedTab.closest('[role="tablist"]');
    if (tablist) {
        const tabs = tablist.querySelectorAll('.tab');
        tabs.forEach(tab => tab.classList.remove('tab-active'));
        clickedTab.classList.add('tab-active');
    }
}

// Theme toggle functionality
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    // Update toggle button icon
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    // Icons are toggled via CSS based on data-theme attribute
    // Theme toggle is icon-only, no text to update
}

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
});
</script>
"""


# ============================================================================
# FEEDBACK / BUG REPORT COMPONENTS
# ============================================================================

FEEDBACK_JS = """
// ========================================
// FEEDBACK: Debug context collection
// ========================================

// Storage for console errors (last 10)
window._feedbackConsoleErrors = [];
window._feedbackHTMXRequests = [];

// Intercept console.error
(function() {
    const originalError = console.error;
    console.error = function(...args) {
        window._feedbackConsoleErrors.push({
            type: 'error',
            message: args.map(a => String(a)).join(' '),
            time: new Date().toISOString()
        });
        if (window._feedbackConsoleErrors.length > 10) {
            window._feedbackConsoleErrors.shift();
        }
        originalError.apply(console, args);
    };
})();

// Intercept console.warn
(function() {
    const originalWarn = console.warn;
    console.warn = function(...args) {
        window._feedbackConsoleErrors.push({
            type: 'warn',
            message: args.map(a => String(a)).join(' '),
            time: new Date().toISOString()
        });
        if (window._feedbackConsoleErrors.length > 10) {
            window._feedbackConsoleErrors.shift();
        }
        originalWarn.apply(console, args);
    };
})();

// Intercept JS exceptions
window.addEventListener('error', function(e) {
    window._feedbackConsoleErrors.push({
        type: 'exception',
        message: e.message + ' at ' + e.filename + ':' + e.lineno,
        time: new Date().toISOString()
    });
});

// Intercept HTMX requests (defer until body exists)
document.addEventListener('DOMContentLoaded', function() {
  document.body.addEventListener('htmx:afterRequest', function(e) {
    const xhr = e.detail.xhr;
    window._feedbackHTMXRequests.push({
        url: e.detail.pathInfo?.requestPath || e.detail.requestConfig?.path,
        method: e.detail.requestConfig?.verb?.toUpperCase() || 'GET',
        status: xhr?.status || 'unknown',
        time: new Date().toISOString()
    });
    if (window._feedbackHTMXRequests.length > 10) {
        window._feedbackHTMXRequests.shift();
    }
  });
});

// Collect debug context
function collectDebugContext() {
    return {
        url: window.location.href,
        title: document.title,
        userAgent: navigator.userAgent,
        screenSize: window.innerWidth + 'x' + window.innerHeight,
        consoleErrors: window._feedbackConsoleErrors.slice(-5),
        recentRequests: window._feedbackHTMXRequests.slice(-5),
        formState: collectFormState(),
        sentryEventId: (typeof Sentry !== 'undefined' && Sentry.lastEventId) ? Sentry.lastEventId() : null,
        collectedAt: new Date().toISOString()
    };
}

// Collect form state (without passwords)
function collectFormState() {
    const forms = {};
    document.querySelectorAll('form').forEach((form, idx) => {
        const formData = {};
        form.querySelectorAll('input, select, textarea').forEach(el => {
            if (el.type === 'password' || el.type === 'hidden') return;
            if (!el.name) return;
            formData[el.name] = el.value?.substring(0, 100) || '';
        });
        if (Object.keys(formData).length > 0) {
            forms['form_' + idx] = formData;
        }
    });
    return forms;
}

// Open feedback modal
function openFeedbackModal() {
    const context = collectDebugContext();

    document.getElementById('feedback-page-url').value = context.url;
    document.getElementById('feedback-page-title').value = context.title;
    document.getElementById('feedback-debug-context').value = JSON.stringify(context);

    // Show context preview
    const preview = document.getElementById('feedback-context-preview');
    let previewHtml = '<span class="opacity-70">URL:</span> ' + context.url.substring(0, 50) + (context.url.length > 50 ? '...' : '') + '<br>';
    const browser = context.userAgent.includes('Chrome') ? 'Chrome' :
                   context.userAgent.includes('Firefox') ? 'Firefox' : 'Other';
    previewHtml += '<span class="opacity-70">Browser:</span> ' + browser + '<br>';
    if (context.consoleErrors.length > 0) {
        previewHtml += '<span class="text-error">Console errors:</span> ' + context.consoleErrors.length + '<br>';
    }
    if (context.recentRequests.length > 0) {
        const failed = context.recentRequests.filter(r => r.status >= 400).length;
        previewHtml += '<span class="opacity-70">Recent requests:</span> ' + context.recentRequests.length;
        if (failed > 0) previewHtml += ' <span class="text-error">(' + failed + ' failed)</span>';
        previewHtml += '<br>';
    }
    preview.innerHTML = previewHtml;

    // Show modal
    document.getElementById('feedback-backdrop').style.display = 'block';
    document.getElementById('feedback-modal-box').style.display = 'block';
}

// Close feedback modal
function closeFeedbackModal() {
    document.getElementById('feedback-backdrop').style.display = 'none';
    document.getElementById('feedback-modal-box').style.display = 'none';
    // Reset form
    const form = document.querySelector('#feedback-modal-box form');
    if (form) form.reset();
    const result = document.getElementById('feedback-result');
    if (result) result.innerHTML = '';
    // Clear screenshot state
    window._feedbackScreenshotData = null;
    const thumb = document.getElementById('feedback-screenshot-thumb');
    if (thumb) { thumb.src = ''; thumb.style.display = 'none'; }
    const hidden = document.getElementById('feedback-screenshot-data');
    if (hidden) hidden.value = '';
    const btn = document.getElementById('feedback-add-screenshot-btn');
    if (btn) btn.textContent = 'Добавить скриншот';
}

// Handle file upload for screenshot
function handleScreenshotUpload(input) {
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    if (!file.type.startsWith('image/')) return;
    var reader = new FileReader();
    reader.onload = function(e) {
        compressScreenshot(e.target.result, function(compressed) {
            window._feedbackScreenshotData = compressed;
            var thumb = document.getElementById('feedback-screenshot-thumb');
            thumb.src = compressed;
            thumb.style.display = 'block';
            var hidden = document.getElementById('feedback-screenshot-data');
            hidden.value = compressed;
            var addBtn = document.getElementById('feedback-add-screenshot-btn');
            if (addBtn) addBtn.textContent = 'Изменить скриншот';
        });
    };
    reader.readAsDataURL(file);
    // Reset input so same file can be re-selected
    input.value = '';
}

// Show success toast after feedback submission
function showFeedbackToast() {
    var toast = document.createElement('div');
    toast.textContent = 'Спасибо! Обращение отправлено.';
    toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);' +
        'background:#16a34a;color:#fff;padding:12px 24px;border-radius:8px;' +
        'font-size:14px;font-weight:500;z-index:10000;box-shadow:0 4px 12px rgba(0,0,0,0.15);' +
        'opacity:0;transition:opacity 0.3s ease;';
    document.body.appendChild(toast);
    // Fade in
    requestAnimationFrame(function() {
        toast.style.opacity = '1';
    });
    // Fade out after 3 seconds
    setTimeout(function() {
        toast.style.opacity = '0';
        setTimeout(function() {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }, 3000);
}

// Compress screenshot: resize to max 1280px width, JPEG quality 0.7
function compressScreenshot(dataUrl, callback) {
    var img = new Image();
    img.onload = function() {
        var maxW = 1280;
        var w = img.width;
        var h = img.height;
        if (w > maxW) {
            h = Math.round(h * maxW / w);
            w = maxW;
        }
        var canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        callback(canvas.toDataURL('image/jpeg', 0.7));
    };
    img.onerror = function() { callback(dataUrl); };
    img.src = dataUrl;
}
"""

ANNOTATION_EDITOR_JS = """
// ========================================
// FEEDBACK: Screenshot annotation editor
// ========================================

window._feedbackScreenshotData = null;

function openAnnotationEditor() {
    // 0. Check html2canvas is loaded
    if (typeof html2canvas === 'undefined') {
        console.error('html2canvas not loaded');
        var errMsg = document.createElement('div');
        errMsg.textContent = 'Скриншот недоступен — загрузите файл вручную.';
        errMsg.style.cssText = 'color:#dc2626;font-size:12px;margin-top:4px;';
        var btn = document.getElementById('feedback-add-screenshot-btn');
        if (btn && btn.parentNode) {
            btn.parentNode.appendChild(errMsg);
            setTimeout(function() { if (errMsg.parentNode) errMsg.remove(); }, 5000);
        }
        return;
    }

    // 1. Hide the feedback modal
    document.getElementById('feedback-modal-box').style.display = 'none';

    // 2. Use html2canvas to capture the page
    html2canvas(document.body, {
        useCORS: true,
        allowTaint: true,
        scale: 0.75,
        ignoreElements: function(el) {
            return el.id === 'feedback-modal' || el.id === 'feedback-backdrop';
        },
        onclone: function(clonedDoc) {
            // Fix oklch() colors that html2canvas cannot parse (Tailwind CSS uses oklch)
            // Step 1: Replace oklch() in all <style> tag text (stylesheet parsing fix)
            var styles = clonedDoc.querySelectorAll('style');
            for (var s = 0; s < styles.length; s++) {
                var txt = styles[s].textContent;
                if (txt && txt.indexOf('oklch') !== -1) {
                    styles[s].textContent = txt.replace(/oklch\\([^)]*\\)/g, '#888888');
                }
            }
            // Step 2: Override computed oklch on elements (inline style fix)
            var all = clonedDoc.querySelectorAll('*');
            for (var i = 0; i < all.length; i++) {
                var el = all[i];
                try {
                    var cs = clonedDoc.defaultView.getComputedStyle(el);
                    var props = ['color', 'background-color', 'border-color',
                                 'border-top-color', 'border-right-color',
                                 'border-bottom-color', 'border-left-color',
                                 'outline-color'];
                    for (var j = 0; j < props.length; j++) {
                        var val = cs.getPropertyValue(props[j]);
                        if (val && val.indexOf('oklch') !== -1) {
                            el.style.setProperty(props[j], '#888888', 'important');
                        }
                    }
                } catch(e) { /* skip inaccessible elements */ }
            }
        }
    }).then(function(capturedCanvas) {
        buildAnnotationEditor(capturedCanvas);
    }).catch(function(err) {
        console.error('html2canvas error:', err);
        document.getElementById('feedback-modal-box').style.display = 'block';
        // Show temporary error toast, keep button unchanged for retry
        var errMsg = document.createElement('div');
        errMsg.textContent = 'Не удалось сделать скриншот. Попробуйте ещё раз или загрузите файл.';
        errMsg.style.cssText = 'color:#dc2626;font-size:12px;margin-top:4px;';
        var btn = document.getElementById('feedback-add-screenshot-btn');
        if (btn && btn.parentNode) {
            btn.parentNode.appendChild(errMsg);
            setTimeout(function() { if (errMsg.parentNode) errMsg.remove(); }, 5000);
        }
    });
}

function buildAnnotationEditor(sourceCanvas) {
    var overlay = document.createElement('div');
    overlay.id = 'annotation-editor-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:#1a1a1a;display:flex;flex-direction:column;';

    var toolbar = document.createElement('div');
    toolbar.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;background:#2d2d2d;flex-shrink:0;';

    var tools = [
        { id: 'tool-brush', label: 'Brush', title: 'Draw' },
        { id: 'tool-arrow', label: 'Arrow', title: 'Arrow' },
        { id: 'tool-text', label: 'Text', title: 'Text' },
    ];
    var activeTool = 'brush';

    tools.forEach(function(t) {
        var btn = document.createElement('button');
        btn.id = t.id;
        btn.textContent = t.label;
        btn.title = t.title;
        btn.style.cssText = 'padding:6px 12px;border:1px solid #555;background:#444;color:#fff;border-radius:4px;cursor:pointer;font-size:13px;';
        btn.onclick = function() {
            activeTool = t.id.replace('tool-', '');
            document.querySelectorAll('#annotation-editor-overlay button[id^=tool-]').forEach(function(b) {
                b.style.background = '#444';
            });
            btn.style.background = '#e05b5b';
        };
        toolbar.appendChild(btn);
    });

    var undoBtn = document.createElement('button');
    undoBtn.textContent = 'Undo';
    undoBtn.style.cssText = 'padding:6px 12px;border:1px solid #555;background:#333;color:#ccc;border-radius:4px;cursor:pointer;font-size:13px;margin-left:8px;';
    undoBtn.onclick = function() { undoAnnotation(); };
    toolbar.appendChild(undoBtn);

    var spacer = document.createElement('div');
    spacer.style.flex = '1';
    toolbar.appendChild(spacer);

    var doneBtn = document.createElement('button');
    doneBtn.textContent = 'Done';
    doneBtn.style.cssText = 'padding:6px 16px;border:none;background:#22c55e;color:#fff;border-radius:4px;cursor:pointer;font-size:13px;font-weight:600;';
    doneBtn.onclick = function() { saveAnnotation(annotCanvas); };
    toolbar.appendChild(doneBtn);

    var cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    cancelBtn.style.cssText = 'padding:6px 12px;border:1px solid #555;background:#333;color:#ccc;border-radius:4px;cursor:pointer;font-size:13px;margin-left:4px;';
    cancelBtn.onclick = function() {
        document.getElementById('annotation-editor-overlay').remove();
        document.getElementById('feedback-modal-box').style.display = 'block';
    };
    toolbar.appendChild(cancelBtn);

    overlay.appendChild(toolbar);

    var canvasContainer = document.createElement('div');
    canvasContainer.style.cssText = 'flex:1;overflow:auto;display:flex;align-items:flex-start;justify-content:center;padding:12px;';

    var annotCanvas = document.createElement('canvas');
    annotCanvas.width = sourceCanvas.width;
    annotCanvas.height = sourceCanvas.height;
    annotCanvas.style.cssText = 'background-image:url(' + sourceCanvas.toDataURL() + ');background-size:100% 100%;cursor:crosshair;max-width:100%;';

    var ctx = annotCanvas.getContext('2d');
    ctx.strokeStyle = '#ff3333';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';

    var undoStack = [];
    var MAX_UNDO = 20;

    function saveState() {
        if (undoStack.length >= MAX_UNDO) undoStack.shift();
        undoStack.push(ctx.getImageData(0, 0, annotCanvas.width, annotCanvas.height));
    }

    function undoAnnotation() {
        if (undoStack.length === 0) return;
        var prev = undoStack.pop();
        ctx.putImageData(prev, 0, 0);
    }

    var isDrawing = false;
    var startX = 0, startY = 0;
    var arrowSnapshot = null;

    function getPos(e) {
        var rect = annotCanvas.getBoundingClientRect();
        var scaleX = annotCanvas.width / rect.width;
        var scaleY = annotCanvas.height / rect.height;
        var clientX = e.touches ? e.touches[0].clientX : e.clientX;
        var clientY = e.touches ? e.touches[0].clientY : e.clientY;
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY
        };
    }

    annotCanvas.addEventListener('mousedown', function(e) {
        if (activeTool === 'text') { placeTextInput(e, annotCanvas, ctx, saveState); return; }
        isDrawing = true;
        var pos = getPos(e);
        startX = pos.x; startY = pos.y;
        saveState();
        if (activeTool === 'brush') {
            ctx.beginPath();
            ctx.moveTo(startX, startY);
        }
        if (activeTool === 'arrow') {
            arrowSnapshot = ctx.getImageData(0, 0, annotCanvas.width, annotCanvas.height);
        }
    });

    annotCanvas.addEventListener('mousemove', function(e) {
        if (!isDrawing) return;
        var pos = getPos(e);
        if (activeTool === 'brush') {
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
        }
        if (activeTool === 'arrow' && arrowSnapshot) {
            ctx.putImageData(arrowSnapshot, 0, 0);
            drawArrow(ctx, startX, startY, pos.x, pos.y);
        }
    });

    annotCanvas.addEventListener('mouseup', function(e) {
        if (!isDrawing) return;
        isDrawing = false;
        var pos = getPos(e);
        if (activeTool === 'arrow') {
            ctx.putImageData(arrowSnapshot, 0, 0);
            drawArrow(ctx, startX, startY, pos.x, pos.y);
            arrowSnapshot = null;
        }
    });

    canvasContainer.appendChild(annotCanvas);
    overlay.appendChild(canvasContainer);
    document.body.appendChild(overlay);

    document.getElementById('tool-brush').style.background = '#e05b5b';
}

function drawArrow(ctx, x1, y1, x2, y2) {
    var headLen = 18;
    var angle = Math.atan2(y2 - y1, x2 - x1);
    ctx.strokeStyle = '#ff3333';
    ctx.fillStyle = '#ff3333';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - headLen * Math.cos(angle - Math.PI / 6), y2 - headLen * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(x2 - headLen * Math.cos(angle + Math.PI / 6), y2 - headLen * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fill();
}

var _textInputActive = false;
function placeTextInput(e, canvas, ctx, saveState) {
    if (_textInputActive) return;
    _textInputActive = true;
    var rect = canvas.getBoundingClientRect();
    var scaleX = canvas.width / rect.width;
    var scaleY = canvas.height / rect.height;
    var x = (e.clientX - rect.left);
    var y = (e.clientY - rect.top);

    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Введите текст...';
    input.style.cssText = 'position:fixed;left:' + (rect.left + x) + 'px;top:' + (rect.top + y - 14) + 'px;background:#222;color:#ff3333;border:2px solid #ff3333;padding:4px 8px;font:bold 18px sans-serif;z-index:10001;min-width:150px;outline:none;border-radius:4px;';
    document.body.appendChild(input);
    // Prevent canvas mousedown from stealing focus
    input.addEventListener('mousedown', function(ev) { ev.stopPropagation(); });

    var committed = false;
    function commitText() {
        if (committed) return;
        committed = true;
        var text = input.value.trim();
        if (text) {
            saveState();
            ctx.font = 'bold 20px sans-serif';
            ctx.fillStyle = '#ff3333';
            ctx.fillText(text, x * scaleX, y * scaleY);
        }
        input.remove();
        _textInputActive = false;
    }

    // Delay focus + blur listener to prevent immediate blur
    setTimeout(function() {
        input.focus();
        input.addEventListener('blur', commitText);
    }, 50);
    input.addEventListener('keydown', function(ev) {
        if (ev.key === 'Enter') commitText();
        if (ev.key === 'Escape') { input.remove(); _textInputActive = false; }
    });
}

function saveAnnotation(annotCanvas) {
    var finalCanvas = document.createElement('canvas');
    finalCanvas.width = annotCanvas.width;
    finalCanvas.height = annotCanvas.height;
    var finalCtx = finalCanvas.getContext('2d');

    var bgUrl = annotCanvas.style.backgroundImage.replace(/url\\(["']?/, '').replace(/["']?\\)/, '');
    var bgImg = new Image();
    bgImg.onload = function() {
        finalCtx.drawImage(bgImg, 0, 0);
        finalCtx.drawImage(annotCanvas, 0, 0);
        var rawDataUrl = finalCanvas.toDataURL('image/png');
        compressScreenshot(rawDataUrl, function(compressed) {
            window._feedbackScreenshotData = compressed;

            var thumb = document.getElementById('feedback-screenshot-thumb');
            thumb.src = compressed;
            thumb.style.display = 'block';

            var hidden = document.getElementById('feedback-screenshot-data');
            hidden.value = compressed;

            var addBtn = document.getElementById('feedback-add-screenshot-btn');
            if (addBtn) addBtn.textContent = 'Change screenshot';

            document.getElementById('annotation-editor-overlay').remove();
            document.getElementById('feedback-modal-box').style.display = 'block';
        });
    };
    bgImg.src = bgUrl;
}
"""


def feedback_modal():
    """Feedback modal dialog for bug reports and suggestions (with screenshot annotation)"""
    return Div(
        # Backdrop
        Div(
            id="feedback-backdrop",
            onclick="closeFeedbackModal()",
            cls="fixed inset-0 bg-black/50 z-[999]",
            style="display: none;"
        ),
        # Modal box
        Div(
            H3("Сообщить о проблеме", cls="font-bold text-lg mb-4"),
            Form(
                # Feedback type
                Div(
                    Label("Тип обращения", cls="label"),
                    Select(
                        Option("Ошибка / Баг", value="bug"),
                        Option("UX/UI", value="ux_ui"),
                        Option("Предложение", value="suggestion"),
                        Option("Вопрос", value="question"),
                        name="feedback_type",
                        cls="select select-bordered w-full"
                    ),
                    cls="form-control mb-3"
                ),
                # Description
                Div(
                    Label("Опишите проблему", cls="label"),
                    Textarea(
                        name="description",
                        placeholder="Что случилось? Что ожидали увидеть?",
                        cls="textarea textarea-bordered w-full h-24",
                        required=True
                    ),
                    cls="form-control mb-3"
                ),
                # Screenshot section
                Div(
                    Div(
                        Button(
                            "Добавить скриншот",
                            id="feedback-add-screenshot-btn",
                            type="button",
                            cls="btn btn-sm btn-outline",
                            onclick="openAnnotationEditor()"
                        ),
                        Button(
                            "Загрузить файл",
                            type="button",
                            cls="btn btn-sm btn-outline",
                            onclick="document.getElementById('feedback-file-upload').click()"
                        ),
                        Input(
                            type="file",
                            id="feedback-file-upload",
                            accept="image/*",
                            style="display:none;",
                            onchange="handleScreenshotUpload(this)"
                        ),
                        cls="flex gap-2"
                    ),
                    # Thumbnail preview (hidden until screenshot taken)
                    Img(
                        id="feedback-screenshot-thumb",
                        src="",
                        style="display:none; max-height:80px; margin-top:8px; border:1px solid #e5e7eb; border-radius:4px; cursor:pointer;",
                        onclick="openAnnotationEditor()"
                    ),
                    cls="form-control mb-3"
                ),
                # Context preview
                Div(
                    P("Автоматически прикрепится:", cls="text-xs text-gray-400 mb-1"),
                    Div(id="feedback-context-preview",
                        cls="text-xs bg-base-200 p-2 rounded max-h-16 overflow-auto font-mono"),
                    cls="form-control mb-4"
                ),
                # Hidden fields
                Input(type="hidden", name="page_url", id="feedback-page-url"),
                Input(type="hidden", name="page_title", id="feedback-page-title"),
                Input(type="hidden", name="debug_context", id="feedback-debug-context"),
                Input(type="hidden", name="screenshot", id="feedback-screenshot-data"),
                # Buttons
                Div(
                    btn("Отправить", variant="primary", icon_name="send", type="submit", full_width=True),
                    btn("Закрыть", variant="ghost", type="button", onclick="closeFeedbackModal()", full_width=True, cls="mt-2"),
                    cls="flex flex-col"
                ),
                hx_post="/api/feedback",
                hx_swap="innerHTML",
                hx_target="#feedback-result",
                **{"hx-on::after-request": "if(document.getElementById('feedback-success-marker')){closeFeedbackModal();showFeedbackToast()}"}
            ),
            Div(id="feedback-result"),
            id="feedback-modal-box",
            cls="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl p-6 z-[1000] w-[90%] max-w-2xl max-h-[90vh] overflow-y-auto",
            style="display: none;"
        ),
        id="feedback-modal"
    )


def feedback_button():
    """Floating feedback button (fixed position, bottom right)"""
    return Div(
        Button(
            I(data_lucide="bug", style="width: 36px; height: 36px;"),
            cls="theme-toggle",  # Exempt from global blue button styling
            style="width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; padding: 0; background: white; border: 1px solid #e5e7eb; border-radius: 0.5rem; color: #6b7280; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.1);",
            onclick="openFeedbackModal()",
            type="button",
            title="Сообщить о проблеме"
        ),
        cls="fixed bottom-4 right-4 z-50"
    )


def page_layout(title, *content, session=None, current_path: str = "", hide_nav: bool = False):
    """Standard page layout wrapper with sidebar navigation and theme support.

    Args:
        title: Page title
        *content: Page content elements
        session: User session data
        current_path: Current path for nav highlighting
        hide_nav: If True, hides sidebar and shows full-width content (for login, etc.)
    """
    # Build body content based on hide_nav flag
    if hide_nav:
        body_content = Body(
            *content,
            # Initialize Lucide icons for standalone pages
            Script("""
                document.addEventListener('DOMContentLoaded', function() {
                    if (typeof lucide !== 'undefined') {
                        lucide.createIcons();
                    }
                });
            """)
        )
    else:
        # Impersonation warning banner
        impersonation_banner = None
        if session and session.get("impersonated_role"):
            imp_role = session["impersonated_role"]
            impersonation_banner = Div(
                Span(f"Вы просматриваете как: {ROLE_LABELS_RU.get(imp_role, imp_role)}"),
                A("✕ Выйти", href="/admin/impersonate/exit",
                  style="margin-left: 12px; color: #92400e; text-decoration: underline; font-weight: 600;"),
                style="background: #fef3c7; color: #92400e; padding: 8px 16px; text-align: center; font-size: 13px; font-weight: 500; position: sticky; top: 0; z-index: 999; border-bottom: 1px solid #fcd34d;"
            )

        body_content = Body(
            *([impersonation_banner] if impersonation_banner else []),
            Div(
                sidebar(session or {}, current_path),
                Main(Div(*content, cls="container"), cls="main-content"),
                cls="app-layout"
            ),
            # Feedback components (floating button + modal)
            feedback_button(),
            feedback_modal()
        )

    return Html(
        Head(
            Title(f"{title} - Kvota"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            # Google Fonts - Inter (optimized for screens, tabular numbers)
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
            Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"),
            # PicoCSS - Modern, semantic CSS framework
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css"),
            # DaisyUI + TailwindCSS - Component library
            Script(src="https://cdn.tailwindcss.com"),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css"),
            # Custom styles (nav, badges, app-specific overrides)
            Style(APP_STYLES),
            # HTMX
            Script(src="https://unpkg.com/htmx.org@1.9.10"),
            # Lucide Icons
            Script(src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"),
            # Handsontable - Excel-like spreadsheet
            Script(src="https://cdn.jsdelivr.net/npm/handsontable/dist/handsontable.full.min.js"),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/handsontable/dist/handsontable.full.min.css"),
            # SheetJS - Excel/CSV file parsing
            Script(src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"),
            # html2canvas - screenshot capture for bug reports
            Script(src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"),
            # Sidebar toggle script
            NotStr(SIDEBAR_JS),
            # Feedback JS (debug context collection)
            Script(FEEDBACK_JS),
            # Annotation editor JS for screenshot feedback
            Script(ANNOTATION_EDITOR_JS),
            # Theme initialization + Lucide icons initialization
            Script("""
                (function() {
                    const savedTheme = localStorage.getItem('theme') || 'light';
                    document.documentElement.setAttribute('data-theme', savedTheme);
                })();
                // Initialize Lucide icons after DOM loaded
                document.addEventListener('DOMContentLoaded', function() {
                    if (typeof lucide !== 'undefined') {
                        lucide.createIcons();
                    }
                    // Also reinitialize after HTMX swaps (must be inside DOMContentLoaded so document.body exists)
                    document.body.addEventListener('htmx:afterSwap', function() {
                        if (typeof lucide !== 'undefined') {
                            lucide.createIcons();
                        }
                    });
                });
            """)
        ),
        body_content,
        data_theme="light"  # Default theme
    )


# ============================================================================
# ICON HELPER
# ============================================================================

def icon(name: str, size: int = 20, cls: str = "", color: str = "", style: str = ""):
    """
    Lucide icon helper - renders an icon using data-lucide attribute.

    Args:
        name: Lucide icon name (e.g., 'layout-dashboard', 'users', 'file-text')
        size: Icon size in pixels (default 20)
        cls: Additional CSS classes
        color: Icon color (e.g., '#64748b', 'red')
        style: Additional inline styles

    Example:
        icon('layout-dashboard')  # Dashboard icon
        icon('users', size=24)    # Users icon, larger
        icon('check', color='#10b981')  # Green check icon

    Common icons mapping (emoji -> Lucide):
        📊 -> layout-dashboard
        📋 -> file-text
        📝 -> plus-circle
        👥 -> users
        🛒 -> shopping-cart
        🏭 -> building-2
        🚚 -> truck
        🛃 -> shield-check
        💰 -> wallet
        ⚙️ -> settings
        🔧 -> wrench
        ✅ -> check-circle
        📑 -> file-stack
        🔑 -> key
    """
    style_parts = [f"width: {size}px; height: {size}px;"]
    if color:
        style_parts.append(f"color: {color};")
    if style:
        style_parts.append(style)

    return I(
        data_lucide=name,
        cls=f"lucide-icon {cls}".strip(),
        style=" ".join(style_parts)
    )


# ============================================================================
# DISMISSIBLE HINT HELPER
# ============================================================================

def dismissible_hint(hint_id: str, *content, variant: str = "info"):
    """
    Render a dismissible hint that can be closed by the user.
    Once dismissed, it won't appear again (stored in localStorage).

    Args:
        hint_id: Unique identifier for the hint (used as localStorage key)
        *content: Content to display inside the hint
        variant: Alert variant ('info', 'success', 'warning', 'error')

    Example:
        dismissible_hint("contacts-editing",
            icon("lightbulb", size=16), " Click on a field to edit it.",
            variant="info"
        )
    """
    element_id = f"hint-{hint_id}"
    storage_key = f"hint_dismissed_{hint_id}"

    # Close button handler: hide element and save to localStorage
    close_handler = f"""
        document.getElementById('{element_id}').style.display = 'none';
        localStorage.setItem('{storage_key}', 'true');
    """

    # Script to check localStorage on load and hide if already dismissed
    init_script = Script(f"""
        (function() {{
            if (localStorage.getItem('{storage_key}') === 'true') {{
                var el = document.getElementById('{element_id}');
                if (el) el.style.display = 'none';
            }}
        }})();
    """)

    return Div(
        Div(
            Div(*content, style="flex: 1;"),
            Span(
                icon("x", size=16),
                onclick=close_handler,
                style="cursor: pointer; padding: 4px; margin: -4px; opacity: 0.6; transition: opacity 0.15s;",
                onmouseover="this.style.opacity='1'",
                onmouseout="this.style.opacity='0.6'",
                title="Скрыть подсказку"
            ),
            style="display: flex; align-items: center; gap: 12px;"
        ),
        init_script,
        id=element_id,
        cls=f"alert alert-{variant}",
        style="margin: 1rem 0;"
    )


# ============================================================================
# STATUS BADGE HELPER (Design System V2)
# ============================================================================

def status_badge_v2(status: str, custom_label: str = None) -> Span:
    """
    Render a polished status badge with gradient background.

    Maps raw workflow status values to styled badges with Russian labels.

    Args:
        status: Raw status value from database (e.g., 'pending_procurement')
        custom_label: Override the default label

    Returns:
        Span element with status-badge-v2 classes

    Example:
        status_badge_v2('pending_procurement')  # Returns amber "Закупки" badge
        status_badge_v2('approved')             # Returns green "Одобрено" badge
    """
    # Status mapping: (Russian label, CSS variant)
    mapping = {
        # Workflow statuses
        'pending_procurement': ('Закупки', 'pending'),
        'pending_logistics': ('Логистика', 'info'),
        'pending_customs': ('Таможня', 'purple'),
        'pending_logistics_and_customs': ('Лог+Там', 'purple'),
        'pending_sales_review': ('Проверка', 'warning'),
        'pending_sales': ('Продажи', 'warning'),
        'pending_review': ('На проверке', 'warning'),
        'pending_control': ('Контроль', 'info'),
        'pending_spec_control': ('Контроль спец', 'info'),

        # Final statuses
        'draft': ('Черновик', 'neutral'),
        'approved': ('Одобрено', 'success'),
        'rejected': ('Отклонено', 'error'),
        'cancelled': ('Отменено', 'neutral'),
        'completed': ('Завершено', 'success'),

        # Quote statuses
        'new': ('Новый', 'info'),
        'sent': ('Отправлено', 'info'),
        'in_progress': ('В работе', 'active'),
        'pending': ('Ожидание', 'pending'),

        # Deal statuses
        'active': ('Активна', 'active'),
        'won': ('Выиграна', 'success'),
        'lost': ('Проиграна', 'error'),

        # Spec statuses
        'spec_draft': ('Черновик', 'neutral'),
        'spec_approved': ('Одобрено', 'success'),
    }

    # Normalize status to lowercase for matching (handles DB values like "Pending_procurement")
    status_lower = (status or '').lower().strip()
    label, variant = mapping.get(status_lower, (status or '—', 'neutral'))

    # Use custom label if provided
    if custom_label:
        label = custom_label

    return Span(label, cls=f"status-badge-v2 status-badge-v2--{variant}")


# ============================================================================
# BUTTON HELPERS (BEM System)
# ============================================================================

def btn(
    label: str,
    variant: str = "primary",
    size: str = None,
    icon_name: str = None,
    icon_right: bool = False,
    full_width: bool = False,
    disabled: bool = False,
    loading: bool = False,
    **kwargs
):
    """
    Standardized button helper using BEM classes.

    Args:
        label: Button text
        variant: 'primary' (gray), 'secondary' (outline), 'success' (green outline),
                 'danger' (red outline), 'ghost' (transparent)
        size: None (default), 'sm' (small), 'lg' (large)
        icon_name: Lucide icon name (e.g., 'check', 'x', 'send')
        icon_right: Place icon on the right side
        full_width: Make button full width
        disabled: Disable the button
        loading: Show loading spinner
        **kwargs: Additional attributes (type, onclick, name, value, etc.)

    Examples:
        btn("Сохранить", variant="primary", icon_name="save")
        btn("Одобрить", variant="success", icon_name="check")
        btn("Удалить", variant="danger", icon_name="trash-2", size="sm")
        btn("Добавить строку", variant="ghost", icon_name="plus")
    """
    # Build class list
    classes = ["btn", f"btn--{variant}"]

    if size:
        classes.append(f"btn--{size}")
    if full_width:
        classes.append("btn--full")
    if disabled:
        classes.append("btn--disabled")
    if loading:
        classes.append("btn--loading")

    # Add any extra classes from kwargs
    if "cls" in kwargs:
        classes.append(kwargs.pop("cls"))

    # Build content
    content = []
    icon_size = 14 if size == "sm" else (18 if size == "lg" else 16)

    if icon_name and not icon_right:
        content.append(icon(icon_name, size=icon_size))

    if label:
        content.append(label)

    if icon_name and icon_right:
        content.append(icon(icon_name, size=icon_size))

    return Button(
        *content,
        cls=" ".join(classes),
        disabled=disabled or loading,
        **kwargs
    )


def btn_link(
    label: str,
    href: str,
    variant: str = "primary",
    size: str = None,
    icon_name: str = None,
    icon_right: bool = False,
    full_width: bool = False,
    disabled: bool = False,
    **kwargs
):
    """
    Standardized link styled as button.

    Args:
        label: Link text
        href: URL to navigate to
        variant: Same as btn()
        size: Same as btn()
        icon_name: Lucide icon name
        icon_right: Place icon on the right side
        full_width: Make button full width
        disabled: Disable the link (adds visual disabled state)
        **kwargs: Additional attributes (target, role, etc.)

    Examples:
        btn_link("Новый КП", href="/quotes/new", icon_name="plus")
        btn_link("Назад", href="/quotes", variant="secondary", icon_name="arrow-left")
    """
    # Build class list
    classes = ["btn", f"btn--{variant}"]

    if size:
        classes.append(f"btn--{size}")
    if full_width:
        classes.append("btn--full")
    if disabled:
        classes.append("btn--disabled")

    # Add any extra classes from kwargs
    if "cls" in kwargs:
        classes.append(kwargs.pop("cls"))

    # Build content
    content = []
    icon_size = 14 if size == "sm" else (18 if size == "lg" else 16)

    if icon_name and not icon_right:
        content.append(icon(icon_name, size=icon_size))

    if label:
        content.append(label)

    if icon_name and icon_right:
        content.append(icon(icon_name, size=icon_size))

    # Set role="button" for proper styling
    return A(
        *content,
        href=href if not disabled else None,
        cls=" ".join(classes),
        role="button",
        **kwargs
    )


def btn_icon(
    icon_name: str,
    variant: str = "ghost",
    size: str = None,
    title: str = None,
    disabled: bool = False,
    **kwargs
):
    """
    Icon-only button (square).

    Args:
        icon_name: Lucide icon name
        variant: Same as btn() (default 'ghost' for toolbar icons)
        size: None (default 2.25rem) or 'sm' (1.75rem)
        title: Tooltip text
        disabled: Disable the button
        **kwargs: Additional attributes

    Examples:
        btn_icon("trash-2", variant="danger", title="Удалить")
        btn_icon("edit", title="Редактировать")
        btn_icon("eye", title="Просмотр", size="sm")
    """
    # Build class list
    classes = ["btn", f"btn--{variant}", "btn--icon-only"]

    if size:
        classes.append(f"btn--{size}")
    if disabled:
        classes.append("btn--disabled")

    # Add any extra classes from kwargs
    if "cls" in kwargs:
        classes.append(kwargs.pop("cls"))

    icon_size = 14 if size == "sm" else 18

    return Button(
        icon(icon_name, size=icon_size),
        cls=" ".join(classes),
        title=title,
        disabled=disabled,
        **kwargs
    )


# ============================================================================
# DAISYUI COMPONENT HELPERS
# ============================================================================

def tab_nav(tabs: list, active_tab: str = None, target_id: str = "tab-content"):
    """
    DaisyUI tab navigation with HTMX integration

    Args:
        tabs: List of dicts with {'id': str, 'label': str, 'url': str, 'icon': str (optional)}
        active_tab: ID of the currently active tab
        target_id: HTMX target element ID for tab content

    Example:
        tab_nav([
            {'id': 'general', 'label': 'Общая информация', 'url': '/customers/123/tab/general', 'icon': 'info'},
            {'id': 'addresses', 'label': 'Адреса', 'url': '/customers/123/tab/addresses', 'icon': 'map-pin'}
        ], active_tab='general')
    """
    def render_tab(tab):
        tab_icon = tab.get("icon")
        content = [icon(tab_icon, size=16, cls="tab-icon"), Span(tab["label"])] if tab_icon else [tab["label"]]
        return A(
            *content,
            href=tab.get("url", "#"),
            cls=f"tab tab-lifted {'tab-active' if tab['id'] == active_tab else ''}",
            style="display: inline-flex; align-items: center; gap: 0.375rem;" if tab_icon else None,
            hx_get=tab.get("url") if tab.get("url") and tab.get("url") != "#" else None,
            hx_target=f"#{target_id}" if tab.get("url") and tab.get("url") != "#" else None,
            hx_swap="innerHTML scroll:false",
            hx_push_url="true" if tab.get("url") and tab.get("url") != "#" else None,
            onclick="switchTab(this)"
        )

    return Div(
        *[render_tab(tab) for tab in tabs],
        role="tablist",
        cls="tabs tabs-lifted"
    )


def page_heading(text: str, icon_name: str = None, level: int = 1, **kwargs):
    """
    Page heading with optional Lucide icon.

    Args:
        text: Heading text
        icon_name: Lucide icon name (e.g., 'inbox', 'users', 'truck')
        level: Heading level (1=H1, 2=H2, 3=H3)
        **kwargs: Additional attributes (style, cls, etc.)

    Example:
        page_heading("Мои задачи", icon_name="inbox")
        page_heading("Закупки", icon_name="shopping-cart", level=2)
    """
    # Choose heading tag based on level
    heading_tags = {1: H1, 2: H2, 3: H3, 4: H4}
    HeadingTag = heading_tags.get(level, H1)

    # Icon sizes based on heading level
    icon_sizes = {1: 28, 2: 24, 3: 20, 4: 18}
    icon_size = icon_sizes.get(level, 24)

    # Build content
    if icon_name:
        # Merge styles
        style = kwargs.pop('style', '') or ''
        default_style = "display: flex; align-items: center; gap: 0.5rem;"
        combined_style = f"{default_style} {style}".strip()

        return HeadingTag(
            icon(icon_name, size=icon_size, cls="heading-icon"),
            Span(text),
            style=combined_style,
            **kwargs
        )
    else:
        return HeadingTag(text, **kwargs)


def badge(text: str, type: str = "neutral", size: str = "md"):
    """
    DaisyUI badge component

    Args:
        text: Badge text
        type: Badge color - 'neutral', 'primary', 'secondary', 'accent', 'success', 'warning', 'error', 'info'
        size: Badge size - 'xs', 'sm', 'md', 'lg'

    Example:
        badge("Активен", type="success")
        badge("Админ", type="error", size="sm")
    """
    type_class = f"badge-{type}" if type != "neutral" else ""
    size_class = f"badge-{size}" if size != "md" else ""
    return Span(text, cls=f"badge {type_class} {size_class}".strip())


def stat_card(value: str, label: str, description: str = None, icon: str = None):
    """
    DaisyUI stat card for dashboard statistics

    Args:
        value: Main value to display (large text)
        label: Label above the value
        description: Optional description below the value
        icon: Optional emoji or icon

    Example:
        stat_card(value="₽38,620", label="Выручка", description="Одобренные КП")
    """
    return Div(
        Div(icon, cls="stat-figure text-4xl") if icon else None,
        Div(label, cls="stat-title"),
        Div(value, cls="stat-value text-primary"),
        Div(description, cls="stat-desc") if description else None,
        cls="stat"
    )


def modal_dialog(id: str, title: str, content, actions=None):
    """
    DaisyUI modal dialog

    Args:
        id: Modal ID for targeting
        title: Modal title
        content: Modal body content (can be Div, Form, etc.)
        actions: Optional list of button elements for modal actions

    Example:
        modal_dialog(
            id="delete-confirm",
            title="Подтвердите удаление",
            content=P("Вы уверены, что хотите удалить этот элемент?"),
            actions=[
                btn("Отмена", variant="secondary", onclick="document.getElementById('delete-confirm').close()"),
                btn("Удалить", variant="danger", icon_name="trash-2")
            ]
        )
    """
    return Div(
        Div(
            Div(
                H3(title, cls="font-bold text-lg"),
                content,
                Div(
                    *actions if actions else [],
                    cls="modal-action"
                ) if actions else None,
                cls="modal-box"
            ),
            Form(method="dialog", cls="modal-backdrop"),
            cls="modal-content"
        ),
        id=id,
        cls="modal"
    )


def require_login(session):
    """Check if user is logged in"""
    if not session.get("user"):
        return RedirectResponse("/login", status_code=303)
    return None


def user_has_role(session, role_code: str) -> bool:
    """
    Check if logged-in user has a specific role (from session cache).

    This function checks the roles stored in the session at login time,
    avoiding database queries for role checks.

    Args:
        session: Session dict containing user info
        role_code: Role code to check for (e.g., 'admin', 'sales')

    Returns:
        True if user has the role, False otherwise

    Example:
        if user_has_role(session, 'admin'):
            # Show admin controls
            pass
    """
    user = session.get("user")
    if not user:
        return False
    roles = user.get("roles", [])
    return role_code in roles


def user_has_any_role(session, role_codes: list) -> bool:
    """
    Check if logged-in user has any of the specified roles (from session cache).

    Args:
        session: Session dict containing user info
        role_codes: List of role codes to check for

    Returns:
        True if user has at least one of the roles, False otherwise

    Example:
        if user_has_any_role(session, ['admin', 'finance']):
            # Show financial controls
            pass
    """
    user = session.get("user")
    if not user:
        return False

    # Check impersonation mode first (admin testing feature)
    impersonated_role = session.get("impersonated_role")
    if impersonated_role:
        return impersonated_role in role_codes

    roles = user.get("roles", [])
    return any(code in roles for code in role_codes)


def get_effective_roles(session) -> list:
    """
    Get the effective role list respecting admin impersonation.

    If impersonated_role is set in session, returns [impersonated_role].
    Otherwise returns the real roles from session cache.
    Falls back to DB lookup via get_user_role_codes if session has no cached roles.

    Use this for page content filtering (tasks, dashboard tabs, etc.).
    Do NOT use for admin panel routes -- those must always use real roles.
    """
    impersonated_role = session.get("impersonated_role")
    if impersonated_role:
        return [impersonated_role]

    user = session.get("user")
    if not user:
        return []

    # Try session-cached roles first
    roles = user.get("roles", [])
    if roles:
        return roles

    # Fallback to DB lookup
    user_id = user.get("id")
    org_id = user.get("org_id")
    if user_id and org_id:
        return get_user_role_codes(user_id, org_id)
    return []


def get_user_roles_from_session(session) -> list:
    """
    Get role codes for the logged-in user from session cache.

    Args:
        session: Session dict containing user info

    Returns:
        List of role codes, or empty list if not logged in
    """
    user = session.get("user")
    if not user:
        return []
    return user.get("roles", [])


def format_money(value, currency="RUB"):
    """Format money value. Returns dash for None or zero."""
    if value is None or value == 0:
        return "—"
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{value:,.0f}"


def profit_color(value):
    """Return CSS color for profit value: green for positive, gray for zero/None, red for negative."""
    v = float(value or 0)
    if v > 0:
        return "#059669"
    elif v < 0:
        return "#dc2626"
    return "#9ca3af"


def profit_cell(value, currency="USD"):
    """Render a profit table cell with conditional coloring: green for positive, gray for zero, red for negative."""
    return Td(format_money(value, currency), cls="col-money",
              style=f"color: {profit_color(value)}; font-weight: 500;")


def build_export_filename(doc_type: str, customer_name: str, quote_number: str, ext: str = "pdf") -> str:
    """
    Build human-readable export filename.

    Format: {doc_type}_{company}_{date}_{number}.{ext}
    Example: invoice_AcmeCorp_2024-02-02_44.pdf

    Args:
        doc_type: Document type (invoice, specification, etc.)
        customer_name: Customer/company name
        quote_number: Full quote number like "КП-2024-044"
        ext: File extension (pdf, xlsx)

    Returns:
        Safe ASCII filename string
    """
    import re
    from datetime import date

    # Cyrillic to Latin transliteration map
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    }

    def transliterate(text):
        return ''.join(translit_map.get(c, c) for c in text)

    # Extract numeric suffix from quote number (e.g., "044" from "КП-2024-044")
    number_match = re.search(r'(\d+)$', quote_number or '')
    short_number = number_match.group(1).lstrip('0') or '0' if number_match else '0'

    # Sanitize company name
    safe_name = customer_name or "Unknown"
    # Remove common legal suffixes to shorten
    safe_name = re.sub(r'\s*(ООО|ОАО|ЗАО|ИП|LLC|Inc|Ltd|Corp)\.?\s*', '', safe_name, flags=re.IGNORECASE)
    # Transliterate Cyrillic to Latin
    safe_name = transliterate(safe_name)
    # Keep only ASCII alphanumeric and some safe chars
    safe_name = re.sub(r'[^a-zA-Z0-9\s-]', '', safe_name)
    # Replace spaces with nothing (CamelCase style)
    safe_name = safe_name.replace(' ', '')
    # Truncate if too long
    safe_name = safe_name[:30] if len(safe_name) > 30 else safe_name
    # Fallback if empty after sanitization
    safe_name = safe_name or "Company"

    # Today's date
    today = date.today().isoformat()

    return f"{doc_type}_{safe_name}_{today}_{short_number}.{ext}"


def status_badge(status):
    """Status badge component with DaisyUI styling"""
    # Map old status classes to DaisyUI badge types
    type_map = {
        "draft": "warning",
        "sent": "info",
        "approved": "success",
        "rejected": "error"
    }
    badge_type = type_map.get(status, "neutral")
    return badge(status.capitalize(), type=badge_type)


# ============================================================================
# AUTH ROUTES
# ============================================================================

@rt("/")
def get(session):
    if session.get("user"):
        return RedirectResponse("/tasks", status_code=303)  # New primary entry point
    return RedirectResponse("/login", status_code=303)


@rt("/login")
def get(session):
    if session.get("user"):
        return RedirectResponse("/dashboard", status_code=303)

    # Design system styles for login page
    login_card_style = """
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
        padding: 40px;
        max-width: 420px;
        margin: 0 auto;
    """

    logo_section_style = """
        text-align: center;
        margin-bottom: 32px;
    """

    logo_icon_style = """
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        border-radius: 14px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    """

    title_style = """
        font-size: 24px;
        font-weight: 700;
        color: #1e293b;
        margin: 0 0 6px 0;
        letter-spacing: -0.02em;
    """

    subtitle_style = """
        font-size: 14px;
        color: #64748b;
        margin: 0;
    """

    label_style = """
        display: block;
        font-size: 11px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    """

    input_style = """
        width: 100%;
        padding: 12px 14px;
        font-size: 14px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: #f8fafc;
        color: #1e293b;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
        box-sizing: border-box;
    """

    input_group_style = "margin-bottom: 20px;"

    submit_btn_style = """
        width: 100%;
        padding: 14px 20px;
        font-size: 15px;
        font-weight: 600;
        color: white;
        background: #3b82f6;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-top: 28px;
        transition: background-color 0.15s ease;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    """

    page_bg_style = """
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
    """

    return page_layout("Вход — OneStack",
        Div(
            Div(
                # Logo section
                Div(
                    Div(
                        icon("layers", size=28, style="color: white;"),
                        style=logo_icon_style
                    ),
                    H1("OneStack", style=title_style),
                    P("Система управления коммерческими предложениями", style=subtitle_style),
                    style=logo_section_style
                ),

                # Form
                Form(
                    # Email field
                    Div(
                        Label("Электронная почта", style=label_style, **{"for": "email"}),
                        Input(
                            name="email",
                            type="email",
                            id="email",
                            placeholder="your@email.com",
                            required=True,
                            style=input_style
                        ),
                        style=input_group_style
                    ),
                    # Password field
                    Div(
                        Label("Пароль", style=label_style, **{"for": "password"}),
                        Input(
                            name="password",
                            type="password",
                            id="password",
                            required=True,
                            style=input_style
                        ),
                        style=input_group_style
                    ),
                    # Submit button
                    Button(
                        icon("log-in", size=18),
                        Span("Войти в систему"),
                        type="submit",
                        style=submit_btn_style
                    ),
                    method="post",
                    action="/login"
                ),
                style=login_card_style
            ),
            style=page_bg_style
        ),
        session=session,
        hide_nav=True
    )


@rt("/login")
def post(email: str, password: str, session):
    """Authenticate with Supabase"""
    try:
        # Use anon client for auth
        client = get_anon_client()
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user:
            # Get user's organization
            supabase = get_supabase()
            org_result = supabase.table("organization_members") \
                .select("organization_id, organizations(id, name)") \
                .eq("user_id", response.user.id) \
                .eq("status", "active") \
                .limit(1) \
                .execute()

            org_data = org_result.data[0] if org_result.data else None
            org_id = org_data["organization_id"] if org_data else None

            # Get user's roles in the organization
            user_roles = []
            if org_id:
                user_roles = get_user_role_codes(response.user.id, org_id)

            # training_manager is a super-role for demos — grant all permissions
            if "training_manager" in user_roles:
                all_roles = ["admin", "sales", "procurement", "logistics", "customs",
                             "quote_controller", "spec_controller", "finance",
                             "top_manager", "head_of_sales", "head_of_procurement",
                             "head_of_logistics", "training_manager"]
                user_roles = list(set(user_roles + all_roles))

            session["user"] = {
                "id": response.user.id,
                "email": response.user.email,
                "org_id": org_id,
                "org_name": org_data["organizations"]["name"] if org_data else "No Organization",
                "roles": user_roles  # List of role codes: ['sales', 'admin', etc.]
            }
            session["access_token"] = response.session.access_token

            return RedirectResponse("/dashboard", status_code=303)

    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            error_msg = "Неверный email или пароль"

        # Design system styles for login page (same as GET)
        login_card_style = """
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
            padding: 40px;
            max-width: 420px;
            margin: 0 auto;
        """

        logo_section_style = """
            text-align: center;
            margin-bottom: 32px;
        """

        logo_icon_style = """
            width: 56px;
            height: 56px;
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            border-radius: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        """

        title_style = """
            font-size: 24px;
            font-weight: 700;
            color: #1e293b;
            margin: 0 0 6px 0;
            letter-spacing: -0.02em;
        """

        subtitle_style = """
            font-size: 14px;
            color: #64748b;
            margin: 0;
        """

        label_style = """
            display: block;
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        """

        input_style = """
            width: 100%;
            padding: 12px 14px;
            font-size: 14px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #f8fafc;
            color: #1e293b;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
            box-sizing: border-box;
        """

        input_group_style = "margin-bottom: 20px;"

        submit_btn_style = """
            width: 100%;
            padding: 14px 20px;
            font-size: 15px;
            font-weight: 600;
            color: white;
            background: #3b82f6;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-top: 28px;
            transition: background-color 0.15s ease;
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        """

        page_bg_style = """
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
        """

        error_alert_style = """
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 14px 16px;
            background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
            border: 1px solid #fecaca;
            border-radius: 10px;
            color: #dc2626;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 24px;
        """

        return page_layout("Вход — OneStack",
            Div(
                Div(
                    # Logo section
                    Div(
                        Div(
                            icon("layers", size=28, style="color: white;"),
                            style=logo_icon_style
                        ),
                        H1("OneStack", style=title_style),
                        P("Система управления коммерческими предложениями", style=subtitle_style),
                        style=logo_section_style
                    ),

                    # Error alert
                    Div(
                        icon("alert-circle", size=18),
                        Span(error_msg),
                        style=error_alert_style
                    ),

                    # Form
                    Form(
                        # Email field
                        Div(
                            Label("Электронная почта", style=label_style, **{"for": "email"}),
                            Input(
                                name="email",
                                type="email",
                                id="email",
                                value=email,
                                required=True,
                                style=input_style
                            ),
                            style=input_group_style
                        ),
                        # Password field
                        Div(
                            Label("Пароль", style=label_style, **{"for": "password"}),
                            Input(
                                name="password",
                                type="password",
                                id="password",
                                required=True,
                                style=input_style
                            ),
                            style=input_group_style
                        ),
                        # Submit button
                        Button(
                            icon("log-in", size=18),
                            Span("Войти в систему"),
                            type="submit",
                            style=submit_btn_style
                        ),
                        method="post",
                        action="/login"
                    ),
                    style=login_card_style
                ),
                style=page_bg_style
            ),
            session=session,
            hide_nav=True
        )


@rt("/logout")
def get(session):
    session.clear()
    return RedirectResponse("/login", status_code=303)


@rt("/unauthorized")
def get(session):
    """Page shown when user doesn't have required role"""
    # Design system styles
    card_style = """
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        padding: 48px 40px;
        max-width: 480px;
        margin: 0 auto;
        text-align: center;
    """

    icon_container_style = """
        width: 72px;
        height: 72px;
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border-radius: 20px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 24px;
        border: 1px solid #fecaca;
    """

    title_style = """
        font-size: 22px;
        font-weight: 700;
        color: #1e293b;
        margin: 0 0 12px 0;
        letter-spacing: -0.02em;
    """

    text_style = """
        font-size: 14px;
        color: #64748b;
        margin: 0 0 8px 0;
        line-height: 1.6;
    """

    btn_style = """
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        font-size: 14px;
        font-weight: 600;
        color: #374151;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        text-decoration: none;
        margin-top: 24px;
        transition: background-color 0.15s ease, border-color 0.15s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    """

    page_bg_style = """
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
    """

    return page_layout("Доступ запрещён — OneStack",
        Div(
            Div(
                # Error icon
                Div(
                    icon("shield-x", size=36, style="color: #dc2626;"),
                    style=icon_container_style
                ),
                # Title
                H1("Доступ запрещён", style=title_style),
                # Description
                P("У вас нет прав для доступа к этой странице.", style=text_style),
                P("Обратитесь к администратору, если считаете это ошибкой.", style=text_style),
                # Back button
                A(
                    icon("arrow-left", size=16),
                    Span("Вернуться на главную"),
                    href="/tasks",
                    style=btn_style
                ),
                style=card_style
            ),
            style=page_bg_style
        ),
        session=session,
        hide_nav=True
    )


# ============================================================================
# QUOTES LIST
# ============================================================================

def version_badge(quote_id, current_ver, total_count):
    """Render version badge for quotes list. Clickable if multiple versions."""
    if total_count <= 1:
        return Span(f"v{current_ver}", style="color: #94a3b8; font-size: 12px;")

    badge_style = """
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        color: #0369a1;
        border: 1px solid #bae6fd;
        text-decoration: none;
        transition: background-color 0.15s ease, color 0.15s ease;
    """
    return A(
        f"v{current_ver}",
        Span(f"({total_count})", style="opacity: 0.7; margin-left: 4px;"),
        href=f"/quotes/{quote_id}/versions",
        style=badge_style,
        title="Посмотреть историю версий",
        onclick="event.stopPropagation();"
    )


def _lookup_deal_for_quote(quote_id: str, org_id: str):
    """
    Look up the deal associated with a quote via the FK chain:
    quote_id -> specifications.quote_id -> deals.specification_id

    Returns the deal dict with nested specs/quotes if found, or None.
    """
    supabase = get_supabase()
    try:
        # First find the specification for this quote
        spec_result = supabase.table("specifications") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .limit(1) \
            .is_("deleted_at", None) \
            .execute()
        if not spec_result.data:
            return None

        spec_id = spec_result.data[0]["id"]

        # Then find the deal for this specification
        deal_result = supabase.table("deals").select(
            # FK hints resolve ambiguity: !specifications(deals_specification_id_fkey), !quotes(deals_quote_id_fkey)
            "id, deal_number, signed_at, total_amount, currency, status, created_at, "
            "specifications!deals_specification_id_fkey(id, specification_number, proposal_idn, sign_date, validity_period, "
            "  specification_currency, exchange_rate_to_ruble, client_payment_terms, "
            "  our_legal_entity, client_legal_entity), "
            "quotes!deals_quote_id_fkey(id, idn_quote, customers(name))"
        ).eq("specification_id", spec_id).eq("organization_id", org_id).limit(1).is_("deleted_at", None).execute()

        if deal_result.data:
            return deal_result.data[0]
        return None
    except Exception as e:
        print(f"Error looking up deal for quote {quote_id}: {e}")
        return None


def _calculate_quotes_stage_stats(quotes: list) -> dict:
    """
    Group quotes by workflow_status stage and calculate count + total sum per stage.
    Returns dict keyed by stage group with {count, sum, label, icon_name, color} values.

    All workflow statuses are mapped to logical groups so no quotes are silently dropped:
      - draft
      - pending_procurement
      - logistics: pending_logistics, pending_customs, pending_logistics_and_customs
      - control: pending_quote_control, pending_sales_review, pending_approval
      - pending_spec_control
      - client: sent_to_client, client_negotiation, pending_signature
      - approved
      - deal
      - closed: rejected, cancelled
    """
    stage_groups = {
        "draft": {
            "statuses": ["draft"],
            "label": "Черновик", "icon_name": "file-edit",
            "color": "#6b7280", "bg": "#f3f4f6", "border": "#d1d5db",
        },
        "pending_procurement": {
            "statuses": ["pending_procurement"],
            "label": "Закупки", "icon_name": "shopping-cart",
            "color": "#d97706", "bg": "#fffbeb", "border": "#fcd34d",
        },
        "logistics": {
            "statuses": ["pending_logistics", "pending_customs", "pending_logistics_and_customs"],
            "label": "Лог+Там", "icon_name": "truck",
            "color": "#2563eb", "bg": "#eff6ff", "border": "#93c5fd",
        },
        "control": {
            "statuses": ["pending_quote_control", "pending_sales_review", "pending_approval"],
            "label": "Контроль", "icon_name": "clipboard-check",
            "color": "#ea580c", "bg": "#fff7ed", "border": "#fdba74",
        },
        "pending_spec_control": {
            "statuses": ["pending_spec_control"],
            "label": "Проверка", "icon_name": "search",
            "color": "#0891b2", "bg": "#ecfeff", "border": "#67e8f9",
        },
        "client": {
            "statuses": ["sent_to_client", "client_negotiation", "pending_signature"],
            "label": "Клиент", "icon_name": "send",
            "color": "#0d9488", "bg": "#f0fdfa", "border": "#99f6e4",
        },
        "approved": {
            "statuses": ["approved"],
            "label": "Согласован", "icon_name": "check-circle",
            "color": "#059669", "bg": "#ecfdf5", "border": "#6ee7b7",
        },
        "deal": {
            "statuses": ["deal"],
            "label": "Сделка", "icon_name": "briefcase",
            "color": "#16a34a", "bg": "#f0fdf4", "border": "#86efac",
        },
        "closed": {
            "statuses": ["rejected", "cancelled"],
            "label": "Закрыт", "icon_name": "x-circle",
            "color": "#dc2626", "bg": "#fef2f2", "border": "#fecaca",
        },
    }
    stats = {}
    for group_key, cfg in stage_groups.items():
        matched_statuses = set(cfg["statuses"])
        group_quotes = [q for q in quotes if q.get("workflow_status") in matched_statuses]
        total_sum = sum(float(q.get("total_amount") or 0) for q in group_quotes)
        stats[group_key] = {
            "count": len(group_quotes),
            "sum": total_sum,
            "label": cfg["label"],
            "icon_name": cfg["icon_name"],
            "color": cfg["color"],
            "bg": cfg["bg"],
            "border": cfg["border"],
        }
    return stats


@rt("/quotes")
def get(session, status: str = "", customer_id: str = "", manager_id: str = ""):
    """
    Quotes List page — redesigned with summary stage blocks and compact table.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = get_effective_roles(session)
    # is_sales_only: user has sales role but NOT admin/top_manager/head_of_sales (full visibility)
    has_sales_role = any(r in roles for r in ["sales", "sales_manager"])
    has_full_visibility = any(r in roles for r in ["admin", "top_manager", "head_of_sales"])
    is_sales_only = has_sales_role and not has_full_visibility

    supabase = get_supabase()

    _select = "id, idn_quote, customer_id, customers!customer_id(name, id), workflow_status, total_amount, total_profit_usd, currency, created_at, created_by, quote_versions!quote_versions_quote_id_fkey(version)"

    if is_sales_only:
        # Sales users see quotes for their assigned customers only
        my_customers = supabase.table("customers") \
            .select("id") \
            .eq("organization_id", user["org_id"]) \
            .eq("manager_id", user["id"]) \
            .execute()
        my_customer_ids = [c["id"] for c in (my_customers.data or [])]

        if my_customer_ids:
            result = supabase.table("quotes") \
                .select(_select) \
                .eq("organization_id", user["org_id"]) \
                .in_("customer_id", my_customer_ids) \
                .is_("deleted_at", None) \
                .order("created_at", desc=True) \
                .execute()
        else:
            result = type('Result', (), {'data': []})()
    else:
        result = supabase.table("quotes") \
            .select(_select) \
            .eq("organization_id", user["org_id"]) \
            .is_("deleted_at", None) \
            .order("created_at", desc=True) \
            .execute()

    quotes = result.data or []

    # Process version data for each quote
    for q in quotes:
        versions = q.get("quote_versions") or []
        q["version_count"] = len(versions)
        q["current_version"] = max([v.get("version", 1) for v in versions]) if versions else 1

    # Calculate stage stats for summary blocks (uses UNFILTERED quotes)
    stage_stats = _calculate_quotes_stage_stats(quotes)

    # --- Fetch dropdown data for filters ---
    # Customers list for filter dropdown (sales users see only their assigned customers)
    try:
        cust_query = supabase.table("customers") \
            .select("id, name") \
            .eq("organization_id", user["org_id"])
        if is_sales_only:
            cust_query = cust_query.eq("manager_id", user["id"])
        customers_list = cust_query.order("name").execute().data or []
    except Exception:
        customers_list = []

    # Manager names from distinct created_by values in quotes (for filter + table column)
    managers = []
    creator_ids = list(set(q.get("created_by") for q in quotes if q.get("created_by")))
    manager_names = {}
    if creator_ids:
        try:
            profiles_result = supabase.table("profiles") \
                .select("id, full_name") \
                .in_("id", creator_ids) \
                .order("full_name") \
                .execute()
            managers = profiles_result.data or []
            manager_names = {m["id"]: m.get("full_name", "—") for m in managers}
        except Exception:
            managers = []

    # --- Python-side filtering ---
    filtered_quotes = list(quotes)
    if status:
        filtered_quotes = [q for q in filtered_quotes if q.get("workflow_status") == status]
    if customer_id:
        filtered_quotes = [q for q in filtered_quotes if q.get("customer_id") == customer_id]
    if manager_id:
        filtered_quotes = [q for q in filtered_quotes if q.get("created_by") == manager_id]

    # --- Build filter bar ---
    any_filter_active = bool(status or customer_id or manager_id)

    status_options = [
        Option("Все статусы", value="", selected=(status == "")),
        Option("Черновик", value="draft", selected=(status == "draft")),
        Option("Закупки", value="pending_procurement", selected=(status == "pending_procurement")),
        Option("Логистика", value="pending_logistics", selected=(status == "pending_logistics")),
        Option("Таможня", value="pending_customs", selected=(status == "pending_customs")),
        Option("Контроль КП", value="pending_quote_control", selected=(status == "pending_quote_control")),
        Option("Контроль спец.", value="pending_spec_control", selected=(status == "pending_spec_control")),
        Option("Ревизия", value="pending_sales_review", selected=(status == "pending_sales_review")),
        Option("Согласование", value="pending_approval", selected=(status == "pending_approval")),
        Option("Одобрено", value="approved", selected=(status == "approved")),
        Option("Отправлено", value="sent_to_client", selected=(status == "sent_to_client")),
        Option("Сделка", value="deal", selected=(status == "deal")),
        Option("Отклонено", value="rejected", selected=(status == "rejected")),
        Option("Отменено", value="cancelled", selected=(status == "cancelled")),
    ]

    customer_options = [Option("Все клиенты", value="")]
    for c in customers_list:
        customer_options.append(
            Option(c.get("name", "—"), value=c.get("id", ""), selected=(customer_id == c.get("id", "")))
        )

    manager_select = None
    if not is_sales_only:
        manager_opts = [Option("Все менеджеры", value="", selected=(manager_id == ""))]
        for m in managers:
            manager_opts.append(
                Option(m.get("full_name", "—"), value=m.get("id", ""), selected=(manager_id == m.get("id", "")))
            )
        manager_select = Select(
            *manager_opts,
            name="manager_id",
            style="padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white; flex: 1; min-width: 120px; max-width: 250px;",
            onchange="this.form.submit()",
        )

    reset_link = None
    if any_filter_active:
        reset_link = A(
            "Сбросить",
            href="/quotes",
            style="display: inline-flex; align-items: center; padding: 6px 10px; font-size: 12px; color: #64748b; text-decoration: none; border: 1px solid #e2e8f0; border-radius: 6px; background: white; white-space: nowrap;",
        )

    _filter_select_style = "padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white; flex: 1; min-width: 120px; max-width: 250px;"
    filter_bar = Form(
        Select(
            *status_options,
            name="status",
            style=_filter_select_style,
            onchange="this.form.submit()",
        ),
        Select(
            *customer_options,
            name="customer_id",
            style=_filter_select_style,
            onchange="this.form.submit()",
        ),
        manager_select,
        reset_link,
        method="get",
        action="/quotes",
        style="display: flex; flex-wrap: nowrap; gap: 8px; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; align-items: center;",
    )

    # -- Styles --
    header_card_style = (
        "background: #fafbfc;"
        "border-radius: 12px; border: 1px solid #e2e8f0;"
        "padding: 16px 24px; margin-bottom: 16px;"
        "display: flex; justify-content: space-between; align-items: center;"
        "flex-wrap: wrap; gap: 12px;"
    )
    page_title_style = (
        "display: flex; align-items: center; gap: 12px;"
        "margin: 0; font-size: 20px; font-weight: 700;"
        "color: #1e293b; letter-spacing: -0.02em;"
    )
    count_badge_style = (
        "display: inline-flex; align-items: center;"
        "padding: 3px 10px; border-radius: 9999px;"
        "font-size: 12px; font-weight: 600;"
        "background: #dbeafe;"
        "color: #1e40af; border: 1px solid #bfdbfe;"
    )
    new_btn_style = (
        "display: inline-flex; align-items: center; gap: 8px;"
        "padding: 8px 16px; font-size: 13px; font-weight: 600;"
        "color: white; background: #3b82f6;"
        "border: none; border-radius: 8px; text-decoration: none;"
    )

    # Build summary stage cards
    stage_card_style_tpl = (
        "display: flex; flex-direction: column; align-items: center; gap: 2px;"
        "padding: 10px 6px; border-radius: 10px; min-width: 80px; flex: 1;"
        "border: 1px solid {border}; background: {bg};"
        "transition: transform 0.15s ease, box-shadow 0.15s ease; cursor: default;"
    )
    stage_cards = []
    for stage_key in ["draft", "pending_procurement", "logistics", "control", "pending_spec_control", "client", "approved", "deal", "closed"]:
        s = stage_stats[stage_key]
        card_style = stage_card_style_tpl.format(border=s["border"], bg=s["bg"])
        stage_cards.append(
            Div(
                Div(
                    icon(s["icon_name"], size=16, style=f"color: {s['color']};"),
                    Span(s["label"], style=f"font-size: 11px; font-weight: 600; color: {s['color']}; text-transform: uppercase; letter-spacing: 0.03em;"),
                    style="display: flex; align-items: center; gap: 4px;"
                ),
                Div(str(s["count"]), style=f"font-size: 22px; font-weight: 700; color: {s['color']}; line-height: 1.2;"),
                Div(
                    format_money(s["sum"]) if s["sum"] else "—",
                    style="font-size: 11px; color: #64748b; font-weight: 500;"
                ),
                style=card_style,
            )
        )

    summary_grid = Div(
        *stage_cards,
        style="display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; margin-bottom: 16px;",
    )

    # Build table rows (uses filtered_quotes for display)
    table_rows = []
    for q in filtered_quotes:
        customer_name = (q.get("customers") or {}).get("name", "—")
        cust_id = (q.get("customers") or {}).get("id")
        created_date = format_date_russian(q.get("created_at")) if q.get("created_at") else "—"
        idn_label = q.get("idn_quote", f"#{q['id'][:8]}")
        quote_currency = q.get("currency", "RUB")

        customer_cell = (
            A(customer_name, href=f"/customers/{cust_id}",
              style="color: #1e293b; text-decoration: none; font-weight: 500;",
              onclick="event.stopPropagation();")
            if cust_id else Span(customer_name, style="color: #94a3b8;")
        )

        manager_name = manager_names.get(q.get("created_by"), "—")

        _cell = "padding: 8px 12px; font-size: 13px;"
        table_rows.append(Tr(
            Td(created_date, style=f"{_cell} color: #64748b; white-space: nowrap;"),
            Td(
                A(idn_label, href=f"/quotes/{q['id']}",
                  style="font-weight: 600; color: #3b82f6; text-decoration: none;",
                  onclick="event.stopPropagation();"),
                style=_cell
            ),
            Td(customer_cell, style=_cell),
            Td(manager_name, style=f"{_cell} color: #374151;"),
            Td(workflow_status_badge(q.get("workflow_status", "draft")), style=_cell),
            Td(version_badge(q['id'], q.get('current_version', 1), q.get('version_count', 1)),
               style=f"{_cell} text-align: center;"),
            Td(format_money(q.get("total_amount"), quote_currency), cls="col-money",
               style=_cell),
            Td(format_money(q.get("total_profit_usd"), "USD"), cls="col-money",
               style=f"{_cell} color: {profit_color(q.get('total_profit_usd'))}; font-weight: 500;"),
            cls="clickable-row",
            onclick=f"window.location='/quotes/{q['id']}'"
        ))

    return page_layout("Коммерческие предложения",
        # Header card with title and actions
        Div(
            Div(
                icon("file-text", size=22, style="color: #3b82f6;"),
                H1("Коммерческие предложения", style=page_title_style),
                Span(f"{len(filtered_quotes)}", style=count_badge_style),
                style="display: flex; align-items: center; gap: 12px;"
            ),
            Div(
                A(
                    icon("plus", size=14),
                    Span("Новое КП"),
                    href="/quotes/new",
                    style=new_btn_style,
                    cls="btn",
                ),
            ),
            style=header_card_style
        ),

        # Summary stage blocks
        summary_grid,

        # Filter bar
        filter_bar,

        # Table content with compact styling
        Div(
            Div(
                Table(
                    Thead(Tr(
                        Th("Дата", style="padding: 10px 12px;"),
                        Th("IDN", style="padding: 10px 12px;"),
                        Th("Клиент", style="padding: 10px 12px;"),
                        Th("Менеджер", style="padding: 10px 12px;"),
                        Th("Статус", style="padding: 10px 12px;"),
                        Th("Версии", style="text-align: center; width: 70px; padding: 10px 12px;"),
                        Th("Сумма", cls="col-money", style="padding: 10px 12px;"),
                        Th("Профит", cls="col-money", style="padding: 10px 12px;"),
                    )),
                    Tbody(
                        *table_rows
                    ) if filtered_quotes else Tbody(Tr(Td(
                        Div(
                            icon("file-text", size=28, style="color: #94a3b8; margin-bottom: 8px;"),
                            Div("Нет коммерческих предложений", style="font-size: 14px; font-weight: 500; color: #64748b; margin-bottom: 6px;"),
                            Div("Создайте первое КП для начала работы", style="font-size: 12px; color: #94a3b8; margin-bottom: 12px;"),
                            A(
                                icon("plus", size=14),
                                Span("Создать первое КП"),
                                href="/quotes/new",
                                style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; color: #3b82f6; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; text-decoration: none;",
                                cls="btn",
                            ),
                            style="text-align: center; padding: 32px 24px;"
                        ),
                        colspan="8"
                    ))),
                    cls="table-enhanced"
                ),
                cls="table-enhanced-container"
            ),
            cls="table-responsive"
        ),

        # Table footer with count
        Div(
            Span(f"Всего: {len(filtered_quotes)} КП", style="font-size: 12px; color: #64748b;"),
            cls="table-footer"
        ) if filtered_quotes else None,

        session=session,
        current_path="/quotes"
    )





# ============================================================================
# QUOTE DETAIL
# ============================================================================


def _render_summary_tab(quote, customer, seller_companies, contacts, items, creator_name,
                        created_at_display, expiry_display,
                        quote_controller_name=None, spec_controller_name=None,
                        customs_user_name=None, logistics_user_name=None,
                        rate_on_quote_date=None, rate_on_spec_date=None):
    """Render read-only summary tab with 6-block layout (3 rows x 2 columns).

    LEFT column:  Block I (Основная), Block II (Дополнительная), Block III (Печать)
    RIGHT column: Block IV (Расчеты), Block V (Доставка), Block VI (Итого)
    Row pairing: [I+IV], [II+V], [III+VI]
    """

    # Lookup seller company object
    seller_company = None
    if quote.get("seller_company_id"):
        seller_company = next(
            (sc for sc in seller_companies if str(sc.id) == str(quote.get("seller_company_id", ""))),
            None
        )

    # Lookup contact person
    contact_person = None
    if quote.get("contact_person_id") and contacts:
        contact_person = next(
            (c for c in contacts if c.get("id") == quote.get("contact_person_id")),
            None
        )

    # Delivery method label
    delivery_method_map = {"air": "Авиа", "auto": "Авто", "sea": "Море", "multimodal": "Мультимодально"}
    delivery_method_label = delivery_method_map.get(quote.get("delivery_method") or "", "—")

    # Currency info
    currency = quote.get("currency") or "RUB"
    currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥", "TRY": "₺"}
    currency_symbol = currency_symbols.get(currency, currency)

    # Totals (prefer quote-currency columns, fallback to total_amount)
    total_with_vat = float(quote.get("total_quote_currency") or quote.get("total_amount") or 0)
    total_no_vat = float(quote.get("revenue_no_vat_quote_currency") or 0)
    total_profit = float(quote.get("profit_quote_currency") or 0)
    total_cogs = float(quote.get("cogs_quote_currency") or 0)

    # Fallback for old quotes without revenue_no_vat: derive from total / (1 + tax_rate%)
    if total_no_vat == 0 and total_with_vat > 0:
        tax_rate = float(quote.get("tax_rate") or 20)
        total_no_vat = total_with_vat / (1 + tax_rate / 100)
    # Fallback for old quotes without cogs: cogs = revenue_no_vat - profit
    if total_cogs == 0 and total_no_vat > 0 and total_profit > 0:
        total_cogs = total_no_vat - total_profit

    # Margin = profit / revenue (excl. VAT), Markup = profit / COGS
    margin_pct = (total_profit / total_no_vat) * 100 if total_no_vat > 0 else 0
    markup_pct = (total_profit / total_cogs) * 100 if total_cogs > 0 else 0

    # Payment terms
    payment_terms = quote.get("payment_terms") or "—"
    advance_percent = quote.get("advance_percent") or 0

    # Common styles
    label_style = "color: #6b7280; font-size: 0.7rem; text-transform: uppercase;"
    value_style = "color: #374151; margin-top: 0.25rem; font-size: 0.875rem;"
    card_style = "background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; flex: 1;"
    header_style = "display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
    header_text_style = "font-size: 0.75rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"
    grid_2col = "display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;"

    def _field(label_text, value_text, full_width=False):
        """Helper to render a single read-only field."""
        extra_style = "grid-column: 1 / -1;" if full_width else ""
        return Div(
            Div(label_text, style=label_style),
            Div(str(value_text) if value_text else "—", style=value_style),
            style=extra_style
        )

    def _card_header(icon_name, title):
        """Helper to render a card header with icon."""
        return Div(
            icon(icon_name, size=14, color="#6b7280"),
            Span(f" {title}", style=header_text_style),
            style=header_style
        )

    # --- Action buttons row ---
    # Download button only available after quote controller approval
    _download_allowed_statuses = {"pending_approval", "approved", "sent_to_client", "client_negotiation", "pending_spec_control", "deal"}
    _current_wf_status = quote.get("workflow_status") or quote.get("status", "draft")
    _download_btn = btn("Скачать", variant="secondary", icon_name="download",
        onclick=f"location.href='/quotes/{quote.get('id')}/export/specification'") if _current_wf_status in _download_allowed_statuses else None
    # Download button moved to bottom of summary (after all blocks)
    download_row = Div(
        _download_btn,
        style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.5rem;"
    ) if _download_btn else None

    # --- Block I: Main info (customer/seller + contact phone) ---
    customer_name = (customer or {}).get("name", "—") or "—"
    customer_inn = (customer or {}).get("inn", "—") or "—"
    seller_name = seller_company.name if seller_company else "—"
    seller_inn = getattr(seller_company, "inn", None) or "—" if seller_company else "—"
    contact_name = (contact_person or {}).get("name", "—") if contact_person else "—"
    contact_phone = (contact_person or {}).get("phone", "—") if contact_person else "—"

    # Customer name as clickable link if customer exists
    customer_display = A(
        customer_name,
        href=f"/customers/{quote.get('customer_id')}",
        style="color: #3b82f6; text-decoration: none; font-weight: 500;"
    ) if quote.get("customer_id") and customer_name != "—" else Span("—", style="color: #9ca3af;")

    card_1 = Div(
        _card_header("info", "ОСНОВНАЯ ИНФОРМАЦИЯ"),
        Div(
            Div(
                Div("Клиент", style=label_style),
                Div(customer_display, style="margin-top: 0.25rem;"),
            ),
            _field("ИНН клиента", customer_inn),
            _field("Организация продавец", seller_name),
            _field("ИНН продавца", seller_inn),
            _field("Контактное лицо", contact_name),
            _field("Телефон", contact_phone),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block IV: ПОРЯДОК РАСЧЕТОВ (exchange rates + payment terms) ---
    has_advance = advance_percent and float(advance_percent) > 0
    advance_display = f"{advance_percent}%" if has_advance else "—"

    # Format exchange rates for display
    def _format_rate(rate):
        if rate is None:
            return "—"
        return f"{rate:.4f} \u20bd"

    rate_kp_display = _format_rate(rate_on_quote_date)
    rate_sp_display = _format_rate(rate_on_spec_date)

    card_4 = Div(
        _card_header("credit-card", "ПОРЯДОК РАСЧЕТОВ"),
        Div(
            _field("Условия расчетов", payment_terms),
            _field("Частичная предоплата", "Да" if has_advance else "Нет"),
            _field("Размер аванса", advance_display),
            _field("Валюта КП", currency),
            _field("Курс USD/RUB на дату КП", rate_kp_display),
            _field("Курс USD/RUB на дату СП", rate_sp_display),
            _field("Курс USD/RUB на дату УПД", "—"),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block II: ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (5 workflow actors + dates) ---
    # Format completion dates
    def _format_date(date_str):
        if not date_str:
            return "—"
        try:
            dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return "—"

    quote_control_date = _format_date(quote.get("quote_control_completed_at"))
    spec_control_date = _format_date(quote.get("spec_control_completed_at"))
    customs_date = _format_date(quote.get("customs_completed_at"))
    logistics_date = _format_date(quote.get("logistics_completed_at"))

    card_2 = Div(
        _card_header("users", "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ"),
        Div(
            _field("Создатель", creator_name or "—"),
            _field("Дата создания", created_at_display),
            _field("Контролер КП", quote_controller_name or "—"),
            _field("Дата проверки КП", quote_control_date),
            _field("Контролер СП", spec_controller_name or "—"),
            _field("Дата проверки СП", spec_control_date),
            _field("Таможенный менеджер", customs_user_name or "—"),
            _field("Дата таможни", customs_date),
            _field("Логистический менеджер", logistics_user_name or "—"),
            _field("Дата логистики", logistics_date),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block V: ДОСТАВКА ---
    card_5 = Div(
        _card_header("truck", "ДОСТАВКА"),
        Div(
            _field("Тип сделки", delivery_method_label),
            _field("Базис поставки", quote.get("delivery_terms") or "—"),
            _field("Страна поставки", quote.get("delivery_country") or "—"),
            _field("Город доставки", quote.get("delivery_city") or "—"),
            _field("Адрес поставки", quote.get("delivery_address") or "—", full_width=True),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block III: ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ ---
    card_3 = Div(
        _card_header("printer", "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ"),
        Div(
            _field("Дата выставления КП", created_at_display),
            _field("Срок действия КП", expiry_display),
            _field("Срок действия (дней)", str(quote.get("validity_days") or 30)),
            style=grid_2col
        ),
        cls="card",
        style=card_style
    )

    # --- Block VI: ИТОГО (3-column grid: total, profit, count, margin, markup) ---
    total_amount_display = f"{total_with_vat:,.2f} {currency_symbol}" if total_with_vat else "—"
    total_profit_display = f"{total_profit:,.2f} {currency_symbol}" if total_profit is not None else "—"
    items_count = len(items)
    margin_display = f"{margin_pct:.1f}%"
    markup_display = f"{markup_pct:.1f}%" if total_cogs > 0 else "—"

    _itogo_big = "font-weight: 600; font-size: 1.25rem; margin-top: 0.25rem;"
    card_6 = Div(
        _card_header("dollar-sign", "ИТОГО"),
        Div(
            Div(
                Div("Сумма с НДС", style=label_style),
                Div(total_amount_display, style=f"color: #374151; {_itogo_big}"),
            ),
            Div(
                Div(f"Профит ({currency})", style=label_style),
                Div(total_profit_display,
                    style=f"color: {'#10b981' if total_profit > 0 else '#ef4444' if total_profit < 0 else '#374151'}; {_itogo_big}"),
            ),
            Div(
                Div("Позиции", style=label_style),
                Div(f"{items_count} шт", style=value_style),
            ),
            Div(
                Div("Маржа (профит ÷ выручка без НДС)", style=label_style),
                Div(margin_display,
                    style=f"color: {'#10b981' if margin_pct > 0 else '#374151'}; {_itogo_big}"),
            ),
            Div(
                Div("Наценка (профит ÷ себестоимость)", style=label_style),
                Div(markup_display,
                    style=f"color: {'#10b981' if markup_pct > 0 else '#374151'}; {_itogo_big}"),
            ),
            style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem;"
        ),
        cls="card",
        style=card_style
    )

    # --- Layout: 3 rows x 2 columns ---
    # Row 1: Block I (Основная) + Block IV (Расчеты)
    # Row 2: Block II (Дополнительная) + Block V (Доставка)
    # Row 3: Block III (Печать) + Block VI (Итого)
    return Div(
        # Row 1: Block I + Block IV
        Div(card_1, card_4, style="display: flex; gap: 1rem; margin-bottom: 1rem;"),
        # Row 2: Block II + Block V
        Div(card_2, card_5, style="display: flex; gap: 1rem; margin-bottom: 1rem;"),
        # Row 3: Block III + Block VI
        Div(card_3, card_6, style="display: flex; gap: 1rem; margin-bottom: 1rem;"),
        download_row,
        id="tab-content",
        style="margin-top: 20px;"
    )




def _sales_action_toolbar(quote_id, workflow_status, is_revision, is_justification_needed):
    """Persistent action toolbar shown on BOTH Обзор and Позиции sub-tabs.
    Visually distinct from tab pills: thin bar with sm-sized outline buttons,
    light gray background, top/bottom border separating it from content.
    """
    left_buttons = Div(
        btn_link("Рассчитать", href=f"/quotes/{quote_id}/calculate", variant="secondary", icon_name="calculator", size="sm"),
        btn_link("История версий", href=f"/quotes/{quote_id}/versions", variant="secondary", icon_name="history", size="sm"),
        btn_link("Валидация Excel", href=f"/quotes/{quote_id}/export/validation", variant="secondary", icon_name="table", size="sm") if show_validation_excel(workflow_status) else None,
        btn_link("КП PDF", href=f"/quotes/{quote_id}/export/invoice", variant="secondary", icon_name="file-text", size="sm") if show_quote_pdf(workflow_status) else None,
        btn_link("Счёт PDF", href=f"/quotes/{quote_id}/export/invoice", variant="secondary", icon_name="file-text", size="sm") if show_invoice_and_spec(workflow_status) else None,
        style="display: flex; gap: 0.375rem; flex-wrap: wrap; align-items: center;"
    )
    right_buttons = Div(
        (Form(
            btn("Отправить на контроль", variant="secondary", icon_name="send", type="submit", size="sm"),
            method="post",
            action=f"/quotes/{quote_id}/submit-quote-control",
            style="display: inline;"
        ) if workflow_status == "pending_sales_review" and not is_revision and not is_justification_needed else None),
        btn("Удалить КП", variant="danger", icon_name="trash-2", size="sm",
            id="btn-delete-quote", onclick="showDeleteModal()"),
        style="display: flex; gap: 0.375rem; align-items: center;"
    )
    return Div(
        Div(left_buttons, right_buttons,
            style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;"),
        style=(
            "background: #f8fafc; "
            "border-top: 1px solid #e5e7eb; "
            "border-bottom: 1px solid #e5e7eb; "
            "padding: 0.5rem 0; "
            "margin-bottom: 1rem;"
        )
    )


def _overview_info_subtab(quote, quote_id, customer, customers, seller_companies, contacts,
                          creator_name, created_at_display, expiry_display, is_expired,
                          delivery_terms_options, delivery_method_options,
                          _itogo_total_display, _itogo_profit_display, _itogo_profit_color,
                          _itogo_items_count, _itogo_margin_display, _itogo_margin_color):
    """Render the info sub-tab: ОСНОВНАЯ ИНФОРМАЦИЯ block (full-width, 2-col grid),
    2-column layout with ДОСТАВКА (left) + ИТОГО (right).
    Uses display: grid with grid-template-columns: 1fr 1fr for the bottom row."""
    pass


def _overview_products_subtab(quote, quote_id, items, items_json, workflow_status,
                              is_revision, is_justification_needed, logistics_total,
                              approval_status, session, revision_comment, approval_reason,
                              delivery_terms_options, delivery_method_options,
                              user_has_any_role_fn, user_can_approve_fn):
    """Render the products sub-tab with unified action card.
    Contains: Рассчитать button, История версий, Валидация Excel, КП PDF, Счёт PDF,
    Удалить КП danger button, Отправить на контроль button.
    Includes id="items-spreadsheet" Handsontable container and workflow_transition_history."""
    pass


@rt("/quotes/{quote_id}")
def get(quote_id: str, session, tab: str = "summary", subtab: str = "info"):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    # Respect role impersonation for tab visibility and access control
    impersonated_role = session.get("impersonated_role")
    effective_roles = [impersonated_role] if impersonated_role else user.get("roles", [])
    supabase = get_supabase()

    # Get quote with customer
    result = supabase.table("quotes") \
        .select("*, customers(name, inn, email)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not result.data:
        return page_layout("Не найдено",
            H1("КП не найден"),
            A("← Назад к списку КП", href="/quotes"),
            session=session
        )

    quote = result.data[0]
    customer = quote.get("customers", {})

    # Get customers for dropdown (for inline editing)
    customers_result = supabase.table("customers") \
        .select("id, name, inn") \
        .eq("organization_id", user["org_id"]) \
        .order("name") \
        .execute()
    customers = customers_result.data or []

    # Get seller companies for dropdown
    from services.seller_company_service import get_all_seller_companies
    seller_companies = get_all_seller_companies(organization_id=user["org_id"], is_active=True)

    # Get customer contacts for contact person dropdown
    contacts = []
    if quote.get("customer_id"):
        try:
            contacts_result = supabase.table("customer_contacts") \
                .select("id, name, position, phone, is_lpr") \
                .eq("customer_id", quote["customer_id"]) \
                .order("is_lpr", desc=True) \
                .order("name") \
                .execute()
            contacts = contacts_result.data or []
        except Exception:
            pass

    # Look up creator name from user_profiles
    creator_name = None
    if quote.get("created_by"):
        try:
            creator_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["created_by"]) \
                .limit(1) \
                .execute()
            if creator_result.data and creator_result.data[0].get("full_name"):
                creator_name = creator_result.data[0]["full_name"]
        except Exception:
            pass

    # Look up workflow actor names from user_profiles (quote_controller, spec_controller, customs, logistics)
    quote_controller_name = None
    if quote.get("quote_controller_id"):
        try:
            qc_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["quote_controller_id"]) \
                .limit(1) \
                .execute()
            if qc_result.data and qc_result.data[0].get("full_name"):
                quote_controller_name = qc_result.data[0]["full_name"]
        except Exception:
            pass

    spec_controller_name = None
    if quote.get("spec_controller_id"):
        try:
            sc_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["spec_controller_id"]) \
                .limit(1) \
                .execute()
            if sc_result.data and sc_result.data[0].get("full_name"):
                spec_controller_name = sc_result.data[0]["full_name"]
        except Exception:
            pass

    customs_user_name = None
    if quote.get("assigned_customs_user"):
        try:
            cu_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["assigned_customs_user"]) \
                .limit(1) \
                .execute()
            if cu_result.data and cu_result.data[0].get("full_name"):
                customs_user_name = cu_result.data[0]["full_name"]
        except Exception:
            pass

    logistics_user_name = None
    if quote.get("assigned_logistics_user"):
        try:
            lu_result = supabase.table("user_profiles") \
                .select("full_name") \
                .eq("user_id", quote["assigned_logistics_user"]) \
                .limit(1) \
                .execute()
            if lu_result.data and lu_result.data[0].get("full_name"):
                logistics_user_name = lu_result.data[0]["full_name"]
        except Exception:
            pass

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    items = items_result.data or []

    # Calculate logistics_total from invoices (logistics cost segments)
    # The quotes table does NOT have a logistics_total column — it must be computed
    # by summing logistics_supplier_to_hub + logistics_hub_to_customs + logistics_customs_to_customer
    # from the invoices table, converting each segment to the quote currency.
    logistics_total = 0.0
    try:
        from services.currency_service import convert_amount
        from decimal import Decimal as _Decimal
        _logistics_inv_result = supabase.table("invoices") \
            .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
            .eq("quote_id", quote_id) \
            .execute()
        _logistics_invoices = _logistics_inv_result.data or []
        _quote_currency = quote.get("currency") or "RUB"
        _logistics_total_dec = _Decimal(0)
        for _linv in _logistics_invoices:
            _s2h = _Decimal(str(_linv.get("logistics_supplier_to_hub") or 0))
            _s2h_cur = _linv.get("logistics_supplier_to_hub_currency") or "USD"
            _h2c = _Decimal(str(_linv.get("logistics_hub_to_customs") or 0))
            _h2c_cur = _linv.get("logistics_hub_to_customs_currency") or "USD"
            _c2c = _Decimal(str(_linv.get("logistics_customs_to_customer") or 0))
            _c2c_cur = _linv.get("logistics_customs_to_customer_currency") or "USD"
            if _s2h > 0:
                _logistics_total_dec += convert_amount(_s2h, _s2h_cur, _quote_currency)
            if _h2c > 0:
                _logistics_total_dec += convert_amount(_h2c, _h2c_cur, _quote_currency)
            if _c2c > 0:
                _logistics_total_dec += convert_amount(_c2c, _c2c_cur, _quote_currency)
        logistics_total = float(_logistics_total_dec)
    except Exception:
        logistics_total = 0.0

    # Prepare items data for Handsontable (JSON)
    items_for_handsontable = [
        {
            'id': item.get('id'),
            'row_num': idx + 1,
            'brand': item.get('brand', ''),
            'product_code': item.get('product_code', ''),
            'product_name': item.get('product_name', ''),
            'quantity': item.get('quantity', 1),
            'unit': item.get('unit', 'шт')
        } for idx, item in enumerate(items)
    ]
    items_json = json.dumps(items_for_handsontable)

    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    # Check for revision status (returned from quote control)
    revision_department = quote.get("revision_department")
    revision_comment = quote.get("revision_comment")
    is_revision = revision_department == "sales" and workflow_status == "pending_sales_review"

    # Check for justification status (Feature: approval justification workflow)
    needs_justification = quote.get("needs_justification", False)
    approval_reason = quote.get("approval_reason")
    is_justification_needed = needs_justification and workflow_status == "pending_sales_review"

    # Get approval status for multi-department workflow (Bug #8 follow-up)
    approval_status = get_quote_approval_status(quote_id, user["org_id"]) or {}

    # Delivery terms options
    delivery_terms_options = ["DDP", "DAP", "EXW", "FCA", "CPT", "CIP", "FOB", "CIF"]
    delivery_method_options = [
        ("air", "Авиа"),
        ("auto", "Авто"),
        ("sea", "Море"),
        ("multimodal", "Мультимодально")
    ]
    delivery_priority_options = [
        ("fast", "Лучше быстро"),
        ("cheap", "Лучше дешево"),
        ("normal", "Обычно")
    ]

    # Compute created_at display and expiry info
    created_at_display = "—"
    expiry_display = "—"
    is_expired = False
    if quote.get("created_at"):
        try:
            created_dt = datetime.fromisoformat(quote["created_at"].replace("Z", "+00:00"))
            created_at_display = created_dt.strftime("%d.%m.%Y %H:%M")
            validity = quote.get("validity_days") or 30
            expiry_dt = created_dt + timedelta(days=validity)
            expiry_display = expiry_dt.strftime("%d.%m.%Y")
            is_expired = datetime.now(created_dt.tzinfo) > expiry_dt
        except Exception:
            pass

    # Look up deal for this quote (for finance tabs)
    # Only do the lookup if the tab is a finance tab or we need to check if finance tabs should show
    deal = _lookup_deal_for_quote(quote_id, user["org_id"])
    deal_id = deal["id"] if deal else None

    # If a finance tab is requested but no deal exists, fall back to summary
    if tab in ("finance_main", "plan_fact", "logistics_stages", "currency_invoices", "logistics_expenses") and not deal:
        tab = "summary"

    # Render finance tab content if requested
    if tab in ("finance_main", "plan_fact", "logistics_stages", "currency_invoices", "logistics_expenses") and deal:
        user_roles = effective_roles
        # Check role access for finance tabs
        finance_roles = ["finance", "admin", "top_manager"]
        if tab == "logistics_stages":
            finance_roles.append("logistics")
        if tab == "currency_invoices":
            finance_roles.append("currency_controller")
        if tab == "logistics_expenses":
            finance_roles.append("logistics")
        if not any(r in user_roles for r in finance_roles):
            return RedirectResponse("/unauthorized", status_code=303)

        # Currency invoices tab does not need full deal data fetch
        if tab == "currency_invoices":
            finance_content = _finance_currency_invoices_tab_content(deal_id)
            modal_elements = _finance_payment_modal(deal_id)
            return page_layout(f"Quote {quote.get('idn_quote', '')}",
                quote_header(quote, workflow_status, (customer or {}).get("name")),
                quote_detail_tabs(quote_id, tab, effective_roles, deal=deal, quote=quote, user_id=user["id"]),
                Div(finance_content, id="tab-content", style="margin-top: 20px;"),
                *modal_elements,
                session=session
            )

        # Logistics expenses tab does not need full deal data fetch
        if tab == "logistics_expenses":
            finance_content = _finance_logistics_expenses_tab_content(deal_id, user["org_id"], session)
            modal_elements = _finance_payment_modal(deal_id)
            return page_layout(f"Quote {quote.get('idn_quote', '')}",
                quote_header(quote, workflow_status, (customer or {}).get("name")),
                quote_detail_tabs(quote_id, tab, effective_roles, deal=deal, quote=quote, user_id=user["id"]),
                Div(finance_content, id="tab-content", style="margin-top: 20px;"),
                *modal_elements,
                session=session
            )

        # Fetch full deal data for finance tabs
        deal_full, plan_fact_items_deal, _ = _finance_fetch_deal_data(deal_id, user["org_id"], user_roles)
        if not deal_full:
            tab = "summary"
        else:
            # Build finance tab content
            if tab == "finance_main":
                finance_content = _finance_main_tab_content(deal_id, deal_full, plan_fact_items_deal)
            elif tab == "plan_fact":
                finance_content = _finance_plan_fact_tab_content(deal_id, plan_fact_items_deal)
            elif tab == "logistics_stages":
                finance_content = _finance_logistics_tab_content(deal_id, deal_full, session)

            # Render the quote page with finance tab content
            modal_elements = _finance_payment_modal(deal_id)
            return page_layout(f"Quote {quote.get('idn_quote', '')}",
                quote_header(quote, workflow_status, (customer or {}).get("name")),
                quote_detail_tabs(quote_id, tab, effective_roles, deal=deal, quote=quote, user_id=user["id"]),
                Div(finance_content, id="tab-content", style="margin-top: 20px;"),
                *modal_elements,
                session=session
            )

    # Render summary tab (read-only overview)
    if tab == "summary":
        # Fetch CBR USD/RUB exchange rates for quote and spec dates
        def _fetch_rate_for_date(date_value):
            """Parse a date string/object and fetch CBR USD/RUB rate for that date."""
            if not date_value:
                return None
            try:
                if isinstance(date_value, str):
                    parsed = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
                else:
                    parsed = date_value
                return get_usd_rub_rate(parsed.date() if hasattr(parsed, 'date') else parsed)
            except Exception:
                return None

        rate_on_quote_date = _fetch_rate_for_date(quote.get("created_at"))

        # Fetch spec created_at for rate on spec date
        rate_on_spec_date = None
        try:
            spec_result = supabase.table("specifications") \
                .select("created_at") \
                .eq("quote_id", quote_id) \
                .limit(1) \
                .is_("deleted_at", None) \
                .execute()
            if spec_result.data:
                spec_created_at = spec_result.data[0].get("created_at")
                rate_on_spec_date = _fetch_rate_for_date(spec_created_at)
        except Exception:
            pass

        summary_content = _render_summary_tab(
            quote, customer, seller_companies, contacts, items, creator_name,
            created_at_display, expiry_display,
            quote_controller_name=quote_controller_name,
            spec_controller_name=spec_controller_name,
            customs_user_name=customs_user_name,
            logistics_user_name=logistics_user_name,
            rate_on_quote_date=rate_on_quote_date,
            rate_on_spec_date=rate_on_spec_date,
        )
        return page_layout(f"Quote {quote.get('idn_quote', '')}",
            quote_header(quote, workflow_status, (customer or {}).get("name")),
            quote_detail_tabs(quote_id, "summary", effective_roles, deal=deal, quote=quote, user_id=user["id"]),
            summary_content,
            session=session
        )

    # Precompute ИТОГО block values
    _itogo_total = float(quote.get("total_quote_currency") or quote.get("total_amount") or 0)
    _itogo_revenue_no_vat = float(quote.get("revenue_no_vat_quote_currency") or 0)
    _itogo_profit = float(quote.get("profit_quote_currency") or 0)
    _itogo_cogs = float(quote.get("cogs_quote_currency") or 0)
    _itogo_currency = quote.get("currency", "RUB")
    _itogo_items_count = len(items)
    # Fallback for old quotes without revenue_no_vat
    if _itogo_revenue_no_vat == 0 and _itogo_total > 0:
        _tax_rate = float(quote.get("tax_rate") or 20)
        _itogo_revenue_no_vat = _itogo_total / (1 + _tax_rate / 100)
    # Fallback for old quotes without cogs
    if _itogo_cogs == 0 and _itogo_revenue_no_vat > 0 and _itogo_profit > 0:
        _itogo_cogs = _itogo_revenue_no_vat - _itogo_profit
    # Margin = profit / revenue (excl. VAT); Markup = profit / COGS
    _itogo_margin = (_itogo_profit / _itogo_revenue_no_vat * 100) if _itogo_revenue_no_vat > 0 else 0
    _itogo_markup = (_itogo_profit / _itogo_cogs * 100) if _itogo_cogs > 0 else 0
    _itogo_total_display = format_money(_itogo_total, _itogo_currency) if _itogo_total > 0 else "—"
    _itogo_profit_display = format_money(_itogo_profit, _itogo_currency) if _itogo_profit != 0 else "—"
    _itogo_profit_color = "#16a34a" if _itogo_profit > 0 else "#dc2626" if _itogo_profit < 0 else "#64748b"
    _itogo_margin_display = f"{_itogo_margin:.1f}%" if _itogo_revenue_no_vat > 0 else "—"
    _itogo_markup_display = f"{_itogo_markup:.1f}%" if _itogo_cogs > 0 else "—"
    _itogo_margin_color = "#16a34a" if _itogo_profit > 0 else "#64748b"

    return page_layout(f"Quote {quote.get('idn_quote', '')}",
        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, (customer or {}).get("name")),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "overview", effective_roles, deal=deal, quote=quote, user_id=user["id"]),

        # Workflow progress bar (same as on procurement/logistics/customs pages)
        workflow_progress_bar(workflow_status),

        # Persistent action toolbar

        _sales_action_toolbar(quote_id, workflow_status, is_revision, is_justification_needed),

        # Block I: ОСНОВНАЯ ИНФОРМАЦИЯ (2-column grid)
        Div(
            Div(
                icon("file-text", size=16, color="#64748b"),
                Span(" ОСНОВНАЯ ИНФОРМАЦИЯ", style="font-size: 0.7rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
            ),
            # 2-column grid layout (col 1: dropdowns, col 2: info + additional_info)
            Div(
                # Col 1, Row 1: Seller Company dropdown
                Div(
                    Div("ПРОДАВЕЦ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Select(
                        Option("—", value=""),
                        *[Option(
                            f"{sc.supplier_code} - {sc.name}" if sc.supplier_code else sc.name,
                            value=str(sc.id),
                            selected=(str(sc.id) == str(quote.get("seller_company_id") or ""))
                        ) for sc in seller_companies],
                        name="seller_company_id",
                        id="inline-seller",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "seller_company_id", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 2, Row 1: Creator
                Div(
                    Div("СОЗДАЛ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(creator_name or "—", style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                # Col 1, Row 2: Customer dropdown
                Div(
                    Div("КЛИЕНТ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Select(
                        Option("Выберите клиента...", value="", selected=(not quote.get("customer_id"))),
                        *[Option(
                            f"{c['name']}" + (f" ({c.get('inn', '')})" if c.get('inn') else ""),
                            value=c["id"],
                            selected=(c["id"] == quote.get("customer_id"))
                        ) for c in customers],
                        name="customer_id",
                        id="inline-customer",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;" + (" border-color: #f59e0b; background: #fffbeb;" if not quote.get("customer_id") else ""),
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "customer_id", value: event.target.value}',
                        hx_swap="none"
                    ),
                    Script("""
                        document.getElementById('inline-customer').addEventListener('htmx:afterRequest', function(event) {
                            if (event.detail.successful) { window.location.reload(); }
                        });
                    """),
                ),
                # Col 2, Row 2: Created at
                Div(
                    Div("ДАТА СОЗДАНИЯ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(created_at_display, style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                # Col 1, Row 3: Contact Person
                Div(
                    Div("КОНТАКТНОЕ ЛИЦО", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Select(
                        Option("— Не выбрано —", value=""),
                        *[Option(
                            f"{c['name']}" + (f" ({c.get('position', '')})" if c.get('position') else ""),
                            value=c["id"],
                            selected=(c["id"] == quote.get("contact_person_id"))
                        ) for c in contacts],
                        name="contact_person_id",
                        id="inline-contact-person",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "contact_person_id", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 2, Row 3: Additional info (NEW textarea field)
                Div(
                    Div("ДОП. ИНФОРМАЦИЯ", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Textarea(
                        quote.get("additional_info") or "",
                        name="additional_info",
                        id="inline-additional-info",
                        placeholder="Заметки, комментарии...",
                        rows="3",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box; font-family: inherit; resize: vertical;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "additional_info", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 1, Row 4: Validity days (inline-editable)
                Div(
                    Div("СРОК ДЕЙСТВИЯ (ДНЕЙ)", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Input(
                        type="number",
                        value=str(quote.get("validity_days") or 30),
                        min="1",
                        name="validity_days",
                        style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box; max-width: 120px;",
                        hx_patch=f"/quotes/{quote_id}/inline",
                        hx_trigger="change",
                        hx_vals='js:{field: "validity_days", value: event.target.value}',
                        hx_swap="none"
                    ),
                ),
                # Col 2, Row 4: Expiry date (calculated, with red/green indicator)
                Div(
                    Div("ДЕЙСТВИТЕЛЕН ДО", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Span(
                        expiry_display,
                        style=f"font-size: 14px; padding: 6px 10px; border-radius: 6px; display: inline-block; font-weight: 500; {'background: #fef2f2; color: #dc2626;' if is_expired else 'background: #f0fdf4; color: #16a34a;'}" if expiry_display != "\u2014" else "font-size: 14px; color: #334155; padding: 8px 0; display: block;"
                    ),
                ),
                # Col 1, Row 5: Customs manager (read-only)
                Div(
                    Div("ТАМОЖЕННЫЙ МЕНЕДЖЕР", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(customs_user_name or "—", style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                # Col 2, Row 5: Logistics manager (read-only)
                Div(
                    Div("ЛОГИСТИЧЕСКИЙ МЕНЕДЖЕР", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.375rem;"),
                    Div(logistics_user_name or "—", style="color: #374151; font-size: 0.875rem; padding: 0.25rem 0;"),
                ),
                style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem 1.5rem;"
            ),
            cls="card",
            style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb; margin-bottom: 1rem;"
        ),

        # Block II+III: ДОСТАВКА (left) + summary metrics (right) side-by-side
        Div(
            # Left column: ДОСТАВКА card
            Div(
                Div(
                    icon("truck", size=16, color="#64748b"),
                    Span(" ДОСТАВКА", style="font-size: 0.7rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
                ),

                # Row: Страна, Город, Адрес поставки, Способ, Условия
                Div(
                    # Delivery Country
                    Div(
                        Label("СТРАНА", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Input(
                            type="text",
                            value=quote.get("delivery_country") or "",
                            placeholder="Введите страну",
                            name="delivery_country",
                            id="delivery-country-input",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_country", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 1 1 120px; min-width: 120px;"
                    ),
                    # Delivery City
                    Div(
                        Label("ГОРОД", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Input(
                            type="text",
                            value=quote.get("delivery_city") or "",
                            placeholder="Введите город",
                            name="delivery_city",
                            id="delivery-city-input",
                            list="cities-datalist",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_get="/api/cities/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#cities-datalist",
                            hx_vals='js:{"q": document.getElementById("delivery-city-input").value}',
                            hx_swap="innerHTML",
                            onblur="if(typeof saveDeliveryCity==='function') saveDeliveryCity(this.value)",
                            onchange="if(typeof saveDeliveryCity==='function'){saveDeliveryCity(this.value); syncCountryFromCity(this);}",
                        ),
                        Datalist(id="cities-datalist"),
                        # Always-rendered save function for delivery city (not conditional on workflow status)
                        Script(f"""
                            function saveDeliveryCity(value) {{
                                fetch('/quotes/{quote_id}/inline', {{
                                    method: 'PATCH',
                                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                    body: 'field=delivery_city&value=' + encodeURIComponent(value)
                                }});
                            }}
                            function syncCountryFromCity(cityInput) {{
                                var datalist = document.getElementById('cities-datalist');
                                var countryInput = document.getElementById('delivery-country-input');
                                if (!datalist || !countryInput) return;
                                var options = datalist.querySelectorAll('option');
                                for (var i = 0; i < options.length; i++) {{
                                    if (options[i].value === cityInput.value) {{
                                        var country = options[i].getAttribute('data-country');
                                        if (country) {{
                                            countryInput.value = country;
                                            countryInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                                        }}
                                        break;
                                    }}
                                }}
                            }}
                        """),
                        style="flex: 1 1 120px; min-width: 120px;"
                    ),
                    # АДРЕС поставки (delivery_address)
                    Div(
                        Label("АДРЕС", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Input(
                            type="text",
                            value=quote.get("delivery_address") or "",
                            placeholder="Адрес поставки",
                            name="delivery_address",
                            id="delivery-address-input",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_address", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 2 1 200px; min-width: 200px;"
                    ),
                    # Delivery Method
                    Div(
                        Label("СПОСОБ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Select(
                            Option("—", value=""),
                            *[Option(label, value=val, selected=(val == quote.get("delivery_method"))) for val, label in delivery_method_options],
                            name="delivery_method",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_method", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 1 1 160px; min-width: 160px;"
                    ),
                    # Delivery Terms
                    Div(
                        Label("УСЛОВИЯ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.375rem; display: block;"),
                        Select(
                            *[Option(term, value=term, selected=(term == quote.get("delivery_terms"))) for term in delivery_terms_options],
                            name="delivery_terms",
                            style="width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc; box-sizing: border-box;",
                            hx_patch=f"/quotes/{quote_id}/inline",
                            hx_trigger="change",
                            hx_vals='js:{field: "delivery_terms", value: event.target.value}',
                            hx_swap="none"
                        ),
                        style="flex: 1 1 100px; min-width: 100px;"
                    ),
                    style="display: flex; flex-wrap: wrap; gap: 1rem;"
                ),
                cls="card",
                style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb;"
            ),
            # Right column: ИТОГО card
            Div(
                Div(
                    icon("bar-chart-2", size=16, color="#64748b"),
                    Span(" ИТОГО", style="font-size: 0.7rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e5e7eb;"
                ),
                Div(
                    Div(
                        Div("Общая сумма", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_total_display, style="font-size: 1.1rem; font-weight: 600; color: #1e40af;"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Общий профит", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_profit_display, style=f"font-size: 1.1rem; font-weight: 600; color: {_itogo_profit_color};"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Количество позиций", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(str(_itogo_items_count), style="font-size: 1.1rem; font-weight: 600; color: #374151;"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Маржа (профит ÷ выр. без НДС)", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_margin_display, style=f"font-size: 1.1rem; font-weight: 600; color: {_itogo_margin_color};"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    Div(
                        Div("Наценка (профит ÷ себест.)", style="color: #6b7280; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem;"),
                        Div(_itogo_markup_display, style=f"font-size: 1.1rem; font-weight: 600; color: {'#16a34a' if _itogo_markup > 0 else '#64748b'};"),
                        style="text-align: center; padding: 0.5rem;"
                    ),
                    style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;"
                ),
                cls="card",
                style="background: white; border-radius: 0.75rem; padding: 1rem; border: 1px solid #e5e7eb;"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;"
        ),

        # Products (Handsontable spreadsheet)
        Div(
            # Section header with icon
            Div(
                Div(
                    icon("package", size=16, color="#64748b"),
                    Span(" ПОЗИЦИИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                    Span(id="items-count", style="margin-left: 0.5rem; font-size: 11px; color: #94a3b8;"),
                    style="display: flex; align-items: center;"
                ),
                Div(
                    Span(id="save-status", style="margin-right: 1rem; font-size: 0.85rem; color: #64748b;"),
                    # Add row button
                    A(icon("plus", size=16), " Добавить", id="btn-add-row", role="button", cls="secondary", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; margin-right: 0.5rem; text-decoration: none; font-size: 0.8125rem;"),
                    # Import button
                    A(icon("upload", size=16), " Загрузить", id="btn-import", role="button", cls="secondary", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; margin-right: 0.5rem; text-decoration: none; font-size: 0.8125rem;"),
                    Input(type="file", id="file-import", accept=".xlsx,.xls,.csv", style="display: none;"),
                    # Draft workflow buttons (only for draft status)
                    (A(icon("save", size=16), " Сохранить", id="btn-save-draft", role="button", cls="secondary", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; margin-right: 0.5rem; text-decoration: none; font-size: 0.8125rem;", onclick="showSaveConfirmation()") if workflow_status == 'draft' else None),
                    (A(icon("send", size=16), " Передать в закупки", id="btn-submit-procurement", role="button", cls="btn-submit-disabled", style="padding: 0.375rem 0.75rem; display: inline-flex; align-items: center; gap: 0.375rem; text-decoration: none; border-radius: 6px; font-size: 0.8125rem;", onclick="showChecklistModal()") if workflow_status == 'draft' else None),
                    style="display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem;"
                ),
                style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0;"
            ),
            # Handsontable container with enhanced styling
            Div(
                Div(id="items-spreadsheet", style="width: 100%; height: 400px; overflow: hidden;"),
                cls="handsontable-container"
            ),
            # Footer with count
            Div(
                Span(id="footer-count", style="color: #64748b;"),
                style="padding: 0.5rem 1rem; border-top: 1px solid #e2e8f0; font-size: 0.8125rem;"
            ),
            style="margin: 0; background: #fafbfc; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;"
        ),
        # Handsontable initialization script - EXPLICIT SAVE ONLY (no auto-save)
        Script(f"""
            (function() {{
                var quoteId = '{quote_id}';
                var quoteIdn = '{quote.get("idn_quote", "")}';
                var initialData = {items_json};
                var hot = null;
                var hasUnsavedChanges = false;

                function updateCount() {{
                    var count = hot ? hot.countRows() : 0;
                    var el = document.getElementById('items-count');
                    if (el) el.textContent = '(' + count + ')';
                    var footer = document.getElementById('footer-count');
                    if (footer) footer.textContent = 'Всего: ' + count + ' позиций';
                }}

                function showSaveStatus(status) {{
                    var el = document.getElementById('save-status');
                    if (!el) return;
                    if (status === 'saving') {{
                        el.textContent = 'Сохранение...';
                        el.style.color = '#f59e0b';
                    }} else if (status === 'saved') {{
                        el.textContent = 'Сохранено ✓';
                        el.style.color = '#10b981';
                        hasUnsavedChanges = false;
                        setTimeout(function() {{ el.textContent = ''; }}, 2000);
                    }} else if (status === 'error') {{
                        el.textContent = 'Не удалось сохранить';
                        el.style.color = '#ef4444';
                        setTimeout(function() {{ el.textContent = ''; }}, 5000);
                    }}
                }}

                // Bulk save all items - replaces everything in DB
                function saveAllItems() {{
                    // IMPORTANT: Finish any active cell edit before reading data
                    if (hot) hot.deselectCell();
                    var sourceData = hot.getSourceData();
                    var items = sourceData.filter(function(row) {{
                        return row.product_name && row.product_name.trim();
                    }});

                    if (items.length === 0) {{
                        alert('Нет позиций для сохранения');
                        return Promise.resolve(false);
                    }}

                    showSaveStatus('saving');

                    return fetch('/quotes/' + quoteId + '/items/bulk', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ items: items }})
                    }})
                    .then(function(r) {{ return r.json(); }})
                    .then(function(data) {{
                        if (data.success) {{
                            // Update IDs in table data
                            if (data.items) {{
                                var validIdx = 0;
                                for (var i = 0; i < sourceData.length; i++) {{
                                    if (sourceData[i].product_name && sourceData[i].product_name.trim()) {{
                                        if (data.items[validIdx]) {{
                                            sourceData[i].id = data.items[validIdx].id;
                                        }}
                                        validIdx++;
                                    }}
                                }}
                            }}
                            showSaveStatus('saved');
                            return true;
                        }} else {{
                            showSaveStatus('error');
                            alert('Ошибка сохранения: ' + (data.error || 'Неизвестная ошибка'));
                            return false;
                        }}
                    }})
                    .catch(function(e) {{
                        showSaveStatus('error');
                        alert('Ошибка сети: ' + e.message);
                        return false;
                    }});
                }}

                // Make saveAllItems available globally
                window.saveAllItems = saveAllItems;

                // Warn on page leave with unsaved changes
                window.addEventListener('beforeunload', function(e) {{
                    if (hasUnsavedChanges) {{
                        e.preventDefault();
                        e.returnValue = 'Есть несохранённые изменения. Уйти?';
                    }}
                }});

                // Row numbers are assigned on save, not during editing
                function updateRowNumbers() {{
                    updateCount();
                }}

                function initTable() {{
                    var container = document.getElementById('items-spreadsheet');
                    if (!container || typeof Handsontable === 'undefined') return;

                    hot = new Handsontable(container, {{
                        licenseKey: 'non-commercial-and-evaluation',
                        data: initialData.length > 0 ? initialData : [{{row_num: 1, brand: '', product_code: '', product_name: '', quantity: 1, unit: 'шт'}}],
                        colHeaders: ['№', 'Бренд', 'Артикул', 'Наименование', 'Кол-во', 'Ед.изм.'],
                        columns: [
                            {{data: 'row_num', readOnly: true, type: 'numeric', width: 50,
                              renderer: function(instance, td, row, col, prop, value, cellProperties) {{
                                  // Always show visual row number (1-based), regardless of stored value
                                  td.innerHTML = row + 1;
                                  td.style.textAlign = 'center';
                                  td.style.color = '#666';
                                  return td;
                              }}
                            }},
                            {{data: 'brand', type: 'text', width: 120}},
                            {{data: 'product_code', type: 'text', width: 140}},
                            {{data: 'product_name', type: 'text', width: 300}},
                            {{data: 'quantity', type: 'numeric', width: 80}},
                            {{data: 'unit', type: 'dropdown', source: ['шт', 'упак', 'компл', 'кг', 'г', 'т', 'м', 'мм', 'см', 'м²', 'м³', 'л', 'мл'], width: 80}}
                        ],
                        rowHeaders: false,
                        stretchH: 'all',
                        autoWrapRow: true,
                        autoWrapCol: true,
                        contextMenu: ['row_above', 'row_below', 'remove_row', '---------', 'copy', 'cut'],
                        manualColumnResize: true,
                        minSpareRows: 0,
                        afterChange: function(changes, source) {{
                            if (source === 'loadData' || !changes) return;
                            // Mark as having unsaved changes (no auto-save)
                            hasUnsavedChanges = true;
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }},
                        afterCreateRow: function(index, amount, source) {{
                            hasUnsavedChanges = true;
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }},
                        afterRemoveRow: function() {{
                            hasUnsavedChanges = true;
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }},
                        cells: function(row, col) {{
                            var cellProperties = {{}};
                            var rowData = this.instance.getSourceDataAtRow(row);
                            if (rowData && rowData.id) {{
                                cellProperties.title = quoteIdn + '-' + (row + 1);
                            }}
                            return cellProperties;
                        }}
                    }});

                    updateCount();
                    // Make hot available globally for validation
                    window.hot = hot;
                    if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();

                    var btnAdd = document.getElementById('btn-add-row');
                    if (btnAdd) {{
                        btnAdd.addEventListener('click', function() {{
                            // Add empty row - row_num will be assigned on save
                            // The renderer shows visual row index automatically
                            hot.alter('insert_row_below');
                            updateCount();
                            if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                        }});
                    }}

                    var btnFileImport = document.getElementById('btn-import');
                    var fileInput = document.getElementById('file-import');
                    if (btnFileImport && fileInput) {{
                        btnFileImport.addEventListener('click', function() {{
                            fileInput.click();
                        }});
                        fileInput.addEventListener('change', function(e) {{
                            var file = e.target.files[0];
                            if (!file) return;
                            var reader = new FileReader();
                            reader.onload = function(evt) {{
                                var data = new Uint8Array(evt.target.result);
                                var workbook = XLSX.read(data, {{type: 'array'}});
                                var firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                                var jsonData = XLSX.utils.sheet_to_json(firstSheet, {{header: 1}});
                                showFileImportModal(jsonData);
                            }};
                            reader.readAsArrayBuffer(file);
                            e.target.value = '';
                        }});
                    }}

                    window.switchTab = function(tab) {{
                        document.querySelectorAll('.tab-btn').forEach(function(btn) {{ btn.classList.remove('active'); }});
                        var tabBtn = document.getElementById('tab-' + tab);
                        if (tabBtn) tabBtn.classList.add('active');
                    }};
                }}

                function showFileImportModal(jsonData) {{
                    if (jsonData.length < 2) {{
                        alert('Файл пустой или содержит только заголовки');
                        return;
                    }}
                    var headers = jsonData[0];
                    var preview = jsonData.slice(1, 6);

                    function buildOptions(defaultText) {{
                        var opts = '<option value="">' + defaultText + '</option>';
                        for (var i = 0; i < headers.length; i++) {{
                            opts += '<option value="' + i + '">' + (headers[i] || 'Колонка ' + (i+1)) + '</option>';
                        }}
                        return opts;
                    }}

                    function buildPreviewTable() {{
                        var html = '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;"><thead><tr style="background:#f3f4f6;">';
                        for (var i = 0; i < headers.length; i++) {{
                            html += '<th style="padding:0.5rem;border:1px solid #e5e7eb;text-align:left;">' + (headers[i] || '—') + '</th>';
                        }}
                        html += '</tr></thead><tbody>';
                        for (var r = 0; r < preview.length; r++) {{
                            html += '<tr>';
                            for (var c = 0; c < headers.length; c++) {{
                                html += '<td style="padding:0.5rem;border:1px solid #e5e7eb;">' + (preview[r][c] || '') + '</td>';
                            }}
                            html += '</tr>';
                        }}
                        html += '</tbody></table>';
                        return html;
                    }}

                    var modal = document.createElement('div');
                    modal.id = 'file-import-modal';
                    modal.innerHTML = '<div style="position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;">' +
                        '<div style="background:white;padding:2rem;border-radius:12px;max-width:800px;width:90%;max-height:80vh;overflow:auto;">' +
                        '<h3 style="margin-top:0;">Импорт из файла</h3>' +
                        '<p>Найдено строк: ' + (jsonData.length - 1) + '</p>' +
                        '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin-bottom:1.5rem;">' +
                        '<div><label>Наименование *</label><select id="map-name" style="width:100%;padding:0.5rem;">' + buildOptions('-- Выберите колонку --') + '</select></div>' +
                        '<div><label>Артикул</label><select id="map-code" style="width:100%;padding:0.5rem;">' + buildOptions('-- Не выбрано --') + '</select></div>' +
                        '<div><label>Бренд</label><select id="map-brand" style="width:100%;padding:0.5rem;">' + buildOptions('-- Не выбрано --') + '</select></div>' +
                        '<div><label>Количество</label><select id="map-qty" style="width:100%;padding:0.5rem;">' + buildOptions('-- По умолчанию 1 --') + '</select></div>' +
                        '</div>' +
                        '<h4>Превью данных:</h4>' +
                        '<div style="overflow-x:auto;margin-bottom:1.5rem;">' + buildPreviewTable() + '</div>' +
                        '<div style="display:flex;gap:1rem;justify-content:flex-end;">' +
                        '<button onclick="closeFileImportModal()" style="padding:0.75rem 1.5rem;border:1px solid #d1d5db;background:white;border-radius:8px;cursor:pointer;">Отмена</button>' +
                        '<button onclick="runFileImport()" style="padding:0.75rem 1.5rem;background:#6366f1;color:white;border:none;border-radius:8px;cursor:pointer;">Импортировать</button>' +
                        '</div></div></div>';
                    document.body.appendChild(modal);

                    headers.forEach(function(h, i) {{
                        var lower = (h || '').toString().toLowerCase();
                        if (lower.indexOf('наименование') >= 0 || lower.indexOf('название') >= 0 || lower.indexOf('name') >= 0) {{
                            document.getElementById('map-name').value = i;
                        }}
                        if (lower.indexOf('артикул') >= 0 || lower.indexOf('код') >= 0 || lower.indexOf('sku') >= 0) {{
                            document.getElementById('map-code').value = i;
                        }}
                        if (lower.indexOf('бренд') >= 0 || lower.indexOf('brand') >= 0) {{
                            document.getElementById('map-brand').value = i;
                        }}
                        if (lower.indexOf('кол') >= 0 || lower.indexOf('qty') >= 0 || lower.indexOf('quantity') >= 0) {{
                            document.getElementById('map-qty').value = i;
                        }}
                    }});

                    window.closeFileImportModal = function() {{
                        var m = document.getElementById('file-import-modal');
                        if (m) m.remove();
                    }};

                    window.runFileImport = function() {{
                        var nameIdx = document.getElementById('map-name').value;
                        if (nameIdx === '') {{
                            alert('Выберите колонку для наименования');
                            return;
                        }}
                        var codeIdx = document.getElementById('map-code').value;
                        var brandIdx = document.getElementById('map-brand').value;
                        var qtyIdx = document.getElementById('map-qty').value;

                        var newItems = [];
                        var currentCount = hot.countRows();
                        for (var i = 1; i < jsonData.length; i++) {{
                            var row = jsonData[i];
                            var name = row[nameIdx];
                            if (!name) continue;
                            newItems.push({{
                                row_num: currentCount + newItems.length,
                                brand: brandIdx !== '' ? (row[brandIdx] || '') : '',
                                product_code: codeIdx !== '' ? (row[codeIdx] || '') : '',
                                product_name: name,
                                quantity: qtyIdx !== '' ? (parseInt(row[qtyIdx]) || 1) : 1,
                                unit: 'шт'
                            }});
                        }}

                        if (newItems.length === 0) {{
                            alert('Нет данных для импорта');
                            return;
                        }}

                        // Add items to table (in memory) - user will click Save to persist
                        var sourceData = hot.getSourceData();
                        var filtered = sourceData.filter(function(r) {{ return r.product_name && r.product_name.trim(); }});
                        hot.loadData(filtered.concat(newItems));
                        hasUnsavedChanges = true;
                        updateCount();
                        closeFileImportModal();
                        alert('Импортировано ' + newItems.length + ' позиций. Нажмите "Сохранить" для сохранения.');
                        if (typeof updateSubmitButtonState === 'function') updateSubmitButtonState();
                    }};
                }}

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initTable);
                }} else {{
                    initTable();
                }}
            }})();
        """),
        # Handsontable styles
        Style("""
            #items-spreadsheet .htCore {
                font-size: 14px;
            }
            #items-spreadsheet th {
                background: #f9fafb !important;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 0.75rem;
                letter-spacing: 0.05em;
            }
        """),

        # Multi-department approval progress (Bug #8 follow-up)
        Div(
            H3(icon("file-check", size=20), " Прогресс согласования КП", style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;"),

            # Progress bar visual with 5 departments
            Div(
                *[Div(
                    Div(dept_name, style="font-weight: 600; font-size: 0.75rem; margin-bottom: 0.25rem;"),
                    Div(
                        icon("check-circle", size=28) if approval_status.get(dept, {}).get('approved') else
                        icon("clock", size=28) if approval_status.get(dept, {}).get('can_approve') else icon("x-circle", size=28),
                        style="color: #10b981;" if approval_status.get(dept, {}).get('approved') else ("color: #f59e0b;" if approval_status.get(dept, {}).get('can_approve') else "color: #9ca3af;")
                    ),
                    style="flex: 1; text-align: center; padding: 0.5rem; border-right: 2px solid #e5e7eb;" if dept != 'control' else "flex: 1; text-align: center; padding: 0.5rem;"
                ) for dept, dept_name in [('procurement', 'Закупки'), ('logistics', 'Логистика'), ('customs', 'Таможня'), ('sales', 'Продажи'), ('control', 'Контроль')]],
                style="display: flex; margin-bottom: 1.5rem; background: white; border: 1px solid #e5e7eb; border-radius: 6px;"
            ),

            # Department status details
            *[
                Div(
                    # Header with status
                    Div(
                        Span(
                            icon("check-circle", size=18) if dept_status.get('approved') else
                            icon("clock", size=18) if dept_status.get('can_approve') else icon("x-circle", size=18),
                            f" {QUOTE_DEPARTMENT_NAMES[dept]}",
                            style=f"font-weight: 600; font-size: 1.1rem; color: {'#10b981' if dept_status.get('approved') else ('#f59e0b' if dept_status.get('can_approve') else '#9ca3af')}; display: inline-flex; align-items: center; gap: 0.25rem;"
                        ),
                        Span(
                            " - Одобрено" if dept_status.get('approved') else
                            " - Ожидает проверки" if dept_status.get('can_approve') else
                            " - Недоступно",
                            style="color: #059669;" if dept_status.get('approved') else
                            "color: #d97706;" if dept_status.get('can_approve') else "color: #6b7280;"
                        ),
                        style="margin-bottom: 0.75rem;"
                    ),

                    # If approved - show details
                    (Div(
                        P(f"Одобрил: {dept_status.get('approved_by', 'N/A')}", style="margin: 0.25rem 0; font-size: 0.875rem; color: #6b7280;"),
                        P(f"Дата: {dept_status.get('approved_at', '')[:10]}", style="margin: 0.25rem 0; font-size: 0.875rem; color: #6b7280;") if dept_status.get('approved_at') else None,
                        P(f"Комментарий: {dept_status.get('comments')}", style="margin: 0.25rem 0; font-size: 0.875rem;") if dept_status.get('comments') else None,
                    ) if dept_status.get('approved') else None),

                    # If can approve and user has role - show approve form
                    (Div(
                        Form(
                            Input(type="hidden", name="department", value=dept),
                            Textarea(
                                name="comments",
                                placeholder="Комментарий (необязательно)",
                                style="width: 100%; margin-bottom: 0.5rem; min-height: 60px;"
                            ),
                            btn("Одобрить", variant="success", icon_name="check", type="submit"),
                            action=f"/quotes/{quote_id}/approve-department",
                            method="POST"
                        ),
                        style="margin-top: 0.75rem;"
                    ) if dept_status.get('can_approve') and user_can_approve_quote_department(session, dept) else None),

                    # If blocked - show blocking message
                    (P(
                        f"Требуется одобрение: {', '.join([QUOTE_DEPARTMENT_NAMES[d] for d in dept_status.get('blocking_departments', [])])}",
                        style="margin-top: 0.5rem; font-size: 0.875rem; color: #dc2626;"
                    ) if dept_status.get('blocking_departments') and not dept_status.get('approved') else None),

                    cls="card",
                    style="margin-bottom: 1rem; padding: 1rem; background: #f9fafb;"
                )
                for dept, dept_status in [(d, approval_status.get(d, {})) for d in QUOTE_DEPARTMENTS]
            ],

            cls="card",
            style="background: #f0fdf4; border-left: 4px solid #10b981; margin-bottom: 1.5rem;"
        ) if workflow_status in ['pending_review', 'pending_procurement', 'pending_logistics', 'pending_customs', 'pending_sales', 'pending_control', 'pending_spec_control'] and approval_status else None,

        # CSS for submit button states (using high specificity to override Pico)
        Style("""
            a[role="button"].btn-submit-disabled,
            a[role="button"].btn-submit-disabled:hover,
            a.btn-submit-disabled[role="button"],
            #btn-submit-procurement.btn-submit-disabled {
                background: #e5e7eb !important;
                background-color: #e5e7eb !important;
                color: #9ca3af !important;
                border: 1px solid #d1d5db !important;
                pointer-events: none !important;
                cursor: not-allowed !important;
            }
            a[role="button"].btn-submit-enabled,
            a[role="button"].btn-submit-enabled:hover,
            a.btn-submit-enabled[role="button"],
            #btn-submit-procurement.btn-submit-enabled {
                background: #16a34a !important;
                background-color: #16a34a !important;
                color: white !important;
                border: 1px solid #16a34a !important;
                pointer-events: auto !important;
                cursor: pointer !important;
            }
        """) if workflow_status == 'draft' else None,

        # Draft validation script (moved to header buttons)
        Script(f"""
            // Save all items when clicking Save button
            function showSaveConfirmation() {{
                var btn = document.getElementById('btn-save-draft');
                if (!btn) return;
                var originalHTML = btn.innerHTML;
                btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg> Сохранение...';
                btn.style.pointerEvents = 'none';

                // Save delivery city before saving items (BUG-2 fix)
                var cityInput = document.getElementById('delivery-city-input');
                if (cityInput) saveDeliveryCity(cityInput.value);

                // Call global saveAllItems function
                if (typeof window.saveAllItems === 'function') {{
                    window.saveAllItems().then(function(success) {{
                        if (success) {{
                            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Сохранено!';
                            btn.style.background = '#dcfce7';
                            btn.style.borderColor = '#16a34a';
                            btn.style.color = '#16a34a';
                        }} else {{
                            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> Ошибка';
                            btn.style.background = '#fee2e2';
                            btn.style.borderColor = '#ef4444';
                            btn.style.color = '#ef4444';
                        }}
                        btn.style.pointerEvents = '';
                        setTimeout(function() {{
                            btn.innerHTML = originalHTML;
                            btn.style.background = '';
                            btn.style.borderColor = '';
                            btn.style.color = '';
                        }}, 2000);
                    }});
                }} else {{
                    btn.innerHTML = originalHTML;
                    btn.style.pointerEvents = '';
                    alert('Таблица не загружена');
                }}
            }}

            // Server-side quote values (for validation when fields are on another sub-tab)
            var _quoteData = {{
                customer_id: {json.dumps(str(quote.get("customer_id") or ""))},
                seller_company_id: {json.dumps(str(quote.get("seller_company_id") or ""))},
                delivery_city: {json.dumps(quote.get("delivery_city") or "")},
                delivery_country: {json.dumps(quote.get("delivery_country") or "")},
                delivery_method: {json.dumps(quote.get("delivery_method") or "")},
                delivery_terms: {json.dumps(quote.get("delivery_terms") or "")}
            }};

            // Validation for submit to procurement
            function validateForProcurement() {{
                var errors = [];

                // Check header fields — use DOM if available (info subtab), else server-side data
                var customerEl = document.getElementById('inline-customer');
                var customerVal = customerEl ? customerEl.value : _quoteData.customer_id;
                if (!customerVal) errors.push('Клиент');

                var sellerEl = document.getElementById('inline-seller');
                var sellerVal = sellerEl ? sellerEl.value : _quoteData.seller_company_id;
                if (!sellerVal) errors.push('Продавец');

                var cityEl = document.querySelector('input[name="delivery_city"]');
                var cityVal = cityEl ? cityEl.value.trim() : _quoteData.delivery_city.trim();
                if (!cityVal) errors.push('Город доставки');

                var countryEl = document.querySelector('input[name="delivery_country"]');
                var countryVal = countryEl ? countryEl.value.trim() : _quoteData.delivery_country.trim();
                if (!countryVal) errors.push('Страна');

                var methodEl = document.querySelector('select[name="delivery_method"]');
                var methodVal = methodEl ? methodEl.value : _quoteData.delivery_method;
                if (!methodVal) errors.push('Способ доставки');

                var termsEl = document.querySelector('select[name="delivery_terms"]');
                var termsVal = termsEl ? termsEl.value : _quoteData.delivery_terms;
                if (!termsVal) errors.push('Условия поставки');

                // Check items in Handsontable
                if (typeof hot !== 'undefined' && hot) {{
                    var data = hot.getSourceData();
                    var validItems = 0;
                    for (var i = 0; i < data.length; i++) {{
                        var row = data[i];
                        if (row && row.product_name && row.product_name.trim() &&
                            row.quantity && !isNaN(row.quantity) && row.quantity > 0 &&
                            row.unit && row.unit.trim()) {{
                            validItems++;
                        }}
                    }}
                    if (validItems === 0) {{
                        errors.push('Хотя бы одна позиция (наименование, количество, ед.изм.)');
                    }}
                }} else {{
                    errors.push('Позиции не загружены');
                }}

                return errors;
            }}

            // Update submit button state based on validation
            function updateSubmitButtonState() {{
                var btn = document.getElementById('btn-submit-procurement');
                if (!btn) return;

                var errors = validateForProcurement();
                if (errors.length === 0) {{
                    btn.classList.remove('btn-submit-disabled');
                    btn.classList.add('btn-submit-enabled');
                    btn.title = 'Передать КП в отдел закупок';
                }} else {{
                    btn.classList.remove('btn-submit-enabled');
                    btn.classList.add('btn-submit-disabled');
                    btn.title = 'Заполните: ' + errors.join(', ');
                }}
            }}

            // Submit to procurement with validation - saves first, then submits
            function submitToProcurement() {{
                var errors = validateForProcurement();
                if (errors.length > 0) {{
                    alert('Заполните обязательные поля:\\n- ' + errors.join('\\n- '));
                    return false;
                }}

                var btn = document.getElementById('btn-submit-procurement');
                if (btn) {{
                    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg> Сохранение...';
                    btn.style.pointerEvents = 'none';
                }}

                // Save delivery city before saving items (BUG-2 fix)
                var cityInput = document.getElementById('delivery-city-input');
                if (cityInput) saveDeliveryCity(cityInput.value);

                // First save all items, then submit
                if (typeof window.saveAllItems === 'function') {{
                    window.saveAllItems().then(function(saved) {{
                        if (saved) {{
                            // Now submit via POST
                            var form = document.createElement('form');
                            form.method = 'POST';
                            form.action = '/quotes/{quote_id}/submit-procurement';
                            document.body.appendChild(form);
                            form.submit();
                        }} else {{
                            if (btn) {{
                                btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"></path><path d="M22 2 11 13"></path></svg> Передать в закупки';
                                btn.style.pointerEvents = '';
                            }}
                        }}
                    }});
                }} else {{
                    alert('Таблица не загружена');
                    if (btn) btn.style.pointerEvents = '';
                }}
                return true;
            }}

            // saveDeliveryCity and syncCountryFromCity are defined globally
            // in the delivery city input Script block (always rendered).

            // Run validation on page load and on changes
            document.addEventListener('DOMContentLoaded', function() {{
                updateSubmitButtonState();

                // Listen for changes to update button state
                document.querySelectorAll('input, select').forEach(function(el) {{
                    el.addEventListener('change', updateSubmitButtonState);
                }});
            }});

            // Also update after Handsontable changes
            window.updateSubmitButtonState = updateSubmitButtonState;
        """) if workflow_status == "draft" else None,

        # Sales checklist modal (gate for draft -> pending_procurement transition)
        Div(
            Div(
                # Modal header
                Div(
                    icon("clipboard-check", size=20),
                    Span("Контрольный список", style="font-size: 16px; font-weight: 600; margin-left: 8px;"),
                    style="display: flex; align-items: center; margin-bottom: 16px;"
                ),
                P("Заполните информацию перед передачей в закупки:", style="color: #64748b; margin-bottom: 16px; font-size: 0.875rem;"),
                # Checkboxes
                Div(
                    Label(
                        Input(type="checkbox", id="chk_is_estimate", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Это проценка?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    Label(
                        Input(type="checkbox", id="chk_is_tender", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Это тендер?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    Label(
                        Input(type="checkbox", id="chk_direct_request", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Запрашивал ли клиент напрямую?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    Label(
                        Input(type="checkbox", id="chk_trading_org", style="margin-right: 8px; accent-color: #3b82f6;"),
                        "Запрашивал ли клиент через торгующих организаций?",
                        style="display: flex; align-items: center; cursor: pointer; padding: 8px 0;"
                    ),
                    style="margin-bottom: 16px;"
                ),
                # Textarea (required)
                Div(
                    Label(
                        "Что это за оборудование и для чего оно необходимо? ",
                        Span("*", style="color: #ef4444;"),
                        fr="checklist_equipment",
                        style="font-size: 0.875rem; font-weight: 500; display: block; margin-bottom: 6px;"
                    ),
                    Textarea(
                        id="checklist_equipment",
                        placeholder="Опишите оборудование и его назначение...",
                        style="width: 100%; min-height: 80px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; font-family: inherit; resize: vertical;"
                    ),
                    Span("", id="checklist_error", style="color: #ef4444; font-size: 0.75rem; display: none; margin-top: 4px;"),
                    style="margin-bottom: 20px;"
                ),
                # Dialog buttons
                Div(
                    Button("Отмена", type="button", id="checklist_cancel",
                           style="padding: 10px 24px; background: #f1f5f9; color: #374151; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; font-size: 14px;"),
                    Button(
                        icon("send", size=14),
                        " Передать в закупки",
                        type="button", id="checklist_submit",
                        style="padding: 10px 24px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-weight: 500; cursor: pointer; margin-left: 8px; font-size: 14px; display: inline-flex; align-items: center; gap: 6px;"
                    ),
                    style="display: flex; justify-content: flex-end;"
                ),
                style="background: white; padding: 24px; border-radius: 12px; max-width: 500px; width: 90%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);"
            ),
            id="checklist_modal",
            style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000; justify-content: center; align-items: center;"
        ) if workflow_status == "draft" else None,

        # JavaScript for sales checklist modal
        Script(f"""
            function showChecklistModal() {{
                var errors = validateForProcurement();
                if (errors.length > 0) {{
                    alert('Заполните обязательные поля:\\n- ' + errors.join('\\n- '));
                    return;
                }}
                document.getElementById('checklist_modal').style.display = 'flex';
            }}

            (function() {{
                var modal = document.getElementById('checklist_modal');
                if (!modal) return;

                var cancelBtn = document.getElementById('checklist_cancel');
                var submitBtn = document.getElementById('checklist_submit');
                var errorEl = document.getElementById('checklist_error');

                function closeModal() {{
                    modal.style.display = 'none';
                }}

                cancelBtn.addEventListener('click', closeModal);

                // Close on backdrop click
                modal.addEventListener('click', function(e) {{
                    if (e.target === modal) closeModal();
                }});

                // Close on Escape key
                document.addEventListener('keydown', function(e) {{
                    if (e.key === 'Escape' && modal.style.display === 'flex') closeModal();
                }});

                submitBtn.addEventListener('click', function() {{
                    var desc = document.getElementById('checklist_equipment').value.trim();
                    if (!desc) {{
                        errorEl.textContent = 'Это поле обязательно для заполнения';
                        errorEl.style.display = 'block';
                        document.getElementById('checklist_equipment').style.borderColor = '#ef4444';
                        return;
                    }}
                    errorEl.style.display = 'none';
                    document.getElementById('checklist_equipment').style.borderColor = '#e2e8f0';

                    submitBtn.disabled = true;
                    submitBtn.textContent = 'Отправка...';

                    var checklist = {{
                        is_estimate: document.getElementById('chk_is_estimate').checked,
                        is_tender: document.getElementById('chk_is_tender').checked,
                        direct_request: document.getElementById('chk_direct_request').checked,
                        trading_org_request: document.getElementById('chk_trading_org').checked,
                        equipment_description: desc
                    }};

                    // Save delivery city first
                    var cityInput = document.getElementById('delivery-city-input');
                    if (cityInput) saveDeliveryCity(cityInput.value);

                    // Save all items first, then save checklist + submit
                    var savePromise = (typeof window.saveAllItems === 'function')
                        ? window.saveAllItems()
                        : Promise.resolve(true);

                    savePromise.then(function(saved) {{
                        if (!saved) {{
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Передать в закупки';
                            return;
                        }}

                        fetch('/quotes/{quote_id}/submit-procurement', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{checklist: checklist}})
                        }}).then(function(res) {{
                            if (res.redirected) {{
                                window.location.href = res.url;
                            }} else {{
                                return res.json();
                            }}
                        }}).then(function(data) {{
                            if (data && data.redirect) {{
                                window.location.href = data.redirect;
                            }} else if (data && data.error) {{
                                alert('Ошибка: ' + data.error);
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Передать в закупки';
                            }}
                        }}).catch(function(err) {{
                            alert('Ошибка при отправке: ' + err.message);
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Передать в закупки';
                        }});
                    }});
                }});
            }})();
        """) if workflow_status == "draft" else None,

        # Revision banner for sales (Feature: multi-department return)
        Div(
            Div(
                Span("↩ Возвращено на доработку", style="font-weight: 600; font-size: 1.1rem;"),
                style="margin-bottom: 0.5rem;"
            ),
            Div(
                Span("Комментарий контроллёра КП:", style="font-weight: 500;"),
                P(revision_comment, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap;"),
                style="margin-bottom: 1rem;"
            ) if revision_comment else None,
            P("После внесения исправлений верните КП на проверку.", style="margin: 0; font-size: 0.875rem;"),
            cls="card",
            style="background: #fef3c7; border: 2px solid #f59e0b; margin-bottom: 1rem;"
        ) if is_revision else None,

        # Justification banner (Feature: approval justification workflow)
        Div(
            Div(
                Span("📝 Требуется обоснование для согласования", style="font-weight: 600; font-size: 1.1rem;"),
                style="margin-bottom: 0.5rem;"
            ),
            Div(
                Span("Причина согласования (от контроллёра КП):", style="font-weight: 500;"),
                P(approval_reason, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap;"),
                style="margin-bottom: 1rem;"
            ) if approval_reason else None,
            P("Укажите бизнес-обоснование для согласования этого КП топ-менеджером.", style="margin: 0; font-size: 0.875rem;"),
            cls="card",
            style="background: #dbeafe; border: 2px solid #3b82f6; margin-bottom: 1rem;"
        ) if is_justification_needed else None,

        # Workflow Actions (for pending_sales_review - submit for Quote Control, return after revision, or submit justification)
        Div(
            H3("Действия"),
            # Justification flow: Submit justification for approval (Feature: approval justification workflow)
            Div(
                btn_link("Отправить обоснование", href=f"/quotes/{quote_id}/submit-justification", variant="primary", icon_name="check", size="lg"),
                P("Заполнить обоснование и отправить на согласование топ-менеджеру.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
            ) if is_justification_needed else None,
            # Normal flow: Submit for Quote Control
            Form(
                btn("Отправить на контроль КП", variant="primary", icon_name="file-text", size="lg", type="submit"),
                P("Отправить рассчитанный КП на проверку контроллёру.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
                method="post",
                action=f"/quotes/{quote_id}/submit-quote-control"
            ) if not is_revision and not is_justification_needed else None,
            # Revision flow: Return to Quote Control with comment
            Div(
                btn_link("Вернуть на проверку", href=f"/quotes/{quote_id}/return-to-control", variant="success", icon_name="check", size="lg"),
                P("Отправить КП контроллёру после исправлений.", style="margin-top: 0.5rem; font-size: 0.875rem; color: #666;"),
            ) if is_revision else None,
            cls="card", style="border-left: 4px solid #3b82f6;" if is_justification_needed else ("border-left: 4px solid #ec4899;" if not is_revision else "border-left: 4px solid #22c55e;")
        ) if workflow_status == "pending_sales_review" else None,

        # Workflow Actions (for pending_approval - Top Manager approval)
        Div(
            H3(icon("clock", size=20), " Согласование", cls="card-header"),
            P("Этот КП требует вашего одобрения.", style="margin-bottom: 1rem;"),

            # Show approval context (approval_reason from controller, approval_justification from sales)
            Div(
                Div(
                    Span("📋 Причина согласования (от контроллёра):", style="font-weight: 500;"),
                    P(approval_reason, style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap; background: #fef3c7; padding: 0.5rem; border-radius: 4px;"),
                    style="margin-bottom: 0.75rem;"
                ) if approval_reason else None,
                Div(
                    Span("💼 Обоснование менеджера:", style="font-weight: 500;"),
                    P(quote.get("approval_justification", ""), style="margin: 0.25rem 0 0; font-style: italic; white-space: pre-wrap; background: #dbeafe; padding: 0.5rem; border-radius: 4px;"),
                    style="margin-bottom: 1rem;"
                ) if quote.get("approval_justification") else None,
                style="margin-bottom: 1rem;"
            ) if approval_reason or quote.get("approval_justification") else None,

            Form(
                Div(
                    Label("Комментарий (необязательно):", for_="approval_comment"),
                    Input(type="text", name="comment", id="approval_comment",
                          placeholder="Ваш комментарий...", style="width: 100%; margin-bottom: 1rem;"),
                ),
                Div(
                    btn("Одобрить", variant="success", icon_name="check", type="submit", name="action", value="approve"),
                    btn("Отклонить", variant="danger", icon_name="x", type="submit", name="action", value="reject", cls="ml-3"),
                    btn_link("На доработку", href=f"/quotes/{quote_id}/approval-return", variant="secondary", icon_name="arrow-left", cls="ml-3"),
                    style="display: flex; gap: 0.75rem; flex-wrap: wrap;"
                ),
                method="post",
                action=f"/quotes/{quote_id}/manager-decision"
            ),
            cls="card", style="border-left: 4px solid #f59e0b;"
        ) if workflow_status == "pending_approval" and user_has_any_role(session, ["top_manager", "admin"]) else None,

        # Workflow Actions (for approved/sent_to_client - Client Response)
        Div(
            H3(icon("message-circle", size=20), " Ответ клиента", style="display: flex; align-items: center; gap: 0.5rem;"),
            P("КП одобрено. Какой результат от клиента?", style="margin-bottom: 1rem; color: #666;"),
            Div(
                Form(
                    btn("Клиент согласен → Спецификация", variant="success", icon_name="check", type="submit"),
                    method="post",
                    action=f"/quotes/{quote_id}/submit-spec-control",
                    style="display: inline;"
                ),
                style="margin-bottom: 1rem;"
            ),
            # Compact "mark as sent" — only shown when status is still "approved"
            Div(
                Form(
                    btn("Отметить: отправлено клиенту", variant="secondary", icon_name="send", size="sm", type="submit"),
                    method="post",
                    action=f"/quotes/{quote_id}/send-to-client",
                    style="display: inline;"
                ),
                style="border-top: 1px solid #e2e8f0; padding-top: 0.75rem; margin-top: 0.5rem;"
            ) if workflow_status == "approved" else None,
            cls="card", style="border-left: 4px solid #14b8a6;"
        ) if workflow_status in ("approved", "sent_to_client") and user_has_any_role(session, ["sales", "admin"]) else None,

        # Client Change Request Section (for sent_to_client)
        Div(
            H3(icon("rotate-ccw", size=20), " Клиент просит изменения", style="display: flex; align-items: center; gap: 0.5rem;"),
            P("Выберите тип изменений:", style="margin-bottom: 1rem; color: #666;"),
            Form(
                Div(
                    # Change type radio buttons
                    Div(
                        Input(type="radio", name="change_type", value="add_item", id="change_add_item", required=True),
                        Label(" Добавить позицию → Закупка", fr="change_add_item", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    Div(
                        Input(type="radio", name="change_type", value="logistics", id="change_logistics"),
                        Label(" Изменить логистику → Логистика", fr="change_logistics", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    Div(
                        Input(type="radio", name="change_type", value="price", id="change_price"),
                        Label(" Изменить цену → Расчёт", fr="change_price", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),
                    Div(
                        Input(type="radio", name="change_type", value="full", id="change_full"),
                        Label(" Полный пересчёт → Начало", fr="change_full", style="margin-left: 0.25rem;"),
                        style="margin-bottom: 1rem;"
                    ),
                    style="margin-bottom: 1rem;"
                ),
                # Client comment
                Div(
                    Label("Комментарий клиента:", fr="client_comment", style="font-weight: 500;"),
                    Textarea(name="client_comment", id="client_comment", placeholder="Опишите, что именно хочет изменить клиент...",
                             rows="3", style="width: 100%; margin-top: 0.25rem;"),
                    style="margin-bottom: 1rem;"
                ),
                Div(
                    btn("Отправить на доработку", variant="secondary", icon_name="rotate-ccw", size="lg", type="submit"),
                ),
                method="post",
                action=f"/quotes/{quote_id}/client-change-request"
            ),
            cls="card", style="border-left: 4px solid #f59e0b;"
        ) if workflow_status in ("approved", "sent_to_client") and user_has_any_role(session, ["sales", "admin"]) else None,

        # Client Rejected Section (for sent_to_client)
        Div(
            H3(icon("x-circle", size=20), " Клиент отказался", style="display: flex; align-items: center; gap: 0.5rem; color: #dc2626;"),
            Form(
                Div(
                    Label("Причина отказа *", fr="rejection_reason", style="font-weight: 500;"),
                    Select(
                        Option("-- Выберите причину --", value="", disabled=True, selected=True),
                        Option("Цена слишком высокая", value="price_too_high"),
                        Option("Сроки не устраивают", value="delivery_time"),
                        Option("Выбрали другого поставщика", value="competitor"),
                        Option("Проект отменён / заморожен", value="project_cancelled"),
                        Option("Нет бюджета", value="no_budget"),
                        Option("Изменились требования", value="requirements_changed"),
                        Option("Другое", value="other"),
                        name="rejection_reason",
                        id="rejection_reason",
                        required=True,
                        style="width: 100%; margin-top: 0.25rem;"
                    ),
                    style="margin-bottom: 1rem;"
                ),
                Div(
                    Label("Комментарий:", fr="rejection_comment", style="font-weight: 500;"),
                    Textarea(name="rejection_comment", id="rejection_comment",
                             placeholder="Дополнительные детали об отказе...",
                             rows="2", style="width: 100%; margin-top: 0.25rem;"),
                    style="margin-bottom: 1rem;"
                ),
                btn("Отметить как отказ", variant="danger", icon_name="x", type="submit"),
                method="post",
                action=f"/quotes/{quote_id}/client-rejected"
            ),
            cls="card", style="border-left: 4px solid #dc2626;"
        ) if workflow_status in ("approved", "sent_to_client") and user_has_any_role(session, ["sales", "admin"]) else None,

        # Activity log (workflow transitions history)
        workflow_transition_history(quote_id, limit=50, collapsed=True),

        # Back button removed — toolbar at top has all navigation

        # Delete confirmation modal
        Script(f"""
            function showDeleteModal() {{
                const modal = document.createElement('div');
                modal.id = 'delete-modal';
                modal.innerHTML = `
                    <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;">
                        <div style="background: white; padding: 2rem; border-radius: 12px; max-width: 400px; width: 90%;">
                            <h3 style="margin-top: 0; color: #dc2626;">Удалить КП?</h3>
                            <p>КП будет отмечен как отменённый. Это действие можно отменить.</p>
                            <div style="display: flex; gap: 1rem; justify-content: flex-end; margin-top: 1.5rem;">
                                <button onclick="document.getElementById('delete-modal').remove()" style="padding: 0.75rem 1.5rem; border: 1px solid #d1d5db; background: white; border-radius: 8px; cursor: pointer;">Отмена</button>
                                <button onclick="deleteQuote()" style="padding: 0.75rem 1.5rem; background: #dc2626; color: white; border: none; border-radius: 8px; cursor: pointer;">Удалить</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            }}

            function deleteQuote() {{
                fetch('/quotes/{quote_id}/cancel', {{
                    method: 'POST'
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        window.location.href = data.redirect || '/quotes';
                    }} else {{
                        alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                        document.getElementById('delete-modal').remove();
                    }}
                }})
                .catch(err => {{
                    alert('Ошибка: ' + err.message);
                    document.getElementById('delete-modal').remove();
                }});
            }}
        """),
        session=session
    )


# ============================================================================
# SUBMIT QUOTE FOR PROCUREMENT
# ============================================================================

@rt("/quotes/{quote_id}/submit-procurement", methods=["POST"])
async def post(quote_id: str, session, request):
    """Submit a draft quote for procurement evaluation with sales checklist."""
    # Dual auth: JWT (Next.js) or session (FastHTML)
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        user_meta = api_user.user_metadata or {}
        org_id = user_meta.get("org_id")
        if not org_id:
            try:
                sb = get_supabase()
                om = sb.table("organization_members").select("organization_id").eq("user_id", str(api_user.id)).eq("status", "active").order("created_at").limit(1).execute()
                if om.data:
                    org_id = om.data[0]["organization_id"]
            except Exception:
                pass
        user = {
            "id": str(api_user.id),
            "email": api_user.email or "",
            "name": user_meta.get("name", api_user.email or ""),
            "org_id": org_id,
            "org_name": user_meta.get("org_name", ""),
        }
        user_roles = get_user_role_codes(user["id"], org_id)
    else:
        redirect = require_login(session)
        if redirect:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        user = session["user"]
        user_roles = user.get("roles", [])
        org_id = user["org_id"]

    if not user or not user.get("id"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Parse checklist from JSON body
    checklist_data = None
    try:
        body = await request.body()
        print(f"[SUBMIT-PROCUREMENT] quote_id={quote_id}, body_len={len(body) if body else 0}, roles={user_roles}")
        if body:
            data = json.loads(body)
            checklist_data = data.get("checklist")
    except (json.JSONDecodeError, Exception) as e:
        print(f"[SUBMIT-PROCUREMENT] JSON parse error: {e}, body={body[:200] if body else 'empty'}")

    # Validate checklist is present and has required field
    if not checklist_data or not checklist_data.get("equipment_description", "").strip():
        print(f"[SUBMIT-PROCUREMENT] Checklist validation failed: checklist_data={checklist_data}")
        return JSONResponse({"error": "Заполните контрольный список перед передачей в закупки"}, status_code=400)

    # Save checklist to quotes table
    checklist_to_save = {
        "is_estimate": bool(checklist_data.get("is_estimate", False)),
        "is_tender": bool(checklist_data.get("is_tender", False)),
        "direct_request": bool(checklist_data.get("direct_request", False)),
        "trading_org_request": bool(checklist_data.get("trading_org_request", False)),
        "equipment_description": checklist_data["equipment_description"].strip(),
        "completed_at": datetime.utcnow().isoformat(),
        "completed_by": user["id"]
    }

    supabase = get_supabase()
    try:
        supabase.table("quotes") \
            .update({"sales_checklist": checklist_to_save}) \
            .eq("id", quote_id) \
            .eq("organization_id", org_id) \
            .execute()
    except Exception as e:
        return JSONResponse({"error": f"Ошибка сохранения чеклиста: {str(e)}"}, status_code=500)

    # Use the workflow service to transition to pending_procurement
    result = transition_to_pending_procurement(
        quote_id=quote_id,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Submitted by sales for procurement evaluation"
    )

    if result.success:
        print(f"[SUBMIT-PROCUREMENT] SUCCESS quote_id={quote_id}")
        return JSONResponse({"redirect": f"/quotes/{quote_id}"})
    else:
        print(f"[SUBMIT-PROCUREMENT] TRANSITION FAILED: {result.error_message}")
        return JSONResponse({"error": f"Ошибка перехода: {result.error_message}"}, status_code=400)


# ============================================================================
# SUBMIT QUOTE FOR QUOTE CONTROL
# ============================================================================

@rt("/quotes/{quote_id}/submit-quote-control")
def post(quote_id: str, session):
    """Submit a quote from pending_sales_review to pending_quote_control."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    # Use the workflow service to transition to pending_quote_control
    result = transition_quote_status(
        quote_id=quote_id,
        to_status="pending_quote_control",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Submitted by sales for quote control review"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error submitting quote: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SALES - RETURN TO QUOTE CONTROL AFTER REVISION (Feature: multi-department return)
# ============================================================================

@rt("/quotes/{quote_id}/return-to-control")
def get(quote_id: str, session):
    """
    Form for sales to return a revised quote back to quote control.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data
    workflow_status = quote.get("workflow_status", "draft")
    revision_comment = quote.get("revision_comment", "")
    idn_quote = quote.get("idn_quote", f"#{quote_id[:8]}")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    if workflow_status != "pending_sales_review":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 24px;
    """

    section_header_style = """
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    """

    comment_box_style = """
        background: #fef3c7;
        border-left: 3px solid #f59e0b;
        padding: 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 24px;
    """

    textarea_style = """
        width: 100%;
        min-height: 120px;
        padding: 12px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-size: 14px;
        background: #f8fafc;
        font-family: inherit;
        resize: vertical;
        box-sizing: border-box;
    """

    return page_layout(f"Вернуть на проверку - {idn_quote}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), f" Назад к КП {idn_quote}", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1("Вернуть КП на проверку",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                icon("users", size=14, style="color: #64748b;"),
                Span(f"Клиент: {customer_name}", style="color: #475569;"),
                style="display: flex; align-items: center; gap: 8px; font-size: 14px;"
            ),
            style=header_style
        ),

        # Original comment (if present)
        Div(
            Div(icon("message-circle", size=14), " Исходный комментарий контроллёра", style=section_header_style),
            P(revision_comment if revision_comment else "— нет комментария —",
              style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.5;"),
            style=comment_box_style
        ) if revision_comment else None,

        # Form
        Form(
            Div(
                Div(icon("edit-3", size=14), " Комментарий об исправлениях *", style=section_header_style),
                P("Опишите, какие исправления были внесены:",
                  style="color: #64748b; font-size: 13px; margin: 0 0 12px 0;"),
                Textarea(
                    name="comment",
                    placeholder="Исправлена наценка...\nОбновлены условия оплаты...\nИзменены данные клиента...",
                    required=True,
                    style=textarea_style
                ),
                style="margin-bottom: 24px;"
            ),
            Div(
                Button(icon("check", size=14), " Вернуть на проверку", type="submit",
                       style="padding: 10px 20px; background: #22c55e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/quotes/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                style="display: flex; gap: 12px;"
            ),
            action=f"/quotes/{quote_id}/return-to-control",
            method="post",
            style=form_card_style
        ),
        session=session
    )


@rt("/quotes/{quote_id}/return-to-control")
def post(quote_id: str, session, comment: str = ""):
    """
    Handle return to quote control from sales.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий об исправлениях."),
            A("← Вернуться", href=f"/quotes/{quote_id}/return-to-control"),
            session=session
        )

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("workflow_status") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    current_status = quote_result.data[0].get("workflow_status", "draft")

    if current_status != "pending_sales_review":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_QUOTE_CONTROL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"Исправления от продаж: {comment.strip()}"
    )

    if result.success:
        supabase.table("quotes").update({
            "revision_department": None,
            "revision_comment": None,
            "revision_returned_at": None
        }).eq("id", quote_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " КП возвращено на проверку"),
            P("КП отправлено контроллёру КП для повторной проверки."),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось вернуть КП: {result.error_message}"),
            A("← Назад", href=f"/quotes/{quote_id}/return-to-control"),
            session=session
        )


# ============================================================================
# SUBMIT JUSTIFICATION (Feature: approval justification workflow)
# ============================================================================

@rt("/quotes/{quote_id}/submit-justification")
def get(session, quote_id: str):
    """
    Justification form - sales manager provides business case for approval.

    Feature: Approval justification workflow (Variant B)
    - Controller specifies why approval is needed (approval_reason)
    - Sales manager provides business justification (approval_justification)
    - Then quote goes to top manager with full context
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has sales role
    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    needs_justification = quote.get("needs_justification", False)
    approval_reason = quote.get("approval_reason", "")

    # Check if quote is in correct status and needs justification
    if workflow_status != "pending_sales_review" or not needs_justification:
        return page_layout("Обоснование не требуется",
            H1("Обоснование не требуется"),
            P("Это КП не требует обоснования для согласования."),
            A("← Вернуться к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    return page_layout(f"Обоснование - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к КП", href=f"/quotes/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(icon("file-text", size=28), f" Обоснование для согласования {idn_quote}", cls="page-header"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Approval reason from controller
        Div(
            H3("Причина согласования (от контроллёра КП)"),
            P(approval_reason, style="font-style: italic; white-space: pre-wrap; background: #f3f4f6; padding: 1rem; border-radius: 6px;"),
            cls="card",
            style="margin-bottom: 1rem; background: #fef3c7;"
        ) if approval_reason else None,

        # Form
        Form(
            Div(
                H3("Ваше обоснование", style="margin-bottom: 0.5rem;"),
                P("Объясните, почему эта сделка важна для компании и почему предложенные условия обоснованы.",
                  style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;"),
                Textarea(
                    name="justification",
                    id="justification",
                    placeholder="Укажите бизнес-обоснование...\n\nНапример:\n- Стратегический клиент с большим потенциалом\n- Первая сделка для входа в новый сегмент\n- Конкурентная ситуация требует гибкости по цене",
                    required=True,
                    style="width: 100%; min-height: 200px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                btn("Отправить на согласование", variant="primary", icon_name="send", type="submit"),
                btn_link("Отмена", href=f"/quotes/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 1rem;"
            ),

            action=f"/quotes/{quote_id}/submit-justification",
            method="post",
            cls="card"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/submit-justification")
def post(session, quote_id: str, justification: str = ""):
    """
    Handle justification form submission.

    1. Validate justification is provided
    2. Save approval_justification
    3. Clear needs_justification flag
    4. Call request_approval to send to top manager
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has sales role
    if not user_has_any_role(session, ["sales", "sales_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Validate justification
    if not justification or not justification.strip():
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P("Необходимо указать обоснование для согласования."),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/submit-justification"),
            session=session
        )

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("workflow_status, needs_justification, idn_quote, total_amount, currency, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")
    needs_justification = quote.get("needs_justification", False)
    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "")
    total_amount = quote.get("total_amount")

    # Verify quote is in correct status
    if workflow_status != "pending_sales_review" or not needs_justification:
        return page_layout("Ошибка",
            H1("Обоснование не требуется"),
            P("Это КП не находится в статусе ожидания обоснования."),
            A("← Вернуться к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Save justification and clear flag
    supabase.table("quotes").update({
        "approval_justification": justification.strip(),
        "needs_justification": False
    }).eq("id", quote_id).execute()

    # Get user's role codes for transition
    user_roles = get_user_roles_from_session(session)

    # Transition directly from pending_sales_review to pending_approval
    # (using new transition added for justification workflow)
    from services.workflow_service import transition_quote_status, WorkflowStatus
    from services.approval_service import create_approvals_for_role
    from services.telegram_service import send_approval_notification_for_quote
    import asyncio

    transition_result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_APPROVAL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"[С обоснованием] {justification.strip()[:200]}..."
    )

    if not transition_result.success:
        return page_layout("Ошибка",
            H1("Ошибка отправки"),
            P(f"Не удалось отправить КП на согласование: {transition_result.error_message}"),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/submit-justification"),
            session=session
        )

    # Create approval records for top_manager/admin users
    approvals = create_approvals_for_role(
        quote_id=quote_id,
        organization_id=org_id,
        requested_by=user_id,
        reason=f"[С обоснованием менеджера] {justification.strip()[:200]}...",
        role_codes=['top_manager', 'admin'],
        approval_type='top_manager'
    )
    approvals_created = len(approvals)

    # Send Telegram notifications
    notifications_sent = 0
    if approvals_created > 0:
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            notification_result = loop.run_until_complete(
                send_approval_notification_for_quote(
                    quote_id=quote_id,
                    approval_reason=f"[С обоснованием менеджера] {justification.strip()[:100]}...",
                    requester_id=user_id
                )
            )
            notifications_sent = notification_result.get('telegram_sent', 0)
        except Exception as e:
            print(f"Error sending approval notifications: {e}")

    details = []
    if approvals_created > 0:
        details.append(P(f"Создано запросов на согласование: {approvals_created}"))
    if notifications_sent > 0:
        details.append(P(f"Отправлено уведомлений в Telegram: {notifications_sent}"))

    return page_layout("Успешно",
        H1(icon("check", size=28), " КП отправлено на согласование", cls="page-header"),
        P(f"КП {idn_quote} с вашим обоснованием отправлено на согласование топ-менеджеру."),
        *details,
        P("Вы получите уведомление о решении.", style="color: #666;"),
        btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
        session=session
    )


# ============================================================================
# MANAGER APPROVAL/REJECTION
# ============================================================================

@rt("/quotes/{quote_id}/manager-decision")
def post(quote_id: str, session, action: str = "", comment: str = ""):
    """Top manager approves or rejects a quote."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    # Check role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if action == "approve":
        to_status = "approved"
        comment = comment or "Одобрено топ-менеджером"
    elif action == "reject":
        to_status = "rejected"
        if not comment:
            return page_layout("Error",
                Div("Для отклонения необходимо указать причину.", cls="alert alert-error"),
                A("← Назад к КП", href=f"/quotes/{quote_id}"),
                session=session
            )
    else:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    # Use the workflow service to transition
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=to_status,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=comment
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# TOP MANAGER - RETURN FOR REVISION (Feature: multi-department return)
# ============================================================================

@rt("/quotes/{quote_id}/approval-return")
def get(session, quote_id: str):
    """
    Return for revision form for top manager.
    Similar to quote controller's return form - can return to any department.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    # Check if user has top_manager role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data[0]
    workflow_status = quote.get("workflow_status", "draft")

    # Check if quote is in pending_approval status
    if workflow_status != "pending_approval":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП не находится в статусе ожидания согласования."),
            A("← Вернуться к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    idn_quote = quote.get("idn_quote", "")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    return page_layout(f"Возврат на доработку - {idn_quote}",
        # Header
        Div(
            A("← Вернуться к КП", href=f"/quotes/{quote_id}", style="color: #3b82f6; text-decoration: none;"),
            H1(icon("arrow-left", size=28), f" Возврат КП {idn_quote} на доработку", cls="page-header"),
            P(f"Клиент: {customer_name}", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Department selection form
        Form(
            Div(
                H3("Выберите отдел для доработки", style="margin-bottom: 1rem;"),
                Div(
                    Input(type="radio", name="department", value="quote_control", id="dept_control", checked=True),
                    Label(" Контроль КП", for_="dept_control"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="sales", id="dept_sales"),
                    Label(" Продажи", for_="dept_sales"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="procurement", id="dept_procurement"),
                    Label(" Закупки", for_="dept_procurement"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="logistics", id="dept_logistics"),
                    Label(" Логистика", for_="dept_logistics"),
                    style="margin-bottom: 0.5rem;"
                ),
                Div(
                    Input(type="radio", name="department", value="customs", id="dept_customs"),
                    Label(" Таможня", for_="dept_customs"),
                    style="margin-bottom: 1rem;"
                ),
                style="margin-bottom: 1rem;"
            ),

            Div(
                H3("Комментарий", style="margin-bottom: 0.5rem;"),
                P("Укажите, что необходимо исправить.", style="color: #666; font-size: 0.875rem; margin-bottom: 1rem;"),
                Textarea(
                    name="comment",
                    id="comment",
                    placeholder="Укажите, что необходимо исправить...",
                    required=True,
                    style="width: 100%; min-height: 120px; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; resize: vertical;"
                ),
                style="margin-bottom: 1rem;"
            ),

            # Action buttons
            Div(
                btn("Вернуть на доработку", variant="secondary", icon_name="arrow-left", type="submit"),
                btn_link("Отмена", href=f"/quotes/{quote_id}", variant="ghost"),
                style="display: flex; align-items: center; gap: 1rem;"
            ),

            action=f"/quotes/{quote_id}/approval-return",
            method="post",
            cls="card"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/approval-return")
def post(session, quote_id: str, department: str = "quote_control", comment: str = ""):
    """
    Handle return for revision from top manager.
    Routes to the selected department with revision tracking.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has top_manager role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Validate comment
    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий с описанием необходимых исправлений."),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/approval-return"),
            session=session
        )

    # Map department to workflow status
    department_status_map = {
        "quote_control": WorkflowStatus.PENDING_QUOTE_CONTROL,
        "sales": WorkflowStatus.PENDING_SALES_REVIEW,
        "procurement": WorkflowStatus.PENDING_PROCUREMENT,
        "logistics": WorkflowStatus.PENDING_LOGISTICS,
        "customs": WorkflowStatus.PENDING_CUSTOMS,
    }

    department_names = {
        "quote_control": "Контроль КП",
        "sales": "Продажи",
        "procurement": "Закупки",
        "logistics": "Логистика",
        "customs": "Таможня",
    }

    to_status = department_status_map.get(department, WorkflowStatus.PENDING_QUOTE_CONTROL)
    department_name = department_names.get(department, "Контроль КП")

    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=to_status,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"[Возврат от топ-менеджера] {comment.strip()}"
    )

    if result.success:
        # Save revision tracking info
        supabase = get_supabase()
        supabase.table("quotes").update({
            "revision_department": department if department != "quote_control" else None,
            "revision_comment": comment.strip() if department != "quote_control" else None,
            "revision_returned_at": datetime.now(timezone.utc).isoformat() if department != "quote_control" else None
        }).eq("id", quote_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " КП возвращено на доработку"),
            P(f"КП отправлено в отдел «{department_name}» для доработки."),
            P(f"Комментарий: {comment.strip()}", style="color: #666; font-style: italic;"),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось вернуть КП: {result.error_message}"),
            A("← Вернуться к форме", href=f"/quotes/{quote_id}/approval-return"),
            session=session
        )


# ============================================================================
# SEND TO CLIENT
# ============================================================================

@rt("/quotes/{quote_id}/send-to-client")
def post(quote_id: str, session, sent_to_email: str = ""):
    """Send approved quote to client."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Save sent_at timestamp and sent_to_email
    from datetime import datetime
    supabase = get_supabase()
    supabase.table("quotes").update({
        "sent_at": datetime.utcnow().isoformat(),
        "sent_to_email": sent_to_email.strip() if sent_to_email else None
    }).eq("id", quote_id).execute()

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="sent_to_client",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=f"Quote sent to client at {sent_to_email}" if sent_to_email else "Quote sent to client"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# CLIENT CHANGE REQUEST
# ============================================================================

@rt("/quotes/{quote_id}/client-change-request")
def post(quote_id: str, session, change_type: str = "", client_comment: str = ""):
    """Handle client change request - route to appropriate workflow stage."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Validate change type
    valid_types = ["add_item", "logistics", "price", "full"]
    if change_type not in valid_types:
        return page_layout("Error",
            Div("Invalid change type", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Record the change request
    from datetime import datetime
    try:
        supabase.table("quote_change_requests").insert({
            "quote_id": quote_id,
            "change_type": change_type,
            "client_comment": client_comment.strip() if client_comment else None,
            "requested_by": user["id"],
            "requested_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        # Table might not exist yet if migration not applied - continue anyway
        pass

    # Map change type to target workflow status
    status_map = {
        "add_item": "pending_procurement",
        "logistics": "pending_logistics",
        "price": "pending_sales_review",
        "full": "pending_procurement"
    }

    target_status = status_map.get(change_type, "pending_procurement")

    # Update quote with partial_recalc flag
    try:
        supabase.table("quotes").update({
            "partial_recalc": change_type
        }).eq("id", quote_id).execute()
    except Exception:
        pass

    # Transition quote status
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=target_status,
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=f"Client change request: {change_type}. Comment: {client_comment}" if client_comment else f"Client change request: {change_type}"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SUBMIT FOR SPEC CONTROL
# ============================================================================

@rt("/quotes/{quote_id}/submit-spec-control")
def post(quote_id: str, session):
    """Submit quote for specification control."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="pending_spec_control",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment="Client accepted, submitted for specification"
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Error",
            Div(f"Error: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


@rt("/quotes/{quote_id}/client-rejected")
def post(quote_id: str, session, rejection_reason: str = "", rejection_comment: str = ""):
    """
    Mark quote as rejected by client with reason.
    Transitions to 'rejected' status and stores rejection reason.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_roles = user.get("roles", [])

    if not user_has_any_role(session, ["sales", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    # Map rejection reason codes to human-readable labels
    reason_labels = {
        "price_too_high": "Цена слишком высокая",
        "delivery_time": "Сроки не устраивают",
        "competitor": "Выбрали другого поставщика",
        "project_cancelled": "Проект отменён / заморожен",
        "no_budget": "Нет бюджета",
        "requirements_changed": "Изменились требования",
        "other": "Другое",
    }

    reason_label = reason_labels.get(rejection_reason, rejection_reason)

    # Build comment with reason
    comment_parts = [f"Причина отказа: {reason_label}"]
    if rejection_comment and rejection_comment.strip():
        comment_parts.append(f"Комментарий: {rejection_comment.strip()}")

    full_comment = ". ".join(comment_parts)

    # Store rejection reason in quote metadata
    supabase = get_supabase()
    try:
        supabase.table("quotes").update({
            "rejection_reason": rejection_reason,
            "rejection_comment": rejection_comment.strip() if rejection_comment else None,
            "rejected_at": datetime.now().isoformat(),
            "rejected_by": user["id"]
        }).eq("id", quote_id).execute()
    except Exception as e:
        print(f"Error storing rejection reason: {e}")
        # Continue even if metadata update fails

    result = transition_quote_status(
        quote_id=quote_id,
        to_status="rejected",
        actor_id=user["id"],
        actor_roles=user_roles,
        comment=full_comment
    )

    if result.success:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)
    else:
        return page_layout("Ошибка",
            Div(f"Ошибка: {result.error_message}", cls="alert alert-error"),
            A("← Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )


@rt("/quotes/{quote_id}/approve-department")
def post(quote_id: str, session, department: str = "", comments: str = ""):
    """
    Approve quote for a specific department.

    Bug #8 follow-up: Multi-department approval workflow
    POST handler for department approval form.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    # Validate department parameter
    if not department:
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    # Check if user has permission to approve for this department
    if not user_can_approve_quote_department(session, department):
        return RedirectResponse("/unauthorized", status_code=303)

    # Perform approval
    success, message = approve_quote_department(
        quote_id=quote_id,
        organization_id=user["org_id"],
        department=department,
        user_id=user["id"],
        comments=comments if comments else None
    )

    # Debug logging
    print(f"[DEBUG] Approve department: dept={department}, success={success}, message={message}")

    # Redirect back to quote detail page
    # TODO: Add flash message with success/error message
    return RedirectResponse(f"/quotes/{quote_id}", status_code=303)


# ============================================================================
# QUOTE PRODUCTS
# ============================================================================

# ============================================================================
# QUOTE ITEM API (Handsontable)
# ============================================================================
# Note: /quotes/{quote_id}/products page was removed (2026-01-29)
# Product entry is now done via Handsontable on /quotes/{quote_id} overview page

@rt("/quotes/{quote_id}/items/{item_id}", methods=["PATCH"])
async def patch_quote_item(quote_id: str, item_id: str, session, request):
    """Update a single quote item field (for Handsontable auto-save)"""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    # Parse JSON body
    body = await request.body()
    try:
        data = json.loads(body)
    except:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    # Allowed fields for update
    item_update_fields = ['product_name', 'product_code', 'brand', 'quantity', 'unit']
    update_data = {k: v for k, v in data.items() if k in item_update_fields}

    if not update_data:
        return JSONResponse({"success": False, "error": "No valid fields to update"}, status_code=400)

    try:
        result = supabase.table("quote_items") \
            .update(update_data) \
            .eq("id", item_id) \
            .eq("quote_id", quote_id) \
            .execute()

        if result.data:
            return JSONResponse({"success": True, "item": result.data[0]})
        else:
            return JSONResponse({"success": False, "error": "Item not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@rt("/quotes/{quote_id}/items/bulk", methods=["POST"])
async def bulk_insert_quote_items(quote_id: str, session, request):
    """Bulk insert quote items (for import functionality)"""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id, organization_id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    # Parse JSON body
    body = await request.body()
    try:
        data = json.loads(body)
    except:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    items_data = data.get("items", [])
    if not items_data:
        return JSONResponse({"success": False, "error": "No items provided"}, status_code=400)

    # First, delete existing items for this quote (we're replacing all)
    try:
        supabase.table("quote_items") \
            .delete() \
            .eq("quote_id", quote_id) \
            .execute()
    except Exception as e:
        pass  # Ignore if no items existed

    # Prepare items for insert
    # base_price_vat is nullable with default 0, so we don't pass it
    # row_num column doesn't exist - ordering is by created_at
    insert_items = []
    for idx, item in enumerate(items_data, start=1):
        insert_items.append({
            "quote_id": quote_id,
            "product_name": item.get("product_name", ""),
            "product_code": item.get("product_code", ""),
            "brand": item.get("brand", ""),
            "quantity": int(item.get("quantity", 1)),
            "unit": item.get("unit", "шт")
        })

    try:
        result = supabase.table("quote_items") \
            .insert(insert_items) \
            .execute()

        return JSONResponse({
            "success": True,
            "items": [{"id": item["id"]} for item in result.data],
            "count": len(result.data)
        })
    except Exception as e:
        print(f"Bulk insert error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@rt("/quotes/{quote_id}/inline", methods=["PATCH"])
async def inline_update_quote(quote_id: str, session, request):
    """Inline update a single quote field via HTMX"""
    redirect = require_login(session)
    if redirect:
        return ""

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return ""

    # Parse form data from HTMX
    form = await request.form()
    field = form.get("field")
    value = form.get("value")

    # Debug logging to track "undefined" issue
    print(f"[INLINE UPDATE] quote_id={quote_id}, field={field}, value={repr(value)}")

    if not field:
        return ""

    # Editable fields for inline update
    editable_fields = [
        'customer_id', 'seller_company_id', 'contact_person_id',
        'delivery_city', 'delivery_country', 'delivery_method',
        'delivery_priority', 'delivery_terms', 'delivery_address',
        'currency', 'payment_terms', 'notes', 'validity_days',
        'additional_info'
    ]

    if field not in editable_fields:
        return ""

    # Handle empty values and the string "undefined" (JavaScript serialization bug)
    if value == "" or value is None or value == "undefined":
        value = None

    # Convert integer fields
    if field == "validity_days" and value is not None:
        try:
            value = max(1, int(value))
        except (ValueError, TypeError):
            value = 30

    try:
        update_data = {field: value}
        # When customer changes, clear contact_person_id (belongs to old customer)
        if field == "customer_id":
            update_data["contact_person_id"] = None
        supabase.table("quotes") \
            .update(update_data) \
            .eq("id", quote_id) \
            .execute()
        return ""  # HTMX swap="none", no response needed
    except Exception as e:
        print(f"Inline update error: {e}")
        return ""


@rt("/quotes/{quote_id}/cancel", methods=["POST"])
def cancel_quote(quote_id: str, session):
    """Soft delete quote by setting workflow_status to 'cancelled'"""
    redirect = require_login(session)
    if redirect:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Verify quote belongs to user's org
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

    try:
        result = supabase.table("quotes") \
            .update({
                "workflow_status": "cancelled",
                "stage_entered_at": datetime.now(timezone.utc).isoformat(),
                "overdue_notified_at": None,
            }) \
            .eq("id", quote_id) \
            .execute()

        return JSONResponse({"success": True, "redirect": "/quotes"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ============================================================================
# QUOTE EDIT
# ============================================================================

@rt("/quotes/{quote_id}/edit")
def get(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote (seller_company_id column may not exist if migration not applied)
    result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = result.data[0]

    # Get customers
    customers_result = supabase.table("customers") \
        .select("id, name, inn") \
        .eq("organization_id", user["org_id"]) \
        .order("name") \
        .execute()

    customers = customers_result.data or []

    # Get seller companies for dropdown
    from services.seller_company_service import get_all_seller_companies, format_seller_company_for_dropdown
    seller_companies = get_all_seller_companies(organization_id=user["org_id"], is_active=True)

    # Get customer contacts for contact person dropdown
    edit_contacts = []
    if quote.get("customer_id"):
        try:
            edit_contacts_result = supabase.table("customer_contacts") \
                .select("id, name, position, phone, is_lpr") \
                .eq("customer_id", quote["customer_id"]) \
                .order("is_lpr", desc=True) \
                .order("name") \
                .execute()
            edit_contacts = edit_contacts_result.data or []
        except Exception:
            pass

    # Prepare seller company info for pre-selected value
    # Note: seller_company_id column may not exist if migration 028 not applied
    selected_seller_id = quote.get("seller_company_id")
    selected_seller_label = None
    # We no longer join seller_companies since FK may not exist

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    section_header_style = """
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    input_style = """
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        width: 100%;
        box-sizing: border-box;
    """

    select_style = """
        padding: 10px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 14px;
        background: #f8fafc;
        width: 100%;
        box-sizing: border-box;
    """

    label_style = "display: block; font-size: 13px; color: #475569; margin-bottom: 6px; font-weight: 500;"

    form_group_style = "margin-bottom: 16px;"

    grid_2col_style = "display: grid; grid-template-columns: 1fr 1fr; gap: 20px;"

    return page_layout(f"Редактирование {quote.get('idn_quote', '')}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), " Назад к КП", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1(f"Редактирование КП {quote.get('idn_quote', '')}",
               style="margin: 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            style=header_style
        ),

        Form(
            # Section 1: Client & Status
            Div(
                Div(icon("users", size=14), " Клиент и статус", style=section_header_style),
                Div(
                    Div(
                        Label("Клиент *", style=label_style),
                        Select(
                            *[Option(
                                f"{c['name']} ({c.get('inn', '')})",
                                value=c["id"],
                                selected=(c["id"] == quote.get("customer_id"))
                            ) for c in customers],
                            name="customer_id", required=True,
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    Div(
                        Label("Статус", style=label_style),
                        Select(
                            Option("Черновик", value="draft", selected=quote.get("status") == "draft"),
                            Option("Отправлено", value="sent", selected=quote.get("status") == "sent"),
                            Option("Одобрено", value="approved", selected=quote.get("status") == "approved"),
                            Option("Отклонено", value="rejected", selected=quote.get("status") == "rejected"),
                            name="status",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Label("Компания-продавец *", style=label_style),
                    Select(
                        Option("Выберите компанию...", value=""),
                        *[Option(
                            format_seller_company_for_dropdown(sc),
                            value=sc.id,
                            selected=(str(sc.id) == str(selected_seller_id)) if selected_seller_id else False
                        ) for sc in seller_companies],
                        name="seller_company_id", required=True,
                        style=select_style
                    ),
                    Small("Наше юридическое лицо для продажи",
                          style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                    style=form_group_style
                ),
                Div(
                    Label("Контактное лицо", style=label_style),
                    Select(
                        Option("— Не выбрано —", value=""),
                        *[Option(
                            f"{'⭐ ' if c.get('is_lpr') else ''}{c['name']}" + (f" ({c.get('position', '')})" if c.get('position') else ""),
                            value=c["id"],
                            selected=(c["id"] == quote.get("contact_person_id"))
                        ) for c in edit_contacts],
                        name="contact_person_id",
                        style=select_style
                    ),
                    Small("ЛПР или контакт клиента",
                          style="color: #94a3b8; font-size: 12px; margin-top: 4px; display: block;"),
                    style=form_group_style
                ),
                style=form_card_style
            ),

            # Section 2: Delivery
            Div(
                Div(icon("truck", size=14), " Доставка", style=section_header_style),
                Div(
                    Div(
                        Label("Город доставки", style=label_style),
                        Input(
                            name="delivery_city",
                            id="edit-delivery-city-input",
                            type="text",
                            value=quote.get("delivery_city", "") or "",
                            placeholder="Москва, Пекин и т.д.",
                            list="city-datalist",
                            style=input_style,
                            hx_get="/api/cities/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#city-datalist",
                            hx_vals='js:{"q": document.getElementById("edit-delivery-city-input").value}',
                            hx_swap="innerHTML"
                        ),
                        Datalist(id="city-datalist"),
                        style=form_group_style
                    ),
                    Div(
                        Label("Страна доставки", style=label_style),
                        Input(
                            name="delivery_country",
                            type="text",
                            value=quote.get("delivery_country", "") or "",
                            placeholder="Россия, Китай и т.д.",
                            style=input_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Div(
                        Label("Способ доставки", style=label_style),
                        Select(
                            Option("-- Выберите способ --", value="", selected=not quote.get("delivery_method")),
                            Option("Авиа", value="air", selected=quote.get("delivery_method") == "air"),
                            Option("Авто", value="auto", selected=quote.get("delivery_method") == "auto"),
                            Option("Море", value="sea", selected=quote.get("delivery_method") == "sea"),
                            Option("Мультимодально", value="multimodal", selected=quote.get("delivery_method") == "multimodal"),
                            name="delivery_method",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    Div(
                        Label("Условия поставки", style=label_style),
                        Select(
                            Option("EXW", value="EXW", selected=quote.get("delivery_terms") == "EXW"),
                            Option("FOB", value="FOB", selected=quote.get("delivery_terms") == "FOB"),
                            Option("CIF", value="CIF", selected=quote.get("delivery_terms") == "CIF"),
                            Option("DDP", value="DDP", selected=quote.get("delivery_terms") == "DDP"),
                            name="delivery_terms",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                Div(
                    Div(
                        Label("Приоритет доставки", style=label_style),
                        Select(
                            Option("-- Выберите приоритет --", value="", selected=not quote.get("delivery_priority")),
                            Option("Лучше быстро", value="fast", selected=quote.get("delivery_priority") == "fast"),
                            Option("Лучше дешево", value="cheap", selected=quote.get("delivery_priority") == "cheap"),
                            Option("Обычно", value="normal", selected=quote.get("delivery_priority") == "normal"),
                            name="delivery_priority",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    style=grid_2col_style
                ),
                style=form_card_style
            ),

            # Section 3: Terms
            Div(
                Div(icon("file-text", size=14), " Условия оплаты и сроки", style=section_header_style),
                Div(
                    Div(
                        Label("Валюта", style=label_style),
                        Select(
                            Option("RUB", value="RUB", selected=quote.get("currency") == "RUB"),
                            Option("USD", value="USD", selected=quote.get("currency") == "USD"),
                            Option("EUR", value="EUR", selected=quote.get("currency") == "EUR"),
                            name="currency",
                            style=select_style
                        ),
                        style=form_group_style
                    ),
                    Div(
                        Label("Отсрочка платежа (дней)", style=label_style),
                        Input(name="payment_terms", type="number", value=str(quote.get("payment_terms", 30)), min="0",
                              style=input_style),
                        style=form_group_style
                    ),
                    Div(
                        Label("Срок поставки (дней)", style=label_style),
                        Input(name="delivery_days", type="number", value=str(quote.get("delivery_days", 45)), min="0",
                              style=input_style),
                        style=form_group_style
                    ),
                    Div(
                        Label("Срок действия КП (дней)", style=label_style),
                        Input(name="validity_days", type="number", value=str(quote.get("validity_days", 30)), min="1",
                              style=input_style),
                        style=form_group_style
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 20px;"
                ),
                Div(
                    Label("Примечания", style=label_style),
                    Textarea(quote.get("notes", "") or "", name="notes", rows="3",
                             style=f"{input_style} resize: vertical; min-height: 80px;"),
                    style=form_group_style
                ),
                style=form_card_style
            ),

            # Action buttons
            Div(
                Button(icon("check", size=14), " Сохранить", type="submit",
                       style="padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/quotes/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                Button(icon("trash-2", size=14), " Удалить КП", type="button",
                       hx_delete=f"/quotes/{quote_id}",
                       hx_confirm="Вы уверены, что хотите удалить это КП?",
                       style="padding: 10px 20px; background: #fee2e2; color: #dc2626; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px; margin-left: auto;"),
                style="display: flex; gap: 12px; padding: 20px 0;"
            ),
            method="post",
            action=f"/quotes/{quote_id}/edit"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/edit")
def post(quote_id: str, customer_id: str, status: str, currency: str, delivery_terms: str,
         payment_terms: int, delivery_days: int, notes: str,
         delivery_city: str = None, delivery_country: str = None, delivery_method: str = None,
         delivery_priority: str = None, seller_company_id: str = None,
         contact_person_id: str = None, validity_days: int = 30, session=None):
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    try:
        update_data = {
            "customer_id": customer_id,
            "status": status,
            "currency": currency,
            "delivery_terms": delivery_terms,
            "payment_terms": payment_terms,
            "delivery_days": delivery_days,
            "validity_days": validity_days,
            "notes": notes or None,
            "updated_at": datetime.now().isoformat()
        }

        # Add delivery location if provided
        if delivery_city and delivery_city.strip():
            update_data["delivery_city"] = delivery_city.strip()
        else:
            update_data["delivery_city"] = None

        if delivery_country and delivery_country.strip():
            update_data["delivery_country"] = delivery_country.strip()
        else:
            update_data["delivery_country"] = None

        if delivery_method and delivery_method.strip():
            update_data["delivery_method"] = delivery_method.strip()
        else:
            update_data["delivery_method"] = None

        if delivery_priority and delivery_priority.strip():
            update_data["delivery_priority"] = delivery_priority.strip()
        else:
            update_data["delivery_priority"] = None

        # v3.0: seller_company_id at quote level
        # If provided and not empty, set it; otherwise keep existing or set to None
        if seller_company_id and seller_company_id.strip():
            update_data["seller_company_id"] = seller_company_id.strip()
        else:
            update_data["seller_company_id"] = None

        # Contact person (ЛПР)
        if contact_person_id and contact_person_id.strip():
            update_data["contact_person_id"] = contact_person_id.strip()
        else:
            update_data["contact_person_id"] = None

        supabase.table("quotes").update(update_data) \
            .eq("id", quote_id) \
            .eq("organization_id", user["org_id"]) \
            .execute()

        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    except Exception as e:
        return page_layout("Error",
            Div(f"Error: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}/edit"),
            session=session
        )


@rt("/quotes/{quote_id}")
def delete(quote_id: str, session):
    redirect = require_login(session)
    if redirect:
        return ""

    user = session["user"]
    supabase = get_supabase()

    try:
        # Delete quote items first
        supabase.table("quote_items").delete().eq("quote_id", quote_id).execute()
        # Delete quote
        supabase.table("quotes").delete().eq("id", quote_id).eq("organization_id", user["org_id"]).execute()
        # Redirect to quotes list
        return RedirectResponse("/quotes", status_code=303)
    except Exception as e:
        return Div(f"Error: {str(e)}", cls="alert alert-error")


# ============================================================================
# CUSTOMER DETAIL/EDIT
# ============================================================================

# REMOVED: Old customer detail route - replaced by enhanced version at line ~15609
# This old route was causing routing conflicts preventing /customers/{customer_id}/contacts/new from working


    # REMOVED: GET/POST /customers/{customer_id}/edit routes
    # Customer detail page (/customers/{customer_id}) has inline editing for all fields.


# ============================================================================
# QUOTE CALCULATION (calls existing backend API)
# ============================================================================

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ============================================================================
# CALCULATION HELPERS
# ============================================================================

# Mapping from various database values to SupplierCountry enum values
# DO NOT MODIFY the enum values (right side) - they must match calculation_models.py
SUPPLIER_COUNTRY_MAPPING = {
    # Direct enum values (already valid)
    "Турция": "Турция",
    "Турция (транзитная зона)": "Турция (транзитная зона)",
    "Россия": "Россия",
    "Китай": "Китай",
    "Литва": "Литва",
    "Латвия": "Латвия",
    "Болгария": "Болгария",
    "Польша": "Польша",
    "ЕС (между странами ЕС)": "ЕС (между странами ЕС)",
    "ОАЭ": "ОАЭ",
    "Прочие": "Прочие",
    # ISO codes
    "TR": "Турция",
    "RU": "Россия",
    "CN": "Китай",
    "LT": "Литва",
    "LV": "Латвия",
    "BG": "Болгария",
    "PL": "Польша",
    "AE": "ОАЭ",
    # Additional ISO codes for UI display
    "DE": "Германия",
    "IT": "Италия",
    "FR": "Франция",
    "JP": "Япония",
    "KR": "Корея",
    "IN": "Индия",
    "US": "США",
    "GB": "Великобритания",
    "ES": "Испания",
    "CZ": "Чехия",
    "NL": "Нидерланды",
    "BE": "Бельгия",
    "AT": "Австрия",
    "CH": "Швейцария",
    "SE": "Швеция",
    "FI": "Финляндия",
    "DK": "Дания",
    "TW": "Тайвань",
    "VN": "Вьетнам",
    "TH": "Таиланд",
    "MY": "Малайзия",
    "SG": "Сингапур",
    "SA": "Саудовская Аравия",
    "KZ": "Казахстан",
    "BY": "Беларусь",
    "UZ": "Узбекистан",
    # English names
    "Turkey": "Турция",
    "Russia": "Россия",
    "China": "Китай",
    "Lithuania": "Литва",
    "Latvia": "Латвия",
    "Bulgaria": "Болгария",
    "Poland": "Польша",
    "UAE": "ОАЭ",
    "Germany": "Германия",
    "Italy": "Италия",
    "France": "Франция",
    "Japan": "Япония",
    "South Korea": "Корея",
    "Korea": "Корея",
    "India": "Индия",
    # Special values
    "OTHER": "Прочие",
    "other": "Прочие",
    "Другое": "Прочие",
    "": "Прочие",  # Empty defaults to OTHER
}

# Shared mapping from ISO country codes to Russian names for UI display.
# Used by supplier list, customs workspace, logistics, and other pages.
COUNTRY_NAME_MAP = {
    "RU": "Россия",
    "CN": "Китай",
    "TR": "Турция",
    "DE": "Германия",
    "US": "США",
    "KR": "Корея",
    "JP": "Япония",
    "IT": "Италия",
    "FR": "Франция",
    "PL": "Польша",
    "LT": "Литва",
    "LV": "Латвия",
    "BG": "Болгария",
    "KZ": "Казахстан",
    "BY": "Беларусь",
    "UZ": "Узбекистан",
    "AE": "ОАЭ",
    "IN": "Индия",
    "GB": "Великобритания",
    "ES": "Испания",
    "CZ": "Чехия",
    "NL": "Нидерланды",
    "BE": "Бельгия",
    "AT": "Австрия",
    "CH": "Швейцария",
    "SE": "Швеция",
    "FI": "Финляндия",
    "DK": "Дания",
    "TW": "Тайвань",
    "VN": "Вьетнам",
    "TH": "Таиланд",
    "MY": "Малайзия",
    "SG": "Сингапур",
    "SA": "Саудовская Аравия",
}

# ============================================================================
# VAT ZONE MAPPING (Two-factor: country + price_includes_vat → SupplierCountry)
# ============================================================================

# EU countries: ISO code → {name_ru, vat_rate, zone (SupplierCountry enum value or None)}
# zone=None means the VAT rate has no matching SupplierCountry zone → error when price_includes_vat=True
EU_COUNTRY_VAT_RATES = {
    # 21% → maps to LITHUANIA zone
    "BE": {"name_ru": "Бельгия", "vat_rate": 21, "zone": "Литва"},
    "NL": {"name_ru": "Нидерланды", "vat_rate": 21, "zone": "Литва"},
    "CZ": {"name_ru": "Чехия", "vat_rate": 21, "zone": "Литва"},
    "ES": {"name_ru": "Испания", "vat_rate": 21, "zone": "Литва"},
    "LT": {"name_ru": "Литва", "vat_rate": 21, "zone": "Литва"},
    "LV": {"name_ru": "Латвия", "vat_rate": 21, "zone": "Латвия"},
    # 20% → maps to BULGARIA zone
    "BG": {"name_ru": "Болгария", "vat_rate": 20, "zone": "Болгария"},
    "FR": {"name_ru": "Франция", "vat_rate": 20, "zone": "Болгария"},
    "AT": {"name_ru": "Австрия", "vat_rate": 20, "zone": "Болгария"},
    "SK": {"name_ru": "Словакия", "vat_rate": 20, "zone": "Болгария"},
    # 23% → maps to POLAND zone
    "PL": {"name_ru": "Польша", "vat_rate": 23, "zone": "Польша"},
    "PT": {"name_ru": "Португалия", "vat_rate": 23, "zone": "Польша"},
    "IE": {"name_ru": "Ирландия", "vat_rate": 23, "zone": "Польша"},
    # Unsupported rates → zone=None → ERROR when price_includes_vat=True
    "DE": {"name_ru": "Германия", "vat_rate": 19, "zone": None},
    "IT": {"name_ru": "Италия", "vat_rate": 22, "zone": None},
    "SE": {"name_ru": "Швеция", "vat_rate": 25, "zone": None},
    "DK": {"name_ru": "Дания", "vat_rate": 25, "zone": None},
    "FI": {"name_ru": "Финляндия", "vat_rate": 25.5, "zone": None},
    "HU": {"name_ru": "Венгрия", "vat_rate": 27, "zone": None},
    "RO": {"name_ru": "Румыния", "vat_rate": 19, "zone": None},
    "HR": {"name_ru": "Хорватия", "vat_rate": 25, "zone": None},
    "SI": {"name_ru": "Словения", "vat_rate": 22, "zone": None},
    "EE": {"name_ru": "Эстония", "vat_rate": 22, "zone": None},
    "GR": {"name_ru": "Греция", "vat_rate": 24, "zone": None},
}

EU_ISO_CODES = set(EU_COUNTRY_VAT_RATES.keys())

# Direct country matches: ISO code → SupplierCountry enum value
# These countries have dedicated zones in the calculation engine
DIRECT_COUNTRY_ZONES = {
    "TR": "Турция",
    "RU": "Россия",
    "CN": "Китай",
    "AE": "ОАЭ",
}

# Reverse lookup: Russian name → ISO code
_RUSSIAN_TO_ISO = {}
for _iso, _name_ru in COUNTRY_NAME_MAP.items():
    _RUSSIAN_TO_ISO[_name_ru] = _iso
# Add EU countries not in COUNTRY_NAME_MAP
for _iso, _info in EU_COUNTRY_VAT_RATES.items():
    _RUSSIAN_TO_ISO[_info["name_ru"]] = _iso

# English name → ISO code (for common names)
_ENGLISH_TO_ISO = {
    "Turkey": "TR", "Russia": "RU", "China": "CN", "Lithuania": "LT",
    "Latvia": "LV", "Bulgaria": "BG", "Poland": "PL", "UAE": "AE",
    "Germany": "DE", "Italy": "IT", "France": "FR", "Japan": "JP",
    "South Korea": "KR", "Korea": "KR", "India": "IN", "Belgium": "BE",
    "Netherlands": "NL", "Spain": "ES", "Czech Republic": "CZ",
    "Austria": "AT", "Switzerland": "CH", "Sweden": "SE", "Finland": "FI",
    "Denmark": "DK", "Portugal": "PT", "Ireland": "IE", "Greece": "GR",
    "Hungary": "HU", "Romania": "RO", "Croatia": "HR", "Slovenia": "SI",
    "Estonia": "EE", "Slovakia": "SK",
}

# SupplierCountry enum value → ISO code (for values already mapped to zones)
_ENUM_TO_ISO = {
    "Турция": "TR", "Россия": "RU", "Китай": "CN", "Литва": "LT",
    "Латвия": "LV", "Болгария": "BG", "Польша": "PL", "ОАЭ": "AE",
}


def normalize_country_to_iso(value: str) -> str:
    """Normalize any country representation to ISO 2-letter code.

    Handles: ISO codes ("BE"), Russian names ("Бельгия"), English names ("Belgium"),
    SupplierCountry enum values ("Литва").

    Returns empty string if not recognized.
    """
    if not value:
        return ""
    v = value.strip()
    upper = v.upper()

    # Already an ISO code?
    if len(v) == 2 and upper.isalpha():
        return upper

    # Russian name?
    if v in _RUSSIAN_TO_ISO:
        return _RUSSIAN_TO_ISO[v]

    # English name?
    if v in _ENGLISH_TO_ISO:
        return _ENGLISH_TO_ISO[v]

    # SupplierCountry enum value?
    if v in _ENUM_TO_ISO:
        return _ENUM_TO_ISO[v]

    # Case-insensitive fallbacks
    v_lower = v.lower()
    for eng, iso in _ENGLISH_TO_ISO.items():
        if eng.lower() == v_lower:
            return iso

    return ""


def resolve_vat_zone(country_raw: str, price_includes_vat: bool) -> dict:
    """Map (country, price_includes_vat) → SupplierCountry enum value with reason.

    Returns dict:
        zone: str or None — SupplierCountry enum value for calculation engine
        reason: str — human-readable explanation for quote control page
        warning: str or None — warning message (needs manual check)
        error: str or None — error message (cannot calculate)
    """
    iso = normalize_country_to_iso(country_raw)
    name_ru = COUNTRY_NAME_MAP.get(iso, "") or EU_COUNTRY_VAT_RATES.get(iso, {}).get("name_ru", country_raw or "неизвестная")

    # 1. Empty/unknown country → Прочие with warning
    if not iso:
        return {
            "zone": "Прочие",
            "reason": f"Страна не определена ({country_raw or '—'}) → Прочие",
            "warning": "Страна поставщика не указана — проверьте",
            "error": None,
        }

    # 2. China — always "Китай" regardless of VAT flag
    # Engine already handles China as VAT-free (line 200: if supplier_country == CHINA: N16 = base_price_VAT)
    if iso == "CN":
        return {
            "zone": "Китай",
            "reason": f"{name_ru} → Китай (НДС не применяется)",
            "warning": None,
            "error": None,
        }

    # 3. Direct match countries (TR, RU, AE) — have their own zones
    if iso in DIRECT_COUNTRY_ZONES:
        zone = DIRECT_COUNTRY_ZONES[iso]
        if price_includes_vat:
            return {
                "zone": zone,
                "reason": f"{name_ru} с НДС → {zone}",
                "warning": None,
                "error": None,
            }
        else:
            # Price without VAT → engine shouldn't strip VAT → use Прочие (0%)
            return {
                "zone": "Прочие",
                "reason": f"{name_ru}, цена без НДС → Прочие (0%)",
                "warning": f"Цена без НДС для {name_ru} — проверьте корректность",
                "error": None,
            }

    # 4. EU countries
    if iso in EU_ISO_CODES:
        eu_info = EU_COUNTRY_VAT_RATES[iso]
        vat_rate = eu_info["vat_rate"]

        if not price_includes_vat:
            # EU without VAT → cross-border (0% VAT, 4% EU route markup)
            return {
                "zone": "ЕС (между странами ЕС)",
                "reason": f"{name_ru}, цена без НДС → ЕС cross-border (0% НДС, 4% наценка)",
                "warning": f"Цена без НДС для ЕС ({name_ru}) — проверьте",
                "error": None,
            }
        else:
            # EU with VAT — need matching zone
            zone = eu_info["zone"]
            if zone:
                return {
                    "zone": zone,
                    "reason": f"{name_ru} с НДС {vat_rate}% → зона {zone} (очистка {vat_rate}%)",
                    "warning": None,
                    "error": None,
                }
            else:
                return {
                    "zone": None,
                    "reason": f"НДС {name_ru} ({vat_rate}%) не поддерживается расчётной моделью",
                    "warning": None,
                    "error": f"НДС {name_ru} ({vat_rate}%) не поддерживается. Поддерживаемые ставки: 20% (Болгария), 21% (Литва), 23% (Польша)",
                }

    # 5. Non-EU, non-direct country → Прочие
    if price_includes_vat:
        return {
            "zone": "Прочие",
            "reason": f"{name_ru} → Прочие",
            "warning": f"Цена с НДС для {name_ru} — НДС не будет очищен",
            "error": None,
        }
    return {
        "zone": "Прочие",
        "reason": f"{name_ru} → Прочие",
        "warning": None,
        "error": None,
    }


def _calc_combined_duty(item: Dict) -> float:
    """REQ-004: Compute combined import tariff from percent + per-kg duty.

    Formula: customs_duty + (customs_duty_per_kg * weight_in_kg / base_price * 100)
    Falls back to customs_duty only when weight or price is missing/zero.
    Falls back to legacy import_tariff field when customs_duty is absent.
    """
    import logging

    duty_pct = float(safe_decimal(item.get('customs_duty')))
    duty_per_kg = float(safe_decimal(item.get('customs_duty_per_kg')))

    # If neither column is populated, fall back to legacy field
    if duty_pct == 0 and duty_per_kg == 0:
        legacy = item.get('import_tariff')
        return float(safe_decimal(legacy))

    if duty_per_kg > 0:
        weight = float(safe_decimal(item.get('weight_in_kg')))
        price = float(safe_decimal(item.get('purchase_price_original') or item.get('base_price_vat')))
        if weight > 0 and price > 0:
            kg_as_pct = (duty_per_kg * weight) / price * 100
            return duty_pct + kg_as_pct
        else:
            logging.getLogger(__name__).warning(
                "Item %s: customs_duty_per_kg=%.4f but weight=%.2f, price=%.2f — using duty_pct only",
                item.get('id'), duty_per_kg, weight, price,
            )
            return duty_pct

    return duty_pct


def build_calculation_inputs(items: List[Dict], variables: Dict[str, Any]) -> List[QuoteCalculationInput]:
    """Build calculation inputs for all quote items.

    Note: Uses purchase_price_original as base_price_vat for calculation engine.
    Calculation engine is NOT modified - we adapt data to match its expectations.

    2026-01-26: Added per-item exchange rate calculation. Each item may have a different
    purchase_currency, so we calculate individual exchange rates to quote_currency.

    2026-01-28: Monetary values (brokerage, DM fee) are now stored in ORIGINAL currency.
    Conversion to USD happens here, just before passing to calculation engine.
    """
    from services.currency_service import convert_amount

    # Get quote currency (target currency for all conversions)
    quote_currency = variables.get('currency_of_quote') or variables.get('currency', 'USD')

    # ==========================================================================
    # CONVERT MONETARY VALUES TO QUOTE CURRENCY FOR CALCULATION ENGINE
    #
    # IMPORTANT: The calculation engine uses exchange_rate to convert purchase
    # prices to quote currency (R16 = P16 / exchange_rate). This means S16, AY16
    # are in quote currency. For Y16 = tariff * (AY16 + T16) to be correct,
    # T16 (logistics) must also be in quote currency.
    #
    # Values are stored in various currencies (logistics in USD, brokerage in
    # original currency). We convert ALL to quote currency here.
    #
    # 2026-01-28: Fixed currency mixing bug - was converting to USD but engine
    # outputs S16/AY16 in quote currency, causing Y16 calculation error.
    # ==========================================================================

    # Helper to convert value from source_currency to quote_currency
    def to_quote(value, from_currency):
        if not value:
            return safe_decimal(value)
        if from_currency == quote_currency:
            return safe_decimal(value)
        val = safe_decimal(value)
        if val > 0:
            return safe_decimal(convert_amount(val, from_currency, quote_currency))
        return val

    # Convert brokerage fields from their currencies to quote currency
    brokerage_hub_qc = to_quote(
        variables.get('brokerage_hub'),
        variables.get('brokerage_hub_currency', 'USD')
    )
    brokerage_customs_qc = to_quote(
        variables.get('brokerage_customs'),
        variables.get('brokerage_customs_currency', 'USD')
    )
    warehousing_at_customs_qc = to_quote(
        variables.get('warehousing_at_customs'),
        variables.get('warehousing_at_customs_currency', 'USD')
    )
    customs_documentation_qc = to_quote(
        variables.get('customs_documentation'),
        variables.get('customs_documentation_currency', 'USD')
    )
    brokerage_extra_qc = to_quote(
        variables.get('brokerage_extra'),
        variables.get('brokerage_extra_currency', 'USD')
    )

    # Convert logistics fields from USD to quote currency
    # Logistics costs are aggregated and stored in USD
    logistics_supplier_hub_qc = to_quote(
        variables.get('logistics_supplier_hub'), 'USD'
    )
    logistics_hub_customs_qc = to_quote(
        variables.get('logistics_hub_customs'), 'USD'
    )
    logistics_customs_client_qc = to_quote(
        variables.get('logistics_customs_client'), 'USD'
    )

    # Convert DM Fee from its currency to quote currency (only for fixed type)
    dm_fee_type = variables.get('dm_fee_type', 'fixed')
    dm_fee_currency = variables.get('dm_fee_currency', 'USD')
    if dm_fee_type == 'fixed':
        dm_fee_value_qc = to_quote(variables.get('dm_fee_value'), dm_fee_currency)
    else:
        # Percentage - no conversion needed
        dm_fee_value_qc = safe_decimal(variables.get('dm_fee_value'))

    # Create a copy of variables with quote-currency-converted values
    calc_variables = dict(variables)
    calc_variables['brokerage_hub'] = brokerage_hub_qc
    calc_variables['brokerage_customs'] = brokerage_customs_qc
    calc_variables['warehousing_at_customs'] = warehousing_at_customs_qc
    calc_variables['customs_documentation'] = customs_documentation_qc
    calc_variables['brokerage_extra'] = brokerage_extra_qc
    calc_variables['logistics_supplier_hub'] = logistics_supplier_hub_qc
    calc_variables['logistics_hub_customs'] = logistics_hub_customs_qc
    calc_variables['logistics_customs_client'] = logistics_customs_client_qc
    calc_variables['dm_fee_value'] = dm_fee_value_qc

    # seller_company name comes directly from DB (already matches SellerCompany enum)
    # No normalization needed -- DB names were updated to match enum values exactly

    calc_inputs = []
    for item in items:
        # Skip unavailable items - they shouldn't be included in calculation
        if item.get('is_unavailable'):
            continue

        # REQ-009: Skip import-banned items from calculation entirely
        if item.get('import_banned'):
            continue

        # Get item's purchase currency
        item_currency = item.get('purchase_currency') or item.get('currency_of_base_price', 'USD')

        # Product fields (adapt new schema to calculation engine expectations)
        product = {
            'base_price_vat': safe_decimal(item.get('purchase_price_original') or item.get('base_price_vat')),
            'quantity': item.get('quantity', 1),
            'weight_in_kg': safe_decimal(item.get('weight_in_kg')),
            'customs_code': item.get('customs_code', '0000000000'),
            'supplier_country': resolve_vat_zone(
                item.get('supplier_country') or variables.get('supplier_country', ''),
                bool(item.get('price_includes_vat', False))
            )["zone"] or "Прочие",
            'currency_of_base_price': item_currency,
            'import_tariff': _calc_combined_duty(item),
            'markup': item.get('markup'),
            'supplier_discount': item.get('supplier_discount'),
        }

        # Sum per-item license costs (ДС, СС, СГР) stored in RUB
        # license_ds_cost (numeric), license_ss_cost (numeric), license_sgr_cost (numeric)
        total_license_cost = (
            float(item.get('license_ds_cost') or 0)
            + float(item.get('license_ss_cost') or 0)
            + float(item.get('license_sgr_cost') or 0)
        )

        # Create per-item calc_variables copy and add license cost to brokerage_extra
        # License costs are in RUB, convert to quote currency and add to brokerage_extra
        item_calc_variables = dict(calc_variables)
        if total_license_cost > 0:
            license_cost_qc = to_quote(total_license_cost, 'RUB')
            item_calc_variables['brokerage_extra'] = safe_decimal(calc_variables.get('brokerage_extra', 0)) + safe_decimal(license_cost_qc)

        # Calculate per-item exchange rate (2026-01-26)
        # Formula: exchange_rate = "how many units of source currency per 1 unit of quote currency"
        # Example: if quote is EUR and item is USD, and 1 EUR = 1.08 USD, then exchange_rate = 1.08
        # Calculation: P16 (in USD) / 1.08 = R16 (in EUR)
        if item_currency == quote_currency:
            exchange_rate = Decimal("1.0")
        else:
            # convert_amount(1, quote_currency, item_currency) gives how many item_currency = 1 quote_currency
            exchange_rate = safe_decimal(convert_amount(Decimal("1"), quote_currency, item_currency))
            if exchange_rate == 0:
                exchange_rate = Decimal("1.0")  # Fallback if rate not found

        calc_input = map_variables_to_calculation_input(
            product=product,
            variables=item_calc_variables,  # Per-item variables with license costs in brokerage_extra
            exchange_rate=exchange_rate
        )
        calc_inputs.append(calc_input)

    return calc_inputs


def render_preview_panel(results: List, items: List[Dict], currency: str) -> str:
    """Render the preview panel HTML for HTMX."""
    if not results:
        return Div(P("Add products to preview calculation."), cls="alert alert-info", id="preview-panel")

    # Calculate totals
    total_purchase = sum(safe_decimal(r.purchase_price_total_quote_currency) for r in results)
    total_logistics = sum(safe_decimal(r.logistics_total) for r in results)
    total_cogs = sum(safe_decimal(r.cogs_per_product) for r in results)
    total_profit = sum(safe_decimal(r.profit) for r in results)
    total_no_vat = sum(safe_decimal(r.sales_price_total_no_vat) for r in results)
    total_with_vat = sum(safe_decimal(r.sales_price_total_with_vat) for r in results)

    avg_margin = (total_profit / total_cogs * 100) if total_cogs else Decimal("0")

    # Build product rows for preview
    product_rows = []
    for item, result in zip(items, results):
        product_rows.append(
            Tr(
                Td(item.get('product_name', 'Product')[:30]),
                Td(str(item.get('quantity', 1))),
                Td(format_money(result.sales_price_per_unit_no_vat, currency)),
                Td(format_money(result.sales_price_total_with_vat, currency)),
                Td(format_money(result.profit, currency)),
            )
        )

    return Div(
        H3("Preview (not saved)"),

        # Summary stats
        Div(
            Div(
                Div("Total (excl VAT)", style="font-size: 0.875rem; color: #666;"),
                Div(format_money(total_no_vat, currency), cls="stat-value", style="font-size: 1.5rem;"),
                cls="stat-card"
            ),
            Div(
                Div("Total (incl VAT)", style="font-size: 0.875rem; color: #666;"),
                Div(format_money(total_with_vat, currency), cls="stat-value", style="font-size: 1.5rem; color: #28a745;"),
                cls="stat-card"
            ),
            Div(
                Div("Profit", style="font-size: 0.875rem; color: #666;"),
                Div(format_money(total_profit, currency), cls="stat-value", style="font-size: 1.5rem;"),
                cls="stat-card"
            ),
            Div(
                Div("Avg Margin", style="font-size: 0.875rem; color: #666;"),
                Div(f"{avg_margin:.1f}%", cls="stat-value", style="font-size: 1.5rem;"),
                cls="stat-card"
            ),
            cls="stats-grid", style="margin-bottom: 1rem;"
        ),

        # Cost breakdown
        Table(
            Thead(Tr(Th("Product"), Th("Qty"), Th("Unit Price"), Th("Total"), Th("Profit"))),
            Tbody(*product_rows),
            Tfoot(
                Tr(
                    Td(Strong("TOTAL"), colspan="3"),
                    Td(Strong(format_money(total_with_vat, currency))),
                    Td(Strong(format_money(total_profit, currency))),
                )
            ),
            style="font-size: 0.875rem;"
        ),

        id="preview-panel",
        style="background: #f0fff0; border: 2px solid #28a745; padding: 1rem; border-radius: 8px;"
    )


# ============================================================================
# HTMX LIVE PREVIEW ROUTE
# ============================================================================

@rt("/quotes/{quote_id}/preview")
def post(
    quote_id: str,
    session,
    # Company settings
    seller_company: str = "МАСТЕР БЭРИНГ ООО",
    offer_sale_type: str = "поставка",
    offer_incoterms: str = "DDP",
    # Pricing (note: 'currency' matches form field name)
    currency: str = "RUB",
    markup: str = "15",
    supplier_discount: str = "0",
    exchange_rate: str = "1.0",
    delivery_time: str = "30",
    # Logistics
    logistics_supplier_hub: str = "0",
    logistics_hub_customs: str = "0",
    logistics_customs_client: str = "0",
    # Brokerage (values and currencies)
    brokerage_hub: str = "0",
    brokerage_hub_currency: str = "RUB",
    brokerage_customs: str = "0",
    brokerage_customs_currency: str = "RUB",
    warehousing_at_customs: str = "0",
    warehousing_at_customs_currency: str = "RUB",
    customs_documentation: str = "0",
    customs_documentation_currency: str = "RUB",
    brokerage_extra: str = "0",
    brokerage_extra_currency: str = "RUB",
    # Payment terms
    advance_from_client: str = "100",
    advance_to_supplier: str = "100",
    time_to_advance: str = "0",
    time_to_advance_on_receiving: str = "0",
    # DM Fee
    dm_fee_type: str = "fixed",
    dm_fee_value: str = "0",
    dm_fee_currency: str = "USD",
):
    """HTMX endpoint - returns preview panel only (no DB save)."""
    redirect = require_login(session)
    if redirect:
        return HTMLResponse("Unauthorized", status_code=401)

    user = session["user"]
    supabase = get_supabase()

    # Get quote
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return Div("Quote not found", cls="alert alert-error", id="preview-panel")

    quote = quote_result.data[0]
    # Note: 'currency' comes from form parameter (user's selection)
    # Don't override with quote.get("currency")

    # Get items via composition_service (Phase 5b): overlays purchase price
    # fields from invoice_item_prices when the item has an active composition
    # pointer, otherwise returns the quote_items row unchanged. The dict shape
    # is identical to a plain quote_items SELECT, so build_calculation_inputs()
    # sees no difference.
    items = get_composed_items(quote_id, supabase)

    if not items:
        return Div("Add products to preview.", cls="alert alert-info", id="preview-panel")

    # Validate that all available items have prices before calculation
    items_without_price = []
    for item in items:
        if item.get("is_unavailable"):
            continue
        price = safe_decimal(item.get("purchase_price_original") or item.get("base_price_vat"))
        if price <= 0:
            item_name = item.get("product_name", "—")
            item_brand = item.get("brand", "")
            item_label = f"{item_brand} — {item_name}" if item_brand else item_name
            items_without_price.append(item_label)

    if items_without_price:
        missing_list = Ul(
            *[Li(name, style="margin-bottom: 4px;") for name in items_without_price],
            style="margin: 12px 0; padding-left: 20px;"
        )
        return Div(
            P(Strong("Не все позиции имеют цену."), style="margin-bottom: 8px;"),
            P("Заполните цены в разделе закупок перед расчётом."),
            P(f"Позиции без цены ({len(items_without_price)}):", style="margin-bottom: 4px; color: #64748b;"),
            missing_list,
            cls="alert alert-error", id="preview-panel"
        )

    try:
        # Aggregate delivery time from items (production_time_days) and invoices (logistics_total_days)
        max_production_days = max((item.get("production_time_days") or 0) for item in items) if items else 0

        invoices_days_result = supabase.table("invoices") \
            .select("logistics_total_days") \
            .eq("quote_id", quote_id) \
            .execute()
        max_logistics_days = max((inv.get("logistics_total_days") or 0) for inv in (invoices_days_result.data or [])) if invoices_days_result.data else 0

        aggregated_delivery_time = max_logistics_days + max_production_days
        form_delivery_time = safe_int(delivery_time)
        effective_delivery_time = max(aggregated_delivery_time, form_delivery_time)

        # ==========================================================================
        # STORE VALUES IN ORIGINAL CURRENCY (no conversion on save)
        # Conversion to USD happens only in build_calculation_inputs() before calculation
        # ==========================================================================

        # Build variables from form parameters
        variables = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': effective_delivery_time,  # Uses MAX(logistics_days + production_days) if greater
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,

            # Logistics (stored in USD - aggregated from invoices which are already converted)
            'logistics_supplier_hub': safe_decimal(logistics_supplier_hub),
            'logistics_hub_customs': safe_decimal(logistics_hub_customs),
            'logistics_customs_client': safe_decimal(logistics_customs_client),

            # Brokerage (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
            'brokerage_hub': safe_decimal(brokerage_hub),
            'brokerage_hub_currency': brokerage_hub_currency,
            'brokerage_customs': safe_decimal(brokerage_customs),
            'brokerage_customs_currency': brokerage_customs_currency,
            'warehousing_at_customs': safe_decimal(warehousing_at_customs),
            'warehousing_at_customs_currency': warehousing_at_customs_currency,
            'customs_documentation': safe_decimal(customs_documentation),
            'customs_documentation_currency': customs_documentation_currency,
            'brokerage_extra': safe_decimal(brokerage_extra),
            'brokerage_extra_currency': brokerage_extra_currency,

            # Payment terms
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),

            # DM Fee (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),
            'dm_fee_currency': dm_fee_currency,

            # Exchange rate
            'exchange_rate': safe_decimal(exchange_rate),
        }

        # Build calculation inputs
        calc_inputs = build_calculation_inputs(items, variables)

        # Run calculation (in memory, no save)
        results = calculate_multiproduct_quote(calc_inputs)

        # Return preview panel
        return render_preview_panel(results, items, currency)

    except Exception as e:
        return Div(f"Preview error: {str(e)}", cls="alert alert-error", id="preview-panel")


# ============================================================================
# CALCULATION PAGE (GET) - Enhanced with all variables
# ============================================================================

@rt("/quotes/{quote_id}/calculate")
def get(quote_id: str, session):
    """Calculate quote using the 13-phase calculation engine with HTMX live preview."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote with customer (v3.0 - fetch seller company separately to avoid FK issues)
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get seller company info separately using service function
    from services.seller_company_service import get_seller_company
    seller_company_info = None
    seller_company_display = "Не выбрана"
    seller_company_name = ""
    if quote.get("seller_company_id"):
        seller_company = get_seller_company(quote["seller_company_id"])
        if seller_company:
            seller_company_info = {"id": seller_company.id, "supplier_code": seller_company.supplier_code, "name": seller_company.name}
            seller_company_display = f"{seller_company.supplier_code} - {seller_company.name}"
            seller_company_name = seller_company.name

    # Get quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    items = items_result.data or []

    if not items:
        return page_layout("Невозможно рассчитать",
            H1("Нет позиций"),
            P("Добавьте товары в КП перед расчётом."),
            A("Назад к КП", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Try to load existing calculation variables
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    saved_vars = vars_result.data[0]["variables"] if vars_result.data else {}

    # NOTE: Monetary values (brokerage, DM fee) are now stored in ORIGINAL currency
    # No back-conversion needed for display - values are shown as entered

    # ==========================================================================
    # AGGREGATE LOGISTICS FROM INVOICES (with multi-currency support)
    # Logistics costs are entered per-invoice by logistics department
    # Each segment may have different currency - convert all to QUOTE CURRENCY before summing
    # The calculation engine expects logistics values in quote currency, not USD
    # ==========================================================================
    invoices_result = supabase.table("invoices") \
        .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, "
                "logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
        .eq("quote_id", quote_id) \
        .execute()

    invoices_logistics = invoices_result.data or []

    # Sum logistics costs from all invoices, converting each to USD (standard storage currency)
    # Conversion to quote currency happens only at export time (single point of conversion)
    from services.currency_service import convert_amount
    total_logistics_supplier_hub = Decimal(0)
    total_logistics_hub_customs = Decimal(0)
    total_logistics_customs_client = Decimal(0)

    for inv in invoices_logistics:
        # Supplier → Hub - convert to USD
        s2h_amount = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
        s2h_currency = inv.get("logistics_supplier_to_hub_currency") or "USD"
        if s2h_amount > 0:
            total_logistics_supplier_hub += convert_amount(s2h_amount, s2h_currency, "USD")

        # Hub → Customs - convert to USD
        h2c_amount = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
        h2c_currency = inv.get("logistics_hub_to_customs_currency") or "USD"
        if h2c_amount > 0:
            total_logistics_hub_customs += convert_amount(h2c_amount, h2c_currency, "USD")

        # Customs → Customer - convert to USD
        c2c_amount = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
        c2c_currency = inv.get("logistics_customs_to_customer_currency") or "USD"
        if c2c_amount > 0:
            total_logistics_customs_client += convert_amount(c2c_amount, c2c_currency, "USD")

    # Convert to float for downstream compatibility
    total_logistics_supplier_hub = float(total_logistics_supplier_hub)
    total_logistics_hub_customs = float(total_logistics_hub_customs)
    total_logistics_customs_client = float(total_logistics_customs_client)

    # Use aggregated values from invoices as defaults
    # Override saved_vars if: aggregated > 0 AND (saved is missing or saved is 0)
    # This ensures invoice-level logistics data flows to calculation
    saved_supplier_hub = float(saved_vars.get("logistics_supplier_hub", 0) or 0)
    saved_hub_customs = float(saved_vars.get("logistics_hub_customs", 0) or 0)
    saved_customs_client = float(saved_vars.get("logistics_customs_client", 0) or 0)

    if total_logistics_supplier_hub > 0 and saved_supplier_hub == 0:
        saved_vars["logistics_supplier_hub"] = total_logistics_supplier_hub
    if total_logistics_hub_customs > 0 and saved_hub_customs == 0:
        saved_vars["logistics_hub_customs"] = total_logistics_hub_customs
    if total_logistics_customs_client > 0 and saved_customs_client == 0:
        saved_vars["logistics_customs_client"] = total_logistics_customs_client

    # Default values (with saved values taking precedence)
    def get_var(key, default):
        return saved_vars.get(key, default)

    # Check for partial recalculation
    partial_recalc = quote.get("partial_recalc")

    # Check existing versions and workflow status for version dialog
    existing_versions = list_quote_versions(quote_id, user["org_id"])
    workflow_status = quote.get("workflow_status", "draft")
    can_update, update_reason = can_update_version(quote_id, user["org_id"])
    current_version = get_current_quote_version(quote_id, user["org_id"]) if existing_versions else None
    current_version_num = current_version.get("version_number", 1) if current_version else 0

    # ==========================================================================
    # COMPACT CALCULATE PAGE STYLING (Logistics-inspired design)
    # ==========================================================================
    # Inline styles for compact logistics-style layout
    card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 16px;
        margin-bottom: 12px;
    """
    label_style = "font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;"
    input_row_style = "display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9;"
    input_row_last_style = "display: flex; align-items: center; padding: 8px 0;"
    input_style = "width: 100px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    input_wide_style = "width: 140px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    select_style = "width: 120px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    select_currency_style = "width: 70px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
    section_title_style = "font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; display: flex; align-items: center; gap: 6px;"
    field_label_style = "font-size: 13px; color: #64748b; width: 140px; font-weight: 500;"
    value_style = "font-size: 14px; font-weight: 600; color: #1e40af;"

    # Build seller company display
    seller_company_hidden = Input(type="hidden", name="seller_company", value=seller_company_name if seller_company_info else "")
    if seller_company_info:
        seller_display = Span(seller_company_display, style="font-weight: 600; color: #1e40af;")
    else:
        seller_display = Span("Не выбрана", style="color: #d97706; font-weight: 500;")

    return page_layout(f"Calculate - {quote.get('idn_quote', '')}",
        # Compact header
        Div(
            Div(
                icon("calculator", size=20),
                Span(f"Расчёт {quote.get('idn_quote', '')}", style="font-size: 1.25rem; font-weight: 600; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            Div(
                Span(quote.get('customers', {}).get('name', '—') if quote.get('customers') else '—', style="font-weight: 500;"),
                Span(" • ", style="color: #94a3b8;"),
                Span(f"{currency}", style="color: #3b82f6; font-weight: 600;"),
                Span(" • ", style="color: #94a3b8;"),
                Span(f"{len(items)} поз.", style="color: #64748b;"),
                style="font-size: 13px; margin-top: 4px;"
            ),
            style="margin-bottom: 16px;"
        ),

        # Partial recalculation banner
        Div(
            icon("refresh-cw", size=16),
            Span(" Частичный пересчёт: только наценка", style="font-weight: 600; margin-left: 6px;"),
            Span(" — данные закупки, логистики и таможни сохранены", style="font-size: 12px; color: #065f46; margin-left: 8px;"),
            style="background: linear-gradient(90deg, #dcfce7 0%, #f0fdf4 100%); border: 1px solid #86efac; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; display: flex; align-items: center; color: #166534;"
        ) if partial_recalc == "price" else None,

        # Main form with HTMX live preview
        Form(
            Div(
                # Left column: Compact form cards
                Div(
                    # === COMPANY & PRICING CARD (Combined) ===
                    Div(
                        # Section: Company
                        Div(
                            Span(icon("building-2", size=14), style="color: #64748b;"),
                            Span("Компания и условия", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        # Row: Seller Company
                        Div(
                            Span("Продавец", style=field_label_style),
                            seller_display,
                            A("изменить", href=f"/quotes/{quote_id}/edit", style="font-size: 11px; margin-left: 8px; color: #94a3b8;"),
                            seller_company_hidden,
                            style=input_row_style
                        ),
                        # Row: Sale Type + Incoterms
                        Div(
                            Span("Тип сделки", style=field_label_style),
                            Select(
                                Option("Поставка", value="поставка", selected=True),
                                Option("Транзит", value="транзит"),
                                name="offer_sale_type",
                                style=select_style
                            ),
                            Span("Incoterms", style=f"{field_label_style} margin-left: 20px; width: 80px;"),
                            Select(
                                Option("DDP", value="DDP", selected=get_var('offer_incoterms', 'DDP') == "DDP"),
                                Option("DAP", value="DAP", selected=get_var('offer_incoterms', '') == "DAP"),
                                Option("CIF", value="CIF", selected=get_var('offer_incoterms', '') == "CIF"),
                                Option("FOB", value="FOB", selected=get_var('offer_incoterms', '') == "FOB"),
                                Option("EXW", value="EXW", selected=get_var('offer_incoterms', '') == "EXW"),
                                name="offer_incoterms",
                                style="width: 80px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
                            ),
                            style=input_row_style
                        ),

                        # Divider
                        Div(style="height: 1px; background: #e2e8f0; margin: 12px 0;"),

                        # Section: Pricing
                        Div(
                            Span(icon("percent", size=14), style="color: #64748b;"),
                            Span("Цена и наценка", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        # Row: Currency + Markup
                        Div(
                            Span("Валюта КП", style=field_label_style),
                            Select(
                                Option("RUB", value="RUB", selected=currency == "RUB"),
                                Option("USD", value="USD", selected=currency == "USD"),
                                Option("EUR", value="EUR", selected=currency == "EUR"),
                                Option("CNY", value="CNY", selected=currency == "CNY"),
                                name="currency",
                                style=select_currency_style
                            ),
                            Span("Наценка", style=f"{field_label_style} margin-left: 20px; width: 80px;"),
                            Input(name="markup", type="number", value=str(get_var('markup', 15)), min="0", max="100", step="0.1",
                                  style="width: 70px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("%", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            style=input_row_last_style
                        ),

                        # Hidden fields
                        Input(type="hidden", name="supplier_discount", value=str(get_var('supplier_discount', 0))),
                        Input(type="hidden", name="exchange_rate", value=str(get_var('exchange_rate', 1.0))),
                        Input(type="hidden", name="delivery_time", value=str(get_var('delivery_time', 30))),
                        Input(type="hidden", name="logistics_supplier_hub", value=str(get_var('logistics_supplier_hub', 0))),
                        Input(type="hidden", name="logistics_hub_customs", value=str(get_var('logistics_hub_customs', 0))),
                        Input(type="hidden", name="logistics_customs_client", value=str(get_var('logistics_customs_client', 0))),
                        Input(type="hidden", name="brokerage_hub", value=str(get_var('brokerage_hub', 0))),
                        Input(type="hidden", name="brokerage_hub_currency", value=str(get_var('brokerage_hub_currency', 'RUB'))),
                        Input(type="hidden", name="brokerage_customs", value=str(get_var('brokerage_customs', 0))),
                        Input(type="hidden", name="brokerage_customs_currency", value=str(get_var('brokerage_customs_currency', 'RUB'))),
                        Input(type="hidden", name="warehousing_at_customs", value=str(get_var('warehousing_at_customs', 0))),
                        Input(type="hidden", name="warehousing_at_customs_currency", value=str(get_var('warehousing_at_customs_currency', 'RUB'))),
                        Input(type="hidden", name="customs_documentation", value=str(get_var('customs_documentation', 0))),
                        Input(type="hidden", name="customs_documentation_currency", value=str(get_var('customs_documentation_currency', 'RUB'))),
                        Input(type="hidden", name="brokerage_extra", value=str(get_var('brokerage_extra', 0))),
                        Input(type="hidden", name="brokerage_extra_currency", value=str(get_var('brokerage_extra_currency', 'RUB'))),
                        Input(type="hidden", name="advance_to_supplier", value=str(get_var('advance_to_supplier', 100))),

                        style=card_style
                    ),

                    # === PAYMENT TERMS CARD ===
                    Div(
                        Div(
                            Span(icon("credit-card", size=14), style="color: #64748b;"),
                            Span("Условия оплаты", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        # Row: All payment fields inline
                        Div(
                            Span("Аванс клиента", style=field_label_style),
                            Input(name="advance_from_client", type="number", value=str(get_var('advance_from_client', 100)), min="0", max="100", step="1",
                                  style="width: 60px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("%", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            style=input_row_style
                        ),
                        Div(
                            Span("До аванса", style=field_label_style),
                            Input(name="time_to_advance", type="number", value=str(get_var('time_to_advance', 0)), min="0",
                                  style="width: 60px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("дн.", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            Span("До расчёта", style=f"{field_label_style} margin-left: 20px; width: 80px;"),
                            Input(name="time_to_advance_on_receiving", type="number", value=str(get_var('time_to_advance_on_receiving', 0)), min="0",
                                  style="width: 60px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Span("дн.", style="margin-left: 4px; color: #64748b; font-size: 14px;"),
                            style=input_row_last_style
                        ),
                        style=card_style
                    ),

                    # === DM FEE CARD ===
                    Div(
                        Div(
                            Span(icon("award", size=14), style="color: #64748b;"),
                            Span("Вознаграждение (LPR)", style=section_title_style[len("font-size: 13px; font-weight: 600; color: #374151; margin: 0 0 12px 0; "):]),
                            style=section_title_style
                        ),
                        Div(
                            Span("Тип", style=field_label_style),
                            Select(
                                Option("Фикс.", value="fixed", selected=get_var('dm_fee_type', 'fixed') == "fixed"),
                                Option("%", value="percentage", selected=get_var('dm_fee_type', '') == "percentage"),
                                name="dm_fee_type",
                                style="width: 70px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc;"
                            ),
                            Span("Сумма", style=f"{field_label_style} margin-left: 16px; width: 60px;"),
                            Input(name="dm_fee_value", type="number", value=str(get_var('dm_fee_value', 0)), min="0", step="0.01",
                                  style="width: 80px; padding: 8px 10px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; text-align: right;"),
                            Select(
                                Option("RUB", value="RUB", selected=get_var('dm_fee_currency', 'RUB') == "RUB"),
                                Option("USD", value="USD", selected=get_var('dm_fee_currency', '') == "USD"),
                                Option("EUR", value="EUR", selected=get_var('dm_fee_currency', '') == "EUR"),
                                name="dm_fee_currency",
                                style="width: 65px; padding: 8px 6px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; margin-left: 4px;"
                            ),
                            style=input_row_last_style
                        ),
                        Span("Для % — валюта = валюте КП", style="font-size: 11px; color: #94a3b8; margin-top: 4px; display: block;"),
                        style=card_style
                    ),

                    style="flex: 1; min-width: 380px; max-width: 550px;"
                ),

                # Right column: Preview
                Div(
                    Div(
                        Div(
                            Span(icon("eye", size=14), style="color: #64748b;"),
                            Span("Предпросмотр", style="font-size: 13px; font-weight: 600; color: #374151; margin-left: 6px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        Span("Автообновление при изменении полей", style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 12px;"),
                        Div(
                            P("Введите данные слева для расчёта", style="margin: 0; font-size: 13px;"),
                            style="background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%); padding: 12px; border-radius: 8px; color: #1e40af;",
                            id="preview-panel"
                        ),
                        btn("Обновить", variant="secondary", icon_name="refresh-cw", type="button", size="sm",
                            hx_post=f"/quotes/{quote_id}/preview",
                            hx_target="#preview-panel",
                            hx_include="closest form",
                            style="margin-top: 12px;"
                        ),
                        style=f"{card_style} position: sticky; top: 16px;"
                    ),
                    style="flex: 1; min-width: 320px;"
                ),

                style="display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start;"
            ),

            # Hidden fields for version handling
            Input(type="hidden", name="version_action", id="version_action", value="new" if existing_versions else "auto"),
            Input(type="hidden", name="change_reason", id="change_reason", value=""),

            # Version dialog (shown only if versions exist)
            Div(
                Div(
                    # Dialog header
                    Div(
                        icon("git-branch", size=20),
                        Span("Сохранение версии", style="font-size: 16px; font-weight: 600; margin-left: 8px;"),
                        style="display: flex; align-items: center; margin-bottom: 16px;"
                    ),
                    # Current version info
                    Div(
                        Span(f"Текущая версия: v{current_version_num}", style="font-weight: 500;"),
                        style="margin-bottom: 12px; color: #64748b;"
                    ) if current_version_num > 0 else None,
                    # Options
                    Div(
                        # Update option (only if allowed)
                        Div(
                            Input(type="radio", name="version_choice", value="update", id="version_update",
                                  disabled=not can_update,
                                  style="margin-right: 8px;"),
                            Label(
                                f"Обновить версию v{current_version_num}",
                                fr="version_update",
                                style="cursor: pointer;" if can_update else "cursor: not-allowed; color: #9ca3af;"
                            ),
                            Span(" (не создавать новую)", style="font-size: 12px; color: #64748b;"),
                            style="margin-bottom: 8px;"
                        ) if can_update else Div(
                            icon("lock", size=14),
                            Span(update_reason, style="font-size: 13px; color: #dc2626; margin-left: 6px;"),
                            style="display: flex; align-items: center; margin-bottom: 12px; padding: 8px 12px; background: #fef2f2; border-radius: 6px; border: 1px solid #fecaca;"
                        ),
                        # New version option
                        Div(
                            Input(type="radio", name="version_choice", value="new", id="version_new", checked=True,
                                  style="margin-right: 8px;"),
                            Label(
                                f"Создать версию v{current_version_num + 1}",
                                fr="version_new",
                                style="cursor: pointer; font-weight: 500;"
                            ),
                            style="margin-bottom: 12px;"
                        ),
                        style="margin-bottom: 16px;"
                    ),
                    # Change reason (optional)
                    Div(
                        Label("Причина изменения (опционально):", style="font-size: 13px; color: #64748b; display: block; margin-bottom: 6px;"),
                        Input(type="text", id="change_reason_input", placeholder="Скидка по запросу клиента",
                              style="width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;"),
                        style="margin-bottom: 20px;"
                    ),
                    # Dialog buttons
                    Div(
                        Button("Сохранить", type="button", id="version_dialog_save",
                               style="padding: 10px 24px; background: #10b981; color: white; border: none; border-radius: 6px; font-weight: 500; cursor: pointer;"),
                        Button("Отмена", type="button", id="version_dialog_cancel",
                               style="padding: 10px 24px; background: #f1f5f9; color: #374151; border: 1px solid #e2e8f0; border-radius: 6px; margin-left: 8px; cursor: pointer;"),
                        style="display: flex; justify-content: flex-end;"
                    ),
                    style="background: white; padding: 24px; border-radius: 12px; max-width: 420px; width: 90%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);"
                ),
                id="version_dialog",
                style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000; justify-content: center; align-items: center;"
            ) if existing_versions else None,

            # Actions - compact
            Div(
                btn("Сохранить расчёт", variant="success", icon_name="check", type="button" if existing_versions else "submit",
                    id="save_calc_btn", onclick="showVersionDialog()" if existing_versions else None),
                btn_link("Отмена", href=f"/quotes/{quote_id}", variant="ghost"),
                style="display: flex; gap: 12px; margin-top: 16px; padding: 12px 16px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 10px; border: 1px solid #e2e8f0;"
            ),

            # JavaScript for version dialog
            Script(f"""
                function showVersionDialog() {{
                    document.getElementById('version_dialog').style.display = 'flex';
                }}

                document.addEventListener('DOMContentLoaded', function() {{
                    var dialog = document.getElementById('version_dialog');
                    var saveBtn = document.getElementById('version_dialog_save');
                    var cancelBtn = document.getElementById('version_dialog_cancel');
                    var form = document.querySelector('form[action="/quotes/{quote_id}/calculate"]');

                    if (cancelBtn) {{
                        cancelBtn.addEventListener('click', function() {{
                            dialog.style.display = 'none';
                        }});
                    }}

                    if (saveBtn) {{
                        saveBtn.addEventListener('click', function() {{
                            // Get selected version action
                            var versionChoice = document.querySelector('input[name="version_choice"]:checked');
                            if (versionChoice) {{
                                document.getElementById('version_action').value = versionChoice.value;
                            }}
                            // Get change reason
                            var changeReason = document.getElementById('change_reason_input');
                            if (changeReason) {{
                                document.getElementById('change_reason').value = changeReason.value;
                            }}
                            // Submit the form
                            dialog.style.display = 'none';
                            form.submit();
                        }});
                    }}

                    // Close dialog on backdrop click
                    if (dialog) {{
                        dialog.addEventListener('click', function(e) {{
                            if (e.target === dialog) {{
                                dialog.style.display = 'none';
                            }}
                        }});
                    }}
                }});
            """) if existing_versions else None,

            method="post",
            action=f"/quotes/{quote_id}/calculate",
            hx_post=f"/quotes/{quote_id}/preview",
            hx_target="#preview-panel",
            hx_trigger="input changed delay:500ms from:find input, input changed delay:500ms from:find select"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/calculate")
def post(
    quote_id: str,
    session,
    # Company settings
    seller_company: str = "МАСТЕР БЭРИНГ ООО",
    offer_sale_type: str = "поставка",
    offer_incoterms: str = "DDP",
    # Pricing (note: 'currency' matches form field name)
    currency: str = "RUB",
    markup: str = "15",
    supplier_discount: str = "0",
    exchange_rate: str = "1.0",
    delivery_time: str = "30",
    # Version handling (new fields)
    version_action: str = "auto",  # "auto", "update", "new"
    change_reason: str = "",
    # Logistics
    logistics_supplier_hub: str = "0",
    logistics_hub_customs: str = "0",
    logistics_customs_client: str = "0",
    # Brokerage (values and currencies)
    brokerage_hub: str = "0",
    brokerage_hub_currency: str = "RUB",
    brokerage_customs: str = "0",
    brokerage_customs_currency: str = "RUB",
    warehousing_at_customs: str = "0",
    warehousing_at_customs_currency: str = "RUB",
    customs_documentation: str = "0",
    customs_documentation_currency: str = "RUB",
    brokerage_extra: str = "0",
    brokerage_extra_currency: str = "RUB",
    # Payment terms
    advance_from_client: str = "100",
    advance_to_supplier: str = "100",
    time_to_advance: str = "0",
    time_to_advance_on_receiving: str = "0",
    # DM Fee
    dm_fee_type: str = "fixed",
    dm_fee_value: str = "0",
    dm_fee_currency: str = "RUB",
):
    """Execute full 13-phase calculation engine and save results."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote with items
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Error", Div("Quote not found", cls="alert alert-error"), session=session)

    quote = quote_result.data[0]
    # Note: 'currency' comes from form parameter (user's selection on calculate page)
    # Don't override with quote.get("currency") - the form value is what user wants

    # Get items via composition_service (Phase 5b): overlays purchase price
    # fields from invoice_item_prices when the item has an active composition
    # pointer, otherwise returns the quote_items row unchanged. The dict shape
    # is identical to a plain quote_items SELECT, so build_calculation_inputs()
    # sees no difference.
    items = get_composed_items(quote_id, supabase)

    if not items:
        return page_layout("Error",
            Div("Cannot calculate - no products in quote", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Validate that all available items have prices before calculation
    items_without_price = []
    for item in items:
        if item.get("is_unavailable"):
            continue
        price = safe_decimal(item.get("purchase_price_original") or item.get("base_price_vat"))
        if price <= 0:
            item_name = item.get("product_name", "—")
            item_brand = item.get("brand", "")
            item_label = f"{item_brand} — {item_name}" if item_brand else item_name
            items_without_price.append(item_label)

    if items_without_price:
        missing_list = Ul(
            *[Li(name, style="margin-bottom: 4px;") for name in items_without_price],
            style="margin: 12px 0; padding-left: 20px;"
        )
        return page_layout("Ошибка расчёта",
            Div(
                P(Strong("Не все позиции имеют цену. Заполните цены в разделе закупок перед расчётом."),
                  style="margin-bottom: 8px;"),
                P(f"Позиции без цены ({len(items_without_price)}):", style="margin-bottom: 4px; color: #64748b;"),
                missing_list,
                cls="alert alert-error"
            ),
            A("← Назад к КП", href=f"/quotes/{quote_id}", style="display: inline-block; margin-top: 12px;"),
            session=session
        )

    try:
        # ==========================================================================
        # AGGREGATE LOGISTICS FROM INVOICES (if form values are 0)
        # This ensures invoice-level logistics data flows to calculation even if
        # form fields weren't properly populated
        # ==========================================================================
        form_logistics_supplier_hub = safe_decimal(logistics_supplier_hub)
        form_logistics_hub_customs = safe_decimal(logistics_hub_customs)
        form_logistics_customs_client = safe_decimal(logistics_customs_client)

        print(f"[calc-debug] Form logistics values: S2H={logistics_supplier_hub}, H2C={logistics_hub_customs}, C2C={logistics_customs_client}")
        print(f"[calc-debug] Parsed form values: S2H={form_logistics_supplier_hub}, H2C={form_logistics_hub_customs}, C2C={form_logistics_customs_client}")

        # ==========================================================================
        # AGGREGATE DELIVERY TIME from invoices (logistics_total_days) + items (production_time_days)
        # ==========================================================================
        max_logistics_days = 0
        max_production_days = 0

        # Get max production_time_days from quote_items
        for item in items:
            prod_days = item.get("production_time_days") or 0
            if prod_days > max_production_days:
                max_production_days = prod_days

        # Get max logistics_total_days from invoices
        invoices_days_result = supabase.table("invoices") \
            .select("logistics_total_days") \
            .eq("quote_id", quote_id) \
            .execute()

        for inv in (invoices_days_result.data or []):
            log_days = inv.get("logistics_total_days") or 0
            if log_days > max_logistics_days:
                max_logistics_days = log_days

        # Calculate total delivery time
        aggregated_delivery_time = max_logistics_days + max_production_days
        form_delivery_time = safe_int(delivery_time)

        # Use aggregated value if it's greater than form value
        if aggregated_delivery_time > form_delivery_time:
            effective_delivery_time = aggregated_delivery_time
        else:
            effective_delivery_time = form_delivery_time

        print(f"[calc-debug] Delivery time: max_logistics={max_logistics_days}, max_production={max_production_days}, form={form_delivery_time}, effective={effective_delivery_time}")

        # ALWAYS aggregate logistics from invoices - invoices are the source of truth
        # (form values may be stale from previous calculations with different currency logic)
        print("[calc-debug] Aggregating logistics from invoices...")
        invoices_result = supabase.table("invoices") \
            .select("logistics_supplier_to_hub, logistics_hub_to_customs, logistics_customs_to_customer, "
                    "logistics_supplier_to_hub_currency, logistics_hub_to_customs_currency, logistics_customs_to_customer_currency") \
            .eq("quote_id", quote_id) \
            .execute()

        invoices_logistics = invoices_result.data or []

        # Import convert_amount for use in logistics aggregation and exchange rate calculation
        from services.currency_service import convert_amount

        if invoices_logistics:
            total_logistics_supplier_hub = Decimal(0)
            total_logistics_hub_customs = Decimal(0)
            total_logistics_customs_client = Decimal(0)

            print(f"[calc-debug] Quote currency: {currency}")
            print(f"[calc-debug] Found {len(invoices_logistics)} invoices with logistics data")
            print(f"[calc-debug] Converting all logistics to USD (standard storage currency)")

            for inv in invoices_logistics:
                # Supplier → Hub - convert to USD (standard storage currency)
                s2h_amount = Decimal(str(inv.get("logistics_supplier_to_hub") or 0))
                s2h_currency = inv.get("logistics_supplier_to_hub_currency") or "USD"
                if s2h_amount > 0:
                    converted = convert_amount(s2h_amount, s2h_currency, "USD")
                    print(f"[calc-debug] S2H: {s2h_amount} {s2h_currency} → {converted} USD")
                    total_logistics_supplier_hub += converted

                # Hub → Customs - convert to USD
                h2c_amount = Decimal(str(inv.get("logistics_hub_to_customs") or 0))
                h2c_currency = inv.get("logistics_hub_to_customs_currency") or "USD"
                if h2c_amount > 0:
                    converted = convert_amount(h2c_amount, h2c_currency, "USD")
                    print(f"[calc-debug] H2C: {h2c_amount} {h2c_currency} → {converted} USD")
                    total_logistics_hub_customs += converted

                # Customs → Customer - convert to USD
                c2c_amount = Decimal(str(inv.get("logistics_customs_to_customer") or 0))
                c2c_currency = inv.get("logistics_customs_to_customer_currency") or "USD"
                if c2c_amount > 0:
                    converted = convert_amount(c2c_amount, c2c_currency, "USD")
                    print(f"[calc-debug] C2C: {c2c_amount} {c2c_currency} → {converted} USD")
                    total_logistics_customs_client += converted

            # Use aggregated values (always override form values for logistics)
            print(f"[calc-debug] Aggregated logistics: S2H={total_logistics_supplier_hub}, H2C={total_logistics_hub_customs}, C2C={total_logistics_customs_client}")
            form_logistics_supplier_hub = total_logistics_supplier_hub
            form_logistics_hub_customs = total_logistics_hub_customs
            form_logistics_customs_client = total_logistics_customs_client
            print(f"[calc-debug] Final logistics values: S2H={form_logistics_supplier_hub}, H2C={form_logistics_hub_customs}, C2C={form_logistics_customs_client}")

        # ==========================================================================
        # STORE VALUES IN ORIGINAL CURRENCY (no conversion here)
        # Conversion to USD happens in build_calculation_inputs() before calculation
        # ==========================================================================
        print(f"[calc-debug] Brokerage (original): hub={brokerage_hub} {brokerage_hub_currency}, customs={brokerage_customs} {brokerage_customs_currency}")

        # Build variables from form parameters (store in ORIGINAL currency)
        variables = {
            'currency_of_quote': currency,
            'markup': safe_decimal(markup),
            'supplier_discount': safe_decimal(supplier_discount),
            'offer_incoterms': offer_incoterms,
            'delivery_time': effective_delivery_time,  # Uses MAX(logistics_days + production_days) if greater than form value
            'seller_company': seller_company,
            'offer_sale_type': offer_sale_type,

            # Logistics (stored in USD - aggregated from invoices which are already converted)
            'logistics_supplier_hub': form_logistics_supplier_hub,
            'logistics_hub_customs': form_logistics_hub_customs,
            'logistics_customs_client': form_logistics_customs_client,

            # Brokerage (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
            'brokerage_hub': safe_decimal(brokerage_hub),
            'brokerage_hub_currency': brokerage_hub_currency,
            'brokerage_customs': safe_decimal(brokerage_customs),
            'brokerage_customs_currency': brokerage_customs_currency,
            'warehousing_at_customs': safe_decimal(warehousing_at_customs),
            'warehousing_at_customs_currency': warehousing_at_customs_currency,
            'customs_documentation': safe_decimal(customs_documentation),
            'customs_documentation_currency': customs_documentation_currency,
            'brokerage_extra': safe_decimal(brokerage_extra),
            'brokerage_extra_currency': brokerage_extra_currency,

            # Payment terms
            'advance_from_client': safe_decimal(advance_from_client),
            'advance_to_supplier': safe_decimal(advance_to_supplier),
            'time_to_advance': safe_int(time_to_advance),
            'time_to_advance_on_receiving': safe_int(time_to_advance_on_receiving),

            # DM Fee (stored in ORIGINAL currency, converted to USD in build_calculation_inputs)
            'dm_fee_type': dm_fee_type,
            'dm_fee_value': safe_decimal(dm_fee_value),
            'dm_fee_currency': dm_fee_currency,

            # Exchange rate
            'exchange_rate': safe_decimal(exchange_rate),
        }

        # Build calculation inputs for all items
        calc_inputs = build_calculation_inputs(items, variables)

        print(f"[calc-debug] Variables passed to calc: logistics_supplier_hub={variables['logistics_supplier_hub']}, logistics_hub_customs={variables['logistics_hub_customs']}, logistics_customs_client={variables['logistics_customs_client']}")
        print(f"[calc-debug] Brokerage: hub={variables['brokerage_hub']}, customs={variables['brokerage_customs']}, warehousing={variables['warehousing_at_customs']}, docs={variables['customs_documentation']}, extra={variables['brokerage_extra']}")

        # Run full 13-phase calculation engine
        results = calculate_multiproduct_quote(calc_inputs)

        # Calculate totals from results
        total_purchase = sum(safe_decimal(r.purchase_price_total_quote_currency) for r in results)
        total_logistics = sum(safe_decimal(r.logistics_total) for r in results)
        print(f"[calc-debug] Calc results: total_purchase={total_purchase}, total_logistics={total_logistics}")
        total_brokerage = (
            safe_decimal(variables['brokerage_hub']) +
            safe_decimal(variables['brokerage_customs']) +
            safe_decimal(variables['warehousing_at_customs']) +
            safe_decimal(variables['customs_documentation']) +
            safe_decimal(variables['brokerage_extra'])
        )
        total_cogs = sum(safe_decimal(r.cogs_per_product) for r in results)
        total_profit = sum(safe_decimal(r.profit) for r in results)
        total_no_vat = sum(safe_decimal(r.sales_price_total_no_vat) for r in results)
        total_with_vat = sum(safe_decimal(r.sales_price_total_with_vat) for r in results)
        total_vat = sum(safe_decimal(r.vat_net_payable) for r in results)
        total_customs = sum(safe_decimal(r.customs_fee) for r in results)

        avg_margin = (total_profit / total_cogs * 100) if total_cogs else Decimal("0")

        # Calculate exchange rate from quote currency to USD for analytics
        if currency == 'USD':
            exchange_rate_to_usd = Decimal("1.0")
        else:
            exchange_rate_to_usd = safe_decimal(convert_amount(Decimal("1"), currency, 'USD'))
            if exchange_rate_to_usd == 0:
                exchange_rate_to_usd = Decimal("1.0")  # Fallback

        # Calculate USD equivalents for analytics
        subtotal_usd = total_purchase * exchange_rate_to_usd
        total_amount_usd = total_with_vat * exchange_rate_to_usd
        total_profit_usd = total_profit * exchange_rate_to_usd

        # Update quote totals (only use columns that exist in quotes table)
        supabase.table("quotes").update({
            "subtotal": float(total_purchase),
            "total_amount": float(total_with_vat),
            "total_profit_usd": float(total_profit_usd),
            # Quote-currency totals (for display on summary tab)
            "total_quote_currency": float(total_with_vat),
            "revenue_no_vat_quote_currency": float(total_no_vat),
            "profit_quote_currency": float(total_profit),
            "cogs_quote_currency": float(total_cogs),
            # USD analytics columns
            "exchange_rate_to_usd": float(exchange_rate_to_usd),
            "subtotal_usd": float(subtotal_usd),
            "total_amount_usd": float(total_amount_usd),
            "updated_at": datetime.now().isoformat()
        }).eq("id", quote_id).execute()

        # Convert Decimal values to float for JSON storage
        variables_for_storage = {
            k: float(v) if isinstance(v, Decimal) else v
            for k, v in variables.items()
        }

        # Store calculation variables
        variables_record = {
            "quote_id": quote_id,
            "variables": variables_for_storage,
            "updated_at": datetime.now().isoformat()
        }
        existing_vars = supabase.table("quote_calculation_variables") \
            .select("quote_id") \
            .eq("quote_id", quote_id) \
            .execute()
        if existing_vars.data:
            supabase.table("quote_calculation_variables") \
                .update(variables_record) \
                .eq("quote_id", quote_id) \
                .execute()
        else:
            supabase.table("quote_calculation_variables") \
                .insert(variables_record) \
                .execute()

        # Store per-item calculation results (as JSONB)
        for item, result in zip(items, results):
            # Build phase_results JSONB with all calculation outputs
            phase_results = {
                # Purchase prices
                "N16": float(result.purchase_price_no_vat or 0),
                "P16": float(result.purchase_price_after_discount or 0),
                "R16": float(result.purchase_price_per_unit_quote_currency or 0),
                "S16": float(result.purchase_price_total_quote_currency or 0),
                # Logistics
                "T16": float(result.logistics_first_leg or 0),
                "U16": float(result.logistics_last_leg or 0),
                "V16": float(result.logistics_total or 0),
                # Customs and taxes
                "Y16": float(result.customs_fee or 0),
                "Z16": float(result.excise_tax_amount or 0),
                # COGS
                "AA16": float(result.cogs_per_unit or 0),
                "AB16": float(result.cogs_per_product or 0),
                # Sale prices (excl financial)
                "AD16": float(result.sale_price_per_unit_excl_financial or 0),
                "AE16": float(result.sale_price_total_excl_financial or 0),
                # Profit and fees
                "AF16": float(result.profit or 0),
                "AG16": float(result.dm_fee or 0),
                "AH16": float(result.forex_reserve or 0),
                "AI16": float(result.financial_agent_fee or 0),
                # Final sale prices
                "AJ16": float(result.sales_price_per_unit_no_vat or 0),
                "AK16": float(result.sales_price_total_no_vat or 0),
                "AL16": float(result.sales_price_total_with_vat or 0),
                "AM16": float(result.sales_price_per_unit_with_vat or 0),
                # VAT breakdown
                "AN16": float(result.vat_from_sales or 0),
                "AO16": float(result.vat_on_import or 0),
                "AP16": float(result.vat_net_payable or 0),
                # Special
                "AQ16": float(result.transit_commission or 0),
                # Internal pricing
                "AX16": float(result.internal_sale_price_per_unit or 0),
                "AY16": float(result.internal_sale_price_total or 0),
                # Financing
                "BA16": float(result.financing_cost_initial or 0),
                "BB16": float(result.financing_cost_credit or 0),
            }

            # Convert phase_results to USD for analytics
            rate = float(exchange_rate_to_usd)
            phase_results_usd = {k: v * rate for k, v in phase_results.items()}

            item_result = {
                "quote_id": quote_id,
                "quote_item_id": item["id"],
                "phase_results": phase_results,
                "phase_results_usd": phase_results_usd,
                "calculated_at": datetime.now().isoformat()
            }
            existing_result = supabase.table("quote_calculation_results") \
                .select("quote_item_id") \
                .eq("quote_item_id", item["id"]) \
                .execute()
            if existing_result.data:
                supabase.table("quote_calculation_results") \
                    .update(item_result) \
                    .eq("quote_item_id", item["id"]) \
                    .execute()
            else:
                supabase.table("quote_calculation_results") \
                    .insert(item_result) \
                    .execute()

            # Update quote_items with calculated prices
            quantity = item.get("quantity", 1)
            base_price_vat_per_unit = float(result.sales_price_total_with_vat) / quantity if quantity > 0 else 0
            supabase.table("quote_items").update({
                "base_price_vat": base_price_vat_per_unit
            }).eq("id", item["id"]).execute()

        # Store calculation summary (with USD equivalents for analytics)
        rate = float(exchange_rate_to_usd)
        calc_summary = {
            "quote_id": quote_id,
            # Quote currency values
            "calc_s16_total_purchase_price": float(total_purchase),
            "calc_v16_total_logistics": float(total_logistics),
            "calc_y16_customs_duty": float(total_customs),
            "calc_total_brokerage": float(total_brokerage),
            "calc_ae16_sale_price_total": float(total_no_vat),
            "calc_al16_total_with_vat": float(total_with_vat),
            "calc_af16_profit_margin": float(avg_margin),
            # USD equivalents for analytics
            "exchange_rate_to_usd": rate,
            "calc_s16_total_purchase_price_usd": float(total_purchase) * rate,
            "calc_v16_total_logistics_usd": float(total_logistics) * rate,
            "calc_y16_customs_duty_usd": float(total_customs) * rate,
            "calc_total_brokerage_usd": float(total_brokerage) * rate,
            "calc_ae16_sale_price_total_usd": float(total_no_vat) * rate,
            "calc_al16_total_with_vat_usd": float(total_with_vat) * rate,
            "calc_af16_total_profit_usd": float(total_profit) * rate,
            "calculated_at": datetime.now().isoformat()
        }
        existing_summary = supabase.table("quote_calculation_summaries") \
            .select("quote_id") \
            .eq("quote_id", quote_id) \
            .execute()
        if existing_summary.data:
            supabase.table("quote_calculation_summaries") \
                .update(calc_summary) \
                .eq("quote_id", quote_id) \
                .execute()
        else:
            supabase.table("quote_calculation_summaries") \
                .insert(calc_summary) \
                .execute()

        # Update quote currency if it changed
        if quote.get("currency") != currency:
            supabase.table("quotes") \
                .update({"currency": currency}) \
                .eq("id", quote_id) \
                .execute()

        # Handle partial recalculation for price-only changes
        partial_recalc = quote.get("partial_recalc")
        if partial_recalc == "price":
            # Clear partial_recalc flag
            supabase.table("quotes").update({
                "partial_recalc": None
            }).eq("id", quote_id).execute()

            # Transition back to client_negotiation
            user_roles = user.get("roles", [])
            transition_quote_status(
                quote_id=quote_id,
                to_status="client_negotiation",
                actor_id=user["id"],
                actor_roles=user_roles,
                comment="Partial recalculation: price updated, returning to client negotiation"
            )

        # Create or update quote version for audit trail
        all_results = []
        for item, result in zip(items, results):
            all_results.append({
                "item_id": item["id"],
                "N16": float(result.purchase_price_no_vat or 0),
                "S16": float(result.purchase_price_total_quote_currency or 0),
                "V16": float(result.logistics_total or 0),
                "AB16": float(result.cogs_per_product or 0),
                "AJ16": float(result.sales_price_per_unit_no_vat or 0),
                "AK16": float(result.sales_price_total_no_vat or 0),
                "AL16": float(result.sales_price_total_with_vat or 0),
                "AF16": float(result.profit or 0),
            })

        version_totals = {
            "total_purchase": float(total_purchase),
            "total_logistics": float(total_logistics),
            "total_cogs": float(total_cogs),
            "total_profit": float(total_profit),
            "total_no_vat": float(total_no_vat),
            "total_with_vat": float(total_with_vat),
            "avg_margin": float(avg_margin),
        }

        try:
            # Check existing versions and decide action
            existing_versions = list_quote_versions(quote_id, user["org_id"])
            current_version = get_current_quote_version(quote_id, user["org_id"]) if existing_versions else None

            # Determine change reason text
            reason_text = change_reason if change_reason else "Calculation saved"

            if not existing_versions:
                # First version - always create (no dialog shown)
                # Phase 5d: items sourced from composition_service inside the
                # snapshot function — not passed as kwarg.
                version = create_quote_version(
                    quote_id=quote_id,
                    user_id=user["id"],
                    variables=variables,
                    results=all_results,
                    totals=version_totals,
                    change_reason=reason_text,
                    customer_id=quote.get("customer_id")
                )
                version_number = version.get("version") if version else 1

            elif version_action == "update" and current_version:
                # User chose to update existing version
                can_update_flag, _ = can_update_version(quote_id, user["org_id"])
                if can_update_flag:
                    version = update_quote_version(
                        version_id=current_version["id"],
                        quote_id=quote_id,
                        org_id=user["org_id"],
                        user_id=user["id"],
                        variables=variables,
                        results=all_results,
                        totals=version_totals,
                        change_reason=reason_text
                    )
                    version_number = current_version.get("version_number", 1)
                else:
                    # Can't update, create new instead
                    version = create_quote_version(
                        quote_id=quote_id,
                        user_id=user["id"],
                        variables=variables,
                        results=all_results,
                        totals=version_totals,
                        change_reason=reason_text,
                        customer_id=quote.get("customer_id")
                    )
                    version_number = version.get("version") if version else None

            else:
                # Create new version (default or user explicitly chose "new")
                version = create_quote_version(
                    quote_id=quote_id,
                    user_id=user["id"],
                    variables=variables,
                    results=all_results,
                    totals=version_totals,
                    change_reason=reason_text,
                    customer_id=quote.get("customer_id")
                )
                version_number = version.get("version") if version else None

        except Exception as ve:
            # Version creation is optional - don't fail calculation
            version_number = None
            print(f"Warning: Failed to create version: {ve}")

        # Build detailed results page
        product_rows = []
        for item, result in zip(items, results):
            product_rows.append(
                Tr(
                    Td(item.get('product_name', 'Product')[:40]),
                    Td(str(item.get('quantity', 1))),
                    Td(format_money(result.cogs_per_unit, currency)),
                    Td(format_money(result.sales_price_per_unit_no_vat, currency)),
                    Td(format_money(result.sales_price_total_with_vat, currency)),
                    Td(format_money(result.profit, currency)),
                )
            )

        return page_layout(f"Результат расчёта - {quote.get('idn_quote', '')}",
            Div("Расчёт выполнен и сохранён!", cls="alert alert-success"),

            H1(f"Результат: {quote.get('idn_quote', '')}"),

            # Summary stats
            Div(
                Div(
                    Div("Итого (без НДС)", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_no_vat, currency), cls="stat-value"),
                    cls="stat-card"
                ),
                Div(
                    Div("Итого (с НДС)", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_with_vat, currency), cls="stat-value", style="color: #28a745;"),
                    cls="stat-card"
                ),
                Div(
                    Div("Общий профит", style="font-size: 0.875rem; color: #666;"),
                    Div(format_money(total_profit, currency), cls="stat-value"),
                    cls="stat-card"
                ),
                Div(
                    Div("Наценка (профит ÷ себест.)", style="font-size: 0.875rem; color: #666;"),
                    Div(f"{avg_margin:.1f}%", cls="stat-value"),
                    cls="stat-card"
                ),
                cls="stats-grid"
            ),

            # Cost breakdown
            Div(
                H3("Структура затрат"),
                Table(
                    Tr(Td("Закупка товаров:"), Td(format_money(total_purchase, currency))),
                    Tr(Td("Логистика:"), Td(format_money(total_logistics, currency))),
                    Tr(Td("Брокерские услуги:"), Td(format_money(total_brokerage, currency))),
                    Tr(Td("Себестоимость:"), Td(format_money(total_cogs, currency))),
                    Tr(Td(Strong("НДС к уплате:")), Td(Strong(format_money(total_vat, currency)))),
                ),
                cls="card"
            ),

            # Product details
            Div(
                H3("Детализация по позициям"),
                Table(
                    Thead(
                        Tr(
                            Th("Товар"),
                            Th("Кол-во"),
                            Th("Себест./ед."),
                            Th("Цена/ед."),
                            Th("Итого"),
                            Th("Профит"),
                        )
                    ),
                    Tbody(*product_rows),
                    Tfoot(
                        Tr(
                            Td(Strong("ИТОГО"), colspan="4"),
                            Td(Strong(format_money(total_with_vat, currency))),
                            Td(Strong(format_money(total_profit, currency))),
                        )
                    ),
                ),
                cls="card"
            ),

            # Variables used
            Div(
                H3("Параметры расчёта"),
                Table(
                    Tr(Td("Наценка:"), Td(f"{variables['markup']}%")),
                    Tr(Td("Инкотермс:"), Td(variables['offer_incoterms'])),
                    Tr(Td("Срок поставки:"), Td(f"{variables['delivery_time']} дн.")),
                    Tr(Td("Аванс клиента:"), Td(f"{variables['advance_from_client']}%")),
                    Tr(Td("Курс:"), Td(str(variables['exchange_rate']))),
                ),
                cls="card"
            ),

            # Actions
            Div(
                btn_link("Назад к КП", href=f"/quotes/{quote_id}", variant="secondary", icon_name="arrow-left"),
                btn_link("Пересчитать", href=f"/quotes/{quote_id}/calculate", variant="primary", icon_name="calculator"),
                cls="form-actions"
            ),

            session=session
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return page_layout("Ошибка расчёта",
            Div(f"Ошибка: {str(e)}", cls="alert alert-error"),
            btn_link("Назад", href=f"/quotes/{quote_id}/calculate", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# NOTE: POST /api/quotes/{quote_id}/calculate — extracted in Phase 6B-6a to
# api/quotes.py::calculate_quote, registered via api/routers/quotes.py.


# ============================================================================
# QUOTE CANCEL API + WORKFLOW TRANSITION API
# ============================================================================
# Extracted to api/quotes.py::cancel_quote and api/quotes.py::transition_workflow
# in 6B-6b, registered via api/routers/quotes.py.


# ============================================================================
# QUOTE DOCUMENTS TAB
# ============================================================================

@rt("/quotes/{quote_id}/documents")
def get(quote_id: str, session):
    """View documents tab for a quote with hierarchical binding support"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]
    user_roles = get_session_user_roles(session)

    supabase = get_supabase()

    # Get quote details
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, status, workflow_status, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            Div("Запрошенное КП не существует или у вас нет доступа.", cls="card"),
            A("← К списку КП", href="/quotes"),
            session=session
        )

    quote = quote_result.data[0]
    quote_number = quote.get("idn_quote") or quote_id[:8]
    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    # Get customer name
    customer_name = (quote.get("customers") or {}).get("name", "—")
    if customer_name == "—" and quote.get("customer_id"):
        customer_result = supabase.table("customers") \
            .select("name") \
            .eq("id", quote["customer_id"]) \
            .execute()
        if customer_result.data:
            customer_name = customer_result.data[0].get("name", "—")

    # Get supplier invoices for this quote (for invoice binding dropdown)
    invoices = []
    try:
        # First get quote item IDs
        quote_items_result = supabase.table("quote_items") \
            .select("id") \
            .eq("quote_id", quote_id) \
            .execute()

        quote_item_ids = [item["id"] for item in (quote_items_result.data or [])]

        if quote_item_ids:
            # Get invoice items linked to this quote's items
            invoice_items_result = supabase.table("supplier_invoice_items") \
                .select("invoice_id") \
                .in_("quote_item_id", quote_item_ids) \
                .execute()

            if invoice_items_result.data:
                invoice_ids = list(set(item["invoice_id"] for item in invoice_items_result.data if item.get("invoice_id")))
                if invoice_ids:
                    invoices_result = supabase.table("supplier_invoices") \
                        .select("id, invoice_number, supplier_id") \
                        .in_("id", invoice_ids) \
                        .order("invoice_date", desc=True) \
                        .execute()

                    if invoices_result.data:
                        # Get supplier names
                        supplier_ids = list(set(inv["supplier_id"] for inv in invoices_result.data if inv.get("supplier_id")))
                        suppliers_map = {}
                        if supplier_ids:
                            suppliers_result = supabase.table("suppliers") \
                                .select("id, name") \
                                .in_("id", supplier_ids) \
                                .execute()
                            suppliers_map = {s["id"]: s["name"] for s in (suppliers_result.data or [])}

                        for inv in invoices_result.data:
                            invoices.append({
                                "id": inv["id"],
                                "invoice_number": inv.get("invoice_number", ""),
                                "supplier_name": suppliers_map.get(inv.get("supplier_id"), "")
                            })
    except Exception as e:
        print(f"Error fetching invoices for quote documents: {e}")

    # Get quote items (for certificate binding dropdown)
    items = []
    try:
        items_result = supabase.table("quote_items") \
            .select("id, product_name, product_code, brand") \
            .eq("quote_id", quote_id) \
            .order("position") \
            .execute()

        if items_result.data:
            for item in items_result.data:
                items.append({
                    "id": item["id"],
                    "name": item.get("product_name", "Товар"),
                    "sku": item.get("product_code", ""),
                    "brand": item.get("brand", "")
                })
    except Exception as e:
        print(f"Error fetching items for quote documents: {e}")

    # Determine permissions based on roles
    can_upload = user_has_any_role(session, ["admin", "sales", "sales_manager", "procurement", "quote_controller", "finance", "logistics", "customs"])
    can_delete = user_has_any_role(session, ["admin", "sales_manager", "quote_controller", "finance"])

    # Get total documents count (all related to this quote)
    doc_count = count_all_documents_for_quote(quote_id)

    return page_layout(
        f"Документы КП {quote_number}",

        # Persistent header with IDN, status, client name
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs for quote detail navigation
        quote_detail_tabs(quote_id, "documents", user_roles),

        # Info card with gradient styling
        Div(
            P(
                icon("info", size=16, color="#3b82f6"),
                " Здесь можно загружать и просматривать все документы по КП: документы самого КП, сканы инвойсов и сертификаты на товары.",
                style="display: flex; align-items: flex-start; gap: 0.5rem; margin: 0; color: #64748b; font-size: 0.875rem;"
            ),
            cls="card",
            style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left: 4px solid #3b82f6; margin-bottom: 1.5rem; padding: 1rem; border-radius: 8px;"
        ),

        # Documents section with hierarchical binding
        _quote_documents_section(
            quote_id=quote_id,
            session=session,
            invoices=invoices,
            items=items,
            can_upload=can_upload,
            can_delete=can_delete
        ),

        # Document chain section (grouped by stage)
        _render_document_chain_section(quote_id),

        # Currency invoices section (verified/exported only, hidden if no deal)
        _render_currency_invoices_section(quote_id, supabase),

        # Back button
        Div(
            A(icon("arrow-left", size=16), " К обзору КП", href=f"/quotes/{quote_id}",
              style="display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text-secondary); text-decoration: none;"),
            style="margin-top: 2rem;"
        ),

        session=session
    )


# ============================================================================
# DOCUMENT CHAIN (P2.10)
# ============================================================================

def _build_document_chain(quote_id):
    """
    Build document chain structure for a quote.

    Groups all documents related to a quote into 5 stages:
    - quote: Documents directly attached to the quote (entity_type='quote')
    - specification: Documents attached to specifications (entity_type='specification')
    - supplier_invoice: Documents attached to supplier invoices (entity_type='supplier_invoice')
    - upd: Documents with document_type='upd' (from any entity)
    - customs_declaration: Documents with document_type='customs_declaration' (from any entity)

    Args:
        quote_id: Quote UUID

    Returns:
        Dict with 5 stage keys, each mapping to a list of documents
    """
    all_docs = get_all_documents_for_quote(quote_id)

    chain = {
        "quote": [],
        "specification": [],
        "supplier_invoice": [],
        "customs_declaration": [],
        "upd": [],
    }

    for doc in all_docs:
        # First check document_type for upd and customs_declaration
        if doc.document_type == "upd":
            chain["upd"].append(doc)
        elif doc.document_type == "customs_declaration":
            chain["customs_declaration"].append(doc)
        elif doc.entity_type == "quote":
            chain["quote"].append(doc)
        elif doc.entity_type == "specification":
            chain["specification"].append(doc)
        elif doc.entity_type == "supplier_invoice":
            chain["supplier_invoice"].append(doc)
        else:
            # Default: attach to quote stage
            chain["quote"].append(doc)

    return chain


def _render_document_chain_section(quote_id: str):
    """
    Render the document chain section showing documents grouped by stage.
    Used as a sub-section within the merged Documents tab.
    """
    chain = _build_document_chain(quote_id)

    # Define chain stages with Russian labels and icons
    chain_stages = [
        {"key": "quote", "label": "КП", "icon": "file-text", "color": "#3b82f6"},
        {"key": "specification", "label": "Спецификация", "icon": "clipboard-list", "color": "#8b5cf6"},
        {"key": "supplier_invoice", "label": "Инвойс", "icon": "receipt", "color": "#f59e0b"},
        {"key": "customs_declaration", "label": "ГТД", "icon": "shield", "color": "#ef4444"},
        {"key": "upd", "label": "УПД", "icon": "file-check", "color": "#22c55e"},
    ]

    # Build stage cards
    stage_cards = []
    for stage in chain_stages:
        docs = chain.get(stage["key"], [])
        doc_count = len(docs)

        # Build document list for this stage
        doc_items = []
        for doc in docs:
            doc_items.append(
                Div(
                    I(cls=f"fa-solid {get_file_icon(doc.mime_type)}", style=f"margin-right: 0.5rem; color: {stage['color']};"),
                    A(doc.original_filename,
                      href=f"/documents/{doc.id}/view",
                      target="_blank",
                      style="text-decoration: none; color: #1e293b; font-size: 13px;"),
                    Span(
                        get_document_type_label(doc.document_type),
                        style="margin-left: 8px; font-size: 11px; color: #64748b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;"
                    ) if doc.document_type else "",
                    style="display: flex; align-items: center; padding: 6px 0; border-bottom: 1px solid #f1f5f9;"
                )
            )

        stage_cards.append(
            Div(
                # Stage header
                Div(
                    Div(
                        icon(stage["icon"], size=20, color=stage["color"]),
                        Span(stage["label"], style=f"font-size: 14px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    ),
                    Span(
                        str(doc_count),
                        style=f"background: {stage['color']}20; color: {stage['color']}; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid " + stage["color"] + ";"
                ),
                # Document list or empty state
                Div(*doc_items) if doc_items else Div(
                    Span("Нет документов", style="font-size: 13px; color: #94a3b8; font-style: italic;"),
                    style="padding: 12px 0; text-align: center;"
                ),
                style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
            )
        )

    return Div(
        # Divider
        Hr(style="margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;"),

        # Section header
        H3(
            icon("link", size=20),
            " Цепочка документов по стадиям",
            style="display: flex; align-items: center; gap: 0.5rem; margin: 0 0 1rem; font-size: 1.1rem; color: #1e293b;"
        ),

        # Chain timeline grid
        Div(
            *stage_cards,
            style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;"
        ),
    )


def _render_currency_invoices_section(quote_id: str, supabase):
    """
    Render 'Валютные инвойсы' section for quote documents tab.
    Only shows invoices with status 'verified' or 'exported'.
    Returns empty string if no deal exists for this quote.
    """
    # Check if a deal exists for this quote
    try:
        deal_resp = supabase.table("deals").select("id").eq("quote_id", quote_id).is_("deleted_at", None).execute()
        deals = deal_resp.data or []
    except Exception as e:
        print(f"Error checking deals for quote {quote_id}: {e}")
        return ""

    if not deals:
        return ""

    deal_ids = [d["id"] for d in deals]

    # Fetch approved currency invoices for these deals
    try:
        ci_resp = supabase.table("currency_invoices").select(
            "id, invoice_number, segment, total_amount, currency, status, generated_at"
        ).in_("deal_id", deal_ids).in_("status", ["verified", "exported"]).order("generated_at", desc=True).execute()
        approved_cis = ci_resp.data or []
    except Exception as e:
        print(f"Error fetching approved currency invoices for quote {quote_id}: {e}")
        approved_cis = []

    # Build cards
    if approved_cis:
        cards = []
        for ci in approved_cis:
            total = float(ci.get("total_amount", 0) or 0)
            cards.append(
                A(
                    Div(
                        Div(
                            _ci_segment_badge(ci.get("segment", "")),
                            _ci_status_badge(ci.get("status", "")),
                            style="display: flex; gap: 6px; align-items: center; margin-bottom: 8px;"
                        ),
                        Div(
                            ci.get("invoice_number", "—"),
                            style="font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 4px;"
                        ),
                        Div(
                            f"{total:,.2f} {ci.get('currency', '')}",
                            style="font-size: 13px; color: #64748b;"
                        ),
                    ),
                    href=f"/currency-invoices/{ci['id']}",
                    style="display: block; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; text-decoration: none; transition: box-shadow 0.15s;",
                    onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'",
                    onmouseout="this.style.boxShadow='none'"
                )
            )
        content = Div(*cards, style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px;")
    else:
        content = Div(
            Span("Нет утверждённых валютных инвойсов",
                 style="font-size: 13px; color: #94a3b8; font-style: italic;"),
            style="padding: 16px 0;"
        )

    count_badge = Span(
        str(len(approved_cis)),
        style="background: #8b5cf620; color: #8b5cf6; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"
    ) if approved_cis else ""

    return Div(
        Hr(style="margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;"),
        H3(
            icon("receipt", size=20),
            " Валютные инвойсы",
            count_badge,
            style="display: flex; align-items: center; gap: 0.5rem; margin: 0 0 1rem; font-size: 1.1rem; color: #1e293b;"
        ),
        content,
    )


# ============================================================================
# VERSION HISTORY ROUTES
# ============================================================================

@rt("/quotes/{quote_id}/versions")
def get(quote_id: str, session):
    """View version history for a quote"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    supabase = get_supabase()

    # Get quote
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", user["org_id"]) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("Not Found", H1("Quote not found"), session=session)

    quote = quote_result.data[0]
    currency = quote.get("currency", "USD")

    # Get versions
    versions = list_quote_versions(quote_id, user["org_id"])

    # Build version rows
    version_rows = []
    for v in versions:
        version_rows.append(
            Tr(
                Td(f"v{v['version_number']}"),
                Td(v.get("status", "draft")),
                Td(format_money(v.get("total_quote_currency"), currency)),
                Td(v.get("change_reason", "-")),
                Td(v.get("created_at", "")[:16].replace("T", " ")),
                Td(
                    A("View", href=f"/quotes/{quote_id}/versions/{v['version_number']}", style="margin-right: 0.5rem;"),
                ),
            )
        )

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    table_style = """
        width: 100%;
        border-collapse: collapse;
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    """

    th_style = """
        padding: 14px 16px;
        text-align: left;
        background: #f8fafc;
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        border-bottom: 1px solid #e2e8f0;
    """

    td_style = "padding: 14px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; color: #334155;"

    return page_layout(f"История версий - {quote.get('idn_quote', '')}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), " Назад к КП", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1(f"История версий",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                Span(icon("file-text", size=14), style="color: #64748b;"),
                Span(f"КП: {quote.get('idn_quote', '-')}", style="color: #475569; font-weight: 500;"),
                Span(" • ", style="color: #cbd5e1;"),
                Span(f"Клиент: {quote.get('customers', {}).get('name', '-')}", style="color: #64748b;"),
                style="display: flex; align-items: center; gap: 8px; font-size: 14px;"
            ),
            style=header_style
        ),

        # Versions table
        Table(
            Thead(
                Tr(
                    Th("Версия", style=th_style),
                    Th("Статус", style=th_style),
                    Th("Сумма", style=th_style),
                    Th("Причина изменения", style=th_style),
                    Th("Создана", style=th_style),
                    Th("", style=th_style),
                )
            ),
            Tbody(
                *[Tr(
                    Td(f"v{v['version_number']}", style=f"{td_style} font-weight: 600;"),
                    Td(
                        Span(v.get("status", "draft"),
                             style=f"padding: 4px 10px; border-radius: 12px; font-size: 12px; "
                                   f"background: {'#dcfce7' if v.get('status') == 'approved' else '#fef3c7' if v.get('status') == 'sent' else '#f1f5f9'}; "
                                   f"color: {'#166534' if v.get('status') == 'approved' else '#92400e' if v.get('status') == 'sent' else '#475569'};"),
                        style=td_style
                    ),
                    Td(format_money(v.get("total_quote_currency"), currency), style=f"{td_style} font-weight: 500;"),
                    Td(v.get("change_reason") or "-", style=f"{td_style} color: #64748b;"),
                    Td(v.get("created_at", "")[:16].replace("T", " "), style=f"{td_style} color: #64748b; font-size: 13px;"),
                    Td(
                        A(icon("eye", size=14), " Просмотр", href=f"/quotes/{quote_id}/versions/{v['version_number']}",
                          style="color: #3b82f6; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 4px;"),
                        style=td_style
                    ),
                ) for v in versions]
            ) if version_rows else Tbody(
                Tr(Td("Версий пока нет. Запустите расчёт для создания первой версии.",
                      colspan="6", style=f"{td_style} text-align: center; color: #94a3b8; padding: 40px;"))
            ),
            style=table_style
        ),

        # Action buttons
        Div(
            A(icon("arrow-left", size=14), " К КП", href=f"/quotes/{quote_id}",
              style="padding: 10px 16px; background: #f1f5f9; color: #475569; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
            A(icon("calculator", size=14), " Новый расчёт", href=f"/quotes/{quote_id}/calculate",
              style="padding: 10px 16px; background: #3b82f6; color: white; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
            style="margin-top: 20px; display: flex; gap: 12px;"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/versions/{version_num}")
def get(quote_id: str, version_num: int, session):
    """View specific version details"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    # Get version
    version = get_quote_version(quote_id, version_num, user["org_id"])

    if not version:
        return page_layout("Not Found", H1("Version not found"), session=session)

    # Get quote for context
    supabase = get_supabase()
    quote_result = supabase.table("quotes") \
        .select("idn_quote, currency") \
        .eq("id", quote_id) \
        .is_("deleted_at", None) \
        .execute()

    quote = quote_result.data[0] if quote_result.data else {}
    currency = quote.get("currency", "USD")

    # Build products from snapshot
    products = version.get("products_snapshot", [])
    results = version.get("calculation_results", [])

    product_rows = []
    for i, p in enumerate(products):
        r = results[i] if i < len(results) else {}
        product_rows.append(
            Tr(
                Td(p.get("product_name", "-")[:40]),
                Td(str(p.get("quantity", 1))),
                Td(format_money(r.get("AJ16"), currency)),
                Td(format_money(r.get("AL16"), currency)),
                Td(format_money(r.get("AF16"), currency)),
            )
        )

    # Get variables
    variables = version.get("quote_variables", {})

    return page_layout(f"Version {version_num} - {quote.get('idn_quote', '')}",
        # Gradient header card
        Div(
            Div(
                A(
                    icon("arrow-left", size=16, color="#64748b"),
                    Span("К истории версий", style="margin-left: 6px;"),
                    href=f"/quotes/{quote_id}/versions",
                    style="display: inline-flex; align-items: center; color: #64748b; text-decoration: none; font-size: 13px; margin-bottom: 12px;"
                ),
                Div(
                    icon("history", size=24, color="#6366f1"),
                    Span(f"Версия {version_num}", style="font-size: 24px; font-weight: 600; color: #1e293b; margin-left: 10px;"),
                    status_badge(version.get("status", "draft")),
                    style="display: flex; align-items: center; gap: 12px;"
                ),
                Div(
                    Span(f"КП: {quote.get('idn_quote', '-')}", style="color: #64748b; font-size: 14px;"),
                    style="margin-top: 4px;"
                ),
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        # Two column layout
        Div(
            # Left column - Version Info & Variables
            Div(
                # Version metadata card
                Div(
                    Div(
                        icon("info", size=16, color="#64748b"),
                        Span("ИНФОРМАЦИЯ О ВЕРСИИ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        Div(
                            Span("Дата создания", style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;"),
                            Span(version.get("created_at", "")[:16].replace("T", " "), style="font-size: 14px; font-weight: 500; color: #1e293b;"),
                            style="margin-bottom: 16px;"
                        ),
                        Div(
                            Span("Причина изменения", style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;"),
                            Span(version.get("change_reason", "-") or "-", style="font-size: 14px; font-weight: 500; color: #1e293b;"),
                            style="margin-bottom: 16px;"
                        ),
                        Div(
                            Span("Итого по версии", style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;"),
                            Span(format_money(version.get("total_quote_currency"), currency), style="font-size: 18px; font-weight: 600; color: #059669;"),
                        ),
                    ),
                    style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),

                # Variables snapshot card
                Div(
                    Div(
                        icon("sliders", size=16, color="#64748b"),
                        Span("ПАРАМЕТРЫ РАСЧЁТА", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        *[
                            Div(
                                Span(label, style="font-size: 12px; color: #64748b;"),
                                Span(value, style="font-size: 14px; font-weight: 500; color: #1e293b;"),
                                style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9;"
                            )
                            for label, value in [
                                ("Наценка", f"{variables.get('markup', '-')}%"),
                                ("Инкотермс", variables.get('offer_incoterms', '-') or '-'),
                                ("Срок поставки", f"{variables.get('delivery_time', '-')} дн."),
                                ("Аванс от клиента", f"{variables.get('advance_from_client', '-')}%"),
                                ("Курс обмена", str(variables.get('exchange_rate', '-'))),
                            ]
                        ],
                    ),
                    style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),
                style="flex: 1; min-width: 280px;"
            ),

            # Right column - Products
            Div(
                Div(
                    Div(
                        icon("package", size=16, color="#64748b"),
                        Span("ТОВАРЫ", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;"),
                        Span(f"{len(products)}", style="background: #e0e7ff; color: #4f46e5; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"),
                        style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;"
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Товар", style="text-align: left; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Кол-во", style="text-align: center; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Цена/ед.", style="text-align: right; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Итого", style="text-align: right; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                    Th("Прибыль", style="text-align: right; padding: 12px 16px; background: #f8fafc; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0;"),
                                )
                            ),
                            Tbody(
                                *[
                                    Tr(
                                        Td(p.get("product_name", "-")[:40], style="padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(str(p.get("quantity", 1)), style="text-align: center; padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(format_money((results[i] if i < len(results) else {}).get("AJ16"), currency), style="text-align: right; padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(format_money((results[i] if i < len(results) else {}).get("AL16"), currency), style="text-align: right; padding: 12px 16px; font-size: 14px; font-weight: 500; color: #1e293b; border-bottom: 1px solid #f1f5f9;"),
                                        Td(format_money((results[i] if i < len(results) else {}).get("AF16"), currency), style="text-align: right; padding: 12px 16px; font-size: 14px; font-weight: 500; color: #059669; border-bottom: 1px solid #f1f5f9;"),
                                    )
                                    for i, p in enumerate(products)
                                ] if products else [
                                    Tr(Td("Нет товаров", colspan="5", style="padding: 24px; text-align: center; color: #94a3b8;"))
                                ]
                            ),
                            style="width: 100%; border-collapse: collapse;"
                        ),
                        style="overflow-x: auto;"
                    ),
                    style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
                ),
                style="flex: 2; min-width: 400px;"
            ),
            style="display: flex; gap: 24px; flex-wrap: wrap;"
        ),

        # Action buttons
        Div(
            btn_link("История версий", href=f"/quotes/{quote_id}/versions", variant="secondary", icon_name="history"),
            btn_link("К КП", href=f"/quotes/{quote_id}", variant="primary", icon_name="file-text"),
            style="margin-top: 24px; display: flex; gap: 12px;"
        ),

        session=session
    )


# ============================================================================
# EXPORT ROUTES
# ============================================================================

@rt("/quotes/{quote_id}/export/specification")
def get(quote_id: str, session):
    """Export Specification PDF - uses contract-style template matching DOCX"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    try:
        # First, check if a specification exists for this quote
        from services.specification_service import get_specification_by_quote
        spec = get_specification_by_quote(quote_id, org_id)

        if spec:
            # Use new contract-style template (matches DOCX)
            from services.contract_spec_export import generate_contract_spec_pdf
            pdf_bytes, spec_number = generate_contract_spec_pdf(str(spec.id), org_id)
            safe_spec_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(spec_number))
            filename = f"Specification_{safe_spec_number}.pdf"
        else:
            # Fallback to old template if no specification exists yet
            data = fetch_export_data(quote_id, org_id)
            pdf_bytes = generate_specification_pdf(data)
            customer_name = data.customer.get('company_name') or data.customer.get('name') or ''
            filename = build_export_filename(
                doc_type="specification",
                customer_name=customer_name,
                quote_number=data.quote.get('quote_number', ''),
                ext="pdf"
            )

        # Return as file download
        from starlette.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate PDF: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )


@rt("/quotes/{quote_id}/export/invoice")
def get(quote_id: str, session):
    """Export Invoice PDF (Счет на оплату)"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    try:
        # Fetch all export data
        data = fetch_export_data(quote_id, user["org_id"])

        # Generate PDF
        pdf_bytes = generate_invoice_pdf(data)

        # Return as file download
        from starlette.responses import Response
        customer_name = data.customer.get('company_name') or data.customer.get('name') or ''
        filename = build_export_filename(
            doc_type="invoice",
            customer_name=customer_name,
            quote_number=data.quote.get('quote_number', ''),
            ext="pdf"
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate PDF: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )


@rt("/quotes/{quote_id}/export/validation")
def get(quote_id: str, session):
    """Export Validation Excel spreadsheet"""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]

    try:
        # Fetch all export data
        data = fetch_export_data(quote_id, user["org_id"])

        # Generate Excel
        excel_bytes = create_validation_excel(data)

        # Return as file download (XLSM with macros)
        from starlette.responses import Response
        filename = f"validation_{data.quote.get('quote_number', quote_id)}.xlsm"
        return Response(
            content=excel_bytes,
            media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        return page_layout("Export Error",
            Div(str(e), cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )
    except Exception as e:
        return page_layout("Export Error",
            Div(f"Failed to generate Excel: {str(e)}", cls="alert alert-error"),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )


# ============================================================================
# SETTINGS PAGE + /settings/telegram SHIM — [archived to legacy-fasthtml/settings_profile.py in Phase 6C-2B-4]
# Routes moved: /settings GET+POST, /settings/telegram GET+POST (301 shim to /telegram).
# Superseded by Next.js /settings.
# ============================================================================


def _format_transition_timestamp(dt_str: str) -> str:
    """Format ISO timestamp to DD.MM.YYYY HH:MM."""
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str[:16] if len(dt_str) >= 16 else dt_str


# ============================================================================
# PROCUREMENT WORKSPACE (Feature #33)
# ============================================================================

def workflow_status_badge(status_str: str):
    """
    Create a styled badge for workflow status.
    Uses status-badge-v2 CSS classes for consistent styling.
    """
    try:
        status = WorkflowStatus(status_str) if status_str else None
    except ValueError:
        status = None

    if status:
        name = STATUS_NAMES_SHORT.get(status, status_str)
        # Map workflow statuses to status-badge-v2 CSS variants
        variant_map = {
            WorkflowStatus.DRAFT: "neutral",
            WorkflowStatus.PENDING_PROCUREMENT: "pending",
            WorkflowStatus.PENDING_LOGISTICS: "info",
            WorkflowStatus.PENDING_CUSTOMS: "purple",
            WorkflowStatus.PENDING_SALES_REVIEW: "warning",
            WorkflowStatus.PENDING_QUOTE_CONTROL: "warning",
            WorkflowStatus.PENDING_APPROVAL: "pending",
            WorkflowStatus.APPROVED: "success",
            WorkflowStatus.SENT_TO_CLIENT: "info",
            WorkflowStatus.CLIENT_NEGOTIATION: "info",
            WorkflowStatus.PENDING_SPEC_CONTROL: "info",
            WorkflowStatus.PENDING_SIGNATURE: "purple",
            WorkflowStatus.DEAL: "success",
            WorkflowStatus.REJECTED: "error",
            WorkflowStatus.CANCELLED: "neutral",
        }
        variant = variant_map.get(status, "neutral")
        return Span(name, cls=f"status-badge-v2 status-badge-v2--{variant}")

    return Span(status_str or "—", cls="status-badge-v2 status-badge-v2--neutral")


def quote_header(quote: dict, workflow_status: str, customer_name: str = None):
    """
    Persistent header shown on all quote detail tabs.
    Shows IDN, status badge, customer name, and total sum in a compact single-line card.
    """
    idn = quote.get("idn_quote", "")
    client = customer_name or "—"
    total_amount = quote.get("total_amount")
    currency = quote.get("currency", "RUB")

    # Format total sum
    sum_display = None
    if total_amount and float(total_amount or 0) > 0:
        sum_display = format_money(total_amount, currency)

    return Div(
        # Single row: IDN + Status badge + Client + Sum
        Div(
            # IDN
            Span(f"КП {idn}" if idn else "КП",
                 style="font-size: 1.25rem; font-weight: 700; color: #1e293b; white-space: nowrap;"),
            # Status badge
            workflow_status_badge(workflow_status),
            # Separator
            Span("|", style="color: #d1d5db; font-size: 1.125rem; margin: 0 0.25rem;"),
            # Client name
            Span(client, style="font-size: 1rem; color: #475569; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px;"),
            # Sum (if available)
            Span("|", style="color: #d1d5db; font-size: 1.125rem; margin: 0 0.25rem;") if sum_display else None,
            Span(sum_display, style="font-size: 1rem; font-weight: 600; color: #059669; white-space: nowrap;") if sum_display else None,
            style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;"
        ),
        style="background: white; padding: 0.875rem 1.5rem; border-radius: 0.75rem; margin-bottom: 1rem; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.04);"
    )


def workflow_progress_bar(status_str: str):
    """
    Create a visual workflow progress bar showing the current stage of a quote.

    Feature #87: Прогресс-бар workflow на КП

    Shows workflow stages as a horizontal bar with steps:
    1. Черновик (draft)
    2. Закупки (procurement)
    3. Лог + Там (logistics + customs parallel)
    4. Продажи (sales review)
    5. Контроль (quote control)
    6. Согласование (approval)
    7. Клиент (sent/negotiation)
    8. Спецификация (spec control)
    9. Сделка (deal)

    For rejected/cancelled shows a different indicator.
    """
    try:
        status = WorkflowStatus(status_str) if status_str else None
    except ValueError:
        status = None

    if not status:
        return Div()

    # Handle final negative states separately
    if status == WorkflowStatus.REJECTED:
        return Div(
            Span(icon("x-circle", size=18), " Отклонено", style="color: #dc2626; font-weight: 600; display: inline-flex; align-items: center; gap: 0.5rem;"),
            style="padding: 0.75rem 1rem; background: #fef2f2; border-radius: 8px; border-left: 4px solid #dc2626; margin: 0.5rem 0;"
        )
    if status == WorkflowStatus.CANCELLED:
        return Div(
            Span(icon("ban", size=18), " Отменено", style="color: #57534e; font-weight: 600; display: inline-flex; align-items: center; gap: 0.5rem;"),
            style="padding: 0.75rem 1rem; background: #f5f5f4; border-radius: 8px; border-left: 4px solid #78716c; margin: 0.5rem 0;"
        )

    # Define workflow stages in order (main path)
    # Some stages are parallel (logistics + customs) - we show them as one combined step
    stages = [
        ("draft", "Черновик", [WorkflowStatus.DRAFT]),
        ("procurement", "Закупки", [WorkflowStatus.PENDING_PROCUREMENT]),
        ("logistics_customs", "Лог+Там", [WorkflowStatus.PENDING_LOGISTICS, WorkflowStatus.PENDING_CUSTOMS]),
        ("sales", "Продажи", [WorkflowStatus.PENDING_SALES_REVIEW]),
        ("control", "Контроль", [WorkflowStatus.PENDING_QUOTE_CONTROL]),
        ("approval", "Согласование", [WorkflowStatus.PENDING_APPROVAL]),
        ("approved", "Одобрено", [WorkflowStatus.APPROVED]),
        ("client", "Клиент", [WorkflowStatus.SENT_TO_CLIENT, WorkflowStatus.CLIENT_NEGOTIATION]),
        ("spec", "Спец-я", [WorkflowStatus.PENDING_SPEC_CONTROL, WorkflowStatus.PENDING_SIGNATURE]),
        ("deal", "Сделка", [WorkflowStatus.DEAL]),
    ]

    # Find current stage index
    current_stage_idx = -1
    for idx, (stage_id, name, statuses) in enumerate(stages):
        if status in statuses:
            current_stage_idx = idx
            break

    # Build progress bar
    steps = []
    for idx, (stage_id, name, statuses) in enumerate(stages):
        is_current = status in statuses
        is_completed = idx < current_stage_idx
        is_future = idx > current_stage_idx

        # Determine step styling
        if is_completed:
            # Completed step - green
            circle_style = "background: #22c55e; color: white; border: 2px solid #22c55e;"
            text_style = "color: #22c55e; font-weight: 500;"
            step_icon = "✓"
        elif is_current:
            # Current step - blue with pulse animation
            circle_style = "background: #3b82f6; color: white; border: 2px solid #3b82f6; animation: pulse 2s infinite;"
            text_style = "color: #3b82f6; font-weight: 600;"
            step_icon = str(idx + 1)
        else:
            # Future step - gray
            circle_style = "background: #e5e7eb; color: #9ca3af; border: 2px solid #e5e7eb;"
            text_style = "color: #9ca3af;"
            step_icon = str(idx + 1)

        # Connector line (not for first step)
        connector = None
        if idx > 0:
            line_color = "#22c55e" if is_completed or is_current else "#e5e7eb"
            connector = Div(
                style=f"flex: 1; height: 2px; background: {line_color}; margin: 0 -2px;"
            )

        step = Div(
            # Circle with number or checkmark
            Div(
                step_icon,
                style=f"width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; {circle_style}"
            ),
            # Label
            Div(name, style=f"font-size: 11px; margin-top: 4px; text-align: center; white-space: nowrap; {text_style}"),
            style="display: flex; flex-direction: column; align-items: center; min-width: 50px;"
        )

        if connector:
            steps.append(Div(connector, style="display: flex; align-items: center; flex: 1; padding-bottom: 20px;"))
        steps.append(step)

    # CSS for pulse animation
    pulse_animation = Style("""
        @keyframes pulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
            50% { transform: scale(1.05); box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
        }
    """)

    return Div(
        pulse_animation,
        Div(
            *steps,
            style="display: flex; align-items: flex-start; justify-content: space-between; width: 100%; padding: 0.5rem 0;"
        ),
        style="background: #f9fafb; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; overflow-x: auto;"
    )


def workflow_transition_history(quote_id: str, limit: int = 20, collapsed: bool = True):
    """
    Create a UI component showing the workflow transition history for a quote.

    Feature #88: Просмотр истории переходов

    Shows an audit log of all status changes with:
    - From/to status (with colored badges)
    - Who made the transition (actor)
    - When it happened
    - Any comments/reasons

    Args:
        quote_id: UUID of the quote
        limit: Max number of transitions to show (default 20)
        collapsed: If True, history is collapsed by default with toggle button

    Returns:
        FastHTML Div component with transition history
    """
    from datetime import datetime

    # Get transition history
    history = get_quote_transition_history(quote_id, limit=limit)

    if not history:
        if collapsed:
            return Div()  # Don't show anything if no history and collapsed mode
        return Div(
            H4(icon("history", size=18), " История переходов", style="margin: 0 0 0.5rem; display: flex; align-items: center; gap: 0.5rem;"),
            P("История переходов пуста", style="color: #666; font-size: 0.875rem;"),
            cls="card",
            style="background: #f9fafb;"
        )

    # Resolve actor names (FIO) from user_profiles
    actor_ids = list(set(r.get("actor_id") for r in history if r.get("actor_id")))
    actor_names = {}
    if actor_ids:
        try:
            supabase = get_supabase()
            profiles_result = supabase.table("user_profiles") \
                .select("user_id, full_name") \
                .in_("user_id", actor_ids) \
                .execute()
            for p in (profiles_result.data or []):
                actor_names[p["user_id"]] = p.get("full_name") or ""
        except Exception:
            pass
    for r in history:
        r["actor_name"] = actor_names.get(r.get("actor_id"), "")

    # Build transition rows
    def transition_row(record, is_first=False):
        from_status = record.get("from_status", "—")
        to_status = record.get("to_status", "—")
        from_name = record.get("from_status_name", from_status)
        to_name = record.get("to_status_name", to_status)
        comment = record.get("comment", "")
        actor_role = record.get("actor_role", "")
        created_at = _format_transition_timestamp(record.get("created_at"))

        # Get colors for status badges
        def get_badge_colors(status_str):
            try:
                status = WorkflowStatus(status_str) if status_str else None
            except ValueError:
                status = None

            color_map = {
                WorkflowStatus.DRAFT: ("#f3f4f6", "#1f2937"),
                WorkflowStatus.PENDING_PROCUREMENT: ("#fef3c7", "#92400e"),
                WorkflowStatus.PENDING_LOGISTICS: ("#dbeafe", "#1e40af"),
                WorkflowStatus.PENDING_CUSTOMS: ("#e9d5ff", "#6b21a8"),
                WorkflowStatus.PENDING_SALES_REVIEW: ("#ffedd5", "#9a3412"),
                WorkflowStatus.PENDING_QUOTE_CONTROL: ("#fce7f3", "#9d174d"),
                WorkflowStatus.PENDING_APPROVAL: ("#fef3c7", "#b45309"),
                WorkflowStatus.APPROVED: ("#dcfce7", "#166534"),
                WorkflowStatus.SENT_TO_CLIENT: ("#cffafe", "#0e7490"),
                WorkflowStatus.CLIENT_NEGOTIATION: ("#ccfbf1", "#115e59"),
                WorkflowStatus.PENDING_SPEC_CONTROL: ("#e0e7ff", "#3730a3"),
                WorkflowStatus.PENDING_SIGNATURE: ("#ede9fe", "#5b21b6"),
                WorkflowStatus.DEAL: ("#d1fae5", "#065f46"),
                WorkflowStatus.REJECTED: ("#fee2e2", "#991b1b"),
                WorkflowStatus.CANCELLED: ("#f5f5f4", "#57534e"),
            }
            if status:
                return color_map.get(status, ("#f3f4f6", "#1f2937"))
            return ("#f3f4f6", "#1f2937")

        from_bg, from_text = get_badge_colors(from_status)
        to_bg, to_text = get_badge_colors(to_status)

        role_display = ROLE_LABELS_RU.get(actor_role, actor_role) if actor_role else "—"

        return Div(
            # Timeline dot and line
            Div(
                # Dot
                Div(
                    style=f"width: 10px; height: 10px; border-radius: 50%; background: {'#3b82f6' if is_first else '#cbd5e1'}; margin-top: 5px;"
                ),
                # Line (except for last item)
                Div(style="width: 2px; flex: 1; background: #e5e7eb; margin-left: 4px;"),
                style="display: flex; flex-direction: column; align-items: center; margin-right: 12px;"
            ),
            # Content
            Div(
                # Header: timestamp and role
                Div(
                    Span(created_at, style="font-size: 0.75rem; color: #666;"),
                    Span(f" — {record.get('actor_name', '')}", style="font-size: 0.75rem; font-weight: 600; color: #1e293b;") if record.get("actor_name") else None,
                    Span(f" • {role_display}", style="font-size: 0.75rem; color: #9ca3af;") if role_display != "—" else None,
                    style="margin-bottom: 4px;"
                ),
                # Status transition
                Div(
                    Span(from_name, style=f"display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: {from_bg}; color: {from_text};"),
                    Span(" → ", style="margin: 0 6px; color: #9ca3af;"),
                    Span(to_name, style=f"display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: {to_bg}; color: {to_text};"),
                    style="margin-bottom: 4px;"
                ),
                # Comment if exists
                Div(
                    Span(f"💬 {comment}", style="font-size: 0.8rem; color: #4b5563; font-style: italic;"),
                    style="margin-top: 4px;"
                ) if comment else None,
                style="flex: 1; padding-bottom: 12px;"
            ),
            style="display: flex; align-items: stretch;"
        )

    # Build history list
    history_items = [transition_row(record, idx == 0) for idx, record in enumerate(history)]

    # Container ID for toggle functionality
    container_id = f"transition-history-{quote_id[:8]}"

    if collapsed:
        # Collapsible version with toggle button
        return Div(
            # Toggle button
            Div(
                btn(f"История переходов ({len(history)})", variant="secondary", icon_name="history", type="button", size="sm",
                    onclick=f"document.getElementById('{container_id}').classList.toggle('hidden');"),
                style="margin-bottom: 0.5rem;"
            ),
            # Hidden history container
            Div(
                *history_items,
                id=container_id,
                cls="hidden",  # Hidden by default
                style="padding: 0.75rem; background: #fafafa; border-radius: 8px; border: 1px solid #e5e7eb;"
            ),
            # CSS for hidden class
            Style("""
                .hidden { display: none; }
            """),
            style="margin: 0.5rem 0;"
        )
    else:
        # Always visible version
        return Div(
            H4(icon("history", size=18), " История переходов", style="margin: 0 0 0.75rem; display: flex; align-items: center; gap: 0.5rem;"),
            Div(
                *history_items,
                style="padding: 0.75rem; background: #fafafa; border-radius: 8px; border: 1px solid #e5e7eb;"
            ),
            cls="card",
            style="background: #f9fafb;"
        )




def quote_detail_tabs(quote_id: str, active_tab: str, user_roles: list, deal=None, chat_unread: int = 0, quote: dict = None, user_id: str = None):
    """
    Create role-based tab navigation for quote detail pages.

    Shows tabs based on user roles:
    - summary: all users with access to quote (read-only overview)
    - overview: all users with access to quote (editable sales workspace)
    - procurement: procurement, admin
    - logistics: logistics, head_of_logistics, admin
    - customs: customs, head_of_customs, admin
    - control: quote_controller, admin
    - finance_main, plan_fact, logistics_stages: only when deal exists

    Args:
        quote_id: UUID of the quote
        active_tab: Current active tab (summary, overview, procurement, logistics, customs, control, finance_main, plan_fact, logistics_stages)
        user_roles: List of user roles
        deal: Optional deal dict — finance tabs only appear when deal is not None

    Returns:
        Tab navigation component
    """
    # Define tabs with role requirements
    tabs_config = [
        {
            "id": "summary",
            "label": "Сводка",
            "icon": "file-text",
            "href": f"/quotes/{quote_id}?tab=summary",
            "roles": None,  # All users with quote access
        },
        {
            "id": "overview",
            "label": "Продажи",
            "icon": "shopping-bag",
            "href": f"/quotes/{quote_id}?tab=overview",
            "roles": None,  # All users with quote access
        },
        {
            "id": "procurement",
            "label": "Закупки",
            "icon": "shopping-cart",
            "href": f"/quotes/{quote_id}",
            "roles": ["procurement", "admin"],
        },
        {
            "id": "customs",
            "label": "Таможня",
            "icon": "shield-check",
            "href": f"/customs/{quote_id}",
            "roles": ["customs", "head_of_customs", "admin"],
        },
        {
            "id": "logistics",
            "label": "Логистика",
            "icon": "truck",
            "href": f"/logistics/{quote_id}",
            "roles": ["logistics", "head_of_logistics", "admin"],
        },
        {
            "id": "control",
            "label": "Контроль",
            "icon": "check-circle",
            "href": f"/quote-control/{quote_id}",
            "roles": ["quote_controller", "admin"],
        },
        {
            "id": "cost_analysis",
            "label": "Кост-анализ",
            "icon": "trending-up",
            "href": f"/quotes/{quote_id}/cost-analysis",
            "roles": ["finance", "top_manager", "admin", "quote_controller"],
        },
        {
            "id": "documents",
            "label": "Документы",
            "icon": "folder",
            "href": f"/quotes/{quote_id}/documents",
            "roles": None,  # All users with quote access
        },
        {
            "id": "chat",
            "label": f"Чат ({chat_unread})" if chat_unread > 0 else "Чат",
            "icon": "message-circle",
            "href": f"/quotes/{quote_id}/chat",
            "roles": None,  # All users with quote access
        },
    ]

    # Finance tabs — only shown when a deal exists for this quote
    if deal is not None:
        tabs_config.extend([
            {
                "id": "finance_main",
                "label": "Сделка",
                "icon": "briefcase",
                "href": f"/quotes/{quote_id}?tab=finance_main",
                "roles": ["finance", "admin", "top_manager"],
            },
            {
                "id": "plan_fact",
                "label": "План-факт",
                "icon": "clipboard",
                "href": f"/quotes/{quote_id}?tab=plan_fact",
                "roles": ["finance", "admin", "top_manager"],
            },
            {
                "id": "logistics_stages",
                "label": "Логистика (сделка)",
                "icon": "package",
                "href": f"/quotes/{quote_id}?tab=logistics_stages",
                "roles": ["finance", "logistics", "admin", "top_manager"],
            },
            {
                "id": "currency_invoices",
                "label": "Валютные инвойсы",
                "icon": "file-text",
                "href": f"/quotes/{quote_id}?tab=currency_invoices",
                "roles": ["admin", "currency_controller", "finance"],
            },
            {
                "id": "logistics_expenses",
                "label": "Расходы логистики",
                "icon": "dollar-sign",
                "href": f"/quotes/{quote_id}?tab=logistics_expenses",
                "roles": ["finance", "logistics", "admin", "top_manager"],
            },
        ])

    # Filter tabs based on user roles
    visible_tabs = []
    for tab in tabs_config:
        if tab["roles"] is None:
            visible_tabs.append(tab)
        elif any(r in user_roles for r in tab["roles"]):
            visible_tabs.append(tab)

    # Filter by assignment for non-admin users
    # Department heads and top_manager bypass assignment check for their department
    if quote and user_id and "admin" not in user_roles and "top_manager" not in user_roles:
        # Resolve procurement assignment via quote_items (single source of truth).
        # Lazy-computed so non-procurement tab lookups don't hit the DB.
        _procurement_assigned_cache: dict = {}

        def _user_has_procurement_item(qid: str, uid: str) -> bool:
            cached = _procurement_assigned_cache.get("has")
            if cached is not None:
                return cached
            try:
                result = get_supabase().table("quote_items") \
                    .select("id") \
                    .eq("quote_id", qid) \
                    .eq("assigned_procurement_user", uid) \
                    .limit(1) \
                    .execute()
                has = bool(result.data)
            except Exception:
                has = False
            _procurement_assigned_cache["has"] = has
            return has

        def is_assigned(tab_id):
            if tab_id == "procurement":
                if "head_of_procurement" in user_roles:
                    return True
                return _user_has_procurement_item(quote_id, user_id)
            elif tab_id == "logistics":
                if "head_of_logistics" in user_roles:
                    return True
                return quote.get("assigned_logistics_user") == user_id
            elif tab_id == "customs":
                if "head_of_customs" in user_roles:
                    return True
                return quote.get("assigned_customs_user") == user_id
            return True  # Other tabs not filtered by assignment

        visible_tabs = [t for t in visible_tabs if is_assigned(t["id"])]

    # Build tab elements
    tab_elements = []
    for tab in visible_tabs:
        is_active = tab["id"] == active_tab

        # Styling for active vs inactive
        if is_active:
            tab_style = """
                display: flex; align-items: center; gap: 0.5rem;
                padding: 0.75rem 1.25rem;
                background: #3b82f6; color: white;
                border-radius: 8px 8px 0 0;
                font-weight: 600; font-size: 0.9rem;
                text-decoration: none;
                border-bottom: 3px solid #1d4ed8;
            """
        else:
            tab_style = """
                display: flex; align-items: center; gap: 0.5rem;
                padding: 0.75rem 1.25rem;
                background: #f3f4f6; color: #4b5563;
                border-radius: 8px 8px 0 0;
                font-size: 0.9rem;
                text-decoration: none;
                transition: background-color 0.15s ease, color 0.15s ease;
            """

        tab_elements.append(
            A(
                icon(tab["icon"], size=18),
                Span(tab["label"]),
                href=tab["href"],
                style=tab_style,
                cls="quote-detail-tab" + (" active" if is_active else "")
            )
        )

    # Split tab elements into core and finance groups
    FINANCE_TAB_IDS = {"finance_main", "plan_fact", "logistics_stages", "currency_invoices"}
    core_tab_elements = []
    finance_tab_elements = []
    for tab, elem in zip(visible_tabs, tab_elements):
        if tab["id"] in FINANCE_TAB_IDS:
            finance_tab_elements.append(elem)
        else:
            core_tab_elements.append(elem)

    row_style = "display: flex; gap: 0.25rem; border-bottom: 1px solid #e5e7eb;"

    # Return tabs container with hover style
    if finance_tab_elements:
        return Div(
            Style("""
                .quote-detail-tab:hover:not(.active) {
                    background: #e5e7eb !important;
                    color: #1f2937 !important;
                }
            """),
            Div(*core_tab_elements, style=row_style),
            Div(
                Span("Финансы:", style="display: flex; align-items: center; padding: 0.5rem 0.75rem; color: #6b7280; font-size: 0.8rem; font-weight: 500;"),
                *finance_tab_elements,
                style=row_style + " margin-bottom: 1.5rem;"
            ),
        )
    else:
        return Div(
            Style("""
                .quote-detail-tab:hover:not(.active) {
                    background: #e5e7eb !important;
                    color: #1f2937 !important;
                }
            """),
            Div(*core_tab_elements, style=row_style + " margin-bottom: 1.5rem;")
        )

# ============================================================================
# USER PROFILE PAGE — [archived to legacy-fasthtml/settings_profile.py in Phase 6C-2B-4]
# Routes moved: /profile GET+POST, /profile/{user_id} POST (admin save).
# Superseded by Next.js /profile.
# ============================================================================

@rt("/procurement")
def get(session, status_filter: str = None):
    """
    Redirect to unified dashboard procurement tab.
    Old URL preserved for backwards compatibility.
    """
    url = "/dashboard?tab=procurement"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


# ============================================================================
# SALES CHECKLIST DISPLAY HELPER
# ============================================================================

def _build_sales_checklist_card(sales_checklist):
    """Build a yellow info card displaying sales checklist answers for procurement."""
    if not sales_checklist:
        return None

    # Handle both dict and string (JSONB comes as dict from Supabase)
    if isinstance(sales_checklist, str):
        try:
            sales_checklist = json.loads(sales_checklist)
        except (json.JSONDecodeError, TypeError):
            return None

    def _yes_no(val):
        return "Да" if val else "Нет"

    def _check_icon(val):
        if val:
            return icon("check-circle", size=14, color="#059669")
        return icon("circle", size=14, color="#94a3b8")

    return Div(
        Div(
            icon("clipboard-list", size=18, color="#92400e"),
            Span(" Информация от отдела продаж", style="font-weight: 600; font-size: 1rem; margin-left: 6px; color: #92400e;"),
            style="display: flex; align-items: center; margin-bottom: 12px;"
        ),
        Div(
            Div(
                _check_icon(sales_checklist.get("is_estimate")),
                Span(f" Проценка: {_yes_no(sales_checklist.get('is_estimate'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            Div(
                _check_icon(sales_checklist.get("is_tender")),
                Span(f" Тендер: {_yes_no(sales_checklist.get('is_tender'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            Div(
                _check_icon(sales_checklist.get("direct_request")),
                Span(f" Прямой запрос от клиента: {_yes_no(sales_checklist.get('direct_request'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            Div(
                _check_icon(sales_checklist.get("trading_org_request")),
                Span(f" Запрос через торгующую организацию: {_yes_no(sales_checklist.get('trading_org_request'))}", style="margin-left: 4px;"),
                style="display: flex; align-items: center; padding: 4px 0;"
            ),
            style="margin-bottom: 12px; font-size: 0.875rem; color: #374151;"
        ),
        Div(
            Span("Описание оборудования:", style="font-weight: 600; font-size: 0.875rem; color: #92400e; display: block; margin-bottom: 4px;"),
            P(sales_checklist.get("equipment_description", "---"),
              style="margin: 0; padding: 8px 12px; background: rgba(255,255,255,0.5); border-radius: 6px; font-size: 0.875rem; white-space: pre-wrap; line-height: 1.5;"),
        ),
        cls="card",
        style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-left: 4px solid #f59e0b; margin-bottom: 1rem; padding: 1rem; border-radius: 10px;"
    )




# ============================================================================
# DOCUMENT API ENDPOINTS
# ============================================================================
# Phase 6B-9: /api/documents/{document_id}/download (GET) and
# /api/documents/{document_id} (DELETE) moved to api/documents.py + routed via
# api/routers/documents.py on the FastAPI sub-app mounted at /api.






# ============================================================================
# PROCUREMENT - RETURN TO QUOTE CONTROL (Feature: multi-department return)
# ============================================================================

@rt("/procurement/{quote_id}/return-to-control")
def get(quote_id: str, session):
    """
    Form for procurement to return a revised quote back to quote control.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("КП не существует или у вас нет доступа."),
            A("← К задачам", href="/tasks"),
            session=session
        )

    quote = quote_result.data
    workflow_status = quote.get("workflow_status", "draft")
    revision_comment = quote.get("revision_comment", "")
    idn_quote = quote.get("idn_quote", f"#{quote_id[:8]}")
    customer_name = (quote.get("customers") or {}).get("name", "—") if quote.get("customers") else "—"

    # Can only return from pending_procurement status
    if workflow_status != "pending_procurement":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(workflow_status), workflow_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Design system styles
    header_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 24px;
    """

    form_card_style = """
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 24px;
    """

    section_header_style = """
        font-size: 11px;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    """

    comment_box_style = """
        background: #fef3c7;
        border-left: 3px solid #f59e0b;
        padding: 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 24px;
    """

    textarea_style = """
        width: 100%;
        min-height: 120px;
        padding: 12px 14px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-size: 14px;
        background: #f8fafc;
        font-family: inherit;
        resize: vertical;
        box-sizing: border-box;
    """

    return page_layout(f"Вернуть на проверку - {idn_quote}",
        # Header card
        Div(
            Div(
                A(icon("arrow-left", size=16), f" Назад к закупкам", href=f"/quotes/{quote_id}",
                  style="color: #64748b; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;"),
                style="margin-bottom: 12px;"
            ),
            H1("Вернуть КП на проверку",
               style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #1e293b;"),
            Div(
                icon("file-text", size=14, style="color: #64748b;"),
                Span(f"КП: {idn_quote}", style="color: #475569; font-weight: 500;"),
                Span(" • ", style="color: #cbd5e1;"),
                Span(f"Клиент: {customer_name}", style="color: #64748b;"),
                style="display: flex; align-items: center; gap: 8px; font-size: 14px;"
            ),
            style=header_style
        ),

        # Original comment (if present)
        Div(
            Div(icon("message-circle", size=14), " Исходный комментарий контроллёра", style=section_header_style),
            P(revision_comment if revision_comment else "— нет комментария —",
              style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.5;"),
            style=comment_box_style
        ) if revision_comment else None,

        # Form
        Form(
            Div(
                Div(icon("edit-3", size=14), " Комментарий об исправлениях *", style=section_header_style),
                P("Опишите, какие исправления были внесены:",
                  style="color: #64748b; font-size: 13px; margin: 0 0 12px 0;"),
                Textarea(
                    name="comment",
                    placeholder="Исправлена цена на позицию X...\nОбновлены данные поставщика...\nИзменены сроки производства...",
                    required=True,
                    style=textarea_style
                ),
                style="margin-bottom: 24px;"
            ),
            Div(
                Button(icon("check", size=14), " Вернуть на проверку", type="submit",
                       style="padding: 10px 20px; background: #22c55e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px;"),
                A(icon("x", size=14), " Отмена", href=f"/quotes/{quote_id}",
                  style="padding: 10px 20px; background: #f1f5f9; color: #475569; border: none; border-radius: 6px; font-size: 14px; text-decoration: none; display: flex; align-items: center; gap: 6px;"),
                style="display: flex; gap: 12px;"
            ),
            action=f"/procurement/{quote_id}/return-to-control",
            method="post",
            style=form_card_style
        ),
        session=session
    )


@rt("/procurement/{quote_id}/return-to-control")
def post(quote_id: str, session, comment: str = ""):
    """
    Handle return to quote control from procurement.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return RedirectResponse("/unauthorized", status_code=303)

    if not comment or not comment.strip():
        return page_layout("Ошибка",
            H1("Ошибка"),
            P("Необходимо указать комментарий об исправлениях."),
            A("← Вернуться", href=f"/procurement/{quote_id}/return-to-control"),
            session=session
        )

    supabase = get_supabase()

    # Verify quote exists
    quote_result = supabase.table("quotes") \
        .select("workflow_status") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            A("← К задачам", href="/tasks"),
            session=session
        )

    current_status = quote_result.data[0].get("workflow_status", "draft")

    if current_status != "pending_procurement":
        return page_layout("Возврат невозможен",
            H1("Возврат невозможен"),
            P(f"КП находится в статусе «{STATUS_NAMES.get(WorkflowStatus(current_status), current_status)}»."),
            A("← Назад", href=f"/quotes/{quote_id}"),
            session=session
        )

    # Perform workflow transition
    user_roles = get_user_roles_from_session(session)
    result = transition_quote_status(
        quote_id=quote_id,
        to_status=WorkflowStatus.PENDING_QUOTE_CONTROL,
        actor_id=user_id,
        actor_roles=user_roles,
        comment=f"Исправления от закупок: {comment.strip()}"
    )

    if result.success:
        # Clear revision fields after returning
        supabase.table("quotes").update({
            "revision_department": None,
            "revision_comment": None,
            "revision_returned_at": None
        }).eq("id", quote_id).execute()

        return page_layout("Успешно",
            H1(icon("check", size=28), " КП возвращено на проверку"),
            P("КП отправлено контроллёру КП для повторной проверки."),
            btn_link("К задачам", href="/tasks", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1("Ошибка"),
            P(f"Не удалось вернуть КП: {result.error_message}"),
            A("← Назад", href=f"/procurement/{quote_id}/return-to-control"),
            session=session
        )


@rt("/procurement/{quote_id}/export")
def get(quote_id: str, session):
    """
    Export procurement items to Excel for sending to suppliers.

    Feature #36: Скачивание списка для оценки
    - Exports items belonging to user's assigned brands
    - Creates Excel file with columns for supplier to fill in
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has procurement role
    if not user_has_any_role(session, ["procurement", "admin", "head_of_procurement"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get the quote with customer info
    quote_result = supabase.table("quotes") \
        .select("*, customers(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .single() \
        .is_("deleted_at", None) \
        .execute()

    quote = quote_result.data
    if not quote:
        return RedirectResponse("/procurement", status_code=303)

    customer_name = (quote.get("customers") or {}).get("name", "")

    # Check if user is admin or head_of_procurement - bypass brand filtering
    is_admin = user_has_any_role(session, ["admin", "head_of_procurement"])

    # Get user's assigned brands (admin sees all)
    my_brands = get_assigned_brands(user_id, org_id) if not is_admin else []
    my_brands_lower = [b.lower() for b in my_brands]

    # Get all items for this quote
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("created_at") \
        .execute()

    all_items = items_result.data or []

    # Filter items for my brands (handle None brand values) - admin sees all
    if is_admin:
        my_items = all_items
    else:
        my_items = [item for item in all_items
                    if (item.get("brand") or "").lower() in my_brands_lower]

    if not my_items:
        # No items to export, redirect back with message
        return RedirectResponse(f"/quotes/{quote_id}", status_code=303)

    # Generate Excel
    excel_bytes = create_procurement_excel(
        quote=quote,
        items=my_items,
        brands=my_brands,
        customer_name=customer_name
    )

    # Return as file download
    from starlette.responses import Response
    filename = build_export_filename(
        doc_type="procurement",
        customer_name=customer_name,
        quote_number=quote.get("idn_quote", ''),
        ext="xlsx"
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )






# ============================================================================
# QUOTE CONTROL - CALCULATION COLUMNS DEFINITION
# ============================================================================

# All available calculation columns with their metadata
CALC_COLUMNS = {
    # Purchase group
    "N16": {"name": "Цена закупки/ед", "group": "Закупка", "format": "money"},
    "P16": {"name": "После скидки", "group": "Закупка", "format": "money"},
    "R16": {"name": "Цена/ед в вал. КП", "group": "Закупка", "format": "money"},
    "S16": {"name": "Сумма закупки", "group": "Закупка", "format": "money"},
    # Logistics group
    "T16": {"name": "Логистика 1", "group": "Логистика", "format": "money"},
    "U16": {"name": "Логистика 2", "group": "Логистика", "format": "money"},
    "V16": {"name": "Логистика всего", "group": "Логистика", "format": "money"},
    # Customs group
    "Y16": {"name": "Пошлина", "group": "Таможня", "format": "money"},
    "Z16": {"name": "Акциз", "group": "Таможня", "format": "money"},
    # COGS group
    "AA16": {"name": "Себест./ед", "group": "Себестоимость", "format": "money"},
    "AB16": {"name": "Себестоимость", "group": "Себестоимость", "format": "money"},
    # Sales group
    "AD16": {"name": "Цена без фин.", "group": "Продажа", "format": "money"},
    "AE16": {"name": "Сумма без фин.", "group": "Продажа", "format": "money"},
    "AF16": {"name": "Прибыль", "group": "Продажа", "format": "money", "highlight": True},
    "AG16": {"name": "ЛПР", "group": "Продажа", "format": "money"},
    "AJ16": {"name": "Цена/ед б/НДС", "group": "Продажа", "format": "money"},
    "AK16": {"name": "Сумма б/НДС", "group": "Продажа", "format": "money"},
    "AL16": {"name": "Сумма с НДС", "group": "Продажа", "format": "money", "bold": True},
    # VAT group
    "AP16": {"name": "НДС к уплате", "group": "НДС", "format": "money"},
    # Finance group
    "BA16": {"name": "Финансирование", "group": "Финансы", "format": "money"},
    "BB16": {"name": "Кредит", "group": "Финансы", "format": "money"},
}

# Column presets
CALC_PRESET_BASIC = ["N16", "S16", "V16", "AB16", "AF16", "AK16", "AL16"]
CALC_PRESET_FULL = ["N16", "P16", "S16", "T16", "U16", "V16", "Y16", "AA16", "AB16", "AD16", "AF16", "AG16", "AJ16", "AK16", "AL16", "AP16", "BA16", "BB16"]

# Mapping from phase_results columns to summary columns
CALC_SUMMARY_MAP = {
    "S16": "calc_s16_total_purchase_price",
    "V16": "calc_v16_total_logistics",
    "AB16": "calc_ab16_cogs_total",
    "AF16": "calc_af16_profit_margin",  # Note: this is actually markup %, not total profit
    "AK16": "calc_ak16_final_price_total",
    "AL16": "calc_al16_total_with_vat",
    "Y16": "calc_y16_customs_duty",
    "AP16": "calc_ap16_net_vat_payable",
    "AG16": "calc_ag16_dm_fee",
}

# MIN_MARKUP_RULES and the 5 Janna checklist helpers moved to
# legacy-fasthtml/control_flow.py in Phase 6C-2B Mega-B along with their
# only consumer, /quote-control/{quote_id}.


def get_user_calc_columns(user_id: str, supabase) -> list:
    """Get user's custom column selection from user_settings."""
    try:
        result = supabase.table("user_settings") \
            .select("setting_value") \
            .eq("user_id", user_id) \
            .eq("setting_key", "quote_control_columns") \
            .execute()
        if result.data:
            return (result.data[0].get("setting_value") or {}).get("columns", CALC_PRESET_BASIC)
    except Exception:
        pass
    return CALC_PRESET_BASIC


def save_user_calc_columns(user_id: str, columns: list, supabase) -> bool:
    """Save user's custom column selection to user_settings."""
    try:
        # Upsert the setting
        supabase.table("user_settings").upsert({
            "user_id": user_id,
            "setting_key": "quote_control_columns",
            "setting_value": {"columns": columns, "preset": "custom"},
            "updated_at": "now()"
        }, on_conflict="user_id,setting_key").execute()
        return True
    except Exception:
        return False


def build_calc_table(items_data: list, summary_data: dict, columns: list, currency: str = "RUB"):
    """
    Build calculation details table with selected columns.

    Args:
        items_data: List of dicts with item info and phase_results
        summary_data: Dict with aggregated totals from quote_calculation_summaries
        columns: List of column codes to display (e.g., ["N16", "S16", "V16"])
        currency: Currency code for display

    Returns:
        FastHTML Table element
    """
    # Build header row
    header_cells = [
        Th("Товар", style="text-align: left; white-space: nowrap; position: sticky; left: 0; background: white; z-index: 1;"),
        Th("Кол-во", style="text-align: right; white-space: nowrap;"),
    ]
    for col in columns:
        col_info = CALC_COLUMNS.get(col, {"name": col, "group": ""})
        header_cells.append(
            Th(col_info["name"],
               style="text-align: right; white-space: nowrap;",
               title=f"{col} - {col_info.get('group', '')}")
        )
    header_cells.append(Th("Наценка %", style="text-align: right; white-space: nowrap;"))

    # Build data rows
    data_rows = []
    for item in items_data:
        phase = item.get("phase_results", {})
        row_cells = [
            Td(
                (item.get("product_name") or "—")[:35],
                style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; position: sticky; left: 0; background: white;",
                title=item.get("product_name", "")
            ),
            Td(str(item.get("quantity", "—")), style="text-align: right;"),
        ]

        for col in columns:
            col_info = CALC_COLUMNS.get(col, {})
            value = float(phase.get(col, 0) or 0)
            style = "text-align: right;"
            if col_info.get("highlight"):
                style += " color: #22c55e;"
            if col_info.get("bold"):
                style += " font-weight: 500;"
            row_cells.append(Td(format_money(value, currency), style=style))

        # Margin % calculation
        cogs = float(phase.get("AB16", 0) or 0)
        profit = float(phase.get("AF16", 0) or 0)
        margin_pct = (profit / cogs * 100) if cogs > 0 else 0
        row_cells.append(Td(f"{margin_pct:.1f}%", style="text-align: right; color: #22c55e;"))

        data_rows.append(Tr(*row_cells))

    # Build footer row with totals
    footer_cells = [
        Td(Strong("ИТОГО"), style="position: sticky; left: 0; background: #f9fafb;"),
        Td("", style="background: #f9fafb;"),
    ]
    for col in columns:
        summary_col = CALC_SUMMARY_MAP.get(col)
        if summary_col and summary_data:
            value = float(summary_data.get(summary_col, 0) or 0)
            footer_cells.append(Td(Strong(format_money(value, currency)), style="text-align: right; background: #f9fafb;"))
        else:
            footer_cells.append(Td("—", style="text-align: right; background: #f9fafb;"))
    # Average margin
    avg_margin = float(summary_data.get("calc_af16_profit_margin", 0) or 0) if summary_data else 0
    footer_cells.append(Td(Strong(f"{avg_margin:.1f}%"), style="text-align: right; color: #22c55e; background: #f9fafb;"))

    return Table(
        Thead(Tr(*header_cells)),
        Tbody(*data_rows),
        Tfoot(Tr(*footer_cells)),
        style="width: 100%; font-size: 0.875rem; border-collapse: collapse;"
    )


# ============================================================================
# COST ANALYSIS (КА) DASHBOARD — P&L Waterfall View
# ============================================================================

@app.get("/quotes/{quote_id}/cost-analysis")
def get_cost_analysis(session, quote_id: str):
    """
    Cost Analysis (КА) Dashboard — read-only P&L waterfall for a quote.

    Shows aggregated cost breakdown from existing calculation results:
    - Revenue (no VAT / with VAT)
    - Purchase cost, Logistics (with W2-W10 breakdown), Customs, Excise
    - Gross Profit = Revenue - Direct Costs
    - Financial expenses: DM fee, Forex reserve, Fin agent fee, Financing
    - Net Profit = Gross Profit - Financial Expenses
    - Markup % and Sale/Purchase ratio

    Visible to: finance, top_manager, admin, quote_controller roles.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]
    user_roles = user.get("roles", [])

    # Role check: only finance, top_manager, admin, quote_controller
    allowed_roles = ["finance", "top_manager", "admin", "quote_controller"]
    if not user_has_any_role(session, allowed_roles):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Fetch quote with org isolation check (organization_id must match)
    quote_result = supabase.table("quotes") \
        .select("id, organization_id, idn_quote, title, currency, seller_company_id, delivery_terms, delivery_days, payment_terms, workflow_status, total_amount, customers(name)") \
        .eq("id", quote_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            P("Запрошенное КП не существует."),
            A("← Назад", href="/quotes"),
            session=session
        )

    quote = quote_result.data[0]
    customer_name = (quote.get("customers") or {}).get("name", "—")

    # Org isolation: check organization_id matches user's org_id
    if quote.get("organization_id") != org_id:
        return Redirect("/quotes", status_code=303)

    # Build tab navigation with cost_analysis as active tab
    tabs = quote_detail_tabs(quote_id, "cost_analysis", user_roles, quote=quote, user_id=user_id)

    # Fetch calculation results (phase_results per item)
    calc_results_resp = supabase.table("quote_calculation_results") \
        .select("quote_item_id, phase_results") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_results = calc_results_resp.data if calc_results_resp.data else []

    # Fetch calculation variables (W2-W10 logistics breakdown)
    calc_vars_resp = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_vars = calc_vars_resp.data[0]["variables"] if calc_vars_resp.data else {}

    # If no calculation results exist, show "not calculated" message
    if not calc_results:
        return page_layout(
            f"Кост-анализ — {quote.get('idn_quote', '')}",
            quote_header(quote, quote.get("workflow_status", "draft"), customer_name),
            tabs,
            Div(
                Div(
                    H2("Кост-анализ", style="margin: 0 0 0.5rem 0; font-size: 1.25rem;"),
                    P("Расчёт ещё не выполнен. Вернитесь на вкладку Продажи и нажмите «Рассчитать».",
                      style="color: #6b7280; margin: 0;"),
                    style="padding: 2rem; text-align: center; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb;"
                ),
                style="padding: 1.5rem;"
            ),
            session=session
        )

    # ── Aggregate phase_results across all items ──
    # Keys: AK16=revenue_no_vat, AL16=revenue_with_vat, S16=purchase,
    #        V16=logistics, Y16=customs, Z16=excise,
    #        AG16=dm_fee, AH16=forex_reserve, AI16=financial_agent_fee, BB16=financing
    aggregate_keys = ["AK16", "AL16", "S16", "V16", "Y16", "Z16", "AG16", "AH16", "AI16", "BB16"]
    totals = {k: 0.0 for k in aggregate_keys}

    for result in calc_results:
        pr = result.get("phase_results", {})
        for key in aggregate_keys:
            totals[key] += float(pr.get(key, 0) or 0)

    revenue_no_vat = totals["AK16"]
    revenue_with_vat = totals["AL16"]
    total_purchase = totals["S16"]
    total_logistics = totals["V16"]
    total_customs = totals["Y16"]
    total_excise = totals["Z16"]
    total_dm_fee = totals["AG16"]
    total_forex = totals["AH16"]
    total_fin_agent = totals["AI16"]
    total_financing = totals["BB16"]

    # ── Derived P&L calculations ──
    direct_costs = total_purchase + total_logistics + total_customs + total_excise
    gross_profit = revenue_no_vat - direct_costs

    financial_expenses = total_dm_fee + total_forex + total_fin_agent + total_financing
    net_profit = gross_profit - financial_expenses

    # Markup % = (revenue / purchase - 1) * 100, with zero-division protection
    if total_purchase > 0:
        markup_pct = (revenue_no_vat / total_purchase - 1) * 100
        sale_purchase_ratio = revenue_no_vat / total_purchase
    else:
        markup_pct = 0.0
        sale_purchase_ratio = 0.0

    # Revenue percentage helper (avoid division by zero)
    def pct_of_revenue(value):
        if revenue_no_vat > 0:
            return (value / revenue_no_vat) * 100
        return 0.0

    # ── Extract W2-W10 logistics breakdown from variables ──
    logistics_supplier_hub = float(calc_vars.get("logistics_supplier_hub", 0) or 0)
    logistics_hub_customs = float(calc_vars.get("logistics_hub_customs", 0) or 0)
    logistics_customs_client = float(calc_vars.get("logistics_customs_client", 0) or 0)
    brokerage_hub = float(calc_vars.get("brokerage_hub", 0) or 0)
    brokerage_customs = float(calc_vars.get("brokerage_customs", 0) or 0)
    warehousing_at_customs = float(calc_vars.get("warehousing_at_customs", 0) or 0)
    customs_documentation = float(calc_vars.get("customs_documentation", 0) or 0)
    brokerage_extra = float(calc_vars.get("brokerage_extra", 0) or 0)
    insurance = float(calc_vars.get("rate_insurance", 0) or 0)

    # ── Format helper ──
    def fmt(value):
        return f"{value:,.2f}"

    # ── Card styles ──
    card_style = "background: white; border-radius: 8px; padding: 1rem 1.25rem; border: 1px solid #e5e7eb; text-align: center;"
    card_label_style = "font-size: 0.8rem; color: #6b7280; margin: 0 0 0.25rem 0;"
    card_value_style = "font-size: 1.25rem; font-weight: 700; margin: 0; color: #111827;"

    # ── Build P&L waterfall table ──
    row_style = "border-bottom: 1px solid #f3f4f6;"
    subtotal_style = "border-bottom: 2px solid #e5e7eb; background: #f9fafb; font-weight: 600;"
    indent_style = "padding-left: 2rem; color: #6b7280; font-size: 0.85rem;"

    waterfall_rows = [
        # Revenue section
        Tr(
            Td(Strong("Выручка (без НДС)"), style="padding: 0.5rem 0.75rem;"),
            Td(Strong(fmt(revenue_no_vat)), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td("100.0%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=subtotal_style
        ),
        # Purchase cost
        Tr(
            Td("Сумма закупки", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_purchase), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_purchase):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # Logistics total with breakdown
        Tr(
            Td("Логистика (итого)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_logistics), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_logistics):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # W2-W10 breakdown sub-rows
        Tr(Td("Логистика до СВХ (W2)", style=indent_style), Td(fmt(logistics_supplier_hub), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("ТР — РФ (W3)", style=indent_style), Td(fmt(logistics_hub_customs), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("РФ — КУДА (W4)", style=indent_style), Td(fmt(logistics_customs_client), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Брокерские до РФ (W5)", style=indent_style), Td(fmt(brokerage_hub), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Брокерские в РФ (W6)", style=indent_style), Td(fmt(brokerage_customs), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Порт и СВХ в РФ (W7)", style=indent_style), Td(fmt(warehousing_at_customs), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Сертификация (W8)", style=indent_style), Td(fmt(customs_documentation), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Доп. расход (W9)", style=indent_style), Td(fmt(brokerage_extra), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        Tr(Td("Страховка (W10)", style=indent_style), Td(fmt(insurance), style="text-align: right; padding: 0.25rem 0.75rem; color: #6b7280;"), Td("", style="padding: 0.25rem;"), style="border-bottom: 1px solid #f9fafb;"),
        # Customs duty
        Tr(
            Td("Пошлина", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_customs), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_customs):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # Excise
        Tr(
            Td("Акциз", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_excise), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_excise):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # === Gross Profit subtotal ===
        Tr(
            Td(Strong("= Валовая прибыль (Gross Profit)"), style="padding: 0.5rem 0.75rem;"),
            Td(Strong(fmt(gross_profit)), style=f"text-align: right; padding: 0.5rem 0.75rem; color: {'#16a34a' if gross_profit >= 0 else '#dc2626'};"),
            Td(Strong(f"{pct_of_revenue(gross_profit):.1f}%"), style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=subtotal_style
        ),
        # Financial expenses section
        Tr(
            Td("Вознаграждение ЛПР (DM fee)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_dm_fee), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_dm_fee):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        Tr(
            Td("Резерв курсовой разницы (Forex)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_forex), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_forex):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        Tr(
            Td("Комиссия фин. агента (Financial agent fee)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_fin_agent), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_fin_agent):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        Tr(
            Td("Стоимость финансирования (Financing)", style="padding: 0.5rem 0.75rem;"),
            Td(fmt(total_financing), style="text-align: right; padding: 0.5rem 0.75rem;"),
            Td(f"{pct_of_revenue(total_financing):.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=row_style
        ),
        # === Net Profit subtotal ===
        Tr(
            Td(Strong("= Чистая прибыль (Net Profit)"), style="padding: 0.5rem 0.75rem;"),
            Td(Strong(fmt(net_profit)), style=f"text-align: right; padding: 0.5rem 0.75rem; color: {'#16a34a' if net_profit >= 0 else '#dc2626'};"),
            Td(Strong(f"{pct_of_revenue(net_profit):.1f}%"), style="text-align: right; padding: 0.5rem 0.75rem; color: #6b7280;"),
            style=subtotal_style
        ),
        # Markup
        Tr(
            Td("Наценка (Markup %)", style="padding: 0.5rem 0.75rem;"),
            Td(f"{markup_pct:.1f}%", style="text-align: right; padding: 0.5rem 0.75rem; font-weight: 600;"),
            Td("", style="padding: 0.5rem;"),
            style=row_style
        ),
    ]

    # ── Assemble page ──
    currency = quote.get("currency", "USD")

    content = Div(
        # Top-line metric cards
        Div(
            Div(
                P("Выручка (без НДС)", style=card_label_style),
                P(f"{fmt(revenue_no_vat)} {currency}", style=card_value_style),
                style=card_style
            ),
            Div(
                P("Выручка (с НДС)", style=card_label_style),
                P(f"{fmt(revenue_with_vat)} {currency}", style=card_value_style),
                style=card_style
            ),
            Div(
                P("Чистая прибыль", style=card_label_style),
                P(f"{fmt(net_profit)} {currency}", style=f"{card_value_style} color: {'#16a34a' if net_profit >= 0 else '#dc2626'};"),
                style=card_style
            ),
            Div(
                P("Наценка (выр. ÷ закуп − 1)", style=card_label_style),
                P(f"{markup_pct:.1f}%", style=card_value_style),
                style=card_style
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;"
        ),
        # P&L Waterfall table
        Div(
            H3("P&L Waterfall — Кост-анализ", style="margin: 0 0 1rem 0; font-size: 1.1rem; color: #374151;"),
            Table(
                Thead(
                    Tr(
                        Th("Статья", style="text-align: left; padding: 0.5rem 0.75rem; background: #f9fafb; border-bottom: 2px solid #e5e7eb;"),
                        Th(f"Сумма ({currency})", style="text-align: right; padding: 0.5rem 0.75rem; background: #f9fafb; border-bottom: 2px solid #e5e7eb;"),
                        Th("% от выручки", style="text-align: right; padding: 0.5rem 0.75rem; background: #f9fafb; border-bottom: 2px solid #e5e7eb;"),
                    )
                ),
                Tbody(*waterfall_rows),
                style="width: 100%; border-collapse: collapse; font-size: 0.875rem;"
            ),
            style="background: white; border-radius: 8px; padding: 1.25rem; border: 1px solid #e5e7eb;"
        ),
        style="padding: 1.5rem;"
    )

    return page_layout(
        f"Кост-анализ — {quote.get('idn_quote', '')}",
        quote_header(quote, quote.get("workflow_status", "draft"), customer_name),
        tabs,
        content,
        session=session
    )


@app.get("/quotes/{quote_id}/cost-analysis-json")
def get_cost_analysis_json(session, quote_id: str):
    """API endpoint: Cost analysis raw data as JSON (reserved for future use)."""
    redirect = require_login(session)
    if redirect:
        return redirect
    return JSONResponse({"status": "not_implemented"}, status_code=501)


# ============================================================================
# ADMIN: USER MANAGEMENT
# Feature #84: Страница /admin/users
# ============================================================================

@rt("/admin/users")
def get_admin_users_redirect(session):
    """Redirect old /admin/users to new /admin"""
    return RedirectResponse("/admin", status_code=303)


@rt("/admin")
def get(session):
    """Admin page - user management.

    Feature #84: Страница /admin
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get all organization members with their roles and Telegram status
    members_result = supabase.table("organization_members").select(
        "user_id, status, created_at"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    members = members_result.data if members_result.data else []

    # Get all available roles for this organization (system roles + org-specific roles)
    from services.role_service import get_all_roles
    all_roles = get_all_roles(organization_id=org_id)

    # Build user data with roles
    users_data = []
    for member in members:
        member_user_id = member["user_id"]

        # Get user roles (DB uses 'slug', we call it 'code' in UI)
        user_roles_result = supabase.table("user_roles").select(
            "id, role_id, roles(slug, name)"
        ).eq("user_id", member_user_id).eq("organization_id", org_id).execute()

        member_roles = user_roles_result.data if user_roles_result.data else []
        role_codes = [(r.get("roles") or {}).get("slug", "") for r in member_roles if r.get("roles")]
        role_names = [(r.get("roles") or {}).get("name", "") for r in member_roles if r.get("roles")]

        # Get Telegram status
        tg_result = supabase.table("telegram_users").select(
            "telegram_id, telegram_username, verified_at"
        ).eq("user_id", member_user_id).limit(1).execute()

        tg_data = tg_result.data[0] if tg_result.data else None

        # Query user_profiles for full_name to display in the FIO column
        profile_result = supabase.table("user_profiles").select(
            "full_name"
        ).eq("user_id", member_user_id).limit(1).execute()

        profile_data = profile_result.data[0] if profile_result.data else None
        profile_full_name = profile_data.get("full_name") if profile_data else None

        # Use full_name from user_profiles, fall back to truncated UUID only if no profile
        email_display = profile_full_name if profile_full_name else (member_user_id[:8] + "...")

        users_data.append({
            "user_id": member_user_id,
            "email": email_display,
            "roles": role_codes,
            "role_names": role_names,
            "telegram": tg_data,
            "joined_at": format_date_russian(member["created_at"]) if member.get("created_at") else "-"
        })

    # Build users table rows
    user_rows = []
    for u in users_data:
        # Roles badges - using status-badge style
        role_badges = []
        for i, code in enumerate(u["roles"]):
            name = u["role_names"][i] if i < len(u["role_names"]) else code
            # Map roles to unified badge colors
            badge_class = {
                "admin": "status-error",
                "sales": "status-info",
                "procurement": "status-success",
                "logistics": "status-warning",
                "customs": "status-progress",
                "quote_controller": "status-new",
                "spec_controller": "status-info",
                "finance": "status-success",
                "top_manager": "status-warning",
                "head_of_sales": "status-info",
                "head_of_procurement": "status-success",
                "head_of_logistics": "status-warning",
                "training_manager": "status-neutral",
            }.get(code, "status-neutral")
            role_badges.append(
                Span(name, cls=f"status-badge {badge_class}", style="margin-right: 4px;")
            )

        # Telegram status
        if u["telegram"] and u["telegram"].get("verified_at"):
            tg_status = Span("✓ @" + (u["telegram"].get("username") or str(u["telegram"]["telegram_id"])),
                style="color: #10b981; font-size: 0.875rem;")
        else:
            tg_status = Span("—", style="color: #9ca3af;")

        # Make roles cell clickable for inline editing
        roles_cell = Td(
            Div(
                *role_badges if role_badges else [Span("—", style="color: #9ca3af;")],
                id=f"roles-display-{u['user_id']}",
                style="cursor: pointer;",
                hx_get=f"/admin/users/{u['user_id']}/roles/edit",
                hx_target=f"#roles-cell-{u['user_id']}",
                hx_swap="innerHTML",
                title="Кликните для редактирования ролей"
            ),
            id=f"roles-cell-{u['user_id']}"
        )

        user_rows.append(Tr(
            Td(u["email"]),
            roles_cell,
            Td(tg_status),
            Td(u["joined_at"])
        ))

    users_content = Div(
        # Stats
        Div(
            Div(
                Div(str(len(users_data)), cls="stat-value", style="color: #3b82f6;"),
                Div("Всего пользователей", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(sum(1 for u in users_data if u["telegram"])), cls="stat-value", style="color: #10b981;"),
                Div("С Telegram", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(len(all_roles)), cls="stat-value", style="color: #8b7cf6;"),
                Div("Доступных ролей", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Users table
        Div(
            Div(
                Div(H4("Пользователи организации", style="margin: 0;"), cls="table-header-left"),
                cls="table-header"
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("ФИО"),
                        Th("РОЛИ"),
                        Th("TELEGRAM"),
                        Th("ДАТА")
                    )),
                    Tbody(*user_rows) if user_rows else Tbody(Tr(Td("Нет пользователей", colspan="4", style="text-align: center; padding: 2rem; color: #9ca3af;"))),
                    cls="unified-table"
                ),
                cls="table-responsive"
            ),
            Div(Span(f"Всего: {len(users_data)} пользователей"), cls="table-footer"),
            cls="table-container", style="margin: 0;"
        ),

        # Navigation
        Div(
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            btn_link("Назначение брендов", href="/admin/brands", variant="secondary", icon_name="tag"),
            btn_link("Маршрутизация закупок", href="/admin/procurement-groups", variant="primary", icon_name="git-branch"),
            style="margin-top: 24px; display: flex; gap: 12px;"
        ),
    )

    # Design system styles for admin page
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    return page_layout("Пользователи",
        # Header card with gradient
        Div(
            Div(
                icon("settings", size=24, color="#475569"),
                Span(" Пользователи", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            P("Управление пользователями и ролями",
              style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
            style=header_card_style
        ),

        # Users content (no tabs needed - only users here now)
        users_content,

        session=session
    )


# ============================================================================
# ADMIN FEEDBACK LIST - /admin/feedback
# ============================================================================

STATUS_LABELS = {
    "new": ("Новое", "status-error"),
    "in_progress": ("В работе", "status-warning"),
    "resolved": ("Решено", "status-success"),
    "closed": ("Закрыто", "status-neutral"),
}

FEEDBACK_TYPE_LABELS_RU = {
    "bug": "Ошибка",
    "ux_ui": "UX/UI",
    "suggestion": "Предложение",
    "question": "Вопрос",
}


@rt("/admin/feedback")
def get(session, status_filter: str = ""):
    """Admin page - list all user feedback / bug reports."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            session=session
        )

    supabase = get_supabase()

    # Fetch list - deliberately exclude screenshot_data (potentially large)
    query = supabase.table("user_feedback").select(
        "id, short_id, user_name, user_email, organization_name, "
        "feedback_type, description, status, clickup_task_id, created_at, page_url"
    ).order("created_at", desc=True).limit(200)

    if status_filter:
        query = query.eq("status", status_filter)

    result = query.execute()
    items = result.data if result.data else []

    # Status filter tabs
    all_statuses = [("", "Все"), ("new", "Новые"), ("in_progress", "В работе"),
                    ("resolved", "Решено"), ("closed", "Закрыто")]
    filter_tabs = Div(
        *[
            A(label,
              href=f"/admin/feedback{'?status_filter=' + s if s else ''}",
              cls=f"tab-btn {'active' if status_filter == s else ''}")
            for s, label in all_statuses
        ],
        cls="tabs-nav", style="margin-bottom: 20px;"
    )

    # Table rows
    rows = []
    for item in items:
        status_label, status_cls = STATUS_LABELS.get(item.get("status", "new"), ("—", "status-neutral"))
        type_label = FEEDBACK_TYPE_LABELS_RU.get(item.get("feedback_type", ""), item.get("feedback_type", ""))
        desc_preview = (item.get("description") or "")[:80]
        if len(item.get("description") or "") > 80:
            desc_preview += "..."

        clickup_cell = Td("—")
        if item.get("clickup_task_id"):
            clickup_cell = Td(
                A(item["clickup_task_id"],
                  href=f"https://app.clickup.com/t/{item['clickup_task_id']}",
                  target="_blank",
                  style="font-size: 0.75rem; color: #6366f1;")
            )

        item_short_id = item.get("short_id", "—")
        rows.append(Tr(
            Td(A(item_short_id,
                 href=f"/admin/feedback/{item_short_id}",
                 style="font-weight: 600; font-family: monospace; color: #3b82f6;")),
            Td(Span(type_label, cls="status-badge status-neutral")),
            Td(desc_preview, style="max-width: 300px; font-size: 0.875rem;"),
            Td(item.get("user_name") or item.get("user_email") or "—", style="font-size: 0.875rem;"),
            Td(Span(status_label, cls=f"status-badge {status_cls}")),
            clickup_cell,
            Td(format_date_russian(item.get("created_at")) if item.get("created_at") else "—",
               style="font-size: 0.75rem; white-space: nowrap;"),
            cls="clickable-row",
            onclick=f"window.location='/admin/feedback/{item_short_id}'"
        ))

    table = Div(
        Div(
            Div(H4(f"Обращения ({len(items)})", style="margin: 0;"), cls="table-header-left"),
            cls="table-header"
        ),
        Div(
            Table(
                Thead(Tr(
                    Th("ID"), Th("Тип"), Th("Описание"), Th("Пользователь"),
                    Th("Статус"), Th("ClickUp"), Th("Дата")
                )),
                Tbody(*rows) if rows else Tbody(Tr(
                    Td("Нет обращений", colspan="7",
                       style="text-align: center; padding: 2rem; color: #9ca3af;")
                )),
                cls="unified-table"
            ),
            cls="table-responsive"
        ),
        cls="table-container", style="margin: 0;"
    )

    return page_layout("Обращения",
        Div(
            icon("message-square", size=24, color="#475569"),
            Span(" Обращения пользователей",
                 style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
            style="display: flex; align-items: center; margin-bottom: 6px;"
        ),
        filter_tabs,
        table,
        Div(
            btn_link("Назад", href="/admin", variant="secondary", icon_name="arrow-left"),
            style="margin-top: 20px;"
        ),
        session=session,
        current_path="/admin/feedback"
    )


@rt("/admin/feedback/{short_id}/status", methods=["POST"])
async def post_feedback_status(session, short_id: str, status: str = "new"):
    """HTMX endpoint to update feedback status. Syncs to ClickUp + Telegram."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return Div("Нет прав", cls="text-error")

    from services.feedback_service import update_feedback_status
    result = await update_feedback_status(short_id, status)

    if not result.success:
        return Div(f"Ошибка: {result.message}", cls="text-error text-sm")

    status_label, _ = STATUS_LABELS.get(status, ("—", ""))
    extras = []
    if result.clickup_synced:
        extras.append("ClickUp обновлён")
    if result.telegram_notified:
        extras.append("Telegram уведомлён")
    suffix = f" ({', '.join(extras)})" if extras else ""
    return Span(f"Сохранено: {status_label}{suffix}", cls="text-success text-sm")


# /api/internal/feedback/{short_id}/status was extracted to
# api/feedback.py::update_feedback_status in Phase 6B-8. The INTERNAL_API_KEY
# env var is still required in production — it is read there.


@rt("/admin" + "/feedback/{short_id}/sync-clickup", methods=["POST"])
async def post_feedback_sync_clickup(session, short_id: str):
    """HTMX endpoint to pull ClickUp task status and update local feedback status."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return Div("Нет прав", cls="text-error")

    supabase = get_supabase()
    try:
        result = supabase.table("user_feedback").select("clickup_task_id, status").eq("short_id", short_id).limit(1).execute()
        if not result.data:
            return Span("Обращение не найдено", cls="text-error text-sm")

        task_id = (result.data[0] or {}).get("clickup_task_id")
        if not task_id:
            return Span("Нет привязки к ClickUp", cls="text-warning text-sm")

        from services.clickup_service import get_clickup_task_status
        new_admin_status = await get_clickup_task_status(task_id)
        if not new_admin_status:
            return Span("Не удалось получить статус из ClickUp", cls="text-error text-sm")

        current_status = result.data[0].get("status", "new")
        if new_admin_status == current_status:
            status_label, _ = STATUS_LABELS.get(current_status, ("—", ""))
            return Span(f"Статусы совпадают: {status_label}", cls="text-info text-sm")

        supabase.table("user_feedback").update({
            "status": new_admin_status,
            "updated_at": datetime.now().isoformat()
        }).eq("short_id", short_id).execute()

        old_label, _ = STATUS_LABELS.get(current_status, ("—", ""))
        new_label, _ = STATUS_LABELS.get(new_admin_status, ("—", ""))
        return Span(f"Синхронизировано: {old_label} → {new_label}", cls="text-success text-sm")
    except Exception as e:
        logger.error(f"ClickUp sync failed for {short_id}: {e}")
        return Span(f"Ошибка: {e}", cls="text-error text-sm")


@rt("/admin/feedback/{short_id}")
def get(session, short_id: str):
    """Admin feedback detail page - shows full description, screenshot, context, status form."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return page_layout("Доступ запрещён", H1("Доступ запрещён"), session=session)

    supabase = get_supabase()

    # Fetch full record including screenshot_data
    result = supabase.table("user_feedback").select("*").eq("short_id", short_id).limit(1).execute()
    if not result.data:
        return page_layout("Не найдено",
            H1("Обращение не найдено"),
            P(f"ID: {short_id}"),
            btn_link("К списку", href="/admin/feedback", variant="secondary"),
            session=session
        )

    item = result.data[0]

    status_label, status_cls = STATUS_LABELS.get(item.get("status", "new"), ("—", "status-neutral"))
    type_label = FEEDBACK_TYPE_LABELS_RU.get(item.get("feedback_type", ""), item.get("feedback_type", ""))

    # Screenshot display (prefer URL from Supabase Storage, fall back to base64)
    screenshot_section = None
    screenshot_url = item.get("screenshot_url")
    screenshot_b64 = item.get("screenshot_data")
    if screenshot_url:
        screenshot_section = Div(
            H4("Скриншот", style="margin-bottom: 8px; font-weight: 600;"),
            Img(
                src=screenshot_url,
                style="max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; max-height: 500px;"
            ),
            style="margin-bottom: 20px;"
        )
    elif screenshot_b64:
        screenshot_section = Div(
            H4("Скриншот", style="margin-bottom: 8px; font-weight: 600;"),
            Img(
                src=f"data:image/jpeg;base64,{screenshot_b64}",
                style="max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; max-height: 500px;"
            ),
            style="margin-bottom: 20px;"
        )

    # Debug context display
    context_section = None
    if item.get("debug_context"):
        ctx = item["debug_context"]
        if isinstance(ctx, str):
            try:
                ctx = json.loads(ctx)
            except Exception:
                ctx = {}
        ua = ctx.get("userAgent", "")
        browser = "Chrome" if "Chrome" in ua else "Firefox" if "Firefox" in ua else "Other"
        context_lines = [
            f"Browser: {browser}",
            f"Screen: {ctx.get('screenSize', '—')}",
            f"URL: {ctx.get('url', '—')}",
        ]
        errors = ctx.get("consoleErrors", [])
        if errors:
            context_lines.append(f"Console errors ({len(errors)}):")
            for err in errors:
                context_lines.append(f"  [{err.get('type', 'error')}] {str(err.get('message', ''))[:120]}")
        requests_data = ctx.get("recentRequests", [])
        if requests_data:
            context_lines.append(f"Recent requests ({len(requests_data)}):")
            for req in requests_data:
                status_code = req.get("status", "?")
                line = f"  {req.get('method', 'GET')} {req.get('url', '?')}: {status_code}"
                if isinstance(status_code, int) and status_code >= 400:
                    line += " [FAILED]"
                context_lines.append(line)

        context_section = Div(
            H4("Debug контекст", style="margin-bottom: 8px; font-weight: 600;"),
            Pre(
                "\n".join(context_lines),
                style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; font-size: 0.75rem; overflow-x: auto; white-space: pre-wrap;"
            ),
            style="margin-bottom: 20px;"
        )

    # Status update form (HTMX)
    status_form = Div(
        H4("Обновить статус", style="margin-bottom: 8px; font-weight: 600;"),
        Form(
            Select(
                Option("Новое", value="new", selected=(item.get("status") == "new")),
                Option("В работе", value="in_progress", selected=(item.get("status") == "in_progress")),
                Option("Решено", value="resolved", selected=(item.get("status") == "resolved")),
                Option("Закрыто", value="closed", selected=(item.get("status") == "closed")),
                name="status",
                cls="select select-bordered"
            ),
            Button("Сохранить", type="submit", cls="btn btn-sm btn-primary", style="margin-left: 8px;"),
            Div(id=f"status-result-{short_id}"),
            hx_post=f"/admin/feedback/{short_id}/status",
            hx_target=f"#status-result-{short_id}",
            hx_swap="innerHTML",
            style="display: flex; align-items: center; gap: 8px;"
        ),
        style="margin-bottom: 20px;"
    )

    # ClickUp link and sync button if available
    clickup_section = None
    if item.get("clickup_task_id"):
        clickup_section = Div(
            Div(
                A(
                    icon("external-link", size=14),
                    f" Открыть в ClickUp ({item['clickup_task_id']})",
                    href=f"https://app.clickup.com/t/{item['clickup_task_id']}",
                    target="_blank",
                    style="color: #6366f1; text-decoration: none; font-size: 0.875rem;"
                ),
                Button(
                    icon("refresh-cw", size=14),
                    " Синхронизировать из ClickUp",
                    hx_post=f"/admin/feedback/{short_id}/sync-clickup",
                    hx_target=f"#clickup-sync-result-{short_id}",
                    hx_swap="innerHTML",
                    cls="btn btn-sm btn-secondary",
                    style="margin-left: 12px; font-size: 0.75rem;"
                ),
                style="display: flex; align-items: center; gap: 8px;"
            ),
            Div(id=f"clickup-sync-result-{short_id}"),
            style="margin-bottom: 16px;"
        )

    content_parts = [
        Div(
            btn_link("К списку", href="/admin/feedback", variant="secondary", icon_name="arrow-left"),
            style="margin-bottom: 16px;"
        ),
        Div(
            Div(
                Span(type_label, cls="status-badge status-neutral", style="margin-right: 8px;"),
                Span(status_label, cls=f"status-badge {status_cls}"),
                style="margin-bottom: 8px;"
            ),
            H2(item.get("short_id", ""), style="font-family: monospace; margin-bottom: 4px;"),
            P(f"От: {item.get('user_name') or '—'} ({item.get('user_email') or '—'})",
              style="color: #64748b; font-size: 0.875rem; margin: 0;"),
            P(f"Организация: {item.get('organization_name') or '—'}",
              style="color: #64748b; font-size: 0.875rem; margin: 0;"),
            P(f"Страница: {item.get('page_url') or '—'}",
              style="color: #64748b; font-size: 0.875rem; margin: 4px 0 0 0;"),
            style="margin-bottom: 20px;"
        ),
        Div(
            H4("Описание", style="margin-bottom: 8px; font-weight: 600;"),
            P(item.get("description") or "—",
              style="background: #f8fafc; border-left: 3px solid #3b82f6; padding: 12px; border-radius: 0 6px 6px 0;"),
            style="margin-bottom: 20px;"
        ),
    ]
    if clickup_section:
        content_parts.append(clickup_section)
    content_parts.append(status_form)
    if screenshot_section:
        content_parts.append(screenshot_section)
    if context_section:
        content_parts.append(context_section)

    return page_layout(f"Обращение {short_id}",
        *content_parts,
        session=session,
        current_path="/admin/feedback"
    )


@rt("/admin/users/{user_id}/roles/edit")
def get(user_id: str, session):
    """Inline role editor - returns form HTML fragment for HTMX."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])
    org_id = admin_user["org_id"]

    # Only admins can edit roles
    if "admin" not in roles:
        return Div("Нет прав", style="color: #ef4444;")

    supabase = get_supabase()
    from services.role_service import get_all_roles, get_user_role_codes

    # Get available roles for organization
    all_roles = get_all_roles(organization_id=org_id)

    # Get current user roles
    current_role_codes = get_user_role_codes(user_id, org_id)

    # Build checkboxes for each role
    role_checkboxes = []
    for role in all_roles:
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(role.code, "#6b7280")

        is_checked = role.code in current_role_codes

        role_checkboxes.append(
            Label(
                Input(
                    type="checkbox",
                    name="roles",
                    value=role.code,
                    checked=is_checked,
                    style="margin-right: 6px;"
                ),
                Span(role.name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;"),
                style="display: flex; align-items: center; gap: 4px; margin-bottom: 6px; cursor: pointer;"
            )
        )

    # Return inline form
    return Form(
        Div(
            *role_checkboxes,
            style="display: flex; flex-direction: column; background: #f9fafb; padding: 12px; border-radius: 8px; margin: 4px 0;"
        ),
        Div(
            btn("Сохранить", variant="primary", icon_name="check", type="submit", size="sm"),
            btn("Отмена", variant="ghost", size="sm", type="button",
                hx_get=f"/admin/users/{user_id}/roles/cancel",
                hx_target=f"#roles-cell-{user_id}",
                hx_swap="innerHTML"),
            style="display: flex; gap: 8px; margin-top: 8px;"
        ),
        hx_post=f"/admin/users/{user_id}/roles/update",
        hx_target=f"#roles-cell-{user_id}",
        hx_swap="innerHTML",
        style="margin: 0;"
    )


@rt("/admin/users/{user_id}/roles/update")
def post(user_id: str, session, roles: list = None):
    """Update user roles inline - returns updated badges HTML fragment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    admin_roles = admin_user.get("roles", [])
    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    # Only admins can edit roles
    if "admin" not in admin_roles:
        return Div("Нет прав", style="color: #ef4444;")

    from services.role_service import (
        get_user_role_codes, assign_role, remove_role,
        get_all_roles, get_role_by_code
    )

    # Get current roles
    current_roles = get_user_role_codes(user_id, org_id)

    # Normalize input
    if roles is None:
        roles = []
    elif isinstance(roles, str):
        roles = [roles]

    # Safety: prevent empty roles (user must have at least 1 role)
    if not roles:
        return Div("Ошибка: нельзя убрать все роли. Выберите хотя бы одну.", style="color: #ef4444; padding: 8px; font-size: 0.875rem;")

    # Safety: prevent admin from removing admin role from themselves
    if user_id == admin_id and "admin" in current_roles and "admin" not in roles:
        return Div("Ошибка: нельзя снять роль admin с самого себя.", style="color: #ef4444; padding: 8px; font-size: 0.875rem;")

    # Determine which roles to add/remove
    roles_to_add = [r for r in roles if r not in current_roles]
    roles_to_remove = [r for r in current_roles if r not in roles]

    # Add new roles
    for role_code in roles_to_add:
        assign_role(user_id, org_id, role_code, admin_id)

    # Remove old roles
    for role_code in roles_to_remove:
        remove_role(user_id, org_id, role_code)

    # Get updated roles
    updated_role_codes = get_user_role_codes(user_id, org_id)

    # Build updated badges
    role_badges = []
    all_roles_dict = {r.code: r.name for r in get_all_roles(organization_id=org_id)}

    for code in updated_role_codes:
        name = all_roles_dict.get(code, code)
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(code, "#6b7280")

        role_badges.append(
            Span(name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-right: 4px;")
        )

    # Return updated display
    return Div(
        *role_badges if role_badges else [Span("—", style="color: #9ca3af;")],
        id=f"roles-display-{user_id}",
        style="cursor: pointer;",
        hx_get=f"/admin/users/{user_id}/roles/edit",
        hx_target=f"#roles-cell-{user_id}",
        hx_swap="innerHTML",
        title="Кликните для редактирования ролей"
    )


@rt("/admin/users/{user_id}/roles/cancel")
def get(user_id: str, session):
    """Cancel inline editing - returns original badges HTML fragment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    org_id = admin_user["org_id"]

    from services.role_service import get_user_role_codes, get_all_roles

    # Get current roles
    role_codes = get_user_role_codes(user_id, org_id)

    # Build badges
    role_badges = []
    all_roles_dict = {r.code: r.name for r in get_all_roles(organization_id=org_id)}

    for code in role_codes:
        name = all_roles_dict.get(code, code)
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(code, "#6b7280")

        role_badges.append(
            Span(name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-right: 4px;")
        )

    # Return original display
    return Div(
        *role_badges if role_badges else [Span("—", style="color: #9ca3af;")],
        id=f"roles-display-{user_id}",
        style="cursor: pointer;",
        hx_get=f"/admin/users/{user_id}/roles/edit",
        hx_target=f"#roles-cell-{user_id}",
        hx_swap="innerHTML",
        title="Кликните для редактирования ролей"
    )


@rt("/admin/users/{user_id}/roles")
def get(user_id: str, session):
    """Page to manage roles for a specific user.

    Shows all available roles and allows admin to toggle them on/off.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = admin_user["org_id"]

    # Get all available roles (filter by org to avoid showing irrelevant roles)
    from services.role_service import get_all_roles, get_user_role_codes
    all_roles = get_all_roles(organization_id=org_id)

    # Get current user roles
    current_roles = get_user_role_codes(user_id, org_id)

    # Build role checkboxes with modern card styling
    role_inputs = []
    for r in all_roles:
        checked = r.code in current_roles
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(r.code, "#6b7280")

        card_bg = f"{color}10" if checked else "#f8fafc"
        card_border = color if checked else "#e2e8f0"

        role_inputs.append(
            Label(
                Div(
                    Div(
                        Input(type="checkbox", name="roles", value=r.code, checked=checked, style="width: 16px; height: 16px; accent-color: " + color + ";"),
                        style="margin-right: 12px; display: flex; align-items: center;"
                    ),
                    Div(
                        Div(
                            Span(r.name, style=f"color: {color}; font-weight: 600; font-size: 14px;"),
                            Span(f" ({r.code})", style="color: #94a3b8; font-size: 12px; margin-left: 4px;"),
                        ),
                        Span(r.description or "", style="color: #64748b; font-size: 12px; display: block; margin-top: 2px;") if r.description else None,
                        style="flex: 1;"
                    ),
                    style="display: flex; align-items: flex-start;"
                ),
                style=f"display: block; padding: 12px; margin-bottom: 8px; border-radius: 8px; cursor: pointer; background: {card_bg}; border: 1px solid {card_border};"
            )
        )

    return page_layout(f"Управление ролями",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К списку пользователей",
                href="/admin",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("shield", size=28, color="#6366f1"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Управление ролями", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Span(f"ID: {user_id[:8]}...", style="color: #64748b; font-size: 13px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Two-column layout
        Div(
            # Left column - Current roles
            Div(
                Div(
                    icon("user-check", size=14, color="#64748b"),
                    Span("ТЕКУЩИЕ РОЛИ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    *[Span(code, style="display: inline-block; background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; margin: 0 6px 6px 0;") for code in current_roles]
                    if current_roles else [Span("Нет назначенных ролей", style="color: #94a3b8; font-size: 14px;")]
                ),
                Div(
                    Span(f"{len(current_roles)} ", style="font-weight: 600; color: #1e293b;"),
                    Span("из ", style="color: #64748b;"),
                    Span(f"{len(all_roles)} ", style="font-weight: 600; color: #1e293b;"),
                    Span("ролей назначено", style="color: #64748b;"),
                    style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px;"
                ),
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            # Right column - Role selection form
            Form(
                Div(
                    icon("settings", size=14, color="#64748b"),
                    Span("ВЫБОР РОЛЕЙ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    *role_inputs,
                    style="max-height: 400px; overflow-y: auto; padding-right: 8px;"
                ),
                Input(type="hidden", name="user_id", value=user_id),
                Div(
                    btn("Сохранить роли", variant="primary", icon_name="check", type="submit"),
                    style="margin-top: 20px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ),
                method="POST",
                action=f"/admin/users/{user_id}/roles",
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px;"
        ),

        session=session
    )


@rt("/admin/users/{user_id}/roles")
def post(user_id: str, session, roles: list = None):
    """Handle role updates for a user.

    Compares submitted roles with current roles and adds/removes as needed.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    admin_roles = admin_user.get("roles", [])

    # Only admins can access this page
    if "admin" not in admin_roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    # Handle empty roles list (none selected)
    if roles is None:
        roles = []
    elif isinstance(roles, str):
        roles = [roles]

    # Get current user roles
    from services.role_service import get_user_role_codes, assign_role, remove_role
    current_roles = get_user_role_codes(user_id, org_id)

    # Safety: prevent empty roles (user must have at least 1 role)
    if not roles:
        return page_layout("Ошибка",
            H1("Ошибка обновления ролей"),
            P("Нельзя убрать все роли у пользователя. Выберите хотя бы одну роль."),
            btn_link("Назад", href=f"/admin/users/{user_id}/roles", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Safety: prevent admin from removing admin role from themselves
    if user_id == admin_id and "admin" in current_roles and "admin" not in roles:
        return page_layout("Ошибка",
            H1("Ошибка обновления ролей"),
            P("Нельзя снять роль admin с самого себя. Попросите другого администратора."),
            btn_link("Назад", href=f"/admin/users/{user_id}/roles", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    submitted_roles = set(roles)
    current_roles_set = set(current_roles)

    # Roles to add
    to_add = submitted_roles - current_roles_set
    for role_code in to_add:
        result = assign_role(user_id, org_id, role_code, admin_id)
        if result:
            print(f"Added role {role_code} to user {user_id}")

    # Roles to remove
    to_remove = current_roles_set - submitted_roles
    for role_code in to_remove:
        result = remove_role(user_id, org_id, role_code)
        if result:
            print(f"Removed role {role_code} from user {user_id}")

    # Success message
    return page_layout("Роли обновлены",
        H1("✓ Роли обновлены"),
        P(f"Пользователь: {user_id[:8]}..."),
        P(f"Добавлено ролей: {len(to_add)}" if to_add else ""),
        P(f"Удалено ролей: {len(to_remove)}" if to_remove else ""),
        Div(
            H4("Текущие роли:", style="margin-bottom: 8px;"),
            Div(
                *[Span(code, style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.875rem; margin-right: 4px;") for code in sorted(submitted_roles)]
                if submitted_roles else [Span("Нет ролей", style="color: #9ca3af;")]
            ),
            style="background: #f0fdf4; padding: 12px; border-radius: 8px; margin-top: 16px;"
        ),
        Div(
            btn_link("Назад к списку", href="/admin/users", variant="secondary", icon_name="arrow-left"),
            style="margin-top: 24px;"
        ),
        session=session
    )


# ============================================================================
# ADMIN: BRAND MANAGEMENT
# Feature #85: Страница /admin/brands
# ============================================================================

@rt("/admin/brands")
def get(session):
    """Admin page for brand assignments.

    Feature #85: Страница /admin/brands

    This page allows admins to:
    - View all brand assignments (brand → procurement manager)
    - Import new brands from existing quotes
    - Assign/reassign brands to procurement managers
    - Delete brand assignments
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Import brand service functions
    from services.brand_service import (
        get_all_brand_assignments,
        get_unique_brands_in_org,
        count_assignments_by_user
    )

    # Get all current brand assignments
    assignments = get_all_brand_assignments(org_id)

    # Get unique brands from quote_items in this organization
    # This is for "import from quotes" functionality
    quote_items_result = supabase.table("quote_items").select(
        "brand, quotes!inner(organization_id)"
    ).eq("quotes.organization_id", org_id).execute()

    all_quote_brands = set()
    for item in (quote_items_result.data or []):
        if item.get("brand"):
            all_quote_brands.add(item["brand"])

    # Get already assigned brands
    assigned_brands = set(a.brand.lower() for a in assignments)

    # Find unassigned brands
    unassigned_brands = [b for b in sorted(all_quote_brands) if b.lower() not in assigned_brands]

    # Get procurement users for assignments
    from services.role_service import get_user_role_codes

    # Get all active organization members
    members_result = supabase.table("organization_members").select(
        "user_id"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only users who have the procurement role
    procurement_users = []
    for member in (members_result.data or []):
        user_id = member["user_id"]
        user_roles = get_user_role_codes(user_id, org_id)
        if "procurement" in user_roles:
            procurement_users.append(user_id)

    # Get assignment counts per user
    assignment_counts = count_assignments_by_user(org_id)

    # Build assignment table rows
    assignment_rows = []
    for a in assignments:
        # Get user display (shortened ID)
        user_display = a.user_id[:8] + "..."
        brand_count = assignment_counts.get(a.user_id, 0)

        assignment_rows.append(Tr(
            Td(Span(a.brand, style="font-weight: 600;")),
            Td(user_display),
            Td(str(brand_count)),
            Td(a.created_at.strftime("%Y-%m-%d") if a.created_at else "-"),
            Td(
                Div(
                    btn_link("Изменить", href=f"/admin/brands/{a.id}/edit", variant="secondary", size="sm"),
                    Form(
                        btn("Удалить", variant="danger", size="sm", type="submit"),
                        method="POST",
                        action=f"/admin/brands/{a.id}/delete",
                        style="display: inline;"
                    ),
                    style="display: flex; align-items: center; gap: 0.5rem;"
                )
            )
        ))

    # Build unassigned brands list with modern styling
    unassigned_items = []
    for brand in unassigned_brands:
        unassigned_items.append(
            Div(
                Span(brand, style="font-weight: 600; color: #1e293b; margin-right: 12px;"),
                btn_link("Назначить", href=f"/admin/brands/new?brand={brand}", variant="secondary", size="sm"),
                style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; margin-bottom: 6px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;"
            )
        )

    # Table styles
    th_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    return page_layout("Управление брендами",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К администрированию",
                href="/admin",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content with action button
            Div(
                Div(
                    Div(
                        icon("tag", size=28, color="#8b5cf6"),
                        style="width: 48px; height: 48px; background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                    ),
                    Div(
                        H1("Управление брендами", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        P("Назначение брендов менеджерам по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; align-items: center; flex: 1;"
                ),
                btn_link("Добавить назначение", href="/admin/brands/new", variant="success", icon_name="plus"),
                style="display: flex; align-items: center; justify-content: space-between;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Stats grid
        Div(
            Div(
                Span(str(len(assignments)), style="font-size: 28px; font-weight: 700; color: #10b981; display: block;"),
                Span("Назначено брендов", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(unassigned_brands)), style="font-size: 28px; font-weight: 700; color: #f59e0b; display: block;"),
                Span("Без назначения", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(procurement_users)), style="font-size: 28px; font-weight: 700; color: #3b82f6; display: block;"),
                Span("Менеджеров закупок", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(all_quote_brands)), style="font-size: 28px; font-weight: 700; color: #8b5cf6; display: block;"),
                Span("Всего брендов в КП", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Unassigned brands section
        Div(
            Div(
                icon("alert-circle", size=14, color="#d97706"),
                Span("БРЕНДЫ БЕЗ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #d97706; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center;"
            ),
            Div(
                *unassigned_items if unassigned_items else [
                    Div(
                        icon("check-circle", size=16, color="#10b981"),
                        Span(" Все бренды из КП назначены менеджерам", style="color: #10b981; font-size: 14px; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    )
                ],
                style="max-height: 200px; overflow-y: auto;"
            ),
            style=f"background: {'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)' if unassigned_items else 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'}; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; border: 1px solid {'#fcd34d' if unassigned_items else '#86efac'};"
        ) if all_quote_brands else None,

        # Current assignments table section
        Div(
            Div(
                icon("list", size=14, color="#64748b"),
                Span("ТЕКУЩИЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("Бренд", style=th_style),
                        Th("Менеджер", style=th_style),
                        Th("Всего брендов", style=th_style),
                        Th("Дата назначения", style=th_style),
                        Th("Действия", style=th_style)
                    )),
                    Tbody(*[Tr(
                        Td(Span(a.brand, style="font-weight: 600; color: #8b5cf6;"), style=td_style),
                        Td(a.user_id[:8] + "...", style=td_style),
                        Td(str(assignment_counts.get(a.user_id, 0)), style=td_style),
                        Td(a.created_at.strftime("%Y-%m-%d") if a.created_at else "-", style=td_style),
                        Td(
                            Div(
                                btn_link("Изменить", href=f"/admin/brands/{a.id}/edit", variant="secondary", size="sm"),
                                Form(
                                    btn("Удалить", variant="danger", size="sm", type="submit"),
                                    method="POST",
                                    action=f"/admin/brands/{a.id}/delete",
                                    style="display: inline;"
                                ),
                                style="display: flex; align-items: center; gap: 8px;"
                            ),
                            style=td_style
                        )
                    ) for a in assignments]) if assignment_rows else Tbody(
                        Tr(Td(
                            Div(
                                icon("inbox", size=32, color="#94a3b8"),
                                P("Нет назначений", style="color: #64748b; margin: 8px 0 0 0;"),
                                style="text-align: center; padding: 32px;"
                            ),
                            colspan="5"
                        ))
                    ),
                    style="width: 100%; border-collapse: collapse;"
                ),
                style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
        ),

        session=session
    )


@rt("/admin/brands/new")
def get(session, brand: str = None):
    """Form to create new brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get procurement users
    # First get all active organization members
    members_result = supabase.table("organization_members").select(
        "user_id"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only users who have the procurement role
    from services.role_service import get_user_role_codes
    procurement_users = []
    for member in (members_result.data or []):
        user_id = member["user_id"]
        user_roles = get_user_role_codes(user_id, org_id)
        if "procurement" in user_roles:
            procurement_users.append({
                "user_id": user_id,
                "display": user_id[:8] + "..."
            })

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"])
        for u in procurement_users
    ]

    # Form input styles
    input_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    return page_layout("Новое назначение бренда",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К списку брендов",
                href="/admin/brands",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("plus-circle", size=28, color="#10b981"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Новое назначение бренда", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    P("Назначьте бренд менеджеру по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("tag", size=14, color="#64748b"),
                    Span("ДАННЫЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                # Brand name
                Div(
                    Label("Название бренда *", fr="brand", style=label_style),
                    Input(type="text", name="brand", id="brand", value=brand or "", required=True,
                          placeholder="Например: BOSCH", style=input_style),
                    style="margin-bottom: 16px;"
                ),

                # Manager select
                Div(
                    Label("Менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        Option("— Выберите менеджера —", value="", disabled=True, selected=True),
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else Div(
                        Div(
                            icon("alert-triangle", size=16, color="#ef4444"),
                            Span(" Нет пользователей с ролью 'procurement'", style="color: #ef4444; font-size: 14px; margin-left: 8px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        P("Сначала назначьте роль менеджера по закупкам на ",
                          A("странице пользователей", href="/admin", style="color: #3b82f6; text-decoration: underline;"), ".",
                          style="color: #64748b; font-size: 13px; margin: 0;"),
                        style="padding: 16px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Создать назначение", variant="success", icon_name="plus", type="submit"),
                    btn_link("Отмена", href="/admin/brands", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if user_options else None,

                method="POST",
                action="/admin/brands/new"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


@rt("/admin/brands/new")
def post(session, brand: str, user_id: str):
    """Create new brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    from services.brand_service import create_brand_assignment, get_brand_assignment_by_brand

    # Check if brand is already assigned
    existing = get_brand_assignment_by_brand(org_id, brand)
    if existing:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Бренд уже назначен", cls="page-header"),
            P(f"Бренд '{brand}' уже назначен другому менеджеру."),
            P("Используйте функцию редактирования для изменения назначения."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Create the assignment
    result = create_brand_assignment(
        organization_id=org_id,
        brand=brand.strip(),
        user_id=user_id,
        created_by=admin_id
    )

    if result:
        return page_layout("Назначение создано",
            H1("✓ Назначение создано"),
            P(f"Бренд '{brand}' успешно назначен менеджеру."),
            Div(
                Span(brand, style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;"),
                Span(" → ", style="margin: 0 8px;"),
                Span(user_id[:8] + "...", style="color: #6b7280;"),
                style="margin: 16px 0;"
            ),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка создания", cls="page-header"),
            P("Не удалось создать назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )


@rt("/admin/brands/{assignment_id}/edit")
def get(assignment_id: str, session):
    """Edit form for brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.brand_service import get_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    if not assignment:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get procurement users
    from services.role_service import get_user_role_codes

    # Get all active organization members
    members_result = supabase.table("organization_members").select(
        "user_id"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only users who have the procurement role
    procurement_users = []
    for member in (members_result.data or []):
        user_id = member["user_id"]
        user_roles = get_user_role_codes(user_id, org_id)
        if "procurement" in user_roles:
            procurement_users.append({
                "user_id": user_id,
                "display": user_id[:8] + "..."
            })

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"], selected=(u["user_id"] == assignment.user_id))
        for u in procurement_users
    ]

    # Form input styles
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"

    return page_layout("Редактирование назначения",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К списку брендов",
                href="/admin/brands",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("edit-3", size=28, color="#f59e0b"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Редактирование назначения", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Div(
                        Span("Бренд: ", style="color: #64748b; font-size: 14px;"),
                        Span(assignment.brand, style="color: #8b5cf6; font-size: 14px; font-weight: 600;"),
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("user", size=14, color="#64748b"),
                    Span("ИЗМЕНИТЬ МЕНЕДЖЕРА", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                Input(type="hidden", name="brand", value=assignment.brand),

                # Current assignment info
                Div(
                    Span("Текущий менеджер: ", style="color: #64748b; font-size: 13px;"),
                    Span(assignment.user_id[:8] + "...", style="color: #1e293b; font-weight: 500; font-size: 13px;"),
                    style="padding: 12px; background: #f8fafc; border-radius: 8px; margin-bottom: 16px;"
                ),

                # Manager select
                Div(
                    Label("Новый менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else P("Нет менеджеров с ролью procurement", style="color: #ef4444; font-size: 14px;"),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Сохранить изменения", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/admin/brands", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if user_options else None,

                method="POST",
                action=f"/admin/brands/{assignment_id}/edit"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


@rt("/admin/brands/{assignment_id}/edit")
def post(assignment_id: str, session, user_id: str, brand: str = None):
    """Update brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.brand_service import update_brand_assignment, get_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    if not assignment:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Update the assignment
    result = update_brand_assignment(assignment_id, user_id)

    if result:
        return page_layout("Назначение обновлено",
            H1("✓ Назначение обновлено"),
            P(f"Бренд '{assignment.brand}' переназначен новому менеджеру."),
            Div(
                Span(assignment.brand, style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;"),
                Span(" → ", style="margin: 0 8px;"),
                Span(user_id[:8] + "...", style="color: #6b7280;"),
                style="margin: 16px 0;"
            ),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка обновления", cls="page-header"),
            P("Не удалось обновить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )


@rt("/admin/brands/{assignment_id}/delete")
def post(assignment_id: str, session):
    """Delete brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.brand_service import get_brand_assignment, delete_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    brand_name = assignment.brand if assignment else "Unknown"

    result = delete_brand_assignment(assignment_id)

    if result:
        return page_layout("Назначение удалено",
            H1("✓ Назначение удалено"),
            P(f"Бренд '{brand_name}' больше не назначен менеджеру."),
            P("Бренд вернулся в список неназначенных.", style="color: #6b7280;"),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка удаления", cls="page-header"),
            P("Не удалось удалить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# ============================================================================
# ADMIN: PROCUREMENT GROUP ROUTING
# Маршрутизация закупок: группа продаж → менеджер по закупкам
# ============================================================================

@rt("/admin/procurement-groups")
def get(session):
    """Admin page for procurement group routing assignments.

    Maps sales groups to procurement users. When a quote is created by a
    sales manager in a sales group, all items are routed to the assigned
    procurement user.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = user["org_id"]

    from services.route_procurement_assignment_service import get_all_with_details
    from services.user_profile_service import get_sales_groups, get_organization_users
    from services.role_service import get_users_by_role

    # Get all assignments with joined group names
    assignments_with_details = get_all_with_details(org_id)

    # Get all sales groups
    all_groups = get_sales_groups(org_id)

    # Get all org users for display names
    org_users = get_organization_users(org_id)
    user_name_map = {u["id"]: u.get("full_name") or u.get("email", u["id"][:8] + "...") for u in org_users}

    # Find assigned group IDs
    assigned_group_ids = set(a["sales_group_id"] for a in assignments_with_details)

    # Find unassigned groups
    unassigned_groups = [g for g in all_groups if g["id"] not in assigned_group_ids]

    # Count procurement users (single query via role_service)
    procurement_role_users = get_users_by_role(org_id, "procurement")
    procurement_user_count = len(procurement_role_users)

    # Table styles
    th_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    # Build assignment table rows
    assignment_rows = []
    for a in assignments_with_details:
        user_display = user_name_map.get(a["user_id"], a["user_id"][:8] + "...")
        group_name = a.get("sales_group_name") or a["sales_group_id"][:8] + "..."
        created_at = ""
        if a.get("created_at"):
            try:
                dt = datetime.fromisoformat(a["created_at"].replace("Z", "+00:00"))
                created_at = dt.strftime("%Y-%m-%d")
            except Exception:
                created_at = str(a["created_at"])[:10]

        assignment_rows.append(Tr(
            Td(Span(group_name, style="font-weight: 600; color: #3b82f6;"), style=td_style),
            Td(user_display, style=td_style),
            Td(created_at or "-", style=td_style),
            Td(
                Div(
                    btn_link("Изменить", href=f"/admin/procurement-groups/{a['id']}/edit", variant="secondary", size="sm"),
                    Form(
                        btn("Удалить", variant="danger", size="sm", type="submit"),
                        method="POST",
                        action=f"/admin/procurement-groups/{a['id']}/delete",
                        style="display: inline;"
                    ),
                    style="display: flex; align-items: center; gap: 8px;"
                ),
                style=td_style
            )
        ))

    # Build unassigned groups list
    unassigned_items = []
    for group in unassigned_groups:
        unassigned_items.append(
            Div(
                Span(group["name"], style="font-weight: 600; color: #1e293b; margin-right: 12px;"),
                btn_link("Назначить", href=f"/admin/procurement-groups/new?group_id={group['id']}", variant="secondary", size="sm"),
                style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; margin-bottom: 6px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;"
            )
        )

    return page_layout("Маршрутизация закупок",
        # Header card
        Div(
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К администрированию",
                href="/admin",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    Div(
                        icon("git-branch", size=28, color="#3b82f6"),
                        style="width: 48px; height: 48px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                    ),
                    Div(
                        H1("Маршрутизация закупок", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        P("Назначение групп продаж менеджерам по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; align-items: center; flex: 1;"
                ),
                btn_link("Добавить назначение", href="/admin/procurement-groups/new", variant="success", icon_name="plus"),
                style="display: flex; align-items: center; justify-content: space-between;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Stats grid
        Div(
            Div(
                Span(str(len(assignments_with_details)), style="font-size: 28px; font-weight: 700; color: #10b981; display: block;"),
                Span("Назначено групп", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(unassigned_groups)), style="font-size: 28px; font-weight: 700; color: #f59e0b; display: block;"),
                Span("Без назначения", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(procurement_user_count), style="font-size: 28px; font-weight: 700; color: #3b82f6; display: block;"),
                Span("Менеджеров закупок", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(all_groups)), style="font-size: 28px; font-weight: 700; color: #8b5cf6; display: block;"),
                Span("Всего групп продаж", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Unassigned groups section
        Div(
            Div(
                icon("alert-circle", size=14, color="#d97706"),
                Span("ГРУППЫ БЕЗ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #d97706; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center;"
            ),
            Div(
                *unassigned_items if unassigned_items else [
                    Div(
                        icon("check-circle", size=16, color="#10b981"),
                        Span(" Все группы продаж назначены менеджерам", style="color: #10b981; font-size: 14px; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    )
                ],
                style="max-height: 200px; overflow-y: auto;"
            ),
            style=f"background: {'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)' if unassigned_items else 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'}; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; border: 1px solid {'#fcd34d' if unassigned_items else '#86efac'};"
        ) if all_groups else None,

        # Current assignments table
        Div(
            Div(
                icon("list", size=14, color="#64748b"),
                Span("ТЕКУЩИЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("Группа продаж", style=th_style),
                        Th("Менеджер по закупкам", style=th_style),
                        Th("Дата назначения", style=th_style),
                        Th("Действия", style=th_style)
                    )),
                    Tbody(*assignment_rows) if assignment_rows else Tbody(
                        Tr(Td(
                            Div(
                                icon("inbox", size=32, color="#94a3b8"),
                                P("Нет назначений", style="color: #64748b; margin: 8px 0 0 0;"),
                                style="text-align: center; padding: 32px;"
                            ),
                            colspan="4"
                        ))
                    ),
                    style="width: 100%; border-collapse: collapse;"
                ),
                style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
        ),

        # Help card: cascade priority
        Div(
            Div(
                icon("info", size=14, color="#3b82f6"),
                Span("КАК РАБОТАЕТ МАРШРУТИЗАЦИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #3b82f6; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center;"
            ),
            Div(
                P("1. Группа продаж (высший приоритет) - если менеджер продаж состоит в группе, все позиции КП направляются назначенному закупщику", style="margin: 0 0 8px 0; font-size: 13px; color: #475569;"),
                P("2. Бренд (запасной вариант) - если нет назначения по группе, позиции направляются по назначению брендов", style="margin: 0 0 8px 0; font-size: 13px; color: #475569;"),
                P("3. ПХМБ-КП исключены из маршрутизации", style="margin: 0; font-size: 13px; color: #94a3b8;"),
            ),
            style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 12px; padding: 16px 20px; margin-top: 24px; border: 1px solid #93c5fd;"
        ),

        session=session
    )


@rt("/admin/procurement-groups/new")
def get(session, group_id: str = None):
    """Form to create new procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = user["org_id"]
    from services.user_profile_service import get_sales_groups, get_organization_users
    from services.role_service import get_users_by_role

    # Get all sales groups
    all_groups = get_sales_groups(org_id)

    # Build group options
    group_options = [
        Option(g["name"], value=g["id"], selected=(g["id"] == group_id))
        for g in all_groups
    ]

    # Get procurement users (single query via role_service)
    org_users = get_organization_users(org_id)
    user_name_map = {u["id"]: u.get("full_name") or u.get("email", u["id"][:8] + "...") for u in org_users}

    procurement_role_users = get_users_by_role(org_id, "procurement")
    procurement_users = [
        {"user_id": u["user_id"], "display": user_name_map.get(u["user_id"], u["user_id"][:8] + "...")}
        for u in procurement_role_users
    ]

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"])
        for u in procurement_users
    ]

    # Form styles
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    return page_layout("Новое назначение группы",
        # Header card
        Div(
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К маршрутизации закупок",
                href="/admin/procurement-groups",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    icon("plus-circle", size=28, color="#10b981"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Новое назначение", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    P("Назначьте группу продаж менеджеру по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("git-branch", size=14, color="#64748b"),
                    Span("ДАННЫЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                # Sales group select
                Div(
                    Label("Группа продаж *", fr="sales_group_id", style=label_style),
                    Select(
                        Option("-- Выберите группу --", value="", disabled=True, selected=(not group_id)),
                        *group_options,
                        name="sales_group_id",
                        id="sales_group_id",
                        required=True,
                        style=select_style
                    ) if group_options else Div(
                        Div(
                            icon("alert-triangle", size=16, color="#ef4444"),
                            Span(" Нет групп продаж", style="color: #ef4444; font-size: 14px; margin-left: 8px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        P("Сначала создайте группы продаж в настройках.", style="color: #64748b; font-size: 13px; margin: 0;"),
                        style="padding: 16px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;"
                    ),
                    style="margin-bottom: 16px;"
                ),

                # Procurement user select
                Div(
                    Label("Менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        Option("-- Выберите менеджера --", value="", disabled=True, selected=True),
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else Div(
                        Div(
                            icon("alert-triangle", size=16, color="#ef4444"),
                            Span(" Нет пользователей с ролью 'procurement'", style="color: #ef4444; font-size: 14px; margin-left: 8px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        P("Сначала назначьте роль менеджера по закупкам на ",
                          A("странице пользователей", href="/admin", style="color: #3b82f6; text-decoration: underline;"), ".",
                          style="color: #64748b; font-size: 13px; margin: 0;"),
                        style="padding: 16px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Создать назначение", variant="success", icon_name="plus", type="submit"),
                    btn_link("Отмена", href="/admin/procurement-groups", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if (group_options and user_options) else None,

                method="POST",
                action="/admin/procurement-groups/new"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


@rt("/admin/procurement-groups/new")
def post(session, sales_group_id: str, user_id: str):
    """Create new procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    from services.route_procurement_assignment_service import create_assignment, get_assignment_by_group
    from services.role_service import get_users_by_role

    # Validate user_id belongs to this org's procurement users
    valid_user_ids = {u["user_id"] for u in get_users_by_role(org_id, "procurement")}
    if user_id not in valid_user_ids:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Недопустимый пользователь", cls="page-header"),
            P("Выбранный пользователь не является менеджером по закупкам в вашей организации."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Check if group is already assigned
    existing = get_assignment_by_group(org_id, sales_group_id)
    if existing:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Группа уже назначена", cls="page-header"),
            P("Эта группа продаж уже назначена менеджеру по закупкам."),
            P("Используйте функцию редактирования для изменения назначения."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Create the assignment
    result = create_assignment(
        organization_id=org_id,
        sales_group_id=sales_group_id,
        user_id=user_id,
        created_by=admin_id
    )

    if result:
        return RedirectResponse(url="/admin/procurement-groups", status_code=303)
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка создания", cls="page-header"),
            P("Не удалось создать назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )


@rt("/admin/procurement-groups/{assignment_id}/edit")
def get(assignment_id: str, session):
    """Edit form for procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.route_procurement_assignment_service import get_assignment
    from services.user_profile_service import get_sales_groups, get_organization_users
    from services.role_service import get_users_by_role

    org_id = user["org_id"]

    assignment = get_assignment(assignment_id)
    if not assignment or assignment.organization_id != org_id:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Get sales group name
    all_groups = get_sales_groups(org_id)
    group_name_map = {g["id"]: g["name"] for g in all_groups}
    current_group_name = group_name_map.get(assignment.sales_group_id, assignment.sales_group_id[:8] + "...")

    # Get procurement users (single query via role_service)
    org_users = get_organization_users(org_id)
    user_name_map = {u["id"]: u.get("full_name") or u.get("email", u["id"][:8] + "...") for u in org_users}

    procurement_role_users = get_users_by_role(org_id, "procurement")
    procurement_users = [
        {"user_id": u["user_id"], "display": user_name_map.get(u["user_id"], u["user_id"][:8] + "...")}
        for u in procurement_role_users
    ]

    # Build user options with current selected
    user_options = [
        Option(u["display"], value=u["user_id"], selected=(u["user_id"] == assignment.user_id))
        for u in procurement_users
    ]

    # Form styles
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    current_user_display = user_name_map.get(assignment.user_id, assignment.user_id[:8] + "...")

    return page_layout("Редактирование назначения",
        # Header card
        Div(
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К маршрутизации закупок",
                href="/admin/procurement-groups",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    icon("edit-3", size=28, color="#f59e0b"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Редактирование назначения", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Div(
                        Span("Группа: ", style="color: #64748b; font-size: 14px;"),
                        Span(current_group_name, style="color: #3b82f6; font-size: 14px; font-weight: 600;"),
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("user", size=14, color="#64748b"),
                    Span("ИЗМЕНИТЬ МЕНЕДЖЕРА", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                # Current assignment info
                Div(
                    Span("Текущий менеджер: ", style="color: #64748b; font-size: 13px;"),
                    Span(current_user_display, style="color: #1e293b; font-weight: 500; font-size: 13px;"),
                    style="padding: 12px; background: #f8fafc; border-radius: 8px; margin-bottom: 16px;"
                ),

                # Manager select
                Div(
                    Label("Новый менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else P("Нет менеджеров с ролью procurement", style="color: #ef4444; font-size: 14px;"),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Сохранить изменения", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/admin/procurement-groups", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if user_options else None,

                method="POST",
                action=f"/admin/procurement-groups/{assignment_id}/edit"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


@rt("/admin/procurement-groups/{assignment_id}/edit")
def post(assignment_id: str, session, user_id: str):
    """Update procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.route_procurement_assignment_service import update_assignment, get_assignment
    from services.role_service import get_users_by_role

    org_id = admin_user["org_id"]
    assignment = get_assignment(assignment_id)
    if not assignment or assignment.organization_id != org_id:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Validate user_id belongs to this org's procurement users
    valid_user_ids = {u["user_id"] for u in get_users_by_role(org_id, "procurement")}
    if user_id not in valid_user_ids:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Недопустимый пользователь", cls="page-header"),
            P("Выбранный пользователь не является менеджером по закупкам в вашей организации."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    result = update_assignment(assignment_id, user_id)

    if result:
        return RedirectResponse(url="/admin/procurement-groups", status_code=303)
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка обновления", cls="page-header"),
            P("Не удалось обновить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )


@rt("/admin/procurement-groups/{assignment_id}/delete")
def post(assignment_id: str, session):
    """Delete procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.route_procurement_assignment_service import get_assignment, delete_assignment

    org_id = admin_user["org_id"]
    assignment = get_assignment(assignment_id)
    if not assignment or assignment.organization_id != org_id:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    result = delete_assignment(assignment_id)

    if result:
        return RedirectResponse(url="/admin/procurement-groups", status_code=303)
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка удаления", cls="page-header"),
            P("Не удалось удалить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# ============================================================================
# ADMIN IMPERSONATION ROUTES
# ============================================================================

VALID_IMPERSONATION_ROLES = {
    "sales", "procurement", "logistics", "customs",
    "quote_controller", "spec_controller", "finance",
    "top_manager", "head_of_sales", "head_of_procurement", "head_of_logistics",
    "currency_controller",
}

@rt("/admin/impersonate")
def get(session, role: str = ""):
    """GET /admin/impersonate - Set or clear role impersonation (admin and training_manager)."""
    user = session.get("user")
    user_roles = user.get("roles", []) if user else []
    if not user or ("admin" not in user_roles and "training_manager" not in user_roles):
        return RedirectResponse("/", status_code=303)

    if role:
        if role not in VALID_IMPERSONATION_ROLES:
            return RedirectResponse("/", status_code=303)
        session["impersonated_role"] = role
    else:
        session.pop("impersonated_role", None)

    return RedirectResponse("/", status_code=303)


@rt("/admin/impersonate/exit")
def get(session):
    """GET /admin/impersonate/exit - Clear role impersonation."""
    session.pop("impersonated_role", None)
    return RedirectResponse("/", status_code=303)


# ============================================================================
# CUSTOMERS MANAGEMENT — [archived to legacy-fasthtml/customers.py in Phase 6C-2B-1]
# Routes moved: /customers, /customers/{id}, /customers/{id}/{subtab}, contacts, addresses,
# warehouses, calls, inline-edit fragments. Superseded by Next.js /customers.
# ============================================================================


# ============================================================================
# USER PROFILE VIEW + INLINE EDIT — [archived to legacy-fasthtml/settings_profile.py in Phase 6C-2B-4]
# Routes moved: /profile/{user_id} GET+POST (here and above), /profile/{user_id}/edit-field/{field_name},
# /profile/{user_id}/update-field/{field_name}, /profile/{user_id}/cancel-edit/{field_name}.
# Superseded by Next.js /profile.
# ============================================================================


# ============================================================================
# CUSTOMER CONTRACTS — [archived to legacy-fasthtml/calls_documents_contracts.py in Phase 6C-2B-10a]
# Routes moved: /customer-contracts GET, /customer-contracts/new GET+POST,
# /customer-contracts/{contract_id} GET. Superseded by Next.js (pending).
# services/customer_contract_service.py remains alive.
# ============================================================================


# ============================================================================
# SUPPLIER INVOICES ROUTES — [archived to legacy-fasthtml/supplier_invoices.py in Phase 6C-2B-10b]
# Routes moved: /supplier-invoices GET (registry),
# /supplier-invoices/{invoice_id} GET (detail),
# /supplier-invoices/{invoice_id}/payments/new GET+POST (payment form).
# Helpers moved: _invoice_payment_form (payment form renderer),
# _documents_section (now exclusive to supplier-invoices after Phase 6C-2B-10a).
# services/supplier_invoice_service.py + services/supplier_invoice_payment_service.py
# + services/buyer_company_service.py + services/document_service.py remain alive.
# No Next.js replacement at archive time — supplier-invoice management will be
# rewritten via Next.js + FastAPI post-cutover.
# ============================================================================

# ============================================================================
# DOCUMENT STORAGE ROUTES
# ============================================================================
# Universal document upload/download/delete functionality
# Files stored in Supabase Storage bucket 'kvota-documents'
# Metadata stored in kvota.documents table

def _quote_documents_section(
    quote_id: str,
    session: dict,
    invoices: List[Dict],
    items: List[Dict],
    can_upload: bool = True,
    can_delete: bool = True
):
    """
    Documents section for quotes with hierarchical binding support.

    Shows ALL documents related to a quote:
    - Documents directly attached to the quote
    - Invoice documents (scans, payment orders)
    - Item certificates

    Upload form dynamically shows invoice/item selector based on document type.

    Args:
        quote_id: Quote UUID
        session: User session
        invoices: List of supplier invoices for this quote [{id, invoice_number, supplier_name}]
        items: List of quote items [{id, name, sku, brand}]
        can_upload: Whether user can upload
        can_delete: Whether user can delete
    """
    documents = get_all_documents_for_quote(quote_id)
    doc_types = get_allowed_document_types_for_entity("quote")

    # Build document rows with entity binding info
    doc_rows = []
    for doc in documents:
        # Determine binding label
        if doc.entity_type == "quote":
            binding_label = "КП"
            binding_style = "background: #dbeafe; color: #1e40af;"
        elif doc.entity_type == "supplier_invoice":
            # Find invoice name
            invoice_name = next((inv.get("invoice_number", "Инвойс") for inv in invoices if inv.get("id") == doc.entity_id), "Инвойс")
            binding_label = f"Инв: {invoice_name}"
            binding_style = "background: #fef3c7; color: #92400e;"
        elif doc.entity_type == "quote_item":
            # Find item name
            item_info = next((f"{it.get('name', 'Товар')[:20]}" for it in items if it.get("id") == doc.entity_id), "Товар")
            binding_label = f"Поз: {item_info}"
            binding_style = "background: #d1fae5; color: #065f46;"
        else:
            binding_label = get_entity_type_label(doc.entity_type)
            binding_style = "background: #f3f4f6; color: #374151;"

        doc_rows.append(
            Tr(
                # File icon + name (narrow, truncated, tooltip on hover)
                Td(
                    A(
                        I(cls=f"fa-solid {get_file_icon(doc.mime_type)}", style="margin-right: 0.5rem; color: var(--accent); flex-shrink: 0;"),
                        Span(doc.original_filename, style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"),
                        href=f"/documents/{doc.id}/view",
                        target="_blank",
                        title=doc.original_filename,
                        style="text-decoration: none; color: var(--text-primary); display: flex; align-items: center; max-width: 100%; overflow: hidden;"
                    ),
                    style="max-width: 150px; overflow: hidden;"
                ),
                # Document type
                Td(
                    Span(get_document_type_label(doc.document_type),
                         cls="badge",
                         style="background: var(--accent-light); color: var(--accent); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;")
                    if doc.document_type else "-"
                ),
                # Binding
                Td(
                    Span(binding_label,
                         style=f"{binding_style}; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; white-space: nowrap;")
                ),
                # Description (NEW)
                Td(
                    Span(doc.description or "-",
                         title=doc.description if doc.description else None,
                         style="color: var(--text-secondary); font-size: 0.85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 150px;")
                ),
                # File size
                Td(format_file_size(doc.file_size_bytes) or "-", style="color: var(--text-secondary); font-size: 0.85rem;"),
                # Upload date
                Td(doc.created_at.strftime("%d.%m.%Y") if doc.created_at else "-", style="color: var(--text-secondary); font-size: 0.85rem;"),
                # Actions - small square icon buttons
                Td(
                    A(
                      icon("eye", size=16),
                      href=f"/documents/{doc.id}/view",
                      target="_blank",
                      title="Просмотр",
                      style="display: inline-flex !important; align-items: center !important; justify-content: center !important; width: 32px !important; height: 32px !important; background: #f3f4f6 !important; border: 1px solid #d1d5db !important; border-radius: 6px !important; color: #374151 !important; text-decoration: none !important;"),
                    A(
                      icon("download", size=16),
                      href=f"/documents/{doc.id}/download",
                      title="Скачать",
                      style="display: inline-flex !important; align-items: center !important; justify-content: center !important; width: 32px !important; height: 32px !important; background: #f3f4f6 !important; border: 1px solid #d1d5db !important; border-radius: 6px !important; color: #374151 !important; text-decoration: none !important;"),
                    A(
                      icon("trash-2", size=16),
                      href="#",
                      hx_delete=f"/documents/{doc.id}",
                      hx_confirm="Удалить документ?",
                      hx_target=f"#doc-row-{doc.id}",
                      hx_swap="outerHTML",
                      title="Удалить",
                      style="display: inline-flex !important; align-items: center !important; justify-content: center !important; width: 32px !important; height: 32px !important; background: #f3f4f6 !important; border: 1px solid #d1d5db !important; border-radius: 6px !important; color: #374151 !important; text-decoration: none !important;") if can_delete else None,
                    style="white-space: nowrap; display: flex; gap: 0.5rem;"
                ),
                id=f"doc-row-{doc.id}"
            )
        )

    # Empty state
    if not doc_rows:
        doc_rows.append(
            Tr(
                Td("Документы не загружены", colspan="7", style="text-align: center; color: var(--text-muted); padding: 2rem;")
            )
        )

    # Build invoice options for dropdown
    invoice_options = [Option("— Выберите инвойс —", value="")]
    for inv in invoices:
        supplier = inv.get("supplier_name", "")
        label = f"{inv.get('invoice_number', 'Инвойс')} ({supplier})" if supplier else inv.get("invoice_number", "Инвойс")
        invoice_options.append(Option(label, value=inv.get("id", "")))

    # Build item options for dropdown
    item_options = [Option("— Выберите товар —", value="")]
    for item in items:
        brand = item.get("brand", "")
        sku = item.get("sku", "")
        name = item.get("name", "Товар")[:30]
        label = f"{name}"
        if brand:
            label += f" ({brand})"
        if sku:
            label += f" [{sku}]"
        item_options.append(Option(label, value=item.get("id", "")))

    # JavaScript for dynamic sub-entity selector
    js_script = Script("""
    document.addEventListener('DOMContentLoaded', function() {
        const docTypeSelect = document.getElementById('doc_type');
        const invoiceDiv = document.getElementById('invoice-selector-div');
        const itemDiv = document.getElementById('item-selector-div');
        const invoiceSelect = document.getElementById('sub_entity_invoice');
        const itemSelect = document.getElementById('sub_entity_item');

        const invoiceTypes = ['invoice_scan', 'proforma_scan', 'payment_order'];
        const itemTypes = ['certificate'];

        function updateSelectors() {
            const selectedType = docTypeSelect.value;

            // Update select color: grey for placeholder, black for real selection
            if (selectedType && selectedType !== '') {
                docTypeSelect.style.color = '#111827';
            } else {
                docTypeSelect.style.color = '#9ca3af';
            }

            // Show/hide sub-selectors
            if (invoiceDiv) {
                invoiceDiv.style.display = invoiceTypes.includes(selectedType) ? 'block' : 'none';
            }
            if (itemDiv) {
                itemDiv.style.display = itemTypes.includes(selectedType) ? 'block' : 'none';
            }

            // Clear non-visible selectors
            if (!invoiceTypes.includes(selectedType) && invoiceSelect) {
                invoiceSelect.value = '';
            }
            if (!itemTypes.includes(selectedType) && itemSelect) {
                itemSelect.value = '';
            }
        }

        if (docTypeSelect) {
            docTypeSelect.addEventListener('change', updateSelectors);
            updateSelectors(); // Initial state
        }
    });
    """)

    # JavaScript for drag-and-drop
    drag_drop_js = Script("""
    document.addEventListener('DOMContentLoaded', function() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('doc_file');
        const fileNameSpan = document.getElementById('file-name');

        if (!dropZone || !fileInput) return;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Highlight drop zone
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#6366f1';
                dropZone.style.background = '#eef2ff';
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#d1d5db';
                dropZone.style.background = '#fafafa';
            }, false);
        });

        // Handle dropped files
        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                updateFileName(files[0].name);
            }
        }, false);

        // Handle file input change
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                updateFileName(fileInput.files[0].name);
            }
        });

        // Click to select
        dropZone.addEventListener('click', () => fileInput.click());

        function updateFileName(name) {
            if (fileNameSpan) {
                fileNameSpan.textContent = name;
                fileNameSpan.style.color = '#111827';
            }
        }
    });
    """)

    return Div(
        js_script,
        drag_drop_js,

        # Compact upload form
        Div(
            Form(
                Div(
                    # Left side: Drop zone (wider)
                    Div(
                        Div(
                            I(cls="fa-solid fa-cloud-arrow-up", style="font-size: 1.5rem; color: #9ca3af; margin-bottom: 0.5rem;"),
                            Div(
                                Span("Перетащите файл или ", style="color: #6b7280;"),
                                Span("выберите", style="color: #6366f1; cursor: pointer;"),
                                style="font-size: 0.875rem;"
                            ),
                            Span("", id="file-name", style="font-size: 0.75rem; color: #9ca3af; margin-top: 0.25rem;"),
                            style="display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer;"
                        ),
                        Input(type="file", name="file", id="doc_file", required=True,
                              accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.zip,.rar,.7z,.txt,.csv",
                              style="display: none;"),
                        id="drop-zone",
                        style="border: 2px dashed #d1d5db; border-radius: 8px; padding: 1rem; background: #fafafa; flex: 1; display: flex; align-items: center; justify-content: center; transition: border-color 0.15s ease, background-color 0.15s ease;"
                    ),
                    style="flex: 1; display: flex;"
                ),

                # Right side: Type, description, save
                Div(
                    # Document type with custom styled select
                    Div(
                        Select(
                            Option("Тип документа", value="", disabled=True, selected=True, style="color: #9ca3af;"),
                            *[Option(dt["label"], value=dt["value"]) for dt in doc_types],
                            name="document_type",
                            id="doc_type",
                            style="width: 100%; padding: 0.5rem 2rem 0.5rem 0.5rem; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 0.875rem; background: white; color: #9ca3af; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E\"); background-repeat: no-repeat; background-position: right 0.5rem center; cursor: pointer;"
                        ),
                        style="margin-bottom: 0.5rem; position: relative;"
                    ),

                    # Dynamic sub-entity selectors (hidden by default)
                    Div(
                        Select(
                            *invoice_options,
                            name="sub_entity_invoice",
                            id="sub_entity_invoice",
                            style="width: 100%; padding: 0.4rem; border: 1px solid #fcd34d; border-radius: 4px; font-size: 0.8rem; background: #fffbeb;"
                        ),
                        id="invoice-selector-div",
                        style="display: none; margin-bottom: 0.5rem;"
                    ) if invoices else Div(id="invoice-selector-div", style="display: none;"),

                    Div(
                        Select(
                            *item_options,
                            name="sub_entity_item",
                            id="sub_entity_item",
                            style="width: 100%; padding: 0.4rem; border: 1px solid #6ee7b7; border-radius: 4px; font-size: 0.8rem; background: #ecfdf5;"
                        ),
                        id="item-selector-div",
                        style="display: none; margin-bottom: 0.5rem;"
                    ) if items else Div(id="item-selector-div", style="display: none;"),

                    # Description
                    Div(
                        Input(type="text", name="description", id="doc_desc",
                              placeholder="Описание (опционально)",
                              style="width: 100%; padding: 0.5rem; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 0.875rem;"),
                        style="margin-bottom: 0.5rem;"
                    ),

                    # Save button
                    btn("Сохранить", variant="primary", icon_name="check", type="submit", full_width=True),

                    style="width: 280px; flex-shrink: 0;"
                ),

                # Hidden field for parent quote
                Input(type="hidden", name="parent_quote_id", value=quote_id),

                action=f"/documents/upload/quote/{quote_id}",
                method="POST",
                enctype="multipart/form-data",
                id="doc-upload-form",
                style="display: flex; gap: 0.75rem; align-items: stretch;"
            ),
            style="margin-bottom: 1rem; padding: 1rem; background: white; border: 1px solid #e5e7eb; border-radius: 8px;"
        ) if can_upload else None,

        # Documents table with gradient container
        Div(
            # Section header
            Div(
                icon("folder-open", size=16, color="#64748b"),
                Span(f" ДОКУМЕНТЫ ({len(documents)})", style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px;"),
                style="display: flex; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0;"
            ),
            Table(
                Thead(
                    Tr(
                        Th("Файл", style="width: 15%; color: #64748b; font-size: 0.75rem; text-transform: uppercase;"),
                        Th("Тип", style="width: 12%; color: #64748b; font-size: 0.75rem; text-transform: uppercase;"),
                        Th("Привязка", style="width: 10%; color: #64748b; font-size: 0.75rem; text-transform: uppercase;"),
                        Th("Описание", style="width: 18%; color: #64748b; font-size: 0.75rem; text-transform: uppercase;"),
                        Th("Размер", style="width: 8%; color: #64748b; font-size: 0.75rem; text-transform: uppercase;"),
                        Th("Дата", style="width: 10%; color: #64748b; font-size: 0.75rem; text-transform: uppercase;"),
                        Th("", style="width: 10%;"),
                    )
                ),
                Tbody(*doc_rows, id="documents-tbody"),
                cls="table",
                style="width: 100%;"
            ),
            style="overflow-x: auto; background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); padding: 1.25rem; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
        ),

        cls="documents-section",
        id="documents-section"
    )


# ============================================================================
# DOCUMENTS ROUTES — [archived to legacy-fasthtml/calls_documents_contracts.py in Phase 6C-2B-10a]
# Routes moved: /documents/upload/{entity_type}/{entity_id} POST,
# /documents/{document_id}/download GET, /documents/{document_id}/view GET,
# /documents/{document_id} DELETE, /documents/{entity_type}/{entity_id} GET.
# Superseded by FastAPI /api/documents/* (api/documents.py) for download + delete.
# services/document_service.py remains alive. _documents_section helper archived
# in Phase 6C-2B-10b alongside its last remaining caller (/supplier-invoices).
# ============================================================================



# ============================================================================
# CURRENCY INVOICES HELPERS
# ============================================================================

def _resolve_company_name(supabase, entity_type, entity_id):
    """Resolve company name from polymorphic FK (entity_type + entity_id).

    Used by currency invoices to look up buyer/seller company names
    from either buyer_companies or seller_companies tables.
    """
    if not entity_type or not entity_id:
        return "Не выбрана"
    table = "buyer_companies" if entity_type == "buyer_company" else "seller_companies"
    try:
        resp = supabase.table(table).select("name").eq("id", entity_id).single().execute()
        return (resp.data or {}).get("name", "Неизвестно")
    except Exception:
        return "Неизвестно"


def _ci_status_badge(status):
    """Return a styled Span badge for currency invoice status."""
    colors = {
        "draft": "background: #fef9c3; color: #854d0e;",
        "verified": "background: #dcfce7; color: #166534;",
        "exported": "background: #dbeafe; color: #1e40af;",
    }
    labels = {
        "draft": "Черновик",
        "verified": "Проверен",
        "exported": "Экспортирован",
    }
    style = colors.get(status, "background: #f1f5f9; color: #475569;")
    label = labels.get(status, status or "—")
    return Span(label, style=f"padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; {style}")


from services.deal_data_service import fetch_items_with_buyer_companies as _svc_fetch_items_with_buyer_companies
from services.deal_data_service import fetch_enrichment_data as _svc_fetch_enrichment_data


def _fetch_items_with_buyer_companies(supabase, quote_id):
    """Fetch quote items enriched with buyer_company_id from invoices."""
    return _svc_fetch_items_with_buyer_companies(supabase, quote_id)


def _fetch_enrichment_data(supabase, org_id):
    """Fetch active currency contracts and bank accounts for an organization."""
    return _svc_fetch_enrichment_data(supabase, org_id)


def _finance_fetch_deal_data(deal_id, org_id, user_roles):
    """
    Fetch deal and plan-fact data needed for finance tabs on quote detail page.

    Returns (deal, plan_fact_items, categories) tuple.
    deal contains nested specifications and quotes.
    """
    supabase = get_supabase()

    # Fetch deal with related data
    try:
        deal_result = supabase.table("deals").select(
            # FK hints resolve ambiguity: !specifications(deals_specification_id_fkey), !quotes(deals_quote_id_fkey)
            "id, deal_number, signed_at, total_amount, currency, status, created_at, "
            "specifications!deals_specification_id_fkey(id, specification_number, proposal_idn, sign_date, validity_period, "
            "  specification_currency, exchange_rate_to_ruble, client_payment_terms, "
            "  our_legal_entity, client_legal_entity), "
            "quotes!deals_quote_id_fkey(id, idn_quote, currency, customers(name))"
        ).eq("id", deal_id).eq("organization_id", org_id).single().is_("deleted_at", None).execute()
    except Exception as e:
        print(f"Error fetching deal {deal_id}: {e}")
        return None, [], []

    deal = deal_result.data
    if not deal:
        return None, [], []

    # Fetch plan_fact_items
    try:
        plan_fact_result = supabase.table("plan_fact_items").select(
            "id, description, planned_amount, planned_currency, planned_date, "
            "actual_amount, actual_currency, actual_date, actual_exchange_rate, "
            "variance_amount, payment_document, notes, created_at, "
            "plan_fact_categories(id, code, name, is_income, sort_order)"
        ).eq("deal_id", deal_id).order("planned_date").execute()
        plan_fact_items = plan_fact_result.data or []
    except Exception as e:
        print(f"Error fetching plan_fact_items: {e}")
        plan_fact_items = []

    categories = get_categories_for_role(user_roles)
    return deal, plan_fact_items, categories


def _finance_main_tab_content(deal_id, deal, plan_fact_items):
    """Render the 'Сделка' (main) finance tab content: deal info + plan-fact summary."""
    spec = (deal.get("specifications") or {})
    quote = (deal.get("quotes") or {})
    customer = (quote.get("customers") or {})
    customer_name = customer.get("name", "Неизвестно")

    deal_number = deal.get("deal_number", "-")
    spec_number = spec.get("specification_number", "-") or spec.get("proposal_idn", "-")
    deal_amount = float(deal.get("total_amount", 0) or 0)
    # Currency priority: quote.currency > spec.specification_currency > deal.currency
    deal_currency = quote.get("currency") or spec.get("specification_currency") or deal.get("currency") or "RUB"
    currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥", "TRY": "₺"}
    deal_currency_display = currency_symbols.get(deal_currency, deal_currency)
    signed_at = format_date_russian(deal.get("signed_at")) if deal.get("signed_at") else "-"

    # Calculate plan-fact summary
    total_planned_income = sum(
        float(item.get("planned_amount", 0) or 0)
        for item in plan_fact_items
        if (item.get("plan_fact_categories") or {}).get("is_income", False)
    )
    total_planned_expense = sum(
        float(item.get("planned_amount", 0) or 0)
        for item in plan_fact_items
        if not (item.get("plan_fact_categories") or {}).get("is_income", True)
    )
    total_actual_income = sum(
        float(item.get("actual_amount", 0) or 0)
        for item in plan_fact_items
        if (item.get("plan_fact_categories") or {}).get("is_income", False) and item.get("actual_amount") is not None
    )
    total_actual_expense = sum(
        float(item.get("actual_amount", 0) or 0)
        for item in plan_fact_items
        if not (item.get("plan_fact_categories") or {}).get("is_income", True) and item.get("actual_amount") is not None
    )
    total_variance = sum(
        float(item.get("variance_amount", 0) or 0)
        for item in plan_fact_items
        if item.get("variance_amount") is not None
    )
    paid_count = sum(1 for item in plan_fact_items if item.get("actual_amount") is not None)
    unpaid_count = len(plan_fact_items) - paid_count

    # Status badge
    status_map = {
        "active": ("В работе", "#10b981"),
        "completed": ("Завершена", "#3b82f6"),
        "cancelled": ("Отменена", "#ef4444"),
    }
    status = deal.get("status", "active")
    status_label, _ = status_map.get(status, (status, "#6b7280"))

    return Div(
        # Two-column grid for info cards
        Div(
            # Left column - Deal info card
            Div(
                Div(
                    icon("file-text", size=14, color="#64748b"),
                    Span("ИНФОРМАЦИЯ О СДЕЛКЕ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    *[Div(
                        Span(label, style="font-size: 12px; color: #64748b; display: block; margin-bottom: 2px;"),
                        Span(value, style="font-size: 14px; color: #1e293b; font-weight: 500;"),
                        style="margin-bottom: 12px;"
                    ) for label, value in [
                        ("Номер сделки", deal_number),
                        ("Спецификация", spec_number),
                        ("Клиент", customer_name),
                        ("Сумма сделки", f"{deal_amount:,.2f} {deal_currency_display}"),
                        ("Дата подписания", signed_at),
                        ("Статус", status_label),
                        ("Условия оплаты", spec.get("client_payment_terms", "-") or "-"),
                        ("Наше юр. лицо", spec.get("our_legal_entity", "-") or "-"),
                        ("Юр. лицо клиента", spec.get("client_legal_entity", "-") or "-"),
                    ]],
                ),
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            # Right column - Plan-fact summary card
            Div(
                Div(
                    icon("bar-chart-2", size=14, color="#64748b"),
                    Span("СВОДКА ПЛАН-ФАКТ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    Div(
                        Span("Плановые поступления", style="font-size: 11px; color: #64748b; display: block; margin-bottom: 4px;"),
                        Span(f"{total_planned_income:,.2f} ₽", style="font-size: 18px; font-weight: 600; color: #10b981;"),
                        style="padding: 12px; background: #f0fdf4; border-radius: 8px;"
                    ),
                    Div(
                        Span("Факт. поступления", style="font-size: 11px; color: #64748b; display: block; margin-bottom: 4px;"),
                        Span(f"{total_actual_income:,.2f} ₽", style="font-size: 18px; font-weight: 600; color: #1e293b;"),
                        style="padding: 12px; background: #f8fafc; border-radius: 8px;"
                    ),
                    Div(
                        Span("Плановые расходы", style="font-size: 11px; color: #64748b; display: block; margin-bottom: 4px;"),
                        Span(f"{total_planned_expense:,.2f} ₽", style="font-size: 18px; font-weight: 600; color: #6366f1;"),
                        style="padding: 12px; background: #eef2ff; border-radius: 8px;"
                    ),
                    Div(
                        Span("Факт. расходы", style="font-size: 11px; color: #64748b; display: block; margin-bottom: 4px;"),
                        Span(f"{total_actual_expense:,.2f} ₽", style="font-size: 18px; font-weight: 600; color: #1e293b;"),
                        style="padding: 12px; background: #f8fafc; border-radius: 8px;"
                    ),
                    style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;"
                ),
                Div(
                    Div(
                        Span("Плановая маржа", style="font-size: 12px; color: #64748b;"),
                        Span(f"{total_planned_income - total_planned_expense:,.2f} ₽", style="font-size: 14px; font-weight: 600; color: #1e293b;"),
                        style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;"
                    ),
                    Div(
                        Span("Общее отклонение", style="font-size: 12px; color: #64748b;"),
                        Span(
                            f"{total_variance:+,.2f} ₽" if total_variance != 0 else "0.00 ₽",
                            style=f"font-size: 14px; font-weight: 600; color: {'#ef4444' if total_variance > 0 else '#10b981' if total_variance < 0 else '#64748b'};"
                        ),
                        style="display: flex; justify-content: space-between; padding: 8px 0;"
                    ),
                ),
                Div(
                    Span(
                        icon("check-circle", size=14, color="#10b981"),
                        f" Оплачено: {paid_count}",
                        style="display: inline-flex; align-items: center; padding: 4px 10px; background: #f0fdf4; border-radius: 12px; font-size: 12px; color: #10b981; font-weight: 500; margin-right: 8px;"
                    ),
                    Span(
                        icon("clock", size=14, color="#f59e0b"),
                        f" Ожидает: {unpaid_count}",
                        style="display: inline-flex; align-items: center; padding: 4px 10px; background: #fef3c7; border-radius: 12px; font-size: 12px; color: #d97706; font-weight: 500;"
                    ),
                    style="margin-top: 12px;"
                ),
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px;"
        ),

        # Transition history
        workflow_transition_history(quote.get("id")) if quote.get("id") else None,
    )


def _finance_plan_fact_tab_content(deal_id, plan_fact_items):
    """Render the 'План-факт' tab content: plan-fact payment table + action buttons."""

    # Build plan-fact table row
    def plan_fact_row(item):
        category = item.get("plan_fact_categories", {}) or {}
        is_income = category.get("is_income", False)
        category_name = category.get("name", "Прочее")

        planned_amount = float(item.get("planned_amount", 0) or 0)
        planned_currency = item.get("planned_currency", "RUB")
        planned_str = f"{planned_amount:,.2f} {planned_currency}"

        actual_amount = item.get("actual_amount")
        actual_currency = item.get("actual_currency", "RUB")
        if actual_amount is not None:
            actual_str = f"{float(actual_amount):,.2f} {actual_currency}"
        else:
            actual_str = "-"

        variance = item.get("variance_amount")
        if variance is not None:
            variance_val = float(variance)
            if variance_val > 0:
                variance_str = f"+{variance_val:,.2f}"
                variance_color = "#ef4444" if not is_income else "#10b981"
            elif variance_val < 0:
                variance_str = f"{variance_val:,.2f}"
                variance_color = "#10b981" if not is_income else "#ef4444"
            else:
                variance_str = "0.00"
                variance_color = "#6b7280"
        else:
            variance_str = "-"
            variance_color = "#6b7280"

        planned_date = format_date_russian(item.get("planned_date")) if item.get("planned_date") else "-"
        actual_date = format_date_russian(item.get("actual_date")) if item.get("actual_date") else "-"

        if actual_amount is not None:
            payment_status = Span(icon("check", size=14), " Оплачено", style="color: #10b981; font-weight: 500; display: inline-flex; align-items: center; gap: 0.25rem;")
        else:
            payment_status = Span("○ Ожидает", style="color: #f59e0b;")

        category_color = "#10b981" if is_income else "#6366f1"

        cell_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"
        return Tr(
            Td(
                Span(category_name, style=f"color: {category_color}; font-weight: 600; display: block;"),
                Span(item.get("description", "-") or "-", style="color: #64748b; font-size: 12px;"),
                style=cell_style
            ),
            Td(planned_date, style=cell_style),
            Td(planned_str, style=f"{cell_style} text-align: right; font-weight: 500;"),
            Td(actual_date if actual_amount is not None else "-", style=cell_style),
            Td(actual_str, style=f"{cell_style} text-align: right;"),
            Td(variance_str, style=f"{cell_style} text-align: right; color: {variance_color}; font-weight: 600;"),
            Td(payment_status, style=cell_style),
            Td(
                btn_link("Редакт.", href=f"/finance/{deal_id}/plan-fact/{item['id']}", variant="primary", size="sm") if actual_amount is None else "",
                style=cell_style
            ),
            style="transition: background-color 0.15s ease;",
            onmouseover="this.style.backgroundColor='#f8fafc'",
            onmouseout="this.style.backgroundColor='transparent'"
        )

    table_header_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"

    if plan_fact_items:
        plan_fact_table = Table(
            Thead(
                Tr(
                    Th("Категория / Описание", style=table_header_style),
                    Th("План. дата", style=table_header_style),
                    Th("План. сумма", style=f"{table_header_style} text-align: right;"),
                    Th("Факт. дата", style=table_header_style),
                    Th("Факт. сумма", style=f"{table_header_style} text-align: right;"),
                    Th("Отклонение", style=f"{table_header_style} text-align: right;"),
                    Th("Статус", style=table_header_style),
                    Th("", style=table_header_style),
                )
            ),
            Tbody(*[plan_fact_row(item) for item in plan_fact_items]),
            style="width: 100%; border-collapse: collapse;"
        )
    else:
        plan_fact_table = Div(
            Div(icon("file-plus", size=40, color="#94a3b8"), style="margin-bottom: 12px;"),
            P("Плановые платежи ещё не созданы", style="color: #64748b; font-size: 14px; margin: 0 0 16px 0;"),
            Div(
                btn_link("Сгенерировать из КП", href=f"/finance/{deal_id}/generate-plan-fact", variant="primary", icon_name="refresh-cw"),
                Button(
                    icon("plus", size=14),
                    " Добавить вручную",
                    hx_get=f"/finance/{deal_id}/payments/new",
                    hx_target="#deal-payment-modal-body",
                    hx_swap="innerHTML",
                    onclick="document.getElementById('deal-payment-modal').style.display='flex';",
                    style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: white; border: none; border-radius: 8px; padding: 8px 16px; cursor: pointer; font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 6px;"
                ),
                style="display: flex; gap: 8px; justify-content: center;"
            ),
            style="text-align: center; padding: 40px 20px; background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 12px;"
        )

    return Div(
        # Plan-fact table section
        Div(
            Div(
                Div(
                    icon("list", size=14, color="#64748b"),
                    Span("ПЛАН-ФАКТ ПЛАТЕЖЕЙ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; display: flex; align-items: center;"
                ),
                Div(
                    Button(
                        icon("plus", size=14),
                        " Добавить платёж",
                        hx_get=f"/finance/{deal_id}/payments/new",
                        hx_target="#deal-payment-modal-body",
                        hx_swap="innerHTML",
                        onclick="document.getElementById('deal-payment-modal').style.display='flex';",
                        style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: white; border: none; border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 6px;"
                    ),
                    btn_link("Перегенерировать", href=f"/finance/{deal_id}/generate-plan-fact", variant="secondary", size="sm", icon_name="refresh-cw"),
                    style="display: flex; gap: 8px;"
                ) if plan_fact_items else "",
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                plan_fact_table,
                style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="margin-bottom: 24px;"
        ),
    )


def _finance_logistics_tab_content(deal_id, deal, session):
    """Render the 'Логистика (сделка)' tab content: logistics stages."""
    return Div(
        Div(
            icon("truck", size=14, color="#64748b"),
            Span("ЛОГИСТИКА", style="margin-left: 6px;"),
            style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
        ),
        _deals_logistics_tab(deal_id, deal, session),
        style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; margin-bottom: 24px;"
    )


def _finance_currency_invoices_tab_content(deal_id):
    """Render the 'Валютные инвойсы' tab content: table of currency invoices for a deal."""
    supabase = get_supabase()

    try:
        ci_resp = supabase.table("currency_invoices").select("*").eq("deal_id", deal_id).order("segment").execute()
        currency_invoices = ci_resp.data or []
    except Exception as e:
        print(f"Error fetching currency invoices for deal {deal_id}: {e}")
        currency_invoices = []

    # Resolve company names (polymorphic lookup)
    for ci in currency_invoices:
        ci["seller_name"] = _resolve_company_name(supabase, ci.get("seller_entity_type"), ci.get("seller_entity_id"))
        ci["buyer_name"] = _resolve_company_name(supabase, ci.get("buyer_entity_type"), ci.get("buyer_entity_id"))

    table_header_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    cell_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    if currency_invoices:
        rows = []
        for ci in currency_invoices:
            total_amount = float(ci.get("total_amount", 0) or 0)
            rows.append(Tr(
                Td(
                    A(ci.get("invoice_number", "—"),
                      href=f"/currency-invoices/{ci['id']}",
                      style="color: #3b82f6; text-decoration: none; font-weight: 500;"),
                    style=cell_style
                ),
                Td(
                    Span(ci.get("segment", ""),
                         style="background: #f3f4f6; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;"),
                    style=cell_style
                ),
                Td(ci.get("seller_name", "Не выбрана"), style=cell_style),
                Td(ci.get("buyer_name", "Не выбрана"), style=cell_style),
                Td(f"{total_amount:,.2f}", style=f"{cell_style} text-align: right; font-weight: 500;"),
                Td(ci.get("currency", ""), style=cell_style),
                Td(_ci_status_badge(ci.get("status", "draft")), style=cell_style),
                style="transition: background-color 0.15s ease;",
                onmouseover="this.style.backgroundColor='#f8fafc'",
                onmouseout="this.style.backgroundColor='transparent'"
            ))

        invoices_table = Table(
            Thead(
                Tr(
                    Th("Номер инвойса", style=table_header_style),
                    Th("Сегмент", style=table_header_style),
                    Th("Продавец", style=table_header_style),
                    Th("Покупатель", style=table_header_style),
                    Th("Сумма", style=f"{table_header_style} text-align: right;"),
                    Th("Валюта", style=table_header_style),
                    Th("Статус", style=table_header_style),
                )
            ),
            Tbody(*rows),
            style="width: 100%; border-collapse: collapse;"
        )
    else:
        invoices_table = Div(
            Div(icon("file-text", size=40, color="#94a3b8"), style="margin-bottom: 12px;"),
            P("Валютные инвойсы не сгенерированы", style="color: #64748b; font-size: 14px; margin: 0 0 16px 0;"),
            Form(
                Button(
                    icon("refresh-cw", size=14, color="white"),
                    " Сгенерировать инвойсы",
                    type="submit",
                    style="background: #3b82f6; color: white; border: none; padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;",
                    onclick="return confirm('Сгенерировать валютные инвойсы для этой сделки?')"
                ),
                method="post",
                action=f"/finance/{deal_id}/generate-currency-invoices"
            ),
            style="text-align: center; padding: 40px 20px;"
        )

    return Div(
        Div(
            icon("file-text", size=14, color="#64748b"),
            Span("ВАЛЮТНЫЕ ИНВОЙСЫ", style="margin-left: 6px;"),
            style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
        ),
        invoices_table,
        style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; margin-bottom: 24px;"
    )


def _logistics_expenses_total_el(grand_total_usd, oob=False):
    """Reusable total element with stable id for OOB swap."""
    kwargs = {"id": "logistics-expenses-total", "style": "margin-top: 4px;"}
    if oob:
        kwargs["hx_swap_oob"] = "true"
    return Div(
        Span("Итого (USD): ", style="font-size: 13px; color: #64748b;"),
        Span(f"${float(grand_total_usd):,.2f}", style="font-size: 18px; font-weight: 700; color: #1e293b;"),
        **kwargs
    )


def _finance_logistics_expenses_tab_content(deal_id: str, org_id: str, session) -> object:
    """
    Render 'Расходы логистики' tab.
    Groups expenses by route segment (logistics stage).
    Each segment card has an 'Добавить расход' button that loads an inline HTMX form.
    """
    from services.logistics_service import get_stages_for_deal, STAGE_NAMES, stage_allows_expenses, initialize_logistics_stages
    from services.logistics_expense_service import (
        get_expenses_for_deal, EXPENSE_SUBTYPE_LABELS, get_deal_logistics_summary
    )

    stages = get_stages_for_deal(deal_id)

    # Auto-initialize stages if none exist (deals created before auto-init was added)
    if not stages:
        user = session.get("user", {})
        user_id = user.get("id", "")
        try:
            stages = initialize_logistics_stages(deal_id, user_id)
        except Exception:
            pass

    if not stages:
        return Div(
            Div(
                icon("alert-circle", size=24, color="#f59e0b"),
                H3("Этапы логистики не созданы", style="margin: 8px 0 4px; color: #1e293b;"),
                P("Не удалось инициализировать этапы логистики для этой сделки.",
                  style="color: #64748b; font-size: 13px;"),
                style="text-align: center; padding: 40px;"
            ),
            style="background: white; border-radius: 10px; border: 1px solid #e2e8f0;"
        )
    all_expenses = get_expenses_for_deal(deal_id)

    # Group expenses by stage_id for O(1) lookup
    expenses_by_stage: dict = {}
    for exp in all_expenses:
        sid = exp.logistics_stage_id
        if sid not in expenses_by_stage:
            expenses_by_stage[sid] = []
        expenses_by_stage[sid].append(exp)

    summary = get_deal_logistics_summary(deal_id)
    grand_total_usd = summary.get("grand_total_usd", 0)

    # Header summary
    header = Div(
        Div(
            icon("dollar-sign", size=14, color="#64748b"),
            Span("ФАКТИЧЕСКИЕ РАСХОДЫ НА ЛОГИСТИКУ", style="margin-left: 6px;"),
            style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; display: flex; align-items: center;"
        ),
        _logistics_expenses_total_el(grand_total_usd),
        style="margin-bottom: 20px;"
    )

    # One card per stage
    stage_sections = []
    for stage in stages:
        if not stage_allows_expenses(stage.stage_code):
            continue  # skip gtd_upload
        stage_expenses = expenses_by_stage.get(stage.id, [])
        stage_name = STAGE_NAMES.get(stage.stage_code, stage.stage_code)
        stage_summary = summary.get(stage.stage_code, {})
        stage_total_usd = stage_summary.get("total_usd", 0) if isinstance(stage_summary, dict) else 0

        # Expense rows table
        expense_rows = []
        for exp in stage_expenses:
            subtype_label = EXPENSE_SUBTYPE_LABELS.get(exp.expense_subtype, exp.expense_subtype)
            amount_fmt = f"{float(exp.amount):,.2f} {exp.currency}"
            date_fmt = exp.expense_date.strftime("%d.%m.%Y") if exp.expense_date else "—"
            doc_link = ""
            if exp.document_id:
                doc_link = A(
                    icon("paperclip", size=12),
                    href=f"/documents/{exp.document_id}/download",
                    style="color: #3b82f6; margin-left: 4px;",
                    target="_blank"
                )
            expense_rows.append(
                Tr(
                    Td(date_fmt, style="padding: 8px 12px; font-size: 13px; color: #374151;"),
                    Td(subtype_label, style="padding: 8px 12px; font-size: 13px; color: #374151;"),
                    Td(amount_fmt, style="padding: 8px 12px; font-size: 13px; font-weight: 500; text-align: right;"),
                    Td(exp.description or "—", style="padding: 8px 12px; font-size: 12px; color: #64748b;"),
                    Td(doc_link, style="padding: 8px 12px; text-align: center;"),
                    Td(
                        Button(
                            icon("trash-2", size=12),
                            hx_delete=f"/finance/{deal_id}/logistics-expenses/{exp.id}",
                            hx_target=f"#stage-expenses-{stage.id}",
                            hx_swap="outerHTML",
                            hx_confirm="Удалить расход?",
                            style="background: none; border: none; cursor: pointer; color: #ef4444; padding: 2px 4px;"
                        ),
                        style="padding: 8px 12px; text-align: center;"
                    ),
                    style="border-bottom: 1px solid #f1f5f9;"
                )
            )

        expenses_table = ""
        if expense_rows:
            expenses_table = Table(
                Thead(Tr(
                    Th("Дата", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: left;"),
                    Th("Тип", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: left;"),
                    Th("Сумма", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: right;"),
                    Th("Описание", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: left;"),
                    Th("Файл", style="padding: 8px 12px; font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; background: #f8fafc; text-align: center;"),
                    Th("", style="padding: 8px 12px; background: #f8fafc;"),
                )),
                Tbody(*expense_rows),
                style="width: 100%; border-collapse: collapse;"
            )

        stage_total_display = Div(
            Span(f"Итого по этапу: ", style="font-size: 12px; color: #64748b;"),
            Span(f"${float(stage_total_usd):,.2f}", style="font-size: 14px; font-weight: 600; color: #1e293b;"),
            style="margin-bottom: 8px;"
        ) if stage_expenses else ""

        add_btn = Button(
            icon("plus", size=12),
            " Добавить расход",
            hx_get=f"/finance/{deal_id}/logistics-expenses/new-form?stage_id={stage.id}",
            hx_target=f"#expense-form-{stage.id}",
            hx_swap="innerHTML",
            style="background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 5px;"
        )

        # The section div gets id for HTMX targeting on delete + re-render
        stage_section = Div(
            Div(
                Span(stage_name, style="font-weight: 600; font-size: 14px; color: #1e293b;"),
                add_btn,
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;"
            ),
            Div(id=f"expense-form-{stage.id}"),  # HTMX target for inline form
            stage_total_display,
            expenses_table if expense_rows else P("Нет расходов", style="color: #94a3b8; font-size: 13px;"),
            id=f"stage-expenses-{stage.id}",
            style="background: white; border-radius: 10px; padding: 16px; border: 1px solid #e2e8f0; margin-bottom: 16px;"
        )
        stage_sections.append(stage_section)

    return Div(
        header,
        *stage_sections,
        style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; margin-bottom: 24px;"
    )


def _finance_payment_modal(deal_id):
    """Render the payment modal overlay (hidden by default, populated via HTMX)."""
    modal_css = """
        #deal-payment-modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        #deal-payment-modal .modal-content {
            background: white;
            border-radius: 12px;
            padding: 24px;
            max-width: 520px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
    """
    payment_modal = Div(
        Div(
            Div(
                Div(
                    H3("Регистрация платежа", style="margin: 0; font-size: 16px; font-weight: 600; color: #1e293b;"),
                    Button(
                        icon("x", size=16),
                        onclick="document.getElementById('deal-payment-modal').style.display='none';",
                        style="background: none; border: none; cursor: pointer; color: #64748b; padding: 4px;"
                    ),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;"
                ),
                Div(id="deal-payment-modal-body"),
                cls="modal-content"
            ),
            onclick="if(event.target===this) this.style.display='none';",
            style="display: flex; justify-content: center; align-items: center; width: 100%; height: 100%;"
        ),
        id="deal-payment-modal",
    )
    return Style(modal_css), payment_modal


def _deals_logistics_tab(deal_id, deal, session):
    """Render the logistics tab content with compact horizontal stage cards."""
    stages = get_stages_for_deal(deal_id)

    if not stages:
        return Div(
            P("Этапы логистики не инициализированы.", style="color: #64748b;"),
            style="padding: 20px; text-align: center;"
        )

    stage_cards = []
    for stage in stages:
        code = stage.stage_code
        stage_name = STAGE_NAMES.get(code, code)
        status = stage.status
        allows_exp = stage_allows_expenses(code)

        # Status badge
        status_styles = {
            'pending': ('Ожидает', '#f59e0b', '#fef3c7'),
            'in_progress': ('В работе', '#3b82f6', '#dbeafe'),
            'completed': ('Завершён', '#10b981', '#d1fae5'),
        }
        label, color, bg = status_styles.get(status, ('?', '#6b7280', '#f1f5f9'))
        status_badge = Span(label, style=f"background: {bg}; color: {color}; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;")

        # Expense summary (compact: count + total)
        summary = get_stage_summary(stage.id)
        expense_info = ""
        if allows_exp and summary.get('expense_count', 0) > 0:
            expense_info = Div(
                Span(f"{summary['expense_count']} расх.", style="color: #64748b; font-size: 11px;"),
                Span(f"{summary['total_planned']:,.0f}", style="color: #374151; font-size: 11px; font-weight: 500; margin-left: 4px;"),
                style="margin-top: 6px;"
            )

        # Status update button
        status_form = ""
        if status != 'completed':
            next_status = 'in_progress' if status == 'pending' else 'completed'
            next_label = 'Начать' if next_status == 'in_progress' else 'Завершить'
            status_form = Form(
                Input(type="hidden", name="status", value=next_status),
                Button(next_label, type="submit",
                       style="padding: 3px 10px; font-size: 10px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; width: 100%;"),
                method="post",
                action=f"/finance/{deal_id}/stages/{stage.id}/status",
            )

        # Button to add expense via payment modal
        add_expense_btn = ""
        if allows_exp:
            add_expense_btn = Button(
                icon("plus", size=10),
                " Расход",
                hx_get=f"/finance/{deal_id}/payments/new?stage_id={stage.id}",
                hx_target="#deal-payment-modal-body",
                hx_swap="innerHTML",
                onclick="document.getElementById('deal-payment-modal').style.display='flex';",
                style="padding: 3px 8px; font-size: 10px; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; border: none; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 3px; width: 100%;"
            )

        # Build card with compact vertical layout
        card = Div(
            # Header: stage name
            Div(stage_name, style="font-weight: 600; font-size: 13px; margin-bottom: 4px;"),
            # Status badge
            Div(status_badge, style="margin-bottom: 4px;"),
            # Expense summary
            expense_info if expense_info else "",
            # Action buttons
            Div(
                status_form if status_form else "",
                add_expense_btn if add_expense_btn else "",
                style="display: flex; flex-direction: column; gap: 4px; margin-top: auto;"
            ) if status_form or add_expense_btn else "",
            style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; min-height: 120px; display: flex; flex-direction: column;"
        )
        stage_cards.append(card)

    return Div(
        *stage_cards,
        style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px;"
    )




# ============================================================================
# CURRENCY INVOICE SEGMENT BADGE
# Shared helper used by _render_currency_invoices_section (/quotes/documents)
# and _finance_currency_invoices_tab_content (/finance/{deal_id}).
# The /currency-invoices/* area itself was archived in Phase 6C-2B-8.
# ============================================================================

def _ci_segment_badge(segment):
    """Return a styled Span badge for currency invoice segment."""
    colors = {
        "EURTR": "background: #ede9fe; color: #5b21b6;",
        "TRRU": "background: #fce7f3; color: #9d174d;",
    }
    style = colors.get(segment, "background: #f1f5f9; color: #475569;")
    return Span(segment or "—", style=f"padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; letter-spacing: 0.05em; {style}")


# NOTE: /currency-invoices/* routes (registry, detail, edit, verify, download-docx,
# download-pdf, regenerate) + helpers (_ci_get_company_options,
# _ci_current_entity_value, _fetch_ci_for_download, _resolve_company_details,
# _convert_docx_to_pdf) archived to legacy-fasthtml/currency_invoices.py
# during Phase 6C-2B-8 (2026-04-20). Superseded by Next.js currency-invoice flows.


# ============================================================================
# CALLS REGISTRY — [archived to legacy-fasthtml/calls_documents_contracts.py in Phase 6C-2B-10a]
# Route moved: /calls GET. Superseded by Next.js (pending).
# services/call_service.py remains alive, consumed by /customers/{id}/calls.
# ============================================================================


# --- Composition + Procurement-unlock JSON API (Phase 5b / Phase 6B-4) ---
# GET    /api/quotes/{quote_id}/composition                                     → api/routers/quotes.py (mounted FastAPI)
# POST   /api/quotes/{quote_id}/composition                                     → api/routers/quotes.py
# POST   /api/invoices/{invoice_id}/verify                                      → api/routers/invoices.py
# POST   /api/invoices/{id}/procurement-unlock-approval/{approval_id}/approve   → api/routers/invoices.py
# POST   /api/invoices/{id}/procurement-unlock-approval/{approval_id}/reject    → api/routers/invoices.py


# --- Admin User Management JSON API ---
# POST   /api/admin/users                 → api/routers/admin.py (mounted FastAPI)
# PATCH  /api/admin/users/{user_id}/roles → api/routers/admin.py (mounted FastAPI)
# PATCH  /api/admin/users/{user_id}       → api/routers/admin.py (mounted FastAPI)


# --- VAT Rate JSON API (for Next.js frontend) ---
# GET /api/geo/vat-rate  → api/routers/geo.py (mounted FastAPI)
# PUT /api/admin/vat-rates → api/routers/admin.py (mounted FastAPI)


# --- Procurement Kanban + Sub-Status JSON API (Phase 6B-4) ---
# GET  /api/quotes/kanban                          → api/routers/quotes.py (mounted FastAPI)
# POST /api/quotes/{quote_id}/substatus            → api/routers/quotes.py
# GET  /api/quotes/{quote_id}/status-history       → api/routers/quotes.py


# --- Soft-delete / restore JSON API (Phase 6B-5) ---
# POST /api/quotes/{quote_id}/soft-delete → api/routers/quotes.py (mounted FastAPI)
# POST /api/quotes/{quote_id}/restore     → api/routers/quotes.py (mounted FastAPI)


# --- Cron JSON API (for scheduled background tasks) ---
# GET /api/cron/check-overdue → api/routers/cron.py (mounted FastAPI)


# ============================================================================
# QUOTE CHAT TAB (Comments)
# ============================================================================

def _render_comment_bubble(comment, current_user_id):
    """Render a single chat message bubble."""
    is_own = comment.get("user_id") == current_user_id
    author_name = comment.get("author_name", "Unknown")
    body_raw = comment.get("body", "")
    created_at = comment.get("created_at", "")

    # HTML-escape body BEFORE applying @mention highlighting
    body_escaped = html_mod.escape(body_raw)

    # Highlight @mentions in the escaped body
    import re
    body_html = re.sub(
        r'(@\w+)',
        r'<span style="color: #3b82f6; font-weight: 600;">\1</span>',
        body_escaped
    )

    # Format timestamp
    time_display = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            time_display = dt.strftime("%H:%M")
        except Exception:
            time_display = created_at[:16]

    # Bubble alignment and style
    if is_own:
        bubble_style = """
            background: #dbeafe; border-radius: 12px 12px 4px 12px;
            padding: 0.75rem 1rem; max-width: 75%; margin-left: auto;
            margin-bottom: 0.5rem;
        """
        name_style = "font-size: 0.75rem; font-weight: 600; color: #2563eb; margin-bottom: 0.25rem;"
    else:
        bubble_style = """
            background: #f3f4f6; border-radius: 12px 12px 12px 4px;
            padding: 0.75rem 1rem; max-width: 75%;
            margin-bottom: 0.5rem;
        """
        name_style = "font-size: 0.75rem; font-weight: 600; color: #6b7280; margin-bottom: 0.25rem;"

    return Div(
        Div(author_name, style=name_style),
        Div(NotStr(body_html), style="font-size: 0.9rem; line-height: 1.4; color: #1f2937;"),
        Div(time_display, style="font-size: 0.7rem; color: #9ca3af; text-align: right; margin-top: 0.25rem;"),
        style=bubble_style,
        cls="chat-bubble"
    )


def _render_chat_tab(quote_id, comments, org_users, current_user_id):
    """Render the full chat tab content with messages, input form, and @mention dropdown."""

    # Messages area
    message_elements = []
    for comment in comments:
        message_elements.append(_render_comment_bubble(comment, current_user_id))

    if not message_elements:
        message_elements.append(
            Div(
                icon("message-circle", size=48, color="#d1d5db"),
                P("Нет сообщений", style="color: #9ca3af; margin-top: 0.5rem;"),
                P("Напишите первое сообщение в чат КП", style="color: #d1d5db; font-size: 0.85rem;"),
                id="chat-empty-state",
                style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 3rem;"
            )
        )

    messages_area = Div(
        *message_elements,
        id="chat-messages",
        style="flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; min-height: 300px; max-height: 500px;"
    )

    # Input form
    input_form = Form(
        Div(
            Textarea(
                name="body",
                placeholder="Написать сообщение...",
                id="chat-input",
                rows="2",
                style="flex: 1; border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.75rem; font-size: 0.9rem; resize: none; outline: none;",
            ),
            Input(type="hidden", name="mentions_json", id="mentions-json-input", value=""),
            Button(
                icon("send", size=18),
                type="submit",
                style="background: #3b82f6; color: white; border: none; border-radius: 8px; padding: 0.5rem 1rem; cursor: pointer; display: flex; align-items: center; gap: 0.25rem;",
            ),
            style="display: flex; gap: 0.5rem; align-items: flex-end;"
        ),
        hx_post=f"/quotes/{quote_id}/comments",
        hx_target="#chat-messages",
        hx_swap="beforeend",
        hx_on__after_request="this.querySelector('#chat-input').value = ''; this.querySelector('#mentions-json-input').value = ''; document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;",
        style="padding: 1rem; border-top: 1px solid #e5e7eb;",
    )

    # Chat container
    return Div(
        Div(
            H3(
                icon("message-circle", size=20),
                " Чат по КП",
                style="display: flex; align-items: center; gap: 0.5rem; margin: 0; font-size: 1.1rem;"
            ),
            style="padding: 1rem; border-bottom: 1px solid #e5e7eb;"
        ),
        messages_area,
        input_form,
        Script(f"""
            // Auto-scroll to bottom on page load
            (function() {{
                var el = document.getElementById('chat-messages');
                if (el) el.scrollTop = el.scrollHeight;
            }})();
        """),
        cls="card",
        style="display: flex; flex-direction: column; border-radius: 12px; overflow: hidden; margin-bottom: 1.5rem;"
    )


@rt("/quotes/{quote_id}/chat")
def get(quote_id: str, session):
    """View chat tab for a quote."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user["org_id"]
    user_id = user["id"]
    user_roles = get_session_user_roles(session)

    supabase = get_supabase()

    # Get quote details
    quote_result = supabase.table("quotes") \
        .select("id, idn_quote, customer_id, status, workflow_status, customers!customer_id(name)") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return page_layout("КП не найдено",
            H1("КП не найдено"),
            Div("Запрошенное КП не существует или у вас нет доступа.", cls="card"),
            A("← К списку КП", href="/quotes"),
            session=session
        )

    quote = quote_result.data[0]
    quote_number = quote.get("idn_quote") or quote_id[:8]
    workflow_status = quote.get("workflow_status") or quote.get("status", "draft")

    # Get customer name
    customer_name = (quote.get("customers") or {}).get("name", "—")

    # Import and use comment service
    from services.comment_service import get_comments_for_quote, mark_as_read, get_org_users_for_mentions

    # Mark as read when user opens chat
    mark_as_read(quote_id=quote_id, user_id=user_id)

    # Fetch comments and org users
    comments = get_comments_for_quote(quote_id)
    org_users = get_org_users_for_mentions(org_id)

    return page_layout(
        f"Чат КП {quote_number}",

        # Persistent header
        quote_header(quote, workflow_status, customer_name),

        # Role-based tabs -- chat_unread=0 because we just marked as read
        quote_detail_tabs(quote_id, "chat", user_roles, chat_unread=0),

        # Chat content
        _render_chat_tab(quote_id, comments, org_users, user_id),

        # Back button
        Div(
            A(icon("arrow-left", size=16), " К обзору КП", href=f"/quotes/{quote_id}",
              style="display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text-secondary); text-decoration: none;"),
            style="margin-top: 2rem;"
        ),

        session=session
    )


@rt("/quotes/{quote_id}/comments")
def post(session, quote_id: str, body: str = "", mentions_json: str = ""):
    """Post a new comment to a quote's chat."""
    redirect = require_login(session)
    if redirect:
        return Response("Unauthorized", status_code=401)

    user = session["user"]
    org_id = user["org_id"]
    user_id = user["id"]

    # Validate body not empty
    if not body or not body.strip():
        return Response(status_code=204)

    # Verify quote belongs to org
    supabase = get_supabase()
    quote_result = supabase.table("quotes") \
        .select("id") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .is_("deleted_at", None) \
        .execute()

    if not quote_result.data:
        return Response("Quote not found", status_code=404)

    # Parse mentions
    mentions = []
    if mentions_json:
        try:
            mentions = json.loads(mentions_json)
            if not isinstance(mentions, list):
                mentions = []
        except (json.JSONDecodeError, TypeError):
            mentions = []

    # Create comment
    from services.comment_service import create_comment
    created = create_comment(
        quote_id=quote_id,
        user_id=user_id,
        body=body.strip(),
        mentions=mentions,
    )

    if not created:
        return Response("Error creating comment", status_code=500)

    # Enrich the created comment for rendering
    try:
        profile_result = supabase.table("user_profiles") \
            .select("full_name") \
            .eq("user_id", user_id) \
            .execute()
        author_name = (profile_result.data[0].get("full_name") if profile_result.data else None) or user_id[:8]
    except Exception:
        author_name = user_id[:8]

    created["author_name"] = author_name
    created["user_id"] = user_id

    # Render the new bubble
    bubble = _render_comment_bubble(created, user_id)

    # OOB: remove empty state placeholder when first message is sent
    empty_state_remove = Div(id="chat-empty-state", hx_swap_oob="outerHTML", style="display:none;")

    return Div(bubble, empty_state_remove)


# ============================================================================
# CHANGELOG PAGE — [archived to legacy-fasthtml/approvals_changelog_telegram.py in Phase 6C-2B-6]
# Route moved: /changelog GET. Superseded by Next.js /changelog reading /api/changelog.
# ============================================================================


# ============================================================================
# TELEGRAM CONNECTION PAGE — [archived to legacy-fasthtml/approvals_changelog_telegram.py in Phase 6C-2B-6]
# Routes moved: /telegram GET, /telegram/generate-code POST, /telegram/disconnect POST, /telegram/status GET.
# Helper moved: _telegram_status_fragment. Superseded by Next.js /settings/telegram via /api/integrations/*.
# ============================================================================


# === API: Health check (for Next.js frontend) ===
# GET /api/health is served by api.routers.public via the /api mount.


# ============================================================================
# FASTAPI SUB-APP MOUNT (Phase 6B onwards)
# ============================================================================
# Mount AFTER all legacy @rt("/api/...") handlers. Starlette matches routes in
# declaration order, so specific @rt("/api/...") routes above resolve first,
# and any /api/* path not handled by an @rt route falls through to the mount.
# As endpoints migrate to FastAPI, their @rt registrations are removed and the
# sub-app takes over transparently. Once all endpoints are migrated, this mount
# becomes the sole handler for /api/*.
from api.app import api_app
app.mount("/api", api_app)


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Kvota OneStack - FastHTML + Supabase")
    print("="*50)
    print("  URL: http://localhost:5001")
    print("  Using real Supabase database")
    print("="*50 + "\n")

    serve(port=5001)
