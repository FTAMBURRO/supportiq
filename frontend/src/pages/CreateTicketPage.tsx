import { ArrowLeft } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { createTicket } from '../api/tickets'
import { getReference } from '../api/reference'
import { ErrorBanner, LoadingState } from '../components/States'
import type { CreateTicketInput, TicketPriority, UserSummary } from '../types'
import styles from './CreateTicketPage.module.css'

/** Create a ticket WITHOUT a category (intentionally): the flow that
 * lets SupportIQ classify it automatically on creation. */
export default function CreateTicketPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserSummary[] | null>(null)
  const [referenceError, setReferenceError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [requesterId, setRequesterId] = useState('')
  const [priority, setPriority] = useState<TicketPriority>('MEDIUM')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getReference()
      .then(({ users }) => {
        if (!cancelled) setUsers(users)
      })
      .catch((err) => {
        if (!cancelled) setReferenceError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  /** Minimal client-side validation; the backend stays the source of
   * truth and its messages are shown as-is when it rejects. */
  function validate(): boolean {
    const errors: Record<string, string> = {}
    if (!title.trim()) errors.title = 'Title is required'
    else if (title.trim().length > 200) errors.title = 'Title must be at most 200 characters'
    if (!description.trim()) errors.description = 'Description is required'
    if (!requesterId) errors.requester = 'Requester is required'
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const submit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault()
      if (submitting || !validate()) return
      setSubmitError(null)
      setSubmitting(true)
      const input: CreateTicketInput = {
        title: title.trim(),
        description: description.trim(),
        requester_id: requesterId,
        priority,
      }
      createTicket(input)
        .then((ticket) => navigate(`/tickets/${ticket.ticket_number}`))
        .catch((err) => {
          setSubmitError(errorMessage(err))
          setSubmitting(false)
        })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [title, description, requesterId, priority, submitting],
  )

  if (referenceError) {
    return (
      <div>
        <h1>Create Ticket</h1>
        <ErrorBanner
          message={`Could not load users: ${referenceError}`}
          onRetry={() => window.location.reload()}
        />
      </div>
    )
  }

  if (!users) return <LoadingState label="Loading form…" />

  return (
    <div className={styles.wrapper}>
      <Link to="/tickets" className={styles.back}>
        <ArrowLeft size={14} aria-hidden="true" />
        Tickets
      </Link>
      <h1>Create Ticket</h1>
      <p className={styles.hint}>
        SupportIQ will attempt to classify it automatically after creation.
      </p>

      <form className={styles.form} onSubmit={submit} noValidate>
        {submitError && <ErrorBanner message={submitError} />}

        <div>
          <label htmlFor="title">Title</label>
          <input
            id="title"
            value={title}
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
            aria-invalid={Boolean(fieldErrors.title)}
          />
          {fieldErrors.title && (
            <p className={styles.fieldError}>{fieldErrors.title}</p>
          )}
        </div>

        <div>
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            aria-invalid={Boolean(fieldErrors.description)}
          />
          {fieldErrors.description && (
            <p className={styles.fieldError}>{fieldErrors.description}</p>
          )}
        </div>

        <div className={styles.row}>
          <div>
            <label htmlFor="requester">Requester</label>
            <select
              id="requester"
              value={requesterId}
              onChange={(event) => setRequesterId(event.target.value)}
              aria-invalid={Boolean(fieldErrors.requester)}
            >
              <option value="">Select a user…</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name} ({user.email})
                </option>
              ))}
            </select>
            {fieldErrors.requester && (
              <p className={styles.fieldError}>{fieldErrors.requester}</p>
            )}
          </div>

          <div>
            <label htmlFor="priority">Priority</label>
            <select
              id="priority"
              value={priority}
              onChange={(event) =>
                setPriority(event.target.value as TicketPriority)
              }
            >
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="URGENT">Urgent</option>
            </select>
          </div>
        </div>

        <div className={styles.actions}>
          <button type="submit" className="btn" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create ticket'}
          </button>
          <Link to="/tickets" className="btn btnSecondary">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
