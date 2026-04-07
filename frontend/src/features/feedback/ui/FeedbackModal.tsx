"use client";

import { useState, useCallback, useRef } from "react";
import { Bug, Send, X, Camera, Paperclip } from "lucide-react";
import { submitFeedback, type FeedbackType } from "../api/submitFeedback";
import { collectDebugContext } from "../lib/debugContext";

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
  onScreenshotRequest: () => void;
  screenshotDataUrl?: string;
  onClearScreenshot: () => void;
  onSetScreenshot: (dataUrl: string) => void;
}

const FEEDBACK_TYPES: { value: FeedbackType; label: string }[] = [
  { value: "bug", label: "Ошибка" },
  { value: "ux_ui", label: "UX / UI" },
  { value: "suggestion", label: "Предложение" },
  { value: "question", label: "Вопрос" },
];

export function FeedbackModal({
  open,
  onClose,
  onScreenshotRequest,
  screenshotDataUrl,
  onClearScreenshot,
  onSetScreenshot,
}: FeedbackModalProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("bug");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    shortId?: string;
    error?: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetAndClose = useCallback(() => {
    setFeedbackType("bug");
    setDescription("");
    setResult(null);
    onClearScreenshot();
    onClose();
  }, [onClose, onClearScreenshot]);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          onSetScreenshot(reader.result);
        }
      };
      reader.readAsDataURL(file);
      // Reset input so the same file can be re-selected
      e.target.value = "";
    },
    [onSetScreenshot]
  );

  const handleSubmit = useCallback(async () => {
    if (!description.trim()) return;
    setSubmitting(true);
    setResult(null);

    const debugContext = collectDebugContext();
    const res = await submitFeedback({
      feedbackType,
      description: description.trim(),
      pageUrl: debugContext.url,
      pageTitle: debugContext.title,
      debugContext,
      screenshotDataUrl,
    });

    setSubmitting(false);

    if (res.success) {
      setResult(res);
      setTimeout(resetAndClose, 2000);
    } else {
      setResult(res);
    }
  }, [feedbackType, description, screenshotDataUrl, resetAndClose]);

  if (!open) return null;

  return (
    <>
      <div
        className="feedback-overlay fixed inset-0 bg-black/40 z-[999]"
        onClick={resetAndClose}
      />
      <div
        id="feedback-modal"
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl p-6 z-[1000] w-[90%] max-w-2xl max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Bug size={20} className="text-text-muted" />
            <h3 className="text-lg font-semibold text-text">
              Обратная связь
            </h3>
          </div>
          <button
            onClick={resetAndClose}
            className="p-1 hover:bg-sidebar rounded"
          >
            <X size={18} className="text-text-subtle" />
          </button>
        </div>

        {result && (
          <div
            className={`mb-4 p-3 rounded-md ${
              result.success
                ? "bg-success-bg border border-success/30"
                : "bg-error-bg border border-error/30"
            }`}
          >
            {result.success ? (
              <>
                <p className="text-success font-medium">
                  Спасибо за обратную связь!
                </p>
                <p className="text-sm text-success font-mono mt-1">
                  Номер: {result.shortId}
                </p>
              </>
            ) : (
              <>
                <p className="text-error font-medium">Ошибка при отправке</p>
                <p className="text-sm text-error mt-1">
                  Попробуйте ещё раз через несколько секунд
                </p>
                <button
                  onClick={() => setResult(null)}
                  className="mt-2 text-sm text-error underline hover:no-underline"
                >
                  Попробовать снова
                </button>
              </>
            )}
          </div>
        )}

        {!result?.success && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
          >
            <div className="mb-3">
              <label className="text-xs font-medium text-text-muted mb-1 block">
                Тип
              </label>
              <div className="flex gap-2 flex-wrap">
                {FEEDBACK_TYPES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setFeedbackType(t.value)}
                    className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                      feedbackType === t.value
                        ? "bg-accent-subtle border-accent/50 text-accent"
                        : "border-border text-text-muted hover:bg-sidebar"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-3">
              <label className="text-xs font-medium text-text-muted mb-1 block">
                Описание *
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Опишите проблему или предложение..."
                rows={4}
                className="w-full px-3 py-2 text-sm border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent resize-y min-h-[100px] max-h-[300px]"
                required
              />
            </div>

            <div className="mb-4">
              <label className="text-xs font-medium text-text-muted mb-1 block">
                Скриншот
              </label>
              {screenshotDataUrl ? (
                <div className="relative inline-block">
                  <img
                    src={screenshotDataUrl}
                    alt="Screenshot"
                    className="max-h-32 rounded border border-border-light"
                  />
                  <button
                    type="button"
                    onClick={onClearScreenshot}
                    className="absolute -top-2 -right-2 bg-error text-white rounded-full p-0.5"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={onScreenshotRequest}
                    className="flex items-center gap-2 px-3 py-2 text-sm border border-dashed border-border rounded-md text-text-muted hover:bg-sidebar hover:text-text transition-colors"
                  >
                    <Camera size={16} />
                    Снимок экрана
                  </button>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-2 px-3 py-2 text-sm border border-dashed border-border rounded-md text-text-muted hover:bg-sidebar hover:text-text transition-colors"
                  >
                    <Paperclip size={16} />
                    Прикрепить файл
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting || !description.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-white rounded-md font-medium text-sm hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? (
                <span className="animate-spin h-4 w-4 border-2 border-white/30 border-t-white rounded-full" />
              ) : (
                <Send size={16} />
              )}
              {submitting ? "Отправка..." : "Отправить"}
            </button>
          </form>
        )}
      </div>
    </>
  );
}
