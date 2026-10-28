import { setTokens } from '../api/session'

export interface MockSub {
  id: number
  name: string
  amount: string
  billing_cycle: string
  custom_interval_days: number | null
  is_active: boolean
  start_date: string
  next_billing_date: string
  note: string | null
  monthly_cost: string
  charge_date: string | null
  days_until: number | null
}

export const sub = (over: Partial<MockSub> & Pick<MockSub, 'id' | 'name'>): MockSub => ({
  amount: '10.00',
  billing_cycle: 'monthly',
  custom_interval_days: null,
  is_active: true,
  start_date: '2026-01-01',
  next_billing_date: '2026-10-20',
  note: null,
  monthly_cost: '10.00',
  charge_date: '2026-10-20',
  days_until: 4,
  ...over,
})

export interface Call {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
}

export interface MockState {
  subs: MockSub[]
  plan: 'free' | 'pro'
  calls: Call[]
  loginStatus: number
  registerStatus: number
  createResponse: { status: number; body: unknown } | null
}

export function createState(over: Partial<MockState> = {}): MockState {
  return {
    subs: [
      sub({ id: 1, name: 'Gym', amount: '6.00', billing_cycle: 'weekly', monthly_cost: '26.00', days_until: 1, charge_date: '2026-10-17' }),
      sub({ id: 2, name: 'Netflix', amount: '15.49', monthly_cost: '15.49', days_until: 2, charge_date: '2026-10-18' }),
      sub({ id: 3, name: 'iCloud+', amount: '35.88', billing_cycle: 'yearly', monthly_cost: '2.99', days_until: 120, charge_date: '2027-02-13' }),
      sub({ id: 4, name: 'Notion', amount: '8.00', monthly_cost: '8.00', is_active: false, days_until: null, charge_date: null }),
    ],
    plan: 'free',
    calls: [],
    loginStatus: 200,
    registerStatus: 201,
    createResponse: null,
    ...over,
  }
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

// Minimal in-memory imitation of the backend, enough for the screens.
export function installMockApi(state: MockState) {
  const handler = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input))
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    state.calls.push({ method, path: url.pathname, query: url.searchParams, body })
    const active = state.subs.filter((s) => s.is_active)

    if (url.pathname === '/api/auth/login') {
      return state.loginStatus === 200
        ? json(200, { access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
        : json(state.loginStatus, { detail: 'Incorrect email or password' })
    }
    if (url.pathname === '/api/auth/register') {
      return state.registerStatus === 201
        ? json(201, { id: 1, email: body.email, plan: 'free', default_currency: 'USD' })
        : json(state.registerStatus, { detail: 'Email already registered' })
    }
    if (url.pathname === '/api/auth/me') {
      return json(200, { id: 1, email: 'demo@example.com', plan: state.plan, default_currency: 'USD' })
    }
    if (url.pathname === '/api/stats/summary') {
      return json(200, { monthly_total: '82.10', yearly_total: '985.20', currency: 'USD' })
    }
    if (url.pathname === '/api/stats/breakdown') {
      return json(200, {
        currency: 'USD',
        monthly_total: '82.10',
        by_subscription: active.map((s) => ({
          id: s.id,
          name: s.name,
          billing_cycle: s.billing_cycle,
          monthly_cost: s.monthly_cost,
          share_percent: '33.33',
        })),
        by_cycle: [],
      })
    }
    if (url.pathname === '/api/subscriptions/upcoming') {
      const days = Number(url.searchParams.get('days'))
      return json(
        200,
        active
          .filter((s) => (s.days_until ?? 999) <= days)
          .map((s) => ({
            id: s.id,
            name: s.name,
            amount: s.amount,
            billing_cycle: s.billing_cycle,
            charge_date: s.charge_date,
            days_until: s.days_until,
          })),
      )
    }
    if (url.pathname === '/api/subscriptions' && method === 'GET') {
      let list = [...state.subs]
      const isActive = url.searchParams.get('is_active')
      if (isActive !== null) list = list.filter((s) => String(s.is_active) === isActive)
      const cycle = url.searchParams.get('billing_cycle')
      if (cycle) list = list.filter((s) => s.billing_cycle === cycle)
      const q = url.searchParams.get('q')?.toLowerCase()
      if (q) list = list.filter((s) => s.name.toLowerCase().includes(q))
      return json(200, list)
    }
    if (url.pathname === '/api/subscriptions' && method === 'POST') {
      if (state.createResponse) return json(state.createResponse.status, state.createResponse.body)
      const created = sub({
        id: 100,
        name: body.name,
        amount: body.amount,
        billing_cycle: body.billing_cycle,
        custom_interval_days: body.custom_interval_days,
        monthly_cost: body.amount,
      })
      state.subs.push(created)
      return json(201, created)
    }
    const match = url.pathname.match(/^\/api\/subscriptions\/(\d+)$/)
    if (match) {
      const id = Number(match[1])
      const target = state.subs.find((s) => s.id === id)
      if (!target) return json(404, { detail: 'Subscription not found' })
      if (method === 'PATCH') {
        if (body.is_active !== undefined) {
          target.is_active = body.is_active
          target.days_until = body.is_active ? 4 : null
          target.charge_date = body.is_active ? '2026-10-20' : null
        }
        return json(200, target)
      }
      if (method === 'DELETE') {
        state.subs = state.subs.filter((s) => s.id !== id)
        return new Response(null, { status: 204 })
      }
    }
    return json(404, { detail: 'not found' })
  }
  vi.stubGlobal('fetch', vi.fn(handler))
}

export function signIn() {
  setTokens({ accessToken: 'a', refreshToken: 'r' })
}
