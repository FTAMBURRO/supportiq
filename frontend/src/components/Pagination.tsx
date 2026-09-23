import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Pagination as PaginationData } from '../types'
import styles from './Pagination.module.css'

/** Backend pagination exactly as returned (per_page fixed at 20).
 * Handles `pages: 0` (empty result) by rendering nothing. */
export default function Pagination({
  pagination,
  onPageChange,
}: {
  pagination: PaginationData
  onPageChange: (page: number) => void
}) {
  if (pagination.pages <= 1) return null
  const { page, pages, total } = pagination

  return (
    <nav className={styles.nav} aria-label="Pagination">
      <button
        type="button"
        className={styles.btn}
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft size={14} aria-hidden="true" />
        Previous
      </button>
      <span className={styles.info}>
        Page {page} of {pages} · {total} tickets
      </span>
      <button
        type="button"
        className={styles.btn}
        disabled={page >= pages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
        <ChevronRight size={14} aria-hidden="true" />
      </button>
    </nav>
  )
}
