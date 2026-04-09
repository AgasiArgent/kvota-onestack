# Implementation Plan: Управление пользователями в админке

## Tasks

- [ ] 1. Миграция: Postgres-функция `update_user_roles`
  - Создать миграцию с функцией `kvota.update_user_roles(p_user_id, p_org_id, p_role_slugs[])` 
  - Atomic DELETE + INSERT в одной транзакции
  - Last-admin guard: RAISE EXCEPTION если удаляется последний admin
  - Down-миграция: DROP FUNCTION
  - Применить через `scripts/apply-migrations.sh`
  - _Requirements: 3, 7_

- [ ] 2. Python API: `api/admin_users.py` — три endpoint'а (P)
  - 2.1 `POST /api/admin/users` — создание пользователя
    - Validate JWT + admin role (via `request.state.api_user`)
    - Resolve `org_id` from api_user's org membership (NOT from request body)
    - `auth.admin.create_user(email, password, email_confirm=True)`
    - INSERT `organization_members`, `user_profiles`, `user_roles`
    - Cleanup: delete auth user on INSERT failure
    - Structured docstring
    - _Requirements: 1, 6_
  - 2.2 `PATCH /api/admin/users/{user_id}` — деактивация/активация
    - `status: "active" | "suspended"` in request body
    - Deactivate: `auth.admin.update_user_by_id(ban_duration='forever')` + sign out + update org_members.status
    - Activate: unban + update status
    - Last-admin guard for deactivation
    - Structured docstring
    - _Requirements: 4, 6_
  - 2.3 `PATCH /api/admin/users/{user_id}/roles` — атомарное обновление ролей
    - Call `kvota.update_user_roles()` Postgres function via RPC
    - Validate role_slugs non-empty
    - Structured docstring
    - _Requirements: 3, 6_
  - Register router in `api/__init__.py`

- [ ] 3. Server Actions: thin wrappers (P)
  - Создать `frontend/src/features/admin-users/actions.ts`
  - `createUserAction(payload)` → POST /api/admin/users → revalidatePath
  - `updateUserStatusAction(userId, status)` → PATCH /api/admin/users/{id} → revalidatePath
  - `updateUserRolesAction(userId, roleSlugs)` → PATCH /api/admin/users/{id}/roles → revalidatePath
  - Все через `apiServerClient` (JWT forwarding)
  - _Requirements: 1, 3, 4, 6_

- [ ] 4. UI: CreateUserDialog (P)
  - Создать `frontend/src/features/admin-users/ui/create-user-dialog.tsx`
  - Поля: email, password (с auto-generate + copy button), full_name, roles (checkboxes), position, sales_group (conditional)
  - Zod validation: email required, password min 8, full_name required, roles min 1
  - On submit: `createUserAction` → close dialog + toast on success
  - Error display inline
  - _Requirements: 1_

- [ ] 5. UI: UserEditSheet (P)
  - Создать `frontend/src/features/admin-users/ui/user-edit-sheet.tsx`
  - Profile section: name, position, sales_group → Supabase direct (`updateUserProfile`)
  - Roles section: checkboxes → `updateUserRolesAction`
  - Status section: badge + toggle button → `updateUserStatusAction`
  - Last-admin protection: disable deactivate + admin role removal
  - _Requirements: 2, 3, 4_

- [ ] 6. UI: Extend UsersPageClient
  - Добавить кнопку "Добавить пользователя" (top-right) → opens CreateUserDialog
  - Добавить колонку "Статус" с бейджами (active=green, suspended=red)
  - Row click → opens UserEditSheet (вместо/помимо RoleEditModal)
  - Обновить `entities/admin/types.ts`: добавить `CreateUserPayload`, `UpdateUserPayload`
  - Обновить `entities/admin/mutations.ts`: добавить `updateUserProfile`, удалить/заменить old `updateUserRoles`
  - _Requirements: 2, 5_

- [ ] 7. Browser testing
  - Открыть /admin/users → проверить список с бейджами статуса
  - Создать пользователя → проверить появление в списке
  - Редактировать профиль → проверить сохранение
  - Изменить роли → проверить атомарность
  - Деактивировать → проверить бейдж "Заблокирован"
  - _Requirements: 1, 2, 3, 4, 5_
