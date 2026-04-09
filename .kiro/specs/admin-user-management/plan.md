# Admin User Management — Plan

**Date:** 2026-04-09
**Scope Mode:** HOLD SCOPE
**Status:** Ready for implementation

## Problem Statement
Создание пользователей требует SSH-доступа и 6 шагов SQL — это блокирует масштабирование команды. Только разработчик может добавить нового сотрудника. Существующий код управления ролями имеет security-дыры (browser client mutations, отсутствие IDOR-защиты).

## Scope Mode Rationale
Фича чётко определена (автоматизация ручного процесса), инфраструктура на месте. Нужна надёжность и безопасность, а не расширение скоупа.

## Core Requirements

1. Admin может создать пользователя через форму в UI (email, пароль, имя, роли, должность, sales group)
2. `POST /api/admin/users` — Python endpoint: auth.admin.createUser + INSERT в org_members, user_profiles, user_roles. Structured docstring.
3. Admin может деактивировать/активировать пользователя через UI
4. `PATCH /api/admin/users/{id}` — Python endpoint: ban/unban в auth + update org_members.status + signOut при деактивации
5. Admin может изменить роли пользователя атомарно
6. `PATCH /api/admin/users/{id}/roles` — Python endpoint: вызов Postgres-функции update_user_roles() с last-admin guard
7. Admin может редактировать профиль пользователя (имя, должность, sales group) — Supabase direct (simple CRUD, one table)
8. Server Actions — thin wrappers: auth check → call Python API → revalidatePath
9. Таблица пользователей показывает статус (active/suspended badge)
10. Postgres-функция `update_user_roles(p_user_id, p_org_id, p_role_slugs[])` — атомарный DELETE+INSERT с проверкой last admin

## Deferred Items

1. **Password reset** — пока админ задаёт пароль при создании. Follow-up PR.
2. **Email-приглашения** (magic link) — текущий flow достаточен для B2B <50 юзеров
3. **Аудит-лог** (created_by/updated_by) — отдельный PR
4. **Bulk operations** — <50 юзеров, поштучно ОК
5. **"Must change password" flag** — nice-to-have для внутренней команды

## Key Decisions

- **API-first:** Все multi-table writes через Python API, не Next.js Route Handlers. Server Actions — thin wrappers. Причина: AI агенты и MCP должны иметь доступ к тем же операциям.
- **Пароль задаёт админ:** Не email-invitation. Причина: B2B, <50 юзеров, внутренняя команда.
- **Один план, один PR:** Security fixes идут вместе с фичей. Причина: не создавать окно уязвимости.
- **Postgres-функция для ролей:** Атомарность через DB, не application-level transaction. Причина: надёжнее, проще, last-admin guard на уровне DB.
- **Soft-disable вместо delete:** auth.admin.ban + org_members.status. Причина: CASCADE на auth.users удалит 30+ связанных таблиц.

## Open Questions

- [ ] Supabase Python admin API: `supabase-py` поддерживает `auth.admin`? Или нужен прямой HTTP к GoTrue? — resolve during implementation
- [ ] organization_id: hardcode единственной org или из сессии? — resolve during implementation (рекомендация: из сессии для future-proof)

## Dream State Alignment
Python API endpoints = фундамент для OpenAPI/MCP. Атомарные операции = правильная архитектура для будущего аудит-лога и bulk ops.

## Implementation Notes

- `auto_create_user_profile` trigger сломан — API должен явно INSERT в user_profiles
- При ошибке после auth.admin.createUser — cleanup (delete auth user), иначе orphan
- JWT forwarding из Server Action через apiServerClient — проверить middleware парсинг
- Email uniqueness: Supabase вернёт ошибку — прокинуть человекочитаемое сообщение
- Существующий `updateUserRoles` в mutations.ts — заменить вызовом нового Python API
