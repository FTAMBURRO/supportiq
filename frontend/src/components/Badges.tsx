import type { CategorySource, TicketPriority, TicketStatus } from '../types'
import { priorityLabel, statusLabel } from '../utils/format'
import styles from './Badges.module.css'

/** Badges always carry a TEXT label: color alone never communicates
 * state (accessibility requirement). */

export function StatusBadge({ status }: { status: TicketStatus }) {
  const tone: Record<TicketStatus, string> = {
    OPEN: styles.blue,
    IN_PROGRESS: styles.amber,
    RESOLVED: styles.green,
    CLOSED: styles.gray,
  }
  return (
    <span className={`${styles.badge} ${tone[status]}`}>{statusLabel(status)}</span>
  )
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const tone: Record<TicketPriority, string> = {
    LOW: styles.gray,
    MEDIUM: styles.blue,
    HIGH: styles.amber,
    URGENT: styles.red,
  }
  return (
    <span className={`${styles.badge} ${tone[priority]}`}>
      {priorityLabel(priority)}
    </span>
  )
}

export function CategoryBadge({ name }: { name: string }) {
  return <span className={`${styles.badge} ${styles.outline}`}>{name}</span>
}

/** Provenance of the current category: who decided it. */
export function SourceBadge({ source }: { source: CategorySource }) {
  return (
    <span
      className={`${styles.badge} ${source === 'AI' ? styles.violet : styles.gray}`}
    >
      {source === 'AI' ? 'AI' : 'MANUAL'}
    </span>
  )
}
