"""
Document Service - File storage operations using Supabase Storage

This module provides functions for managing document uploads and metadata:
- Upload files to Supabase Storage bucket
- Store metadata in kvota.documents table
- Generate signed download URLs
- Delete documents (both file and metadata)

Files are stored in Supabase Storage bucket 'kvota-documents'.
Metadata (filename, type, entity link) is stored in PostgreSQL.

Entity types supported:
- supplier_invoice, quote, specification, quote_item
- supplier, customer, seller_company, buyer_company
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import os
import uuid
import mimetypes
from supabase import create_client, ClientOptions


# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Storage bucket name
BUCKET_NAME = "kvota-documents"

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Spreadsheets
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Archives
    "application/zip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    # Text
    "text/plain",
    "text/csv",
}

# Maximum file size (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Valid entity types
VALID_ENTITY_TYPES = {
    "supplier_invoice",
    "quote",
    "specification",
    "quote_item",
    "supplier",
    "customer",
    "seller_company",
    "buyer_company",
}

# Valid document types
VALID_DOCUMENT_TYPES = {
    "invoice_scan",
    "proforma_scan",
    "payment_order",
    "contract",
    "certificate",
    "ttn",
    "cmr",
    "bill_of_lading",
    "customs_declaration",
    "founding_docs",
    "license",
    "other",
}

# Document type labels (Russian)
DOCUMENT_TYPE_LABELS = {
    "invoice_scan": "Скан инвойса",
    "proforma_scan": "Скан проформы",
    "payment_order": "Платёжное поручение",
    "contract": "Договор",
    "certificate": "Сертификат",
    "ttn": "ТТН",
    "cmr": "CMR",
    "bill_of_lading": "Коносамент",
    "customs_declaration": "Таможенная декларация",
    "founding_docs": "Учредительные документы",
    "license": "Лицензия",
    "other": "Прочее",
}


def _get_supabase():
    """Get Supabase client with service role key - kvota schema."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY,
        options=ClientOptions(schema="kvota")
    )


def _get_storage_client():
    """Get Supabase client for storage operations (no schema override needed)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@dataclass
class Document:
    """
    Represents a document metadata record.

    Files are stored in Supabase Storage, this holds metadata.

    Hierarchical binding:
    - entity_type/entity_id: Direct binding to specific entity (quote, invoice, item)
    - parent_quote_id: For quick retrieval of ALL documents related to a quote
    """
    id: str
    organization_id: str
    entity_type: str
    entity_id: str
    storage_path: str
    original_filename: str
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    document_type: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None
    parent_quote_id: Optional[str] = None  # For hierarchical aggregation


def _parse_document(data: dict) -> Document:
    """Parse database row into Document object."""
    return Document(
        id=data["id"],
        organization_id=data["organization_id"],
        entity_type=data["entity_type"],
        entity_id=data["entity_id"],
        storage_path=data["storage_path"],
        original_filename=data["original_filename"],
        file_size_bytes=data.get("file_size_bytes"),
        mime_type=data.get("mime_type"),
        document_type=data.get("document_type"),
        description=data.get("description"),
        uploaded_by=data.get("uploaded_by"),
        created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        parent_quote_id=data.get("parent_quote_id"),
    )


# =============================================================================
# VALIDATION
# =============================================================================

def validate_entity_type(entity_type: str) -> bool:
    """Validate entity type is supported."""
    return entity_type in VALID_ENTITY_TYPES


def validate_document_type(document_type: Optional[str]) -> bool:
    """Validate document type if provided."""
    if document_type is None:
        return True
    return document_type in VALID_DOCUMENT_TYPES


def validate_mime_type(mime_type: str) -> bool:
    """Validate MIME type is allowed."""
    return mime_type in ALLOWED_MIME_TYPES


def validate_file_size(size_bytes: int) -> bool:
    """Validate file size is within limits."""
    return 0 < size_bytes <= MAX_FILE_SIZE


def get_mime_type(filename: str) -> str:
    """Get MIME type from filename."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


# =============================================================================
# STORAGE PATH GENERATION
# =============================================================================

def generate_storage_path(
    entity_type: str,
    entity_id: str,
    filename: str,
    organization_id: str,
) -> str:
    """
    Generate unique storage path for a file.

    Format: {org_id}/{entity_type}/{entity_id}/{uuid}_{filename}

    Example: abc123/quotes/def456/a1b2c3d4_invoice.pdf
    """
    # Generate unique prefix to avoid collisions
    unique_prefix = str(uuid.uuid4())[:8]

    # Sanitize filename (keep only safe characters)
    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    if not safe_filename:
        safe_filename = "document"

    return f"{organization_id}/{entity_type}s/{entity_id}/{unique_prefix}_{safe_filename}"


# =============================================================================
# UPLOAD Operations
# =============================================================================

def upload_document(
    organization_id: str,
    entity_type: str,
    entity_id: str,
    file_content: bytes,
    filename: str,
    *,
    document_type: Optional[str] = None,
    description: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    parent_quote_id: Optional[str] = None,
) -> Tuple[Optional[Document], Optional[str]]:
    """
    Upload a document to storage and create metadata record.

    Args:
        organization_id: Organization UUID
        entity_type: Type of parent entity (quote, supplier_invoice, quote_item, etc.)
        entity_id: UUID of parent entity
        file_content: File bytes
        filename: Original filename
        document_type: Classification (invoice_scan, contract, etc.)
        description: Optional description
        uploaded_by: User UUID who uploaded
        parent_quote_id: Parent quote ID for hierarchical aggregation (allows fetching
                         all documents for a quote including invoice docs and item certs)

    Returns:
        Tuple of (Document, None) on success, or (None, error_message) on failure

    Example:
        # Direct quote document
        doc, error = upload_document(
            organization_id="org-uuid",
            entity_type="quote",
            entity_id="quote-uuid",
            file_content=file_bytes,
            filename="contract.pdf",
            document_type="contract",
            parent_quote_id="quote-uuid"  # Same as entity_id for direct binding
        )

        # Invoice document linked to quote
        doc, error = upload_document(
            organization_id="org-uuid",
            entity_type="supplier_invoice",
            entity_id="invoice-uuid",
            file_content=file_bytes,
            filename="invoice_scan.pdf",
            document_type="invoice_scan",
            parent_quote_id="quote-uuid"  # Links to parent quote for aggregation
        )
    """
    # Validate entity type
    if not validate_entity_type(entity_type):
        return None, f"Invalid entity type: {entity_type}"

    # Validate document type
    if not validate_document_type(document_type):
        return None, f"Invalid document type: {document_type}"

    # Validate file size
    file_size = len(file_content)
    if not validate_file_size(file_size):
        return None, f"File too large: {file_size / 1024 / 1024:.1f} MB (max {MAX_FILE_SIZE / 1024 / 1024:.0f} MB)"

    # Get MIME type
    mime_type = get_mime_type(filename)
    if not validate_mime_type(mime_type):
        return None, f"File type not allowed: {mime_type}"

    # Generate storage path
    storage_path = generate_storage_path(entity_type, entity_id, filename, organization_id)

    try:
        # Upload to Supabase Storage
        storage_client = _get_storage_client()
        storage_result = storage_client.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type}
        )

        # Check if upload succeeded
        if hasattr(storage_result, 'error') and storage_result.error:
            return None, f"Storage upload failed: {storage_result.error}"

        # Create metadata record
        supabase = _get_supabase()
        insert_data = {
            "organization_id": organization_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "storage_path": storage_path,
            "original_filename": filename,
            "file_size_bytes": file_size,
            "mime_type": mime_type,
            "document_type": document_type,
            "description": description,
            "uploaded_by": uploaded_by,
            "parent_quote_id": parent_quote_id,
        }

        result = supabase.table("documents").insert(insert_data).execute()

        if result.data and len(result.data) > 0:
            return _parse_document(result.data[0]), None

        # Rollback: delete uploaded file if metadata insert failed
        storage_client.storage.from_(BUCKET_NAME).remove([storage_path])
        return None, "Failed to create document metadata"

    except Exception as e:
        error_msg = str(e)
        print(f"Error uploading document: {error_msg}")
        return None, f"Upload failed: {error_msg}"


# =============================================================================
# READ Operations
# =============================================================================

def get_document(document_id: str) -> Optional[Document]:
    """
    Get a document by ID.

    Args:
        document_id: Document UUID

    Returns:
        Document object if found, None otherwise
    """
    try:
        supabase = _get_supabase()
        result = supabase.table("documents").select("*").eq("id", document_id).execute()

        if result.data and len(result.data) > 0:
            return _parse_document(result.data[0])
        return None

    except Exception as e:
        print(f"Error getting document: {e}")
        return None


def get_documents_for_entity(
    entity_type: str,
    entity_id: str,
    *,
    document_type: Optional[str] = None,
) -> List[Document]:
    """
    Get all documents for a specific entity.

    Args:
        entity_type: Type of parent entity
        entity_id: UUID of parent entity
        document_type: Optional filter by document type

    Returns:
        List of Document objects

    Example:
        docs = get_documents_for_entity("quote", "quote-uuid")
        invoice_scans = get_documents_for_entity("quote", "quote-uuid", document_type="invoice_scan")
    """
    try:
        supabase = _get_supabase()
        query = supabase.table("documents").select("*")\
            .eq("entity_type", entity_type)\
            .eq("entity_id", entity_id)\
            .order("created_at", desc=True)

        if document_type:
            query = query.eq("document_type", document_type)

        result = query.execute()

        return [_parse_document(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting documents for entity: {e}")
        return []


def get_all_documents_for_quote(quote_id: str) -> List[Document]:
    """
    Get ALL documents related to a quote (hierarchical).

    This includes:
    - Documents directly attached to the quote (entity_type=quote)
    - Documents attached to supplier invoices of this quote
    - Certificates attached to quote items

    All fetched via parent_quote_id for efficiency.

    Args:
        quote_id: Quote UUID

    Returns:
        List of Document objects sorted by created_at desc
    """
    try:
        supabase = _get_supabase()
        result = supabase.table("documents").select("*")\
            .eq("parent_quote_id", quote_id)\
            .order("created_at", desc=True)\
            .execute()

        return [_parse_document(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting all documents for quote: {e}")
        return []


def count_all_documents_for_quote(quote_id: str) -> int:
    """Count all documents related to a quote (via parent_quote_id)."""
    try:
        supabase = _get_supabase()
        result = supabase.table("documents").select("id", count="exact")\
            .eq("parent_quote_id", quote_id)\
            .execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting documents for quote: {e}")
        return 0


def get_documents_by_organization(
    organization_id: str,
    *,
    entity_type: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Document]:
    """
    Get documents for an organization with optional filters.

    Args:
        organization_id: Organization UUID
        entity_type: Optional filter by entity type
        document_type: Optional filter by document type
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of Document objects
    """
    try:
        supabase = _get_supabase()
        query = supabase.table("documents").select("*")\
            .eq("organization_id", organization_id)\
            .order("created_at", desc=True)

        if entity_type:
            query = query.eq("entity_type", entity_type)
        if document_type:
            query = query.eq("document_type", document_type)

        result = query.range(offset, offset + limit - 1).execute()

        return [_parse_document(row) for row in result.data] if result.data else []

    except Exception as e:
        print(f"Error getting documents by organization: {e}")
        return []


def count_documents_for_entity(entity_type: str, entity_id: str) -> int:
    """Count documents for an entity."""
    try:
        supabase = _get_supabase()
        result = supabase.table("documents").select("id", count="exact")\
            .eq("entity_type", entity_type)\
            .eq("entity_id", entity_id)\
            .execute()

        return result.count if result.count else 0

    except Exception as e:
        print(f"Error counting documents: {e}")
        return 0


# =============================================================================
# DOWNLOAD Operations
# =============================================================================

def get_download_url(document_id: str, expires_in: int = 3600) -> Optional[str]:
    """
    Get a signed download URL for a document.

    Args:
        document_id: Document UUID
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL string, or None if document not found
    """
    document = get_document(document_id)
    if not document:
        return None

    try:
        storage_client = _get_storage_client()
        result = storage_client.storage.from_(BUCKET_NAME).create_signed_url(
            path=document.storage_path,
            expires_in=expires_in
        )

        if result and "signedURL" in result:
            return result["signedURL"]
        return None

    except Exception as e:
        print(f"Error creating signed URL: {e}")
        return None


def get_public_url(document_id: str) -> Optional[str]:
    """
    Get public URL for a document (if bucket is public).

    Note: For private buckets, use get_download_url() instead.
    """
    document = get_document(document_id)
    if not document:
        return None

    try:
        storage_client = _get_storage_client()
        result = storage_client.storage.from_(BUCKET_NAME).get_public_url(document.storage_path)
        return result

    except Exception as e:
        print(f"Error getting public URL: {e}")
        return None


# =============================================================================
# UPDATE Operations
# =============================================================================

def update_document(
    document_id: str,
    *,
    document_type: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Document]:
    """
    Update document metadata.

    Note: File content cannot be updated, only metadata.

    Args:
        document_id: Document UUID
        document_type: New document type
        description: New description

    Returns:
        Updated Document object, or None on failure
    """
    if document_type is not None and not validate_document_type(document_type):
        return None

    try:
        supabase = _get_supabase()

        update_data = {}
        if document_type is not None:
            update_data["document_type"] = document_type
        if description is not None:
            update_data["description"] = description

        if not update_data:
            return get_document(document_id)

        result = supabase.table("documents").update(update_data)\
            .eq("id", document_id)\
            .execute()

        if result.data and len(result.data) > 0:
            return _parse_document(result.data[0])
        return None

    except Exception as e:
        print(f"Error updating document: {e}")
        return None


# =============================================================================
# DELETE Operations
# =============================================================================

def delete_document(document_id: str) -> Tuple[bool, Optional[str]]:
    """
    Delete a document (both file and metadata).

    Args:
        document_id: Document UUID

    Returns:
        Tuple of (success, error_message)
    """
    # Get document first to get storage path
    document = get_document(document_id)
    if not document:
        return False, "Document not found"

    try:
        # Delete from storage
        storage_client = _get_storage_client()
        storage_result = storage_client.storage.from_(BUCKET_NAME).remove([document.storage_path])

        # Delete metadata record
        supabase = _get_supabase()
        supabase.table("documents").delete().eq("id", document_id).execute()

        return True, None

    except Exception as e:
        error_msg = str(e)
        print(f"Error deleting document: {error_msg}")
        return False, f"Delete failed: {error_msg}"


def delete_documents_for_entity(entity_type: str, entity_id: str) -> Tuple[int, Optional[str]]:
    """
    Delete all documents for an entity.

    Args:
        entity_type: Type of parent entity
        entity_id: UUID of parent entity

    Returns:
        Tuple of (deleted_count, error_message)
    """
    documents = get_documents_for_entity(entity_type, entity_id)
    if not documents:
        return 0, None

    deleted_count = 0
    errors = []

    for doc in documents:
        success, error = delete_document(doc.id)
        if success:
            deleted_count += 1
        else:
            errors.append(f"{doc.original_filename}: {error}")

    if errors:
        return deleted_count, f"Some deletions failed: {'; '.join(errors)}"

    return deleted_count, None


# =============================================================================
# UTILITY Functions
# =============================================================================

def get_document_type_label(document_type: str) -> str:
    """Get Russian label for document type."""
    return DOCUMENT_TYPE_LABELS.get(document_type, document_type or "Документ")


def get_file_icon(mime_type: Optional[str]) -> str:
    """Get Font Awesome icon class for MIME type."""
    if not mime_type:
        return "fa-file"

    if mime_type.startswith("image/"):
        return "fa-file-image"
    elif mime_type == "application/pdf":
        return "fa-file-pdf"
    elif mime_type in ("application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        return "fa-file-word"
    elif mime_type in ("application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        return "fa-file-excel"
    elif mime_type.startswith("text/"):
        return "fa-file-alt"
    elif "zip" in mime_type or "rar" in mime_type or "7z" in mime_type:
        return "fa-file-archive"
    else:
        return "fa-file"


def format_file_size(size_bytes: Optional[int]) -> str:
    """Format file size for display."""
    if not size_bytes:
        return ""

    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"


def get_documents_summary_for_entity(entity_type: str, entity_id: str) -> Dict[str, Any]:
    """
    Get summary of documents for an entity.

    Returns:
        Dict with:
        - count: Total number of documents
        - by_type: Count by document type
        - total_size: Total file size in bytes
    """
    documents = get_documents_for_entity(entity_type, entity_id)

    by_type = {}
    total_size = 0

    for doc in documents:
        doc_type = doc.document_type or "other"
        by_type[doc_type] = by_type.get(doc_type, 0) + 1
        total_size += doc.file_size_bytes or 0

    return {
        "count": len(documents),
        "by_type": by_type,
        "total_size": total_size,
        "total_size_formatted": format_file_size(total_size),
    }


def get_allowed_document_types_for_entity(entity_type: str) -> List[Dict[str, str]]:
    """
    Get list of relevant document types for an entity type.

    Returns list of dicts with 'value' and 'label' for dropdown.

    Note: For 'quote' entity type, ALL document types are shown because
    the quote documents page aggregates docs from invoices and items too.
    """
    # Define relevant document types per entity
    entity_document_types = {
        "supplier_invoice": ["invoice_scan", "proforma_scan", "payment_order", "other"],
        # Quote shows ALL types because it aggregates from invoices and items
        "quote": [
            "invoice_scan", "proforma_scan", "payment_order",  # Invoice-related
            "certificate",  # Item-related
            "contract", "ttn", "cmr", "bill_of_lading", "customs_declaration",  # Quote-related
            "founding_docs", "license", "other"  # Other
        ],
        "specification": ["contract", "ttn", "cmr", "bill_of_lading", "customs_declaration", "other"],
        "quote_item": ["certificate", "other"],
        "supplier": ["contract", "license", "certificate", "other"],
        "customer": ["contract", "other"],
        "seller_company": ["founding_docs", "license", "contract", "other"],
        "buyer_company": ["founding_docs", "license", "contract", "other"],
    }

    types = entity_document_types.get(entity_type, list(VALID_DOCUMENT_TYPES))

    return [
        {"value": t, "label": DOCUMENT_TYPE_LABELS.get(t, t)}
        for t in types
    ]


# Document types that require binding to a supplier invoice
INVOICE_DOCUMENT_TYPES = {"invoice_scan", "proforma_scan", "payment_order"}

# Document types that require binding to a quote item
ITEM_DOCUMENT_TYPES = {"certificate"}


def get_required_sub_entity_type(document_type: Optional[str]) -> Optional[str]:
    """
    Determine if a document type requires binding to a sub-entity.

    Args:
        document_type: The document type

    Returns:
        'supplier_invoice' if needs invoice binding,
        'quote_item' if needs item binding,
        None if binds directly to quote
    """
    if document_type in INVOICE_DOCUMENT_TYPES:
        return "supplier_invoice"
    elif document_type in ITEM_DOCUMENT_TYPES:
        return "quote_item"
    return None


def get_entity_type_label(entity_type: str) -> str:
    """Get Russian label for entity type."""
    labels = {
        "quote": "КП",
        "supplier_invoice": "Инвойс",
        "quote_item": "Товар",
        "specification": "Спецификация",
        "supplier": "Поставщик",
        "customer": "Клиент",
        "seller_company": "Компания-продавец",
        "buyer_company": "Компания-покупатель",
    }
    return labels.get(entity_type, entity_type)
