"use client";

import Link from "next/link";
import type { SourcingEntry } from "@/entities/position/types";
import { AvailabilityBadge } from "./positions-table";
import { formatDate, formatPrice } from "./format";

interface Props {
  entries: SourcingEntry[];
}

export function PositionHistory({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <tr>
        <td colSpan={8} className="px-6 py-3 bg-muted/50 text-sm text-text-muted">
          Нет записей
        </td>
      </tr>
    );
  }

  return (
    <>
      {entries.map((entry) => (
        <tr
          key={entry.id}
          className={`bg-muted/50 border-b border-border-light text-sm ${
            entry.isUnavailable ? "opacity-50" : ""
          }`}
        >
          {/* Empty cell for expand chevron column */}
          <td className="px-3 py-2" />
          {/* Status */}
          <td className="px-3 py-2">
            <AvailabilityBadge status={entry.isUnavailable ? "unavailable" : "available"} />
          </td>
          {/* Brand — empty for detail rows */}
          <td className="px-3 py-2" />
          {/* SKU — show proforma instead */}
          <td className="px-3 py-2 text-text-muted">
            {entry.proformaNumber ?? "—"}
          </td>
          {/* Quote link */}
          <td className="px-3 py-2">
            <Link
              href={`/quotes/${entry.quoteId}`}
              className="text-accent hover:underline"
            >
              {entry.quoteIdn || "—"}
            </Link>
          </td>
          {/* Price */}
          <td className="px-3 py-2 tabular-nums text-text-muted">
            {entry.isUnavailable ? "Недоступен" : formatPrice(entry.price, entry.currency)}
          </td>
          {/* MOZ */}
          <td className="px-3 py-2 text-text-muted">
            {entry.mozName ?? "—"}
          </td>
          {/* Date */}
          <td className="px-3 py-2 tabular-nums text-text-muted">
            {formatDate(entry.updatedAt)}
          </td>
        </tr>
      ))}
    </>
  );
}
