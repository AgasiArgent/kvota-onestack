.PHONY: dev-setup dev-up dev-down dev-reset test lint seed migrate db-shell help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Local development
# ============================================================================

dev-setup: ## Full local setup: start PG, create schema, migrate, seed
	docker compose -f docker-compose.dev.yml up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@until docker exec kvota-postgres-dev pg_isready -U kvota 2>/dev/null; do sleep 1; done
	python scripts/setup_local_db.py

dev-up: ## Start the app in dev mode (requires .env or .env.dev)
	python main.py

dev-down: ## Stop local PostgreSQL
	docker compose -f docker-compose.dev.yml down

dev-reset: ## Drop everything, recreate schema, migrate, seed
	docker compose -f docker-compose.dev.yml up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@until docker exec kvota-postgres-dev pg_isready -U kvota 2>/dev/null; do sleep 1; done
	python scripts/setup_local_db.py --reset

# ============================================================================
# Database
# ============================================================================

migrate: ## Apply pending migrations to DATABASE_URL
	python scripts/migrate.py

migrate-status: ## Show migration status
	python scripts/migrate.py status

seed: ## Run seed script against DATABASE_URL
	python scripts/seed_dev_data.py

db-shell: ## Open psql shell to local dev database (kvota schema)
	PGOPTIONS='-c search_path=kvota,public' psql postgresql://kvota:devpassword@localhost:5434/kvota_dev

# ============================================================================
# Quality
# ============================================================================

test: ## Run tests
	python -m pytest tests/ -v

lint: ## Run ruff linter
	ruff check .

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix .

# ============================================================================
# Frontend
# ============================================================================

frontend-dev: ## Start frontend dev server
	cd frontend && npm run dev

frontend-types: ## Regenerate Supabase types after migrations
	cd frontend && npm run db:types
