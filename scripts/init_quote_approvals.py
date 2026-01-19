#!/usr/bin/env python3
"""
Script to initialize approvals field on quotes table
Works by updating existing quotes through Supabase client
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import get_supabase

def init_approvals():
    """Initialize approvals field on all quotes"""
    supabase = get_supabase()

    default_approvals = {
        "procurement": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
        "logistics": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
        "customs": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
        "sales": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
        "control": {"approved": False, "approved_by": None, "approved_at": None, "comments": None}
    }

    legacy_approvals = {
        "procurement": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
        "logistics": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
        "customs": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
        "sales": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
        "control": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"}
    }

    print("Initializing quote approvals...")

    try:
        # Get all quotes
        print("Fetching all quotes...")
        result = supabase.table('quotes').select('id, status, approvals').execute()

        quotes = result.data
        print(f"Found {len(quotes)} quotes")

        # Process each quote
        updated_count = 0
        legacy_count = 0
        skipped_count = 0

        for quote in quotes:
            quote_id = quote['id']
            status = quote.get('status')
            existing_approvals = quote.get('approvals')

            # Skip if already has approvals
            if existing_approvals:
                print(f"  Quote {quote_id[:8]}... already has approvals, skipping")
                skipped_count += 1
                continue

            # Determine which approvals to use
            if status in ['pending_spec_control', 'approved', 'won', 'lost']:
                # Legacy quotes - mark all as approved
                approvals_to_set = legacy_approvals
                legacy_count += 1
                print(f"  Quote {quote_id[:8]}... (status: {status}) -> setting legacy approvals")
            else:
                # New quotes - initialize empty
                approvals_to_set = default_approvals
                print(f"  Quote {quote_id[:8]}... (status: {status}) -> initializing approvals")

            # Update quote
            supabase.table('quotes').update({
                'approvals': approvals_to_set
            }).eq('id', quote_id).execute()

            updated_count += 1

        print(f"\n✅ Migration completed!")
        print(f"   Updated: {updated_count} quotes")
        print(f"   Legacy (pre-approved): {legacy_count} quotes")
        print(f"   Skipped (already had approvals): {skipped_count} quotes")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    init_approvals()
