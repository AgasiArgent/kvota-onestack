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
    get_alta_client,
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
