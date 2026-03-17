"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Users, Plus, Pencil, Trash2, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SupplierContact } from "@/entities/supplier/types";
import { deleteSupplierContact } from "@/entities/supplier/mutations";
import { ContactFormModal } from "./contact-form-modal";

interface Props {
  supplierId: string;
  contacts: SupplierContact[];
}

export function TabContacts({ supplierId, contacts }: Props) {
  const router = useRouter();
  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<SupplierContact | undefined>();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function handleContactSaved() {
    router.refresh();
  }

  function openEditContact(contact: SupplierContact) {
    setEditingContact(contact);
    setContactModalOpen(true);
  }

  function openNewContact() {
    setEditingContact(undefined);
    setContactModalOpen(true);
  }

  async function handleDelete(contactId: string) {
    setDeletingId(contactId);
    try {
      await deleteSupplierContact(contactId);
      router.refresh();
    } catch (err) {
      console.error("Failed to delete contact:", err);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Контакты</h3>
        <Button size="sm" variant="outline" onClick={openNewContact}>
          <Plus size={14} />
          Добавить
        </Button>
      </div>
      {contacts.length === 0 ? (
        <div className="py-12 text-center">
          <Users size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет контактов</p>
          <p className="text-xs text-text-subtle">Контакты этого поставщика появятся здесь</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ФИО</TableHead>
              <TableHead>Должность</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Телефон</TableHead>
              <TableHead>Заметки</TableHead>
              <TableHead className="w-[80px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">
                  {c.name}
                  {c.is_primary && (
                    <Star size={14} className="ml-1 text-yellow-500 fill-yellow-500 inline" />
                  )}
                </TableCell>
                <TableCell className="text-text-muted">{c.position ?? "—"}</TableCell>
                <TableCell>
                  {c.email ? (
                    <a href={`mailto:${c.email}`} className="text-accent hover:underline">
                      {c.email}
                    </a>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>
                  {c.phone ? (
                    <a href={`tel:${c.phone}`} className="text-accent hover:underline">
                      {c.phone}
                    </a>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell className="text-text-muted max-w-[200px] truncate">
                  {c.notes ?? "—"}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => openEditContact(c)}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted"
                      title="Редактировать"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(c.id)}
                      disabled={deletingId === c.id}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-error"
                      title="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <ContactFormModal
        open={contactModalOpen}
        onClose={() => {
          setContactModalOpen(false);
          setEditingContact(undefined);
        }}
        onSaved={handleContactSaved}
        supplierId={supplierId}
        contact={editingContact}
      />
    </div>
  );
}
