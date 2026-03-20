"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuoteComment } from "@/entities/quote/types";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { useRealtimeComments } from "./use-realtime-comments";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  quoteId: string;
  idnQuote: string;
  userId: string;
  initialComments: QuoteComment[];
}

export function ChatPanel({
  isOpen,
  onClose,
  quoteId,
  idnQuote,
  userId,
  initialComments,
}: ChatPanelProps) {
  const { messages, sendMessage, isConnected } = useRealtimeComments(
    quoteId,
    userId,
    initialComments
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wasOpenRef = useRef(false);

  // Auto-scroll to bottom on new messages or when panel opens
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: wasOpenRef.current ? "smooth" : "instant" });
    }
    wasOpenRef.current = isOpen;
  }, [isOpen, messages.length]);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/10 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-[380px] max-w-[calc(100vw-48px)]",
          "bg-background border-l border-border shadow-xl",
          "flex flex-col",
          "transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-background">
          <div className="flex items-center gap-2 min-w-0">
            <h3 className="text-sm font-semibold truncate">
              {"Чат по "}{idnQuote}
            </h3>
            <span
              className={cn(
                "flex-shrink-0 w-2 h-2 rounded-full",
                isConnected ? "bg-green-500" : "bg-gray-300"
              )}
              title={isConnected ? "Подключено" : "Нет соединения"}
            />
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            aria-label="Закрыть чат"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto py-3">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full px-6">
              <p className="text-sm text-muted-foreground text-center">
                Нет сообщений. Начните обсуждение по этой коммерческой предложению.
              </p>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  comment={msg}
                  isOwn={msg.user_id === userId}
                />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input */}
        <ChatInput onSend={sendMessage} />
      </div>
    </>
  );
}
