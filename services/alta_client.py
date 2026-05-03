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

# Alta exposes two distinct subdomains:
#   - www.alta.ru  for Такса / xml_nodes / АПУ (verified 2026-05-03 via curl probe — www2 404s on these)
#   - www2.alta.ru for Express batch classifier
# Conflating them broke production after the customs Phase 1 deploy:
# /api/customs/non-tariff-measures returned 404, /api/customs/resolve-rates
# would have too once the date_ kwarg fix landed.
ALTA_TAKSA_BASE = "https://www.alta.ru"
ALTA_EXPRESS_BASE = "https://www2.alta.ru"
ALTA_TAKSA_URL = f"{ALTA_TAKSA_BASE}/tnved/xml/"
ALTA_NODES_URL = f"{ALTA_TAKSA_BASE}/tnved/xml_nodes/"
ALTA_APU_URL = f"{ALTA_TAKSA_BASE}/tnved/xml_apu/"
ALTA_EXPRESS_URL = f"{ALTA_EXPRESS_BASE}/tools/autotnved/v2/"

# Rate.source provenance (mirrors kvota.tnved_rates.source CHECK constraint).
RateSource = Literal['alta-live', 'alta-revalidate', 'manual']
_VALID_RATE_SOURCES: frozenset[str] = frozenset(
    {'alta-live', 'alta-revalidate', 'manual'}
)

# country_or_areal regex (mirrors migration 298 CHECK constraint).
_COUNTRY_PATTERN = re.compile(r"^C:\d+$")
_AREAL_PATTERN = re.compile(r"^A:\w+$")

# Allowed sign tokens between adjacent value slots (matches schema CHECK).
_VALID_SIGN_TOKENS: frozenset[str] = frozenset({"+", ">"})

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

    # Provenance for the customs_calc adapter switch (REQ-4 / decisions Q1).
    # Populated when reading from `kvota.tnved_rates.source` ('alta-live' |
    # 'alta-revalidate' | 'manual'). The Alta XML response itself does not
    # carry this field — it is set by the persistence layer on read/upsert.
    source: RateSource | None = None

    def __post_init__(self) -> None:
        """Enforce schema CHECK invariants at construction time.

        Mirrors the constraints in migration 298 — a Rate that the DB
        would reject must not be constructable in memory either.
        """
        # 1. country_or_areal format
        if self.country_or_areal is not None:
            if not (
                _COUNTRY_PATTERN.match(self.country_or_areal)
                or _AREAL_PATTERN.match(self.country_or_areal)
            ):
                raise ValueError(
                    f"Rate invariant violated: country_or_areal must be "
                    f"None, 'C:<digits>', or 'A:<token>', got "
                    f"{self.country_or_areal!r}"
                )

        # 2. Sign-vs-slot consistency: sign_1 connects slots 1 and 2, so
        # slot 2 must be populated whenever sign_1 is set; mirror for
        # sign_2 / slot 3. Conversely, when slot 2 (or 3) is populated
        # the corresponding sign must be one of the allowed tokens.
        if self.value_2_number is not None:
            if self.sign_1 not in _VALID_SIGN_TOKENS:
                raise ValueError(
                    f"Rate invariant violated: sign_1 must be one of "
                    f"{sorted(_VALID_SIGN_TOKENS)} when value_2_number "
                    f"is set, got {self.sign_1!r}"
                )
        if self.value_3_number is not None:
            if self.sign_2 not in _VALID_SIGN_TOKENS:
                raise ValueError(
                    f"Rate invariant violated: sign_2 must be one of "
                    f"{sorted(_VALID_SIGN_TOKENS)} when value_3_number "
                    f"is set, got {self.sign_2!r}"
                )

        # 3. Percent-vs-currency exclusion: percent units never carry a
        # currency (% is dimensionless). OKEI-coded units MAY carry one.
        for slot, unit, currency in (
            (1, self.value_1_unit, self.value_1_currency),
            (2, self.value_2_unit, self.value_2_currency),
            (3, self.value_3_unit, self.value_3_currency),
        ):
            if unit == "percent" and currency is not None:
                raise ValueError(
                    f"Rate invariant violated: value_{slot}_currency "
                    f"must be None when value_{slot}_unit='percent', "
                    f"got {currency!r}"
                )

        # 4. source provenance — mirror Literal at runtime so values
        # constructed from JSONB / DB rows (where Literal isn't enforced)
        # still get caught.
        if (
            self.source is not None
            and self.source not in _VALID_RATE_SOURCES
        ):
            raise ValueError(
                f"Rate invariant violated: source must be one of "
                f"{sorted(_VALID_RATE_SOURCES)} or None, got "
                f"{self.source!r}"
            )


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
    `services.telegram_service` if configured; otherwise falls back to
    Sentry capture so ops still has a second observability channel.
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
    # Sentry fallback — keeps the alert visible to ops even when Telegram
    # is down or ADMIN_TELEGRAM_CHAT_ID is unset. Wrapped defensively so
    # telemetry never breaks the caller (M10 review fix).
    try:
        import sentry_sdk

        sentry_sdk.capture_message(
            f"customs admin alert (Telegram unavailable): {message}",
            level="warning",
        )
    except ImportError:
        pass  # Sentry not installed in this environment
    except Exception:
        pass  # never break the caller on telemetry


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
        # Last-known packet_left from Alta — populated after each request
        # by ``_log_packet_left``. Read by ``api.cron.cron_revalidate_rates``
        # to abort the loop when the prepaid packet runs low (REQ-6 AC#5).
        self.last_packet_left: int | None = None
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

        # Такса / xml_nodes / АПУ return errors as <Error>...</Error>
        # rather than the Express <response><handled>false> envelope.
        # Detect the Такса error format first (root tag is "Error") and
        # raise AltaApiError so callers see the same exception path
        # regardless of which Alta endpoint failed.
        if root.tag == "Error":
            err_code_text = _text(root.find("ErrorCode"))
            err_descr = _text(root.find("ErrorDescr")) or "<no description>"
            try:
                code = int(err_code_text)
            except ValueError:
                code = 0
            raise AltaApiError(
                code or -1,
                err_descr if code in DOCUMENTED_ERROR_CODES
                          else f"Alta error {err_code_text!r}: {err_descr}",
            )

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

        Also stores the value in ``self.last_packet_left`` so
        ``api.cron.cron_revalidate_rates`` (REQ-6 AC#5) can read it
        after each call without re-parsing the response XML.

        Throttled: at most one alert of each kind per hour.
        """
        if left_count is None:
            return
        self.last_packet_left = left_count
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
        # Param names per Alta Такса spec (verified 2026-05-03 against the
        # `<Error><ErrorCode>101</ErrorCode>` returned in production):
        #   tncode (NOT tnved), login (NOT slogin), secret (NOT hash).
        # Phase 0 used Express-style names which DIFFER from Такса/АПУ —
        # the rename to AltaClient kept Express names everywhere.
        params = {
            "tncode": tncode,
            "country": country,
            "date": date_.isoformat(),
            "certificate": "1" if certificate else "0",
            "sp_certificate": "1" if sp_certificate else "0",
            "login": self._login,
            "secret": self._sign(tncode),
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
            "tncode": tncode,
            "country": country,
            "mode": mode,
            "login": self._login,
            "secret": self._sign(tncode),
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
            "login": self._login,
            "secret": self._sign(query),
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
            "login": self._login,
            "secret": self._sign(payload_id),
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
        """Extract Rate dataclasses from a Такса <GoodInfo> response.

        Alta Такса real schema (verified 2026-05-03 against live response):
            <GoodInfo>
              <Code>...</Code>
              <Importlist>
                <Import>
                  <Value>10%, но не менее 0,04 евро/кг</Value>
                  <ValueDetail>
                    <ValueCount>10</ValueCount>
                    <ValueUnit>%</ValueUnit>
                  </ValueDetail>
                  <ValueDetailAdd>          <!-- combined-rate 2nd part -->
                    <ValueCount>0.04</ValueCount>
                    <ValueUnit>евро/кг</ValueUnit>
                    <ValueCurrency>EUR</ValueCurrency>
                  </ValueDetailAdd>
                  ...
                </Import>
              </Importlist>
              <Exciselist>
                <Excise>...</Excise>
              </Exciselist>
              <VATlist>
                <VAT>...</VAT>
              </VATlist>
            </GoodInfo>

        Phase-1 minimal mapping:
          - <Importlist><Import>     → payment_type='IMP'
          - <Exciselist><Excise>     → payment_type='AKC'
          - <VATlist><VAT>           → payment_type='NDS'

        Slot extraction:
          - value_1_*  ← <ValueDetail>
          - value_2_*  ← <ValueDetailAdd> when present
          - sign_1     ← '>' (Alta combined-rate semantics: "не менее" → max)
          - country_or_areal: NOT echoed by Alta on Такса, kept None.
          - raw_value_string ← <Value> verbatim.

        Edge cases (Phase 2 follow-up — see TODO):
          - Multiple Import alternatives (preferences vs base) — we take all.
          - <ValueDetail2>/<ValueDetail3> "не менее"/"не более" subblocks.
          - Excise with <Condition> (alcohol strength etc.) — currently flat.
          - VAT <Directory> for льготные ставки.
        """
        rates: list[Rate] = []

        def _slot_from(detail_el: ET.Element | None):
            """Map <ValueCount>/<ValueUnit>/<ValueCurrency> → (number, unit, currency)."""
            if detail_el is None:
                return None, None, None
            count_text = _text(detail_el.find("ValueCount"))
            unit_text = _text(detail_el.find("ValueUnit"))
            currency_text = _text(detail_el.find("ValueCurrency"))
            try:
                # Alta uses both '.' and ',' as decimal separator.
                number = float(count_text.replace(",", ".")) if count_text else None
            except (ValueError, AttributeError):
                number = None
            unit = self._normalize_unit(unit_text) if unit_text else None
            currency = currency_text or None
            return number, unit, currency

        def _emit(elem: ET.Element, payment_type: str):
            v1_number, v1_unit, v1_currency = _slot_from(elem.find("ValueDetail"))
            v2_number, v2_unit, v2_currency = _slot_from(elem.find("ValueDetailAdd"))
            sign_1 = ">" if v2_number is not None else None
            raw = _text(elem.find("Value")) or None

            # Rate.__post_init__ rejects percent + currency together.
            # Some Alta responses set ValueCurrency on a percent value
            # (e.g., "% от стоимости в EUR" rendered with currency=EUR);
            # strip it for percent units to satisfy the invariant.
            if v1_unit == "percent":
                v1_currency = None
            if v2_unit == "percent":
                v2_currency = None

            try:
                rates.append(
                    Rate(
                        tnved_code=tncode,
                        payment_type=payment_type,
                        country_or_areal=None,
                        valid_from=date.today(),
                        valid_to=None,
                        value_1_number=v1_number,
                        value_1_unit=v1_unit,
                        value_1_currency=v1_currency,
                        value_2_number=v2_number,
                        value_2_unit=v2_unit,
                        value_2_currency=v2_currency,
                        sign_1=sign_1,
                        raw_value_string=raw,
                        certificate_required=certificate,
                        sp_certificate_required=sp_certificate,
                    )
                )
            except ValueError as exc:
                # Invariant violation — log and skip rather than fail the
                # whole fetch. The user sees the rest of the rates.
                logger.warning(
                    "Skipping unparseable %s rate for %s: %s (raw=%r)",
                    payment_type, tncode, exc, raw,
                )

        for el in root.findall("Importlist/Import"):
            _emit(el, "IMP")
        for el in root.findall("Exciselist/Excise"):
            _emit(el, "AKC")
        for el in root.findall("VATlist/VAT"):
            _emit(el, "NDS")

        return rates

    @staticmethod
    def _normalize_unit(unit_text: str) -> str:
        """Coerce Alta's free-text unit to our canonical form.

        Alta uses Russian unit strings (%, евро/кг, руб/шт, etc.); we
        normalize to the schema's CHECK constraint vocabulary:
          '%'        → 'percent'
          *кг*       → '166' (OKEI kg)
          *л* (litre)→ '111'
          *шт*       → '796'
          unknown    → return verbatim (Rate.__post_init__ will reject if
                       paired with currency, but the user sees raw_value
                       so the data isn't lost).
        """
        u = (unit_text or "").lower().strip()
        if "%" in u:
            return "percent"
        if "кг" in u:
            return "166"
        if "лит" in u or "л " in u or u == "л":
            return "111"
        if "шт" in u:
            return "796"
        return unit_text  # passthrough for unmapped units

    def _extract_measures(
        self,
        root: ET.Element,
        tncode: str,
    ) -> list[Measure]:
        """Extract Measure dataclasses from a xml_nodes <GoodInfo> response.

        Real schema: ``<GoodInfo><Notes><Note>...</Note></Notes></GoodInfo>``
        Each Note carries Type/Name/Description/Document/Link (subset).
        """
        measures: list[Measure] = []
        for el in root.findall("Notes/Note"):
            measures.append(
                Measure(
                    tnved_code=tncode,
                    country_or_areal=None,
                    measure_type=_text(el.find("Type")) or "unknown",
                    name=_text(el.find("Name")) or "",
                    description=_text(el.find("Description")) or None,
                    document_basis=_text(el.find("Document")) or None,
                    document_link=_text(el.find("Link")) or None,
                    valid_from=None,
                    valid_to=None,
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
