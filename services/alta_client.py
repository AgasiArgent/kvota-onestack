"""Alta-Soft XML API async client (REQ-2 customs-phase-1).

Single entry point for the four Alta endpoints:
- Такса         /tnved/xml/         — duty/excise/VAT rates
- xml_nodes     /tnved/xml_nodes/   — non-tariff measures (separate billing)
- АПУ           /tnved/xml_apu/     — interactive classifier (suggest + codes)
- Express       /tools/autotnved/v2/ — batch classifier

Lifted from Phase 0 (`scripts/phase0_eval_alta_express.py`) and adapted to
async + production-grade error handling, packet warnings via Telegram, and
FastAPI Depends factory.

Reference: `.kiro/specs/customs-phase-1-rates-and-measures/{requirements,design,decisions}.md`
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALTA_BASE_URL = "https://www2.alta.ru"
ALTA_TAKSA_URL = f"{ALTA_BASE_URL}/tnved/xml/"
ALTA_NODES_URL = f"{ALTA_BASE_URL}/tnved/xml_nodes/"
ALTA_APU_URL = f"{ALTA_BASE_URL}/tnved/xml_apu/"
ALTA_EXPRESS_URL = f"{ALTA_BASE_URL}/tools/autotnved/v2/"

HTTP_TIMEOUT_SECONDS: float = 30.0

# Polling — Phase 0 calibrated values (1 initial + 5 retries × 2.0s)
POLL_MAX_ATTEMPTS: int = 6
POLL_DELAY_SECONDS: float = 2.0

# Network retry policy (REQ-2 AC#12)
NETWORK_RETRY_MAX_ATTEMPTS: int = 2
NETWORK_RETRY_BACKOFF: tuple[float, ...] = (1.0, 2.0)

# Documented Alta error codes (REQ-2 AC#5)
DOCUMENTED_ERROR_CODES: frozenset[int] = frozenset({100, 110, 120, 140, 201})

# Packet warning threshold (REQ-2 AC#10)
PACKET_LOW_THRESHOLD: int = 100
PACKET_ALERT_THROTTLE = timedelta(hours=1)

# Encoding fallback for Такса/xml_nodes endpoints (gotcha #2)
TAKSA_DEFAULT_ENCODING = "windows-1251"


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rate:
    """Mirrors `kvota.tnved_rates` 3-slot model (migration 298).

    `value_*_unit`: 'percent' | OKEI code (e.g. '166'=kg, '111'=l, '796'=шт)
    `value_*_currency`: ISO-4217 (NULL for percent)
    `sign_1` / `sign_2`: '+' | '>' | None — relation between adjacent slots
    """
    tnved_code: str
    payment_type: str
    country_or_areal: str | None  # 'C:643' | 'A:EAEU' | None (base)
    valid_from: date
    valid_to: date | None = None

    value_1_number: float | None = None
    value_1_unit: str | None = None
    value_1_currency: str | None = None

    value_2_number: float | None = None
    value_2_unit: str | None = None
    value_2_currency: str | None = None
    sign_1: str | None = None

    value_3_number: float | None = None
    value_3_unit: str | None = None
    value_3_currency: str | None = None
    sign_2: str | None = None

    raw_value_string: str | None = None
    certificate_required: bool = False
    sp_certificate_required: bool = False


@dataclass(frozen=True)
class Measure:
    """Non-tariff regulation measure (Alta xml_nodes response)."""
    tnved_code: str
    country_or_areal: str | None
    measure_type: str
    name: str
    description: str | None = None
    document_basis: str | None = None
    document_link: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None


@dataclass(frozen=True)
class ApuSuggestResponse:
    payload_id: str
    suggestions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ApuCode:
    code: str
    description: str
    confidence: float | None = None


@dataclass(frozen=True)
class ExpressItem:
    id: int
    name: str


@dataclass(frozen=True)
class ExpressPrediction:
    id: int
    code: str
    code_weight: int
    probability: float


@dataclass(frozen=True)
class ExpressBatchResponse:
    handled: bool
    message: str
    predictions: list[ExpressPrediction] = field(default_factory=list)
    balance: float | None = None
    packet_left: int | None = None
    packet_used: int | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AltaApiError(Exception):
    """Alta API returned a documented or undocumented error code."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Alta API error {code}: {message}")


# ---------------------------------------------------------------------------
# Module-level mutable state — singleton + alert throttling
# ---------------------------------------------------------------------------

_client_singleton: AltaClient | None = None
_last_alert_at: dict[str, datetime] = {}


# ---------------------------------------------------------------------------
# Telegram alerting (Q2)
# ---------------------------------------------------------------------------


async def notify_admin(message: str) -> None:
    """Send an admin alert via the existing Telegram service.

    Module-level wrapper so tests can patch a single symbol. Uses
    `services.telegram_service` if configured; otherwise logs only.
    """
    try:
        from services import telegram_service

        bot = telegram_service.get_bot()
        chat_id = os.getenv("ADMIN_TELEGRAM_CHAT_ID", "")
        if bot and chat_id:
            await bot.send_message(chat_id=int(chat_id), text=message[:4096])
            logger.info("AltaClient admin alert sent: %s", message[:120])
            return
    except Exception as exc:  # pragma: no cover — alerting must never crash callers
        logger.error("Failed to send AltaClient admin alert: %s", exc)
    logger.warning("AltaClient admin alert (telegram unavailable): %s", message)


# ---------------------------------------------------------------------------
# AltaClient
# ---------------------------------------------------------------------------


def _text(elem: ET.Element | None) -> str:
    return (elem.text or "").strip() if elem is not None else ""


class AltaClient:
    """Async XML client for the four Alta-Soft endpoints.

    Credentials never leak: plaintext password lives only in `__init__`,
    instance stores `_password_md5`. `repr()` redacts both fields.
    """

    def __init__(self, login: str, password: str):
        self._login: str = login
        self._password_md5: str = hashlib.md5(
            password.encode("utf-8")
        ).hexdigest()
        self._http_timeout: float = HTTP_TIMEOUT_SECONDS
        # plaintext `password` parameter goes out of scope here

    def __repr__(self) -> str:
        return "AltaClient(login=<redacted>, password=<redacted>)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, param: str) -> str:
        """MD5 double-hash signature.

        `md5(f"{param}:{login}:{md5(password)}".encode("utf-8")).hexdigest()`

        IMPORTANT: `param` is hashed in raw UTF-8 — never URL-encoded
        (gotcha #1 from Phase 0). URL-encoding is applied afterwards
        when assembling GET parameters.
        """
        return hashlib.md5(
            f"{param}:{self._login}:{self._password_md5}".encode("utf-8")
        ).hexdigest()

    def _decode_xml(self, response: httpx.Response) -> str:
        """Detect XML encoding and decode bytes.

        Order of precedence (gotcha #2):
        1. HTTP Content-Type charset
        2. XML declaration `<?xml ... encoding="..."?>`
        3. windows-1251 fallback for Такса/xml_nodes endpoints
        4. utf-8 fallback for Express
        """
        # 1. charset header — httpx exposes via .charset_encoding
        charset = response.charset_encoding
        if charset:
            try:
                return response.content.decode(charset)
            except (LookupError, UnicodeDecodeError):
                pass

        # 2. XML declaration in first ~200 bytes
        head = response.content[:200]
        match = re.search(
            rb'<\?xml[^>]*encoding=["\']([^"\']+)["\']',
            head,
            re.IGNORECASE,
        )
        if match:
            decl_enc = match.group(1).decode("ascii", errors="ignore")
            try:
                return response.content.decode(decl_enc)
            except (LookupError, UnicodeDecodeError):
                pass

        # 3/4. URL-based fallback
        url = str(response.url) if response.url else ""
        fallback = (
            "utf-8" if "tools/autotnved" in url else TAKSA_DEFAULT_ENCODING
        )
        return response.content.decode(fallback, errors="replace")

    def _parse_response(self, xml_text: str) -> dict[str, Any]:
        """Parse Alta XML, raising AltaApiError on documented/undocumented errors.

        Returns a dict with at minimum {`handled`, `message`, ...}.
        Express-specific keys (`predictions`, `balance`, `packet_*`) are
        included when present.
        """
        root = ET.fromstring(xml_text)
        handled = _text(root.find("handled")).lower() == "true"
        message = _text(root.find("message"))

        if not handled:
            try:
                code = int(message)
            except ValueError:
                code = 0
            if code in DOCUMENTED_ERROR_CODES:
                raise AltaApiError(code, message)
            if code != 0:
                raise AltaApiError(
                    code, f"undocumented Alta error code: {message!r}"
                )
            # code == 0: queue-pending / non-numeric → caller decides

        result: dict[str, Any] = {
            "handled": handled,
            "message": message,
            "root": root,
        }

        # Express predictions
        predictions: list[ExpressPrediction] = []
        response_el = root.find("response")
        if response_el is not None:
            for item_el in response_el.findall("item"):
                try:
                    predictions.append(
                        ExpressPrediction(
                            id=int(_text(item_el.find("id"))),
                            code=_text(item_el.find("code")),
                            code_weight=int(
                                _text(item_el.find("codeWeight")) or 0
                            ),
                            probability=float(
                                _text(item_el.find("probability")) or 0.0
                            ),
                        )
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"malformed prediction in response: {exc}"
                    ) from exc
        result["predictions"] = predictions

        balance_text = _text(root.find("balance"))
        result["balance"] = float(balance_text) if balance_text else None

        packet_first = root.find("packet/item")
        if packet_first is not None:
            left_text = _text(packet_first.find("left_count"))
            used_text = _text(packet_first.find("used_count"))
            result["packet_left"] = int(left_text) if left_text else None
            result["packet_used"] = int(used_text) if used_text else None
        else:
            result["packet_left"] = None
            result["packet_used"] = None

        return result

    def _log_packet_left(self, left_count: int | None) -> None:
        """Log packet remaining; Telegram-alert when low (REQ-2 AC#10, Q2).

        Throttled: at most one alert of each kind per hour.
        """
        if left_count is None:
            return
        logger.info("Alta packet remaining: %d", left_count)
        if left_count >= PACKET_LOW_THRESHOLD:
            return

        logger.warning(
            "Alta packet running low: %d remaining (threshold %d)",
            left_count,
            PACKET_LOW_THRESHOLD,
        )
        key = "packet_low"
        now = datetime.now()
        last = _last_alert_at.get(key)
        if last is not None and (now - last) < PACKET_ALERT_THROTTLE:
            return
        _last_alert_at[key] = now

        message = (
            f"⚠️ Alta packet running low: {left_count} requests remaining "
            f"(threshold {PACKET_LOW_THRESHOLD}). Consider topping up."
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(notify_admin(message))
            else:  # pragma: no cover
                loop.run_until_complete(notify_admin(message))
        except RuntimeError:
            # No event loop available (sync context) — schedule a thread-safe call
            try:
                asyncio.run(notify_admin(message))
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to dispatch packet alert: %s", exc)

    async def _with_retries(self, coro_factory) -> Any:
        """Run an async operation with retries on network errors.

        Retries only on connect/read timeouts. AltaApiError and HTTP 4xx
        bubble up immediately (no retry — deterministic errors).
        """
        last_exc: Exception | None = None
        for attempt in range(NETWORK_RETRY_MAX_ATTEMPTS):
            try:
                return await coro_factory()
            except (httpx.ConnectTimeout, httpx.ReadTimeout,
                    httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < NETWORK_RETRY_MAX_ATTEMPTS - 1:
                    backoff = NETWORK_RETRY_BACKOFF[
                        min(attempt, len(NETWORK_RETRY_BACKOFF) - 1)
                    ]
                    logger.warning(
                        "Alta network error (attempt %d): %s — retrying in %.1fs",
                        attempt + 1, exc, backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    break
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def get_rates(
        self,
        tncode: str,
        country: int,
        date_: date,
        certificate: bool = False,
        sp_certificate: bool = False,
    ) -> list[Rate]:
        """Fetch duty/excise/VAT rates for a TN VED code + country + date.

        Endpoint: Alta Такса `/tnved/xml/`. Response is windows-1251.
        """
        params = {
            "tnved": tncode,
            "country": country,
            "date": date_.isoformat(),
            "certificate": "1" if certificate else "0",
            "sp_certificate": "1" if sp_certificate else "0",
            "slogin": self._login,
            "hash": self._sign(tncode),
        }

        async def _do_call() -> list[Rate]:
            async with httpx.AsyncClient(
                timeout=self._http_timeout
            ) as client:
                resp = await client.get(ALTA_TAKSA_URL, params=params)
                resp.raise_for_status()
                xml_text = self._decode_xml(resp)
                parsed = self._parse_response(xml_text)
                self._log_packet_left(parsed.get("packet_left"))
                return self._extract_rates(
                    parsed["root"], tncode,
                    certificate, sp_certificate,
                )

        return await self._with_retries(_do_call)

    async def get_non_tariff_measures(
        self,
        tncode: str,
        country: int,
        mode: Literal["import", "export"] = "import",
    ) -> list[Measure]:
        """Fetch non-tariff measures (gotcha #5 — billed separately, ~3₽/call).

        Endpoint: `/tnved/xml_nodes/`.
        """
        params = {
            "tnved": tncode,
            "country": country,
            "mode": mode,
            "slogin": self._login,
            "hash": self._sign(tncode),
        }

        async def _do_call() -> list[Measure]:
            async with httpx.AsyncClient(
                timeout=self._http_timeout
            ) as client:
                resp = await client.get(ALTA_NODES_URL, params=params)
                resp.raise_for_status()
                xml_text = self._decode_xml(resp)
                parsed = self._parse_response(xml_text)
                self._log_packet_left(parsed.get("packet_left"))
                return self._extract_measures(
                    parsed["root"], tncode,
                )

        return await self._with_retries(_do_call)

    async def apu_suggest(
        self, query: str, limit: int = 10
    ) -> ApuSuggestResponse:
        """АПУ stage 1: suggest descriptors from a free-text query."""
        params = {
            "action": "suggest",
            "q": query,
            "limit": limit,
            "slogin": self._login,
            "hash": self._sign(query),
        }

        async def _do_call() -> ApuSuggestResponse:
            async with httpx.AsyncClient(
                timeout=self._http_timeout
            ) as client:
                resp = await client.get(ALTA_APU_URL, params=params)
                resp.raise_for_status()
                xml_text = self._decode_xml(resp)
                parsed = self._parse_response(xml_text)
                self._log_packet_left(parsed.get("packet_left"))
                root = parsed["root"]
                payload_id = _text(root.find("payload_id"))
                suggestions: list[dict[str, Any]] = []
                response_el = root.find("response")
                if response_el is not None:
                    for item_el in response_el.findall("item"):
                        suggestions.append(
                            {child.tag: _text(child) for child in item_el}
                        )
                return ApuSuggestResponse(
                    payload_id=payload_id, suggestions=suggestions
                )

        return await self._with_retries(_do_call)

    async def apu_codes(
        self, payload_id: str, limit: int = 10
    ) -> list[ApuCode]:
        """АПУ stage 2: resolve descriptors → candidate TN VED codes."""
        params = {
            "action": "codes",
            "payload_id": payload_id,
            "limit": limit,
            "slogin": self._login,
            "hash": self._sign(payload_id),
        }

        async def _do_call() -> list[ApuCode]:
            async with httpx.AsyncClient(
                timeout=self._http_timeout
            ) as client:
                resp = await client.get(ALTA_APU_URL, params=params)
                resp.raise_for_status()
                xml_text = self._decode_xml(resp)
                parsed = self._parse_response(xml_text)
                self._log_packet_left(parsed.get("packet_left"))
                root = parsed["root"]
                codes: list[ApuCode] = []
                response_el = root.find("response")
                if response_el is not None:
                    for item_el in response_el.findall("item"):
                        code = _text(item_el.find("code"))
                        description = _text(item_el.find("description"))
                        prob_text = _text(item_el.find("probability"))
                        confidence = (
                            float(prob_text) if prob_text else None
                        )
                        codes.append(
                            ApuCode(
                                code=code,
                                description=description,
                                confidence=confidence,
                            )
                        )
                return codes

        return await self._with_retries(_do_call)

    async def classify_batch(
        self,
        items: list[ExpressItem] | list[dict[str, Any]],
        request_id: str,
        *,
        group_hint: str | None = None,
    ) -> ExpressBatchResponse:
        """Alta Express batch classify.

        Idempotent by `request_id` — Alta will return the same response for
        repeat calls. Polls up to POLL_MAX_ATTEMPTS times.

        REQ-2 AC#9: `group_hint` is accepted for forward-compat but never
        emitted in the XML payload (Phase 1 MVP). A warning is logged when
        a non-None hint is passed.
        """
        if group_hint is not None:
            logger.warning(
                "classify_batch: group_hint=%r ignored "
                "(Phase 1 MVP — XML payload omits group= attribute)",
                group_hint,
            )

        xml_payload = self._build_express_xml(items)
        body = urllib.parse.urlencode({
            "slogin": self._login,
            "hash": self._sign(request_id),
            "xml": xml_payload,
            "tnveddescr": "1",
            "requestid": request_id,
        })
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async def _do_call() -> ExpressBatchResponse:
            last_message = ""
            async with httpx.AsyncClient(
                timeout=self._http_timeout
            ) as client:
                for attempt in range(POLL_MAX_ATTEMPTS):
                    resp = await client.post(
                        ALTA_EXPRESS_URL, content=body, headers=headers,
                    )
                    resp.raise_for_status()
                    xml_text = self._decode_xml(resp)
                    parsed = self._parse_response(xml_text)
                    self._log_packet_left(parsed.get("packet_left"))
                    if parsed["handled"]:
                        return ExpressBatchResponse(
                            handled=True,
                            message=parsed["message"],
                            predictions=parsed["predictions"],
                            balance=parsed.get("balance"),
                            packet_left=parsed.get("packet_left"),
                            packet_used=parsed.get("packet_used"),
                        )
                    last_message = parsed["message"]
                    if attempt >= POLL_MAX_ATTEMPTS - 1:
                        break
                    await asyncio.sleep(POLL_DELAY_SECONDS)

            raise RuntimeError(
                f"Alta Express polling exhausted for "
                f"request_id={request_id}, last_message={last_message!r}"
            )

        return await self._with_retries(_do_call)

    # ------------------------------------------------------------------
    # Response → domain object adapters
    # ------------------------------------------------------------------

    def _extract_rates(
        self,
        root: ET.Element,
        tncode: str,
        certificate: bool,
        sp_certificate: bool,
    ) -> list[Rate]:
        """Extract Rate dataclasses from a Такса response XML root.

        country_or_areal is read from the XML response (Alta echoes
        which country/areal the rate applies to). Caller's `country`
        parameter only flows into the request URL — see get_rates().
        """
        rates: list[Rate] = []
        # Alta Такса response shape: <rates><rate>...</rate>...</rates>
        rates_container = root.find("rates")
        if rates_container is None:
            return rates

        for rate_el in rates_container.findall("rate"):
            payment_type = _text(rate_el.find("payment_type")) or _text(
                rate_el.find("type")
            )
            country_or_areal = _text(rate_el.find("country_or_areal")) or None

            valid_from_text = _text(rate_el.find("valid_from"))
            valid_from = (
                date.fromisoformat(valid_from_text)
                if valid_from_text else date.today()
            )
            valid_to_text = _text(rate_el.find("valid_to"))
            valid_to = (
                date.fromisoformat(valid_to_text) if valid_to_text else None
            )

            def _slot_number(tag: str) -> float | None:
                txt = _text(rate_el.find(tag))
                return float(txt) if txt else None

            def _slot_str(tag: str) -> str | None:
                txt = _text(rate_el.find(tag))
                return txt or None

            rates.append(
                Rate(
                    tnved_code=tncode,
                    payment_type=payment_type,
                    country_or_areal=country_or_areal,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    value_1_number=_slot_number("value_1_number"),
                    value_1_unit=_slot_str("value_1_unit"),
                    value_1_currency=_slot_str("value_1_currency"),
                    value_2_number=_slot_number("value_2_number"),
                    value_2_unit=_slot_str("value_2_unit"),
                    value_2_currency=_slot_str("value_2_currency"),
                    sign_1=_slot_str("sign_1"),
                    value_3_number=_slot_number("value_3_number"),
                    value_3_unit=_slot_str("value_3_unit"),
                    value_3_currency=_slot_str("value_3_currency"),
                    sign_2=_slot_str("sign_2"),
                    raw_value_string=_slot_str("raw_value_string"),
                    certificate_required=certificate,
                    sp_certificate_required=sp_certificate,
                )
            )
        return rates

    def _extract_measures(
        self,
        root: ET.Element,
        tncode: str,
    ) -> list[Measure]:
        measures: list[Measure] = []
        container = root.find("measures") or root.find("response")
        if container is None:
            return measures

        for el in container.findall("measure"):
            country_or_areal = _text(el.find("country_or_areal")) or None
            valid_from_text = _text(el.find("valid_from"))
            valid_to_text = _text(el.find("valid_to"))
            measures.append(
                Measure(
                    tnved_code=tncode,
                    country_or_areal=country_or_areal,
                    measure_type=_text(el.find("measure_type")) or "unknown",
                    name=_text(el.find("name")),
                    description=_text(el.find("description")) or None,
                    document_basis=_text(el.find("document_basis")) or None,
                    document_link=_text(el.find("document_link")) or None,
                    valid_from=(
                        date.fromisoformat(valid_from_text)
                        if valid_from_text else None
                    ),
                    valid_to=(
                        date.fromisoformat(valid_to_text)
                        if valid_to_text else None
                    ),
                )
            )
        return measures

    def _build_express_xml(
        self, items: list[ExpressItem] | list[dict[str, Any]]
    ) -> str:
        """Build Alta Express request XML.

        Phase 1 MVP: no `group=` attribute (REQ-2 AC#9).
        """
        root = ET.Element("xml")
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                item_id = item.get("id", idx)
                name = item.get("name", "")
            else:
                item_id = item.id
                name = item.name
            i_el = ET.SubElement(root, "i", attrib={"id": str(item_id)})
            ET.SubElement(i_el, "name").text = str(name)
        return ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------------------
# DI factory (Q6)
# ---------------------------------------------------------------------------


def get_alta_client() -> AltaClient:
    """FastAPI Depends factory — lazy module-level singleton.

    Reads `ALTA_LOGIN` / `ALTA_PASSWORD` from environment exactly once.
    Tests can override via:
        app.dependency_overrides[get_alta_client] = lambda: MockAltaClient()
    """
    global _client_singleton
    if _client_singleton is None:
        login = os.environ["ALTA_LOGIN"]
        password = os.environ["ALTA_PASSWORD"]
        _client_singleton = AltaClient(login, password)
    return _client_singleton
