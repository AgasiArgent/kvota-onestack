"""
Kvota OneStack - FastHTML + Supabase

A single-language (Python) quotation platform.
Run with: python main.py
"""

from fasthtml.common import *
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
import os
import json
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

from services.database import get_supabase

# Import export services
from services.export_data_mapper import format_date_russian

# Import role service
from services.role_service import get_user_role_codes

# Import workflow service for status display
from services.workflow_service import (
    WorkflowStatus, STATUS_NAMES_SHORT,
    get_quote_transition_history,
)

# Import approval service (Feature #65, #86)
from services.approval_service import count_pending_approvals

from services.logistics_service import (
    get_stages_for_deal, get_stage_summary, stage_allows_expenses,
    STAGE_NAMES,
)
from services.plan_fact_service import get_categories_for_role

# Import calculation engine — build_calculation_inputs (defined in this file)
# uses these symbols and is imported by api/quotes.py for the FastAPI
# calculate endpoint. DO NOT REMOVE without adjusting api/quotes.py.
from calculation_mapper import map_variables_to_calculation_input, safe_decimal
from calculation_models import QuoteCalculationInput

# Import document service for file uploads — used by _quote_documents_section
# (preserved) and _finance_logistics_expenses_tab_content (preserved).
from services.document_service import (
    get_file_icon, format_file_size,
    get_allowed_document_types_for_entity,
    get_all_documents_for_quote,
    get_entity_type_label,
    get_document_type_label,
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
# COST ANALYSIS (КА) DASHBOARD — [archived to legacy-fasthtml/cost_analysis.py in Phase 6C-2B Mega-F]
# Route moved: @app.get /quotes/{quote_id}/cost-analysis (full P&L waterfall handler).
# Route deleted: @app.get /quotes/{quote_id}/cost-analysis-json (501 stub — no functionality).
# Superseded by FastAPI GET /api/quotes/{quote_id}/cost-analysis
# + Next.js /quotes/[id]/cost-analysis page (PR #50).
# ============================================================================


# ============================================================================
# ADMIN CLUSTER — [archived to legacy-fasthtml/admin_cluster.py in Phase 6C-2B Mega-E]
# Routes moved (25): /admin + /admin/users, /admin/feedback + 3 sub-routes,
# /admin/users/{user_id}/roles (5 variants), /admin/brands + 5 sub-routes,
# /admin/procurement-groups + 5 sub-routes, /admin/impersonate + /exit.
# Module-level constants moved: STATUS_LABELS, FEEDBACK_TYPE_LABELS_RU,
# VALID_IMPERSONATION_ROLES. Superseded by Next.js /admin + /api/admin/*.
# ============================================================================


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
