#!/bin/bash
# ===========================================================================
# Master script: Apply all kvota schema migrations
# ===========================================================================
# Description: Applies all migrations to move OneStack to kvota schema
# Usage: ./apply_kvota_migrations.sh [--dry-run]
# Created: 2026-01-20
# ===========================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_HOST="${DB_HOST:-supabase-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"
MIGRATIONS_DIR="./migrations"
DRY_RUN=false

# Parse arguments
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}DRY RUN MODE: No changes will be applied${NC}"
fi

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to execute SQL file
execute_migration() {
    local migration_file=$1
    local migration_name=$(basename "$migration_file")

    echo -e "${BLUE}Applying: $migration_name${NC}"

    if [[ "$DRY_RUN" == true ]]; then
        print_warning "DRY RUN: Would apply $migration_name"
        return 0
    fi

    if docker exec "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -f "/tmp/$migration_name" 2>&1; then
        print_success "$migration_name applied successfully"
        return 0
    else
        print_error "$migration_name failed"
        return 1
    fi
}

# Function to copy migration to container
copy_to_container() {
    local migration_file=$1
    local migration_name=$(basename "$migration_file")

    if [[ "$DRY_RUN" == true ]]; then
        return 0
    fi

    docker cp "$migration_file" "$DB_HOST:/tmp/$migration_name"
}

# ===========================================================================
# PRE-FLIGHT CHECKS
# ===========================================================================

print_header "Pre-flight Checks"

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    print_error "Docker is not running"
    exit 1
fi
print_success "Docker is running"

# Check if database container exists
if ! docker ps | grep -q "$DB_HOST"; then
    print_error "Database container '$DB_HOST' is not running"
    exit 1
fi
print_success "Database container is running"

# Check if migrations directory exists
if [[ ! -d "$MIGRATIONS_DIR" ]]; then
    print_error "Migrations directory not found: $MIGRATIONS_DIR"
    exit 1
fi
print_success "Migrations directory found"

# Check if all migration files exist
MIGRATIONS=(
    "100_create_kvota_schema.sql"
    "101_move_tables_to_kvota_schema.sql"
    "102_create_buyer_companies_kvota.sql"
    "103_create_bank_accounts_kvota.sql"
    "105_create_brand_supplier_assignments_kvota.sql"
    "106_create_supplier_invoices_kvota.sql"
    "107_create_supplier_invoice_items_kvota.sql"
    "108_create_supplier_invoice_payments_kvota.sql"
)

for migration in "${MIGRATIONS[@]}"; do
    if [[ ! -f "$MIGRATIONS_DIR/$migration" ]]; then
        print_error "Migration file not found: $migration"
        exit 1
    fi
done
print_success "All migration files found (${#MIGRATIONS[@]} files)"

# ===========================================================================
# BACKUP
# ===========================================================================

if [[ "$DRY_RUN" == false ]]; then
    print_header "Creating Backup"

    BACKUP_FILE="backup_before_kvota_$(date +%Y%m%d_%H%M%S).sql"

    echo "Creating backup: $BACKUP_FILE"
    if docker exec "$DB_HOST" pg_dump -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE" 2>&1; then
        print_success "Backup created: $BACKUP_FILE"
    else
        print_error "Backup failed"
        exit 1
    fi
fi

# ===========================================================================
# APPLY MIGRATIONS
# ===========================================================================

print_header "Applying Migrations"

for migration in "${MIGRATIONS[@]}"; do
    migration_path="$MIGRATIONS_DIR/$migration"

    # Copy migration to container
    if [[ "$DRY_RUN" == false ]]; then
        copy_to_container "$migration_path"
    fi

    # Execute migration
    if ! execute_migration "$migration_path"; then
        print_error "Migration failed: $migration"
        print_warning "You can restore from backup: $BACKUP_FILE"
        exit 1
    fi

    sleep 1  # Small delay between migrations
done

# ===========================================================================
# VERIFICATION
# ===========================================================================

print_header "Verification"

if [[ "$DRY_RUN" == false ]]; then
    # Check if kvota schema exists
    echo "Checking if kvota schema exists..."
    if docker exec "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'kvota';" | grep -q 1; then
        print_success "Schema 'kvota' exists"
    else
        print_error "Schema 'kvota' not found"
        exit 1
    fi

    # Count tables in kvota schema
    echo "Counting tables in kvota schema..."
    TABLE_COUNT=$(docker exec "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'kvota';" | tr -d ' ')
    print_success "Found $TABLE_COUNT tables in kvota schema"

    if [[ $TABLE_COUNT -lt 50 ]]; then
        print_warning "Expected at least 50 tables (45 moved + 5 new), found $TABLE_COUNT"
    fi

    # List tables
    echo -e "\nTables in kvota schema:"
    docker exec "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'kvota' ORDER BY tablename;" | head -20
fi

# ===========================================================================
# SUMMARY
# ===========================================================================

print_header "Migration Summary"

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}DRY RUN COMPLETED${NC}"
    echo "No changes were made to the database"
    echo ""
    echo "To apply migrations for real, run:"
    echo "  ./apply_kvota_migrations.sh"
else
    echo -e "${GREEN}✓ ALL MIGRATIONS APPLIED SUCCESSFULLY${NC}"
    echo ""
    echo "Applied ${#MIGRATIONS[@]} migrations:"
    for migration in "${MIGRATIONS[@]}"; do
        echo "  ✓ $migration"
    done
    echo ""
    echo -e "${GREEN}Backup saved to: $BACKUP_FILE${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Update backend code to use schema 'kvota'"
    echo "  2. Update frontend Supabase client config"
    echo "  3. Test the application"
    echo ""
    echo "See MIGRATION_CODE_CHANGES.md for code update instructions"
fi

print_header "Done"
