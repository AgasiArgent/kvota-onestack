import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemLabel?: string;
  buildHref: (page: number) => string;
}

function getPageNumbers(
  currentPage: number,
  totalPages: number
): (number | "ellipsis")[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis")[] = [1];

  if (currentPage > 3) {
    pages.push("ellipsis");
  }

  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (currentPage < totalPages - 2) {
    pages.push("ellipsis");
  }

  pages.push(totalPages);

  return pages;
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  itemLabel = "записей",
  buildHref,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages = getPageNumbers(currentPage, totalPages);

  return (
    <div className="flex items-center justify-center gap-4 text-sm">
      <span className="text-text-muted">
        {totalItems} {itemLabel}
      </span>

      <nav className="flex items-center gap-1">
        {currentPage > 1 ? (
          <Link
            href={buildHref(currentPage - 1)}
            className="p-1.5 rounded-md text-text-muted hover:text-text transition-colors"
            aria-label="Предыдущая страница"
          >
            <ChevronLeft size={16} />
          </Link>
        ) : (
          <span className="p-1.5 text-text-subtle cursor-default" aria-disabled>
            <ChevronLeft size={16} />
          </span>
        )}

        {pages.map((page, index) =>
          page === "ellipsis" ? (
            <span
              key={`ellipsis-${index}`}
              className="px-2 py-1 text-text-muted select-none"
            >
              ...
            </span>
          ) : page === currentPage ? (
            <span
              key={page}
              className="bg-accent text-white rounded-md px-3 py-1 font-medium"
            >
              {page}
            </span>
          ) : (
            <Link
              key={page}
              href={buildHref(page)}
              className="text-text-muted hover:text-text px-3 py-1 rounded-md transition-colors"
            >
              {page}
            </Link>
          )
        )}

        {currentPage < totalPages ? (
          <Link
            href={buildHref(currentPage + 1)}
            className="p-1.5 rounded-md text-text-muted hover:text-text transition-colors"
            aria-label="Следующая страница"
          >
            <ChevronRight size={16} />
          </Link>
        ) : (
          <span className="p-1.5 text-text-subtle cursor-default" aria-disabled>
            <ChevronRight size={16} />
          </span>
        )}
      </nav>
    </div>
  );
}
