"use client";

interface MetricCardProps {
  value: string;
  label: string;
  variant?: "default" | "accent" | "warning";
}

export function MetricCard({ value, label, variant = "default" }: MetricCardProps) {
  const valueColor =
    variant === "accent"
      ? "text-emerald-600"
      : variant === "warning"
        ? "text-amber-600"
        : "text-foreground";

  return (
    <div className="flex flex-col items-center gap-1 min-w-[100px]">
      <span className={`text-2xl font-semibold tabular-nums ${valueColor}`}>
        {value}
      </span>
      <span className="text-xs text-muted-foreground text-center leading-tight">
        {label}
      </span>
    </div>
  );
}
