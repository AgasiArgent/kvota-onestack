# Frontend Foundation (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the Next.js frontend with auth, layout, sidebar, design system, and Supabase client — producing a working app shell that renders the sidebar and a placeholder dashboard page.

**Architecture:** Next.js 15 (App Router) with FSD structure. Supabase Auth via `@supabase/ssr`. Design tokens ported from `design-system.md` to Tailwind config. shadcn/ui for base components. Thin `api/` Python layer for JWT validation.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS v4, shadcn/ui, `@supabase/ssr`, `lucide-react` (icons)

**Spec:** `docs/superpowers/specs/2026-03-10-frontend-migration-design.md`

---

## Chunk 1: Project Scaffold + Tooling

### Task 1: Initialize Next.js project

**Files:**
- Create: `frontend/package.json` (via create-next-app)
- Create: `frontend/next.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/.gitignore`

- [ ] **Step 1: Create Next.js app**

```bash
cd /Users/andreynovikov/workspace/tech/projects/kvota/onestack
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-turbopack
```

Select defaults for all prompts. This creates `frontend/` with App Router, TypeScript, Tailwind, ESLint.

- [ ] **Step 2: Verify it runs**

```bash
cd frontend && npm run dev
```

Expected: Next.js dev server starts on `http://localhost:3000`, shows default page.

- [ ] **Step 3: Clean default content**

Remove default Next.js boilerplate from `frontend/src/app/page.tsx` — replace with minimal placeholder:

```tsx
// frontend/src/app/page.tsx
export default function Home() {
  return <div>OneStack</div>;
}
```

Remove default styles from `frontend/src/app/globals.css` — keep only Tailwind directives:

```css
/* frontend/src/app/globals.css */
@import "tailwindcss";
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Next.js 15 frontend scaffold"
```

---

### Task 2: Set up FSD directory structure

**Files:**
- Create: `frontend/src/shared/ui/.gitkeep`
- Create: `frontend/src/shared/lib/.gitkeep`
- Create: `frontend/src/shared/config/index.ts`
- Create: `frontend/src/shared/types/.gitkeep`
- Create: `frontend/src/entities/.gitkeep`
- Create: `frontend/src/features/.gitkeep`
- Create: `frontend/src/widgets/.gitkeep`

- [ ] **Step 1: Create FSD layer directories**

```bash
cd frontend/src
mkdir -p shared/{ui,lib,config,types} entities features widgets
touch shared/ui/.gitkeep shared/lib/.gitkeep shared/types/.gitkeep
touch entities/.gitkeep features/.gitkeep widgets/.gitkeep
```

- [ ] **Step 2: Create shared config with env vars**

```typescript
// frontend/src/shared/config/index.ts
export const config = {
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL!,
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  pythonApiUrl: process.env.PYTHON_API_URL || "http://localhost:5001",
  appBaseUrl: process.env.NEXT_PUBLIC_APP_BASE_URL || "http://localhost:3000",
} as const;
```

- [ ] **Step 3: Create .env.local.example template**

```bash
# frontend/.env.local.example
# Copy to .env.local and fill in values
NEXT_PUBLIC_SUPABASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
PYTHON_API_URL=http://localhost:5001
NEXT_PUBLIC_APP_BASE_URL=http://localhost:3000
```

Ensure `frontend/.gitignore` includes `.env.local` (Next.js default .gitignore already does).

- [ ] **Step 4: Add FSD lint rule to .eslintrc**

Add import restriction to prevent upward imports across FSD layers:

```jsonc
// Add to frontend/eslint.config.mjs (or equivalent)
// Rule: entities cannot import from features/widgets/pages
// features cannot import from widgets/pages
// This is advisory for now — enforced by code review
```

Note: Full FSD lint enforcement with `eslint-plugin-boundaries` can be added later. For now, the directory structure + code review enforces the rule.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared frontend/src/entities frontend/src/features frontend/src/widgets frontend/.env.local.example
git commit -m "feat: add FSD directory structure and shared config"
```

---

### Task 3: Install and configure shadcn/ui

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/shared/ui/button.tsx` (first component)
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init
```

When prompted:
- Style: Default
- Base color: Slate
- CSS variables: yes
- Source directory: `src`
- Components location: `src/shared/ui`
- Utilities location: `src/shared/lib/utils`

This creates `components.json` and sets up the CSS variables.

- [ ] **Step 2: Install first component (Button)**

```bash
npx shadcn@latest add button
```

Verify: `frontend/src/shared/ui/button.tsx` exists.

- [ ] **Step 3: Install additional base components**

```bash
npx shadcn@latest add card input label badge separator avatar dropdown-menu tooltip sheet scroll-area
```

These are the base components needed for the sidebar and layout.

- [ ] **Step 4: Install lucide-react for icons**

```bash
npm install lucide-react
```

The existing FastHTML app uses Lucide icons (same icon set). This ensures visual consistency.

- [ ] **Step 5: Verify build**

```bash
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: configure shadcn/ui with base components"
```

---

### Task 4: Port design system tokens to Tailwind config

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/tailwind.config.ts` (if exists) or CSS variables

Reference: `design-system.md` in project root — the source of truth for all visual tokens.

- [ ] **Step 1: Add CSS custom properties matching design system**

Add to `frontend/src/app/globals.css` after the Tailwind directives:

```css
@import "tailwindcss";

/* Register custom tokens for Tailwind v4 utilities (e.g. bg-bg-page, text-text-primary) */
@theme {
  --color-bg-page: #f8fafc;
  --color-bg-card: #ffffff;
  --color-border: #e2e8f0;
  --color-text-primary: #1e293b;
  --color-text-secondary: #64748b;
  --color-text-muted: #94a3b8;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;
}

@layer base {
  :root {
    /* === Primary: Blue === */
    --blue-50: #eff6ff;
    --blue-100: #dbeafe;
    --blue-200: #bfdbfe;
    --blue-300: #93c5fd;
    --blue-400: #60a5fa;
    --blue-500: #3b82f6;
    --blue-600: #2563eb;
    --blue-700: #1d4ed8;
    --blue-800: #1e40af;
    --blue-900: #1e3a8a;

    /* === Gray: Slate (blue-tinted) === */
    --bg-page: #f8fafc;
    --bg-card: #ffffff;
    --border-color: #e2e8f0;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
    --shadow-subtle: 0 1px 4px rgba(0, 0, 0, 0.06);

    /* === Semantic === */
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
    --info: #3b82f6;

    /* === Status Badges === */
    --badge-draft-bg: #fef3c7;
    --badge-draft-text: #92400e;
    --badge-progress-bg: #dbeafe;
    --badge-progress-text: #1e40af;
    --badge-approved-bg: #d1fae5;
    --badge-approved-text: #065f46;
    --badge-rejected-bg: #fee2e2;
    --badge-rejected-text: #991b1b;
    --badge-pending-bg: #fef3c7;
    --badge-pending-text: #92400e;
    --badge-cancelled-bg: #f3f4f6;
    --badge-cancelled-text: #4b5563;

    /* === Typography === */
    --text-2xs: 11px;
    --text-xs: 12px;
    --text-sm: 14px;
    --text-base: 16px;
    --text-lg: 18px;
    --text-xl: 20px;
    --text-2xl: 24px;

    /* === Sidebar === */
    --sidebar-width: 260px;
    --sidebar-collapsed-width: 60px;

    /* === Layout === */
    --content-max-width: 1200px;
    --form-max-width: 600px;
  }

  /* Sidebar-aware main content margin */
  .sidebar-margin {
    margin-left: var(--sidebar-width);
    transition: margin-left 0.2s ease;
  }
  html[data-sidebar-collapsed="true"] .sidebar-margin {
    margin-left: var(--sidebar-collapsed-width);
  }

  /* Dark mode overrides */
  .dark {
    --bg-page: #0f172a;
    --bg-card: #1e293b;
    --border-color: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --shadow-subtle: 0 1px 4px rgba(0, 0, 0, 0.3);
  }
}

/* === Font: Inter === */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

@layer base {
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: var(--text-primary);
    background: var(--bg-page);
  }

  h1, h2, h3, h4, h5, h6 {
    line-height: 1.25;
    letter-spacing: -0.01em;
  }
}
```

- [ ] **Step 2: Verify styles render**

Update `frontend/src/app/page.tsx` to test tokens:

```tsx
import { Button } from "@/shared/ui/button";

export default function Home() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">OneStack</h1>
      <Button>Test Button</Button>
    </div>
  );
}
```

Run `npm run dev` — verify Inter font loads, button renders with blue primary.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/globals.css frontend/src/app/page.tsx
git commit -m "feat: port design system tokens to Tailwind CSS variables"
```

---

## Chunk 2: Supabase Auth + Middleware

### Task 5: Set up Supabase client (browser + server)

**Files:**
- Create: `frontend/src/shared/lib/supabase/client.ts`
- Create: `frontend/src/shared/lib/supabase/server.ts`
- Create: `frontend/src/shared/lib/supabase/middleware.ts`

**Important:** The Supabase instance uses the `kvota` schema (not `public`). All client initializations must set `db: { schema: 'kvota' }`.

- [ ] **Step 1: Install Supabase packages**

```bash
cd frontend
npm install @supabase/supabase-js @supabase/ssr
```

- [ ] **Step 2: Create browser client**

```typescript
// frontend/src/shared/lib/supabase/client.ts
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      db: { schema: "kvota" },
    }
  );
}
```

- [ ] **Step 3: Create server client**

```typescript
// frontend/src/shared/lib/supabase/server.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      db: { schema: "kvota" },
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing sessions.
          }
        },
      },
    }
  );
}
```

- [ ] **Step 4: Create middleware helper**

```typescript
// frontend/src/shared/lib/supabase/middleware.ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      db: { schema: "kvota" },
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Refresh session if expired
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Redirect to login if not authenticated (except login page itself)
  if (
    !user &&
    !request.nextUrl.pathname.startsWith("/login") &&
    !request.nextUrl.pathname.startsWith("/auth")
  ) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/lib/supabase/
git commit -m "feat: add Supabase client (browser + server + middleware)"
```

---

### Task 6: Add Next.js auth middleware

**Files:**
- Create: `frontend/src/middleware.ts`

- [ ] **Step 1: Create middleware**

```typescript
// frontend/src/middleware.ts
import { type NextRequest } from "next/server";
import { updateSession } from "@/shared/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     * - public files (images, etc.)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
```

- [ ] **Step 2: Verify middleware runs**

Start dev server. Visit `http://localhost:3000` without being logged in. Should redirect to `/login`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "feat: add auth middleware with session refresh"
```

---

### Task 7: Create login page

**Files:**
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/features/auth/login-form.tsx`

- [ ] **Step 1: Create login form component**

```tsx
// frontend/src/features/auth/login-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/shared/lib/supabase/client";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/ui/card";
import { Layers, LogIn } from "lucide-react";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(
        authError.message.includes("Invalid login credentials")
          ? "Неверный email или пароль"
          : authError.message
      );
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-slate-100 via-slate-200 to-slate-100">
      <Card className="w-full max-w-[420px] shadow-lg">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-700 rounded-[14px] flex items-center justify-center shadow-md">
            <Layers className="text-white" size={28} />
          </div>
          <div>
            <CardTitle className="text-2xl font-bold tracking-tight">OneStack</CardTitle>
            <CardDescription>Система управления коммерческими предложениями</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1">
              <Label htmlFor="email" className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Электронная почта
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password" className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Пароль
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-md">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              <LogIn size={18} />
              {loading ? "Вход..." : "Войти в систему"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Create login page**

```tsx
// frontend/src/app/login/page.tsx
import { redirect } from "next/navigation";
import { createClient } from "@/shared/lib/supabase/server";
import { LoginForm } from "@/features/auth/login-form";

export default async function LoginPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (user) {
    redirect("/dashboard");
  }

  return <LoginForm />;
}
```

- [ ] **Step 3: Verify login works**

Run dev server. Navigate to `/login`. Enter valid credentials. Should redirect to `/dashboard` (which will show the placeholder for now).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/login/ frontend/src/features/auth/
git commit -m "feat: add login page with Supabase auth"
```

---

## Chunk 3: User Context + Sidebar Layout

### Task 8: Create user context with role loading

**Files:**
- Create: `frontend/src/entities/user/types.ts`
- Create: `frontend/src/entities/user/get-session-user.ts`
- Create: `frontend/src/entities/user/index.ts`

The current FastHTML app loads user roles from `organization_members` → `user_roles` → `roles` tables. The Next.js app needs the same data.

- [ ] **Step 1: Define user types**

```typescript
// frontend/src/entities/user/types.ts
export interface SessionUser {
  id: string;
  email: string;
  orgId: string | null;
  orgName: string;
  roles: string[];
}

// All active roles in the system (from migration 168)
export const ACTIVE_ROLES = [
  "admin",
  "sales",
  "procurement",
  "logistics",
  "customs",
  "quote_controller",
  "spec_controller",
  "finance",
  "top_manager",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
] as const;

export type RoleCode = (typeof ACTIVE_ROLES)[number];

export const ROLE_LABELS_RU: Record<string, string> = {
  admin: "Администратор",
  sales: "Продажи",
  procurement: "Закупки",
  logistics: "Логистика",
  customs: "Таможня",
  quote_controller: "Контроль КП",
  spec_controller: "Контроль спецификаций",
  finance: "Финансы",
  top_manager: "Руководитель",
  head_of_sales: "Руководитель продаж",
  head_of_procurement: "Руководитель закупок",
  head_of_logistics: "Руководитель логистики",
  training_manager: "Менеджер обучения",
  currency_controller: "Валютный контроль",
};
```

- [ ] **Step 2: Create server-side user loader**

```typescript
// frontend/src/entities/user/get-session-user.ts
import { createClient } from "@/shared/lib/supabase/server";
import type { SessionUser } from "./types";

export async function getSessionUser(): Promise<SessionUser | null> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) return null;

  // Get organization membership
  const { data: orgMembers } = await supabase
    .from("organization_members")
    .select("organization_id, organizations(id, name)")
    .eq("user_id", user.id)
    .eq("status", "active")
    .limit(1);

  const orgData = orgMembers?.[0];
  const orgId = orgData?.organization_id ?? null;
  const orgName = (orgData?.organizations as { name: string } | null)?.name ?? "No Organization";

  // Get user roles
  let roles: string[] = [];
  if (orgId) {
    const { data: userRoles } = await supabase
      .from("user_roles")
      .select("roles(slug)")
      .eq("user_id", user.id)
      .eq("organization_id", orgId);

    roles = (userRoles ?? [])
      .map((ur) => (ur.roles as { slug: string } | null)?.slug)
      .filter((slug): slug is string => slug !== null && slug !== undefined);

    // training_manager gets all roles (super-role for demos)
    if (roles.includes("training_manager")) {
      const allRoles = [
        "admin", "sales", "procurement", "logistics", "customs",
        "quote_controller", "spec_controller", "finance",
        "top_manager", "head_of_sales", "head_of_procurement",
        "head_of_logistics", "training_manager",
      ];
      roles = [...new Set([...roles, ...allRoles])];
    }
  }

  return {
    id: user.id,
    email: user.email ?? "",
    orgId,
    orgName,
    roles,
  };
}
```

- [ ] **Step 3: Create barrel export**

```typescript
// frontend/src/entities/user/index.ts
export type { SessionUser, RoleCode } from "./types";
export { ACTIVE_ROLES, ROLE_LABELS_RU } from "./types";
export { getSessionUser } from "./get-session-user";
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/entities/user/
git commit -m "feat: add user entity with role loading from Supabase"
```

---

### Task 9: Create sidebar widget

**Files:**
- Create: `frontend/src/widgets/sidebar/sidebar.tsx`
- Create: `frontend/src/widgets/sidebar/sidebar-menu.ts`
- Create: `frontend/src/widgets/sidebar/index.ts`

Port the sidebar menu structure from `main.py:2696-2776` to a declarative config.

- [ ] **Step 1: Define menu structure**

```typescript
// frontend/src/widgets/sidebar/sidebar-menu.ts
import type { LucideIcon } from "lucide-react";
import {
  Inbox, PlayCircle, Newspaper, Send, PlusCircle, BarChart3,
  Clock, Users, FileText, Building2, ClipboardList, Phone,
  Building, Calendar, User, MessageSquare, GitBranch, Settings,
} from "lucide-react";

export interface MenuItem {
  icon: LucideIcon;
  label: string;
  href: string;
  roles: string[] | null; // null = visible to all authenticated users
  badge?: number;
}

export interface MenuSection {
  title: string;
  items: MenuItem[];
}

interface MenuConfig {
  roles: string[];
  isAdmin: boolean;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
}

export function buildMenuSections(config: MenuConfig): MenuSection[] {
  const { roles, isAdmin, pendingApprovalsCount = 0, changelogUnreadCount = 0 } = config;
  const hasRole = (...r: string[]) => isAdmin || r.some((role) => roles.includes(role));
  const sections: MenuSection[] = [];

  // === MAIN ===
  const mainItems: MenuItem[] = [
    { icon: Inbox, label: "Мои задачи", href: "/tasks", roles: null },
    { icon: PlayCircle, label: "Обучение", href: "/training", roles: null },
    {
      icon: Newspaper, label: "Обновления", href: "/changelog", roles: null,
      ...(changelogUnreadCount > 0 ? { badge: changelogUnreadCount } : {}),
    },
    { icon: Send, label: "Уведомления", href: "/telegram", roles: null },
  ];

  if (hasRole("sales", "sales_manager")) {
    mainItems.push({ icon: PlusCircle, label: "Новый КП", href: "/quotes/new", roles: ["sales", "sales_manager", "admin"] });
  }
  if (hasRole("top_manager", "sales", "sales_manager", "head_of_sales", "procurement", "logistics", "head_of_logistics", "customs", "quote_controller", "spec_controller", "finance")) {
    mainItems.push({ icon: BarChart3, label: "Обзор", href: "/dashboard?tab=overview", roles: null });
  }
  if (hasRole("top_manager")) {
    mainItems.push({
      icon: Clock, label: "Согласования", href: "/approvals", roles: ["admin", "top_manager"],
      ...(pendingApprovalsCount > 0 ? { badge: pendingApprovalsCount } : {}),
    });
  }
  sections.push({ title: "Главное", items: mainItems });

  // === REGISTRIES ===
  const registries: MenuItem[] = [];
  if (hasRole("sales", "sales_manager", "top_manager", "head_of_sales")) {
    registries.push({ icon: Users, label: "Клиенты", href: "/customers", roles: ["sales", "sales_manager", "admin", "top_manager", "head_of_sales"] });
  }
  registries.push({ icon: FileText, label: "Коммерческие предложения", href: "/quotes", roles: null });
  if (hasRole("procurement")) {
    registries.push({ icon: Building2, label: "Поставщики", href: "/suppliers", roles: ["procurement", "admin"] });
    registries.push({ icon: ClipboardList, label: "Очередь PHMB", href: "/phmb/procurement", roles: ["procurement", "admin"] });
  }
  if (hasRole("customs", "finance")) {
    registries.push({ icon: FileText, label: "Таможенные декларации", href: "/customs/declarations", roles: ["customs", "finance", "admin"] });
  }
  if (hasRole("sales", "sales_manager", "top_manager")) {
    registries.push({ icon: Phone, label: "Журнал звонков", href: "/calls", roles: ["sales", "sales_manager", "top_manager", "admin"] });
  }
  if (isAdmin) {
    registries.push({ icon: Building, label: "Юрлица", href: "/companies", roles: ["admin"] });
  }
  if (registries.length > 0) {
    sections.push({ title: "Реестры", items: registries });
  }

  // === FINANCE ===
  if (hasRole("finance", "top_manager", "currency_controller")) {
    const financeItems: MenuItem[] = [
      { icon: FileText, label: "Контроль платежей", href: "/finance?tab=erps", roles: ["finance", "top_manager", "admin"] },
      { icon: Calendar, label: "Календарь", href: "/payments/calendar", roles: ["finance", "top_manager", "admin"] },
    ];
    if (hasRole("currency_controller")) {
      financeItems.push({ icon: FileText, label: "Валютные инвойсы", href: "/currency-invoices", roles: ["currency_controller", "admin"] });
    }
    sections.push({ title: "Финансы", items: financeItems });
  }

  // === ADMIN ===
  if (isAdmin) {
    sections.push({
      title: "Администрирование",
      items: [
        { icon: User, label: "Пользователи", href: "/admin", roles: ["admin"] },
        { icon: MessageSquare, label: "Обращения", href: "/admin/feedback", roles: ["admin"] },
        { icon: GitBranch, label: "Маршрутизация закупок", href: "/admin/procurement-groups", roles: ["admin"] },
        { icon: Settings, label: "Настройки", href: "/settings", roles: ["admin"] },
      ],
    });
  }

  return sections;
}
```

- [ ] **Step 2: Create sidebar component**

```tsx
// frontend/src/widgets/sidebar/sidebar.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Moon, Sun, Menu } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback } from "@/shared/ui/avatar";
import { Badge } from "@/shared/ui/badge";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { Separator } from "@/shared/ui/separator";
import { cn } from "@/shared/lib/utils";
import type { SessionUser } from "@/entities/user";
import { buildMenuSections } from "./sidebar-menu";

interface SidebarProps {
  user: SessionUser;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
}

export function Sidebar({ user, pendingApprovalsCount = 0, changelogUnreadCount = 0 }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    document.documentElement.setAttribute("data-sidebar-collapsed", String(next));
  }

  const isAdmin = user.roles.includes("admin") || user.roles.includes("training_manager");
  const sections = buildMenuSections({
    roles: user.roles,
    isAdmin,
    pendingApprovalsCount,
    changelogUnreadCount,
  });

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
  }

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const initials = user.email[0]?.toUpperCase() ?? "U";

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700 flex flex-col z-50 transition-[width] duration-200",
        collapsed ? "w-[60px]" : "w-[260px]"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-14 border-b border-slate-200 dark:border-slate-700">
        {!collapsed && (
          <Link href="/dashboard" className="font-semibold text-lg text-blue-600">
            Kvota
          </Link>
        )}
        <div className="flex items-center gap-1">
          <button onClick={toggleTheme} className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800" title="Переключить тему">
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <button onClick={toggleCollapsed} className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800" title="Свернуть панель">
            <Menu size={18} />
          </button>
        </div>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1">
        <nav className="py-2">
          {sections.map((section, idx) => (
            <div key={section.title} className="mb-1">
              {!collapsed && (
                <div className="px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {section.title}
                </div>
              )}
              {section.items.map((item) => {
                const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href.split("?")[0]));
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href + item.label}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400"
                        : "text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800",
                      collapsed && "justify-center px-0"
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    <Icon size={20} className="shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                    {!collapsed && item.badge && (
                      <Badge variant="destructive" className="ml-auto text-[10px] px-1.5 py-0 min-w-[18px] text-center">
                        {item.badge}
                      </Badge>
                    )}
                  </Link>
                );
              })}
              {idx < sections.length - 1 && <Separator className="my-1" />}
            </div>
          ))}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t border-slate-200 dark:border-slate-700 p-3">
        <Link href="/profile" className="flex items-center gap-3 mb-2">
          <Avatar className="h-8 w-8">
            <AvatarFallback className="bg-blue-100 text-blue-700 text-sm">{initials}</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-sm truncate">{user.email}</p>
              <p className="text-xs text-blue-500">Профиль</p>
            </div>
          )}
        </Link>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-600 text-xs w-full px-1"
          title="Выйти из системы"
        >
          <LogOut size={16} />
          {!collapsed && <span>Выйти</span>}
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Create barrel export**

```typescript
// frontend/src/widgets/sidebar/index.ts
export { Sidebar } from "./sidebar";
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/widgets/sidebar/
git commit -m "feat: add sidebar widget with role-based menu"
```

---

### Task 10: Create app layout with sidebar

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/(app)/layout.tsx`
- Create: `frontend/src/app/(app)/dashboard/page.tsx`

Use Next.js route groups: `(app)` for authenticated pages with sidebar, login page has no sidebar.

- [ ] **Step 1: Update root layout**

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OneStack",
  description: "Система управления коммерческими предложениями",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body className="antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Create authenticated layout with sidebar**

```tsx
// frontend/src/app/(app)/layout.tsx
import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { Sidebar } from "@/widgets/sidebar";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  if (!user) {
    redirect("/login");
  }

  // Sidebar is a client component that manages its own collapse state.
  // Main content uses CSS transition to match sidebar width changes.
  // The sidebar broadcasts its collapsed state via a data attribute on <html>.
  return (
    <div className="flex min-h-screen">
      <Sidebar user={user} />
      <main className="flex-1 sidebar-margin p-6 max-w-[1200px]">
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Create dashboard placeholder**

```tsx
// frontend/src/app/(app)/dashboard/page.tsx
export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Дашборд</h1>
      <p className="text-slate-500">Скоро здесь появится обзорная панель.</p>
    </div>
  );
}
```

- [ ] **Step 4: Remove old root page**

Update `frontend/src/app/page.tsx` to redirect to dashboard:

```tsx
// frontend/src/app/page.tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
```

- [ ] **Step 5: Verify full flow**

1. `npm run dev`
2. Visit `http://localhost:3000` → redirects to `/login`
3. Log in with valid credentials → redirects to `/dashboard`
4. Sidebar visible with correct menu items for user's role
5. Clicking sidebar items navigates (pages show 404 for now — expected)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/
git commit -m "feat: add app layout with sidebar and auth-gated routes"
```

---

## Chunk 4: Python API Layer + Docker

### Task 11: Create Python API router for JWT-authenticated endpoints

**Files:**
- Create: `api/__init__.py`
- Create: `api/auth.py`
- Modify: `main.py` (mount API router)

This adds JWT validation for the `/api/*` endpoints that Next.js will call.

- [ ] **Step 1: Create API auth middleware**

```python
# api/auth.py
"""JWT validation middleware for /api/* endpoints called by the Next.js frontend.

All /api/* routes (except /api/health) require a valid Supabase JWT.
This is enforced as Starlette middleware, not a per-handler decorator,
so new API endpoints are protected by default.
"""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Paths under /api/ that don't require auth
PUBLIC_API_PATHS = {"/api/health"}


def get_user_from_token(auth_header: str):
    """Extract and validate Supabase JWT from Authorization header value."""
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    try:
        from gotrue import SyncGoTrueClient
        gotrue = SyncGoTrueClient(
            url=f"{SUPABASE_URL}/auth/v1",
            headers={"apikey": SUPABASE_ANON_KEY},
        )
        user = gotrue.get_user(token)
        return user.user if user else None
    except Exception:
        return None


class ApiAuthMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to /api/* (except public paths)."""

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Only apply to /api/* routes
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip public endpoints
        if path in PUBLIC_API_PATHS:
            return await call_next(request)

        # Validate JWT
        auth_header = request.headers.get("authorization", "")
        user = get_user_from_token(auth_header)
        if not user:
            return JSONResponse(
                {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid or missing token"}},
                status_code=401,
            )

        # Attach user to request state for downstream handlers
        request.state.api_user = user
        return await call_next(request)
```

- [ ] **Step 2: Create API router init**

```python
# api/__init__.py
"""
Thin JSON API layer for Next.js frontend.
Mounted at /api/* in main.py.

Endpoints here are called by the Next.js app for operations
that require server-side Python (calculation, workflow, exports).
Simple CRUD goes directly through Supabase client in Next.js.
"""
```

- [ ] **Step 3: Mount API in main.py**

Two changes to main.py:

**A)** After `app = fast_app(...)` initialization (around line 136-140), add the middleware:

```python
# JWT auth middleware for /api/* endpoints (Next.js frontend)
from api.auth import ApiAuthMiddleware
app.add_middleware(ApiAuthMiddleware)
```

**B)** Before `serve()` at the end (around line 49244), add the health check:

```python
# === API: Health check (for Next.js frontend) ===
@rt("/api/health")
def get():
    return JSONResponse({"success": True, "status": "ok"})
```

Note: The middleware protects all `/api/*` routes by default (except `/api/health`). New API endpoints added in later phases are automatically authenticated — no decorator needed per handler.

- [ ] **Step 4: Verify API health endpoint**

```bash
curl http://localhost:5001/api/health
```

Expected: `{"success":true,"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add api/ main.py
git commit -m "feat: add Python API layer with JWT auth and health endpoint"
```

---

### Task 12: Add frontend to Docker Compose

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS base

# Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Build
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_APP_BASE_URL

ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_APP_BASE_URL=$NEXT_PUBLIC_APP_BASE_URL

RUN npm run build

# Production
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

- [ ] **Step 2: Add standalone output to next.config**

```typescript
// frontend/next.config.ts — add output: "standalone"
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [ ] **Step 3: Update docker-compose.prod.yml**

```yaml
version: '3.8'

services:
  onestack:
    build: .
    container_name: kvota-onestack
    restart: unless-stopped
    ports:
      - "5001:5001"
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - APP_SECRET=${APP_SECRET}
      - DEBUG=false
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
      - TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME:-}
      - TELEGRAM_WEBHOOK_URL=${TELEGRAM_WEBHOOK_URL:-}
      - ADMIN_TELEGRAM_CHAT_ID=${ADMIN_TELEGRAM_CHAT_ID:-}
      - DADATA_API_KEY=${DADATA_API_KEY:-}
      - HERE_API_KEY=${HERE_API_KEY:-}
      - CLICKUP_API_KEY=${CLICKUP_API_KEY:-}
      - CLICKUP_BUG_LIST_ID=${CLICKUP_BUG_LIST_ID:-}
      - APP_BASE_URL=${APP_BASE_URL:-https://kvotaflow.ru}
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5001/login')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - kvota-network

  frontend:
    build:
      context: ./frontend
      args:
        # PUBLIC_ vars are embedded at build time and sent to browser — must be publicly reachable URLs
        - NEXT_PUBLIC_SUPABASE_URL=${PUBLIC_SUPABASE_URL}
        - NEXT_PUBLIC_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
        - NEXT_PUBLIC_APP_BASE_URL=${APP_BASE_URL:-https://kvotaflow.ru}
    container_name: kvota-frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - PYTHON_API_URL=http://kvota-onestack:5001
      # Runtime server-side env vars (not embedded in browser bundle)
      - NEXT_PUBLIC_SUPABASE_URL=${PUBLIC_SUPABASE_URL}
      - NEXT_PUBLIC_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
    depends_on:
      - onestack
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - kvota-network

networks:
  kvota-network:
    driver: bridge
```

- [ ] **Step 4: Verify Docker build**

```bash
cd frontend && docker build -t kvota-frontend-test .
```

Expected: Build succeeds. Image created.

- [ ] **Step 5: Commit**

```bash
git add frontend/Dockerfile frontend/next.config.ts docker-compose.prod.yml
git commit -m "feat: add frontend Docker container to compose"
```

---

### Task 13: Create Python API client for Next.js

**Files:**
- Create: `frontend/src/shared/lib/api.ts`

This is how the Next.js app calls the Python backend (for calculation, workflow, exports).

- [ ] **Step 1: Create API client**

Two variants — one for client components (browser), one for server components/route handlers.

```typescript
// frontend/src/shared/lib/api.ts

/**
 * Python API client for CLIENT components (browser-side).
 * Uses browser Supabase client to get JWT from session.
 */
"use client";

import { createClient } from "@/shared/lib/supabase/client";

const PYTHON_API_URL = process.env.NEXT_PUBLIC_PYTHON_API_URL || "";

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export async function apiClient<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  const response = await fetch(`${PYTHON_API_URL}/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
      ...options.headers,
    },
  });

  return response.json();
}
```

```typescript
// frontend/src/shared/lib/api-server.ts

/**
 * Python API client for SERVER components and Route Handlers.
 * Uses server Supabase client (cookie-based) to get JWT.
 * Only import this in server-side code.
 */
import { createClient } from "@/shared/lib/supabase/server";

const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://localhost:5001";

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export async function apiServerClient<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();

  const response = await fetch(`${PYTHON_API_URL}/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
      ...options.headers,
    },
  });

  return response.json();
}
```

Note: The browser client uses `NEXT_PUBLIC_PYTHON_API_URL` (empty string = same origin, proxied by Caddy). The server client uses `PYTHON_API_URL` (internal Docker network URL).

- [ ] **Step 2: Verify health check call**

Add a temporary test to the dashboard page:

```tsx
// Temporary: test API connectivity
// Remove after verification
```

Actually, skip manual test — the health endpoint is simple enough. Test it when integrating the first real API endpoint.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/shared/lib/api.ts
git commit -m "feat: add Python API client with JWT auth header"
```

---

## Summary

**Phase 1 produces:**
- Next.js 15 app with FSD structure
- Supabase Auth (login/logout, session refresh, middleware)
- Sidebar with full role-based menu (matching FastHTML exactly)
- Design system tokens ported to CSS variables
- shadcn/ui base components installed
- Python API auth layer (JWT validation)
- Docker container ready for deployment
- API client for Next.js → Python communication

**Phase 1 does NOT include:**
- Any user-facing page content (only placeholder dashboard)
- Caddy config changes (deployed separately when ready)
- Real-time subscriptions (Phase 2: Chat)
- Any FastHTML code deletion

---

## Chunk 5: Feedback Widget (First Real Component)

**Spec:** `docs/superpowers/specs/2026-03-13-feedback-widget-nextjs-design.md`

Migrates the feedback widget ("жучок") from FastHTML to a React component. First real feature on the Next.js foundation. Uses existing Python API `/api/feedback` with JWT auth, uploads screenshots to Supabase Storage.

### Task 14: Backend — DB migration + Storage bucket + API dual-auth

**Files:**
- Create: `migrations/213_add_screenshot_url.sql`
- Modify: `main.py:25790-25920` (submit_feedback endpoint)
- Modify: `main.py:31593+` (admin detail page — screenshot display)

This task updates the Python backend to support both FastHTML session auth and JWT auth on the `/api/feedback` endpoint, adds a `screenshot_url` column, and creates the Supabase Storage bucket.

- [ ] **Step 1: Create DB migration**

```sql
-- migrations/213_add_screenshot_url.sql
-- Add screenshot_url column for Supabase Storage URLs (Next.js widget)
-- Existing screenshot_data (base64) kept for backward compat with FastHTML widget
ALTER TABLE kvota.user_feedback ADD COLUMN IF NOT EXISTS screenshot_url TEXT;
```

- [ ] **Step 2: Apply migration**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"ALTER TABLE kvota.user_feedback ADD COLUMN IF NOT EXISTS screenshot_url TEXT;\""
```

- [ ] **Step 3: Create Supabase Storage bucket**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('feedback-screenshots', 'feedback-screenshots', true, 5242880, ARRAY['image/jpeg', 'image/png'])
ON CONFLICT (id) DO NOTHING;
\""
```

Note: `public: true` means files are readable via public URL. Upload still requires auth (RLS policy below).

- [ ] **Step 4: Add Storage RLS policy for authenticated uploads**

```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c \"
CREATE POLICY feedback_screenshot_upload ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'feedback-screenshots');

CREATE POLICY feedback_screenshot_read ON storage.objects
  FOR SELECT TO anon, authenticated
  USING (bucket_id = 'feedback-screenshots');
\""
```

- [ ] **Step 5: Update `/api/feedback` endpoint for dual auth + screenshot_url**

In `main.py`, update the `submit_feedback` function to:
1. Accept user from JWT (`request.state.api_user`) OR FastHTML session
2. Accept JSON body (from Next.js) in addition to form data (from FastHTML)
3. Accept `screenshot_url` field

Replace the endpoint (lines ~25790-25920):

```python
@rt("/api/feedback", methods=["POST"])
async def submit_feedback(session, request: Request):
    """Handle feedback submission from both FastHTML (form) and Next.js (JSON)."""
    import json as json_lib
    import logging
    logger = logging.getLogger(__name__)

    # Dual auth: JWT (Next.js) or session (FastHTML)
    api_user = getattr(request.state, 'api_user', None)
    if api_user:
        # JWT auth — look up user details from DB
        user_meta = api_user.user_metadata or {}
        user = {
            "id": str(api_user.id),
            "email": api_user.email or "",
            "name": user_meta.get("name", api_user.email or ""),
            "org_id": user_meta.get("org_id"),
            "org_name": user_meta.get("org_name", ""),
        }
    else:
        user = session.get("user", {})

    # Dual input: JSON (Next.js) or form (FastHTML)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    feedback_type = body.get("feedback_type", "bug")
    description = body.get("description", "").strip()
    page_url = body.get("page_url", "")
    page_title = body.get("page_title", "")
    debug_context_str = body.get("debug_context", "{}")
    screenshot_data = body.get("screenshot", "").strip() if body.get("screenshot") else ""
    screenshot_url = body.get("screenshot_url", "").strip() if body.get("screenshot_url") else ""

    if not description:
        if "application/json" in content_type:
            return JSONResponse({"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Description required"}}, status_code=400)
        return Div("Пожалуйста, опишите проблему", cls="text-error mt-2")

    try:
        debug_context = json_lib.loads(debug_context_str) if isinstance(debug_context_str, str) else debug_context_str
    except Exception:
        debug_context = {}

    short_id = generate_feedback_short_id()
    supabase = get_supabase()

    # Strip data URI prefix for base64 storage
    screenshot_b64 = None
    if screenshot_data and screenshot_data.startswith("data:image"):
        screenshot_b64 = screenshot_data.split(",", 1)[1] if "," in screenshot_data else None

    try:
        org_id = user.get("org_id")
        try:
            if org_id:
                org_check = supabase.table("organizations").select("id").eq("id", org_id).limit(1).execute()
                if not org_check.data:
                    org_id = None
        except Exception:
            pass

        insert_payload = {
            "short_id": short_id,
            "user_id": user.get("id"),
            "user_email": user.get("email"),
            "user_name": user.get("name", user.get("email", "Неизвестный")),
            "organization_id": org_id,
            "organization_name": user.get("org_name", ""),
            "page_url": page_url,
            "page_title": page_title,
            "user_agent": request.headers.get("user-agent", ""),
            "feedback_type": feedback_type,
            "description": description,
            "debug_context": debug_context,
        }
        if screenshot_b64:
            insert_payload["screenshot_data"] = screenshot_b64
        if screenshot_url:
            insert_payload["screenshot_url"] = screenshot_url

        # Retry with new short_id on UNIQUE constraint violation
        for attempt in range(3):
            try:
                supabase.table("user_feedback").insert(insert_payload).execute()
                break
            except Exception as insert_err:
                if "duplicate" in str(insert_err).lower() and attempt < 2:
                    short_id = generate_feedback_short_id()
                    insert_payload["short_id"] = short_id
                    continue
                raise

        # ClickUp + Telegram (best-effort, unchanged)
        clickup_task_id = None
        try:
            admin_url = f"{os.getenv('APP_BASE_URL', 'https://kvotaflow.ru')}/admin/feedback/{short_id}"
            clickup_task_id = await create_clickup_bug_task(
                short_id=short_id, feedback_type=feedback_type,
                description=description,
                user_name=user.get("name", user.get("email", "Неизвестный")),
                user_email=user.get("email", ""),
                org_name=user.get("org_name", ""),
                page_url=page_url, debug_context=debug_context,
                admin_url=admin_url, has_screenshot=bool(screenshot_b64 or screenshot_url)
            )
            if clickup_task_id:
                supabase.table("user_feedback").update(
                    {"clickup_task_id": clickup_task_id}
                ).eq("short_id", short_id).execute()
        except Exception as e:
            logger.warning(f"ClickUp task creation failed for {short_id}: {e}")

        try:
            clickup_url = f"https://app.clickup.com/t/{clickup_task_id}" if clickup_task_id else None
            await send_admin_bug_report_with_photo(
                short_id=short_id,
                user_name=user.get("name", user.get("email", "Неизвестный")),
                user_email=user.get("email", ""),
                org_name=user.get("org_name", ""),
                page_url=page_url, feedback_type=feedback_type,
                description=description, debug_context=debug_context,
                screenshot_b64=screenshot_b64, clickup_url=clickup_url
            )
        except Exception as e:
            logger.warning(f"Telegram notification failed for {short_id}: {e}")

        # Dual response: JSON (Next.js) or HTML (FastHTML)
        if "application/json" in content_type:
            return JSONResponse({"success": True, "data": {"short_id": short_id}})

        return Div(
            Div(id="feedback-success-marker", style="display:none"),
            Div("Спасибо за обратную связь!", cls="text-success font-medium"),
            P(f"Номер обращения: {short_id}", cls="text-sm text-gray-500 mt-1 font-mono"),
            btn("Закрыть", variant="secondary", size="sm", onclick="closeFeedbackModal()", type="button")
        )

    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        if "application/json" in content_type:
            return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Failed to save feedback"}}, status_code=500)

        return Div(
            Div("Ошибка при отправке", cls="text-error font-medium"),
            P("Попробуйте ещё раз через несколько секунд", cls="text-sm text-gray-500 mt-1"),
            btn("Попробовать снова", variant="secondary", size="sm",
                onclick="document.getElementById('feedback-result').innerHTML=''", type="button", cls="mt-2"),
            cls="mt-2"
        )
```

- [ ] **Step 6: Update admin detail page to show screenshot_url**

Find the admin feedback detail handler (around line 31593+). Where it renders the screenshot, add a check for `screenshot_url` first:

```python
# In the admin detail rendering, before the base64 screenshot display:
screenshot_url = feedback.get("screenshot_url")
screenshot_b64 = feedback.get("screenshot_data")

if screenshot_url:
    screenshot_el = Img(src=screenshot_url, cls="max-w-full rounded-lg border", style="max-height: 500px;")
elif screenshot_b64:
    screenshot_el = Img(src=f"data:image/jpeg;base64,{screenshot_b64}", cls="max-w-full rounded-lg border", style="max-height: 500px;")
else:
    screenshot_el = P("Скриншот не прикреплён", cls="text-sm text-gray-400")
```

- [ ] **Step 7: Commit**

```bash
git add migrations/213_add_screenshot_url.sql main.py
git commit -m "feat: add screenshot_url column, dual-auth + JSON support on /api/feedback"
```

---

### Task 15: Debug context collector + submission API client

**Files:**
- Create: `frontend/src/features/feedback/lib/debugContext.ts`
- Create: `frontend/src/features/feedback/api/submitFeedback.ts`
- Create: `frontend/src/features/feedback/index.ts`

- [ ] **Step 1: Create debug context collector**

```typescript
// frontend/src/features/feedback/lib/debugContext.ts

interface ConsoleEntry {
  type: "error" | "warn" | "exception";
  message: string;
  time: string;
}

interface DebugContext {
  url: string;
  title: string;
  userAgent: string;
  screenSize: string;
  consoleErrors: ConsoleEntry[];
  collectedAt: string;
}

// Circular buffer for console errors (max 10)
const consoleErrors: ConsoleEntry[] = [];
let interceptorsInstalled = false;

function pushError(entry: ConsoleEntry) {
  consoleErrors.push(entry);
  if (consoleErrors.length > 10) consoleErrors.shift();
}

/** Install console.error/warn interceptors. Call once at app init. */
export function installErrorInterceptors() {
  if (interceptorsInstalled) return;
  interceptorsInstalled = true;

  const origError = console.error;
  console.error = (...args: unknown[]) => {
    pushError({ type: "error", message: args.map(String).join(" "), time: new Date().toISOString() });
    origError.apply(console, args);
  };

  const origWarn = console.warn;
  console.warn = (...args: unknown[]) => {
    pushError({ type: "warn", message: args.map(String).join(" "), time: new Date().toISOString() });
    origWarn.apply(console, args);
  };

  window.addEventListener("error", (e) => {
    pushError({ type: "exception", message: `${e.message} at ${e.filename}:${e.lineno}`, time: new Date().toISOString() });
  });
}

/** Collect current debug context snapshot. */
export function collectDebugContext(): DebugContext {
  return {
    url: window.location.href,
    title: document.title,
    userAgent: navigator.userAgent,
    screenSize: `${window.innerWidth}x${window.innerHeight}`,
    consoleErrors: consoleErrors.slice(-5),
    collectedAt: new Date().toISOString(),
  };
}
```

- [ ] **Step 2: Create screenshot compression utility**

```typescript
// frontend/src/features/feedback/lib/compressScreenshot.ts

const MAX_WIDTH = 1280;
const JPEG_QUALITY = 0.7;

/** Resize image to max width and compress as JPEG. Returns data URL. */
export function compressScreenshot(dataUrl: string): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      let w = img.width;
      let h = img.height;
      if (w > MAX_WIDTH) {
        h = Math.round((h * MAX_WIDTH) / w);
        w = MAX_WIDTH;
      }
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      canvas.getContext("2d")!.drawImage(img, 0, 0, w, h);
      resolve(canvas.toDataURL("image/jpeg", JPEG_QUALITY));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}

/** Convert data URL to Blob for upload. */
export function dataUrlToBlob(dataUrl: string): Blob {
  const [header, base64] = dataUrl.split(",");
  const mime = header.match(/:(.*?);/)?.[1] || "image/jpeg";
  const bytes = atob(base64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return new Blob([arr], { type: mime });
}
```

- [ ] **Step 3: Create submission API function**

```typescript
// frontend/src/features/feedback/api/submitFeedback.ts
"use client";

import { createClient } from "@/shared/lib/supabase/client";
import { dataUrlToBlob } from "../lib/compressScreenshot";

export type FeedbackType = "bug" | "ux_ui" | "suggestion" | "question";

interface SubmitFeedbackParams {
  feedbackType: FeedbackType;
  description: string;
  pageUrl: string;
  pageTitle: string;
  debugContext: Record<string, unknown>;
  screenshotDataUrl?: string; // compressed JPEG data URL
}

interface SubmitResult {
  success: boolean;
  shortId?: string;
  error?: string;
}

export async function submitFeedback(params: SubmitFeedbackParams): Promise<SubmitResult> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  if (!session) {
    return { success: false, error: "Not authenticated" };
  }

  let screenshotUrl = "";

  // Upload screenshot to Supabase Storage if present
  if (params.screenshotDataUrl) {
    try {
      const blob = dataUrlToBlob(params.screenshotDataUrl);
      const timestamp = Date.now();
      const path = `${session.user.id}/${timestamp}.jpg`;

      const { error: uploadError } = await supabase.storage
        .from("feedback-screenshots")
        .upload(path, blob, { contentType: "image/jpeg", upsert: false });

      if (uploadError) throw uploadError;

      const { data: urlData } = supabase.storage
        .from("feedback-screenshots")
        .getPublicUrl(path);

      screenshotUrl = urlData.publicUrl;
    } catch (err) {
      console.warn("Screenshot upload failed, submitting without:", err);
      // Continue without screenshot — don't block submission
    }
  }

  // POST to Python API
  try {
    const apiBaseUrl = process.env.NEXT_PUBLIC_PYTHON_API_URL || "";
    const response = await fetch(`${apiBaseUrl}/api/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        feedback_type: params.feedbackType,
        description: params.description,
        page_url: params.pageUrl,
        page_title: params.pageTitle,
        debug_context: params.debugContext,
        screenshot_url: screenshotUrl,
      }),
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
      return { success: false, error: result.error?.message || "Submit failed" };
    }
    return { success: true, shortId: result.data?.short_id };
  } catch (err) {
    return { success: false, error: "Network error" };
  }
}
```

- [ ] **Step 4: Create feature barrel export**

```typescript
// frontend/src/features/feedback/index.ts
export { FeedbackButton } from "./ui/FeedbackButton";
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/feedback/lib/ frontend/src/features/feedback/api/ frontend/src/features/feedback/index.ts
git commit -m "feat: add feedback submission API + debug context collector"
```

---

### Task 16: FeedbackButton + FeedbackModal

**Files:**
- Create: `frontend/src/features/feedback/ui/FeedbackButton.tsx`
- Create: `frontend/src/features/feedback/ui/FeedbackModal.tsx`

- [ ] **Step 1: Create FeedbackModal**

```tsx
// frontend/src/features/feedback/ui/FeedbackModal.tsx
"use client";

import { useState, useCallback } from "react";
import { Bug, Send, X, Camera } from "lucide-react";
import { submitFeedback, type FeedbackType } from "../api/submitFeedback";
import { collectDebugContext } from "../lib/debugContext";

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
  onScreenshotRequest: () => void;
  screenshotDataUrl?: string;
  onClearScreenshot: () => void;
}

const FEEDBACK_TYPES: { value: FeedbackType; label: string }[] = [
  { value: "bug", label: "Ошибка" },
  { value: "ux_ui", label: "UX / UI" },
  { value: "suggestion", label: "Предложение" },
  { value: "question", label: "Вопрос" },
];

export function FeedbackModal({
  open,
  onClose,
  onScreenshotRequest,
  screenshotDataUrl,
  onClearScreenshot,
}: FeedbackModalProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("bug");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; shortId?: string; error?: string } | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!description.trim()) return;
    setSubmitting(true);
    setResult(null);

    const debugContext = collectDebugContext();
    const res = await submitFeedback({
      feedbackType,
      description: description.trim(),
      pageUrl: debugContext.url,
      pageTitle: debugContext.title,
      debugContext,
      screenshotDataUrl,
    });

    setSubmitting(false);

    if (res.success) {
      setResult(res);
      // Auto-close after 2s on success
      setTimeout(() => {
        resetAndClose();
      }, 2000);
    } else {
      setResult(res);
    }
  }, [feedbackType, description, screenshotDataUrl]);

  const resetAndClose = useCallback(() => {
    setFeedbackType("bug");
    setDescription("");
    setResult(null);
    onClearScreenshot();
    onClose();
  }, [onClose, onClearScreenshot]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-[999]"
        onClick={resetAndClose}
      />
      {/* Modal */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl p-6 z-[1000] w-[90%] max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Bug size={20} className="text-slate-500" />
            <h3 className="text-lg font-semibold text-slate-800">Обратная связь</h3>
          </div>
          <button onClick={resetAndClose} className="p-1 hover:bg-slate-100 rounded">
            <X size={18} className="text-slate-400" />
          </button>
        </div>

        {/* Result */}
        {result && (
          <div className={`mb-4 p-3 rounded-md ${result.success ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}>
            {result.success ? (
              <>
                <p className="text-green-700 font-medium">Спасибо за обратную связь!</p>
                <p className="text-sm text-green-600 font-mono mt-1">Номер: {result.shortId}</p>
              </>
            ) : (
              <>
                <p className="text-red-700 font-medium">Ошибка при отправке</p>
                <p className="text-sm text-red-600 mt-1">Попробуйте ещё раз через несколько секунд</p>
                <button
                  onClick={() => setResult(null)}
                  className="mt-2 text-sm text-red-700 underline hover:no-underline"
                >
                  Попробовать снова
                </button>
              </>
            )}
          </div>
        )}

        {/* Form (hide after success) */}
        {!result?.success && (
          <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
            {/* Type selector */}
            <div className="mb-3">
              <label className="text-xs font-medium text-slate-500 mb-1 block">Тип</label>
              <div className="flex gap-2 flex-wrap">
                {FEEDBACK_TYPES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setFeedbackType(t.value)}
                    className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                      feedbackType === t.value
                        ? "bg-blue-50 border-blue-300 text-blue-700"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Description */}
            <div className="mb-3">
              <label className="text-xs font-medium text-slate-500 mb-1 block">Описание *</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Опишите проблему или предложение..."
                rows={4}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 resize-y"
                required
              />
            </div>

            {/* Screenshot */}
            <div className="mb-4">
              <label className="text-xs font-medium text-slate-500 mb-1 block">Скриншот</label>
              {screenshotDataUrl ? (
                <div className="relative inline-block">
                  <img
                    src={screenshotDataUrl}
                    alt="Screenshot"
                    className="max-h-32 rounded border border-slate-200"
                  />
                  <button
                    type="button"
                    onClick={onClearScreenshot}
                    className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-0.5"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={onScreenshotRequest}
                  className="flex items-center gap-2 px-3 py-2 text-sm border border-dashed border-slate-300 rounded-md text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors"
                >
                  <Camera size={16} />
                  Добавить скриншот
                </button>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting || !description.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-500 text-white rounded-md font-medium text-sm hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? (
                <span className="animate-spin h-4 w-4 border-2 border-white/30 border-t-white rounded-full" />
              ) : (
                <Send size={16} />
              )}
              {submitting ? "Отправка..." : "Отправить"}
            </button>
          </form>
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 2: Create FeedbackButton (orchestrator component)**

```tsx
// frontend/src/features/feedback/ui/FeedbackButton.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Bug } from "lucide-react";
import { FeedbackModal } from "./FeedbackModal";
import { AnnotationEditor } from "./AnnotationEditor";
import { captureScreenshot } from "./ScreenshotCapture";
import { installErrorInterceptors } from "../lib/debugContext";

export function FeedbackButton() {
  const [modalOpen, setModalOpen] = useState(false);
  const [screenshotDataUrl, setScreenshotDataUrl] = useState<string>();
  const [annotatorOpen, setAnnotatorOpen] = useState(false);
  const [rawScreenshot, setRawScreenshot] = useState<string>();

  useEffect(() => {
    installErrorInterceptors();
  }, []);

  const handleScreenshotRequest = useCallback(async () => {
    setModalOpen(false); // Hide modal during capture
    try {
      const dataUrl = await captureScreenshot();
      setRawScreenshot(dataUrl);
      setAnnotatorOpen(true);
    } catch {
      // Capture failed — re-show modal without screenshot
      setModalOpen(true);
    }
  }, []);

  const handleAnnotationSave = useCallback((annotatedDataUrl: string) => {
    setScreenshotDataUrl(annotatedDataUrl);
    setAnnotatorOpen(false);
    setRawScreenshot(undefined);
    setModalOpen(true);
  }, []);

  const handleAnnotationCancel = useCallback(() => {
    setAnnotatorOpen(false);
    setRawScreenshot(undefined);
    setModalOpen(true);
  }, []);

  const handleClearScreenshot = useCallback(() => {
    setScreenshotDataUrl(undefined);
  }, []);

  return (
    <>
      {/* Floating bug button */}
      <button
        onClick={() => setModalOpen(true)}
        className="fixed bottom-4 right-4 z-50 w-16 h-16 flex items-center justify-center bg-white border border-slate-200 rounded-lg text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-md cursor-pointer transition-colors"
        title="Сообщить о проблеме"
        type="button"
      >
        <Bug size={36} />
      </button>

      {/* Modal */}
      <FeedbackModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onScreenshotRequest={handleScreenshotRequest}
        screenshotDataUrl={screenshotDataUrl}
        onClearScreenshot={handleClearScreenshot}
      />

      {/* Annotation editor overlay */}
      {annotatorOpen && rawScreenshot && (
        <AnnotationEditor
          screenshotDataUrl={rawScreenshot}
          onSave={handleAnnotationSave}
          onCancel={handleAnnotationCancel}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/feedback/ui/FeedbackButton.tsx frontend/src/features/feedback/ui/FeedbackModal.tsx
git commit -m "feat: add FeedbackButton and FeedbackModal React components"
```

---

### Task 17: Screenshot capture with html2canvas

**Files:**
- Create: `frontend/src/features/feedback/ui/ScreenshotCapture.ts`

- [ ] **Step 1: Install html2canvas**

```bash
cd frontend && npm install html2canvas
```

- [ ] **Step 2: Create screenshot capture function**

```typescript
// frontend/src/features/feedback/ui/ScreenshotCapture.ts
import html2canvas from "html2canvas";
import { compressScreenshot } from "../lib/compressScreenshot";

/** Capture page screenshot, compress, and return as JPEG data URL. */
export async function captureScreenshot(): Promise<string> {
  const canvas = await html2canvas(document.body, {
    useCORS: true,
    allowTaint: true,
    scale: 0.75,
    ignoreElements: (el) => {
      // Ignore feedback widget elements
      return el.id === "feedback-modal" || el.classList?.contains("feedback-overlay");
    },
    onclone: (clonedDoc) => {
      // Fix oklch() colors that html2canvas cannot parse (Tailwind v4 uses oklch)
      const styles = clonedDoc.querySelectorAll("style");
      styles.forEach((s) => {
        if (s.textContent?.includes("oklch")) {
          s.textContent = s.textContent.replace(/oklch\([^)]*\)/g, "#888888");
        }
      });

      const all = clonedDoc.querySelectorAll("*");
      const colorProps = [
        "color", "background-color", "border-color",
        "border-top-color", "border-right-color",
        "border-bottom-color", "border-left-color",
      ];
      all.forEach((el) => {
        try {
          const cs = clonedDoc.defaultView?.getComputedStyle(el);
          if (!cs) return;
          colorProps.forEach((prop) => {
            const val = cs.getPropertyValue(prop);
            if (val?.includes("oklch")) {
              (el as HTMLElement).style.setProperty(prop, "#888888", "important");
            }
          });
        } catch {
          // Skip inaccessible elements
        }
      });
    },
  });

  const rawDataUrl = canvas.toDataURL("image/png");
  return compressScreenshot(rawDataUrl);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/feedback/ui/ScreenshotCapture.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: add screenshot capture with html2canvas and oklch fix"
```

---

### Task 18: Annotation editor (canvas drawing tools)

**Files:**
- Create: `frontend/src/features/feedback/ui/AnnotationEditor.tsx`

- [ ] **Step 1: Create AnnotationEditor component**

This is the most complex component — a full-screen canvas overlay with brush, arrow, and text tools plus undo.

```tsx
// frontend/src/features/feedback/ui/AnnotationEditor.tsx
"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Pencil, ArrowUpRight, Type, Undo2, Check, X } from "lucide-react";
import { compressScreenshot } from "../lib/compressScreenshot";

type Tool = "brush" | "arrow" | "text";

interface AnnotationEditorProps {
  screenshotDataUrl: string;
  onSave: (annotatedDataUrl: string) => void;
  onCancel: () => void;
}

const STROKE_COLOR = "#ff3333";
const STROKE_WIDTH = 3;
const ARROW_HEAD_LEN = 18;
const MAX_UNDO = 20;

export function AnnotationEditor({ screenshotDataUrl, onSave, onCancel }: AnnotationEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tool, setTool] = useState<Tool>("brush");
  const [imageLoaded, setImageLoaded] = useState(false);
  const undoStackRef = useRef<ImageData[]>([]);
  const drawStateRef = useRef({
    isDrawing: false,
    startX: 0,
    startY: 0,
    arrowSnapshot: null as ImageData | null,
  });
  const bgImageRef = useRef<HTMLImageElement | null>(null);

  // Load background image + set canvas size
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      bgImageRef.current = img;
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = img.width;
      canvas.height = img.height;
      setImageLoaded(true);
    };
    img.src = screenshotDataUrl;
  }, [screenshotDataUrl]);

  const getCtx = useCallback(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) {
      ctx.strokeStyle = STROKE_COLOR;
      ctx.fillStyle = STROKE_COLOR;
      ctx.lineWidth = STROKE_WIDTH;
      ctx.lineCap = "round";
    }
    return ctx;
  }, []);

  const saveState = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = getCtx();
    if (!canvas || !ctx) return;
    if (undoStackRef.current.length >= MAX_UNDO) undoStackRef.current.shift();
    undoStackRef.current.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
  }, [getCtx]);

  const undo = useCallback(() => {
    const ctx = getCtx();
    if (!ctx || undoStackRef.current.length === 0) return;
    const prev = undoStackRef.current.pop()!;
    ctx.putImageData(prev, 0, 0);
  }, [getCtx]);

  const getPos = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (canvas.width / rect.width),
      y: (e.clientY - rect.top) * (canvas.height / rect.height),
    };
  }, []);

  const drawArrow = useCallback((ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) => {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - ARROW_HEAD_LEN * Math.cos(angle - Math.PI / 6), y2 - ARROW_HEAD_LEN * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(x2 - ARROW_HEAD_LEN * Math.cos(angle + Math.PI / 6), y2 - ARROW_HEAD_LEN * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fill();
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (tool === "text") {
      handleTextPlace(e);
      return;
    }
    const ctx = getCtx();
    if (!ctx) return;
    const pos = getPos(e);
    const state = drawStateRef.current;
    state.isDrawing = true;
    state.startX = pos.x;
    state.startY = pos.y;
    saveState();
    if (tool === "brush") {
      ctx.beginPath();
      ctx.moveTo(pos.x, pos.y);
    }
    if (tool === "arrow") {
      const canvas = canvasRef.current!;
      state.arrowSnapshot = ctx.getImageData(0, 0, canvas.width, canvas.height);
    }
  }, [tool, getCtx, getPos, saveState]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const state = drawStateRef.current;
    if (!state.isDrawing) return;
    const ctx = getCtx();
    if (!ctx) return;
    const pos = getPos(e);
    if (tool === "brush") {
      ctx.lineTo(pos.x, pos.y);
      ctx.stroke();
    }
    if (tool === "arrow" && state.arrowSnapshot) {
      ctx.putImageData(state.arrowSnapshot, 0, 0);
      drawArrow(ctx, state.startX, state.startY, pos.x, pos.y);
    }
  }, [tool, getCtx, getPos, drawArrow]);

  const handleMouseUp = useCallback((e: React.MouseEvent) => {
    const state = drawStateRef.current;
    if (!state.isDrawing) return;
    state.isDrawing = false;
    if (tool === "arrow" && state.arrowSnapshot) {
      const ctx = getCtx();
      if (ctx) {
        const pos = getPos(e);
        ctx.putImageData(state.arrowSnapshot, 0, 0);
        drawArrow(ctx, state.startX, state.startY, pos.x, pos.y);
      }
      state.arrowSnapshot = null;
    }
  }, [tool, getCtx, getPos, drawArrow]);

  const handleTextPlace = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const displayX = e.clientX - rect.left;
    const displayY = e.clientY - rect.top;

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Введите текст...";
    input.style.cssText = `position:fixed;left:${rect.left + displayX}px;top:${rect.top + displayY - 14}px;background:#222;color:${STROKE_COLOR};border:2px solid ${STROKE_COLOR};padding:4px 8px;font:bold 18px sans-serif;z-index:10001;min-width:150px;outline:none;border-radius:4px;`;
    document.body.appendChild(input);
    input.addEventListener("mousedown", (ev) => ev.stopPropagation());

    let committed = false;
    const commitText = () => {
      if (committed) return;
      committed = true;
      const text = input.value.trim();
      if (text) {
        const ctx = getCtx();
        if (ctx) {
          saveState();
          ctx.font = "bold 20px sans-serif";
          ctx.fillStyle = STROKE_COLOR;
          ctx.fillText(text, displayX * scaleX, displayY * scaleY);
        }
      }
      input.remove();
    };

    setTimeout(() => {
      input.focus();
      input.addEventListener("blur", commitText);
    }, 50);
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") commitText();
      if (ev.key === "Escape") { input.remove(); }
    });
  }, [getCtx, saveState]);

  const handleSave = useCallback(async () => {
    const canvas = canvasRef.current;
    const bgImg = bgImageRef.current;
    if (!canvas || !bgImg) return;

    // Merge background + annotations into final canvas
    const finalCanvas = document.createElement("canvas");
    finalCanvas.width = canvas.width;
    finalCanvas.height = canvas.height;
    const ctx = finalCanvas.getContext("2d")!;
    ctx.drawImage(bgImg, 0, 0);
    ctx.drawImage(canvas, 0, 0);

    const rawDataUrl = finalCanvas.toDataURL("image/png");
    const compressed = await compressScreenshot(rawDataUrl);
    onSave(compressed);
  }, [onSave]);

  const tools: { id: Tool; icon: typeof Pencil; label: string }[] = [
    { id: "brush", icon: Pencil, label: "Кисть" },
    { id: "arrow", icon: ArrowUpRight, label: "Стрелка" },
    { id: "text", icon: Type, label: "Текст" },
  ];

  return (
    <div className="fixed inset-0 z-[9999] bg-neutral-900 flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 bg-neutral-800 shrink-0">
        {tools.map((t) => (
          <button
            key={t.id}
            onClick={() => setTool(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm ${
              tool === t.id ? "bg-red-500/80 text-white" : "bg-neutral-700 text-neutral-300 hover:bg-neutral-600"
            }`}
            title={t.label}
          >
            <t.icon size={16} />
            {t.label}
          </button>
        ))}
        <button onClick={undo} className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-neutral-700 text-neutral-400 hover:bg-neutral-600 ml-2" title="Отменить">
          <Undo2 size={16} />
        </button>
        <div className="flex-1" />
        <button onClick={handleSave} className="flex items-center gap-1.5 px-4 py-1.5 rounded text-sm bg-green-600 text-white hover:bg-green-500 font-medium">
          <Check size={16} /> Готово
        </button>
        <button onClick={onCancel} className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-neutral-700 text-neutral-400 hover:bg-neutral-600">
          <X size={16} /> Отмена
        </button>
      </div>

      {/* Canvas */}
      <div className="flex-1 overflow-auto flex items-start justify-center p-3">
        {imageLoaded && (
          <canvas
            ref={canvasRef}
            className="max-w-full cursor-crosshair"
            style={{
              backgroundImage: `url(${screenshotDataUrl})`,
              backgroundSize: "100% 100%",
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/feedback/ui/AnnotationEditor.tsx
git commit -m "feat: add annotation editor with brush, arrow, text tools and undo"
```

---

### Task 19: Wire feedback widget into layout

**Files:**
- Modify: `frontend/src/app/(app)/layout.tsx` (add FeedbackButton)
- Update: `frontend/src/features/feedback/index.ts` (verify exports)

- [ ] **Step 1: Add FeedbackButton to authenticated layout**

In `frontend/src/app/(app)/layout.tsx`, import and render the FeedbackButton after the sidebar:

```tsx
// Add import at top:
import { FeedbackButton } from "@/features/feedback";

// Add after <main> closing tag, inside the flex container:
<FeedbackButton />
```

The layout should look like:

```tsx
return (
  <div className="flex min-h-screen">
    <Sidebar user={user} />
    <main className="flex-1 sidebar-margin p-6 max-w-[1200px]">
      {children}
    </main>
    <FeedbackButton />
  </div>
);
```

- [ ] **Step 2: Verify locally**

```bash
cd frontend && npm run dev
```

1. Navigate to `http://localhost:3000` (should redirect to login)
2. Log in with test credentials
3. Click the bug icon (bottom-right)
4. Fill in a description, submit
5. Check admin at `https://kvotaflow.ru/admin/feedback` for the new entry

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app frontend/src/features/feedback/
git commit -m "feat: wire feedback widget into authenticated layout"
```

---

## Summary

**Phase 1 Foundation (Chunks 1-4) produces:**
- Next.js 15 app with FSD structure
- Supabase Auth (login/logout, session refresh, middleware)
- Sidebar with full role-based menu (matching FastHTML exactly)
- Design system tokens ported to CSS variables
- shadcn/ui base components installed
- Python API auth layer (JWT validation)
- Docker container ready for deployment
- API client for Next.js → Python communication

**Chunk 5 (Feedback Widget) produces:**
- FeedbackButton: floating bug icon on all authenticated pages
- FeedbackModal: type selector + description + screenshot
- ScreenshotCapture: html2canvas with oklch fix + JPEG compression
- AnnotationEditor: brush, arrow, text tools with undo
- Screenshots uploaded to Supabase Storage (not base64 in DB)
- Python API updated: dual auth (session + JWT), dual format (form + JSON), screenshot_url support
- Backward compatible: FastHTML widget continues to work on unmigrated pages

**Next phase:** Phase 2 (Chat) — new feature, builds on this foundation.
