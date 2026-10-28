import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/endpoints'
import { ApiError } from '../api/client'
import { clearTokens, getTokens, onSessionExpired, setTokens } from '../api/session'
import type { User } from '../api/types'

type Status = 'loading' | 'anon' | 'authed' | 'error'

interface AuthValue {
  status: Status
  user: User | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  retry: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(() => (getTokens() ? 'loading' : 'anon'))
  const [user, setUser] = useState<User | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!getTokens()) return
    let cancelled = false
    api
      .me()
      .then((me) => {
        if (cancelled) return
        setUser(me)
        setStatus('authed')
      })
      .catch((error) => {
        if (cancelled) return
        if (error instanceof ApiError) {
          clearTokens()
          setStatus('anon')
        } else {
          setStatus('error')
        }
      })
    return () => {
      cancelled = true
    }
  }, [attempt])

  useEffect(
    () =>
      onSessionExpired(() => {
        setUser(null)
        setStatus('anon')
      }),
    [],
  )

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password)
    setTokens(tokens)
    try {
      setUser(await api.me())
      setStatus('authed')
    } catch (error) {
      clearTokens()
      throw error
    }
  }, [])

  const register = useCallback(
    async (email: string, password: string) => {
      await api.register(email, password)
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setStatus('anon')
  }, [])

  const retry = useCallback(() => {
    setStatus('loading')
    setAttempt((n) => n + 1)
  }, [])

  const value = useMemo(
    () => ({ status, user, login, register, logout, retry }),
    [status, user, login, register, logout, retry],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
