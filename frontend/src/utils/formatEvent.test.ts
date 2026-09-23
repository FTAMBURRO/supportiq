import { describe, expect, it } from 'vitest'
import { actorLabel, formatEvent, type EventNameMaps } from './formatEvent'
import type { TicketEvent, TicketEventType } from '../types'

const maps: EventNameMaps = {
  userNameById: new Map([['user-1', 'Ana García']]),
  categoryNameById: new Map([
    ['cat-1', 'Network'],
    ['cat-2', 'Hardware'],
  ]),
  categoryNameBySlug: new Map([['network', 'Network']]),
}

function event(
  type: TicketEventType,
  data: TicketEvent['data'] = {},
  actor: TicketEvent['actor'] = null,
): TicketEvent {
  return {
    id: 'event-1',
    type,
    actor,
    data,
    created_at: '2026-09-23T12:00:00+00:00',
  }
}

describe('formatEvent', () => {
  it('formats TICKET_CREATED', () => {
    expect(formatEvent(event('TICKET_CREATED'), maps)).toEqual({
      text: 'Ticket created',
    })
  })

  it('formats STATUS_CHANGED with human labels and an arrow', () => {
    const formatted = formatEvent(
      event('STATUS_CHANGED', { from: 'OPEN', to: 'IN_PROGRESS' }),
      maps,
    )
    expect(formatted.text).toBe('Status changed Open → In Progress')
  })

  it('formats PRIORITY_CHANGED with human labels', () => {
    const formatted = formatEvent(
      event('PRIORITY_CHANGED', { from: 'MEDIUM', to: 'URGENT' }),
      maps,
    )
    expect(formatted.text).toBe('Priority changed Medium → Urgent')
  })

  it('resolves the assignee id to a name', () => {
    const formatted = formatEvent(
      event('ASSIGNED', { from: null, to: 'user-1' }),
      maps,
    )
    expect(formatted.text).toBe('Assigned to Ana García')
  })

  it('renders an unassign as "Unassigned"', () => {
    const formatted = formatEvent(
      event('ASSIGNED', { from: 'user-1', to: null }),
      maps,
    )
    expect(formatted.text).toBe('Unassigned')
  })

  it('falls back to a short id when a user id cannot be resolved', () => {
    const formatted = formatEvent(
      event('ASSIGNED', { from: null, to: 'unknown-user-id' }),
      maps,
    )
    expect(formatted.text).toBe('Assigned to unknown-…')
  })

  it('resolves category ids in CATEGORY_CHANGED, null meaning Uncategorized', () => {
    const formatted = formatEvent(
      event('CATEGORY_CHANGED', { from: 'cat-1', to: 'cat-2' }),
      maps,
    )
    expect(formatted.text).toBe('Category changed from Network to Hardware')

    const clearing = formatEvent(
      event('CATEGORY_CHANGED', { from: 'cat-1', to: null }),
      maps,
    )
    expect(clearing.text).toBe('Category changed from Network to Uncategorized')
  })

  it('formats AI_CLASSIFIED with a confidence score, never a probability', () => {
    const formatted = formatEvent(
      event('AI_CLASSIFIED', {
        category_id: 'cat-1',
        category_slug: 'network',
        confidence: 0.82,
        share: 0.75,
        margin: 0.2,
        top_similarity: 0.9,
        k: 5,
        neighbors_used: 4,
        evidence: [],
      }),
      maps,
    )
    expect(formatted.text).toBe('AI classified this ticket as Network')
    expect(formatted.detail).toBe('Confidence score: 82%')
    expect(`${formatted.text} ${formatted.detail}`).not.toContain('probability')
  })

  it('falls back to the raw slug when the category slug is unknown', () => {
    const formatted = formatEvent(
      event('AI_CLASSIFIED', {
        category_id: 'x',
        category_slug: 'brand-new-slug',
        confidence: 0.6,
        share: 0.5,
        margin: 0.1,
        top_similarity: 0.7,
        k: 5,
        neighbors_used: 2,
        evidence: [],
      }),
      maps,
    )
    expect(formatted.text).toBe('AI classified this ticket as brand-new-slug')
    expect(formatted.detail).toBe('Confidence score: 60%')
  })

  it('humanizes unknown event types instead of crashing', () => {
    const formatted = formatEvent(
      event('SOME_FUTURE_EVENT' as TicketEventType),
      maps,
    )
    expect(formatted.text).toBe('some future event')
  })
})

describe('actorLabel', () => {
  it('renders null actors as System', () => {
    expect(actorLabel(event('TICKET_CREATED'))).toBe('System')
  })

  it('renders the actor full name when present', () => {
    const withActor = event(
      'PRIORITY_CHANGED',
      { from: 'LOW', to: 'HIGH' },
      { id: 'user-1', full_name: 'Ana García', email: 'ana@supportiq.test' },
    )
    expect(actorLabel(withActor)).toBe('Ana García')
  })
})
