import { api } from './client'
import type {
  CreateTicketInput,
  PaginatedTickets,
  Ticket,
  TicketEvent,
  TicketListParams,
  UpdateTicketInput,
} from '../types'

/** GET /api/tickets — only the params the backend really supports. */
export function listTickets(params: TicketListParams = {}): Promise<PaginatedTickets> {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.priority) query.set('priority', params.priority)
  if (params.category_id) query.set('category_id', params.category_id)
  if (params.page && params.page > 1) query.set('page', String(params.page))
  // per_page intentionally absent: fixed at the backend default of 20.
  const qs = query.toString()
  return api.get<PaginatedTickets>(`/api/tickets${qs ? `?${qs}` : ''}`)
}

/** GET /api/tickets/<ticket_number> */
export function getTicket(ticketNumber: string): Promise<Ticket> {
  return api.get<Ticket>(`/api/tickets/${encodeURIComponent(ticketNumber)}`)
}

/** GET /api/tickets/<ticket_number>/events — oldest first, not paginated. */
export function getTicketEvents(ticketNumber: string): Promise<{ items: TicketEvent[] }> {
  return api.get<{ items: TicketEvent[] }>(
    `/api/tickets/${encodeURIComponent(ticketNumber)}/events`,
  )
}

/** POST /api/tickets → 201 with the created ticket. */
export function createTicket(input: CreateTicketInput): Promise<Ticket> {
  return api.post<Ticket>('/api/tickets', input)
}

/** PATCH /api/tickets/<ticket_number> → 200 with the updated ticket. */
export function updateTicket(
  ticketNumber: string,
  input: UpdateTicketInput,
): Promise<Ticket> {
  return api.patch<Ticket>(
    `/api/tickets/${encodeURIComponent(ticketNumber)}`,
    input,
  )
}
