# OneStack Project - Claude Instructions

**Project:** OneStack (Kvota Quotation Management System)
**Stack:** FastAPI (FastHTML) + Supabase PostgreSQL
**Deployment:** Docker on VPS (beget-kvota)

---

## 🗄️ Database - CRITICAL

**Schema:** `kvota` (NOT `public`) | **Role column:** `r.slug` (NOT `r.code`)

**Key Rules:**
- ✅ Always use `kvota.table_name` prefix
- ✅ Use `r.slug` not `r.code` in RLS policies
- ✅ Configure clients with `schema: "kvota"`
- ✅ Check `.claude/skills/db-kvota/skill.md` before migrations

**Reference Files:**
- `.claude/skills/db-kvota/skill.md` - Commands & troubleshooting
- `DATABASE_GUIDE.md` - Detailed guide
- `DATABASE_TABLES.md` - Table schemas

---

## 📁 Project Structure

```
onestack/
├── main.py                 # FastAPI application
├── services/
│   └── database.py        # Supabase client (schema: kvota)
├── migrations/            # Database migrations
├── .claude/
│   └── skills/
│       └── db-kvota/      # Database helper skill
├── docker-compose.prod.yml
└── Dockerfile
```

---

## 🚀 Deployment

**VPS Access:**
```bash
ssh beget-kvota
```

**Container:** `kvota-onestack`
```bash
docker logs kvota-onestack
docker restart kvota-onestack
```

**CI/CD:** Push to main → auto-deploy via GitHub Actions

---

## 🛠️ Development Workflow

1. Make changes locally
2. **Test through UI** (Chrome Extension Tool) ← MANDATORY
3. Commit with descriptive message
4. Push to main → CI/CD deploys automatically
5. Monitor: `ssh beget-kvota "docker logs kvota-onestack --tail 50"`

---

## 🧪 Testing - CRITICAL

**ALWAYS test changes through UI using Chrome Extension Tool (claude-in-chrome MCP):**

```
1. After making code changes, commit and push to deploy
2. Use mcp__claude-in-chrome__* tools to test in browser
3. Navigate, click, fill forms, take screenshots
4. Verify all functionality works end-to-end
```

**Never skip UI testing** - backend changes must be verified through actual user interface.

---

## 🐛 Debugging

**Database errors:**
- "relation does not exist" → Check `kvota.` schema prefix
- "column r.code does not exist" → Use `r.slug`
- RLS blocks access → Check user roles & `.claude/skills/db-kvota/skill.md`

**Application logs:**
```bash
ssh beget-kvota "docker logs kvota-onestack --tail 50"
```

---

## 📋 Key Files

**Config:** `services/database.py` (Supabase client), `docker-compose.prod.yml`, `.env` (on VPS)
**Docs:** `DATABASE_GUIDE.md`, `DATABASE_TABLES.md`, `MIGRATION_GUIDE.md`
**Skills:** `.claude/skills/db-kvota/`

---

## ⚠️ Common Pitfalls (from production incidents)

**PostgREST FK ambiguity:**
- When querying tables with multiple foreign keys to the same target, PostgREST cannot auto-detect which FK to use
- ALWAYS specify the FK relationship explicitly: `table!fk_column(fields)` instead of `table(fields)`
- Example: `quotes!customer_id(name)` NOT just `customers(name)`
- This causes silent failures that only surface after deployment

**Python variable scoping in route handlers:**
- Variables defined inside `if/for/try` blocks or in a GET handler are NOT accessible in a separate POST handler
- Before writing POST/PUT handlers, verify every variable you reference is defined in THAT handler's scope
- Common bug: defining `convert_amount` in GET `/quotes/{id}` but using it in POST `/quotes/{id}` — they're separate functions
- Always trace variable definitions to ensure they're in scope

**Hardcoded values:**
- NEVER use hardcoded example timestamps (like `14:35`), IDs, or URLs
- Always use `datetime.now()`, generated UUIDs, or config variables
- If generating files with timestamps, use the actual current time

---

## ✅ Best Practices

**Migrations:**
```sql
-- migrations/XXX_description.sql
CREATE TABLE kvota.new_table (...);  -- Always use kvota schema
WHERE r.slug IN ('admin', 'finance')  -- Always use r.slug in RLS
```

**Commits:**
1. Test through UI first (Chrome Extension Tool)
2. Use descriptive commit messages
3. Include "Co-Authored-By: Claude Sonnet 4.5"
4. Push to main → CI/CD auto-deploys

---

## 🎨 Design System

**Tokens:** `design-system.md` — READ before any UI work.
**Styles:** `APP_STYLES` in `main.py` (line ~149) — all CSS variables.

**Rules:**
- Follow `design-system.md` for all colors, fonts, spacing, components
- Font: Inter (not Manrope) — constrained type scale (11/12/14/16/18/20/24px)
- Spacing: constrained scale (4/6/8/12/16/20/24/32/48px)
- No `transition: all` — animate specific properties only
- No `transform: translateY()` on hover — no card lift, no button bounce
- No inline `style=` for colors/fonts/spacing — use CSS vars or classes
- Use `.btn` BEM classes for buttons, not raw `<button>` styles

---

**Last updated:** 2026-03-10
**Database schema:** kvota (51 tables)
**VPS:** beget-kvota
**Container:** kvota-onestack
