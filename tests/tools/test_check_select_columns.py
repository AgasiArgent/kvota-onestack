"""Unit tests for the schema-drift lint tool.

Each test creates an isolated temporary repo with a small ``database.types.ts``
fixture and a single ``.py`` source file, then invokes the lint via
``main(argv)`` and asserts on stdout/stderr/exit-code.
"""

from __future__ import annotations

import io
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

# Add tools/ to sys.path so we can import directly.
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import check_select_columns as cs  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _write_types(tmp_path: Path, body: str) -> Path:
    """Write a minimal ``database.types.ts`` and return its path."""
    types = tmp_path / "database.types.ts"
    types.write_text(textwrap.dedent(body), encoding="utf-8")
    return types


def _write_py(tmp_path: Path, name: str, body: str) -> Path:
    """Write a small Python source file under ``tmp_path`` and return its path."""
    py = tmp_path / name
    py.write_text(textwrap.dedent(body), encoding="utf-8")
    return py


def _run(types: Path, *py_paths: Path) -> tuple[int, str, str]:
    """Invoke the lint and capture (exit_code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    argv = ["--types-file", str(types), *(str(p) for p in py_paths)]
    with redirect_stdout(out), redirect_stderr(err):
        code = cs.main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def basic_types(tmp_path: Path) -> Path:
    """A minimal types.ts with two tables we use in most tests."""
    return _write_types(
        tmp_path,
        """\
        export type Json = string

        export type Database = {
          kvota: {
            Tables: {
              quotes: {
                Row: {
                  id: string
                  organization_id: string
                  currency: string
                  customer_id: string | null
                }
                Insert: {}
                Update: {}
                Relationships: []
              }
              quote_items: {
                Row: {
                  id: string
                  quote_id: string
                  hs_code: string | null
                  quantity: number
                }
                Insert: {}
                Update: {}
                Relationships: []
              }
            }
            Views: { [_ in never]: never }
            Functions: { [_ in never]: never }
          }
        }
        """,
    )


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_valid_columns_clean(tmp_path, basic_types):
    """All selected columns exist on the table → exit 0, no violations."""
    py = _write_py(
        tmp_path,
        "good.py",
        """\
        def fetch(supabase):
            return (
                supabase.table("quotes")
                .select("id, organization_id, currency")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "not in" not in out  # no violation lines


def test_invalid_column_flagged(tmp_path, basic_types):
    """An invalid column name → exit 1, violation reported."""
    py = _write_py(
        tmp_path,
        "bad.py",
        """\
        def fetch(supabase):
            return (
                supabase.table("quotes")
                .select("id, currency_of_quote")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 1, out + err
    assert "column 'currency_of_quote' not in kvota.quotes" in out


def test_wildcard_select_skipped(tmp_path, basic_types):
    """``.select("*")`` is opaque — exit 0, no violations."""
    py = _write_py(
        tmp_path,
        "wild.py",
        """\
        def fetch(supabase):
            return supabase.table("quotes").select("*").execute()
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "not in" not in out


def test_postgrest_embed_only_top_level_checked(tmp_path, basic_types):
    """Embed sub-selects target child tables — only parent cols are checked.

    The parent select is ``id, child_table!inner(child_col)`` — the lint must
    NOT complain about ``child_col`` against the parent table.
    """
    py = _write_py(
        tmp_path,
        "embed.py",
        """\
        def fetch(supabase):
            return (
                supabase.table("quotes")
                .select("id, currency, quote_items!inner(hs_code, quantity)")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "hs_code" not in out  # NOT flagged against quotes
    assert "quantity" not in out


def test_fstring_select_warns_when_unresolvable(tmp_path, basic_types):
    """An f-string with a name we can't resolve → exit 0 with WARNING."""
    py = _write_py(
        tmp_path,
        "fstring.py",
        """\
        def fetch(supabase, dynamic_cols):
            return (
                supabase.table("quotes")
                .select(f"{dynamic_cols}")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "WARNING" in err
    assert "static check skipped" in err


def test_unknown_table_warns(tmp_path, basic_types):
    """Table not found in schema → exit 0 with WARNING, no violations."""
    py = _write_py(
        tmp_path,
        "unknown.py",
        """\
        def fetch(supabase):
            return supabase.table("non_existent_table").select("foo").execute()
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "table 'non_existent_table' not found" in err


def test_unknown_chain_shape_warns(tmp_path, basic_types):
    """``.select()`` without a ``.table()`` in chain → WARNING, exit 0."""
    py = _write_py(
        tmp_path,
        "no_table.py",
        """\
        def fetch():
            # No supabase chain — ``.select()`` on an arbitrary object.
            return some_other_lib.select("foo, bar")
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "could not resolve .table()/.from_()" in err


def test_resolves_module_constant(tmp_path, basic_types):
    """A module-level tuple of column names referenced via ``", ".join`` is
    resolved statically and validated."""
    py = _write_py(
        tmp_path,
        "constant.py",
        """\
        _FIELDS = ("id", "currency", "hs_code")  # hs_code is wrong table

        def fetch(supabase):
            return (
                supabase.table("quotes")
                .select(",".join(_FIELDS))
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 1, out + err
    assert "column 'hs_code' not in kvota.quotes" in out


def test_resolves_fstring_with_local_join(tmp_path, basic_types):
    """f-string mixing a join() result with literal text — both halves resolved
    and validated. Also exercises the ``Starred`` unpacking path used in
    ``api/customs.py:434``."""
    py = _write_py(
        tmp_path,
        "fstring_resolved.py",
        """\
        _AUTOFILL = ("hs_code", "missing_field")

        def fetch(supabase):
            select_cols = ", ".join(("id", *_AUTOFILL))
            return (
                supabase.table("quote_items")
                .select(f"{select_cols}, quotes!inner(organization_id)")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 1, out + err
    assert "column 'missing_field' not in kvota.quote_items" in out
    # ``hs_code`` is valid on quote_items; should NOT be flagged.
    assert "hs_code" not in out


def test_aliased_embed_handled(tmp_path, basic_types):
    """PostgREST aliased embed ``alias:table(col)`` → embed stripped, alias
    not mistaken for a parent column."""
    py = _write_py(
        tmp_path,
        "alias.py",
        """\
        def fetch(supabase):
            return (
                supabase.table("quotes")
                .select("id, customer:quote_items(hs_code)")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 0, out + err
    assert "not in" not in out


def test_reports_summary_count(tmp_path, basic_types):
    """The summary line at the end shows total violation + file counts."""
    py = _write_py(
        tmp_path,
        "twobad.py",
        """\
        def fetch(supabase):
            return (
                supabase.table("quotes")
                .select("nope_a, nope_b, currency")
                .execute()
            )
        """,
    )
    code, out, err = _run(basic_types, py)
    assert code == 1
    assert "Found 2 schema-drift violations across 1 files." in out
