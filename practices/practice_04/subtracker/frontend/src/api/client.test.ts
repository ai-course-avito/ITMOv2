import { ApiError, NetworkError, request } from './client'
import { getTokens, onSessionExpired, setTokens } from './session'

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api client', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    setTokens({ accessToken: 'old', refreshToken: 'refresh' })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('sends the bearer token and converts keys to camelCase', async () => {
    fetchMock.mockResolvedValueOnce(json(200, { monthly_total: '82.10', yearly_total: '985.20', currency: 'USD' }))
    const data = await request<{ monthlyTotal: string }>('/api/stats/summary')
    expect(data.monthlyTotal).toBe('82.10')
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer old')
  })

  it('converts request bodies to snake_case', async () => {
    fetchMock.mockResolvedValueOnce(json(201, { id: 1 }))
    await request('/api/subscriptions', { method: 'POST', body: { billingCycle: 'monthly', customIntervalDays: null } })
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(JSON.parse(init.body as string)).toEqual({ billing_cycle: 'monthly', custom_interval_days: null })
  })

  it('refreshes an expired access token once and repeats the request', async () => {
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'expired' }))
      .mockResolvedValueOnce(json(200, { access_token: 'new', token_type: 'bearer' }))
      .mockResolvedValueOnce(json(200, { ok: true }))
    const data = await request<{ ok: boolean }>('/api/auth/me')
    expect(data.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(getTokens()?.accessToken).toBe('new')
    const retry = fetchMock.mock.calls[2]?.[1] as RequestInit
    expect((retry.headers as Record<string, string>).Authorization).toBe('Bearer new')
  })

  it('shares one refresh request between parallel 401 responses', async () => {
    let refreshCalls = 0
    fetchMock.mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/api/auth/refresh')) {
        refreshCalls += 1
        return json(200, { access_token: 'new', token_type: 'bearer' })
      }
      const auth = ((fetchMock.mock.lastCall?.[1] as RequestInit | undefined)?.headers ?? {}) as Record<string, string>
      return auth.Authorization === 'Bearer old' ? json(401, { detail: 'x' }) : json(200, { ok: true })
    })
    await Promise.all([request('/api/a'), request('/api/b')])
    expect(refreshCalls).toBe(1)
  })

  it('clears the session and notifies when the refresh token is rejected too', async () => {
    const expired = vi.fn()
    const off = onSessionExpired(expired)
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'expired' }))
      .mockResolvedValueOnce(json(401, { detail: 'bad refresh' }))
    await expect(request('/api/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(getTokens()).toBeNull()
    expect(expired).toHaveBeenCalledTimes(1)
    off()
  })

  it('does not start the refresh flow for login failures', async () => {
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'Incorrect email or password' }))
    await expect(request('/api/auth/login', { method: 'POST', body: {}, auth: false })).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(getTokens()?.accessToken).toBe('old')
  })

  it('turns a failed fetch into a NetworkError', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(request('/api/stats/summary')).rejects.toBeInstanceOf(NetworkError)
  })

  it('returns undefined for 204', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(request('/api/subscriptions/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})
