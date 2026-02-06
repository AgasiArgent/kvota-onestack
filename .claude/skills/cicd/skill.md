# Skill: cicd

GitHub repository setup, CI/CD pipeline, and deployment workflow for OneStack.

## Activation

**Trigger keywords:**
- "deploy", "deployment", "CI/CD", "pipeline"
- "GitHub Actions", "workflow", "build status"
- "push to main", "merge", "PR"
- "tests failing in CI", "deploy failed"

## Repository

| Property | Value |
|----------|-------|
| Repo | `AgasiArgent/kvota-onestack` |
| URL | https://github.com/AgasiArgent/kvota-onestack |
| Default branch | `main` |
| Remote | `origin` |

## Pipeline Overview

```
Push to main
    │
    ▼
┌──────────┐     success     ┌──────────┐
│  CI Job  │ ──────────────► │  Deploy  │
│ (tests)  │                 │  (VPS)   │
└──────────┘                 └──────────┘
    │                            │
    ▼                            ▼
pytest tests/ -v           git pull + docker
on ubuntu-latest           compose up --build
Python 3.12                on beget-kvota VPS
```

**Two-stage pipeline:**
1. **CI** (`ci.yml`) — runs on every push to main and on PRs
2. **Deploy** (`deploy.yml`) — triggers ONLY after CI succeeds, ONLY on main branch

## CI Workflow (`.github/workflows/ci.yml`)

**Triggers:** push to main, pull requests to main

**What it does:**
1. Checkout code
2. Setup Python 3.12 with pip cache
3. Install system deps (libpango, libpangocairo, libgdk-pixbuf — needed for PDF generation)
4. Install Python deps from `requirements.txt` + pytest
5. Run `pytest tests/ -v --tb=short`

**Environment secrets used:**
- `SUPABASE_URL` — Supabase API endpoint
- `SUPABASE_ANON_KEY` — Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key
- `APP_SECRET` — set to `test-secret` in CI

**Common CI failures:**
- Missing import or syntax error → fix code
- Test failure → check test output, fix test or implementation
- Dependency install failure → check requirements.txt
- System dependency missing → update apt-get install step

## Deploy Workflow (`.github/workflows/deploy.yml`)

**Triggers:** after CI workflow completes successfully on main

**What it does:**
1. SSH into VPS via `appleboy/ssh-action@v1.0.3`
2. `cd /root/onestack`
3. `git pull origin main`
4. `docker compose up -d --build`
5. `docker image prune -f` (cleanup old images)

**Secrets used:**
- `VPS_HOST` — VPS IP address (217.26.25.207)
- `VPS_SSH_KEY` — SSH private key for root access

**Common deploy failures:**
- SSH connection timeout → VPS might be down, check with `ping 217.26.25.207`
- Git pull conflict → VPS has local changes, SSH in and resolve
- Docker build failure → check Dockerfile, usually missing dependency
- Port already in use → another container using port 5001

## Checking Pipeline Status

### From CLI (gh command)
```bash
# Check latest CI run
gh run list --workflow=ci.yml --limit 5

# Check latest deploy run
gh run list --workflow=deploy.yml --limit 5

# View specific run details
gh run view RUN_ID

# View run logs
gh run view RUN_ID --log

# Watch a running workflow
gh run watch
```

### After Push Workflow
After pushing to main, the expected flow is:
1. CI starts (~1-2 min to complete)
2. If CI passes → Deploy triggers automatically (~1 min)
3. Total time from push to live: ~3-4 minutes

### Verifying Deployment
```bash
# 1. Check GitHub Actions succeeded
gh run list --limit 3

# 2. Check container is running on VPS
ssh beget-kvota "docker ps | grep kvota-onestack"

# 3. Check recent logs for errors
ssh beget-kvota "docker logs kvota-onestack --tail 20"

# 4. Check health endpoint
ssh beget-kvota "docker inspect kvota-onestack --format '{{.State.Health.Status}}'"

# 5. Test in browser (use Claude-in-Chrome)
# Navigate to https://kvotaflow.ru and verify
```

## Git Workflow

### Standard Development Flow
```
1. Make changes locally
2. Run tests: pytest tests/ -v
3. Commit with descriptive message
4. Push to main: git push origin main
5. CI runs tests automatically
6. If CI passes → auto-deploy to VPS
7. Verify in browser at https://kvotaflow.ru
```

### Branch Strategy
- **main** — production branch, auto-deploys
- No feature branches currently (direct to main)
- PRs trigger CI but NOT deploy

### Commit Convention
- Descriptive messages explaining "why" not just "what"
- Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` when Claude assists

## Database Migrations in CI/CD

**Migrations are NOT auto-applied by the pipeline.**

After deploying code that includes new migrations:
```bash
# Apply migrations manually via SSH
ssh beget-kvota "cd /root/onestack && bash scripts/apply-migrations.sh"
```

The migration script:
- Tracks applied migrations in `kvota.migrations` table
- Only applies pending migrations
- Handles non-critical errors gracefully
- Migration files: `migrations/*.sql` (sequential numbering)

## Secrets Management

**GitHub Secrets** (configured in repo Settings > Secrets):
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `VPS_HOST`
- `VPS_SSH_KEY`

**VPS Environment** (`.env` file on VPS at `/root/onestack/.env`):
- Same Supabase credentials
- `APP_SECRET` (production secret, different from CI test-secret)
- `TELEGRAM_BOT_TOKEN` (optional)
- `TELEGRAM_WEBHOOK_URL` (optional)

**NEVER commit `.env` files or secrets to the repository.**

## Troubleshooting

### CI passed but deploy didn't trigger
- Check that the push was to `main` branch
- Deploy workflow uses `workflow_run` event — check if CI run is associated with main
- View deploy workflow runs: `gh run list --workflow=deploy.yml`

### Deploy succeeded but app is broken
- Check container logs: `ssh beget-kvota "docker logs kvota-onestack --tail 50"`
- Check if migrations are needed: new columns/tables may cause errors
- Rollback: `ssh beget-kvota "cd /root/onestack && git checkout HEAD~1 && docker compose up -d --build"`

### Tests pass locally but fail in CI
- Check Python version (CI uses 3.12)
- Check if test needs Supabase credentials (CI has real credentials via secrets)
- Check for system dependency differences (CI runs on ubuntu-latest)

---

**Last updated:** 2026-02-06
**Repo:** AgasiArgent/kvota-onestack
**Pipeline:** CI (pytest) → Deploy (SSH + docker compose)
**Deploy target:** beget-kvota VPS, container kvota-onestack
