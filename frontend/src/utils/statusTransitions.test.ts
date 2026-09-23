import { describe, expect, it } from 'vitest'
import { ALL_PRIORITIES, STATUS_TRANSITIONS, selectableStatuses } from './statusTransitions'

describe('STATUS_TRANSITIONS', () => {
  it('mirrors the backend transition matrix', () => {
    expect(STATUS_TRANSITIONS.OPEN).toEqual(['IN_PROGRESS', 'RESOLVED'])
    expect(STATUS_TRANSITIONS.IN_PROGRESS).toEqual(['OPEN', 'RESOLVED'])
    expect(STATUS_TRANSITIONS.RESOLVED).toEqual(['IN_PROGRESS', 'CLOSED'])
    expect(STATUS_TRANSITIONS.CLOSED).toEqual([])
  })
})

describe('selectableStatuses', () => {
  it('offers the current status plus its valid targets', () => {
    expect(selectableStatuses('OPEN')).toEqual(['OPEN', 'IN_PROGRESS', 'RESOLVED'])
    expect(selectableStatuses('RESOLVED')).toEqual([
      'RESOLVED',
      'IN_PROGRESS',
      'CLOSED',
    ])
  })

  it('offers only the current status for a closed ticket', () => {
    expect(selectableStatuses('CLOSED')).toEqual(['CLOSED'])
  })
})

describe('ALL_PRIORITIES', () => {
  it('lists the four backend priorities', () => {
    expect(ALL_PRIORITIES).toEqual(['LOW', 'MEDIUM', 'HIGH', 'URGENT'])
  })
})
