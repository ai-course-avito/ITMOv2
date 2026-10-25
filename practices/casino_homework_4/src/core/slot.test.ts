import { describe, it, expect } from 'vitest'
import { spin } from './slot'

const rngSeq = (vals: number[]) => {
  let i = 0
  return () => vals[i++ % vals.length]
}

describe('spin', () => {
  it('deducts bet and pays 2x for adjacent pair', () => {
    const rng = rngSeq([0, 0, 0.4]) // 🍒, 🍒, 🍋 → pair → 2x
    const res = spin({ balance: 100, bet: 10 }, rng)
    expect(res.win).toBe(20)
    expect(res.balance).toBe(110)
  })

  it('throws on insufficient balance', () => {
    const rng = rngSeq([0])
    expect(() => spin({ balance: 5, bet: 10 }, rng)).toThrow('Insufficient balance')
  })
})
