"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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
// Letter templates (mirrors services/letter_templates.py)
// ---------------------------------------------------------------------------

type Language = "ru" | "en";

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

const LETTER_TEMPLATE_EN = `Dear {greeting},

Please consider providing a quotation for the following items:

{items_list}

Delivery terms: {incoterms}
Delivery destination: {delivery_country}
Currency: {currency}

Detailed specification is attached.
Please send us your prices and delivery times.

Best regards,
{sender_name}
{sender_email}
{sender_phone}`;

const SUBJECT_TEMPLATE_EN = "Request for quotation: {skus}";

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
  initialLanguage?: Language;
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
  initialLanguage = "ru",
}: LetterDraftComposerProps) {
  const [recipientEmail, setRecipientEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(false);

  // Snapshot of the template we last rendered — lets us detect if the user
  // has edited the body before we overwrite on language change.
  const lastRenderedBodyRef = useRef<string>("");
  const lastRenderedSubjectRef = useRef<string>("");

  const buildTemplateContext = useCallback(
    (lang: Language): Record<string, string> => {
      const skus = items
        .slice(0, 3)
        .map((i) => i.product_code ?? i.product_name)
        .join(", ");

      const fallbackGreeting = lang === "en" ? "Supplier" : "поставщик";
      const noItemsPlaceholder =
        lang === "en" ? "(no items listed)" : "(позиции не указаны)";
      const qtyUnit = lang === "en" ? "pcs" : "шт.";

      // For EN, prefer name_en when available for each item
      const itemsList =
        items.length > 0
          ? items
              .map((i, idx) => {
                const displayName =
                  lang === "en"
                    ? ((i as { name_en?: string | null }).name_en ?? i.product_name)
                    : i.product_name;
                return `${idx + 1}. ${i.brand ?? ""} ${i.product_code ?? ""} — ${displayName} (${i.quantity} ${qtyUnit})`;
              })
              .join("\n")
          : noItemsPlaceholder;

      return {
        greeting: supplierName !== "\u2014" ? supplierName : fallbackGreeting,
        items_list: itemsList,
        delivery_country: pickupCountry ?? "",
        incoterms: incoterms ?? "",
        currency,
        sender_name: "",
        sender_email: "",
        sender_phone: "",
        skus,
      };
    },
    [items, supplierName, pickupCountry, incoterms, currency]
  );

  const renderForLanguage = useCallback(
    (lang: Language): { subject: string; body: string } => {
      const ctx = buildTemplateContext(lang);
      const subjectTpl = lang === "en" ? SUBJECT_TEMPLATE_EN : SUBJECT_TEMPLATE_RU;
      const bodyTpl = lang === "en" ? LETTER_TEMPLATE_EN : LETTER_TEMPLATE_RU;
      return {
        subject: renderTemplate(subjectTpl, ctx),
        body: renderTemplate(bodyTpl, ctx),
      };
    },
    [buildTemplateContext]
  );

  // Load existing draft or fill from template when dialog opens
  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    setLoadingDraft(true);

    fetchActiveLetterDraft(invoiceId)
      .then((draft: LetterDraft | null) => {
        if (cancelled) return;

        if (draft) {
          // Pre-load saved draft. Use draft's language if present.
          const draftLang: Language = draft.language === "en" ? "en" : "ru";
          setLanguage(draftLang);
          setRecipientEmail(draft.recipient_email ?? "");
          setSubject(draft.subject ?? "");
          setBodyText(draft.body_text ?? "");
          // Mark refs as matching what's loaded so any "equals template" check
          // against a fresh render won't match — preserves user edits on toggle.
          lastRenderedSubjectRef.current = draft.subject ?? "";
          lastRenderedBodyRef.current = draft.body_text ?? "";
        } else {
          // Render from template at the requested initial language
          setLanguage(initialLanguage);
          const rendered = renderForLanguage(initialLanguage);
          setRecipientEmail(supplierEmail ?? "");
          setSubject(rendered.subject);
          setBodyText(rendered.body);
          lastRenderedSubjectRef.current = rendered.subject;
          lastRenderedBodyRef.current = rendered.body;
        }
      })
      .catch(() => {
        // On error, still populate from template
        if (cancelled) return;
        setLanguage(initialLanguage);
        const rendered = renderForLanguage(initialLanguage);
        setRecipientEmail(supplierEmail ?? "");
        setSubject(rendered.subject);
        setBodyText(rendered.body);
        lastRenderedSubjectRef.current = rendered.subject;
        lastRenderedBodyRef.current = rendered.body;
      })
      .finally(() => {
        if (!cancelled) setLoadingDraft(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, invoiceId, supplierEmail, initialLanguage, renderForLanguage]);

  function handleLanguageChange(nextLang: Language) {
    if (nextLang === language) return;

    const rendered = renderForLanguage(nextLang);

    // Only overwrite fields that the user hasn't edited. Compare current value
    // to the last-rendered snapshot; if they match, safe to replace.
    const bodyUntouched = bodyText === lastRenderedBodyRef.current;
    const subjectUntouched = subject === lastRenderedSubjectRef.current;

    const nextSubject = subjectUntouched ? rendered.subject : subject;
    const nextBody = bodyUntouched ? rendered.body : bodyText;

    setLanguage(nextLang);
    setSubject(nextSubject);
    setBodyText(nextBody);

    // Update snapshots only for fields we just rewrote, so subsequent toggles
    // still detect user edits on the untouched side.
    lastRenderedSubjectRef.current = subjectUntouched
      ? rendered.subject
      : lastRenderedSubjectRef.current;
    lastRenderedBodyRef.current = bodyUntouched
      ? rendered.body
      : lastRenderedBodyRef.current;

    if (!bodyUntouched || !subjectUntouched) {
      toast.info(
        nextLang === "en"
          ? "Язык переключён. Отредактированные поля сохранены."
          : "Язык переключён. Отредактированные поля сохранены."
      );
    }
  }

  async function handleSaveDraft() {
    setSaving(true);
    try {
      await saveLetterDraft(invoiceId, {
        recipient_email: recipientEmail,
        subject,
        body_text: bodyText,
        language,
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
        language,
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
            <div className="flex items-center justify-between">
              <Label>Язык письма</Label>
              <div
                role="radiogroup"
                aria-label="Язык письма"
                className="inline-flex rounded-md border border-border overflow-hidden"
              >
                <button
                  type="button"
                  role="radio"
                  aria-checked={language === "ru"}
                  onClick={() => handleLanguageChange("ru")}
                  className={`px-2 py-1 text-xs font-medium transition-colors ${
                    language === "ru"
                      ? "bg-accent text-white"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  RU
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={language === "en"}
                  onClick={() => handleLanguageChange("en")}
                  className={`px-2 py-1 text-xs font-medium transition-colors border-l border-border ${
                    language === "en"
                      ? "bg-accent text-white"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  EN
                </button>
              </div>
            </div>

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
