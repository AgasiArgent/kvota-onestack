#!/usr/bin/env python3
"""
Beta Test User Creation Script

Creates 19 beta test users for MasterBearing team.
Run AFTER migration 178 (departments/groups setup) and cleanup_before_beta.sql.

Usage:
    python scripts/create_beta_users.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.client import ClientOptions

load_dotenv()

ORG_ID = "69ff6eda-3fd6-4d24-88b7-a9977c7a08b0"
PASSWORD = "Mb2026Beta!"

# Beta users: email, full_name, position, roles[], department, group
BETA_USERS = [
    {
        "email": "chislova.e@masterbearing.ru",
        "full_name": "Числова Екатерина",
        "position": "Руководитель отдела закупок",
        "roles": ["procurement", "head_of_procurement"],
        "department": "Закупки",
        "group": "Закупки общий департамент",
    },
    {
        "email": "nagumanova.u@masterbearing.ru",
        "full_name": "Нагуманова Юлия",
        "position": "МОЗ",
        "roles": ["procurement"],
        "department": "Закупки",
        "group": "Закупки общий департамент",
    },
    {
        "email": "lliubov.d@masterbearing.ru",
        "full_name": "Давыдова Любовь",
        "position": "Руководитель группы продаж",
        "roles": ["sales", "head_of_sales"],
        "department": "Продажи",
        "group": "PHMB",
    },
    {
        "email": "denis.r@masterbearing.ru",
        "full_name": "Рогачёв Денис",
        "position": "МОП",
        "roles": ["sales"],
        "department": "Продажи",
        "group": "PHMB",
    },
    {
        "email": "barmina.a@masterbearing.ru",
        "full_name": "Бармина Анастасия",
        "position": "МОЗ",
        "roles": ["procurement"],
        "department": "Закупки",
        "group": "PHMB",
    },
    {
        "email": "arutsev.georgiy@masterbearing.ru",
        "full_name": "Аруцев Георгий",
        "position": "Руководитель группы продаж",
        "roles": ["sales", "head_of_sales"],
        "department": "Продажи",
        "group": "Группа Аруцева",
    },
    {
        "email": "anatoliy.e@masterbearing.ru",
        "full_name": "Ершов Анатолий",
        "position": "МОП",
        "roles": ["sales"],
        "department": "Продажи",
        "group": "Группа Аруцева",
    },
    {
        "email": "a.chugrishin@masterbearing.ru",
        "full_name": "Чугришин Александр",
        "position": "Руководитель группы продаж",
        "roles": ["sales", "head_of_sales"],
        "department": "Продажи",
        "group": "Группа Чугришина",
    },
    {
        "email": "camilla.g@masterbearing.ru",
        "full_name": "Гаптукаева Камилла",
        "position": "МОП",
        "roles": ["sales"],
        "department": "Продажи",
        "group": "Группа Чугришина",
    },
    {
        "email": "anton.p@masterbearing.ru",
        "full_name": "Пономарев Антон",
        "position": "Руководитель группы продаж",
        "roles": ["sales", "head_of_sales"],
        "department": "Продажи",
        "group": "Группа Пономарева",
    },
    {
        "email": "sergey.m@masterbearing.ru",
        "full_name": "Марыныч Сергей",
        "position": "МОП",
        "roles": ["sales"],
        "department": "Продажи",
        "group": "Группа Пономарева",
    },
    {
        "email": "roman.c@masterbearing.ru",
        "full_name": "Чариков Роман",
        "position": "МОП",
        "roles": ["sales"],
        "department": "Продажи",
        "group": "Группа Пономарева",
    },
    {
        "email": "anastasiia.sergeeva@masterbearing.ru",
        "full_name": "Сергеева Анастасия",
        "position": "МОЗ",
        "roles": ["procurement"],
        "department": "Закупки",
        "group": "Группа Пономарева",
    },
    {
        "email": "bisenova.zhanna@masterbearing.ru",
        "full_name": "Бисенова Жанна",
        "position": "Контроль КП / Контроль СП",
        "roles": ["quote_controller", "spec_controller"],
        "department": "Контроль",
        "group": None,
    },
    {
        "email": "ivan.guk@masterbearing.ru",
        "full_name": "Гук Иван",
        "position": "Руководитель отдела финансов",
        "roles": ["finance", "head_of_finance"],
        "department": "Финансы",
        "group": None,
    },
    {
        "email": "shmeleva.ekaterina@masterbearing.ru",
        "full_name": "Шмелева Екатерина",
        "position": "МОФ",
        "roles": ["finance"],
        "department": "Финансы",
        "group": None,
    },
    {
        "email": "markin.r@masterbearing.ru",
        "full_name": "Маркин Роман",
        "position": "МОТ",
        "roles": ["customs"],
        "department": "Таможня",
        "group": None,
    },
    {
        "email": "oleg.k@masterbearing.ru",
        "full_name": "Князев Олег",
        "position": "МОТ",
        "roles": ["customs"],
        "department": "Таможня",
        "group": None,
    },
    {
        "email": "milana.d@masterbearing.ru",
        "full_name": "Далелова Милана",
        "position": "МОЛ",
        "roles": ["logistics"],
        "department": "Логистика",
        "group": None,
    },
]


def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key, options=ClientOptions(schema="kvota"))


def main():
    print("=" * 60)
    print("OneStack Beta User Creation")
    print("=" * 60)

    supabase = get_supabase()

    # Load role map
    roles_result = supabase.table("roles").select("id, slug").execute()
    role_map = {r["slug"]: r["id"] for r in roles_result.data}
    print(f"Roles loaded: {list(role_map.keys())}")

    # Load department map
    dept_result = supabase.table("departments").select("id, name").execute()
    dept_map = {d["name"]: d["id"] for d in dept_result.data}
    print(f"Departments loaded: {list(dept_map.keys())}")

    # Load sales_groups map
    groups_result = supabase.table("sales_groups").select("id, name").execute()
    group_map = {g["name"]: g["id"] for g in groups_result.data}
    print(f"Groups loaded: {list(group_map.keys())}")

    created = 0
    errors = 0

    for user in BETA_USERS:
        email = user["email"]
        print(f"\n--- {user['full_name']} ({email}) ---")

        try:
            # 1. Create auth user
            user_response = supabase.auth.admin.create_user({
                "email": email,
                "password": PASSWORD,
                "email_confirm": True,
            })
            user_id = str(user_response.user.id)
            print(f"  Auth user created: {user_id[:8]}...")

            # 2. Add to organization
            supabase.table("organization_members").insert({
                "user_id": user_id,
                "organization_id": ORG_ID,
                "status": "active",
                "is_owner": False,
            }).execute()
            print(f"  Added to org")

            # 3. Assign roles
            for role_slug in user["roles"]:
                role_id = role_map.get(role_slug)
                if role_id:
                    supabase.table("user_roles").insert({
                        "user_id": user_id,
                        "organization_id": ORG_ID,
                        "role_id": role_id,
                    }).execute()
                    print(f"  Role: {role_slug}")
                else:
                    print(f"  WARNING: Role '{role_slug}' not found!")

            # 4. Create user profile
            profile_data = {
                "user_id": user_id,
                "organization_id": ORG_ID,
                "full_name": user["full_name"],
                "position": user["position"],
            }

            dept_id = dept_map.get(user["department"])
            if dept_id:
                profile_data["department_id"] = dept_id
            else:
                print(f"  WARNING: Department '{user['department']}' not found!")

            if user["group"]:
                group_id = group_map.get(user["group"])
                if group_id:
                    profile_data["sales_group_id"] = group_id
                else:
                    print(f"  WARNING: Group '{user['group']}' not found!")

            supabase.table("user_profiles").insert(profile_data).execute()
            print(f"  Profile created")

            created += 1

        except Exception as e:
            if "already been registered" in str(e) or "already exists" in str(e).lower():
                print(f"  SKIPPED: User already exists")
            else:
                print(f"  ERROR: {e}")
                errors += 1

    print(f"\n{'=' * 60}")
    print(f"Created: {created} | Errors: {errors} | Total: {len(BETA_USERS)}")
    print(f"Password for all: {PASSWORD}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
