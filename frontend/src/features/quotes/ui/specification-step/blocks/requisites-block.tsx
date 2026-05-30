"use client";

import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import type { CustomerContractRow } from "../queries";

export interface SellerCompanyItem {
  id: string;
  name: string;
}

export interface CountryItem {
  id: string;
  name: string;
}

export interface RequisitesBlockProps {
  canEdit: boolean;

  // Наше юрлицо (FK seller_company_id + name snapshot)
  sellerCompanies: readonly SellerCompanyItem[];
  sellerCompanyId: string | null;
  onSellerCompanyChange: (id: string | null) => void;
  /** Highlights the «Наше юрлицо» picker as a validation error (Req 5.2). */
  sellerCompanyInvalid?: boolean;

  // Договор (FK contract_id) — inline-create handled by parent slot
  contracts: readonly CustomerContractRow[];
  contractId: string | null;
  onContractChange: (id: string | null) => void;
  /** Inline-create affordance + form, rendered by the parent. */
  contractCreateSlot?: React.ReactNode;
  /** Highlights the «Договор» picker as a validation error (Req 5.2). */
  contractInvalid?: boolean;

  // Страны (string columns)
  countries: readonly CountryItem[];
  cargoPickupCountry: string | null;
  onCargoPickupCountryChange: (value: string | null) => void;
  goodsShipmentCountry: string | null;
  onGoodsShipmentCountryChange: (value: string | null) => void;
  supplierPaymentCountry: string | null;
  onSupplierPaymentCountryChange: (value: string | null) => void;

  // Юрлицо клиента (read-only)
  clientLegalEntity: string | null;
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <p className="text-sm mt-1">{value || "—"}</p>
    </div>
  );
}

function contractLabel(c: CustomerContractRow): string {
  return `${c.contract_number} от ${c.contract_date}`;
}

/**
 * Block «Реквизиты» — Req 2.1–2.7.
 *
 * Every dropdown is a `SearchableCombobox` (project-wide standard: all selects
 * are searchable). Read-only display when the user lacks edit rights.
 */
export function RequisitesBlock({
  canEdit,
  sellerCompanies,
  sellerCompanyId,
  onSellerCompanyChange,
  sellerCompanyInvalid = false,
  contracts,
  contractId,
  onContractChange,
  contractCreateSlot,
  contractInvalid = false,
  countries,
  cargoPickupCountry,
  onCargoPickupCountryChange,
  goodsShipmentCountry,
  onGoodsShipmentCountryChange,
  supplierPaymentCountry,
  onSupplierPaymentCountryChange,
  clientLegalEntity,
}: RequisitesBlockProps) {
  const selectedSeller = sellerCompanies.find((s) => s.id === sellerCompanyId);
  const selectedContract = contracts.find((c) => c.id === contractId);

  return (
    <Card className="p-4 space-y-3">
      <h4 className="text-sm font-semibold">Реквизиты</h4>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Наше юрлицо */}
        <div>
          <Label className="text-xs text-muted-foreground">Наше юрлицо</Label>
          {canEdit ? (
            <SearchableCombobox<SellerCompanyItem>
              value={sellerCompanyId}
              onChange={onSellerCompanyChange}
              items={sellerCompanies}
              getLabel={(s) => s.name}
              placeholder="Выберите юрлицо"
              emptyMessage="Нет юрлиц"
              className="mt-1"
              popoverWidthClass="w-80"
              invalid={sellerCompanyInvalid}
            />
          ) : (
            <p className="text-sm mt-1">{selectedSeller?.name ?? "—"}</p>
          )}
        </div>

        {/* Юрлицо клиента (read-only) */}
        <ReadOnlyField label="Юрлицо клиента" value={clientLegalEntity ?? ""} />

        {/* Договор */}
        <div className="sm:col-span-2 space-y-2">
          <Label className="text-xs text-muted-foreground">Договор</Label>
          {canEdit ? (
            <SearchableCombobox<CustomerContractRow>
              value={contractId}
              onChange={onContractChange}
              items={contracts}
              getLabel={contractLabel}
              placeholder="Выберите договор"
              emptyMessage="Нет договоров"
              className="mt-1"
              popoverWidthClass="w-80"
              invalid={contractInvalid}
            />
          ) : (
            <p className="text-sm mt-1">
              {selectedContract ? contractLabel(selectedContract) : "—"}
            </p>
          )}
          {canEdit && contractCreateSlot}
        </div>

        {/* Страны */}
        <div>
          <Label className="text-xs text-muted-foreground">Страна забора груза</Label>
          {canEdit ? (
            <SearchableCombobox<CountryItem>
              value={cargoPickupCountry}
              onChange={onCargoPickupCountryChange}
              items={countries}
              getLabel={(c) => c.name}
              placeholder="Выберите страну"
              emptyMessage="Нет стран"
              className="mt-1"
            />
          ) : (
            <p className="text-sm mt-1">{cargoPickupCountry || "—"}</p>
          )}
        </div>

        <div>
          <Label className="text-xs text-muted-foreground">Страна отгрузки товара</Label>
          {canEdit ? (
            <SearchableCombobox<CountryItem>
              value={goodsShipmentCountry}
              onChange={onGoodsShipmentCountryChange}
              items={countries}
              getLabel={(c) => c.name}
              placeholder="Выберите страну"
              emptyMessage="Нет стран"
              className="mt-1"
            />
          ) : (
            <p className="text-sm mt-1">{goodsShipmentCountry || "—"}</p>
          )}
        </div>

        <div>
          <Label className="text-xs text-muted-foreground">Страна оплаты поставщику</Label>
          {canEdit ? (
            <SearchableCombobox<CountryItem>
              value={supplierPaymentCountry}
              onChange={onSupplierPaymentCountryChange}
              items={countries}
              getLabel={(c) => c.name}
              placeholder="Выберите страну"
              emptyMessage="Нет стран"
              className="mt-1"
            />
          ) : (
            <p className="text-sm mt-1">{supplierPaymentCountry || "—"}</p>
          )}
        </div>
      </div>
    </Card>
  );
}
