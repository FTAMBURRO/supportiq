import { listCategories } from './categories'
import { listUsers } from './users'
import type { CategorySummary, UserSummary } from '../types'

export interface ReferenceData {
  users: UserSummary[]
  categories: CategorySummary[]
}

let cached: Promise<ReferenceData> | null = null

/** Users + categories fetched once per session and reused everywhere
 * (selects, table joins, event formatting). Cleared on failure so the
 * next call retries instead of caching a rejected promise. */
export function getReference(): Promise<ReferenceData> {
  if (!cached) {
    cached = Promise.all([listUsers(), listCategories()]).then(
      ([users, categories]) => ({ users, categories }),
    )
    cached.catch(() => {
      cached = null
    })
  }
  return cached
}

/** id → display name for users. Unresolvable ids fall back to a short id. */
export function userName(users: UserSummary[], id: string | null): string {
  if (!id) return 'Unassigned'
  const found = users.find((user) => user.id === id)
  return found ? found.full_name : `${id.slice(0, 8)}…`
}

/** id → category; null → "Uncategorized". Falls back to a short id. */
export function categoryName(
  categories: CategorySummary[],
  id: string | null,
): string {
  if (!id) return 'Uncategorized'
  const found = categories.find((category) => category.id === id)
  return found ? found.name : `${id.slice(0, 8)}…`
}
