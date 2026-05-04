"""Tests for services/alta_client.py — REQ-2 customs-phase-1.

Covers MD5 signing, windows-1251 decoding, error code recognition,
polling, packet warnings, credentials hygiene, and DI factory.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services import alta_client as alta_client_module
from services.alta_client import (
    AltaApiError,
    AltaClient,
    Rate,
    _classify_import_payment_type,
    get_alta_client,
    notify_admin,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_singleton() -> None:
    """Reset the module-level singleton between tests."""
    alta_client_module._client_singleton = None
    alta_client_module._last_alert_at.clear()


@pytest.fixture(autouse=True)
def _clean_module_state():
    _reset_singleton()
    yield
    _reset_singleton()


def _make_response(content: bytes, *, charset: str | None = None,
                   status: int = 200,
                   url: str = "https://www2.alta.ru/tnved/xml/") -> httpx.Response:
    headers = {}
    if charset:
        headers["Content-Type"] = f"text/xml; charset={charset}"
    else:
        headers["Content-Type"] = "text/xml"
    request = httpx.Request("GET", url)
    response = httpx.Response(
        status_code=status, content=content, headers=headers, request=request,
    )
    return response


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def test_sign_request_md5_double_hash():
    """Phase 0 fixture: sign_request("REQ-001", "sa67089", "ELpT58hp")."""
    client = AltaClient("sa67089", "ELpT58hp")
    pwd_md5 = hashlib.md5(b"ELpT58hp").hexdigest()
    expected = hashlib.md5(
        f"REQ-001:sa67089:{pwd_md5}".encode("utf-8")
    ).hexdigest()
    assert client._sign("REQ-001") == expected


def test_sign_uses_raw_utf8_not_url_encoded():
    """Cyrillic param → MD5 of raw UTF-8 bytes, NOT URL-encoded."""
    client = AltaClient("user", "pass")
    cyrillic = "Кириллица"
    pwd_md5 = hashlib.md5(b"pass").hexdigest()
    raw_expected = hashlib.md5(
        f"{cyrillic}:user:{pwd_md5}".encode("utf-8")
    ).hexdigest()

    import urllib.parse
    url_encoded = urllib.parse.quote(cyrillic)
    url_encoded_md5 = hashlib.md5(
        f"{url_encoded}:user:{pwd_md5}".encode("utf-8")
    ).hexdigest()

    assert client._sign(cyrillic) == raw_expected
    assert raw_expected != url_encoded_md5  # gotcha #1


def test_sign_handles_unicode_password():
    client = AltaClient("user", "пароль123")
    pwd_md5 = hashlib.md5("пароль123".encode("utf-8")).hexdigest()
    expected = hashlib.md5(
        f"REQ-1:user:{pwd_md5}".encode("utf-8")
    ).hexdigest()
    assert client._sign("REQ-1") == expected


# ---------------------------------------------------------------------------
# Credentials hygiene (REQ-2 AC#11)
# ---------------------------------------------------------------------------


def test_credentials_not_in_repr():
    client = AltaClient("sa67089", "ELpT58hp")
    rep = repr(client)
    assert "sa67089" not in rep
    assert "ELpT58hp" not in rep


def test_password_not_stored_plaintext():
    client = AltaClient("user", "supersecret123")
    state = vars(client)
    for value in state.values():
        if isinstance(value, str):
            assert value != "supersecret123"
    # And specifically: no attribute literally equals plaintext password
    assert "supersecret123" not in str(state)


def test_credentials_not_logged_on_error(caplog):
    """Errors raised from the client must not contain login or password."""
    import logging

    client = AltaClient("sa67089", "ELpT58hp")
    caplog.set_level(logging.DEBUG)
    try:
        client._parse_response(
            "<root><handled>false</handled><message>100</message></root>"
        )
    except AltaApiError as exc:
        assert "sa67089" not in str(exc)
        assert "ELpT58hp" not in str(exc)
    for record in caplog.records:
        assert "ELpT58hp" not in record.getMessage()


# ---------------------------------------------------------------------------
# XML decoding (REQ-2 AC#4, gotcha #2)
# ---------------------------------------------------------------------------


def test_decode_xml_windows1251():
    client = AltaClient("u", "p")
    xml_bytes = (
        '<?xml version="1.0" encoding="windows-1251"?>'
        "<root><message>Кириллица</message></root>"
    ).encode("windows-1251")
    response = _make_response(xml_bytes)  # no charset header
    decoded = client._decode_xml(response)
    assert "Кириллица" in decoded


def test_decode_xml_utf8():
    client = AltaClient("u", "p")
    xml_bytes = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<root><message>привет</message></root>"
    ).encode("utf-8")
    response = _make_response(xml_bytes, charset="utf-8")
    decoded = client._decode_xml(response)
    assert "привет" in decoded


def test_decode_xml_charset_header_takes_precedence():
    """When charset header and XML declaration disagree, charset header wins."""
    client = AltaClient("u", "p")
    # Encode bytes as utf-8 but lie in the XML declaration about windows-1251
    xml_bytes = (
        '<?xml version="1.0" encoding="windows-1251"?>'
        "<root><message>привет</message></root>"
    ).encode("utf-8")
    # Charset header says utf-8 — should win
    response = _make_response(xml_bytes, charset="utf-8")
    decoded = client._decode_xml(response)
    assert "привет" in decoded


# ---------------------------------------------------------------------------
# Error code recognition (REQ-2 AC#5, AC#6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [100, 110, 120, 140, 201])
def test_parse_response_documented_error_codes(code):
    client = AltaClient("u", "p")
    xml = f"<root><handled>false</handled><message>{code}</message></root>"
    with pytest.raises(AltaApiError) as exc_info:
        client._parse_response(xml)
    assert exc_info.value.code == code


def test_parse_response_undocumented_code():
    client = AltaClient("u", "p")
    xml = "<root><handled>false</handled><message>999</message></root>"
    with pytest.raises(AltaApiError) as exc_info:
        client._parse_response(xml)
    assert exc_info.value.code == 999
    assert "undocumented" in str(exc_info.value).lower()


def test_parse_response_handled_true_returns_result():
    client = AltaClient("u", "p")
    xml = (
        "<root><handled>true</handled><message>ok</message>"
        "<response><item><id>1</id><code>1234567890</code>"
        "<codeWeight>10</codeWeight><probability>0.85</probability></item></response>"
        "</root>"
    )
    result = client._parse_response(xml)
    assert result["handled"] is True


# ---------------------------------------------------------------------------
# classify_batch — polling and group_hint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_batch_polling_returns_after_handled_true():
    client = AltaClient("u", "p")
    pending_xml = (
        "<root><handled>false</handled><message></message></root>"
    ).encode("utf-8")
    success_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<root><handled>true</handled><message>ok</message>"
        "<response><item><id>1</id><code>1234567890</code>"
        "<codeWeight>10</codeWeight><probability>0.85</probability></item></response>"
        "<packet><item><left_count>500</left_count><used_count>10</used_count></item></packet>"
        "</root>"
    ).encode("utf-8")

    call_count = {"n": 0}

    async def mock_post(url, content=None, headers=None):
        call_count["n"] += 1
        if call_count["n"] < 4:
            return _make_response(pending_xml, charset="utf-8")
        return _make_response(success_xml, charset="utf-8")

    mock_async_client = MagicMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    mock_async_client.post = AsyncMock(side_effect=mock_post)

    with patch.object(alta_client_module.httpx, "AsyncClient",
                      return_value=mock_async_client), \
         patch.object(alta_client_module.asyncio, "sleep",
                      new=AsyncMock()):
        result = await client.classify_batch(
            items=[{"id": 1, "name": "test product"}],
            request_id="REQ-TEST-001",
        )

    assert call_count["n"] == 4
    assert result.handled is True


@pytest.mark.asyncio
async def test_classify_batch_polling_timeout_surfaces_last_message():
    client = AltaClient("u", "p")
    pending_xml = (
        "<root><handled>false</handled>"
        "<message>queue-pending-token-XYZ</message></root>"
    ).encode("utf-8")

    async def mock_post(url, content=None, headers=None):
        return _make_response(pending_xml, charset="utf-8")

    mock_async_client = MagicMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    mock_async_client.post = AsyncMock(side_effect=mock_post)

    with patch.object(alta_client_module.httpx, "AsyncClient",
                      return_value=mock_async_client), \
         patch.object(alta_client_module.asyncio, "sleep",
                      new=AsyncMock()):
        with pytest.raises(RuntimeError) as exc_info:
            await client.classify_batch(
                items=[{"id": 1, "name": "test"}],
                request_id="REQ-TIMEOUT-001",
            )

    msg = str(exc_info.value)
    assert "REQ-TIMEOUT-001" in msg
    assert "queue-pending-token-XYZ" in msg


@pytest.mark.asyncio
async def test_classify_batch_drops_group_hint(caplog):
    """REQ-2 AC#9: group_hint accepted but never sent in XML."""
    import logging

    client = AltaClient("u", "p")
    success_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<root><handled>true</handled><message>ok</message>"
        "<response><item><id>1</id><code>1234567890</code>"
        "<codeWeight>10</codeWeight><probability>0.9</probability></item></response>"
        "</root>"
    ).encode("utf-8")

    captured_bodies = []

    async def mock_post(url, content=None, headers=None):
        captured_bodies.append(content)
        return _make_response(success_xml, charset="utf-8")

    mock_async_client = MagicMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    mock_async_client.post = AsyncMock(side_effect=mock_post)

    caplog.set_level(logging.WARNING)
    with patch.object(alta_client_module.httpx, "AsyncClient",
                      return_value=mock_async_client), \
         patch.object(alta_client_module.asyncio, "sleep",
                      new=AsyncMock()):
        await client.classify_batch(
            items=[{"id": 1, "name": "tester"}],
            request_id="REQ-GROUP-001",
            group_hint="some_group_value",
        )

    # Verify group= attribute is not in the outgoing payload
    body_text = "".join(captured_bodies)
    assert 'group="some_group_value"' not in body_text
    assert "group=" not in body_text or "groupid" in body_text.lower() or "<group>" not in body_text
    # Warning was logged
    warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("group_hint" in r.getMessage().lower() or "group" in r.getMessage().lower()
               for r in warning_logs)


# ---------------------------------------------------------------------------
# Packet left warnings (REQ-2 AC#10, Q2)
# ---------------------------------------------------------------------------


def test_packet_left_above_100_no_warning():
    client = AltaClient("u", "p")
    with patch.object(alta_client_module, "notify_admin",
                      new_callable=AsyncMock) as mock_alert:
        client._log_packet_left(500)
    mock_alert.assert_not_called()


def test_packet_left_warning_below_100_alerts_telegram():
    client = AltaClient("u", "p")
    with patch.object(alta_client_module, "notify_admin",
                      new_callable=AsyncMock) as mock_alert:
        client._log_packet_left(50)
    mock_alert.assert_called_once()
    call_args = mock_alert.call_args
    sent_text = (call_args.args[0] if call_args.args
                 else call_args.kwargs.get("message", ""))
    assert "50" in str(sent_text) or "100" in str(sent_text)


def test_packet_left_warning_throttled_1_per_hour():
    client = AltaClient("u", "p")
    with patch.object(alta_client_module, "notify_admin",
                      new_callable=AsyncMock) as mock_alert:
        client._log_packet_left(50)
        client._log_packet_left(40)  # Within an hour — should be suppressed
    assert mock_alert.call_count == 1


def test_packet_left_warning_fires_again_after_one_hour():
    client = AltaClient("u", "p")
    with patch.object(alta_client_module, "notify_admin",
                      new_callable=AsyncMock) as mock_alert:
        client._log_packet_left(50)
        # Move the throttle key back >1 hour to simulate elapsed time
        for key in list(alta_client_module._last_alert_at):
            alta_client_module._last_alert_at[key] = (
                datetime.now() - timedelta(hours=2)
            )
        client._log_packet_left(40)
    assert mock_alert.call_count == 2


# ---------------------------------------------------------------------------
# DI factory (REQ-2 AC#11, Q6)
# ---------------------------------------------------------------------------


def test_get_alta_client_lazy_singleton(monkeypatch):
    monkeypatch.setenv("ALTA_LOGIN", "factory_user")
    monkeypatch.setenv("ALTA_PASSWORD", "factory_pass")
    a = get_alta_client()
    b = get_alta_client()
    assert a is b


def test_get_alta_client_reads_env(monkeypatch):
    monkeypatch.setenv("ALTA_LOGIN", "envuser")
    monkeypatch.setenv("ALTA_PASSWORD", "envpass")
    client = get_alta_client()
    assert client._login == "envuser"
    expected_md5 = hashlib.md5(b"envpass").hexdigest()
    assert client._password_md5 == expected_md5


def test_app_dependency_overrides(monkeypatch):
    """Demonstrate that `get_alta_client` is overrideable for tests."""
    from fastapi import FastAPI, Depends

    monkeypatch.setenv("ALTA_LOGIN", "real")
    monkeypatch.setenv("ALTA_PASSWORD", "real")

    class MockAltaClient:
        async def get_rates(self, *args, **kwargs):
            return []

    app = FastAPI()

    @app.get("/_test")
    async def _endpoint(client=Depends(get_alta_client)):
        return {"type": type(client).__name__}

    mock = MockAltaClient()
    app.dependency_overrides[get_alta_client] = lambda: mock

    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        resp = client.get("/_test")
        assert resp.status_code == 200
        assert resp.json()["type"] == "MockAltaClient"


# ---------------------------------------------------------------------------
# HTTP timeout & retries (REQ-2 AC#12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_timeout_30s():
    """AsyncClient is constructed with timeout=30.0."""
    client = AltaClient("u", "p")
    success_xml = (
        '<?xml version="1.0" encoding="windows-1251"?>'
        "<root><handled>true</handled><message>ok</message>"
        "<rates></rates></root>"
    ).encode("windows-1251")

    async def mock_get(*args, **kwargs):
        return _make_response(success_xml, charset="windows-1251")

    mock_async_client = MagicMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    mock_async_client.get = AsyncMock(side_effect=mock_get)
    mock_async_client.post = AsyncMock(side_effect=mock_get)

    captured_kwargs = {}

    def _capture_constructor(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_async_client

    with patch.object(alta_client_module.httpx, "AsyncClient",
                      side_effect=_capture_constructor):
        try:
            await client.get_rates("1234567890", 156, date(2026, 5, 1))
        except Exception:
            pass  # we only care about the constructor kwargs

    assert captured_kwargs.get("timeout") == 30.0


@pytest.mark.asyncio
async def test_retries_on_network_error():
    """First call: ConnectTimeout; second: success. Sleep ~1s between."""
    client = AltaClient("u", "p")
    success_xml = (
        '<?xml version="1.0" encoding="windows-1251"?>'
        "<root><handled>true</handled><message>ok</message>"
        "<rates></rates></root>"
    ).encode("windows-1251")

    call_count = {"n": 0}

    async def mock_get(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectTimeout("timeout")
        return _make_response(success_xml, charset="windows-1251")

    mock_async_client = MagicMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    mock_async_client.get = AsyncMock(side_effect=mock_get)

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    with patch.object(alta_client_module.httpx, "AsyncClient",
                      return_value=mock_async_client), \
         patch.object(alta_client_module.asyncio, "sleep", new=fake_sleep):
        await client.get_rates("1234567890", 156, date(2026, 5, 1))

    assert call_count["n"] == 2
    # Backoff: at least one 1s sleep between attempts
    assert any(s >= 1 for s in sleep_calls)


@pytest.mark.asyncio
async def test_no_retry_on_alta_api_error():
    """AltaApiError must NOT trigger retry."""
    client = AltaClient("u", "p")
    error_xml = (
        '<?xml version="1.0" encoding="windows-1251"?>'
        "<root><handled>false</handled><message>100</message></root>"
    ).encode("windows-1251")

    call_count = {"n": 0}

    async def mock_get(*args, **kwargs):
        call_count["n"] += 1
        return _make_response(error_xml, charset="windows-1251")

    mock_async_client = MagicMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=None)
    mock_async_client.get = AsyncMock(side_effect=mock_get)

    with patch.object(alta_client_module.httpx, "AsyncClient",
                      return_value=mock_async_client), \
         patch.object(alta_client_module.asyncio, "sleep", new=AsyncMock()):
        with pytest.raises(AltaApiError) as exc_info:
            await client.get_rates("1234567890", 156, date(2026, 5, 1))

    assert exc_info.value.code == 100
    assert call_count["n"] == 1  # No retry


# ---------------------------------------------------------------------------
# Rate dataclass invariants (TD-1, TD-3 review fixes)
# ---------------------------------------------------------------------------


def _valid_rate_kwargs(**overrides: object) -> dict:
    """Minimal-valid Rate kwargs that satisfy all __post_init__ checks."""
    base = {
        "tnved_code": "1234567890",
        "payment_type": "IMP",
        "country_or_areal": "C:643",
        "valid_from": date(2025, 1, 1),
        "value_1_number": 10.0,
        "value_1_unit": "percent",
    }
    base.update(overrides)
    return base


class TestRateInvariants:
    """__post_init__ enforces schema CHECK constraints from migration 298."""

    def test_valid_rate_constructs(self):
        Rate(**_valid_rate_kwargs())  # Must not raise

    def test_country_or_areal_none_allowed(self):
        Rate(**_valid_rate_kwargs(country_or_areal=None))

    def test_country_or_areal_country_format(self):
        Rate(**_valid_rate_kwargs(country_or_areal="C:643"))
        Rate(**_valid_rate_kwargs(country_or_areal="C:156"))

    def test_country_or_areal_areal_format(self):
        Rate(**_valid_rate_kwargs(country_or_areal="A:EAEU"))
        Rate(**_valid_rate_kwargs(country_or_areal="A:CIS"))

    @pytest.mark.parametrize("bad", [
        "643",         # missing prefix
        "C:abc",       # non-digit country
        "C:",          # empty digits
        "country-643", # arbitrary string
        "A:",          # empty areal token
        "X:643",       # wrong prefix
    ])
    def test_country_or_areal_rejects_bad_format(self, bad):
        with pytest.raises(ValueError, match="country_or_areal"):
            Rate(**_valid_rate_kwargs(country_or_areal=bad))

    def test_sign_1_required_when_value_2_set(self):
        with pytest.raises(ValueError, match="sign_1"):
            Rate(**_valid_rate_kwargs(
                value_2_number=5.0,
                value_2_unit="166",
                sign_1=None,
            ))

    @pytest.mark.parametrize("bad_sign", ["*", "-", "<", "x"])
    def test_sign_1_rejects_invalid_token(self, bad_sign):
        with pytest.raises(ValueError, match="sign_1"):
            Rate(**_valid_rate_kwargs(
                value_2_number=5.0,
                value_2_unit="166",
                sign_1=bad_sign,
            ))

    @pytest.mark.parametrize("good_sign", ["+", ">"])
    def test_sign_1_accepts_valid_tokens(self, good_sign):
        Rate(**_valid_rate_kwargs(
            value_2_number=5.0,
            value_2_unit="166",
            sign_1=good_sign,
        ))

    def test_sign_2_required_when_value_3_set(self):
        with pytest.raises(ValueError, match="sign_2"):
            Rate(**_valid_rate_kwargs(
                value_2_number=5.0,
                value_2_unit="166",
                sign_1="+",
                value_3_number=2.0,
                value_3_unit="166",
                sign_2=None,
            ))

    def test_percent_unit_with_currency_rejected(self):
        with pytest.raises(ValueError, match="value_1_currency"):
            Rate(**_valid_rate_kwargs(
                value_1_unit="percent",
                value_1_currency="USD",
            ))

    def test_percent_unit_no_currency_accepted(self):
        Rate(**_valid_rate_kwargs(
            value_1_unit="percent",
            value_1_currency=None,
        ))

    def test_okei_unit_with_currency_accepted(self):
        # value_1_unit='166' (kg) with EUR currency = 5 EUR/kg — legal
        Rate(**_valid_rate_kwargs(
            value_1_unit="166",
            value_1_currency="EUR",
        ))

    def test_percent_in_slot_2_with_currency_rejected(self):
        with pytest.raises(ValueError, match="value_2_currency"):
            Rate(**_valid_rate_kwargs(
                value_2_number=5.0,
                value_2_unit="percent",
                value_2_currency="USD",
                sign_1="+",
            ))

    def test_source_rejects_unknown_string(self):
        with pytest.raises(ValueError, match="source"):
            Rate(**_valid_rate_kwargs(source="bogus-source"))

    @pytest.mark.parametrize(
        "good_source", ["alta-live", "alta-revalidate", "manual"]
    )
    def test_source_accepts_known_values(self, good_source):
        Rate(**_valid_rate_kwargs(source=good_source))

    def test_source_none_accepted(self):
        Rate(**_valid_rate_kwargs(source=None))


# ---------------------------------------------------------------------------
# notify_admin Sentry fallback (M10 review fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_admin_falls_back_to_sentry_when_telegram_unavailable(
    monkeypatch,
):
    """When Telegram raises, the alert should still reach Sentry."""
    # Force the Telegram path to fail
    fake_service = MagicMock()
    fake_service.get_bot.side_effect = RuntimeError("telegram down")

    fake_sentry = MagicMock()
    captured: list[dict] = []

    def _capture_message(msg, level=None):
        captured.append({"msg": msg, "level": level})

    fake_sentry.capture_message = _capture_message

    import sys
    monkeypatch.setitem(sys.modules, "services.telegram_service", fake_service)
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)

    await notify_admin("test alert payload")

    assert len(captured) == 1
    assert "test alert payload" in captured[0]["msg"]
    assert captured[0]["level"] == "warning"


@pytest.mark.asyncio
async def test_notify_admin_no_chat_id_falls_back_to_sentry(monkeypatch):
    """When ADMIN_TELEGRAM_CHAT_ID is unset, Sentry still gets the alert."""
    fake_bot = MagicMock()
    fake_service = MagicMock()
    fake_service.get_bot.return_value = fake_bot

    fake_sentry = MagicMock()
    captured: list[str] = []
    fake_sentry.capture_message = lambda msg, level=None: captured.append(msg)

    import sys
    monkeypatch.setitem(sys.modules, "services.telegram_service", fake_service)
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID", raising=False)

    await notify_admin("alert without chat id")

    assert any("alert without chat id" in m for m in captured)


@pytest.mark.asyncio
async def test_notify_admin_no_sentry_module_does_not_raise(monkeypatch):
    """When sentry_sdk is not installed, notify_admin must still complete."""
    fake_service = MagicMock()
    fake_service.get_bot.side_effect = RuntimeError("telegram down")

    import sys
    monkeypatch.setitem(sys.modules, "services.telegram_service", fake_service)
    # Force the import to fail by setting sentry_sdk to None and using a
    # finder that raises ImportError for that name.
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)

    # ImportError of `import sentry_sdk` must not propagate
    await notify_admin("alert without sentry")


# ---------------------------------------------------------------------------
# Migration 301 — _extract_rates variant metadata capture
# ---------------------------------------------------------------------------


def _multivariant_taksa_xml() -> bytes:
    """Trimmed real Alta response (HS=7326909807 × 156, probed 2026-05-03).

    Covers two IMP variants (one льготная "Беспошлинно", one "прочее" 7.5%)
    and three NDS variants (0% льготная медтехника, 10% медизделия, 22%
    стандарт). The parser must produce one Rate per variant with category /
    description / legal-doc populated and is_default set on the catch-all rows.
    """
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<GoodInfo><Code>7326909807</Code>'
        '<Importlist>'
        '<Import>'
        '<Value>Беспошлинно</Value>'
        '<ValueDetail><ValueCount>0</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>- зажимное устройство</Prim>'
        '<Order>09b00130</Order>'
        '<OrderCond>Льгота по уплате ввозных таможенных пошлин предоставляется</OrderCond>'
        '<Link>https://www.alta.ru/tamdoc/09b00130/</Link>'
        '</Import>'
        '<Import>'
        '<Value>7.5%</Value>'
        '<ValueDetail><ValueCount>7.5</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>- прочее</Prim>'
        '<Order>09b00130</Order>'
        '<OrderCond>НЕТ льготы</OrderCond>'
        '<Link>https://www.alta.ru/tamdoc/09b00130/</Link>'
        '</Import>'
        '</Importlist>'
        '<Exciselist/>'
        '<VATlist>'
        '<VAT>'
        '<Value>0%</Value>'
        '<ValueDetail><ValueCount>0</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Directory><RuName>Технические средства для инвалидов</RuName>'
        '<EnName>nds_inv</EnName></Directory>'
        '<MainCondition>Изделия прочие из черных металлов (НДС):</MainCondition>'
        '<Condition>- 29. Специальные средства для самообслуживания</Condition>'
        '<Document>Постановление 1042 от 30.09.2015 Правительства РФ</Document>'
        '<Link>https://www.alta.ru/tamdoc/15ps1042/</Link>'
        '</VAT>'
        '<VAT>'
        '<Value>10%</Value>'
        '<ValueDetail><ValueCount>10</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Directory><RuName>Жизненно необходимая медтехника</RuName>'
        '<EnName>nds_lecr</EnName></Directory>'
        '<MainCondition>Изделия прочие из черных металлов (НДС Медизделия):</MainCondition>'
        '<Condition>- Медизделия (Регистрационное удостоверение)</Condition>'
        '<Document>Постановление 688 от 15.09.2008 Правительства РФ</Document>'
        '<Link>https://www.alta.ru/tamdoc/08ps0688/</Link>'
        '</VAT>'
        '<VAT>'
        '<Value>22%</Value>'
        '<ValueDetail><ValueCount>22</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Directory><RuName>Жизненно необходимая медтехника</RuName>'
        '<EnName>nds_lecr</EnName></Directory>'
        '<MainCondition>Изделия прочие из черных металлов (НДС Медизделия):</MainCondition>'
        '<Condition>- Прочие</Condition>'
        '<Document>Постановление 688 от 15.09.2008 Правительства РФ</Document>'
        '<Link>https://www.alta.ru/tamdoc/08ps0688/</Link>'
        '</VAT>'
        '</VATlist>'
        '</GoodInfo>'
    )
    return xml.encode("utf-8")


@pytest.mark.asyncio
async def test_get_rates_captures_imp_variant_metadata():
    """IMP variant should preserve <Prim>/<Order>/<OrderCond>/<Link>.

    Default-variant detection picks the "прочее" row (НЕТ льготы) — that's
    the rate that applies when no льгота classification matches. The
    "зажимное устройство" льготная must NOT be marked default.
    """
    client = AltaClient(login="testlogin", password="testpw")

    fake_resp = _make_response(_multivariant_taksa_xml(), charset="utf-8")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = fake_resp
        mock_client_cls.return_value = mock_client

        rates = await client.get_rates(
            "7326909807", 156, date(2026, 5, 3),
        )

    imp_rates = [r for r in rates if r.payment_type == "IMP"]
    assert len(imp_rates) == 2

    by_desc = {r.description: r for r in imp_rates}
    assert "- зажимное устройство" in by_desc
    assert "- прочее" in by_desc

    lgota = by_desc["- зажимное устройство"]
    assert lgota.value_1_number == 0
    assert lgota.is_default is False  # льготная — not default
    assert lgota.condition_text and "предоставляется" in lgota.condition_text
    assert lgota.order_ref == "09b00130"
    # IMP fallback: category_code = order_ref when no <Directory>
    assert lgota.category_code == "09b00130"
    assert lgota.legal_link == "https://www.alta.ru/tamdoc/09b00130/"
    assert lgota.legal_document is None  # IMP responses use Order, not Document

    default = by_desc["- прочее"]
    assert default.value_1_number == 7.5
    assert default.is_default is True   # "прочее" → default
    assert default.condition_text == "НЕТ льготы"


@pytest.mark.asyncio
async def test_get_rates_captures_nds_directory_metadata():
    """NDS variant should preserve <Directory>/<MainCondition>/<Condition>/
    <Document>/<Link>. Default-variant detection picks "- Прочие".
    """
    client = AltaClient(login="testlogin", password="testpw")

    fake_resp = _make_response(_multivariant_taksa_xml(), charset="utf-8")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = fake_resp
        mock_client_cls.return_value = mock_client

        rates = await client.get_rates(
            "7326909807", 156, date(2026, 5, 3),
        )

    nds_rates = [r for r in rates if r.payment_type == "NDS"]
    assert len(nds_rates) == 3

    by_value = {r.value_1_number: r for r in nds_rates}
    nds_zero = by_value[0]
    assert nds_zero.category_code == "nds_inv"
    assert nds_zero.category_ru == "Технические средства для инвалидов"
    assert nds_zero.is_default is False
    assert (
        nds_zero.legal_document
        == "Постановление 1042 от 30.09.2015 Правительства РФ"
    )
    assert nds_zero.legal_link == "https://www.alta.ru/tamdoc/15ps1042/"

    nds_ten = by_value[10]
    assert nds_ten.category_code == "nds_lecr"
    assert nds_ten.is_default is False  # specific категория, not default

    nds_default = by_value[22]
    assert nds_default.category_code == "nds_lecr"  # has Directory
    assert nds_default.is_default is True  # "- Прочие" — catch-all
    assert nds_default.description == "- Прочие"


@pytest.mark.asyncio
async def test_get_rates_emits_one_row_per_alta_variant():
    """Probe of HS=7326909807 returns 5 rows (2 IMP + 3 NDS), each emitted
    as its own Rate. The previous parser collapsed them — the resolver
    then arbitrarily picked НДС 0% even for shaybas. This is the tracer
    test that distinguishes "all variants captured" from "first wins".
    """
    client = AltaClient(login="testlogin", password="testpw")

    fake_resp = _make_response(_multivariant_taksa_xml(), charset="utf-8")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = fake_resp
        mock_client_cls.return_value = mock_client

        rates = await client.get_rates(
            "7326909807", 156, date(2026, 5, 3),
        )

    assert len(rates) == 5
    payment_counts: dict[str, int] = {}
    for r in rates:
        payment_counts[r.payment_type] = payment_counts.get(r.payment_type, 0) + 1
    assert payment_counts == {"IMP": 2, "NDS": 3}


# ---------------------------------------------------------------------------
# Phase A — Importlist payment_type classification (Req 1)
# ---------------------------------------------------------------------------


def _antidumping_taksa_xml() -> bytes:
    """Trimmed real Alta response shape for HS=7304110008 × Украина.

    Models the antidumping case probed during Phase A scoping: 6 variants
    под Решением 702 КТС (Антидемпинговые пошлины) + 1 base IMP под «реш.80».
    The previous parser collapsed all 7 into IMP — Phase A splits the 6
    антидемпинг rows into IMPDEMP and keeps the «реш.80» as IMP.
    """
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<GoodInfo><Code>7304110008</Code>'
        '<Importlist>'
        # Base IMP (реш.80 — default)
        '<Import>'
        '<Value>5%</Value>'
        '<ValueDetail><ValueCount>5</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>- прочее</Prim>'
        '<Order>реш.80</Order>'
        '<OrderCond>НЕТ льготы</OrderCond>'
        '<Link>https://www.alta.ru/tamdoc/12reh0080/</Link>'
        '</Import>'
        # 6 антидемпинг variants (Решение 702 КТС)
        '<Import>'
        '<Value>18.9%</Value>'
        '<ValueDetail><ValueCount>18.9</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>ОАО Интерпайп</Prim>'
        '<Order>Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — производитель ОАО Интерпайп)</Order>'
        '<Link>https://www.alta.ru/tamdoc/11k00702/</Link>'
        '</Import>'
        '<Import>'
        '<Value>23.4%</Value>'
        '<ValueDetail><ValueCount>23.4</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>ОАО Северский</Prim>'
        '<Order>Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — производитель ОАО Северский)</Order>'
        '<Link>https://www.alta.ru/tamdoc/11k00702/</Link>'
        '</Import>'
        '<Import>'
        '<Value>19.4%</Value>'
        '<ValueDetail><ValueCount>19.4</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>ОАО Никопольский</Prim>'
        '<Order>Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — производитель ОАО Никопольский)</Order>'
        '<Link>https://www.alta.ru/tamdoc/11k00702/</Link>'
        '</Import>'
        '<Import>'
        '<Value>37.8%</Value>'
        '<ValueDetail><ValueCount>37.8</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>прочие</Prim>'
        '<Order>Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — прочие производители)</Order>'
        '<Link>https://www.alta.ru/tamdoc/11k00702/</Link>'
        '</Import>'
        '<Import>'
        '<Value>14.2%</Value>'
        '<ValueDetail><ValueCount>14.2</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>ОАО Днепропетровский</Prim>'
        '<Order>Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — производитель ОАО Днепропетровский)</Order>'
        '<Link>https://www.alta.ru/tamdoc/11k00702/</Link>'
        '</Import>'
        '<Import>'
        '<Value>26.7%</Value>'
        '<ValueDetail><ValueCount>26.7</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>ОАО Харцызский</Prim>'
        '<Order>Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — производитель ОАО Харцызский)</Order>'
        '<Link>https://www.alta.ru/tamdoc/11k00702/</Link>'
        '</Import>'
        '</Importlist>'
        '<Exciselist/>'
        '<VATlist/>'
        '</GoodInfo>'
    )
    return xml.encode("utf-8")


# Unit tests — _classify_import_payment_type ----------------------------------


def test_classify_imp_default_when_no_order():
    """Empty/None <Order> → IMP без warning (legacy non-categorised data, AC#10)."""
    assert _classify_import_payment_type(None) == ("IMP", False)
    assert _classify_import_payment_type("") == ("IMP", False)


def test_classify_imp_when_resh_prefix():
    """Order starting with "реш." → IMP без warning (AC#6)."""
    assert _classify_import_payment_type("реш.80") == ("IMP", False)
    assert _classify_import_payment_type("Реш.130") == ("IMP", False)
    # "Решение 80" variant
    assert _classify_import_payment_type("Решение 80 от ...") == ("IMP", False)


def test_classify_impdemp_from_antidemp_text():
    """Order containing "антидемп" → IMPDEMP (AC#2)."""
    assert _classify_import_payment_type(
        "Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины — ОАО Интерпайп)"
    ) == ("IMPDEMP", False)
    # case-insensitive
    assert _classify_import_payment_type("АНТИДЕМПИНГОВАЯ пошлина") == ("IMPDEMP", False)


def test_classify_impcomp_from_compensation_text():
    """Order containing "компенсационн" → IMPCOMP (AC#3)."""
    assert _classify_import_payment_type(
        "Решение 123 (Компенсационные пошлины)"
    ) == ("IMPCOMP", False)
    assert _classify_import_payment_type("компенсационная пошлина") == ("IMPCOMP", False)


def test_classify_impdop_from_special_text():
    """Order containing "специальн" or "специальная защитная" → IMPDOP (AC#4)."""
    assert _classify_import_payment_type(
        "Решение 555 (Специальная защитная пошлина)"
    ) == ("IMPDOP", False)
    assert _classify_import_payment_type("Специальные тарифы") == ("IMPDOP", False)


def test_classify_imptmp_from_seasonal_text():
    """Order containing "сезонн" → IMPTMP (AC#5)."""
    assert _classify_import_payment_type(
        "Постановление 100 (Сезонная пошлина на сахар)"
    ) == ("IMPTMP", False)
    assert _classify_import_payment_type("СЕЗОННЫЕ пошлины") == ("IMPTMP", False)


def test_classify_unknown_pattern_defaults_imp_with_warning():
    """Non-empty, non-default text matching no pattern → IMP + is_unknown=True (AC#7)."""
    payment_type, is_unknown = _classify_import_payment_type("Неизвестный документ ABC-2099")
    assert payment_type == "IMP"
    assert is_unknown is True


@pytest.mark.asyncio
async def test_extract_rates_emits_warning_for_unknown_order_pattern(caplog):
    """When <Order> matches no known pattern, _extract_rates logs structured WARNING.

    The log entry includes tnved_code, order_ref, and unknown_order_pattern flag
    so ops can grep production logs and extend `_IMPORT_TYPE_PATTERNS` without
    a release (Req 1 AC#7).
    """
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<GoodInfo><Code>1234567890</Code>'
        '<Importlist>'
        '<Import>'
        '<Value>5%</Value>'
        '<ValueDetail><ValueCount>5</ValueCount><ValueUnit>%</ValueUnit></ValueDetail>'
        '<Prim>- прочее</Prim>'
        '<Order>Неклассифицированный документ XYZ</Order>'
        '</Import>'
        '</Importlist>'
        '<Exciselist/><VATlist/>'
        '</GoodInfo>'
    ).encode("utf-8")

    client = AltaClient(login="testlogin", password="testpw")
    fake_resp = _make_response(xml, charset="utf-8")

    with caplog.at_level("WARNING", logger="services.alta_client"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            rates = await client.get_rates(
                "1234567890", 156, date(2026, 5, 3),
            )

    # Defaulted to IMP despite unknown pattern
    assert len(rates) == 1
    assert rates[0].payment_type == "IMP"

    # WARNING with structured fields
    matching = [r for r in caplog.records if "unknown <Order> pattern" in r.message]
    assert len(matching) == 1
    record = matching[0]
    assert record.levelname == "WARNING"
    assert getattr(record, "tnved_code", None) == "1234567890"
    assert getattr(record, "order_ref", None) == "Неклассифицированный документ XYZ"
    assert getattr(record, "unknown_order_pattern", None) is True


# Integration test — _extract_rates classifies antidumping variants -----------


@pytest.mark.asyncio
async def test_get_rates_classifies_antidumping_variants():
    """Antidumping fixture: 6× IMPDEMP variants + 1× IMP base.

    Previously the parser hardcoded "IMP" for every Importlist row, so the
    антидемпинг information collapsed into the base IMP rate. Phase A
    classifier splits them so the resolver can group by payment_type and
    the UI can render an orange antidumping block.
    """
    client = AltaClient(login="testlogin", password="testpw")

    fake_resp = _make_response(_antidumping_taksa_xml(), charset="utf-8")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = fake_resp
        mock_client_cls.return_value = mock_client

        rates = await client.get_rates(
            "7304110008", 804, date(2026, 5, 3),
        )

    payment_counts: dict[str, int] = {}
    for r in rates:
        payment_counts[r.payment_type] = payment_counts.get(r.payment_type, 0) + 1
    assert payment_counts == {"IMP": 1, "IMPDEMP": 6}

    impdemp_rates = [r for r in rates if r.payment_type == "IMPDEMP"]
    # All IMPDEMP rates carry the Решение 702 reference in order_ref
    for r in impdemp_rates:
        assert r.order_ref is not None
        assert "702" in r.order_ref
        assert "Антидемпинг" in r.order_ref

    imp_rates = [r for r in rates if r.payment_type == "IMP"]
    assert imp_rates[0].order_ref == "реш.80"
