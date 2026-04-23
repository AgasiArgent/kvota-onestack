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
# 4b. Aggregated canvas-level DTO — Task 10 (GET /api/journey/nodes)
# ---------------------------------------------------------------------------


class JourneyNodeAggregated(JourneyBaseModel):
    """Canvas-level merged view of a node (manifest + state + counts).

    Returned by ``GET /api/journey/nodes`` — the primary data endpoint for
    the Journey canvas (design.md §4.4, §5.2, requirements.md Req 4.3–4.8).

    Data comes from three sources merged on ``node_id``:

    1. **Manifest** (``frontend/public/journey-manifest.json``, Task 7) —
       immutable route / cluster / title / roles / stories per node.
    2. **State** (``kvota.journey_node_state``) — mutable impl/qa status.
       Nodes with no state row surface with ``impl_status=None`` and
       ``qa_status=None`` per Req 4.4 ("grey=unset").
    3. **Ghost nodes** (``kvota.journey_ghost_nodes``) — planned-but-unshipped
       rows; they carry their own ``title``/``cluster``/``proposed_route``
       because they are absent from the manifest.

    Counts are scalar integers computed server-side so the canvas does not
    have to page through related rows:

    - ``stories_count`` — length of the manifest node's ``stories`` array
      (always 0 for ghost nodes: ghosts are not yet in code, so no story
      can reference them).
    - ``pins_count`` — count of ``kvota.journey_pins`` rows for this node.
    - ``feedback_count`` — count of ``kvota.user_feedback`` rows for this
      node *visible to the requesting user* (Req 4.6, 11.2 — admin sees all,
      non-admin sees only own submissions).
    """

    node_id: NodeId = Field(..., description="Stable node identifier (app: or ghost:).")
    route: str = Field(
        ...,
        description=(
            "Next.js route path for ``app:*`` nodes; ``proposed_route`` "
            "(possibly empty) for ``ghost:*`` nodes."
        ),
    )
    title: str = Field(..., description="Display title from manifest or ghost row.")
    cluster: str = Field(
        ...,
        description=(
            "Cluster slug. ``ghost`` for ghost rows without an explicit "
            "cluster; otherwise mirrors manifest ``cluster``."
        ),
    )
    roles: list[str] = Field(
        default_factory=list,
        description="RoleSlug[] from manifest (empty for ghost nodes).",
    )
    impl_status: ImplStatus | None = Field(
        default=None,
        description="Impl status from state row; null until first recorded.",
    )
    qa_status: QaStatus | None = Field(
        default=None,
        description="QA status from state row; null until first recorded.",
    )
    version: int = Field(
        default=0,
        ge=0,
        description=(
            "Current optimistic-concurrency version on ``journey_node_state``. "
            "Zero when no state row exists yet (client must treat as 0 on "
            "first PATCH)."
        ),
    )
    stories_count: int = Field(
        default=0,
        ge=0,
        description="Number of stories attached to the node in the manifest.",
    )
    feedback_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Count of ``kvota.user_feedback`` rows for this node visible to "
            "the requesting user under application-layer access rules "
            "(Req 11.2): admin sees all, non-admin sees only own."
        ),
    )
    pins_count: int = Field(
        default=0,
        ge=0,
        description="Count of ``kvota.journey_pins`` rows for this node.",
    )
    ghost_status: GhostStatus | None = Field(
        default=None,
        description="Only set for ``ghost:*`` nodes; mirrors ``journey_ghost_nodes.status``.",
    )
    proposed_route: str | None = Field(
        default=None,
        description=(
            "Only set for ``ghost:*`` nodes. The human-supplied draft route; "
            "may be null if the ghost was created without one."
        ),
    )
    updated_at: str | None = Field(
        default=None,
        description=(
            "ISO-8601 timestamp of the last state update (null if no state "
            "row exists for the node)."
        ),
    )


# ---------------------------------------------------------------------------
# 4c. Drawer-detail DTO — Task 11 (GET /api/journey/node/{node_id})
# ---------------------------------------------------------------------------


class JourneyFeedbackSummary(JourneyBaseModel):
    """Compact feedback row for the drawer's top-3 list.

    Mirrors the fields ``/admin/feedback`` surfaces in its list view. Not the
    full ``kvota.user_feedback`` row — attachments, full timeline metadata,
    and internal fields are fetched lazily by the drawer's "view all" link
    (Req 5.3 opens ``/admin/feedback?node_id=...`` in a new tab).
    """

    id: str = Field(..., description="UUID primary key of the feedback row.")
    short_id: str | None = Field(
        default=None,
        description="Short human-readable ID (e.g. ``FB-240421-152311-abc1``).",
    )
    node_id: NodeId | None = Field(
        default=None,
        description="Node this feedback targets (may be null for legacy rows).",
    )
    user_id: str | None = Field(
        default=None,
        description="``auth.users.id`` of the submitter, if recorded.",
    )
    description: str | None = Field(
        default=None,
        description="User-submitted description text.",
    )
    feedback_type: str | None = Field(
        default=None,
        description="Free-form type label (``bug``, ``improvement``, ...).",
    )
    status: str | None = Field(
        default=None,
        description="Lifecycle status (``new`` / ``triaged`` / ``done`` / ...).",
    )
    created_at: str | None = Field(
        default=None,
        description="ISO-8601 creation timestamp.",
    )


class JourneyNodeDetail(JourneyBaseModel):
    """Full drawer payload for a single node (Req 5.1, design.md §4.4).

    Composes five sources merged on ``node_id``:

    1. **Manifest / ghost row** — route / title / cluster / roles / stories.
    2. **State** — impl/qa status, version, notes, updated_at. Absent row →
       status fields are ``None`` and ``version=0``.
    3. **Pins** — every ``kvota.journey_pins`` row for this node (QA +
       training). The drawer filters/splits client-side.
    4. **Latest verification per pin** — map ``{pin_id: JourneyVerification}``.
       Pins with no verification are simply absent from the map; the drawer
       renders those as "untested".
    5. **Feedback top-3** — ``JourneyFeedbackSummary[]`` ordered by
       ``created_at`` DESC, filtered by application-layer visibility
       (Req 11.2 — admin sees all, others see own). The full list is
       reachable via the drawer's "view all" link.

    Ghost nodes supply their own ``title`` / ``cluster`` / ``proposed_route``
    (they are absent from the manifest) and expose ``ghost_status``. Pin /
    verification sections remain queryable for ghosts but will typically be
    empty (Req 5.2 hides screenshots/pins in the UI for ghosts).
    """

    node_id: NodeId = Field(..., description="Stable node identifier.")
    route: str = Field(..., description="Route path (or proposed route for ghosts).")
    title: str = Field(..., description="Display title.")
    cluster: str = Field(..., description="Cluster slug.")
    roles: list[str] = Field(
        default_factory=list,
        description="RoleSlug[] from manifest (empty for ghost nodes).",
    )
    stories_count: int = Field(
        default=0,
        ge=0,
        description="Number of stories attached in the manifest.",
    )
    impl_status: ImplStatus | None = Field(
        default=None,
        description="Impl status from state row; null until first recorded.",
    )
    qa_status: QaStatus | None = Field(
        default=None,
        description="QA status from state row; null until first recorded.",
    )
    version: int = Field(
        default=0,
        ge=0,
        description="Current optimistic-concurrency version (0 when no state row).",
    )
    notes: str | None = Field(
        default=None,
        description="Free-form state notes (Markdown rendered sanitised by UI).",
    )
    updated_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of the last state update.",
    )
    ghost_status: GhostStatus | None = Field(
        default=None,
        description="Only set for ``ghost:*`` nodes.",
    )
    proposed_route: str | None = Field(
        default=None,
        description="Only set for ``ghost:*`` nodes.",
    )
    pins: list[JourneyPin] = Field(
        default_factory=list,
        description="Every pin anchored to this node (QA + training).",
    )
    verifications_by_pin: dict[str, JourneyVerification] = Field(
        default_factory=dict,
        description=(
            "Latest verification per pin, keyed by ``pin_id``. Pins without "
            "a verification are absent from the map."
        ),
    )
    feedback: list[JourneyFeedbackSummary] = Field(
        default_factory=list,
        description=(
            "Top-3 visible feedback rows for this node, ordered by "
            "``created_at`` DESC. Filtered by the same admin/non-admin rule "
            "as ``feedback_count`` on the canvas endpoint (Req 11.2)."
        ),
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
    "JourneyNodeAggregated",
    "JourneyFeedbackSummary",
    "JourneyNodeDetail",
    # scaffold
    "JourneyPing",
]
