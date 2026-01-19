#!/usr/bin/env python3
"""
Script to run quote approvals migration via Supabase RPC/SQL
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import get_supabase

def run_migration():
    """Execute the migration SQL"""
    supabase = get_supabase()

    print("Running quote approvals migration...")
    print("Note: Column must be added manually via Supabase SQL Editor")
    print("Run: ALTER TABLE quotes ADD COLUMN IF NOT EXISTS approvals JSONB;")
    print("")

    try:

        # Step 2: Initialize existing quotes
        print("2. Initializing approvals for existing quotes...")
        result = supabase.table('quotes').update({
            'approvals': {
                "procurement": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
                "logistics": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
                "customs": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
                "sales": {"approved": False, "approved_by": None, "approved_at": None, "comments": None},
                "control": {"approved": False, "approved_by": None, "approved_at": None, "comments": None}
            }
        }).is_('approvals', 'null').execute()
        print(f"✓ Initialized {len(result.data) if result.data else 0} quotes")

        # Step 3: Mark legacy quotes as approved
        print("3. Marking legacy quotes (advanced status) as approved...")
        result = supabase.table('quotes').update({
            'approvals': {
                "procurement": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
                "logistics": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
                "customs": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
                "sales": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"},
                "control": {"approved": True, "approved_by": None, "approved_at": None, "comments": "Legacy approval (migrated)"}
            }
        }).in_('status', ['pending_spec_control', 'approved', 'won', 'lost']).execute()
        print(f"✓ Marked {len(result.data) if result.data else 0} legacy quotes as approved")

        print("\n✅ Migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    run_migration()
