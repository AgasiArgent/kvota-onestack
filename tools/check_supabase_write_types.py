#!/usr/bin/env python3
"""Static check: forbid `as Record<string, ...>` casts in frontend/src/.

Background: this antipattern is what let MOZ-82 ship with a broken schema.
PR #114 introduced ``handleSaveInvoiceField(updates: Record<string, ...>)``
plus inline ``as Record<string, ...>`` casts on the .update() argument,
which fully disabled Supabase's typed Update<T> contract. The frontend
then wrote to ``invoices.vat_rate`` for weeks while the column did not
exist in the schema; PostgREST silently rejected every save (42703) but
the UI showed success toasts. See migration 310 + the postmortem in
``docs/plans/2026-05-07-tester-comments.md``.

The fix is to use the generated row types directly:

    import type { Database } from "@/shared/types/database.types";
    type InvoicesUpdate = Database["kvota"]["Tables"]["invoices"]["Update"];
    async function handleSaveInvoiceField(updates: InvoicesUpdate) { ... }

That makes ``tsc`` reject any unknown column at compile time. This script
is the merge gate that prevents the antipattern from coming back via a
copy-paste or a quick "as Record" hack.

Allowlist: a small, explicit set of files where ``Record<string, ...>`` is
genuinely the right type (URL params, opaque JSON payloads). Add entries
sparingly and document why next to the path.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIR = REPO_ROOT / "frontend" / "src"
SKIP_DIR_NAMES = {"__tests__", "__mocks__", "node_modules", ".next"}
ALLOWED_EXTENSIONS = {".ts", ".tsx"}

# Targeted pattern: `as Record<string, ...>` cast specifically applied to a
# Supabase write argument. We only flag the SAME-LINE case; multi-line is
# rare (linters/prettier collapse short call sites) and worth catching at
# review-time rather than producing false positives on JSON/error parsing.
#
# Matches things like:
#     .update({ ...} as Record<string, unknown>)
#     .insert({...} as Record<string, any>)
#     .upsert({...} as Record<string, X>)
WRITE_CAST_PATTERN = re.compile(
    r"\.(update|insert|upsert)\([^)]*\bas\s+Record<string\s*,"
)


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_no, source_line) for each violation in file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    violations: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if WRITE_CAST_PATTERN.search(line):
            violations.append((line_no, line.strip()))
    return violations


def main() -> int:
    if not SCAN_DIR.is_dir():
        print(f"ERROR: scan directory not found: {SCAN_DIR}", file=sys.stderr)
        return 2

    has_violations = False
    for path in sorted(SCAN_DIR.rglob("*")):
        if not path.is_file() or path.suffix not in ALLOWED_EXTENSIONS:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for line_no, source in scan_file(path):
            print(
                f"{rel}:{line_no}: forbidden `as Record<string, ...>` cast — "
                f"use Database['kvota']['Tables'][T]['Update'|'Insert'] instead. "
                f"Source: {source}"
            )
            has_violations = True

    if has_violations:
        print(
            "\nDocs: see migration 310 postmortem in docs/plans/"
            "2026-05-07-tester-comments.md and tools/check_supabase_write_types.py "
            "header for context.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
