"use client";

import { useState, useCallback, useEffect } from "react";
import type { QuoteComment } from "@/entities/quote/types";
import type { OrgMember } from "./chat-input";
import { ChatFab } from "./chat-fab";
import { ChatPanel } from "./chat-panel";

interface ChatWrapperProps {
  quoteId: string;
  idnQuote: string;
  userId: string;
  orgId: string;
  initialComments: QuoteComment[];
  orgMembers?: OrgMember[];
}

export function ChatWrapper({
  quoteId,
  idnQuote,
  userId,
  orgId,
  initialComments,
  orgMembers,
}: ChatWrapperProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    document.documentElement.setAttribute("data-chat-open", String(isOpen));
    return () => document.documentElement.removeAttribute("data-chat-open");
  }, [isOpen]);

  const toggleChat = useCallback(() => {
    setIsOpen((prev) => {
      if (!prev) {
        // Opening — clear unread
        setUnreadCount(0);
      }
      return !prev;
    });
  }, []);

  const closeChat = useCallback(() => {
    setIsOpen(false);
  }, []);

  // Track new messages for unread badge (when panel is closed)
  const handleNewMessage = useCallback(() => {
    setIsOpen((open) => {
      if (!open) {
        setUnreadCount((c) => c + 1);
      }
      return open;
    });
  }, []);

  return (
    <>
      {!isOpen && (
        <ChatFab unreadCount={unreadCount} onClick={toggleChat} />
      )}
      <ChatPanel
        isOpen={isOpen}
        onClose={closeChat}
        quoteId={quoteId}
        idnQuote={idnQuote}
        userId={userId}
        orgId={orgId}
        initialComments={initialComments}
        onNewMessage={handleNewMessage}
        orgMembers={orgMembers}
      />
    </>
  );
}
