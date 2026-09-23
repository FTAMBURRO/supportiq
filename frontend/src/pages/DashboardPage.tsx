import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardSummary } from '../api/dashboard'
import { errorMessage } from '../api/client'
import ProgressBar from '../components/ProgressBar'
import StatCard from '../components/StatCard'
import { ErrorBanner, LoadingState } from '../components/States'
import type { DashboardSummary, TicketPriority } from '../types'
import { priorityLabel, statusLabel } from '../utils/format'
import styles from './DashboardPage.module.css'

const PRIORITY_ORDER: ReadonlyArray<{
  key: keyof DashboardSummary['priority']
  label: TicketPriority
}> = [
  { key: 'urgent', label: 'URGENT' },
  { key: 'high', label: 'HIGH' },
  { key: 'medium', label: 'MEDIUM' },
  { key: 'low', label: 'LOW' },
]

const STATUS_ORDER = ['open', 'in_progress', 'resolved', 'closed'] as const

/** Dashboard: headline counters + two CSS bar overviews, straight from
 * GET /api/dashboard/summary. No chart library. */
export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    getDashboardSummary()
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const retry = useCallback(() => {
    setError(null)
    setReloadKey((key) => key + 1)
  }, [])

  if (error) return <ErrorBanner message={error} onRetry={retry} />
  if (!summary) return <LoadingState label="Loading dashboard…" />

  const priorityMax = Math.max(
    ...PRIORITY_ORDER.map(({ key }) => summary.priority[key]),
  )
  const statusMax = Math.max(...STATUS_ORDER.map((s) => summary.tickets[s]))
  const statusLabels: Record<(typeof STATUS_ORDER)[number], string> = {
    open: statusLabel('OPEN'),
    in_progress: statusLabel('IN_PROGRESS'),
    resolved: statusLabel('RESOLVED'),
    closed: statusLabel('CLOSED'),
  }

  return (
    <div>
      <div className={styles.header}>
        <h1>Support Dashboard</h1>
        <Link to="/tickets" className={styles.viewAll}>
          View all tickets →
        </Link>
      </div>

      <section className={styles.stats} aria-label="Ticket totals">
        <StatCard label="Total Tickets" value={summary.tickets.total} />
        <StatCard label="Open" value={summary.tickets.open} />
        <StatCard label="In Progress" value={summary.tickets.in_progress} />
        <StatCard label="Unassigned" value={summary.unassigned} />
      </section>

      <div className={styles.panels}>
        <section className={styles.panel} aria-label="Tickets by priority">
          <h2>Tickets by Priority</h2>
          <div className={styles.bars}>
            {PRIORITY_ORDER.map(({ key, label }) => (
              <ProgressBar
                key={key}
                label={priorityLabel(label)}
                value={summary.priority[key]}
                max={priorityMax}
              />
            ))}
          </div>
        </section>

        <section className={styles.panel} aria-label="Status overview">
          <h2>Status overview</h2>
          <div className={styles.bars}>
            {STATUS_ORDER.map((status) => (
              <ProgressBar
                key={status}
                label={statusLabels[status]}
                value={summary.tickets[status]}
                max={statusMax}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
