"use client";

/**
 * QA verify-button row (Task 23 — Req 9.1–9.4).
 *
 * Rendered inside each QA pin's drawer row (see `pin-list-section.tsx`) and
 * inside the pin-popover on the annotated-screen overlay. Emits one INSERT
 * per click against `kvota.journey_verifications` (append-only — RLS denies
 * UPDATE and DELETE for every role, Req 9.2).
 *
 * Visibility is gated on {@link shouldShowVerifyButtons}: training-mode pins
 * never get verify buttons (Req 8 note 7), and only `admin` / `quote_controller`
 * / `spec_controller` may record verifications (Req 9.2 + `access.ts`).
 *
 * Broken-path UI: clicking the "Сломано" button reveals an inline note
 * textarea — the note is required (≥ 5 chars) because a bare "something
 * broke" entry is worthless for triage. The DB does NOT enforce this
 * (migration 500 lets `note` be null for all result values); UI enforcement
 * is the only gate. See Task 23 report — logged as debt.
 */

import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import {
  JOURNEY_QUERY_KEYS,
  createVerification,
  type JourneyNodeId,
  type JourneyPin,
  type RoleSlug,
  type VerifyResult,
} from "@/entities/journey";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import {
  buildVerificationPayload,
  classifyVerifyError,
  shouldShowVerifyButtons,
} from "./_verify-helpers";

const BROKEN_NOTE_MIN = 5;

export interface VerifyButtonsProps {
  readonly pin: JourneyPin;
  readonly nodeId: JourneyNodeId;
  readonly userId: string;
  readonly userRoles: readonly RoleSlug[];
}

export function VerifyButtons({
  pin,
  nodeId,
  userId,
  userRoles,
}: VerifyButtonsProps) {
  const qc = useQueryClient();
  const [submitting, setSubmitting] = useState<VerifyResult | null>(null);
  const [brokenOpen, setBrokenOpen] = useState(false);
  const [note, setNote] = useState("");

  if (!shouldShowVerifyButtons(pin, userRoles)) return null;

  const record = async (result: VerifyResult, rawNote?: string) => {
    setSubmitting(result);
    const payload = buildVerificationPayload({
      pinId: pin.id,
      nodeId,
      result,
      note: rawNote ?? null,
      testedBy: userId,
    });
    const { error } = await createVerification(payload);
    setSubmitting(null);
    if (error) {
      toast.error(classifyVerifyError(error).userMessage);
      return;
    }
    toast.success("Верификация записана");
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodeDetail(nodeId) });
    setBrokenOpen(false);
    setNote("");
  };

  const onBrokenSubmit = () => {
    if (note.trim().length < BROKEN_NOTE_MIN) return;
    void record("broken", note);
  };

  return (
    <div
      data-testid={`verify-buttons-${pin.id}`}
      className="flex flex-col gap-1.5"
    >
      <div className="flex flex-wrap gap-1.5">
        <Button
          size="sm"
          variant="outline"
          disabled={submitting !== null}
          onClick={() => void record("verified")}
          data-testid={`verify-btn-verified-${pin.id}`}
          className="border-success text-success hover:bg-success-subtle"
        >
          {submitting === "verified" ? "…" : "✓ Верифицировано"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={submitting !== null}
          onClick={() => setBrokenOpen((v) => !v)}
          data-testid={`verify-btn-broken-${pin.id}`}
          className="border-destructive text-destructive hover:bg-destructive/10"
        >
          ✗ Сломано
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={submitting !== null}
          onClick={() => void record("skip")}
          data-testid={`verify-btn-skip-${pin.id}`}
        >
          {submitting === "skip" ? "…" : "Пропустить"}
        </Button>
      </div>
      {brokenOpen && (
        <div
          data-testid={`verify-broken-note-${pin.id}`}
          className="flex flex-col gap-1"
        >
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Что сломано? (не менее 5 символов)"
            rows={2}
            className="text-xs"
          />
          <div className="flex gap-1.5">
            <Button
              size="sm"
              disabled={
                submitting !== null || note.trim().length < BROKEN_NOTE_MIN
              }
              onClick={onBrokenSubmit}
              data-testid={`verify-broken-submit-${pin.id}`}
            >
              {submitting === "broken" ? "Запись…" : "Записать"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={submitting !== null}
              onClick={() => {
                setBrokenOpen(false);
                setNote("");
              }}
            >
              Отмена
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
