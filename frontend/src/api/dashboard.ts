import { api } from './client'
import type { DashboardSummary } from '../types'

/** GET /api/dashboard/summary */
export function getDashboardSummary(): Promise<DashboardSummary> {
  return api.get<DashboardSummary>('/api/dashboard/summary')
}
