import { camelizeKeys, snakeizeKeys } from './case'
import { clearTokens, getTokens, notifySessionExpired, setTokens } from './session'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  constructor(status: number, detail: unknown) {
    super(`API error ${status}`)
    this.status = status
    this.detail = detail
  }
}

export class NetworkError extends Error {
  constructor() {
    super('Network error')
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  query?: Record<string, string | number | boolean | undefined>
  body?: unknown
  // false for login, register and refresh: they must not trigger the refresh flow.
  auth?: boolean
  signal?: AbortSignal
}

let refreshing: Promise<boolean> | null = null

// One refresh request is shared by all requests that got 401 at the same time.
function refreshAccessToken(): Promise<boolean> {
  if (refreshing) return refreshing
  refreshing = (async () => {
    const tokens = getTokens()
    if (!tokens) return false
    try {
      const data = await send<{ accessToken: string }>('/api/auth/refresh', {
        method: 'POST',
        body: { refreshToken: tokens.refreshToken },
        auth: false,
      })
      setTokens({ accessToken: data.accessToken, refreshToken: tokens.refreshToken })
      return true
    } catch (error) {
      if (error instanceof ApiError) return false
      throw error
    }
  })().finally(() => {
    refreshing = null
  })
  return refreshing
}

async function send<T>(path: string, options: RequestOptions): Promise<T> {
  const { method = 'GET', query, body, auth = true, signal } = options
  const url = new URL(path, API_URL)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
  }
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const tokens = getTokens()
    if (tokens) headers.Authorization = `Bearer ${tokens.accessToken}`
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(snakeizeKeys(body)),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new NetworkError()
  }

  if (response.status === 204) return undefined as T
  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, (data as { detail?: unknown } | null)?.detail ?? data)
  }
  return camelizeKeys<T>(data)
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await send<T>(path, options)
  } catch (error) {
    const canRefresh = options.auth !== false && error instanceof ApiError && error.status === 401
    if (!canRefresh) throw error
    if (await refreshAccessToken()) return send<T>(path, options)
    clearTokens()
    notifySessionExpired()
    throw error
  }
}
