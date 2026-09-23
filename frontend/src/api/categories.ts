import { api } from './client'
import type { CategorySummary } from '../types'

/** GET /api/categories → plain array of active categories, name order. */
export function listCategories(): Promise<CategorySummary[]> {
  return api.get<CategorySummary[]>('/api/categories')
}
