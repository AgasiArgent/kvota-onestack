import type { ProcurementUserWorkload } from "../model/types";

interface Props {
  users: ProcurementUserWorkload[];
}

export function WorkloadCards({ users }: Props) {
  if (users.length === 0) return null;

  return (
    <div>
      <h3 className="text-sm font-medium text-text-muted mb-3">
        Загрузка закупщиков
      </h3>
      <div className="flex flex-wrap gap-3">
        {users.map((u) => (
          <div
            key={u.user_id}
            className="px-4 py-3 rounded-lg border border-border-light bg-surface text-center min-w-[120px]"
          >
            <p className="text-sm font-medium text-text truncate">
              {u.full_name ?? "—"}
            </p>
            <p className="text-2xl font-bold text-accent mt-1">
              {u.active_items}
            </p>
            <p className="text-xs text-text-muted">позиций</p>
          </div>
        ))}
      </div>
    </div>
  );
}
