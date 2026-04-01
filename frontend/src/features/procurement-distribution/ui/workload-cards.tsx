import type { ProcurementUserWorkload } from "../model/types";

interface Props {
  users: ProcurementUserWorkload[];
}

/** "Числова Екатерина Романовна" → "Числова Е." */
function shortName(fullName: string | null): string {
  if (!fullName) return "—";
  const parts = fullName.trim().split(/\s+/);
  if (parts.length <= 1) return fullName;
  const surname = parts[0];
  const initial = parts[1][0];
  return `${surname} ${initial}.`;
}

export function WorkloadCards({ users }: Props) {
  if (users.length === 0) return null;

  return (
    <div>
      <h3 className="text-xs font-medium text-text-muted mb-2">
        Загрузка закупщиков
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {users.map((u) => (
          <div
            key={u.user_id}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-border-light bg-surface text-xs"
          >
            <span className="text-text truncate max-w-[100px]">
              {shortName(u.full_name)}
            </span>
            <span className="font-semibold text-accent min-w-[14px] text-center">
              {u.active_items}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
