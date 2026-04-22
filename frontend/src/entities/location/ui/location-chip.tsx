import type { ReactNode } from "react";
import { Factory, Warehouse, ShieldCheck, Building2, User, MapPin, Globe } from "lucide-react";
import { CountryFlag } from "@/shared/ui/country-flag";
import { countryNameToIso2 } from "@/shared/lib/country";
import { cn } from "@/lib/utils";

/**
 * LocationChip — inline pill for locations: workspace tables, route
 * constructor timeline, admin routing patterns.
 *
 * Variants:
 *   - solid    (default)  — filled warm-gray background
 *   - wildcard            — dashed border + italic, for "* Любой"
 *   - ghost               — transparent, compact inline use
 *
 * Country resolution:
 *   - `iso2` if provided → direct flag lookup
 *   - else → `countryNameToIso2(country)` (shared/lib/country.ts)
 *   - unknown country → neutral globe glyph (no flag)
 *
 * Data source: locations.{country, city, location_type}. See spec §5.2.
 */

export type LocationType = "supplier" | "hub" | "customs" | "own_warehouse" | "client";

export interface LocationChipLocation {
  /** Human-readable country name as stored in DB (e.g. "Китай"). */
  country: string;
  /** Optional precomputed iso2; preferred when available. */
  iso2?: string;
  /** City name shown as trailing "· City". */
  city?: string;
  /** Location type drives leading icon when no flag is available. */
  type?: LocationType;
  /** Overrides the default label (country [· city]). */
  name?: string;
}

interface LocationChipProps {
  location?: LocationChipLocation;
  variant?: "solid" | "wildcard" | "ghost";
  size?: "sm" | "md";
  /** Override label entirely (e.g. "* Любой" for wildcards). */
  label?: string;
  trailing?: ReactNode;
  className?: string;
}

const TYPE_ICON: Record<LocationType, typeof Factory> = {
  supplier: Factory,
  hub: Warehouse,
  customs: ShieldCheck,
  own_warehouse: Building2,
  client: User,
};

function buildLabel(loc: LocationChipLocation): string {
  if (loc.name) return loc.name;
  if (loc.city && loc.country) return `${loc.country} · ${loc.city}`;
  return loc.country || "—";
}

export function LocationChip({
  location,
  variant = "solid",
  size = "md",
  label,
  trailing,
  className,
}: LocationChipProps) {
  const isWildcard = variant === "wildcard";
  const isGhost = variant === "ghost";

  const resolvedLabel = label ?? (location ? buildLabel(location) : "—");

  const iso2 = location?.iso2 ?? countryNameToIso2(location?.country);

  const baseCls =
    "inline-flex items-center gap-1.5 rounded-sm font-medium whitespace-nowrap";
  const sizeCls = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  const variantCls = isWildcard
    ? "bg-transparent border border-dashed border-border text-text-muted italic"
    : isGhost
      ? "bg-transparent text-text"
      : "bg-sidebar border border-border-light text-text";

  let leading: ReactNode = null;
  if (!isWildcard) {
    if (iso2) {
      leading = (
        <CountryFlag
          iso2={iso2}
          className={size === "sm" ? "text-[13px]" : "text-[14px] leading-none"}
        />
      );
    } else if (location?.type) {
      const Icon = TYPE_ICON[location.type] ?? MapPin;
      leading = (
        <Icon
          size={size === "sm" ? 12 : 14}
          strokeWidth={2}
          className="text-text-muted"
          aria-hidden
        />
      );
    } else if (location?.country) {
      leading = (
        <Globe
          size={size === "sm" ? 12 : 14}
          strokeWidth={2}
          className="text-text-subtle"
          aria-hidden
        />
      );
    }
  }

  return (
    <span className={cn(baseCls, sizeCls, variantCls, className)}>
      {leading}
      <span>{resolvedLabel}</span>
      {trailing}
    </span>
  );
}
