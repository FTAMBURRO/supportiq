/** Types derived EXCLUSIVELY from the real backend serializers.
 * Nothing here is invented: every field mirrors app/api/serializers.py. */

export type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED'

export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'

/** Who set the current category: a human or the classifier. */
export type CategorySource = 'MANUAL' | 'AI'

export type TicketEventType =
  | 'TICKET_CREATED'
  | 'STATUS_CHANGED'
  | 'PRIORITY_CHANGED'
  | 'ASSIGNED'
  | 'CATEGORY_CHANGED'
  | 'AI_CLASSIFIED'

/** Nested reference objects as serialized by the backend. */
export interface CategoryRef {
  id: string
  name: string
  slug: string
}

export interface UserRef {
  id: string
  full_name: string
  email: string
}

/** GET /api/users and GET /api/categories return plain arrays of these. */
export type UserSummary = UserRef
export type CategorySummary = CategoryRef

/** serialize_ticket(): the single ticket representation. */
export interface Ticket {
  id: string
  ticket_number: string
  title: string
  description: string
  status: TicketStatus
  priority: TicketPriority
  requester_id: string
  assignee_id: string | null
  category_id: string | null
  category: CategoryRef | null
  category_source: CategorySource
  /** Heuristic score in (0..1], NOT a calibrated probability; null when
   * a human set (or cleared) the category. */
  classification_confidence: number | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  closed_at: string | null
}

export interface Pagination {
  page: number
  per_page: number
  total: number
  /** 0 when total is 0 (backend ceil division). */
  pages: number
}

export interface PaginatedTickets {
  items: Ticket[]
  pagination: Pagination
}

/** serialize_event(): shapes of `data` differ per event type. */
export interface StatusChangedData {
  from: string
  to: string
}

export interface PriorityChangedData {
  from: string
  to: string
}

/** User ids (or null); resolve to names via GET /api/users. */
export interface AssignedData {
  from: string | null
  to: string | null
}

/** Category ids (or null); resolve to names via GET /api/categories. */
export interface CategoryChangedData {
  from: string | null
  to: string | null
}

export interface AiClassifiedEvidence {
  ticket_number: string
  category_slug: string
  similarity: number
}

export interface AiClassifiedData {
  category_id: string
  category_slug: string
  confidence: number
  share: number
  margin: number
  top_similarity: number
  k: number
  neighbors_used: number
  evidence: AiClassifiedEvidence[]
}

export type TicketEventData =
  | StatusChangedData
  | PriorityChangedData
  | AssignedData
  | CategoryChangedData
  | AiClassifiedData
  | Record<string, never>

export interface TicketEvent {
  id: string
  type: TicketEventType
  /** null for system-generated / pre-auth events → renders as "System". */
  actor: UserRef | null
  data: TicketEventData
  created_at: string
}

export interface EventList {
  items: TicketEvent[]
}

/** GET /api/dashboard/summary (exact keys, zero-filled). */
export interface DashboardSummary {
  tickets: {
    total: number
    open: number
    in_progress: number
    resolved: number
    closed: number
  }
  priority: {
    urgent: number
    high: number
    medium: number
    low: number
  }
  unassigned: number
}

/** The backend's consistent error envelope. */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
  }
}

/** Query params supported by GET /api/tickets (nothing else exists). */
export interface TicketListParams {
  status?: string
  priority?: string
  category_id?: string
  page?: number
}

/** POST /api/tickets body (category intentionally absent in the UI:
 * tickets are created uncategorized so the classifier can act). */
export interface CreateTicketInput {
  title: string
  description: string
  requester_id: string
  priority?: TicketPriority
}

/** PATCH /api/tickets/<n> body: any subset of these fields. */
export interface UpdateTicketInput {
  title?: string
  description?: string
  status?: TicketStatus
  priority?: TicketPriority
  assignee_id?: string | null
  category_id?: string | null
}
