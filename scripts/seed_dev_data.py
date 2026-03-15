#!/usr/bin/env python3
"""
Seed development data for local PostgreSQL.

Creates organizations, users, roles, customers, quotes at various stages,
and supporting reference data. Idempotent — safe to run multiple times.

Can be run standalone or called from setup_local_db.py.

Usage:
    python scripts/seed_dev_data.py
"""

import os
import sys
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path

from dotenv import load_dotenv

env_dev = Path(__file__).parent.parent / ".env.dev"
if env_dev.exists():
    load_dotenv(env_dev)
else:
    load_dotenv()


# ============================================================================
# Fixed UUIDs for deterministic seeding (idempotency)
# ============================================================================

ORG_ID = "a0000000-0000-0000-0000-000000000001"

USER_ADMIN = "b0000000-0000-0000-0000-000000000001"
USER_SALES = "b0000000-0000-0000-0000-000000000002"
USER_PROCUREMENT = "b0000000-0000-0000-0000-000000000003"
USER_LOGISTICS = "b0000000-0000-0000-0000-000000000004"
USER_CUSTOMS = "b0000000-0000-0000-0000-000000000005"
USER_FINANCE = "b0000000-0000-0000-0000-000000000006"
USER_QC = "b0000000-0000-0000-0000-000000000007"
USER_SC = "b0000000-0000-0000-0000-000000000008"
USER_TOP = "b0000000-0000-0000-0000-000000000009"

CUSTOMER_1 = "c0000000-0000-0000-0000-000000000001"
CUSTOMER_2 = "c0000000-0000-0000-0000-000000000002"
CUSTOMER_3 = "c0000000-0000-0000-0000-000000000003"

SELLER_CO_1 = "d0000000-0000-0000-0000-000000000001"
SELLER_CO_2 = "d0000000-0000-0000-0000-000000000002"

QUOTE_DRAFT_1 = "e0000000-0000-0000-0000-000000000001"
QUOTE_DRAFT_2 = "e0000000-0000-0000-0000-000000000002"
QUOTE_PROCUREMENT = "e0000000-0000-0000-0000-000000000003"
QUOTE_CONTROL = "e0000000-0000-0000-0000-000000000004"
QUOTE_APPROVED = "e0000000-0000-0000-0000-000000000005"
QUOTE_SPEC = "e0000000-0000-0000-0000-000000000006"
QUOTE_DEAL = "e0000000-0000-0000-0000-000000000007"

SPEC_1 = "f0000000-0000-0000-0000-000000000001"
SPEC_2 = "f0000000-0000-0000-0000-000000000002"

DEAL_1 = "f1000000-0000-0000-0000-000000000001"


# ============================================================================
# Helpers
# ============================================================================

def upsert(cur, table, data, conflict_column="id"):
    """Insert or skip on conflict."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON CONFLICT ({conflict_column}) DO NOTHING"
    cur.execute(sql, list(data.values()))


def now_iso():
    return datetime.now().isoformat()


# ============================================================================
# Seed functions
# ============================================================================

def seed_organization(cur):
    """Create test organization."""
    print("  Seeding organization...")
    upsert(cur, "kvota.organizations", {
        "id": ORG_ID,
        "name": "ООО Тест Трейд",
        "created_at": now_iso(),
    })


def seed_roles(cur):
    """Create standard roles."""
    print("  Seeding roles...")
    roles = [
        ("sales", "Менеджер по продажам", "Создание и ведение КП, работа с клиентами"),
        ("procurement", "Менеджер по закупкам", "Оценка закупочных цен по брендам"),
        ("logistics", "Логист", "Расчёт стоимости и сроков доставки"),
        ("customs", "Менеджер ТО", "Таможенное оформление, коды ТН ВЭД, пошлины"),
        ("quote_controller", "Контроллер КП", "Проверка КП перед отправкой клиенту"),
        ("spec_controller", "Контроллер спецификаций", "Подготовка и проверка спецификаций"),
        ("finance", "Финансовый менеджер", "Ведение план-факта по сделкам"),
        ("top_manager", "Топ-менеджер", "Согласование и отчётность"),
        ("admin", "Администратор", "Управление пользователями и настройками"),
        ("head_of_sales", "Руководитель отдела продаж", "Руководство продажами"),
        ("head_of_procurement", "Руководитель отдела закупок", "Руководство закупками"),
        ("head_of_logistics", "Руководитель отдела логистики", "Руководство логистикой"),
        ("head_of_finance", "Руководитель отдела финансов", "Руководство финансами"),
        ("training_manager", "Менеджер обучения", "Просмотр всех разделов для обучения"),
        ("currency_controller", "Контролёр валютных документов", "Проверка валютных инвойсов"),
    ]

    for slug, name, desc in roles:
        cur.execute("""
            INSERT INTO kvota.roles (organization_id, slug, name, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (ORG_ID, slug, name, desc))


def seed_users_and_memberships(cur):
    """Create dev users with org memberships and role assignments."""
    print("  Seeding users and role assignments...")

    users = [
        (USER_ADMIN, "admin", "Админов Алексей"),
        (USER_SALES, "sales", "Продажин Сергей"),
        (USER_PROCUREMENT, "procurement", "Закупкина Ольга"),
        (USER_LOGISTICS, "logistics", "Логистов Дмитрий"),
        (USER_CUSTOMS, "customs", "Таможенко Анна"),
        (USER_FINANCE, "finance", "Финансова Мария"),
        (USER_QC, "quote_controller", "Контролёров Иван"),
        (USER_SC, "spec_controller", "Спеконтролева Елена"),
        (USER_TOP, "top_manager", "Директоров Петр"),
    ]

    for user_id, role_slug, full_name in users:
        # Organization membership
        cur.execute("""
            INSERT INTO kvota.organization_members (user_id, organization_id, status, is_owner)
            VALUES (%s, %s, 'active', %s)
            ON CONFLICT (user_id, organization_id) DO NOTHING
        """, (user_id, ORG_ID, role_slug == "admin"))

        # Role assignment
        cur.execute("""
            INSERT INTO kvota.user_roles (user_id, organization_id, role_id)
            SELECT %s, %s, r.id
            FROM kvota.roles r
            WHERE r.slug = %s AND r.organization_id = %s
            ON CONFLICT DO NOTHING
        """, (user_id, ORG_ID, role_slug, ORG_ID))

        # User profile (table may not exist depending on migration state)
        try:
            cur.execute("SAVEPOINT sp_profile")
            cur.execute("""
                INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, ORG_ID, full_name, role_slug))
            cur.execute("RELEASE SAVEPOINT sp_profile")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT sp_profile")


def seed_customers(cur):
    """Create test customers."""
    print("  Seeding customers...")

    customers = [
        {
            "id": CUSTOMER_1,
            "name": "ООО МашСервис",
            "organization_id": ORG_ID,
            "inn": "7701234567",
            "email": "zakup@mashservis.ru",
            "phone": "+7 (495) 123-45-67",
            "order_source": "Входящий звонок",
        },
        {
            "id": CUSTOMER_2,
            "name": "АО ПромТехника",
            "organization_id": ORG_ID,
            "inn": "7707654321",
            "email": "supply@promteh.ru",
            "phone": "+7 (495) 987-65-43",
            "order_source": "Тендер",
        },
        {
            "id": CUSTOMER_3,
            "name": "ИП Кузнецов А.В.",
            "organization_id": ORG_ID,
            "inn": "770300112233",
            "email": "kuznecov@mail.ru",
            "phone": "+7 (916) 555-33-22",
            "order_source": "Рекомендация",
        },
    ]

    for c in customers:
        c["created_at"] = now_iso()
        upsert(cur, "kvota.customers", c)


def seed_seller_companies(cur):
    """Create seller companies (our legal entities for selling)."""
    print("  Seeding seller companies...")

    try:
        cur.execute("SAVEPOINT sp_seller")
        upsert(cur, "kvota.seller_companies", {
            "id": SELLER_CO_1,
            "organization_id": ORG_ID,
            "name": 'ООО "Тест Трейд"',
            "company_code": "TT",
            "inn": "7712345678",
            "kpp": "771201001",
            "country": "Россия",
        })
        upsert(cur, "kvota.seller_companies", {
            "id": SELLER_CO_2,
            "organization_id": ORG_ID,
            "name": 'ООО "Тест Логистикс"',
            "company_code": "TL",
            "inn": "7787654321",
            "kpp": "778701001",
            "country": "Россия",
        })
        cur.execute("RELEASE SAVEPOINT sp_seller")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_seller")
        print("    (seller_companies table not yet created, skipping)")


def seed_quotes(cur):
    """Create quotes at various workflow stages."""
    print("  Seeding quotes...")

    base_date = date.today() - timedelta(days=30)

    quotes = [
        # Draft quotes (early stage)
        {
            "id": QUOTE_DRAFT_1,
            "idn_quote": "2603-0001",
            "title": "КП подшипники SKF",
            "customer_id": CUSTOMER_1,
            "organization_id": ORG_ID,
            "currency": "RUB",
            "delivery_terms": "DDP",
            "delivery_city": "Москва",
            "delivery_country": "Россия",
            "status": "draft",
            "workflow_status": "draft",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=1)).isoformat(),
        },
        {
            "id": QUOTE_DRAFT_2,
            "idn_quote": "2603-0002",
            "title": "КП ремни приводные",
            "customer_id": CUSTOMER_3,
            "organization_id": ORG_ID,
            "currency": "USD",
            "delivery_terms": "CIP",
            "delivery_city": "Екатеринбург",
            "delivery_country": "Россия",
            "status": "draft",
            "workflow_status": "draft",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=3)).isoformat(),
        },
        # In procurement
        {
            "id": QUOTE_PROCUREMENT,
            "idn_quote": "2603-0003",
            "title": "КП муфты FAG",
            "customer_id": CUSTOMER_1,
            "organization_id": ORG_ID,
            "currency": "EUR",
            "delivery_terms": "DDP",
            "delivery_city": "Санкт-Петербург",
            "delivery_country": "Россия",
            "status": "draft",
            "workflow_status": "pending_procurement",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=5)).isoformat(),
        },
        # In control
        {
            "id": QUOTE_CONTROL,
            "idn_quote": "2603-0004",
            "title": "КП уплотнения Garlock",
            "customer_id": CUSTOMER_2,
            "organization_id": ORG_ID,
            "currency": "RUB",
            "delivery_terms": "DDP",
            "delivery_city": "Новосибирск",
            "delivery_country": "Россия",
            "status": "draft",
            "workflow_status": "pending_quote_control",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=10)).isoformat(),
        },
        # Approved (ready for specification)
        {
            "id": QUOTE_APPROVED,
            "idn_quote": "2603-0005",
            "title": "КП цепи Renold",
            "customer_id": CUSTOMER_2,
            "organization_id": ORG_ID,
            "currency": "RUB",
            "delivery_terms": "DDP",
            "delivery_city": "Москва",
            "delivery_country": "Россия",
            "status": "approved",
            "workflow_status": "approved",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=12)).isoformat(),
        },
        # Has specification
        {
            "id": QUOTE_SPEC,
            "idn_quote": "2603-0006",
            "title": "КП электродвигатели ABB",
            "customer_id": CUSTOMER_1,
            "organization_id": ORG_ID,
            "currency": "RUB",
            "delivery_terms": "DDP",
            "delivery_city": "Москва",
            "delivery_country": "Россия",
            "status": "approved",
            "workflow_status": "specification",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=15)).isoformat(),
        },
        # Has deal
        {
            "id": QUOTE_DEAL,
            "idn_quote": "2603-0007",
            "title": "КП фильтры Donaldson",
            "customer_id": CUSTOMER_3,
            "organization_id": ORG_ID,
            "currency": "RUB",
            "delivery_terms": "DDP",
            "delivery_city": "Казань",
            "delivery_country": "Россия",
            "status": "approved",
            "workflow_status": "deal",
            "created_by": USER_SALES,
            "created_at": (base_date + timedelta(days=20)).isoformat(),
        },
    ]

    for q in quotes:
        upsert(cur, "kvota.quotes", q)


def seed_quote_items(cur):
    """Create quote line items."""
    print("  Seeding quote items...")

    items = [
        # Draft quote 1 items
        {
            "id": str(uuid.UUID(int=1001)),
            "quote_id": QUOTE_DRAFT_1,
            "sku": "SKF-6205-2RS",
            "description": "Подшипник шариковый SKF 6205 2RS",
            "brand": "SKF",
            "quantity": 50,
            "base_price": 450.00,
            "base_price_vat": 540.00,
            "currency": "RUB",
        },
        {
            "id": str(uuid.UUID(int=1002)),
            "quote_id": QUOTE_DRAFT_1,
            "sku": "SKF-6310-2Z",
            "description": "Подшипник шариковый SKF 6310 2Z",
            "brand": "SKF",
            "quantity": 20,
            "base_price": 1200.00,
            "base_price_vat": 1440.00,
            "currency": "RUB",
        },
        # Procurement quote items (with procurement data)
        {
            "id": str(uuid.UUID(int=1003)),
            "quote_id": QUOTE_PROCUREMENT,
            "sku": "FAG-23220-E1",
            "description": "Муфта упругая FAG 23220 E1",
            "brand": "FAG",
            "quantity": 5,
            "base_price": 85.00,
            "base_price_vat": 85.00,
            "currency": "EUR",
            "assigned_procurement_user": USER_PROCUREMENT,
            "procurement_status": "in_progress",
            "supplier_city": "Schweinfurt",
            "production_time_days": 14,
        },
        {
            "id": str(uuid.UUID(int=1004)),
            "quote_id": QUOTE_PROCUREMENT,
            "sku": "FAG-NU316-E",
            "description": "Подшипник роликовый FAG NU316 E",
            "brand": "FAG",
            "quantity": 10,
            "base_price": 120.00,
            "base_price_vat": 120.00,
            "currency": "EUR",
            "assigned_procurement_user": USER_PROCUREMENT,
            "procurement_status": "pending",
        },
        # Control quote items
        {
            "id": str(uuid.UUID(int=1005)),
            "quote_id": QUOTE_CONTROL,
            "sku": "GARLOCK-3000",
            "description": "Уплотнение торцевое Garlock 3000",
            "brand": "Garlock",
            "quantity": 100,
            "base_price": 890.00,
            "base_price_vat": 1068.00,
            "currency": "RUB",
            "procurement_status": "completed",
        },
        # Approved quote items
        {
            "id": str(uuid.UUID(int=1006)),
            "quote_id": QUOTE_APPROVED,
            "sku": "RENOLD-12B-1",
            "description": "Цепь роликовая Renold 12B-1",
            "brand": "Renold",
            "quantity": 30,
            "base_price": 2500.00,
            "base_price_vat": 3000.00,
            "currency": "RUB",
            "procurement_status": "completed",
        },
        # Spec quote items
        {
            "id": str(uuid.UUID(int=1007)),
            "quote_id": QUOTE_SPEC,
            "sku": "ABB-M3BP-160",
            "description": "Электродвигатель ABB M3BP 160",
            "brand": "ABB",
            "quantity": 2,
            "base_price": 185000.00,
            "base_price_vat": 222000.00,
            "currency": "RUB",
            "procurement_status": "completed",
        },
        # Deal quote items
        {
            "id": str(uuid.UUID(int=1008)),
            "quote_id": QUOTE_DEAL,
            "sku": "DONALDSON-P551000",
            "description": "Фильтр масляный Donaldson P551000",
            "brand": "Donaldson",
            "quantity": 200,
            "base_price": 650.00,
            "base_price_vat": 780.00,
            "currency": "RUB",
            "procurement_status": "completed",
        },
        {
            "id": str(uuid.UUID(int=1009)),
            "quote_id": QUOTE_DEAL,
            "sku": "DONALDSON-P550440",
            "description": "Фильтр топливный Donaldson P550440",
            "brand": "Donaldson",
            "quantity": 150,
            "base_price": 480.00,
            "base_price_vat": 576.00,
            "currency": "RUB",
            "procurement_status": "completed",
        },
    ]

    for item in items:
        item["created_at"] = now_iso()
        upsert(cur, "kvota.quote_items", item)


def seed_specifications(cur):
    """Create specifications for quotes that reached spec/deal stages."""
    print("  Seeding specifications...")

    try:
        cur.execute("SAVEPOINT sp_specs")
        upsert(cur, "kvota.specifications", {
            "id": SPEC_1,
            "quote_id": QUOTE_SPEC,
            "organization_id": ORG_ID,
            "specification_number": "СП-2603-0006",
            "specification_currency": "RUB",
            "status": "approved",
            "created_by": USER_SC,
            "created_at": now_iso(),
        })
        upsert(cur, "kvota.specifications", {
            "id": SPEC_2,
            "quote_id": QUOTE_DEAL,
            "organization_id": ORG_ID,
            "specification_number": "СП-2603-0007",
            "specification_currency": "RUB",
            "status": "signed",
            "created_by": USER_SC,
            "created_at": now_iso(),
        })
        cur.execute("RELEASE SAVEPOINT sp_specs")
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp_specs")
        print(f"    (specifications: {e})")


def seed_deals(cur):
    """Create a deal for the deal-stage quote."""
    print("  Seeding deals...")

    try:
        cur.execute("SAVEPOINT sp_deals")
        upsert(cur, "kvota.deals", {
            "id": DEAL_1,
            "specification_id": SPEC_2,
            "quote_id": QUOTE_DEAL,
            "organization_id": ORG_ID,
            "deal_number": "СД-2603-0007",
            "signed_at": (date.today() - timedelta(days=5)).isoformat(),
            "total_amount": 202200.00,
            "currency": "RUB",
            "status": "active",
            "created_by": USER_SC,
            "created_at": now_iso(),
        })
        cur.execute("RELEASE SAVEPOINT sp_deals")
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp_deals")
        print(f"    (deals: {e})")


def seed_plan_fact_categories(cur):
    """Create plan/fact categories."""
    print("  Seeding plan_fact_categories...")

    categories = [
        ("client_payment", "Оплата от клиента", True, 1),
        ("supplier_payment", "Оплата поставщику", False, 2),
        ("logistics", "Логистика", False, 3),
        ("customs", "Таможня", False, 4),
        ("customs_vat", "НДС таможенный", False, 5),
        ("tax", "Налоги", False, 6),
        ("finance_commission", "Банковская комиссия", False, 7),
        ("other", "Прочее", False, 8),
    ]

    try:
        cur.execute("SAVEPOINT sp_pf_categories")
        for code, name, is_income, sort_order in categories:
            cur.execute("""
                INSERT INTO kvota.plan_fact_categories (code, name, is_income, sort_order)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO NOTHING
            """, (code, name, is_income, sort_order))
        cur.execute("RELEASE SAVEPOINT sp_pf_categories")
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp_pf_categories")
        print(f"    (plan_fact_categories: {e})")


# ============================================================================
# Main entry points
# ============================================================================

def seed_all(conn):
    """Run all seed functions. Called from setup_local_db.py or standalone."""
    print("Seeding development data...")

    with conn.cursor() as cur:
        cur.execute("SET search_path TO kvota, public")

        seed_organization(cur)
        seed_roles(cur)
        seed_users_and_memberships(cur)
        seed_customers(cur)
        seed_seller_companies(cur)
        seed_quotes(cur)
        seed_quote_items(cur)
        seed_specifications(cur)
        seed_deals(cur)
        seed_plan_fact_categories(cur)

    conn.commit()
    print("  Seed data complete.")

    _print_summary()


def _print_summary():
    print()
    print("  Dev accounts (no Supabase Auth — login via session mock only):")
    print("  ---------------------------------------------------------------")
    print(f"  Admin:         user_id={USER_ADMIN}")
    print(f"  Sales:         user_id={USER_SALES}")
    print(f"  Procurement:   user_id={USER_PROCUREMENT}")
    print(f"  Logistics:     user_id={USER_LOGISTICS}")
    print(f"  Customs:       user_id={USER_CUSTOMS}")
    print(f"  Finance:       user_id={USER_FINANCE}")
    print(f"  QC:            user_id={USER_QC}")
    print(f"  SC:            user_id={USER_SC}")
    print(f"  Top Manager:   user_id={USER_TOP}")
    print()
    print("  Quotes seeded: 7 (2 draft, 1 procurement, 1 control, 1 approved, 1 spec, 1 deal)")
    print("  Customers: 3  |  Quote items: 9  |  Specs: 2  |  Deals: 1")


def main():
    """Standalone execution — connects to DB and seeds."""
    import psycopg2

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set.")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    conn.autocommit = False

    try:
        seed_all(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
