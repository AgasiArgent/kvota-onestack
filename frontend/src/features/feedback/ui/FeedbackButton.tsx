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
    } catch {
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
        className="fixed bottom-4 right-4 z-50 w-16 h-16 flex items-center justify-center bg-white border border-slate-200 rounded-lg text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-md cursor-pointer transition-colors"
        title="Сообщить о проблеме"
        type="button"
      >
        <Bug size={36} />
      </button>

      <FeedbackModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onScreenshotRequest={handleScreenshotRequest}
        screenshotDataUrl={screenshotDataUrl}
        onClearScreenshot={handleClearScreenshot}
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
