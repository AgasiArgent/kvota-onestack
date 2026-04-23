import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { WorkspaceAnalyticsRow } from "../api/server-queries";

interface AnalyticsPanelProps {
  domain: "logistics" | "customs";
  rows: WorkspaceAnalyticsRow[];
}

/**
 * Formats a duration in hours for display. Uses hours up to 24h, days beyond.
 * Examples: 3.2 → "3.2 ч", 28 → "1.2 д", 0 → "—".
 */
function formatDuration(hours: number): string {
  if (!hours || hours <= 0) return "—";
  if (hours < 24) return `${hours.toFixed(1)} ч`;
  return `${(hours / 24).toFixed(1)} д`;
}

function formatOnTime(onTime: number, onTimePct: number, total: number): string {
  if (!total) return "—";
  return `${onTime} / ${total} (${onTimePct.toFixed(0)}%)`;
}

/**
 * AnalyticsPanel — per-user completion table for head_of_* on workspace pages.
 *
 * Columns:
 *   - Пользователь
 *   - Завершено инвойсов
 *   - Медианное время (created → completed)
 *   - В срок (count + %)
 *
 * Source: GET /api/workspace/{domain}/analytics (see server-queries.ts).
 * Server-rendered — no client interactivity needed.
 */
export function AnalyticsPanel({ domain, rows }: AnalyticsPanelProps) {
  const title =
    domain === "logistics"
      ? "Производительность логистов"
      : "Производительность таможенников";

  return (
    <section className="rounded-lg border border-border-light bg-card">
      <header className="px-4 py-3 border-b border-border-light">
        <h2 className="text-sm font-semibold text-text tracking-tight">
          {title}
        </h2>
        <p className="text-xs text-text-muted mt-0.5">
          Кто сколько отработал — завершённые инвойсы и медианное время
        </p>
      </header>

      {rows.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-text-muted">
          Нет данных для отображения
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-4">Пользователь</TableHead>
              <TableHead className="text-right">Завершено инвойсов</TableHead>
              <TableHead className="text-right">Медианное время</TableHead>
              <TableHead className="text-right pr-4">В срок</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.user_id}>
                <TableCell className="pl-4 font-medium text-text">
                  {row.user_name}
                </TableCell>
                <TableCell className="text-right tabular-nums text-text">
                  {row.completed_count}
                </TableCell>
                <TableCell className="text-right tabular-nums text-text">
                  {formatDuration(row.median_hours)}
                </TableCell>
                <TableCell className="text-right tabular-nums text-text pr-4">
                  {formatOnTime(
                    row.on_time_count,
                    row.on_time_pct,
                    row.completed_count,
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
