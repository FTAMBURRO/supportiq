import type { TicketPriority, TicketStatus } from '../types'

/** Status transitions mirrored from the backend
 * (ticket_service._ALLOWED_STATUS_TRANSITIONS). The backend remains the
 * authority: this only keeps the select from offering impossible moves. */
export const STATUS_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  OPEN: ['IN_PROGRESS', 'RESOLVED'],
  IN_PROGRESS: ['OPEN', 'RESOLVED'],
  RESOLVED: ['IN_PROGRESS', 'CLOSED'],
  CLOSED: [],
}

/** Statuses a human may pick for a ticket in `current` (including the
 * current one itself, which the select shows as the selected value). */
export function selectableStatuses(current: TicketStatus): TicketStatus[] {
  return [current, ...STATUS_TRANSITIONS[current]]
}

export const ALL_PRIORITIES: TicketPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'URGENT']
