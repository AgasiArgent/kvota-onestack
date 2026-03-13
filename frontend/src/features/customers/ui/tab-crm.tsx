import { Users, MapPin, StickyNote, Star } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Customer, CustomerContact } from "@/entities/customer";

interface Props {
  customer: Customer;
  contacts: CustomerContact[];
}

export function TabCRM({ customer, contacts }: Props) {
  return (
    <div className="space-y-6">
      <ContactsSection contacts={contacts} />
      <Separator />
      <AddressesSection customer={customer} />
      <Separator />
      <NotesSection notes={customer.notes} />
    </div>
  );
}

function ContactsSection({ contacts }: { contacts: CustomerContact[] }) {
  return (
    <div>
      <h3 className="text-base font-semibold mb-3">Контакты</h3>
      {contacts.length === 0 ? (
        <div className="py-12 text-center">
          <Users size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет контактов</p>
          <p className="text-xs text-text-subtle">Контакты этого клиента появятся здесь</p>
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">
                  {c.name}
                  {c.is_primary && <Star size={14} className="ml-1 text-yellow-500 fill-yellow-500 inline" />}
                  {c.is_lpr && <span className="ml-1 text-accent text-xs">ЛПР</span>}
                </TableCell>
                <TableCell className="text-text-muted">{c.position ?? "—"}</TableCell>
                <TableCell>
                  {c.email ? (
                    <a href={`mailto:${c.email}`} className="text-accent hover:underline">
                      {c.email}
                    </a>
                  ) : "—"}
                </TableCell>
                <TableCell>
                  {c.phone ? (
                    <a href={`tel:${c.phone}`} className="text-accent hover:underline">
                      {c.phone}
                    </a>
                  ) : "—"}
                </TableCell>
                <TableCell className="text-text-muted max-w-[200px] truncate">
                  {c.notes ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function AddressesSection({ customer }: { customer: Customer }) {
  const addresses = [
    { label: "Юридический", value: customer.legal_address },
    { label: "Фактический", value: customer.actual_address },
    { label: "Почтовый", value: customer.postal_address },
  ];

  const hasAnyAddress = addresses.some((a) => a.value);
  const hasWarehouses = customer.warehouse_addresses && customer.warehouse_addresses.length > 0;

  return (
    <div>
      <h3 className="text-base font-semibold mb-3">Адреса</h3>
      {!hasAnyAddress && !hasWarehouses ? (
        <div className="py-12 text-center">
          <MapPin size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет адресов</p>
          <p className="text-xs text-text-subtle">Адреса клиента появятся здесь</p>
        </div>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Официальные адреса</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {addresses.map((addr) => (
                <div key={addr.label}>
                  <div className="text-xs font-semibold text-text-subtle uppercase">{addr.label}</div>
                  <div className="text-sm">{addr.value || "Не указан"}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Склады</CardTitle>
            </CardHeader>
            <CardContent>
              {hasWarehouses ? (
                <div className="space-y-2">
                  {customer.warehouse_addresses!.map((wh, i) => (
                    <div key={i} className="text-sm">
                      {wh.label && <span className="font-medium">{wh.label}: </span>}
                      {wh.address}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-text-subtle text-sm">Нет адресов складов</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function NotesSection({ notes }: { notes: string | null }) {
  return (
    <div>
      <h3 className="text-base font-semibold mb-3">Заметки</h3>
      {notes ? (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm whitespace-pre-wrap">{notes}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="py-12 text-center">
          <StickyNote size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет заметок</p>
          <p className="text-xs text-text-subtle">Заметки и примечания появятся здесь</p>
        </div>
      )}
    </div>
  );
}
