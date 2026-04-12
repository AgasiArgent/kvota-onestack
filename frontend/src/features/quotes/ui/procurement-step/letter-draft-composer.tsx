"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  fetchActiveLetterDraft,
  type LetterDraft,
} from "@/entities/invoice/queries";
import {
  saveLetterDraft,
  sendLetterDraft,
} from "@/entities/invoice/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Russian letter template (mirrors services/letter_templates.py)
// ---------------------------------------------------------------------------

const LETTER_TEMPLATE_RU = `Уважаемый {greeting},

Прошу рассмотреть возможность поставки следующих позиций:

{items_list}

Условия поставки: {incoterms}
Страна назначения: {delivery_country}
Валюта: {currency}

Подробная спецификация во вложении.
Пожалуйста, предоставьте ваши цены и сроки поставки.

С уважением,
{sender_name}
{sender_email}
{sender_phone}`;

const SUBJECT_TEMPLATE_RU = "Запрос коммерческого предложения: {skus}";

function renderTemplate(
  template: string,
  context: Record<string, string>
): string {
  return template.replace(/\{(\w+)\}/g, (match, key) => context[key] ?? "");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface LetterDraftComposerProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  supplierName: string;
  supplierEmail: string | null;
  items: QuoteItemRow[];
  currency: string;
  incoterms: string | null;
  pickupCountry: string | null;
}

export function LetterDraftComposer({
  open,
  onClose,
  invoiceId,
  supplierName,
  supplierEmail,
  items,
  currency,
  incoterms,
  pickupCountry,
}: LetterDraftComposerProps) {
  const [recipientEmail, setRecipientEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(false);

  const buildTemplateContext = useCallback((): Record<string, string> => {
    const skus = items
      .slice(0, 3)
      .map((i) => i.product_code ?? i.product_name)
      .join(", ");

    const itemsList =
      items.length > 0
        ? items
            .map(
              (i, idx) =>
                `${idx + 1}. ${i.brand ?? ""} ${i.product_code ?? ""} — ${i.product_name} (${i.quantity} шт.)`
            )
            .join("\n")
        : "(позиции не указаны)";

    return {
      greeting: supplierName !== "\u2014" ? supplierName : "поставщик",
      items_list: itemsList,
      delivery_country: pickupCountry ?? "",
      incoterms: incoterms ?? "",
      currency,
      sender_name: "",
      sender_email: "",
      sender_phone: "",
      skus,
    };
  }, [items, supplierName, pickupCountry, incoterms, currency]);

  // Load existing draft or fill from template when dialog opens
  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    setLoadingDraft(true);

    fetchActiveLetterDraft(invoiceId)
      .then((draft: LetterDraft | null) => {
        if (cancelled) return;

        if (draft) {
          // Pre-load saved draft
          setRecipientEmail(draft.recipient_email ?? "");
          setSubject(draft.subject ?? "");
          setBodyText(draft.body_text ?? "");
        } else {
          // Render from template
          const ctx = buildTemplateContext();
          setRecipientEmail(supplierEmail ?? "");
          setSubject(renderTemplate(SUBJECT_TEMPLATE_RU, ctx));
          setBodyText(renderTemplate(LETTER_TEMPLATE_RU, ctx));
        }
      })
      .catch(() => {
        // On error, still populate from template
        if (cancelled) return;
        const ctx = buildTemplateContext();
        setRecipientEmail(supplierEmail ?? "");
        setSubject(renderTemplate(SUBJECT_TEMPLATE_RU, ctx));
        setBodyText(renderTemplate(LETTER_TEMPLATE_RU, ctx));
      })
      .finally(() => {
        if (!cancelled) setLoadingDraft(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, invoiceId, supplierEmail, buildTemplateContext]);

  async function handleSaveDraft() {
    setSaving(true);
    try {
      await saveLetterDraft(invoiceId, {
        recipient_email: recipientEmail,
        subject,
        body_text: bodyText,
      });
      toast.success("Черновик сохранён");
    } catch {
      toast.error("Не удалось сохранить черновик");
    } finally {
      setSaving(false);
    }
  }

  async function handleSend() {
    // Save first, then send
    setSending(true);
    try {
      await saveLetterDraft(invoiceId, {
        recipient_email: recipientEmail,
        subject,
        body_text: bodyText,
      });
      await sendLetterDraft(invoiceId);
      toast.success("Письмо отправлено");
      onClose();
    } catch {
      toast.error("Не удалось отправить письмо");
    } finally {
      setSending(false);
    }
  }

  const canSend = recipientEmail.trim().length > 0;
  const isLoading = saving || sending;

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-lg z-[200]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Подготовить письмо поставщику</DialogTitle>
          <DialogDescription>
            Отредактируйте текст письма и отправьте поставщику
          </DialogDescription>
        </DialogHeader>

        {loadingDraft ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>
                Email получателя <span className="text-destructive">*</span>
              </Label>
              <Input
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="supplier@example.com"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Тема письма</Label>
              <Input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Запрос коммерческого предложения"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Текст письма</Label>
              <Textarea
                value={bodyText}
                onChange={(e) => setBodyText(e.target.value)}
                rows={10}
                className="text-sm"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
          >
            Отмена
          </Button>
          <Button
            variant="outline"
            onClick={handleSaveDraft}
            disabled={isLoading || loadingDraft}
          >
            {saving && <Loader2 size={14} className="animate-spin mr-1" />}
            Сохранить черновик
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSend}
            disabled={isLoading || !canSend || loadingDraft}
          >
            {sending && <Loader2 size={14} className="animate-spin mr-1" />}
            Отправить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
