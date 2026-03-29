"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  FileText,
  Upload,
  Check,
  X,
  Download,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { createClient } from "@/shared/lib/supabase/client";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";
import type {
  SpecificationRow,
  CustomerContractRow,
  CustomerContactRow,
} from "./queries";

const SPEC_STATUS_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "outline" }> = {
  draft: { label: "Черновик", variant: "secondary" },
  pending_review: { label: "На проверке", variant: "outline" },
  approved: { label: "Утверждена", variant: "default" },
  signed: { label: "Подписана", variant: "default" },
};

interface SpecificationStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  userRoles: string[];
}

export function SpecificationStep({
  quote,
  items,
  userRoles,
}: SpecificationStepProps) {
  const router = useRouter();
  const [spec, setSpec] = useState<SpecificationRow | null>(null);
  const [contracts, setContracts] = useState<CustomerContractRow[]>([]);
  const [contacts, setContacts] = useState<CustomerContactRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [creatingDeal, setCreatingDeal] = useState(false);

  // Form state
  const [contractId, setContractId] = useState<string>("");
  const [signDate, setSignDate] = useState("");
  const [readinessPeriod, setReadinessPeriod] = useState("");
  const [dayType, setDayType] = useState("рабочих дней");
  const [signatoryId, setSignatoryId] = useState("");

  // Inline contract creation
  const [showContractForm, setShowContractForm] = useState(false);
  const [newContractNumber, setNewContractNumber] = useState("");
  const [newContractDate, setNewContractDate] = useState("");
  const [creatingContract, setCreatingContract] = useState(false);

  // Inline signatory creation
  const [showSignatoryForm, setShowSignatoryForm] = useState(false);
  const [newSignatoryName, setNewSignatoryName] = useState("");
  const [newSignatoryPosition, setNewSignatoryPosition] = useState("");
  const [creatingSignatory, setCreatingSignatory] = useState(false);

  const isSpecController = userRoles.some((r) =>
    ["spec_controller", "admin"].includes(r)
  );
  const isSalesManager = userRoles.some((r) =>
    ["sales", "head_of_sales", "sales_manager"].includes(r)
  );
  const canEdit = isSpecController;
  const canExportAndUpload = isSpecController || isSalesManager;

  // Extract fields not in the strict type via casting
  const quoteAny = quote as Record<string, unknown>;
  const customerId = quoteAny.customer_id as string | undefined;
  const orgId = quoteAny.organization_id as string;

  // Load spec + contracts + contacts
  const loadData = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();

    const [specRes, contractsRes, contactsRes] = await Promise.all([
      supabase
        .from("specifications")
        .select("id, quote_id, quote_version_id, contract_id, specification_number, sign_date, status, readiness_period, signed_scan_url, created_at, updated_at")
        .eq("quote_id", quote.id)
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
      customerId
        ? supabase
            .from("customer_contracts")
            .select("id, customer_id, contract_number, contract_date, status, next_specification_number")
            .eq("customer_id", customerId)
            .eq("status", "active")
            .order("contract_date", { ascending: false })
        : Promise.resolve({ data: [], error: null }),
      customerId
        ? supabase
            .from("customer_contacts")
            .select("id, customer_id, name, position, is_signatory")
            .eq("customer_id", customerId)
            .order("name")
        : Promise.resolve({ data: [], error: null }),
    ]);

    const specData = specRes.data as SpecificationRow | null;
    setSpec(specData);
    setContracts((contractsRes.data as CustomerContractRow[]) ?? []);
    setContacts((contactsRes.data as CustomerContactRow[]) ?? []);

    // Populate form from existing spec
    if (specData) {
      setContractId(specData.contract_id ?? "");
      setSignDate(specData.sign_date ?? "");
      setReadinessPeriod(specData.readiness_period ?? "");
    }

    setLoading(false);
  }, [quote.id, customerId]);

  useEffect(() => { loadData(); }, [loadData]);

  // Create specification
  async function handleCreate() {
    setCreating(true);
    try {
      const supabase = createClient();
      const specNumber = `SP-${quote.idn_quote.replace("Q-", "")}`;

      const insertData = {
        quote_id: quote.id,
        organization_id: orgId,
        contract_id: contractId || null,
        specification_number: specNumber,
        sign_date: signDate || null,
        readiness_period: readinessPeriod ? `${readinessPeriod} ${dayType}` : null,
        status: "draft" as const,
      };
      const { data, error } = await supabase
        .from("specifications")
        .insert(insertData as never)
        .select("id, specification_number")
        .single();

      if (error) throw error;
      toast.success(`Спецификация ${data.specification_number} создана`);
      router.refresh();
      loadData();
    } catch {
      toast.error("Не удалось создать спецификацию");
    } finally {
      setCreating(false);
    }
  }

  // Save specification
  async function handleSave() {
    if (!spec) return;
    setSaving(true);
    try {
      const supabase = createClient();
      const { error } = await supabase
        .from("specifications")
        .update({
          contract_id: contractId || null,
          sign_date: signDate || null,
          readiness_period: readinessPeriod ? `${readinessPeriod} ${dayType}` : null,
          updated_at: new Date().toISOString(),
        })
        .eq("id", spec.id);

      if (error) throw error;
      toast.success("Спецификация сохранена");
      loadData();
    } catch {
      toast.error("Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  }

  // Upload signed scan
  async function handleUploadScan(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !spec) return;
    setUploading(true);
    try {
      const supabase = createClient();
      const ext = file.name.split(".").pop() ?? "pdf";
      const path = `specifications/${spec.id}/signed-scan.${ext}`;

      const { error: uploadError } = await supabase.storage
        .from("kvota-documents")
        .upload(path, file, { upsert: true });
      if (uploadError) throw uploadError;

      const { data: urlData } = supabase.storage
        .from("kvota-documents")
        .getPublicUrl(path);

      await supabase
        .from("specifications")
        .update({ signed_scan_url: urlData.publicUrl, status: "approved", updated_at: new Date().toISOString() })
        .eq("id", spec.id);

      toast.success("Скан загружен");
      loadData();
    } catch {
      toast.error("Не удалось загрузить скан");
    } finally {
      setUploading(false);
    }
  }

  // Create deal
  async function handleCreateDeal() {
    if (!spec) return;
    setCreatingDeal(true);
    try {
      const supabase = createClient();

      // Generate deal number
      const year = new Date().getFullYear();
      const { count } = await supabase
        .from("deals")
        .select("id", { count: "exact", head: true })
        .gte("created_at", `${year}-01-01`);
      const seq = (count ?? 0) + 1;
      const dealNumber = `DEAL-${year}-${String(seq).padStart(4, "0")}`;

      // Update spec
      await supabase
        .from("specifications")
        .update({ status: "signed", updated_at: new Date().toISOString() })
        .eq("id", spec.id);

      // Create deal
      const dealData = {
        specification_id: spec.id,
        quote_id: quote.id,
        organization_id: orgId,
        deal_number: dealNumber,
        signed_at: spec.sign_date ?? new Date().toISOString().slice(0, 10),
        total_amount: quoteAny.total_amount as number ?? 0,
        currency: quote.currency ?? "USD",
        status: "active",
      };
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { error: dealError } = await (supabase.from("deals") as any).insert(dealData);
      if (dealError) throw dealError;

      // Update quote workflow
      await supabase
        .from("quotes")
        .update({ workflow_status: "spec_signed" })
        .eq("id", quote.id);

      toast.success(`Сделка ${dealNumber} создана!`);
      router.refresh();
    } catch {
      toast.error("Не удалось создать сделку");
    } finally {
      setCreatingDeal(false);
    }
  }

  // Inline contract creation
  async function handleCreateContract() {
    if (!customerId || !newContractNumber || !newContractDate) return;
    setCreatingContract(true);
    try {
      const supabase = createClient();
      const { data, error } = await supabase
        .from("customer_contracts")
        .insert({
          organization_id: orgId,
          customer_id: customerId,
          contract_number: newContractNumber,
          contract_date: newContractDate,
          status: "active",
        })
        .select("id, contract_number")
        .single();

      if (error) throw error;
      toast.success(`Договор ${data.contract_number} создан`);
      setContractId(data.id);
      setShowContractForm(false);
      setNewContractNumber("");
      setNewContractDate("");
      loadData();
    } catch {
      toast.error("Не удалось создать договор");
    } finally {
      setCreatingContract(false);
    }
  }

  // Inline signatory creation
  async function handleCreateSignatory() {
    if (!customerId || !newSignatoryName) return;
    setCreatingSignatory(true);
    try {
      const supabase = createClient();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { error } = await (supabase.from("customer_contacts") as any).insert({
        customer_id: customerId,
        name: newSignatoryName,
        position: newSignatoryPosition || null,
        is_signatory: true,
      });
      if (error) throw error;
      toast.success(`Подписант ${newSignatoryName} добавлен`);
      setShowSignatoryForm(false);
      setNewSignatoryName("");
      setNewSignatoryPosition("");
      loadData();
    } catch {
      toast.error("Не удалось добавить подписанта");
    } finally {
      setCreatingSignatory(false);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  const isReadOnly = spec?.status === "signed" || spec?.status === "approved";
  const signatories = contacts.filter((c) => c.is_signatory);
  const hasContract = contracts.length > 0 || !!contractId;
  const hasSignatory = signatories.length > 0;
  const hasScan = !!spec?.signed_scan_url;

  return (
    <div className="flex-1 min-w-0 flex flex-col">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* Status card */}
        {spec && (
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <FileText size={20} className="text-muted-foreground" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">
                    {spec.specification_number ?? "Без номера"}
                  </span>
                  <Badge variant={SPEC_STATUS_LABELS[spec.status]?.variant ?? "outline"}>
                    {SPEC_STATUS_LABELS[spec.status]?.label ?? spec.status}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Создана: {spec.created_at ? new Date(spec.created_at).toLocaleDateString("ru-RU") : "—"}
                </p>
              </div>
            </div>
          </Card>
        )}

        {/* Prerequisites checklist */}
        <Card className="p-5 space-y-4">
          <h4 className="text-sm font-semibold text-foreground">Предварительные условия</h4>

          {/* Items */}
          <div className="flex items-center gap-3">
            {items.length > 0 ? (
              <Check size={16} className="text-green-600 shrink-0" />
            ) : (
              <X size={16} className="text-red-500 shrink-0" />
            )}
            <span className="text-sm">Позиции КП</span>
            <span className="text-sm text-muted-foreground ml-auto">{items.length} шт.</span>
          </div>

          <div className="border-t border-border" />

          {/* Contract */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              {hasContract ? (
                <Check size={16} className="text-green-600 shrink-0" />
              ) : (
                <X size={16} className="text-red-500 shrink-0" />
              )}
              <span className="text-sm">Договор клиента</span>
              {contracts.length === 0 && !isReadOnly && !showContractForm && (
                <button
                  type="button"
                  className="ml-auto text-xs text-accent hover:underline"
                  onClick={() => setShowContractForm(true)}
                >
                  + Создать
                </button>
              )}
            </div>

            {contracts.length > 0 && !isReadOnly && (
              <div className="pl-7">
                <Select value={contractId} onValueChange={(v) => setContractId(v ?? "")}>
                  <SelectTrigger className="h-9 text-sm w-full">
                    <SelectValue placeholder="Выберите договор">
                      {contractId
                        ? (() => { const c = contracts.find((c) => c.id === contractId); return c ? `${c.contract_number} от ${c.contract_date}` : "Выберите договор"; })()
                        : "Выберите договор"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {contracts.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.contract_number} от {c.contract_date}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {showContractForm && (
              <div className="pl-7 p-3 bg-muted/50 rounded-lg space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-muted-foreground">Номер договора</Label>
                    <Input
                      value={newContractNumber}
                      onChange={(e) => setNewContractNumber(e.target.value)}
                      placeholder="Д-2026-001"
                      className="h-9 text-sm mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Дата договора</Label>
                    <Input
                      type="date"
                      value={newContractDate}
                      onChange={(e) => setNewContractDate(e.target.value)}
                      className="h-9 text-sm mt-1"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={handleCreateContract}
                    disabled={creatingContract || !newContractNumber || !newContractDate}
                  >
                    {creatingContract ? <Loader2 size={14} className="animate-spin" /> : "Создать"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowContractForm(false)}>
                    Отмена
                  </Button>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-border" />

          {/* Signatory */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              {hasSignatory ? (
                <Check size={16} className="text-green-600 shrink-0" />
              ) : (
                <X size={16} className="text-amber-500 shrink-0" />
              )}
              <span className="text-sm">Подписант клиента</span>
              {!hasSignatory && !isReadOnly && !showSignatoryForm && (
                <button
                  type="button"
                  className="ml-auto text-xs text-accent hover:underline"
                  onClick={() => setShowSignatoryForm(true)}
                >
                  + Добавить
                </button>
              )}
            </div>

            {signatories.length > 0 && (
              <p className="pl-7 text-sm text-muted-foreground">
                {signatories.map((s) => `${s.name}${s.position ? ` — ${s.position}` : ""}`).join(", ")}
              </p>
            )}

            {!hasSignatory && isReadOnly && (
              <p className="pl-7 text-xs text-muted-foreground">Не указан</p>
            )}

            {showSignatoryForm && (
              <div className="pl-7 p-3 bg-muted/50 rounded-lg space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-muted-foreground">ФИО</Label>
                    <Input
                      value={newSignatoryName}
                      onChange={(e) => setNewSignatoryName(e.target.value)}
                      placeholder="Иванов Иван Иванович"
                      className="h-9 text-sm mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Должность</Label>
                    <Input
                      value={newSignatoryPosition}
                      onChange={(e) => setNewSignatoryPosition(e.target.value)}
                      placeholder="Генеральный директор"
                      className="h-9 text-sm mt-1"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={handleCreateSignatory}
                    disabled={creatingSignatory || !newSignatoryName}
                  >
                    {creatingSignatory ? <Loader2 size={14} className="animate-spin" /> : "Добавить"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowSignatoryForm(false)}>
                    Отмена
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Delivery terms */}
        {canEdit && !isReadOnly && (
          <Card className="p-4 space-y-3">
            <h4 className="text-sm font-semibold">Условия поставки</h4>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Срок поставки</Label>
                <Input
                  type="number"
                  value={readinessPeriod}
                  onChange={(e) => setReadinessPeriod(e.target.value)}
                  placeholder="45"
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">Тип дней</Label>
                <Select value={dayType} onValueChange={(v) => setDayType(v ?? "рабочих дней")}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="рабочих дней">рабочих дней</SelectItem>
                    <SelectItem value="календарных дней">календарных дней</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Дата подписания</Label>
                <Input
                  type="date"
                  value={signDate}
                  onChange={(e) => setSignDate(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
            </div>
          </Card>
        )}

        {/* Read-only terms for signed specs */}
        {isReadOnly && spec && (
          <Card className="p-4 space-y-2">
            <h4 className="text-sm font-semibold">Условия поставки</h4>
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <span className="text-xs text-muted-foreground">Срок поставки</span>
                <p>{spec.readiness_period ?? "—"}</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground">Дата подписания</span>
                <p>{spec.sign_date ? new Date(spec.sign_date).toLocaleDateString("ru-RU") : "—"}</p>
              </div>
              <div>
                <span className="text-xs text-muted-foreground">Статус</span>
                <p>{SPEC_STATUS_LABELS[spec.status]?.label ?? spec.status}</p>
              </div>
            </div>
          </Card>
        )}

        {/* Documents section */}
        {spec && canExportAndUpload && (
          <Card className="p-4 space-y-3">
            <h4 className="text-sm font-semibold">Документы</h4>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(`/export/specification/${spec.id}`, "_blank")}
              >
                <Download size={14} />
                Скачать PDF
              </Button>
            </div>

            {/* Signed scan upload */}
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-6 text-center transition-colors",
                hasScan ? "border-green-200 bg-green-50" : "border-border hover:border-accent/50"
              )}
            >
              {hasScan ? (
                <div className="flex items-center justify-center gap-2 text-green-700">
                  <Check size={16} />
                  <span className="text-sm font-medium">Подписанный скан загружен</span>
                </div>
              ) : (
                <>
                  <Upload size={24} className="mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground mb-2">
                    Загрузите скан подписанной спецификации
                  </p>
                  <label className="cursor-pointer inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                    {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                    Выбрать файл
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      className="hidden"
                      onChange={handleUploadScan}
                    />
                  </label>
                  <p className="text-xs text-muted-foreground mt-1">PDF, JPG, PNG до 10 МБ</p>
                </>
              )}
            </div>
          </Card>
        )}

        {/* Success banner for signed specs */}
        {spec?.status === "signed" && (
          <Card className="p-4 bg-green-50 border-green-200">
            <div className="flex items-center gap-2 text-green-800">
              <Check size={16} />
              <span className="text-sm font-semibold">Спецификация подписана. Сделка создана.</span>
            </div>
          </Card>
        )}
      </div>

      {/* Sticky action bar */}
      <div className="border-t border-border px-6 py-3 flex items-center justify-between bg-background">
        {!spec && canEdit && (
          <Button
            onClick={handleCreate}
            disabled={creating}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
            Создать спецификацию
          </Button>
        )}

        {spec && canEdit && !isReadOnly && (
          <Button onClick={handleSave} disabled={saving} variant="outline">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null}
            Сохранить черновик
          </Button>
        )}

        {spec && hasScan && spec.status !== "signed" && canEdit && (
          <Button
            onClick={handleCreateDeal}
            disabled={creatingDeal}
            className="bg-green-600 text-white hover:bg-green-700"
          >
            {creatingDeal ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            Подтвердить и создать сделку
          </Button>
        )}

        {!canEdit && !canExportAndUpload && (
          <span className="text-sm text-muted-foreground">
            Нет прав для работы со спецификацией
          </span>
        )}
      </div>
    </div>
  );
}
