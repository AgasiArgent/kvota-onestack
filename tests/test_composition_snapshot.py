"""
Track A2 — composition_service snapshot regression test.

Guards the DB→items mapping performed by
``services.composition_service.get_composed_items()``. Track A1 (the
golden-master test) does NOT exercise this path — A1 feeds the calculation
engine through its own .xlsm-derived shim. A2 closes that gap by snapshotting
the *real* output of ``get_composed_items()`` for two fixture quotes and
asserting it stays byte-stable against a committed JSON fixture.

A regression in the composition layer — a renamed field, a dropped key, a
changed merge/split rule, a coverage-join bug — flips this test red.

Design: docs/plans/2026-05-18-calc-engine-verification-design.md §6 (A2).

DB requirement
--------------
``get_composed_items()`` reads ``kvota.quote_items`` and
``kvota.invoice_item_coverage`` through the Supabase REST client. The test
needs a reachable DB. When the DB is unreachable (e.g. CI without Supabase
credentials), the whole module is skipped via ``pytest.mark.skipif`` so CI
does not hard-fail. The committed fixture is recorded while the DB IS
reachable; refresh it by running this module's ``_record_snapshot`` helper.

The Supabase client used here is NOT built via
``services.database.get_supabase()``: ``tests/conftest.py`` overwrites
``SUPABASE_URL`` in ``os.environ`` with a dummy host for the offline
unit-test suite, so a client built from the live ``os.environ`` would
connect to a fake host. Credentials are instead resolved by
``_make_supabase()`` in two tiers (see its docstring): the repo-root
``.env`` file first (the local-dev path), then the REAL ``SUPABASE_URL``
that conftest stashed into ``conftest._REAL_SUPABASE_URL`` before
clobbering it (the CI path — GitHub Actions injects the credentials as
env vars from secrets and commits no ``.env`` file). When neither tier
yields credentials the DB is treated as unreachable and the module skips.

Determinism
-----------
``get_composed_items()`` returns a list whose order is not contractually
fixed. The snapshot sorts items by (quote_item_id, invoice_item_id,
product_name) before comparing. Every captured field is a stable DB value —
the identity UUIDs (quote_item_id / invoice_item_id / invoice_id) are
persisted row ids, not per-call generated — and the output carries no
timestamps, so no field needs freezing.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.composition_service import get_composed_items  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture quotes — snapshotted by this test
# ---------------------------------------------------------------------------

# Quote IDN -> quote UUID. get_composed_items() takes the UUID form.
#   Q-TEST-P5B-01 — the existing composition_service regression-fixture quote
#                   (seeded in the DB; covers a multi-item composition).
#   Q-202605-0011 — the IDEMITSU golden-corpus quote (see design.md §4).
SNAPSHOT_QUOTES = {
    "Q-TEST-P5B-01": "11111111-1111-1111-1111-111111111111",
    "Q-202605-0011": "470d2daf-ffac-46f1-8895-925d3d22304b",
}

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "composition_snapshot.json",
)


# ---------------------------------------------------------------------------
# Supabase client — resolves real credentials immune to the conftest dummy-URL
# override, so A2 runs both locally (.env file) and in CI (env-var secrets).
# ---------------------------------------------------------------------------

ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".env",
)


def _resolve_supabase_credentials() -> tuple[str | None, str | None]:
    """Resolve the REAL Supabase URL + service-role key, dummy-URL-immune.

    ``tests/conftest.py`` overwrites ``SUPABASE_URL`` in ``os.environ`` with
    a dummy host to protect the offline unit-test suite, so a naive
    ``os.environ["SUPABASE_URL"]`` read here would yield the dummy and make
    A2 connect to a fake host (ERROR instead of run-or-skip). Credentials
    are resolved in two tiers, real value first:

      1. **Repo-root ``.env`` file** — the local-developer path. Read with
         ``dotenv_values`` (NOT ``os.environ``) so the conftest override is
         bypassed entirely. ``.env`` is git-ignored; CI has no such file.
      2. **conftest's stashed real URL** — the CI path. GitHub Actions
         injects ``SUPABASE_URL`` / ``SUPABASE_SERVICE_ROLE_KEY`` as env
         vars from secrets and commits no ``.env`` file. ``conftest.py``
         captures the ORIGINAL ``SUPABASE_URL`` into
         ``conftest._REAL_SUPABASE_URL`` *before* clobbering it; the
         service-role key is never clobbered, so it is read straight from
         ``os.environ``.

    Returns ``(None, None)`` when neither tier yields both values — the
    caller treats that as "DB unreachable" and the module skips. This is
    the genuine local-without-DB case (no ``.env`` file, no real env vars).
    """
    from dotenv import dotenv_values

    env = dotenv_values(ENV_PATH)
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return url, key

    # CI path: .env absent. Recover the real URL conftest stashed before it
    # clobbered os.environ["SUPABASE_URL"]; the service-role key is left
    # untouched by conftest, so os.environ holds the real one.
    try:
        from tests.conftest import _REAL_SUPABASE_URL
    except ImportError:
        _REAL_SUPABASE_URL = None
    real_url = url or _REAL_SUPABASE_URL
    real_key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if real_url and real_key:
        return real_url, real_key

    return None, None


def _make_supabase():
    """Build a kvota-scoped Supabase client against the real DB.

    Credentials come from ``_resolve_supabase_credentials()`` — the
    dummy-URL-immune resolver (``.env`` file → conftest's stashed real URL
    → none). Mirrors the schema/options used by
    ``services.database.get_supabase`` so ``get_composed_items()`` sees the
    same client it would in production.

    Returns None when credentials are missing or the supabase package is
    unavailable — the caller treats that as "DB unreachable".
    """
    try:
        from supabase import create_client
        from supabase.client import ClientOptions
    except ImportError:
        return None

    url, key = _resolve_supabase_credentials()
    if not url or not key:
        return None

    return create_client(url, key, options=ClientOptions(schema="kvota"))


# ---------------------------------------------------------------------------
# DB-reachability probe — skips the whole module when no DB is available
# ---------------------------------------------------------------------------

def _db_reachable() -> bool:
    """Return True iff the Supabase DB answers a trivial read.

    get_composed_items() goes through the Supabase REST client (kvota
    schema), so the probe is also a Supabase call. Any failure (missing
    credentials, network, RLS) means "not reachable": the module is skipped
    rather than failed — CI without DB credentials must not hard-fail.
    """
    supabase = _make_supabase()
    if supabase is None:
        return False
    try:
        supabase.table("quotes").select("id").limit(1).execute()
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_reachable()

pytestmark = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="Supabase DB unreachable — composition snapshot needs a live DB.",
)


# ---------------------------------------------------------------------------
# Normalisation — make get_composed_items() output comparison-stable
# ---------------------------------------------------------------------------

def _sort_key(item: dict) -> tuple:
    """Stable ordering key for one composed item.

    get_composed_items() does not guarantee list order. Sorting by the
    identity triple (quote_item_id, invoice_item_id, product_name) yields a
    deterministic sequence for the comparison.
    """
    return (
        str(item.get("quote_item_id") or ""),
        str(item.get("invoice_item_id") or ""),
        str(item.get("product_name") or ""),
    )


def _normalise(items: list[dict]) -> list[dict]:
    """Sort composed items into the snapshot's canonical order.

    The output has no volatile fields (no timestamps; the UUIDs are
    persisted row ids), so ordering is the only normalisation needed.
    """
    return sorted(items, key=_sort_key)


def _build_snapshot() -> dict:
    """Call get_composed_items() for every fixture quote and return the
    normalised snapshot structure (the exact shape of the committed JSON)."""
    supabase = _make_supabase()
    snapshot: dict = {}
    for idn, quote_uuid in SNAPSHOT_QUOTES.items():
        items = _normalise(get_composed_items(quote_uuid, supabase))
        snapshot[idn] = {
            "quote_id": quote_uuid,
            "item_count": len(items),
            "items": items,
        }
    return snapshot


def _load_fixture() -> dict:
    """Read the committed snapshot fixture, JSON-round-tripped so its types
    match the live snapshot (also JSON-round-tripped) exactly."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _record_snapshot() -> None:
    """Regenerate tests/fixtures/composition_snapshot.json from the live DB.

    Not a test — the manual fixture-regeneration entrypoint, run via the
    ``__main__`` block at the bottom of this module
    (``python tests/test_composition_snapshot.py``) when the fixture quotes
    change and the snapshot must be re-baselined. Requires a reachable DB.
    """
    snapshot = _build_snapshot()
    with open(FIXTURE_PATH, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2, sort_keys=True,
                  default=str)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fixture_file_exists_and_covers_both_quotes():
    """The committed fixture exists and has an entry for every snapshot quote.

    A missing fixture means the snapshot was never recorded; a missing quote
    entry means the fixture drifted from SNAPSHOT_QUOTES.
    """
    assert os.path.exists(FIXTURE_PATH), (
        f"Snapshot fixture missing: {FIXTURE_PATH}. "
        "Record it with _record_snapshot() while the DB is reachable."
    )
    fixture = _load_fixture()
    assert set(fixture.keys()) == set(SNAPSHOT_QUOTES.keys()), (
        "Fixture quote set drifted from SNAPSHOT_QUOTES: "
        f"fixture={sorted(fixture)} expected={sorted(SNAPSHOT_QUOTES)}"
    )


def test_get_composed_items_matches_committed_snapshot():
    """get_composed_items() output still equals the committed snapshot.

    This is the regression gate: any change to the DB→items mapping
    (composition_service.get_composed_items) — renamed/dropped field, altered
    merge/split behaviour, coverage-join change — makes the live snapshot
    diverge from the fixture and fails here. The JSON round-trip on both
    sides normalises numeric/None types so the equality is exact.
    """
    live = json.loads(json.dumps(_build_snapshot(), default=str))
    expected = _load_fixture()
    assert live == expected, (
        "get_composed_items() output diverged from the committed snapshot. "
        "If the change is intentional, re-record with _record_snapshot()."
    )


@pytest.mark.parametrize("idn", sorted(SNAPSHOT_QUOTES))
def test_per_quote_item_count_and_keys_stable(idn: str):
    """Per-quote guard: item count and the per-item key set are unchanged.

    A focused check that pinpoints which quote regressed and whether the
    break is a count change (composition shape) or a schema change (item
    keys) — clearer than the all-or-nothing equality above.
    """
    expected = _load_fixture()[idn]
    live_items = _normalise(
        get_composed_items(SNAPSHOT_QUOTES[idn], _make_supabase())
    )

    assert len(live_items) == expected["item_count"], (
        f"{idn}: composed item count changed "
        f"({len(live_items)} != {expected['item_count']})"
    )

    expected_items = expected["items"]
    for live_item, expected_item in zip(live_items, expected_items):
        assert set(live_item.keys()) == set(expected_item.keys()), (
            f"{idn}: composed item key set changed for "
            f"{live_item.get('product_name')!r} — "
            f"added={set(live_item) - set(expected_item)} "
            f"removed={set(expected_item) - set(live_item)}"
        )


# ---------------------------------------------------------------------------
# Manual fixture regeneration — ``python tests/test_composition_snapshot.py``
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not DB_AVAILABLE:
        sys.exit("Supabase DB unreachable — cannot record the snapshot.")
    _record_snapshot()
    print(f"Recorded composition snapshot -> {FIXTURE_PATH}")
