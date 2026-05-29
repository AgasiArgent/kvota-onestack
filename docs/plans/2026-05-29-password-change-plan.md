# Password Change & Admin Reset — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any logged-in user change their own password on `/profile`, and let an admin reset any same-org user's password from the UserEditSheet (manual hand-off).

**Architecture:** Self-service is a client-side Supabase Auth call (`signInWithPassword` re-verify → `updateUser`) in `entities/profile/mutations.ts` — no API endpoint. Admin reset is privileged (service_role) so it goes through a new `PATCH /api/admin/users/{id}/password` reusing the existing `_get_admin_user` + `_verify_user_in_org` guards. The password generate/copy widget is extracted to `shared/` so create-user and admin-reset share one component.

**Tech Stack:** Next.js 15 (App Router, FSD) · shadcn/ui · Supabase Auth (`@supabase/ssr`) · FastAPI (Starlette handlers + thin APIRouter) · pytest · vitest (node + jsdom projects).

**Spec:** `docs/plans/2026-05-29-password-change-design.md`

---

## File Structure

**Create**
- `frontend/src/shared/lib/password.ts` — `generatePassword()` util
- `frontend/src/shared/lib/__tests__/password.test.ts` — util unit test
- `frontend/src/shared/ui/password-generate-input.tsx` — shared input + generate + copy
- `frontend/src/shared/ui/__tests__/password-generate-input.dom.test.tsx` — component test
- `frontend/src/features/profile/ui/change-password-section.tsx` — self-service card
- `frontend/src/features/profile/ui/__tests__/change-password-section.dom.test.tsx` — component test
- `frontend/src/entities/profile/__tests__/change-password.test.ts` — mutation test
- `tests/test_admin_users_password.py` — backend handler tests

**Modify**
- `frontend/src/shared/ui/index.ts` — export `PasswordGenerateInput`
- `frontend/src/features/admin-users/ui/create-user-dialog.tsx` — use shared util + component
- `api/admin_users.py` — add `reset_user_password` handler
- `api/routers/admin.py` — register `PATCH /users/{user_id}/password`
- `tests/test_api_routers_admin.py` — routing + OpenAPI assertions for the new path
- `frontend/src/features/admin-users/actions.ts` — `resetUserPasswordAction`
- `frontend/src/features/admin-users/ui/user-edit-sheet.tsx` — «Сброс пароля» section
- `frontend/src/entities/profile/mutations.ts` — `changePassword`
- `frontend/src/features/profile/index.ts` — export `ChangePasswordSection`
- `frontend/src/app/(app)/profile/page.tsx` — render `ChangePasswordSection`

---

## Task 1: Shared `generatePassword` util

**Files:**
- Create: `frontend/src/shared/lib/password.ts`
- Test: `frontend/src/shared/lib/__tests__/password.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/shared/lib/__tests__/password.test.ts
import { describe, it, expect } from "vitest";
import { generatePassword, PASSWORD_CHARSET } from "@/shared/lib/password";

describe("generatePassword", () => {
  it("returns a 12-character string", () => {
    expect(generatePassword()).toHaveLength(12);
  });

  it("uses only characters from the allowed charset", () => {
    for (let i = 0; i < 50; i++) {
      for (const ch of generatePassword()) {
        expect(PASSWORD_CHARSET).toContain(ch);
      }
    }
  });

  it("produces different values across calls", () => {
    const a = generatePassword();
    const b = generatePassword();
    expect(a).not.toEqual(b);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/shared/lib/__tests__/password.test.ts`
Expected: FAIL — cannot resolve `@/shared/lib/password`.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/shared/lib/password.ts

/** Characters used for generated passwords. Excludes ambiguous glyphs (0/O, 1/l/I). */
export const PASSWORD_CHARSET =
  "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%";

/** Generate a 12-character random password using the Web Crypto API. */
export function generatePassword(): string {
  const array = new Uint8Array(12);
  crypto.getRandomValues(array);
  return Array.from(
    array,
    (byte) => PASSWORD_CHARSET[byte % PASSWORD_CHARSET.length]
  ).join("");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/shared/lib/__tests__/password.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/lib/password.ts frontend/src/shared/lib/__tests__/password.test.ts
git commit -m "feat(shared): extract generatePassword util"
```

---

## Task 2: Shared `PasswordGenerateInput` component

A controlled text input with generate (↻) and copy (⧉) buttons. Mirrors the
inline widget currently in `create-user-dialog.tsx:266-298`.

**Files:**
- Create: `frontend/src/shared/ui/password-generate-input.tsx`
- Test: `frontend/src/shared/ui/__tests__/password-generate-input.dom.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/shared/ui/__tests__/password-generate-input.dom.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PasswordGenerateInput } from "@/shared/ui/password-generate-input";

describe("PasswordGenerateInput", () => {
  it("calls onChange with a 12-char password when generate is clicked", () => {
    const onChange = vi.fn();
    render(<PasswordGenerateInput value="" onChange={onChange} />);
    fireEvent.click(screen.getByTitle("Сгенерировать пароль"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toHaveLength(12);
  });

  it("calls onChange when the user types", () => {
    const onChange = vi.fn();
    render(<PasswordGenerateInput value="" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hunter2!" },
    });
    expect(onChange).toHaveBeenCalledWith("hunter2!");
  });

  it("disables the copy button when value is empty", () => {
    render(<PasswordGenerateInput value="" onChange={() => {}} />);
    expect(screen.getByTitle("Скопировать пароль")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/shared/ui/__tests__/password-generate-input.dom.test.tsx`
Expected: FAIL — cannot resolve `@/shared/ui/password-generate-input`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/shared/ui/password-generate-input.tsx
"use client";

import { Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { generatePassword } from "@/shared/lib/password";

interface PasswordGenerateInputProps {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  placeholder?: string;
  error?: boolean;
  autoFocus?: boolean;
}

export function PasswordGenerateInput({
  value,
  onChange,
  id,
  placeholder = "Минимум 8 символов",
  error = false,
  autoFocus = false,
}: PasswordGenerateInputProps) {
  async function handleCopy() {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      toast.success("Пароль скопирован");
    } catch {
      toast.error("Не удалось скопировать");
    }
  }

  return (
    <div className="flex gap-2">
      <Input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className={`flex-1 ${error ? "border-destructive" : ""}`}
      />
      <Button
        type="button"
        variant="outline"
        size="default"
        onClick={() => onChange(generatePassword())}
        title="Сгенерировать пароль"
      >
        <RefreshCw size={14} />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="default"
        onClick={handleCopy}
        disabled={!value}
        title="Скопировать пароль"
      >
        <Copy size={14} />
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Export from the shared/ui barrel**

Add to `frontend/src/shared/ui/index.ts` (after the `CountryFlag` export on line 1):

```ts
export { PasswordGenerateInput } from "./password-generate-input";
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/shared/ui/__tests__/password-generate-input.dom.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/shared/ui/password-generate-input.tsx frontend/src/shared/ui/__tests__/password-generate-input.dom.test.tsx frontend/src/shared/ui/index.ts
git commit -m "feat(shared): add PasswordGenerateInput component"
```

---

## Task 3: Refactor create-user-dialog to use the shared widget

Behaviour-preserving: replace the inline `generatePassword()` + password input
block with the shared util and component. The existing create-user flow must
keep working identically.

**Files:**
- Modify: `frontend/src/features/admin-users/ui/create-user-dialog.tsx`

- [ ] **Step 1: Remove the inline `generatePassword` and import the shared util + component**

Delete the local `generatePassword` function (`create-user-dialog.tsx:56-62`).
Update imports near the top:
- Remove `Copy, RefreshCw` from the `lucide-react` import (line 5) **only if** no
  longer used elsewhere in the file (they are not — verify with a grep).
- Remove `toast`'s `handleCopyPassword` usage (the copy logic moves into the shared component).
- Add:

```ts
import { PasswordGenerateInput } from "@/shared/ui/password-generate-input";
```

- [ ] **Step 2: Delete the now-unused handlers**

Remove `handleGeneratePassword` (`:144-150`) and `handleCopyPassword` (`:152-160`).
(The generate action is internal to `PasswordGenerateInput`; the clear-error on
generate is handled in Step 3's inline `onChange`.)

- [ ] **Step 3: Replace the password input block**

Replace the `<div className="flex gap-2"> … </div>` password input group
(`create-user-dialog.tsx:266-298`) with:

```tsx
<PasswordGenerateInput
  id="create-user-password"
  value={password}
  error={!!errors.password}
  onChange={(val) => {
    setPassword(val);
    if (errors.password)
      setErrors((prev) => ({ ...prev, password: undefined }));
  }}
/>
```

- [ ] **Step 4: Typecheck + lint the file**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: no errors referencing `create-user-dialog.tsx` (no unused `Copy`/`RefreshCw`/`generatePassword`).

- [ ] **Step 5: Run any existing create-user tests + the new shared tests**

Run: `cd frontend && npx vitest run src/features/admin-users src/shared/ui/__tests__/password-generate-input.dom.test.tsx`
Expected: PASS (or "no test files" for admin-users if none exist — that's fine; the typecheck in Step 4 is the guard).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/admin-users/ui/create-user-dialog.tsx
git commit -m "refactor(admin-users): use shared PasswordGenerateInput in create dialog"
```

---

## Task 4: Backend `reset_user_password` handler (TDD)

**Files:**
- Modify: `api/admin_users.py`
- Test: `tests/test_admin_users_password.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_admin_users_password.py
"""Tests for api/admin_users.reset_user_password (admin password reset)."""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import admin_users  # noqa: E402
from api.admin_users import reset_user_password  # noqa: E402

ADMIN = {"id": "admin-1", "email": "a@x.com", "org_id": "org-1"}
TARGET = "22222222-2222-2222-2222-222222222222"


def _make_request(*, api_user_id="admin-1", body=None, raw_body_error=False):
    req = MagicMock()
    req.state = SimpleNamespace(
        api_user=None
        if api_user_id is None
        else SimpleNamespace(id=api_user_id, email="a@x.com")
    )
    req.headers = {"content-type": "application/json"}

    async def _json():
        if raw_body_error:
            raise ValueError("bad json")
        return body or {}

    req.json = _json
    return req


def _run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(resp) -> dict:
    return json.loads(resp.body)


def test_no_auth_returns_401():
    """No api_user → 401 (via _get_admin_user, before any supabase call)."""
    req = _make_request(api_user_id=None)
    resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 401
    assert _body(resp)["error"]["code"] == "UNAUTHORIZED"


def test_missing_password_returns_400():
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)):
        req = _make_request(body={})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_short_password_returns_400():
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)):
        req = _make_request(body={"password": "short"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_target_not_in_org_returns_404():
    from starlette.responses import JSONResponse

    not_found = JSONResponse(
        {"success": False, "error": {"code": "NOT_FOUND", "message": "x"}},
        status_code=404,
    )
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)), patch.object(
        admin_users, "_verify_user_in_org", return_value=(None, not_found)
    ):
        req = _make_request(body={"password": "validpass123"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 404


def test_success_calls_update_user_by_id_and_returns_200():
    sb = MagicMock()
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)), patch.object(
        admin_users, "_verify_user_in_org", return_value=({"user_id": TARGET}, None)
    ), patch.object(admin_users, "get_supabase", return_value=sb):
        req = _make_request(body={"password": "validpass123"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 200
    assert _body(resp) == {"success": True, "data": {"user_id": TARGET}}
    sb.auth.admin.update_user_by_id.assert_called_once_with(
        TARGET, {"password": "validpass123"}
    )


def test_supabase_failure_returns_500():
    sb = MagicMock()
    sb.auth.admin.update_user_by_id.side_effect = Exception("boom")
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)), patch.object(
        admin_users, "_verify_user_in_org", return_value=({"user_id": TARGET}, None)
    ), patch.object(admin_users, "get_supabase", return_value=sb):
        req = _make_request(body={"password": "validpass123"})
        resp = _run(reset_user_password(req, TARGET))
    assert resp.status_code == 500
    assert _body(resp)["error"]["code"] == "SERVER_ERROR"


def test_password_is_never_logged():
    sb = MagicMock()
    with patch.object(admin_users, "_get_admin_user", return_value=(ADMIN, None)), patch.object(
        admin_users, "_verify_user_in_org", return_value=({"user_id": TARGET}, None)
    ), patch.object(admin_users, "get_supabase", return_value=sb), patch.object(
        admin_users, "logger"
    ) as mock_logger:
        req = _make_request(body={"password": "secretpw123"})
        _run(reset_user_password(req, TARGET))
    logged = " ".join(str(c) for c in mock_logger.mock_calls)
    assert "secretpw123" not in logged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_admin_users_password.py -v`
Expected: FAIL — `ImportError: cannot import name 'reset_user_password'`.

- [ ] **Step 3: Implement the handler**

Add to `api/admin_users.py` after `update_user_status` (i.e. after line 387):

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
    admin_user, auth_err = _get_admin_user(request)
    if auth_err:
        return auth_err
    assert admin_user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    password = body.get("password") or ""
    if not password:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Password is required", "fields": {"password": "Password is required"}}},
            status_code=400,
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        msg = f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": msg, "fields": {"password": msg}}},
            status_code=400,
        )

    org_id = admin_user["org_id"]
    _, member_err = _verify_user_in_org(user_id, org_id)
    if member_err:
        return member_err

    sb = get_supabase()
    try:
        sb.auth.admin.update_user_by_id(user_id, {"password": password})
    except Exception as e:
        logger.error("Failed to reset password for user %s: %s", user_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to reset password"}},
            status_code=500,
        )

    return JSONResponse({"success": True, "data": {"user_id": user_id}})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_admin_users_password.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint**

Run: `ruff check api/admin_users.py tests/test_admin_users_password.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add api/admin_users.py tests/test_admin_users_password.py
git commit -m "feat(admin): reset_user_password handler (admin sets a user's password)"
```

---

## Task 5: Register the route + routing tests

**Files:**
- Modify: `api/routers/admin.py`
- Test: `tests/test_api_routers_admin.py`

- [ ] **Step 1: Write the failing routing/schema tests**

Add to `tests/test_api_routers_admin.py` inside `TestAdminRoutesRegistered`:

```python
    def test_patch_user_password_registered(self, subapp_client: TestClient) -> None:
        """PATCH /admin/users/{user_id}/password must exist."""
        response = subapp_client.patch(
            "/admin/users/11111111-1111-1111-1111-111111111111/password", json={}
        )
        assert response.status_code != 404
```

And add to `TestAdminOpenApiSchema.test_schema_declares_correct_methods` (after the existing asserts):

```python
        assert "patch" in paths["/admin/users/{user_id}/password"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_api_routers_admin.py -v -k "password or correct_methods"`
Expected: FAIL — route returns 404 / path missing from schema.

- [ ] **Step 3: Register the route**

In `api/routers/admin.py`, add to the import block (alphabetical, after `create_user`):

```python
    reset_user_password as _reset_user_password,
```

And add the route alongside the other `{user_id}` routes (after `patch_admin_user_roles`):

```python
@router.patch("/users/{user_id}/password")
async def patch_admin_user_password(request: Request, user_id: str) -> JSONResponse:
    """Reset a user's password."""
    return await _reset_user_password(request, user_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_api_routers_admin.py -v`
Expected: PASS (all, including the two new assertions).

- [ ] **Step 5: Commit**

```bash
git add api/routers/admin.py tests/test_api_routers_admin.py
git commit -m "feat(admin): register PATCH /api/admin/users/{id}/password"
```

---

## Task 6: `resetUserPasswordAction` server action

**Files:**
- Modify: `frontend/src/features/admin-users/actions.ts`

- [ ] **Step 1: Add the action**

Append to `frontend/src/features/admin-users/actions.ts`:

```ts
export async function resetUserPasswordAction(
  userId: string,
  password: string
): Promise<ApiResponse<{ user_id: string }>> {
  const res = await apiServerClient<{ user_id: string }>(
    `/admin/users/${userId}/password`,
    {
      method: "PATCH",
      body: JSON.stringify({ password }),
    }
  );
  if (res.success) {
    revalidatePath("/admin/users");
  }
  return res;
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/admin-users/actions.ts
git commit -m "feat(admin-users): resetUserPasswordAction server action"
```

---

## Task 7: «Сброс пароля» section in UserEditSheet

**Files:**
- Modify: `frontend/src/features/admin-users/ui/user-edit-sheet.tsx`

- [ ] **Step 1: Add imports**

Add to the import block of `user-edit-sheet.tsx`:

```ts
import { PasswordGenerateInput } from "@/shared/ui/password-generate-input";
```

And extend the existing actions import (currently `updateUserRolesAction, updateUserStatusAction`) to include `resetUserPasswordAction`:

```ts
import {
  resetUserPasswordAction,
  updateUserRolesAction,
  updateUserStatusAction,
} from "@/features/admin-users/actions";
```

- [ ] **Step 2: Add state + handler**

Add near the other `useState` hooks (after the status state block, ~line 106):

```ts
  // Password reset state
  const [newPassword, setNewPassword] = useState("");
  const [resettingPassword, setResettingPassword] = useState(false);
```

Add this handler near `handleStatusChange`:

```ts
  async function handleResetPassword() {
    if (newPassword.length < 8) {
      toast.error("Пароль должен быть не короче 8 символов");
      return;
    }
    setResettingPassword(true);
    try {
      const res = await resetUserPasswordAction(member.user_id, newPassword);
      if (res.success) {
        toast.success("Пароль сброшен");
        setNewPassword("");
      } else {
        toast.error(res.error?.message ?? "Ошибка сброса пароля");
      }
    } catch {
      toast.error("Ошибка сброса пароля");
    } finally {
      setResettingPassword(false);
    }
  }
```

- [ ] **Step 3: Add the section JSX**

Insert after the Status `</section>` and before the closing `</div>` of the
sheet body (i.e. after line 456, before line 457's `</div>`):

```tsx
            <Separator />

            {/* Section: Password reset */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Сброс пароля
              </h3>
              <p className="text-xs text-muted-foreground">
                Передайте новый пароль пользователю. Он сможет сменить его в
                своём профиле.
              </p>
              <PasswordGenerateInput
                value={newPassword}
                onChange={setNewPassword}
              />
              <Button
                onClick={handleResetPassword}
                disabled={resettingPassword || newPassword.length < 8}
                size="sm"
                className="self-end"
              >
                {resettingPassword && (
                  <Loader2 size={14} className="animate-spin" />
                )}
                Сбросить пароль
              </Button>
            </section>
```

- [ ] **Step 4: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin-users/ui/user-edit-sheet.tsx
git commit -m "feat(admin-users): admin password reset section in UserEditSheet"
```

---

## Task 8: `changePassword` self-service mutation (TDD)

**Files:**
- Modify: `frontend/src/entities/profile/mutations.ts`
- Test: `frontend/src/entities/profile/__tests__/change-password.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/entities/profile/__tests__/change-password.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

const signInWithPassword = vi.fn();
const updateUser = vi.fn();

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signInWithPassword, updateUser } }),
}));

import { changePassword } from "@/entities/profile/mutations";

describe("changePassword", () => {
  beforeEach(() => {
    signInWithPassword.mockReset();
    updateUser.mockReset();
  });

  it("re-verifies the current password then updates", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    updateUser.mockResolvedValue({ error: null });

    await changePassword("u@x.com", "oldpw123", "newpw456");

    expect(signInWithPassword).toHaveBeenCalledWith({
      email: "u@x.com",
      password: "oldpw123",
    });
    expect(updateUser).toHaveBeenCalledWith({ password: "newpw456" });
  });

  it("throws CURRENT_PASSWORD_INVALID and does NOT update when current password is wrong", async () => {
    signInWithPassword.mockResolvedValue({ error: { message: "bad" } });

    await expect(
      changePassword("u@x.com", "wrong", "newpw456")
    ).rejects.toThrow("CURRENT_PASSWORD_INVALID");
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("propagates an updateUser error", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    updateUser.mockResolvedValue({ error: new Error("weak password") });

    await expect(
      changePassword("u@x.com", "oldpw123", "x")
    ).rejects.toThrow("weak password");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/entities/profile/__tests__/change-password.test.ts`
Expected: FAIL — `changePassword` is not exported.

- [ ] **Step 3: Implement the mutation**

Append to `frontend/src/entities/profile/mutations.ts`:

```ts
/**
 * Self-service password change. Re-verifies the current password (Supabase has
 * no dedicated "verify password" call) before setting the new one. Supabase
 * returns a fresh session, so the user stays logged in.
 */
export async function changePassword(
  email: string,
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const supabase = createClient();

  const { error: verifyError } = await supabase.auth.signInWithPassword({
    email,
    password: currentPassword,
  });
  if (verifyError) {
    throw new Error("CURRENT_PASSWORD_INVALID");
  }

  const { error: updateError } = await supabase.auth.updateUser({
    password: newPassword,
  });
  if (updateError) throw updateError;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/entities/profile/__tests__/change-password.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/entities/profile/mutations.ts frontend/src/entities/profile/__tests__/change-password.test.ts
git commit -m "feat(profile): changePassword self-service mutation"
```

---

## Task 9: `ChangePasswordSection` UI + wire into /profile

**Files:**
- Create: `frontend/src/features/profile/ui/change-password-section.tsx`
- Test: `frontend/src/features/profile/ui/__tests__/change-password-section.dom.test.tsx`
- Modify: `frontend/src/features/profile/index.ts`
- Modify: `frontend/src/app/(app)/profile/page.tsx`

- [ ] **Step 1: Write the failing component test**

```tsx
// frontend/src/features/profile/ui/__tests__/change-password-section.dom.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const changePassword = vi.fn();
vi.mock("@/entities/profile/mutations", () => ({ changePassword }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

import { ChangePasswordSection } from "@/features/profile/ui/change-password-section";

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("ChangePasswordSection", () => {
  beforeEach(() => changePassword.mockReset());

  it("rejects a new password shorter than 8 chars", async () => {
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "oldpw123");
    fill("Новый пароль", "short");
    fill("Повторите новый пароль", "short");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    expect(await screen.findByText(/не короче 8/i)).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("rejects mismatched confirmation", async () => {
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "oldpw123");
    fill("Новый пароль", "newpw456");
    fill("Повторите новый пароль", "different");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    expect(await screen.findByText(/не совпадают/i)).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("calls changePassword on a valid submit", async () => {
    changePassword.mockResolvedValue(undefined);
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "oldpw123");
    fill("Новый пароль", "newpw456");
    fill("Повторите новый пароль", "newpw456");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    await waitFor(() =>
      expect(changePassword).toHaveBeenCalledWith("u@x.com", "oldpw123", "newpw456")
    );
  });

  it("shows a field error when the current password is wrong", async () => {
    changePassword.mockRejectedValue(new Error("CURRENT_PASSWORD_INVALID"));
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "wrongpw1");
    fill("Новый пароль", "newpw456");
    fill("Повторите новый пароль", "newpw456");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    expect(await screen.findByText(/неверный текущий пароль/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/features/profile/ui/__tests__/change-password-section.dom.test.tsx`
Expected: FAIL — cannot resolve `@/features/profile/ui/change-password-section`.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/features/profile/ui/change-password-section.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { changePassword } from "@/entities/profile/mutations";

interface Props {
  email: string;
}

export function ChangePasswordSection({ email }: Props) {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!current || !next || !confirm) {
      setError("Заполните все поля");
      return;
    }
    if (next.length < 8) {
      setError("Новый пароль должен быть не короче 8 символов");
      return;
    }
    if (next !== confirm) {
      setError("Пароли не совпадают");
      return;
    }
    if (next === current) {
      setError("Новый пароль совпадает с текущим");
      return;
    }

    setSaving(true);
    try {
      await changePassword(email, current, next);
      toast.success("Пароль изменён");
      setCurrent("");
      setNext("");
      setConfirm("");
      router.refresh();
    } catch (err) {
      if (err instanceof Error && err.message === "CURRENT_PASSWORD_INVALID") {
        setError("Неверный текущий пароль");
      } else {
        toast.error("Не удалось сменить пароль");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Смена пароля</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-sm">
          <div className="space-y-1.5">
            <Label htmlFor="cp-current">Текущий пароль</Label>
            <Input
              id="cp-current"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-next">Новый пароль</Label>
            <Input
              id="cp-next"
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-confirm">Повторите новый пароль</Label>
            <Input
              id="cp-confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            type="submit"
            disabled={saving}
            className="self-start bg-accent text-white hover:bg-accent-hover"
          >
            {saving ? "Сохранение..." : "Сменить пароль"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

> Note: `<Label htmlFor>` + matching `<Input id>` is what makes
> `getByLabelText` work in the test — keep the ids in sync.

- [ ] **Step 4: Export from the feature barrel**

Replace `frontend/src/features/profile/index.ts` contents with:

```ts
export { ProfileForm } from "./ui/profile-form";
export { ChangePasswordSection } from "./ui/change-password-section";
```

- [ ] **Step 5: Wire into the profile page**

In `frontend/src/app/(app)/profile/page.tsx`:
- Update the import on line 5 to also pull `ChangePasswordSection`:

```ts
import { ProfileForm, ChangePasswordSection } from "@/features/profile";
```

- Render it inside the returned `<div className="space-y-6">`, after `TelegramSection` (after line 43):

```tsx
      <ChangePasswordSection email={user.email} />
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/features/profile/ui/__tests__/change-password-section.dom.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/profile/ui/change-password-section.tsx frontend/src/features/profile/ui/__tests__/change-password-section.dom.test.tsx frontend/src/features/profile/index.ts "frontend/src/app/(app)/profile/page.tsx"
git commit -m "feat(profile): self-service change-password section on /profile"
```

---

## Task 10: Full verification + finish

**Files:** none (verification only)

- [ ] **Step 1: Full frontend test + typecheck + lint**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: all green.

- [ ] **Step 2: Full backend test + lint**

Run: `python3 -m pytest tests/test_admin_users_password.py tests/test_api_routers_admin.py -v && ruff check api/admin_users.py api/routers/admin.py tests/test_admin_users_password.py`
Expected: all green.

- [ ] **Step 3: Manual verification (localhost:3000 + prod Supabase)**

Per the standard pre-deploy flow (`frontend/.env.local`):
1. Log in as a normal user → `/profile` → «Смена пароля»: wrong current → inline
   "Неверный текущий пароль"; correct current + matching new ≥8 → "Пароль изменён",
   still logged in. Log out + log back in with the new password.
2. Log in as admin → `/admin/users` → open a user → «Сброс пароля»: generate →
   copy → "Сбросить пароль" → "Пароль сброшен". Verify that user can log in with
   the new password, then change it themselves via step 1.

- [ ] **Step 4: Finish the branch**

Use superpowers:finishing-a-development-branch to open the PR (base `main`,
head `feat/password-change`).

---

## Self-Review

**Spec coverage**
- Self-service (current→new→confirm, re-verify, no re-login) → Tasks 8, 9. ✓
- Admin reset (manual hand-off, generate/copy) → Tasks 4-7. ✓
- Shared widget extraction (no drift) → Tasks 1-3. ✓
- min-8 client+server, password never logged, org-scoped, no last-admin guard → Tasks 4, 7, 9. ✓
- Email/Telegram out of scope → not implemented (correct). ✓

**Placeholder scan:** none — every step has real code + commands.

**Type/name consistency:** `generatePassword`/`PASSWORD_CHARSET` (T1) used in T2; `PasswordGenerateInput(value,onChange,id,error)` (T2) used in T3/T7; `resetUserPasswordAction(userId,password)` (T6) used in T7; `reset_user_password(request,user_id)` (T4) used in T5; `changePassword(email,current,new)` (T8) used in T9; `ChangePasswordSection({email})` (T9) used in profile page. ✓
