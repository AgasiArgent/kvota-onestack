"use client";

import { LocationChip } from "@/entities/location/ui/location-chip";
import type { LogisticsSegmentLocationRef } from "@/entities/logistics-segment";
import { cn } from "@/lib/utils";

/**
 * SegmentNode — a location chip rendered as a timeline node. Wraps
 * {@link LocationChip} with consistent fallback styling for unfilled
 * locations (a template just applied with null placeholders yields
 * empty from/to values until the logistician picks concrete ones).
 */

interface SegmentNodeProps {
  location?: LogisticsSegmentLocationRef;
  placeholder?: string;
  size?: "sm" | "md";
  className?: string;
}

export function SegmentNode({
  location,
  placeholder = "Не выбрано",
  size = "sm",
  className,
}: SegmentNodeProps) {
  if (!location) {
    return (
      <LocationChip
        variant="wildcard"
        size={size}
        label={placeholder}
        className={className}
      />
    );
  }
  return (
    <LocationChip
      location={location}
      size={size}
      className={cn(className)}
    />
  );
}
