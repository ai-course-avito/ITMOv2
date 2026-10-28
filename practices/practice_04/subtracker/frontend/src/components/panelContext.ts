import { createContext, useContext } from 'react'
import type { Subscription } from '../api/types'

export interface PanelValue {
  // Opens the add/edit panel; null means a new subscription.
  open: (subscription?: Subscription | null) => void
}

export const PanelContext = createContext<PanelValue | null>(null)

export function usePanel(): PanelValue {
  const value = useContext(PanelContext)
  if (!value) throw new Error('usePanel must be used inside AppLayout')
  return value
}
