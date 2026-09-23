import type {
  AiClassifiedData,
  AssignedData,
  CategoryChangedData,
  PriorityChangedData,
  StatusChangedData,
  TicketEvent,
} from '../types'
import { formatConfidence, priorityLabel, statusLabel } from './format'

/** Maps used to resolve the ids stored in event payloads to display
 * names. Missing entries fall back gracefully (short id / raw slug). */
export interface EventNameMaps {
  userNameById: Map<string, string>
  categoryNameById: Map<string, string>
  categoryNameBySlug: Map<string, string>
}

function shortId(id: string): string {
  return `${id.slice(0, 8)}…`
}

function userLabel(maps: EventNameMaps, id: string | null): string {
  if (!id) return 'Unassigned'
  return maps.userNameById.get(id) ?? shortId(id)
}

function categoryLabel(maps: EventNameMaps, id: string | null): string {
  if (!id) return 'Uncategorized'
  return maps.categoryNameById.get(id) ?? shortId(id)
}

/** A single human-readable line (plus optional detail) for one event.
 * Never renders raw JSON. */
export interface FormattedEvent {
  text: string
  detail?: string
}

export function formatEvent(
  event: TicketEvent,
  maps: EventNameMaps,
): FormattedEvent {
  switch (event.type) {
    case 'TICKET_CREATED':
      return { text: 'Ticket created' }

    case 'STATUS_CHANGED': {
      const data = event.data as StatusChangedData
      return {
        text: `Status changed ${statusLabel(data.from as never)} → ${statusLabel(data.to as never)}`,
      }
    }

    case 'PRIORITY_CHANGED': {
      const data = event.data as PriorityChangedData
      return {
        text: `Priority changed ${priorityLabel(data.from as never)} → ${priorityLabel(data.to as never)}`,
      }
    }

    case 'ASSIGNED': {
      const data = event.data as AssignedData
      if (data.to === null) return { text: 'Unassigned' }
      return { text: `Assigned to ${userLabel(maps, data.to)}` }
    }

    case 'CATEGORY_CHANGED': {
      const data = event.data as CategoryChangedData
      return {
        text: `Category changed from ${categoryLabel(maps, data.from)} to ${categoryLabel(maps, data.to)}`,
      }
    }

    case 'AI_CLASSIFIED': {
      const data = event.data as AiClassifiedData
      const name =
        maps.categoryNameBySlug.get(data.category_slug) ?? data.category_slug
      return {
        text: `AI classified this ticket as ${name}`,
        // Heuristic score, never phrased as a probability.
        detail: `Confidence score: ${formatConfidence(data.confidence)}`,
      }
    }

    default: {
      // Unknown type (forward compatibility): humanize, never crash.
      // `event.type` is `never` here because every known type is
      // handled; widen it to string so a future type still renders.
      const rawType = event.type as string
      const humanized = rawType.toLowerCase().split('_').join(' ')
      return { text: humanized }
    }
  }
}

/** Actor display: null means a system event (pre-auth backend). */
export function actorLabel(event: TicketEvent): string {
  return event.actor ? event.actor.full_name : 'System'
}
