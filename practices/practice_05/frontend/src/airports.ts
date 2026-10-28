export type Airport = { city: string; airport: string; code: string }

// Initial supported routes. Keep one entry per airport, including Moscow's three airports.
export const airports: readonly Airport[] = [
  { city: 'Москва', airport: 'Шереметьево', code: 'SVO' },
  { city: 'Москва', airport: 'Домодедово', code: 'DME' },
  { city: 'Москва', airport: 'Внуково', code: 'VKO' },
  { city: 'Санкт-Петербург', airport: 'Пулково', code: 'LED' },
  { city: 'Казань', airport: 'Казань', code: 'KZN' },
  { city: 'Сочи', airport: 'Сочи', code: 'AER' },
]

export function airportLabel(airport: Airport) {
  return `${airport.city} — ${airport.airport}`
}

export function matchingAirports(text: string) {
  const query = text.trim().toLocaleLowerCase('ru-RU')
  return query ? airports.filter(airport => airport.city.toLocaleLowerCase('ru-RU').startsWith(query)) : []
}
