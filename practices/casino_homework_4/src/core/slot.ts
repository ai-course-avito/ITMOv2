import type { RNG } from './random'

export interface SpinInput {
  balance: number
  bet: number
}

export interface SpinResult {
  win: number
  balance: number
  symbols: string[]
}

const reels = ['🍒', '🍋', '⭐', '7️⃣'] as const

export function spin({ balance, bet }: SpinInput, rng: RNG): SpinResult {
  if (bet <= 0) throw new Error('Bet must be positive')
  if (balance < bet) throw new Error('Insufficient balance')

  const pull = () => reels[Math.floor(rng() * reels.length)]
  const symbols = [pull(), pull(), pull()]

  let multiplier = 0
  if (symbols.every((s) => s === '7️⃣')) multiplier = 10
  else if (symbols.every((s) => s === '⭐')) multiplier = 5
  else if (symbols[0] === symbols[1] || symbols[1] === symbols[2]) multiplier = 2

  const win = bet * multiplier
  const newBalance = balance - bet + win
  return { win, balance: newBalance, symbols }
}
