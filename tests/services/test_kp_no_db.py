"""Static guard: the KP renderer must never touch the database.

REQ-20.1, REQ-20.2, REQ-20.5, REQ-20.6 state explicitly that the KP Builder
system does NOT persist proposals, NOT connect to quotes/specifications
registries, NOT email PDFs, and NOT version generated KPs in iteration 1.

This regex-scan over the four KP modules is the executable enforcement of
that boundary: if anyone on a future iteration accidentally adds a
``supabase.from('kp_proposals').insert(...)`` or a `from services.database
import supabase`, this test fails and the merge is blocked.

Scoped narrowly to the four KP files — broader linting belongs in CI tools
(ruff, eslint), not here.
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_KP_FILES = (
    _REPO_ROOT / "services" / "kp_export.py",
    _REPO_ROOT / "services" / "kp_branding.py",
    _REPO_ROOT / "api" / "kp.py",
    _REPO_ROOT / "api" / "routers" / "kp.py",
)

# Patterns that would indicate the KP track is reaching into the DB layer.
# ``\b`` boundaries keep ``insert_html``-style false positives out.
_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bfrom\s+services\.database\b", "imports the Supabase client"),
    (r"\bimport\s+services\.database\b", "imports the Supabase client"),
    (r"\bsupabase\s*\.\s*(?:from|table|rpc|auth|storage)\b", "calls the Supabase client"),
    (r"\bINSERT\s+INTO\b", "embeds an INSERT statement"),
    (r"\bUPDATE\s+\w+\s+SET\b", "embeds an UPDATE statement"),
    (r"\bDELETE\s+FROM\b", "embeds a DELETE statement"),
    (r"\bSELECT\s+[\w*,\s]+\s+FROM\b", "embeds a SELECT statement"),
)


@pytest.mark.unit
def test_kp_modules_do_not_reference_database() -> None:
    """REQ-20: no DB writes, no quote-registry coupling from the KP renderer."""
    violations: list[str] = []
    for path in _KP_FILES:
        assert path.exists(), f"Expected KP module missing: {path}"
        source = path.read_text(encoding="utf-8")
        for pattern, description in _FORBIDDEN_PATTERNS:
            if re.search(pattern, source, flags=re.IGNORECASE):
                violations.append(f"{path.relative_to(_REPO_ROOT)} {description} (pattern: {pattern!r})")

    assert not violations, (
        "KP renderer must remain DB-free (REQ-20). Violations:\n  "
        + "\n  ".join(violations)
    )
