import { airportLabel, airports, type Airport } from './airports.ts'

export type AirportChoice = { text: string; selected: Airport | null }

export type FareSearchInput = {
  origin: AirportChoice
  destination: AirportChoice
  departureDate: string
  returnDate: string
  roundTrip: boolean
  market: string
  direct: boolean
  maxPrice: string
}

export type FareSearchErrors = {
  origin?: string
  destination?: string
  form?: string
}

export type FareSearchRequest = {
  endpoint: '/api/fares/one-way' | '/api/fares/round-trip'
  body: {
    origin: string
    destination: string
    departure_date: string
    market: string
    direct: boolean
    return_date?: string
    max_price?: number
  }
  routeLabel: string
}

export type FareSearchPreparation =
  | { ok: true; request: FareSearchRequest }
  | { ok: false; errors: FareSearchErrors }

const SELECT_AIRPORT = 'Выберите аэропорт из списка.'
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function confirmedAirport(choice: AirportChoice): Airport | null {
  const selected = choice.selected
  const valid = selected !== null
    && choice.text === airportLabel(selected)
    && airports.some(airport => airport.code === selected.code
      && airport.city === selected.city && airport.airport === selected.airport)
  return valid ? selected : null
}

function validDate(value: string): boolean {
  if (!DATE_PATTERN.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function localToday(now: Date): string {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Pure preparation: editing the form never starts a search or changes a result.
export function prepareFareSearch(input: FareSearchInput, now = new Date()): FareSearchPreparation {
  const errors: FareSearchErrors = {}
  const origin = confirmedAirport(input.origin)
  const destination = confirmedAirport(input.destination)
  if (!origin) errors.origin = SELECT_AIRPORT
  if (!destination) errors.destination = SELECT_AIRPORT
  if (!origin || !destination) return { ok: false, errors }
  if (origin.code === destination.code) {
    return { ok: false, errors: { form: 'Пункты отправления и назначения должны отличаться.' } }
  }
  if (!validDate(input.departureDate) || input.departureDate < localToday(now)) {
    return { ok: false, errors: { form: 'Укажите полную дату вылета не в прошлом.' } }
  }
  if (input.roundTrip && (!validDate(input.returnDate) || input.returnDate < input.departureDate)) {
    return { ok: false, errors: { form: 'Дата возвращения должна быть не раньше даты вылета.' } }
  }
  if (!/^[A-Z]{2}$/.test(input.market)) {
    return { ok: false, errors: { form: 'Выберите рынок поиска.' } }
  }
  const maxPrice = input.maxPrice.trim()
  if (maxPrice && (!/^[1-9]\d*$/.test(maxPrice) || !Number.isSafeInteger(Number(maxPrice)))) {
    return { ok: false, errors: { form: 'Максимальная цена должна быть положительным целым числом.' } }
  }

  return {
    ok: true,
    request: {
      endpoint: input.roundTrip ? '/api/fares/round-trip' : '/api/fares/one-way',
      body: {
        origin: origin.code,
        destination: destination.code,
        departure_date: input.departureDate,
        market: input.market,
        direct: input.direct,
        ...(input.roundTrip ? { return_date: input.returnDate } : {}),
        ...(maxPrice ? { max_price: Number(maxPrice) } : {}),
      },
      routeLabel: `${airportLabel(origin)} → ${airportLabel(destination)}`,
    },
  }
}

// Call only after an explicit form submission and after clearing the previous result.
export async function postFareSearch<T>(request: FareSearchRequest, fetcher: typeof fetch = fetch): Promise<T> {
  let response: Response
  try {
    response = await fetcher(request.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request.body),
    })
  } catch {
    throw new Error('Не удалось выполнить поиск.')
  }

  let data: unknown
  try {
    data = await response.json()
  } catch {
    throw new Error('Не удалось выполнить поиск.')
  }
  if (!response.ok) {
    const detail = typeof data === 'object' && data !== null && 'detail' in data ? data.detail : null
    throw new Error(typeof detail === 'string' ? detail : response.status === 422
      ? 'Проверьте маршрут и даты поиска.'
      : 'Не удалось выполнить поиск.')
  }
  return data as T
}
