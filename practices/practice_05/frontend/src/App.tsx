import { useState, type FormEvent } from 'react'

type Segment = {
  marketing_carrier_code: string | null
  operating_carrier_name: string | null
  departure_airport: string
  departure_time_local: string
  arrival_airport: string
  arrival_time_local: string
}
type Leg = { carrier: string | null; stops: number; segments: Segment[] }
type Itinerary = {
  ignav_id: string
  price: { amount: number; currency: string }
  outbound: Leg
  inbound: Leg | null
  requires_self_transfer: boolean
}
type PriceComparison = {
  status: 'compared' | 'no_previous_price' | 'no_current_price' | 'currency_mismatch'
  previous_price: number | null
  current_price: number | null
  previous_currency: string | null
  current_currency: string | null
  difference: number | null
  percent_difference: number | null
  previous_search_at: string | null
  current_search_at: string
}
type SearchResult = { itineraries: Itinerary[]; observed_at: string | null; cache_hit: boolean; comparison: PriceComparison }

function money(amount: number, currency: string) {
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency }).format(amount)
}

function comparisonText(comparison: PriceComparison) {
  if (comparison.status === 'no_current_price') return 'В этом поиске билетов нет, поэтому сравнить цены нельзя.'
  if (comparison.status === 'no_previous_price') return 'Это первый поиск с такими параметрами. Пока не с чем сравнивать.'
  if (comparison.status === 'currency_mismatch') return 'Валюта результата отличается от предыдущего поиска. Сравнение цен невозможно.'
  const difference = comparison.difference ?? 0
  if (difference === 0) return 'Минимальная цена не изменилась с прошлого поиска.'
  const direction = difference < 0 ? 'Дешевле' : 'Дороже'
  const change = money(Math.abs(difference), comparison.current_currency ?? 'RUB')
  const percent = comparison.percent_difference === null ? '' : ` (${Math.abs(comparison.percent_difference).toFixed(1)}%)`
  return `${direction} на ${change}${percent} по сравнению с предыдущим поиском.`
}

function legText(leg: Leg) {
  const first = leg.segments[0]
  const last = leg.segments[leg.segments.length - 1]
  const carrier = leg.carrier || first.operating_carrier_name || first.marketing_carrier_code || 'Перевозчик не указан'
  const stops = leg.stops === 0 ? 'без пересадок' : `${leg.stops} пересадок`
  return `${first.departure_airport} ${first.departure_time_local.replace('T', ' ')} → ${last.arrival_airport} ${last.arrival_time_local.replace('T', ' ')} · ${carrier} · ${stops}`
}

function App() {
  const [origin, setOrigin] = useState('MOW')
  const [destination, setDestination] = useState('LED')
  const [departureDate, setDepartureDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [roundTrip, setRoundTrip] = useState(false)
  const [direct, setDirect] = useState(false)
  const [maxPrice, setMaxPrice] = useState('')
  const [market, setMarket] = useState('RU')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SearchResult | null>(null)
  const [searchedRoute, setSearchedRoute] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult(null)
    if (origin.trim().toUpperCase() === destination.trim().toUpperCase()) {
      setError('Пункты отправления и назначения должны отличаться.')
      return
    }
    if (roundTrip && returnDate < departureDate) {
      setError('Дата возвращения должна быть не раньше даты вылета.')
      return
    }
    const body = {
      origin: origin.trim().toUpperCase(),
      destination: destination.trim().toUpperCase(),
      departure_date: departureDate,
      market,
      direct,
      ...(roundTrip ? { return_date: returnDate } : {}),
      ...(maxPrice ? { max_price: Number(maxPrice) } : {}),
    }
    setIsLoading(true)
    try {
      const response = await fetch(`/api/fares/${roundTrip ? 'round-trip' : 'one-way'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await response.json()
      if (!response.ok) {
        const detail = data.detail
        throw new Error(typeof detail === 'string' ? detail : 'Проверьте маршрут и даты поиска.')
      }
      setSearchedRoute(`${body.origin} → ${body.destination}`)
      setResult(data as SearchResult)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось выполнить поиск.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="page">
      <header className="topbar"><span className="topbar-brand">Билетик</span><span className="topbar-active">Поиск</span><span className="topbar-right">Поиск авиабилетов</span></header>
      <main className="main">
        <div className="logo" aria-label="Билетик"><span className="logo-blue">Б</span><span className="logo-red">и</span><span className="logo-yellow">л</span><span className="logo-blue">е</span><span className="logo-green">т</span><span className="logo-red">и</span><span className="logo-blue">к</span></div>
        <p className="tagline">Найдите билет по приятной цене</p>
        <form className="search-form" onSubmit={handleSubmit}>
          <div className="route-fields">
            <label className="field"><span>Откуда · IATA</span><input value={origin} onChange={event => setOrigin(event.target.value)} pattern="[A-Za-z]{3}" maxLength={3} required placeholder="MOW" /></label>
            <span className="route-arrow" aria-hidden="true">→</span>
            <label className="field"><span>Куда · IATA</span><input value={destination} onChange={event => setDestination(event.target.value)} pattern="[A-Za-z]{3}" maxLength={3} required placeholder="LED" /></label>
          </div>
          <div className="options-row">
            <label className="field"><span>Дата вылета</span><input type="date" value={departureDate} min={new Date().toLocaleDateString('en-CA')} onChange={event => setDepartureDate(event.target.value)} required /></label>
            {roundTrip && <label className="field"><span>Дата возвращения</span><input type="date" value={returnDate} min={departureDate} onChange={event => setReturnDate(event.target.value)} required /></label>}
          </div>
          <div className="options-row">
            <label className="field"><span>Максимальная цена</span><input type="number" min="1" step="1" value={maxPrice} onChange={event => setMaxPrice(event.target.value)} placeholder="Без ограничения" /></label>
            <label className="field"><span>Рынок · валюта зависит от него</span><select value={market} onChange={event => setMarket(event.target.value)}><option value="RU">Россия</option><option value="US">США</option><option value="GB">Великобритания</option><option value="TR">Турция</option><option value="AE">ОАЭ</option></select></label>
          </div>
          <div className="checks"><label><input type="checkbox" checked={roundTrip} onChange={event => setRoundTrip(event.target.checked)} /> Туда и обратно</label><label><input type="checkbox" checked={direct} onChange={event => setDirect(event.target.checked)} /> Только прямые</label></div>
          <button className="search-button" type="submit" disabled={isLoading}>{isLoading ? 'Ищем билеты…' : 'Найти билеты'}</button>
        </form>
        <div className="feedback" aria-live="polite">{error && <p className="error">{error}</p>}{isLoading && <p>Проверяем варианты маршрута…</p>}</div>
        {result && <section className="results" aria-label="Результаты поиска">
          <h1>{searchedRoute}</h1>
          <p className="results-note">Цены ориентировочные; наличие и итоговую стоимость нужно проверить у продавца.</p>
          {result.comparison && <div className="comparison" aria-label="Сравнение цен">
            <strong>{comparisonText(result.comparison)}</strong>
            {result.comparison.current_price !== null && result.comparison.current_currency && <span>Сейчас: {money(result.comparison.current_price, result.comparison.current_currency)}</span>}
            {result.comparison.previous_price !== null && result.comparison.previous_currency && <span>Прошлый поиск: {money(result.comparison.previous_price, result.comparison.previous_currency)}</span>}
            {result.cache_hit && <small>Тарифы получены из кеша и могут не отражать новое изменение цены.</small>}
          </div>}
          {result.itineraries.length === 0 ? <p>По вашему запросу билеты не найдены. Попробуйте другие даты или фильтры.</p> : <div className="flights">{result.itineraries.map(itinerary => <article className="flight" key={itinerary.ignav_id}>
            <div className="flight-details"><div>Туда: {legText(itinerary.outbound)}</div>{itinerary.inbound && <div>Обратно: {legText(itinerary.inbound)}</div>}{itinerary.requires_self_transfer && <div>Может потребоваться самостоятельная пересадка</div>}</div>
            <strong>от {money(itinerary.price.amount, itinerary.price.currency)}</strong>
          </article>)}</div>}
        </section>}
      </main>
      <footer className="footer">Учебный проект · Поиск авиабилетов</footer>
    </div>
  )
}

export default App
