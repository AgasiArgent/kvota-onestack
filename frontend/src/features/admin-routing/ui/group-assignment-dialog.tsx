"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UserSelect } from "./user-select";
import type { SalesGroup } from "../model/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  availableGroups: SalesGroup[];
  onSubmit: (groupId: string, userId: string) => Promise<void>;
}

export function GroupAssignmentDialog({
  open,
  onOpenChange,
  orgId,
  availableGroups,
  onSubmit,
}: Props) {
  const [groupId, setGroupId] = useState("");
  const [userId, setUserId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setGroupId("");
      setUserId("");
    }
  }, [open]);

  async function handleSubmit() {
    if (!groupId || !userId) return;

    setSubmitting(true);
    try {
      await onSubmit(groupId, userId);
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !submitting && onOpenChange(val)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Добавить правило группы</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Группа продаж <span className="text-error">*</span>
            </Label>
            <Select value={groupId} onValueChange={(val) => setGroupId(val ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите группу" />
              </SelectTrigger>
              <SelectContent>
                {availableGroups.map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </fieldset>
          <fieldset className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Менеджер закупок <span className="text-error">*</span>
            </Label>
            <UserSelect
              value={userId}
              onValueChange={setUserId}
              orgId={orgId}
            />
          </fieldset>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!groupId || !userId || submitting}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Создать правило
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
