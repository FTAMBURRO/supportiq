import { Plus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { getReference } from '../api/reference'
import { listTickets } from '../api/tickets'
import FilterBar from '../components/FilterBar'
import Pagination from '../components/Pagination'
import { EmptyState, ErrorBanner, LoadingState } from '../components/States'
import TicketTable from '../components/TicketTable'
import type {
  CategorySummary,
  PaginatedTickets,
  TicketListParams,
  UserSummary,
} from '../types'
import styles from './TicketsPage.module.css'

/** Tickets list: filters + page live in the URL (?status=&priority=
 * &category_id=&page=), pagination is the backend's real one.
 *
 * State resets (showing "loading" again) happen in the event handlers
 * that change the query; effects only set state from async responses. */
export default function TicketsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const params: TicketListParams = {
    status: searchParams.get('status') ?? undefined,
    priority: searchParams.get('priority') ?? undefined,
    category_id: searchParams.get('category_id') ?? undefined,
    page: Number(searchParams.get('page')) || 1,
  }

  const [page, setPage] = useState<PaginatedTickets | null>(null)
  const [categories, setCategories] = useState<CategorySummary[]>([])
  const [users, setUsers] = useState<UserSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const query = searchParams.toString()

  useEffect(() => {
    let cancelled = false
    getReference()
      .then(({ users, categories }) => {
        if (cancelled) return
        setUsers(users)
        setCategories(categories)
      })
      .catch(() => {
        // The list must still load if reference data fails; the category
        // select stays empty and names fall back to short ids.
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const current = new URLSearchParams(query)
    const listParams: TicketListParams = {
      status: current.get('status') ?? undefined,
      priority: current.get('priority') ?? undefined,
      category_id: current.get('category_id') ?? undefined,
      page: Number(current.get('page')) || 1,
    }
    let cancelled = false
    listTickets(listParams)
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [query, reloadKey])

  const retry = useCallback(() => {
    setError(null)
    setReloadKey((key) => key + 1)
  }, [])

  function updateParams(next: TicketListParams) {
    const nextQuery = new URLSearchParams()
    if (next.status) nextQuery.set('status', next.status)
    if (next.priority) nextQuery.set('priority', next.priority)
    if (next.category_id) nextQuery.set('category_id', next.category_id)
    if (next.page && next.page > 1) nextQuery.set('page', String(next.page))
    setPage(null) // show the loading state for the new query
    setError(null)
    setSearchParams(nextQuery)
  }

  const filtered = Boolean(params.status || params.priority || params.category_id)

  return (
    <div>
      <div className={styles.header}>
        <h1>Tickets</h1>
        <Link to="/tickets/new" className={`btn ${styles.create}`}>
          <Plus size={15} aria-hidden="true" />
          Create Ticket
        </Link>
      </div>

      <FilterBar params={params} categories={categories} onChange={updateParams} />

      {error && <ErrorBanner message={error} onRetry={retry} />}

      {!page && !error && <LoadingState label="Loading tickets…" />}

      {page && page.items.length === 0 && (
        <EmptyState
          title={
            filtered ? 'No tickets match these filters' : 'No tickets yet'
          }
          hint={
            filtered
              ? 'Try clearing the filters.'
              : 'Create the first ticket to get started.'
          }
          action={
            filtered ? (
              <button
                type="button"
                className={`btn btnSecondary ${styles.emptyAction}`}
                onClick={() => updateParams({ page: 1 })}
              >
                Clear filters
              </button>
            ) : (
              <Link to="/tickets/new" className={`btn ${styles.emptyAction}`}>
                Create the first ticket
              </Link>
            )
          }
        />
      )}

      {page && page.items.length > 0 && (
        <>
          <TicketTable
            page={page}
            users={users}
            onOpen={(ticketNumber) => navigate(`/tickets/${ticketNumber}`)}
          />
          <Pagination
            pagination={page.pagination}
            onPageChange={(next) => updateParams({ ...params, page: next })}
          />
        </>
      )}
    </div>
  )
}
