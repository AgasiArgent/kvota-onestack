"use client";

/**
 * DOM picker (Task 21 — Req 8.5b).
 *
 * Loads the target route in a same-origin iframe and listens for clicks
 * inside it. On click, derives a stable selector via `selectorFromElement`
 * and passes it up to the caller.
 *
 * Practical caveats (flagged for Task 22/23 to harden):
 *   - Same-origin is REQUIRED: the parent cannot read `contentDocument` of
 *     a cross-origin iframe. Today both `/journey` and the targeted routes
 *     live on the same Next.js origin, so this works in dev and prod.
 *   - CSP `frame-ancestors`: if the prod Caddy config emits an aggressive
 *     `Content-Security-Policy` on the target route, the iframe may fail
 *     to load. The picker handles this gracefully — the user can still
 *     enter a selector manually. Monitoring/fix tracked in Task 22.
 *   - If `contentDocument` is null (CSP block / cross-origin), we show an
 *     inline error and keep the dialog open so the user can type manually.
 */

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { selectorFromElement } from "@/features/journey/lib/selector-from-element";

interface Props {
  readonly targetRoute: string;
  readonly onPick: (selector: string) => void;
  readonly onCancel: () => void;
}

const HIGHLIGHT_CLASS = "__journey-picker-highlight";

export function DomPicker({ targetRoute, onPick, onCancel }: Props) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const onLoad = () => {
      const doc = iframe.contentDocument;
      if (!doc) {
        setBlocked(true);
        return;
      }

      // Inject highlight stylesheet into the iframe.
      const style = doc.createElement("style");
      style.textContent = `
        .${HIGHLIGHT_CLASS} {
          outline: 2px dashed #3b82f6 !important;
          outline-offset: 2px !important;
          cursor: crosshair !important;
        }
      `;
      doc.head.appendChild(style);

      let current: Element | null = null;
      const onOver = (e: Event) => {
        const t = e.target as Element | null;
        if (!t) return;
        if (current) current.classList.remove(HIGHLIGHT_CLASS);
        current = t;
        t.classList.add(HIGHLIGHT_CLASS);
      };
      const onClick = (e: Event) => {
        e.preventDefault();
        e.stopPropagation();
        const target = e.target as Element | null;
        const selector = selectorFromElement(target);
        if (selector) onPick(selector);
      };

      doc.addEventListener("mouseover", onOver, true);
      doc.addEventListener("click", onClick, true);

      return () => {
        doc.removeEventListener("mouseover", onOver, true);
        doc.removeEventListener("click", onClick, true);
        if (current) current.classList.remove(HIGHLIGHT_CLASS);
      };
    };

    iframe.addEventListener("load", onLoad);
    return () => iframe.removeEventListener("load", onLoad);
  }, [onPick]);

  return (
    <div
      data-testid="dom-picker-overlay"
      className="fixed inset-0 z-[100] flex flex-col bg-black/60"
      role="dialog"
      aria-label="DOM picker"
    >
      <div className="flex items-center justify-between border-b border-border-light bg-sidebar px-4 py-2">
        <p className="text-xs text-text">
          Кликните на элемент на странице:{" "}
          <code className="font-mono">{targetRoute}</code>
        </p>
        <Button variant="outline" onClick={onCancel} size="sm">
          Отмена
        </Button>
      </div>

      {blocked ? (
        <div className="flex flex-1 items-center justify-center bg-background p-4 text-center text-xs text-text-muted">
          Не удалось открыть страницу во фрейме. Возможно, включён CSP
          frame-ancestors. Введите селектор вручную.
        </div>
      ) : (
        <iframe
          ref={iframeRef}
          src={targetRoute}
          className="h-full w-full flex-1 bg-white"
          title="DOM picker"
          data-testid="dom-picker-iframe"
        />
      )}
    </div>
  );
}
