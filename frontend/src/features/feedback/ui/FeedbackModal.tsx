"use client";

import { useState, useCallback, useRef } from "react";
import { Bug, Send, X, Camera, Paperclip } from "lucide-react";
import { SearchableCombobox } from "@/shared/ui";
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

interface FeedbackTypeOption {
  id: FeedbackType;
  label: string;
}

const FEEDBACK_TYPES: FeedbackTypeOption[] = [
  { id: "bug", label: "Ошибка" },
  { id: "ux_ui", label: "UX / UI" },
  { id: "suggestion", label: "Предложение" },
  { id: "question", label: "Вопрос" },
];

const TEXTAREA_CLASS =
  "w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent resize-y min-h-[72px] max-h-[240px]";

type FieldKey = "stepsTaken" | "actualResult";

export function FeedbackModal({
  open,
  onClose,
  onScreenshotRequest,
  screenshotDataUrl,
  onClearScreenshot,
  onSetScreenshot,
}: FeedbackModalProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("bug");
  const [stepsTaken, setStepsTaken] = useState("");
  const [expectedResult, setExpectedResult] = useState("");
  const [actualResult, setActualResult] = useState("");
  const [missing, setMissing] = useState<Set<FieldKey>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    shortId?: string;
    error?: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetAndClose = useCallback(() => {
    setFeedbackType("bug");
    setStepsTaken("");
    setExpectedResult("");
    setActualResult("");
    setMissing(new Set());
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
    // Validate required fields: «Что делал» + «Что получил». Name + highlight
    // every missing field (no silent failures — project rule).
    const nextMissing = new Set<FieldKey>();
    if (!stepsTaken.trim()) nextMissing.add("stepsTaken");
    if (!actualResult.trim()) nextMissing.add("actualResult");
    setMissing(nextMissing);
    if (nextMissing.size > 0) return;

    setSubmitting(true);
    setResult(null);

    const debugContext = collectDebugContext();
    const res = await submitFeedback({
      feedbackType,
      stepsTaken: stepsTaken.trim(),
      expectedResult: expectedResult.trim(),
      actualResult: actualResult.trim(),
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
  }, [
    feedbackType,
    stepsTaken,
    expectedResult,
    actualResult,
    screenshotDataUrl,
    resetAndClose,
  ]);

  const clearMissing = useCallback((field: FieldKey) => {
    setMissing((prev) => {
      if (!prev.has(field)) return prev;
      const next = new Set(prev);
      next.delete(field);
      return next;
    });
  }, []);

  if (!open) return null;

  const missingLabels: string[] = [];
  if (missing.has("stepsTaken")) missingLabels.push("Что делал");
  if (missing.has("actualResult")) missingLabels.push("Что получил");

  const canSubmit = stepsTaken.trim().length > 0 && actualResult.trim().length > 0;

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
              <SearchableCombobox<FeedbackTypeOption>
                value={feedbackType}
                onChange={(id) => {
                  if (id) setFeedbackType(id as FeedbackType);
                }}
                items={FEEDBACK_TYPES}
                getLabel={(t) => t.label}
                clearable={false}
                ariaLabel="Тип обращения"
                searchPlaceholder="Поиск типа…"
                popoverWidthClass="w-72"
                className="w-72 max-w-full"
              />
            </div>

            <div className="mb-3">
              <label
                htmlFor="feedback-steps-taken"
                className="text-xs font-medium text-text-muted mb-1 block"
              >
                Что делал *
              </label>
              <textarea
                id="feedback-steps-taken"
                value={stepsTaken}
                onChange={(e) => {
                  setStepsTaken(e.target.value);
                  clearMissing("stepsTaken");
                }}
                placeholder="Опишите ваши действия…"
                rows={3}
                aria-invalid={missing.has("stepsTaken")}
                className={`${TEXTAREA_CLASS} ${
                  missing.has("stepsTaken")
                    ? "border-error focus:border-error focus:ring-error/20"
                    : "border-border"
                }`}
              />
            </div>

            <div className="mb-3">
              <label
                htmlFor="feedback-expected-result"
                className="text-xs font-medium text-text-muted mb-1 block"
              >
                Что ожидал получить
              </label>
              <textarea
                id="feedback-expected-result"
                value={expectedResult}
                onChange={(e) => setExpectedResult(e.target.value)}
                placeholder="Какого результата вы ожидали…"
                rows={3}
                className={`${TEXTAREA_CLASS} border-border`}
              />
            </div>

            <div className="mb-4">
              <label
                htmlFor="feedback-actual-result"
                className="text-xs font-medium text-text-muted mb-1 block"
              >
                Что получил *
              </label>
              <textarea
                id="feedback-actual-result"
                value={actualResult}
                onChange={(e) => {
                  setActualResult(e.target.value);
                  clearMissing("actualResult");
                }}
                placeholder="Что произошло на самом деле…"
                rows={3}
                aria-invalid={missing.has("actualResult")}
                className={`${TEXTAREA_CLASS} ${
                  missing.has("actualResult")
                    ? "border-error focus:border-error focus:ring-error/20"
                    : "border-border"
                }`}
              />
            </div>

            {missingLabels.length > 0 && (
              <p role="alert" className="mb-3 text-sm text-error">
                Заполните обязательные поля: {missingLabels.join(", ")}.
              </p>
            )}

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
              disabled={submitting || !canSubmit}
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
