"""Tests for services/classifier.py — Phase 2 TN ВЭД classification."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.alta_client import (
    AltaApiError,
    ExpressBatchResponse,
    ExpressPrediction,
)
from services.classifier import (
    Candidate,
    ClassifierError,
    ClassifyInput,
    classify_items,
    log_classification_choice,
)


def _make_alta(predictions, packet_left=500, packet_used=10):
    alta = MagicMock()
    alta.last_packet_left = packet_left
    alta.classify_batch = AsyncMock(
        return_value=ExpressBatchResponse(
            handled=True,
            message="ok",
            predictions=predictions,
            balance=1000.0,
            packet_left=packet_left,
            packet_used=packet_used,
        )
    )
    return alta


def _make_sb_with_codes(code_to_desc):
    """Mock supabase that returns description rows for tnved_codes."""
    sb = MagicMock()
    rows = [{"code": c, "description": d} for c, d in code_to_desc.items()]

    def table_router(name):
        chain = MagicMock()
        if name == "tnved_codes":
            (chain.select.return_value
                  .in_.return_value
                  .execute.return_value) = MagicMock(data=rows)
        elif name == "tnved_classification_log":
            chain.insert.return_value.execute.return_value = MagicMock(data=[])
        return chain

    sb.table.side_effect = table_router
    return sb


@pytest.mark.asyncio
async def test_classify_empty_inputs_raises_bad_request():
    alta = _make_alta([])
    with pytest.raises(ClassifierError) as exc_info:
        await classify_items([], alta_client=alta)
    assert exc_info.value.code == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_classify_packet_floor_blocks_call():
    """Refuses new calls when Alta packet quota is too low (cron budget protection)."""
    alta = _make_alta([], packet_left=10)  # below floor=50
    with pytest.raises(ClassifierError) as exc_info:
        await classify_items(
            [ClassifyInput(name="Шайба")],
            alta_client=alta,
        )
    assert exc_info.value.code == "PACKET_EXHAUSTED"
    alta.classify_batch.assert_not_called()


@pytest.mark.asyncio
async def test_classify_returns_top_k_per_input():
    """Each input gets its own ordered candidate list (highest probability first)."""
    preds = [
        ExpressPrediction(id=1, code="7326909807", code_weight=10, probability=0.85),
        ExpressPrediction(id=1, code="7318159000", code_weight=8, probability=0.45),
        ExpressPrediction(id=2, code="4016939000", code_weight=12, probability=0.75),
    ]
    alta = _make_alta(preds)
    sb = _make_sb_with_codes({"7326909807": "Изделия из черных металлов"})

    with patch("services.classifier.get_supabase", return_value=sb):
        outcome = await classify_items(
            [
                ClassifyInput(name="Шайба М6", quote_item_id="qi-1"),
                ClassifyInput(name="Уплотнительное кольцо", quote_item_id="qi-2"),
            ],
            alta_client=alta,
        )

    assert len(outcome.results) == 2
    r1, r2 = outcome.results
    assert r1.input_idx == 1
    assert r1.quote_item_id == "qi-1"
    assert len(r1.candidates) == 2
    # Sorted by probability descending
    assert r1.candidates[0].code == "7326909807"
    assert r1.candidates[0].probability == 0.85
    # Description enrichment from local cache
    assert r1.candidates[0].description == "Изделия из черных металлов"
    assert r1.candidates[1].description is None
    # Per-input grouping
    assert r2.input_idx == 2
    assert r2.candidates[0].code == "4016939000"


@pytest.mark.asyncio
async def test_classify_no_predictions_marks_error():
    """Input with zero predictions gets error message but doesn't fail batch."""
    alta = _make_alta([
        ExpressPrediction(id=1, code="7326909807", code_weight=10, probability=0.85),
    ])
    sb = _make_sb_with_codes({})
    with patch("services.classifier.get_supabase", return_value=sb):
        outcome = await classify_items(
            [
                ClassifyInput(name="Шайба"),
                ClassifyInput(name="Что-то странное"),
            ],
            alta_client=alta,
        )

    assert len(outcome.results[0].candidates) == 1
    assert outcome.results[1].candidates == []
    assert outcome.results[1].error == "No candidates returned by Alta"


@pytest.mark.asyncio
async def test_classify_alta_error_maps_to_classifier_error():
    alta = MagicMock()
    alta.last_packet_left = 500
    alta.classify_batch = AsyncMock(side_effect=AltaApiError(110, "Auth failed"))

    with pytest.raises(ClassifierError) as exc_info:
        await classify_items(
            [ClassifyInput(name="Шайба")],
            alta_client=alta,
        )
    assert exc_info.value.code == "ALTA_UNAVAILABLE"


@pytest.mark.asyncio
async def test_classify_request_id_stable_for_same_inputs():
    """Same inputs same day → identical request_id (idempotent)."""
    alta = _make_alta([])
    sb = _make_sb_with_codes({})

    inputs = [ClassifyInput(name="Шайба", quote_item_id="qi-1")]
    today = date(2026, 5, 3)

    with patch("services.classifier.get_supabase", return_value=sb):
        out1 = await classify_items(inputs, alta_client=alta, today=today)
        out2 = await classify_items(inputs, alta_client=alta, today=today)

    assert out1.request_id == out2.request_id
    # Different day produces a different id
    out3 = await _run_with_sb(
        classify_items, sb, inputs, alta, date(2026, 5, 4),
    )
    assert out1.request_id != out3.request_id


async def _run_with_sb(fn, sb, inputs, alta, today):
    with patch("services.classifier.get_supabase", return_value=sb):
        return await fn(inputs, alta_client=alta, today=today)


@pytest.mark.asyncio
async def test_classify_brand_concatenated_into_query():
    """Brand and description are appended to name when calling Alta."""
    alta = _make_alta([])
    sb = _make_sb_with_codes({})

    with patch("services.classifier.get_supabase", return_value=sb):
        await classify_items(
            [ClassifyInput(name="Шайба", brand="SuperRotors", description="М6 нерж")],
            alta_client=alta,
        )

    # Verify the name passed into ExpressItem combined all three
    args, _ = alta.classify_batch.call_args
    items = args[0]
    assert items[0].name == "Шайба SuperRotors М6 нерж"


def test_log_classification_choice_swallows_db_errors():
    """Audit-log failures must not block the user save."""
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = ConnectionError(
        "db down"
    )
    with patch("services.classifier.get_supabase", return_value=sb):
        # Should not raise
        log_classification_choice(
            quote_item_id="qi-1",
            chosen_code="7326909807",
            candidates=[Candidate("7326909807", 0.85, 10, None)],
            user_id="user-1",
        )


def test_log_classification_choice_writes_full_payload():
    """Confirms the audit row carries chosen_code + candidate snapshot."""
    sb = MagicMock()
    captured: dict = {}

    def capture_insert(payload):
        captured["payload"] = payload
        execute = MagicMock()
        execute.execute.return_value = MagicMock(data=[])
        return execute

    sb.table.return_value.insert.side_effect = capture_insert
    with patch("services.classifier.get_supabase", return_value=sb):
        log_classification_choice(
            quote_item_id="qi-1",
            chosen_code="7326909807",
            candidates=[
                Candidate("7326909807", 0.85, 10, "metal"),
                Candidate("7318159000", 0.40, 8, None),
            ],
            user_id="user-1",
            input_text="Шайба М6",
        )

    payload = captured["payload"]
    assert payload["quote_item_id"] == "qi-1"
    assert payload["chosen_code"] == "7326909807"
    assert payload["method"] == "express"
    assert payload["input_text"] == "Шайба М6"
    assert payload["user_id"] == "user-1"
    assert len(payload["suggested_codes"]) == 2
    assert payload["suggested_codes"][0]["code"] == "7326909807"
