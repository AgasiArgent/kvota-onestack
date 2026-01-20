# OneStack Project - Claude Instructions

**Project:** OneStack (Kvota Quotation Management System)
**Stack:** FastAPI (FastHTML) + Supabase PostgreSQL
**Deployment:** Docker on VPS (beget-kvota)

---

## 🗄️ Database - CRITICAL

**ALWAYS use the `db-kvota` skill when working with database!**

### Quick Facts

- **Schema:** `kvota` (NOT `public`)
- **Tables:** 51 tables in kvota schema
- **Role column:** `r.slug` (NOT `r.code`)
- **Location:** Supabase PostgreSQL on VPS

### Database Skill

**Skill:** `.claude/skills/db-kvota/`

**Auto-activates when:**
- Mentioning database, БД, supabase, postgres
- Working with migrations
- Database errors occur
- Querying tables

**Key reminders:**
- ✅ Always use `kvota.table_name` prefix
- ✅ Use `r.slug` not `r.code` in RLS policies
- ✅ Configure clients with `schema: "kvota"`
- ✅ Check skill before migrations

### Files to Reference

When working with database, check:
- **`.claude/skills/db-kvota/skill.md`** - Quick commands & troubleshooting
- **`DATABASE_GUIDE.md`** - Detailed guide
- **`DATABASE_TABLES.md`** - Table schemas
- **`migrations/`** - Migration files

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

### Working with Database

1. **Check skill first:** Review `.claude/skills/db-kvota/skill.md`
2. **Use kvota schema:** Always prefix with `kvota.`
3. **Verify on VPS:** Test queries before code changes
4. **Update migrations:** Keep numbered sequence

### Making Changes

1. **Local development**
2. **Commit with descriptive message**
3. **Push to main** → CI/CD deploys automatically
4. **Monitor logs:** `docker logs kvota-onestack`

### Creating Migrations

**Follow pattern:**
```sql
-- migrations/XXX_description.sql
-- Always use kvota schema
CREATE TABLE kvota.new_table (...);

-- Always use r.slug in RLS
WHERE r.slug IN ('admin', 'finance')
```

---

## 🐛 Debugging

### Database Issues

**First:** Activate `db-kvota` skill or read `.claude/skills/db-kvota/skill.md`

**Common errors:**
- "relation does not exist" → Check schema prefix
- "column r.code does not exist" → Use r.slug
- RLS blocks access → Check user roles

**Quick diagnostic:**
```bash
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres \
  -c 'SELECT schemaname, COUNT(*) FROM pg_tables
      WHERE schemaname IN (\"kvota\", \"public\") GROUP BY schemaname;'"
```

### Application Issues

**Check logs:**
```bash
ssh beget-kvota "docker logs kvota-onestack --tail 100"
```

**Check health:**
```bash
ssh beget-kvota "docker ps | grep kvota"
```

---

## 📋 Key Files

### Configuration

- **`services/database.py`** - Supabase client (MUST have `schema: "kvota"`)
- **`docker-compose.prod.yml`** - Production config
- **`.env`** - Environment variables (on VPS)

### Documentation

- **`DATABASE_GUIDE.md`** - Database guide for humans
- **`DATABASE_TABLES.md`** - Table schemas reference
- **`MIGRATION_GUIDE.md`** - Migration instructions
- **`PRODUCTION_TABLES.md`** - Production database state

### Skills

- **`.claude/skills/db-kvota/`** - Database helper skill

---

## ✅ Best Practices

### Database Operations

1. **Always use kvota schema**
   ```python
   # ✅ Correct
   supabase = create_client(url, key, options={"schema": "kvota"})
   ```

2. **Always use r.slug in RLS**
   ```sql
   -- ✅ Correct
   WHERE r.slug IN ('admin', 'finance')
   ```

3. **Check skill before work**
   - Read `.claude/skills/db-kvota/skill.md` first
   - Use provided commands
   - Follow checklist

### Code Changes

1. **Test on VPS before commit**
2. **Use descriptive commit messages**
3. **Include "Co-Authored-By: Claude Sonnet 4.5"**
4. **Let CI/CD handle deployment**

### Migrations

1. **Create backup first**
2. **Use sequential numbering**
3. **Test on copy if possible**
4. **Always use kvota prefix**
5. **Verify after applying**

---

## 🎯 Remember

**When working with database:**
1. ✅ Activate `db-kvota` skill (auto-triggers)
2. ✅ Use `kvota` schema everywhere
3. ✅ Use `r.slug` not `r.code`
4. ✅ Check skill.md for commands
5. ✅ Test on VPS before committing

**When in doubt:**
- Check `.claude/skills/db-kvota/skill.md`
- Review `DATABASE_GUIDE.md`
- Look at existing migrations in `migrations/`

---

**Last updated:** 2026-01-20
**Database schema:** kvota (51 tables)
**VPS:** beget-kvota
**Container:** kvota-onestack
