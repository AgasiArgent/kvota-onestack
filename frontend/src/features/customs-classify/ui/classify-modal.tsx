"use client";

import { useEffect, useState } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

import { extractErrorMessage } from "@/shared/lib/errors";

import { classifyItems, selectClassification } from "../api/classify";
import {
  type Candidate,
  type ClassifyResult,
  type ConfidenceTier,
  confidenceTier,
  formatProbability,
} from "../model/types";

export interface ClassifyModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Quote item being classified — required so backend can write hs_code. */
  quoteItemId: string;
  /** Pre-fill the search field. Usually the product name. */
  initialName: string;
  /** Optional brand to bias Alta's ML — appended to the name in the query. */
  initialBrand?: string;
  /**
   * Called after the user confirms a code. Receives the chosen code so the
   * parent dialog can update its form state without re-fetching.
   */
  onSelected: (code: string) => void;
}

interface State {
  status: "idle" | "loading" | "loaded" | "error";
  result: ClassifyResult | null;
  packetLeft: number | null;
  error: string | null;
}

const TIER_BADGE_VARIANT: Record<ConfidenceTier, "default" | "secondary" | "outline"> = {
  high: "default",
  medium: "secondary",
  low: "outline",
};

const TIER_LABEL: Record<ConfidenceTier, string> = {
  high: "Высокая",
  medium: "Средняя",
  low: "Низкая",
};

/**
 * Modal that classifies a product description into TN ВЭД candidates via
 * Alta Express. Customs-specialist picks one; the chosen code is saved to
 * `quote_items.hs_code` and surfaced back to the parent dialog form.
 */
export function ClassifyModal({
  open,
  onOpenChange,
  quoteItemId,
  initialName,
  initialBrand,
  onSelected,
}: ClassifyModalProps) {
  const [name, setName] = useState(initialName);
  const [brand, setBrand] = useState(initialBrand ?? "");
  const [state, setState] = useState<State>({
    status: "idle",
    result: null,
    packetLeft: null,
    error: null,
  });
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Re-seed when the modal opens with a different item.
  useEffect(() => {
    if (open) {
      setName(initialName);
      setBrand(initialBrand ?? "");
      setState({ status: "idle", result: null, packetLeft: null, error: null });
      setSelectedCode(null);
    }
  }, [open, initialName, initialBrand]);

  async function handleClassify() {
    if (!name.trim()) {
      toast.error("Введите название товара");
      return;
    }
    setState({ status: "loading", result: null, packetLeft: null, error: null });
    setSelectedCode(null);

    const res = await classifyItems({
      items: [
        {
          name: name.trim(),
          brand: brand.trim() || null,
          quote_item_id: quoteItemId,
        },
      ],
    });

    if (!res.success || !res.data) {
      const msg = res.error?.message ?? "Не удалось получить варианты";
      setState({ status: "error", result: null, packetLeft: null, error: msg });
      return;
    }

    const result = res.data.results[0] ?? null;
    setState({
      status: "loaded",
      result,
      packetLeft: res.data.packet_left,
      error: null,
    });

    // Auto-select the top candidate so customs-specialist just confirms.
    if (result?.candidates.length) {
      setSelectedCode(result.candidates[0].code);
    }
  }

  async function handleConfirm() {
    if (!state.result || !selectedCode) return;

    const candidate = state.result.candidates.find((c) => c.code === selectedCode);
    setSaving(true);
    const res = await selectClassification({
      quote_item_id: quoteItemId,
      chosen_code: selectedCode,
      candidates_shown: state.result.candidates,
      input_text: state.result.name,
    });
    setSaving(false);

    if (!res.success || !res.data) {
      toast.error(res.error?.message ?? "Не удалось сохранить код");
      return;
    }

    toast.success(
      `Код ${selectedCode} сохранён${candidate?.description ? ` — ${candidate.description}` : ""}`,
    );
    onSelected(selectedCode);
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={16} />
            Подбор кода ТН ВЭД по названию
          </DialogTitle>
          <DialogDescription>
            Alta Express подбирает топ-5 кандидатов по описанию.
            Каждый запрос тратит 1 пакет Alta.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название товара"
              disabled={state.status === "loading" || saving}
              autoFocus
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleClassify}
              disabled={state.status === "loading" || saving || !name.trim()}
              className="gap-1.5"
            >
              {state.status === "loading" ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Search size={14} />
              )}
              Подобрать
            </Button>
          </div>
          <Input
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            placeholder="Бренд (необязательно)"
            disabled={state.status === "loading" || saving}
            className="text-sm"
          />
        </div>

        {state.status === "error" ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {state.error}
          </div>
        ) : null}

        {state.status === "loaded" && state.result ? (
          <ResultView
            result={state.result}
            selectedCode={selectedCode}
            onSelect={setSelectedCode}
            packetLeft={state.packetLeft}
          />
        ) : null}

        <DialogFooter className="gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Отмена
          </Button>
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={!selectedCode || saving}
          >
            {saving ? (
              <Loader2 size={14} className="mr-1.5 animate-spin" />
            ) : null}
            Подтвердить выбор
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface ResultViewProps {
  result: ClassifyResult;
  selectedCode: string | null;
  onSelect: (code: string) => void;
  packetLeft: number | null;
}

function ResultView({
  result,
  selectedCode,
  onSelect,
  packetLeft,
}: ResultViewProps) {
  if (result.candidates.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-sm text-muted-foreground">
        {extractErrorMessage(result) ?? "Alta не нашла подходящих кодов. Уточните описание."}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Найдено вариантов: {result.candidates.length}</span>
        {packetLeft != null ? <span>Пакетов осталось: {packetLeft}</span> : null}
      </div>
      <ul className="flex flex-col gap-1 rounded-md border border-border bg-muted/20 p-2">
        {result.candidates.map((c) => (
          <CandidateRow
            key={c.code}
            candidate={c}
            checked={c.code === selectedCode}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </div>
  );
}

interface CandidateRowProps {
  candidate: Candidate;
  checked: boolean;
  onSelect: (code: string) => void;
}

function CandidateRow({ candidate, checked, onSelect }: CandidateRowProps) {
  const tier = confidenceTier(candidate.probability);
  return (
    <label
      className={`flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 transition-colors ${
        checked ? "bg-card ring-1 ring-primary/30" : "hover:bg-card/60"
      }`}
    >
      <input
        type="radio"
        name="classify-candidate"
        checked={checked}
        onChange={() => onSelect(candidate.code)}
        className="mt-0.5 cursor-pointer"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-sm tabular-nums text-foreground">
            {candidate.code}
          </span>
          <Badge variant={TIER_BADGE_VARIANT[tier]} className="text-[10px]">
            {formatProbability(candidate.probability)} · {TIER_LABEL[tier]}
          </Badge>
        </div>
        {candidate.description ? (
          <span className="text-xs text-muted-foreground">
            {candidate.description}
          </span>
        ) : null}
      </div>
    </label>
  );
}
