"use client";

import { useState, useCallback } from "react";
import type { QuoteComment } from "@/entities/quote/types";
import { ChatFab } from "./chat-fab";
import { ChatPanel } from "./chat-panel";

interface ChatWrapperProps {
  quoteId: string;
  idnQuote: string;
  userId: string;
  initialComments: QuoteComment[];
}

export function ChatWrapper({
  quoteId,
  idnQuote,
  userId,
  initialComments,
}: ChatWrapperProps) {
  const [isOpen, setIsOpen] = useState(false);

  const toggleChat = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const closeChat = useCallback(() => {
    setIsOpen(false);
  }, []);

  return (
    <>
      {!isOpen && (
        <ChatFab unreadCount={0} onClick={toggleChat} />
      )}
      <ChatPanel
        isOpen={isOpen}
        onClose={closeChat}
        quoteId={quoteId}
        idnQuote={idnQuote}
        userId={userId}
        initialComments={initialComments}
      />
    </>
  );
}
