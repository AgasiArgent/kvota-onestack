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
import { createClient } from "@/shared/lib/supabase/client";
import { canEditSpecControl } from "@/shared/lib/roles";
import { confirmSignatureAndCreateDeal } from "./mutations";
import { SPECIFICATION_SELECT } from "./columns";
import { FromCalcBlock } from "./blocks/from-calc-block";
import { RequisitesBlock, type SellerCompanyItem, type CountryItem } from "./blocks/requisites-block";
import { ConditionsBlock } from "./blocks/conditions-block";
import { ControlBlock, type SigningFxMode } from "./blocks/control-block";
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

const DEFAULT_FX_MODE: SigningFxMode = "cbr_on_payment_day";

function isFxMode(value: string | null): value is SigningFxMode {
  return value === "cbr_on_payment_day" || value === "fixed";
}

interface SpecificationStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  userRoles: string[];
  userId: string;
}

export function SpecificationStep({
  quote,
  items,
  userRoles,
  userId,
}: SpecificationStepProps) {
  const router = useRouter();
  const [spec, setSpec] = useState<SpecificationRow | null>(null);
  const [contracts, setContracts] = useState<CustomerContractRow[]>([]);
  const [contacts, setContacts] = useState<CustomerContactRow[]>([]);
  const [sellerCompanies, setSellerCompanies] = useState<SellerCompanyItem[]>([]);
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [controllerName, setControllerName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [creatingDeal, setCreatingDeal] = useState(false);

  // Form state — requisites
  const [contractId, setContractId] = useState<string | null>(null);
  const [sellerCompanyId, setSellerCompanyId] = useState<string | null>(null);
  const [cargoPickupCountry, setCargoPickupCountry] = useState<string | null>(null);
  const [goodsShipmentCountry, setGoodsShipmentCountry] = useState<string | null>(null);
  const [supplierPaymentCountry, setSupplierPaymentCountry] = useState<string | null>(null);

  // Form state — conditions
  const [signDate, setSignDate] = useState("");
  const [validityPeriod, setValidityPeriod] = useState("");
  const [readinessPeriod, setReadinessPeriod] = useState("");
  const [dayType, setDayType] = useState("рабочих дней");
  const [logisticsPeriod, setLogisticsPeriod] = useState("");
  const [cargoType, setCargoType] = useState("");
  const [deliveryCityRussia, setDeliveryCityRussia] = useState("");

  // Form state — control stamp
  const [signingFxMode, setSigningFxMode] = useState<SigningFxMode>(DEFAULT_FX_MODE);
  const [signingFxRate, setSigningFxRate] = useState("");

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

  const isSalesManager = userRoles.some((r) =>
    ["sales", "head_of_sales", "sales_manager"].includes(r)
  );

  // Extract fields not in the strict type via casting
  const quoteAny = quote as Record<string, unknown>;
  const customerId = quoteAny.customer_id as string | undefined;
  const orgId = quoteAny.organization_id as string;
  const customerName =
    (quote.customer as { name?: string } | null)?.name ?? null;

  // Load spec + contracts + contacts + seller companies + countries
  const loadData = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();

    const [specRes, contractsRes, contactsRes, countriesRes, sellerCompaniesRes, profileRes] =
      await Promise.all([
        supabase
          .from("specifications")
          .select(SPECIFICATION_SELECT)
          .eq("quote_id", quote.id)
          .is("deleted_at", null)
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
        supabase
          .from("locations")
          .select("country")
          .eq("organization_id", orgId),
        // Наше юрлицо source — fetched inline (same browser-client pattern as the
        // other reads here) rather than importing the entities/quote barrel, which
        // re-exports server-only queries and would break the client bundle build.
        supabase
          .from("seller_companies")
          .select("id, name")
          .eq("organization_id", orgId)
          .eq("is_active", true)
          .order("name"),
        supabase
          .from("user_profiles")
          .select("full_name")
          .eq("user_id", userId)
          .maybeSingle(),
      ]);

    const specData = specRes.data as unknown as SpecificationRow | null;
    setSpec(specData);
    setContracts((contractsRes.data as CustomerContractRow[]) ?? []);
    setContacts((contactsRes.data as CustomerContactRow[]) ?? []);
    setSellerCompanies((sellerCompaniesRes.data as SellerCompanyItem[]) ?? []);
    setControllerName((profileRes.data as { full_name: string } | null)?.full_name ?? null);

    // Distinct, sorted countries from locations
    const countryRows = (countriesRes.data as { country: string | null }[]) ?? [];
    const distinct = Array.from(
      new Set(
        countryRows
          .map((r) => r.country)
          .filter((c): c is string => !!c && c.trim().length > 0)
      )
    ).sort((a, b) => a.localeCompare(b, "ru"));
    setCountries(distinct.map((c) => ({ id: c, name: c })));

    // Populate form from existing spec
    if (specData) {
      setContractId(specData.contract_id ?? null);
      setSignDate(specData.sign_date ?? "");
      setReadinessPeriod(specData.readiness_period ?? "");
      setSellerCompanyId(specData.seller_company_id ?? null);
      setCargoPickupCountry(specData.cargo_pickup_country ?? null);
      setGoodsShipmentCountry(specData.goods_shipment_country ?? null);
      setSupplierPaymentCountry(specData.supplier_payment_country ?? null);
      setValidityPeriod(specData.validity_period ?? "");
      setLogisticsPeriod(specData.logistics_period ?? "");
      setCargoType(specData.cargo_type ?? "");
      setDeliveryCityRussia(specData.delivery_city_russia ?? "");
      setSigningFxMode(isFxMode(specData.signing_fx_mode) ? specData.signing_fx_mode : DEFAULT_FX_MODE);
      setSigningFxRate(specData.signing_fx_rate != null ? String(specData.signing_fx_rate) : "");
    }

    // Auto-select single contract
    const contractList = (contractsRes.data as CustomerContractRow[]) ?? [];
    if (!specData?.contract_id && contractList.length === 1) {
      setContractId(contractList[0].id);
    }

    setLoading(false);
  }, [quote.id, customerId, orgId, userId]);

  useEffect(() => { loadData(); }, [loadData]);

  // Build the new-field payload shared by insert + update. `null` for empties;
  // signing_fx_rate is null unless the mode is 'fixed'.
  function buildRequisitesPayload() {
    const sellerName = sellerCompanies.find((s) => s.id === sellerCompanyId)?.name ?? null;
    const fxRate =
      signingFxMode === "fixed" && signingFxRate.trim() !== ""
        ? Number(signingFxRate)
        : null;
    return {
      contract_id: contractId || null,
      seller_company_id: sellerCompanyId || null,
      // dual-write snapshot of the chosen company name (export compatibility)
      our_legal_entity: sellerName,
      cargo_pickup_country: cargoPickupCountry || null,
      goods_shipment_country: goodsShipmentCountry || null,
      supplier_payment_country: supplierPaymentCountry || null,
      sign_date: signDate || null,
      validity_period: validityPeriod || null,
      readiness_period: readinessPeriod ? `${readinessPeriod} ${dayType}` : null,
      logistics_period: logisticsPeriod || null,
      cargo_type: cargoType || null,
      delivery_city_russia: deliveryCityRussia || null,
      signing_fx_mode: signingFxMode,
      signing_fx_rate: fxRate,
    };
  }

  // Create specification
  async function handleCreate() {
    setCreating(true);
    try {
      const supabase = createClient();
      const specNumber = `SP-${quote.idn_quote.replace("Q-", "")}`;

      const insertData = {
        quote_id: quote.id,
        organization_id: orgId,
        specification_number: specNumber,
        status: "draft" as const,
        created_by: userId,
        ...buildRequisitesPayload(),
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
          ...buildRequisitesPayload(),
          updated_at: new Date().toISOString(),
        } as never)
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

      // Also create a record in documents table for the documents panel
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (supabase.from("documents") as any).insert({
        organization_id: orgId,
        entity_type: "specification",
        entity_id: spec.id,
        parent_quote_id: quote.id,
        storage_path: path,
        original_filename: file.name,
        file_size_bytes: file.size,
        mime_type: file.type || "application/pdf",
        document_type: "specification_signed_scan",
        description: "Подписанный скан спецификации",
      });

      toast.success("Скан загружен");
      loadData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "unknown";
      toast.error(`Не удалось загрузить скан: ${msg}`);
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
    }
  }

  // Create deal via Python API endpoint (api-first pattern)
  async function handleCreateDeal() {
    if (!spec) return;
    setCreatingDeal(true);
    try {
      const result = await confirmSignatureAndCreateDeal(spec.id);
      const dealNumber = result?.deal_number ?? "";
      const invoicesCreated = result?.invoices_created ?? 0;
      const skipReason = result?.invoices_skipped_reason;

      if (invoicesCreated > 0) {
        toast.success(`Сделка ${dealNumber} создана! Валютных инвойсов: ${invoicesCreated}`);
      } else if (skipReason) {
        toast.success(`Сделка ${dealNumber} создана. Инвойсы не созданы: ${skipReason}`);
      } else {
        toast.success(`Сделка ${dealNumber} создана!`);
      }
      router.push("/quotes");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "unknown";
      toast.error(`Не удалось создать сделку: ${msg}`);
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
        organization_id: orgId,
        name: newSignatoryName,
        position: newSignatoryPosition || null,
        is_signatory: true,
      });
      if (error) throw new Error(error.message);
      toast.success(`Подписант ${newSignatoryName} добавлен`);
      setShowSignatoryForm(false);
      setNewSignatoryName("");
      setNewSignatoryPosition("");
      loadData();
    } catch (err) {
      toast.error(`Не удалось добавить подписанта: ${err instanceof Error ? err.message : "unknown"}`);
      console.error("Signatory creation error:", err);
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
  // Edit-gate (Req 11.3): role grant AND not locked by status.
  const canEdit = canEditSpecControl(userRoles) && !isReadOnly;
  const canExportAndUpload = canEditSpecControl(userRoles) || isSalesManager;
  const signatories = contacts.filter((c) => c.is_signatory);
  const hasSignatory = signatories.length > 0;
  const hasScan = !!spec?.signed_scan_url;

  const readinessDisplay = spec?.readiness_period ?? null;
  const clientLegalEntity = spec?.client_legal_entity ?? customerName;

  // Inline contract-create affordance + form, threaded into the requisites block.
  const contractCreateSlot = (
    <div className="space-y-2">
      {contracts.length === 0 && !showContractForm && (
        <button
          type="button"
          className="text-xs text-accent hover:underline"
          onClick={() => setShowContractForm(true)}
        >
          + Создать договор
        </button>
      )}

      {showContractForm && (
        <div className="p-3 bg-muted/50 rounded-lg space-y-3">
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
  );

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
                  Создана: {spec.created_at ? new Date(spec.created_at).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" }) : "—"}
                </p>
              </div>
            </div>
          </Card>
        )}

        {/* ====== Фаза «На контроле» — 4 блока ====== */}

        {/* 1. Из расчёта (read-only) */}
        <FromCalcBlock
          currency={quote.currency}
          total={quote.total_quote_currency}
          totalWithVat={quote.total_with_vat_quote}
          profitUsd={quote.total_profit_usd}
          fxToUsd={quote.exchange_rate_to_usd}
        />

        {/* 2. Реквизиты */}
        <RequisitesBlock
          canEdit={canEdit}
          sellerCompanies={sellerCompanies}
          sellerCompanyId={sellerCompanyId}
          onSellerCompanyChange={setSellerCompanyId}
          contracts={contracts}
          contractId={contractId}
          onContractChange={setContractId}
          contractCreateSlot={contractCreateSlot}
          countries={countries}
          cargoPickupCountry={cargoPickupCountry}
          onCargoPickupCountryChange={setCargoPickupCountry}
          goodsShipmentCountry={goodsShipmentCountry}
          onGoodsShipmentCountryChange={setGoodsShipmentCountry}
          supplierPaymentCountry={supplierPaymentCountry}
          onSupplierPaymentCountryChange={setSupplierPaymentCountry}
          clientLegalEntity={clientLegalEntity}
        />

        {/* 3. Условия спецификации */}
        <ConditionsBlock
          canEdit={canEdit}
          signDate={signDate}
          onSignDateChange={setSignDate}
          validityPeriod={validityPeriod}
          onValidityPeriodChange={setValidityPeriod}
          readinessPeriod={readinessPeriod}
          onReadinessPeriodChange={setReadinessPeriod}
          dayType={dayType}
          onDayTypeChange={setDayType}
          logisticsPeriod={logisticsPeriod}
          onLogisticsPeriodChange={setLogisticsPeriod}
          cargoType={cargoType}
          onCargoTypeChange={setCargoType}
          deliveryCityRussia={deliveryCityRussia}
          onDeliveryCityRussiaChange={setDeliveryCityRussia}
          readinessDisplay={readinessDisplay}
        />

        {/* 4. Контроль */}
        <ControlBlock
          canEdit={canEdit}
          signingFxMode={signingFxMode}
          onSigningFxModeChange={setSigningFxMode}
          signingFxRate={signingFxRate}
          onSigningFxRateChange={setSigningFxRate}
          controllerLabel={controllerName ?? "Вы"}
          controlDate={null}
        />

        {/* Signatory (client) — kept from prerequisites */}
        <Card className="p-5 space-y-2">
          <div className="flex items-center gap-3">
            {hasSignatory ? (
              <Check size={16} className="text-green-600 shrink-0" />
            ) : (
              <X size={16} className="text-amber-500 shrink-0" />
            )}
            <span className="text-sm font-semibold">Подписант клиента</span>
            {!hasSignatory && canEdit && !showSignatoryForm && (
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

          {!hasSignatory && !canEdit && (
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
        </Card>

        {/* ====== Existing scan → deal flow (restructured in PR3) ====== */}

        {/* Items count */}
        <Card className="p-4">
          <div className="flex items-center gap-3">
            {items.length > 0 ? (
              <Check size={16} className="text-green-600 shrink-0" />
            ) : (
              <X size={16} className="text-red-500 shrink-0" />
            )}
            <span className="text-sm">Позиции КП</span>
            <span className="text-sm text-muted-foreground ml-auto">{items.length} шт.</span>
          </div>
        </Card>

        {/* Workflow guidance + Documents */}
        {spec && canExportAndUpload && (
          <Card className="p-5 space-y-4">
            <h4 className="text-sm font-semibold">Оформление спецификации</h4>

            {/* Step 1: Export */}
            <div className="flex items-start gap-3">
              <span className={cn(
                "flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0",
                hasScan ? "bg-green-100 text-green-700" : "bg-accent/10 text-accent"
              )}>1</span>
              <div className="flex-1">
                <p className="text-sm font-medium">Скачать и отправить клиенту</p>
                <p className="text-xs text-muted-foreground mb-2">Экспортируйте спецификацию и отправьте на подпись</p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(`https://kvotaflow.ru/spec-control/${spec.id}/export-pdf`, "_blank")}
                  >
                    <Download size={14} />
                    Скачать PDF
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(`https://kvotaflow.ru/spec-control/${spec.id}/export-docx`, "_blank")}
                  >
                    <Download size={14} />
                    Скачать DOCX
                  </Button>
                </div>
              </div>
            </div>

            <div className="border-t border-border" />

            {/* Step 2: Upload signed scan */}
            <div className="flex items-start gap-3">
              <span className={cn(
                "flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0",
                hasScan ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"
              )}>2</span>
              <div className="flex-1">
                <p className="text-sm font-medium">Загрузить подписанный скан</p>
                <p className="text-xs text-muted-foreground mb-2">После подписания клиентом загрузите скан</p>
                <div
                  className={cn(
                    "border-2 border-dashed rounded-lg p-4 text-center transition-colors",
                    hasScan ? "border-green-200 bg-green-50" : "border-border hover:border-accent/50"
                  )}
                >
                  {hasScan ? (
                    <div className="flex items-center justify-center gap-2 text-green-700">
                      <Check size={16} />
                      <span className="text-sm font-medium">Скан загружен</span>
                    </div>
                  ) : (
                    <label className="cursor-pointer inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                      {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                      Выбрать файл (PDF, JPG, PNG)
                      <input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        className="hidden"
                        onChange={handleUploadScan}
                      />
                    </label>
                  )}
                </div>
              </div>
            </div>

            <div className="border-t border-border" />

            {/* Step 3: Create deal */}
            <div className="flex items-start gap-3">
              <span className={cn(
                "flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0",
                spec.status === "signed" ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"
              )}>3</span>
              <div className="flex-1">
                <p className="text-sm font-medium">Подтвердить и создать сделку</p>
                <p className="text-xs text-muted-foreground">Проверьте скан и переведите в сделку</p>
              </div>
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
        {/* Left side */}
        <div>
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

          {spec && canEdit && (
            <Button onClick={handleSave} disabled={saving} variant="outline">
              {saving ? <Loader2 size={14} className="animate-spin" /> : null}
              Сохранить черновик
            </Button>
          )}

          {!canEditSpecControl(userRoles) && !canExportAndUpload && (
            <span className="text-sm text-muted-foreground">
              Нет прав для работы со спецификацией
            </span>
          )}
        </div>

        {/* Right side */}
        <div>
          {spec && hasScan && spec.status !== "signed" && canEditSpecControl(userRoles) && (
            <Button
              onClick={handleCreateDeal}
              disabled={creatingDeal}
              className="bg-green-600 text-white hover:bg-green-700"
            >
              {creatingDeal ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              Подтвердить и создать сделку
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
