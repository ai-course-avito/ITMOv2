import { create } from 'zustand'

const STORAGE_KEY = 'luckyspin.balance.v1'

export interface BalanceState {
  balance: number
  history: { type: 'spin' | 'bonus'; delta: number; at: string }[]
  add(amount: number, reason: 'spin' | 'bonus'): void
  set(amount: number): void
}

function load(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return 1000
    const n = Number(JSON.parse(raw))
    return Number.isFinite(n) ? n : 1000
  } catch {
    return 1000
  }
}

function save(n: number) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(n)) } catch { /* ignore */ }
}

export const useBalance = create<BalanceState>((set, get) => ({
  balance: load(),
  history: [],
  add(amount, reason) {
    const next = get().balance + amount
    save(next)
    set((s) => ({
      balance: next,
      history: [...s.history, { type: reason, delta: amount, at: new Date().toISOString() }],
    }))
  },
  set(amount) {
    save(amount)
    set({ balance: amount })
  }
}))
