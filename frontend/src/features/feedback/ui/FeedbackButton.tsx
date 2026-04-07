"use client";

import { useState, useEffect, useCallback } from "react";
import { Bug } from "lucide-react";
import { FeedbackModal } from "./FeedbackModal";
import { AnnotationEditor } from "./AnnotationEditor";
import { captureScreenshot } from "./ScreenshotCapture";
import { installErrorInterceptors } from "../lib/debugContext";

export function FeedbackButton() {
  const [modalOpen, setModalOpen] = useState(false);
  const [screenshotDataUrl, setScreenshotDataUrl] = useState<string>();
  const [annotatorOpen, setAnnotatorOpen] = useState(false);
  const [rawScreenshot, setRawScreenshot] = useState<string>();

  useEffect(() => {
    installErrorInterceptors();
  }, []);

  const handleScreenshotRequest = useCallback(async () => {
    setModalOpen(false);
    try {
      const dataUrl = await captureScreenshot();
      setRawScreenshot(dataUrl);
      setAnnotatorOpen(true);
    } catch (err) {
      console.error("[FeedbackWidget] Screenshot capture failed:", err);
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
        onClick={() => setModalOpen(true)}
        className="fixed bottom-4 right-4 z-50 w-11 h-11 flex items-center justify-center bg-card border border-border-light rounded-lg text-text-subtle hover:text-text-muted hover:border-border shadow-sm cursor-pointer transition-colors"
        title="Сообщить о проблеме"
        type="button"
      >
        <Bug size={20} />
      </button>

      <FeedbackModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onScreenshotRequest={handleScreenshotRequest}
        screenshotDataUrl={screenshotDataUrl}
        onClearScreenshot={handleClearScreenshot}
        onSetScreenshot={setScreenshotDataUrl}
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
