import { readStored, removeStored, writeStored } from '../lib/storage'
import type { Tokens } from './types'

const KEY = 'subtracker.session'

// Tokens live in localStorage so a reload keeps the user signed in.
// Trade-off: scripts of the page can read them (XSS); accepted for the MVP, see SPEC.md.
export function getTokens(): Tokens | null {
  const raw = readStored(KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<Tokens>
    if (typeof parsed.accessToken === 'string' && typeof parsed.refreshToken === 'string') {
      return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken }
    }
  } catch {
    /* fall through */
  }
  return null
}

export function setTokens(tokens: Tokens): void {
  writeStored(KEY, JSON.stringify(tokens))
}

export function clearTokens(): void {
  removeStored(KEY)
}

type Listener = () => void
const expiredListeners = new Set<Listener>()

export function onSessionExpired(listener: Listener): () => void {
  expiredListeners.add(listener)
  return () => expiredListeners.delete(listener)
}

export function notifySessionExpired(): void {
  expiredListeners.forEach((listener) => listener())
}
