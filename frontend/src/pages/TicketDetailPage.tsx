import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage, isApiError } from '../api/client'
import { getReference } from '../api/reference'
import { getTicket } from '../api/tickets'
import { SourceBadge, StatusBadge, PriorityBadge } from '../components/Badges'
import ConfidenceNote from '../components/ConfidenceNote'
import { ErrorBanner, LoadingState, EmptyState } from '../components/States'
import type { Ticket } from '../types'
import { formatDateTime } from '../utils/format'
import { userName } from '../api/reference'
import styles from './TicketDetailPage.module.css'

/** Full ticket view. The AI block renders ONLY what the backend returns
 * (category_source / category / classification_confidence) — nothing is
 * hardcoded; when there is no category the honest abstention copy is
 * shown instead. */
export default function TicketDetailPage() {
  const { ticketNumber = '' } = useParams()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [users, setUsers] = useState<Awaited<ReturnType<typeof getReference>>['users']>([])
  // Errors are tied to the load they came from: an error for a previous
  // ticket/reload never shows up for the current one (and no setState
  // runs synchronously inside the effects below).
  const [error, setError] = useState<{ key: string; message: string } | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const loadKey = `${ticketNumber}#${reloadKey}`

  useEffect(() => {
    let cancelled = false
    getReference()
      .then(({ users }) => {
        if (!cancelled) setUsers(users)
      })
      .catch(() => {
        // Names fall back to short ids; the ticket itself must load.
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const key = `${ticketNumber}#${reloadKey}`
    let cancelled = false
    getTicket(ticketNumber)
      .then((data) => {
        if (cancelled) return
        setTicket(data)
        setNotFound(false)
      })
      .catch((err) => {
        if (cancelled) return
        if (isApiError(err) && err.isNotFound) setNotFound(true)
        else setError({ key, message: errorMessage(err) })
      })
    return () => {
      cancelled = true
    }
  }, [ticketNumber, reloadKey])

  const activeError =
    error && error.key === loadKey ? error.message : null

  if (notFound) {
    return (
      <div>
        <h1>Ticket not found</h1>
        <EmptyState
          title={`No ticket ${ticketNumber} exists.`}
          hint="It may have been created with a different number."
          action={
            <Link to="/tickets" className="btn btnSecondary" style={{ marginTop: 14 }}>
              Back to tickets
            </Link>
          }
        />
      </div>
    )
  }

  if (activeError) return <ErrorBanner message={activeError} onRetry={() => setReloadKey((k) => k + 1)} />
  if (!ticket || ticket.ticket_number !== ticketNumber) {
    return <LoadingState label="Loading ticket…" />
  }

  const showAiBlock =
    ticket.category_source === 'AI' &&
    ticket.category !== null &&
    ticket.classification_confidence !== null

  return (
    <div>
      <Link to="/tickets" className={styles.back}>
        <ArrowLeft size={14} aria-hidden="true" />
        Tickets
      </Link>

      <div className={styles.header}>
        <span className={styles.ticketNumber}>{ticket.ticket_number}</span>
        <StatusBadge status={ticket.status} />
        <PriorityBadge priority={ticket.priority} />
        <SourceBadge source={ticket.category_source} />
      </div>
      <h1 className={styles.title}>{ticket.title}</h1>

      <div className={styles.grid}>
        <div>
          <section className={styles.card}>
            <h2>Description</h2>
            <p className={styles.description}>{ticket.description}</p>
          </section>
        </div>

        <div>
          <section className={styles.card}>
            <h2>Details</h2>
            <dl className={styles.meta}>
              <dt>Requester</dt>
              <dd>{userName(users, ticket.requester_id)}</dd>

              <dt>Assignee</dt>
              <dd>{userName(users, ticket.assignee_id)}</dd>

              <dt>Category</dt>
              <dd className={styles.metaRow}>
                {ticket.category ? (
                  ticket.category.name
                ) : (
                  <span className={styles.uncategorized}>Uncategorized</span>
                )}
              </dd>

              <dt>Created</dt>
              <dd>{formatDateTime(ticket.created_at)}</dd>

              <dt>Updated</dt>
              <dd>{formatDateTime(ticket.updated_at)}</dd>

              {ticket.resolved_at && (
                <>
                  <dt>Resolved</dt>
                  <dd>{formatDateTime(ticket.resolved_at)}</dd>
                </>
              )}
              {ticket.closed_at && (
                <>
                  <dt>Closed</dt>
                  <dd>{formatDateTime(ticket.closed_at)}</dd>
                </>
              )}
            </dl>
          </section>

          <section className={styles.card} aria-label="Classification">
            <h2>AI Classification</h2>
            {showAiBlock && ticket.category && (
              <>
                <p className={styles.aiCategory}>{ticket.category.name}</p>
                <ConfidenceNote value={ticket.classification_confidence!} />
              </>
            )}
            {!showAiBlock && ticket.category === null && (
              <div className={styles.aiNote}>
                <p className={styles.uncategorized}>Uncategorized</p>
                <p className={styles.uncategorized} style={{ marginTop: 6 }}>
                  SupportIQ did not classify this ticket automatically because the
                  historical evidence was not strong enough. A human can set the
                  category.
                </p>
              </div>
            )}
            {!showAiBlock && ticket.category !== null && (
              <p className={styles.uncategorized}>
                Category set manually by a human.
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
