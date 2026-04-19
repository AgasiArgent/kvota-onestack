"""
Regression guard (Phase 5d recovery T3) — catches JS/TS property accesses
on ``QuoteItemRow``-typed values that reference columns dropped in
migration 284.

Why this exists
---------------
The sibling guard ``test_migration_284_no_legacy_refs.py`` only scans
``.from("quote_items").select(...)`` / raw-SQL contexts. It misses
property-access sites like ``item.invoice_id`` where ``item`` is typed
``QuoteItemRow``. Post-migration-284, those reads return ``undefined`` at
runtime because the columns no longer exist on the row shape — tsc flags
them as compile errors only after ``database.types.ts`` is regenerated.

During the 2026-04-19 migration-284 apply attempt, a silent runtime break
on ``logistics-step.tsx:33`` (``item.invoice_id``) slipped past the
existing guard and only surfaced via tsc once types were regenerated.
This module closes that gap so CI blocks future PRs that introduce the
same pattern.

Detection strategy
------------------
Per-file, regex + scope-aware walk:

  Pass 1 — typed bindings.
  Scan every declaration of form ``<name>[?]: <Type>[]`` (array) and
  ``<name>[?]: <Type>`` (scalar). For each, record the effective scope:
    - Inside a function/arrow parameter list → scope is the function
      body that follows the parameter list.
    - Inside an ``interface X { ... }`` or ``type X = { ... }`` body →
      scope is file-wide (types are ambient).
    - Inside any other ``{...}`` block → scope is that block.
    - At top level → scope is file-wide.
  Bindings for BOTH ``QuoteItemRow`` and competing types are recorded,
  so local ``items: CompleteGuardItem[]`` correctly shadows a file-wide
  ``items: QuoteItemRow[]`` prop.

  Pass 2 — closure bindings.
  For each closure / iterator of the form
    - ``<coll>.(map|filter|reduce|forEach|...)((<el>[, <i>]) => ...)``
    - ``for (const <el> of <coll>)``
  resolve ``<coll>``'s type via the innermost Pass-1 binding at the
  closure's position. Record the closure's body byte range alongside
  ``<el>`` and the collection's typename.

  Pass 3 — detect accesses.
  For each ``<base>.<LEGACY_COL>`` match:
    - If there's a closure binding of ``<base>`` that contains the
      access position, take the innermost and keep the match iff that
      binding's type is ``QuoteItemRow``.
    - Else, take the innermost Pass-1 scalar binding of ``<base>`` and
      keep the match iff its type is ``QuoteItemRow``.
  For ``<coll>[N].<LEGACY_COL>`` direct-index accesses, keep the match
  iff the innermost Pass-1 array binding of ``<coll>`` at that position
  is ``QuoteItemRow[]``.

This scope-aware heuristic produces zero false positives on the current
codebase: we only flag accesses on variables we KNOW are bound to a
QuoteItemRow, and we respect inner shadowing.

Exemptions
----------
  1. Files on the skip list (tests, generated types, entity queries,
     types module).
  2. Block / line comments (stripped before scanning).
  3. Lines with the opt-in marker
     ``// phase-5d: dormant-fasthtml-exempt`` on the same line or
     preceding line.
  4. Accesses inside a nested closure that rebinds the same name to a
     different type (not common — ignored; adds false-negatives only).

Run
---
    pytest tests/test_migration_284_js_property_refs.py -v
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Columns dropped from ``quote_items`` in migration 284. Kept in sync with
# ``test_migration_284_no_legacy_refs.LEGACY_COLUMNS`` — see
# ``test_legacy_columns_align_with_sibling_guard`` for enforcement.
#
# ``invoice_id`` is intentionally INCLUDED here despite being too generic
# for the sibling's string-match scan: in this guard we only flag
# ``<el>.invoice_id`` where ``<el>`` is bound to a QuoteItemRow collection,
# which eliminates the false positives on invoice_items rows etc.
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
    "invoice_id",
)

# Roots to scan. Frontend-only: Python accesses are covered by the
# sibling guard's dict/SQL scans.
SCAN_ROOTS: tuple[str, ...] = ("frontend/src",)

SCAN_EXTENSIONS: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx")

# Global skip list (path fragments).
SKIP_PATH_FRAGMENTS: tuple[str, ...] = (
    "__pycache__",
    "node_modules",
    ".next",
    "dist",
    "build",
    # Frontend tests reference legacy names in mock data; refactored as
    # part of T2. tsc catches their regressions, not this guard.
    "__tests__",
    # Auto-generated schema types mirror the live DB.
    "frontend/src/shared/types/database.types.ts",
    # Where QuoteItemRow is DEFINED — any reference is self-referential.
    "frontend/src/entities/quote/queries.ts",
    "frontend/src/entities/quote/types.ts",
)

# Opt-in marker matching the sibling guard.
DORMANT_MARKER_RE = re.compile(
    r"(?:^|\s)//\s*phase-5d:\s*dormant-fasthtml-exempt\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Comment stripping (TS/JS only)
# ---------------------------------------------------------------------------

_TS_LINE_COMMENT_RE = re.compile(r"//.*$")


def _strip_comments_ts(source: str) -> str:
    """Remove ``/* ... */`` block comments and ``//`` line comments while
    preserving line count."""

    def _repl_block(m: re.Match[str]) -> str:
        text = m.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in text)

    out = re.sub(r"/\*[\s\S]*?\*/", _repl_block, source)
    return "\n".join(_TS_LINE_COMMENT_RE.sub("", line) for line in out.split("\n"))


# ---------------------------------------------------------------------------
# Balanced-paren utility (used by binding + closure walks)
# ---------------------------------------------------------------------------


def _balanced_body_end(source: str, open_idx: int, open_ch: str) -> int:
    """Given the byte index of an opening paren/brace, return the byte
    index of its matching close. Returns ``len(source)`` if unbalanced.

    Walks a simple character-by-character match counter.
    """
    pairs = {"(": ")", "{": "}", "[": "]"}
    close_ch = pairs[open_ch]
    depth = 0
    i = open_idx
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


# ---------------------------------------------------------------------------
# Type binding detection (Pass 1)
# ---------------------------------------------------------------------------

# ``<identifier>[?]: <TypeName>[]`` — typed array binding. Covers props,
# fn params, local lets. Capture: (1) identifier, (2) typename.
_ANY_COLLECTION_TYPE_RE = re.compile(
    r"""
    \b
    ([A-Za-z_$][\w$]*)              # (1) identifier
    \s*\??\s*:\s*
    ([A-Z][A-Za-z_$][\w$]*)         # (2) typename (uppercase-starting)
    \s*\[\s*\]
    """,
    re.VERBOSE,
)

# ``<identifier>[?]: <TypeName>`` — single typed binding (NOT an array).
# Used to flag direct function params like ``function f(item: QuoteItemRow)``.
# Capture: (1) identifier, (2) typename.
#
# The negative lookahead uses ``\b`` + ``[^\w...]`` to prevent partial-
# typename matches via regex backtracking. We match the full typename
# greedily, then require the next non-word character to be NOT ``[`` and
# NOT ``.``.
_SCALAR_TYPE_RE = re.compile(
    r"""
    \b
    ([A-Za-z_$][\w$]*)              # (1) identifier
    \s*\??\s*:\s*
    ([A-Z][A-Za-z_$][\w$]*)         # (2) typename (uppercase-starting)
    \b                              # word boundary anchors typename end
    (?!\s*[\[.])                    # next non-whitespace must NOT be [ or .
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class TypeBinding:
    """One typed binding (collection or scalar) with its scope range.

    Scope is the innermost ``{...}`` block that contains the declaration.
    Top-level declarations (not inside braces) have scope = entire file.
    """

    name: str           # identifier being bound
    type_name: str      # the bound typename (without ``[]`` suffix)
    is_array: bool      # True for ``T[]``, False for ``T``
    start: int          # byte offset where scope begins (``{`` position)
    end: int            # byte offset where scope ends (``}`` position)


def _enclosing_body_range(source: str, pos: int) -> tuple[int, int]:
    """Return the byte range of the binding's effective scope.

    Rules:
      1. If ``pos`` is inside a ``(...)`` that's followed (after
         optional ``: RetType``) by ``{`` or ``=>``, the scope is the
         function/arrow body that follows the parameter list.
      2. Else, if ``pos`` is inside ``{...}`` which is itself an
         ``interface X { ... }`` or ``type X = { ... }`` body, the
         binding is ambient and scope is the whole file.
      3. Else, if ``pos`` is inside ``{...}``, scope is that block.
      4. Else (top-level), scope is the whole file.
    """
    # (1) Check for param-list scope first.
    #
    # Walk backward past matched parens to find the innermost UNCLOSED
    # ``(``. Stop if we hit ``{`` first (that means we're inside a
    # braced scope, not a param list).
    paren_depth = 0
    brace_depth = 0
    param_open = -1
    for i in range(pos, -1, -1):
        ch = source[i]
        if ch == ")":
            paren_depth += 1
        elif ch == "(":
            if paren_depth == 0:
                param_open = i
                break
            paren_depth -= 1
        elif ch == "}":
            brace_depth += 1
        elif ch == "{":
            if brace_depth == 0:
                # We're inside a ``{...}`` block, not a ``(...)``.
                # Fall through to brace handling below.
                break
            brace_depth -= 1

    if param_open >= 0:
        param_close = _balanced_body_end(source, param_open, "(")
        # Check what follows the closing ``)``: optionally ``: <RetType>``,
        # then ``{`` or ``=>``.
        after = source[param_close + 1 : param_close + 200]
        # Strip a return-type annotation: ``: <anything until { or => or ;>``
        # Only interpret ``:`` as return-type if followed by a typename.
        m = re.match(r"\s*(?::\s*[^{=;]+)?\s*(?:\{|=>\s*\{?)", after)
        if m:
            # Find ``{`` after param_close; if present, scope is that block.
            # If ``=>`` without ``{``, scope is until the statement terminator.
            brace_idx = source.find("{", param_close + 1, param_close + 1 + len(after))
            if brace_idx >= 0:
                close = _balanced_body_end(source, brace_idx, "{")
                return (brace_idx, close)
            # Arrow function without braces → single-expression body. We
            # cannot precisely scope it; fall through to brace handling.

    # (2)/(3)/(4): brace-scope handling (same as before).
    depth = 0
    open_pos = -1
    for i in range(pos, -1, -1):
        ch = source[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                open_pos = i
                break
            depth -= 1
    if open_pos < 0:
        return (0, len(source))
    # Interface / type body → ambient, file-wide.
    lead = source[max(0, open_pos - 80):open_pos]
    if re.search(r"\binterface\s+[A-Za-z_$][\w$]*(?:\s*extends\s[^{]+)?\s*$", lead):
        return (0, len(source))
    if re.search(r"\btype\s+[A-Za-z_$][\w$]*\s*=\s*$", lead):
        return (0, len(source))
    close_pos = _balanced_body_end(source, open_pos, "{")
    return (open_pos, close_pos)


def _find_type_bindings(source: str) -> list[TypeBinding]:
    """Return all typed bindings in the file with their enclosing
    brace-block scope. A binding applies only within the innermost
    ``{...}`` that contains its declaration — this lets us distinguish
    ``items: CompleteGuardItem[]`` inside one function from
    ``items: QuoteItemRow[]`` inside another.

    Top-level declarations (not inside any ``{...}``) apply to the whole
    file — covers React component prop types and top-level interfaces.
    """
    bindings: list[TypeBinding] = []
    # Array bindings.
    for m in _ANY_COLLECTION_TYPE_RE.finditer(source):
        start, end = _enclosing_body_range(source, m.start())
        bindings.append(
            TypeBinding(
                name=m.group(1),
                type_name=m.group(2),
                is_array=True,
                start=start,
                end=end,
            )
        )
    # Scalar bindings. We'd double-match the collection form (the
    # scalar regex uses a negative lookahead for ``[``), so these are
    # strictly scalar.
    for m in _SCALAR_TYPE_RE.finditer(source):
        start, end = _enclosing_body_range(source, m.start())
        bindings.append(
            TypeBinding(
                name=m.group(1),
                type_name=m.group(2),
                is_array=False,
                start=start,
                end=end,
            )
        )
    return bindings


def _innermost_type_binding(
    bindings: list[TypeBinding], name: str, pos: int, *, is_array: bool
) -> TypeBinding | None:
    """Return the innermost binding of ``name`` whose scope contains
    ``pos`` and matches ``is_array``.
    """
    candidates = [
        b for b in bindings
        if b.name == name
        and b.is_array == is_array
        and b.start <= pos <= b.end
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda b: b.end - b.start)


# ---------------------------------------------------------------------------
# Closure-body detection (Pass 2)
# ---------------------------------------------------------------------------

_CLOSURE_METHODS = (
    "map", "filter", "reduce", "reduceRight", "forEach",
    "some", "every", "find", "findIndex", "findLast",
    "flatMap",
)


def _build_method_closure_re() -> re.Pattern[str]:
    """Match ``<coll>.(map|filter|...)((<el>[, <i>]) => ...)``.

    Captures:
      coll   — collection identifier
      method — method name
      first  — first callback param
      second — second callback param (reduce uses this as the element)
    """
    methods = "|".join(_CLOSURE_METHODS)
    return re.compile(
        rf"""
        \b(?P<coll>[A-Za-z_$][\w$]*)
        \.\s*
        (?P<method>{methods})
        \(\s*\(?\s*
        (?P<first>[A-Za-z_$][\w$]*)
        (?:\s*,\s*(?P<second>[A-Za-z_$][\w$]*))?
        (?:\s*,\s*(?P<third>[A-Za-z_$][\w$]*))?
        """,
        re.VERBOSE,
    )


def _build_for_of_re() -> re.Pattern[str]:
    """Match ``for (const|let|var <el> of <coll>)``."""
    return re.compile(
        r"""
        \bfor\s*\(\s*
        (?:const|let|var)\s+
        (?P<first>[A-Za-z_$][\w$]*)
        \s+of\s+
        (?P<coll>[A-Za-z_$][\w$]*)
        \b
        """,
        re.VERBOSE,
    )


_METHOD_CLOSURE_RE = _build_method_closure_re()
_FOR_OF_RE = _build_for_of_re()


@dataclass(frozen=True)
class Binding:
    """Closure binding of an element name against a typed collection."""

    element: str           # variable name bound to the element
    collection_type: str   # typename of the collection (e.g. QuoteItemRow)
    start: int             # byte offset where binding scope begins
    end: int               # byte offset where binding scope ends


def _collect_bindings(
    source: str, type_bindings: list[TypeBinding]
) -> list[Binding]:
    """Walk the source, producing all closure bindings with their
    scope byte ranges.

    For method closures, the scope is the body of the callback. For
    ``for (... of coll)``, the scope is the statement body.

    The collection's typename is resolved SCOPE-AWARE: the innermost
    type binding of the collection variable whose scope contains the
    closure site wins. This lets us correctly classify a local
    ``items: CompleteGuardItem[]`` inside one function while another
    function has ``items: QuoteItemRow[]``.
    """
    bindings: list[Binding] = []

    # Method closures: <coll>.<method>((el, [i]) => <body>)
    for m in _METHOD_CLOSURE_RE.finditer(source):
        coll = m.group("coll")
        coll_type_binding = _innermost_type_binding(
            type_bindings, coll, m.start(), is_array=True
        )
        if coll_type_binding is None:
            continue
        typename = coll_type_binding.type_name
        method = m.group("method")
        if method in {"reduce", "reduceRight"}:
            element = m.group("second")
        else:
            element = m.group("first")
        if not element:
            continue
        call_open = source.find("(", m.start("method"))
        if call_open < 0:
            continue
        call_close = _balanced_body_end(source, call_open, "(")
        bindings.append(
            Binding(
                element=element,
                collection_type=typename,
                start=call_open,
                end=call_close,
            )
        )

    # for (const el of coll) { ... }
    for m in _FOR_OF_RE.finditer(source):
        coll = m.group("coll")
        coll_type_binding = _innermost_type_binding(
            type_bindings, coll, m.start(), is_array=True
        )
        if coll_type_binding is None:
            continue
        typename = coll_type_binding.type_name
        element = m.group("first")
        header_open = source.rfind("(", 0, m.end())
        if header_open < 0:
            continue
        header_close = _balanced_body_end(source, header_open, "(")
        body_start = header_close + 1
        i = body_start
        while i < len(source) and source[i] in " \t\r\n":
            i += 1
        if i < len(source) and source[i] == "{":
            body_end = _balanced_body_end(source, i, "{")
        else:
            nl = source.find("\n", i)
            sc = source.find(";", i)
            body_end = min(x for x in (nl, sc, len(source)) if x > i)
        bindings.append(
            Binding(
                element=element,
                collection_type=typename,
                start=body_start,
                end=body_end,
            )
        )

    return bindings


def _nearest_binding_for(
    bindings: list[Binding], element: str, pos: int
) -> Binding | None:
    """Return the innermost binding of ``element`` whose range contains
    ``pos``, or ``None`` if no binding applies.

    Innermost = smallest range containing ``pos``.
    """
    candidates = [
        b for b in bindings
        if b.element == element and b.start <= pos <= b.end
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda b: b.end - b.start)


# ---------------------------------------------------------------------------
# Access detection (Pass 3)
# ---------------------------------------------------------------------------


def _build_prop_access_re(col: str) -> re.Pattern[str]:
    """``<base>.<col>`` or ``<base>?.<col>``. Capture base = group(1)."""
    col_q = re.escape(col)
    return re.compile(
        rf"\b([A-Za-z_$][\w$]*)\s*(?:\.|\?\.)\s*{col_q}\b"
    )


def _build_index_access_re(coll: str, col: str) -> re.Pattern[str]:
    coll_q = re.escape(coll)
    col_q = re.escape(col)
    return re.compile(
        rf"\b{coll_q}\[\s*[^\]]+\]\s*(?:\.|\?\.)\s*{col_q}\b"
    )


_PROP_ACCESS_RES: dict[str, re.Pattern[str]] = {
    col: _build_prop_access_re(col) for col in LEGACY_COLUMNS
}


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacyPropertyRef:
    """One detected property-access violation."""

    path: str  # relative to PROJECT_ROOT
    line_no: int  # 1-indexed
    column: str
    base: str  # LHS identifier (or ``coll[N]`` for index access)
    snippet: str

    def describe(self) -> str:
        return (
            f"{self.path}:{self.line_no}  "
            f"[{self.base}.{self.column}]  "
            f"{self.snippet.strip()[:160]}"
        )


def _is_path_allowlisted(rel_path: str) -> bool:
    return any(frag in rel_path for frag in SKIP_PATH_FRAGMENTS)


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        abs_root = PROJECT_ROOT / root
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


def _has_dormant_marker(line: str, prev_line: str) -> bool:
    return bool(
        DORMANT_MARKER_RE.search(line) or DORMANT_MARKER_RE.search(prev_line)
    )


def _offset_to_line_no(source: str, offset: int) -> int:
    """1-indexed line number for a given byte offset."""
    return source.count("\n", 0, offset) + 1


def _line_bounds(source: str, line_no: int) -> tuple[int, int]:
    """(start, end) byte offsets of the given 1-indexed line."""
    # Find the start by counting newlines.
    start = 0
    for _ in range(line_no - 1):
        nl = source.find("\n", start)
        if nl < 0:
            return (start, len(source))
        start = nl + 1
    end = source.find("\n", start)
    if end < 0:
        end = len(source)
    return (start, end)


def _scan_file(path: Path) -> list[LegacyPropertyRef]:
    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    # Scanning uses the comment-stripped source (comments freely mention
    # legacy names in doc blocks). The dormant-marker check uses the
    # RAW source so the marker comment itself is visible.
    raw_lines = raw.splitlines()
    source = _strip_comments_ts(raw)

    # Pass 1: all typed bindings (collections + scalars) with their
    # brace-scoped ranges.
    type_bindings = _find_type_bindings(source)

    # Quick exit: no QuoteItemRow binding of any kind.
    if not any(b.type_name == "QuoteItemRow" for b in type_bindings):
        return []

    # Precompute the set of collection names that are QuoteItemRow[]
    # somewhere (for the index-access pass).
    qi_collection_names = {
        b.name for b in type_bindings
        if b.type_name == "QuoteItemRow" and b.is_array
    }

    # Pass 2: scope-aware closure bindings (for collections).
    bindings = _collect_bindings(source, type_bindings)

    # Pass 3: property-access hits.
    lines = source.splitlines()
    refs: list[LegacyPropertyRef] = []
    seen: set[tuple[str, int, str, str]] = set()

    for col in LEGACY_COLUMNS:
        # Element accesses: find every ``<base>.<col>`` and classify the
        # ``<base>`` binding. Resolution order (closest binding wins):
        #   (a) innermost closure binding of ``<base>`` containing the
        #       access — fires if the closure iterates a QuoteItemRow[]
        #       collection.
        #   (b) innermost scalar type binding of ``<base>`` in scope —
        #       fires if declared ``<base>: QuoteItemRow``.
        for m in _PROP_ACCESS_RES[col].finditer(source):
            base = m.group(1)
            pos = m.start()
            line_no = _offset_to_line_no(source, pos)

            closure_binding = _nearest_binding_for(bindings, base, pos)

            if closure_binding is not None:
                # Innermost closure wins — shadows any outer scalar
                # binding of the same name.
                if closure_binding.collection_type != "QuoteItemRow":
                    continue
                # else: fall through to flag.
            else:
                scalar_binding = _innermost_type_binding(
                    type_bindings, base, pos, is_array=False
                )
                if scalar_binding is None:
                    continue
                if scalar_binding.type_name != "QuoteItemRow":
                    continue

            # Opt-in marker on this line or the previous line — checked
            # against the RAW source (comments are stripped from
            # ``source``, so the marker has to come from ``raw_lines``).
            raw_line = raw_lines[line_no - 1] if line_no - 1 < len(raw_lines) else ""
            raw_prev = (
                raw_lines[line_no - 2]
                if line_no >= 2 and line_no - 2 < len(raw_lines)
                else ""
            )
            if _has_dormant_marker(raw_line, raw_prev):
                continue

            key = (rel_path, line_no, col, base)
            if key in seen:
                continue
            seen.add(key)

            # Snippet: the raw source line (before comment-stripping).
            snippet = lines[line_no - 1] if line_no - 1 < len(lines) else ""
            refs.append(
                LegacyPropertyRef(
                    path=rel_path,
                    line_no=line_no,
                    column=col,
                    base=base,
                    snippet=snippet,
                )
            )

        # Index accesses: ``<coll>[N].<col>`` where ``<coll>`` is a
        # QuoteItemRow collection.
        for coll in qi_collection_names:
            for m in _build_index_access_re(coll, col).finditer(source):
                pos = m.start()
                line_no = _offset_to_line_no(source, pos)
                # Scope check: the coll name must resolve to
                # QuoteItemRow[] at THIS position (not merely somewhere
                # in the file).
                coll_binding = _innermost_type_binding(
                    type_bindings, coll, pos, is_array=True
                )
                if coll_binding is None or coll_binding.type_name != "QuoteItemRow":
                    continue

                line_start, line_end = _line_bounds(source, line_no)
                line = source[line_start:line_end]
                prev_line = ""
                if line_no > 1:
                    prev_start, prev_end = _line_bounds(source, line_no - 1)
                    prev_line = source[prev_start:prev_end]
                if _has_dormant_marker(line, prev_line):
                    continue

                base = f"{coll}[...]"
                key = (rel_path, line_no, col, base)
                if key in seen:
                    continue
                seen.add(key)

                snippet = lines[line_no - 1] if line_no - 1 < len(lines) else line
                refs.append(
                    LegacyPropertyRef(
                        path=rel_path,
                        line_no=line_no,
                        column=col,
                        base=base,
                        snippet=snippet,
                    )
                )

    return refs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_legacy_property_accesses_on_quote_item_row() -> None:
    """Zero legacy-column property accesses on QuoteItemRow-bound values.

    If this fails, each printed violation is a post-migration-284 runtime
    break — ``item.<legacy_col>`` returns ``undefined`` because the
    column no longer exists on the selected row shape.

    To fix a violation, either:
      - Switch the source data to ``invoice_items`` (joined via
        ``invoice_item_coverage``) and retype the prop / variable
        accordingly.
      - Pass the legacy value through props from a parent that already
        has the invoice_items row.
      - If the access is knowingly DORMANT (e.g. FastHTML-adjacent
        helper kept alive through the strangler-fig migration), add
        ``// phase-5d: dormant-fasthtml-exempt`` on or above the line.
    """
    all_refs: list[LegacyPropertyRef] = []
    for path in _iter_scan_files():
        all_refs.extend(_scan_file(path))

    if all_refs:
        msg_lines = [
            f"Found {len(all_refs)} legacy property access(es) on "
            f"QuoteItemRow-bound values:",
            "",
        ]
        for r in all_refs:
            msg_lines.append("  " + r.describe())
        msg_lines.append("")
        msg_lines.append(
            "Migration 284 drops the columns above from kvota.quote_items. "
            "Each access reads ``undefined`` at runtime. Rebind to an "
            "invoice_items row via coverage, or mark DORMANT with "
            "``// phase-5d: dormant-fasthtml-exempt``."
        )
        pytest.fail("\n".join(msg_lines))


@pytest.mark.unit
def test_guard_scope_is_non_empty() -> None:
    """Meta-test: at least one file declares a ``QuoteItemRow[]``
    collection binding.

    If the scope goes empty (all files filtered out, repo restructured),
    the main test would trivially pass — this test catches that.
    """
    matched = 0
    for p in _iter_scan_files():
        src = p.read_text(encoding="utf-8", errors="ignore")
        bindings = _find_type_bindings(_strip_comments_ts(src))
        if any(b.type_name == "QuoteItemRow" for b in bindings):
            matched += 1
    assert matched >= 5, (
        f"Scan scope has only {matched} files declaring a ``QuoteItemRow`` "
        f"binding. Expected at least 5. Verify SCAN_ROOTS and "
        f"SKIP_PATH_FRAGMENTS are correct."
    )


@pytest.mark.unit
def test_legacy_columns_align_with_sibling_guard() -> None:
    """Our LEGACY_COLUMNS list must match the sibling guard's list.

    If migration 284 changes (e.g. a column is added or removed from
    the drop list), both guards need updating together.
    """
    sibling = (
        PROJECT_ROOT / "tests" / "test_migration_284_no_legacy_refs.py"
    ).read_text(encoding="utf-8")
    # Find the opening of the tuple literal, then walk forward to the
    # matching close paren. A simple regex ``\(([\s\S]*?)\)`` would stop
    # at the first inner ``)`` (e.g. inside a comment), so we do matched-
    # paren walking here.
    start_m = re.search(
        r"LEGACY_COLUMNS:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(",
        sibling,
    )
    assert start_m, "Could not locate LEGACY_COLUMNS in sibling guard"
    open_pos = sibling.index("(", start_m.start())
    depth = 0
    close_pos = -1
    for i in range(open_pos, len(sibling)):
        ch = sibling[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                close_pos = i
                break
    assert close_pos > 0, "Unbalanced parentheses in sibling LEGACY_COLUMNS"
    body = sibling[open_pos + 1 : close_pos]
    # Strip line comments before extracting string literals — otherwise
    # ``# ... "invoice_id" ...`` in a commentary could pollute results.
    body_no_comments = re.sub(r"#[^\n]*", "", body)
    sibling_cols = set(re.findall(r'"([a-z_][a-z0-9_]*)"', body_no_comments))
    ours = set(LEGACY_COLUMNS)
    # Both directions must match — keeping them identical is the policy.
    assert ours == sibling_cols, (
        f"LEGACY_COLUMNS diverged between guards. "
        f"Only in this guard: {sorted(ours - sibling_cols)}. "
        f"Only in sibling guard: {sorted(sibling_cols - ours)}. "
        f"Update both in lockstep."
    )
