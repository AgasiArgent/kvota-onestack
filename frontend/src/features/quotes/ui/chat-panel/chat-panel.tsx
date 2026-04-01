"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuoteComment } from "@/entities/quote/types";
import type { OrgMember } from "./chat-input";
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
  onNewMessage?: () => void;
  orgMembers?: OrgMember[];
}

export function ChatPanel({
  isOpen,
  onClose,
  quoteId,
  idnQuote,
  userId,
  initialComments,
  onNewMessage,
  orgMembers,
}: ChatPanelProps) {
  const { messages, sendMessage, isConnected } = useRealtimeComments(
    quoteId,
    userId,
    initialComments,
    onNewMessage
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

  if (!isOpen) return null;

  return (
    <div
      className={cn(
        "fixed top-0 right-0 z-50",
        "w-[340px] h-full",
        "bg-background border-l border-border shadow-lg",
        "flex flex-col"
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
              Нет сообщений. Начните обсуждение.
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
      <ChatInput onSend={sendMessage} orgMembers={orgMembers} />
    </div>
  );
}
