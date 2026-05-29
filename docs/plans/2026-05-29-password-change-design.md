# Password Change & Admin Reset — Design

**Date:** 2026-05-29
**Branch:** `feat/password-change`
**Status:** Design — awaiting review

## Overview

OneStack currently has **no way to change a password** after a user is created.
Admins set an initial password at create time (`api/admin_users.py::create_user`,
`email_confirm: True`), and that password is permanent. There is no self-service
change and no admin reset. This adds both, forming a complete loop:

> User forgets password → asks admin → admin sets a new one and hands it off →
> user logs in → user changes it to something private via their profile.

## Locked decisions (confirmed with user)

1. **Self-service** requires the **current password** to confirm the change
   (re-verify via `signInWithPassword`, then `updateUser`). Protects an
   unattended/hijacked open session from a silent takeover.
2. **Admin reset** uses **manual hand-off** — "the simpler the better". The admin
   generates/sets a new password, copies it, and gives it to the user directly.
   **No email, no Telegram, no SMTP.** (Both were investigated; email is not
   wired up at all, Telegram only reaches linked+verified users and DMing a
   plaintext password is a security smell — see "Investigated & rejected".)
3. Password rule stays the existing **minimum 8 characters**
   (`MIN_PASSWORD_LENGTH = 8`), mirrored client-side. No new strength rules.

## Scope

**In scope**
- Self-service "change my password" on `/profile`.
- Admin "reset password" for any user in the same org, in the existing
  `UserEditSheet`.
- One new backend endpoint + one new server action + two new UI sections.
- Extract the existing password generate/copy widget to a shared component
  (consumed by both `create-user-dialog` and the new admin reset section).

**Out of scope (this iteration)**
- Logged-out "Forgot password?" flow (email reset link). Not needed — the admin
  is the reset mechanism. Would require new SMTP setup; deferred.
- Telegram delivery of the new password.
- Forcing logout of the target user's other sessions on admin reset.
- Password strength rules beyond the existing 8-char minimum.

## Architecture

The same operation ("set a password") sits on two sides of the trust boundary:

| | Self-service | Admin reset |
|---|---|---|
| Acts as | the user themselves | an admin acting on another user |
| Supabase key | anon key + user session (browser) | service_role (server only) |
| Mechanism | `auth.updateUser({ password })` (client) | `auth.admin.update_user_by_id(id, {...})` (Python API) |
| Needs Python API? | **No** — self-scoped auth op, no side effects | **Yes** — privileged, server-side only |
| Layer | `entities/profile/mutations.ts` (client mutation) | `api/admin_users.py` + server action |

This matches the project's API-first test: self-service is a single self-scoped
auth call (Supabase-direct is correct, like `updateProfile`); admin reset is a
privileged operation requiring the service-role key, which must never reach the
browser — so it goes through `/api/admin/*`.

---

## Feature 1 — Self-service change password

### Files
- **Edit** `frontend/src/entities/profile/mutations.ts` → add `changePassword(...)`.
- **New** `frontend/src/features/profile/ui/change-password-section.tsx`.
- **Edit** `frontend/src/features/profile/index.ts` → export `ChangePasswordSection`.
- **Edit** `frontend/src/app/(app)/profile/page.tsx` → render it, passing `email={user.email}`.

### Mutation (`entities/profile/mutations.ts`)

```ts
export async function changePassword(
  email: string,
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const supabase = createClient();

  // 1. Re-verify the current password. On success this re-establishes the
  //    same user's session; on failure it leaves the session untouched.
  const { error: verifyError } = await supabase.auth.signInWithPassword({
    email,
    password: currentPassword,
  });
  if (verifyError) {
    throw new Error("CURRENT_PASSWORD_INVALID");
  }

  // 2. Set the new password. Supabase returns a fresh session; the
  //    @supabase/ssr cookie sync keeps the user logged in (no re-login).
  const { error: updateError } = await supabase.auth.updateUser({
    password: newPassword,
  });
  if (updateError) throw updateError;
}
```

### UI (`change-password-section.tsx`)
- `"use client"`. Rendered as a `Card` to match `TelegramSection` /
  `DepartmentSection` (consistent profile-page styling).
- Title: **«Смена пароля»**. Card body holds a controlled form:
  - `Текущий пароль` — `type="password"`
  - `Новый пароль` — `type="password"`
  - `Повторите новый пароль` — `type="password"`
  - Primary button: **«Сменить пароль»**
- Client validation before submit (inline errors near each field, per
  validation-UX rule — name + highlight the offending field):
  - all three fields non-empty
  - new password ≥ 8 chars
  - new === confirm
  - new !== current (avoid a no-op)
- On `changePassword` rejection:
  - `CURRENT_PASSWORD_INVALID` → field error on «Текущий пароль»: «Неверный текущий пароль».
  - otherwise → toast «Не удалось сменить пароль».
- On success → `toast.success("Пароль изменён")`, clear the three fields.
- Submit button shows `Loader2` spinner + disabled while in flight (no double submit).

### Entry point
`/profile` is already reachable from the sidebar avatar
(`widgets/sidebar/sidebar.tsx:271-308`). No new nav item required.

### Session note
`updateUser({ password })` does **not** invalidate the current session — Supabase
issues a fresh token and `@supabase/ssr` writes the new cookies. The middleware
(`shared/lib/supabase/middleware.ts`) keeps refreshing as normal. No forced
re-login.

---

## Feature 2 — Admin reset password

### Files
- **Edit** `api/admin_users.py` → new `async def reset_user_password(request, user_id)`.
- **Edit** `api/routers/admin.py` → import + `@router.patch("/users/{user_id}/password")`.
- **Edit** `frontend/src/features/admin-users/actions.ts` → `resetUserPasswordAction`.
- **Edit** `frontend/src/features/admin-users/ui/user-edit-sheet.tsx` → new section.
- Tests: `tests/test_api_routers_admin.py` (+ handler-level tests).

### Backend handler (`api/admin_users.py`)

```python
async def reset_user_password(request, user_id: str) -> JSONResponse:
    """Set a new password for a user in the admin's organization.

    Path: PATCH /api/admin/users/{user_id}/password
    Params:
        password: str (required) — New password (min 8 chars)
    Returns:
        user_id: str
    Side Effects:
        - Calls sb.auth.admin.update_user_by_id(user_id, {"password": ...})
    Roles: admin
    """
    admin_user, auth_err = _get_admin_user(request)        # admin + org scope
    if auth_err:
        return auth_err
    assert admin_user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": {
            "code": "BAD_REQUEST", "message": "Invalid JSON body"}}, status_code=400)

    password = body.get("password") or ""
    if not password:
        return JSONResponse({"success": False, "error": {
            "code": "VALIDATION_ERROR", "message": "Password is required",
            "fields": {"password": "Password is required"}}}, status_code=400)
    if len(password) < MIN_PASSWORD_LENGTH:
        return JSONResponse({"success": False, "error": {
            "code": "VALIDATION_ERROR",
            "message": f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
            "fields": {"password": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}}},
            status_code=400)

    org_id = admin_user["org_id"]
    _, member_err = _verify_user_in_org(user_id, org_id)   # same-org target
    if member_err:
        return member_err

    sb = get_supabase()
    try:
        sb.auth.admin.update_user_by_id(user_id, {"password": password})
    except Exception as e:
        logger.error("Failed to reset password for user %s: %s", user_id, e)
        return JSONResponse({"success": False, "error": {
            "code": "SERVER_ERROR", "message": "Failed to reset password"}}, status_code=500)

    return JSONResponse({"success": True, "data": {"user_id": user_id}})
```

- **Never log the password.** Only `user_id` + error appear in logs.
- **No last-admin guard** — resetting a password endangers nothing (unlike
  deactivation or admin-role removal). Org-scoping is the only authorization.
- Authorization reuses `_get_admin_user` (admin role + org from
  `organization_members`, never the body) and `_verify_user_in_org`.

### Routing (`api/routers/admin.py`)
Add to the import block and register alongside the `roles` route (more-specific
two-segment path; place with the other `{user_id}/...` routes):

```python
from api.admin_users import (
    create_user as _create_user,
    reset_user_password as _reset_user_password,   # new
    update_user_roles as _update_user_roles,
    update_user_status as _update_user_status,
)

@router.patch("/users/{user_id}/password")
async def patch_admin_user_password(request: Request, user_id: str) -> JSONResponse:
    """Reset a user's password."""
    return await _reset_user_password(request, user_id)
```

### Server action (`features/admin-users/actions.ts`)
Clone `updateUserStatusAction`:

```ts
export async function resetUserPasswordAction(
  userId: string,
  password: string
): Promise<ApiResponse<{ user_id: string }>> {
  const res = await apiServerClient<{ user_id: string }>(
    `/admin/users/${userId}/password`,
    { method: "PATCH", body: JSON.stringify({ password }) }
  );
  if (res.success) revalidatePath("/admin/users");
  return res;
}
```

### UI (`user-edit-sheet.tsx`)
Add a **fourth** `<section>` after a `<Separator/>`, matching the existing
Профиль / Роли / Статус blocks:
- Heading: **«Сброс пароля»**.
- Body: the shared password input (text field + generate + copy buttons) +
  a **«Сбросить пароль»** button.
- One-line helper text under the heading: «Передайте новый пароль пользователю.
  Он сможет сменить его в своём профиле.» (sets the hand-off expectation).
- Validation: password ≥ 8 chars before enabling submit (mirror server rule).
- On success: `toast.success("Пароль сброшен")`, clear the field. Keep the sheet
  open (admin may still be copying). Spinner + disabled while in flight.
- On error: map `VALIDATION_ERROR` to a field error, else toast the message.

---

## Shared component extraction (avoid drift)

`generatePassword()` and the input+generate+copy trio currently live inline in
`create-user-dialog.tsx` (`:56-62`, `:266-298`). With a second consumer (admin
reset) this is exactly the "extract when there are 2 concrete uses" case.

- **New** `frontend/src/shared/lib/password.ts` → `generatePassword(): string`
  (moved verbatim from `create-user-dialog.tsx:56-62`).
- **New** `frontend/src/shared/ui/password-generate-input.tsx` → a controlled
  component: text `Input` + generate (`RefreshCw`) + copy (`Copy`) buttons with
  the existing toast on copy. Props: `value`, `onChange`, `error?`, `id?`,
  `placeholder?`.
- **Edit** `create-user-dialog.tsx` to consume both (removing the inline copies).
  This is a behaviour-preserving refactor — the existing create-user flow keeps
  working exactly as before; covered by its existing tests.

> The self-service form does **not** use this widget — its fields are masked
> (`type="password"`) and there is no generate/copy there.

---

## Security considerations

- Self-service requires the current password (re-verify via `signInWithPassword`)
  before `updateUser` — no silent takeover from an open session.
- Admin reset is gated by `_get_admin_user` (admin role) + `_verify_user_in_org`
  (same org) — an admin cannot reset users outside their organization.
- The service_role key stays server-side (`get_supabase()` in Python); it is
  never exposed to the browser.
- Passwords are never logged (neither handler logs the value).
- Min length 8 enforced on both client and server (defense at the boundary).
- `apiServerClient` forwards the caller's JWT; the Python `ApiAuthMiddleware`
  populates `request.state.api_user` — same auth path as the existing admin
  endpoints.

## Testing plan

**Backend (`tests/test_api_routers_admin.py` + handler tests)**
- 200/`success` path: admin resets a same-org user's password.
- 400 when password missing.
- 400 when password < 8 chars.
- 401 when no `api_user`.
- 403 when caller is not admin.
- 404 when target user is not in the caller's org.
- 500 path when the Supabase admin call raises (mock raises → error envelope).
- Assert the password value is **not** present in any log call.

**Frontend**
- `changePassword` mutation (`*.dom.test.tsx` per the jsdom setup): wrong current
  password → throws `CURRENT_PASSWORD_INVALID`; happy path calls
  `signInWithPassword` then `updateUser` (mock the supabase client).
- `ChangePasswordSection`: validation errors (empty, too short, mismatch,
  new===current) render inline; success clears fields + toasts.
- `PasswordGenerateInput`: generate fills, copy writes to clipboard.
- Manual: localhost:3000 against prod Supabase (per the standard pre-deploy
  flow) — self-change as a normal user, admin reset from `/admin/users`.

## Build sequence

1. Shared extraction: `shared/lib/password.ts` + `shared/ui/password-generate-input.tsx`;
   refactor `create-user-dialog.tsx` to use them (verify create-user still works).
2. Backend: `reset_user_password` handler + router registration + tests (TDD).
3. Server action `resetUserPasswordAction`.
4. Admin UI: «Сброс пароля» section in `UserEditSheet`.
5. Self-service: `changePassword` mutation + `ChangePasswordSection` + wire into
   `/profile` + export.
6. Lint + tsc + pytest green; manual localhost verification; PR.

## Investigated & rejected (why "simpler" is right)

- **Email reset link** — no SMTP anywhere in the repo; the app deliberately
  bypasses Supabase email on every user create (`email_confirm: True`). Would
  require dashboard SMTP setup + `/forgot-password` + `/auth/callback?type=recovery`
  pages. Deferred.
- **Telegram delivery** — `telegram_users` (`user_id → telegram_id`) +
  `get_user_telegram_id()` + `send_message()` are live, so it's technically
  possible. Rejected for now: only reaches users who linked **and** verified
  Telegram (no fallback for the rest), and DMing a plaintext password is a
  security smell. Could be revisited as an opt-in "notify user" enhancement
  later, sending a "your password was reset, change it now" notice rather than
  the password itself.
