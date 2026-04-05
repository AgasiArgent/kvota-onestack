"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import type { QuoteStep } from "@/entities/quote/types";
import type { QuoteContextData } from "./context-panel/queries";
import { QuoteStickyHeader } from "./quote-sticky-header";
import { ContextPanel } from "./context-panel/context-panel";

const CONTEXT_PANEL_STORAGE_KEY = "context-panel-closed";
const CONTEXT_PANEL_MAX_ENTRIES = 100;

function isQuotePanelClosed(quoteId: string): boolean {
  try {
    const ids: string[] = JSON.parse(
      localStorage.getItem(CONTEXT_PANEL_STORAGE_KEY) ?? "[]"
    );
    return ids.includes(quoteId);
  } catch {
    return false;
  }
}

function persistQuotePanelClosed(quoteId: string, closed: boolean): void {
  try {
    let ids: string[] = JSON.parse(
      localStorage.getItem(CONTEXT_PANEL_STORAGE_KEY) ?? "[]"
    );
    ids = ids.filter((id) => id !== quoteId);
    if (closed) {
      ids.push(quoteId);
      if (ids.length > CONTEXT_PANEL_MAX_ENTRIES) {
        ids = ids.slice(-CONTEXT_PANEL_MAX_ENTRIES);
      }
    }
    localStorage.setItem(CONTEXT_PANEL_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // localStorage unavailable — silent fall-through
  }
}

interface QuoteDetailShellProps {
  quote: QuoteDetailRow;
  documentCount: number;
  activeStep: QuoteStep;
  userRoles: string[];
  contextData: QuoteContextData;
  stepContent: ReactNode;
  chat: ReactNode;
  rail: ReactNode;
}

/**
 * Client-side layout shell for the quote detail page. Owns the single piece
 * of cross-component state (context panel open/closed), composes the sticky
 * header with the panel in the left column (above step content), and keeps
 * the chat + status rail at their natural positions so the panel never shifts
 * them horizontally.
 */
export function QuoteDetailShell({
  quote,
  documentCount,
  activeStep,
  userRoles,
  contextData,
  stepContent,
  chat,
  rail,
}: QuoteDetailShellProps) {
  // Start with the panel expanded on SSR and initial client render to avoid
  // hydration mismatches (localStorage is not available on the server).
  // After mount, read the persisted preference and collapse if the user had
  // closed the panel for this specific quote. The setState-in-effect here is
  // intentional: we're bridging a browser-only API (localStorage) into React
  // state, which is the canonical SSR pattern and cannot be derived at render.
  const [isContextOpen, setIsContextOpen] = useState(true);

  useEffect(() => {
    if (isQuotePanelClosed(quote.id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsContextOpen(false);
    }
  }, [quote.id]);

  function handleToggleContext() {
    setIsContextOpen((prev) => {
      const next = !prev;
      persistQuotePanelClosed(quote.id, !next);
      return next;
    });
  }

  return (
    <div className="flex flex-col h-full">
      <QuoteStickyHeader
        quote={quote}
        documentCount={documentCount}
        activeStep={activeStep}
        userRoles={userRoles}
        isContextOpen={isContextOpen}
        onToggleContext={handleToggleContext}
      />
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          {isContextOpen && (
            <ContextPanel quote={quote} data={contextData} />
          )}
          {stepContent}
        </div>
        {chat}
        {rail}
      </div>
    </div>
  );
}
