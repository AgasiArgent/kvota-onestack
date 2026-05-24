"""End-to-end PDF rendering test for ``render_proposal_pdf``.

Drives the renderer against the canonical ``default_proposal.json`` fixture
(matches the design's ``DEFAULT_DATA`` byte-for-byte) and asserts:

- Output starts with the PDF magic ``%PDF-``.
- pikepdf can open it (i.e. it is a well-formed PDF, not corrupt bytes).
- The document has exactly two pages.
- An embedded ``Inter`` font shows up in the page font enumeration
  (catches DejaVu-Sans fallback regressions per ADR-8).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pytest

from services.kp_export import (
    KpItem,
    KpPackagingItem,
    KpProposal,
    KpServices,
    render_proposal_pdf,
)

_FIXTURE_DIR = Path(__file__).parent / "__fixtures__"
_DEFAULT_FIXTURE = _FIXTURE_DIR / "default_proposal.json"


def _build_proposal_from_json(payload: dict) -> KpProposal:
    """Mirror of the API handler's ``_build_proposal`` for test isolation."""
    items = tuple(
        KpItem(
            name=str(i.get("name", "")),
            model=str(i.get("model", "")),
            qty=str(i.get("qty", "")),
            price=str(i.get("price", "")),
        )
        for i in payload.get("items", [])
    )
    packaging = tuple(
        KpPackagingItem(
            text=str(p.get("text", "")),
            checked=bool(p.get("checked", False)),
        )
        for p in payload.get("packaging", [])
    )
    svc_in = payload.get("services", {}) or {}
    services = KpServices(
        delivery=bool(svc_in.get("delivery")),
        training=bool(svc_in.get("training")),
        supervision=bool(svc_in.get("supervision")),
        warranty=bool(svc_in.get("warranty")),
        commissioning=bool(svc_in.get("commissioning")),
        service=bool(svc_in.get("service")),
    )

    def _s(key: str) -> str:
        return str(payload.get(key, "") or "")

    return KpProposal(
        subtitle=_s("subtitle"),
        supplier=_s("supplier"),
        manager=_s("manager"),
        phone=_s("phone"),
        email=_s("email"),
        address=_s("address"),
        basis=_s("basis"),
        payment=_s("payment"),
        date=_s("date"),
        lead=_s("lead"),
        amount=_s("amount"),
        price_includes=_s("price_includes"),
        items=items,
        notes=_s("notes"),
        specs=tuple(str(s) for s in payload.get("specs", [])),
        packaging=packaging,
        conditions=tuple(str(c) for c in payload.get("conditions", [])),
        services=services,
        notes2=_s("notes2"),
        contact_phone=_s("contact_phone"),
        contact_email=_s("contact_email"),
        contact_site=_s("contact_site"),
        contact_address=_s("contact_address"),
        foot_phone=_s("foot_phone"),
        foot_site=_s("foot_site"),
        foot_email=_s("foot_email"),
    )


@pytest.fixture(scope="module")
def default_proposal() -> KpProposal:
    payload = json.loads(_DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    return _build_proposal_from_json(payload)


@pytest.fixture(scope="module")
def rendered_pdf(default_proposal: KpProposal) -> bytes:
    """Render once per module — Chromium launch is the slow path (~1-2s)."""
    return render_proposal_pdf(default_proposal)


@pytest.mark.integration
class TestRenderedPdf:
    def test_returns_bytes(self, rendered_pdf: bytes) -> None:
        assert isinstance(rendered_pdf, bytes)
        assert len(rendered_pdf) > 1000  # arbitrary sanity floor

    def test_starts_with_pdf_magic(self, rendered_pdf: bytes) -> None:
        assert rendered_pdf.startswith(b"%PDF-")

    def test_pikepdf_can_open(self, rendered_pdf: bytes) -> None:
        with pikepdf.Pdf.open(io.BytesIO(rendered_pdf)) as pdf:
            assert pdf is not None

    def test_has_exactly_two_pages(self, rendered_pdf: bytes) -> None:
        with pikepdf.Pdf.open(io.BytesIO(rendered_pdf)) as pdf:
            assert len(pdf.pages) == 2

    def test_inter_font_embedded(self, rendered_pdf: bytes) -> None:
        """Walk every page's /Font resource dictionary and assert at least
        one font name contains ``Inter`` — i.e. Chromium embedded the
        bundled font instead of falling back to a system font (ADR-8).
        """
        with pikepdf.Pdf.open(io.BytesIO(rendered_pdf)) as pdf:
            found_inter = False
            for page in pdf.pages:
                resources = page.get("/Resources", {})
                fonts = resources.get("/Font", {}) if resources else {}
                if not fonts:
                    continue
                for _key, font_obj in fonts.items():
                    base_font = str(font_obj.get("/BaseFont", ""))
                    if "Inter" in base_font:
                        found_inter = True
                        break
                if found_inter:
                    break
            assert found_inter, (
                "No Inter font embedded; Chromium likely fell back to a "
                "system font — Cyrillic rendering will silently break."
            )
