import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { UserDepartment } from "@/entities/user";

interface Props {
  department: UserDepartment;
}

export function DepartmentSection({ department }: Props) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Подразделение</CardTitle>
          <span className="text-xs text-text-muted">Изменяется администратором</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex justify-between items-start">
          <span className="text-text-muted text-sm">Роли</span>
          <div className="flex flex-wrap gap-1.5 justify-end">
            {department.roles.length > 0 ? (
              department.roles.map((role) => (
                <Badge key={role.slug} variant="secondary">
                  {role.name}
                </Badge>
              ))
            ) : (
              <span className="text-sm">—</span>
            )}
          </div>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted text-sm">Руководитель</span>
          <span className="text-sm font-medium">
            {department.supervisor?.full_name ?? "—"}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
