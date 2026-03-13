"use client";

import { useState, useCallback } from "react";
import { Bug, Send, X, Camera } from "lucide-react";
import { submitFeedback, type FeedbackType } from "../api/submitFeedback";
import { collectDebugContext } from "../lib/debugContext";

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
  onScreenshotRequest: () => void;
  screenshotDataUrl?: string;
  onClearScreenshot: () => void;
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
}: FeedbackModalProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("bug");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    shortId?: string;
    error?: string;
  } | null>(null);

  const resetAndClose = useCallback(() => {
    setFeedbackType("bug");
    setDescription("");
    setResult(null);
    onClearScreenshot();
    onClose();
  }, [onClose, onClearScreenshot]);

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
            <Bug size={20} className="text-slate-500" />
            <h3 className="text-lg font-semibold text-slate-800">
              Обратная связь
            </h3>
          </div>
          <button
            onClick={resetAndClose}
            className="p-1 hover:bg-slate-100 rounded"
          >
            <X size={18} className="text-slate-400" />
          </button>
        </div>

        {result && (
          <div
            className={`mb-4 p-3 rounded-md ${
              result.success
                ? "bg-green-50 border border-green-200"
                : "bg-red-50 border border-red-200"
            }`}
          >
            {result.success ? (
              <>
                <p className="text-green-700 font-medium">
                  Спасибо за обратную связь!
                </p>
                <p className="text-sm text-green-600 font-mono mt-1">
                  Номер: {result.shortId}
                </p>
              </>
            ) : (
              <>
                <p className="text-red-700 font-medium">Ошибка при отправке</p>
                <p className="text-sm text-red-600 mt-1">
                  Попробуйте ещё раз через несколько секунд
                </p>
                <button
                  onClick={() => setResult(null)}
                  className="mt-2 text-sm text-red-700 underline hover:no-underline"
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
              <label className="text-xs font-medium text-slate-500 mb-1 block">
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
                        ? "bg-blue-50 border-blue-300 text-blue-700"
                        : "border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-3">
              <label className="text-xs font-medium text-slate-500 mb-1 block">
                Описание *
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Опишите проблему или предложение..."
                rows={4}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 resize-y"
                required
              />
            </div>

            <div className="mb-4">
              <label className="text-xs font-medium text-slate-500 mb-1 block">
                Скриншот
              </label>
              {screenshotDataUrl ? (
                <div className="relative inline-block">
                  <img
                    src={screenshotDataUrl}
                    alt="Screenshot"
                    className="max-h-32 rounded border border-slate-200"
                  />
                  <button
                    type="button"
                    onClick={onClearScreenshot}
                    className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-0.5"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={onScreenshotRequest}
                  className="flex items-center gap-2 px-3 py-2 text-sm border border-dashed border-slate-300 rounded-md text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors"
                >
                  <Camera size={16} />
                  Добавить скриншот
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting || !description.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-500 text-white rounded-md font-medium text-sm hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
