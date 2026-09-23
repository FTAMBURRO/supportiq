import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage, isApiError } from '../api/client'
import { getReference } from '../api/reference'
import { getTicket, getTicketEvents, updateTicket } from '../api/tickets'
import { SourceBadge, StatusBadge, PriorityBadge } from '../components/Badges'
import ConfidenceNote from '../components/ConfidenceNote'
import EventTimeline from '../components/EventTimeline'
import { ErrorBanner, LoadingState, EmptyState } from '../components/States'
import type {
  CategorySummary,
  Ticket,
  TicketEvent,
  TicketPriority,
  TicketStatus,
  UpdateTicketInput,
  UserSummary,
} from '../types'
import { formatDateTime, priorityLabel, statusLabel } from '../utils/format'
import type { EventNameMaps } from '../utils/formatEvent'
import { userName } from '../api/reference'
import { ALL_PRIORITIES, selectableStatuses } from '../utils/statusTransitions'
import styles from './TicketDetailPage.module.css'

interface KeyedError {
  key: string
  message: string
}

/** Full ticket view: display, inline editing (4 selects → PATCH) and
 * the event history.
 *
 * The AI block renders ONLY what the backend returns
 * (category_source / category / classification_confidence) — nothing is
 * hardcoded; when there is no category the honest abstention copy is
 * shown instead. The backend stays the authority on updates: 409
 * responses are surfaced and trigger a refetch of the real state. */
export default function TicketDetailPage() {
  const { ticketNumber = '' } = useParams()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [events, setEvents] = useState<TicketEvent[] | null>(null)
  const [users, setUsers] = useState<UserSummary[]>([])
  const [categories, setCategories] = useState<CategorySummary[]>([])
  const [error, setError] = useState<KeyedError | null>(null)
  const [eventsError, setEventsError] = useState<KeyedError | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const [saving, setSaving] = useState(false)
  const [patchError, setPatchError] = useState<string | null>(null)

  const loadKey = `${ticketNumber}#${reloadKey}`

  useEffect(() => {
    let cancelled = false
    getReference()
      .then(({ users, categories }) => {
        if (cancelled) return
        setUsers(users)
        setCategories(categories)
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

  useEffect(() => {
    const key = `${ticketNumber}#${reloadKey}`
    let cancelled = false
    getTicketEvents(ticketNumber)
      .then((data) => {
        if (!cancelled) setEvents(data.items)
      })
      .catch((err) => {
        if (!cancelled) setEventsError({ key, message: errorMessage(err) })
      })
    return () => {
      cancelled = true
    }
  }, [ticketNumber, reloadKey])

  const reload = () => setReloadKey((k) => k + 1)

  /** PATCH the backend, then refresh ticket + events from the truth. */
  async function patch(input: UpdateTicketInput): Promise<void> {
    if (saving) return
    setSaving(true)
    setPatchError(null)
    try {
      const updated = await updateTicket(ticketNumber, input)
      setTicket(updated)
      const data = await getTicketEvents(ticketNumber)
      setEvents(data.items)
    } catch (err) {
      setPatchError(errorMessage(err))
      if (isApiError(err) && err.status === 409) {
        // The backend rejected the transition: show its message and
        // reload the authoritative state behind the user's view.
        getTicket(ticketNumber).then(setTicket).catch(() => {})
        getTicketEvents(ticketNumber)
          .then((data) => setEvents(data.items))
          .catch(() => {})
      }
    } finally {
      setSaving(false)
    }
  }

  if (notFound) {
    return (
      <div>
        <h1>Ticket not found</h1>
        <EmptyState
          title={`No ticket ${ticketNumber} exists.`}
          hint="It may have been created with a different number."
          action={
            <Link to="/tickets" className={`btn btnSecondary ${styles.notFoundLink}`}>
              Back to tickets
            </Link>
          }
        />
      </div>
    )
  }

  const activeError = error && error.key === loadKey ? error.message : null
  const activeEventsError =
    eventsError && eventsError.key === loadKey ? eventsError.message : null

  if (activeError) return <ErrorBanner message={activeError} onRetry={reload} />
  if (!ticket || ticket.ticket_number !== ticketNumber) {
    return <LoadingState label="Loading ticket…" />
  }

  const showAiBlock =
    ticket.category_source === 'AI' &&
    ticket.category !== null &&
    ticket.classification_confidence !== null

  const maps: EventNameMaps = {
    userNameById: new Map(users.map((user) => [user.id, user.full_name])),
    categoryNameById: new Map(categories.map((c) => [c.id, c.name])),
    categoryNameBySlug: new Map(categories.map((c) => [c.slug, c.name])),
  }

  const statusOptions = selectableStatuses(ticket.status)
  // Keep a current value visible even if it is no longer in the active
  // reference lists (e.g. an inactive category/assignee).
  const categoryOptions = categories.filter(
    (c) => c.id !== ticket.category_id,
  )
  const assigneeUsers = users.filter((u) => u.id !== ticket.assignee_id)

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

          <section className={styles.card}>
            <h2>History</h2>
            {activeEventsError && (
              <ErrorBanner message={activeEventsError} onRetry={reload} />
            )}
            {!activeEventsError && events === null && (
              <LoadingState label="Loading history…" />
            )}
            {activeEventsError && events === null && null}
            {events !== null && events.length === 0 && (
              <EmptyState title="No events yet" />
            )}
            {events !== null && events.length > 0 && (
              <EventTimeline events={events} maps={maps} />
            )}
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

          <section className={styles.card}>
            <h2>Edit ticket</h2>
            <div className={styles.edits}>
              <div>
                <label htmlFor="edit-status">Status</label>
                <select
                  id="edit-status"
                  value={ticket.status}
                  disabled={saving || statusOptions.length <= 1}
                  onChange={(event) =>
                    void patch({ status: event.target.value as TicketStatus })
                  }
                >
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {statusLabel(status)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="edit-priority">Priority</label>
                <select
                  id="edit-priority"
                  value={ticket.priority}
                  disabled={saving}
                  onChange={(event) =>
                    void patch({ priority: event.target.value as TicketPriority })
                  }
                >
                  {ALL_PRIORITIES.map((priority) => (
                    <option key={priority} value={priority}>
                      {priorityLabel(priority)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="edit-category">Category</label>
                <select
                  id="edit-category"
                  value={ticket.category_id ?? ''}
                  disabled={saving}
                  onChange={(event) =>
                    void patch({
                      category_id: event.target.value || null,
                    })
                  }
                >
                  <option value="">Uncategorized</option>
                  {ticket.category && (
                    <option value={ticket.category.id}>
                      {ticket.category.name}
                    </option>
                  )}
                  {categoryOptions.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="edit-assignee">Assignee</label>
                <select
                  id="edit-assignee"
                  value={ticket.assignee_id ?? ''}
                  disabled={saving}
                  onChange={(event) =>
                    void patch({ assignee_id: event.target.value || null })
                  }
                >
                  <option value="">Unassigned</option>
                  {ticket.assignee_id && (
                    <option value={ticket.assignee_id}>
                      {userName(users, ticket.assignee_id)}
                    </option>
                  )}
                  {assigneeUsers.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.full_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className={styles.editActions}>
              {saving && (
                <span className={styles.saving} role="status">
                  Saving…
                </span>
              )}
            </div>
            {patchError && <ErrorBanner message={patchError} />}
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
