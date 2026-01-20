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

**Last updated:** 2026-01-20
**Database schema:** kvota (51 tables)
**VPS:** beget-kvota
**Container:** kvota-onestack
