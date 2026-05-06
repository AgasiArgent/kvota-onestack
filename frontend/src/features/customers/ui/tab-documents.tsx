"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { ScrollableTable } from "@/shared/ui/scrollable-table";
import { Plus, Pencil, Trash2, FileText, Upload, Download, Loader2 } from "lucide-react";
import type {
  CustomerContract,
  CustomerDocumentRow,
} from "@/entities/customer";
import {
  deleteContract,
  uploadCustomerDocument,
  deleteCustomerDocument,
} from "@/entities/customer/mutations";
import { ContractFormModal } from "./contract-form-modal";
import { useRouter } from "next/navigation";
import { createClient } from "@/shared/lib/supabase/client";
import { toast } from "sonner";

interface Quote {
  id: string;
  idn: string;
  total_amount: number | null;
  profit_amount: number | null;
  created_at: string | null;
  status: string;
}

interface Spec {
  id: string;
  idn: string | null;
  total_amount: number | null;
  profit_amount: number | null;
  created_at: string | null;
  status: string;
}

interface Props {
  customerId: string;
  quotes: Quote[];
  specs: Spec[];
  contracts: CustomerContract[];
  contractDocs: CustomerDocumentRow[];
  foundingDocs: CustomerDocumentRow[];
  initialSubTab?: string;
}

type SubTab = "quotes" | "specs";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "quotes", label: "КП" },
  { key: "specs", label: "Спецификации" },
];

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  calculating: "Расчёт",
  calculated: "Рассчитан",
  in_review: "На проверке",
  approved: "Одобрен",
  rejected: "Отклонён",
  cancelled: "Отменён",
  signed: "Подписана",
  active: "Активна",
  completed: "Завершена",
};

const CONTRACT_STATUS_LABELS: Record<string, string> = {
  active: "Действующий",
  suspended: "Приостановлен",
  terminated: "Расторгнут",
};

function contractStatusVariant(status: string): "default" | "outline" | "destructive" {
  switch (status) {
    case "active":
      return "default";
    case "suspended":
      return "outline";
    case "terminated":
      return "destructive";
    default:
      return "outline";
  }
}

export function TabDocuments({
  customerId,
  quotes,
  specs,
  contracts,
  contractDocs,
  foundingDocs,
  initialSubTab,
}: Props) {
  const router = useRouter();
  const [activeSubTab, setActiveSubTab] = useState<SubTab>(
    (initialSubTab as SubTab) ?? "quotes"
  );
  const [contractModalOpen, setContractModalOpen] = useState(false);
  const [editingContract, setEditingContract] = useState<CustomerContract | undefined>();

  function formatDate(d: string | null) {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("ru-RU");
  }

  function formatAmount(n: number | null) {
    if (n == null) return "—";
    return `$${n.toLocaleString("ru-RU")}`;
  }

  function handleAddContract() {
    setEditingContract(undefined);
    setContractModalOpen(true);
  }

  function handleEditContract(contract: CustomerContract) {
    setEditingContract(contract);
    setContractModalOpen(true);
  }

  async function handleDeleteContract(contract: CustomerContract) {
    const confirmed = window.confirm(
      `Удалить договор ${contract.contract_number}?`
    );
    if (!confirmed) return;

    try {
      await deleteContract(contract.id);
      router.refresh();
    } catch (err) {
      console.error("Failed to delete contract:", err);
      alert("Не удалось удалить договор. Попробуйте ещё раз.");
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Уставные документы (МОП-8) */}
      <CustomerDocumentsSection
        customerId={customerId}
        documentType="founding_docs"
        title="Уставные документы"
        emptyText="Нет уставных документов"
        documents={foundingDocs}
        testId="founding-docs"
      />

      {/* Contract attachments (МОП-7) */}
      <CustomerDocumentsSection
        customerId={customerId}
        documentType="contract"
        title="Файлы договоров"
        emptyText="Нет прикреплённых файлов"
        documents={contractDocs}
        testId="contract-docs"
      />

      {/* Contracts section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
            Договоры
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={handleAddContract}
          >
            <Plus className="size-4" />
            Добавить договор
          </Button>
        </div>

        {contracts.length === 0 ? (
          <p className="py-4 text-center text-text-subtle text-sm">
            Нет договоров
          </p>
        ) : (
          <ScrollableTable>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Номер</TableHead>
                  <TableHead>Дата</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Заметки</TableHead>
                  <TableHead className="w-[80px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {contracts.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">
                      {c.contract_number}
                    </TableCell>
                    <TableCell className="text-text-muted tabular-nums">
                      {formatDate(c.contract_date)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={contractStatusVariant(c.status)}>
                        {CONTRACT_STATUS_LABELS[c.status] ?? c.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-text-muted max-w-[200px] truncate">
                      {c.notes ?? "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7"
                          onClick={() => handleEditContract(c)}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-error hover:text-error"
                          onClick={() => handleDeleteContract(c)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollableTable>
        )}
      </section>

      {/* KP / Specs sub-tabs */}
      <section>
        <div className="flex gap-2 mb-6">
          {SUB_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveSubTab(tab.key)}
              className={cn(
                "px-3 py-1.5 text-sm rounded-md transition-colors",
                activeSubTab === tab.key
                  ? "bg-accent-subtle text-accent font-medium"
                  : "text-text-muted hover:bg-sidebar"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeSubTab === "quotes" && (
          <DocumentTable
            items={quotes}
            emptyText="Нет КП"
            linkPrefix="/quotes"
            formatDate={formatDate}
            formatAmount={formatAmount}
          />
        )}
        {activeSubTab === "specs" && (
          <DocumentTable
            items={specs}
            emptyText="Нет спецификаций"
            linkPrefix="/specifications"
            formatDate={formatDate}
            formatAmount={formatAmount}
          />
        )}
      </section>

      <ContractFormModal
        open={contractModalOpen}
        onClose={() => setContractModalOpen(false)}
        onSaved={() => {}}
        customerId={customerId}
        contract={editingContract}
      />
    </div>
  );
}

function CustomerDocumentsSection({
  customerId,
  documentType,
  title,
  emptyText,
  documents,
  testId,
}: {
  customerId: string;
  documentType: "contract" | "founding_docs";
  title: string;
  emptyText: string;
  documents: CustomerDocumentRow[];
  testId: string;
}) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadCustomerDocument(customerId, file, documentType);
      toast.success(`Файл "${file.name}" загружен`);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDownload(doc: CustomerDocumentRow) {
    setDownloadingId(doc.id);
    try {
      const supabase = createClient();
      const { data, error } = await supabase.storage
        .from("kvota-documents")
        .createSignedUrl(doc.storage_path, 60);
      if (error) throw error;
      if (data?.signedUrl) {
        window.open(data.signedUrl, "_blank");
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось открыть файл"
      );
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(doc: CustomerDocumentRow) {
    const confirmed = window.confirm(`Удалить файл "${doc.original_filename}"?`);
    if (!confirmed) return;
    setDeletingId(doc.id);
    try {
      await deleteCustomerDocument(doc.id, doc.storage_path);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка удаления");
    } finally {
      setDeletingId(null);
    }
  }

  function formatSize(bytes: number | null) {
    if (bytes == null) return "—";
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  }

  function formatDate(d: string | null) {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("ru-RU");
  }

  return (
    <section data-testid={`section-${testId}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
          {title}
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          data-testid={`upload-${testId}`}
        >
          {uploading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Upload className="size-4" />
          )}
          {uploading ? "Загрузка..." : "Загрузить файл"}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx"
          onChange={handleFile}
          data-testid={`upload-input-${testId}`}
        />
      </div>

      {documents.length === 0 ? (
        <p className="py-4 text-center text-text-subtle text-sm">{emptyText}</p>
      ) : (
        <ScrollableTable>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Файл</TableHead>
                <TableHead className="w-[120px]">Размер</TableHead>
                <TableHead className="w-[120px]">Загружен</TableHead>
                <TableHead className="w-[100px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="font-medium">
                    <span className="inline-flex items-center gap-2">
                      <FileText className="size-4 shrink-0 text-text-muted" />
                      <span className="truncate" title={doc.original_filename}>
                        {doc.original_filename}
                      </span>
                    </span>
                    {doc.description && (
                      <p className="mt-0.5 text-xs text-text-subtle truncate">
                        {doc.description}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="tabular-nums text-text-muted">
                    {formatSize(doc.file_size_bytes)}
                  </TableCell>
                  <TableCell className="text-text-muted tabular-nums">
                    {formatDate(doc.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        onClick={() => handleDownload(doc)}
                        disabled={downloadingId === doc.id}
                        title="Скачать"
                      >
                        {downloadingId === doc.id ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Download className="size-3.5" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-error hover:text-error"
                        onClick={() => handleDelete(doc)}
                        disabled={deletingId === doc.id}
                        title="Удалить"
                      >
                        {deletingId === doc.id ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="size-3.5" />
                        )}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollableTable>
      )}
    </section>
  );
}

function DocumentTable({
  items,
  emptyText,
  linkPrefix,
  formatDate,
  formatAmount,
}: {
  items: { id: string; idn: string | null; total_amount: number | null; profit_amount: number | null; created_at: string | null; status: string }[];
  emptyText: string;
  linkPrefix: string;
  formatDate: (d: string | null) => string;
  formatAmount: (n: number | null) => string;
}) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-text-subtle">{emptyText}</p>;
  }
  return (
    <ScrollableTable>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>No.</TableHead>
            <TableHead>Сумма</TableHead>
            <TableHead>Профит</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell>
                <Link
                  href={`${linkPrefix}/${item.id}`}
                  className="text-accent hover:underline font-medium"
                >
                  {item.idn}
                </Link>
              </TableCell>
              <TableCell className="tabular-nums">{formatAmount(item.total_amount)}</TableCell>
              <TableCell className="tabular-nums">{formatAmount(item.profit_amount)}</TableCell>
              <TableCell className="text-text-muted">{formatDate(item.created_at)}</TableCell>
              <TableCell>
                <Badge variant="secondary">{STATUS_LABELS[item.status] ?? item.status}</Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ScrollableTable>
  );
}
