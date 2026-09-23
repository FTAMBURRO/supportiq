import type { TicketPriority, TicketStatus } from '../types'

/** Human labels for backend enum values (never shown raw). */

export function statusLabel(status: TicketStatus): string {
  switch (status) {
    case 'OPEN':
      return 'Open'
    case 'IN_PROGRESS':
      return 'In Progress'
    case 'RESOLVED':
      return 'Resolved'
    case 'CLOSED':
      return 'Closed'
  }
}

export function priorityLabel(priority: TicketPriority): string {
  switch (priority) {
    case 'LOW':
      return 'Low'
    case 'MEDIUM':
      return 'Medium'
    case 'HIGH':
      return 'High'
    case 'URGENT':
      return 'Urgent'
  }
}

/** Confidence as a percentage label. The backend value is a heuristic
 * score in (0..1] — NEVER describe it as a probability. */
export function formatConfidence(value: number | null): string {
  if (value === null) return '—'
  return `${Math.round(value * 100)}%`
}

/** ISO timestamp → "23 Sep 2026, 14:05" (local time). */
export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** ISO timestamp → "2 min ago" for table columns. */
export function formatRelativeTime(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const seconds = Math.round((date.getTime() - Date.now()) / 1000)
  const formatter = new Intl.RelativeTimeFormat(undefined, {
    numeric: 'auto',
  })
  const minutes = Math.round(seconds / 60)
  if (Math.abs(minutes) < 1) return 'just now'
  if (Math.abs(minutes) < 60) return formatter.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return formatter.format(hours, 'hour')
  const days = Math.round(hours / 24)
  if (Math.abs(days) < 30) return formatter.format(days, 'day')
  const months = Math.round(days / 30)
  if (Math.abs(months) < 12) return formatter.format(months, 'month')
  return formatter.format(Math.round(months / 12), 'year')
}
