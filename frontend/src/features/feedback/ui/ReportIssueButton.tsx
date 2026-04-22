"use client";

import { useCallback, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { FeedbackModal } from "./FeedbackModal";
import { AnnotationEditor } from "./AnnotationEditor";
import { captureScreenshot } from "./ScreenshotCapture";

interface ReportIssueButtonProps {
  /**
   * Journey node id that will be attached to the submitted feedback.
   * Must be the manifest/ghost identifier, e.g. `app:/quotes/[id]`.
   */
  nodeId: string;
  /** Visual override — the drawer may want a tighter chip, the dashboard a full CTA. */
  className?: string;
  /** Optional text override (defaults to "Сообщить о проблеме"). */
  label?: string;
}

/**
 * "Report issue" CTA rendered inside the /journey drawer and anywhere else
 * that knows its current node id. Opens the shared `FeedbackModal` with the
 * node id preset so the resulting row on `kvota.user_feedback` carries the
 * link back to the journey node.
 *
 * Parallel to the floating `<FeedbackButton />` widget but:
 *   - Fixed at the call-site (not a page-global FAB).
 *   - Always carries a `nodeId`.
 *   - Caller decides the trigger label/icon via props.
 *
 * Req 11.1 b-half — new feedback from within /journey carries node_id.
 */
export function ReportIssueButton({
  nodeId,
  className,
  label = "Сообщить о проблеме",
}: ReportIssueButtonProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [screenshotDataUrl, setScreenshotDataUrl] = useState<string>();
  const [annotatorOpen, setAnnotatorOpen] = useState(false);
  const [rawScreenshot, setRawScreenshot] = useState<string>();

  const handleScreenshotRequest = useCallback(async () => {
    setModalOpen(false);
    try {
      const dataUrl = await captureScreenshot();
      setRawScreenshot(dataUrl);
      setAnnotatorOpen(true);
    } catch (err) {
      console.error("[ReportIssueButton] Screenshot capture failed:", err);
      setModalOpen(true);
    }
  }, []);

  const handleAnnotationSave = useCallback((annotatedDataUrl: string) => {
    setScreenshotDataUrl(annotatedDataUrl);
    setAnnotatorOpen(false);
    setRawScreenshot(undefined);
    setModalOpen(true);
  }, []);

  const handleAnnotationCancel = useCallback(() => {
    setAnnotatorOpen(false);
    setRawScreenshot(undefined);
    setModalOpen(true);
  }, []);

  const handleClearScreenshot = useCallback(() => {
    setScreenshotDataUrl(undefined);
  }, []);

  return (
    <>
      <button
        type="button"
        data-testid="report-issue-button"
        data-node-id={nodeId}
        onClick={() => setModalOpen(true)}
        className={
          className ??
          "inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-border text-text-muted hover:bg-sidebar hover:text-text transition-colors"
        }
        title={label}
      >
        <AlertTriangle size={14} />
        {label}
      </button>

      <FeedbackModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onScreenshotRequest={handleScreenshotRequest}
        screenshotDataUrl={screenshotDataUrl}
        onClearScreenshot={handleClearScreenshot}
        onSetScreenshot={setScreenshotDataUrl}
        nodeId={nodeId}
      />

      {annotatorOpen && rawScreenshot && (
        <AnnotationEditor
          screenshotDataUrl={rawScreenshot}
          onSave={handleAnnotationSave}
          onCancel={handleAnnotationCancel}
        />
      )}
    </>
  );
}
