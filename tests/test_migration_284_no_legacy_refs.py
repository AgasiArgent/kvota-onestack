"""
Regression guard for migration 284 — Phase 5d Group 6.

Migration 284 drops 16 columns on kvota.quote_items plus the entire
kvota.invoice_item_prices table. After the drop, any production code that
still reads those columns (via Supabase ``.from("quote_items").select(...)``
or raw ``SELECT FROM quote_items``) will fail at runtime.

This test scans the production code tree for lingering references and
fails loudly if any are found outside the explicit DORMANT allowlist
(FastHTML HTML-rendering regions in main.py, documented in
``.kiro/specs/phase-5d-legacy-refactor/main-py-classification.md``).

Policy (per design.md §2.5):
  FastHTML HTML handlers are DORMANT — migration 284 will break them at
  runtime, accepted trade-off. The Next.js + /api/* surfaces must not
  contain any legacy reference.

Allowlist mechanism (hybrid):
  1. Hardcoded line-range ranges for main.py DORMANT FastHTML regions.
  2. Per-line ``# phase-5d: dormant-fasthtml-exempt`` / ``// phase-5d:
     dormant-fasthtml-exempt`` marker on any production line that's a
     known DORMANT surface not covered by the line-range list.

Detection patterns:
  1. ``.from("quote_items").select("...<LEGACY_COL>...")`` (Supabase JS)
  2. ``.table("quote_items").select("...<LEGACY_COL>...")`` (Supabase PY)
  3. ``SELECT ... <LEGACY_COL> ... FROM quote_items`` (raw SQL)
  4. ``FROM kvota.quote_items`` + nearby legacy col (raw SQL view/function)

Column references inside nested ``invoice_items!inner(...)`` subselects
are ALLOWED — they read from the new table (migration 281) where these
columns legitimately live. Dict / attribute accesses like
``item.get("purchase_price_original")`` are also ALLOWED because the
dict can come from ``composition_service.get_composed_items()`` (which
sources from invoice_items via coverage).

Run: pytest tests/test_migration_284_no_legacy_refs.py -v
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

# Resolve project root from this file location — avoids CI path assumptions.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 16 legacy columns dropped from quote_items in migration 284 (per
# phase-5c-invoice-items/design.md §1.2 + §6).
#
# Note: the design mentions "minimum_order_quantity" but the actual column
# in kvota.quote_items is named min_order_quantity (verified on VPS
# 2026-04-18). We scan for the actual column name.
LEGACY_COLUMNS: tuple[str, ...] = (
    "purchase_price_original",
    "purchase_currency",
    "base_price_vat",
    "price_includes_vat",
    "customs_code",
    "supplier_country",
    "weight_in_kg",
    "production_time_days",
    "min_order_quantity",
    "dimension_height_mm",
    "dimension_width_mm",
    "dimension_length_mm",
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
    # invoice_id is also dropped but it's too generic a name (invoice_id
    # exists on invoice_items, invoice_item_coverage, invoices, etc.). We
    # only flag it in the strict ``FROM quote_items`` + select-list context
    # — see _is_legacy_quote_items_select below.
    "invoice_id",
)

# Legacy table (dropped entirely in migration 284).
LEGACY_TABLE = "invoice_item_prices"

# Production file roots to scan. Paths relative to PROJECT_ROOT.
PRODUCTION_PATHS: tuple[str, ...] = (
    "main.py",
    "api",
    "services",
    "frontend/src",
)

# File suffixes to scan within the production paths.
SCAN_EXTENSIONS: tuple[str, ...] = (".py", ".ts", ".tsx", ".js", ".jsx")

# Paths (relative to PROJECT_ROOT) to skip entirely. These are either:
#  - generated code (database.types.ts) — always mirrors current schema,
#    regenerated post-apply
#  - internal __tests__ directories (tests freely reference legacy)
#  - __pycache__ / node_modules / similar
SKIP_PATH_FRAGMENTS: tuple[str, ...] = (
    "__pycache__",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__tests__",  # frontend tests
    # Auto-generated schema types — regenerated after migration 284 applies.
    "frontend/src/shared/types/database.types.ts",
)

# DORMANT FastHTML regions in main.py. Line ranges are inclusive on both
# ends. Authoritative source:
# .kiro/specs/phase-5d-legacy-refactor/main-py-classification.md
#
# Each entry is (start_line, end_line, description).
MAIN_PY_DORMANT_RANGES: tuple[tuple[int, int, str], ...] = (
    # /procurement/{quote_id} FastHTML workspace — entire handler + helpers.
    (17594, 18800, "/procurement/{quote_id} FastHTML page (invoice_card, detail table)"),
    # FastHTML POST / helper block (render_invoices_list + legacy bulk updates).
    # Range covers main-py-classification.md:14 "main.py:19292-19900 FastHTML subset".
    (19292, 19900, "FastHTML POST handlers + render_invoices_list helper"),
    # Invoice cards loop + invoice detail table for FastHTML /logistics route.
    (20041, 20200, "FastHTML invoices/logistics card region (20041-20200)"),
    # Logistics card render.
    (20420, 21000, "FastHTML logistics card + quote_items select for weight/volume"),
    # Invoice detail page (FastHTML) + price math.
    (21955, 22100, "FastHTML invoice detail HTML render (21955-22100)"),
    # Customs workspace (FastHTML /customs/{quote_id}) + customs_item_card.
    (22100, 22400, "FastHTML /customs/{quote_id} workspace"),
    # Invoice detail render + invoice detail display (FastHTML).
    (25030, 25400, "FastHTML invoice detail family (25030-25400)"),
    # Finance tab totals (FastHTML).
    (30290, 30500, "FastHTML finance tab totals"),
    # Registry invoice totals (FastHTML).
    (43100, 43400, "FastHTML registry invoice totals"),
    # Quote detail check region (line 24142 classification).
    (24100, 24200, "FastHTML quote detail check (24100-24200)"),
)

# Opt-in comment marker for any other DORMANT line we don't want to break.
# Place ABOVE or ON the same line as the legacy reference. Matches either
# Python or TS/JS comment syntax.
DORMANT_MARKER_RE = re.compile(
    r"(?:^|\s)(?:#|//)\s*phase-5d:\s*dormant-fasthtml-exempt\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacyRef:
    """One detected legacy reference (for error reporting)."""

    path: str  # relative to PROJECT_ROOT
    line_no: int  # 1-indexed
    column: str
    snippet: str

    def describe(self) -> str:
        return f"{self.path}:{self.line_no}  [{self.column}]  {self.snippet.strip()[:160]}"


def _is_path_allowlisted(rel_path: str) -> bool:
    """Whole-path exclusion for generated / test / vendor trees."""
    return any(frag in rel_path for frag in SKIP_PATH_FRAGMENTS)


def _is_line_in_main_py_dormant_range(line_no: int) -> str | None:
    """Return description if line is in a hardcoded DORMANT range, else None."""
    for start, end, desc in MAIN_PY_DORMANT_RANGES:
        if start <= line_no <= end:
            return desc
    return None


def _has_dormant_marker(line: str, prev_line: str) -> bool:
    """Check current + previous line for the exempt comment marker."""
    return bool(
        DORMANT_MARKER_RE.search(line) or DORMANT_MARKER_RE.search(prev_line)
    )


# Detection regexes — each returns True iff the line contains a legacy
# access pattern that migration 284 will break.

# Supabase ``.from("quote_items")`` or ``.table("quote_items")`` followed
# by ``.select(...)``. We grab the full logical "call chain" up to the
# next closing parenthesis of select — Supabase select strings can wrap
# over multiple lines, so we use a window (current line + a few ahead).
_QUOTE_ITEMS_TABLE_RE = re.compile(
    r"""\.(?:from|table)\(\s*["']quote_items["']\s*\)""",
    re.VERBOSE,
)

# Raw SQL: ``FROM quote_items`` or ``FROM kvota.quote_items``. Case-
# insensitive because SQL keywords can be either case.
_FROM_QUOTE_ITEMS_RE = re.compile(
    r"""FROM\s+(?:kvota\.)?quote_items\b""",
    re.IGNORECASE,
)

# ``UPDATE quote_items`` or ``UPDATE kvota.quote_items`` SET col = ...
# If the SET targets a legacy column, it's a legacy reference too.
_UPDATE_QUOTE_ITEMS_RE = re.compile(
    r"""UPDATE\s+(?:kvota\.)?quote_items\b""",
    re.IGNORECASE,
)


def _is_legacy_quote_items_select(
    lines: list[str], line_idx: int
) -> list[str]:
    """Return the list of legacy columns referenced in a select rooted at
    line_idx. Empty list means no legacy reference.

    Reads a window of up to 20 lines starting at line_idx to cover multi-
    line select strings. Stops when parentheses balance.
    """
    # Collect the chain starting at line_idx.
    joined = []
    depth = 0
    started = False
    for j in range(line_idx, min(line_idx + 20, len(lines))):
        chunk = lines[j]
        joined.append(chunk)
        for ch in chunk:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                depth -= 1
                if started and depth <= 0:
                    break
        if started and depth <= 0:
            break

    blob = "\n".join(joined)

    # Strip out any nested invoice_items!inner(...) / invoice_item_coverage(...)
    # subselects — columns inside those SOURCE from the new tables, not from
    # quote_items. We peel them by removing the innermost parenthesized
    # groups whose lead-in includes the new-table name.
    cleaned = _strip_new_table_subselects(blob)

    hits = []
    for col in LEGACY_COLUMNS:
        # invoice_id is too generic; only flag it in a FROM quote_items + SET
        # context which this function already guarantees.
        pattern = re.compile(r"\b" + re.escape(col) + r"\b")
        if pattern.search(cleaned):
            hits.append(col)
    return hits


def _strip_new_table_subselects(blob: str) -> str:
    """Remove any substring of the form ``invoice_items!inner(...)``,
    ``invoice_items(...)``, ``invoice_item_coverage!...(...)``, or similar
    nested relationship selects so we only check the outer quote_items
    column list.

    Regex matches a keyword (``invoice_items`` optionally followed by
    ``!<relation_name>``) immediately followed by a parenthesized group.
    Handles one level of nesting via a simple matched-paren walk (good
    enough for real PostgREST select strings, which rarely nest deeper
    than 2 inside a single relationship spec).
    """
    keywords = ("invoice_items", "invoice_item_coverage")
    # Repeatedly strip innermost matches.
    out = blob
    while True:
        best_start = -1
        best_end = -1
        for kw in keywords:
            # find ``<kw>(`` or ``<kw>!<relation>(``
            for m in re.finditer(
                re.escape(kw) + r"(?:!\w+)?\s*\(",
                out,
            ):
                start = m.start()
                lparen = m.end() - 1
                # Walk forward to the matching right paren.
                depth = 0
                rparen = -1
                for i in range(lparen, len(out)):
                    if out[i] == "(":
                        depth += 1
                    elif out[i] == ")":
                        depth -= 1
                        if depth == 0:
                            rparen = i
                            break
                if rparen > 0 and (
                    best_start < 0 or (rparen - start) < (best_end - best_start)
                ):
                    # Track the shortest (= innermost) match so we strip
                    # deepest first and don't accidentally drop the outer
                    # quote_items select spec.
                    best_start = start
                    best_end = rparen
        if best_start < 0:
            break
        out = out[:best_start] + out[best_end + 1 :]
    return out


# ---------------------------------------------------------------------------
# Comment / docstring stripping
# ---------------------------------------------------------------------------
# Comments and docstrings freely reference legacy names (migration notes,
# historical rationale). Stripping them before scanning keeps the check
# focused on executable code.


_PY_LINE_COMMENT_RE = re.compile(r"(?<!['\"])#.*$")
_TS_LINE_COMMENT_RE = re.compile(r"//.*$")


def _strip_comments_python(source: str) -> str:
    """Replace Python line comments and triple-quoted strings with spaces,
    preserving line count.

    Not a full parser — regex-based, good enough for this diagnostic test.
    Handles the three common docstring forms: ``\"\"\"...\"\"\"`` and ``'''...'''``
    on single or multiple lines. String literals that aren't docstrings
    (e.g. ``x = "...purchase_price_original..."``) are intentionally NOT
    stripped — they could be executable SQL strings. We strip only triple-
    quoted blocks which are structurally docstrings in practice.
    """
    # Strip triple-quoted strings, preserving newlines.
    def _repl_triple(m: re.Match[str]) -> str:
        text = m.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in text)

    out = re.sub(r'"""[\s\S]*?"""', _repl_triple, source)
    out = re.sub(r"'''[\s\S]*?'''", _repl_triple, out)

    # Strip line comments. Use a line-by-line pass to avoid accidentally
    # matching ``#`` inside strings (best-effort — a proper tokenizer would
    # be more correct, but for our purposes this is sufficient).
    stripped_lines = []
    for line in out.split("\n"):
        stripped_lines.append(_PY_LINE_COMMENT_RE.sub("", line))
    return "\n".join(stripped_lines)


def _strip_comments_ts(source: str) -> str:
    """Strip TS/JS line comments ``//`` and block comments ``/* */``,
    preserving line count."""

    def _repl_block(m: re.Match[str]) -> str:
        text = m.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in text)

    out = re.sub(r"/\*[\s\S]*?\*/", _repl_block, source)
    stripped_lines = []
    for line in out.split("\n"):
        stripped_lines.append(_TS_LINE_COMMENT_RE.sub("", line))
    return "\n".join(stripped_lines)


def _strip_comments_for_suffix(source: str, suffix: str) -> str:
    if suffix == ".py":
        return _strip_comments_python(source)
    return _strip_comments_ts(source)


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------


def _iter_production_files() -> list[Path]:
    files: list[Path] = []
    for root in PRODUCTION_PATHS:
        abs_root = PROJECT_ROOT / root
        if abs_root.is_file():
            rel = abs_root.relative_to(PROJECT_ROOT).as_posix()
            if not _is_path_allowlisted(rel):
                files.append(abs_root)
            continue
        if not abs_root.exists():
            continue
        for p in abs_root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in SCAN_EXTENSIONS:
                continue
            rel = p.relative_to(PROJECT_ROOT).as_posix()
            if _is_path_allowlisted(rel):
                continue
            files.append(p)
    return files


def _scan_file(path: Path) -> list[LegacyRef]:
    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    is_main_py = rel_path == "main.py"
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []  # binary / unreadable — skip

    # Strip comments / docstrings to focus scanning on executable code.
    # Comments frequently reference the columns in migration notes and
    # historical rationale; flagging them produces noise, not signal.
    source = _strip_comments_for_suffix(raw, path.suffix)
    lines = source.splitlines()

    refs: list[LegacyRef] = []

    for idx, line in enumerate(lines):
        line_no = idx + 1
        prev_line = lines[idx - 1] if idx > 0 else ""

        # Fast-path skip for main.py hardcoded DORMANT ranges.
        if is_main_py and _is_line_in_main_py_dormant_range(line_no):
            continue

        # Opt-in marker — honor on current or previous line.
        if _has_dormant_marker(line, prev_line):
            continue

        # Pattern 1: ``.from|.table("quote_items")`` with legacy col in select.
        if _QUOTE_ITEMS_TABLE_RE.search(line):
            cols = _is_legacy_quote_items_select(lines, idx)
            for col in cols:
                refs.append(
                    LegacyRef(
                        path=rel_path,
                        line_no=line_no,
                        column=col,
                        snippet=line,
                    )
                )

        # Pattern 2: raw SQL ``FROM quote_items`` + legacy column in the
        # surrounding statement. We look 10 lines either side so multi-line
        # SQL strings are covered.
        if _FROM_QUOTE_ITEMS_RE.search(line):
            window_start = max(0, idx - 10)
            window_end = min(len(lines), idx + 10)
            window_blob = _strip_new_table_subselects(
                "\n".join(lines[window_start:window_end])
            )
            for col in LEGACY_COLUMNS:
                # Skip ``invoice_id`` inside docstrings that mention quote_items
                # incidentally — we only flag when the token is inside a SELECT
                # list. A quick proxy: require the column name on the same line
                # or within 3 lines of the FROM.
                local_window = "\n".join(
                    lines[max(0, idx - 3) : min(len(lines), idx + 10)]
                )
                local_cleaned = _strip_new_table_subselects(local_window)
                if (
                    re.search(r"\b" + re.escape(col) + r"\b", local_cleaned)
                    and re.search(r"\bSELECT\b", local_cleaned, re.IGNORECASE)
                ):
                    refs.append(
                        LegacyRef(
                            path=rel_path,
                            line_no=line_no,
                            column=col,
                            snippet=line,
                        )
                    )

        # Pattern 3: ``UPDATE quote_items`` setting a legacy column.
        if _UPDATE_QUOTE_ITEMS_RE.search(line):
            window_blob = "\n".join(
                lines[idx : min(len(lines), idx + 15)]
            )
            cleaned = _strip_new_table_subselects(window_blob)
            for col in LEGACY_COLUMNS:
                if re.search(
                    r"\b" + re.escape(col) + r"\s*=",
                    cleaned,
                ):
                    refs.append(
                        LegacyRef(
                            path=rel_path,
                            line_no=line_no,
                            column=col,
                            snippet=line,
                        )
                    )

        # Pattern 4: legacy ``invoice_item_prices`` table name anywhere in
        # production code (regardless of context — the table is gone).
        if LEGACY_TABLE in line:
            refs.append(
                LegacyRef(
                    path=rel_path,
                    line_no=line_no,
                    column=LEGACY_TABLE,
                    snippet=line,
                )
            )

    # Deduplicate — same (line, column) might hit multiple patterns.
    seen: set[tuple[str, int, str]] = set()
    unique: list[LegacyRef] = []
    for r in refs:
        key = (r.path, r.line_no, r.column)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_legacy_quote_items_refs_in_production_code() -> None:
    """Zero legacy references in production code outside DORMANT allowlist.

    If this fails, the printed list shows each surviving reference. For
    each one, either (a) refactor to read from invoice_items via coverage,
    or (b) add a ``# phase-5d: dormant-fasthtml-exempt`` marker on the
    preceding line if the surface is knowingly DORMANT.
    """
    all_refs: list[LegacyRef] = []
    for path in _iter_production_files():
        all_refs.extend(_scan_file(path))

    if all_refs:
        msg_lines = [
            f"Found {len(all_refs)} legacy reference(s) in production code:",
            "",
        ]
        for r in all_refs:
            msg_lines.append("  " + r.describe())
        msg_lines.append("")
        msg_lines.append(
            "Migration 284 drops these columns + the invoice_item_prices "
            "table. Each reference above must be either (a) refactored to "
            "read from invoice_items via invoice_item_coverage, or (b) "
            "marked with ``# phase-5d: dormant-fasthtml-exempt`` on the "
            "preceding/same line if the surface is knowingly DORMANT."
        )
        pytest.fail("\n".join(msg_lines))


@pytest.mark.unit
def test_migration_284_file_exists() -> None:
    """Migration 284 SQL file must be present in the migrations directory.

    Guards against the regression check landing before the actual migration
    is written.
    """
    mig = PROJECT_ROOT / "migrations" / "284_drop_legacy_schema.sql"
    assert mig.is_file(), f"Missing migration file: {mig}"


@pytest.mark.unit
def test_migration_284_drops_expected_columns() -> None:
    """Migration 284 SQL contains DROP COLUMN for each of the 16 legacy cols."""
    mig = PROJECT_ROOT / "migrations" / "284_drop_legacy_schema.sql"
    sql = mig.read_text(encoding="utf-8")
    missing: list[str] = []
    for col in LEGACY_COLUMNS:
        if not re.search(
            r"DROP\s+COLUMN\s+IF\s+EXISTS\s+" + re.escape(col) + r"\b",
            sql,
            re.IGNORECASE,
        ):
            missing.append(col)
    assert not missing, (
        f"Migration 284 is missing DROP COLUMN for: {missing}"
    )


@pytest.mark.unit
def test_migration_284_drops_invoice_item_prices() -> None:
    """Migration 284 SQL drops the kvota.invoice_item_prices table."""
    mig = PROJECT_ROOT / "migrations" / "284_drop_legacy_schema.sql"
    sql = mig.read_text(encoding="utf-8")
    assert re.search(
        r"DROP\s+TABLE\s+IF\s+EXISTS\s+kvota\.invoice_item_prices\b",
        sql,
        re.IGNORECASE,
    ), "Migration 284 must contain DROP TABLE IF EXISTS kvota.invoice_item_prices"


@pytest.mark.unit
def test_migration_284_recreates_positions_registry_view() -> None:
    """Migration 284 must DROP + CREATE positions_registry_view.

    PostgreSQL won't drop columns while a view depends on them, so the
    view must be dropped before ALTER TABLE DROP COLUMN runs. After the
    drops, the view is recreated sourcing price data from invoice_items.
    """
    mig = PROJECT_ROOT / "migrations" / "284_drop_legacy_schema.sql"
    sql = mig.read_text(encoding="utf-8")
    assert re.search(
        r"DROP\s+VIEW\s+IF\s+EXISTS\s+kvota\.positions_registry_view\b",
        sql,
        re.IGNORECASE,
    ), "Migration 284 must DROP VIEW positions_registry_view before dropping columns"
    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+kvota\.positions_registry_view\b",
        sql,
        re.IGNORECASE,
    ), "Migration 284 must recreate positions_registry_view after column drops"
    # The rewritten view should source price via invoice_items JOIN.
    assert "invoice_items" in sql and "invoice_item_coverage" in sql, (
        "Rewritten view must JOIN invoice_items + invoice_item_coverage"
    )
