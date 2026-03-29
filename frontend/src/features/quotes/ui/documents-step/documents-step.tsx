"use client";

import { useState, useEffect, useCallback } from "react";
import { FileText, Loader2 } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import { ENTITY_TYPE_LABELS } from "./constants";
import { DocumentUpload } from "./document-upload";
import { DocumentGroup, type DocumentRow } from "./document-group";

interface DocumentsStepProps {
  quote: QuoteDetailRow;
  userId: string;
}

const ENTITY_TYPE_ORDER = [
  "quote",
  "supplier_invoice",
  "quote_item",
  "specification",
];

export function DocumentsStep({ quote, userId }: DocumentsStepProps) {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);

  const quoteAny = quote as Record<string, unknown>;
  const orgId = quoteAny.organization_id as string;

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    const { data, error } = await supabase
      .from("documents")
      .select(
        "id, entity_type, entity_id, storage_path, original_filename, file_size_bytes, mime_type, document_type, description, created_at"
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

  // Group documents by entity_type
  const grouped = new Map<string, DocumentRow[]>();
  for (const doc of documents) {
    const group = grouped.get(doc.entity_type) ?? [];
    group.push(doc);
    grouped.set(doc.entity_type, group);
  }

  // Sort groups by predefined order
  const sortedGroups = ENTITY_TYPE_ORDER.filter((et) => grouped.has(et)).map(
    (et) => ({
      entityType: et,
      title: ENTITY_TYPE_LABELS[et] ?? et,
      docs: grouped.get(et)!,
    })
  );

  // Append any unknown entity types at the end
  for (const [et, docs] of grouped) {
    if (!ENTITY_TYPE_ORDER.includes(et)) {
      sortedGroups.push({
        entityType: et,
        title: ENTITY_TYPE_LABELS[et] ?? et,
        docs,
      });
    }
  }

  return (
    <div className="flex-1 min-w-0 flex flex-col">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <DocumentUpload
          quoteId={quote.id}
          orgId={orgId}
          userId={userId}
          onUploaded={loadDocuments}
        />

        {sortedGroups.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <FileText size={40} strokeWidth={1} />
            <p className="text-sm mt-3">Документы не найдены</p>
            <p className="text-xs mt-1">
              Загрузите документ с помощью формы выше
            </p>
          </div>
        )}

        {sortedGroups.map((group) => (
          <DocumentGroup
            key={group.entityType}
            title={group.title}
            documents={group.docs}
            onDeleted={loadDocuments}
          />
        ))}
      </div>
    </div>
  );
}
