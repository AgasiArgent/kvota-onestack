"use client";

import { useState, useEffect, useCallback } from "react";
import { FileText, Loader2 } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import { ENTITY_TYPE_LABELS } from "./constants";
import { DocumentUpload } from "./document-upload";
import { DocumentGroup, type DocumentRow } from "./document-group";
import { PromoteDocumentDialog } from "./promote-document-dialog";

interface DocumentsStepProps {
  quote: QuoteDetailRow;
  userId: string;
}

// Non-quote official documents (supplier invoices, specs, etc.) keep their
// existing entity-type grouping. Only entity_type='quote' docs are split
// into "official" vs "chat media".
const NON_QUOTE_ENTITY_TYPE_ORDER = [
  "supplier_invoice",
  "quote_item",
  "specification",
];

export function DocumentsStep({ quote, userId }: DocumentsStepProps) {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [promoteTarget, setPromoteTarget] = useState<DocumentRow | null>(null);

  const quoteAny = quote as Record<string, unknown>;
  const orgId = quoteAny.organization_id as string;

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    const { data, error } = await supabase
      .from("documents")
      .select(
        "id, entity_type, entity_id, storage_path, original_filename, file_size_bytes, mime_type, document_type, description, created_at, comment_id, status"
      )
      .eq("parent_quote_id", quote.id)
      .order("created_at", { ascending: false });

    if (!error && data) {
      setDocuments(data as DocumentRow[]);
    }
    setLoading(false);
  }, [quote.id]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  // Partition quote-scoped documents into:
  //   - official: document_type is set (direct uploads + promoted chat media
  //     + legacy pre-migration docs, which always had document_type)
  //   - chat media: document_type is NULL AND comment_id IS NOT NULL
  // Docs with no document_type AND no comment_id are orphans from a failed
  // chat upload — we hide them from the UI (they sit in the bucket/table
  // until a cleanup job runs).
  // Everything with entity_type != 'quote' falls into "other" groups.
  const quoteOfficial: DocumentRow[] = [];
  const chatMedia: DocumentRow[] = [];
  const nonQuoteByType = new Map<string, DocumentRow[]>();

  for (const doc of documents) {
    if (doc.entity_type === "quote") {
      if (doc.document_type) {
        quoteOfficial.push(doc);
      } else if (doc.comment_id) {
        chatMedia.push(doc);
      }
      // else: orphan — skip
    } else {
      const group = nonQuoteByType.get(doc.entity_type) ?? [];
      group.push(doc);
      nonQuoteByType.set(doc.entity_type, group);
    }
  }

  const sortedOtherGroups = [
    ...NON_QUOTE_ENTITY_TYPE_ORDER.filter((et) => nonQuoteByType.has(et)).map(
      (et) => ({
        entityType: et,
        title: ENTITY_TYPE_LABELS[et] ?? et,
        docs: nonQuoteByType.get(et)!,
      })
    ),
    ...Array.from(nonQuoteByType.entries())
      .filter(([et]) => !NON_QUOTE_ENTITY_TYPE_ORDER.includes(et))
      .map(([et, docs]) => ({
        entityType: et,
        title: ENTITY_TYPE_LABELS[et] ?? et,
        docs,
      })),
  ];

  const hasNoDocuments =
    quoteOfficial.length === 0 &&
    chatMedia.length === 0 &&
    sortedOtherGroups.length === 0;

  return (
    <div className="flex-1 min-w-0 flex flex-col">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <DocumentUpload
          quoteId={quote.id}
          orgId={orgId}
          userId={userId}
          onUploaded={loadDocuments}
        />

        {hasNoDocuments && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <FileText size={40} strokeWidth={1} />
            <p className="text-sm mt-3">Документы не найдены</p>
            <p className="text-xs mt-1">
              Загрузите документ с помощью формы выше или отправьте файл в чате
            </p>
          </div>
        )}

        {/* Official quote documents (direct uploads + promoted chat media) */}
        {(quoteOfficial.length > 0 || chatMedia.length > 0) && (
          <DocumentGroup
            title={ENTITY_TYPE_LABELS.quote ?? "Документы КП"}
            documents={quoteOfficial}
            onDeleted={loadDocuments}
            emptyMessage="Пока нет официальных документов. Повысьте файл из чата ниже."
          />
        )}

        {/* Chat media — files shared in the quote chat */}
        {chatMedia.length > 0 && (
          <DocumentGroup
            title="Медиа из чата"
            documents={chatMedia}
            onDeleted={loadDocuments}
            onPromote={(doc) => setPromoteTarget(doc)}
          />
        )}

        {/* Other entity groups (supplier invoices, specs, etc.) */}
        {sortedOtherGroups.map((group) => (
          <DocumentGroup
            key={group.entityType}
            title={group.title}
            documents={group.docs}
            onDeleted={loadDocuments}
          />
        ))}
      </div>

      <PromoteDocumentDialog
        document={promoteTarget}
        onClose={() => setPromoteTarget(null)}
        onPromoted={() => {
          setPromoteTarget(null);
          void loadDocuments();
        }}
      />
    </div>
  );
}
