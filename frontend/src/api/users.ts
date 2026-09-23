import { api } from './client'
import type { UserSummary } from '../types'

/** GET /api/users → plain array of active users, name order. */
export function listUsers(): Promise<UserSummary[]> {
  return api.get<UserSummary[]>('/api/users')
}
