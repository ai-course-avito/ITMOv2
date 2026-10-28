import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

// Bumped after any change of subscriptions so open screens reload their data.
interface Value {
  version: number
  bump: () => void
}

const DataVersionContext = createContext<Value | null>(null)

export function DataVersionProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0)
  const bump = useCallback(() => setVersion((v) => v + 1), [])
  const value = useMemo(() => ({ version, bump }), [version, bump])
  return <DataVersionContext.Provider value={value}>{children}</DataVersionContext.Provider>
}

export function useDataVersion(): Value {
  const value = useContext(DataVersionContext)
  if (!value) throw new Error('useDataVersion must be used inside DataVersionProvider')
  return value
}
