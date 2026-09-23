import { describe, expect, it } from 'vitest'
import { formatConfidence, formatDateTime, formatRelativeTime, priorityLabel, statusLabel } from './format'

describe('statusLabel / priorityLabel', () => {
  it('maps every backend enum to a human label', () => {
    expect(statusLabel('OPEN')).toBe('Open')
    expect(statusLabel('IN_PROGRESS')).toBe('In Progress')
    expect(statusLabel('RESOLVED')).toBe('Resolved')
    expect(statusLabel('CLOSED')).toBe('Closed')
    expect(priorityLabel('LOW')).toBe('Low')
    expect(priorityLabel('MEDIUM')).toBe('Medium')
    expect(priorityLabel('HIGH')).toBe('High')
    expect(priorityLabel('URGENT')).toBe('Urgent')
  })
})

describe('formatConfidence', () => {
  it('renders the heuristic score as a percentage', () => {
    expect(formatConfidence(0.82)).toBe('82%')
    expect(formatConfidence(1)).toBe('100%')
    expect(formatConfidence(0.55)).toBe('55%')
  })

  it('renders null (human-set category) as an em dash', () => {
    expect(formatConfidence(null)).toBe('—')
  })
})

describe('formatDateTime', () => {
  it('accepts ISO timestamps', () => {
    expect(formatDateTime('2026-09-23T12:00:00+00:00')).toContain('2026')
  })

  it('returns an em dash for null or unparseable input', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('—')
  })
})

describe('formatRelativeTime', () => {
  it('returns "just now" for timestamps within the last minute', () => {
    const iso = new Date(Date.now() + 10_000).toISOString()
    expect(formatRelativeTime(iso)).toBe('just now')
  })

  it('returns an em dash for null or unparseable input', () => {
    expect(formatRelativeTime(null)).toBe('—')
    expect(formatRelativeTime('nope')).toBe('—')
  })

  it('returns a non-empty relative label for older timestamps', () => {
    const iso = new Date(Date.now() - 5 * 60_000).toISOString()
    expect(formatRelativeTime(iso)).not.toBe('')
    expect(formatRelativeTime(iso)).not.toBe('—')
  })
})
