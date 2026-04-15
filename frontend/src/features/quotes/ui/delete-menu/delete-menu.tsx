"use client";

import { useState } from "react";
import { MoreVertical, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DeleteConfirmDialog } from "./delete-confirm-dialog";

interface DeleteMenuProps {
  /**
   * Quote ID. Spec/Deal stages of the same entity must pass their
   * parent quote_id — the single `/api/quotes/{id}/soft-delete` endpoint
   * cascades to the attached specification and deal rows.
   */
  quoteId: string;
  /** idn_quote for display in the confirmation dialog. */
  entityName: string;
  /** Current user roles. Menu renders only when 'admin' is present. */
  roles: string[];
}

/**
 * Destructive-action menu for quote/spec/deal detail headers.
 *
 * Visible to admins only — hidden completely for other roles (absent,
 * not disabled). Clicking the menu item opens a confirmation dialog
 * before calling the soft-delete endpoint.
 */
export function DeleteMenu({ quoteId, entityName, roles }: DeleteMenuProps) {
  const [dialogOpen, setDialogOpen] = useState(false);

  if (!roles.includes("admin")) {
    return null;
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Действия с КП"
        >
          <MoreVertical size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem
            variant="destructive"
            onClick={() => setDialogOpen(true)}
          >
            <Trash2 size={14} />
            Удалить квоту
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <DeleteConfirmDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        quoteId={quoteId}
        entityName={entityName}
      />
    </>
  );
}
