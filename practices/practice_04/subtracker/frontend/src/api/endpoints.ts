import { request } from './client'
import type {
  Breakdown,
  ListParams,
  Subscription,
  SubscriptionInput,
  SubscriptionListItem,
  Summary,
  Tokens,
  UpcomingCharge,
  User,
} from './types'

interface LoginResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
}

export const api = {
  async login(email: string, password: string): Promise<Tokens> {
    const data = await request<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    })
    return { accessToken: data.accessToken, refreshToken: data.refreshToken }
  },
  register: (email: string, password: string) =>
    request<User>('/api/auth/register', { method: 'POST', body: { email, password }, auth: false }),
  me: () => request<User>('/api/auth/me'),
  summary: (signal?: AbortSignal) => request<Summary>('/api/stats/summary', { signal }),
  breakdown: (signal?: AbortSignal) => request<Breakdown>('/api/stats/breakdown', { signal }),
  upcoming: (days: number, signal?: AbortSignal) =>
    request<UpcomingCharge[]>('/api/subscriptions/upcoming', { query: { days }, signal }),
  listSubscriptions: (params: ListParams, signal?: AbortSignal) =>
    request<SubscriptionListItem[]>('/api/subscriptions', {
      query: {
        is_active: params.isActive,
        billing_cycle: params.billingCycle,
        q: params.q?.trim() || undefined,
        sort: params.sort,
        order: params.order,
        limit: 500,
      },
      signal,
    }),
  createSubscription: (input: SubscriptionInput) =>
    request<Subscription>('/api/subscriptions', { method: 'POST', body: input }),
  updateSubscription: (id: number, patch: Partial<SubscriptionInput>) =>
    request<Subscription>(`/api/subscriptions/${id}`, { method: 'PATCH', body: patch }),
  deleteSubscription: (id: number) =>
    request<void>(`/api/subscriptions/${id}`, { method: 'DELETE' }),
}
