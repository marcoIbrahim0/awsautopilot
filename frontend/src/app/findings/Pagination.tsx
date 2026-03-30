'use client';

import { Button } from '@/components/ui/Button';

interface PaginationProps {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (newOffset: number) => void;
  itemLabel?: string;
}

export function Pagination({ offset, limit, total, onPageChange, itemLabel = 'findings' }: PaginationProps) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between pt-6 mt-4 border-t border-border/30">
      <p className="text-sm text-muted">
        Showing {offset + 1} - {Math.min(offset + limit, total)} of {total} {itemLabel}
      </p>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          disabled={!hasPrev}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Previous
        </Button>

        <span className="text-sm text-muted px-2">
          Page {currentPage} of {totalPages}
        </span>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(offset + limit)}
          disabled={!hasNext}
        >
          Next
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        </Button>
      </div>
    </div>
  );
}
