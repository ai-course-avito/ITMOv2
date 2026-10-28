import assert from 'node:assert/strict'
import test from 'node:test'

import { airportLabel, airports, matchingAirports } from './airports.ts'
import { postFareSearch, prepareFareSearch } from './fareSearch.ts'

const now = new Date(2026, 9, 29)
const chosen = airport => ({ text: airportLabel(airport), selected: airport })
const base = {
  origin: chosen(airports[0]),
  destination: chosen(airports[3]),
  departureDate: '2026-11-15',
  returnDate: '',
  roundTrip: false,
  market: 'RU',
  direct: false,
  maxPrice: '',
}

test('catalog has unique airport codes and city prefix suggestions', () => {
  assert.equal(new Set(airports.map(airport => airport.code)).size, airports.length)
  assert.equal(new Set(airports.map(airport => airport.city)).size, 48)
  assert.equal(airports.length, 58)
  assert.deepEqual(matchingAirports('  мОС ' ).map(airport => airport.code), ['SVO', 'DME', 'VKO'])
  assert.deepEqual(matchingAirports('оск'), [])
  assert.deepEqual(matchingAirports('кАЗ').map(airport => airport.code), ['KZN'])
  assert.deepEqual(matchingAirports(' лОн ').map(airport => airport.code), ['LHR', 'LGW', 'LCY', 'STN', 'LTN'])
  assert.deepEqual(matchingAirports('пар').map(airport => airport.code), ['CDG', 'ORY'])
  assert.deepEqual(matchingAirports('рим').map(airport => airport.code), ['FCO', 'CIA'])
  assert.deepEqual(matchingAirports('киш').map(airport => airport.code), ['RMO'])
  assert.deepEqual(matchingAirports(''), [])
  assert.deepEqual(matchingAirports('SVO'), [])
})

test('European capital choices use their airport codes in the existing request', () => {
  const origin = airports.find(airport => airport.code === 'LHR')
  const destination = airports.find(airport => airport.code === 'CDG')
  assert.ok(origin && destination)
  const prepared = prepareFareSearch({ ...base, origin: chosen(origin), destination: chosen(destination) }, now)
  assert.equal(prepared.ok, true)
  if (!prepared.ok) return
  assert.equal(prepared.request.body.origin, 'LHR')
  assert.equal(prepared.request.body.destination, 'CDG')
  assert.equal(prepared.request.routeLabel, 'Лондон — Хитроу → Париж — Шарль-де-Голль')
})

test('prepares one-way request using only selected airport codes and existing filters', () => {
  const prepared = prepareFareSearch({ ...base, direct: true, maxPrice: '5000' }, now)
  assert.equal(prepared.ok, true)
  if (!prepared.ok) return
  assert.equal(prepared.request.endpoint, '/api/fares/one-way')
  assert.deepEqual(prepared.request.body, {
    origin: 'SVO', destination: 'LED', departure_date: '2026-11-15',
    market: 'RU', direct: true, max_price: 5000,
  })
  assert.equal(prepared.request.routeLabel, 'Москва — Шереметьево → Санкт-Петербург — Пулково')
})

test('rejects unconfirmed, edited, and unknown airports', () => {
  for (const origin of [
    { text: 'Москва', selected: null },
    { text: 'SVO', selected: null },
    { text: 'Москва', selected: airports[0] },
    chosen({ city: 'Москва', airport: 'Несуществующий', code: 'ZZZ' }),
  ]) {
    const prepared = prepareFareSearch({ ...base, origin }, now)
    assert.equal(prepared.ok, false)
    if (!prepared.ok) assert.equal(prepared.errors.origin, 'Выберите аэропорт из списка.')
  }
})

test('allows two airports in one city but rejects the same airport', () => {
  const valid = prepareFareSearch({ ...base, destination: chosen(airports[1]) }, now)
  assert.equal(valid.ok, true)
  const invalid = prepareFareSearch({ ...base, destination: chosen(airports[0]) }, now)
  assert.equal(invalid.ok, false)
  if (!invalid.ok) assert.match(invalid.errors.form, /должны отличаться/)
})

test('round-trip preserves return date and rejects invalid dates or price', () => {
  const valid = prepareFareSearch({ ...base, roundTrip: true, returnDate: '2026-11-20' }, now)
  assert.equal(valid.ok, true)
  if (valid.ok) {
    assert.equal(valid.request.endpoint, '/api/fares/round-trip')
    assert.equal(valid.request.body.return_date, '2026-11-20')
  }
  for (const input of [
    { departureDate: '2026-02-30' },
    { departureDate: '2026-10-28' },
    { roundTrip: true, returnDate: '2026-11-14' },
    { maxPrice: '0' },
  ]) {
    assert.equal(prepareFareSearch({ ...base, ...input }, now).ok, false)
  }
})

test('POST makes one request and forwards string service errors', async () => {
  const prepared = prepareFareSearch(base, now)
  assert.equal(prepared.ok, true)
  if (!prepared.ok) return
  const calls = []
  const fetcher = async (...args) => {
    calls.push(args)
    return new Response(JSON.stringify({ itineraries: [] }), { status: 200 })
  }
  const result = await postFareSearch(prepared.request, fetcher)
  assert.deepEqual(result, { itineraries: [] })
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], '/api/fares/one-way')
  assert.equal(JSON.parse(calls[0][1].body).origin, 'SVO')

  await assert.rejects(
    postFareSearch(prepared.request, async () => new Response(JSON.stringify({ detail: 'Ошибка сервиса.' }), { status: 503 })),
    /Ошибка сервиса/,
  )
  await assert.rejects(
    postFareSearch(prepared.request, async () => { throw new Error('offline') }),
    /Не удалось выполнить поиск/,
  )
  await assert.rejects(
    postFareSearch(prepared.request, async () => new Response(JSON.stringify({ detail: [] }), { status: 422 })),
    /Проверьте маршрут и даты поиска/,
  )
  await assert.rejects(
    postFareSearch(prepared.request, async () => new Response(JSON.stringify({ detail: [] }), { status: 503 })),
    /Не удалось выполнить поиск/,
  )
  await assert.rejects(
    postFareSearch(prepared.request, async () => new Response('broken JSON', { status: 200 })),
    /Не удалось выполнить поиск/,
  )
})
