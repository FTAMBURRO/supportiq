import type { CategorySummary, TicketListParams } from '../types'
import { priorityLabel, statusLabel } from '../utils/format'
import styles from './FilterBar.module.css'

const STATUSES = ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'] as const
const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'] as const

/** Filters limited to what GET /api/tickets really supports: status,
 * priority and category. No search, no sort, no requester/assignee
 * filters — the API does not offer them. Values live in the URL. */
export default function FilterBar({
  params,
  categories,
  onChange,
}: {
  params: TicketListParams
  categories: CategorySummary[]
  onChange: (next: TicketListParams) => void
}) {
  const hasFilters = Boolean(params.status || params.priority || params.category_id)

  return (
    <div className={styles.bar}>
      <div className={styles.field}>
        <label htmlFor="filter-status">Status</label>
        <select
          id="filter-status"
          value={params.status ?? ''}
          onChange={(event) =>
            onChange({ ...params, status: event.target.value || undefined, page: 1 })
          }
        >
          <option value="">All statuses</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {statusLabel(status)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="filter-priority">Priority</label>
        <select
          id="filter-priority"
          value={params.priority ?? ''}
          onChange={(event) =>
            onChange({ ...params, priority: event.target.value || undefined, page: 1 })
          }
        >
          <option value="">All priorities</option>
          {PRIORITIES.map((priority) => (
            <option key={priority} value={priority}>
              {priorityLabel(priority)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="filter-category">Category</label>
        <select
          id="filter-category"
          value={params.category_id ?? ''}
          onChange={(event) =>
            onChange({
              ...params,
              category_id: event.target.value || undefined,
              page: 1,
            })
          }
        >
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </div>

      {hasFilters && (
        <button
          type="button"
          className={styles.clear}
          onClick={() => onChange({ page: 1 })}
        >
          Clear filters
        </button>
      )}
    </div>
  )
}
