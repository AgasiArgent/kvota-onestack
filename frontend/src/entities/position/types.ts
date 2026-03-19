export type AvailabilityStatus = "available" | "unavailable" | "mixed";

export interface ProductListItem {
  brand: string;
  idnSku: string;
  productName: string;
  latestPrice: number | null;
  latestCurrency: string | null;
  lastMozName: string | null;
  lastMozId: string | null;
  lastUpdated: string;
  entryCount: number;
  availabilityStatus: AvailabilityStatus;
}

export interface SourcingEntry {
  id: string;
  quoteId: string;
  quoteIdn: string;
  updatedAt: string;
  isUnavailable: boolean;
  price: number | null;
  currency: string | null;
  mozName: string | null;
  proformaNumber: string | null;
}
