"""Pydantic v2 models for the Customer Journey Map API (`/api/journey/*`).

Source of truth: `.kiro/specs/customer-journey-map/design.md` §4.4.
TypeScript mirrors: `frontend/src/entities/journey/types.ts` §4.1–§4.2.

This module is the authoritative Python contract for Wave 4 endpoints
(Tasks 10 — aggregate read, 11 — per-node detail, 12 — state PATCH,
13 — Playwright webhook). Each Wave 4 task extends these stubs with
handler-specific response models; shared primitives (RoleSlug, NodeId,
status literals, envelope) stay here.

Design notes:
- All fields use Pydantic v2 ``Field(...)`` descriptions so the generated
  OpenAPI schema is self-documenting (feeds future MCP tool generation —
  see `.kiro/steering/api-first.md`).
- Envelope models (``JourneySuccessEnvelope[T]`` / ``JourneyErrorEnvelope``)
  are generic so each endpoint can bind its own payload type without
  re-declaring the shape (Req 16.4).
- Legacy handlers may still use ``api/envelope.py`` helpers — those return
  raw ``JSONResponse``. Typed endpoints (new code) should prefer these
  models so the response schema appears in OpenAPI.
"""

from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# ---------------------------------------------------------------------------
# 1. Primitive aliases — mirror TS `entities/journey/types.ts`
# ---------------------------------------------------------------------------

#: Stable node identifier. Must start with ``app:`` (real Next.js route) or
#: ``ghost:`` (planned-but-unshipped node). Pattern matches the
#: ``JourneyNodeId`` TS template-literal union in §4.1.
NodeId = Annotated[
    str,
    StringConstraints(pattern=r"^(app:|ghost:).+"),
]

#: Implementation status. Mirrors DB CHECK on ``journey_node_state.impl_status``
#: and the ``ImplStatus`` TS literal union (§4.2).
ImplStatus = Literal["done", "partial", "missing"]

#: QA status. Mirrors DB CHECK on ``journey_node_state.qa_status`` and the
#: ``QaStatus`` TS literal union (§4.2).
QaStatus = Literal["verified", "broken", "untested"]

#: Ghost node lifecycle status (§4.2 ``GhostStatus``).
GhostStatus = Literal["proposed", "approved", "in_progress", "shipped"]

#: Pin mode — QA assertion vs training-onboarding step (§4.2 ``PinMode``).
PinMode = Literal["qa", "training"]

#: Verification outcome (§4.2 ``VerifyResult``).
VerifyResult = Literal["verified", "broken", "skip"]

#: Active role slugs per migration 168 (2026-02-11). Mirrors ``RoleSlug``
#: TS union. Kept as a string Literal rather than an Enum so both JSON
#: wire values and Python type checks stay identical to TS.
RoleSlug = Literal[
    "admin",
    "top_manager",
    "head_of_sales",
    "head_of_procurement",
    "head_of_logistics",
    "sales",
    "quote_controller",
    "spec_controller",
    "finance",
    "procurement",
    "procurement_senior",
    "logistics",
    "customs",
]


# ---------------------------------------------------------------------------
# 2. Base model — shared config for every journey DTO
# ---------------------------------------------------------------------------


class JourneyBaseModel(BaseModel):
    """Shared Pydantic v2 config for every model in this module.

    - ``extra="forbid"`` — reject unknown fields on incoming requests so
      client drift surfaces immediately (Postel's Law — strict servers).
    - ``frozen=True`` — models are value objects; mutations should produce
      new instances (aligns with TS ``readonly`` fields and
      ``.claude/rules/common/coding-style.md`` immutability rule).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# 3. Envelope models — Req 16.4
# ---------------------------------------------------------------------------

T = TypeVar("T")


class JourneyErrorBody(JourneyBaseModel):
    """The ``error`` sub-object inside an error envelope."""

    code: str = Field(
        ...,
        description=(
            "UPPER_SNAKE_CASE machine-readable error code "
            "(e.g. 'STALE_VERSION', 'FORBIDDEN_FIELD', 'NOT_FOUND')."
        ),
    )
    message: str = Field(
        ...,
        description="Human-readable description (for logs and fallback UI).",
    )


class JourneySuccessEnvelope(JourneyBaseModel, Generic[T]):
    """Standard success envelope ``{success: true, data: T}`` (Req 16.4).

    Wave 4 handlers parameterise this generic with their own payload model,
    e.g. ``JourneySuccessEnvelope[NodeListData]``.
    """

    success: Literal[True] = Field(
        default=True,
        description="Always ``true`` on success envelopes.",
    )
    data: T = Field(..., description="Endpoint-specific payload.")


class JourneyErrorEnvelope(JourneyBaseModel):
    """Standard error envelope ``{success: false, error: {code, message}}``."""

    success: Literal[False] = Field(
        default=False,
        description="Always ``false`` on error envelopes.",
    )
    error: JourneyErrorBody = Field(
        ...,
        description="Structured error details (machine + human).",
    )


# ---------------------------------------------------------------------------
# 4. Domain DTOs — stubs for Wave 4 endpoints to extend
# ---------------------------------------------------------------------------


class JourneyNodeState(JourneyBaseModel):
    """Current impl/qa status for a node.

    Mirrors ``kvota.journey_node_state`` rows and the TS ``JourneyNodeState``
    interface (§4.2). The ``version`` column supports optimistic-concurrency
    control on PATCH (returns 409 ``STALE_VERSION`` when stale — see Wave 4
    Task 12).
    """

    node_id: NodeId = Field(..., description="Stable node identifier (app:/ghost:).")
    impl_status: ImplStatus | None = Field(
        default=None,
        description="Implementation status; null until first recorded.",
    )
    qa_status: QaStatus | None = Field(
        default=None,
        description="QA status; null until first recorded.",
    )
    notes: str | None = Field(
        default=None,
        description="Free-form notes (Markdown allowed; UI renders sanitised).",
    )
    version: int = Field(
        ...,
        ge=0,
        description="Monotonic version counter. Clients echo on PATCH for concurrency.",
    )
    last_tested_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of last QA verification, if any.",
    )
    updated_at: str = Field(..., description="ISO-8601 timestamp of last update.")
    updated_by: str | None = Field(
        default=None,
        description="``auth.users.id`` of last editor, if known.",
    )


class JourneyPin(JourneyBaseModel):
    """QA or training pin anchored to a DOM selector on a node screenshot.

    Mirrors ``kvota.journey_pins`` rows and the TS ``JourneyPin`` interface
    (§4.2). Position is stored as a relative bbox (``last_rel_*`` fractions
    in 0.0–1.0) so it survives viewport-size changes. Wave 4 Task 13 (the
    Playwright webhook) updates the bbox fields.
    """

    id: str = Field(..., description="UUID primary key.")
    node_id: NodeId = Field(..., description="Parent node.")
    selector: str = Field(
        ...,
        description="DOM selector (CSS or ``[data-testid=...]``) resolved by Playwright.",
    )
    expected_behavior: str = Field(
        ...,
        description="Short statement of what the pin asserts (visible to QA).",
    )
    mode: PinMode = Field(..., description="``qa`` or ``training``.")
    training_step_order: int | None = Field(
        default=None,
        ge=0,
        description="Order within a training sequence; null for QA pins.",
    )
    linked_story_ref: str | None = Field(
        default=None,
        description="Optional story ref from the manifest (e.g. 'phase-5b#3').",
    )
    last_rel_x: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Last-known horizontal position (fraction of screenshot width).",
    )
    last_rel_y: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Last-known vertical position (fraction of screenshot height).",
    )
    last_rel_width: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Last-known width fraction.",
    )
    last_rel_height: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Last-known height fraction.",
    )
    last_position_update: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of last Playwright bbox refresh.",
    )
    selector_broken: bool = Field(
        default=False,
        description="True if Playwright could not resolve the selector on last run.",
    )
    created_by: str = Field(..., description="``auth.users.id`` of creator.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")


class JourneyVerification(JourneyBaseModel):
    """One verification event recorded against a pin.

    Mirrors ``kvota.journey_verifications`` rows and the TS
    ``JourneyVerification`` interface (§4.2). Append-only — UPDATE and DELETE
    are denied by RLS for every role (see design.md §5).
    """

    id: str = Field(..., description="UUID primary key.")
    pin_id: str = Field(..., description="Pin being verified.")
    node_id: NodeId = Field(..., description="Parent node (denormalised from pin).")
    result: VerifyResult = Field(
        ...,
        description="``verified``, ``broken``, or ``skip``.",
    )
    note: str | None = Field(
        default=None,
        description="Optional free-form note (e.g. why ``broken``).",
    )
    attachment_urls: list[str] | None = Field(
        default=None,
        max_length=3,
        description=(
            "Up to 3 Supabase Storage object keys (bucket "
            "``journey-verification-attachments``). Resolved to signed URLs "
            "at render time. Null if no attachments."
        ),
    )
    tested_by: str = Field(..., description="``auth.users.id`` of verifier.")
    tested_at: str = Field(..., description="ISO-8601 verification timestamp.")


class JourneyFlowStep(JourneyBaseModel):
    """One step within a curated flow (§4.2 ``JourneyFlowStep``)."""

    node_id: NodeId = Field(..., description="Node this step points at.")
    action: str = Field(..., description="Short imperative verb phrase.")
    note: str = Field(..., description="Context sentence displayed above the node.")


class JourneyFlow(JourneyBaseModel):
    """Curated onboarding / QA / training flow.

    Mirrors ``kvota.journey_flows`` rows and the TS ``JourneyFlow`` interface
    (§4.2). Steps are embedded as JSON on the row.
    """

    id: str = Field(..., description="UUID primary key.")
    slug: str = Field(..., description="URL-safe unique identifier.")
    title: str = Field(..., description="Display title.")
    role: RoleSlug = Field(..., description="Primary persona role.")
    persona: str = Field(..., description="Free-form persona label (display only).")
    description: str = Field(..., description="Multi-sentence flow description.")
    est_minutes: int = Field(
        ...,
        ge=0,
        description="Estimated completion time in minutes.",
    )
    steps: list[JourneyFlowStep] = Field(
        ...,
        description="Ordered step list (JSONB array on the row).",
    )
    display_order: int = Field(
        ...,
        description="Sort index within a persona group in the sidebar.",
    )
    is_archived: bool = Field(
        default=False,
        description="Hidden from sidebar when true; row retained for history.",
    )


# ---------------------------------------------------------------------------
# 5. Scaffold ping — used by Task 9 tests and the scaffold stub endpoint
# ---------------------------------------------------------------------------


class JourneyPing(JourneyBaseModel):
    """Payload for the scaffold ``GET /api/journey/ping`` endpoint.

    Exists so Wave 4 tests can hit a real handler with a typed response
    before the aggregate/detail endpoints land. Safe to delete once
    ``/api/journey/nodes`` (Task 10) ships — but cheap to keep as a
    health-check.
    """

    status: Literal["ok"] = Field(
        default="ok",
        description="Liveness marker — always ``ok`` when router is mounted.",
    )


__all__ = [
    # primitives
    "NodeId",
    "ImplStatus",
    "QaStatus",
    "GhostStatus",
    "PinMode",
    "VerifyResult",
    "RoleSlug",
    # base / envelopes
    "JourneyBaseModel",
    "JourneyErrorBody",
    "JourneySuccessEnvelope",
    "JourneyErrorEnvelope",
    # DTOs
    "JourneyNodeState",
    "JourneyPin",
    "JourneyVerification",
    "JourneyFlow",
    "JourneyFlowStep",
    # scaffold
    "JourneyPing",
]
