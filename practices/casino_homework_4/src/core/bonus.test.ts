import { describe, it, expect } from 'vitest'
import { bonusEligibility } from './bonus'

describe('bonusEligibility', () => {
  it('eligible if never claimed', () => {
    const res = bonusEligibility({ lastClaimedAtISO: null }, new Date('2026-10-07T00:10:00Z'))
    expect(res.eligible).toBe(true)
  })

  it('not eligible same UTC day', () => {
    const res = bonusEligibility({ lastClaimedAtISO: '2026-10-07T01:00:00Z' }, new Date('2026-10-07T12:00:00Z'))
    expect(res.eligible).toBe(false)
  })

  it('eligible next day', () => {
    const res = bonusEligibility({ lastClaimedAtISO: '2026-10-06T23:30:00Z' }, new Date('2026-10-07T00:10:00Z'))
    expect(res.eligible).toBe(true)
  })
})
