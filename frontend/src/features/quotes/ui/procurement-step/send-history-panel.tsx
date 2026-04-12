"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, FileSpreadsheet, Mail } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { fetchSendHistory, type LetterDraft } from "@/entities/invoice/queries";

const dateFmt = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

interface SendHistoryPanelProps {
  invoiceId: string;
}

export function SendHistoryPanel({ invoiceId }: SendHistoryPanelProps) {
  const [history, setHistory] = useState<LetterDraft[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetchSendHistory(invoiceId).then(setHistory);
  }, [invoiceId]);

  if (history.length === 0) return null;

  return (
    <div className="border-b border-border">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-4 py-2 flex items-center gap-2 text-left hover:bg-muted/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-muted-foreground" />
        ) : (
          <ChevronRight size={14} className="text-muted-foreground" />
        )}
        <span className="text-xs font-medium text-muted-foreground">
          История отправок ({history.length})
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-2 space-y-1">
          {history.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <span className="tabular-nums shrink-0">
                {entry.sent_at
                  ? dateFmt.format(new Date(entry.sent_at))
                  : dateFmt.format(new Date(entry.created_at))}
              </span>

              {entry.method === "xls_download" ? (
                <Badge variant="outline" className="text-xs gap-1 py-0">
                  <FileSpreadsheet size={10} />
                  XLS
                </Badge>
              ) : (
                <Badge variant="outline" className="text-xs gap-1 py-0">
                  <Mail size={10} />
                  Письмо
                </Badge>
              )}

              <Badge variant="secondary" className="text-xs py-0 uppercase">
                {entry.language}
              </Badge>

              {entry.method === "xls_download" ? (
                <span>Отправлено через скачивание XLS</span>
              ) : (
                <span className="truncate">{entry.subject}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
