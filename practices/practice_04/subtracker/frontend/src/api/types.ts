// Types are camelCase: the API client converts snake_case keys at the boundary.
// Money fields are decimal strings and are never turned into numbers.
export type BillingCycle = 'monthly' | 'yearly' | 'weekly' | 'custom_days'
export type Plan = 'free' | 'pro'

export interface User {
  id: number
  email: string
  plan: Plan
  defaultCurrency: string
}

export interface Tokens {
  accessToken: string
  refreshToken: string
}

export interface Summary {
  monthlyTotal: string
  yearlyTotal: string
  currency: string
}

export interface SubscriptionShare {
  id: number
  name: string
  billingCycle: BillingCycle
  monthlyCost: string
  sharePercent: string
}

export interface Breakdown {
  currency: string
  monthlyTotal: string
  bySubscription: SubscriptionShare[]
}

export interface UpcomingCharge {
  id: number
  name: string
  amount: string
  billingCycle: BillingCycle
  chargeDate: string
  daysUntil: number
}

export interface Subscription {
  id: number
  name: string
  amount: string
  billingCycle: BillingCycle
  customIntervalDays: number | null
  isActive: boolean
  startDate: string
  nextBillingDate: string
  note: string | null
}

export interface SubscriptionListItem extends Subscription {
  monthlyCost: string
  chargeDate: string | null
  daysUntil: number | null
}

export interface SubscriptionInput {
  name: string
  amount: string
  billingCycle: BillingCycle
  customIntervalDays: number | null
  startDate: string
  note: string | null
  isActive: boolean
}

export type SortField = 'charge_date' | 'amount' | 'monthly_cost' | 'name'

export interface ListParams {
  isActive?: boolean
  billingCycle?: BillingCycle
  q?: string
  sort?: SortField
  order?: 'asc' | 'desc'
}
